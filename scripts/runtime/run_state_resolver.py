from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.artifact_validator import validate_artifact_manifest
from runtime.builder_backend import builder_backend_status, production_requires_builder_backend
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    REQUEST_NAME,
    SOURCING_PLAN_NAME,
    read_json,
)
from runtime.render import CANONICAL_RENDER_RESULT, LEGACY_RENDER_RESULTS
from runtime.setup_status import setup_readiness
from runtime.skill_route import route_for_stage
from runtime.workspace_resolver import resolve_workspace_for_run

SCHEMA_VERSION = "deck_run_state.v1"

GENERATION_SESSION_NAME = "generation_session.json"
GENERATION_TASK_INDEX = Path("generation_tasks") / "index.json"
QUALITY_DIR = "quality_reports"
BUILD_MANIFEST = Path("build") / "build_manifest.json"
ARTIFACT_MANIFEST = Path("build") / "artifact_manifest.json"



def _safe_read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _file_mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _read_generation_status(root: Path) -> tuple[str, dict[str, Any] | None]:
    session = _safe_read(root / GENERATION_SESSION_NAME)
    if not session:
        return "", None
    status = str(session.get("status") or "").strip().lower()
    return status or "unknown", session


def _generation_tasks_count(root: Path) -> int:
    index_path = root / GENERATION_TASK_INDEX
    payload = _safe_read(index_path)
    if not payload:
        return 0
    tasks = payload.get("tasks")
    return len(tasks) if isinstance(tasks, list) else 0


def _run_mode_for_root(root: Path) -> str:
    request = _safe_read(root / REQUEST_NAME) or {}
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


def _render_result_present(root: Path) -> bool:
    if _safe_read(root / CANONICAL_RENDER_RESULT):
        return True
    return any(_safe_read(root / legacy) for legacy in LEGACY_RENDER_RESULTS)


def _read_render_result(root: Path) -> tuple[Path, dict[str, Any] | None, str]:
    render_result_path = root / CANONICAL_RENDER_RESULT
    render_result = _safe_read(render_result_path)
    if render_result:
        return render_result_path, render_result, "canonical"
    for legacy in LEGACY_RENDER_RESULTS:
        legacy_path = root / legacy
        legacy_result = _safe_read(legacy_path)
        if legacy_result:
            return legacy_path, legacy_result, "legacy"
    return render_result_path, None, "missing"


def _build_status(root: Path) -> dict[str, Any]:
    build_manifest_path = root / BUILD_MANIFEST
    artifact_manifest_path = root / ARTIFACT_MANIFEST
    build_manifest = _safe_read(build_manifest_path)
    artifact_manifest = _safe_read(artifact_manifest_path)
    render_result_path, render_result, render_source = _read_render_result(root)
    artifacts = []
    if artifact_manifest and isinstance(artifact_manifest.get("artifacts"), list):
        artifacts = [item for item in artifact_manifest["artifacts"] if isinstance(item, dict)]
    elif render_result and isinstance(render_result.get("artifacts"), list):
        artifacts = [item for item in render_result["artifacts"] if isinstance(item, dict)]
    fixture_policy = _run_mode_for_root(root) in {"fixture", "dev"}
    artifact_validation = (
        validate_artifact_manifest(
            root,
            artifact_manifest,
            expected_source_fingerprint=str(artifact_manifest.get("source_fingerprint") or ""),
            allow_contract_smoke=fixture_policy,
            allow_non_client_deliverable=fixture_policy,
        )
        if artifact_manifest
        else {}
    )
    invalid_artifacts = [
        str(item.get("artifact_id") or item.get("path") or "artifact")
        for item in artifacts
        if str(item.get("validation_status") or "validated") != "validated"
    ]
    if artifact_validation and not artifact_validation.get("valid"):
        invalid_artifacts.extend(
            str(item.get("artifact_id") or item.get("path") or "artifact")
            for item in artifact_validation.get("artifacts", [])
            if isinstance(item, dict) and not item.get("valid")
        )
    if render_result:
        status = str(render_result.get("status") or "completed")
    elif artifact_manifest:
        status = "built"
    elif build_manifest:
        status = "prepared"
    else:
        status = "missing"
    if artifact_validation and not artifact_validation.get("valid"):
        status = "invalid"
    return {
        "status": status,
        "build_manifest": str(BUILD_MANIFEST) if build_manifest else "",
        "artifact_manifest": str(ARTIFACT_MANIFEST) if artifact_manifest else "",
        "render_result": str(render_result_path.relative_to(root)) if render_result else "",
        "render_source": render_source,
        "source_fingerprint": str(
            (render_result or {}).get("source_fingerprint")
            or (artifact_manifest or {}).get("source_fingerprint")
            or (build_manifest or {}).get("source_fingerprint")
            or ""
        ),
        "artifact_count": len(artifacts),
        "invalid_artifacts": invalid_artifacts,
        "validation": artifact_validation,
        "editability": sorted(set(str(item.get("editability") or "") for item in artifacts if item.get("editability"))),
        "formats": sorted(set(str(item.get("kind") or "") for item in artifacts if item.get("kind"))),
        "artifact_path": str((render_result or {}).get("artifact_path") or ""),
        "page_count": int((render_result or {}).get("page_count") or (artifact_manifest or {}).get("page_count") or 0),
    }


def _pick_first_draft_gate(root: Path) -> dict[str, Any] | None:
    quality_dir = root / QUALITY_DIR
    if not quality_dir.is_dir():
        return None
    for filename in ("draft_v2_gate.json", "draft_gate.json"):
        payload = _safe_read(quality_dir / filename)
        if payload:
            payload["_report_file"] = filename
            payload["_report_path"] = str(quality_dir / filename)
            return payload
    return None


def _draft_gate_blocks(gate: dict[str, Any] | None) -> tuple[bool, str]:
    if not gate:
        return True, "missing draft gate"

    status = str(gate.get("status") or "").strip().lower()
    if status == "pass" or status == "pass_with_warning" or status == "":
        if gate.get("blocks_delivery"):
            return True, str(gate.get("blocking_issue") or "draft gate blocks delivery")
        return False, ""

    if status == "pass_with_override":
        return False, ""

    if gate.get("blocks_delivery"):
        return True, str(gate.get("blocking_issue") or "draft gate blocks delivery")

    return True, f"draft gate status is {status}"


def _gate_timestamp(gate: dict[str, Any] | None) -> datetime | None:
    if not gate:
        return None
    parsed = _parse_timestamp(gate.get("created_at"))
    if parsed:
        return parsed
    report_path = gate.get("_report_path")
    if report_path:
        return _file_mtime(Path(str(report_path)))
    return None


def _quality_required_timestamp(root: Path, session: dict[str, Any] | None) -> datetime | None:
    parsed = _parse_timestamp((session or {}).get("quality_required_at"))
    if parsed:
        return parsed
    return _file_mtime(root / GENERATION_SESSION_NAME)


def _fresh_draft_gate_for_generation(root: Path, session: dict[str, Any] | None) -> tuple[bool, str]:
    gate = _pick_first_draft_gate(root)
    blocked, reason = _draft_gate_blocks(gate)
    if blocked:
        return False, reason
    required_at = _quality_required_timestamp(root, session)
    if not required_at:
        return False, "generation session is missing quality_required_at"
    gate_at = _gate_timestamp(gate)
    if not gate_at:
        return False, "draft gate is missing created_at"
    if gate_at < required_at:
        return False, "draft gate is stale for current generation results"
    return True, ""


def _normalize_review_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"approved", "keep"}:
        return "approved"
    if status in {"rejected", "reject", "replace"}:
        return "rejected"
    if status in {"needs_review", "needs_evidence", "missing", "pending", "manual_placeholder"}:
        return "pending"
    if not status:
        return "pending"
    return "pending"


def _review_summary_from_manifest(preview_manifest: dict[str, Any], page_tasks: dict[str, Any]) -> dict[str, Any]:
    pages = preview_manifest.get("pages")
    page_list = pages if isinstance(pages, list) else []
    summary = {
        "status": "",
        "total_pages": len(page_list),
        "approved_count": 0,
        "rejected_count": 0,
        "pending_count": 0,
        "raw_statuses": [],
    }

    manifest_status = str(preview_manifest.get("review_status") or "").strip().lower()
    if manifest_status in {"needs_review", "needs_evidence", "pending", "missing"}:
        summary["status"] = "needs_review"
        summary["pending_count"] = max(1, len(page_list))
        summary["raw_statuses"].append(manifest_status)
        return summary
    if manifest_status == "approved" and not page_list:
        summary["status"] = "review_complete"
        summary["approved_count"] = 1
        summary["raw_statuses"].append(manifest_status)
        return summary

    for page in page_list:
        if not isinstance(page, dict):
            continue
        raw_status = page.get("review_status")
        if raw_status in (None, ""):
            raw_status = page.get("decision")
        normalized = _normalize_review_status(raw_status)
        summary["raw_statuses"].append(str(raw_status or ""))
        if normalized == "approved":
            summary["approved_count"] += 1
        elif normalized == "rejected":
            summary["rejected_count"] += 1
        else:
            summary["pending_count"] += 1

    if summary["pending_count"]:
        summary["status"] = "needs_review"
    elif summary["approved_count"]:
        summary["status"] = "review_complete"
    elif page_list:
        summary["status"] = "needs_review"
    else:
        task_status = str(page_tasks.get("review_status") or "").strip().lower() if isinstance(page_tasks, dict) else ""
        if task_status in {"approved", "review_complete"}:
            summary["status"] = "review_complete"
            summary["approved_count"] = 1
        elif task_status:
            summary["status"] = "needs_review"
            summary["pending_count"] = 1

    return summary


def _review_status_from_manifest(preview_manifest: dict[str, Any], page_tasks: dict[str, Any]) -> str:
    return str(_review_summary_from_manifest(preview_manifest, page_tasks).get("status") or "")


def _run_readiness_summary(
    root: Path,
    request: dict[str, Any],
    setup_payload: dict[str, Any],
    workspace: dict[str, Any],
    review_status: str,
) -> dict[str, Any]:
    generation_session = _safe_read(root / GENERATION_SESSION_NAME)
    generation_gate = _pick_first_draft_gate(root)
    generation_blocked, generation_block_reason = _draft_gate_blocks(generation_gate)
    render_result_path, render_result, render_source = _read_render_result(root)
    build = _build_status(root)
    builder_backend = builder_backend_status()

    setup_status = setup_payload.get("status", {}) or {}
    return {
        "setup": {
            "status": "ready" if bool(setup_status.get("production_ready") or setup_status.get("workspace_ready")) else "blocked",
            "install_ready": bool(setup_status.get("install_ready")),
            "workspace_ready": bool(setup_status.get("workspace_ready")),
            "run_ready": bool(setup_status.get("run_ready")),
            "production_ready": bool(setup_status.get("production_ready")),
            "run_mode": setup_payload.get("run_mode"),
        },
        "workspace": {
            "required": bool(workspace.get("workspace_required")),
            "resolved_from": str(workspace.get("resolved_from") or ""),
            "resolved_workspace": str(workspace.get("resolved_workspace") or ""),
            "valid": bool(workspace.get("workspace_valid")),
            "exists": bool(workspace.get("workspace_exists")),
            "blocked": bool(workspace.get("blocked")),
            "report": workspace.get("workspace_report") or {},
        },
        "artifacts": {
            "request": bool(request),
            "context_manifest": (root / CONTEXT_MANIFEST_NAME).exists(),
            "deck_brief": (root / DECK_BRIEF_NAME).exists(),
            "claim_map": (root / CLAIM_MAP_NAME).exists(),
            "narrative_plan": (root / NARRATIVE_PLAN_NAME).exists(),
            "page_tasks": (root / PAGE_TASKS_NAME).exists(),
            "sourcing_plan": (root / SOURCING_PLAN_NAME).exists(),
            "generation": {
                "task_count": _generation_tasks_count(root),
                "session_exists": bool(generation_session),
                "session_status": generation_session.get("status") if generation_session else "",
                "producer": (generation_session or {}).get("tool") or (generation_session or {}).get("producer") or "",
                "profile": (generation_session or {}).get("run_mode") or (generation_session or {}).get("profile") or "",
            },
            "build": build,
            "builder_backend": builder_backend,
            "preview": (root / PREVIEW_MANIFEST_NAME).exists(),
            "quality_gate": bool(generation_gate),
            "draft_gate_blocking": generation_blocked,
            "draft_gate_blocking_reason": generation_block_reason,
            "preview_review_status": review_status,
            "preview_review_summary": _review_summary_from_manifest(
                _safe_read(root / PREVIEW_MANIFEST_NAME) or {},
                _safe_read(root / PAGE_TASKS_NAME) or {},
            ),
            "render": {
                "required": True,
                "status": str((render_result or {}).get("status") or ("present" if render_result else "missing")),
                "source": render_source if render_result else "missing",
                "render_result": str(render_result_path.relative_to(root)) if render_result else "",
                "artifact_path": (render_result or {}).get("artifact_path", ""),
                "tool": (render_result or {}).get("tool", ""),
                "format": (render_result or {}).get("format", ""),
                "source_fingerprint": (render_result or {}).get("source_fingerprint", ""),
                "artifact_manifest": (render_result or {}).get("artifact_manifest", ""),
                "editability": build.get("editability", []),
            },
            "export": (root / "approved_queue.json").exists() or (root / "export_queue.json").exists(),
            "quality": bool(generation_gate) and not generation_blocked,
            "benchmark_checkpoints": (root / "benchmark_checkpoints.json").exists(),
        },
    }


def _resolve_stage(root: Path, run_mode: str) -> tuple[str, list[dict[str, str]], str]:
    request = _safe_read(root / REQUEST_NAME) or {}

    if not request:
        return (
            "needs_request",
            [{"action": "run", "reason": "missing request.json"}],
            "missing request.json",
        )

    if not (root / CONTEXT_MANIFEST_NAME).exists():
        return (
            "needs_context",
            [{"action": "context", "reason": "context manifest is missing"}],
            "context manifest is missing",
        )
    if not (root / DECK_BRIEF_NAME).exists():
        return (
            "needs_brief",
            [{"action": "brief", "reason": "deck brief is missing"}],
            "deck brief is missing",
        )
    if not (root / CLAIM_MAP_NAME).exists():
        return (
            "needs_claim_map",
            [{"action": "claim_map", "reason": "claim map is missing"}],
            "claim map is missing",
        )
    if not (root / NARRATIVE_PLAN_NAME).exists():
        return (
            "needs_narrative_plan",
            [{"action": "plan", "reason": "narrative plan is missing"}],
            "narrative plan is missing",
        )
    if not (root / PAGE_TASKS_NAME).exists():
        return (
            "needs_page_tasks",
            [{"action": "page_tasks", "reason": "page tasks are missing"}],
            "page tasks are missing",
        )
    if not (root / SOURCING_PLAN_NAME).exists():
        return (
            "needs_sourcing",
            [{"action": "sourcing", "reason": "sourcing plan is missing"}],
            "sourcing plan is missing",
        )

    generation_task_count = _generation_tasks_count(root)
    has_generation_session = (root / GENERATION_SESSION_NAME).exists()
    if generation_task_count > 0 and not has_generation_session:
        return (
            "needs_generation_session",
            [{"action": "run_generation", "reason": "generation_session.json is required"}],
            "generation_session.json is required",
        )

    if has_generation_session:
        gen_status, generation_session = _read_generation_status(root)
        if gen_status in {"dispatched", "awaiting_agent_execution"}:
            return (
                "awaiting_agent_execution",
                [{"action": "agent_execution", "reason": f"generation session status={gen_status}"}],
                f"generation session status={gen_status}",
            )
        if gen_status in {"created", "running"}:
            return (
                "generation_running",
                [{"action": "run_generation", "reason": f"generation session status={gen_status}"}],
                f"generation session status={gen_status}",
            )
        if gen_status in {"failed", "blocked"}:
            return (
                "generation_failed",
                [{"action": "run_generation", "reason": f"generation session status={gen_status}"}],
                f"generation session status={gen_status}",
            )
        if gen_status in {"completed", "partial", "result_files_present"}:
            return (
                "needs_generation_import",
                [{"action": "generation_import", "reason": f"generation session status={gen_status}"}],
                f"generation session status={gen_status}",
            )
        if gen_status == "results_imported":
            return (
                "needs_preview_refresh",
                [{"action": "preview_refresh", "reason": "generation results imported but preview is not refreshed"}],
                "generation results imported but preview is not refreshed",
            )
        if gen_status == "quality_required":
            fresh, freshness_reason = _fresh_draft_gate_for_generation(root, generation_session)
            if not fresh:
                reason = freshness_reason or "generation results require fresh quality gate"
                return (
                    "needs_draft_gate",
                    [{"action": "draft_gate", "reason": reason}],
                    reason,
                )
        if gen_status == "ready_for_build":
            pass
        elif gen_status and gen_status not in {"preview_refreshed", "quality_required"}:
            return (
                "needs_generation_import",
                [{"action": "generation_import", "reason": "generation session requires import or refresh"}],
                "generation session requires import or refresh",
            )

    if not (root / PREVIEW_MANIFEST_NAME).exists():
        return (
            "needs_preview",
            [{"action": "preview", "reason": "preview manifest is missing"}],
            "preview manifest is missing",
        )

    preview = _safe_read(root / PREVIEW_MANIFEST_NAME) or {}
    page_tasks = _safe_read(root / PAGE_TASKS_NAME) or {}
    review_status = _review_status_from_manifest(preview, page_tasks)
    if review_status and review_status != "review_complete":
        return (
            "needs_review",
            [{"action": "review", "reason": f"preview review status is {review_status}"}],
            f"preview review status is {review_status}",
        )

    draft_gate = _pick_first_draft_gate(root)
    blocked, reason = _draft_gate_blocks(draft_gate)
    if blocked:
        return (
            "needs_draft_gate",
            [{"action": "draft_gate", "reason": reason}],
            reason,
        )

    if generation_task_count > 0:
        backend = builder_backend_status()
        if production_requires_builder_backend(run_mode) and not backend.get("production_capable"):
            return (
                "needs_builder_backend",
                [{"action": "builder_backend", "reason": str(backend.get("blocking_reason") or "PPT Master backend is not ready")}],
                str(backend.get("blocking_reason") or "PPT Master backend is not ready"),
            )

    if generation_task_count > 0 and not _render_result_present(root):
        build_status = _build_status(root)
        if not build_status.get("build_manifest"):
            return (
                "needs_build",
                [{"action": "build", "reason": "build manifest is missing after review and quality gate"}],
                "build manifest is missing after review and quality gate",
            )
        if build_status.get("invalid_artifacts"):
            return (
                "needs_render",
                [{"action": "render", "reason": "artifact manifest contains invalid artifacts"}],
                "artifact manifest contains invalid artifacts",
            )
        return (
            "needs_render",
            [{"action": "render", "reason": "render result is missing after build"}],
            "render result is missing after build",
        )

    if run_mode == "benchmark":
        return "ready_for_benchmark", [], "ready for benchmark"
    return "ready_for_client_export", [], "ready for export"


def _next_command(stage: str, root: Path, run_id: str) -> str:
    if stage == "needs_request":
        return f"deck-master start --run-dir {root} --run-id {run_id}"
    if stage == "needs_context":
        return f"deck-master import-context-pack --run-dir {root} --run-id {run_id} --input <context_pack.json>"
    if stage == "needs_brief":
        return f"deck-master build-brief --run-dir {root} --run-id {run_id}"
    if stage == "needs_claim_map":
        return f"deck-master build-claim-map --run-dir {root} --run-id {run_id}"
    if stage == "needs_narrative_plan":
        return f"deck-master autoplan --run-dir {root} --run-id {run_id}"
    if stage in {"needs_page_tasks", "needs_sourcing"}:
        return f"deck-master decide-sourcing --run-dir {root} --run-id {run_id}"
    if stage == "needs_generation_session":
        return f"deck-master generation-session create --run-dir {root} --run-id {run_id}"
    if stage == "generation_running":
        return f"deck-master generation-session status --run-dir {root} --run-id {run_id}"
    if stage == "awaiting_agent_execution":
        return f"deck-master generation-session status --run-dir {root} --run-id {run_id}"
    if stage in {"generation_failed", "needs_generation_import"}:
        return f"deck-master generation-session import-results --run-dir {root} --run-id {run_id} --input <result.json>"
    if stage == "needs_preview_refresh":
        return f"deck-master refresh-preview-from-generation --run-dir {root} --run-id {run_id}"
    if stage == "needs_preview":
        return f"deck-master build-preview --run-dir {root} --run-id {run_id}"
    if stage == "needs_draft_gate":
        return f"deck-master quality-gate draft --run-dir {root} --run-id {run_id}"
    if stage == "needs_builder_backend":
        return "deck-master suite-status --target codex --output json"
    if stage == "needs_build":
        return f"deck-master build prepare --run-dir {root} --run-id {run_id}"
    if stage == "needs_render":
        return f"deck-master build run --run-dir {root} --run-id {run_id}"
    if stage == "needs_review":
        return f"deck-master run-state --run-dir {root} --run-id {run_id}"
    if stage in {"ready_for_benchmark", "ready_for_client_export"}:
        return f"deck-master export --run-dir {root} --run-id {run_id}"
    return f"deck-master orchestration-check --run-dir {root} --run-id {run_id}"


def _allowed_blocking(stage: str, reason: str, run_mode: str) -> tuple[list[str], list[dict[str, str]]]:
    allowed: list[str] = []
    blocked_actions: list[dict[str, str]] = []

    if stage in {
        "needs_request",
        "needs_context",
        "needs_brief",
        "needs_claim_map",
        "needs_narrative_plan",
        "needs_page_tasks",
        "needs_sourcing",
        "needs_generation_session",
        "awaiting_agent_execution",
        "generation_running",
        "generation_failed",
        "needs_generation_import",
        "needs_preview_refresh",
        "needs_preview",
        "needs_draft_gate",
        "needs_builder_backend",
        "needs_build",
        "needs_render",
    }:
        blocked_actions.append({"action": "client_export", "reason": reason})

    if stage == "needs_generation_session":
        allowed.append("create_generation_session")
    if stage == "awaiting_agent_execution":
        allowed.append("inspect_generation_dispatch")
    if stage == "needs_review":
        allowed.append("open_review_cockpit")
        if run_mode in {"fixture", "dev"}:
            allowed.append("import_quality_review")
    if stage in {"ready_for_client_export", "ready_for_benchmark"}:
        allowed.extend(["open_review_cockpit", "import_quality_review", "client_export"])

    if stage == "blocked_workspace":
        blocked_actions.append({"action": "workspace", "reason": reason or "workspace is invalid or missing"})

    return sorted(set(allowed)), blocked_actions


def resolve_run_state(
    run_dir: str | Path,
    *,
    cli_workspace: str | None = None,
    run_mode: str | None = None,
    dev_allow_unsetup: bool = False,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    request = _safe_read(root / REQUEST_NAME) or {}
    resolved_mode = str(run_mode or request.get("run_mode") or "production")

    workspace = resolve_workspace_for_run(
        run_dir=root,
        request=request,
        cli_workspace=cli_workspace,
        run_mode=resolved_mode,
        allow_dev_bypass=dev_allow_unsetup,
    )

    setup_payload = setup_readiness(
        workspace=workspace.get("resolved_workspace"),
        run_mode=resolved_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )

    run_id = str(request.get("run_id") or root.name)
    stage, base_blocked_actions, reason = _resolve_stage(root, resolved_mode)

    if workspace.get("blocked") and stage != "needs_request":
        stage = "blocked_workspace"
        reason = "; ".join(workspace.get("reasons", [])) or reason

    preview = _safe_read(root / PREVIEW_MANIFEST_NAME) or {}
    page_tasks = _safe_read(root / PAGE_TASKS_NAME) or {}
    review_status = _review_status_from_manifest(preview, page_tasks)

    if stage in {"ready_for_client_export", "ready_for_benchmark"}:
        if workspace.get("workspace_required") and not workspace.get("workspace_valid", False):
            stage = "blocked_workspace"
            reason = "production requires a valid workspace"

    allowed_actions, blocked_reason_actions = _allowed_blocking(stage, reason, resolved_mode)
    blocked_actions = list(base_blocked_actions)
    blocked_actions.extend(blocked_reason_actions)
    blocked_actions.extend({"action": "workspace", "reason": msg} for msg in workspace.get("reasons", []) if msg)

    readiness = _run_readiness_summary(root, request, setup_payload, workspace, review_status)
    next_command = _next_command(stage, root, run_id)
    first_reason = reason
    for item in blocked_actions:
        if item.get("reason"):
            first_reason = str(item["reason"])
            break
    skill_route = route_for_stage(stage, reason=first_reason, next_command=next_command)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_dir": str(root),
        "run_id": run_id,
        "run_mode": resolved_mode,
        "policy_mode": "fixture" if resolved_mode in {"fixture", "dev"} else "production",
        "stage": stage,
        "readiness": readiness,
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "next_command": next_command,
        "recommended_skill": skill_route["recommended_skill"],
        "skill_stage": skill_route["skill_stage"],
        "skill_reason": skill_route["skill_reason"],
        "next_skill_command": skill_route["next_skill_command"],
        "skill_route": skill_route,
    }
