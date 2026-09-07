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
    """Aggregate asset feedback by reviewed revision (SC-1 C4/F01).

    The statistical unit is (asset, run, reviewed revision); the final
    review decision of that unit is what counts — an earlier approve that is
    explicitly superseded by a later reject is not double counted. Events
    without a revision identity go to ``legacy_unknown`` and are NOT folded
    into the acceptance rate. Delivery counting stays independent of the
    outcome; repeated exports do not lift the rate.
    """

    feedback_path = workspace_dir / "assets" / "asset_feedback.jsonl"
    entries = _safe_read_jsonl(feedback_path)

    final_decisions: dict[tuple[str, str, str], str] = {}
    legacy_unknown = 0
    delivered_counter: Counter[str] = Counter()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event = entry.get("event_type", "")
        slide_id = entry.get("canonical_slide_id", "")
        if not slide_id:
            continue
        if event in ("delivered", "delivery_positive_signal", "exported_client", "exported_internal"):
            # delivery signals stay independent of the review outcome
            delivered_counter[slide_id] += 1
        if event not in ("preview_approved", "preview_rejected", "exported_client", "exported_internal"):
            continue
        outcome = "accepted" if event in ("preview_approved", "exported_client", "exported_internal") else "rejected"
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        run_id = str(entry.get("run_id") or payload.get("run_id") or "")
        revision = str(entry.get("reviewed_revision") or payload.get("reviewed_revision") or "").strip()
        if not run_id and not revision:
            # Legacy event without any dedup key: recorded separately, never
            # guessed into a review group.
            legacy_unknown += 1
            continue
        key = (slide_id, run_id, revision)
        # Later events in the file supersede earlier ones for the same unit.
        final_decisions[key] = outcome

    per_slide: dict[str, dict[str, int]] = defaultdict(lambda: {"accepted": 0, "rejected": 0})
    for (slide_id, _run, _rev), outcome in final_decisions.items():
        per_slide[slide_id][outcome] += 1

    return {
        "final_decisions": final_decisions,
        "per_slide": dict(per_slide),
        "legacy_unknown": legacy_unknown,
        "delivered_counter": dict(delivered_counter),
    }


def _aggregate_strong_assets(workspace_dir: Path) -> dict[str, Any]:
    """Acceptance rate = accepted / (accepted + rejected) over final review
    decisions, deduped by reviewed revision. Delivery count is display-only."""

    fb = _aggregate_feedback(workspace_dir)
    per_slide = fb["per_slide"]
    delivered = fb["delivered_counter"]

    assets: list[dict[str, Any]] = []
    for slide_id, counts in per_slide.items():
        accepted = counts["accepted"]
        rejected = counts["rejected"]
        review_total = accepted + rejected
        if review_total == 0:
            continue
        acceptance_rate = accepted / review_total
        assets.append({
            "canonical_slide_id": slide_id,
            # Kept for schema compatibility; the acceptance rate now counts
            # rejections — the legacy "approved/(approved+delivered)" value
            # no longer feeds any ranking.
            "approval_rate": round(acceptance_rate, 4),
            "acceptance_rate": round(acceptance_rate, 4),
            "accepted_count": accepted,
            "rejected_count": rejected,
            "reviewed_count": review_total,
            "delivered_count": delivered.get(slide_id, 0),
        })

    # Outcome first: repeated exports must not lift an asset's rank.
    assets.sort(key=lambda a: (a["acceptance_rate"], a["reviewed_count"], a["delivered_count"]), reverse=True)
    return {
        "assets": assets[:10],
        "legacy_unknown": fb["legacy_unknown"],
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
        rate = asset.get("acceptance_rate", asset.get("approval_rate", 0))
        reviewed = asset.get("reviewed_count", 0)
        if rate >= 0.8:
            # Small samples show counts, never generalize from one acceptance.
            sample_note = f"（n={reviewed}，样本量小，仅作参考）" if reviewed < 5 else f"（n={reviewed}）"
            guidance.append(f"优先考虑高接受率资产 {sid}（acceptance rate {rate:.0%} {sample_note}）。")

    return guidance


def _build_experience_cards(workspace_dir: Path) -> list[dict[str, Any]]:
    """SC-1 C4: limited experience cards, built ONLY from real feedback.

    Minimal record: the applicable problem, the adopted structure/mechanism,
    why the user modified or kept it, the evidence source category, the
    applicable/not-applicable scope, and the source run reference with its
    approval scope. Customer facts never become cross-project knowledge
    automatically — cards carry source refs, not copied material.
    """

    feedback_path = workspace_dir / "assets" / "asset_feedback.jsonl"
    entries = _safe_read_jsonl(feedback_path)
    cards: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        slide_id = str(entry.get("canonical_slide_id") or "")
        run_id = str(entry.get("run_id") or payload.get("run_id") or "")
        revision = str(entry.get("reviewed_revision") or payload.get("reviewed_revision") or "").strip()
        key = (slide_id, run_id, revision)
        if not slide_id or key in seen:
            continue
        seen.add(key)
        event = str(entry.get("event_type") or "")
        notes = str(entry.get("notes") or payload.get("notes") or "").strip()
        if not notes:
            continue
        cards.append(
            {
                "card_id": f"exp_{len(cards) + 1:03d}",
                "applicable_problem": slide_id,
                "adopted_structure": str(payload.get("adopted_structure") or ""),
                "user_reason": notes[:300],
                "kept_or_modified": "modified" if event == "preview_rejected" else "kept",
                "evidence_source_category": str(payload.get("evidence_source_category") or "run_feedback"),
                "applicable_scope": str(payload.get("applicable_scope") or ""),
                "not_applicable_scope": str(payload.get("not_applicable_scope") or ""),
                "source_run_ref": run_id,
                "approval_scope": str(payload.get("approval_scope") or "workspace_feedback"),
                "recorded_at": str(entry.get("timestamp") or ""),
            }
        )
    return cards[:20]


# --------------------------------------------------------------------------- #
# Build pack
# --------------------------------------------------------------------------- #


def build_learning_pack(workspace_dir: str | Path) -> dict[str, Any]:
    """Build workspace learning pack JSON."""
    ws = Path(workspace_dir).expanduser().resolve()

    failure_modes = _aggregate_failure_modes(ws)
    assets_result = _aggregate_strong_assets(ws)
    strong_assets = assets_result["assets"]
    guidance = _build_agent_guidance(failure_modes, strong_assets)
    experience_cards = _build_experience_cards(ws)

    pack: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workspace": ws.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "high_value_patterns": [],
        "frequent_failure_modes": failure_modes,
        "strong_assets": strong_assets,
        "agent_guidance": guidance,
        # SC-1 C4: legacy events without a dedup key are counted, never
        # folded into acceptance stats.
        "legacy_feedback_unknown": assets_result["legacy_unknown"],
        "experience_cards": experience_cards,
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
