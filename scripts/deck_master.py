from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from context_intake.local_sources import build_context_manifest
from context_intake.context_pack import (
    ContextPackError,
    create_run_from_context_pack,
    import_context_pack,
    validate_context_pack,
)
from advisory.narrative import (
    NarrativeAdviceError,
    apply_narrative_advice,
    import_narrative_advice,
    prepare_narrative_advice_task,
)
from quality.external_review import (
    ExternalReviewError,
    import_external_review,
    import_quality_findings,
    prepare_quality_review,
)
from generation.handback import (
    GenerationHandbackError,
    import_generation_result,
    normalize_generation_result,
    prepare_generation_handoff,
    refresh_preview_from_generation,
    validate_generation_result,
)
from generation.session import (
    GenerationSessionError,
    create_generation_session,
    generation_session_status,
    import_generation_results,
    run_generation as run_generation_session,
    validate_generation_session,
)
from learning.pack import build_learning_pack, show_learning_pack
from validators.companion_tools import validate_ppt_library_result, validate_render_result
from metrics.run_metrics import summarize_run_metrics
from uat.generation_tool import run_generation_tool_uat
from uat.ppt_library import run_ppt_library_uat
from uat.real_workflow_smoke import run_real_workflow_smoke
from uat.render_tool import run_render_tool_uat
from benchmark.case import BenchmarkCaseError, load_benchmark_case
from benchmark.aggregate import BenchmarkAggregateError, write_benchmark_aggregate_report
from benchmark.checkpoints import BenchmarkCheckpointError, write_benchmark_checkpoint
from benchmark.report import BenchmarkReportError, write_benchmark_report, write_benchmark_rc_report
from benchmark.runner import (
    BenchmarkRunError,
    collect_pending_external_steps,
    create_benchmark_run,
    run_local_preview_pipeline,
    summarize_and_write_metrics,
    write_benchmark_run_summary,
)
from conversation.brief_compiler import compile_deck_brief
from conversation.session_builder import build_conversation_session
from generation.task_builder import create_generation_tasks
from orchestrate.export_queue import export_queue
from orchestrate.preview_builder import build_preview_from_sourcing
from narrative.claim_graph import build_claim_evidence_graph
from narrative.judgment_builder import build_judgments
from planning.brief_intake import build_request
from planning.claim_map import build_claim_map
from planning.narrative_planner import plan_narrative
from planning.page_tasks import build_page_tasks
from planning.sourcing_decider import decide_sourcing, load_library_results
from quality.gate_runner import (
    evaluate_delivery_gate,
    evaluate_draft_gate,
    evaluate_render_gate,
    write_gate_report,
)
from quality.customer_visible_safety import (
    evaluate_customer_visible_safety_gate,
    load_customer_visible_forbidden_terms,
)
from quality.draft_gate_v2 import evaluate_draft_gate_v2
from quality.evidence_gate import evaluate_evidence_gate
from quality.context_conflict_gate import evaluate_context_conflict_gate
from quality.confidentiality_gate import evaluate_confidentiality_gate
from quality.brand_gate import evaluate_brand_gate
from quality.overrides import create_override, list_active_overrides, revoke_override
from delivery.validate import validate_delivery
from delivery.outcome import record_delivery_outcome
from feedback.library_feedback import LibraryFeedbackError, record_library_feedback
from team.opportunity import create_opportunity, attach_run
from team.approval import submit_approval, approve, reject
from connectors.import_contract import validate_import_manifest, import_to_context_manifest
from skills.installer import (
    SkillInstallError,
    backend_bind,
    backend_status,
    backend_unbind,
    backend_verify,
    build_release_tree,
    install_release_tree,
    install_skill,
    rollback_release_tree,
    inspect_suite_status,
    verify_release_tree,
    product_capability_manifest,
    suite_install,
    suite_migration_apply,
    suite_migration_plan,
    suite_migration_rollback,
    suite_repair,
    validate_product_capability_manifest,
    validate_skill,
    uninstall_skill,
)
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    CONVERSATION_SESSION_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    REQUEST_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    create_run,
    load_request,
    read_json,
    write_artifact,
    write_json,
)
from runtime.next_step import resolve_next_step
from runtime.skill_route import route_for_input_type, route_for_stage
from runtime.import_log import append_import_log
from runtime.orchestration import import_plan, import_render_result, orchestration_check
from runtime.build import build_status, prepare_build, run_build
from runtime.render import render_fixture_html, render_status
from runtime.final_readiness import compute_final_readiness
from runtime.rc_gate import RCGateError, write_rc_gate_report
from runtime.run_state_resolver import resolve_run_state, resolve_runtime_stage
from runtime.sourcing_import import import_sourcing, validate_sourcing
from runtime.workspace_binding import bind_workspace
from runtime.workspace_resolver import resolve_workspace_for_run
from workflow import resolve_workflow_state
from workflow.handoff import HandoffError, HandoffRuntime
from workflow.approval import ApprovalError, ApprovalRuntime
from workflow.policy import PolicyError, PreauthorizationRuntime, transition_key
from runtime.skill_route import route_for_skill_name, route_for_stage_manifest_aware
from tools.ppt_library_client import PPTLibraryClientError, import_library_selection, run_library_selection
from workspace.foundation import MANIFEST_NAME, WorkspaceError, init_workspace, register_workspace, validate_workspace
from workspace.project_init import init_deck_project
from runtime.setup_status import SetupError, configured_runs_dir, require_setup_ready, run_setup, setup_status


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_COMMANDS = {
    "plan",
    "start-conversation",
    "build-brief",
    "build-claim-map",
    "autoplan",
    "search-library",
    "import-library-selection",
    "decide-sourcing",
    "create-generation-tasks",
    "build-preview",
    "export",
    "quality-gate",
    "import-sourcing",
    "validate-sourcing",
    "override",
    "opportunity",
    "approval",
    "build-judgments",
    "build-claim-graph",
    "import-context-pack",
    "create-run-from-context-pack",
    "prepare-narrative-advice",
    "import-narrative-advice",
    "apply-narrative-advice",
    "prepare-quality-review",
    "import-quality-review",
    "import-quality-findings",
    "prepare-generation-handoff",
    "import-generation-result",
    "refresh-preview-from-generation",
    "render",
    "import-plan",
    "import-render-result",
    "summarize-run-metrics",
    "uat-ppt-library",
    "uat-generation-tool",
    "uat-render-tool",
    "smoke-real-workflow",
    "benchmark-run",
    "benchmark-report",
    "benchmark-rc-report",
    "benchmark-checkpoint",
    "delivery",
    "generation-session",
    "run-generation",
    "record-library-feedback",
    "workflow-autopilot",
    "autopilot-v1",
}


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _agent_evidence_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        resolved = candidate.expanduser().resolve()
        return str(resolved.relative_to(ROOT))
    except (OSError, ValueError):
        return str(path)


def _unique_strings(items: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _add_agent_output_contract(
    payload: dict[str, Any],
    *,
    next_agent_action: str,
    evidence_paths: list[str | Path],
) -> dict[str, Any]:
    payload.setdefault("next_agent_action", next_agent_action)
    payload.setdefault("evidence_paths", _unique_strings([_agent_evidence_path(path) for path in evidence_paths]))
    return payload


def _blocked_next_agent_action(payload: dict[str, Any], fallback: str) -> str:
    blockers = payload.get("blockers")
    if isinstance(blockers, list):
        for blocker in blockers:
            if isinstance(blocker, dict) and blocker.get("message"):
                return str(blocker["message"])
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        return fallback
    return fallback


def runs_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "runs_dir", None):
        return Path(args.runs_dir).expanduser().resolve()
    return configured_runs_dir(ROOT / "runs")


def resolve_run_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "run_dir", None):
        return Path(args.run_dir).expanduser().resolve()
    if getattr(args, "run_id", None):
        return runs_dir(args) / args.run_id
    raise RunStateError("--run-dir or --run-id is required.")


def artifact_exists(run_dir: Path, filename: str) -> bool:
    return (run_dir / filename).exists()


def read_optional_json(run_dir: Path, filename: str) -> dict[str, Any] | None:
    path = run_dir / filename
    if not path.exists():
        return None
    return read_json(path)


def _workspace_for_setup_guard(args: argparse.Namespace) -> str | None:
    if getattr(args, "workspace", None):
        return str(args.workspace)
    if getattr(args, "run_dir", None):
        request_path = Path(args.run_dir).expanduser().resolve() / "request.json"
        if request_path.exists():
            try:
                request = read_json(request_path)
                return str(request.get("workspace") or "") or None
            except RunStateError:
                return None
    return None


def _normalize_run_mode(value: str | None) -> str:
    mode = (value or "production").strip().lower()
    if mode in {"production", "fixture", "dev", "benchmark"}:
        return mode
    return "production"


def _dev_allow_unsetup(args: argparse.Namespace) -> bool:
    if bool(getattr(args, "dev_allow_unsetup", False)):
        return True
    return os.environ.get("DECK_MASTER_DEV_SKIP_SETUP") == "1"


def _normalize_planner_mode(value: str | None, run_mode: str) -> str:
    if value in {"fixture_template", "workspace_fallback", "production_narrative"}:
        return value
    if run_mode == "fixture":
        return "fixture_template"
    return "production_narrative"


def _workspace_id_for_path(path: str) -> str:
    workspace_root = Path(path).expanduser().resolve()
    manifest_path = workspace_root / MANIFEST_NAME
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            candidate = str(manifest.get("workspace_id") or "").strip()
            if candidate:
                return candidate
        except Exception:
            pass
    return f"workspace_{workspace_root.name}"


def _apply_workspace_runtime_fields(
    request: dict[str, Any],
    args: argparse.Namespace,
    *,
    run_mode: str,
) -> dict[str, Any]:
    resolution = resolve_workspace_for_run(
        run_dir=getattr(args, "run_dir", None) or getattr(args, "runs_dir", None) or ".",
        request=request,
        cli_workspace=getattr(args, "workspace", None) or None,
        run_mode=run_mode,
        allow_dev_bypass=_dev_allow_unsetup(args),
    )
    if resolution.get("blocked"):
        reasons = "; ".join(str(reason) for reason in resolution.get("reasons", []) if reason)
        raise RunStateError(reasons or "workspace resolution blocked")
    workspace_path = str(resolution.get("resolved_workspace") or "").strip()
    if workspace_path:
        request["workspace"] = workspace_path
        request["workspace_id"] = _workspace_id_for_path(workspace_path)
        request["workspace_manifest_ref"] = MANIFEST_NAME
        request["workspace_resolved_from"] = str(resolution.get("resolved_from") or "")
    return request


def _resolve_workspace_for_setup_status(args: argparse.Namespace) -> str | None:
    if getattr(args, "workspace", None):
        return str(args.workspace)
    if getattr(args, "run_dir", None) or getattr(args, "run_id", None):
        try:
            run_dir = resolve_run_dir(args)
        except RunStateError:
            return None
        request_path = run_dir / "request.json"
        if request_path.exists():
            try:
                request = read_json(request_path)
                return str(request.get("workspace") or "") or None
            except RunStateError:
                return None
    return None


def _start_orchestration_summary(run_dir: Path, state: dict[str, Any]) -> dict[str, Any]:
    required = [
        REQUEST_NAME,
        CONTEXT_MANIFEST_NAME,
        DECK_BRIEF_NAME,
        CLAIM_MAP_NAME,
        NARRATIVE_PLAN_NAME,
        PAGE_TASKS_NAME,
        SOURCING_PLAN_NAME,
        "preview_manifest.json",
    ]
    stage = str(state.get("stage") or "")
    return {
        "status": "ready_for_external_production"
        if stage in {"ready_for_client_export", "ready_for_benchmark"}
        else ("needs_quality_gate" if stage == "needs_draft_gate" else "blocked"),
        "missing_artifacts": [name for name in required if not (run_dir / name).exists()],
        "allow_external_production": stage in {"ready_for_client_export", "ready_for_benchmark"},
        "next_command": state.get("next_command", ""),
    }


def _load_workspace_archetypes(request: dict[str, Any]) -> dict[str, Any] | None:
    workspace = request.get("workspace")
    if not workspace:
        return None
    workspace_dir = Path(str(workspace)).expanduser().resolve()
    json_path = workspace_dir / "structure-assets" / "page_archetypes.json"
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    md_path = workspace_dir / "structure-assets" / "page_archetypes.md"
    if not md_path.exists():
        return None
    roles = [
        "opener",
        "problem",
        "solution",
        "architecture",
        "case",
        "roi",
        "cta",
        "appendix",
    ]
    return {
        "archetypes": [
            {"role": role, "ref": f"structure-assets/page_archetypes.md#{role}"}
            for role in roles
        ]
    }


def _build_judgments_if_possible(
    run_dir: Path,
    request: dict[str, Any],
    claim_map: dict[str, Any] | None,
) -> dict[str, Any] | None:
    deck_brief = read_optional_json(run_dir, DECK_BRIEF_NAME)
    if not deck_brief or not claim_map:
        return None
    context_manifest = read_optional_json(run_dir, CONTEXT_MANIFEST_NAME) or {}
    judgments = build_judgments(request, deck_brief, claim_map, context_manifest)
    write_artifact(run_dir, "consulting_judgments.json", judgments, action="judgments.created")
    return judgments


def _build_claim_graph_if_possible(
    run_dir: Path,
    claim_map: dict[str, Any] | None,
    page_tasks: dict[str, Any],
    judgments: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not claim_map:
        return None
    context_manifest = read_optional_json(run_dir, CONTEXT_MANIFEST_NAME) or {}
    graph = build_claim_evidence_graph(claim_map, page_tasks, context_manifest, judgments)
    write_artifact(run_dir, "claim_evidence_graph.json", graph, action="claim_evidence_graph.created")
    return graph


def write_plan_artifacts(
    run_dir: Path,
    request: dict[str, Any],
    *,
    planning_mode: str = "classic",
    planner_mode: str = "production_narrative",
) -> dict[str, Any]:
    claim_map = read_optional_json(run_dir, CLAIM_MAP_NAME)
    judgments: dict[str, Any] | None = None
    claim_graph: dict[str, Any] | None = None
    workspace_archetypes: dict[str, Any] | None = None

    run_mode = str(request.get("run_mode") or "production").strip().lower()
    if planner_mode == "production_narrative" and run_mode == "production" and not claim_map:
        raise RunStateError(
            "planner blocked: run_mode=production requires claim_map for production_narrative planner"
        )

    if planning_mode == "narrative_v2":
        judgments = _build_judgments_if_possible(run_dir, request, claim_map)
        workspace_archetypes = _load_workspace_archetypes(request)

    narrative_plan = plan_narrative(
        request,
        judgments=judgments,
        claim_graph=claim_graph,
        workspace_archetypes=workspace_archetypes,
        planner_mode=planner_mode,
    )
    if claim_map:
        enrich_narrative_with_claims(narrative_plan, claim_map)
    page_tasks = build_page_tasks(
        narrative_plan,
        claim_map,
        claim_graph=claim_graph,
        judgments=judgments,
    )

    if planning_mode == "narrative_v2":
        claim_graph = _build_claim_graph_if_possible(run_dir, claim_map, page_tasks, judgments)
        narrative_plan = plan_narrative(
            request,
            judgments=judgments,
            claim_graph=claim_graph,
            workspace_archetypes=workspace_archetypes,
            planner_mode=planner_mode,
        )
        if claim_map:
            enrich_narrative_with_claims(narrative_plan, claim_map)
        page_tasks = build_page_tasks(
            narrative_plan,
            claim_map,
            claim_graph=claim_graph,
            judgments=judgments,
        )
        _build_claim_graph_if_possible(run_dir, claim_map, page_tasks, judgments)

    write_artifact(run_dir, NARRATIVE_PLAN_NAME, narrative_plan, action="narrative.plan.created")
    write_artifact(run_dir, PAGE_TASKS_NAME, page_tasks, action="page_tasks.created")
    return narrative_plan


def enrich_narrative_with_claims(narrative_plan: dict[str, Any], claim_map: dict[str, Any]) -> None:
    claims = [claim for claim in claim_map.get("claims", []) if isinstance(claim, dict)]
    if not claims:
        return
    for index, beat in enumerate(narrative_plan.get("beats", [])):
        if not isinstance(beat, dict):
            continue
        claim = claims[index % len(claims)]
        claim_text = str(claim.get("claim") or "").strip()
        if not claim_text:
            continue
        beat["core_claim"] = claim_text
        beat["reuse_query"] = f"{beat.get('reuse_query', '')} {claim_text}".strip()
        beat["generation_brief"] = f"{beat.get('generation_brief', '')} 核心论点：{claim_text}"
        if claim.get("risk_flags"):
            beat["claim_risk_flags"] = claim.get("risk_flags", [])


def command_plan(args: argparse.Namespace) -> dict[str, Any]:
    run_mode = _normalize_run_mode(getattr(args, "run_mode", None))
    planner_mode = _normalize_planner_mode(getattr(args, "planner_mode", None), run_mode)
    request = build_request(
        brief=args.brief or "",
        brief_file=args.brief_file,
        industry=args.industry or "",
        target_pages=args.target_pages,
        audience=args.audience,
        style_preference=args.style_preference or "",
        run_id=args.run_id or "",
    )
    request["run_mode"] = run_mode
    request = _apply_workspace_runtime_fields(request, args, run_mode=run_mode)
    run_dir = create_run(runs_dir(args), request, run_id=args.run_id or None, force=args.force)
    request = load_request(run_dir)
    narrative_plan = write_plan_artifacts(
        run_dir,
        request,
        planning_mode=getattr(args, "planning_mode", "classic"),
        planner_mode=planner_mode,
    )
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "planned", "pages": len(narrative_plan["beats"])}


def command_start_conversation(args: argparse.Namespace) -> dict[str, Any]:
    run_mode = _normalize_run_mode(getattr(args, "run_mode", None))
    context_files = [str(path) for path in args.context_file]
    context_manifest = build_context_manifest(context_files, workspace=args.workspace or "")
    request = build_request(
        brief=args.brief or str(context_manifest.get("summary") or ""),
        industry=args.industry or "",
        target_pages=args.target_pages,
        audience=args.audience,
        style_preference=args.style_preference or "",
        run_id=args.run_id or "",
    )
    request["run_mode"] = run_mode
    request = _apply_workspace_runtime_fields(request, args, run_mode=run_mode)
    context_manifest["workspace"] = str(request.get("workspace") or "")
    run_dir = create_run(runs_dir(args), request, run_id=args.run_id or None, force=args.force)
    request = load_request(run_dir)
    context_manifest["run_id"] = request["run_id"]
    write_artifact(run_dir, CONTEXT_MANIFEST_NAME, context_manifest, action="context.manifest.created")
    conversation = build_conversation_session(request, context_manifest)
    write_artifact(run_dir, CONVERSATION_SESSION_NAME, conversation, action="conversation.session.created")
    return {
        "run_id": request["run_id"],
        "run_dir": str(run_dir),
        "status": "conversation_started",
        "sources": len(context_manifest["sources"]),
    }


def command_build_brief(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    request = load_request(run_dir)
    context_manifest = read_json(run_dir / CONTEXT_MANIFEST_NAME)
    conversation = read_json(run_dir / CONVERSATION_SESSION_NAME)
    deck_brief = compile_deck_brief(request, context_manifest, conversation)
    write_artifact(run_dir, DECK_BRIEF_NAME, deck_brief, action="deck_brief.created")
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "brief_ready", "core_points": len(deck_brief["core_points"])}


def command_build_claim_map(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    deck_brief = read_json(run_dir / DECK_BRIEF_NAME)
    context_manifest = read_json(run_dir / CONTEXT_MANIFEST_NAME)
    claim_map = build_claim_map(deck_brief, context_manifest)
    write_artifact(run_dir, CLAIM_MAP_NAME, claim_map, action="claim_map.created")
    if artifact_exists(run_dir, NARRATIVE_PLAN_NAME):
        narrative_plan = read_json(run_dir / NARRATIVE_PLAN_NAME)
        page_tasks = build_page_tasks(narrative_plan, claim_map)
        write_artifact(run_dir, PAGE_TASKS_NAME, page_tasks, action="page_tasks.created")
    return {"run_id": deck_brief.get("run_id", run_dir.name), "run_dir": str(run_dir), "status": "claim_map_ready", "claims": len(claim_map["claims"])}


def command_search_library(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    request = load_request(run_dir)
    narrative_plan_path = run_dir / NARRATIVE_PLAN_NAME
    narrative_plan = read_json(narrative_plan_path)
    results = run_library_selection(
        narrative_plan=narrative_plan,
        narrative_plan_path=narrative_plan_path,
        request=request,
        run_dir=run_dir,
        mode=args.library_mode,
        command=args.ppt_lib_command,
        allow_fixture_fallback=bool(getattr(args, "allow_fixture_library_fallback", False)),
    )
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "library_ready", "source": results.get("source", "")}


def command_library_status(args: argparse.Namespace) -> dict[str, Any]:
    suite = inspect_suite_status(targets=["codex"], include_optional=True)
    library_items = [item for item in suite.get("skills", []) if item.get("skill") == "ppt-library"]
    workspace = getattr(args, "workspace", "") or ""
    return {
        "schema_version": "deck_master_library_status.v1",
        "status": "ready" if any(item.get("status") == "ready" for item in library_items) else "blocked",
        "workspace": str(Path(workspace).expanduser().resolve()) if workspace else "",
        "suite_status": suite.get("status"),
        "ppt_library": library_items,
        "next_command": "" if any(item.get("status") == "ready" for item in library_items) else "deck-master suite-repair --target codex",
    }


def command_import_library_selection(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return import_library_selection(run_dir, Path(args.input).expanduser())


def command_decide_sourcing(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    narrative_plan = read_json(run_dir / NARRATIVE_PLAN_NAME)
    library_results = load_library_results(run_dir)
    sourcing_plan = decide_sourcing(narrative_plan, library_results)
    write_artifact(run_dir, SOURCING_PLAN_NAME, sourcing_plan, action="sourcing.plan.created")
    return {
        "run_id": sourcing_plan.get("run_id", run_dir.name),
        "run_dir": str(run_dir),
        "status": "sourcing_ready",
        "decisions": len(sourcing_plan["decisions"]),
    }


def command_create_generation_tasks(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    sourcing_plan = read_json(run_dir / SOURCING_PLAN_NAME)
    tasks = create_generation_tasks(sourcing_plan, run_dir)
    return {"run_id": sourcing_plan.get("run_id", run_dir.name), "run_dir": str(run_dir), "status": "generation_tasks_ready", "tasks": len(tasks["tasks"])}


def command_build_preview(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    sourcing_plan = read_json(run_dir / SOURCING_PLAN_NAME)
    generation_tasks_path = run_dir / "generation_tasks" / "index.json"
    generation_tasks = read_json(generation_tasks_path) if generation_tasks_path.exists() else None
    manifest = build_preview_from_sourcing(sourcing_plan, run_dir, generation_tasks)
    return {"run_id": manifest["run_id"], "run_dir": str(run_dir), "status": "preview_ready", "pages": len(manifest["pages"])}


def command_export(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    queue_type = getattr(args, "queue_type", "client")
    final_readiness = {}
    if queue_type == "client":
        final_readiness = compute_final_readiness(
            run_dir,
            run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
    queue = export_queue(
        run_dir,
        set(args.decision),
        queue_type=queue_type,
        allow_quality_override=getattr(args, "allow_quality_override", False),
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
    else:
        output = run_dir / "approved_queue.json"
    write_json(output, queue)
    return {
        "run_id": queue["run_id"],
        "run_dir": str(run_dir),
        "status": "exported" if queue["pages"] else "blocked",
        "output": str(output),
        "pages": len(queue["pages"]),
        "blocked": queue["blocked_count"],
        "final_readiness": final_readiness or queue.get("final_readiness", {}),
    }


def command_autoplan(args: argparse.Namespace) -> dict[str, Any]:
    existing_run = bool((getattr(args, "run_id", None) or getattr(args, "run_dir", None)) and not (args.brief or args.brief_file))
    planning_mode = getattr(args, "planning_mode", "classic")
    run_mode = _normalize_run_mode(getattr(args, "run_mode", None))
    planner_mode = _normalize_planner_mode(getattr(args, "planner_mode", None), run_mode)
    if existing_run:
        run_dir = resolve_run_dir(args)
        request = load_request(run_dir)
        request = _apply_workspace_runtime_fields(request, args, run_mode=str(request.get("run_mode") or run_mode))
        write_json(run_dir / REQUEST_NAME, request)
        needs_plan = not artifact_exists(run_dir, NARRATIVE_PLAN_NAME)
        needs_v2_artifacts = planning_mode == "narrative_v2" and (
            not artifact_exists(run_dir, "consulting_judgments.json")
            or not artifact_exists(run_dir, "claim_evidence_graph.json")
        )
        if needs_plan or needs_v2_artifacts:
            write_plan_artifacts(run_dir, request, planning_mode=planning_mode, planner_mode=planner_mode)
    else:
        plan_result = command_plan(args)
        run_dir = Path(plan_result["run_dir"])
    args.run_dir = str(run_dir)
    command_search_library(args)
    command_decide_sourcing(args)
    command_create_generation_tasks(args)
    preview_result = command_build_preview(args)
    return preview_result | {"status": "autoplan_preview_ready"}


def command_quality_gate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    request = load_request(run_dir)
    run_id = request.get("run_id", run_dir.name)
    expected_pages = args.expected_pages
    if expected_pages is None:
        preview_manifest = read_optional_json(run_dir, "preview_manifest.json")
        if preview_manifest and isinstance(preview_manifest.get("pages"), list):
            expected_pages = len(preview_manifest["pages"])

    if args.gate == "draft":
        deck_brief = read_optional_json(run_dir, DECK_BRIEF_NAME) or {
            "run_id": run_id,
            "project_name": request.get("project_name", run_dir.name),
            "business_goal": request.get("business_goal", ""),
        }
        claim_map = read_optional_json(run_dir, CLAIM_MAP_NAME) or {"run_id": run_id, "claims": [], "risk_flags": ["missing_claim_map"]}
        page_tasks = read_optional_json(run_dir, PAGE_TASKS_NAME) or {"run_id": run_id, "tasks": []}
        report = evaluate_draft_gate(deck_brief, claim_map, page_tasks)
    elif args.gate == "draft_v2":
        deck_brief = read_optional_json(run_dir, DECK_BRIEF_NAME) or {
            "run_id": run_id,
            "project_name": request.get("project_name", run_dir.name),
            "business_goal": request.get("business_goal", ""),
        }
        claim_map = read_optional_json(run_dir, CLAIM_MAP_NAME) or {"run_id": run_id, "claims": [], "risk_flags": ["missing_claim_map"]}
        page_tasks = read_optional_json(run_dir, PAGE_TASKS_NAME) or {"run_id": run_id, "tasks": []}
        judgments = read_optional_json(run_dir, "consulting_judgments.json")
        ceg = read_optional_json(run_dir, "claim_evidence_graph.json")
        report = evaluate_draft_gate_v2(deck_brief, claim_map, page_tasks, judgments, ceg)
    elif args.gate == "render":
        if not args.artifact:
            raise RunStateError("--artifact is required for render gate.")
        report = evaluate_render_gate(run_id, args.artifact, expected_pages=expected_pages, forbidden_terms=args.forbidden)
    elif args.gate == "delivery":
        if not args.artifact:
            raise RunStateError("--artifact is required for delivery gate.")
        safety_terms = load_customer_visible_forbidden_terms(run_dir, extra_terms=args.forbidden)
        report = evaluate_delivery_gate(run_id, args.artifact, expected_pages=expected_pages, forbidden_terms=safety_terms)
        safety_report = evaluate_customer_visible_safety_gate(
            run_id,
            args.artifact,
            expected_pages=expected_pages,
            forbidden_terms=safety_terms,
        )
        safety_paths = write_gate_report(run_dir, "customer_visible_safety", safety_report)
        write_artifact(
            run_dir,
            "quality_reports/customer_visible_safety_gate.index.json",
            {
                "report": safety_paths,
                "status": safety_report["status"],
                "blocks_delivery": safety_report["blocks_delivery"],
            },
            action="quality.customer_visible_safety_gate.created",
        )
    elif args.gate in {"customer-visible-safety", "customer_visible_safety"}:
        if not args.artifact:
            raise RunStateError("--artifact is required for customer-visible-safety gate.")
        safety_terms = load_customer_visible_forbidden_terms(run_dir, extra_terms=args.forbidden)
        report = evaluate_customer_visible_safety_gate(
            run_id,
            args.artifact,
            expected_pages=expected_pages,
            forbidden_terms=safety_terms,
        )
    elif args.gate == "evidence":
        claim_map = read_optional_json(run_dir, CLAIM_MAP_NAME) or {"run_id": run_id, "claims": []}
        page_tasks = read_optional_json(run_dir, PAGE_TASKS_NAME) or {"run_id": run_id, "tasks": []}
        ceg = read_optional_json(run_dir, "claim_evidence_graph.json") or {"run_id": run_id, "claims": [], "evidence": [], "gaps": []}
        sourcing_plan = read_optional_json(run_dir, SOURCING_PLAN_NAME) or {"run_id": run_id, "decisions": []}
        report = evaluate_evidence_gate(run_id, claim_map, page_tasks, ceg, sourcing_plan)
    elif args.gate == "context-conflict":
        sourcing_plan = read_optional_json(run_dir, SOURCING_PLAN_NAME) or {"run_id": run_id, "decisions": []}
        ws_dir = request.get("workspace", "")
        asset_graph: dict[str, Any] = {}
        if ws_dir:
            ag_path = Path(ws_dir) / "assets" / "asset_graph.json"
            if ag_path.exists():
                try:
                    asset_graph = json.loads(ag_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
        report = evaluate_context_conflict_gate(run_id, request, sourcing_plan, asset_graph)
    elif args.gate == "confidentiality":
        ws_dir = request.get("workspace", "")
        ws_forbidden = str(Path(ws_dir) / "quality" / "forbidden_terms.md") if ws_dir else None
        sourcing_plan = read_optional_json(run_dir, SOURCING_PLAN_NAME)
        preview_manifest = read_optional_json(run_dir, "preview_manifest.json")
        report = evaluate_confidentiality_gate(
            run_id,
            forbidden_terms=args.forbidden,
            workspace_forbidden_terms_path=ws_forbidden,
            preview_manifest=preview_manifest,
            sourcing_plan=sourcing_plan,
        )
    elif args.gate == "brand":
        ws_dir = request.get("workspace", "")
        preview_manifest = read_optional_json(run_dir, "preview_manifest.json") or {}
        approved_count = sum(1 for p in preview_manifest.get("pages", []) if p.get("decision") == "approved")
        report = evaluate_brand_gate(
            run_id,
            workspace_dir=ws_dir or None,
            final_artifact=args.artifact,
            approved_page_count=approved_count,
        )
    else:
        raise RunStateError(f"Unknown gate: {args.gate}")

    gate_name = str(report.get("gate") or args.gate)
    paths = write_gate_report(run_dir, gate_name, report)
    write_artifact(
        run_dir,
        f"quality_reports/{gate_name}_gate.index.json",
        {"report": paths, "status": report["status"], "blocks_delivery": report["blocks_delivery"]},
        action=f"quality.{gate_name}_gate.created",
    )
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "gate": gate_name,
        "status": report["status"],
        "blocks_delivery": report["blocks_delivery"],
        "findings": len(report["findings"]),
        "report": paths,
    }


def command_override_create(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    override = create_override(
        run_dir, args.finding_id, args.severity, args.reason, args.approver,
        scope=args.scope, actor=args.actor, expires_days=args.expires_days,
    )
    return {"status": "override_created", "override": override}


def command_override_list(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    overrides = list_active_overrides(run_dir)
    return {"status": "overrides_listed", "count": len(overrides), "overrides": overrides}


def command_override_revoke(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    override = revoke_override(run_dir, args.override_id, args.reason)
    return {"status": "override_revoked", "override": override}


def command_delivery_validate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    if not args.artifact:
        raise RunStateError("--artifact is required for delivery validate.")
    expected_pages = args.expected_pages
    if expected_pages is None:
        pm = read_optional_json(run_dir, "preview_manifest.json")
        if pm and isinstance(pm.get("pages"), list):
            expected_pages = sum(1 for p in pm["pages"] if p.get("decision") == "approved")
    return validate_delivery(run_dir, args.artifact, expected_page_count=expected_pages or 0)


def command_final_readiness(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    payload = compute_final_readiness(
        run_dir,
        artifact_path=getattr(args, "artifact", None),
        expected_page_count=getattr(args, "expected_pages", None),
        write=not bool(getattr(args, "no_write", False)),
        run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
        dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
    )
    status = str(payload.get("status") or "")
    next_agent_action = (
        "Final readiness is ready; export may proceed."
        if status == "ready"
        else _blocked_next_agent_action(payload, "Resolve final-readiness blockers before export.")
    )
    return _add_agent_output_contract(
        payload,
        next_agent_action=next_agent_action,
        evidence_paths=[
            run_dir / "delivery" / "final_readiness.json",
            run_dir / "render_results" / "render_result.json",
            run_dir / "delivery" / "final_version_lineage.json",
            run_dir / "quality_reports",
        ],
    )


def command_delivery_record_outcome(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return record_delivery_outcome(
        run_dir,
        delivered=args.delivered,
        advanced_to_next_stage=args.advanced_to_next_stage,
        customer_reaction=args.customer_reaction or "",
        notes=args.notes or "",
    )


def command_opportunity_create(args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace:
        raise RunStateError("--workspace is required for opportunity create.")
    return create_opportunity(args.workspace, args.client_name, args.industry)


def command_opportunity_attach_run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace:
        raise RunStateError("--workspace is required for opportunity attach-run.")
    return attach_run(args.workspace, args.opportunity_id, args.run_id)


def command_approval_submit(args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace:
        raise RunStateError("--workspace is required for approval submit.")
    return submit_approval(args.workspace, args.run_id, args.submitted_by, notes=args.notes or "")


def command_approval_approve(args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace:
        raise RunStateError("--workspace is required for approval approve.")
    return approve(args.workspace, args.approval_id, args.approver, notes=args.notes or "")


def command_approval_reject(args: argparse.Namespace) -> dict[str, Any]:
    if not args.workspace:
        raise RunStateError("--workspace is required for approval reject.")
    return reject(args.workspace, args.approval_id, args.rejecter, reason=args.reason or "")


def command_connector_import(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = validate_import_manifest(manifest)
    if not validation["valid"]:
        raise ValueError(f"Invalid import manifest: {'; '.join(validation['errors'])}")
    context = import_to_context_manifest(manifest, base_dir=args.base_dir or "")
    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"status": "imported", "output": str(out), "validation": validation}
    return {"status": "imported", "context_manifest": context, "validation": validation}


def command_next_step(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    payload = resolve_next_step(
        run_dir,
        cli_workspace=getattr(args, "workspace", None),
        run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
        dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
    )
    # Project the contract stage so next-step shares the same resolution as
    # run-state / route-skill / workflow status (A5 consistency).
    try:
        wf = resolve_workflow_state(run_dir, runtime_stage_fn=_safe_runtime_stage)
        payload["current_skill_stage"] = wf.get("current_skill_stage", "")
        payload["contract_recommended_next_skill"] = wf.get("recommended_next_skill", "")
    except Exception:
        pass
    next_command = str(payload.get("next_command") or "").strip()
    runtime_stage = str(payload.get("runtime_stage") or "").strip()
    blocking_issues = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    if next_command:
        next_agent_action = f"Run the returned next_command: {next_command}"
    elif blocking_issues:
        next_agent_action = str(blocking_issues[0])
    else:
        next_agent_action = f"Continue from runtime_stage {runtime_stage or 'unknown'}."
    return _add_agent_output_contract(
        payload,
        next_agent_action=next_agent_action,
        evidence_paths=[
            run_dir / REQUEST_NAME,
            run_dir / NARRATIVE_PLAN_NAME,
            run_dir / PAGE_TASKS_NAME,
            run_dir / SOURCING_PLAN_NAME,
            run_dir / "preview_manifest.json",
            run_dir / "workflow_state.json",
        ],
    )


def command_build_judgments(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    request = load_request(run_dir)
    deck_brief = read_json(run_dir / DECK_BRIEF_NAME)
    claim_map = read_json(run_dir / CLAIM_MAP_NAME)
    context_manifest = read_optional_json(run_dir, CONTEXT_MANIFEST_NAME) or {}
    judgments = build_judgments(request, deck_brief, claim_map, context_manifest)
    write_artifact(run_dir, "consulting_judgments.json", judgments, action="judgments.created")
    return {
        "run_id": request.get("run_id", run_dir.name),
        "run_dir": str(run_dir),
        "status": "judgments_ready",
        "judgments": len(judgments["judgments"]),
    }


def command_build_claim_graph(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    claim_map = read_json(run_dir / CLAIM_MAP_NAME)
    page_tasks = read_optional_json(run_dir, PAGE_TASKS_NAME) or {"run_id": claim_map.get("run_id", ""), "tasks": []}
    context_manifest = read_optional_json(run_dir, CONTEXT_MANIFEST_NAME) or {}
    judgments = read_optional_json(run_dir, "consulting_judgments.json")
    graph = build_claim_evidence_graph(claim_map, page_tasks, context_manifest, judgments)
    write_artifact(run_dir, "claim_evidence_graph.json", graph, action="claim_evidence_graph.created")
    return {
        "run_id": graph["run_id"],
        "run_dir": str(run_dir),
        "status": "claim_graph_ready",
        "claims": len(graph["claims"]),
        "evidence": len(graph["evidence"]),
        "gaps": len(graph["gaps"]),
    }


def command_init_workspace(args: argparse.Namespace) -> dict[str, Any]:
    workspace_dir = Path(args.workspace).expanduser().resolve()
    manifest = init_workspace(workspace_dir, args.name)
    return {"workspace": str(workspace_dir), "name": args.name, "status": "initialized"}


def command_init_project(args: argparse.Namespace) -> dict[str, Any]:
    return init_deck_project(args.workspace, name=args.name)


def command_register_workspace(args: argparse.Namespace) -> dict[str, Any]:
    workspace_dir = Path(args.workspace).expanduser().resolve()
    reference_ppt = Path(args.reference_ppt).expanduser().resolve() if args.reference_ppt else None
    manifest = register_workspace(workspace_dir, reference_ppt)
    return {"workspace": str(workspace_dir), "status": "registered", "reference_ppt": str(reference_ppt) if reference_ppt else None}


def command_validate_workspace(args: argparse.Namespace) -> dict[str, Any]:
    workspace_dir = Path(args.workspace).expanduser().resolve()
    result = validate_workspace(workspace_dir)
    return result


def command_setup(args: argparse.Namespace) -> dict[str, Any]:
    result = run_setup(
        workspace=getattr(args, "workspace", None),
        runs_dir=getattr(args, "runs_dir", None),
        targets=getattr(args, "target", None),
        review_cockpit_url=getattr(args, "review_cockpit_url", None),
        repair=bool(getattr(args, "repair_workspace", False)),
    )
    if bool(getattr(args, "install_suite", False)):
        result["suite_install"] = suite_install(
            targets=getattr(args, "target", None),
            include_optional=False,
            repair=False,
        )
        result["setup_status"] = setup_status(
            workspace=getattr(args, "workspace", None),
            run_mode="production",
            include_suite=True,
        )
    return result


def command_setup_status(args: argparse.Namespace) -> dict[str, Any]:
    return setup_status(
        workspace=_resolve_workspace_for_setup_status(args),
        run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
        include_suite=bool(getattr(args, "include_suite", False)),
    )


def _blocked_suite_capabilities(setup: dict[str, Any]) -> list[dict[str, str]]:
    suite = setup.get("suite") if isinstance(setup.get("suite"), dict) else {}
    blocked: list[dict[str, str]] = []
    skill_items = suite.get("skills", [])
    if not isinstance(skill_items, list):
        skill_items = []
    for item in skill_items:
        if not isinstance(item, dict) or not item.get("required"):
            continue
        if item.get("status") == "ready" and item.get("valid") is True:
            continue
        blocked.append(
            {
                "target": str(item.get("target") or ""),
                "skill": str(item.get("skill") or ""),
                "status": str(item.get("status") or "blocked"),
                "reason": str(item.get("error") or item.get("cli_error") or ""),
            }
        )
    return blocked


def _start_first_action(setup: dict[str, Any], run_state: dict[str, Any] | None = None) -> str:
    setup_command = str(setup.get("next_command") or "").strip()
    if setup.get("status") != "ready":
        return setup_command or "deck-master setup-status --include-suite --output json"
    if setup.get("full_suite_ready") is False:
        suite = setup.get("suite") if isinstance(setup.get("suite"), dict) else {}
        return str(suite.get("next_command") or setup_command or "deck-master suite-repair --target codex")
    if run_state:
        return str(run_state.get("next_command") or setup_command or "deck-master setup-status --include-suite --output json")
    return setup_command or "deck-master setup-status --include-suite --output json"


def command_start(args: argparse.Namespace) -> dict[str, Any]:
    run_mode = _normalize_run_mode(getattr(args, "run_mode", None))
    setup = setup_status(
        workspace=_resolve_workspace_for_setup_status(args),
        run_mode=run_mode,
        include_suite=True,
        write_event=False,
    )
    blocked_capabilities = _blocked_suite_capabilities(setup)
    first_action = _start_first_action(setup)
    payload: dict[str, Any] = {
        "schema_version": "deck_master_start.v1",
        "status": setup.get("status", "blocked"),
        "run_mode": run_mode,
        "setup_status": setup,
        "suite": setup.get("suite") or {},
        "full_suite_ready": bool(setup.get("full_suite_ready")),
        "task_readiness": setup.get("task_readiness") or {},
        "production_backend_ready": bool(setup.get("production_backend_ready")),
        "client_delivery_ready": bool(setup.get("client_delivery_ready")),
        "blocking_summary": setup.get("blocking_summary") or [],
        "blocked_capabilities": blocked_capabilities,
        "first_action": first_action,
        "active_workspace": (setup.get("config") or {}).get("active_workspace", "")
        if isinstance(setup.get("config"), dict)
        else "",
        "production_ready": bool(setup.get("production_ready")),
        "next_command": first_action,
    }
    if getattr(args, "run_dir", None) or getattr(args, "run_id", None):
        run_dir = resolve_run_dir(args)
        run_state = resolve_run_state(
            run_dir,
            cli_workspace=getattr(args, "workspace", None),
            run_mode=run_mode,
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
        payload["run_state"] = run_state
        payload["orchestration"] = _start_orchestration_summary(run_dir, run_state)
        payload["run_next_command"] = run_state.get("next_command") or ""
        payload["first_action"] = _start_first_action(setup, run_state)
        payload["next_command"] = payload["first_action"]
        payload["recommended_skill"] = run_state.get("recommended_skill", "")
        payload["skill_route"] = run_state.get("skill_route", {})
    else:
        setup_stage = ""
        setup_reason = ""
        if setup.get("status") != "ready":
            setup_stage = "blocked_setup"
            setup_reason = "Deck Master setup is not ready."
        elif setup.get("full_suite_ready") is False:
            setup_stage = "blocked_suite"
            setup_reason = "Deck Master suite is not fully ready."
        if setup_stage:
            route = route_for_stage(setup_stage, reason=setup_reason, next_command=payload["next_command"])
        else:
            route = route_for_input_type("project_start", next_command="deck-master init-project --workspace <workspace> --name <project>")
        payload["recommended_skill"] = route["recommended_skill"]
        payload["skill_route"] = route
    return payload


def command_route_skill(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "run_dir", None) or getattr(args, "run_id", None):
        run_state = resolve_run_state(
            resolve_run_dir(args),
            cli_workspace=getattr(args, "workspace", None),
            run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
        payload = run_state.get("skill_route") or route_for_stage_manifest_aware(
            str(run_state.get("stage") or ""),
            reason=str(run_state.get("skill_reason") or ""),
            next_command=str(run_state.get("next_command") or ""),
        )
        # manifest-driven projection: share current_skill_stage with the other
        # three state entries (A5 consistency).
        try:
            wf = resolve_workflow_state(resolve_run_dir(args), runtime_stage_fn=_safe_runtime_stage)
            payload["current_skill_stage"] = wf.get("current_skill_stage", "")
        except Exception:
            pass
        return payload
    # No run context: route by input type (manifest-validated).
    payload = route_for_input_type(
        str(getattr(args, "input_type", "") or ""),
        next_command=str(getattr(args, "next_command", "") or ""),
    )
    return payload


def _autopilot_args(args: argparse.Namespace, **overrides: Any) -> argparse.Namespace:
    values = vars(args).copy()
    defaults = {
        "library_mode": "auto",
        "ppt_lib_command": "ppt-lib",
        "allow_fixture_library_fallback": False,
        "planning_mode": "classic",
        "planner_mode": None,
        "gate": "draft",
        "artifact": None,
        "expected_pages": None,
        "forbidden": [],
        "output": None,
        "decision": ["approved"],
        "queue_type": "client",
        "allow_quality_override": False,
        "force": False,
        "tool": "ppt-deck-pro-max",
        "tool_command": None,
        "dry_run": False,
        "no_execute": False,
    }
    defaults.update(values)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _autopilot_stop_reason(stage: str) -> str:
    return {
        "needs_request": "需要先创建项目请求。",
        "needs_context": "需要先导入项目资料或 context pack。",
        "blocked_workspace": "工作区未就绪，需要先运行 deck-init 或 setup repair。",
        "awaiting_agent_execution": "正在等待外部 Agent 执行生成任务并回传结果。",
        "generation_running": "生成任务仍在运行或等待状态更新。",
        "generation_failed": "生成任务失败，需要人工查看原因。",
        "needs_generation_import": "需要导入 Agent 回传的 generation result。",
        "needs_builder_backend": "缺少可用于生产交付的 Deck Builder 后端。",
        "needs_review": "页面需要人工审阅或批准。",
        "ready_for_client_export": "已到客户导出阶段。",
        "ready_for_benchmark": "已到 benchmark 放行阶段。",
    }.get(stage, f"当前阶段 {stage} 无自动动作。")


def _autopilot_action(stage: str, args: argparse.Namespace) -> tuple[str, dict[str, Any] | None]:
    if stage == "needs_brief":
        return "build-brief", command_build_brief(_autopilot_args(args))
    if stage == "needs_claim_map":
        return "build-claim-map", command_build_claim_map(_autopilot_args(args))
    if stage in {"needs_narrative_plan", "needs_page_tasks", "needs_sourcing", "needs_preview"}:
        return "autoplan", command_autoplan(_autopilot_args(args))
    if stage == "needs_generation_session":
        command_generation_session_create(_autopilot_args(args, force=False))
        return "run-generation", command_run_generation(_autopilot_args(args))
    if stage == "needs_preview_refresh":
        return "refresh-preview-from-generation", command_refresh_preview_from_generation(_autopilot_args(args))
    if stage == "needs_draft_gate":
        return "quality-gate draft", command_quality_gate(_autopilot_args(args, gate="draft"))
    if stage == "needs_build":
        return "build prepare", command_build_prepare(_autopilot_args(args))
    if stage == "needs_render":
        return "build run", command_build_run(_autopilot_args(args))
    if stage in {"ready_for_client_export", "ready_for_benchmark"}:
        return "export", command_export(_autopilot_args(args, queue_type="client"))
    return "", None


def command_workflow_autopilot(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    mode = str(getattr(args, "mode", "quick") or "quick")
    max_steps = int(getattr(args, "max_steps", 8) or 8)
    steps: list[dict[str, Any]] = []
    review_only_allowed = {"needs_draft_gate", "needs_review", "ready_for_client_export", "ready_for_benchmark"}
    repair_allowed = {"needs_draft_gate", "needs_builder_backend", "needs_build", "needs_render", "ready_for_client_export", "ready_for_benchmark"}

    status = "stopped"
    stop_reason = ""
    final_state: dict[str, Any] = {}

    for index in range(max_steps):
        state = resolve_run_state(
            run_dir,
            cli_workspace=getattr(args, "workspace", None),
            run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
        final_state = state
        stage = str(state.get("stage") or "")
        route = state.get("skill_route") or route_for_stage(stage, next_command=str(state.get("next_command") or ""))

        if mode == "review-only" and stage not in review_only_allowed:
            stop_reason = "review-only mode only advances review, quality, and export stages."
            break
        if mode == "repair" and stage not in repair_allowed:
            stop_reason = "repair mode only advances quality, build, render, and export stages."
            break

        action, result = _autopilot_action(stage, args)
        if not action:
            stop_reason = _autopilot_stop_reason(stage)
            break

        steps.append(
            {
                "index": index + 1,
                "stage": stage,
                "recommended_skill": route.get("recommended_skill", ""),
                "action": action,
                "result_status": str((result or {}).get("status") or ""),
            }
        )

        next_state = resolve_run_state(
            run_dir,
            cli_workspace=getattr(args, "workspace", None),
            run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
        final_state = next_state
        if str(next_state.get("stage") or "") == stage:
            stop_reason = f"autopilot stopped because stage did not advance after {action}."
            break
    else:
        status = "max_steps_reached"
        stop_reason = f"Stopped after {max_steps} steps."

    if steps and status != "max_steps_reached":
        status = "advanced"
    report = {
        "schema_version": "deck_master_autopilot.v1",
        "status": status,
        "mode": mode,
        "run_id": str(final_state.get("run_id") or run_dir.name),
        "run_dir": str(run_dir),
        "steps": steps,
        "stop_reason": stop_reason,
        "final_stage": str(final_state.get("stage") or ""),
        "recommended_skill": str(final_state.get("recommended_skill") or ""),
        "next_command": str(final_state.get("next_command") or ""),
        "skill_route": final_state.get("skill_route") or {},
    }
    write_json(run_dir / "workflow_autopilot_report.json", report)
    return report


def command_run_state(args: argparse.Namespace) -> dict[str, Any]:
    state = resolve_run_state(
        resolve_run_dir(args),
        cli_workspace=getattr(args, "workspace", None),
        run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
        dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
    )
    # Project the contract view (current_skill_stage) alongside the runtime
    # view so run-state / next-step / route-skill / workflow status all share
    # one stage resolution (A5 consistency). Additive; never overrides runtime.
    try:
        wf = resolve_workflow_state(
            resolve_run_dir(args),
            run_id=str(state.get("run_id") or ""),
            runtime_stage_fn=_safe_runtime_stage,
        )
        state["current_skill_stage"] = wf.get("current_skill_stage", "")
        state["contract_recommended_next_skill"] = wf.get("recommended_next_skill", "")
        state["contract_approval_required"] = bool(wf.get("approval_required", False))
    except Exception:
        pass
    return state


def _safe_runtime_stage(run_dir: str | Path) -> str:
    try:
        return resolve_runtime_stage(run_dir)
    except Exception:
        return ""


def _actor_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": str(getattr(args, "actor_id", "") or "cli"),
        "role": str(getattr(args, "actor_role", "") or "operator"),
    }


def _wf_state(args: argparse.Namespace) -> dict[str, Any]:
    return resolve_workflow_state(
        resolve_run_dir(args),
        run_id=str(getattr(args, "run_id", "") or ""),
        runtime_stage_fn=_safe_runtime_stage,
    )


def command_workflow_status(args: argparse.Namespace) -> dict[str, Any]:
    payload = _wf_state(args)
    try:
        from workflow.questions import QuestionResolver
        from workflow.stage_checks import evaluate_stage_checks

        run_dir = resolve_run_dir(args)
        current_stage = str(payload.get("current_skill_stage") or "")
        if current_stage:
            question_gaps = QuestionResolver().blocking(run_dir, current_stage)
            stage_checks = evaluate_stage_checks(run_dir, current_stage)
            payload["pending_questions_count"] = len(question_gaps)
            payload["coverage_gaps"] = list(stage_checks.coverage_gaps)
            payload["required_modules_status"] = list(stage_checks.required_modules_status)
    except Exception:
        pass
    return payload


def command_workflow_stages(args: argparse.Namespace) -> dict[str, Any]:
    state = _wf_state(args)
    return {"run_id": state.get("run_id"), "stages": state.get("stages", [])}


def command_workflow_handoff_prepare(args: argparse.Namespace) -> dict[str, Any]:
    rt = HandoffRuntime()
    return rt.prepare(
        resolve_run_dir(args),
        str(args.from_stage),
        run_id=str(getattr(args, "run_id", "") or "") or None,
        created_by=str(getattr(args, "created_by", "") or "") or None,
    )


def command_workflow_handoff_list(args: argparse.Namespace) -> dict[str, Any]:
    rt = HandoffRuntime()
    return {"handoffs": rt.list(resolve_run_dir(args))}


def command_workflow_handoff_accept(args: argparse.Namespace) -> dict[str, Any]:
    rt = HandoffRuntime()
    return rt.accept(resolve_run_dir(args), str(args.handoff_id), actor=str(_actor_from_args(args).get("id")))


def command_workflow_handoff_consume(args: argparse.Namespace) -> dict[str, Any]:
    rt = HandoffRuntime()
    return rt.consume(resolve_run_dir(args), str(args.handoff_id))


def command_workflow_handoff_reject(args: argparse.Namespace) -> dict[str, Any]:
    rt = HandoffRuntime()
    return rt.reject(
        resolve_run_dir(args),
        str(args.handoff_id),
        reason=str(args.reason),
        repair_owner_stage=str(getattr(args, "repair_owner_stage", "") or ""),
        actor=str(_actor_from_args(args).get("id")),
    )


def command_workflow_approval_request(args: argparse.Namespace) -> dict[str, Any]:
    ap = ApprovalRuntime()
    return ap.request(
        resolve_run_dir(args),
        str(args.handoff_id),
        run_id=str(getattr(args, "run_id", "") or ""),
        actor=_actor_from_args(args),
    )


def command_workflow_approval_approve(args: argparse.Namespace) -> dict[str, Any]:
    ap = ApprovalRuntime()
    return ap.approve(
        resolve_run_dir(args),
        str(args.approval_id),
        actor=_actor_from_args(args),
        preauthorization_id=str(getattr(args, "preauthorization_id", "") or ""),
    )


def command_workflow_approval_reject(args: argparse.Namespace) -> dict[str, Any]:
    ap = ApprovalRuntime()
    return ap.reject(
        resolve_run_dir(args),
        str(args.approval_id),
        actor=_actor_from_args(args),
        reason=str(args.reason),
        repair_owner_stage=str(getattr(args, "repair_owner_stage", "") or ""),
    )


def command_workflow_approval_list(args: argparse.Namespace) -> dict[str, Any]:
    ap = ApprovalRuntime()
    return {"approvals": ap.list(resolve_run_dir(args))}


def command_workflow_approval_status(args: argparse.Namespace) -> dict[str, Any]:
    ap = ApprovalRuntime()
    cleared, reason = ap.is_transition_cleared(
        resolve_run_dir(args), str(args.from_stage), run_id=str(getattr(args, "run_id", "") or "")
    )
    return {"from_stage": args.from_stage, "cleared": cleared, "reason": reason}


def command_workflow_preauth_create(args: argparse.Namespace) -> dict[str, Any]:
    preauth = PreauthorizationRuntime()
    transitions = [t for t in str(args.allowed_transitions or "").split(",") if t]
    policy = preauth.create(
        resolve_run_dir(args),
        run_id=str(args.run_id),
        actor=_actor_from_args(args),
        mode=str(args.mode),
        allowed_transitions=transitions,
        material_roots=[m for m in str(getattr(args, "material_roots", "") or "").split(",") if m],
        max_generated_pages=int(getattr(args, "max_generated_pages", 0) or 0) or None,
        max_cost_class=str(getattr(args, "max_cost_class", "low")),
        ttl_seconds=int(getattr(args, "ttl_seconds", 3600) or 3600),
    )
    return policy.data


def command_workflow_preauth_list(args: argparse.Namespace) -> dict[str, Any]:
    preauth = PreauthorizationRuntime()
    return {"preauthorizations": [p.data for p in preauth.list(resolve_run_dir(args))]}


def command_workflow_preauth_revoke(args: argparse.Namespace) -> dict[str, Any]:
    preauth = PreauthorizationRuntime()
    return preauth.revoke(resolve_run_dir(args), str(args.policy_id), by_actor=_actor_from_args(args)).data


def command_workflow_autopilot_v2(args: argparse.Namespace) -> dict[str, Any]:
    from workflow.autopilot import AutopilotV2

    ap = AutopilotV2()
    result = ap.run(
        resolve_run_dir(args),
        mode=str(args.mode),
        max_steps=int(getattr(args, "max_steps", 8) or 8),
        run_id=str(getattr(args, "run_id", "") or "") or None,
        repair_owner_stage=str(getattr(args, "repair_owner_stage", "") or ""),
    )
    return {
        "mode": result.mode,
        "stop_reason": result.stop_reason,
        "final_stage": result.final_stage,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "steps": [s.__dict__ for s in result.steps],
    }


def command_doctor(args: argparse.Namespace) -> dict[str, Any]:
    run_mode = _normalize_run_mode(getattr(args, "run_mode", None))
    payload: dict[str, Any] = {
        "schema_version": "deck_master_doctor.v1",
        "run_mode": run_mode,
        "setup_status": setup_status(
            workspace=_resolve_workspace_for_setup_status(args),
            run_mode=run_mode,
        ),
    }
    if getattr(args, "run_dir", None):
        payload["run_state"] = resolve_run_state(
            resolve_run_dir(args),
            cli_workspace=getattr(args, "workspace", None),
            run_mode=run_mode,
            dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
        )
    return payload


def _agent_doctor_add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    status: str,
    summary: str,
    *,
    details: dict[str, Any] | None = None,
    evidence_paths: list[str | Path] | None = None,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": status,
            "summary": summary,
            "details": details or {},
            "evidence_paths": _unique_strings([_agent_evidence_path(path) for path in (evidence_paths or [])]),
        }
    )


def _agent_doctor_path_check(
    checks: list[dict[str, Any]],
    check_id: str,
    paths: list[str | Path],
    summary: str,
    *,
    missing_status: str = "blocked",
) -> None:
    missing = [str(path) for path in paths if not Path(path).exists()]
    _agent_doctor_add_check(
        checks,
        check_id,
        "pass" if not missing else missing_status,
        summary,
        details={"missing": missing},
        evidence_paths=paths,
    )


def _production_dependency_report(suite_payload: dict[str, Any]) -> tuple[bool, list[str], list[dict[str, Any]]]:
    dependencies = suite_payload.get("external_dependency_status")
    if not isinstance(dependencies, list):
        dependencies = []
    required = {"ppt-master"}
    by_name = {
        str(item.get("name") or ""): item
        for item in dependencies
        if isinstance(item, dict)
    }
    missing: list[str] = []
    for name in sorted(required):
        item = by_name.get(name)
        if not item:
            missing.append(name)
            continue
        binding_status = str(item.get("binding_status") or "")
        verified = bool(item.get("verified"))
        git_sha = str(item.get("git_sha") or "").strip()
        if binding_status != "bound_verified" or not verified or not git_sha:
            missing.append(name)
    return not missing, missing, [item for item in dependencies if isinstance(item, dict) and item.get("name") in required]


def _agent_doctor_result(mode: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [
        {"check_id": check["check_id"], "summary": check["summary"], "details": check.get("details", {})}
        for check in checks
        if check.get("status") in {"blocked", "fail"}
    ]
    warnings = [
        {"check_id": check["check_id"], "summary": check["summary"], "details": check.get("details", {})}
        for check in checks
        if check.get("status") == "warn"
    ]
    status = "blocked" if errors else "ready"
    evidence_paths = _unique_strings(
        [
            path
            for check in checks
            for path in (check.get("evidence_paths") if isinstance(check.get("evidence_paths"), list) else [])
        ]
    )
    if status == "ready" and mode == "preview":
        next_agent_action = (
            "Preview path is Agent-operable. Use fixture mode, then stop before production until production mode is ready."
        )
    elif status == "ready":
        next_agent_action = "Production prerequisites are ready; continue with final-readiness or release validation."
    else:
        first_error = errors[0]["summary"] if errors else "Agent doctor is blocked."
        next_agent_action = f"Stop and report: {first_error}"
    return {
        "schema_version": "deck_master_agent_doctor.v1",
        "status": status,
        "mode": mode,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "next_agent_action": next_agent_action,
        "evidence_paths": evidence_paths,
    }


def command_agent_doctor(args: argparse.Namespace) -> dict[str, Any]:
    mode = str(getattr(args, "mode", "preview") or "preview")
    checks: list[dict[str, Any]] = []
    contracts_root = ROOT / "docs" / "contracts"
    if not contracts_root.exists():
        contracts_root = ROOT / "contracts"

    _agent_doctor_path_check(
        checks,
        "cli_entrypoint",
        [ROOT / "scripts" / "deck_master.py"],
        "Local deck-master CLI entrypoint is present.",
    )
    _agent_doctor_path_check(
        checks,
        "agent_docs",
        [ROOT / "AGENTS.md", ROOT / "docs" / "agent-task-index.md", ROOT / "docs" / "agent-recovery-playbook.md"],
        "Agent entrypoint and routing docs are present.",
    )
    _agent_doctor_path_check(
        checks,
        "contracts",
        [
            contracts_root / "setup-status.v2.schema.json",
            contracts_root / "workflow-state.v1.schema.json",
            contracts_root / "final-readiness.v1.schema.json",
            contracts_root / "rc-gate-report.v1.schema.json",
        ],
        "Core runtime contracts are present.",
    )
    _agent_doctor_path_check(
        checks,
        "review_desk_static",
        [
            ROOT / "scripts" / "preview" / "static" / "index.html",
            ROOT / "scripts" / "preview" / "static" / "style.css",
            ROOT / "scripts" / "preview" / "static" / "app.js",
        ],
        "Review Desk static files are present.",
    )
    _agent_doctor_path_check(
        checks,
        "fixture_demo_entrypoint",
        [ROOT / "scripts" / "demo.sh", ROOT / "examples" / "briefs" / "retail_digital_transformation.txt"],
        "Fixture demo entrypoint and public brief are present.",
    )

    run_dir_raw = str(getattr(args, "run_dir", "") or "").strip()
    run_dir = Path(run_dir_raw).expanduser().resolve() if run_dir_raw else Path("/tmp/deck-master-demo/oss-demo")
    if run_dir.exists():
        try:
            preview_payload = command_preview_gate(
                argparse.Namespace(run_dir=str(run_dir), expect_unconfigured_backend_ok=True)
            )
        except Exception as exc:
            _agent_doctor_add_check(
                checks,
                "preview_gate",
                "blocked",
                "Preview gate could not run.",
                details={"run_dir": str(run_dir), "error": str(exc)},
                evidence_paths=[run_dir],
            )
        else:
            _agent_doctor_add_check(
                checks,
                "preview_gate",
                "pass" if preview_payload.get("status") == "pass" else "blocked",
                "Fixture preview gate result is available.",
                details={
                    "status": preview_payload.get("status"),
                    "run_dir": str(run_dir),
                    "next_agent_action": preview_payload.get("next_agent_action", ""),
                },
                evidence_paths=[run_dir, run_dir / "preview_manifest.json"],
            )
    elif run_dir_raw:
        _agent_doctor_add_check(
            checks,
            "preview_gate",
            "blocked",
            "Requested run directory is missing; preview-gate cannot verify the demo.",
            details={"run_dir": str(run_dir)},
            evidence_paths=[run_dir],
        )
    else:
        _agent_doctor_add_check(
            checks,
            "preview_gate",
            "warn",
            "Fixture demo run is not created yet; run scripts/demo.sh before preview-gate.",
            details={
                "expected_run_dir": str(run_dir),
                "next_command": "bash scripts/demo.sh",
            },
            evidence_paths=[ROOT / "scripts" / "demo.sh"],
        )

    suite_payload = inspect_suite_status(
        targets=getattr(args, "target", None),
        include_optional=True,
    )
    production_dependencies_ready, missing_dependencies, dependencies = _production_dependency_report(suite_payload)
    if mode == "preview":
        _agent_doctor_add_check(
            checks,
            "production_backend_projection",
            "pass" if production_dependencies_ready else "warn",
            (
                "Production backend is fully bound."
                if production_dependencies_ready
                else "Production backend is not ready; preview must stay in fixture mode."
            ),
            details={
                "missing_or_unready": missing_dependencies,
                "external_dependency_status": dependencies,
            },
            evidence_paths=["product-capability-manifest.json", "docs/agent-recovery-playbook.md"],
        )
        return _agent_doctor_result(mode, checks)

    _agent_doctor_add_check(
        checks,
        "suite_status",
        "pass" if bool(suite_payload.get("full_suite_ready")) else "blocked",
        (
            "Required suite capabilities are ready."
            if bool(suite_payload.get("full_suite_ready"))
            else "Required suite capabilities are missing or blocked."
        ),
        details={
            "status": suite_payload.get("status"),
            "full_suite_ready": suite_payload.get("full_suite_ready"),
            "blocking_summary": suite_payload.get("blocking_summary", []),
        },
        evidence_paths=["skills/manifest.json", "product-capability-manifest.json"],
    )
    _agent_doctor_add_check(
        checks,
        "production_backend",
        "pass" if production_dependencies_ready else "blocked",
        (
            "Production backend dependencies are bound, verified, and pinned."
            if production_dependencies_ready
            else "Production backend dependencies are missing, unverified, or not pinned."
        ),
        details={
            "missing_or_unready": missing_dependencies,
            "external_dependency_status": dependencies,
        },
        evidence_paths=["product-capability-manifest.json", "docs/agent-recovery-playbook.md"],
    )

    release_root_raw = str(getattr(args, "release_root", "") or "").strip()
    release_root = Path(release_root_raw).expanduser().resolve() if release_root_raw else Path.home() / ".deck-master" / "current"
    capability_lock = release_root / "deck_capability_lock.json"
    _agent_doctor_add_check(
        checks,
        "capability_lock",
        "pass" if capability_lock.exists() else "blocked",
        (
            "Capability lock is present."
            if capability_lock.exists()
            else "Capability lock is missing; production release state is not pinned."
        ),
        details={"release_root": str(release_root), "capability_lock": str(capability_lock)},
        evidence_paths=[capability_lock],
    )

    if run_dir_raw:
        try:
            final_payload = command_final_readiness(
                argparse.Namespace(
                    run_dir=str(run_dir),
                    run_id=None,
                    runs_dir=None,
                    artifact=None,
                    expected_pages=None,
                    no_write=True,
                    run_mode="production",
                    dev_allow_unsetup=False,
                    workspace=getattr(args, "workspace", ""),
                )
            )
        except Exception as exc:
            _agent_doctor_add_check(
                checks,
                "final_readiness",
                "blocked",
                "Final readiness could not run.",
                details={"run_dir": str(run_dir), "error": str(exc)},
                evidence_paths=[run_dir],
            )
        else:
            _agent_doctor_add_check(
                checks,
                "final_readiness",
                "pass" if final_payload.get("status") == "ready" else "blocked",
                "Final readiness result is available.",
                details={
                    "status": final_payload.get("status"),
                    "blockers": final_payload.get("blockers", []),
                    "next_agent_action": final_payload.get("next_agent_action", ""),
                },
                evidence_paths=[run_dir / "delivery" / "final_readiness.json", run_dir / "render_results" / "render_result.json"],
            )
    else:
        _agent_doctor_add_check(
            checks,
            "final_readiness",
            "blocked",
            "Production mode requires --run-dir so final-readiness can be checked.",
            details={"next_command": "deck-master final-readiness --run-dir <run_dir> --no-write"},
            evidence_paths=[],
        )

    return _agent_doctor_result(mode, checks)


def command_install_skill(args: argparse.Namespace) -> dict[str, Any]:
    if bool(getattr(args, "suite", False)):
        return suite_install(
            targets=getattr(args, "target", None),
            include_optional=bool(getattr(args, "include_optional", False)),
        )
    target = getattr(args, "target", None)
    if isinstance(target, list):
        target = target[-1] if target else None
    return install_skill(
        target=target,
        agent_skill_dir=getattr(args, "agent_skill_dir", None),
        force=getattr(args, "force", False),
        source_skill_dir=getattr(args, "source_skill_dir", None),
    )


def command_suite_status(args: argparse.Namespace) -> dict[str, Any]:
    payload = inspect_suite_status(
        targets=getattr(args, "target", None),
        include_optional=True,
    )
    next_agent_action = str(payload.get("next_agent_action") or "")
    if not next_agent_action:
        next_agent_action = (
            "Suite ready."
            if payload.get("status") == "ready"
            else "Run deck-master suite-repair --target codex, then rerun suite-status."
        )
    return _add_agent_output_contract(
        payload,
        next_agent_action=next_agent_action,
        evidence_paths=[
            "product-capability-manifest.json",
            "skills/manifest.json",
            "skills/deck-master/SKILL.md",
            "docs/contracts",
        ],
    )


def command_product_capability_manifest(args: argparse.Namespace) -> dict[str, Any]:
    return product_capability_manifest()


def command_validate_product_capability_manifest(args: argparse.Namespace) -> dict[str, Any]:
    return validate_product_capability_manifest()


def command_suite_build_release_tree(args: argparse.Namespace) -> dict[str, Any]:
    return build_release_tree(
        getattr(args, "output", None),
        force=bool(getattr(args, "force", False)),
        dry_run=bool(getattr(args, "dry_run", False)),
    )


def _release_smoke_next_agent_action(payload: dict[str, Any], release_root_arg: str | None) -> str:
    if payload.get("status") == "passed":
        return "Release smoke passed; release tree is ready for publication checks."
    release_root = str(payload.get("release_root") or release_root_arg or "~/.deck-master/current")
    target = "/tmp/deck-master-0.9.14-preview-release"
    prefix = (
        f"Default active release tree is stale or incomplete at {release_root}."
        if not release_root_arg
        else f"Release smoke failed for {release_root}."
    )
    return (
        f"{prefix} Build and verify a fresh tree: "
        f"python3 scripts/deck_master.py release-build --output {target} --force && "
        f"python3 scripts/deck_master.py release-smoke --release-root {target}"
    )


def command_release_smoke(args: argparse.Namespace) -> dict[str, Any]:
    release_root_arg = getattr(args, "release_root", None)
    payload = verify_release_tree(
        release_root_arg,
        run_smoke=not bool(getattr(args, "no_smoke", False)),
    )
    next_agent_action = _release_smoke_next_agent_action(payload, release_root_arg)
    release_root = Path(str(payload.get("release_root") or getattr(args, "release_root", "") or "")).expanduser()
    return _add_agent_output_contract(
        payload,
        next_agent_action=next_agent_action,
        evidence_paths=[
            release_root / "release-manifest.json",
            release_root / "deck_capability_lock.json",
            release_root / "SHA256SUMS",
            release_root / "bin" / "deck-master",
        ],
    )


def command_release_install(args: argparse.Namespace) -> dict[str, Any]:
    return install_release_tree(run_smoke=not bool(getattr(args, "no_smoke", False)))


def command_release_rollback(args: argparse.Namespace) -> dict[str, Any]:
    return rollback_release_tree()


def command_suite_install(args: argparse.Namespace) -> dict[str, Any]:
    return suite_install(
        targets=getattr(args, "target", None),
        include_optional=bool(getattr(args, "include_optional", False)),
    )


def command_suite_repair(args: argparse.Namespace) -> dict[str, Any]:
    return suite_repair(
        targets=getattr(args, "target", None),
        include_optional=bool(getattr(args, "include_optional", False)),
    )


def command_backend_bind(args: argparse.Namespace) -> dict[str, Any]:
    return backend_bind(name=str(args.name), repo_path=str(args.repo))


def command_backend_status(args: argparse.Namespace) -> dict[str, Any]:
    return backend_status()


def command_backend_verify(args: argparse.Namespace) -> dict[str, Any]:
    return backend_verify(name=str(args.name))


def command_backend_unbind(args: argparse.Namespace) -> dict[str, Any]:
    return backend_unbind(name=str(args.name))


def command_suite_migrate_legacy_skills(args: argparse.Namespace) -> dict[str, Any]:
    if bool(getattr(args, "rollback", False)):
        return suite_migration_rollback(str(getattr(args, "rollback_id", "")))
    if bool(getattr(args, "apply", False)):
        return suite_migration_apply(str(getattr(args, "plan_file", "")))
    return suite_migration_plan(
        targets=getattr(args, "target", None),
        agent_skill_dir=getattr(args, "agent_skill_dir", None),
    )


def command_validate_skill(args: argparse.Namespace) -> dict[str, Any]:
    return validate_skill(
        target=args.target,
        agent_skill_dir=getattr(args, "agent_skill_dir", None),
        source_skill_dir=getattr(args, "source_skill_dir", None),
    )


def command_uninstall_skill(args: argparse.Namespace) -> dict[str, Any]:
    return uninstall_skill(
        target=args.target,
        agent_skill_dir=getattr(args, "agent_skill_dir", None),
        source_skill_dir=getattr(args, "source_skill_dir", None),
    )


def command_orchestration_check(args: argparse.Namespace) -> dict[str, Any]:
    return orchestration_check(
        resolve_run_dir(args),
        cli_workspace=getattr(args, "workspace", None),
        run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
        dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
    )


def command_import_plan(args: argparse.Namespace) -> dict[str, Any]:
    return import_plan(resolve_run_dir(args), args.input, source=args.source)


def command_import_render_result(args: argparse.Namespace) -> dict[str, Any]:
    return import_render_result(resolve_run_dir(args), args.input)


def command_render(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    if not bool(getattr(args, "fixture_safe", False)):
        return run_build(run_dir)
    request = load_request(run_dir)
    run_mode = _normalize_run_mode(str(request.get("run_mode") or getattr(args, "run_mode", None)))
    if run_mode in {"production", "benchmark"}:
        raise RunStateError("render --fixture-safe is blocked for production and benchmark runs.")
    return render_fixture_html(
        run_dir,
        output_format=getattr(args, "format", "html"),
        fixture_safe=bool(getattr(args, "fixture_safe", False)),
    )


def command_render_status(args: argparse.Namespace) -> dict[str, Any]:
    return render_status(resolve_run_dir(args))


def command_build_prepare(args: argparse.Namespace) -> dict[str, Any]:
    return prepare_build(resolve_run_dir(args))


def command_build_run(args: argparse.Namespace) -> dict[str, Any]:
    return run_build(resolve_run_dir(args))


def command_build_status(args: argparse.Namespace) -> dict[str, Any]:
    return build_status(resolve_run_dir(args))


def command_bind_workspace(args: argparse.Namespace) -> dict[str, Any]:
    return bind_workspace(resolve_run_dir(args), args.workspace, reason=args.reason or "")


def command_import_sourcing(args: argparse.Namespace) -> dict[str, Any]:
    return import_sourcing(resolve_run_dir(args), args.input, source=args.source)


def command_validate_sourcing(args: argparse.Namespace) -> dict[str, Any]:
    return validate_sourcing(resolve_run_dir(args))


def command_import_context_pack(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser().resolve()
    try:
        pack = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContextPackError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    merge = getattr(args, "merge", False)
    return import_context_pack(run_dir, pack, merge=merge)


def command_create_run_from_context_pack(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).expanduser().resolve()
    try:
        pack = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContextPackError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    return create_run_from_context_pack(
        workspace=args.workspace,
        pack=pack,
        run_id=getattr(args, "run_id", None),
        industry=getattr(args, "industry", "") or "",
        audience=getattr(args, "audience", "client") or "client",
        runs_dir=runs_dir(args),
    )


def command_prepare_narrative_advice(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return prepare_narrative_advice_task(run_dir)


def command_import_narrative_advice(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NarrativeAdviceError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    return import_narrative_advice(run_dir, result)


def command_apply_narrative_advice(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NarrativeAdviceError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    dry_run = getattr(args, "dry_run", False)
    apply_sections = None
    raw = getattr(args, "apply", None)
    if raw:
        apply_sections = [s.strip() for s in raw.split(",") if s.strip()]
    return apply_narrative_advice(run_dir, result, dry_run=dry_run, apply_sections=apply_sections)


def command_prepare_quality_review(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    scope_str = getattr(args, "scope", "semantic") or "semantic"
    scopes = [s.strip() for s in scope_str.split(",") if s.strip()]
    return prepare_quality_review(run_dir, scopes=scopes)


def command_import_quality_review(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExternalReviewError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    replace = getattr(args, "replace", False)
    return import_external_review(run_dir, result, replace=replace)


def command_import_quality_findings(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return import_quality_findings(run_dir, Path(args.input).expanduser(), replace=bool(getattr(args, "replace", False)))


def command_prepare_generation_handoff(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return prepare_generation_handoff(run_dir)


def command_import_generation_result(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GenerationHandbackError(f"Bad JSON in {input_path}: {exc.msg}") from exc
    force = getattr(args, "force", False)
    expected_run_id = str(load_request(run_dir).get("run_id") or run_dir.name)
    expected_session_id = ""
    session_path = run_dir / "generation_session.json"
    if session_path.exists():
        expected_session_id = str(read_json(session_path).get("session_id") or "")
    try:
        normalized = normalize_generation_result(
            result,
            expected_run_id=expected_run_id,
            expected_session_id=expected_session_id or None,
            run_dir=run_dir,
        )
        imported = import_generation_result(run_dir, normalized, force=force)
    except GenerationHandbackError as exc:
        append_import_log(run_dir, import_type="generation_result", source="ppt-deck-pro-max", status="rejected", source_path=input_path, errors=[str(exc)])
        raise
    append_import_log(
        run_dir,
        import_type="generation_result",
        source="ppt-deck-pro-max",
        status="imported",
        source_path=input_path,
        canonical_refs=[f"generation_results/{imported.get('task_id')}.json"],
        payload={"task_id": imported.get("task_id"), "result_status": imported.get("result_status")},
    )
    return imported


def command_refresh_preview_from_generation(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return refresh_preview_from_generation(run_dir)


def command_generation_session_create(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return create_generation_session(
        run_dir,
        tool=getattr(args, "tool", "ppt-deck-pro-max"),
        workspace=(str(args.workspace) if getattr(args, "workspace", None) else None),
        tool_command=getattr(args, "tool_command", None),
        force=bool(getattr(args, "force", False)),
    )


def command_generation_session_validate(args: argparse.Namespace) -> dict[str, Any]:
    return validate_generation_session(
        resolve_run_dir(args),
        tool=getattr(args, "tool", None),
        tool_command=getattr(args, "tool_command", None),
    )


def command_generation_session_status(args: argparse.Namespace) -> dict[str, Any]:
    return generation_session_status(
        resolve_run_dir(args),
        tool=getattr(args, "tool", None),
        tool_command=getattr(args, "tool_command", None),
    )


def command_generation_session_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    return run_generation_session(
        resolve_run_dir(args),
        tool=getattr(args, "tool", "ppt-deck-pro-max"),
        dry_run=False,
        no_execute=True,
        tool_command=getattr(args, "tool_command", None),
    )


def command_run_generation(args: argparse.Namespace) -> dict[str, Any]:
    return run_generation_session(
        resolve_run_dir(args),
        tool=getattr(args, "tool", "ppt-deck-pro-max"),
        dry_run=bool(getattr(args, "dry_run", False)),
        no_execute=bool(getattr(args, "no_execute", False)),
        tool_command=getattr(args, "tool_command", None),
    )


def command_generation_session_import_results(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return import_generation_results(
        run_dir,
        Path(args.input).expanduser(),
        force=bool(getattr(args, "force", False)),
    )


def command_record_library_feedback(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    run_id = getattr(args, "run_id", None)
    if not run_id:
        run_id = load_request(run_dir).get("run_id", run_dir.name)
    return record_library_feedback(
        run_dir,
        run_id=str(run_id),
        page_task_id=getattr(args, "page_task_id", ""),
        beat_id=getattr(args, "beat_id", ""),
        candidate_id=getattr(args, "candidate_id", ""),
        outcome=getattr(args, "outcome", ""),
        input_path=getattr(args, "input", None),
        apply=bool(getattr(args, "apply", False)),
    )


def command_build_learning_pack(args: argparse.Namespace) -> dict[str, Any]:
    return build_learning_pack(args.workspace)


def command_show_learning_pack(args: argparse.Namespace) -> dict[str, Any]:
    return show_learning_pack(args.workspace)


def command_validate_ppt_library_result(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"Bad JSON: {exc.msg}"], "warnings": []}
    return validate_ppt_library_result(result)


def command_validate_render_result(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"Bad JSON: {exc.msg}"], "warnings": []}
    return validate_render_result(result)


def command_validate_generation_result(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).expanduser().resolve()
    try:
        result = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"Bad JSON: {exc.msg}"], "warnings": []}
    run_dir = resolve_run_dir(args) if getattr(args, "run_dir", None) or getattr(args, "run_id", None) else None
    return validate_generation_result(result, run_dir=run_dir)


def command_summarize_run_metrics(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    metrics = summarize_run_metrics(run_dir)
    # Write run_metrics.json to run dir.
    out_path = Path(run_dir) / "run_metrics.json"
    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def command_uat_ppt_library(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser()
    if not input_path.is_absolute():
        input_path = run_dir / input_path
    return run_ppt_library_uat(
        run_dir,
        input_path.resolve(),
        require_screenshot=bool(getattr(args, "require_screenshot", False)),
        min_candidate_coverage=float(getattr(args, "min_candidate_coverage", 0.7)),
        min_screenshot_coverage=float(getattr(args, "min_screenshot_coverage", 0.8)),
        min_confidence=float(getattr(args, "min_confidence", 0.4)),
    )


def command_uat_generation_tool(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return run_generation_tool_uat(
        run_dir,
        tool=getattr(args, "tool", "ppt-deck-pro-max"),
        require_preview=bool(getattr(args, "require_preview", False)),
        require_artifact=bool(getattr(args, "require_artifact", False)),
        sample_limit=getattr(args, "sample_limit", None),
    )


def command_uat_render_tool(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    input_path = Path(args.input).expanduser() if getattr(args, "input", None) else None
    artifact_path = Path(args.artifact).expanduser() if getattr(args, "artifact", None) else None
    return run_render_tool_uat(
        run_dir,
        input_path=input_path,
        artifact_path=artifact_path,
        allow_external=bool(getattr(args, "allow_external", False)),
    )


def command_smoke_real_workflow(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return run_real_workflow_smoke(run_dir)


def command_validate_benchmark_case(args: argparse.Namespace) -> dict[str, Any]:
    case = load_benchmark_case(args.case, benchmark_dir=getattr(args, "benchmark_dir", None))
    return {
        "valid": True,
        "errors": [],
        "warnings": case.warnings,
        "case_id": case.data["case_id"],
        "case_path": str(case.path),
        "resolved_paths": {key: str(value) for key, value in case.resolved_paths.items()},
    }


def command_benchmark_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    payload = write_benchmark_checkpoint(
        run_dir,
        args.checkpoint,
        timestamp=getattr(args, "timestamp", None),
        note=getattr(args, "note", "") or "",
    )
    return {
        "status": "checkpoint_recorded",
        "run_id": payload["run_id"],
        "run_dir": str(run_dir),
        "checkpoint": args.checkpoint,
        "output": str(run_dir / "benchmark_checkpoints.json"),
    }


def command_benchmark_report(args: argparse.Namespace) -> dict[str, Any]:
    case = load_benchmark_case(args.case, benchmark_dir=getattr(args, "benchmark_dir", None))
    run_dir = resolve_run_dir(args)
    if bool(getattr(args, "rc_readiness", False)):
        _ensure_ready_for_benchmark(run_dir)
    pending_external_steps = collect_pending_external_steps(case, run_dir)
    return write_benchmark_report(
        case,
        run_dir,
        benchmark_dir=getattr(args, "benchmark_dir", None),
        force=bool(getattr(args, "force", False)),
        pending_external_steps=pending_external_steps,
    )


def _ensure_ready_for_benchmark(run_dir: Path) -> dict[str, Any]:
    state = resolve_run_state(
        run_dir,
        cli_workspace=None,
        run_mode=None,
        dev_allow_unsetup=False,
    )
    if state.get("stage") != "ready_for_benchmark":
        raise BenchmarkReportError(
            "benchmark readiness blocked. current stage is "
            f"{state.get('stage')} and expected ready_for_benchmark."
        )
    return state


def _is_fixture_benchmark_case(case: Any) -> bool:
    workflow = case.data.get("workflow", {}) if hasattr(case, "data") else {}
    if str(workflow.get("library_mode") or "").strip().lower() == "fixture":
        return True
    return str(case.data.get("case_id") or "").strip().endswith("_fixture")


def _ensure_rc_benchmark_boundary(case: Any, run_dir: Path) -> None:
    if _is_fixture_benchmark_case(case):
        raise BenchmarkReportError("benchmark RC report blocked: fixture cases cannot enter RC benchmark.")
    request = read_json(run_dir / REQUEST_NAME)
    run_mode = str(request.get("run_mode") or "").strip().lower()
    if run_mode != "benchmark":
        raise BenchmarkReportError(
            "benchmark RC report blocked: run_mode must be benchmark."
        )


def command_benchmark_rc_report(args: argparse.Namespace) -> dict[str, Any]:
    case = load_benchmark_case(args.case, benchmark_dir=getattr(args, "benchmark_dir", None))
    run_dir = resolve_run_dir(args)
    _ensure_rc_benchmark_boundary(case, run_dir)
    _ensure_ready_for_benchmark(run_dir)
    pending_external_steps = collect_pending_external_steps(case, run_dir)
    if pending_external_steps:
        steps = ", ".join(str(step.get("step") or "unknown") for step in pending_external_steps)
        raise BenchmarkReportError(
            "benchmark RC report blocked: pending external steps must be completed before RC report: "
            f"{steps}."
        )
    return write_benchmark_rc_report(
        case,
        run_dir,
        benchmark_dir=getattr(args, "benchmark_dir", None),
        force=bool(getattr(args, "force", False)),
        pending_external_steps=pending_external_steps,
    )


def command_benchmark_run(args: argparse.Namespace) -> dict[str, Any]:
    case = load_benchmark_case(args.case, benchmark_dir=getattr(args, "benchmark_dir", None))
    if getattr(args, "mode", "semi-auto") != "semi-auto":
        raise BenchmarkRunError("Only semi-auto benchmark mode is supported in v0.9.7.")
    run_dir, _pack = create_benchmark_run(
        case,
        run_id=getattr(args, "run_id", None),
        force=bool(getattr(args, "force_run", False)),
    )
    pipeline_steps = run_local_preview_pipeline(
        case,
        run_dir,
        command_funcs={
            "build_brief": command_build_brief,
            "build_claim_map": command_build_claim_map,
            "autoplan": command_autoplan,
            "quality_gate": command_quality_gate,
        },
    )
    summarize_and_write_metrics(run_dir)
    pending_external_steps = collect_pending_external_steps(case, run_dir)
    write_benchmark_run_summary(
        run_dir,
        case,
        pipeline_steps=pipeline_steps,
        pending_external_steps=pending_external_steps,
    )
    report = write_benchmark_report(
        case,
        run_dir,
        benchmark_dir=getattr(args, "benchmark_dir", None),
        force=bool(getattr(args, "force_report", False)),
        pending_external_steps=pending_external_steps,
    )
    return {
        "status": report["status"],
        "case_id": case.data["case_id"],
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "report": report["report"],
        "pending_external_steps": pending_external_steps,
    }


def command_benchmark_list(args: argparse.Namespace) -> dict[str, Any]:
    benchmark_dir = Path(args.benchmark_dir).expanduser().resolve()
    cases_dir = benchmark_dir / "cases"
    results_dir = benchmark_dir / "results"
    cases = []
    if cases_dir.exists():
        for case_path in sorted(cases_dir.glob("*/benchmark_case.json")):
            try:
                case = load_benchmark_case(case_path, benchmark_dir=benchmark_dir)
                cases.append({"case_id": case.data["case_id"], "case_name": case.data.get("case_name", ""), "path": str(case_path)})
            except BenchmarkCaseError as exc:
                cases.append({"case_id": case_path.parent.name, "path": str(case_path), "error": str(exc)})
    results = []
    if results_dir.exists():
        for report_path in sorted(results_dir.glob("*/*/benchmark_report.json")):
            results.append({
                "case_id": report_path.parent.parent.name,
                "run_id": report_path.parent.name,
                "report": str(report_path),
            })
    return {"status": "listed", "benchmark_dir": str(benchmark_dir), "cases": cases, "results": results}


def command_benchmark_aggregate_report(args: argparse.Namespace) -> dict[str, Any]:
    return write_benchmark_aggregate_report(
        getattr(args, "benchmark_dir", str(ROOT / "benchmarks")),
        min_real_cases=int(getattr(args, "min_real_cases", 3)),
        force=bool(getattr(args, "force", False)),
    )


def command_rc_gate(args: argparse.Namespace) -> dict[str, Any]:
    return write_rc_gate_report(
        getattr(args, "output_dir", str(ROOT / "rc_reports")),
        benchmark_dir=getattr(args, "benchmark_dir", str(ROOT / "benchmarks")),
        skip_browser_smoke=bool(getattr(args, "skip_browser_smoke", False)),
        require_browser_smoke=bool(getattr(args, "require_browser_smoke", False)),
        min_real_cases=int(getattr(args, "min_real_cases", 3)),
        force=bool(getattr(args, "force", False)),
    )


def command_preview_gate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(str(args.run_dir)).expanduser().resolve()
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, summary: str, details: dict[str, Any] | None = None) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if passed else "fail",
                "summary": summary,
                "details": details or {},
            }
        )

    add("run_dir_exists", run_dir.is_dir(), "Run directory exists.", {"run_dir": str(run_dir)})
    required_files = [
        "request.json",
        "narrative_plan.json",
        "page_tasks.json",
        "sourcing_plan.json",
        "preview_manifest.json",
    ]
    missing = [name for name in required_files if not (run_dir / name).exists()]
    add("required_files", not missing, "Fixture run has required planning and preview files.", {"missing": missing})

    page_count = 0
    unsafe_markers: list[str] = []
    manifest: dict[str, Any] = {}
    manifest_path = run_dir / "preview_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        pages = manifest.get("pages") if isinstance(manifest.get("pages"), list) else []
        page_count = len(pages)
        manifest_text = manifest_path.read_text(encoding="utf-8")
        markers = ("Users/", "home/", "placeholder", "真实客户", "客户名称", "售前", "internal", "agent")
        unsafe_markers = [marker for marker in markers if marker in manifest_text]
    add("preview_pages", page_count >= 10, "Preview manifest has at least 10 pages.", {"page_count": page_count})
    add("public_demo_safety", not unsafe_markers, "Preview manifest has no public-demo safety markers.", {"markers": unsafe_markers})

    preview_static = ROOT / "scripts" / "preview" / "static"
    static_required = ["index.html", "style.css", "app.js"]
    missing_static = [name for name in static_required if not (preview_static / name).exists()]
    add("review_desk_static", not missing_static, "Review Desk static assets are present.", {"missing": missing_static})

    backend = backend_status()
    dependencies = backend.get("external_dependency_status") if isinstance(backend.get("external_dependency_status"), list) else []
    dependency_statuses = {
        str(item.get("name") or ""): str(item.get("binding_status") or "")
        for item in dependencies
        if isinstance(item, dict)
    }
    bad_ready = [
        str(item.get("name") or "")
        for item in dependencies
        if isinstance(item, dict)
        and str(item.get("name") or "") == "ppt-master"
        and str(item.get("binding_status") or "") == "bound_verified"
        and not str(item.get("repo_path") or item.get("git_sha") or "").strip()
        and bool(getattr(args, "expect_unconfigured_backend_ok", False))
    ]
    add(
        "unconfigured_backend_not_ready",
        not bad_ready,
        "Unconfigured production dependencies do not report ready.",
        {"dependency_statuses": dependency_statuses, "unexpected_ready": bad_ready},
    )

    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    payload = {
        "schema_version": "deck_master_preview_gate.v1",
        "status": status,
        "run_dir": str(run_dir),
        "checks": checks,
        "preview_manifest": str(manifest_path),
        "title": str(manifest.get("title") or ""),
    }
    return _add_agent_output_contract(
        payload,
        next_agent_action=(
            "Proceed with Review Desk preview or release validation."
            if status == "pass"
            else "Fix failed preview-gate checks before treating the demo as ready."
        ),
        evidence_paths=[
            run_dir / "request.json",
            run_dir / "preview_manifest.json",
            ROOT / "scripts" / "preview" / "static" / "index.html",
            ROOT / "scripts" / "preview" / "static" / "style.css",
            ROOT / "scripts" / "preview" / "static" / "app.js",
        ],
    )


def add_brief_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--brief")
    parser.add_argument("--brief-file")
    parser.add_argument("--industry")
    parser.add_argument("--target-pages", default="auto")
    parser.add_argument("--audience", choices=["exec", "team", "client"], default="client")
    parser.add_argument("--style-preference", default="")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--workspace", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="production")


def add_conversation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default="")
    parser.add_argument("--context-file", action="append", required=True)
    parser.add_argument("--brief", default="")
    parser.add_argument("--industry")
    parser.add_argument("--target-pages", default="auto")
    parser.add_argument("--audience", choices=["exec", "team", "client"], default="client")
    parser.add_argument("--style-preference", default="")
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="production")


def add_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="production")
    parser.add_argument("--workspace", default="")


def add_library_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library-mode", choices=["auto", "real", "fixture"], default="auto")
    parser.add_argument("--ppt-lib-command", default="ppt-lib")
    parser.add_argument("--allow-fixture-library-fallback", action="store_true")


def add_planning_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--planning-mode", choices=["classic", "narrative_v2"], default="classic")


def add_planner_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--planner-mode",
        choices=["fixture_template", "workspace_fallback", "production_narrative"],
        default=None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck Master demand-to-preview orchestration CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup", help="Configure first-run Deck Master runtime")
    p_setup.add_argument("--workspace", default=None, help="Active Deck Master workspace")
    p_setup.add_argument("--runs-dir", default=None, help="Default runs directory")
    p_setup.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"], help="Agent skill target to validate")
    p_setup.add_argument("--review-cockpit-url", default=None)
    p_setup.add_argument("--repair-workspace", action="store_true", help="Create missing standard workspace directories and placeholder files")
    p_setup.add_argument("--install-suite", action="store_true", help="Build release tree and install required suite skill links")
    p_setup.set_defaults(func=command_setup)

    p_setup_status = sub.add_parser("setup-status", help="Check first-run Deck Master setup")
    p_setup_status.add_argument("--workspace", default=None)
    p_setup_status.add_argument("--run-dir", default=None)
    p_setup_status.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="production")
    p_setup_status.add_argument("--include-suite", action="store_true", help="Include Deck Master suite readiness")
    p_setup_status.add_argument("--output", choices=["json"], default="json")
    p_setup_status.set_defaults(func=command_setup_status)

    p_agent_doctor = sub.add_parser("agent-doctor", help="Check Agent-operable readiness")
    p_agent_doctor.add_argument("--mode", choices=["preview", "production"], default="preview")
    p_agent_doctor.add_argument("--run-dir", default=None)
    p_agent_doctor.add_argument("--workspace", default="")
    p_agent_doctor.add_argument("--release-root", default=None)
    p_agent_doctor.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"])
    p_agent_doctor.add_argument("--output", choices=["json"], default="json")
    p_agent_doctor.set_defaults(func=command_agent_doctor)

    p_suite_status = sub.add_parser("suite-status", help="Inspect Deck Master suite readiness without writing files")
    p_suite_status.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"])
    p_suite_status.add_argument("--output", choices=["json"], default="json")
    p_suite_status.set_defaults(func=command_suite_status)

    p_product_manifest = sub.add_parser("product-capability-manifest", help="Print Deck Master product capability manifest")
    p_product_manifest.add_argument("--output", choices=["json"], default="json")
    p_product_manifest.set_defaults(func=command_product_capability_manifest)

    p_validate_product_manifest = sub.add_parser("validate-product-capability-manifest", help="Validate Deck Master product capability manifest")
    p_validate_product_manifest.set_defaults(func=command_validate_product_capability_manifest)

    p_release_tree = sub.add_parser("suite-build-release-tree", help="Build Deck Master release tree")
    p_release_tree.add_argument("--output", required=True, help="Release tree output path")
    p_release_tree.add_argument("--force", action="store_true")
    p_release_tree.add_argument("--dry-run", action="store_true")
    p_release_tree.set_defaults(func=command_suite_build_release_tree)

    p_release_build = sub.add_parser("release-build", help="Build self-contained Deck Master release tree")
    p_release_build.add_argument("--output", required=True, help="Release tree output path")
    p_release_build.add_argument("--force", action="store_true")
    p_release_build.add_argument("--dry-run", action="store_true")
    p_release_build.set_defaults(func=command_suite_build_release_tree)

    p_release_smoke = sub.add_parser("release-smoke", help="Verify a Deck Master release tree")
    p_release_smoke.add_argument("--release-root", default=None, help="Release tree path; defaults to ~/.deck-master/current")
    p_release_smoke.add_argument("--no-smoke", action="store_true", help="Skip launching the release entrypoint")
    p_release_smoke.add_argument("--output", choices=["json"], default="json")
    p_release_smoke.set_defaults(func=command_release_smoke)

    p_release_install = sub.add_parser("release-install", help="Install Deck Master release tree via staging verification and activation")
    p_release_install.add_argument("--no-smoke", action="store_true", help="Skip launching the release entrypoint")
    p_release_install.set_defaults(func=command_release_install)

    p_release_rollback = sub.add_parser("release-rollback", help="Restore the previous Deck Master release tree")
    p_release_rollback.set_defaults(func=command_release_rollback)

    p_suite_install = sub.add_parser("suite-install", help="Install Deck Master suite skill links")
    p_suite_install.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"])
    p_suite_install.add_argument("--include-optional", action="store_true")
    p_suite_install.set_defaults(func=command_suite_install)

    p_suite_repair = sub.add_parser("suite-repair", help="Repair Deck Master suite symlinks without overwriting real directories")
    p_suite_repair.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"])
    p_suite_repair.add_argument("--include-optional", action="store_true")
    p_suite_repair.set_defaults(func=command_suite_repair)

    p_backend = sub.add_parser("backend", help="Manage external backend binding")
    backend_cmds = p_backend.add_subparsers(dest="backend_command", required=True)
    p_backend_bind = backend_cmds.add_parser("bind", help="Bind a backend dependency repo as the trusted source")
    p_backend_bind.add_argument("name", choices=["ppt-master"])
    p_backend_bind.add_argument("--repo", required=True, help="Path to backend dependency repository root")
    p_backend_bind.set_defaults(func=command_backend_bind)
    p_backend_status = backend_cmds.add_parser("status", help="Show backend dependency binding status")
    p_backend_status.set_defaults(func=command_backend_status)
    p_backend_verify = backend_cmds.add_parser("verify", help="Re-run certification on the bound backend dependency")
    p_backend_verify.add_argument("name", choices=["ppt-master"])
    p_backend_verify.set_defaults(func=command_backend_verify)
    p_backend_unbind = backend_cmds.add_parser("unbind", help="Unbind a backend dependency")
    p_backend_unbind.add_argument("name", choices=["ppt-master"])
    p_backend_unbind.set_defaults(func=command_backend_unbind)

    p_suite_migrate = sub.add_parser("suite-migrate-legacy-skills", help="Plan, apply, or rollback legacy skill directory migration")
    p_suite_migrate.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"])
    p_suite_migrate.add_argument("--agent-skill-dir", default=None)
    p_suite_migrate.add_argument("--plan", action="store_true")
    p_suite_migrate.add_argument("--apply", action="store_true")
    p_suite_migrate.add_argument("--plan-file", default="")
    p_suite_migrate.add_argument("--rollback", action="store_true")
    p_suite_migrate.add_argument("--rollback-id", default="")
    p_suite_migrate.set_defaults(func=command_suite_migrate_legacy_skills)

    p_doctor = sub.add_parser("doctor", help="Show setup and run state diagnostics")
    p_doctor.add_argument("--workspace", default="")
    p_doctor.add_argument("--run-dir", default=None)
    p_doctor.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="production")
    p_doctor.set_defaults(func=command_doctor)

    p_run_state = sub.add_parser("run-state", help="Resolve canonical run state")
    add_run_args(p_run_state)
    p_run_state.set_defaults(func=command_run_state)

    p_plan = sub.add_parser("plan", help="Create request.json and narrative_plan.json from a brief")
    add_brief_args(p_plan)
    add_planning_mode_arg(p_plan)
    add_planner_mode_arg(p_plan)
    p_plan.set_defaults(func=command_plan)

    p_start = sub.add_parser("start-conversation", help="Create a guided Deck conversation run from local context")
    add_conversation_args(p_start)
    p_start.set_defaults(func=command_start_conversation)

    p_start_entry = sub.add_parser("start", help="Show Deck Master setup, run state, and next action")
    add_run_args(p_start_entry)
    p_start_entry.set_defaults(func=command_start)

    p_brief = sub.add_parser("build-brief", help="Compile deck_brief.json from context and conversation")
    add_run_args(p_brief)
    p_brief.set_defaults(func=command_build_brief)

    p_claim = sub.add_parser("build-claim-map", help="Compile claim_map.json from deck_brief.json")
    add_run_args(p_claim)
    p_claim.set_defaults(func=command_build_claim_map)

    p_autoplan = sub.add_parser("autoplan", help="Run brief intake through preview manifest")
    add_brief_args(p_autoplan)
    add_library_args(p_autoplan)
    add_planning_mode_arg(p_autoplan)
    add_planner_mode_arg(p_autoplan)
    p_autoplan.set_defaults(func=command_autoplan)

    def add_autopilot_parser(name: str) -> None:
        p_workflow = sub.add_parser(name, help="Advance a Deck Master workflow until a safe stop condition")
        add_run_args(p_workflow)
        add_library_args(p_workflow)
        add_planning_mode_arg(p_workflow)
        add_planner_mode_arg(p_workflow)
        p_workflow.add_argument("--mode", choices=["quick", "production", "repair", "review-only"], default="quick")
        p_workflow.add_argument("--max-steps", type=int, default=8)
        p_workflow.set_defaults(func=command_workflow_autopilot)

    add_autopilot_parser("workflow-autopilot")
    add_autopilot_parser("autopilot-v1")

    p_search = sub.add_parser("search-library", help="Run PPT Library selection for an existing run")
    add_run_args(p_search)
    add_library_args(p_search)
    p_search.set_defaults(func=command_search_library)

    p_library_status = sub.add_parser("library-status", help="Inspect PPT Library readiness without writing files")
    p_library_status.add_argument("--workspace", default="")
    p_library_status.add_argument("--output", choices=["json"], default="json")
    p_library_status.set_defaults(func=command_library_status)

    p_import_library = sub.add_parser("import-library-selection", help="Import PPT Library selection handback")
    add_run_args(p_import_library)
    p_import_library.add_argument("--input", required=True, help="Path to deck_master_ppt_library_selection.v1 JSON")
    p_import_library.set_defaults(func=command_import_library_selection)

    p_decide = sub.add_parser("decide-sourcing", help="Create sourcing_plan.json from library results")
    add_run_args(p_decide)
    p_decide.set_defaults(func=command_decide_sourcing)

    p_tasks = sub.add_parser("create-generation-tasks", help="Create Deck Pro Max task packages")
    add_run_args(p_tasks)
    p_tasks.set_defaults(func=command_create_generation_tasks)

    p_preview = sub.add_parser("build-preview", help="Build preview_manifest.json from sourcing decisions")
    add_run_args(p_preview)
    p_preview.set_defaults(func=command_build_preview)

    p_export = sub.add_parser("export", help="Export approved page queue")
    add_run_args(p_export)
    p_export.add_argument("--output")
    p_export.add_argument("--decision", action="append", default=["approved"])
    p_export.add_argument("--queue-type", choices=["client", "internal"], default="client")
    p_export.add_argument("--allow-quality-override", action="store_true")
    p_export.set_defaults(func=command_export)

    p_final_readiness = sub.add_parser("final-readiness", help="Compute final client readiness")
    add_run_args(p_final_readiness)
    p_final_readiness.add_argument("--artifact", help="Final artifact path. Defaults to render_result artifact_path.")
    p_final_readiness.add_argument("--expected-pages", type=int, default=None, help="Expected final page count")
    p_final_readiness.add_argument("--no-write", action="store_true", help="Return readiness without writing final_readiness.json")
    p_final_readiness.set_defaults(func=command_final_readiness)

    p_quality = sub.add_parser("quality-gate", help="Run a Deck Master quality gate")
    add_run_args(p_quality)
    p_quality.add_argument(
        "gate",
        choices=[
            "draft",
            "draft_v2",
            "render",
            "delivery",
            "customer-visible-safety",
            "customer_visible_safety",
            "evidence",
            "context-conflict",
            "confidentiality",
            "brand",
        ],
    )
    p_quality.add_argument("--artifact", help="Rendered or final PPTX artifact for render/delivery/brand gates")
    p_quality.add_argument("--expected-pages", type=int)
    p_quality.add_argument("--forbidden", action="append", default=[], help="Forbidden visible term. Can be repeated.")
    p_quality.set_defaults(func=command_quality_gate)

    p_override = sub.add_parser("override", help="Manage quality finding overrides")
    override_sub = p_override.add_subparsers(dest="override_command", required=True)

    p_oc = override_sub.add_parser("create", help="Create a quality override")
    add_run_args(p_oc)
    p_oc.add_argument("--finding-id", required=True)
    p_oc.add_argument("--severity", required=True, choices=["P1", "P2"])
    p_oc.add_argument("--reason", required=True)
    p_oc.add_argument("--approver", required=True)
    p_oc.add_argument("--scope", default="client_export")
    p_oc.add_argument("--actor", default="user")
    p_oc.add_argument("--expires-days", type=int, default=14)
    p_oc.set_defaults(func=command_override_create)

    p_ol = override_sub.add_parser("list", help="List active overrides")
    add_run_args(p_ol)
    p_ol.set_defaults(func=command_override_list)

    p_or = override_sub.add_parser("revoke", help="Revoke an override")
    add_run_args(p_or)
    p_or.add_argument("--override-id", required=True)
    p_or.add_argument("--reason", default="")
    p_or.set_defaults(func=command_override_revoke)

    p_next = sub.add_parser("next-step", help="Resolve next step for a run")
    add_run_args(p_next)
    p_next.set_defaults(func=command_next_step)

    p_route_skill = sub.add_parser("route-skill", help="Resolve the recommended Deck Master skill")
    p_route_skill.add_argument("--input-type", default="", help="Known input type such as raw_materials or approved_preview")
    p_route_skill.add_argument("--next-command", default="", help="Optional command to include in route output")
    add_run_args(p_route_skill)
    p_route_skill.set_defaults(func=command_route_skill)

    # --- Skill OS workflow group (A5) ---
    p_workflow_os = sub.add_parser("workflow", help="Skill OS workflow runtime: stages, handoffs, approvals, preauthorization")
    wf_sub = p_workflow_os.add_subparsers(dest="workflow_command", required=True)

    p_wf_status = wf_sub.add_parser("status", help="Resolve the contract workflow state for a run")
    add_run_args(p_wf_status)
    p_wf_status.set_defaults(func=command_workflow_status)

    p_wf_stages = wf_sub.add_parser("stages", help="List per-stage contract status")
    add_run_args(p_wf_stages)
    p_wf_stages.set_defaults(func=command_workflow_stages)

    # handoff
    p_wf_h = wf_sub.add_parser("handoff", help="Stage handoff runtime")
    h_sub = p_wf_h.add_subparsers(dest="handoff_command", required=True)

    p_wf_h_prep = h_sub.add_parser("prepare", help="Prepare an append-only handoff for a stage (exit-validated)")
    add_run_args(p_wf_h_prep)
    p_wf_h_prep.add_argument("--from-stage", required=True)
    p_wf_h_prep.add_argument("--created-by", default="")
    p_wf_h_prep.set_defaults(func=command_workflow_handoff_prepare)

    p_wf_h_list = h_sub.add_parser("list", help="List handoffs")
    add_run_args(p_wf_h_list)
    p_wf_h_list.set_defaults(func=command_workflow_handoff_list)

    p_wf_h_acc = h_sub.add_parser("accept", help="Accept an awaiting-approval handoff")
    add_run_args(p_wf_h_acc)
    p_wf_h_acc.add_argument("--handoff-id", required=True)
    p_wf_h_acc.add_argument("--actor-id", default="cli")
    p_wf_h_acc.add_argument("--actor-role", default="operator")
    p_wf_h_acc.set_defaults(func=command_workflow_handoff_accept)

    p_wf_h_con = h_sub.add_parser("consume", help="Mark an accepted handoff as consumed")
    add_run_args(p_wf_h_con)
    p_wf_h_con.add_argument("--handoff-id", required=True)
    p_wf_h_con.set_defaults(func=command_workflow_handoff_consume)

    p_wf_h_rej = h_sub.add_parser("reject", help="Reject a handoff and route repair")
    add_run_args(p_wf_h_rej)
    p_wf_h_rej.add_argument("--handoff-id", required=True)
    p_wf_h_rej.add_argument("--reason", required=True)
    p_wf_h_rej.add_argument("--repair-owner-stage", default="")
    p_wf_h_rej.add_argument("--actor-id", default="cli")
    p_wf_h_rej.add_argument("--actor-role", default="operator")
    p_wf_h_rej.set_defaults(func=command_workflow_handoff_reject)

    # approval
    p_wf_a = wf_sub.add_parser("approval", help="Transition approval runtime")
    a_sub = p_wf_a.add_subparsers(dest="approval_command", required=True)

    p_wf_a_req = a_sub.add_parser("request", help="Open a pending approval bound to a handoff")
    add_run_args(p_wf_a_req)
    p_wf_a_req.add_argument("--handoff-id", required=True)
    p_wf_a_req.add_argument("--actor-id", default="cli")
    p_wf_a_req.add_argument("--actor-role", default="requester")
    p_wf_a_req.set_defaults(func=command_workflow_approval_request)

    p_wf_a_app = a_sub.add_parser("approve", help="Approve a pending approval (human)")
    add_run_args(p_wf_a_app)
    p_wf_a_app.add_argument("--approval-id", required=True)
    p_wf_a_app.add_argument("--actor-id", default="cli")
    p_wf_a_app.add_argument("--actor-role", default="approver")
    p_wf_a_app.add_argument("--preauthorization-id", default="")
    p_wf_a_app.set_defaults(func=command_workflow_approval_approve)

    p_wf_a_rej = a_sub.add_parser("reject", help="Reject a pending approval with repair routing")
    add_run_args(p_wf_a_rej)
    p_wf_a_rej.add_argument("--approval-id", required=True)
    p_wf_a_rej.add_argument("--reason", required=True)
    p_wf_a_rej.add_argument("--repair-owner-stage", default="")
    p_wf_a_rej.add_argument("--actor-id", default="cli")
    p_wf_a_rej.add_argument("--actor-role", default="approver")
    p_wf_a_rej.set_defaults(func=command_workflow_approval_reject)

    p_wf_a_list = a_sub.add_parser("list", help="List approvals")
    add_run_args(p_wf_a_list)
    p_wf_a_list.set_defaults(func=command_workflow_approval_list)

    p_wf_a_st = a_sub.add_parser("status", help="Check whether a transition's approval gate is cleared")
    add_run_args(p_wf_a_st)
    p_wf_a_st.add_argument("--from-stage", required=True)
    p_wf_a_st.set_defaults(func=command_workflow_approval_status)

    # preauthorization
    p_wf_p = wf_sub.add_parser("preauth", help="Explicit transition preauthorization (D10)")
    pre_sub = p_wf_p.add_subparsers(dest="preauth_command", required=True)

    p_wf_p_cr = pre_sub.add_parser("create", help="Create a scoped preauthorization")
    add_run_args(p_wf_p_cr)
    p_wf_p_cr.add_argument("--mode", required=True, choices=["interactive", "preauthorized", "quick", "repair", "review-only"])
    p_wf_p_cr.add_argument("--allowed-transitions", required=True, help="Comma-separated transition keys, e.g. deck-brief->deck-planner")
    p_wf_p_cr.add_argument("--actor-id", default="cli")
    p_wf_p_cr.add_argument("--actor-role", default="operator")
    p_wf_p_cr.add_argument("--material-roots", default="")
    p_wf_p_cr.add_argument("--max-generated-pages", type=int, default=0)
    p_wf_p_cr.add_argument("--max-cost-class", default="low", choices=["none", "low", "medium", "high"])
    p_wf_p_cr.add_argument("--ttl-seconds", type=int, default=3600)
    p_wf_p_cr.set_defaults(func=command_workflow_preauth_create)

    p_wf_p_ls = pre_sub.add_parser("list", help="List preauthorizations")
    add_run_args(p_wf_p_ls)
    p_wf_p_ls.set_defaults(func=command_workflow_preauth_list)

    p_wf_p_rv = pre_sub.add_parser("revoke", help="Revoke a preauthorization")
    add_run_args(p_wf_p_rv)
    p_wf_p_rv.add_argument("--policy-id", required=True)
    p_wf_p_rv.add_argument("--actor-id", default="cli")
    p_wf_p_rv.add_argument("--actor-role", default="operator")
    p_wf_p_rv.set_defaults(func=command_workflow_preauth_revoke)

    p_wf_ap = wf_sub.add_parser("autopilot", help="Run the contract-aware, approval-aware workflow executor (v2)")
    add_run_args(p_wf_ap)
    p_wf_ap.add_argument("--mode", required=True, choices=["interactive", "preauthorized", "quick", "repair", "review-only"])
    p_wf_ap.add_argument("--max-steps", type=int, default=8)
    p_wf_ap.add_argument("--repair-owner-stage", default="")
    p_wf_ap.set_defaults(func=command_workflow_autopilot_v2)

    p_orchestration = sub.add_parser("orchestration-check", help="Check run orchestration completeness")
    add_run_args(p_orchestration)
    p_orchestration.set_defaults(func=command_orchestration_check)

    p_bind_workspace = sub.add_parser("bind-workspace", help="Bind an existing run to a workspace")
    p_bind_workspace.add_argument("--run-dir")
    p_bind_workspace.add_argument("--run-id")
    p_bind_workspace.add_argument("--runs-dir", default=None)
    p_bind_workspace.add_argument("--workspace", required=True)
    p_bind_workspace.add_argument("--reason", required=True)
    p_bind_workspace.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)
    p_bind_workspace.add_argument("--run-mode", choices=["production", "fixture", "dev", "benchmark"], default="fixture")
    p_bind_workspace.set_defaults(func=command_bind_workspace)

    p_judgments = sub.add_parser("build-judgments", help="Generate consulting judgments")
    add_run_args(p_judgments)
    p_judgments.set_defaults(func=command_build_judgments)

    p_ceg = sub.add_parser("build-claim-graph", help="Build claim-evidence graph")
    add_run_args(p_ceg)
    p_ceg.set_defaults(func=command_build_claim_graph)

    p_init_ws = sub.add_parser("init-workspace", help="Initialize a new Deck workspace")
    p_init_ws.add_argument("--workspace", required=True, help="Workspace directory path")
    p_init_ws.add_argument("--name", required=True, help="Workspace name")
    p_init_ws.set_defaults(func=command_init_workspace)

    p_init_project = sub.add_parser("init-project", help="Initialize a Deck Master project workspace")
    p_init_project.add_argument("--workspace", required=True, help="Workspace directory path")
    p_init_project.add_argument("--name", required=True, help="Project name")
    p_init_project.set_defaults(func=command_init_project)

    p_reg_ws = sub.add_parser("register-workspace", help="Register an existing workspace")
    p_reg_ws.add_argument("--workspace", required=True, help="Workspace directory path")
    p_reg_ws.add_argument("--reference-ppt", default=None, help="Reference PPTX file path")
    p_reg_ws.set_defaults(func=command_register_workspace)

    p_val_ws = sub.add_parser("validate-workspace", help="Validate workspace integrity")
    p_val_ws.add_argument("--workspace", required=True, help="Workspace directory path")
    p_val_ws.set_defaults(func=command_validate_workspace)

    # ---- delivery subcommands ----
    p_delivery = sub.add_parser("delivery", help="Delivery validation and outcome tracking")
    delivery_sub = p_delivery.add_subparsers(dest="delivery_command", required=True)

    p_dv = delivery_sub.add_parser("validate", help="Validate final delivery artifact")
    add_run_args(p_dv)
    p_dv.add_argument("--artifact", required=True, help="Path to final PPTX artifact")
    p_dv.add_argument("--expected-pages", type=int, default=None, help="Expected page count")
    p_dv.set_defaults(func=command_delivery_validate)

    p_dro = delivery_sub.add_parser("record-outcome", help="Record delivery outcome")
    add_run_args(p_dro)
    p_dro.add_argument("--delivered", action="store_true", help="Mark as delivered")
    p_dro.add_argument("--advanced-to-next-stage", action="store_true", help="Advanced to next stage")
    p_dro.add_argument("--customer-reaction", default="")
    p_dro.add_argument("--notes", default="")
    p_dro.set_defaults(func=command_delivery_record_outcome)

    # ---- opportunity subcommands ----
    p_opportunity = sub.add_parser("opportunity", help="Manage opportunities")
    opp_sub = p_opportunity.add_subparsers(dest="opportunity_command", required=True)

    p_oc_opp = opp_sub.add_parser("create", help="Create a new opportunity")
    p_oc_opp.add_argument("--workspace", required=True, help="Workspace directory path")
    p_oc_opp.add_argument("--client-name", required=True)
    p_oc_opp.add_argument("--industry", required=True)
    p_oc_opp.set_defaults(func=command_opportunity_create)

    p_ar = opp_sub.add_parser("attach-run", help="Attach a run to an opportunity")
    p_ar.add_argument("--workspace", required=True, help="Workspace directory path")
    p_ar.add_argument("--opportunity-id", required=True)
    p_ar.add_argument("--run-id", required=True)
    p_ar.set_defaults(func=command_opportunity_attach_run)

    # ---- approval subcommands ----
    p_approval = sub.add_parser("approval", help="Manage approval flows")
    approval_sub = p_approval.add_subparsers(dest="approval_command", required=True)

    p_as = approval_sub.add_parser("submit", help="Submit a run for approval")
    p_as.add_argument("--workspace", required=True, help="Workspace directory path")
    p_as.add_argument("--run-id", required=True)
    p_as.add_argument("--submitted-by", required=True)
    p_as.add_argument("--notes", default="")
    p_as.set_defaults(func=command_approval_submit)

    p_aa = approval_sub.add_parser("approve", help="Approve a pending approval")
    p_aa.add_argument("--workspace", required=True, help="Workspace directory path")
    p_aa.add_argument("--approval-id", required=True)
    p_aa.add_argument("--approver", required=True)
    p_aa.add_argument("--notes", default="")
    p_aa.set_defaults(func=command_approval_approve)

    p_aj = approval_sub.add_parser("reject", help="Reject a pending approval")
    p_aj.add_argument("--workspace", required=True, help="Workspace directory path")
    p_aj.add_argument("--approval-id", required=True)
    p_aj.add_argument("--rejecter", required=True)
    p_aj.add_argument("--reason", default="")
    p_aj.set_defaults(func=command_approval_reject)

    # ---- connector subcommands ----
    p_connector = sub.add_parser("connector", help="Import data from external systems")
    conn_sub = p_connector.add_subparsers(dest="connector_command", required=True)

    p_ci = conn_sub.add_parser("import", help="Import a connector manifest into context_manifest.json")
    p_ci.add_argument("--manifest", required=True, help="Path to connector import manifest JSON")
    p_ci.add_argument("--base-dir", default="", help="Base directory for resolving source file paths")
    p_ci.add_argument("--output", default=None, help="Write output context manifest to this path")
    p_ci.set_defaults(func=command_connector_import)

    # ---- skill management ----
    p_install = sub.add_parser("install-skill", help="Install Deck Master skill into an Agent skill directory")
    p_install.add_argument("--target", action="append", required=True, choices=["codex", "claude-code", "hermes", "custom"])
    p_install.add_argument("--agent-skill-dir", default=None, help="Agent skill directory (required for custom target)")
    p_install.add_argument("--source-skill-dir", default=None, help="Deck Master skill source directory (defaults to ~/.deck-master/current/skills/deck-master)")
    p_install.add_argument("--force", action="store_true", help="Replace existing symlink")
    p_install.add_argument("--suite", action="store_true", help="Install suite skill links")
    p_install.add_argument("--include-optional", action="store_true", help="Include optional companion skills when using --suite")
    p_install.set_defaults(func=command_install_skill)

    p_validate_skill = sub.add_parser("validate-skill", help="Validate Deck Master skill symlink")
    p_validate_skill.add_argument("--target", required=True, choices=["codex", "claude-code", "hermes", "custom"])
    p_validate_skill.add_argument("--agent-skill-dir", default=None)
    p_validate_skill.add_argument("--source-skill-dir", default=None)
    p_validate_skill.set_defaults(func=command_validate_skill)

    p_uninstall = sub.add_parser("uninstall-skill", help="Remove Deck Master skill symlink")
    p_uninstall.add_argument("--target", required=True, choices=["codex", "claude-code", "hermes", "custom"])
    p_uninstall.add_argument("--agent-skill-dir", default=None)
    p_uninstall.add_argument("--source-skill-dir", default=None)
    p_uninstall.set_defaults(func=command_uninstall_skill)

    p_import_plan = sub.add_parser("import-plan", help="Import a human or Agent plan override into a run")
    add_run_args(p_import_plan)
    p_import_plan.add_argument("--input", required=True, help="Path to plan Markdown or JSON")
    p_import_plan.add_argument("--source", required=True, choices=["human", "agent"])
    p_import_plan.set_defaults(func=command_import_plan)

    p_build = sub.add_parser("build", help="Prepare, run, or inspect production build artifacts")
    build_sub = p_build.add_subparsers(dest="build_command", required=True)

    p_build_prepare = build_sub.add_parser("prepare", help="Write build manifest from current preview manifest")
    add_run_args(p_build_prepare)
    p_build_prepare.set_defaults(func=command_build_prepare)

    p_build_run = build_sub.add_parser("run", help="Build HTML/PDF/PNG/PPTX artifacts")
    add_run_args(p_build_run)
    p_build_run.set_defaults(func=command_build_run)

    p_build_status = build_sub.add_parser("status", help="Inspect production build artifacts")
    add_run_args(p_build_status)
    p_build_status.set_defaults(func=command_build_status)

    p_render = sub.add_parser("render", help="Render a run through the bundled PPT Master path")
    add_run_args(p_render)
    p_render.add_argument("--format", choices=["html"], default="html")
    p_render.add_argument("--fixture-safe", action="store_true", help="Allow provider-free fixture render output")
    p_render.set_defaults(func=command_render)

    p_render_status = sub.add_parser("render-status", help="Inspect canonical or legacy render result")
    add_run_args(p_render_status)
    p_render_status.set_defaults(func=command_render_status)

    p_import_render = sub.add_parser("import-render-result", help="Import PPT Master or renderer handback result")
    add_run_args(p_import_render)
    p_import_render.add_argument("--input", required=True, help="Path to render result JSON")
    p_import_render.set_defaults(func=command_import_render_result)

    p_import_sourcing = sub.add_parser("import-sourcing", help="Import a JSON sourcing plan override into a run")
    add_run_args(p_import_sourcing)
    p_import_sourcing.add_argument("--input", required=True, help="Path to sourcing plan JSON")
    p_import_sourcing.add_argument("--source", required=True, choices=["human", "agent"])
    p_import_sourcing.set_defaults(func=command_import_sourcing)

    p_validate_sourcing = sub.add_parser("validate-sourcing", help="Validate current sourcing_plan.json")
    add_run_args(p_validate_sourcing)
    p_validate_sourcing.set_defaults(func=command_validate_sourcing)

    # ---- context pack ----
    p_icp = sub.add_parser("import-context-pack", help="Import an Agent-generated context pack into a run")
    add_run_args(p_icp)
    p_icp.add_argument("--input", required=True, help="Path to context pack JSON")
    p_icp.add_argument("--merge", action="store_true", help="Update existing sources by source_id instead of rejecting duplicates")
    p_icp.set_defaults(func=command_import_context_pack)

    p_crcp = sub.add_parser("create-run-from-context-pack", help="Create a new run from a context pack")
    p_crcp.add_argument("--workspace", required=True, help="Workspace directory path")
    p_crcp.add_argument("--input", required=True, help="Path to context pack JSON")
    p_crcp.add_argument("--run-id", default=None)
    p_crcp.add_argument("--industry", default="")
    p_crcp.add_argument("--audience", choices=["exec", "team", "client"], default="client")
    p_crcp.add_argument("--runs-dir", default=None)
    p_crcp.set_defaults(func=command_create_run_from_context_pack)

    # ---- narrative advisory ----
    p_pna = sub.add_parser("prepare-narrative-advice", help="Generate a narrative advice task for an Agent")
    add_run_args(p_pna)
    p_pna.set_defaults(func=command_prepare_narrative_advice)

    p_ina = sub.add_parser("import-narrative-advice", help="Import Agent narrative advice result")
    add_run_args(p_ina)
    p_ina.add_argument("--input", required=True, help="Path to narrative advice JSON")
    p_ina.set_defaults(func=command_import_narrative_advice)

    p_ana = sub.add_parser("apply-narrative-advice", help="Apply narrative advice to run artifacts")
    add_run_args(p_ana)
    p_ana.add_argument("--input", required=True, help="Path to narrative advice JSON")
    p_ana.add_argument("--dry-run", action="store_true", help="Generate diff only, do not modify artifacts")
    p_ana.add_argument("--apply", default=None, help="Comma-separated sections: core-thesis,page-recommendations,risks")
    p_ana.set_defaults(func=command_apply_narrative_advice)

    # ---- external quality review ----
    p_pqr = sub.add_parser("prepare-quality-review", help="Generate external quality review task for an Agent")
    add_run_args(p_pqr)
    p_pqr.add_argument("--scope", default="semantic", help="Comma-separated scopes: semantic,visual,evidence,client-readiness")
    p_pqr.set_defaults(func=command_prepare_quality_review)

    p_iqr = sub.add_parser("import-quality-review", help="Import external quality review result")
    add_run_args(p_iqr)
    p_iqr.add_argument("--input", required=True, help="Path to external quality review JSON")
    p_iqr.add_argument("--replace", action="store_true", help="Replace existing report from same reviewer/scope")
    p_iqr.set_defaults(func=command_import_quality_review)

    p_iqf = sub.add_parser("import-quality-findings", help="Import PPT Quality Gate findings handback")
    add_run_args(p_iqf)
    p_iqf.add_argument("--input", required=True, help="Path to deck_master_quality_findings.v1 JSON")
    p_iqf.add_argument("--replace", action="store_true", help="Replace existing report from same reviewer/scope")
    p_iqf.set_defaults(func=command_import_quality_findings)

    # ---- generation handoff / handback ----
    p_pgh = sub.add_parser("prepare-generation-handoff", help="Enhance generation tasks with handoff fields for build tools")
    add_run_args(p_pgh)
    p_pgh.set_defaults(func=command_prepare_generation_handoff)

    p_igr = sub.add_parser("import-generation-result", help="Import generation result from a build tool")
    add_run_args(p_igr)
    p_igr.add_argument("--input", required=True, help="Path to generation result JSON")
    p_igr.add_argument("--force", action="store_true", help="Override locked pages")
    p_igr.set_defaults(func=command_import_generation_result)

    p_rpg = sub.add_parser("refresh-preview-from-generation", help="Update preview manifest from generation results")
    add_run_args(p_rpg)
    p_rpg.set_defaults(func=command_refresh_preview_from_generation)

    p_gs = sub.add_parser("generation-session", help="Manage generation sessions")
    gs_sub = p_gs.add_subparsers(dest="generation_session_command", required=True)

    p_gs_create = gs_sub.add_parser("create", help="Create generation_session.json for a run")
    add_run_args(p_gs_create)
    p_gs_create.add_argument("--tool", default="ppt-deck-pro-max")
    p_gs_create.add_argument("--tool-command", default=None, help="Override tool command directly")
    p_gs_create.add_argument("--force", action="store_true", help="Recreate session if exists")
    p_gs_create.set_defaults(func=command_generation_session_create)

    p_gs_validate = gs_sub.add_parser("validate", help="Validate generation session and tool availability")
    add_run_args(p_gs_validate)
    p_gs_validate.add_argument("--tool", default=None)
    p_gs_validate.add_argument("--tool-command", default=None, help="Override tool command directly")
    p_gs_validate.set_defaults(func=command_generation_session_validate)

    p_gs_status = gs_sub.add_parser("status", help="Read generation session status")
    add_run_args(p_gs_status)
    p_gs_status.add_argument("--tool", default=None)
    p_gs_status.add_argument("--tool-command", default=None, help="Override tool command directly")
    p_gs_status.set_defaults(func=command_generation_session_status)

    p_gs_dispatch = gs_sub.add_parser("dispatch", help="Write Agent dispatch package without launching an executor")
    add_run_args(p_gs_dispatch)
    p_gs_dispatch.add_argument("--tool", default="ppt-deck-pro-max")
    p_gs_dispatch.add_argument("--tool-command", default=None, help="Override tool command directly")
    p_gs_dispatch.set_defaults(func=command_generation_session_dispatch)

    p_gs_import = gs_sub.add_parser("import-results", help="Import generation result and refresh preview manifest")
    add_run_args(p_gs_import)
    p_gs_import.add_argument("--input", required=True, help="Path to generation result JSON")
    p_gs_import.add_argument("--force", action="store_true", help="Override locked pages")
    p_gs_import.set_defaults(func=command_generation_session_import_results)

    p_rg = sub.add_parser("run-generation", help="Run the production generation tool")
    add_run_args(p_rg)
    p_rg.add_argument("--tool", default="ppt-deck-pro-max")
    p_rg.add_argument("--tool-command", default=None, help="Override tool command directly")
    p_rg.add_argument("--dry-run", action="store_true")
    p_rg.add_argument("--no-execute", action="store_true")
    p_rg.set_defaults(func=command_run_generation)

    p_rlf = sub.add_parser("record-library-feedback", help="Queue PPT Library feedback event inside a run")
    add_run_args(p_rlf)
    p_rlf.add_argument("--page-task-id", default="")
    p_rlf.add_argument("--beat-id", default="")
    p_rlf.add_argument("--candidate-id", default="")
    p_rlf.add_argument("--outcome", default="")
    p_rlf.add_argument("--input", default=None, help="Path to library feedback JSON")
    p_rlf.add_argument("--dry-run", action="store_true", help="Write only the run-local feedback event queue")
    p_rlf.add_argument("--apply", action="store_true", help="Experimental: apply feedback to external library")
    p_rlf.set_defaults(func=command_record_library_feedback)

    # ---- workspace learning ----
    p_blp = sub.add_parser("build-learning-pack", help="Aggregate workspace learning for next Agent run")
    p_blp.add_argument("--workspace", required=True, help="Workspace directory path")
    p_blp.set_defaults(func=command_build_learning_pack)

    p_slp = sub.add_parser("show-learning-pack", help="Show existing workspace learning pack")
    p_slp.add_argument("--workspace", required=True, help="Workspace directory path")
    p_slp.set_defaults(func=command_show_learning_pack)

    # ---- companion tool validators ----
    p_vplr = sub.add_parser("validate-ppt-library-result", help="Validate PPT Library candidate result")
    p_vplr.add_argument("--input", required=True, help="Path to library result JSON")
    p_vplr.set_defaults(func=command_validate_ppt_library_result)

    p_vgr = sub.add_parser("validate-generation-result", help="Validate generation result")
    add_run_args(p_vgr)
    p_vgr.add_argument("--input", required=True, help="Path to generation result JSON")
    p_vgr.set_defaults(func=command_validate_generation_result)

    p_vrr = sub.add_parser("validate-render-result", help="Validate PPT Master render result")
    p_vrr.add_argument("--input", required=True, help="Path to render result JSON")
    p_vrr.set_defaults(func=command_validate_render_result)

    # ---- metrics ----
    p_srm = sub.add_parser("summarize-run-metrics", help="Compute run metrics from events and artifacts")
    add_run_args(p_srm)
    p_srm.set_defaults(func=command_summarize_run_metrics)

    # ---- v0.9.6 companion tool UAT ----
    p_upl = sub.add_parser("uat-ppt-library", help="Run PPT Library selection UAT")
    add_run_args(p_upl)
    p_upl.add_argument("--input", required=True, help="Path to library selection JSON")
    p_upl.add_argument("--require-screenshot", action="store_true")
    p_upl.add_argument("--min-candidate-coverage", type=float, default=0.7)
    p_upl.add_argument("--min-screenshot-coverage", type=float, default=0.8)
    p_upl.add_argument("--min-confidence", type=float, default=0.4)
    p_upl.set_defaults(func=command_uat_ppt_library)

    p_ugt = sub.add_parser("uat-generation-tool", help="Run generation tool handoff/handback UAT")
    add_run_args(p_ugt)
    p_ugt.add_argument("--tool", default="ppt-deck-pro-max")
    p_ugt.add_argument("--require-preview", action="store_true")
    p_ugt.add_argument("--require-artifact", action="store_true")
    p_ugt.add_argument("--sample-limit", type=int)
    p_ugt.set_defaults(func=command_uat_generation_tool)

    p_urt = sub.add_parser("uat-render-tool", help="Run render tool artifact UAT")
    add_run_args(p_urt)
    p_urt.add_argument("--input", help="Path to render result JSON")
    p_urt.add_argument("--artifact", help="Path to final artifact")
    p_urt.add_argument("--allow-external", action="store_true")
    p_urt.set_defaults(func=command_uat_render_tool)

    p_srw = sub.add_parser("smoke-real-workflow", help="Run real workflow smoke for a Deck run")
    add_run_args(p_srw)
    p_srw.set_defaults(func=command_smoke_real_workflow)

    # ---- v0.9.7 benchmark harness ----
    p_vbc = sub.add_parser("validate-benchmark-case", help="Validate a benchmark case")
    p_vbc.add_argument("--case", required=True, help="Path to benchmark_case.json")
    p_vbc.add_argument("--benchmark-dir", default=None)
    p_vbc.set_defaults(func=command_validate_benchmark_case)

    p_brn = sub.add_parser("benchmark-run", help="Run a local semi-auto benchmark")
    p_brn.add_argument("--case", required=True, help="Path to benchmark_case.json")
    p_brn.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_brn.add_argument("--mode", choices=["semi-auto"], default="semi-auto")
    p_brn.add_argument("--run-id", default=None)
    p_brn.add_argument("--force-run", action="store_true", help="Replace an existing run with the same run id")
    p_brn.add_argument("--force-report", action="store_true", help="Replace an existing benchmark report")
    p_brn.set_defaults(func=command_benchmark_run)

    p_brep = sub.add_parser("benchmark-report", help="Build a benchmark report from an existing run")
    add_run_args(p_brep)
    p_brep.add_argument("--case", required=True, help="Path to benchmark_case.json")
    p_brep.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_brep.add_argument("--force", action="store_true", help="Replace an existing benchmark report")
    p_brep.add_argument(
        "--rc-readiness",
        action="store_true",
        help="Require run_state stage ready_for_benchmark before generating report.",
    )
    p_brep.set_defaults(func=command_benchmark_report)

    p_brr = sub.add_parser("benchmark-rc-report", help="Build RC benchmark report after ready_for_benchmark")
    add_run_args(p_brr)
    p_brr.add_argument("--case", required=True, help="Path to benchmark_case.json")
    p_brr.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_brr.add_argument("--force", action="store_true", help="Replace an existing RC benchmark report")
    p_brr.set_defaults(func=command_benchmark_rc_report)

    p_bcp = sub.add_parser("benchmark-checkpoint", help="Record a benchmark checkpoint")
    add_run_args(p_bcp)
    p_bcp.add_argument(
        "--checkpoint",
        required=True,
        choices=[
            "context_ready",
            "preview_ready",
            "human_review_started",
            "human_review_completed",
            "approved_queue_ready",
            "final_delivery_ready",
        ],
    )
    p_bcp.add_argument("--timestamp", default=None)
    p_bcp.add_argument("--note", default="")
    p_bcp.set_defaults(func=command_benchmark_checkpoint)

    p_blist = sub.add_parser("benchmark-list", help="List benchmark cases and reports")
    p_blist.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_blist.set_defaults(func=command_benchmark_list)

    p_bagg = sub.add_parser("benchmark-aggregate-report", help="Build aggregate benchmark report")
    p_bagg.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_bagg.add_argument("--min-real-cases", type=int, default=3)
    p_bagg.add_argument("--force", action="store_true")
    p_bagg.set_defaults(func=command_benchmark_aggregate_report)

    p_rc_gate = sub.add_parser("rc-gate", help="Run Deck Master release-candidate gate")
    p_rc_gate.add_argument("--output-dir", default=str(ROOT / "rc_reports"))
    p_rc_gate.add_argument("--benchmark-dir", default=str(ROOT / "benchmarks"))
    p_rc_gate.add_argument("--min-real-cases", type=int, default=3)
    p_rc_gate.add_argument("--skip-browser-smoke", action="store_true")
    p_rc_gate.add_argument("--require-browser-smoke", action="store_true")
    p_rc_gate.add_argument("--force", action="store_true")
    p_rc_gate.set_defaults(func=command_rc_gate)

    p_preview_gate = sub.add_parser("preview-gate", help="Run Deck Master Technical Preview gate")
    p_preview_gate.add_argument("--run-dir", required=True)
    p_preview_gate.add_argument("--expect-unconfigured-backend-ok", action="store_true")
    p_preview_gate.set_defaults(func=command_preview_gate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command in PROTECTED_COMMANDS:
            require_setup_ready(
                dev_allow_unsetup=_dev_allow_unsetup(args),
                workspace=_workspace_for_setup_guard(args),
                run_mode=_normalize_run_mode(getattr(args, "run_mode", None)),
            )
        result = args.func(args)
        print_json(result)
        if args.command == "preview-gate" and isinstance(result, dict) and result.get("status") != "pass":
            raise SystemExit(2)
    except (
        RunStateError,
        PPTLibraryClientError,
        WorkspaceError,
        SkillInstallError,
        SetupError,
        ContextPackError,
        GenerationSessionError,
        NarrativeAdviceError,
        ExternalReviewError,
        GenerationHandbackError,
        BenchmarkCaseError,
        BenchmarkAggregateError,
        BenchmarkCheckpointError,
        BenchmarkReportError,
        BenchmarkRunError,
        RCGateError,
        HandoffError,
        ApprovalError,
        PolicyError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
