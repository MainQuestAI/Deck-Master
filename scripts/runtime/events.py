from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS_NAME = "events.jsonl"

EVENT_TYPES = {
    "step_started",
    "step_completed",
    "tool_call",
    "decision",
    "error",
    "manual_action",
    "artifact_written",
}

CANONICAL_SCHEMA_VERSION = "deck_event.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def events_path(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve() / EVENTS_NAME


def append_event(
    run_dir: str | Path,
    action: str,
    *,
    status: str = "ok",
    actor: str = "deck_master",
    target: str = "",
    payload_ref: str = "",
    error: str = "",
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not action:
        raise ValueError("event action is required.")
    event = {
        "timestamp": utc_now(),
        "actor": actor,
        "action": action,
        "target": target,
        "status": status,
        "payload_ref": payload_ref,
        "error": error,
        "data": data or {},
    }
    path = events_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _infer_status(event_type: str) -> str:
    """根据 event_type 推断默认 status。"""
    mapping = {
        "step_completed": "completed",
        "step_started": "started",
        "error": "error",
    }
    return mapping.get(event_type, "ok")


def append_typed_event(
    run_dir: str | Path,
    event_type: str,
    step: str,
    message: str,
    *,
    run_id: str = "",
    refs: list[str] | None = None,
    severity: str = "info",
    payload: dict[str, Any] | None = None,
    action: str = "",
    status: str = "",
) -> dict[str, Any]:
    """写入 canonical typed event。

    自动补 timestamp/run_id/schema_version。
    如果 action 未提供，默认为 step。
    如果 status 未提供，根据 event_type 推断：
      - step_completed -> "completed"
      - step_started -> "started"
      - error -> "error"
      - 其他 -> "ok"
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type: {event_type}. Must be one of: {', '.join(sorted(EVENT_TYPES))}"
        )

    event: dict[str, Any] = {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "timestamp": utc_now(),
        "run_id": run_id,
        "event_type": event_type,
        "step": step,
        "message": message,
        "refs": refs or [],
        "severity": severity,
        "action": action or step,
        "status": status or _infer_status(event_type),
    }
    if payload:
        event["payload"] = payload

    path = events_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(
    run_dir: str | Path, *, strict: bool = False
) -> list[dict[str, Any]]:
    """读取事件日志。

    strict=False（默认）时跳过坏 JSONL 行。
    strict=True 时遇到坏行抛 ValueError（旧行为）。
    """
    path = events_path(run_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            if strict:
                raise ValueError(
                    f"Invalid event JSON on line {line_number}: {exc.msg}"
                ) from exc
            continue
        if not isinstance(event, dict):
            if strict:
                raise ValueError(f"Event on line {line_number} must be an object.")
            continue
        events.append(event)
    return events
