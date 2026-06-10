from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.run_state import write_json


def severity_for_flags(flags: list[str]) -> str:
    if any(flag in {"missing_core_claim", "evidence_gap"} for flag in flags):
        return "P1"
    return "P2"


def evaluate_draft(deck_brief: dict[str, Any], claim_map: dict[str, Any], page_tasks: dict[str, Any]) -> dict[str, Any]:
    findings = []
    if not deck_brief.get("business_goal"):
        findings.append(
            {
                "finding_id": "draft_goal_missing",
                "severity": "P1",
                "message": "Deck 缺少明确业务目标。",
                "refs": ["deck_brief.json"],
            }
        )
    for claim in claim_map.get("claims", []):
        flags = list(claim.get("risk_flags", []))
        if flags:
            findings.append(
                {
                    "finding_id": f"{claim.get('claim_id')}_risk",
                    "severity": severity_for_flags(flags),
                    "message": f"论点缺少足够证据：{claim.get('claim')}",
                    "refs": ["claim_map.json"],
                    "risk_flags": flags,
                }
            )
    for task in page_tasks.get("tasks", []):
        planning = task.get("planning", {}) if isinstance(task.get("planning"), dict) else {}
        if not planning.get("core_claim"):
            findings.append(
                {
                    "finding_id": f"{task.get('beat_id')}_missing_claim",
                    "severity": "P1",
                    "message": "页面缺少主论点。",
                    "refs": ["page_tasks.json"],
                    "beat_id": task.get("beat_id"),
                }
            )
        if planning.get("gaps"):
            findings.append(
                {
                    "finding_id": f"{task.get('beat_id')}_gaps",
                    "severity": "P2",
                    "message": "页面存在证据或信息缺口。",
                    "refs": ["page_tasks.json"],
                    "beat_id": task.get("beat_id"),
                    "risk_flags": planning.get("gaps", []),
                }
            )
    status = "pass"
    if any(finding["severity"] == "P1" for finding in findings):
        status = "rework_required"
    elif findings:
        status = "conditional_pass"
    return {
        "run_id": deck_brief.get("run_id", ""),
        "gate": "draft",
        "status": status,
        "summary": {
            "claims": len(claim_map.get("claims", [])),
            "page_tasks": len(page_tasks.get("tasks", [])),
            "findings": len(findings),
        },
        "findings": findings,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Draft Gate Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Claims: {report.get('summary', {}).get('claims', 0)}",
        f"- Page tasks: {report.get('summary', {}).get('page_tasks', 0)}",
        f"- Findings: {report.get('summary', {}).get('findings', 0)}",
        "",
    ]
    for finding in report.get("findings", []):
        lines.append(f"## {finding.get('finding_id')}")
        lines.append("")
        lines.append(f"- Severity: `{finding.get('severity')}`")
        lines.append(f"- Message: {finding.get('message')}")
        if finding.get("beat_id"):
            lines.append(f"- Beat: `{finding.get('beat_id')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_draft_gate_report(run_dir: str | Path, report: dict[str, Any]) -> dict[str, str]:
    root = Path(run_dir).expanduser().resolve()
    output_dir = root / "quality_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json(output_dir / "draft_gate.json", report)
    md_path = output_dir / "draft_gate.md"
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
