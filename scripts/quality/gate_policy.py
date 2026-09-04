from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quality.gate_freshness import report_currentity
from quality.overrides import has_active_override
from runtime.render import find_render_result

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


def _finding_id(finding: dict[str, Any]) -> str:
    return str(
        finding.get("finding_id")
        or finding.get("id")
        or finding.get("code")
        or finding.get("message")
        or ""
    )


def _severity(finding: dict[str, Any]) -> str:
    return str(finding.get("severity") or "P2").strip().upper()


def current_artifact(root: Path | str) -> Path | None:
    """Resolve the artifact selected by the current render/build state."""
    run_dir = Path(root).expanduser().resolve()
    _render_path, render_result, _source = find_render_result(run_dir)
    if isinstance(render_result, dict):
        raw = str(render_result.get("artifact_path") or render_result.get("artifact") or "").strip()
        if raw:
            artifact = Path(raw).expanduser()
            if not artifact.is_absolute():
                artifact = run_dir / artifact
            return artifact.resolve()
    high_density_artifact = run_dir / "high_density_build" / "pptx" / "deck_high_density.pptx"
    status_path = run_dir / "high_density_build" / "status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {}
    if (
        isinstance(status, dict)
        and str(status.get("builder_profile") or "") == "high_density"
        and str(status.get("status") or "").lower() == "completed"
        and high_density_artifact.exists()
    ):
        return high_density_artifact.resolve()
    return None


def _blocking_candidates(report: dict[str, Any], gate: str) -> list[dict[str, Any]]:
    findings = _report_findings(report)
    candidates = [item for item in findings if _severity(item) in {"P0", "P1"}]
    if _report_blocks(report) and not candidates:
        candidates = [{
            "finding_id": f"{gate}_gate_blocking",
            "severity": "P1",
            "message": f"{gate} gate blocks delivery.",
            "_gate_name": gate,
        }]
    return candidates


def resolve_required_gates(
    root: Path | str,
    artifact: Path | str | None,
    *,
    builder_profile: str = "",
    output_profile: str = "",
    run_mode: str = "",
    reports: list[dict[str, Any]] | None = None,
    include_non_required_blockers: bool = False,
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
    current_blockers: list[dict[str, Any]] = []
    overridden_p1: list[dict[str, Any]] = []
    stale_reports: list[dict[str, Any]] = []
    unbound_reports: list[dict[str, Any]] = []
    current_candidates_by_gate: dict[str, list[dict[str, Any]]] = {}
    current_blockers_by_gate: dict[str, list[dict[str, Any]]] = {}

    for report in available:
        gate = normalize_gate_name(str(report.get("gate") or report.get("_gate_name") or ""))
        if not gate:
            continue
        currentity = report_currentity(run_dir, {**report, "gate": gate}, artifact)
        currentity_status = str(currentity.get("status") or ("current" if currentity.get("current") else "stale"))
        status = normalize_gate_name(str(report.get("status") or ""))
        blocks = _report_blocks(report)
        summary = {
            "gate": gate,
            "required": gate in required,
            "satisfied": False,
            "currentity": currentity_status,
            "status": status,
            "blocks_delivery": blocks,
            "report_file": str(report.get("_report_file") or ""),
            "reason": str(currentity.get("reason") or ""),
        }
        if gate in gate_status and gate_status[gate]["currentity"] in {"missing", "stale", "unbound"}:
            gate_status[gate] = summary
        if currentity_status == "stale":
            stale_reports.append(summary)
        elif currentity_status == "unbound":
            unbound_reports.append(summary)
        elif currentity.get("current"):
            should_collect = gate in required or include_non_required_blockers
            if should_collect:
                candidates = _blocking_candidates(report, gate)
                current_candidates_by_gate.setdefault(gate, []).extend(candidates)
                for finding in candidates:
                    item = {**finding, "_gate_name": gate}
                    severity = _severity(item)
                    if severity == "P0":
                        current_blockers.append(item)
                        current_blockers_by_gate.setdefault(gate, []).append(item)
                    elif severity == "P1":
                        finding_id = _finding_id(item)
                        if finding_id and has_active_override(run_dir, finding_id):
                            overridden_p1.append(item)
                        else:
                            current_blockers.append(item)
                            current_blockers_by_gate.setdefault(gate, []).append(item)

        if gate in gate_status and currentity.get("current"):
            candidates = current_candidates_by_gate.get(gate, [])
            unresolved = current_blockers_by_gate.get(gate, [])
            all_candidates_overridden_p1 = bool(candidates) and all(
                _severity(item) == "P1" and _finding_id(item) and has_active_override(run_dir, _finding_id(item))
                for item in candidates
            )
            gate_status[gate]["satisfied"] = (
                status in PASSING_GATE_STATUSES and not unresolved
            ) or all_candidates_overridden_p1

    missing = [gate for gate, summary in gate_status.items() if not summary.get("satisfied")]
    required_gate_satisfied = not missing
    # A gate can carry a blocking status even when its report has no findings.
    # The synthetic finding above keeps that status visible to all consumers.
    satisfied = required_gate_satisfied and not current_blockers
    if not required_gate_satisfied:
        recommended_action = "run_required_quality_gate"
    elif current_blockers:
        recommended_action = "repair_current_quality_findings"
    else:
        recommended_action = "final_readiness"
    return {
        "required_gates": required,
        "gate_status": list(gate_status.values()),
        "current_pass_gates": [gate for gate, summary in gate_status.items() if summary.get("satisfied")],
        "missing_gates": missing,
        "missing_required_gates": missing,
        "stale_gates": stale_reports,
        "unbound_gates": unbound_reports,
        "stale_reports": stale_reports,
        "unbound_reports": unbound_reports,
        "blocking_findings": current_blockers,
        "current_blockers": current_blockers,
        "overridden_p1": overridden_p1,
        "required_gate_satisfied": required_gate_satisfied,
        "recommended_action": recommended_action,
        "satisfied": satisfied,
    }
