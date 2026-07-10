"""Lightweight Metrics Hooks for Deck Master v0.9.

Implements summarize-run-metrics: compute run metrics from events and artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from feedback.library_feedback import summarize_library_feedback_events
from runtime.events import read_events
from runtime.import_log import summarize_import_log
from runtime.run_state import (
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    RunStateError,
    read_json,
)
from review.readiness import summarize_sourcing_readiness

SCHEMA_VERSION = "deck_run_metrics.v1"


def _parse_timestamp(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _minutes_between(a: datetime, b: datetime) -> float:
    delta = abs((b - a).total_seconds()) / 60.0
    return round(delta, 1)


def _review_status_from_page(page: dict[str, Any]) -> str:
    status = str(page.get("review_status", ""))
    if status:
        return status
    decision = str(page.get("decision", "needs_review"))
    if decision in {"approved", "keep"}:
        return "approved"
    if decision == "rejected":
        return "rejected"
    return "needs_review"


def summarize_run_metrics(run_dir: str | Path) -> dict[str, Any]:
    """Compute run metrics from events and artifacts."""
    root = Path(run_dir).expanduser().resolve()

    request_path = root / "request.json"
    run_id = ""
    if request_path.exists():
        try:
            req = read_json(request_path)
            run_id = str(req.get("run_id", ""))
        except RunStateError:
            pass

    events = read_events(root, strict=False)

    # Extract key timestamps from events.
    first_event_ts: datetime | None = None
    preview_ready_ts: datetime | None = None
    first_quality_gate_ts: datetime | None = None
    approved_queue_ts: datetime | None = None

    for event in events:
        ts = _parse_timestamp(event.get("timestamp", ""))
        if ts and not first_event_ts:
            first_event_ts = ts

        step = event.get("step", event.get("action", ""))

        if "preview" in step.lower() and not preview_ready_ts:
            preview_ready_ts = ts
        if "quality" in step.lower() and "gate" in step.lower() and not first_quality_gate_ts:
            first_quality_gate_ts = ts
        if "approved" in step.lower() and "queue" in step.lower() and not approved_queue_ts:
            approved_queue_ts = ts

    # Fallback to file mtime.
    preview_path = root / PREVIEW_MANIFEST_NAME
    if not preview_ready_ts and preview_path.exists():
        mtime = preview_path.stat().st_mtime
        preview_ready_ts = datetime.fromtimestamp(mtime, tz=timezone.utc)

    quality_dir = root / "quality_reports"
    if not first_quality_gate_ts and quality_dir.exists():
        gate_files = list(quality_dir.glob("*_gate.json"))
        if gate_files:
            oldest = min(gate_files, key=lambda f: f.stat().st_mtime)
            mtime = oldest.stat().st_mtime
            first_quality_gate_ts = datetime.fromtimestamp(mtime, tz=timezone.utc)

    # Compute durations.
    durations: dict[str, Any] = {}
    if first_event_ts and preview_ready_ts:
        durations["created_to_preview_minutes"] = _minutes_between(first_event_ts, preview_ready_ts)
    if preview_ready_ts and first_quality_gate_ts:
        durations["preview_to_first_quality_gate_minutes"] = _minutes_between(
            preview_ready_ts, first_quality_gate_ts
        )

    # Page counts.
    page_tasks_data: dict[str, Any] = {}
    if (root / PAGE_TASKS_NAME).exists():
        try:
            page_tasks_data = read_json(root / PAGE_TASKS_NAME)
        except RunStateError:
            pass

    tasks = page_tasks_data.get("tasks", [])
    preview_data: dict[str, Any] = {}
    if preview_path.exists():
        try:
            preview_data = read_json(preview_path)
        except RunStateError:
            pass
    pages = preview_data.get("pages", [])
    page_source = pages if pages else tasks
    total_pages = len(page_source)
    approved = sum(1 for p in page_source if isinstance(p, dict) and _review_status_from_page(p) == "approved")
    rejected = sum(1 for p in page_source if isinstance(p, dict) and _review_status_from_page(p) == "rejected")
    needs_review = total_pages - approved - rejected

    sourcing_readiness = summarize_sourcing_readiness(root, fallback_tasks=tasks)
    source_counts = sourcing_readiness["decision_counts"]

    # Quality finding counts.
    p0_total = 0
    p1_total = 0
    p2_total = 0
    blocking_reports = 0
    if quality_dir.exists():
        for gate_file in quality_dir.glob("*_gate.json"):
            try:
                report = read_json(gate_file)
            except RunStateError:
                continue
            summary = report.get("summary", {})
            p0_total += summary.get("p0_count", 0)
            p1_total += summary.get("p1_count", 0)
            p2_total += summary.get("p2_count", 0)
            if (
                report.get("blocks_delivery")
                or report.get("status") == "rework_required"
                or summary.get("p0_count", 0)
                or summary.get("p1_count", 0)
            ):
                blocking_reports += 1

    import_summary = summarize_import_log(root)
    feedback_summary = summarize_library_feedback_events(root)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": first_event_ts.isoformat() if first_event_ts else "",
        "preview_ready_at": preview_ready_ts.isoformat() if preview_ready_ts else "",
        "first_quality_gate_at": first_quality_gate_ts.isoformat() if first_quality_gate_ts else "",
        "approved_queue_created_at": approved_queue_ts.isoformat() if approved_queue_ts else "",
        "durations": durations,
        "counts": {
            "pages": total_pages,
            "approved": approved,
            "rejected": rejected,
            "needs_review": needs_review,
            "reuse": source_counts.get("reuse", 0),
            "adapt": source_counts.get("adapt", 0),
            "generate": source_counts.get("generate", 0),
            "manual_placeholder": source_counts.get("manual", 0),
            "quality_findings": p0_total + p1_total + p2_total,
            "p0": p0_total,
            "p1": p1_total,
            "p2": p2_total,
            "blocking_quality_reports": blocking_reports,
            "imports": import_summary["total"],
            "pending_library_feedback": feedback_summary["pending"],
        },
        "imports": import_summary,
        "library_feedback": feedback_summary,
        "sourcing_readiness": sourcing_readiness,
    }
