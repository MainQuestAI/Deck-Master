"""Context Pack import for Deck Master v0.9.

Implements the ``deck_context_pack.v1`` Agent handoff contract.
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

    schema = pack.get("schema_version")
    if schema != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{SCHEMA_VERSION}', got '{schema}'."
        )

    run_id = pack.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required and must be a non-empty string.")

    sources = pack.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array.")
        sources = []

    seen_source_ids: set[str] = set()
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{i}] must be an object.")
            continue

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
        "source_id": source.get("source_id", ""),
        "source_type": source.get("source_type", ""),
        "origin_type": source.get("origin_type", ""),
        "origin_path": source.get("origin_path", ""),
        "title": source.get("title", ""),
        "summary": source.get("summary", ""),
        "kind": source.get("source_type", "external_agent"),
        "evidence_candidates": candidates,
        "sensitivity": agg_sens,
        "publication_status": agg_pub,
    }


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

    # Load existing manifest or start fresh.
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
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

    existing_sources: dict[str, int] = {
        s.get("source_id"): i
        for i, s in enumerate(manifest.get("sources", []))
        if isinstance(s, dict)
    }

    pack_sources = pack.get("sources", [])
    added: list[str] = []
    updated: list[str] = []
    rejected: list[str] = []

    for source in pack_sources:
        sid = str(source.get("source_id", ""))
        entry = _source_to_manifest_entry(source)

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

    # Write context_manifest.json (atomic via write_json).
    write_json(manifest_path, manifest)

    # Write pack copy.
    pack_id = _pack_id(pack)
    packs_dir = root / "context_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    write_json(packs_dir / f"{pack_id}.json", pack)

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
        "workspace": workspace,
        "industry": industry,
        "audience": audience,
        "source": "context_pack",
        "context_pack_run_id": pack_run_id,
    }

    root = create_run(runs_dir, request, run_id=actual_run_id)
    result = import_context_pack(root, pack)

    return {
        "status": "created",
        "run_id": actual_run_id,
        "run_dir": str(root),
        "import": result,
    }
