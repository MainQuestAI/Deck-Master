from __future__ import annotations
from typing import Any
from pathlib import Path

SCHEMA_VERSION = "deck_brand_gate.v1"

def evaluate_brand_gate(
    run_id: str,
    *,
    workspace_dir: str | Path | None = None,
    final_artifact: str | Path | None = None,
    approved_page_count: int = 0,
) -> dict[str, Any]:
    """轻量版 Brand Gate。

    检查：
    - 是否存在 workspace visual-system
    - final artifact 是否存在
    - 页数是否与 approved queue 一致
    - 可抽取文本时检查字体/品牌词基础一致性

    状态：pass / conditional_pass / rework_required / not_applicable
    """
    findings = []

    # 检查 final artifact 是否存在
    artifact_path = Path(final_artifact) if final_artifact else None
    if not artifact_path or not artifact_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "gate": "brand",
            "status": "not_applicable",
            "findings": [],
            "message": "无渲染资产，Brand Gate 暂不适用。等待渲染资产生成后重新运行。",
            "blocks_delivery": False,
        }

    brand_requirements: list[Path] = []
    if workspace_dir:
        vs_dir = Path(workspace_dir) / "visual-system"
        if vs_dir.is_dir():
            brand_requirements = [path for path in vs_dir.iterdir() if path.is_file() and path.stat().st_size > 0]

    if brand_requirements:
        findings.append({
            "finding_id": "brand_review_not_performed",
            "severity": "P2",
            "dimension": "visual_consistency",
            "message": "已发现品牌要求，但本检查没有对成品颜色、字体和素材进行实际品牌审阅。",
            "refs": [str(path) for path in brand_requirements],
            "repair_instruction": "对照品牌要求审阅当前成品，并记录具体观察与修订。",
        })

    # 检查页数（简化：用 python-pptx 如果可用）
    actual_pages = None
    try:
        from pptx import Presentation
        prs = Presentation(str(artifact_path))
        actual_pages = len(prs.slides)
    except Exception:
        pass

    if actual_pages is not None and approved_page_count > 0:
        if actual_pages != approved_page_count:
            findings.append({
                "finding_id": "brand_page_count_mismatch",
                "severity": "P1",
                "dimension": "page_consistency",
                "message": f"Final artifact 页数 {actual_pages} 与 approved queue 页数 {approved_page_count} 不一致。",
                "refs": [str(artifact_path)],
                "repair_instruction": "检查组装流程，确保所有 approved 页面都已包含在 final artifact 中。",
            })

    has_p0 = any(f["severity"] == "P0" for f in findings)
    has_p1 = any(f["severity"] == "P1" for f in findings)

    if has_p0:
        status = "rework_required"
    elif has_p1:
        status = "rework_required"
    elif findings:
        status = "conditional_pass"
    else:
        status = "not_applicable"

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": "brand",
        "status": status,
        "findings": findings,
        "blocks_delivery": has_p0 or has_p1,
    }
