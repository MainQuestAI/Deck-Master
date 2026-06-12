from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "deck_draft_gate_v2.v1"

# 检查维度
DIMENSIONS = [
    "thesis_clarity",        # 没有核心主张
    "claim_coverage",        # 核心 claim 无页面承载
    "evidence_readiness",    # required evidence 缺失
    "argument_flow",         # 页面顺序无法形成证明链
    "audience_fit",          # 受众和表达密度不匹配
    "specificity",           # 客户专属页缺客户证据
    "risk_visibility",       # 风险未暴露
]

# 状态
STATUSES = {"pass", "conditional_pass", "rework_required"}


def evaluate_draft_gate_v2(
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    consulting_judgments: dict[str, Any] | None = None,
    claim_evidence_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """增强版 Draft Gate 检查。

    检查维度：
    - thesis_clarity: 核心主张是否清晰
    - claim_coverage: 核心 claim 是否有页面承载
    - evidence_readiness: required evidence 是否就绪
    - argument_flow: 页面顺序能否形成证明链
    - audience_fit: 受众和表达密度是否匹配
    - specificity: 客户专属页是否有客户证据
    - risk_visibility: 风险是否被暴露和标记

    状态：
    - pass: 所有检查通过
    - conditional_pass: 有 P2 级问题但无 P0/P1
    - rework_required: 有 P0 或 P1 级问题
    """
    run_id = str(
        deck_brief.get("run_id")
        or claim_map.get("run_id")
        or page_tasks.get("run_id")
        or ""
    )

    findings: list[dict[str, Any]] = []
    dimension_scores: dict[str, int] = {dim: 5 for dim in DIMENSIONS}

    # 1. thesis_clarity: 检查核心主张
    _check_thesis_clarity(deck_brief, claim_map, findings, dimension_scores)

    # 2. claim_coverage: 检查 claim 是否有页面承载
    _check_claim_coverage(claim_map, page_tasks, findings, dimension_scores)

    # 3. evidence_readiness: 检查证据就绪状态
    _check_evidence_readiness(claim_map, page_tasks, claim_evidence_graph, findings, dimension_scores)

    # 4. argument_flow: 检查论证流程
    _check_argument_flow(page_tasks, findings, dimension_scores)

    # 5. audience_fit: 检查受众匹配
    _check_audience_fit(deck_brief, page_tasks, findings, dimension_scores)

    # 6. specificity: 检查客户专属
    _check_specificity(deck_brief, claim_map, page_tasks, findings, dimension_scores)

    # 7. risk_visibility: 检查风险暴露
    _check_risk_visibility(claim_map, consulting_judgments, findings, dimension_scores)

    # 计算整体状态
    status = _compute_status(findings, dimension_scores)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "draft_v2",
        "status": status,
        "dimension_scores": dimension_scores,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "p0_count": sum(1 for f in findings if f.get("severity") == "P0"),
            "p1_count": sum(1 for f in findings if f.get("severity") == "P1"),
            "p2_count": sum(1 for f in findings if f.get("severity") == "P2"),
            "claims": len(claim_map.get("claims", [])),
            "page_tasks": len(page_tasks.get("tasks", [])),
        },
        "blocks_delivery": status == "rework_required",
    }


def _make_finding(
    finding_id: str,
    severity: str,
    dimension: str,
    message: str,
    refs: list[str],
    repair_instruction: str,
    page_id: str = "",
) -> dict[str, Any]:
    result = {
        "finding_id": finding_id,
        "severity": severity,
        "dimension": dimension,
        "message": message,
        "refs": refs,
        "repair_instruction": repair_instruction,
    }
    if page_id:
        result["page_id"] = page_id
    return result


def _compute_status(findings: list[dict[str, Any]], scores: dict[str, int]) -> str:
    """根据 findings 和 scores 计算整体状态。"""
    has_p0 = any(f.get("severity") == "P0" for f in findings)
    has_p1 = any(f.get("severity") == "P1" for f in findings)

    if has_p0:
        return "rework_required"
    if has_p1:
        return "rework_required"

    # 检查低分维度
    low_dims = [dim for dim, score in scores.items() if score <= 2]
    if low_dims:
        return "conditional_pass"

    return "pass"


def _check_thesis_clarity(
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查核心主张是否清晰。"""
    business_goal = deck_brief.get("business_goal", "")
    core_points = deck_brief.get("core_points", [])
    claims = claim_map.get("claims", [])

    if not business_goal:
        scores["thesis_clarity"] -= 3
        findings.append(_make_finding(
            "v2_thesis_missing_goal",
            "P1",
            "thesis_clarity",
            "Deck 缺少明确业务目标，无法判断核心主张。",
            ["deck_brief.json"],
            "补充业务目标、目标受众和期望推动的客户决策。",
        ))

    if not core_points and not claims:
        scores["thesis_clarity"] -= 2
        findings.append(_make_finding(
            "v2_thesis_no_claims",
            "P1",
            "thesis_clarity",
            "没有核心论点，Deck 将退化为材料堆叠。",
            ["claim_map.json"],
            "从业务问题和客户痛点出发，提炼 3-5 个核心论点。",
        ))


def _check_claim_coverage(
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查核心 claim 是否有页面承载。"""
    claims = claim_map.get("claims", [])
    tasks = page_tasks.get("tasks", [])

    # 收集所有 page task 关联的 claim
    covered_claim_ids: set[str] = set()
    for task in tasks:
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
        claim_ref = planning.get("claim_ref") or planning.get("claim_id") or ""
        if claim_ref:
            covered_claim_ids.add(claim_ref)
        # 也检查 core_claim 文本匹配
        core_claim = planning.get("core_claim", "")
        if core_claim:
            for claim in claims:
                claim_text = claim.get("claim", "")
                if core_claim in claim_text or claim_text in core_claim:
                    covered_claim_ids.add(claim.get("claim_id", ""))

    for claim in claims:
        claim_id = claim.get("claim_id", "")
        if claim_id and claim_id not in covered_claim_ids:
            # opener/closing 不强制覆盖
            role = ""
            for task in tasks:
                planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
                if planning.get("claim_ref") == claim_id or planning.get("claim_id") == claim_id:
                    role = planning.get("role", "")
                    break
            if role in ("opener", "closing"):
                continue

            scores["claim_coverage"] -= 2
            findings.append(_make_finding(
                f"v2_claim_uncovered_{claim_id}",
                "P1",
                "claim_coverage",
                f"核心论点 '{claim.get('claim', '')[:50]}' 没有页面承载。",
                ["claim_map.json", "page_tasks.json"],
                "为该论点分配一个页面，或在 narrative plan 中增加对应 beat。",
            ))


def _check_evidence_readiness(
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    claim_evidence_graph: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查 required evidence 是否就绪。"""
    claims = claim_map.get("claims", [])

    for claim in claims:
        risk_flags = claim.get("risk_flags", [])
        if "evidence_gap" in risk_flags or "missing_required_evidence" in risk_flags:
            scores["evidence_readiness"] -= 1
            findings.append(_make_finding(
                f"v2_evidence_gap_{claim.get('claim_id', 'unknown')}",
                "P1",
                "evidence_readiness",
                f"论点 '{claim.get('claim', '')[:50]}' 缺少必要证据。",
                ["claim_map.json"],
                "补充客户案例、产品截图、业务数据或会议原话作为证据。",
                page_id=claim.get("claim_id", ""),
            ))

    # 如果有 claim evidence graph，检查 gaps
    if claim_evidence_graph:
        gaps = claim_evidence_graph.get("gaps", [])
        for gap in gaps:
            scores["evidence_readiness"] -= 1
            findings.append(_make_finding(
                f"v2_graph_gap_{gap.get('claim_id', 'unknown')}",
                "P1",
                "evidence_readiness",
                f"证据图谱标记缺口：{gap.get('description', '未知')}",
                ["claim_evidence_graph.json"],
                gap.get("repair_instruction", "补充缺失证据。"),
            ))


def _check_argument_flow(
    page_tasks: dict[str, Any],
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查页面顺序能否形成证明链。"""
    tasks = page_tasks.get("tasks", [])
    if len(tasks) < 3:
        scores["argument_flow"] -= 1
        findings.append(_make_finding(
            "v2_flow_too_few_pages",
            "P2",
            "argument_flow",
            f"页面数量（{len(tasks)}）过少，可能无法形成完整论证链。",
            ["page_tasks.json"],
            "考虑增加问题定义、解决路径、证据和总结页面。",
        ))

    # 检查是否有 opener
    roles: list[str] = []
    for task in tasks:
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
        roles.append(planning.get("role", ""))

    if roles and "opener" not in roles:
        scores["argument_flow"] -= 1
        findings.append(_make_finding(
            "v2_flow_no_opener",
            "P2",
            "argument_flow",
            "没有 opener 页面来建立问题框架。",
            ["page_tasks.json"],
            "在 narrative plan 开头增加问题框架页面。",
        ))


def _check_audience_fit(
    deck_brief: dict[str, Any],
    page_tasks: dict[str, Any],
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查受众和表达密度是否匹配。"""
    audience = deck_brief.get("audience", "")
    tasks = page_tasks.get("tasks", [])

    if audience == "exec" and len(tasks) > 20:
        scores["audience_fit"] -= 2
        findings.append(_make_finding(
            "v2_audience_exec_too_many",
            "P2",
            "audience_fit",
            f"面向 exec 受众但页数（{len(tasks)}）过多。",
            ["deck_brief.json", "page_tasks.json"],
            "精简到 10-15 页核心内容，突出决策要点。",
        ))


def _check_specificity(
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查客户专属页是否有客户证据。"""
    claims = claim_map.get("claims", [])
    for claim in claims:
        risk_flags = claim.get("risk_flags", [])
        if "needs_customer_evidence" in risk_flags:
            scores["specificity"] -= 1
            findings.append(_make_finding(
                f"v2_specificity_{claim.get('claim_id', 'unknown')}",
                "P1",
                "specificity",
                f"客户专属论点 '{claim.get('claim', '')[:50]}' 缺少客户证据。",
                ["claim_map.json"],
                "补充客户原话、客户材料或客户确认的数据。",
            ))


def _check_risk_visibility(
    claim_map: dict[str, Any],
    consulting_judgments: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    scores: dict[str, int],
) -> None:
    """检查风险是否被暴露和标记。"""
    risk_flags = claim_map.get("risk_flags", [])

    if not risk_flags:
        # 没有任何风险标记可能意味着风险评估不足
        scores["risk_visibility"] -= 1
        findings.append(_make_finding(
            "v2_risk_no_flags",
            "P2",
            "risk_visibility",
            "没有任何风险标记，可能需要重新评估证据和假设。",
            ["claim_map.json"],
            "审查每个论点的假设和证据强度，标记不确定的判断。",
        ))

    # 检查 judgments 中的 open_questions
    if consulting_judgments:
        open_questions = consulting_judgments.get("open_questions", [])
        if open_questions:
            scores["risk_visibility"] = max(scores["risk_visibility"], 3)
