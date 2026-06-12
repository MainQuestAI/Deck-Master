from __future__ import annotations

from typing import Any


def _table(mapping: dict[str, Any]) -> str:
    lines = ["| Metric | Value |", "|---|---:|"]
    for key, value in mapping.items():
        if value is None:
            text = "pending"
        elif isinstance(value, float):
            text = f"{value:.2f}".rstrip("0").rstrip(".")
        else:
            text = str(value)
        lines.append(f"| `{key}` | {text} |")
    return "\n".join(lines)


def _status_table(mapping: dict[str, Any]) -> str:
    lines = ["| Item | Status |", "|---|---|"]
    for key, value in mapping.items():
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def render_benchmark_markdown(report: dict[str, Any]) -> str:
    case = report.get("case", {}) if isinstance(report.get("case"), dict) else {}
    artifact_index = report.get("artifact_index", {}) if isinstance(report.get("artifact_index"), dict) else {}
    recommendations = report.get("recommendations", [])

    lines = [
        f"# Benchmark Report: {case.get('case_name') or report.get('case_id')}",
        "",
        "## Case Summary",
        "",
        f"- Case ID: `{report.get('case_id')}`",
        f"- Case name: {case.get('case_name', '')}",
        f"- Industry: {case.get('industry', '')}",
        f"- Audience: {case.get('audience', '')}",
        f"- Status: `{report.get('status')}`",
        "",
        "## Run Summary",
        "",
        f"- Run ID: `{report.get('run_id')}`",
        f"- Created at: `{report.get('created_at')}`",
        f"- Readiness: `{report.get('readiness', {}).get('overall', '')}`",
        "",
        "## Efficiency Metrics",
        "",
        _table(report.get("efficiency_metrics", {})),
        "",
        "## Page Metrics",
        "",
        _table(report.get("page_metrics", {})),
        "",
        "## Source Metrics",
        "",
        _table(report.get("source_metrics", {})),
        "",
        "## Quality Metrics",
        "",
        _table(report.get("quality_metrics", {})),
        "",
        "## Generation Metrics",
        "",
        _table(report.get("generation_metrics", {})),
        "",
        "## UAT Summary",
        "",
        _status_table(report.get("uat_summary", {})),
        "",
        "## Target Evaluation",
        "",
        _status_table(report.get("target_evaluation", {})),
        "",
        "## Score",
        "",
        _table(report.get("score", {})),
        "",
        "## Recommendations",
        "",
    ]
    if recommendations:
        lines.extend([f"- {item}" for item in recommendations])
    else:
        lines.append("- No immediate recommendation.")
    lines.extend(["", "## Artifact Index", ""])
    if artifact_index:
        lines.extend([f"- `{key}`: `{value}`" for key, value in artifact_index.items()])
    else:
        lines.append("- No artifacts indexed.")
    lines.append("")
    return "\n".join(lines)

