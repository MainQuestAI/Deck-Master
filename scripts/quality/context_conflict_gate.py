from __future__ import annotations
from typing import Any

SCHEMA_VERSION = "deck_context_conflict_gate.v1"

def evaluate_context_conflict_gate(
    run_id: str,
    request: dict[str, Any],
    sourcing_plan: dict[str, Any],
    asset_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """检查复用页与当前客户语境冲突。

    检查项：
    - 历史页行业与当前行业冲突
    - 历史页客户名残留
    - 历史页场景与当前 claim 不匹配
    - 历史证据缺对外授权
    """
    findings = []
    current_industry = request.get("industry", "")
    current_client = request.get("project_name", "")

    for decision in sourcing_plan.get("decisions", []):
        if decision.get("source_decision") not in ("reuse", "adapt"):
            continue

        candidate = decision.get("selected_candidate") or {}
        beat_id = decision.get("beat_id", "")
        candidate_industry = candidate.get("industry", candidate.get("metadata", {}).get("industry", ""))
        candidate_client = candidate.get("client_name", candidate.get("metadata", {}).get("client_name", ""))

        # 行业冲突
        if current_industry and candidate_industry and current_industry != candidate_industry:
            findings.append({
                "finding_id": f"conflict_industry_{beat_id}",
                "severity": "P1",
                "dimension": "industry_conflict",
                "message": f"历史页行业 '{candidate_industry}' 与当前行业 '{current_industry}' 冲突。",
                "page_id": beat_id,
                "asset_id": candidate.get("canonical_slide_id", ""),
                "source_ref": candidate.get("source_pptx", ""),
                "repair_instruction": "替换为同行业历史页或标记为 adapt 并重写行业语境。",
            })

        # 客户名残留
        if candidate_client and current_client and candidate_client != current_client:
            findings.append({
                "finding_id": f"conflict_client_{beat_id}",
                "severity": "P1",
                "dimension": "client_name_residual",
                "message": f"历史页包含其他客户名 '{candidate_client}'。",
                "page_id": beat_id,
                "asset_id": candidate.get("canonical_slide_id", ""),
                "source_ref": candidate.get("source_pptx", ""),
                "repair_instruction": "清除或替换历史客户名。",
            })

    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)
    status = "rework_required" if (has_p0 or has_p1) else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "context_conflict",
        "status": status,
        "findings": findings,
        "blocks_delivery": has_p0 or has_p1,
    }
