from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quality.pptx_audit import audit_pptx
from quality.rubric import (
    DIMENSION_LABELS,
    blocks_delivery,
    decision_from,
    default_scorecard,
    lower_score,
    score_summary,
)
from runtime.run_state import write_json


def severity_for_flags(flags: list[str]) -> str:
    if any(flag in {"missing_core_claim", "evidence_gap"} for flag in flags):
        return "P1"
    return "P2"


def finding(
    finding_id: str,
    severity: str,
    dimension: str,
    message: str,
    refs: list[str],
    repair_instruction: str,
    page_id: str = "",
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "finding_id": finding_id,
        "severity": severity,
        "dimension": dimension,
        "message": message,
        "refs": refs,
        "repair_instruction": repair_instruction,
    }
    if page_id:
        payload["page_id"] = page_id
    if risk_flags:
        payload["risk_flags"] = risk_flags
    return payload


def _report(
    run_id: str,
    gate: str,
    scorecard: dict[str, int],
    findings: list[dict[str, Any]],
    summary: dict[str, Any],
    artifact: str = "",
) -> dict[str, Any]:
    status = decision_from(scorecard, findings)
    page_findings = [item for item in findings if item.get("page_id")]
    repair_plan = [
        item["repair_instruction"]
        for item in findings
        if item.get("severity") in {"P0", "P1", "P2"} and item.get("repair_instruction")
    ][:8]
    return {
        "run_id": run_id,
        "gate": gate,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "artifact": artifact,
        "scorecard": scorecard,
        "score_summary": score_summary(scorecard),
        "summary": summary | {"findings": len(findings), "page_findings": len(page_findings)},
        "findings": findings,
        "page_findings": page_findings,
        "repair_plan": repair_plan,
        "blocks_delivery": blocks_delivery(status, findings),
    }


def evaluate_draft_gate(
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
) -> dict[str, Any]:
    scorecard = default_scorecard(4)
    findings: list[dict[str, Any]] = []
    run_id = str(deck_brief.get("run_id") or claim_map.get("run_id") or page_tasks.get("run_id") or "")

    if not deck_brief.get("business_goal"):
        lower_score(scorecard, "narrative_integrity", 2)
        findings.append(
            finding(
                "draft_goal_missing",
                "P1",
                "narrative_integrity",
                "Deck 缺少明确业务目标。",
                ["deck_brief.json"],
                "补充这份 Deck 的目标受众、希望推动的客户决策，以及本次方案要证明的核心判断。",
            )
        )

    for claim in claim_map.get("claims", []):
        flags = list(claim.get("risk_flags", []))
        if flags:
            severity = severity_for_flags(flags)
            lower_score(scorecard, "evidence_and_specificity", 2 if severity == "P1" else 3)
            findings.append(
                finding(
                    f"{claim.get('claim_id')}_risk",
                    severity,
                    "evidence_and_specificity",
                    f"论点缺少足够证据：{claim.get('claim')}",
                    ["claim_map.json"],
                    "为该论点补充客户原话、数据、案例、产品截图或历史方案页，并说明证据如何支撑判断。",
                    risk_flags=flags,
                )
            )

    for task in page_tasks.get("tasks", []):
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
        beat_id = str(task.get("beat_id") or "")
        if not planning.get("core_claim"):
            lower_score(scorecard, "page_job_clarity", 2)
            findings.append(
                finding(
                    f"{beat_id}_missing_claim",
                    "P1",
                    "page_job_clarity",
                    "页面缺少主论点。",
                    ["page_tasks.json"],
                    "为页面写出一句可被客户理解的主张，并让标题、证据和视觉结构围绕这句主张组织。",
                    page_id=beat_id,
                )
            )
        if planning.get("gaps"):
            lower_score(scorecard, "information_density", 3)
            findings.append(
                finding(
                    f"{beat_id}_gaps",
                    "P2",
                    "information_density",
                    "页面存在证据或信息缺口。",
                    ["page_tasks.json"],
                    "把缺口拆成可补充的证据项，优先补客户语境、产品证明、案例或明确的业务影响。",
                    page_id=beat_id,
                    risk_flags=list(planning.get("gaps", [])),
                )
            )

    return _report(
        run_id,
        "draft",
        scorecard,
        findings,
        {
            "claims": len(claim_map.get("claims", [])),
            "page_tasks": len(page_tasks.get("tasks", [])),
        },
    )


def evaluate_render_gate(
    run_id: str,
    artifact: str | Path,
    expected_pages: int | None = None,
    forbidden_terms: list[str] | None = None,
) -> dict[str, Any]:
    audit = audit_pptx(artifact, expected_pages=expected_pages, forbidden_terms=forbidden_terms)
    scorecard = default_scorecard(4)
    findings: list[dict[str, Any]] = []

    if not audit["page_count_matches"]:
        lower_score(scorecard, "visual_readiness", 2)
        findings.append(
            finding(
                "render_page_count_mismatch",
                "P1",
                "visual_readiness",
                f"PPTX 页数为 {audit['slide_count']}，期望页数为 {audit['expected_pages']}。",
                [str(audit["artifact"])],
                "重新检查组装计划、预览页数和 PPTX 输出，确保没有漏页、重复页或旧版本混入。",
            )
        )

    for slide in audit["sparse_pages"]:
        lower_score(scorecard, "information_density", 2)
        findings.append(
            finding(
                f"slide_{slide['slide_number']:03d}_sparse",
                "P1",
                "information_density",
                "渲染页文本和证据密度过低。",
                [slide["path"]],
                "补充业务含义、证据说明、关键数字或产品证明，避免页面只剩短标签。",
                page_id=f"slide_{slide['slide_number']:03d}",
            )
        )

    for slide in audit["possible_full_slide_images"]:
        lower_score(scorecard, "screenshot_and_asset_integration", 2)
        findings.append(
            finding(
                f"slide_{slide['slide_number']:03d}_possible_full_slide_image",
                "P1",
                "screenshot_and_asset_integration",
                "PPTX 页面疑似整页截图迁移，可能破坏可编辑交付质量。",
                [slide["path"]],
                "优先使用原生 slide 复用或对象级生成；如果必须用图片，需要明确标注为临时降级产物。",
                page_id=f"slide_{slide['slide_number']:03d}",
            )
        )

    return _report(
        run_id,
        "render",
        scorecard,
        findings,
        {
            "slide_count": audit["slide_count"],
            "sparse_pages": len(audit["sparse_pages"]),
            "possible_full_slide_images": len(audit["possible_full_slide_images"]),
        },
        artifact=str(audit["artifact"]),
    ) | {"audit": audit}


def evaluate_delivery_gate(
    run_id: str,
    artifact: str | Path,
    expected_pages: int | None = None,
    forbidden_terms: list[str] | None = None,
) -> dict[str, Any]:
    audit = audit_pptx(artifact, expected_pages=expected_pages, forbidden_terms=forbidden_terms)
    scorecard = default_scorecard(4)
    findings: list[dict[str, Any]] = []

    if not audit["page_count_matches"]:
        lower_score(scorecard, "delivery_readiness", 1)
        findings.append(
            finding(
                "delivery_page_count_mismatch",
                "P0",
                "delivery_readiness",
                f"交付 PPTX 页数为 {audit['slide_count']}，期望页数为 {audit['expected_pages']}。",
                [str(audit["artifact"])],
                "停止交付，重新对齐 source、preview、PPTX 和导出包的页数。",
            )
        )

    for hit in audit["forbidden_hits"]:
        lower_score(scorecard, "consulting_style_expression", 1)
        findings.append(
            finding(
                f"slide_{hit['slide_number']:03d}_forbidden_terms",
                "P0",
                "consulting_style_expression",
                f"可见内容包含内部或禁用词：{', '.join(hit['terms'])}",
                [f"slide_{hit['slide_number']:03d}"],
                "删除或改写客户不可见措辞，再重新生成最终 PPTX。",
                page_id=f"slide_{hit['slide_number']:03d}",
                risk_flags=hit["terms"],
            )
        )

    if not audit["media_files"]:
        lower_score(scorecard, "delivery_readiness", 3)
        findings.append(
            finding(
                "delivery_no_media",
                "P2",
                "delivery_readiness",
                "PPTX 包内没有媒体文件，若方案依赖截图或视觉证据，需要复核资源是否缺失。",
                [str(audit["artifact"])],
                "确认本稿是否应包含产品截图、客户证据图或案例图；如需要，补齐后重新导出。",
            )
        )

    return _report(
        run_id,
        "delivery",
        scorecard,
        findings,
        {
            "slide_count": audit["slide_count"],
            "media_count": audit["media_count"],
            "forbidden_hits": len(audit["forbidden_hits"]),
        },
        artifact=str(audit["artifact"]),
    ) | {"audit": audit}


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# {str(report.get('gate', 'quality')).title()} Gate Report",
        "",
        "**Quality Decision**",
        f"- Status: `{report.get('status')}`",
        f"- Blocks delivery: `{str(report.get('blocks_delivery', False)).lower()}`",
        f"- Artifact: {report.get('artifact') or 'n/a'}",
        "",
        "**Scorecard**",
    ]
    scorecard = report.get("scorecard", {})
    for dimension, score in scorecard.items():
        lines.append(f"- {DIMENSION_LABELS.get(dimension, dimension)}: {score}/5")
    lines.extend(["", "**Findings**"])
    if not report.get("findings"):
        lines.append("- No findings.")
    for item in report.get("findings", []):
        page = f" [{item.get('page_id')}]" if item.get("page_id") else ""
        lines.append(f"- {item.get('severity')} {item.get('finding_id')}{page}: {item.get('message')}")
        lines.append(f"  Repair: {item.get('repair_instruction')}")
    lines.extend(["", "**Repair Plan**"])
    if not report.get("repair_plan"):
        lines.append("- No repair required.")
    for index, repair in enumerate(report.get("repair_plan", []), start=1):
        lines.append(f"{index}. {repair}")
    return "\n".join(lines).rstrip() + "\n"


def write_gate_report(run_dir: str | Path, gate: str, report: dict[str, Any]) -> dict[str, str]:
    root = Path(run_dir).expanduser().resolve()
    output_dir = root / "quality_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json(output_dir / f"{gate}_gate.json", report)
    md_path = output_dir / f"{gate}_gate.md"
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
