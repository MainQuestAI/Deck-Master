from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FEEDBACK_EVENTS = {
    "preview_approved",
    "preview_rejected",
    "exported_internal",
    "exported_client",
    "delivered",
    "delivery_positive_signal",
    "delivery_negative_signal",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def feedback_path(workspace_dir: str | Path) -> Path:
    return Path(workspace_dir) / "assets" / "asset_feedback.jsonl"


def append_feedback(
    workspace_dir: str | Path,
    event_type: str,
    canonical_slide_id: str,
    run_id: str = "",
    page_id: str = "",
    notes: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """追加一条 asset feedback。

    event_type 必须是 FEEDBACK_EVENTS 之一。
    JSONL 只能 append，不能整体重写。
    """
    if event_type not in FEEDBACK_EVENTS:
        raise ValueError(f"Invalid feedback event_type: {event_type}")
    if not canonical_slide_id:
        raise ValueError("canonical_slide_id is required")

    entry = {
        "timestamp": utc_now(),
        "event_type": event_type,
        "canonical_slide_id": canonical_slide_id,
        "run_id": run_id,
        "page_id": page_id,
        "notes": notes,
    }
    if payload:
        entry["payload"] = payload

    path = feedback_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_feedback(workspace_dir: str | Path) -> list[dict[str, Any]]:
    """读取所有 feedback。跳过坏行。"""
    path = feedback_path(workspace_dir)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries


def get_asset_feedback_summary(
    workspace_dir: str | Path,
    canonical_slide_id: str,
) -> dict[str, Any]:
    """获取单个 asset 的反馈汇总。

    返回：
    {
        "canonical_slide_id": str,
        "approval_count": int,
        "rejection_count": int,
        "export_count": int,
        "delivered_count": int,
        "total_events": int,
        "latest_event": dict | None,
    }
    """
    all_feedback = read_feedback(workspace_dir)
    asset_feedback = [f for f in all_feedback if f.get("canonical_slide_id") == canonical_slide_id]

    approval_count = sum(1 for f in asset_feedback if f.get("event_type") == "preview_approved")
    rejection_count = sum(1 for f in asset_feedback if f.get("event_type") == "preview_rejected")
    export_count = sum(1 for f in asset_feedback if f.get("event_type") in ("exported_internal", "exported_client"))
    delivered_count = sum(1 for f in asset_feedback if f.get("event_type") == "delivered")

    return {
        "canonical_slide_id": canonical_slide_id,
        "approval_count": approval_count,
        "rejection_count": rejection_count,
        "export_count": export_count,
        "delivered_count": delivered_count,
        "total_events": len(asset_feedback),
        "latest_event": asset_feedback[-1] if asset_feedback else None,
    }


def is_duplicate_feedback(
    workspace_dir: str | Path,
    event_type: str,
    canonical_slide_id: str,
    run_id: str,
    page_id: str,
    *,
    window_seconds: int = 60,
) -> bool:
    """检查是否是重复的 feedback 事件（去重）。"""
    all_feedback = read_feedback(workspace_dir)
    for f in all_feedback:
        if (
            f.get("event_type") == event_type
            and f.get("canonical_slide_id") == canonical_slide_id
            and f.get("run_id") == run_id
            and f.get("page_id") == page_id
        ):
            return True
    return False


def append_feedback_dedup(
    workspace_dir: str | Path,
    event_type: str,
    canonical_slide_id: str,
    run_id: str = "",
    page_id: str = "",
    notes: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """追加 feedback，如果是重复则返回 None。"""
    if is_duplicate_feedback(workspace_dir, event_type, canonical_slide_id, run_id, page_id):
        return None
    return append_feedback(workspace_dir, event_type, canonical_slide_id, run_id, page_id, notes, payload)
