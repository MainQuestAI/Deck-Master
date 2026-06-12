from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCase
from benchmark.checkpoints import (
    calculate_checkpoint_duration_minutes,
    calculate_human_review_minutes,
    read_benchmark_checkpoints,
)
from benchmark.markdown import render_benchmark_markdown
from benchmark.scoring import build_score, build_target_evaluation
from orchestrate.export_queue import export_queue
from runtime.run_state import RunStateError, read_json, write_json


SCHEMA_VERSION = "deck_benchmark_report.v1"


class BenchmarkReportError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except RunStateError:
        return {}


def _safe_load_any_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _minutes_between_iso(start: Any, end: Any) -> float | None:
    start_time = _parse_iso(start)
    end_time = _parse_iso(end)
    if not start_time or not end_time:
        return None
    minutes = (end_time - start_time).total_seconds() / 60
    return minutes if minutes >= 0 else None


def _checkpoint_timestamp(checkpoints_payload: dict[str, Any], checkpoint: str) -> str:
    checkpoints = checkpoints_payload.get("checkpoints", {})
    if not isinstance(checkpoints, dict):
        return ""
    entry = checkpoints.get(checkpoint, {})
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("timestamp") or "")


def _quality_reports(run_dir: Path) -> list[dict[str, Any]]:
    quality_dir = run_dir / "quality_reports"
    if not quality_dir.exists():
        return []
    reports = []
    for path in sorted(quality_dir.glob("*_gate.json")):
        payload = _safe_read_json(path)
        if payload:
            payload["_artifact_path"] = f"quality_reports/{path.name}"
            reports.append(payload)
    return reports


def _count_findings_by_severity(reports: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for report in reports:
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        if any(key in summary for key in ("p0_count", "p1_count", "p2_count")):
            counts["P0"] += int(summary.get("p0_count") or 0)
            counts["P1"] += int(summary.get("p1_count") or 0)
            counts["P2"] += int(summary.get("p2_count") or 0)
            continue
        for key in ("findings", "page_findings"):
            for finding in report.get(key, []):
                if not isinstance(finding, dict):
                    continue
                severity = str(finding.get("severity") or "").upper()
                if severity in counts:
                    counts[severity] += 1
    return counts


def _external_review_findings(reports: list[dict[str, Any]]) -> int:
    total = 0
    for report in reports:
        path = str(report.get("_artifact_path", ""))
        if "external_" not in path:
            continue
        for key in ("findings", "page_findings"):
            value = report.get(key, [])
            if isinstance(value, list):
                total += len([item for item in value if isinstance(item, dict)])
    return total


def _page_metrics(run_dir: Path, run_metrics: dict[str, Any]) -> dict[str, Any]:
    counts = run_metrics.get("counts", {}) if isinstance(run_metrics.get("counts"), dict) else {}
    pages = int(counts.get("pages") or 0)
    approved = int(counts.get("approved") or 0)
    rejected = int(counts.get("rejected") or 0)
    needs_review = int(counts.get("needs_review") or 0)
    if pages == 0:
        preview = _safe_read_json(run_dir / "preview_manifest.json")
        preview_pages = preview.get("pages", []) if isinstance(preview.get("pages"), list) else []
        pages = len(preview_pages)
        approved = sum(1 for page in preview_pages if isinstance(page, dict) and page.get("decision") == "approved")
        rejected = sum(1 for page in preview_pages if isinstance(page, dict) and page.get("decision") == "rejected")
        needs_review = max(pages - approved - rejected, 0)
    return {
        "pages": pages,
        "approved": approved,
        "rejected": rejected,
        "needs_review": needs_review,
        "page_acceptance_rate": round(approved / pages, 4) if pages else None,
    }


def _source_metrics(run_metrics: dict[str, Any]) -> dict[str, Any]:
    counts = run_metrics.get("counts", {}) if isinstance(run_metrics.get("counts"), dict) else {}
    pages = int(counts.get("pages") or 0)
    reuse = int(counts.get("reuse") or 0)
    adapt = int(counts.get("adapt") or 0)
    generate = int(counts.get("generate") or 0)
    manual_placeholder = int(counts.get("manual_placeholder") or 0)
    return {
        "reuse": reuse,
        "adapt": adapt,
        "generate": generate,
        "manual_placeholder": manual_placeholder,
        "reuse_adapt_rate": round((reuse + adapt) / pages, 4) if pages else None,
    }


def _generation_metrics(run_dir: Path) -> dict[str, Any]:
    tasks = _safe_read_json(run_dir / "generation_tasks" / "index.json")
    raw_tasks = tasks.get("tasks", []) if isinstance(tasks.get("tasks"), list) else []
    task_count = len(raw_tasks)
    completed = failed = partial = 0
    results_dir = run_dir / "generation_results"
    if results_dir.exists():
        for result_path in sorted(results_dir.glob("*.json")):
            result = _safe_read_json(result_path)
            status = str(result.get("status") or "")
            if status == "completed":
                completed += 1
            elif status == "failed":
                failed += 1
            elif status == "partial":
                partial += 1
    return {
        "task_count": task_count,
        "completed": completed,
        "failed": failed,
        "partial": partial,
        "generation_success_rate": round(completed / task_count, 4) if task_count else None,
    }


def _uat_summary(run_dir: Path) -> dict[str, str]:
    names = {
        "ppt_library": "ppt_library_uat.json",
        "generation_tool": "generation_tool_uat.json",
        "render_tool": "render_tool_uat.json",
        "real_workflow_smoke": "real_workflow_smoke.json",
    }
    summary: dict[str, str] = {}
    for key, filename in names.items():
        payload = _safe_read_json(run_dir / "uat_reports" / filename)
        summary[key] = str(payload.get("status") or "not_applicable") if payload else "not_applicable"
    return summary


def _artifact_index(run_dir: Path) -> dict[str, str]:
    candidates = {
        "request": "request.json",
        "context_manifest": "context_manifest.json",
        "deck_brief": "deck_brief.json",
        "claim_graph": "claim_evidence_graph.json",
        "preview_manifest": "preview_manifest.json",
        "quality_reports": "quality_reports/",
        "uat_reports": "uat_reports/",
        "run_metrics": "run_metrics.json",
        "benchmark_checkpoints": "benchmark_checkpoints.json",
        "benchmark_run_summary": "benchmark_run_summary.json",
    }
    index: dict[str, str] = {}
    for key, rel in candidates.items():
        path = run_dir / rel
        if path.exists():
            index[key] = str(path)
    return index


def _quality_metrics(run_dir: Path, reports: list[dict[str, Any]], export_payload: dict[str, Any]) -> dict[str, Any]:
    counts = _count_findings_by_severity(reports)
    claim_graph = _safe_read_json(run_dir / "claim_evidence_graph.json")
    gaps = claim_graph.get("gaps", []) if isinstance(claim_graph.get("gaps"), list) else []
    return {
        "p0": counts["P0"],
        "p1": counts["P1"],
        "p2": counts["P2"],
        "evidence_gap_count": len(gaps),
        "external_review_findings": _external_review_findings(reports),
        "export_blocked_count": int(export_payload.get("blocked_count") or 0),
        "quality_gate_present": bool(reports),
    }


def _efficiency_metrics(case: BenchmarkCase, run_metrics: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    durations = run_metrics.get("durations", {}) if isinstance(run_metrics.get("durations"), dict) else {}
    checkpoints = read_benchmark_checkpoints(run_dir)
    context_to_preview_minutes = calculate_checkpoint_duration_minutes(
        checkpoints, "context_ready", "preview_ready"
    )
    if context_to_preview_minutes is None:
        context_to_preview_minutes = durations.get("created_to_preview_minutes")
    context_to_review_ready_minutes = calculate_checkpoint_duration_minutes(
        checkpoints, "context_ready", "human_review_started"
    )
    if context_to_review_ready_minutes is None:
        context_to_review_ready_minutes = _minutes_between_iso(
            _checkpoint_timestamp(checkpoints, "context_ready"),
            run_metrics.get("first_quality_gate_at"),
        )
    context_to_approved_queue_minutes = calculate_checkpoint_duration_minutes(
        checkpoints, "context_ready", "approved_queue_ready"
    )
    human_review_minutes = calculate_human_review_minutes(checkpoints)
    baseline = float(case.data.get("inputs", {}).get("baseline_manual_hours") or 0)
    actual_hours = None
    if context_to_approved_queue_minutes is not None:
        actual_hours = float(context_to_approved_queue_minutes) / 60.0
    elif context_to_preview_minutes is not None:
        actual_hours = float(context_to_preview_minutes) / 60.0
    return {
        "baseline_manual_hours": baseline,
        "created_to_preview_minutes": durations.get("created_to_preview_minutes"),
        "context_to_preview_minutes": context_to_preview_minutes,
        "preview_to_first_quality_gate_minutes": durations.get("preview_to_first_quality_gate_minutes"),
        "context_to_review_ready_minutes": context_to_review_ready_minutes,
        "context_to_approved_queue_minutes": context_to_approved_queue_minutes,
        "human_review_minutes": human_review_minutes,
        "estimated_time_saved_hours": round(baseline - actual_hours, 2) if actual_hours is not None else None,
    }


def _recommendations(
    *,
    target_evaluation: dict[str, str],
    quality_metrics: dict[str, Any],
    pending_external_steps: list[dict[str, Any]],
) -> list[str]:
    items: list[str] = []
    if pending_external_steps:
        steps = ", ".join(step["step"] for step in pending_external_steps)
        items.append(f"Complete pending external workflow steps before using this case for RC readiness: {steps}.")
    if target_evaluation.get("page_acceptance_rate") in {"fail", "warning"}:
        items.append("Review rejected and needs_review pages, then rerun the benchmark report.")
    if quality_metrics.get("evidence_gap_count", 0):
        items.append("Close visible evidence gaps or lower unsupported claim strength.")
    if quality_metrics.get("p0", 0):
        items.append("Resolve P0 quality findings before any client-facing export.")
    if not items:
        items.append("Use this report as a local harness baseline and compare against the next run.")
    return items


def build_benchmark_report(
    case: BenchmarkCase,
    run_dir: str | Path,
    *,
    pending_external_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run_metrics = _safe_read_json(root / "run_metrics.json")
    if not run_metrics:
        from metrics.run_metrics import summarize_run_metrics

        run_metrics = summarize_run_metrics(root)
    try:
        export_payload = export_queue(root, {"approved"}, queue_type="client")
    except Exception:  # noqa: BLE001 - report should remain readable on partial runs.
        export_payload = {"pages": [], "blocked_pages": [], "blocked_count": 0}
    reports = _quality_reports(root)
    page_metrics = _page_metrics(root, run_metrics)
    source_metrics = _source_metrics(run_metrics)
    quality_metrics = _quality_metrics(root, reports, export_payload)
    generation_metrics = _generation_metrics(root)
    efficiency_metrics = _efficiency_metrics(case, run_metrics, root)
    uat_summary = _uat_summary(root)
    success_targets = case.data.get("success_targets", {}) if isinstance(case.data.get("success_targets"), dict) else {}
    target_evaluation = build_target_evaluation(
        success_targets,
        efficiency_metrics=efficiency_metrics,
        page_metrics=page_metrics,
        source_metrics=source_metrics,
        quality_metrics=quality_metrics,
    )
    weights = case.data.get("scoring", {}).get("weights") if isinstance(case.data.get("scoring"), dict) else None
    score = build_score(target_evaluation, weights)
    if pending_external_steps is None:
        summary = _safe_read_json(root / "benchmark_run_summary.json")
        raw_pending = summary.get("pending_external_steps", [])
        pending = [item for item in raw_pending if isinstance(item, dict)] if isinstance(raw_pending, list) else []
    else:
        pending = pending_external_steps
    status = "completed"
    if pending:
        status = "pending_external_agent"
    elif any(value == "fail" for value in target_evaluation.values()):
        status = "warning"
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.data["case_id"],
        "run_id": root.name,
        "created_at": _utc_now(),
        "status": status,
        "case": {
            "case_name": case.data.get("case_name", ""),
            "industry": case.data.get("industry", ""),
            "audience": case.data.get("audience", ""),
            "target_pages": case.data.get("target_pages"),
        },
        "readiness": {
            "overall": "needs_review" if status != "completed" else "report_ready",
            "export_ready": bool(export_payload.get("pages")),
            "quality_blocked": bool(export_payload.get("blocked_count")),
        },
        "efficiency_metrics": efficiency_metrics,
        "page_metrics": page_metrics,
        "source_metrics": source_metrics,
        "quality_metrics": quality_metrics,
        "generation_metrics": generation_metrics,
        "uat_summary": uat_summary,
        "target_evaluation": target_evaluation,
        "score": score,
        "pending_external_steps": pending,
        "recommendations": _recommendations(
            target_evaluation=target_evaluation,
            quality_metrics=quality_metrics,
            pending_external_steps=pending,
        ),
        "artifact_index": _artifact_index(root),
    }


def result_dir_for(case: BenchmarkCase, run_dir: str | Path, benchmark_dir: str | Path | None = None) -> Path:
    base = Path(benchmark_dir).expanduser().resolve() if benchmark_dir else case.benchmark_dir
    if base is None:
        base = Path("benchmarks").resolve()
    return base / "results" / str(case.data["case_id"]) / Path(run_dir).expanduser().resolve().name


def write_benchmark_report(
    case: BenchmarkCase,
    run_dir: str | Path,
    *,
    benchmark_dir: str | Path | None = None,
    force: bool = False,
    pending_external_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = build_benchmark_report(case, run_dir, pending_external_steps=pending_external_steps)
    out_dir = result_dir_for(case, run_dir, benchmark_dir)
    json_path = out_dir / "benchmark_report.json"
    markdown_path = out_dir / "benchmark_report.md"
    if not force and (json_path.exists() or markdown_path.exists()):
        raise BenchmarkReportError(f"Benchmark report already exists: {out_dir}. Use --force to overwrite.")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(json_path, report)
    markdown_path.write_text(render_benchmark_markdown(report), encoding="utf-8")
    run_root = Path(run_dir).expanduser().resolve()
    for name in ("run_metrics.json",):
        src = run_root / name
        if src.exists():
            (out_dir / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    uat = report.get("uat_summary", {})
    write_json(out_dir / "uat_summary.json", {"schema_version": "deck_benchmark_uat_summary.v1", "summary": uat})
    write_json(
        out_dir / "artifact_index.json",
        {"schema_version": "deck_benchmark_artifact_index.v1", "artifact_index": report.get("artifact_index", {})},
    )
    return {
        "status": report["status"],
        "case_id": report["case_id"],
        "run_id": report["run_id"],
        "report": str(json_path),
        "markdown": str(markdown_path),
        "result_dir": str(out_dir),
    }
