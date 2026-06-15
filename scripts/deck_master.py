from __future__ import annotations

import argparse
import json
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
    prepare_quality_review,
)
from generation.handback import (
    GenerationHandbackError,
    import_generation_result,
    prepare_generation_handoff,
    refresh_preview_from_generation,
    validate_generation_result,
)
from learning.pack import build_learning_pack, show_learning_pack
from validators.companion_tools import validate_ppt_library_result, validate_render_result
from metrics.run_metrics import summarize_run_metrics
from uat.generation_tool import run_generation_tool_uat
from uat.ppt_library import run_ppt_library_uat
from uat.real_workflow_smoke import run_real_workflow_smoke
from uat.render_tool import run_render_tool_uat
from benchmark.case import BenchmarkCaseError, load_benchmark_case
from benchmark.checkpoints import BenchmarkCheckpointError, write_benchmark_checkpoint
from benchmark.report import BenchmarkReportError, write_benchmark_report
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
from quality.draft_gate_v2 import evaluate_draft_gate_v2
from quality.evidence_gate import evaluate_evidence_gate
from quality.context_conflict_gate import evaluate_context_conflict_gate
from quality.confidentiality_gate import evaluate_confidentiality_gate
from quality.brand_gate import evaluate_brand_gate
from quality.overrides import create_override, list_active_overrides, revoke_override
from delivery.validate import validate_delivery
from delivery.outcome import record_delivery_outcome
from team.opportunity import create_opportunity, attach_run
from team.approval import submit_approval, approve, reject
from connectors.import_contract import validate_import_manifest, import_to_context_manifest
from skills.installer import SkillInstallError, install_skill, validate_skill, uninstall_skill
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    CONVERSATION_SESSION_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    create_run,
    load_request,
    read_json,
    write_artifact,
    write_json,
)
from runtime.next_step import resolve_next_step
from runtime.orchestration import import_plan, import_render_result, orchestration_check
from tools.ppt_library_client import PPTLibraryClientError, run_library_selection
from workspace.foundation import WorkspaceError, init_workspace, register_workspace, validate_workspace
from runtime.setup_status import SetupError, configured_runs_dir, require_setup_ready, run_setup, setup_status


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_COMMANDS = {
    "plan",
    "start-conversation",
    "build-brief",
    "build-claim-map",
    "autoplan",
    "search-library",
    "decide-sourcing",
    "create-generation-tasks",
    "build-preview",
    "export",
    "quality-gate",
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
    "prepare-generation-handoff",
    "import-generation-result",
    "refresh-preview-from-generation",
    "import-plan",
    "import-render-result",
    "summarize-run-metrics",
    "uat-ppt-library",
    "uat-generation-tool",
    "uat-render-tool",
    "smoke-real-workflow",
    "benchmark-run",
    "benchmark-report",
    "benchmark-checkpoint",
    "delivery",
}


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


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
) -> dict[str, Any]:
    claim_map = read_optional_json(run_dir, CLAIM_MAP_NAME)
    judgments: dict[str, Any] | None = None
    claim_graph: dict[str, Any] | None = None
    workspace_archetypes: dict[str, Any] | None = None

    if planning_mode == "narrative_v2":
        judgments = _build_judgments_if_possible(run_dir, request, claim_map)
        workspace_archetypes = _load_workspace_archetypes(request)

    narrative_plan = plan_narrative(
        request,
        judgments=judgments,
        claim_graph=claim_graph,
        workspace_archetypes=workspace_archetypes,
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
    request = build_request(
        brief=args.brief or "",
        brief_file=args.brief_file,
        industry=args.industry or "",
        target_pages=args.target_pages,
        audience=args.audience,
        style_preference=args.style_preference or "",
        run_id=args.run_id or "",
    )
    run_dir = create_run(runs_dir(args), request, run_id=args.run_id or None, force=args.force)
    request = load_request(run_dir)
    narrative_plan = write_plan_artifacts(
        run_dir,
        request,
        planning_mode=getattr(args, "planning_mode", "classic"),
    )
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "planned", "pages": len(narrative_plan["beats"])}


def command_start_conversation(args: argparse.Namespace) -> dict[str, Any]:
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
    if args.workspace:
        request["workspace"] = str(Path(args.workspace).expanduser().resolve())
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
    )
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "library_ready", "source": results.get("source", "")}


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
    queue = export_queue(
        run_dir,
        set(args.decision),
        queue_type=getattr(args, "queue_type", "client"),
        allow_quality_override=getattr(args, "allow_quality_override", False),
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
    else:
        output = run_dir / "approved_queue.json"
    write_json(output, queue)
    return {"run_id": queue["run_id"], "run_dir": str(run_dir), "status": "exported", "output": str(output), "pages": len(queue["pages"]), "blocked": queue["blocked_count"]}


def command_autoplan(args: argparse.Namespace) -> dict[str, Any]:
    existing_run = bool((getattr(args, "run_id", None) or getattr(args, "run_dir", None)) and not (args.brief or args.brief_file))
    planning_mode = getattr(args, "planning_mode", "classic")
    if existing_run:
        run_dir = resolve_run_dir(args)
        request = load_request(run_dir)
        needs_plan = not artifact_exists(run_dir, NARRATIVE_PLAN_NAME)
        needs_v2_artifacts = planning_mode == "narrative_v2" and (
            not artifact_exists(run_dir, "consulting_judgments.json")
            or not artifact_exists(run_dir, "claim_evidence_graph.json")
        )
        if needs_plan or needs_v2_artifacts:
            write_plan_artifacts(run_dir, request, planning_mode=planning_mode)
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
        report = evaluate_delivery_gate(run_id, args.artifact, expected_pages=expected_pages, forbidden_terms=args.forbidden)
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

    paths = write_gate_report(run_dir, args.gate, report)
    write_artifact(
        run_dir,
        f"quality_reports/{args.gate}_gate.index.json",
        {"report": paths, "status": report["status"], "blocks_delivery": report["blocks_delivery"]},
        action=f"quality.{args.gate}_gate.created",
    )
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "gate": args.gate,
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
    return resolve_next_step(run_dir)


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
    return run_setup(
        workspace=getattr(args, "workspace", None),
        runs_dir=getattr(args, "runs_dir", None),
        targets=getattr(args, "target", None),
        review_cockpit_url=getattr(args, "review_cockpit_url", None) or "http://127.0.0.1:5050",
        repair=bool(getattr(args, "repair_workspace", False)),
    )


def command_setup_status(args: argparse.Namespace) -> dict[str, Any]:
    return setup_status(workspace=getattr(args, "workspace", None))


def command_install_skill(args: argparse.Namespace) -> dict[str, Any]:
    return install_skill(
        target=args.target,
        agent_skill_dir=getattr(args, "agent_skill_dir", None),
        force=getattr(args, "force", False),
        source_skill_dir=getattr(args, "source_skill_dir", None),
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
    return orchestration_check(resolve_run_dir(args))


def command_import_plan(args: argparse.Namespace) -> dict[str, Any]:
    return import_plan(resolve_run_dir(args), args.input, source=args.source)


def command_import_render_result(args: argparse.Namespace) -> dict[str, Any]:
    return import_render_result(resolve_run_dir(args), args.input)


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
    return import_generation_result(run_dir, result, force=force)


def command_refresh_preview_from_generation(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = resolve_run_dir(args)
    return refresh_preview_from_generation(run_dir)


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
    return validate_generation_result(result)


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
    pending_external_steps = collect_pending_external_steps(case, run_dir)
    return write_benchmark_report(
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
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)


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


def add_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--dev-allow-unsetup", action="store_true", help=argparse.SUPPRESS)


def add_library_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library-mode", choices=["auto", "real", "fixture"], default="auto")
    parser.add_argument("--ppt-lib-command", default="ppt-lib")


def add_planning_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--planning-mode", choices=["classic", "narrative_v2"], default="classic")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck Master demand-to-preview orchestration CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup", help="Configure first-run Deck Master runtime")
    p_setup.add_argument("--workspace", default=None, help="Active Deck Master workspace")
    p_setup.add_argument("--runs-dir", default=None, help="Default runs directory")
    p_setup.add_argument("--target", action="append", default=[], choices=["codex", "claude-code", "hermes"], help="Agent skill target to validate")
    p_setup.add_argument("--review-cockpit-url", default="http://127.0.0.1:5050")
    p_setup.add_argument("--repair-workspace", action="store_true", help="Create missing standard workspace directories and placeholder files")
    p_setup.set_defaults(func=command_setup)

    p_setup_status = sub.add_parser("setup-status", help="Check first-run Deck Master setup")
    p_setup_status.add_argument("--workspace", default=None)
    p_setup_status.set_defaults(func=command_setup_status)

    p_plan = sub.add_parser("plan", help="Create request.json and narrative_plan.json from a brief")
    add_brief_args(p_plan)
    add_planning_mode_arg(p_plan)
    p_plan.set_defaults(func=command_plan)

    p_start = sub.add_parser("start-conversation", help="Create a guided Deck conversation run from local context")
    add_conversation_args(p_start)
    p_start.set_defaults(func=command_start_conversation)

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
    p_autoplan.set_defaults(func=command_autoplan)

    p_search = sub.add_parser("search-library", help="Run PPT Library selection for an existing run")
    add_run_args(p_search)
    add_library_args(p_search)
    p_search.set_defaults(func=command_search_library)

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

    p_quality = sub.add_parser("quality-gate", help="Run a Deck Master quality gate")
    add_run_args(p_quality)
    p_quality.add_argument(
        "gate",
        choices=["draft", "draft_v2", "render", "delivery", "evidence", "context-conflict", "confidentiality", "brand"],
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

    p_orchestration = sub.add_parser("orchestration-check", help="Check run orchestration completeness")
    add_run_args(p_orchestration)
    p_orchestration.set_defaults(func=command_orchestration_check)

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
    p_install.add_argument("--target", required=True, choices=["codex", "claude-code", "hermes", "custom"])
    p_install.add_argument("--agent-skill-dir", default=None, help="Agent skill directory (required for custom target)")
    p_install.add_argument("--source-skill-dir", default=None, help="Deck Master skill source directory (defaults to ~/.deck-master/current/skills/deck-master)")
    p_install.add_argument("--force", action="store_true", help="Replace existing symlink")
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

    p_import_render = sub.add_parser("import-render-result", help="Import PPT Master or renderer handback result")
    add_run_args(p_import_render)
    p_import_render.add_argument("--input", required=True, help="Path to render result JSON")
    p_import_render.set_defaults(func=command_import_render_result)

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
    p_brep.set_defaults(func=command_benchmark_report)

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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command in PROTECTED_COMMANDS:
            require_setup_ready(
                dev_allow_unsetup=bool(getattr(args, "dev_allow_unsetup", False)),
                workspace=_workspace_for_setup_guard(args),
            )
        print_json(args.func(args))
    except (
        RunStateError,
        PPTLibraryClientError,
        WorkspaceError,
        SkillInstallError,
        SetupError,
        ContextPackError,
        NarrativeAdviceError,
        ExternalReviewError,
        GenerationHandbackError,
        BenchmarkCaseError,
        BenchmarkCheckpointError,
        BenchmarkReportError,
        BenchmarkRunError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
