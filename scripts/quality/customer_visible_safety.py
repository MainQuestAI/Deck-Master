from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quality.gate_freshness import artifact_identity
from quality.pptx_audit import audit_pptx
from quality.pptx_audit import load_page_roles, requires_page_role_contract
from runtime.run_state import read_json


SCHEMA_VERSION = "deck_customer_visible_safety_gate.v1"
GATE_NAME = "customer_visible_safety"
DEFAULT_FORBIDDEN_TERMS = [
    "关键图示",
    "证书墙",
    "缩略图",
    "卡一",
    "卡二",
    "左区",
    "右区",
    "左屏",
    "右屏",
    "功能证据 + 业务价值",
    "系统功能证据 + 业务价值",
    "系统功能证据",
    "待补",
    "占位",
    "TODO",
    "TBD",
    "placeholder",
    "manual_placeholder",
]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _terms_from_file(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    terms: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def _workspace_for_run(run_dir: Path) -> Path | None:
    request_path = run_dir / "request.json"
    if not request_path.exists():
        return None
    try:
        request = read_json(request_path)
    except Exception:
        return None
    workspace = str(request.get("workspace") or "").strip()
    if not workspace:
        return None
    return Path(workspace).expanduser().resolve()


def load_customer_visible_forbidden_terms(
    run_dir: str | Path | None = None,
    *,
    extra_terms: list[str] | None = None,
) -> list[str]:
    terms = list(DEFAULT_FORBIDDEN_TERMS)
    root = Path(run_dir).expanduser().resolve() if run_dir else None
    if root:
        terms.extend(_terms_from_file(root / "quality" / "forbidden_terms.md"))
        workspace = _workspace_for_run(root)
        if workspace:
            terms.extend(_terms_from_file(workspace / "quality" / "forbidden_terms.md"))
    terms.extend(extra_terms or [])
    return _dedupe(terms)


def _page_id_for_hit(hit: dict[str, Any]) -> str:
    slide_number = hit.get("slide_number")
    if isinstance(slide_number, int) and slide_number > 0:
        return f"slide_{slide_number:03d}"
    return ""


def _finding_for_hit(index: int, hit: dict[str, Any]) -> dict[str, Any]:
    term = str(hit.get("term") or "")
    scope = str(hit.get("scope") or "pptx")
    package_path = str(hit.get("package_path") or "")
    page_id = _page_id_for_hit(hit)
    finding_id = f"customer_visible_forbidden_{index:03d}"
    finding: dict[str, Any] = {
        "finding_id": finding_id,
        "severity": "P0",
        "dimension": "customer_visible_safety",
        "message": f"最终 PPT 包含客户不可见的内部制作语言：{term}",
        "refs": [package_path] if package_path else [],
        "repair_instruction": "删除或改写该词，再重新生成最终 PPTX 并重新运行客户可见内容安全门禁。",
        "risk_flags": [term],
        "term": term,
        "scope": scope,
        "package_path": package_path,
        "slide_number": hit.get("slide_number"),
        "excerpt": str(hit.get("excerpt") or ""),
    }
    if page_id:
        finding["page_id"] = page_id
    return finding


def evaluate_customer_visible_safety_gate(
    run_id: str,
    artifact: str | Path,
    *,
    expected_pages: int | None = None,
    forbidden_terms: list[str] | None = None,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    terms = _dedupe(forbidden_terms or DEFAULT_FORBIDDEN_TERMS)
    page_roles = load_page_roles(run_dir) if run_dir else None
    audit = audit_pptx(
        artifact,
        expected_pages=expected_pages,
        forbidden_terms=terms,
        page_roles=page_roles,
        strict_page_roles=requires_page_role_contract(run_dir),
    )
    findings = [
        _finding_for_hit(index, hit)
        for index, hit in enumerate(audit.get("forbidden_hits", []), start=1)
    ]
    for slide_number in audit.get("missing_page_roles", []):
        findings.append(
            {
                "finding_id": f"customer_visible_missing_page_role_{int(slide_number):03d}",
                "severity": "P1",
                "dimension": "page_role_contract",
                "message": f"最终 PPT 第 {int(slide_number)} 页缺少 page_role 映射。",
                "repair_instruction": "在 Standard Build Manifest 或 high-density page scene 中补齐 canonical page_role，并重新生成和扫描最终 PPTX。",
                "slide_number": int(slide_number),
                "page_id": f"slide_{int(slide_number):03d}",
            }
        )
    # SC-1 C3 (spec 06 §6.6): client-visible scope covers speaker notes,
    # metadata, hidden slides and internal labels — not just visible text.
    # The scan applies to real PPTX packages; artifacts the pptx reader
    # cannot open fall back to the base audit above (never crash the gate).
    try:
        from quality.semantic_checks import scan_delivery_pptx

        for index, scan_finding in enumerate(scan_delivery_pptx(artifact), start=1):
            findings.append(
                {
                    "finding_id": f"customer_visible_hidden_content_{index:03d}",
                    "severity": "P1",
                    "dimension": "hidden_content",
                    "message": str(scan_finding.get("message") or ""),
                    "repair_instruction": "移除隐藏内容/元数据/内部标签后重新导出，再重新运行 customer_visible_safety 门。",
                    "slide_number": int(scan_finding.get("slide") or 0) or None,
                    "page_id": f"slide_{int(scan_finding.get('slide') or 0):03d}" if scan_finding.get("slide") else "",
                }
            )
    except Exception:  # noqa: BLE001 - scan is additive; unreadable artifacts keep base-audit findings only.
        pass
    blocked = bool(findings)
    status = "rework_required" if blocked else "pass"
    p0_count = sum(1 for item in findings if item.get("severity") == "P0")
    p1_count = sum(1 for item in findings if item.get("severity") == "P1")
    artifact_path = Path(str(audit.get("artifact") or artifact)).expanduser().resolve()
    identity_root = Path(run_dir).expanduser().resolve() if run_dir else artifact_path.parent
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": GATE_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "artifact": str(audit.get("artifact") or ""),
        **artifact_identity(identity_root, artifact_path),
        "scorecard": {
            "customer_visible_safety": 1 if blocked else 5,
            "delivery_readiness": 1 if blocked else 5,
        },
        "score_summary": {
            "min_score": 1 if blocked else 5,
            "average_score": 1 if blocked else 5,
        },
        "summary": {
            "scanned_items": len(audit.get("text_items", [])),
            "forbidden_hits": len(audit.get("forbidden_hits", [])),
            "terms_loaded": len(terms),
            "p0_count": p0_count,
            "p1_count": p1_count,
            "p2_count": 0,
            "findings": len(findings),
            "page_findings": sum(1 for item in findings if item.get("page_id")),
        },
        "findings": findings,
        "page_findings": [item for item in findings if item.get("page_id")],
        "repair_plan": [
            "清理最终 PPTX 中的内部制作语言、占位标签和模板默认文案。",
            "重新导出 PPTX 后再次运行 delivery gate 和 final readiness。",
        ]
        if blocked
        else [],
        "blocks_delivery": blocked,
        "audit": audit,
        "forbidden_terms": terms,
    }
