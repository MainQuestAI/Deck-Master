from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quality.gate_freshness import report_currentity

PASSING_GATE_STATUSES = {"pass", "conditional_pass", "pass_with_warning", "pass_with_override"}
BLOCKING_GATE_STATUSES = {"rework_required", "failed", "blocked"}
ARTIFACT_REQUIRED_GATES = ("render", "delivery", "customer_visible_safety")


def normalize_gate_name(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def required_gate_names(
    *,
    builder_profile: str = "",
    output_profile: str = "",
    run_mode: str = "",
) -> list[str]:
    mode = normalize_gate_name(run_mode)
    output = normalize_gate_name(output_profile)
    builder = normalize_gate_name(builder_profile)
    if mode in {"fixture", "dev"}:
        return ["render"]
    if builder == "high_density" or output == "production_pptx" or mode in {"production", "benchmark"}:
        return list(ARTIFACT_REQUIRED_GATES)
    return ["render", "delivery"]


def load_gate_reports(root: Path | str) -> list[dict[str, Any]]:
    run_dir = Path(root).expanduser().resolve()
    reports: list[dict[str, Any]] = []
    quality_dir = run_dir / "quality_reports"
    if not quality_dir.is_dir():
        return reports
    for gate_file in sorted(quality_dir.glob("*_gate.json")):
        try:
            report = json.loads(gate_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(report, dict):
            continue
        gate_name = normalize_gate_name(str(report.get("gate") or gate_file.stem.removesuffix("_gate")))
        item = dict(report)
        item["_gate_name"] = gate_name
        item["_report_file"] = gate_file.name
        reports.append(item)
    return reports


def _report_blocks(report: dict[str, Any]) -> bool:
    return bool(report.get("blocks_delivery")) or normalize_gate_name(str(report.get("status") or "")) in BLOCKING_GATE_STATUSES


def _report_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in ("findings", "page_findings"):
        for finding in report.get(key, []):
            if isinstance(finding, dict):
                item = dict(finding)
                item["_gate_name"] = report.get("_gate_name", "")
                findings.append(item)
    return findings


def resolve_required_gates(
    root: Path | str,
    artifact: Path | str | None,
    *,
    builder_profile: str = "",
    output_profile: str = "",
    run_mode: str = "",
    reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    run_dir = Path(root).expanduser().resolve()
    required = required_gate_names(
        builder_profile=builder_profile,
        output_profile=output_profile,
        run_mode=run_mode,
    )
    available = reports if reports is not None else load_gate_reports(run_dir)
    gate_status: dict[str, dict[str, Any]] = {
        gate: {
            "gate": gate,
            "required": True,
            "satisfied": False,
            "currentity": "missing",
            "status": "missing",
            "blocks_delivery": False,
            "report_file": "",
            "reason": "gate report is missing",
        }
        for gate in required
    }
    blocking_findings: list[dict[str, Any]] = []
    stale_gates: list[dict[str, Any]] = []
    unbound_gates: list[dict[str, Any]] = []

    for report in available:
        gate = normalize_gate_name(str(report.get("gate") or report.get("_gate_name") or ""))
        if not gate:
            continue
        currentity = report_currentity(run_dir, {**report, "gate": gate}, artifact, artifact_bound=(gate in required))
        currentity_status = str(currentity.get("status") or ("current" if currentity.get("current") else "stale"))
        status = normalize_gate_name(str(report.get("status") or ""))
        blocks = _report_blocks(report)
        summary = {
            "gate": gate,
            "required": gate in required,
            "satisfied": bool(currentity.get("current")) and status in PASSING_GATE_STATUSES and not blocks,
            "currentity": currentity_status,
            "status": status,
            "blocks_delivery": blocks,
            "report_file": str(report.get("_report_file") or ""),
            "reason": str(currentity.get("reason") or ""),
        }
        if gate in gate_status and gate_status[gate]["currentity"] in {"missing", "stale", "unbound"}:
            gate_status[gate] = summary
        if currentity_status == "stale":
            stale_gates.append(summary)
        elif currentity_status == "unbound":
            unbound_gates.append(summary)
        elif currentity.get("current") and blocks:
            blocking_findings.extend(_report_findings(report))

    missing = [gate for gate, summary in gate_status.items() if not summary.get("satisfied")]
    return {
        "required_gates": required,
        "gate_status": list(gate_status.values()),
        "current_pass_gates": [gate for gate, summary in gate_status.items() if summary.get("satisfied")],
        "missing_gates": missing,
        "stale_gates": stale_gates,
        "unbound_gates": unbound_gates,
        "blocking_findings": blocking_findings,
        "satisfied": not missing and not blocking_findings,
    }
