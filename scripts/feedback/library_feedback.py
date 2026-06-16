from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.import_log import append_import_log
from runtime.run_state import assert_external_result_matches_run, ensure_run_dirs, read_json

FEEDBACK_SCHEMA_VERSION = "deck_master_ppt_library_feedback_event.v1"
FEEDBACK_QUEUE = "external/ppt_library/library_feedback_events.jsonl"
VALID_OUTCOMES = {"approved", "rejected", "used", "unused", "won", "lost", "unknown"}


class LibraryFeedbackError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_library_feedback_events(run_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir).expanduser().resolve() / FEEDBACK_QUEUE
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def summarize_library_feedback_events(run_dir: str | Path) -> dict[str, Any]:
    events = read_library_feedback_events(run_dir)
    pending = [event for event in events if event.get("status") == "pending"]
    by_outcome: dict[str, int] = {}
    for event in pending:
        outcome = str(event.get("outcome") or "unknown")
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
    return {
        "schema_version": "deck_master_library_feedback_summary.v1",
        "total": len(events),
        "pending": len(pending),
        "by_outcome": by_outcome,
        "latest": events[-1] if events else None,
    }


def _event_from_input(input_path: str | Path | None) -> dict[str, Any]:
    if not input_path:
        return {}
    payload = read_json(Path(input_path).expanduser().resolve())
    return payload


def record_library_feedback(
    run_dir: str | Path,
    *,
    run_id: str,
    page_task_id: str = "",
    beat_id: str = "",
    candidate_id: str = "",
    outcome: str = "",
    input_path: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    payload = _event_from_input(input_path)
    page_task_id = str(payload.get("page_task_id") or page_task_id or "")
    beat_id = str(payload.get("beat_id") or beat_id or "")
    candidate_id = str(payload.get("candidate_id") or candidate_id or "")
    outcome = str(payload.get("outcome") or outcome or "")
    run_id = str(payload.get("run_id") or run_id or "")

    missing = [
        name
        for name, value in {
            "run_id": run_id,
            "page_task_id": page_task_id,
            "beat_id": beat_id,
            "candidate_id": candidate_id,
            "outcome": outcome,
        }.items()
        if not value
    ]
    if missing:
        raise LibraryFeedbackError("Missing required fields: " + ", ".join(missing))
    if outcome not in VALID_OUTCOMES:
        raise LibraryFeedbackError(f"outcome must be one of {sorted(VALID_OUTCOMES)}.")
    try:
        assert_external_result_matches_run(root, run_id, artifact_name="library feedback")
    except Exception as exc:
        raise LibraryFeedbackError(str(exc)) from exc

    if apply:
        raise LibraryFeedbackError("--apply is experimental and is not implemented in v0.9.12.")

    idempotency_key = f"{run_id}/{page_task_id}/{beat_id}/{candidate_id}/{outcome}"
    existing = read_library_feedback_events(root)
    if any(event.get("idempotency_key") == idempotency_key for event in existing):
        return {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "status": "duplicate",
            "idempotency_key": idempotency_key,
            "queue_path": FEEDBACK_QUEUE,
        }

    event = {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "timestamp": _utc_now(),
        "run_id": run_id,
        "page_task_id": page_task_id,
        "beat_id": beat_id,
        "candidate_id": candidate_id,
        "outcome": outcome,
        "status": "pending",
        "idempotency_key": idempotency_key,
        "source": "deck-master",
    }
    if payload.get("notes"):
        event["notes"] = str(payload["notes"])

    queue_path = root / FEEDBACK_QUEUE
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    append_import_log(
        root,
        import_type="library_feedback",
        source="deck-master",
        status="queued",
        source_path=input_path,
        canonical_refs=[FEEDBACK_QUEUE],
        payload={"idempotency_key": idempotency_key, "outcome": outcome},
    )
    return {
        **event,
        "queue_path": FEEDBACK_QUEUE,
    }
