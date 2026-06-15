from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generation.handback import (
    GenerationHandbackError,
    import_generation_result,
    refresh_preview_from_generation,
    validate_generation_result,
)
from runtime.events import append_typed_event
from runtime.run_state import (
    REQUEST_NAME,
    ensure_run_dirs,
    load_request,
    read_json,
    write_json,
)
from runtime.tool_registry import ToolRegistryError, check_tool_available, resolve_tool_command


SCHEMA_VERSION = "deck_generation_session.v1"
SESSION_NAME = "generation_session.json"
SESSIONS_DIR = "generation_sessions"
TASKS_DIR = "generation_tasks"
RESULTS_DIR = "generation_results"

VALID_STATUSES = {
    "created",
    "blocked",
    "dispatched",
    "running",
    "completed",
    "partial",
    "failed",
    "results_imported",
    "preview_refreshed",
    "quality_required",
}


class GenerationSessionError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(run_dir: str | Path) -> Path:
    return ensure_run_dirs(run_dir)


def _session_path(run_dir: Path) -> Path:
    return run_dir / SESSION_NAME


def _session_history_path(run_dir: Path, session_id: str) -> Path:
    return run_dir / SESSIONS_DIR / f"{session_id}.json"


def _run_id(run_dir: Path) -> str:
    if (run_dir / REQUEST_NAME).exists():
        request = load_request(run_dir)
        return str(request.get("run_id") or run_dir.name)
    return run_dir.name


def _load_generation_tasks(run_dir: Path) -> list[dict[str, Any]]:
    index_path = run_dir / TASKS_DIR / "index.json"
    if not index_path.exists():
        raise GenerationSessionError("generation_tasks/index.json not found.")
    index = read_json(index_path)
    raw = index.get("tasks")
    if isinstance(raw, list):
        return [task for task in raw if isinstance(task, dict)]
    task_ids = index.get("task_ids")
    if not isinstance(task_ids, list):
        return []
    tasks = []
    for task_id in task_ids:
        task_path = run_dir / TASKS_DIR / f"{task_id}.json"
        if not task_path.exists():
            continue
        try:
            payload = read_json(task_path)
        except Exception:
            continue
        if isinstance(payload, dict):
            tasks.append(payload)
    return tasks


def _resolve_tool(
    *,
    tool: str,
    run_dir: Path,
    workspace: str | None,
    tool_command: str | None,
) -> tuple[list[str], dict[str, Any]]:
    command, entry, _ = resolve_tool_command(
        tool,
        run_dir,
        workspace=workspace,
        cli_tool_command=tool_command,
    )
    return command, entry


def _ensure_session_exists(run_dir: Path) -> dict[str, Any]:
    path = _session_path(run_dir)
    if not path.exists():
        raise GenerationSessionError("generation session missing; run generation-session create first.")
    return read_json(path)


def _set_session_status(
    run_dir: Path,
    session: dict[str, Any],
    status: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise GenerationSessionError(f"Unknown generation session status: {status}")
    session["status"] = status
    if status in {"running"} and not session.get("started_at"):
        session["started_at"] = _utc_now()
    if status in {
        "completed",
        "partial",
        "failed",
        "results_imported",
        "preview_refreshed",
        "quality_required",
    }:
        if not session.get("completed_at"):
            session["completed_at"] = _utc_now()
    if extra:
        session.update(extra)
    write_json(_session_path(run_dir), session)
    history = _session_history_path(run_dir, str(session.get("session_id") or "unknown"))
    if history.exists():
        write_json(history, session)
    return session


def _write_session(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_run_dirs(run_dir)
    write_json(_session_path(run_dir), payload)
    ensure_run_dirs(run_dir / SESSIONS_DIR)
    write_json(_session_history_path(run_dir, str(payload.get("session_id") or "unknown")), payload)
    return payload


def _run_tool_available(
    tool: str,
    run_dir: Path,
    *,
    workspace: str | None,
    tool_command: str | None,
) -> tuple[bool, str, list[str], dict[str, Any]]:
    try:
        command, entry = _resolve_tool(
            tool=tool,
            run_dir=run_dir,
            workspace=workspace,
            tool_command=tool_command,
        )
    except ToolRegistryError as exc:
        return False, str(exc), [], {}
    availability_check = entry.get("availability_check")
    if not isinstance(availability_check, list):
        availability_check = []
    ok, reason = check_tool_available(command, availability_check=availability_check or None)
    return ok, reason, command, entry


def create_generation_session(
    run_dir: str | Path,
    *,
    tool: str,
    workspace: str | None = None,
    tool_command: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root = _run_dir(run_dir)
    tasks = _load_generation_tasks(root)
    if not tasks:
        raise GenerationSessionError("No generation tasks found in generation_tasks/index.json.")

    session_path = _session_path(root)
    if session_path.exists() and not force:
        raise GenerationSessionError("generation_session.json already exists; use --force.")

    request_workspace = workspace
    if request_workspace is None:
        if (root / REQUEST_NAME).exists():
            request = load_request(root)
            request_workspace = str(request.get("workspace") or "")

    command, _ = _resolve_tool(
        tool=tool,
        run_dir=root,
        workspace=request_workspace,
        tool_command=tool_command,
    )

    run_id = _run_id(root)
    session_id = f"{run_id}-gen-{_utc_now().replace(':', '').replace('-', '')}"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "session_id": session_id,
        "tool": tool,
        "status": "created",
        "tasks_total": len(tasks),
        "tasks_completed": 0,
        "tasks_failed": 0,
        "command": command,
        "started_at": "",
        "completed_at": "",
        "errors": [],
        "workspace": request_workspace or "",
    }
    _write_session(root, payload)
    append_typed_event(
        root,
        "step_completed",
        "generation.session.created",
        f"Created generation session for tool={tool}.",
        run_id=run_id,
        refs=[SESSION_NAME],
        payload={"tool": tool, "session_id": session_id},
    )
    return payload


def validate_generation_session(
    run_dir: str | Path,
    *,
    tool: str | None = None,
    tool_command: str | None = None,
) -> dict[str, Any]:
    root = _run_dir(run_dir)
    request = load_request(root) if (root / REQUEST_NAME).exists() else {}
    session = read_json(_session_path(root)) if _session_path(root).exists() else None
    workspace = str(request.get("workspace", "")) if isinstance(request, dict) else ""
    active_tool = tool or (session.get("tool") if isinstance(session, dict) else "")

    errors: list[str] = []
    warnings: list[str] = []
    status = "created"
    if isinstance(session, dict):
        previous_status = session.get("status")
        if isinstance(previous_status, str) and previous_status in VALID_STATUSES:
            status = previous_status

    if session is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": _run_id(root),
            "status": "blocked",
            "tool": active_tool,
            "errors": ["generation session missing"],
            "warnings": [],
        }

    if not active_tool:
        status = "blocked"
        errors.append("tool is required.")
    elif status in {"created", "dispatched", "running"}:
        ok, reason, command, _ = _run_tool_available(
            active_tool,
            root,
            workspace=workspace,
            tool_command=tool_command,
        )
        if not ok:
            status = "blocked"
            errors.append(reason)
        else:
            session["command"] = command

    try:
        tasks = _load_generation_tasks(root)
    except GenerationSessionError as exc:
        status = "blocked"
        errors.append(str(exc))
        tasks = []
    if not tasks:
        status = "blocked"
        warnings.append("No generation tasks found.")
    for task in tasks:
        source_decision = task.get("source_decision")
        if source_decision and source_decision not in {"generate", "adapt"}:
            warnings.append(f"{task.get('task_id')} has unsupported source_decision={source_decision}")
    if session.get("status") in {"failed", "blocked"}:
        status = "blocked"

    session["tasks_total"] = len(tasks)
    session["tasks_completed"] = session_task_counter(root)
    if status == "blocked":
        _set_session_status(root, session, "blocked")

    write_json(_session_path(root), session)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": session.get("run_id", _run_id(root)),
        "session_id": session.get("session_id"),
        "status": status,
        "tool": active_tool,
        "command": session.get("command", []),
        "errors": errors,
        "warnings": warnings,
        "session": session,
    }


def generation_session_status(
    run_dir: str | Path,
    *,
    tool: str | None = None,
    tool_command: str | None = None,
) -> dict[str, Any]:
    validation = validate_generation_session(run_dir, tool=tool, tool_command=tool_command)
    session = validation.get("session") if isinstance(validation.get("session"), dict) else {}
    validation_status = validation.get("status", "created")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(session.get("run_id") or _run_id(_run_dir(run_dir))),
        "session_id": session.get("session_id"),
        "status": validation_status,
        "tool": session.get("tool"),
        "command": session.get("command", []),
        "tasks_total": session.get("tasks_total", 0),
        "tasks_completed": session.get("tasks_completed", 0),
        "tasks_failed": session.get("tasks_failed", 0),
        "needs_quality_gate": validation_status == "quality_required",
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "session": session,
    }


def run_generation(
    run_dir: str | Path,
    *,
    tool: str,
    dry_run: bool = False,
    no_execute: bool = False,
    tool_command: str | None = None,
) -> dict[str, Any]:
    root = _run_dir(run_dir)
    request = load_request(root) if (root / REQUEST_NAME).exists() else {}
    session = _ensure_session_exists(root)
    workspace = str(request.get("workspace") or "")
    session["tool"] = tool

    if dry_run or no_execute:
        command, entry = _resolve_tool(
            tool=tool,
            run_dir=root,
            workspace=workspace,
            tool_command=tool_command,
        )
        session["command"] = command
        _set_session_status(root, session, "dispatched", extra={"command": command, "command_entry": entry})
        append_typed_event(
            root,
            "tool_call",
            "generation.run.prepared",
            "Generation command prepared.",
            run_id=session.get("run_id", root.name),
            refs=[SESSION_NAME],
            payload={
                "tool": tool,
                "dry_run": dry_run,
                "no_execute": no_execute,
                "command": command,
            },
        )
        return {
            "status": "dispatched",
            "run_id": session.get("run_id", root.name),
            "tool": tool,
            "command": command,
            "dry_run": dry_run,
            "no_execute": no_execute,
        }

    ok, reason, command, entry = _run_tool_available(
        tool,
        root,
        workspace=workspace,
        tool_command=tool_command,
    )
    if not ok:
        _set_session_status(root, session, "blocked")
        raise GenerationSessionError(f"tool unavailable: {reason}")

    session["command"] = command
    _set_session_status(root, session, "running", extra={"command_entry": entry})

    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        session = _set_session_status(
            root,
            session,
            "failed",
            extra={"error": completed.stderr.strip() or completed.stdout.strip() or "execution failed"},
        )
        append_typed_event(
            root,
            "step_completed",
            "generation.session.failed",
            "Generation execution failed.",
            run_id=session.get("run_id", root.name),
            refs=[SESSION_NAME],
            payload={"returncode": completed.returncode},
            severity="error",
        )
        return {
            "status": "failed",
            "run_id": session.get("run_id", root.name),
            "tool": tool,
            "command": command,
            "returncode": completed.returncode,
            "stderr": completed.stderr,
            "stdout": completed.stdout,
        }

    session = _set_session_status(root, session, "completed", extra={"command_output": completed.stdout})
    append_typed_event(
        root,
        "step_completed",
        "generation.session.completed",
        "Generation execution completed.",
        run_id=session.get("run_id", root.name),
        refs=[SESSION_NAME],
        payload={"returncode": completed.returncode},
    )
    return {
        "status": "completed",
        "run_id": session.get("run_id", root.name),
        "tool": tool,
        "command": command,
        "returncode": completed.returncode,
    }


def _validate_result_path(run_dir: Path, value: Any, *, field_name: str, required: bool) -> str:
    if not value:
        if required:
            raise GenerationSessionError(f"{field_name} is required.")
        return ""
    path = Path(str(value))
    if path.is_absolute():
        raise GenerationSessionError(f"{field_name} must be run-relative: {value}")
    if ".." in path.parts:
        raise GenerationSessionError(f"{field_name} must be inside run directory: {value}")
    resolved = (run_dir / path).resolve()
    root_text = str(run_dir)
    if str(resolved) != root_text and not str(resolved).startswith(root_text + os.sep):
        raise GenerationSessionError(f"{field_name} must be inside run directory: {value}")
    if not resolved.exists():
        raise GenerationSessionError(f"{field_name} not found: {value}")
    return str(path)


def import_generation_results(
    run_dir: str | Path,
    input_path: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    root = _run_dir(run_dir)
    session = _ensure_session_exists(root)
    result_path = Path(input_path).expanduser().resolve()
    if not result_path.exists():
        raise GenerationSessionError(f"Result file not found: {result_path}")
    raw = read_json(result_path)
    if not isinstance(raw, dict):
        raise GenerationSessionError("Result payload must be a JSON object.")

    if not raw.get("beat_id") and raw.get("page_id"):
        raw["beat_id"] = str(raw["page_id"])
    if raw.get("beat_id") and not raw.get("page_id"):
        raw["page_id"] = str(raw["beat_id"])

    validation = validate_generation_result(raw)
    if not validation.get("valid"):
        raise GenerationSessionError("Invalid generation result: " + "; ".join(validation.get("errors", [])))

    status = str(raw.get("status", ""))
    _validate_result_path(run_dir=root, value=raw.get("artifact_path"), field_name="artifact_path", required=(status in {"completed", "partial"}))
    _validate_result_path(run_dir=root, value=raw.get("preview_path"), field_name="preview_path", required=(status == "completed"))

    try:
        imported = import_generation_result(root, raw, force=force)
    except GenerationHandbackError as exc:
        raise GenerationSessionError(str(exc)) from exc

    session["tasks_completed"] = session_task_counter(root)
    refresh_result = refresh_preview_from_generation(root)
    if refresh_result.get("status") == "refreshed":
        session = _set_session_status(root, session, "quality_required")
        append_typed_event(
            root,
            "step_completed",
            "generation.quality_required",
            "Generation results imported and preview refreshed, waiting quality gate.",
            run_id=session.get("run_id", root.name),
            refs=[RESULTS_DIR],
            payload={"session_id": session.get("session_id")},
        )
    else:
        session = _set_session_status(root, session, "results_imported")

    append_typed_event(
        root,
        "step_completed",
        "generation.session.results_imported",
        "Generation results imported.",
        run_id=session.get("run_id", root.name),
        refs=["generation_results", "generation_tasks"],
        payload={"task_id": imported.get("task_id"), "result_status": imported.get("result_status"), "refresh_status": refresh_result.get("status")},
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": session.get("run_id", root.name),
        "session_id": session.get("session_id"),
        "status": session.get("status"),
        "needs_quality_gate": session.get("status") == "quality_required",
        "import_result": imported,
        "refresh_preview": refresh_result,
    }


def session_task_counter(run_dir: Path) -> int:
    completed = 0
    tasks = _load_generation_tasks(run_dir)
    for task in tasks:
        if task.get("status") == "completed":
            completed += 1
    return completed
