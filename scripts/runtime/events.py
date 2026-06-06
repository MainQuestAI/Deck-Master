from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS_NAME = "events.jsonl"


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


def read_events(run_dir: str | Path) -> list[dict[str, Any]]:
    path = events_path(run_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid event JSON on line {line_number}: {exc.msg}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Event on line {line_number} must be an object.")
        events.append(event)
    return events
