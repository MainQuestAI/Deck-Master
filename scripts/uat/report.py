from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_typed_event


SCHEMA_VERSION = "deck_uat_report.v1"
_UNSAFE_MARKERS = (
    "/Users/",
    "/Volumes/",
    "/home/",
    "/opt/",
    "/private/",
    "/tmp/",
    "/var/",
    "\\Users\\",
)
_UNSAFE_KEYS = ('"source_file"', '"source_path"')


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id_from_dir(run_dir: Path) -> str:
    request_path = run_dir / "request.json"
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            return str(request.get("run_id") or run_dir.name)
        except json.JSONDecodeError:
            return run_dir.name
    return run_dir.name


def build_check(
    check_id: str,
    passed: bool,
    severity: str,
    message: str,
    *,
    refs: list[str] | None = None,
) -> dict[str, Any]:
    safe_refs = []
    for ref in refs or []:
        value = str(ref).strip().replace("\\", "/")
        if not value or value.startswith("/") or "../" in value or value == "..":
            value = "[external-ref]"
        if value not in safe_refs:
            safe_refs.append(value)
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "severity": severity,
        "message": message,
        "refs": safe_refs,
    }


def _evidence_safety_violations(*texts: str) -> list[str]:
    configured = [
        marker.strip()
        for marker in os.environ.get("DECK_MASTER_EVIDENCE_FORBIDDEN_MARKERS", "").split(",")
        if marker.strip()
    ]
    joined = "\n".join(texts)
    violations = [f"forbidden marker: {marker}" for marker in (*_UNSAFE_MARKERS, *configured) if marker in joined]
    violations.extend(f"forbidden field: {key.strip(chr(34))}" for key in _UNSAFE_KEYS if key in joined)
    if re.search(r'"\s*:\s*"/(?!/)', joined):
        violations.append("absolute path value")
    return sorted(set(violations))


def build_uat_report(
    run_dir: Path,
    tool: str,
    checks: list[dict[str, Any]],
    metrics: dict[str, Any],
    recommendations: list[str],
    *,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    failed = sum(1 for check in checks if not check.get("passed") and check.get("severity") == "error")
    warnings = sum(1 for check in checks if not check.get("passed") and check.get("severity") == "warning")
    passed = sum(1 for check in checks if check.get("passed"))
    if failed:
        status = "fail"
    elif warnings:
        status = "warning"
    elif not checks:
        status = "not_applicable"
    else:
        status = "pass"
    findings = [
        {
            "finding_id": check.get("check_id", "uat_check"),
            "severity": check.get("severity", "info"),
            "message": check.get("message", ""),
            "refs": check.get("refs", []),
        }
        for check in checks
        if not check.get("passed")
    ]
    return {
        "schema_version": schema_version,
        "run_id": _run_id_from_dir(run_dir),
        "tool": tool,
        "status": status,
        "created_at": utc_now(),
        "summary": {
            "checks": len(checks),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        },
        "metrics": metrics,
        "findings": findings,
        "recommendations": recommendations,
    }


def render_uat_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('tool', 'uat')} UAT Report",
        "",
        f"- Run: `{report.get('run_id', '')}`",
        f"- Status: `{report.get('status', '')}`",
        f"- Created: `{report.get('created_at', '')}`",
        "",
        "## Summary",
        "",
    ]
    summary = report.get("summary", {})
    lines.extend(
        [
            f"- Checks: {summary.get('checks', 0)}",
            f"- Passed: {summary.get('passed', 0)}",
            f"- Warnings: {summary.get('warnings', 0)}",
            f"- Failed: {summary.get('failed', 0)}",
            "",
            "## Metrics",
            "",
        ]
    )
    metrics = report.get("metrics", {})
    if metrics:
        for key, value in metrics.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No metrics.")
    lines.extend(["", "## Findings", ""])
    findings = report.get("findings", [])
    if findings:
        for finding in findings:
            refs = ", ".join(finding.get("refs", []))
            ref_text = f" ({refs})" if refs else ""
            lines.append(f"- [{finding.get('severity', 'info')}] {finding.get('message', '')}{ref_text}")
    else:
        lines.append("- No findings.")
    lines.extend(["", "## Recommendations", ""])
    recommendations = report.get("recommendations", [])
    if recommendations:
        for item in recommendations:
            lines.append(f"- {item}")
    else:
        lines.append("- No recommendations.")
    return "\n".join(lines) + "\n"


def write_uat_report(run_dir: Path, name: str, report: dict[str, Any]) -> dict[str, Any]:
    output_dir = run_dir / "uat_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{name}.json"
    md_path = output_dir / f"{name}.md"
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    json.loads(payload)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(render_uat_markdown(report), encoding="utf-8")
    violations = _evidence_safety_violations(
        json_path.read_text(encoding="utf-8"),
        md_path.read_text(encoding="utf-8"),
    )
    if violations:
        json_path.unlink(missing_ok=True)
        md_path.unlink(missing_ok=True)
        raise ValueError(f"UAT evidence safety scan failed: {', '.join(violations)}")
    append_typed_event(
        run_dir,
        "artifact_written",
        f"uat.{name}.written",
        f"UAT report written: {name}",
        run_id=str(report.get("run_id", "")),
        refs=[f"uat_reports/{name}.json", f"uat_reports/{name}.md"],
        severity="info" if report.get("status") != "fail" else "warning",
        payload={"status": report.get("status"), "tool": report.get("tool")},
    )
    result = dict(report)
    result["json_path"] = str(json_path)
    result["markdown_path"] = str(md_path)
    return result
