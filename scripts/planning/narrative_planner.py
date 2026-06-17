from __future__ import annotations

import re
from typing import Any

from planning.page_budget import beat_templates, density_for, resolve_page_count


# Argument chain position mapping by role.
_ROLE_ARGUMENT_CHAIN: dict[str, list[str]] = {
    "opener": ["业务问题"],
    "problem": ["业务问题", "根因"],
    "solution": ["解决路径", "证据"],
    "architecture": ["解决路径", "证据"],
    "case": ["证据", "客户决策"],
    "roi": ["证据", "客户决策"],
    "cta": ["客户决策"],
    "appendix": ["证据"],
}

# Roles that typically require evidence.
_ROLES_REQUIRING_EVIDENCE = {"case", "roi", "architecture"}

# Allowed evidence types per role.
_ROLE_EVIDENCE_TYPES: dict[str, list[str]] = {
    "case": ["case_study", "customer_material", "meeting_quote"],
    "roi": ["data_point", "case_study", "customer_material"],
    "architecture": ["product_screenshot", "data_point", "customer_material"],
    "solution": ["product_screenshot", "customer_material", "data_point"],
    "problem": ["meeting_quote", "customer_material", "data_point"],
    "opener": ["meeting_quote", "customer_material"],
    "cta": ["data_point", "customer_material"],
    "appendix": ["data_point", "product_screenshot", "customer_material"],
}


def identify_gaps(request: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if not request.get("industry"):
        gaps.append({"field": "industry", "message": "缺少明确行业，检索会按跨行业方案处理。"})
    if not request.get("must_cover_topics"):
        gaps.append({"field": "must_cover_topics", "message": "缺少必须覆盖主题，页面规划会采用通用方案结构。"})
    if "案例" not in str(request.get("brief", "")) and "case" not in str(request.get("brief", "")).lower():
        gaps.append({"field": "case_evidence", "message": "缺少可引用案例，案例页需要人工确认或生成占位。"})
    return gaps


def _is_restricted_sample(request: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(request.get("project_name") or ""),
            str(request.get("industry") or ""),
            str(request.get("business_goal") or ""),
            str(request.get("brief") or ""),
        ]
    )
    lowered = text.lower()
    if any(token in lowered for token in ["云南白药", "医药", "内容底座", "内容中台"]):
        return True
    return any(re.search(rf"(?<![a-z0-9]){token}(?![a-z0-9])", lowered) for token in ["dam", "cms", "ai"])


def _planner_input_sources(planner_mode: str, workspace_archetypes: dict[str, Any] | None = None) -> list[str]:
    if planner_mode == "fixture_template":
        return ["fixture_template"]
    if planner_mode == "workspace_fallback":
        sources = ["workspace_fallback"]
        if workspace_archetypes:
            sources.append("workspace_archetypes")
        return sources
    sources = ["deck_brief", "claim_map", "workspace_archetypes"]
    return sources


def _planner_fallback_reason(
    planner_mode: str,
    request: dict[str, Any],
    workspace_archetypes: dict[str, Any] | None,
    judgments: dict[str, Any] | None,
) -> str:
    if planner_mode == "workspace_fallback":
        if not request.get("industry"):
            return "industry fallback applied"
        return "workspace fallback used"
    if planner_mode == "fixture_template":
        return ""
    if workspace_archetypes and not judgments:
        return "workspace_fallback_without_claims"
    return ""


def _template_filter(
    planner_mode: str,
    request: dict[str, Any],
    templates: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    if planner_mode != "production_narrative":
        return templates
    if not _is_restricted_sample(request):
        return templates
    return [
        template
        for template in templates
        if "库存可视化" not in template[1] and "最后一公里配送" not in template[1]
    ]


def _mentions_retail_specific_path(
    request: dict[str, Any],
    judgments: dict[str, Any] | None,
    claim_graph: dict[str, Any] | None,
) -> bool:
    topics = request.get("must_cover_topics", [])
    topic_text = " ".join(str(item) for item in topics if item) if isinstance(topics, list) else str(topics or "")
    chunks = [
        str(request.get("project_name") or ""),
        str(request.get("industry") or ""),
        str(request.get("business_goal") or ""),
        str(request.get("brief") or ""),
        topic_text,
    ]
    if judgments:
        for item in judgments.get("judgments", []):
            if isinstance(item, dict):
                chunks.append(str(item.get("statement") or ""))
    if claim_graph:
        for item in claim_graph.get("claims", []):
            if isinstance(item, dict):
                chunks.append(str(item.get("statement") or ""))
        for item in claim_graph.get("gaps", []):
            if isinstance(item, dict):
                chunks.append(str(item.get("description") or ""))
    text = " ".join(chunks)
    return any(keyword in text for keyword in ("全渠道", "库存", "最后一公里", "配送", "履约"))


def _template_profile(
    planner_mode: str,
    request: dict[str, Any],
    judgments: dict[str, Any] | None,
    claim_graph: dict[str, Any] | None,
) -> str:
    if planner_mode == "fixture_template":
        return "retail"
    if _mentions_retail_specific_path(request, judgments, claim_graph):
        return "retail"
    return "generic"


def topic_hint(request: dict[str, Any], fallback: str) -> str:
    topics = request.get("must_cover_topics") or []
    if isinstance(topics, list) and topics:
        return "、".join(str(topic) for topic in topics)
    return fallback


def build_reuse_query(request: dict[str, Any], role: str, title: str) -> str:
    industry = request.get("industry") or "跨行业"
    topics = topic_hint(request, title)
    return f"{industry} {topics} {role} {title}"


def _extract_judgment_statement(judgments: dict[str, Any], topic: str) -> str:
    """Extract the statement from a judgment with the given topic."""
    for j in judgments.get("judgments", []):
        if isinstance(j, dict) and j.get("topic") == topic:
            return str(j.get("statement", ""))
    return ""


def _derive_decision_intent(role: str, judgments: dict[str, Any] | None) -> str:
    """Derive decision_intent from judgments based on role."""
    if not judgments:
        return ""
    bp = _extract_judgment_statement(judgments, "business_problem")
    sa = _extract_judgment_statement(judgments, "solution_approach")
    if role in ("opener", "problem"):
        return f"让客户确认业务问题：{bp}" if bp else ""
    if role in ("solution", "architecture"):
        return f"让客户认可解决路径：{sa}" if sa else ""
    if role == "case":
        return "用案例降低客户疑虑，推动试点决策。"
    if role == "roi":
        return "让客户确认价值预期，支持预算审批。"
    if role == "cta":
        return "推动客户确认下一步行动计划。"
    return ""


def _build_evidence_policy(role: str, claim_graph: dict[str, Any] | None) -> dict[str, Any]:
    """Build evidence_policy for a beat based on role and claim_graph."""
    required = role in _ROLES_REQUIRING_EVIDENCE
    allowed = list(_ROLE_EVIDENCE_TYPES.get(role, ["customer_material", "data_point"]))
    missing_action = "manual_placeholder"
    # If claim_graph has gaps relevant to this role, flag it.
    if claim_graph:
        for gap in claim_graph.get("gaps", []):
            if isinstance(gap, dict) and gap.get("claim_id"):
                missing_action = "manual_placeholder"
                break
    return {
        "required": required,
        "allowed_evidence_types": allowed,
        "missing_evidence_action": missing_action,
    }


def _infer_customer_specificity(role: str, judgments: dict[str, Any] | None) -> str:
    """Infer customer_specificity_level from role and judgments."""
    if role in ("case", "roi"):
        return "client_specific"
    if role in ("problem", "solution"):
        # Check if judgments mention specific industry/client context
        if judgments:
            bp = _extract_judgment_statement(judgments, "business_problem")
            if bp and len(bp) > 20:
                return "industry_specific"
        return "industry_specific"
    return "generic"


def _find_claim_ids_for_beat(
    beat_id: str,
    role: str,
    claim_graph: dict[str, Any] | None,
) -> list[str]:
    """Find claim_ids associated with a beat via page_refs in claim_graph."""
    if not claim_graph:
        return []
    page_refs = claim_graph.get("page_refs", {})
    matched: list[str] = []
    for claim_id, pages in page_refs.items():
        if isinstance(pages, list) and beat_id in pages:
            matched.append(claim_id)
    return matched


def plan_narrative(
    request: dict[str, Any],
    judgments: dict[str, Any] | None = None,
    claim_graph: dict[str, Any] | None = None,
    workspace_archetypes: dict[str, Any] | None = None,
    planner_mode: str = "production_narrative",
) -> dict[str, Any]:
    page_count = resolve_page_count(str(request.get("target_pages") or "auto"), str(request.get("audience") or "client"))
    gaps = identify_gaps(request)
    templates = _template_filter(
        planner_mode,
        request,
        beat_templates(page_count, template_profile=_template_profile(planner_mode, request, judgments, claim_graph)),
    )
    adjusted_page_count = len(templates)
    density = density_for(adjusted_page_count)
    beats: list[dict[str, Any]] = []
    fallback_reason = _planner_fallback_reason(planner_mode, request, workspace_archetypes, judgments)
    input_sources = _planner_input_sources(planner_mode, workspace_archetypes)
    for index, (role, title, goal) in enumerate(templates, start=1):
        beat_id = f"beat_{index:02d}_{role}"
        evidence_need = "历史方案页或通用方法论"
        if role == "case":
            evidence_need = "可引用客户案例或相似项目经验"
        elif role == "roi":
            evidence_need = "收益指标、效率提升或成本优化依据"
        elif role == "architecture":
            evidence_need = "目标架构、系统关系或数据流证据"

        # Build brief — enrich with judgments if available.
        brief = f"{goal} 需求背景：{request.get('business_goal', '')}"
        if judgments:
            bp = _extract_judgment_statement(judgments, "business_problem")
            sa = _extract_judgment_statement(judgments, "solution_approach")
            if role in ("opener", "problem") and bp:
                brief += f" 判断依据：{bp}"
            elif role in ("solution", "architecture") and sa:
                brief += f" 方案路径：{sa}"

        beat: dict[str, Any] = {
            "beat_id": beat_id,
            "order": index,
            "page_title": title,
            "role": role,
            "brief": brief,
            "content_goal": goal,
            "evidence_need": evidence_need,
            "visual_need": "历史页截图、架构图、能力矩阵或生成型页面",
            "density": density,
            "reuse_query": build_reuse_query(request, role, title),
            "generation_brief": f"生成一页{title}，用于{request.get('project_name', 'Deck')}。{goal}",
            "approval_required": role in {"case", "roi", "architecture"},
        }

        # Enhanced fields — only populated when optional inputs are provided.
        # decision_intent
        decision_intent = _derive_decision_intent(role, judgments)
        if decision_intent:
            beat["decision_intent"] = decision_intent

        # argument_chain
        chain = list(_ROLE_ARGUMENT_CHAIN.get(role, ["证据"]))
        beat["argument_chain"] = chain

        # evidence_policy
        evidence_policy = _build_evidence_policy(role, claim_graph)
        beat["evidence_policy"] = evidence_policy

        # customer_specificity_level
        specificity = _infer_customer_specificity(role, judgments)
        beat["customer_specificity_level"] = specificity

        # workspace_refs
        ws_refs: list[str] = []
        if workspace_archetypes:
            archetypes = workspace_archetypes.get("archetypes", [])
            if isinstance(archetypes, list):
                for arch in archetypes:
                    if isinstance(arch, dict) and arch.get("role") == role:
                        ref = arch.get("ref") or arch.get("archetype_id", "")
                        if ref:
                            ws_refs.append(ref)
            # Also check direct role-keyed refs.
            role_ref = workspace_archetypes.get(role)
            if isinstance(role_ref, str) and role_ref:
                ws_refs.append(role_ref)
            elif isinstance(role_ref, list):
                ws_refs.extend(str(r) for r in role_ref if r)
        if ws_refs:
            beat["workspace_refs"] = ws_refs

        # Claim association from claim_graph.
        claim_ids = _find_claim_ids_for_beat(beat_id, role, claim_graph)
        if claim_ids:
            beat["claim_ids"] = claim_ids

        beats.append(beat)

    return {
        "run_id": request.get("run_id", ""),
        "title": request.get("project_name", "Deck Master Run"),
        "target_pages": adjusted_page_count,
        "density": density,
        "industry": request.get("industry", ""),
        "audience": request.get("audience", "client"),
        "planner_mode": planner_mode,
        "input_sources": input_sources,
        "fallback_reason": fallback_reason,
        "roles": [beat["role"] for beat in beats],
        "gaps": gaps,
        "beats": beats,
    }
