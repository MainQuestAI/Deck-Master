"""Context Pack import for Deck Master v0.9.

Accepts legacy ``deck_context_pack.v1`` and version-bound ``deck_context_pack.v2``.
For v2, based_on.input_fingerprint is SHA256 of UTF-8 bytes from
json.dumps(based_on.input_refs, sort_keys=True) (Python default separators and
ASCII escaping). Each source origin/hash must occur in that ordered refs list.
A full extraction requires real source bytes and a nonempty host snapshot;
the snapshot is copied into the same immutable revision as the manifest.
Legacy imports lacking attested coverage remain legacy_unknown, never full.
A partial web research excerpt may be upgraded using capture_supersedes_sha256,
the exact original URL and a complete actual host capture. The original excerpt
and provenance remain in research_excerpt_capture; this does not repeat research.
External Agents produce a Context Pack JSON; Deck Master validates and
imports it into a run's ``context_manifest.json``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event
from runtime.run_state import (
    CONTEXT_MANIFEST_NAME,
    RunStateError,
    assert_external_result_matches_run,
    ensure_run_dirs,
    read_json,
    write_json,
)
from runtime.workspace_resolver import resolve_workspace_for_run
from workspace.foundation import MANIFEST_NAME

SCHEMA_VERSION = "deck_context_pack.v1"

VALID_PUBLICATION_STATUS = {"safe_to_use", "internal_only", "needs_redaction", "unknown"}
VALID_SENSITIVITY = {"normal", "sensitive", "high"}


class ContextPackError(ValueError):
    """Raised when a context pack is invalid or import fails."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def validate_context_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Validate a context pack against deck_context_pack.v1.

    Returns ``{"valid": True, "warnings": [...]}`` on success.
    Returns ``{"valid": False, "errors": [...], "warnings": [...]}`` on failure.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(pack, dict):
        return {"valid": False, "errors": ["Pack must be a JSON object."], "warnings": []}

    from context_intake.reading import reading_errors
    schema = pack.get("schema_version")
    if schema not in (SCHEMA_VERSION, "deck_context_pack.v2"):
        errors.append(
            f"schema_version must be '{SCHEMA_VERSION}', got '{schema}'."
        )

    run_id = pack.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required and must be a non-empty string.")

    if schema == "deck_context_pack.v2":
        import jsonschema
        from native_pptx.contracts import SCHEMA_DIR
        contract = json.loads((SCHEMA_DIR / "context-pack.v2.schema.json").read_text())
        errors.extend(error.message for error in jsonschema.Draft202012Validator(contract).iter_errors(pack))
    if schema == "deck_context_pack.v2" and not errors:
        import hashlib
        refs = pack["based_on"]["input_refs"]
        expected = hashlib.sha256(json.dumps(refs, sort_keys=True).encode()).hexdigest()
        if pack["based_on"]["input_fingerprint"] != expected:
            errors.append("based_on input fingerprint does not match ordered input refs")
        for source in pack["sources"]:
            if {"ref":source["origin_ref"], "sha256":source["file_sha256"]} not in refs:
                errors.append("source is not bound by based_on input refs")
    sources = pack.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array.")
        sources = []

    seen_source_ids: set[str] = set()
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{i}] must be an object.")
            continue

        errors.extend(f"sources[{i}]: {error}" for error in reading_errors(source))
        sid = source.get("source_id")
        if not sid or not isinstance(sid, str):
            errors.append(f"sources[{i}].source_id is required.")
        elif sid in seen_source_ids:
            errors.append(f"Duplicate source_id: '{sid}'.")
        else:
            seen_source_ids.add(str(sid))

        sens = source.get("sensitivity", "normal")
        if sens not in VALID_SENSITIVITY:
            errors.append(
                f"sources[{i}].sensitivity must be one of {sorted(VALID_SENSITIVITY)}, got '{sens}'."
            )

        candidates = source.get("evidence_candidates", [])
        if not isinstance(candidates, list):
            errors.append(f"sources[{i}].evidence_candidates must be an array.")
            continue

        seen_ev_ids: set[str] = set()
        for j, ev in enumerate(candidates):
            if not isinstance(ev, dict):
                errors.append(f"sources[{i}].evidence_candidates[{j}] must be an object.")
                continue

            eid = ev.get("evidence_id")
            if not eid or not isinstance(eid, str):
                errors.append(f"sources[{i}].evidence_candidates[{j}].evidence_id is required.")
            elif eid in seen_ev_ids:
                errors.append(
                    f"Duplicate evidence_id '{eid}' in source '{sid}'."
                )
            else:
                seen_ev_ids.add(str(eid))

            pub = ev.get("publication_status", "unknown")
            if pub not in VALID_PUBLICATION_STATUS:
                errors.append(
                    f"sources[{i}].evidence_candidates[{j}].publication_status "
                    f"must be one of {sorted(VALID_PUBLICATION_STATUS)}, got '{pub}'."
                )

            ev_sens = ev.get("sensitivity", "normal")
            if ev_sens not in VALID_SENSITIVITY:
                errors.append(
                    f"sources[{i}].evidence_candidates[{j}].sensitivity "
                    f"must be one of {sorted(VALID_SENSITIVITY)}, got '{ev_sens}'."
                )

            if ev_sens == "high" or sens == "high":
                warnings.append(
                    f"Source '{sid}' evidence '{eid}' has high sensitivity — "
                    "will be blocked from client export."
                )

    global_constraints = pack.get("global_constraints", [])
    if not isinstance(global_constraints, list):
        errors.append("global_constraints must be an array.")

    result: dict[str, Any] = {"valid": len(errors) == 0, "warnings": warnings}
    if errors:
        result["errors"] = errors
    return result


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pack_id(pack: dict[str, Any]) -> str:
    """Derive a stable pack id from run_id + timestamp or hash."""
    run_id = str(pack.get("run_id", "unknown"))
    created = pack.get("created_at", "")
    if created:
        safe = re.sub(r"[^a-zA-Z0-9]", "", created)[:20]
        return f"{run_id}_{safe}"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{run_id}_{stamp}"


def _source_to_manifest_entry(source: dict[str, Any]) -> dict[str, Any]:
    """Convert a context pack source into a context_manifest source entry."""
    from context_intake.reading import preserved_reading
    candidates = source.get("evidence_candidates", [])
    # Aggregate publication status: if any candidate is needs_redaction or
    # internal_only, mark the source accordingly.
    pub_statuses = [
        c.get("publication_status", "unknown") for c in candidates if isinstance(c, dict)
    ]
    if "needs_redaction" in pub_statuses:
        agg_pub = "needs_redaction"
    elif "internal_only" in pub_statuses:
        agg_pub = "internal_only"
    elif all(s == "safe_to_use" for s in pub_statuses) and pub_statuses:
        agg_pub = "safe_to_use"
    else:
        agg_pub = "unknown"

    sensitivities = [source.get("sensitivity", "normal")] + [
        c.get("sensitivity", "normal") for c in candidates if isinstance(c, dict)
    ]
    agg_sens = "high" if "high" in sensitivities else (
        "sensitive" if "sensitive" in sensitivities else "normal"
    )

    return {
        "reading": preserved_reading(source),
        **{key: source[key] for key in ("sha256", "file_sha256", "extraction", "critical") if key in source},
        "source_id": source.get("source_id", ""),
        "source_type": source.get("source_type", ""),
        "origin_type": source.get("origin_type", ""),
        "origin_path": source.get("origin_path", source.get("origin_ref", "")),
        "title": source.get("title", ""),
        "summary": source.get("summary", ""),
        "kind": source.get("source_type", "external_agent"),
        "evidence_candidates": candidates,
        "sensitivity": agg_sens,
        "publication_status": agg_pub,
    }


def _workspace_id_for_path(path: str) -> str:
    workspace_root = Path(path).expanduser().resolve()
    manifest_path = workspace_root / MANIFEST_NAME
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            candidate = str(manifest.get("workspace_id") or "").strip()
            if candidate:
                return candidate
        except Exception:
            pass
    return f"workspace_{workspace_root.name}"


def _apply_workspace_runtime_fields(request: dict[str, Any], workspace: str, run_mode: str) -> dict[str, Any]:
    resolution = resolve_workspace_for_run(
        run_dir=".",
        request=request,
        cli_workspace=workspace,
        run_mode=run_mode,
    )
    if resolution.get("blocked"):
        reasons = "; ".join(str(reason) for reason in resolution.get("reasons", []) if reason)
        raise ContextPackError(reasons or "workspace resolution blocked")
    workspace_path = str(resolution.get("resolved_workspace") or "").strip()
    if not workspace_path:
        raise ContextPackError("workspace is required for context pack run creation")
    request["workspace"] = workspace_path
    request["workspace_id"] = _workspace_id_for_path(workspace_path)
    request["workspace_manifest_ref"] = MANIFEST_NAME
    request["workspace_resolved_from"] = str(resolution.get("resolved_from") or "")
    return request


def import_context_pack(
    run_dir: str | Path,
    pack: dict[str, Any],
    *,
    merge: bool = False,
) -> dict[str, Any]:
    """Import a validated context pack into a run.

    Args:
        run_dir: Run directory.
        pack: Context pack dict (must pass validate_context_pack first).
        merge: If True, update existing sources by source_id. If False,
               reject duplicate source_ids.

    Returns:
        Import result dict.
    """
    validation = validate_context_pack(pack)
    if not validation["valid"]:
        raise ContextPackError(
            "Invalid context pack: " + "; ".join(validation.get("errors", []))
        )

    root = ensure_run_dirs(run_dir)
    try:
        assert_external_result_matches_run(
            root,
            pack.get("run_id", ""),
            artifact_name="context pack",
        )
    except RunStateError as exc:
        raise ContextPackError(str(exc)) from exc

    manifest_path = root / CONTEXT_MANIFEST_NAME

    from workflow.actions import revision_read, revision_input_path
    with revision_read(root, fresh=True) as expected_revision:
        input_manifest_path = revision_input_path(root, manifest_path)
        # Load existing manifest or start fresh.
        if input_manifest_path.exists():
            try:
                manifest = read_json(input_manifest_path)
            except RunStateError as exc:
                raise ContextPackError(
                    f"Cannot read existing context_manifest.json: {exc}. "
                    "Import aborted — existing data preserved."
                ) from exc
        else:
            manifest = {
                "schema_version": "deck_context_manifest.v1",
                "sources": [],
                "summary": "",
                "constraints": [],
            }

    original_manifest = json.dumps(manifest, sort_keys=True)
    existing_sources: dict[str, int] = {
        s.get("source_id"): i
        for i, s in enumerate(manifest.get("sources", []))
        if isinstance(s, dict)
    }

    validation_sources = json.loads(original_manifest).get("sources", [])
    pack_sources = pack.get("sources", [])
    extraction_outputs = {}
    extraction_inputs = {}
    added: list[str] = []
    updated: list[str] = []
    rejected: list[str] = []

    for source in pack_sources:
        sid = str(source.get("source_id", ""))
        from context_intake.reading import verify_source_bytes
        existing = manifest["sources"][existing_sources[sid]] if sid in existing_sources else None
        verify_source_bytes(source, existing)
        entry = _source_to_manifest_entry(source)
        if source.get("extraction"):
            import hashlib
            snapshot = Path(source["extraction"]["snapshot_ref"]).expanduser()
            data = snapshot.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            managed = f"context_packs/extractions/{sha}.snapshot"
            extraction_outputs[managed] = data
            extraction_inputs[str(snapshot)] = sha
            entry["extraction"] = {**entry["extraction"], "snapshot_ref":managed}
            entry["reading"]["snapshot_sha256"] = sha
            for reading_range in entry["reading"]["read_ranges"]:
                reading_range["snapshot_ref"] = managed
        if existing and source.get("capture_supersedes_sha256"):
            entry["sha256"] = source["file_sha256"]
            entry["kind"] = existing["kind"]
            entry["research_excerpt_capture"] = existing.get("research_excerpt_capture") or {
                key: existing[key] for key in ("sha256", "excerpt", "reading", "provenance") if key in existing
            }
        if existing:
            # Retain local registration identity and its authorized file path.
            entry = {**existing, **entry}
        if existing == entry and merge:
            continue

        if sid in existing_sources:
            if not merge:
                rejected.append(sid)
                continue
            # Merge: replace existing entry.
            idx = existing_sources[sid]
            manifest["sources"][idx] = entry
            updated.append(sid)
        else:
            manifest["sources"].append(entry)
            existing_sources[sid] = len(manifest["sources"]) - 1
            added.append(sid)

    # Preserve global constraints.
    pack_constraints = pack.get("global_constraints", [])
    existing_constraints = manifest.get("constraints", [])
    for c in pack_constraints:
        if c not in existing_constraints:
            existing_constraints.append(c)
    manifest["constraints"] = existing_constraints
    if pack.get("conflicts"):
        conflicts = {item["conflict_id"]:item for item in manifest.get("conflicts", []) if isinstance(item,dict) and item.get("conflict_id")}
        conflicts.update({item["conflict_id"]:item for item in pack["conflicts"]})
        manifest["conflicts"] = list(conflicts.values())

    if json.dumps(manifest, sort_keys=True) == original_manifest:
        return {"status":"idempotent" if not rejected else "imported", "added":[], "updated":[], "rejected":rejected,
                "total_sources":len(manifest["sources"]), "warnings":validation.get("warnings", [])}
    from context_intake.reading import reading_blockers
    manifest["reading_coverage"] = {
        "sources_total":len(manifest["sources"]),
        "sources_full":sum(s.get("reading",{}).get("coverage")=="full" for s in manifest["sources"]),
        "unread_sources":reading_blockers(manifest),
    }
    manifest["host_extract_tasks"] = [task for task in manifest.get("host_extract_tasks", [])
                                      if any(s.get("source_id")==task.get("source_id") and s.get("reading",{}).get("coverage")!="full" for s in manifest["sources"])]
    # Commit the new Context and its source handback as one immutable revision.
    # The expected parent prevents a concurrent import from overwriting another.
    import hashlib
    from workflow.actions import create_action_envelope, stage_action_result, commit_action_result
    pack_id = _pack_id(pack)
    pack_relative = f"context_packs/{pack_id}.json"
    fingerprint = hashlib.sha256(original_manifest.encode()).hexdigest()
    action = "context_" + hashlib.sha256((fingerprint + json.dumps(pack, sort_keys=True)).encode()).hexdigest()[:32]
    envelope = create_action_envelope(action_id=action, task_id=action, scope_pages=["context"],
                                     permission="runtime", input_fingerprint=fingerprint)
    stage_action_result(root, envelope, {
        **extraction_outputs,
        CONTEXT_MANIFEST_NAME: json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        pack_relative: json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
    })
    def current_fingerprint():
        for path, expected in extraction_inputs.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:
                raise ContextPackError("Extraction snapshot changed before commit")
        for source in pack_sources:
            existing = next((s for s in validation_sources if s.get("source_id")==source.get("source_id")), None)
            verify_source_bytes(source, existing)
        return fingerprint
    commit_action_result(root, envelope, expected_revision=expected_revision,
                         current_input_fingerprint=current_fingerprint,
                         targets={CONTEXT_MANIFEST_NAME:manifest_path, pack_relative:root/pack_relative, **{name:root/name for name in extraction_outputs}})

    # Write typed event.
    run_id = str(pack.get("run_id", ""))
    append_typed_event(
        root,
        "artifact_written",
        "context_pack.imported",
        f"Context pack imported: {len(added)} added, {len(updated)} updated, {len(rejected)} rejected.",
        run_id=run_id,
        refs=[CONTEXT_MANIFEST_NAME, f"context_packs/{pack_id}.json"],
        payload={
            "pack_id": pack_id,
            "added": added,
            "updated": updated,
            "rejected": rejected,
            "merge": merge,
        },
    )

    return {
        "status": "imported",
        "pack_id": pack_id,
        "added": added,
        "updated": updated,
        "rejected": rejected,
        "total_sources": len(manifest["sources"]),
        "warnings": validation.get("warnings", []),
    }


def create_run_from_context_pack(
    workspace: str,
    pack: dict[str, Any],
    *,
    run_id: str | None = None,
    industry: str = "",
    audience: str = "client",
    runs_dir: str | Path = "runs",
) -> dict[str, Any]:
    """Create a new run from a context pack.

    Creates request.json and imports the pack into the new run.
    """
    from runtime.run_state import create_run

    validation = validate_context_pack(pack)
    if not validation["valid"]:
        raise ContextPackError(
            "Invalid context pack: " + "; ".join(validation.get("errors", []))
        )

    pack_run_id = str(pack.get("run_id", ""))
    actual_run_id = run_id or pack_run_id

    sources = pack.get("sources", [])
    first_title = ""
    for s in sources:
        if isinstance(s, dict) and s.get("title"):
            first_title = str(s["title"])
            break

    request: dict[str, Any] = {
        "project_name": first_title or actual_run_id,
        "run_id": actual_run_id,
        "run_mode": "production",
        "industry": industry,
        "audience": audience,
        "source": "context_pack",
        "context_pack_run_id": pack_run_id,
    }
    request = _apply_workspace_runtime_fields(request, workspace, "production")

    root = create_run(runs_dir, request, run_id=actual_run_id)
    result = import_context_pack(root, pack)

    return {
        "status": "created",
        "run_id": actual_run_id,
        "run_dir": str(root),
        "import": result,
    }
