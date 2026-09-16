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
from pathlib import Path
from typing import Any

from . import __version__
from . import service
from .models import ModelError
from .service import ServiceError
from .store import StoreError
from .tasks import EnvelopeError, TaskConflict


def _emit(payload: dict[str, Any]) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=1, default=str)
    sys.stdout.write("\n")
    return 0


def _error(code: str, message: str, next_action: str, field: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "field": field, "next_action": next_action}}


def _fail(exc: Exception) -> int:
    if isinstance(exc, (EnvelopeError, ModelError, ServiceError)):
        return _emit_and_exit(_error("invalid_input", str(exc), "fix the named field"), 2)
    if isinstance(exc, TaskConflict):
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

    create = sub.add_parser("create")
    create.add_argument("--brief", required=False, help="task brief text (or --brief-file)")
    create.add_argument("--brief-file", required=False)
    create.add_argument("--title", default="")
    create.add_argument("--source", action="append", default=[])
    create.add_argument("--out", required=True)
    create.add_argument("--design", default=None)
    create.add_argument("--draft", default=None, help="complete draft JSON to import")
    create.add_argument("--no-open", action="store_true")

    continue_cmd = sub.add_parser("continue")
    continue_cmd.add_argument("--project", required=True)
    continue_cmd.add_argument("--no-open", action="store_true")

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

    return parser


def _read_brief(options) -> str:
    if options.brief_file:
        return open(options.brief_file, encoding="utf-8").read()
    if options.brief:
        return options.brief
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    try:
        if options.command == "create":
            design = None
            if options.design:
                design = json.loads(open(options.design, encoding="utf-8").read())
            draft = None
            if options.draft:
                draft = json.loads(open(options.draft, encoding="utf-8").read())
            payload = service.create(
                options.out,
                brief=_read_brief(options),
                title=options.title,
                sources=options.source,
                design=design,
                draft=draft,
            )
            return _emit(payload)
        if options.command == "continue":
            return _emit(service.continue_project(options.project))
        if options.command == "import-draft":
            return _emit(service.import_draft(options.project, draft_path=options.input))
        if options.command == "view":
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
    return 2


def _read_brief(options) -> str:
    if options.brief_file:
        from pathlib import Path

        return Path(options.brief_file).read_text(encoding="utf-8")
    if options.brief:
        return options.brief
    return sys.stdin.read()


def _dispatch_task(options) -> int:
    if options.task_command == "accept":
        return _emit(
            service.accept_result(
                options.project,
                task_id=options.task_id,
                operation_id=options.operation_id,
                produced_against=options.produced_against,
                result_path=options.result,
            )
        )
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
        )
    )


def _store(project_dir):
    from .store import Store
    from pathlib import Path

    return Store(Path(project_dir).expanduser())


if __name__ == "__main__":
    raise SystemExit(main())
