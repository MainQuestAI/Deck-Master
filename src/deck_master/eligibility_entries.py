"""The T04 entry inventory: every public business entry, the eligibility action
it must consume, where that gate physically lands, and why a read-only entry is
exempt (AC-R04: 所有有副作用的边界消费同一资格事实).

``COVERAGE`` is machine-checked by ``tests/rebuild/test_eligibility_entry_coverage.py``:
the test enumerates the real surface (service.py public functions,
``operations.public`` wrappers, the CLI subcommand tree, the ``/api`` route
literals in the HTTP frontends) and fails on any entry this file does not
classify. A new write path therefore cannot be added without deciding which
eligibility action it consumes — that is the machine guarantee against
"逐步接入口" (TASKS.md T04 note).

A classification is either
  * an action from ``eligibility.ACTIONS`` (the entry has side effects and must
    call ``eligibility.guard``/``evaluate`` at its boundary), or
  * an explicit exemption with a reason (reads, projections, UI-journal state,
    installation, or a report that only *describes* the decision).
"""
from __future__ import annotations

import argparse
import importlib
import pkgutil
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Legacy command surface (cli._LEGACY_* sets). These names never reach the new
# parser: they map to a rebuilt command or refuse with guidance. They are
# enumerated literally here so a new legacy name still needs an explicit row.

def legacy_refusal_entries() -> set[str]:
    """The refusal-only legacy surface: names the CLI maps or refuses before the
    parser runs. Read from the CLI's own tables (its refusal vocabulary stays in
    one place) instead of re-listing retired names in a living module."""
    from . import cli
    names = set(cli._LEGACY_GUIDANCE) | set(cli._LEGACY_RETIRED)
    return {f"legacy:{name}" for name in names}


# Read-only / non-project exemptions, grouped so the reason is stated once


READ_REASONS = {
    "read_model": "read-only projection/read model; no project control change",
    "read_download": "reads an already-fixed immutable export object",
    "read_plan": "immutable derived plan/preview; writes no Document, Task, allowance or call",
    "read_analysis": "read-only analysis/plan output",
    "ui_state": "personal UI journal / gallery / overview state; never writes project control or business objects",
    "legacy_refusal": "legacy mapping/refusal surface: maps to a rebuilt command or refuses with guidance; writes nothing",
    "internal": "internal write mechanics/helper used by classified entries; not an independently reachable business entry",
    "staging": "stages a material upload for later confirmation; writes no Document/Task/allowance",
    "install": "installation/registry/diagnostic surface; not project business state",
}

# ---------------------------------------------------------------------------
# Surface classifications: name -> (action | None, gate, exempt reason | None)


SERVICE_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    "create": ("create",
               "service.create: routing only; the compose task it opens passes the "
               "dispatch.compose gate inside open_compose_task", None),
    "continue_project": ("continue_project",
                         "service.continue_project: consumes the decision and returns the "
                         "card/gaps; every dispatch it makes goes through a gated helper", None),
    "open_compose_task": ("dispatch.compose",
                          "service.open_compose_task: guard before new_task/commit", None),
    "open_host_task": ("dispatch.host_task",
                       "service.open_host_task: guard before the dispatch commit", None),
    "open_blueprint_task": ("dispatch.blueprint",
                            "service.open_blueprint_task: guard before reserve_allowances and "
                            "the dispatch commit", None),
    "inputs_update": ("content.inputs_update",
                      "service.inputs_update: guard inside the locked transaction before "
                      "staging/commit; the reconciliation task is dispatched through "
                      "open_compose_task's gate", None),
    "accept_result": ("task.accept",
                      "service.accept_result → tasks.accept_result: call facts settle first "
                      "(unchanged protocol, CONTRACTS §6.1 accept_result exception), then "
                      "adoption consumes the gate", None),
    "import_draft": ("import_draft", "service.import_draft: guard before _adopt_draft", None),
    "import_asset": ("asset.import", "service.import_asset: guard before the design commit", None),
    "update_design": ("design.update", "service.update_design: guard before the design commit", None),
    "task_start": ("task.start", "service.task_start: guard before the claim commit", None),
    "task_cancel": ("task.cancel", "service.task_cancel: consumes the decision; cancellation "
                                   "stays available while paused (CONTRACTS §7.1)", None),
    "task_summary": (None, "-", READ_REASONS["read_model"]),
    "task_status": (None, "-", READ_REASONS["read_model"]),
    "inputs_show": (None, "-", READ_REASONS["read_model"]),
}


COLLABORATION_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    "collaboration.start_request": ("request.start",
                                    "collaboration.start_request: T02 write path owns record "
                                    "correctness; T04 consumes the decision", None),
    "collaboration.record_decision": ("decision.record",
                                      "collaboration.record_decision: T02 write path owns "
                                      "evidence/delegation correctness", None),
    "collaboration.grant": ("authorization.grant",
                            "collaboration.grant: T02 write path owns scope/parent-chain "
                            "correctness", None),
    "collaboration.revoke_authorization": ("authorization.revoke",
                                           "collaboration.revoke_authorization: withdrawal is a "
                                           "fact, never refused", None),
    "collaboration.pause_request": ("request.pause",
                                    "collaboration.pause_request: stop fact, always recordable", None),
    "collaboration.resume_request": ("request.resume",
                                     "collaboration.resume_request: explicit resume; never widens "
                                     "scope (T02 re-derives from the same request)", None),
    "collaboration.describe": (None, "-", READ_REASONS["read_model"]),
    "collaboration.payload_digest": (None, "-", READ_REASONS["internal"]),
    "collaboration.write_digest": (None, "-", READ_REASONS["internal"]),
    "collaboration.resolve_evidence": (None, "-", READ_REASONS["internal"]),
    "collaboration.replay_or_conflict": (None, "-", READ_REASONS["internal"]),
    "collaboration.commit_collaboration_change": (None, "-", READ_REASONS["internal"]),
    "collaboration_migration.describe": ("migration.describe",
                                         "collaboration_migration.describe: read-only migration plan", None),
    "collaboration_migration.apply": ("migration.apply",
                                      "collaboration_migration.apply: single-transaction migration "
                                      "with plan digest + CAS", None),
    "collaboration_migration.migration_plan": (None, "-", READ_REASONS["internal"]),
    "collaboration_migration.migration_response": (None, "-", READ_REASONS["internal"]),
}


OPERATIONS_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    # -- write operations that need an action
    "annotation_service.save": ("annotation.save",
                                "annotation_service.save: guard before the annotation commit", None),
    "candidates.plan": ("change.plan",
                        "candidates.plan: read-only candidate plan (immutable object); consumes "
                        "the plan decision and reports it", None),
    "candidates.adopt": ("candidate.adopt",
                         "candidates.adopt: guard before the adoption commit (adoption never "
                         "consumes image-call credit)", None),
    "candidates.decide": ("candidate.select",
                          "candidates.decide: guard before recording the decision", None),
    "changes.plan": ("change.plan", "changes.plan: read-only derived plan (immutable object)", None),
    "changes.commit": ("change.commit", "changes.commit: guard before dispatch/commit", None),
    "content_ops.plan": ("change.plan", "content_ops.plan: read-only plan (immutable object)", None),
    "content_ops.commit": ("content.operation",
                           "content_ops.commit: guard before the outline/content commit", None),
    "content_ops.inputs": ("content.inputs_update",
                           "content_ops.inputs: recoverable inputs update; same gate as "
                           "service.inputs_update", None),
    "exports.create": ("export.delivery",
                       "exports.create: purpose=delivery consumes the delivery gate; "
                       "review/engineering stay report-only", None),
    "icons.propose": ("style.propose", "icons.propose: guard before the design proposal commit", None),
    "icons.draft": ("style.propose", "icons.draft: guard before the recipe draft commit", None),
    "icons.confirm": ("candidate.select",
                      "icons.confirm: guard before recording the accepted design dimension", None),
    "icons.preview": ("render.preview", "icons.preview: local rendering only; request scope applies", None),
    "candidate_preview.request": ("render.preview",
                                  "candidate_preview.request: local candidate rendering request", None),
    "restoration.commit": ("restore",
                           "restoration.commit: reporting-only decision (never refused: "
                           "restore recovers content facts and keeps the current control)", None),
    "source_uploads.receive": (None, "-", READ_REASONS["staging"]),
    "stages.assemble": ("stage.assemble", "stages.assemble: guard before the assembly commit", None),
    "styles.propose": ("style.propose", "styles.propose: guard before the proposal/recipe commit", None),
    "styles.confirm": ("design.update", "styles.confirm: guard before the design commit", None),
    "visual_styles.analyze": ("dispatch.host_task",
                              "visual_styles.analyze: dispatches a Host analysis task", None),
    "visual_styles.import_reference": ("asset.import",
                                       "visual_styles.import_reference: guard before the "
                                       "reference/asset commit", None),
    # -- read-only operations
    "operations.show": (None, "-", READ_REASONS["read_model"]),
    "annotation_service.list_annotations": (None, "-", READ_REASONS["read_model"]),
    "candidate_preview.file_bytes": (None, "-", READ_REASONS["read_download"]),
    "candidate_preview.status": (None, "-", READ_REASONS["read_model"]),
    "candidates.listing": (None, "-", READ_REASONS["read_model"]),
    "candidates.show": (None, "-", READ_REASONS["read_model"]),
    "changes.handoff": (None, "-", READ_REASONS["read_model"]),
    "changes.list_changes": (None, "-", READ_REASONS["read_model"]),
    "content_ops.lineage": (None, "-", READ_REASONS["read_model"]),
    "content_ops.source": (None, "-", READ_REASONS["read_model"]),
    "exports.describe": (None, "-", READ_REASONS["read_model"]),
    "exports.download": (None, "-", READ_REASONS["read_download"]),
    "exports.show": (None, "-", READ_REASONS["read_download"]),
    "icons.catalog": (None, "-", READ_REASONS["read_model"]),
    "icons.inspect": (None, "-", READ_REASONS["read_analysis"]),
    "icons.listing": (None, "-", READ_REASONS["read_model"]),
    "icons.plan": ("change.plan", "icons.plan: read-only design plan (immutable object)", None),
    "restoration.plan": (None, "-", READ_REASONS["read_plan"]),
    "source_uploads.show": (None, "-", READ_REASONS["read_model"]),
    "styles.listing": (None, "-", READ_REASONS["read_model"]),
    "styles.plan": ("change.plan", "styles.plan: read-only design plan (immutable object)", None),
    "styles.show": (None, "-", READ_REASONS["read_model"]),
    "visual_styles.listing": (None, "-", READ_REASONS["read_model"]),
}


CLI_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    # -- creation and routing
    "create": ("create", "cli.create → service.create (routing gate)", None),
    "continue": ("continue_project", "cli.continue → service.continue_project (decision card)", None),
    "import-draft": ("import_draft", "cli.import-draft → service.import_draft", None),
    "import": ("asset.import", "cli.import → service.import_asset", None),
    # -- execution and fees
    "task accept": ("task.accept", "cli.task accept → service.accept_result", None),
    "task start": ("task.start", "cli.task start → service.task_start", None),
    "task cancel": ("task.cancel", "cli.task cancel → service.task_cancel (available while paused)", None),
    "task call allocate": ("allowance.allocate",
                           "cli.task call allocate → tasks.allocate_call_allowances", None),
    "task call begin": ("call.begin", "cli.task call begin → tasks.call_begin", None),
    "task call settle": ("call.settle",
                         "cli.task call settle → tasks.call_settle (settles facts; never a new "
                         "production channel)", None),
    "requests freeze": ("generation.dispatch",
                        "cli.requests freeze → generation.freeze (bounded call input)", None),
    # -- adoption
    "inputs update": ("content.inputs_update", "cli.inputs update → service.inputs_update", None),
    "edit": ("page.edit", "cli.edit → editing.edit_page", None),
    "build": ("compile.ppt", "cli.build → pipeline.produce (local production)", None),
    "annotations save": ("annotation.save", "cli.annotations save → annotation_service.save", None),
    # -- change / candidates / design
    "changes plan": ("change.plan", "cli.changes plan → changes.plan (immutable plan object)", None),
    "changes commit": ("change.commit", "cli.changes commit → changes.commit", None),
    "candidates plan": ("change.plan", "cli.candidates plan → candidates.plan (immutable plan object)", None),
    "candidates adopt": ("candidate.adopt", "cli.candidates adopt → candidates.adopt", None),
    "candidates decision": ("candidate.select", "cli.candidates decision → candidates.decide", None),
    "content plan": ("change.plan", "cli.content plan → content_ops.plan (immutable plan object)", None),
    "content commit": ("content.operation", "cli.content commit → content_ops.commit", None),
    "content inputs": ("content.inputs_update", "cli.content inputs → content_ops.inputs", None),
    "styles propose": ("style.propose", "cli.styles propose → styles.propose", None),
    "styles confirm": ("design.update", "cli.styles confirm → styles.confirm", None),
    "styles analyze": ("dispatch.host_task", "cli.styles analyze → visual_styles.analyze", None),
    "styles references import": ("asset.import",
                                 "cli.styles references import → visual_styles.import_reference", None),
    "icons propose": ("style.propose", "cli.icons propose → icons.propose", None),
    "icons draft": ("style.propose", "cli.icons draft → icons.draft", None),
    "icons confirm": ("candidate.select", "cli.icons confirm → icons.confirm", None),
    "stages assemble": ("stage.assemble", "cli.stages assemble → stages.assemble", None),
    "candidate-preview request": ("render.preview",
                                  "cli.candidate-preview request → candidate_preview.request", None),
    # -- delivery
    "export": ("export.delivery", "cli.export → exports.create (purpose gate)", None),
    "handoff-check": ("handoff.delivery", "cli.handoff-check → handoff.check_handoff", None),
    # -- history and policy
    "history restore": ("restore",
                        "cli.history restore → editing.restore (reporting-only decision: the "
                        "current request/withdrawal/pause stay in force)", None),
    "history commit-restore": ("restore",
                               "cli.history commit-restore → restoration.commit (reporting-only "
                               "decision; recovery keeps the current control)", None),
    "ui plan-clear": (None, "-", READ_REASONS["ui_state"]),
    "ui commit-clear": (None, "-", READ_REASONS["ui_state"]),
    # -- read-only / non-project
    "doctor": (None, "-", READ_REASONS["install"]),
    "legacy-map": (None, "-", READ_REASONS["read_model"]),
    "view": (None, "-", READ_REASONS["read_model"]),
    "workbench": (None, "-", READ_REASONS["install"]),
    "install candidate": (None, "-", READ_REASONS["install"]),
    "install activate": (None, "-", READ_REASONS["install"]),
    "install rollback": (None, "-", READ_REASONS["install"]),
    "inputs show": (None, "-", READ_REASONS["read_model"]),
    "task status": (None, "-", READ_REASONS["read_model"]),
    "task list": (None, "-", READ_REASONS["read_model"]),
    "operations show": (None, "-", READ_REASONS["read_model"]),
    "changes handoff": (None, "-", READ_REASONS["read_model"]),
    "changes list": (None, "-", READ_REASONS["read_model"]),
    "candidates list": (None, "-", READ_REASONS["read_model"]),
    "candidates show": (None, "-", READ_REASONS["read_model"]),
    "content lineage": (None, "-", READ_REASONS["read_model"]),
    "content source": (None, "-", READ_REASONS["read_model"]),
    "styles list": (None, "-", READ_REASONS["read_model"]),
    "styles show": (None, "-", READ_REASONS["read_model"]),
    "styles plan": ("change.plan", "cli.styles plan → styles.plan (immutable plan object)", None),
    "styles references list": (None, "-", READ_REASONS["read_model"]),
    "styles references show": (None, "-", READ_REASONS["read_model"]),
    "icons catalog": (None, "-", READ_REASONS["read_model"]),
    "icons inspect": (None, "-", READ_REASONS["read_analysis"]),
    "icons list": (None, "-", READ_REASONS["read_model"]),
    "icons plan": ("change.plan", "cli.icons plan → icons.plan (immutable plan object)", None),
    "requests show": (None, "-", READ_REASONS["read_model"]),
    "attempts show": (None, "-", READ_REASONS["read_model"]),
    "history list": (None, "-", READ_REASONS["read_model"]),
    "history plan-restore": (None, "-", READ_REASONS["read_plan"]),
    "annotations list": (None, "-", READ_REASONS["read_model"]),
    "candidate-preview status": (None, "-", READ_REASONS["read_model"]),
    # -- legacy alias surface (cli._LEGACY_ALIAS); reached before the parser
    "legacy:final-readiness": ("readiness.final",
                               "cli._legacy_final_readiness: consumes the delivery report policy",
                               None),
    "legacy:import-plan": ("import_draft",
                           "cli._legacy_import_plan: full deck_page_package.v2 plans import as a draft",
                           None),
    "legacy:agent-doctor": (None, "-", READ_REASONS["install"]),
    "legacy:next-step": (None, "-", READ_REASONS["read_model"]),
    "legacy:run-state": (None, "-", READ_REASONS["read_model"]),
    "legacy:product-capability-manifest": (None, "-", READ_REASONS["read_model"]),
    "legacy:validate-product-capability-manifest": (None, "-", READ_REASONS["read_model"]),
    # -- legacy build subcommands (cli._LEGACY_BUILD_SUBCOMMANDS)
    "legacy:build prepare": (None, "-", READ_REASONS["read_model"]),
    "legacy:build status": (None, "-", READ_REASONS["read_model"]),
    "legacy:build run": (None, "-", READ_REASONS["legacy_refusal"]),
    "legacy:build retry": (None, "-", READ_REASONS["legacy_refusal"]),
    "legacy:build select-style": (None, "-", READ_REASONS["legacy_refusal"]),
    "legacy:build import-provider-result": (None, "-", READ_REASONS["legacy_refusal"]),
    "legacy:build approve-blueprint": (None, "-", READ_REASONS["legacy_refusal"]),
}


# HTTP: exact route literals plus prefix rows for parameterised paths. Prefix
# rows are matched longest-first, so a more specific row wins.
HTTP_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    # -- write routes
    "/api/annotations/batch": ("annotation.save", "web.do_POST → annotation_service.save", None),
    "/api/changes/plan": ("change.plan", "web.do_POST → changes.plan (immutable plan object)", None),
    "/api/changes/commit": ("change.commit", "web.do_POST → changes.commit", None),
    "/api/candidates/plan": ("change.plan", "web.do_POST → candidates.plan (immutable plan object)", None),
    "/api/candidates/adopt": ("candidate.adopt", "web.do_POST → candidates.adopt", None),
    "/api/candidates/decision": ("candidate.select", "web.do_POST → candidates.decide", None),
    "/api/stages/assemble": ("stage.assemble", "web.do_POST → stages.assemble", None),
    "/api/styles/analyze": ("dispatch.host_task", "web.do_POST → visual_styles.analyze", None),
    "/api/styles/propose": ("style.propose", "web.do_POST → styles.propose", None),
    "/api/styles/confirm": ("design.update", "web.do_POST → styles.confirm", None),
    "/api/styles/plan": ("change.plan", "web.do_POST → styles.plan (immutable plan object)", None),
    "/api/styles/references/import": ("asset.import",
                                      "web.do_POST → visual_styles.import_reference", None),
    "/api/content/plan": ("change.plan", "web.do_POST → content_ops.plan (immutable plan object)", None),
    "/api/content/commit": ("content.operation", "web.do_POST → content_ops.commit", None),
    "/api/content/inputs": ("content.inputs_update", "web.do_POST → content_ops.inputs", None),
    "/api/content/uploads": (None, "-", READ_REASONS["staging"]),
    "/api/icons/propose": ("style.propose", "web.do_POST → icons.propose", None),
    "/api/icons/confirm": ("candidate.select", "web.do_POST → icons.confirm", None),
    "/api/icons/plan": ("change.plan", "web.do_POST → icons.plan (immutable plan object)", None),
    "/api/icons/preview": ("render.preview", "web.do_POST → icons.preview (local rendering)", None),
    "/api/candidate-preview/request": ("render.preview",
                                       "web.do_POST → candidate_preview.request", None),
    "/api/inputs/update": ("content.inputs_update", "web.do_POST → service.inputs_update", None),
    "/api/requests/freeze": ("generation.dispatch", "web.do_POST → generation.freeze", None),
    "/api/edit": ("page.edit", "web.do_POST → editing.edit_page", None),
    "/api/feedback": ("dispatch.host_task",
                      "web.do_POST → service.open_host_task (feedback dispatch)", None),
    "/api/cancel": ("task.cancel", "web.do_POST → service.task_cancel (available while paused)", None),
    "/api/history/commit-restore": ("restore",
                                    "web.do_POST → restoration.commit (reporting-only decision)", None),
    "/api/restore": ("restore",
                     "web.do_POST → editing.restore (reporting-only decision)", None),
    "/api/exports": ("export.delivery",
                     "web.do_POST → exports.create (purpose=delivery consumes the gate)", None),
    "/api/export": ("export.delivery",
                    "web.do_POST → editing.export_project (working/review copies stay report-only)", None),
    # -- HTTP write routes that only touch personal UI state
    "/api/drafts/save": (None, "-", READ_REASONS["ui_state"]),
    "/api/drafts/import": (None, "-", READ_REASONS["ui_state"]),
    "/api/drafts/recovery": (None, "-", READ_REASONS["ui_state"]),
    "/api/ui-state": (None, "-", READ_REASONS["ui_state"]),
    "/api/ui-state/plan-clear": (None, "-", READ_REASONS["ui_state"]),
    "/api/ui-state/commit-clear": (None, "-", READ_REASONS["ui_state"]),
    "/api/ui-state/plan-restore": (None, "-", READ_REASONS["ui_state"]),
    "/api/ui-state/restore": (None, "-", READ_REASONS["ui_state"]),
    "/api/gallery": (None, "-", READ_REASONS["ui_state"]),
    "/api/overview": (None, "-", READ_REASONS["ui_state"]),
    "/api/result-reading": (None, "-", READ_REASONS["ui_state"]),
    "/api/result-reading/import-legacy": (None, "-", READ_REASONS["ui_state"]),
    "/api/text-ranges/validate": (None, "-", READ_REASONS["read_model"]),
    # -- read/projection routes
    "/api/check": (None, "-", READ_REASONS["read_model"]),
    "/api/compose/handoff": (None, "-", READ_REASONS["read_model"]),
    "/api/content-plan": (None, "-", READ_REASONS["read_model"]),
    "/api/export-facts": (None, "-", READ_REASONS["read_model"]),
    "/api/file": (None, "-", READ_REASONS["read_download"]),
    "/api/health": (None, "-", READ_REASONS["read_model"]),
    "/api/history": (None, "-", READ_REASONS["read_model"]),
    "/api/inputs": (None, "-", READ_REASONS["read_model"]),
    "/api/project": (None, "-", READ_REASONS["read_model"]),
    "/api/reviews": (None, "-", READ_REASONS["read_model"]),
    "/api/session": (None, "-", READ_REASONS["read_model"]),
    "/api/tasks": (None, "-", READ_REASONS["read_model"]),
    "/api/thumbnail-file": (None, "-", READ_REASONS["read_download"]),
    "/api/thumbnails": (None, "-", READ_REASONS["read_model"]),
    "/api/view": (None, "-", READ_REASONS["read_model"]),
    "/api/workbench": (None, "-", READ_REASONS["read_model"]),
    "/api/styles": (None, "-", READ_REASONS["read_model"]),
    "/api/annotations": (None, "-", READ_REASONS["read_model"]),
    "/api/changes": (None, "-", READ_REASONS["read_model"]),
    "/api/candidates": (None, "-", READ_REASONS["read_model"]),
    "/api/drafts": (None, "-", READ_REASONS["ui_state"]),
}

HTTP_PREFIX_ENTRIES: dict[str, tuple[str | None, str, str | None]] = {
    "/api/actions/": (None, "-", READ_REASONS["read_model"]),
    "/api/annotations/": (None, "-", READ_REASONS["read_model"]),
    "/api/attempts/": (None, "-", READ_REASONS["read_model"]),
    "/api/candidate-preview/": (None, "-", READ_REASONS["read_model"]),
    "/api/candidates/": (None, "-", READ_REASONS["read_model"]),
    "/api/changes/": (None, "-", READ_REASONS["read_model"]),
    "/api/content/": (None, "-", READ_REASONS["read_model"]),
    "/api/drafts/": (None, "-", READ_REASONS["ui_state"]),
    "/api/exports/": (None, "-", READ_REASONS["read_download"]),
    "/api/history/": (None, "-", READ_REASONS["read_model"]),
    "/api/icons/": (None, "-", READ_REASONS["read_model"]),
    "/api/operations/": (None, "-", READ_REASONS["read_model"]),
    "/api/pages/": (None, "-", READ_REASONS["read_model"]),
    "/api/requests/": (None, "-", READ_REASONS["read_model"]),
    "/api/stages/": (None, "-", READ_REASONS["read_model"]),
    "/api/styles/": (None, "-", READ_REASONS["read_model"]),
    "/api/tasks/": (None, "-", READ_REASONS["read_model"]),
    "/api/text-ranges/": (None, "-", READ_REASONS["read_model"]),
    "/api/ui-state/": (None, "-", READ_REASONS["ui_state"]),
    "/api/view/": (None, "-", READ_REASONS["read_model"]),
}


@dataclass(frozen=True)
class Classification:
    surface: str
    entry: str
    action: str | None
    gate: str
    exempt: str | None

    @property
    def gated(self) -> bool:
        return self.action is not None


# ---------------------------------------------------------------------------
# Discovery: the real surface, read from the code


_SERVICE_SKIP = {"main"}


def service_surface() -> set[str]:
    """Module-level functions of service.py — the shared use-case surface."""
    import inspect
    from . import service
    return {name for name, value in vars(service).items()
            if not name.startswith("_") and inspect.isfunction(value)
            and getattr(value, "__module__", "") == "deck_master.service"
            and name not in _SERVICE_SKIP}


def operations_surface() -> set[str]:
    import deck_master
    found = set()
    for module_info in pkgutil.iter_modules(deck_master.__path__):
        try:
            module = importlib.import_module(f"deck_master.{module_info.name}")
        except Exception:  # noqa: BLE001 - an unimportable optional module has no surface
            continue
        for name, value in vars(module).items():
            if getattr(value, "__public_operation__", None):
                found.add(f"{module_info.name}.{name}")
    return found


def cli_surface() -> set[str]:
    """The parsed subcommand tree plus the legacy alias/refusal surface that is
    handled before the parser (cli._legacy_dispatch)."""
    from . import cli
    parser = cli.build_parser()
    names: list[str] = []

    def walk(current, prefix: str) -> None:
        subparsers = next((action for action in current._actions
                           if isinstance(action, argparse._SubParsersAction)), None)
        if subparsers is None:
            names.append(prefix.strip())
            return
        for name, child in sorted(subparsers.choices.items()):
            walk(child, f"{prefix}{name} ")

    walk(parser, "")
    parsed = {name for name in names if name}
    legacy = {f"legacy:{name}" for name in
              set(cli._LEGACY_ALIAS) | set(cli._LEGACY_GUIDANCE) | set(cli._LEGACY_RETIRED)}
    legacy |= {f"legacy:build {name}" for name in cli._LEGACY_BUILD_SUBCOMMANDS}
    return parsed | legacy


def http_surface() -> set[str]:
    """Every ``/api`` route literal in the HTTP frontends."""
    import re
    from importlib import resources
    found = set()
    for filename in ("web.py", "view_server.py", "local_runtime.py"):
        try:
            text = resources.files("deck_master").joinpath(filename).read_text("utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            continue
        for match in re.finditer(r"['\"](/api/[^'\"]*)['\"]", text):
            found.add(match.group(1))
    return found


def collaboration_surface() -> set[str]:
    """Public functions of the T02 collaboration write path and its migration."""
    import inspect
    from . import collaboration, collaboration_migration
    found = set()
    for module_name, module in (("collaboration", collaboration),
                                ("collaboration_migration", collaboration_migration)):
        for name, value in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(value):
                continue
            if getattr(value, "__module__", "") != f"deck_master.{module_name}":
                continue
            found.add(f"{module_name}.{name}")
    return found


SURFACES = {
    "service": (service_surface, SERVICE_ENTRIES),
    "operations": (operations_surface, OPERATIONS_ENTRIES),
    "collaboration": (collaboration_surface, COLLABORATION_ENTRIES),
    "cli": (cli_surface, CLI_ENTRIES),
    "http": (http_surface, HTTP_ENTRIES),
}

# §6.2 boundary actions without a dedicated frontend entry are realized by
# another classified entry; the coverage test requires every boundary action to
# be either direct or named here with the entries that carry it.
BOUNDARY_VIA: dict[str, tuple[str, ...]] = {
    "allowance.repair": ("service.continue_project",),
    "style.trial": ("operations.changes.commit", "service.open_blueprint_task"),
    "style.expand": ("operations.changes.commit", "service.open_blueprint_task"),
    "compile.svg": ("cli.build", "service.open_host_task"),
    "compile.repair": ("cli.build", "service.open_host_task"),
    "readiness.final": ("cli.legacy:final-readiness",),
    "delivery.historical": ("operations.exports.create",),
    "policy.update": ("collaboration.collaboration.record_decision",
                      "collaboration.collaboration.pause_request"),
    "authority.update": ("collaboration.collaboration.grant",
                         "collaboration.collaboration.revoke_authorization"),
}


def classify(surface: str, entry: str) -> Classification | None:
    table = SURFACES[surface][1]
    row = table.get(entry)
    if row is None and surface == "cli" and entry.startswith("legacy:"):
        if entry in legacy_refusal_entries():
            row = (None, "-", READ_REASONS["legacy_refusal"])
    if row is None and surface == "http":
        for prefix in sorted(HTTP_PREFIX_ENTRIES, key=len, reverse=True):
            if entry.startswith(prefix):
                row = HTTP_PREFIX_ENTRIES[prefix]
                break
    if row is None:
        return None
    action, gate, exempt = row
    return Classification(surface=surface, entry=entry, action=action, gate=gate, exempt=exempt)


def inventory() -> list[Classification]:
    rows: list[Classification] = []
    for surface, (discover, _) in SURFACES.items():
        for entry in sorted(discover()):
            found = classify(surface, entry)
            if found is not None:
                rows.append(found)
    return rows


def uncovered() -> dict[str, list[str]]:
    """Entries present in the code but absent from the inventory."""
    missing: dict[str, list[str]] = {}
    for surface, (discover, _) in SURFACES.items():
        gaps = sorted(entry for entry in discover() if classify(surface, entry) is None)
        if gaps:
            missing[surface] = gaps
    return missing


def stale() -> dict[str, list[str]]:
    """Inventory rows that no longer match any real entry."""
    rows: dict[str, list[str]] = {}
    for surface, (discover, table) in SURFACES.items():
        present = discover()
        gaps = []
        for entry in table:
            if surface == "http":
                if not any(real == entry or real.startswith(entry) for real in present):
                    gaps.append(entry)
            elif entry not in present:
                gaps.append(entry)
        if gaps:
            rows[surface] = sorted(gaps)
    return rows


def coverage_stats() -> dict:
    rows = inventory()
    gated = [row for row in rows if row.gated]
    exempt = [row for row in rows if not row.gated]
    return {
        "total": len(rows),
        "gated": len(gated),
        "exempt": len(exempt),
        "by_surface": {surface: sum(1 for row in rows if row.surface == surface)
                       for surface in SURFACES},
        "actions": sorted({row.action for row in gated}),
    }
