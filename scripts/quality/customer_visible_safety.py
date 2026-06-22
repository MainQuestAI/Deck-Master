from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quality.pptx_audit import audit_pptx
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
    "制作",
    "讲标",
    "投标",
    "评审",
    "评分",
    "内部",
    "Brief",
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
) -> dict[str, Any]:
    terms = _dedupe(forbidden_terms or DEFAULT_FORBIDDEN_TERMS)
    audit = audit_pptx(artifact, expected_pages=expected_pages, forbidden_terms=terms)
    findings = [
        _finding_for_hit(index, hit)
        for index, hit in enumerate(audit.get("forbidden_hits", []), start=1)
    ]
    blocked = bool(findings)
    status = "rework_required" if blocked else "pass"
    p0_count = sum(1 for item in findings if item.get("severity") == "P0")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": GATE_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "artifact": str(audit.get("artifact") or ""),
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
            "p1_count": 0,
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
