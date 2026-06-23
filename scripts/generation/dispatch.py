from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generation.handback import source_fingerprint_for_run
from runtime.run_state import read_json, write_json

DISPATCH_SCHEMA_VERSION = "deck_generation_dispatch_package.v1"
DISPATCH_DIR = "generation_dispatch"
DISPATCH_PACKAGE_NAME = "dispatch_package.json"
DISPATCH_INSTRUCTIONS_NAME = "agent_instructions.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def _tasks(run_dir: Path) -> list[dict[str, Any]]:
    tasks_dir = run_dir / "generation_tasks"
    index = _safe_read(tasks_dir / "index.json")
    raw_tasks = index.get("tasks")
    if isinstance(raw_tasks, list):
        return [task for task in raw_tasks if isinstance(task, dict)]

    task_ids = index.get("task_ids")
    if not isinstance(task_ids, list):
        return []

    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        task = _safe_read(tasks_dir / f"{task_id}.json")
        if task:
            tasks.append(task)
    return tasks


def _context_refs(run_dir: Path) -> list[str]:
    refs = [
        "request.json",
        "deck_brief.json",
        "claim_map.json",
        "narrative_plan.json",
        "page_tasks.json",
        "sourcing_plan.json",
        "generation_tasks/index.json",
    ]
    return [ref for ref in refs if (run_dir / ref).exists()]


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("task_id") or task.get("id") or "")
    return {
        "task_id": task_id,
        "beat_id": str(task.get("beat_id") or task.get("page_id") or ""),
        "page_id": str(task.get("page_id") or task.get("beat_id") or ""),
        "page_title": str(task.get("page_title") or task.get("title") or ""),
        "source_decision": str(task.get("source_decision") or ""),
        "task_file": f"generation_tasks/{task_id}.json" if task_id else "",
        "expected_outputs": task.get("expected_outputs") if isinstance(task.get("expected_outputs"), list) else [],
        "quality_requirements": task.get("quality_requirements") if isinstance(task.get("quality_requirements"), list) else [],
        "workspace_refs": task.get("workspace_refs") if isinstance(task.get("workspace_refs"), list) else [],
    }


def write_generation_dispatch_package(
    run_dir: str | Path,
    *,
    session: dict[str, Any],
    tool: str,
    command: list[str] | None = None,
    command_entry: dict[str, Any] | None = None,
    reason: str = "awaiting_agent_execution",
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    dispatch_dir = root / DISPATCH_DIR
    dispatch_dir.mkdir(parents=True, exist_ok=True)

    task_summaries = [_task_summary(task) for task in _tasks(root)]
    package_path = dispatch_dir / DISPATCH_PACKAGE_NAME
    instructions_path = dispatch_dir / DISPATCH_INSTRUCTIONS_NAME
    package = {
        "schema_version": DISPATCH_SCHEMA_VERSION,
        "run_id": str(session.get("run_id") or root.name),
        "session_id": str(session.get("session_id") or ""),
        "tool": tool,
        "status": "awaiting_agent_execution",
        "reason": reason,
        "created_at": _utc_now(),
        "source_fingerprint": source_fingerprint_for_run(root),
        "context_refs": _context_refs(root),
        "task_count": len(task_summaries),
        "tasks": task_summaries,
        "output_contract": {
            "schema_version": "deck_generation_result.v2",
            "result_dir": "generation_results",
            "required": [
                "run_id",
                "session_id",
                "task_id",
                "page_id",
                "producer",
                "status",
                "source_fingerprint",
                "artifacts",
                "preview",
                "created_at",
            ],
        },
        "import_commands": {
            "single_result": f"deck-master generation-session import-results --run-dir {root} --input <result.json>",
            "batch": f"deck-master generation-session import-results --run-dir {root} --input {root / 'generation_results'}",
        },
        "agent_instructions": str(instructions_path.relative_to(root)),
        "command_preview": command or [],
        "command_entry": command_entry or {},
    }
    write_json(package_path, package)

    instructions = [
        "# Deck Master Generation Agent Dispatch",
        "",
        f"- Run ID: `{package['run_id']}`",
        f"- Session ID: `{package['session_id']}`",
        f"- Tool: `{tool}`",
        f"- Task count: `{len(task_summaries)}`",
        "",
        "## Required Output",
        "",
        "Write one `deck_generation_result.v2` JSON file per completed or failed task into `generation_results/`.",
        "Each completed or partial result must point only to run-relative artifact paths and include SHA-256, byte size, and source fingerprint.",
        "",
        "## Import",
        "",
        f"Single result: `{package['import_commands']['single_result']}`",
        f"Batch: `{package['import_commands']['batch']}`",
    ]
    instructions_path.write_text("\n".join(instructions) + "\n", encoding="utf-8")
    return {
        "schema_version": DISPATCH_SCHEMA_VERSION,
        "status": "awaiting_agent_execution",
        "dispatch_package": str(package_path.relative_to(root)),
        "agent_instructions": str(instructions_path.relative_to(root)),
        "task_count": len(task_summaries),
    }
