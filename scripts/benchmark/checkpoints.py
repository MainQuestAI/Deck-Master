from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event, utc_now
from runtime.run_state import read_json, write_json


SCHEMA_VERSION = "deck_benchmark_checkpoints.v1"
CHECKPOINTS_NAME = "benchmark_checkpoints.json"
ALLOWED_CHECKPOINTS = {
    "context_ready",
    "preview_ready",
    "human_review_started",
    "human_review_completed",
    "approved_queue_ready",
    "final_delivery_ready",
}


class BenchmarkCheckpointError(ValueError):
    pass


def _normalize_timestamp(timestamp: str | datetime | None) -> str:
    if timestamp is None:
        return utc_now()
    if isinstance(timestamp, datetime):
        value = timestamp
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(timestamp, str) and timestamp.strip():
        _parse_timestamp(timestamp)
        return timestamp.strip()
    raise BenchmarkCheckpointError("timestamp must be an ISO timestamp when provided.")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkCheckpointError("checkpoint timestamp is missing.")
    raw = value.strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise BenchmarkCheckpointError(f"Invalid checkpoint timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _run_id_from_dir(run_dir: Path) -> str:
    request_path = run_dir / "request.json"
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return run_dir.name
        if isinstance(request, dict):
            return str(request.get("run_id") or run_dir.name)
    return run_dir.name


def _empty_payload(run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": _run_id_from_dir(run_dir),
        "updated_at": utc_now(),
        "checkpoints": {},
    }


def read_benchmark_checkpoints(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    path = root / CHECKPOINTS_NAME
    if not path.exists():
        return _empty_payload(root)
    payload = read_json(path)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkCheckpointError(f"schema_version must be {SCHEMA_VERSION}.")
    checkpoints = payload.get("checkpoints")
    if not isinstance(checkpoints, dict):
        raise BenchmarkCheckpointError("checkpoints must be an object.")
    return payload


def write_benchmark_checkpoint(
    run_dir: str | Path,
    checkpoint: str,
    *,
    timestamp: str | datetime | None = None,
    note: str = "",
) -> dict[str, Any]:
    if checkpoint not in ALLOWED_CHECKPOINTS:
        allowed = ", ".join(sorted(ALLOWED_CHECKPOINTS))
        raise BenchmarkCheckpointError(f"checkpoint must be one of: {allowed}.")

    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    payload = read_benchmark_checkpoints(root)
    checkpoint_timestamp = _normalize_timestamp(timestamp)
    payload["run_id"] = str(payload.get("run_id") or _run_id_from_dir(root))
    payload["updated_at"] = utc_now()
    payload.setdefault("checkpoints", {})[checkpoint] = {
        "timestamp": checkpoint_timestamp,
        "note": str(note or ""),
    }
    write_json(root / CHECKPOINTS_NAME, payload)

    append_typed_event(
        root,
        "manual_action",
        step=f"benchmark_checkpoint.{checkpoint}",
        message=f"Benchmark checkpoint recorded: {checkpoint}",
        run_id=str(payload["run_id"]),
        refs=[CHECKPOINTS_NAME],
        payload={
            "checkpoint": checkpoint,
            "checkpoint_timestamp": checkpoint_timestamp,
            "note": str(note or ""),
        },
        action="benchmark.checkpoint.recorded",
    )
    return payload


def calculate_human_review_minutes(checkpoints_or_run_dir: dict[str, Any] | str | Path) -> float | None:
    if isinstance(checkpoints_or_run_dir, dict):
        payload = checkpoints_or_run_dir
    else:
        payload = read_benchmark_checkpoints(checkpoints_or_run_dir)
    checkpoints = payload.get("checkpoints", {})
    if not isinstance(checkpoints, dict):
        raise BenchmarkCheckpointError("checkpoints must be an object.")

    started = checkpoints.get("human_review_started")
    completed = checkpoints.get("human_review_completed")
    if not isinstance(started, dict) or not isinstance(completed, dict):
        return None

    start_time = _parse_timestamp(started.get("timestamp"))
    completed_time = _parse_timestamp(completed.get("timestamp"))
    minutes = (completed_time - start_time).total_seconds() / 60
    if minutes < 0:
        raise BenchmarkCheckpointError("human_review_completed must be after human_review_started.")
    return minutes
