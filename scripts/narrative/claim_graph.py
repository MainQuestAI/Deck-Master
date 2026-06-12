from __future__ import annotations
from typing import Any

SCHEMA_VERSION = "deck_claim_evidence_graph.v1"


def build_claim_evidence_graph(
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    context_manifest: dict[str, Any] | None = None,
    consulting_judgments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 claim-evidence graph。

    产物结构：
    {
        "schema_version": "deck_claim_evidence_graph.v1",
        "run_id": str,
        "claims": [...],         # 增强的 claim 列表
        "evidence": [...],       # 证据列表
        "assumptions": [...],    # 假设列表
        "risks": [...],          # 风险列表
        "page_refs": {...},      # claim_id -> [page_id] 映射
        "gaps": [...],           # 证据缺口
    }

    Claim 结构：
    {
        "claim_id": str,
        "type": "core" | "supporting" | "contextual",
        "statement": str,
        "supporting_evidence": [evidence_id],
        "assumptions": [assumption_id],
        "risks": [risk_id],
        "required_evidence": [str],
        "page_refs": [page_id],
    }

    Evidence 结构：
    {
        "evidence_id": str,
        "source_ref": str,
        "evidence_type": "meeting_quote" | "customer_material" | "case_study" | "product_screenshot" | "data_point" | "assumption",
        "summary": str,
        "confidence": float,
        "publication_status": "safe_to_use" | "internal_only" | "needs_redaction" | "unknown",
    }
    """
    run_id = claim_map.get("run_id", "")

    # 构建 claims
    graph_claims: list[dict[str, Any]] = []
    all_evidence: list[dict[str, Any]] = []
    all_assumptions: list[dict[str, Any]] = []
    all_risks: list[dict[str, Any]] = []
    page_refs_map: dict[str, list[str]] = {}
    gaps: list[dict[str, Any]] = []

    raw_claims = claim_map.get("claims", [])
    tasks = page_tasks.get("tasks", [])
    sources = (context_manifest or {}).get("sources", [])

    # 建立 source evidence
    evidence_counter = 0
    source_evidence_map: dict[str, str] = {}  # source_id -> evidence_id
    candidate_evidence_map: dict[str, str] = {}  # candidate evidence_id -> graph evidence_id
    for source in sources:
        if not isinstance(source, dict):
            continue
        evidence_counter += 1
        eid = f"evidence_{evidence_counter:03d}"
        source_id = str(source.get("source_id", ""))
        source_evidence_map[source_id] = eid

        kind = str(source.get("kind", ""))
        evidence_type = _infer_evidence_type(kind)
        pub_status = _infer_publication_status(kind, source)

        all_evidence.append({
            "evidence_id": eid,
            "source_ref": source_id or f"context_manifest.json#source_{evidence_counter}",
            "evidence_type": evidence_type,
            "summary": str(source.get("summary", source.get("excerpt", ""))),
            "confidence": 0.7 if source.get("summary") else 0.4,
            "publication_status": pub_status,
        })

        # v0.9: consume evidence_candidates from context pack import.
        candidates = source.get("evidence_candidates", [])
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                cand_id = str(candidate.get("evidence_id", ""))
                if not cand_id:
                    continue
                evidence_counter += 1
                cand_eid = f"evidence_{evidence_counter:03d}"
                candidate_evidence_map[cand_id] = cand_eid
                cand_type = _infer_evidence_type(str(candidate.get("evidence_type", kind)))
                cand_pub = str(candidate.get("publication_status", pub_status))
                all_evidence.append({
                    "evidence_id": cand_eid,
                    "source_ref": source_id,
                    "evidence_type": cand_type,
                    "summary": str(candidate.get("quote_or_excerpt", candidate.get("claim_hint", ""))),
                    "confidence": 0.6 if candidate.get("quote_or_excerpt") else 0.4,
                    "publication_status": cand_pub,
                    "sensitivity": str(candidate.get("sensitivity", "normal")),
                    "candidate_id": cand_id,
                })

    # 构建 claims 和关联
    for index, claim in enumerate(raw_claims, start=1):
        claim_id = claim.get("claim_id", f"claim_{index:02d}")

        # 关联 evidence
        supporting_evidence: list[str] = []
        for ref in claim.get("evidence_refs", []):
            if ref in source_evidence_map:
                supporting_evidence.append(source_evidence_map[ref])
            elif ref in candidate_evidence_map:
                supporting_evidence.append(candidate_evidence_map[ref])

        # 关联 pages
        claim_pages: list[str] = []
        for task in tasks:
            planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
            core_claim = planning.get("core_claim", "")
            if claim.get("claim", "") in core_claim or core_claim in claim.get("claim", ""):
                beat_id = task.get("beat_id", "")
                if beat_id:
                    claim_pages.append(beat_id)
        page_refs_map[claim_id] = claim_pages

        # 构建 assumptions
        claim_assumptions: list[str] = []
        if not supporting_evidence:
            assumption_id = f"assumption_{len(all_assumptions) + 1:03d}"
            all_assumptions.append({
                "assumption_id": assumption_id,
                "claim_id": claim_id,
                "statement": f"假设 '{claim.get('claim', '')[:50]}' 成立，但缺少直接证据。",
                "risk_level": "medium",
            })
            claim_assumptions.append(assumption_id)

        # 构建 risks
        claim_risks: list[str] = []
        risk_flags = claim.get("risk_flags", [])
        for flag in risk_flags:
            risk_id = f"risk_{len(all_risks) + 1:03d}"
            all_risks.append({
                "risk_id": risk_id,
                "claim_id": claim_id,
                "flag": flag,
                "description": _describe_risk(flag),
                "severity": "high" if flag in ("missing_core_claim",) else "medium",
            })
            claim_risks.append(risk_id)

        # 确定 claim type
        claim_type = "core" if index <= 3 else "supporting"
        if not claim_pages and claim_type == "core":
            claim_type = "core"  # 保持 core 即使没有 page

        # Required evidence
        required_evidence = claim.get("evidence_needed", [])

        # 检查 gaps
        if not supporting_evidence and required_evidence:
            gaps.append({
                "claim_id": claim_id,
                "description": f"论点 '{claim.get('claim', '')[:50]}' 需要 {len(required_evidence)} 项证据但当前为 0。",
                "required_evidence": required_evidence,
                "repair_instruction": f"补充以下证据：{'、'.join(required_evidence[:3])}",
            })

        graph_claims.append({
            "claim_id": claim_id,
            "type": claim_type,
            "statement": claim.get("claim", ""),
            "supporting_evidence": supporting_evidence,
            "assumptions": claim_assumptions,
            "risks": claim_risks,
            "required_evidence": required_evidence,
            "page_refs": claim_pages,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "claims": graph_claims,
        "evidence": all_evidence,
        "assumptions": all_assumptions,
        "risks": all_risks,
        "page_refs": page_refs_map,
        "gaps": gaps,
    }


def _infer_evidence_type(kind: str) -> str:
    mapping = {
        "meeting_transcript": "meeting_quote",
        "meeting_notes": "meeting_quote",
        "customer_material": "customer_material",
        "case_study": "case_study",
        "screenshot": "product_screenshot",
        "product_doc": "product_screenshot",
        "data": "data_point",
        "report": "data_point",
    }
    return mapping.get(kind, "assumption")


def _infer_publication_status(kind: str, source: dict) -> str:
    if source.get("confidential"):
        return "needs_redaction"
    if kind in ("internal_doc", "internal_notes"):
        return "internal_only"
    if kind in ("meeting_transcript", "customer_material"):
        return "safe_to_use"
    return "unknown"


def _describe_risk(flag: str) -> str:
    descriptions = {
        "evidence_gap": "论点缺少充分证据支撑。",
        "missing_core_claim": "核心论点缺失。",
        "missing_required_evidence": "必要证据缺失。",
        "needs_customer_evidence": "需要客户专属证据。",
        "needs_solution_clarity": "解决路径不够清晰。",
    }
    return descriptions.get(flag, f"风险标记：{flag}")
