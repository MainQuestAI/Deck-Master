"""Workspace Learning Pack for Deck Master v0.9.

Aggregates feedback from past runs into a learning pack that external Agents
can read before the next run.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.run_state import RunStateError, read_json

SCHEMA_VERSION = "deck_workspace_learning_pack.v1"
LEARNING_DIR = "learning"
PACK_FILENAME = "workspace_learning_pack.json"
SUMMARY_FILENAME = "agent_context_summary.md"


def _safe_read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except RunStateError:
        return None


def _safe_read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _find_run_dirs(workspace_dir: Path) -> list[Path]:
    """Find all run directories under a workspace's runs/."""
    runs_dir = workspace_dir / "runs"
    if not runs_dir.exists():
        return []
    return [d for d in sorted(runs_dir.iterdir()) if d.is_dir()]


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def _aggregate_feedback(workspace_dir: Path) -> dict[str, Any]:
    """Aggregate asset feedback from workspace."""
    feedback_path = workspace_dir / "assets" / "asset_feedback.jsonl"
    entries = _safe_read_jsonl(feedback_path)

    approval_counter: Counter[str] = Counter()
    rejection_counter: Counter[str] = Counter()
    delivered_counter: Counter[str] = Counter()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event = entry.get("event_type", "")
        slide_id = entry.get("canonical_slide_id", "")
        if not slide_id:
            continue
        if event in ("preview_approved", "exported_client", "exported_internal"):
            approval_counter[slide_id] += 1
        elif event == "preview_rejected":
            rejection_counter[slide_id] += 1
        elif event in ("delivered", "delivery_positive_signal"):
            delivered_counter[slide_id] += 1

    return {
        "approval_counter": dict(approval_counter),
        "rejection_counter": dict(rejection_counter),
        "delivered_counter": dict(delivered_counter),
    }


def _aggregate_failure_modes(workspace_dir: Path) -> list[dict[str, Any]]:
    """Aggregate quality failure modes from run quality reports."""
    message_counter: Counter[str] = Counter()
    message_repair: dict[str, str] = {}

    for run_dir in _find_run_dirs(workspace_dir):
        quality_dir = run_dir / "quality_reports"
        if not quality_dir.exists():
            continue
        for gate_file in quality_dir.glob("*_gate.json"):
            report = _safe_read(gate_file)
            if not report:
                continue
            for f in report.get("findings", []):
                if not isinstance(f, dict):
                    continue
                msg = f.get("message", "")[:80]
                if msg:
                    message_counter[msg] += 1
                    repair = f.get("repair_instruction", "")
                    if repair:
                        message_repair[msg] = repair

    result: list[dict[str, Any]] = []
    for i, (msg, count) in enumerate(message_counter.most_common(10), start=1):
        result.append({
            "failure_id": f"failure_{i:03d}",
            "description": msg,
            "count": count,
            "repair_instruction": message_repair.get(msg, ""),
        })
    return result


def _aggregate_strong_assets(workspace_dir: Path) -> list[dict[str, Any]]:
    """Identify strong assets from feedback and delivery data."""
    fb = _aggregate_feedback(workspace_dir)
    approval = fb["approval_counter"]
    delivered = fb["delivered_counter"]

    # Combine approval and delivery counts.
    all_slides = set(approval.keys()) | set(delivered.keys())
    assets: list[dict[str, Any]] = []

    for slide_id in all_slides:
        app_count = approval.get(slide_id, 0)
        del_count = delivered.get(slide_id, 0)
        total = app_count + del_count
        if total == 0:
            continue
        approval_rate = app_count / total if total > 0 else 0.0
        assets.append({
            "canonical_slide_id": slide_id,
            "approval_rate": round(approval_rate, 2),
            "delivered_count": del_count,
            "approved_count": app_count,
        })

    # Sort by delivered_count desc, then approval_rate desc.
    assets.sort(key=lambda a: (a["delivered_count"], a["approval_rate"]), reverse=True)
    return assets[:10]


def _build_agent_guidance(failure_modes: list[dict[str, Any]], strong_assets: list[dict[str, Any]]) -> list[str]:
    """Build agent guidance from failure modes and strong assets."""
    guidance: list[str] = []
    for fm in failure_modes[:3]:
        desc = fm.get("description", "")
        repair = fm.get("repair_instruction", "")
        if repair:
            guidance.append(f"遇到 '{desc[:40]}' 问题时：{repair}")
        elif desc:
            guidance.append(f"避免重复问题：'{desc[:50]}'。")

    for asset in strong_assets[:2]:
        sid = asset.get("canonical_slide_id", "")
        if asset.get("approval_rate", 0) >= 0.8:
            guidance.append(f"优先使用高通过率资产 {sid}（approval rate {asset['approval_rate']:.0%}）。")

    return guidance


# --------------------------------------------------------------------------- #
# Build pack
# --------------------------------------------------------------------------- #


def build_learning_pack(workspace_dir: str | Path) -> dict[str, Any]:
    """Build workspace learning pack JSON."""
    ws = Path(workspace_dir).expanduser().resolve()

    failure_modes = _aggregate_failure_modes(ws)
    strong_assets = _aggregate_strong_assets(ws)
    guidance = _build_agent_guidance(failure_modes, strong_assets)

    pack: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workspace": ws.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "high_value_patterns": [],
        "frequent_failure_modes": failure_modes,
        "strong_assets": strong_assets,
        "agent_guidance": guidance,
    }

    # Write to workspace.
    learning_dir = ws / LEARNING_DIR
    learning_dir.mkdir(parents=True, exist_ok=True)
    pack_path = learning_dir / PACK_FILENAME
    pack_path.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Write markdown summary.
    summary_path = learning_dir / SUMMARY_FILENAME
    summary_path.write_text(_build_markdown_summary(pack), encoding="utf-8")

    return pack


def _build_markdown_summary(pack: dict[str, Any]) -> str:
    lines: list[str] = ["# Workspace Learning Summary\n"]

    lines.append("## Frequent failure modes")
    fms = pack.get("frequent_failure_modes", [])
    if not fms:
        lines.append("- No failure modes recorded yet.\n")
    else:
        for fm in fms[:5]:
            desc = fm.get("description", "")
            repair = fm.get("repair_instruction", "")
            count = fm.get("count", 0)
            line = f"- {desc}（{count} 次）"
            if repair:
                line += f"：{repair}"
            lines.append(line)
        lines.append("")

    lines.append("## Strong assets")
    assets = pack.get("strong_assets", [])
    if not assets:
        lines.append("- No strong assets recorded yet.\n")
    else:
        for a in assets[:5]:
            sid = a.get("canonical_slide_id", "")
            rate = a.get("approval_rate", 0)
            delivered = a.get("delivered_count", 0)
            lines.append(f"- {sid}：approval rate {rate:.0%}, delivered {delivered} 次。")
        lines.append("")

    lines.append("## Agent guidance")
    guidance = pack.get("agent_guidance", [])
    if not guidance:
        lines.append("- No guidance yet. Run more decks to build guidance.\n")
    else:
        for g in guidance:
            lines.append(f"- {g}")
        lines.append("")

    return "\n".join(lines) + "\n"


def show_learning_pack(workspace_dir: str | Path) -> dict[str, Any]:
    """Read and return the existing learning pack."""
    ws = Path(workspace_dir).expanduser().resolve()
    pack_path = ws / LEARNING_DIR / PACK_FILENAME
    if not pack_path.exists():
        return {
            "status": "not_found",
            "workspace": ws.name,
            "message": "No learning pack found. Run build-learning-pack first.",
        }
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    return {"status": "found", "workspace": ws.name, "pack": pack}
