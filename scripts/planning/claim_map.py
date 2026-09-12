from __future__ import annotations

from typing import Any
import copy


EVIDENCE_KEYWORDS = ("案例", "截图", "数据", "指标", "证明", "结果", "转写", "会议", "原话")


def evidence_fragments(context_manifest: dict[str, Any]) -> list[dict[str, str]]:
    fragments: list[dict[str, str]] = []
    for source in context_manifest.get("sources", []):
        if not isinstance(source, dict):
            continue
        text = f"{source.get('name', '')} {source.get('summary', '')} {source.get('excerpt', '')}"
        if any(keyword in text for keyword in EVIDENCE_KEYWORDS):
            fragments.append(
                {
                    "source_id": str(source.get("source_id", "")),
                    "kind": str(source.get("kind", "")),
                    "summary": str(source.get("summary", "")),
                }
            )
    return fragments


def build_claim_map(deck_brief: dict[str, Any], context_manifest: dict[str, Any], *, run_dir=None) -> dict[str, Any]:
    from conversation.brief_compiler import brief_conflict_blockers
    blockers = brief_conflict_blockers(deck_brief, context_manifest, run_dir=run_dir)
    if blockers:
        raise ValueError("Unresolved declared source conflict blocks claim compilation: " + ", ".join(b["conflict_id"] for b in blockers))
    fragments = evidence_fragments(context_manifest)
    claims = []
    assumptions = [copy.deepcopy(a) for a in deck_brief.get("working_assumptions", []) if isinstance(a, dict)]
    for index, point in enumerate(deck_brief.get("core_points", []), start=1):
        text = str(point).strip()
        if not text:
            continue
        # SC-1 F02: a resolvable reference is not reviewed evidence. Claims
        # with candidate fragments carry evidence_unreviewed, not a clean bill.
        if fragments:
            risk_flags = ["evidence_unreviewed"]
        else:
            risk_flags = ["evidence_gap"]
        bound_assumptions = [a for a in assumptions if str(a.get("statement") or "").strip() in (text, text.removeprefix("工作假设：").strip()) or f"claim_{index:02d}" in a.get("claim_refs", [])]
        claims.append(
            {
                "claim_id": f"claim_{index:02d}",
                "claim": text,
                "why_it_matters": f"该判断支撑 {deck_brief.get('business_goal', '本次方案目标')}。",
                "supporting_arguments": [
                    "明确业务问题和目标状态。",
                    "连接产品能力、业务场景和可验证证据。",
                ],
                "evidence_needed": ["客户案例、产品截图、业务数据或会议原话"],
                "evidence_refs": [fragment["source_id"] for fragment in fragments[:3]],
                "risk_flags": risk_flags,
                "working_assumptions": bound_assumptions,
                "fact_kind": "working_assumption" if bound_assumptions else "analysis_judgment",
                "support_status": "unsupported",
            }
        )
    if not claims:
        claims.append(
            {
                "claim_id": "claim_01",
                "claim": str(deck_brief.get("business_goal") or "明确客户问题并给出解决方案"),
                "why_it_matters": "没有核心论点，Deck 会退化成材料堆叠。",
                "supporting_arguments": [],
                "evidence_needed": ["需要补充核心观点和证据"],
                "evidence_refs": [],
                "risk_flags": ["missing_core_claim", "evidence_gap"],
            }
        )
    return {
        "run_id": deck_brief.get("run_id", ""),
        "title": deck_brief.get("project_name", "Deck Master Run"),
        "claims": claims,
        "working_assumptions": assumptions,
        "source_refs": deck_brief.get("source_refs", []),
        "risk_flags": sorted({flag for claim in claims for flag in claim.get("risk_flags", [])}),
    }
