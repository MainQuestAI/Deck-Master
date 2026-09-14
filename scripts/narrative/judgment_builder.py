from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "deck_consulting_judgments.v1"

# Judgment 主题类型
JUDGMENT_TOPICS = [
    "business_problem",       # 核心业务问题
    "solution_approach",      # 解决路径
    "evidence_sufficiency",   # 证据充分性
    "audience_alignment",     # 受众匹配
    "competitive_position",   # 竞争定位
    "implementation_risk",    # 实施风险
]


def build_judgments(
    request: dict[str, Any],
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    context_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从输入 artifacts 生成 consulting judgments。

    规则：
    1. 至少生成 3 条 judgment
    2. 每条 judgment 对应一个 topic
    3. 缺证据的 judgment 必须带 risk flag
    4. confidence 基于证据覆盖度计算
    """
    run_id = request.get("run_id", deck_brief.get("run_id", ""))
    judgments: list[dict[str, Any]] = []
    open_questions: list[str] = []

    claims = claim_map.get("claims", [])
    core_points = deck_brief.get("core_points", [])
    business_goal = request.get("business_goal", deck_brief.get("business_goal", ""))
    industry = request.get("industry", "")
    audience = request.get("audience", "client")
    sources = (context_manifest or {}).get("sources", [])

    # Judgment 1: business_problem
    business_problem = _judge_business_problem(business_goal, claims, sources)
    judgments.append(business_problem)

    # Judgment 2: solution_approach
    solution = _judge_solution_approach(core_points, claims, business_goal)
    judgments.append(solution)

    # Judgment 3: evidence_sufficiency
    evidence = _judge_evidence_sufficiency(claims, sources)
    judgments.append(evidence)
    if evidence.get("risk_flags"):
        open_questions.append("需要补充更多客户专属证据来支撑核心论点。")

    # Judgment 4: audience_alignment (如果有足够信息)
    if audience and core_points:
        alignment = _judge_audience_alignment(audience, core_points, business_goal)
        judgments.append(alignment)

    # Judgment 5: 基于 claim risk flags
    for claim in claims:
        if claim.get("risk_flags"):
            judgments.append({
                "judgment_id": f"judgment_claim_{claim.get('claim_id', 'unknown')}",
                "topic": "evidence_sufficiency",
                "statement": f"论点 '{claim.get('claim', '')[:60]}' 存在证据风险。",
                "rationale": f"风险标记：{', '.join(claim.get('risk_flags', []))}",
                "confidence": 0.5,
                "source_refs": [f"claim_map.json#{claim.get('claim_id', '')}"],
                "risk_flags": list(claim.get("risk_flags", [])),
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "judgments": judgments,
        "open_questions": open_questions,
    }


def _judge_business_problem(business_goal: str, claims: list, sources: list) -> dict:
    """判断核心业务问题是否清晰。"""
    has_evidence = bool(sources)
    confidence = 0.7 if has_evidence else 0.4
    risk_flags = [] if has_evidence else ["needs_customer_evidence"]

    statement = f"客户核心问题是{business_goal[:80]}。" if business_goal else "核心业务问题尚未明确。"

    return {
        "judgment_id": "judgment_business_problem",
        "topic": "business_problem",
        "statement": statement,
        "rationale": "会议转写和 brief 指向核心业务问题。" if has_evidence else "缺少客户直接输入，业务问题基于推断。",
        "confidence": confidence,
        "source_refs": ["context_manifest.json"] if has_evidence else [],
        "risk_flags": risk_flags,
    }


def _judge_solution_approach(core_points: list, claims: list, business_goal: str) -> dict:
    """判断解决路径是否清晰。"""
    has_claims = bool(claims) and len(claims) >= 2
    confidence = 0.75 if has_claims else 0.45
    risk_flags = [] if has_claims else ["needs_solution_clarity"]

    return {
        "judgment_id": "judgment_solution_approach",
        "topic": "solution_approach",
        "statement": f"方案路径涵盖 {len(core_points)} 个核心要点。" if core_points else "解决路径需要进一步细化。",
        "rationale": f"从 {len(claims)} 个论点和 {len(core_points)} 个核心要点推导出方案路径。",
        "confidence": confidence,
        "source_refs": ["deck_brief.json", "claim_map.json"],
        "risk_flags": risk_flags,
    }


def _judge_evidence_sufficiency(claims: list, sources: list) -> dict:
    """核对每个论点的证据引用是否真实对应到当前材料。

    这里只做代码层核对：引用存在且能匹配到当前来源清单（source_id/name/
    path/sha256）。引用存在不代表证据语义上充分，语义支撑由主编/编辑判断，
    不做"未标风险即充分"的推断。
    """
    source_keys: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        for field in ("source_id", "name", "path", "sha256"):
            value = str(source.get(field) or "").strip()
            if value:
                source_keys.add(value)

    def _has_resolvable_evidence(claim: dict) -> bool:
        refs = claim.get("evidence_refs") if isinstance(claim.get("evidence_refs"), list) else []
        for ref in refs:
            ref_text = str(ref or "").strip()
            if not ref_text:
                continue
            if any(ref_text == key or ref_text in key or key in ref_text for key in source_keys):
                return True
        return False

    total_claims = len(claims)
    claims_with_evidence = sum(1 for claim in claims if isinstance(claim, dict) and _has_resolvable_evidence(claim))
    ratio = claims_with_evidence / max(total_claims, 1)
    confidence = round(min(0.9, ratio * 0.8 + 0.1), 2)
    risk_flags = [] if ratio >= 0.7 else ["needs_customer_evidence"]

    if total_claims and claims_with_evidence:
        statement = f"{claims_with_evidence}/{total_claims} 个论点的证据引用与当前材料核对一致。"
        rationale = (
            f"证据引用核对率 {ratio:.0%}。引用存在不代表证据语义上充分，语义支撑需由主编/编辑判断。"
        )
    elif total_claims:
        statement = f"0/{total_claims} 个论点的证据引用能与当前材料核对。"
        rationale = "没有论点的证据引用匹配到当前来源清单，需要补充可核对的证据。"
    else:
        statement = "没有可核对的论点。"
        rationale = "claim_map 为空，无法进行证据引用核对。"

    return {
        "judgment_id": "judgment_evidence_sufficiency",
        "topic": "evidence_sufficiency",
        "statement": statement,
        "rationale": rationale,
        "confidence": confidence,
        "source_refs": ["claim_map.json", "context_manifest.json"],
        "risk_flags": risk_flags,
    }


def _judge_audience_alignment(audience: str, core_points: list, business_goal: str) -> dict:
    """判断受众匹配度。"""
    confidence = 0.65 if core_points else 0.4
    return {
        "judgment_id": "judgment_audience_alignment",
        "topic": "audience_alignment",
        "statement": f"内容面向 {audience} 受众，共 {len(core_points)} 个核心要点。",
        "rationale": f"受众类型为 {audience}，需要匹配相应的表达密度和决策层次。",
        "confidence": confidence,
        "source_refs": ["request.json", "deck_brief.json"],
        "risk_flags": [],
    }
