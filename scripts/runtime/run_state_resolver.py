from __future__ import annotations

from pathlib import Path
from typing import Any

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
from runtime.setup_status import setup_readiness
from runtime.workspace_resolver import resolve_workspace_for_run

SCHEMA_VERSION = "deck_run_state.v1"

GENERATION_SESSION_NAME = "generation_session.json"
GENERATION_TASK_INDEX = Path("generation_tasks") / "index.json"
QUALITY_DIR = "quality_reports"
RENDER_RESULT_NAME = "render_result.json"


def _safe_read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
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


def _pick_first_draft_gate(root: Path) -> dict[str, Any] | None:
    quality_dir = root / QUALITY_DIR
    if not quality_dir.is_dir():
        return None
    for filename in ("draft_v2_gate.json", "draft_gate.json"):
        payload = _safe_read(quality_dir / filename)
        if payload:
            payload["_report_file"] = filename
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


def _review_status_from_manifest(preview_manifest: dict[str, Any], page_tasks: dict[str, Any]) -> str:
    manifest_status = str(preview_manifest.get("review_status") or "").strip()
    if manifest_status:
        return manifest_status

    pages = preview_manifest.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            status = str(page.get("review_status") or "").strip()
            if status:
                return status
            status = str(page.get("decision") or "").strip()
            if status:
                return status

    if isinstance(page_tasks, dict):
        status = str(page_tasks.get("review_status") or "").strip()
        if status:
            return status

    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        status = str(page.get("decision") or "").strip()
        if status in {"approved", "needs_review", "replace", "keep", "pending"}:
            return status

    return ""


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
            },
            "preview": (root / PREVIEW_MANIFEST_NAME).exists(),
            "quality_gate": bool(generation_gate),
            "draft_gate_blocking": generation_blocked,
            "draft_gate_blocking_reason": generation_block_reason,
            "preview_review_status": review_status,
            "render": {
                "required": True,
                "status": "present" if (root / "external_results" / RENDER_RESULT_NAME).exists() else "missing",
                "artifact_path": (
                    _safe_read(root / "external_results" / RENDER_RESULT_NAME) or {}
                ).get("artifact_path", ""),
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
        gen_status, _ = _read_generation_status(root)
        if gen_status in {"running", "dispatched"}:
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
        if gen_status and gen_status not in {"completed", "results_imported", "preview_refreshed"}:
            return (
                "needs_generation_import",
                [{"action": "run_generation", "reason": "generation session requires import or refresh"}],
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
    if review_status and review_status != "approved":
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

    if run_mode == "benchmark":
        return "ready_for_benchmark", [], "ready for benchmark"
    return "ready_for_client_export", [], "ready for export"


def _next_command(stage: str, root: Path, run_id: str) -> str:
    if stage in {"needs_request", "needs_context"}:
        return f"deck-master start-conversation --run-dir {root} --run-id {run_id}"
    if stage == "needs_brief":
        return f"deck-master build-brief --run-dir {root} --run-id {run_id}"
    if stage == "needs_claim_map":
        return f"deck-master build-claim-map --run-dir {root} --run-id {run_id}"
    if stage == "needs_narrative_plan":
        return f"deck-master autoplan --run-dir {root} --run-id {run_id}"
    if stage in {"needs_page_tasks", "needs_sourcing"}:
        return f"deck-master decide-sourcing --run-dir {root} --run-id {run_id}"
    if stage == "needs_generation_session":
        return f"deck-master create-generation-tasks --run-dir {root} --run-id {run_id}"
    if stage in {"generation_running", "generation_failed", "needs_generation_import"}:
        return f"deck-master import-generation-result --run-dir {root} --run-id {run_id}"
    if stage == "needs_preview":
        return f"deck-master build-preview --run-dir {root} --run-id {run_id}"
    if stage == "needs_draft_gate":
        return f"deck-master quality-gate draft --run-dir {root} --run-id {run_id}"
    if stage == "needs_review":
        return f"deck-master import-quality-review --run-dir {root} --run-id {run_id}"
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
        "generation_running",
        "generation_failed",
        "needs_generation_import",
        "needs_preview",
        "needs_draft_gate",
    }:
        blocked_actions.append({"action": "client_export", "reason": reason})

    if stage == "needs_generation_session":
        allowed.append("create_generation_tasks")
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
        "next_command": _next_command(stage, root, run_id),
    }
