from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCaseError, load_benchmark_case
from runtime.run_state import RunStateError, read_json, write_json


SCHEMA_VERSION = "deck_benchmark_aggregate_report.v1"


class BenchmarkAggregateError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (RunStateError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _case_paths(benchmark_dir: Path) -> list[Path]:
    return sorted((benchmark_dir / "cases").glob("*/benchmark_case.json"))


def _report_paths(benchmark_dir: Path) -> list[Path]:
    results_dir = benchmark_dir / "results"
    if not results_dir.exists():
        return []
    paths: list[Path] = []
    for name in ("benchmark_report.json", "benchmark_rc_report.json"):
        paths.extend(sorted(results_dir.glob(f"*/*/{name}")))
    return sorted(paths)


def _load_cases(benchmark_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in _case_paths(benchmark_dir):
        try:
            case = load_benchmark_case(path, benchmark_dir=benchmark_dir)
        except BenchmarkCaseError as exc:
            invalid.append({"path": str(path), "error": str(exc)})
            continue
        data = case.data
        cases.append({
            "case_id": data.get("case_id"),
            "case_name": data.get("case_name"),
            "case_type": data.get("case_type", "fixture"),
            "template": bool(data.get("template")),
            "industry": data.get("industry", ""),
            "audience": data.get("audience", ""),
            "target_pages": data.get("target_pages"),
            "raw_source_policy": (data.get("source_material") or {}).get("raw_source_policy", ""),
            "metadata_path": str(path),
            "warnings": case.warnings,
        })
    return cases, invalid


def _load_reports(benchmark_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in _report_paths(benchmark_dir):
        payload = _safe_read_json(path)
        if not payload:
            continue
        path_case_id = path.parent.parent.name
        path_run_id = path.parent.name
        payload_case_id = payload.get("case_id")
        payload_run_id = payload.get("run_id")
        payload_matches_path = payload_case_id == path_case_id and payload_run_id == path_run_id
        status = payload.get("status")
        score = payload.get("score", {}) if isinstance(payload.get("score"), dict) else {}
        readiness = payload.get("readiness", {}) if isinstance(payload.get("readiness"), dict) else {}
        page_metrics = payload.get("page_metrics", {}) if isinstance(payload.get("page_metrics"), dict) else {}
        efficiency = payload.get("efficiency_metrics", {}) if isinstance(payload.get("efficiency_metrics"), dict) else {}
        rc_eligibility = payload.get("rc_eligibility", {}) if isinstance(payload.get("rc_eligibility"), dict) else {}
        rc_eligible = bool(rc_eligibility.get("eligible"))
        reports.append({
            "case_id": payload_case_id,
            "run_id": payload_run_id,
            "path_case_id": path_case_id,
            "path_run_id": path_run_id,
            "payload_matches_path": payload_matches_path,
            "p4_eligible": payload_matches_path and status == "completed" and rc_eligible,
            "rc_eligible": rc_eligible,
            "rc_eligibility": rc_eligibility,
            "status": status,
            "report_type": path.name,
            "path": str(path),
            "score_overall": score.get("overall"),
            "final_ready": bool(readiness.get("final_ready")),
            "page_acceptance_rate": page_metrics.get("page_acceptance_rate"),
            "estimated_time_saved_hours": efficiency.get("estimated_time_saved_hours"),
        })
    return reports


def _build_report_coverage(
    real_cases: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    real_case_ids = {
        str(case.get("case_id"))
        for case in real_cases
        if case.get("case_id")
    }
    by_case: dict[str, set[str]] = {case_id: set() for case_id in real_case_ids}
    by_case_run: dict[str, dict[str, set[str]]] = {case_id: {} for case_id in real_case_ids}
    for report in reports:
        if not report.get("p4_eligible"):
            continue
        case_id = str(report.get("path_case_id") or "")
        run_id = str(report.get("path_run_id") or "")
        report_type = report.get("report_type")
        if not case_id or case_id not in by_case or not isinstance(report_type, str):
            continue
        by_case[case_id].add(report_type)
        if run_id:
            by_case_run[case_id].setdefault(run_id, set()).add(report_type)

    required_types = {"benchmark_report.json", "benchmark_rc_report.json"}
    cases = []
    for case_id in sorted(real_case_ids):
        present = by_case.get(case_id, set())
        runs = []
        complete_run_ids = []
        best_run_types: set[str] = set()
        for run_id, report_types in sorted(by_case_run.get(case_id, {}).items()):
            missing_for_run = sorted(required_types - report_types)
            if len(report_types) > len(best_run_types):
                best_run_types = report_types
            if not missing_for_run:
                complete_run_ids.append(run_id)
            runs.append({
                "run_id": run_id,
                "benchmark_report": "benchmark_report.json" in report_types,
                "benchmark_rc_report": "benchmark_rc_report.json" in report_types,
                "complete": not missing_for_run,
                "missing_report_types": missing_for_run,
            })
        missing = sorted(required_types - best_run_types) if not complete_run_ids else []
        cases.append({
            "case_id": case_id,
            "benchmark_report": "benchmark_report.json" in present,
            "benchmark_rc_report": "benchmark_rc_report.json" in present,
            "complete": bool(complete_run_ids),
            "complete_run_ids": complete_run_ids,
            "missing_report_types": missing,
            "runs": runs,
        })
    complete_case_ids = [item["case_id"] for item in cases if item["complete"]]
    return {
        "required_report_types": sorted(required_types),
        "complete_real_case_count": len(complete_case_ids),
        "complete_real_case_ids": complete_case_ids,
        "cases": cases,
    }


def _numeric(values: list[Any]) -> list[float]:
    numbers: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numbers.append(float(value))
    return numbers


def build_benchmark_aggregate_report(
    benchmark_dir: str | Path,
    *,
    min_real_cases: int = 3,
) -> dict[str, Any]:
    root = Path(benchmark_dir).expanduser().resolve()
    cases, invalid_cases = _load_cases(root)
    reports = _load_reports(root)
    real_cases = [
        case for case in cases
        if case.get("case_type") == "real_metadata" and not case.get("template")
    ]
    fixture_cases = [
        case for case in cases
        if case.get("case_type") != "real_metadata" or case.get("template")
    ]
    report_coverage = _build_report_coverage(real_cases, reports)
    status = "blocked"
    if len(real_cases) >= min_real_cases:
        status = (
            "report_ready"
            if report_coverage["complete_real_case_count"] >= min_real_cases
            else "metadata_ready"
        )
    metrics = {
        "average_score_overall": _mean(_numeric([report.get("score_overall") for report in reports])),
        "average_page_acceptance_rate": _mean(_numeric([report.get("page_acceptance_rate") for report in reports])),
        "average_estimated_time_saved_hours": _mean(_numeric([report.get("estimated_time_saved_hours") for report in reports])),
        "final_ready_count": sum(1 for report in reports if report.get("final_ready")),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "created_at": _utc_now(),
        "benchmark_dir": str(root),
        "min_real_cases": min_real_cases,
        "case_counts": {
            "total": len(cases),
            "real_metadata": len(real_cases),
            "fixture": len(fixture_cases),
            "invalid": len(invalid_cases),
        },
        "report_counts": {
            "total": len(reports),
            "benchmark_report": sum(1 for report in reports if report.get("report_type") == "benchmark_report.json"),
            "benchmark_rc_report": sum(1 for report in reports if report.get("report_type") == "benchmark_rc_report.json"),
            "complete_real_case_pairs": report_coverage["complete_real_case_count"],
        },
        "report_coverage": report_coverage,
        "private_source_policy": {
            "raw_sources_committed": False,
            "allowed_reference": "local_path_only",
            "real_cases_have_local_source_policy": all(
                case.get("raw_source_policy") == "local_path_only" for case in real_cases
            ),
        },
        "metrics": metrics,
        "real_cases": real_cases,
        "fixture_cases": fixture_cases,
        "invalid_cases": invalid_cases,
        "reports": reports,
    }


def render_benchmark_aggregate_markdown(report: dict[str, Any]) -> str:
    counts = report.get("case_counts", {})
    report_counts = report.get("report_counts", {})
    metrics = report.get("metrics", {})
    lines = [
        "# Benchmark Aggregate Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Real metadata cases: `{counts.get('real_metadata', 0)}`",
        f"- Fixture cases: `{counts.get('fixture', 0)}`",
        f"- Invalid cases: `{counts.get('invalid', 0)}`",
        f"- Reports: `{report_counts.get('total', 0)}`",
        f"- Complete real case report pairs: `{report_counts.get('complete_real_case_pairs', 0)}`",
        f"- Average score: `{metrics.get('average_score_overall')}`",
        f"- Average page acceptance: `{metrics.get('average_page_acceptance_rate')}`",
        f"- Final ready count: `{metrics.get('final_ready_count', 0)}`",
        "",
        "## Real Cases",
        "",
    ]
    for case in report.get("real_cases", []):
        lines.append(
            f"- `{case.get('case_id')}`: {case.get('industry', '')}, "
            f"{case.get('target_pages', '')} pages, source policy `{case.get('raw_source_policy', '')}`"
        )
    if not report.get("real_cases"):
        lines.append("- None")
    lines.extend(["", "## Real Case Report Coverage", ""])
    coverage_cases = report.get("report_coverage", {}).get("cases", [])
    for item in coverage_cases:
        missing = ", ".join(item.get("missing_report_types", [])) or "none"
        lines.append(
            f"- `{item.get('case_id')}`: complete `{item.get('complete')}`, missing `{missing}`"
        )
    if not coverage_cases:
        lines.append("- None")
    lines.extend(["", "## Reports", ""])
    for item in report.get("reports", []):
        lines.append(
            f"- `{item.get('case_id')}` / `{item.get('run_id')}`: "
            f"status `{item.get('status')}`, score `{item.get('score_overall')}`"
        )
    if not report.get("reports"):
        lines.append("- No benchmark reports have been generated yet.")
    lines.append("")
    return "\n".join(lines)


def write_benchmark_aggregate_report(
    benchmark_dir: str | Path,
    *,
    min_real_cases: int = 3,
    force: bool = False,
) -> dict[str, Any]:
    root = Path(benchmark_dir).expanduser().resolve()
    report = build_benchmark_aggregate_report(root, min_real_cases=min_real_cases)
    out_dir = root / "results" / "aggregate"
    json_path = out_dir / "benchmark_aggregate_report.json"
    markdown_path = out_dir / "benchmark_aggregate_report.md"
    if not force and (json_path.exists() or markdown_path.exists()):
        raise BenchmarkAggregateError(f"Benchmark aggregate report already exists: {out_dir}. Use --force to overwrite.")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(json_path, report)
    markdown_path.write_text(render_benchmark_aggregate_markdown(report), encoding="utf-8")
    return {
        "status": report["status"],
        "report": str(json_path),
        "markdown": str(markdown_path),
        "case_counts": report["case_counts"],
        "report_counts": report["report_counts"],
    }
