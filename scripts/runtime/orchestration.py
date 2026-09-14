from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from planning.page_tasks import build_page_tasks
from production.page_package import PagePackageIndex
from runtime.events import append_event
from runtime.import_log import append_import_log
from runtime.next_step import resolve_next_step
from runtime.render import CANONICAL_RENDER_RESULT
from runtime.run_state import REQUEST_NAME
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    ensure_run_dirs,
    load_request,
    read_json,
    write_json,
)
from runtime.run_state_resolver import resolve_run_state
from validators.companion_tools import validate_render_result


SCHEMA_VERSION = "deck_orchestration_check.v1"
PLAN_IMPORT_SCHEMA = "deck_plan_import.v1"
PAGE_PACKAGES_DIR = "page_packages"
REQUIRED_SEQUENCE = [
    REQUEST_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    CLAIM_MAP_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    PREVIEW_MANIFEST_NAME,
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _quality_reports(root: Path) -> list[str]:
    quality_dir = root / "quality_reports"
    if not quality_dir.is_dir():
        return []
    return sorted(path.name for path in quality_dir.glob("*_gate.json"))


def orchestration_check(
    run_dir: str | Path,
    *,
    cli_workspace: str | None = None,
    run_mode: str | None = None,
    dev_allow_unsetup: bool = False,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    state = resolve_run_state(
        root,
        cli_workspace=cli_workspace,
        run_mode=run_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )
    run_id = str(state.get("run_id") or root.name)

    stage = str(state.get("stage") or "")
    reasons = [entry.get("reason", "") for entry in state.get("blocked_actions", []) if entry.get("reason")]
    package_mode = (root / PAGE_PACKAGES_DIR / "index.json").exists() and bool(
        _existing_beat_page_map(root)
    )
    if stage in {"ready_for_client_export", "ready_for_benchmark"}:
        status = "ready_for_external_production"
    elif stage == "needs_draft_gate":
        status = "needs_quality_gate"
    elif stage == "needs_render":
        status = "needs_render"
    elif stage == "blocked_workspace":
        status = "blocked"
    else:
        status = "blocked"

    # A full-draft run never creates the sourcing/preview artifacts; reporting
    # them as permanently missing would misdirect repair.
    missing = [
        name
        for name in REQUIRED_SEQUENCE
        if not (root / name).exists() and not (package_mode and name in {SOURCING_PLAN_NAME, PREVIEW_MANIFEST_NAME})
    ]
    if status == "blocked":
        for name in REQUIRED_SEQUENCE:
            if name == PREVIEW_MANIFEST_NAME and state.get("stage") == "needs_preview" and name not in missing:
                continue
    quality = _quality_reports(root)
    allowed = {
        "external_generation_allowed": status == "ready_for_external_production",
        "external_review_allowed": status in {"ready_for_external_production", "blocked"},
        "client_export_allowed": status == "ready_for_external_production",
        "benchmark_rc_allowed": state.get("stage") == "ready_for_benchmark",
    }
    next_step = resolve_next_step(
        root,
        cli_workspace=cli_workspace,
        run_mode=run_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_dir": str(root),
        "status": status,
        "missing_artifacts": missing,
        "quality_reports": quality,
        "next_command": next_step.get("next_command", ""),
        "next_step_status": next_step.get("status", ""),
        "allow_external_production": status == "ready_for_external_production",
        "policy": allowed,
        "reasons": reasons,
    }
    append_event(
        root,
        "orchestration.checked",
        target=run_id,
        payload_ref="",
        data={
            "status": status,
            "missing_artifacts": missing,
            "allow_external_production": status == "ready_for_external_production",
        },
    )
    return result


def import_plan(run_dir: str | Path, input_path: str | Path, *, source: str) -> dict[str, Any]:
    if source not in {"human", "agent"}:
        raise RunStateError("--source must be 'human' or 'agent'.")

    root = ensure_run_dirs(run_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise RunStateError(f"Plan input not found: {input_file}")

    request = load_request(root)
    run_id = str(request.get("run_id") or root.name)
    title = str(request.get("project_name") or request.get("business_goal") or run_id)

    page_packages: list[dict[str, Any]] | None = None
    if input_file.suffix.lower() == ".json":
        payload = read_json(input_file)
        narrative_plan, page_tasks, page_packages = _parse_json_plan(
            payload, run_id=run_id, title=title, root=root, input_file=input_file
        )
        mode = "full_draft" if page_packages is not None else "plan"
    else:
        narrative_plan, page_tasks = _load_markdown_plan(input_file, run_id=run_id, title=title)
        mode = "plan"

    backup_dir = root / "overrides" / f"plan_{_utc_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in (NARRATIVE_PLAN_NAME, PAGE_TASKS_NAME):
        current = root / name
        if current.exists():
            shutil.copy2(current, backup_dir / name)
    if page_packages is not None:
        _backup_downstream_for_import(root, backup_dir)

    removed_pages: list[str] = []
    new_pages: list[str] = []
    changed_pages: list[str] = []
    reordered = False
    downstream: dict[str, Any] = {}
    try:
        if page_packages is not None:
            removed_pages, new_pages, changed_pages, reordered = _write_full_draft_packages(root, page_packages)
            write_json(root / PAGE_TASKS_NAME, page_tasks)
            write_json(root / NARRATIVE_PLAN_NAME, narrative_plan)
            downstream = _prune_downstream_pages(root, removed_pages, changed_pages)
        else:
            write_json(root / NARRATIVE_PLAN_NAME, narrative_plan)
            write_json(root / PAGE_TASKS_NAME, page_tasks)
    except Exception:
        _restore_plan_backup(root, backup_dir)
        raise

    append_event(
        root,
        "plan.override.imported",
        target=run_id,
        payload_ref=str(input_file),
        data={
            "source": source,
            "input": str(input_file),
            "backup_dir": str(backup_dir),
            "mode": mode,
            "beats": len(narrative_plan.get("beats", [])),
            "tasks": len(page_tasks.get("tasks", [])),
            "page_packages": len(page_packages) if page_packages is not None else 0,
            "removed_pages": removed_pages,
            "new_pages": new_pages,
            "changed_pages": changed_pages,
            "reordered": reordered,
            "downstream": downstream,
        },
    )
    result = {
        "schema_version": PLAN_IMPORT_SCHEMA,
        "status": "imported",
        "mode": mode,
        "run_id": run_id,
        "run_dir": str(root),
        "source": source,
        "input": str(input_file),
        "backup_dir": str(backup_dir),
        "beats": len(narrative_plan.get("beats", [])),
        "tasks": len(page_tasks.get("tasks", [])),
    }
    if page_packages is not None:
        result["page_packages"] = len(page_packages)
        result["removed_pages"] = removed_pages
        result["new_pages"] = new_pages
        result["changed_pages"] = changed_pages
        result["reordered"] = reordered
        result["downstream"] = downstream
    return result


def import_render_result(run_dir: str | Path, input_path: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise RunStateError(f"Render result not found: {input_file}")
    result = read_json(input_file)
    validation = validate_render_result(result)
    if not validation["valid"]:
        raise RunStateError("Invalid render result: " + "; ".join(validation["errors"]))
    request = load_request(root)
    run_id = str(request.get("run_id") or root.name)
    if str(result.get("run_id") or "") != run_id:
        raise RunStateError(f"render result run_id mismatch: got {result.get('run_id')}, expected {run_id}.")

    target = root / CANONICAL_RENDER_RESULT
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, result)
    preview_updated = _update_preview_from_render_result(root, result)
    append_import_log(
        root,
        import_type="render_result",
        source=str(result.get("tool") or "ppt-master"),
        status="accepted",
        source_path=input_file,
        canonical_refs=[str(CANONICAL_RENDER_RESULT)],
    )
    append_event(
        root,
        "external_result.imported",
        target=run_id,
        payload_ref=str(target.relative_to(root)),
        data={
            "tool": result.get("tool", "ppt-master"),
            "status": result.get("status", ""),
            "artifact_path": result.get("artifact_path", ""),
            "preview_dir": result.get("preview_dir", ""),
            "preview_manifest_updated": preview_updated,
        },
    )
    return {
        "status": "imported",
        "run_id": run_id,
        "result": str(target),
        "artifact_path": result.get("artifact_path", ""),
        "preview_dir": result.get("preview_dir", ""),
        "preview_manifest_updated": preview_updated,
    }


def _update_preview_from_render_result(root: Path, result: dict[str, Any]) -> bool:
    preview_path = root / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        return False
    preview = read_json(preview_path)
    preview["render_status"] = result.get("status", "")
    preview["final_artifact_path"] = result.get("artifact_path", "")
    preview["final_preview_dir"] = result.get("preview_dir", "")
    preview["external_render_result"] = str(CANONICAL_RENDER_RESULT)
    if result.get("page_count") is not None:
        preview["render_page_count"] = result.get("page_count")

    page_updates = result.get("page_previews", [])
    if isinstance(page_updates, list):
        for update in page_updates:
            if not isinstance(update, dict):
                continue
            key = str(update.get("page_id") or update.get("beat_id") or "")
            new_preview = str(update.get("preview_path") or "")
            if not key or not new_preview:
                continue
            preview_ref = Path(new_preview)
            if preview_ref.is_absolute() or ".." in preview_ref.parts:
                raise RunStateError(f"render preview_path must be run-relative: {new_preview}")
            for page in preview.get("pages", []):
                if not isinstance(page, dict):
                    continue
                if key in {str(page.get("page_id") or ""), str(page.get("beat_id") or "")}:
                    previous = page.get("preview_path", "")
                    if previous and previous != new_preview:
                        page["previous_preview_path"] = previous
                    page["preview_path"] = new_preview
                    page["render_status"] = result.get("status", "")
                    break

    write_json(preview_path, preview)
    return True


def _parse_json_plan(
    payload: dict[str, Any],
    *,
    run_id: str,
    title: str,
    root: Path,
    input_file: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]] | None]:
    narrative_plan = payload.get("narrative_plan", payload)
    if not isinstance(narrative_plan, dict) or not isinstance(narrative_plan.get("beats"), list):
        raise RunStateError("JSON plan must contain narrative_plan.beats or beats.")
    narrative_plan["run_id"] = run_id
    narrative_plan.setdefault("title", title)

    page_packages_raw = payload.get("page_packages")
    if page_packages_raw is None:
        page_tasks = payload.get("page_tasks")
        if not isinstance(page_tasks, dict):
            page_tasks = build_page_tasks(narrative_plan, {"run_id": run_id, "claims": []})
        page_tasks["run_id"] = run_id
        return narrative_plan, page_tasks, None

    if not isinstance(page_packages_raw, list) or not page_packages_raw:
        raise RunStateError("page_packages must be a non-empty array when provided.")

    page_packages = _prepare_full_draft_packages(
        narrative_plan,
        page_packages_raw,
        page_tasks=payload.get("page_tasks"),
        run_id=run_id,
        root=root,
        input_file=input_file,
    )
    narrative_plan["target_pages"] = len(narrative_plan["beats"])
    page_tasks = _full_draft_page_tasks(narrative_plan, payload.get("page_tasks"), run_id=run_id)
    return narrative_plan, page_tasks, page_packages


def _prepare_full_draft_packages(
    narrative_plan: dict[str, Any],
    packages_raw: list[Any],
    *,
    page_tasks: Any,
    run_id: str,
    root: Path,
    input_file: Path,
) -> list[dict[str, Any]]:
    """Validate the received full draft before anything is written.

    Page identity, page set consistency and customer-visible completeness are
    all enforced here so a rejected import leaves the run untouched and an
    accepted import can be written in one pass.
    """
    beats = narrative_plan["beats"]
    beat_ids: list[str] = []
    beat_order_by_id: dict[str, int] = {}
    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            raise RunStateError(f"narrative beat #{index} must be an object.")
        beat_id = str(beat.get("beat_id") or "").strip()
        if not beat_id:
            raise RunStateError(
                f"narrative beat #{index} is missing beat_id; full-draft import requires stable page identity."
            )
        if not _safe_identifier(beat_id):
            raise RunStateError(f"narrative beat_id is not a safe identifier: {beat_id!r}")
        if beat_id in beat_order_by_id:
            raise RunStateError(f"duplicate narrative beat_id: {beat_id}")
        if not str(beat.get("page_title") or beat.get("title") or "").strip():
            raise RunStateError(f"narrative beat {beat_id} is missing page_title.")
        # The beats array is the deck order; order is derived, never re-template.
        beat["order"] = index
        beat_ids.append(beat_id)
        beat_order_by_id[beat_id] = index

    existing_map = _existing_beat_page_map(root)
    page_id_by_beat: dict[str, str] = {}
    taken: set[str] = set()
    for beat_id in beat_ids:
        page_id = existing_map.get(beat_id) or beat_id
        if page_id in taken:
            raise RunStateError(f"page_id collision for beat {beat_id}: {page_id}")
        page_id_by_beat[beat_id] = page_id
        taken.add(page_id)

    from production.page_package import normalize_package_for_import

    packages: list[dict[str, Any]] = []
    beats_covered: set[str] = set()
    for index, raw in enumerate(packages_raw, start=1):
        if not isinstance(raw, dict):
            raise RunStateError(f"page_packages[{index}] must be an object.")
        beat_id = str(raw.get("beat_id") or "").strip()
        if not beat_id:
            raise RunStateError(
                f"page_packages[{index}] is missing beat_id; every imported page must map to a narrative beat."
            )
        if beat_id not in beat_order_by_id:
            raise RunStateError(
                f"page_packages[{index}] references unknown beat_id {beat_id!r}; unknown pages are not silently skipped."
            )
        if beat_id in beats_covered:
            raise RunStateError(f"page_packages[{index}] duplicates beat_id {beat_id}.")
        beats_covered.add(beat_id)
        customer_visible = raw.get("customer_visible")
        if not isinstance(customer_visible, dict) or not _has_body_text(customer_visible):
            raise RunStateError(
                f"page package for {beat_id} has no complete customer-visible content; "
                "customer_visible.title and body_blocks are required."
            )
        packages.append(
            normalize_package_for_import(
                raw,
                run_id=run_id,
                beat_id=beat_id,
                page_id=page_id_by_beat[beat_id],
                order=beat_order_by_id[beat_id],
                input_artifacts=[{"path": str(input_file), "kind": "plan_import"}],
            )
        )

    missing = [beat_id for beat_id in beat_ids if beat_id not in beats_covered]
    if missing:
        raise RunStateError(f"full draft is missing page packages for beats: {missing}")

    _assign_evidence_ids(packages)
    for package in packages:
        _assert_page_package_contract(package)
    _check_citations_against_sources(root, packages)
    return packages


def _assign_evidence_ids(packages: list[dict[str, Any]]) -> None:
    """Give every imported citation a globally unique evidence_id.

    The builder's evidence ledger references evidence ids across pages, so a
    draft whose pages cite sources without ids would collide on the per-page
    E001 fallback at build time. Authors who supplied explicit ids keep them;
    collisions after assignment are reported, not silently renumbered.
    """
    assigned: dict[str, str] = {}
    for package in packages:
        page_id = str(package.get("page_id") or "")
        order = int(package.get("order") or 0)
        page_ids: set[str] = {
            str(item.get("evidence_id") or item.get("citation_id") or item.get("id") or "").strip()
            for key in ("evidence_bindings", "citations")
            for item in (package.get(key) or [])
            if isinstance(item, dict)
        }
        page_ids.discard("")
        counter = 0
        for key in ("evidence_bindings", "citations"):
            items = package.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                evidence_id = str(
                    item.get("evidence_id") or item.get("citation_id") or item.get("id") or ""
                ).strip()
                if not evidence_id:
                    counter += 1
                    while f"E{order:02d}{counter:02d}" in page_ids:
                        counter += 1
                    evidence_id = f"E{order:02d}{counter:02d}"
                    page_ids.add(evidence_id)
                    item["evidence_id"] = evidence_id
                if evidence_id in assigned and assigned[evidence_id] != page_id:
                    raise RunStateError(
                        f"duplicate evidence_id {evidence_id} on pages {assigned[evidence_id]} and {page_id}; "
                        "evidence ids must be globally unique across the draft."
                    )
                assigned[evidence_id] = page_id


def _full_draft_page_tasks(
    narrative_plan: dict[str, Any],
    page_tasks: Any,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Keep agent-provided page tasks 1:1 with the received beats, or derive them.

    Received tasks keep their planning content (claims, source links, generation
    requirements); only order is re-synced to the received beats array.
    """
    beat_ids = [str(beat.get("beat_id") or "") for beat in narrative_plan["beats"] if isinstance(beat, dict)]
    if isinstance(page_tasks, dict) and isinstance(page_tasks.get("tasks"), list):
        tasks = page_tasks["tasks"]
        task_by_beat: dict[str, dict[str, Any]] = {}
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                raise RunStateError(f"page_tasks.tasks[{index}] must be an object.")
            beat_id = str(task.get("beat_id") or "").strip()
            if not beat_id or beat_id not in beat_ids:
                raise RunStateError(
                    f"page_tasks.tasks[{index}] references unknown beat_id {beat_id!r}; "
                    "page_tasks must cover exactly the narrative beats."
                )
            if beat_id in task_by_beat:
                raise RunStateError(f"page_tasks.tasks[{index}] duplicates beat_id {beat_id}.")
            task_by_beat[beat_id] = task
        missing = [beat_id for beat_id in beat_ids if beat_id not in task_by_beat]
        if missing:
            raise RunStateError(f"page_tasks is missing tasks for beats: {missing}")
        order_by_beat = {
            str(beat.get("beat_id") or ""): int(beat.get("order") or 0)
            for beat in narrative_plan["beats"]
            if isinstance(beat, dict)
        }
        for beat_id, task in task_by_beat.items():
            task["order"] = order_by_beat[beat_id]
        page_tasks["run_id"] = run_id
        return page_tasks
    return build_page_tasks(narrative_plan, {"run_id": run_id, "claims": []})


def _safe_identifier(value: str) -> bool:
    if not value or "/" in value or "\\" in value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _has_body_text(customer_visible: dict[str, Any]) -> bool:
    if not str(customer_visible.get("title") or "").strip():
        return False
    blocks = customer_visible.get("body_blocks")
    if not isinstance(blocks, list) or not blocks:
        return False
    for block in blocks:
        if isinstance(block, dict):
            if any(str(value).strip() for value in block.values() if isinstance(value, (str, int, float))):
                return True
        elif isinstance(block, str) and block.strip():
            return True
    return False


def _existing_beat_page_map(root: Path) -> dict[str, str]:
    """beat_id -> page_id for import-written packages already on the run."""
    directory = root / PAGE_PACKAGES_DIR
    if not directory.is_dir():
        return {}
    mapping: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(package, dict) or package.get("legacy_inferred"):
            continue
        beat_id = str(package.get("beat_id") or "").strip()
        page_id = str(package.get("page_id") or "").strip()
        if beat_id and page_id:
            mapping[beat_id] = page_id
    return mapping


def _assert_page_package_contract(package: dict[str, Any]) -> None:
    try:
        from high_density.contracts import ContractError, assert_valid
    except ImportError as exc:  # pragma: no cover - declared runtime dependency
        raise RunStateError(
            "page package contract validation is unavailable; install the deck-master runtime dependencies"
        ) from exc  # lazy: the high_density package pulls the builder runtime
    try:
        assert_valid("page_package", package)
    except ContractError as exc:
        raise RunStateError(f"page package {package.get('page_id')} invalid: {exc}") from exc


def _check_citations_against_sources(root: Path, packages: list[dict[str, Any]]) -> None:
    """Every citation must resolve to a source the run actually has.

    Citations are free-form objects; any string value that matches a manifest
    source name/path/fingerprint (substring either way) counts as resolved.
    A citation that references nothing identifiable is reported, not skipped.
    """
    manifest = _safe_read_context_manifest(root)
    if manifest is None:
        return
    source_identities = _context_source_identities(manifest)
    if not source_identities:
        return
    unknown: list[str] = []
    for package in packages:
        for index, citation in enumerate(package.get("citations") or [], start=1):
            if not isinstance(citation, dict):
                continue
            values = [str(value) for value in citation.values() if isinstance(value, (str, int, float))]
            if not any(_matches_identity(str(value), source_identities) for value in values):
                unknown.append(f"{package.get('page_id')} citation#{index}")
    if unknown:
        raise RunStateError(
            "citations reference sources missing from context_manifest.json: " + ", ".join(unknown)
        )


def _safe_read_context_manifest(root: Path) -> dict[str, Any] | None:
    path = root / CONTEXT_MANIFEST_NAME
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _context_source_identities(manifest: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    for key in ("sources", "local_sources", "files", "items"):
        entries = manifest.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for field in ("name", "path", "sha256", "source_id", "id", "title"):
                value = str(entry.get(field) or "").strip()
                if value:
                    identities.add(value)
    return identities


def _matches_identity(value: str, identities: set[str]) -> bool:
    if not value.strip():
        return False
    for identity in identities:
        if identity in value or value in identity:
            return True
    return False


def _write_full_draft_packages(
    root: Path,
    packages: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str], bool]:
    """Write the received packages and retire removed pages from the active set.

    Returns (removed_pages, new_pages, changed_pages, reordered). Old copies
    were already copied into the import backup before this runs, so history
    survives the deletion.
    """
    directory = root / PAGE_PACKAGES_DIR
    old_by_beat: dict[str, dict[str, Any]] = {}
    old_orders: dict[str, int] = {}
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            if path.name == "index.json":
                continue
            try:
                package = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(package, dict) or package.get("legacy_inferred"):
                continue
            beat_id = str(package.get("beat_id") or "").strip()
            if not beat_id:
                continue
            old_by_beat[beat_id] = package
            old_orders[beat_id] = int(package.get("order") or 0)

    new_by_beat = {str(package["beat_id"]): package for package in packages}
    removed = sorted(
        str(package.get("page_id") or beat_id)
        for beat_id, package in old_by_beat.items()
        if beat_id not in new_by_beat
    )
    new_pages = sorted(beat_id for beat_id in new_by_beat if beat_id not in old_by_beat)
    changed = sorted(
        str(new_by_beat[beat_id].get("page_id") or beat_id)
        for beat_id in new_by_beat
        if beat_id in old_by_beat
        and old_by_beat[beat_id].get("source_fingerprint") != new_by_beat[beat_id].get("source_fingerprint")
    )
    reordered = any(
        beat_id in old_orders and old_orders[beat_id] != int(new_by_beat[beat_id].get("order") or 0)
        for beat_id in new_by_beat
    )

    index = PagePackageIndex(root)
    for package in packages:
        index.write(package)
    for beat_id, package in old_by_beat.items():
        if beat_id not in new_by_beat:
            index.remove(str(package.get("page_id") or ""))
    return removed, new_pages, changed, reordered


def _backup_downstream_for_import(root: Path, backup_dir: Path) -> None:
    for name in (SOURCING_PLAN_NAME, PREVIEW_MANIFEST_NAME, "generation_session.json"):
        current = root / name
        if current.exists():
            shutil.copy2(current, backup_dir / name)
    packages_dir = root / PAGE_PACKAGES_DIR
    if packages_dir.is_dir():
        shutil.copytree(packages_dir, backup_dir / PAGE_PACKAGES_DIR, dirs_exist_ok=True)
    generation_index = root / "generation_tasks" / "index.json"
    if generation_index.exists():
        (backup_dir / "generation_tasks").mkdir(exist_ok=True)
        shutil.copy2(generation_index, backup_dir / "generation_tasks" / "index.json")


def _restore_plan_backup(root: Path, backup_dir: Path) -> None:
    """Best-effort rollback so an interrupted import never looks like current state."""
    watched = (NARRATIVE_PLAN_NAME, PAGE_TASKS_NAME, SOURCING_PLAN_NAME, PREVIEW_MANIFEST_NAME, PAGE_PACKAGES_DIR)
    backed_up = {item.name for item in backup_dir.iterdir()}
    for name in watched:
        if name in backed_up:
            continue
        path = root / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
    for item in backup_dir.iterdir():
        target = root / item.name
        try:
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        except Exception:
            continue


def _prune_downstream_pages(root: Path, removed_pages: list[str], changed_pages: list[str]) -> dict[str, Any]:
    """Drop removed/content-changed pages from derived downstream artifacts.

    Unaffected pages keep their decisions and previews. Derived artifacts are
    re-created by their own commands, so pruning is best-effort per artifact
    and any failure is reported instead of silently kept.
    """
    affected: set[str] = set()
    for value in list(removed_pages) + list(changed_pages):
        affected.add(str(value))
    if not affected:
        return {}
    summary: dict[str, Any] = {}
    summary.update(_prune_pages_in_artifact(root / SOURCING_PLAN_NAME, "pages", affected))
    summary.update(_prune_pages_in_artifact(root / PREVIEW_MANIFEST_NAME, "pages", affected))
    summary.update(_prune_generation_tasks(root, affected))
    return {key: value for key, value in summary.items() if value}


def _prune_pages_in_artifact(path: Path, key: str, affected: set[str]) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
        pages = payload.get(key)
        if not isinstance(pages, list):
            return {}
        kept = [
            page
            for page in pages
            if not (isinstance(page, dict) and ({str(page.get("page_id") or ""), str(page.get("beat_id") or "")} & affected))
        ]
        if len(kept) == len(pages):
            return {}
        if kept:
            payload[key] = kept
            write_json(path, payload)
        else:
            path.unlink()
        return {path.name: "pruned"}
    except Exception:
        return {path.name: "prune_failed"}


def _prune_generation_tasks(root: Path, affected: set[str]) -> dict[str, str]:
    index_path = root / "generation_tasks" / "index.json"
    if not index_path.exists():
        return {}
    try:
        payload = read_json(index_path)
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            return {}
        kept = [
            task
            for task in tasks
            if not (
                isinstance(task, dict)
                and (
                    {str(task.get("page_id") or ""), str(task.get("beat_id") or ""), str(task.get("page_task_id") or "")}
                    & affected
                )
            )
        ]
        if len(kept) == len(tasks):
            return {}
        if kept:
            payload["tasks"] = kept
            write_json(index_path, payload)
        else:
            index_path.unlink()
            session = root / "generation_session.json"
            if session.exists():
                session.unlink()
        return {"generation_tasks/index.json": "pruned"}
    except Exception:
        return {"generation_tasks/index.json": "prune_failed"}


def _load_markdown_plan(input_file: Path, *, run_id: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = input_file.read_text(encoding="utf-8")
    headings = _extract_page_headings(text)
    if not headings:
        raise RunStateError("Markdown plan must contain page headings like '## 01 ...'.")

    beats: list[dict[str, Any]] = []
    for index, heading in enumerate(headings, start=1):
        role = _infer_role(index, len(headings), heading)
        beat_id = f"beat_{index:02d}_{role}"
        beats.append(
            {
                "beat_id": beat_id,
                "role": role,
                "title": heading,
                "generation_brief": f"根据人工校准规划生成页面：{heading}",
                "reuse_query": heading,
            }
        )

    narrative_plan = {
        "run_id": run_id,
        "title": title,
        "target_pages": len(beats),
        "audience": "client",
        "industry": "",
        "density": "high",
        "roles": [beat["role"] for beat in beats],
        "beats": beats,
        "gaps": [],
    }
    return narrative_plan, build_page_tasks(narrative_plan, {"run_id": run_id, "claims": []})


def _extract_page_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        label = stripped[3:].strip()
        if re.match(r"^(第?\s*)?\d{1,2}[\.、｜|:\s-]", label) or "页" in label[:8]:
            headings.append(label)
    return headings


def _infer_role(index: int, total: int, title: str) -> str:
    value = title.lower()
    if index == 1:
        return "opener"
    if index == total:
        return "cta"
    if any(token in title for token in ("背景", "问题", "挑战", "监管")):
        return "problem"
    if any(token in title for token in ("架构", "底座", "系统", "流程")):
        return "architecture"
    if any(token in title for token in ("价值", "收益", "验收")):
        return "roi"
    if "case" in value or "案例" in title:
        return "case"
    return "solution"
