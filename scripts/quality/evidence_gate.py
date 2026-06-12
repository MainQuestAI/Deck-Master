from __future__ import annotations
from typing import Any
from pathlib import Path
import json

SCHEMA_VERSION = "deck_evidence_gate.v1"

def evaluate_evidence_gate(
    run_id: str,
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
    claim_evidence_graph: dict[str, Any] | None = None,
    sourcing_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """检查 claim 与 required evidence。

    阻断规则：
    - required evidence 缺失：P1
    - claim 无页面承载：P1
    - evidence 标记 internal_only 仍进入 client queue：P0
    """
    findings = []
    claims = claim_map.get("claims", [])
    tasks = page_tasks.get("tasks", [])

    # 收集有页面承载的 claim IDs
    covered_claim_ids = set()
    for task in tasks:
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
        claim_ref = planning.get("claim_ref") or planning.get("claim_id") or ""
        if claim_ref:
            covered_claim_ids.add(claim_ref)
        core_claim = planning.get("core_claim", "")
        if core_claim:
            for claim in claims:
                if core_claim in claim.get("claim", "") or claim.get("claim", "") in core_claim:
                    covered_claim_ids.add(claim.get("claim_id", ""))

    # 检查 claim 无页面承载
    for claim in claims:
        cid = claim.get("claim_id", "")
        if cid not in covered_claim_ids:
            findings.append({
                "finding_id": f"evidence_uncovered_{cid}",
                "severity": "P1",
                "dimension": "claim_coverage",
                "message": f"论点 '{claim.get('claim', '')[:50]}' 没有页面承载。",
                "refs": ["claim_map.json", "page_tasks.json"],
                "repair_instruction": "为该论点分配页面或增加对应 beat。",
                "page_id": cid,
            })

    # 检查 required evidence 缺失
    if claim_evidence_graph:
        for gap in claim_evidence_graph.get("gaps", []):
            findings.append({
                "finding_id": f"evidence_gap_{gap.get('claim_id', 'unknown')}",
                "severity": "P1",
                "dimension": "evidence_readiness",
                "message": gap.get("description", "证据缺口。"),
                "refs": ["claim_evidence_graph.json"],
                "repair_instruction": gap.get("repair_instruction", "补充缺失证据。"),
            })
    else:
        for claim in claims:
            if claim.get("risk_flags"):
                for flag in claim.get("risk_flags", []):
                    if "evidence" in flag.lower():
                        findings.append({
                            "finding_id": f"evidence_missing_{claim.get('claim_id', '')}",
                            "severity": "P1",
                            "dimension": "evidence_readiness",
                            "message": f"论点 '{claim.get('claim', '')[:50]}' 缺少必要证据。",
                            "refs": ["claim_map.json"],
                            "repair_instruction": "补充客户案例、产品截图或业务数据。",
                        })

    # 检查 internal_only evidence 进入 client queue
    if sourcing_plan:
        for decision in sourcing_plan.get("decisions", []):
            candidate = decision.get("selected_candidate") or {}
            pub_status = candidate.get("publication_status", "")
            if pub_status == "internal_only" and decision.get("source_decision") == "reuse":
                findings.append({
                    "finding_id": f"evidence_internal_{decision.get('beat_id', '')}",
                    "severity": "P0",
                    "dimension": "evidence_publication",
                    "message": f"internal_only 证据被标记为 reuse，不能进入 client queue。",
                    "refs": ["sourcing_plan.json"],
                    "repair_instruction": "更换为 safe_to_use 证据或改为 generate。",
                    "page_id": decision.get("beat_id", ""),
                })

    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)

    if has_p0:
        status = "rework_required"
    elif has_p1:
        status = "rework_required"
    else:
        status = "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "evidence",
        "status": status,
        "findings": findings,
        "blocking_summary": {
            "p0_count": sum(1 for f in findings if f["severity"] == "P0"),
            "p1_count": sum(1 for f in findings if f["severity"] == "P1"),
        },
        "blocks_delivery": has_p0 or has_p1,
    }
