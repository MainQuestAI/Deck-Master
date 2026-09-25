"""Rebuilt CLI (spec 09.1–09.4).

One small command surface backed by service use cases; every command supports
``--json`` (the Host default). Exit codes follow 09.3: 0 local action done
(read ``status`` for deck state), 2 invalid input, 3 awaiting host/tool,
4 execution failure, 5 conflict/late result with current unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
import subprocess
from pathlib import Path
from typing import Any

from .compiler.svg import SvgError
from . import __version__
from . import service
from .models import ModelError
from .service import ServiceError
from .store import StoreError, ConflictError
from .tasks import EnvelopeError, TaskConflict


def _emit(payload: dict[str, Any]) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=1, default=str)
    sys.stdout.write("\n")
    return 0


def _error(code: str, message: str, next_action: str, field: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "field": field, "next_action": next_action}}


def _fail(exc: Exception) -> int:
    from .pipeline import NeedsTool

    error_code = getattr(exc, "error_code", None)
    if error_code is not None:
        from .errors import NEXT_ACTIONS_BY_CODE

        return _emit_and_exit(
            _error(error_code, str(exc), NEXT_ACTIONS_BY_CODE.get(error_code, "follow the named recovery"),
                   field=getattr(exc, "path", None)),
            getattr(exc, "exit_code", 2),
        )
    if isinstance(exc, NeedsTool):
        return _emit_and_exit(_error("needs_tool", str(exc), "configure the reported tool"), 3)
    if isinstance(exc, (EnvelopeError, ModelError, ServiceError, SvgError)):
        return _emit_and_exit(_error("invalid_input", str(exc), "fix the named field"), 2)
    if isinstance(exc, (TaskConflict, ConflictError)):
        return _emit_and_exit(_error("conflict", str(exc), "rebase or read new inputs"), 5)
    if isinstance(exc, FileNotFoundError):
        return _emit_and_exit(_error("invalid_input", str(exc), "check the path"), 2)
    return _emit_and_exit(_error("execution_failed", str(exc), "inspect the failure detail"), 4)


def _emit_and_exit(payload: dict, code: int) -> int:
    json.dump(payload, sys.stderr, ensure_ascii=False, indent=1, default=str)
    sys.stderr.write("\n")
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deck-master", description="Deck Master rebuilt core")
    parser.add_argument("--version", action="version", version=f"deck-master {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--step", choices=("compose","blueprint","compile","render","view","export"), default="view")
    doctor.add_argument("--font", action="append", default=[])
    doctor.add_argument("--host-imagegen", action="store_true", help="Host reports tool availability; not provider verification")

    sub.add_parser("legacy-map", help="List every pre-rebuild command and its mapping class (spec 09.6)")

    installation=sub.add_parser('install')
    installs=installation.add_subparsers(dest='install_command',required=True)
    candidate=installs.add_parser('candidate');candidate.add_argument('--prefix',required=True);candidate.add_argument('--manifest',required=True)
    activation=installs.add_parser('activate');activation.add_argument('--prefix',required=True);activation.add_argument('--release-id',required=True)
    rollback=installs.add_parser('rollback');rollback.add_argument('--prefix',required=True)

    create = sub.add_parser("create")
    create.add_argument("--brief", required=False, help="task brief text (or --brief-file)")
    create.add_argument("--brief-file", required=False)
    create.add_argument("--title", default="")
    create.add_argument("--source", action="append", default=[],
                        help="material file or directory; directories are expanded recursively")
    create.add_argument("--out", required=True)
    create.add_argument("--design", default=None)
    create.add_argument("--draft", default=None, help="complete draft JSON to import")
    create.add_argument("--no-open", action="store_true")
    create.add_argument("--audience", default=None, help="who must understand or decide what")
    create.add_argument("--scenario", default=None, help="the exchange scenario")
    create.add_argument("--presentation-mode", dest="presentation_mode",
                        choices=("live", "read_alone", "mixed"), default=None,
                        help="live/read_alone/mixed; defaults live without claiming user choice")
    create.add_argument("--page-limit", dest="page_limit", type=int, default=None,
                        help="maximum page count, not a target")
    create.add_argument("--decision", action="append", default=None,
                        help="a user-confirmed decision; repeatable, always the full effective set")
    create.add_argument("--task-file", dest="task_file", default=None,
                        help="JSON object carrying the task facts (spec v1.1 3.1 fields)")

    continue_cmd = sub.add_parser("continue")
    continue_cmd.add_argument("--project", required=True)
    continue_cmd.add_argument("--no-open", action="store_true")

    inputs_cmd = sub.add_parser("inputs")
    inputs_sub = inputs_cmd.add_subparsers(dest="inputs_command", required=True)
    inputs_show_parser = inputs_sub.add_parser("show")
    inputs_show_parser.add_argument("--project", required=True)
    inputs_update_parser = inputs_sub.add_parser("update")
    inputs_update_parser.add_argument("--project", required=True)
    inputs_update_parser.add_argument("--patch", required=True,
                                      help="patch JSON; paths inside resolve against this file's directory")
    inputs_update_parser.add_argument("--base-revision", dest="base_revision", required=True)
    inputs_update_parser.add_argument("--operation-id", dest="operation_id", required=True)

    view_cmd = sub.add_parser("view")
    view_cmd.add_argument("--project", required=True)
    view_cmd.add_argument("--open", action="store_true", default=False)
    view_cmd.add_argument("--no-open", action="store_true")
    view_cmd.add_argument("--json", dest="as_json", action="store_true")

    import_draft = sub.add_parser("import-draft")
    import_draft.add_argument("--project", required=True)
    import_draft.add_argument("--input", required=True)

    import_asset = sub.add_parser("import")
    import_asset.add_argument("--project", required=True)
    import_asset.add_argument("asset", nargs="?", default=None)
    import_asset.add_argument("--asset-id")
    import_asset.add_argument("--kind")
    import_asset.add_argument("--file")
    import_asset.add_argument("--external-use", default="allowed")

    accept = sub.add_parser("task")
    task_sub = accept.add_subparsers(dest="task_command", required=True)

    accept_parser = task_sub.add_parser("accept")
    accept_parser.add_argument("--project", required=True)
    accept_parser.add_argument("--task-id", required=True)
    accept_parser.add_argument("--operation-id", required=True)
    accept_parser.add_argument("--produced-against", required=True)
    accept_parser.add_argument("--result", required=True)

    start_parser = task_sub.add_parser("start")
    start_parser.add_argument("--project", required=True)
    start_parser.add_argument("--task-id", required=True)
    start_parser.add_argument("--execution-ref", required=True)

    status_parser = task_sub.add_parser("status")
    status_parser.add_argument("--project", required=True)
    status_parser.add_argument("--task-id", required=True)

    cancel_parser = task_sub.add_parser("cancel")
    cancel_parser.add_argument("--project", required=True)
    cancel_parser.add_argument("--task-id", required=True)
    cancel_parser.add_argument("--reason", default="")

    call_parser = task_sub.add_parser("call")
    call_sub = call_parser.add_subparsers(dest="call_command", required=True)
    allocate = call_sub.add_parser("allocate")
    allocate.add_argument("--project", required=True)
    allocate.add_argument("--task-id", required=True)
    allocate.add_argument("--count", type=int, default=1)
    begin = call_sub.add_parser("begin")
    begin.add_argument("--project", required=True)
    begin.add_argument("--task-id", required=True)
    begin.add_argument("--allowance-id", required=True)
    begin.add_argument("--execution-ref", default=None)
    settle = call_sub.add_parser("settle")
    settle.add_argument("--project", required=True)
    settle.add_argument("--task-id", required=True)
    settle.add_argument("--allowance-id", required=True)
    settle.add_argument("--outcome", required=True, choices=["consumed", "not_sent", "unknown"])
    settle.add_argument("--report", default=None)
    settle.add_argument("--invocation-ref", default=None)

    build = sub.add_parser('build')
    build.add_argument('--project', required=True)
    edit = sub.add_parser('edit')
    edit.add_argument('--project', required=True)
    edit.add_argument('--page', required=True, help='complete updated Page JSON')
    edit.add_argument('--base-revision', required=True)
    edit.add_argument('--page-hash', required=True)
    edit.add_argument('--operation-id', required=True)
    export = sub.add_parser('export')
    export.add_argument('--project', required=True)
    export.add_argument('--out', required=True)
    export.add_argument('--purpose', choices=['review','working','delivery'], default='review')
    handoff = sub.add_parser('handoff-check')
    handoff.add_argument('--project', required=True)
    handoff.add_argument('--file', required=True)
    handoff.add_argument('--purpose', choices=['review','delivery'], default='review')
    history = sub.add_parser('history')
    history_sub = history.add_subparsers(dest='history_command', required=True)
    history_list = history_sub.add_parser('list')
    history_list.add_argument('--project', required=True)
    history_restore = history_sub.add_parser('restore')
    history_restore.add_argument('--project', required=True)
    history_restore.add_argument('--revision', required=True)
    history_restore.add_argument('--base-revision', required=True)
    history_restore.add_argument('--operation-id', required=True)
    # JSON is the default; retain an explicit switch on every executable leaf.
    def json_switch(command):
        if not any('--json' in action.option_strings for action in command._actions):
            command.add_argument('--json', action='store_true')
        for action in command._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    json_switch(child)
    json_switch(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 2 and argv[0] == 'import' and argv[1] == 'legacy' and \
            any(flag in argv[2:] for flag in ('--input', '--out', '--inspect')):
        return _dispatch_import_legacy(argv[2:])
    legacy = _legacy_dispatch(argv)
    if legacy is not None:
        return legacy
    parser = build_parser()
    options = parser.parse_args(argv)
    try:
        if options.command == 'legacy-map':
            return _emit(legacy_mapping_table())
        if options.command == 'install':
            from .install import install_candidate,activate,rollback
            try:
                if options.install_command=='candidate':result=install_candidate(options.prefix,options.manifest)
                elif options.install_command=='activate':result=activate(options.prefix,options.release_id)
                else:result=rollback(options.prefix)
            except ValueError as exc:
                return _emit_and_exit(_error('invalid_input',str(exc),'check candidate and prefix'),2)
            return _emit(result)
        if options.command == 'doctor':
            from .doctor import diagnose
            result=diagnose(options.step,fonts=options.font,host_imagegen=options.host_imagegen)
            _emit(result)
            return 0 if result['status']=='ready' else 3
        if options.command == 'history':
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .editing import history, restore
            if options.history_command == 'list':
                return _emit(history(options.project))
            return _emit(restore(options.project,revision_id=options.revision,base_revision=options.base_revision,operation_id=options.operation_id))
        if options.command == 'build':
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .pipeline import produce
            return _emit(produce(options.project))
        if options.command == 'edit':
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .editing import edit_page
            return _emit(edit_page(options.project,page=json.loads(Path(options.page).read_text()),base_revision=options.base_revision,page_hash=options.page_hash,operation_id=options.operation_id))
        if options.command == 'export':
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .editing import export_project
            return _emit(export_project(options.project,output_dir=options.out,purpose=options.purpose))
        if options.command == 'handoff-check':
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .handoff import check_handoff
            result = check_handoff(options.project, file_path=options.file, purpose=options.purpose)
            _emit(result)
            return 0 if result['status'] == 'verified' else 3
        if options.command == "create":
            rejected = _reject_legacy_run(options.out, '--out')
            if rejected is not None:
                return rejected
            design = None
            if options.design:
                design = json.loads(open(options.design, encoding="utf-8").read())
            draft = None
            if options.draft:
                draft = json.loads(open(options.draft, encoding="utf-8").read())
            task_fields = _merge_task_fields(options)
            payload = service.create(
                options.out,
                brief=task_fields["brief"],
                title=task_fields.get("title") or "",
                sources=options.source,
                design=design,
                draft=draft,
                audience=task_fields.get("audience") or "",
                scenario=task_fields.get("scenario") or "",
                presentation_mode=task_fields.get("presentation_mode"),
                page_limit=task_fields.get("page_limit"),
                existing_decisions=task_fields.get("existing_decisions"),
            )
            if _project_has_pages(options.out):
                payload = _attach_workbench_url(options.out, payload)
            return _emit(payload)
        if options.command == "continue":
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            payload = service.continue_project(options.project)
            _emit(payload)
            return 3 if payload["status"] in ("awaiting_host", "needs_tool", "needs_input") else 0
        if options.command == "inputs":
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            if options.inputs_command == "show":
                return _emit(service.inputs_show(options.project))
            patch_path = Path(options.patch).expanduser()
            payload = service.inputs_update(
                options.project,
                patch=json.loads(patch_path.read_text(encoding="utf-8")),
                base_revision=options.base_revision,
                operation_id=options.operation_id,
                patch_dir=patch_path.parent,
            )
            if _project_has_pages(options.project):
                payload = _attach_workbench_url(options.project, payload)
            return _emit(payload)
        if options.command == "import-draft":
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            payload = service.import_draft(options.project, draft_path=options.input)
            if _project_has_pages(options.project):
                payload = _attach_workbench_url(options.project, payload)
            return _emit(payload)
        if options.command == "view":
            rejected = _reject_legacy_run(options.project)
            if rejected is not None:
                return rejected
            from .web import open_view, service_status

            if options.open:
                return _emit(open_view(options.project, open_browser=not options.no_open))
            return _emit(service_status(options.project))
        if options.command == "import":
            return _emit(
                service.import_asset(
                    options.project,
                    asset_id=options.asset_id or options.asset,
                    kind=options.kind or "logo",
                    file_path=options.file,
                    external_use=options.external_use,
                )
            )
        if options.command == "task":
            return _dispatch_task(options)
    except (EnvelopeError, ModelError, ServiceError, TaskConflict, FileNotFoundError, StoreError) as exc:
        return _fail(exc)
    except json.JSONDecodeError as exc:
        return _emit_and_exit(_error("invalid_input", f"unreadable JSON input: {exc}", "fix the JSON file"), 2)
    except SvgError as exc:
        return _fail(exc)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        return _fail(exc)
    return 2


TASK_FILE_FIELDS = {"title", "brief", "audience", "scenario", "presentation_mode",
                    "page_limit", "existing_decisions"}


def _load_task_file(path: str) -> dict:
    from .errors import TaskFieldConflict

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaskFieldConflict("(task-file)", f"task file is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise TaskFieldConflict("(task-file)", "task file must be a JSON object")
    unknown = sorted(set(raw) - TASK_FILE_FIELDS)
    if unknown:
        raise TaskFieldConflict("(task-file)", f"unknown task fields: {unknown}")
    if "presentation_mode" in raw and raw["presentation_mode"] not in ("live", "read_alone", "mixed"):
        raise TaskFieldConflict("(task-file)/presentation_mode", "must be live, read_alone or mixed")
    if "page_limit" in raw and raw["page_limit"] is not None and \
            (not isinstance(raw["page_limit"], int) or isinstance(raw["page_limit"], bool)
             or raw["page_limit"] < 1):
        raise TaskFieldConflict("(task-file)/page_limit", "must be a positive integer or null")
    if "existing_decisions" in raw and (
            not isinstance(raw["existing_decisions"], list)
            or not all(isinstance(item, str) for item in raw["existing_decisions"])):
        raise TaskFieldConflict("(task-file)/existing_decisions", "must be an array of strings")
    for field in ("title", "brief", "audience", "scenario"):
        if field in raw and not isinstance(raw[field], str):
            raise TaskFieldConflict(f"(task-file)/{field}", "must be a string")
    return raw


def _merge_task_fields(options) -> dict:
    """Merge CLI task facts with --task-file (spec v1.1 §3.2).

    Explicit CLI scalars win; absent flags never overwrite file values with
    argparse defaults. ``--decision`` and file decisions are rejected
    together instead of being concatenated.
    """
    from .errors import TaskFieldConflict

    file_fields = _load_task_file(options.task_file) if options.task_file else {}
    if options.brief and options.brief_file:
        raise TaskFieldConflict("(brief)", "--brief and --brief-file are mutually exclusive")
    if options.decision is not None and "existing_decisions" in file_fields:
        raise TaskFieldConflict(
            "(decision)",
            "--decision and task-file existing_decisions cannot both be provided; "
            "decisions are always the full effective set",
        )

    if options.brief_file:
        brief = Path(options.brief_file).read_text(encoding="utf-8")
    elif options.brief:
        brief = options.brief
    elif "brief" in file_fields:
        brief = file_fields["brief"]
    else:
        brief = sys.stdin.read()
    if not (brief or "").strip():
        raise TaskFieldConflict("(brief)", "brief must not be empty after merging CLI and task file")

    fields: dict = {"brief": brief}
    if options.title:
        fields["title"] = options.title
    elif file_fields.get("title"):
        fields["title"] = file_fields["title"]
    if options.audience is not None:
        fields["audience"] = options.audience
    elif "audience" in file_fields:
        fields["audience"] = file_fields["audience"]
    if options.scenario is not None:
        fields["scenario"] = options.scenario
    elif "scenario" in file_fields:
        fields["scenario"] = file_fields["scenario"]
    if options.presentation_mode is not None:
        fields["presentation_mode"] = options.presentation_mode
    elif "presentation_mode" in file_fields:
        fields["presentation_mode"] = file_fields["presentation_mode"]
    if options.page_limit is not None:
        fields["page_limit"] = options.page_limit
    elif "page_limit" in file_fields:
        fields["page_limit"] = file_fields["page_limit"]
    if options.decision is not None:
        fields["existing_decisions"] = options.decision
    elif "existing_decisions" in file_fields:
        fields["existing_decisions"] = file_fields["existing_decisions"]
    return fields


# ---------------------------------------------------------------------------
# Pre-rebuild command mapping (spec 09.6). Every legacy entry has exactly one
# class — alias (executes the new semantics), guidance (points at the new
# command, non-zero exit) or retired (non-zero exit). Nothing here imports or
# execs the retired legacy entry; old runs are never migrated in place.

_GUIDANCE_LIBRARY = (
    "新核心不实现整页库流程;请用来源文件创建项目,或固定旧版本安装操作历史 run。"
    "新工作一律走 deck-master create --brief … --source … --out …"
)

_LEGACY_GUIDANCE = {
    'start-conversation': 'deck-master create --brief … --source … --out …(不隐式生成规则稿)',
    'start': 'deck-master create(新项目)或 deck-master view --project <dir>(已有项目)',
    'plan': 'deck-master create --brief … --source … --out …',
    'build-brief': 'deck-master create --brief … --source … --out …',
    'build-claim-map': 'deck-master create 后由内容方法派生;不单独生成 claim_map',
    'autoplan': 'deck-master create --draft <完整稿.json> 或 import-draft',
    'search-library': _GUIDANCE_LIBRARY,
    'decide-sourcing': _GUIDANCE_LIBRARY,
    'library-status': _GUIDANCE_LIBRARY,
    'import-library-selection': _GUIDANCE_LIBRARY,
    'record-library-feedback': _GUIDANCE_LIBRARY,
    'uat-ppt-library': _GUIDANCE_LIBRARY,
    'validate-ppt-library-result': _GUIDANCE_LIBRARY,
    'suite-status': 'deck-master doctor --step view(renderer/字体按步如实报告)',
    'suite-install': '无需安装 suite;pip 安装后 deck-master 直接可用',
    'suite-repair': '无需 suite 修复;pip 安装后 deck-master 直接可用',
    'setup': '新核心无首次运行配置;pip install -e . 后直接 create',
    'setup-status': 'deck-master doctor --step compose',
}

_LEGACY_RETIRED = {
    'backend', 'suite-build-release-tree', 'release-build', 'release-smoke',
    'release-install', 'release-rollback', 'suite-migrate-legacy-skills',
    'install-skill', 'validate-skill', 'uninstall-skill', 'orchestration-check',
    'bind-workspace', 'build-judgments', 'build-claim-graph', 'init-workspace',
    'init-project', 'register-workspace', 'validate-workspace', 'delivery',
    'opportunity', 'connector', 'render', 'render-status', 'import-render-result',
    'import-sourcing', 'validate-sourcing', 'import-context-pack',
    'create-run-from-context-pack', 'prepare-narrative-advice',
    'import-narrative-advice', 'apply-narrative-advice', 'prepare-quality-review',
    'import-quality-review', 'import-quality-findings', 'prepare-generation-handoff',
    'import-generation-result', 'refresh-preview-from-generation',
    'generation-session', 'run-generation', 'build-learning-pack',
    'show-learning-pack', 'validate-generation-result', 'validate-render-result',
    'summarize-run-metrics', 'uat-generation-tool', 'uat-render-tool',
    'smoke-real-workflow', 'validate-benchmark-case', 'benchmark-run',
    'benchmark-report', 'benchmark-rc-report', 'benchmark-checkpoint',
    'benchmark-list', 'benchmark-aggregate-report', 'rc-gate', 'preview-gate',
}

_LEGACY_BUILD_SUBCOMMANDS = {
    'prepare': 'read-only status derived from the current ProjectView',
    'status': 'read-only status derived from the current ProjectView',
    'run': 'deck-master build --project <dir> 本地编译渲染',
    'retry': None,
    'select-style': None,
    'import-provider-result': None,
    'approve-blueprint': None,
}

_LEGACY_ALIAS = {
    'agent-doctor', 'next-step', 'run-state', 'final-readiness', 'import-plan',
    'product-capability-manifest', 'validate-product-capability-manifest',
}


def _looks_like_legacy_run(path: Path) -> bool:
    """Old-run shape recognition: no new Document pointer, but old markers."""
    if (path / '.deckmaster' / 'current.json').is_file():
        return False
    return any((path / name).exists() for name in
               ('preview_manifest.json', 'run.json', 'request.json', 'narrative_plan.json'))


def _reject_legacy_run(path_value, option='--project'):
    path = Path(path_value).expanduser()
    if _looks_like_legacy_run(path):
        return _emit_and_exit(_error(
            'legacy_run_format',
            f'{option} {path} 是旧版 run(preview_manifest/run.json 标记),新写命令不就地初始化或迁移;'
            '请按 docs/migration-to-rebuilt-core.md 处置,或固定旧版本安装操作该 run',
            'convert with import-draft or pin the legacy version'), 2)
    return None


def _legacy_json(code, message, **extra):
    payload = {'error': {'code': code, 'message': message}}
    payload['error'].update(extra)
    return payload


def _legacy_dispatch(argv: list[str]) -> int | None:
    command = next((token for token in argv if not token.startswith('-')), None)
    if command is None:
        return None
    if command == 'build' and len(argv) > 1 and argv[argv.index('build') + 1] in _LEGACY_BUILD_SUBCOMMANDS:
        return _legacy_build(argv)
    if command in _LEGACY_GUIDANCE:
        return _emit_and_exit(_legacy_json(
            'legacy_guidance', f'旧命令 {command} 已由新核心取代: {_LEGACY_GUIDANCE[command]}',
            next_action='use the mapped rebuilt command'), 2)
    if command in _LEGACY_RETIRED:
        return _emit_and_exit(_legacy_json(
            'retired_command', f'旧命令 {command} 已退役,不进入新任务前置;'
            '对照表见 deck-master legacy-map 与 docs/migration-to-rebuilt-core.md',
            next_action='none'), 2)
    if command in _LEGACY_ALIAS:
        handler = {
            'agent-doctor': _legacy_agent_doctor,
            'next-step': _legacy_next_step,
            'run-state': _legacy_next_step,
            'final-readiness': _legacy_final_readiness,
            'import-plan': _legacy_import_plan,
            'product-capability-manifest': _legacy_manifest,
            'validate-product-capability-manifest': _legacy_manifest_validate,
        }[command]
        return handler(argv)
    return None


def _option_value(argv, name, default=None):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return default


def _legacy_agent_doctor(argv) -> int:
    mode = _option_value(argv, '--mode', 'preview')
    step = 'export' if mode == 'production' else 'view'
    from .doctor import diagnose
    result = diagnose(step, host_imagegen=('--host-imagegen' in argv))
    _emit(result)
    return 0 if result['status'] == 'ready' else 3


def _legacy_next_step(argv) -> int:
    # spec 09.6: 新项目返回同一 ProjectView;旧 run 拒绝就地初始化。
    run_dir = _option_value(argv, '--run-dir')
    if run_dir:
        rejected = _reject_legacy_run(run_dir, '--run-dir')
        if rejected is not None:
            return rejected
        project = run_dir
    else:
        project = _option_value(argv, '--project')
    if not project:
        return _emit_and_exit(_legacy_json('invalid_input', '提供 --project <dir>(旧 --run-dir 仅用于识别拒绝)',
                                           next_action='add --project'), 2)
    from .view import project_view
    view = project_view(project)
    next_action = ('submit_host_results' if view['pending_tasks']
                   else 'continue_production' if view['page_count'] else 'create_or_import_content')
    return _emit({**view, 'next_action': next_action})


def _legacy_final_readiness(argv) -> int:
    project = _option_value(argv, '--project') or _option_value(argv, '--run-dir')
    if not project:
        return _emit_and_exit(_legacy_json('invalid_input', '提供 --project <dir>', next_action='add --project'), 2)
    rejected = _reject_legacy_run(project)
    if rejected is not None:
        return rejected
    from .editing import check_summary
    from .store import Store
    from .view import project_view
    store = Store(project)
    doc = store.load_document()
    summary = check_summary(store, doc)
    view = project_view(project)
    report = {
        'status': 'ready' if summary['status'] == 'pass' and doc['outputs'].get('pptx') else 'blocked',
        'review_status': summary['status'],
        'unresolved': {'missing_dimensions': sorted(summary['missing_dimensions']),
                       'failed_dimensions': sorted(k for k, v in summary['dimensions'].items()
                                                 if v['open_must_fix'] or v['status'] == 'fail')},
        'view_status': view['view_status'],
        'revision_id': doc['revision_id'],
        'evidence_level': 'engineering',
    }
    return _emit(report)


def _legacy_import_plan(argv) -> int:
    source = _option_value(argv, '--input') or _option_value(argv, '--plan')
    if not source:
        return _emit_and_exit(_legacy_json('invalid_input', 'import-plan 需要 --input <plan.json>',
                                           next_action='add --input'), 2)
    raw = json.loads(Path(source).read_text(encoding='utf-8'))
    pages = raw.get('pages') if isinstance(raw, dict) else None
    project = _option_value(argv, '--project')
    if isinstance(pages, list) and pages and \
            all(isinstance(page, dict) and page.get('schema_version') == 'deck_page_package.v2'
                for page in pages):
        # 已是 v2 完整稿:按 import-draft 语义接收,源数据不改,未知字段由 check_page 显式报错。
        return _emit(service.import_draft(project or '.', draft_payload=raw))
    legacy_keys = sorted(set(raw) - {'pages', 'page_order'}) if isinstance(raw, dict) else []
    return _emit_and_exit(_legacy_json(
        'legacy_plan_format',
        f'{source} 不是 Page v2 完整稿(检测到旧字段: {legacy_keys or "结构不符"});'
        '新核心不就地迁移旧 plan,请按 docs/migration-to-rebuilt-core.md 转换后 import-draft,'
        '未知字段必须显式映射、不得静默丢弃', next_action='convert then import-draft'), 2)


def _legacy_manifest(argv) -> int:
    import deck_master
    repo_root = Path(deck_master.__file__).resolve().parents[2]
    manifest_path = repo_root / 'product-capability-manifest.json'
    if not manifest_path.is_file():
        # T24: the v0.9.x manifest is archived, not deleted; the alias keeps
        # serving it from the archive for history lookups.
        manifest_path = repo_root / 'docs' / 'archive' / 'pre-rebuild' / 'product-capability-manifest.v09.json'
    return _emit(json.loads(manifest_path.read_text(encoding='utf-8')))


def _legacy_manifest_validate(argv) -> int:
    try:
        _legacy_manifest(argv)
    except Exception as exc:  # noqa: BLE001
        return _emit_and_exit(_legacy_json('invalid_input', f'manifest 不可解析: {exc}',
                                           next_action='fix the JSON'), 2)
    return _emit({'status': 'valid'})


def _legacy_build(argv) -> int:
    index = argv.index('build')
    subcommand = argv[index + 1]
    mapping = _LEGACY_BUILD_SUBCOMMANDS[subcommand]
    run_dir = _option_value(argv, '--run-dir')
    if run_dir:
        rejected = _reject_legacy_run(run_dir, '--run-dir')
        if rejected is not None:
            return rejected
    if mapping is None:
        return _emit_and_exit(_legacy_json(
            'retired_command', f'build {subcommand} 已退役(MBB 阶段/style 锁定属于旧制作链)',
            next_action='none'), 2)
    if subcommand == 'run':
        return _emit_and_exit(_legacy_json(
            'legacy_guidance', '旧 build run 映射: deck-master build --project <dir>(本地编译渲染)',
            next_action='deck-master build --project <dir>'), 2)
    project = _option_value(argv, '--project') or run_dir
    if not project:
        return _emit_and_exit(_legacy_json('invalid_input', '提供 --project <dir>', next_action='add --project'), 2)
    from .view import project_view
    view = project_view(project)
    return _emit({'status': 'prepared' if view['page_count'] else 'awaiting_content',
                  'page_count': view['page_count'],
                  'outputs': view['outputs'], 'view_status': view['view_status']})


def legacy_mapping_table() -> dict:
    return {
        'alias': sorted(_LEGACY_ALIAS),
        'guidance': sorted(_LEGACY_GUIDANCE),
        'retired': sorted(_LEGACY_RETIRED | {f'build {name}' for name, mapped in
                                             _LEGACY_BUILD_SUBCOMMANDS.items() if mapped is None}),
        'legacy_build_subcommands': sorted(_LEGACY_BUILD_SUBCOMMANDS),
        'note': 'spec 09.6;退役的旧入口不再被新 CLI 调用',
    }



def _dispatch_import_legacy(argv: list[str]) -> int:
    """`deck-master import legacy --input <old-run> --out <new-project> [--inspect]`."""
    parser = argparse.ArgumentParser(prog='deck-master import legacy')
    parser.add_argument('--input', required=True, help='旧 run 目录或 v1 页包文件(只读)')
    parser.add_argument('--out', required=True, help='新项目目录(必须为空/不存在)')
    parser.add_argument('--inspect', action='store_true', help='dry-run: 输出字段/媒体/未知项计划,不写项目')
    options = parser.parse_args(argv)
    from . import legacy as legacy_mod
    try:
        result = legacy_mod.import_legacy(options.input, options.out, inspect_only=options.inspect)
    except legacy_mod.LegacyNormalizationRequired as exc:
        return _emit_and_exit(_error('needs_normalization', str(exc), 'map the named fields explicitly',
                                     field='; '.join(exc.unknown_fields)), 2)
    except legacy_mod.LegacyError as exc:
        return _emit_and_exit(_error('legacy_import_refused', str(exc), 'fix the named legacy input'), 2)
    return _emit(result)


def _project_has_pages(project: Path | str) -> bool:
    try:
        from .store import Store

        return bool(Store(project).load_document().get("pages"))
    except Exception:  # noqa: BLE001
        return False


def _attach_workbench_url(project: Path | str, payload: dict) -> dict:
    """Auto ``view --open`` after the first real content arrives (spec 10.4).

    Failures degrade to a real reason instead of a missing URL: no browser,
    service start failure and non-interactive runs stay distinguishable.
    """
    import os
    if os.environ.get("DECK_MASTER_NO_AUTO_VIEW"):
        payload.setdefault("findings", []).append(
            {"code": "workbench_auto_view_disabled",
             "message": "non-interactive run; open with: deck-master view --open --project <dir>"})
        payload["review_url"] = None
        payload["view_status"] = "available"
        return payload
    from .web import open_view
    try:
        info = open_view(project, open_browser=True)
    except Exception as exc:  # noqa: BLE001 - the workbench must never break the accept
        info = {"review_url": None, "view_status": "unavailable", "detail": str(exc)}
    payload["review_url"] = info.get("review_url")
    payload["view_status"] = info.get("view_status", "unavailable")
    if not info.get("review_url"):
        payload.setdefault("findings", []).append(
            {"code": "workbench_unavailable", "message": info.get("detail", "view service unavailable")}
        )
    return payload


def _dispatch_task(options) -> int:
    rejected = _reject_legacy_run(options.project)
    if rejected is not None:
        return rejected
    if options.task_command == "accept":
        had_pages = True
        try:
            from .store import Store
            had_pages = bool(Store(options.project).load_document().get("pages"))
        except Exception:  # noqa: BLE001 - adoption below reports real errors
            pass
        payload = service.accept_result(
            options.project,
            task_id=options.task_id,
            operation_id=options.operation_id,
            produced_against=options.produced_against,
            result_path=options.result,
        )
        if not had_pages:
            payload = _attach_workbench_url(options.project, payload)
        return _emit(payload)
    if options.task_command == "start":
        return _emit(
            service.task_start(
                options.project, task_id=options.task_id, execution_ref=options.execution_ref
            )
        )
    if options.task_command == "status":
        return _emit(service.task_status(options.project, task_id=options.task_id))
    if options.task_command == "cancel":
        return _emit(
            service.task_cancel(options.project, task_id=options.task_id, reason=options.reason)
        )
    if options.task_command == "call":
        return _dispatch_call(options)
    return 2


def _dispatch_call(options) -> int:
    from . import tasks as tasks_mod

    if options.call_command == "allocate":
        return _emit(
            tasks_mod.allocate_call_allowances(
                _store(options.project), task_id=options.task_id, count=options.count,
            )
        )
    if options.call_command == "begin":
        return _emit(
            tasks_mod.call_begin(
                _store(options.project),
                task_id=options.task_id,
                allowance_id=options.allowance_id,
                execution_ref=options.execution_ref,
            )
        )
    report_bytes = None
    report_ext = "json"
    if options.report:
        from pathlib import Path

        report_file = Path(options.report)
        report_bytes = report_file.read_bytes()
        report_ext = report_file.suffix.lstrip(".").lower() or "json"
    return _emit(
        tasks_mod.call_settle(
            _store(options.project),
            task_id=options.task_id,
            allowance_id=options.allowance_id,
            outcome=options.outcome,
            report_bytes=report_bytes,
            report_ext=report_ext,
            invocation_ref=options.invocation_ref,
        )
    )


def _store(project_dir):
    from .store import Store
    from pathlib import Path

    return Store(Path(project_dir).expanduser())


if __name__ == "__main__":
    raise SystemExit(main())
