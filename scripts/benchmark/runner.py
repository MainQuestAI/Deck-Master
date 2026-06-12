from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark.case import BenchmarkCase, BenchmarkCaseError
from benchmark.checkpoints import write_benchmark_checkpoint
from conversation.session_builder import build_conversation_session
from context_intake.context_pack import import_context_pack
from metrics.run_metrics import summarize_run_metrics
from runtime.events import append_typed_event
from runtime.run_state import (
    CONTEXT_MANIFEST_NAME,
    CONVERSATION_SESSION_NAME,
    DECK_BRIEF_NAME,
    RunStateError,
    create_run,
    ensure_run_dirs,
    load_request,
    read_json,
    write_artifact,
    write_json,
)


class BenchmarkRunError(ValueError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def default_run_id(case: BenchmarkCase) -> str:
    return f"bench-{case.data['case_id']}-{utc_stamp()}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchmarkRunError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkRunError(f"Bad JSON in {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkRunError(f"JSON file must contain an object: {path}")
    return payload


def _context_pack_for_run(case: BenchmarkCase, run_id: str) -> dict[str, Any]:
    context_path = case.resolved_paths.get("context_pack")
    if not context_path:
        raise BenchmarkRunError("Benchmark case inputs.context_pack is required for benchmark-run.")
    pack = _read_json(context_path)
    pack["run_id"] = run_id
    return pack


def _brief_from_case(case: BenchmarkCase, pack: dict[str, Any]) -> str:
    source_summaries = []
    for source in pack.get("sources", []):
        if isinstance(source, dict) and source.get("summary"):
            source_summaries.append(str(source["summary"]))
    parts = [
        str(case.data.get("case_name") or case.data["case_id"]),
        str(case.data.get("description") or ""),
        " ".join(source_summaries),
    ]
    return "\n".join(part for part in parts if part.strip())


def create_benchmark_run(
    case: BenchmarkCase,
    *,
    run_id: str | None = None,
    force: bool = False,
) -> tuple[Path, dict[str, Any]]:
    actual_run_id = run_id or default_run_id(case)
    runs_dir = case.resolved_paths.get("runs_dir")
    if runs_dir is None:
        raise BenchmarkCaseError("Benchmark case runs_dir could not be resolved.")

    pack = _context_pack_for_run(case, actual_run_id)
    request = {
        "run_id": actual_run_id,
        "project_name": str(case.data.get("case_name") or case.data["case_id"]),
        "industry": str(case.data.get("industry") or ""),
        "audience": str(case.data.get("audience") or "client"),
        "business_goal": _brief_from_case(case, pack),
        "brief": _brief_from_case(case, pack),
        "target_pages": str(case.data.get("target_pages") or "auto"),
        "workspace": str(case.resolved_paths.get("workspace") or ""),
        "source": "benchmark_case",
        "benchmark_case_id": case.data["case_id"],
    }
    run_dir = create_run(runs_dir, request, run_id=actual_run_id, force=force)
    import_context_pack(run_dir, pack, merge=True)
    request = load_request(run_dir)
    context_manifest = read_json(run_dir / CONTEXT_MANIFEST_NAME)
    conversation = build_conversation_session(request, context_manifest)
    write_artifact(run_dir, CONVERSATION_SESSION_NAME, conversation, action="conversation.session.created")
    write_benchmark_checkpoint(run_dir, "context_ready", note="Context pack imported for benchmark run.")
    append_typed_event(
        run_dir,
        "step_completed",
        "benchmark.run.created",
        "Benchmark run created from benchmark case.",
        run_id=actual_run_id,
        refs=["request.json", "context_manifest.json"],
        payload={"case_id": case.data["case_id"], "case_path": str(case.path)},
    )
    return run_dir, pack


def run_local_preview_pipeline(
    case: BenchmarkCase,
    run_dir: Path,
    *,
    command_funcs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run the local, provider-free Deck Master steps used by semi-auto benchmark."""
    steps: list[dict[str, Any]] = []
    args = type("BenchmarkArgs", (), {})()
    args.run_dir = str(run_dir)
    args.run_id = None
    args.runs_dir = str(case.resolved_paths.get("runs_dir") or run_dir.parent)
    args.brief = None
    args.brief_file = None
    args.library_mode = str(case.data.get("workflow", {}).get("library_mode") or "fixture")
    args.ppt_lib_command = "ppt-lib"
    args.planning_mode = str(case.data.get("workflow", {}).get("planning_mode") or "classic")
    args.gate = "draft_v2"
    args.artifact = None
    args.expected_pages = None
    args.forbidden = []

    for name in ("build_brief", "build_claim_map", "autoplan", "quality_gate"):
        try:
            result = command_funcs[name](args)
            steps.append({"step": name, "status": "completed", "result": result})
        except Exception as exc:  # noqa: BLE001 - benchmark report should capture partial local runs.
            steps.append({"step": name, "status": "warning", "error": str(exc)})
            break

    write_benchmark_checkpoint(run_dir, "preview_ready", note="Semi-auto benchmark local preview pipeline attempted.")
    return steps


def summarize_and_write_metrics(run_dir: Path) -> dict[str, Any]:
    metrics = summarize_run_metrics(run_dir)
    write_json(run_dir / "run_metrics.json", metrics)
    return metrics


def collect_pending_external_steps(case: BenchmarkCase, run_dir: Path) -> list[dict[str, Any]]:
    workflow = case.data.get("workflow", {}) if isinstance(case.data.get("workflow"), dict) else {}
    checks = [
        ("requires_narrative_advice", "narrative_advice", run_dir / "narrative_advice" / "applied.json", None),
        ("requires_external_quality_review", "external_quality_review", run_dir / "quality_reports", "external_*_gate.json"),
        ("requires_generation_result", "generation_result", run_dir / "generation_results", "*.json"),
        ("requires_render_result", "render_result", run_dir / "render_result.json", None),
    ]
    pending: list[dict[str, Any]] = []
    for flag, step, path, pattern in checks:
        if not workflow.get(flag):
            continue
        if pattern and path.is_dir():
            exists = any(path.glob(pattern))
        else:
            exists = path.exists() and (not path.is_dir() or any(path.iterdir()))
        if not exists:
            pending.append({"step": step, "status": "pending_external_agent", "path": str(path)})
    return pending


def write_benchmark_run_summary(
    run_dir: Path,
    case: BenchmarkCase,
    *,
    pipeline_steps: list[dict[str, Any]],
    pending_external_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_run_dirs(run_dir)
    payload = {
        "schema_version": "deck_benchmark_run_summary.v1",
        "run_id": load_request(run_dir).get("run_id", run_dir.name),
        "case_id": case.data["case_id"],
        "case_path": str(case.path),
        "pipeline_steps": pipeline_steps,
        "pending_external_steps": pending_external_steps,
    }
    write_artifact(run_dir, "benchmark_run_summary.json", payload, action="benchmark.run.summary.created")
    return payload
