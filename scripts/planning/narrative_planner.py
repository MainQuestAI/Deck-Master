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

REQUIRED_SOLUTION_MODULES: list[dict[str, str]] = [
    {"module_id": "company_credentials", "label": "公司介绍/资质"},
    {"module_id": "demand_understanding", "label": "需求理解"},
    {"module_id": "problem_diagnosis", "label": "现状与问题诊断"},
    {"module_id": "target_vision", "label": "目标愿景"},
    {"module_id": "business_solution", "label": "业务方案"},
    {"module_id": "platform_architecture", "label": "平台规划/架构"},
    {"module_id": "implementation_path", "label": "实施路径"},
    {"module_id": "service_assurance", "label": "服务与保障"},
    {"module_id": "case_evidence", "label": "案例/证据"},
    {"module_id": "next_step", "label": "收尾与推进动作"},
]

_ROLE_MODULE_COVERAGE: dict[str, set[str]] = {
    "opener": {"company_credentials", "target_vision"},
    "problem": {"demand_understanding", "problem_diagnosis"},
    "solution": {"business_solution"},
    "architecture": {"platform_architecture"},
    "case": {"case_evidence"},
    "roi": {"case_evidence"},
    "cta": {"next_step"},
}

_TITLE_MODULE_HINTS: tuple[tuple[str, set[str]], ...] = (
    ("资质", {"company_credentials"}),
    ("公司", {"company_credentials"}),
    ("需求", {"demand_understanding"}),
    ("痛点", {"problem_diagnosis"}),
    ("挑战", {"problem_diagnosis"}),
    ("现状", {"problem_diagnosis"}),
    ("愿景", {"target_vision"}),
    ("方案", {"business_solution"}),
    ("能力", {"business_solution"}),
    ("架构", {"platform_architecture"}),
    ("平台", {"platform_architecture"}),
    ("实施", {"implementation_path"}),
    ("路径", {"implementation_path"}),
    ("服务", {"service_assurance"}),
    ("保障", {"service_assurance"}),
    ("案例", {"case_evidence"}),
    ("证据", {"case_evidence"}),
    ("推进", {"next_step"}),
    ("下一步", {"next_step"}),
)


def _modules_for_beat(beat: dict[str, Any]) -> set[str]:
    role = str(beat.get("role") or "")
    title = str(beat.get("page_title") or beat.get("title") or "")
    modules = set(_ROLE_MODULE_COVERAGE.get(role, set()))
    for token, implied in _TITLE_MODULE_HINTS:
        if token in title:
            modules.update(implied)
    return modules


def build_required_modules_status(beats: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = {
        item["module_id"]: {
            "module_id": item["module_id"],
            "label": item["label"],
            "status": "missing",
            "beat_ids": [],
            "page_titles": [],
        }
        for item in REQUIRED_SOLUTION_MODULES
    }

    for beat in beats:
        if not isinstance(beat, dict):
            continue
        beat_id = str(beat.get("beat_id") or "")
        page_title = str(beat.get("page_title") or beat.get("title") or "")
        for module_id in _modules_for_beat(beat):
            item = coverage.get(module_id)
            if item is None:
                continue
            item["status"] = "covered"
            if beat_id and beat_id not in item["beat_ids"]:
                item["beat_ids"].append(beat_id)
            if page_title and page_title not in item["page_titles"]:
                item["page_titles"].append(page_title)

    required_modules_status = [coverage[item["module_id"]] for item in REQUIRED_SOLUTION_MODULES]
    missing_modules = [item["label"] for item in required_modules_status if item["status"] != "covered"]
    return {
        "required_modules_status": required_modules_status,
        "missing_modules": missing_modules,
        "coverage_matrix": {
            "required_modules": required_modules_status,
            "covered_count": len(required_modules_status) - len(missing_modules),
            "missing_count": len(missing_modules),
            "complete": not missing_modules,
        },
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
    if any(token in lowered for token in ["医药", "医疗", "healthcare", "pharma", "内容底座", "内容中台"]):
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
    # SC-1 F06: production narrative is driven by the solution model and
    # evidence. Keyword-based retail-sample filtering of template titles was
    # removed — templates are only a structural hint in every mode.
    return templates


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


def _solution_model_beats(
    solution_model: dict[str, Any],
    page_count: int,
    density: str,
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    """SC-1 B4: production narrative driven by the approved solution model.

    Page jobs come from problems/capabilities/components/phases — never from
    generic template titles. Customer-facing conclusions carry no internal
    SCR/MBB labels (spec 05 §5.3).
    """

    beats: list[dict[str, Any]] = []
    business_goal = str(request.get("business_goal") or "")
    problems = [item for item in solution_model.get("problems", []) if isinstance(item, dict)]
    capabilities = [item for item in solution_model.get("capabilities", []) if isinstance(item, dict)]
    components = {str(item.get("component_id") or ""): item for item in solution_model.get("components", []) if isinstance(item, dict)}
    phases = [item for item in solution_model.get("phases", []) if isinstance(item, dict)]

    def _page(
        role: str,
        title: str,
        conclusion: str,
        page_job: str,
        *,
        claim_refs: list[str] | None = None,
        required_components: list[str] | None = None,
        expected_visual: str = "文字+结构化图形",
    ) -> dict[str, Any]:
        order = len(beats) + 1
        return {
            "beat_id": f"beat_{order:02d}_{role}",
            "order": order,
            "page_title": title,
            "role": role,
            "page_job": page_job,
            "conclusion": conclusion,
            "brief": page_job,
            "content_goal": conclusion,
            "claim_refs": claim_refs or [],
            "required_components": required_components or [],
            "expected_visual": expected_visual,
            "content_budget": "standard",
            "transition": "",
            "evidence_need": "客户材料证据或明确设计依据",
            "visual_need": expected_visual,
            "density": density,
            "generation_brief": f"围绕“{conclusion}”组织本页论证与材料。",
            "approval_required": role in {"case", "roi", "architecture"},
            "customer_specificity_level": "customer_specific",
        }

    if business_goal or problems:
        first_problem = problems[0] if problems else {}
        beats.append(
            _page(
                "opener",
                str(first_problem.get("title") or "核心问题与目标"),
                str(first_problem.get("statement") or business_goal or ""),
                "对齐客户要做的决策与衡量标准",
            )
        )
    for problem in problems[1 : max(0, page_count - 3)]:
        beats.append(
            _page(
                "problem",
                str(problem.get("title") or "关键问题"),
                str(problem.get("statement") or ""),
                f"说明该问题的影响与依据（{', '.join(str(x) for x in problem.get('evidence_refs', [])) or '待补证据'}）",
            )
        )
    for capability in capabilities:
        if len(beats) >= page_count - 2:
            break
        required = [str(ref) for ref in (capability.get("component_ids") or []) if str(ref) in components]
        beats.append(
            _page(
                "solution",
                str(capability.get("title") or capability.get("capability_id") or "能力机制"),
                str(capability.get("mechanism") or ""),
                f"说明能力如何改变问题，可检查结果：{capability.get('checkable_result', '')}",
                required_components=required,
            )
        )
    if any(str(item.get("component_id") or "") for item in components.values()) and len(beats) < page_count - 1:
        beats.append(
            _page(
                "architecture",
                "架构与组件边界",
                "组件职责、关系与实施边界与方案一致",
                "对齐业务架构、应用/数据流视图的组件与边界",
                required_components=[cid for cid in components if cid],
                expected_visual="架构视图（业务/应用/数据）",
            )
        )
    for phase in phases:
        if len(beats) >= page_count:
            break
        beats.append(
            _page(
                "roi" if phase.get("exit_criteria") else "solution",
                str(phase.get("title") or phase.get("phase_id") or "实施阶段"),
                str(phase.get("goal") or ""),
                f"阶段产出与退出标准：{phase.get('exit_criteria', '待明确')}",
            )
        )
    return beats[:page_count]


def plan_narrative(
    request: dict[str, Any],
    judgments: dict[str, Any] | None = None,
    claim_graph: dict[str, Any] | None = None,
    workspace_archetypes: dict[str, Any] | None = None,
    planner_mode: str = "production_narrative",
    solution_model: dict[str, Any] | None = None,
    narrative_candidates: list[dict[str, Any]] | None = None,
    selected_candidate_id: str | None = None,
    selection_decision_ref: str | None = None,
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

    solution_driven = planner_mode == "production_narrative" and isinstance(solution_model, dict) and bool(solution_model.get("capabilities"))
    if solution_driven:
        solution_density = density_for(page_count)
        beats = _solution_model_beats(solution_model, page_count, solution_density, request)
        adjusted_page_count = len(beats)
    else:
        beats = []
    fallback_reason = _planner_fallback_reason(planner_mode, request, workspace_archetypes, judgments)
    input_sources = _planner_input_sources(planner_mode, workspace_archetypes)
    if solution_driven:
        input_sources = list(dict.fromkeys(input_sources + ["solution_model"]))
        fallback_reason = ""
    for index, (role, title, goal) in enumerate([] if solution_driven else templates, start=1):
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

    module_coverage = build_required_modules_status(beats)

    # SC-1 B4: narrative-plan v3 candidate structure. When explicit
    # candidates are supplied they pass through; otherwise a single candidate
    # derived from the chosen storyline is recorded with a
    # single_viable_path selection reason — no fabricated pseudo-options.
    candidates: list[dict[str, Any]] = []
    selected_id = None
    decision_ref = str(selection_decision_ref or request.get("selection_decision_ref") or "")
    recommended_id = ""
    selection_reason = ""
    if solution_driven:
        if narrative_candidates:
            candidates = [dict(item) for item in narrative_candidates if isinstance(item, dict)]
            recommended = next((item for item in candidates if item.get("recommended")), candidates[0] if candidates else None)
            recommended_id = str((recommended or {}).get("candidate_id") or "")
        else:
            recommended_id = "candidate_single_viable_path"
            selection_reason = "single_viable_path: one coherent storyline derivable from the solution model; no fabricated alternatives"
            candidates = [
                {
                    "candidate_id": recommended_id,
                    "title": str(request.get("project_name") or "方案主线"),
                    "storyline": [beat.get("conclusion") or beat.get("page_title", "") for beat in beats],
                    "recommended": True,
                    "recommendation_reason": selection_reason,
                    "beat_ids": [beat["beat_id"] for beat in beats],
                }
            ]

        supplied_selection = selected_candidate_id or request.get("selected_candidate_id")
        if supplied_selection:
            if str(supplied_selection) not in {str(c.get("candidate_id")) for c in candidates}:
                raise ValueError("selected narrative candidate is not in current candidates")
            if not decision_ref.strip():
                raise ValueError("selected narrative candidate requires selection_decision_ref")
            selected_id = str(supplied_selection)
            selection_reason = "explicit selection recorded in " + decision_ref
        elif len(candidates) > 1:
            gaps.append({"field": "narrative_selection", "message": "多个真实主线候选尚无明确选择；推荐不代表用户决定。"})

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
        "candidates": candidates,
        "recommended_candidate_id": recommended_id,
        "selected_candidate_id": selected_id,
        "selection_decision_ref": decision_ref if selected_id else "",
        "selection_reason": selection_reason,
        "coverage_matrix": module_coverage["coverage_matrix"],
        "required_modules_status": module_coverage["required_modules_status"],
        "missing_modules": module_coverage["missing_modules"],
    }
