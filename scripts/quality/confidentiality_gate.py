from __future__ import annotations
from typing import Any
from pathlib import Path
import re

SCHEMA_VERSION = "deck_confidentiality_gate.v1"

# 默认敏感词模式（密钥、token、账号、报价底线）
SENSITIVE_PATTERNS = [
    (r'(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S+', "P0", "密钥/token 暴露"),
    (r'\b(?:账号|account)\s*[:=]\s*\S+', "P0", "账号信息暴露"),
    (r'(?:底价|成本价|报价底线)\s*[:=]?\s*[\d,]+', "P0", "报价底线暴露"),
]

def evaluate_confidentiality_gate(
    run_id: str,
    *,
    forbidden_terms: list[str] | None = None,
    workspace_forbidden_terms_path: str | Path | None = None,
    preview_manifest: dict[str, Any] | None = None,
    sourcing_plan: dict[str, Any] | None = None,
    artifact_text: str = "",
) -> dict[str, Any]:
    """检查内部词、客户名残留、敏感来源。"""
    findings = []

    # 加载 forbidden terms
    all_forbidden = list(forbidden_terms or [])
    if workspace_forbidden_terms_path:
        path = Path(workspace_forbidden_terms_path)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                term = line.strip()
                if term and not term.startswith("#"):
                    all_forbidden.append(term)

    # 检查 artifact_text 中的 forbidden terms
    for term in all_forbidden:
        if term.lower() in artifact_text.lower():
            findings.append({
                "finding_id": f"confidential_forbidden_{term[:20]}",
                "severity": "P1",
                "dimension": "forbidden_terms",
                "message": f"内容包含禁用词：'{term[:30]}'。",
                "refs": ["forbidden_terms.md"],
                "repair_instruction": f"删除或替换 '{term[:30]}'。",
            })

    # 检查敏感模式
    for pattern, severity, description in SENSITIVE_PATTERNS:
        matches = re.findall(pattern, artifact_text, re.IGNORECASE)
        for match in matches[:3]:  # 最多报告 3 个匹配
            findings.append({
                "finding_id": f"confidential_sensitive_{description}",
                "severity": severity,
                "dimension": "sensitive_data",
                "message": f"检测到敏感数据：{description}。",
                "refs": [],
                "repair_instruction": "删除敏感数据后再导出。",
            })

    # 检查 sourcing plan 中的 needs_redaction 来源
    if sourcing_plan:
        for decision in sourcing_plan.get("decisions", []):
            candidate = decision.get("selected_candidate") or {}
            pub_status = candidate.get("publication_status", "")
            if pub_status == "needs_redaction" and decision.get("source_decision") in ("reuse", "adapt"):
                findings.append({
                    "finding_id": f"confidential_redaction_{decision.get('beat_id', '')}",
                    "severity": "P0",
                    "dimension": "source_publication",
                    "message": "needs_redaction 来源进入 client export。",
                    "page_id": decision.get("beat_id", ""),
                    "refs": ["sourcing_plan.json"],
                    "repair_instruction": "对来源进行脱敏处理或替换为其他来源。",
                })

    # 检查 preview manifest 页面标题中的 forbidden terms
    if preview_manifest:
        for page in preview_manifest.get("pages", []):
            title = page.get("title", "")
            notes = page.get("notes", "")
            text_to_check = f"{title} {notes}"
            for term in all_forbidden:
                if term.lower() in text_to_check.lower():
                    findings.append({
                        "finding_id": f"confidential_page_{page.get('page_id', '')}_{term[:15]}",
                        "severity": "P1",
                        "dimension": "forbidden_terms",
                        "message": f"页面 '{page.get('page_id', '')}' 包含禁用词：'{term[:30]}'。",
                        "page_id": page.get("page_id", ""),
                        "refs": ["preview_manifest.json"],
                        "repair_instruction": f"从页面标题或备注中删除 '{term[:30]}'。",
                    })

    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)
    status = "rework_required" if has_p0 else ("conditional_pass" if has_p1 else "pass")

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "confidentiality",
        "status": status,
        "findings": findings,
        "blocks_delivery": has_p0,
    }
