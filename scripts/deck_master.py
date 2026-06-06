from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from generation.task_builder import create_generation_tasks
from orchestrate.export_queue import export_queue
from orchestrate.preview_builder import build_preview_from_sourcing
from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from planning.sourcing_decider import decide_sourcing, load_library_results
from runtime.run_state import (
    NARRATIVE_PLAN_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    create_run,
    load_request,
    read_json,
    write_artifact,
    write_json,
)
from tools.ppt_library_client import PPTLibraryClientError, run_library_selection


ROOT = Path(__file__).resolve().parents[1]


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def runs_dir(args: argparse.Namespace) -> Path:
    return Path(args.runs_dir).expanduser().resolve()


def resolve_run_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "run_dir", None):
        return Path(args.run_dir).expanduser().resolve()
    if getattr(args, "run_id", None):
        return runs_dir(args) / args.run_id
    raise RunStateError("--run-dir or --run-id is required.")


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
    narrative_plan = plan_narrative(request)
    write_artifact(run_dir, NARRATIVE_PLAN_NAME, narrative_plan, action="narrative.plan.created")
    return {"run_id": request["run_id"], "run_dir": str(run_dir), "status": "planned", "pages": len(narrative_plan["beats"])}


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
    queue = export_queue(run_dir, set(args.decision))
    if args.output:
        output = Path(args.output).expanduser().resolve()
    else:
        output = run_dir / "approved_queue.json"
    write_json(output, queue)
    return {"run_id": queue["run_id"], "run_dir": str(run_dir), "status": "exported", "output": str(output), "pages": len(queue["pages"])}


def command_autoplan(args: argparse.Namespace) -> dict[str, Any]:
    plan_result = command_plan(args)
    run_dir = Path(plan_result["run_dir"])
    args.run_dir = str(run_dir)
    command_search_library(args)
    command_decide_sourcing(args)
    command_create_generation_tasks(args)
    preview_result = command_build_preview(args)
    return preview_result | {"status": "autoplan_preview_ready"}


def add_brief_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--brief")
    parser.add_argument("--brief-file")
    parser.add_argument("--industry")
    parser.add_argument("--target-pages", default="auto")
    parser.add_argument("--audience", choices=["exec", "team", "client"], default="client")
    parser.add_argument("--style-preference", default="")
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", default=str(ROOT / "runs"))
    parser.add_argument("--force", action="store_true")


def add_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", default=str(ROOT / "runs"))


def add_library_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library-mode", choices=["auto", "real", "fixture"], default="auto")
    parser.add_argument("--ppt-lib-command", default="ppt-lib")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck Master demand-to-preview orchestration CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Create request.json and narrative_plan.json from a brief")
    add_brief_args(p_plan)
    p_plan.set_defaults(func=command_plan)

    p_autoplan = sub.add_parser("autoplan", help="Run brief intake through preview manifest")
    add_brief_args(p_autoplan)
    add_library_args(p_autoplan)
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
    p_export.set_defaults(func=command_export)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        print_json(args.func(args))
    except (RunStateError, PPTLibraryClientError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
