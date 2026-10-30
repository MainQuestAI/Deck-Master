"""Service use cases for the rebuilt core (spec 09.1–09.5).

create/continue/task accept are the only entrypoints CLI and Web share.
No rule Planner, no loop claim, no library/workspace prerequisite: a plain
material directory starts a project (AC-C06). Confirmed decisions are never
re-asked; repeating continue returns the same pending tasks (AC-C04).

Dispatch consistency: a Host task records ``dispatch_revision`` (the revision
it was committed in) and ``produced_against`` (the content hash of the parent
revision it was derived from). ``accept`` re-checks both inside the project
lock, so a stale submission is refused with current unchanged (exit 5).
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .review_evidence import TrustedContext

from . import eligibility
from . import tasks as tasks_mod
from .content import normalize_design_assets, check_page
from .errors import (ImportRequiresPhasedPath, InputRevisionConflict, SourceUnreadable,
                     SourceUnsupported)
from .method_resources import method_release, method_resources
from .models import bump_revision, canonical_json_bytes, compute_input_digest, content_identity, input_alignment, new_document, sha256_bytes, validate_document_semantics, writer_at_least, collaboration_required
from .sources import discover_sources, read_source_snapshot
from .store import Store, StoreError, ConflictError
from .production import project_prompt, resolve_design
from .review import PAGE_VISUAL_KINDS
from .work_context import response_projection
from .current_work import after_action



class ServiceError(StoreError):
    """A use-case level failure with the offending field named."""


def _response(
    *,
    status: str,
    document: dict,
    requested_action: str,
    pending_tasks: list | None = None,
    next_action: str | None = None,
    result_refs: list | None = None,
    findings: list | None = None,
    evidence_level: str = "engineering",
) -> dict:
    return {
        "status": status,
        "project_id": document.get("project_id"),
        "revision_id": document.get("revision_id"),
        "requested_action": requested_action,
        "result_refs": result_refs or [],
        "pending_tasks": pending_tasks or [],
        "findings": findings or [],
        "next_action": next_action,
        "input_alignment": input_alignment(document),
        "review_url": None,  # real loopback URL arrives with the workbench (T05/T14)
        "view_status": "view_arrives_with_workbench",
        "evidence_level": evidence_level,
    }


def _validate_task_response_protocol(response_protocol):
    if response_protocol not in (None, "task_receipt.v1"):
        raise ServiceError("response_protocol", "unsupported task response protocol; use task_receipt.v1 or omit for legacy work orders")


def _task_receipt(response: dict, task: dict) -> dict:
    """Negotiated mutation facts, never a work order or proof of input reading.

    The caller supplies the transaction's fixed snapshot/task (the applied
    snapshot for exact replay). No other pending task or source is expanded.
    """
    fields = ("task_id", "operation_id", "kind", "intent", "status", "scope_pages",
              "dispatch_revision", "produced_against", "execution_ref", "execution_started_at",
              "protocol_version", "required_capabilities", "host_protocol", "call_allowances",
              "result_refs", "candidate_refs", "generation_requests", "generation_attempts")
    response.pop("pending_tasks", None)
    response.update({
        "schema_version": "task_receipt.v1",
        "task": {key: copy.deepcopy(task[key]) for key in fields if key in task},
        "context_ready": False,
        "context_read": {"command": "methods", "task_id": task["task_id"],
                         "read_protocol": "work_context.v2", "body_mode": "full"},
    })
    return response




def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_operation_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _new_source_id(existing_ids: set[str]) -> str:
    candidate = f"src-{uuid.uuid4().hex[:8]}"
    while candidate in existing_ids:
        candidate = f"src-{uuid.uuid4().hex[:8]}"
    return candidate


@response_projection
@after_action
def create(
    project_dir: Path | str,
    *,
    brief: str,
    title: str = "",
    sources: list[Path | str] | None = None,
    design: dict | None = None,
    draft: dict | None = None,
    audience: str = "",
    scenario: str = "",
    presentation_mode: str | None = None,
    page_limit: int | None = None,
    existing_decisions: list[str] | None = None,
    project_format: str | None = None,
    request_input: dict | None = None,
    adapter_context=None,
    selected_resource_ids=None,
    business_framing: bool = False,
) -> dict:
    """Publish a complete RC3 project atomically; no old writer is visible."""
    import shutil
    import tempfile
    from . import collaboration, content_production
    from .project_initialization import collaboration_region, request_defaults
    if project_format not in (None, "workbench.v3"):
        raise ServiceError("project_format", "only the current workbench.v3 format can be created")
    if type(business_framing) is not bool:
        raise ServiceError('business_framing', 'expected a boolean contract opt-in')
    if business_framing and (draft is not None or (request_input or {}).get('content_intent') in ('write_only', 'speech_only')
                            or (request_input or {}).get('intent', 'full_deck') not in ('full_deck', 'content_only')):
        raise ServiceError('business_framing', 'business framing is for new planning, not a confirmed or bounded manuscript')
    if draft is not None:
        _validate_draft(draft)
    target = Path(project_dir).expanduser().absolute()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ServiceError("project", "select a new or empty project directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    private = Path(tempfile.mkdtemp(prefix=".rc3-create-", dir=target.parent))
    stage = private / target.name
    store = Store(stage)
    try:
        discovered = discover_sources(sources or [], out_dir=target)
        extracts = []
        for source_path in discovered["adopted"]:
            try:
                extract, data = read_source_snapshot(source_path)
                extracts.append((source_path, extract, data))
            except (SourceUnreadable, SourceUnsupported) as exc:
                if source_path.resolve() in discovered["explicit"]:
                    raise
                discovered["errored"].append({"path": str(source_path), "code": exc.error_code, "detail": str(exc)})
        store.ensure_layout()
        entries, seen = [], set()
        for path, extract, data in extracts:
            entry = _entry_from_extract(store, path, extract, _new_source_id(seen), data=data)
            entries.append(entry); seen.add(entry["source_id"])
        mode_source = "provided" if presentation_mode is not None else "default"
        document = new_document(project_id=target.name if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", target.name)
            else "project-" + uuid.uuid4().hex,
            task={"title": title or "Deck task", "brief": brief, "audience": audience,
                "scenario": scenario, "presentation_mode": presentation_mode or "live",
                "presentation_mode_source": mode_source, "page_limit": page_limit,
                "existing_decisions": existing_decisions or []},
            design_context=normalize_design_assets(store, design or {}, base_dir=target), sources=entries,
            operation_id=_new_operation_id("create"))
        document["collaboration"] = collaboration_region(imported=draft is not None)
        from .models import require_writer
        require_writer(document, "rc3-entry.v1")
        if draft is not None:
            from .project_initialization import prepare_manuscript
            document, _ = prepare_manuscript(store, document, draft, adapter_context=adapter_context)
        store.init_project(document, operation_id=document["change"]["operation_id"])
        request = request_defaults(store, document, supplied=request_input,
            page_ids=[p["page_id"] for p in (draft or {}).get("pages", [])], imported=draft is not None)
        collaboration.start_request(stage, input=request, base_revision=document["revision_id"],
            operation_id=_new_operation_id("request"), adapter_context=adapter_context)
        document = store.load_document()
        dispatched_task = None
        if request["intent"] in ("full_deck", "content_only"):
            if content_production.completion_status(store, document)['state'] == 'completed':
                updated = content_production.close_completed_content_request(store, copy.deepcopy(document))
                collaboration.commit_collaboration_change(store, document, operation_id=_new_operation_id('complete'),
                    action='request.complete', digest=collaboration.payload_digest('request.complete', {'request_id': request.get('request_id')}),
                    description='Complete the requested fixed content without production', updated=updated,
                    response={'request_id': updated['collaboration']['request']['request_id'], 'closed_reason': 'completed'})
            else:
                dispatched_task = content_production.next_phase_task(store, document, selected_resource_ids=selected_resource_ids,
                                                                     business_framing=business_framing)
        if selected_resource_ids is not None and dispatched_task is None:
            raise ServiceError("selected_resource_ids", "resource selection requires a new Task dispatch")
        if not target.exists():
            target.mkdir()
        (stage / ".deckmaster").rename(target / ".deckmaster")
    finally:
        shutil.rmtree(private)
    store = Store(target); document = store.load_document()
    response = _response(status="created", document=document, requested_action="create",
        pending_tasks=_pending_host_tasks(document, store), next_action="submit_host_results" if not draft else "inspect_imported_manuscript")
    response.update(sources_adopted=[{"source_id": entry["source_id"], "name": entry["name"]} for entry in entries],
        sources_skipped=discovered["skipped"], sources_errored=discovered["errored"])
    response["completion"] = content_production.completion_status(store, document)
    return response


def _validate_draft(payload):
    if not isinstance(payload, dict):
        raise ServiceError("draft", "a manuscript object is required")
    unknown = set(payload) - {"pages", "page_order", "brief", "title", "schema_version", "content_plan"}
    if unknown:
        raise ServiceError("draft", f"unsupported manuscript fields: {sorted(unknown)}")
    if payload.get("schema_version") not in (None, "deck_draft.v1"):
        raise ServiceError("draft/schema_version", "unsupported manuscript version")
    if payload.get("content_plan") is not None:
        from .models import validate_schema
        validate_schema("content_plan_input", payload["content_plan"])
    pages = payload.get('pages') if isinstance(payload, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ServiceError('(draft)/pages', 'draft must carry a non-empty pages array')
    ids = [check_page(page)['page_id'] for page in pages]
    order = payload.get('page_order') or ids
    if len(set(ids)) != len(ids) or len(order) != len(ids) or set(order) != set(ids):
        raise ServiceError('(draft)/page_order', 'must list each unique page exactly once')




def revision_compose_task(store: Store, document, *, operation_id, reason, impact=None, selected_resource_ids=None) -> dict:
    """Build the input-reconciliation task for this project's writer boundary.

    A collaboration.v1 project dispatches the phased compose.v2
    ``input_revision`` variant; every older project keeps the historical
    compose.v1 content-update task. Callers that already own a transaction
    commit the returned task themselves. When an impact analysis is available
    its concrete claim/page list travels with the instruction, so the
    revision works against named objects instead of a general "inputs changed".
    """
    if collaboration_required(document):
        from .content_production import build_phase_task
        instruction = (f"输入已更新（operation {operation_id}）：{reason}。读取新输入与 diff，"
                       "提交 compose.v2 input_revision：changed_layers、每个变化层的 proposal Ref 与 diff。")
        if impact is not None:
            from .content_impact import impact_summary_text
            instruction += f" 影响分析：{impact_summary_text(impact)}。"
        return build_phase_task(
            store, document, operation_id=_new_operation_id("compose"), intent="input_revision",
            input_revision_id=operation_id, instruction=instruction, selected_resource_ids=selected_resource_ids)
    return _input_compose_task(document, operation_id=operation_id, reason=reason, store=store, selected_resource_ids=selected_resource_ids)


def _input_compose_task(document, *, operation_id, reason, store=None, selected_resource_ids=None):
    pages = document.get("pages") or []
    if pages:
        intent = "input_revision"
        scope = [entry["page_id"] for entry in pages]
        instruction = (
            f"输入已更新（operation {operation_id}）：{reason}。"
            "读取新输入、变化说明与全稿概览，检查相关正文和跨页结论；提交 content_update，"
            "只包含真正变化的完整 Page v2、新增/删除页 ID 和最终页序；无影响时给出具体 unchanged_reason。"
        )
    else:
        intent = "initial"
        scope = []
        instruction = (
            f"输入已更新（operation {operation_id}）：{reason}。"
            "读取全部来源与任务事实，按方法写完整 Page v2 正文与页序。"
        )
    methods = method_resources("compose", intent=intent)
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12],
        operation_id=_new_operation_id("compose"),
        kind="compose",
        intent=intent,
        input_digest=compute_input_digest(document),
        input_revision_id=operation_id,
        method_release=method_release(methods),
        scope_pages=scope,
        instruction=instruction,
        inputs=[],
        dependencies=[{"kind": "content",
                       "identity": f"document-revision:{document['revision_id']}",
                       "sha256": content_identity(document)}],
        dispatch_revision=document["revision_id"],
        produced_against=content_identity(document),
        selected_resource_ids=selected_resource_ids,
    )
    from .content_plan import protocol_fields
    task.update(protocol_fields(document, intent, store=store))
    return task


def open_compose_task(store: Store, document: dict, *, operation_id: str,
                      intent: str = "initial", input_revision_id: str | None = None,
                      phase: str | None = None, selected_resource_ids=None) -> dict:
    """Open a compose Host task against the current content identity.

    The routing decision runs first (CONTRACTS §6.2 row 1): a content task
    consumes the request's own intent/scope/decision state before any task
    object is created. A collaboration.v1 project then dispatches the phased
    compose.v2 protocol (CONTRACTS §11.5); every older project keeps the
    historical compose.v1 dispatch byte-for-byte.
    """
    eligibility.guard(store, document, "dispatch.compose")
    if collaboration_required(document) and intent != "import_draft":
        # An imported draft is already a complete manuscript: it keeps the
        # historical import envelope instead of entering the phased protocol.
        from .content_production import open_phase_task
        return open_phase_task(store, document, operation_id=operation_id, intent=intent,
                               input_revision_id=input_revision_id, phase=phase, selected_resource_ids=selected_resource_ids)
    produced_against = content_identity(document)
    methods = method_resources("compose", intent=intent)
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12],
        operation_id=operation_id,
        kind="compose",
        intent=intent,
        input_digest=compute_input_digest(document),
        input_revision_id=input_revision_id,
        method_release=method_release(methods),
        scope_pages=[],
        instruction=(
            "Read every source in Task.sources plus the method resources; derive the "
            "audience's open question and write complete visible copy as Page v2 with "
            "an explicit page order. Same source supports different framings; do not "
            "call a rule planner or fill pages from templates."
        ),
        inputs=[],
        dependencies=[
            {
                "kind": "content",
                "identity": f"document-revision:{document['revision_id']}",
                "sha256": produced_against,
            }
        ],
        dispatch_revision=document["revision_id"],
        produced_against=produced_against,
        selected_resource_ids=selected_resource_ids,
    )
    from .content_plan import protocol_fields
    task.update(protocol_fields(document, intent, store=store))
    task_ref = store.put_json_object(task)
    bumped = bump_revision(
        document,
        {
            "operation_id": f"dispatch-{uuid.uuid4().hex[:12]}",
            "kind": "task_update",
            "description": "compose task opened for Host",
            "read_set": [],
        },
    )
    bumped["tasks"] = list(document.get("tasks") or []) + [task_ref]
    store.commit_change(
        base_revision=document["revision_id"],
        document=bumped,
        operation_id=bumped["change"]["operation_id"],
    )
    return task


def _pending_host_tasks(document: dict, store: Store, *, include_trials=True, read_protocol=None, body_mode=None, cache_offer=None, observed_context=None, collector=None) -> list[dict]:
    from .work_context import active_collector, ResourceCollector, validate_options
    mode = validate_options(read_protocol, body_mode, cache_offer)
    collector = collector or active_collector()
    own_collector = collector is None and read_protocol is not None
    if own_collector:
        collector = ResourceCollector(body_mode=mode, cache_offer=cache_offer, observed_context=observed_context)
    if collector is not None:
        store = collector.store(store)
    pending = []
    dispatch_documents = {}
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if (task.get("status") in ("awaiting_host", "running") and
                (include_trials or task.get("stage_request", {}).get("mode") != "trial")):
            pending.append(task_summary(store, document, task, dispatch_documents=dispatch_documents, collector=collector))
    return collector.envelope({"project_id": document["project_id"], "current_revision": document["revision_id"], "tasks": pending}) if own_collector else pending


@tasks_mod._project_transaction
def _retire_missing_page_inputs(store: Store, document: dict | None = None) -> dict:
    """Recover older runs whose pending review outlived its actual inputs."""
    document = store.load_document()
    affected = {e['page_id'] for e in document.get('pages') or []
                if not e.get('svg') or not e.get('svg_preview')}
    updated = dict(document)
    updated['tasks'] = list(document.get('tasks') or [])
    changed = False
    for index, ref in enumerate(updated['tasks']):
        task = store.read_object_json(ref)
        if (task.get('status') in ('awaiting_host', 'running') and
                task.get('review_stage') == 'page_visual' and
                task.get('kind') in ('review', 'repair') and
                (affected.intersection(task.get('scope_pages') or []) or
                 len(task.get('scope_pages') or []) != 1)):
            updated['tasks'][index] = store.put_json_object(
                {**task, 'status': 'superseded', 'updated_at': _utc_now_iso()})
            changed = True
    changed = bool(tasks_mod._supersede_stale_reviews(store, updated)) or changed
    if not changed:
        return document
    bumped = bump_revision(updated, {'operation_id': _new_operation_id('retire'),
                                    'kind': 'task_update',
                                    'description': 'retire review task with missing or changed inputs',
                                    'read_set': []})
    store._commit_locked(base_revision=document['revision_id'], document=bumped,
                         operation_id=bumped['change']['operation_id'], blobs=[])
    return store.load_document()


def _dispatch_snapshot(store: Store, document: dict, task: dict) -> dict:
    """The revision the task was dispatched in; the work order binds to it."""
    revision = task.get("dispatch_revision")
    if revision and revision != document.get("revision_id"):
        return store.load_document(revision)
    return document


def _project_context(store: Store, document: dict, task: dict, dispatched: dict) -> dict:
    """Task facts + input freshness for the work order (spec v1.1 §3.3).

    A still-valid task reads its task/sources from the dispatch snapshot, not
    from whatever the current Document happens to carry. A task superseded by
    an input update, or one whose inputs moved underneath it, is ``stale``:
    continue hands out a fresh task.
    """
    status = task.get("status")
    if status in ("completed", "failed", "cancelled"):
        context_status = "terminal"
    elif status == "superseded" or not tasks_mod.task_inputs_current(store, document, task):
        context_status = "stale"
    else:
        context_status = "current"
    task_fields = dict(dispatched.get("task") or document.get("task") or {})
    task_fields["presentation_mode_source"] = task_fields.get("presentation_mode_source") or "default"
    context = {
        "task": task_fields,
        "input_digest": compute_input_digest(dispatched),
        "dispatch_revision": task.get("dispatch_revision"),
        "current_revision": document.get("revision_id"),
        "context_status": context_status,
        "input_alignment": input_alignment(document),
    }
    if context_status == "stale":
        context["hint"] = "inputs moved after dispatch; run deck-master continue to obtain a fresh task"
    return context


def task_summary(store: Store, document: dict, task: dict, *, dispatch_documents=None,
                 read_protocol=None, body_mode=None, cache_offer=None, observed_context=None, collector=None) -> dict:
    from .work_context import active_collector, ResourceCollector, validate_options
    mode = validate_options(read_protocol, body_mode, cache_offer)
    collector = collector or active_collector()
    own_collector = collector is None and read_protocol is not None
    if own_collector:
        collector = ResourceCollector(body_mode=mode, cache_offer=cache_offer, observed_context=observed_context)
    if collector is None:
        return _task_summary_v1(store, document, task, dispatch_documents=dispatch_documents)
    store = collector.store(store)
    try:
        order = _task_summary_v1(store, document, task,
                                dispatch_documents=dispatch_documents if dispatch_documents is not None else collector.documents,
                                collector=collector)
    except (StoreError, OSError, ValueError) as exc:
        # A damaged immutable dependency cannot erase still-readable Task,
        # source and Page facts, or be replaced by a different current version.
        from .method_resources import resolve_task_methods
        resolved = resolve_task_methods(task, reader=collector.read_method)
        order = {**copy.deepcopy(task), 'method_resources': resolved['methods'],
                 'method_basis_status': resolved['basis_status'], 'method_basis_issues': resolved['issues'],
                 'method_manifest': resolved['method_manifest'],
                 'current_method_release': resolved['current_method_release'],
                 'project_context': {'current_revision': document['revision_id'],
                                     'dispatch_revision': task.get('dispatch_revision'), 'context_status': 'unavailable'},
                 'source_reading': [], 'sources': [], 'page_entries': [],
                 'work_order_gap': str(exc)}
        collector.unavailable('work_order', task['task_id'],
                              {'reader': 'work context', 'task_id': task['task_id'],
                               'dispatch_revision': task.get('dispatch_revision')}, exc)
        try:
            dispatched = _dispatch_snapshot(store, document, task)
            order['sources'] = copy.deepcopy(dispatched.get('sources') or [])
            order['page_entries'] = [copy.deepcopy(entry) for entry in dispatched.get('pages') or []
                                     if entry['page_id'] in (task.get('scope_pages') or [])]
            order['resolved_design_context'] = copy.deepcopy(dispatched.get('design_context') or {})
            order['outputs'] = copy.deepcopy(dispatched.get('outputs') or {})
            order['reference_images'] = []
            from PIL import Image
            import io
            for entry in order['page_entries']:
                if not entry.get('blueprint'):
                    continue
                original, dimensions = None, None
                try:
                    original = store.read_object_json(entry['blueprint'])
                    with Image.open(io.BytesIO(store.read_object_bytes(original['file']))) as image:
                        dimensions = list(image.size)
                except (StoreError, OSError, ValueError) as image_exc:
                    collector.unavailable('original_image', entry['page_id'],
                                          {'reader': 'immutable object', 'artifact': entry['blueprint']}, image_exc)
                order['reference_images'].append({'page_id': entry['page_id'], 'artifact': entry['blueprint'],
                                                  'file': original['file'] if original else None,
                                                  'dimensions': dimensions,
                                                  'requirement': 'Read this exact immutable image before reconstructing; matching page text alone does not establish visual fidelity.'})
            order['source_inventory_state'] = 'available'
        except (StoreError, OSError, ValueError):
            order['source_inventory_state'] = 'unavailable'
    order = collector.project(store, document, order)
    return collector.envelope({"project_id": document["project_id"], "current_revision": document["revision_id"],
                               "tasks": [order]}) if own_collector else order


def _task_summary_v1(store: Store, document: dict, task: dict, *, dispatch_documents=None, collector=None) -> dict:
    """The Host work order: identity, inputs, resolved design, method entrypoints."""
    revision = task.get("dispatch_revision")
    if dispatch_documents is None:
        dispatched = _dispatch_snapshot(store, document, task)
    else:
        # One response may contain many tasks from the same immutable dispatch
        # snapshot. Read that snapshot once for this response, never across
        # operations; current task/input freshness is still checked below.
        dispatch_key = (str(store.project_root.resolve()), document['project_id'], revision)
        if dispatch_key not in dispatch_documents:
            dispatch_documents[dispatch_key] = _dispatch_snapshot(store, document, task)
        dispatched = dispatch_documents[dispatch_key]
    from .method_resources import resolve_task_methods
    resolved_methods = resolve_task_methods(task, reader=collector.read_method if collector else None)
    methods = resolved_methods["methods"]
    from . import visual_styles
    summary = {
        "task_id": task["task_id"],
        "operation_id": task["operation_id"],
        "kind": task["kind"],
        "intent": task.get("intent"),
        "method_release": task.get("method_release"),
        "current_method_release": resolved_methods["current_method_release"],
        "method_basis_status": resolved_methods["basis_status"],
        "method_basis_issues": resolved_methods["issues"],
        "method_manifest": resolved_methods["method_manifest"],
        "content_validation_policy": task.get("content_validation_policy"),
        "review_stage": task.get("review_stage", "final"),
        "status": task["status"],
        "scope_pages": task.get("scope_pages") or [],
        "instruction": task.get("instruction") or "",
        "inputs": task.get("inputs") or [],
        "dispatch_revision": task.get("dispatch_revision"),
        "produced_against": task.get("produced_against"),
        "call_allowances": task.get("call_allowances") or [],
        "sources": dispatched.get("sources") or [],
        "resolved_design_context": dispatched.get("design_context") or {},
        "method_resources": methods,
        **({"visual_analysis": visual_styles.work_order(store, document, task)} if task["kind"] == "style_analyze" else {}),
        "project_context": _project_context(store, document, task, dispatched),
        "staging_dir": str(store.staging_dir / task['operation_id']),
    }
    for key in ("collaboration_binding", "stage_request", "candidate_refs", "execution_ref", "execution_started_at"):
        if key in task:
            summary[key] = task[key]
    if task.get("change_binding"):
        from .changes import action_for_task
        summary["change_binding"] = task["change_binding"]
        summary["change_action"] = action_for_task(store, document, task)
    if task.get("review_units") is not None:
        summary["review_plan"] = {"units": task["review_units"]}
    for key in ("protocol_version", "required_capabilities", "host_protocol", "generation_requests", "generation_attempts"):
        if key in task:
            summary[key] = task[key]
    if task.get('status') in ('superseded', 'cancelled', 'completed', 'failed'):
        if task.get('status') == 'superseded':
            summary['invalidated_reason'] = 'task inputs or page scope changed; continue creates a current task'
        return summary
    if task.get('content_operation_ref'):
        summary['content_operation'] = store.read_object_json(task['content_operation_ref'])
        summary['content_operation']['annotation_policy'] = 'retain_original_basis'
    if task.get("protocol_version") == "compose.v1":
        from .content_plan import projection, source_version
        summary["content_plan_contract"] = {"schema_version": "content_plan_input.v1", "required": True,
            "sources": [{"source_id": s["source_id"], "source_version": source_version(s)} for s in dispatched["sources"]],
            "prior": projection(store, dispatched),
            "instruction": "Return content_plan with every resulting page goal, chapter, versioned source locator and unresolved fact; Page remains the body-copy truth."}
    from .store import StoreError
    summary['source_reading'] = []
    for source in dispatched.get('sources') or []:
        ref=source.get('extract')
        if ref and ref['path'].endswith('.json'):
            try:
                extract=store.read_object_json(ref)
                summary['source_reading'].append({
                    'source_id': source['source_id'], **extract,
                    'extract_path': str(store.project_root / ref['path']),
                    'original_path': str(store.project_root / extract['original_file']['path'])
                    if extract.get('original_file') else extract['original_uri'],
                })
            except (StoreError, OSError, ValueError, KeyError, TypeError):
                if collector is None:
                    raise
                continue
    if task.get('review_subject') is not None:
        summary['review_subject'] = task['review_subject']
    if task.get('kind') in ('reconstruct','repair','review'):
        summary['page_entries'] = [e for e in document['pages'] if e['page_id'] in task['scope_pages']]
        summary['reference_images'] = []
        summary['page_design_contexts'] = {}
        for entry in summary['page_entries']:
            from .production import adopted_blueprint_design, resolve_page_design
            if task.get('review_stage') == 'original_image':
                from .original_review import task_packet
                _, fixed_original = task_packet(store, task)
                effective = fixed_original['resolved_design']
                summary['original_expression_packet'] = fixed_original
                summary['reference_images'] = [{'page_id': fixed_original['page_id'],
                    'artifact': fixed_original['original_ref'], 'file': fixed_original['image_ref'],
                    'path': str(store.project_root / fixed_original['image_ref']['path']),
                    'requirement': fixed_original['review_instructions']}]
            elif task.get('review_stage') == 'preproduction':
                # Requalify the current manuscript before regenerating an old
                # image; content review does not consume its visual recipe.
                page = store.read_object_json(entry['page'])
                effective, _ = resolve_design(page, document['design_context'],
                                              document['design_context'].get('assets') or [])
            else:
                original_entry = next(e for e in dispatched['pages'] if e['page_id'] == entry['page_id'])
                original_design = adopted_blueprint_design(store, dispatched, original_entry)
                if (original_design is not None and (entry['blueprint'] != original_entry['blueprint']
                        or original_entry['blueprint'] not in task.get('inputs', []))):
                    raise ServiceError('task/inputs', 'adopted blueprint is outside the actual consumer Task inputs')
                effective=resolve_page_design(store,document,entry,require_current=True)
                if (('content_requirements' in effective or 'content_requirements_v1' in task.get('required_capabilities', []))
                        and entry['blueprint'] not in task.get('inputs', [])):
                    raise ServiceError('task/inputs', 'adopted blueprint is outside the actual consumer Task inputs')
            summary['page_design_contexts'][entry['page_id']]=effective
            if len(summary['page_entries']) == 1 and 'content_requirements' in effective:
                summary['resolved_design_context'] = copy.deepcopy(effective)
            if entry['blueprint'] and task.get('review_stage') != 'original_image':
                from PIL import Image
                import io
                original = None
                try:
                    original=store.read_object_json(entry['blueprint'])
                    with Image.open(io.BytesIO(store.read_object_bytes(original['file']))) as image:
                        dimensions=list(image.size)
                except (StoreError, OSError, ValueError) as exc:
                    if collector is None:
                        raise
                    collector.unavailable('original_image', entry['page_id'],
                                          {'reader': 'immutable object', 'artifact': entry['blueprint'],
                                           'file': original.get('file') if original else None}, exc)
                    dimensions = None
                summary['reference_images'].append({'page_id':entry['page_id'],'artifact':entry['blueprint'],'file':original['file'] if original else None,'dimensions':dimensions,'requirement':'Read this exact immutable image before reconstructing; matching page text alone does not establish visual fidelity.'})
        summary['outputs'] = document['outputs']
        summary['staging_dir'] = str(store.staging_dir / task['operation_id'])
        if task.get('review_stage') == 'page_visual':
            from .editing import _current_artifact_digests
            digests = _current_artifact_digests(store, document)
            summary['page_visual_requirements'] = []
            summary['prior_page_visual_findings'] = []
            for entry in summary['page_entries']:
                effective = summary['page_design_contexts'][entry['page_id']]
                keys = [f"content:page:{entry['page_id']}", f"blueprint:{entry['page_id']}",
                        f"artifact:svg:{entry['page_id']}", f"style:{entry['page_id']}"]
                keys += [f'asset:{aid}' for aid in effective.get('allowed_asset_ids') or []]
                summary['page_visual_requirements'].append({
                    'page_id': entry['page_id'],
                    'subject_refs': [entry[slot] for slot in ('page', 'blueprint', 'svg', 'svg_preview')],
                    'dependencies': [{'kind': key.split(':', 1)[0],
                                      'identity': key.split(':', 1)[1], 'sha256': digests[key]}
                                     for key in keys],
                    'review_kinds': list(PAGE_VISUAL_KINDS),
                })
                for ref in document.get('reviews') or []:
                    prior = store.read_object_json(ref)
                    if (prior.get('review_stage') != 'page_visual' or
                            prior.get('kind') not in PAGE_VISUAL_KINDS or
                            not prior.get('findings')):
                        continue
                    if any(dep.get('kind') == 'content' and dep.get('identity') == f"page:{entry['page_id']}"
                           for dep in prior.get('dependencies') or []):
                        summary['prior_page_visual_findings'].append({
                            'review_ref': ref, 'review_id': prior['review_id'],
                            'kind': prior['kind'], 'findings': prior['findings'],
                        })
        elif task.get('kind') == 'review':
            from .editing import page_visual_summary
            summary['prior_page_visual_evidence'] = []
            for entry in summary['page_entries']:
                if all(entry.get(slot) for slot in ('blueprint', 'svg', 'svg_preview')):
                    summary['prior_page_visual_evidence'].append({
                        'page_id': entry['page_id'],
                        'check_summary': page_visual_summary(store, document, entry),
                        'reviews': [ref for ref in document.get('reviews') or []
                                    if (prior := store.read_object_json(ref)).get('review_stage') == 'page_visual'
                                    and entry['page'] in prior.get('subjects', [])],
                        'usage': 'prior observation only; final checks still follow review_plan.units',
                    })
    if task.get("kind") == "blueprint":
        from .production import stored_blueprint_request
        candidate, _ = stored_blueprint_request(store, task)
        if candidate is not None:
            summary["production_request"] = candidate
            if candidate.get("resolved_design_context") is not None:
                summary["resolved_design_context"] = copy.deepcopy(candidate["resolved_design_context"])
            else:
                page = store.read_object_json(next(p["page"] for p in document["pages"] if p["page_id"] == candidate["page_id"]))
                summary["resolved_design_context"], _ = resolve_design(page, document["design_context"], document["design_context"].get("assets") or [])
        if task.get("protocol_version"):
            from .generation import prepared_input
            summary["generation_input"] = prepared_input(store, document, task)
    return summary


@tasks_mod._project_transaction
def open_blueprint_task(store: Store, document: dict, page_entry: dict, *, selected_resource_ids=None) -> dict:
    """Dispatch one Codex ImageGen task with one service-owned allowance."""
    current = store.load_document()
    if content_identity(current) != content_identity(document):
        raise tasks_mod.TaskConflict("(blueprint)", "inputs changed before dispatch")
    document = current
    # An image blueprint is real production: request scope, authorization and
    # preproduction review are checked before the task or its allowance exist.
    eligibility.guard(store, document, "dispatch.blueprint",
                      context={"targets": {"page_ids": [page_entry["page_id"]],
                                           "layers": ["blueprint"]}})
    for ref in document.get("tasks") or []:
        existing = store.read_object_json(ref)
        if existing.get("stage_request", {}).get("mode") != "trial" and existing.get("kind") == "blueprint" and existing.get("status") in ("awaiting_host", "running") and existing.get("scope_pages") == [page_entry["page_id"]]:
            if selected_resource_ids is not None:
                raise ServiceError("selected_resource_ids", "existing Task is frozen; use formal reissue")
            return existing
    # Validate the final dispatch scope before persisting the production request.
    # stamp_task still freezes the final binding below.
    methods = method_resources("blueprint", phase="production",
                               selected_resource_ids=selected_resource_ids)
    page_ref = page_entry["page"]
    page = store.read_object_json(page_ref)
    from .production import resolve_generation_design
    modern = store.workbench_protocol_required(document)
    design = resolve_generation_design(store, document, page_entry) if modern else document["design_context"]
    request = project_prompt(page, design, design.get("assets") or [])
    request["permitted_asset_files"] = _resolve_permitted_asset_files(store, request["projection"]["permitted_assets"])
    request_ref = store.put_json_object(request)
    operation_id = _new_operation_id("blueprint")
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12],
        operation_id=operation_id,
        kind="blueprint",
        method_release=method_release(methods),
        scope_pages=[page["page_id"]],
        instruction=(
            "Codex专用：读取 production_request.prompt，先领取任务并 begin 本任务的调用额度，"
            "使用当前会话内置图像工具生成一张真实蓝图；保存原始图片与实际提交prompt，实际阅图后"
            "settle，再用 blueprint 信封提交。不得请求 Provider/API Key，不得用 fixture 或本地占位图。"
        ),
        inputs=[page_ref, request_ref],
        dependencies=[
            {"kind": "content", "identity": f"page:{page['page_id']}", "sha256": page_ref["sha256"]},
            {"kind": "style", "identity": f"style:{request['projection']['visual_spec']['style_ref']}", "sha256": request["projection_sha256"]},
        ],
        dispatch_revision=document["revision_id"],
        produced_against=content_identity(document),
        cost_class="external_generation",
    )
    from . import collaboration_binding
    collaboration_binding.stamp_task(
        store, document, task, phase="production", executor_type="host",
        page_ids=[page["page_id"]], adoption_policy="within_scope",
        action="dispatch.blueprint",
        action_targets={"page_ids": [page["page_id"]], "layers": ["blueprint"]},
        selected_resource_ids=selected_resource_ids)
    task, _ = tasks_mod.reserve_allowances(store, document, task, 1)
    from .generation import protocol_fields
    task.update(protocol_fields(document, store=store))
    task_ref = store.put_json_object(task)
    bumped = bump_revision(
        document,
        {
            "operation_id": f"dispatch-{operation_id}",
            "kind": "task_update",
            "description": f"blueprint task opened for page {page['page_id']}",
            "read_set": [],
        },
    )
    bumped["tasks"] = list(document.get("tasks") or []) + [task_ref]
    from .models import require_writer
    if modern:
        require_writer(bumped, "rc3.v1")
    store._commit_locked(blobs=[],
        base_revision=document["revision_id"],
        document=bumped,
        operation_id=bumped["change"]["operation_id"],
    )
    refreshed = store.load_document()
    return tasks_mod._lookup_task(refreshed, task["task_id"], store)


def _resolve_permitted_asset_files(store: Store, assets: list[dict]) -> list[dict]:
    """Expose only allowed immutable asset bytes to the Codex task."""
    resolved = []
    for asset in assets:
        try:
            artifact = store.read_object_json(asset["artifact"])
            store.read_object_bytes(artifact['file'])
        except (KeyError, StoreError) as exc:
            raise StoreError(f"asset:{asset.get('asset_id')}",
                             'stored asset reference is unreadable; restore or replace it') from exc
        resolved.append(
            {
                "asset_id": asset["asset_id"],
                "kind": asset.get("kind"),
                "media_type": artifact.get("media_type"),
                "file": artifact.get("file"),
            }
        )
    return resolved


def _eligibility_report(decision: dict) -> dict:
    """The decision projection attached to routing responses (no IDs/hashes in
    the human path; the machine fields stay available for adapters)."""
    return {
        "allowed": decision["allowed"],
        "action": decision["action"],
        "enforcement": decision["enforcement"],
        "reason_codes": decision["reason_codes"],
        "reasons": decision["reasons"],
        "responsible_role": decision["responsible_role"],
        "next_action": decision["next_action"],
        "decision_card": decision["decision_card_ref_or_projection"],
        "scope": decision["scope"],
    }


@response_projection
@after_action
def continue_project(project_dir: Path | str, *, selected_resource_ids=None) -> dict:
    """Run runnable local work and return the stable pending Host tasks.

    `continue` is a routing action: it consumes the same eligibility judgement
    and reports it as a decision card/gap list (CONTRACTS §5: waiting for the
    user is not a production task), while every dispatch it attempts goes
    through its own gated helper.
    """
    try:
        result = _continue_project(project_dir, selected_resource_ids=selected_resource_ids)
    except eligibility.EligibilityBlocked as exc:
        # A blocked dispatch is reported as a decision/stop card instead of an
        # exception (CONTRACTS §5: waiting for the user is not a production
        # task); nothing was dispatched, so the card is the whole answer.
        document = Store(Path(project_dir)).load_document()
        decision = exc.decision
        response = _response(
            status="needs_input", document=document, requested_action="continue",
            findings=[{"code": decision["reason_codes"][0],
                       "field": f"eligibility/{decision['action']}",
                       "message": decision["reasons"][0]["detail"],
                       "reasons": decision["reasons"],
                       "responsible_role": decision["responsible_role"],
                       "next_action": decision["next_action"],
                       "decision_card": decision["decision_card_ref_or_projection"]}],
            next_action=decision["next_action"] or "resolve_admission_gap")
        if decision["enforcement"] == "active":
            response["eligibility"] = _eligibility_report(decision)
        return response
    except tasks_mod.CallBlocked as exc:
        document = Store(Path(project_dir)).load_document()
        return _with_eligibility(project_dir, _response(
            status="needs_input", document=document, requested_action="continue",
            findings=[{"code": "external_call_blocked", "field": exc.path, "message": exc.detail}],
            next_action="resolve_external_call_block"))
    except StoreError as exc:
        if not exc.path.startswith('asset:'):
            raise
        document = Store(Path(project_dir)).load_document()
        return _with_eligibility(project_dir, _response(
            status='needs_input', document=document, requested_action='continue',
            findings=[{'code': 'broken_asset_reference', 'field': exc.path,
                       'message': exc.detail}], next_action='restore_or_replace_asset'))
    return _with_eligibility(project_dir, result)


def _with_eligibility(project_dir, response: dict) -> dict:
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    decision = eligibility.evaluate(store, document, document, "continue_project")
    from .content_production import completion_status
    response["completion"] = completion_status(store, document)
    if decision["enforcement"] == "active":
        response["eligibility"] = _eligibility_report(decision)
    return response


@tasks_mod._project_transaction
def _recover_input_revision(store, *, selected_resource_ids=None):
    document = store.load_document()
    all_tasks = [store.read_object_json(ref) for ref in document.get('tasks') or []]
    if input_alignment(document) != 'needs_reconciliation':
        stale = [index for index, task in enumerate(all_tasks)
                 if task.get('kind') == 'compose' and task.get('intent') == 'input_revision'
                 and task.get('status') in ('awaiting_host', 'running', 'queued')
                 and not tasks_mod.task_inputs_current(store, document, task)]
        if stale:
            updated = bump_revision(document, {'operation_id': _new_operation_id('retire-input'),
                                     'kind': 'task_update', 'description': 'retire stale input revisions', 'read_set': []})
            for index in stale:
                updated['tasks'][index] = store.put_json_object(
                    {**all_tasks[index], 'status': 'superseded', 'updated_at': _utc_now_iso()})
            store._commit_locked(base_revision=document['revision_id'], document=updated,
                                 operation_id=updated['change']['operation_id'], blobs=[])
        return
    valid = next((task for task in reversed(all_tasks)
                  if task.get('kind') == 'compose' and task.get('intent') == 'input_revision'
                  and task.get('status') in ('awaiting_host', 'running')
                  and tasks_mod.task_inputs_current(store, document, task)), None)
    if valid and not any(task.get('kind') in tasks_mod.HOST_TASK_KINDS
                         and task.get('status') in ('awaiting_host', 'running', 'queued')
                         and task['task_id'] != valid['task_id'] for task in all_tasks):
        return
    # Use the operation that caused the mismatch, not a later display-name edit.
    origin = document
    while origin.get('parent_revision_id'):
        change = origin.get('change') or {}
        if change.get('kind') == 'restore':
            break
        if change.get('kind') == 'input_update':
            parent = store.load_document(origin['parent_revision_id'])
            if compute_input_digest(parent) != compute_input_digest(origin):
                break
        origin = store.load_document(origin['parent_revision_id'])
    change = origin.get('change') or {}
    updated = bump_revision(document, {'operation_id': _new_operation_id('resume-input'),
                                       'kind': 'task_update', 'description': 'resume input reconciliation', 'read_set': []})
    for index, task in enumerate(all_tasks):
        if (task.get('kind') in tasks_mod.HOST_TASK_KINDS
                and task.get('status') in ('awaiting_host', 'running', 'queued')
                and (not valid or task['task_id'] != valid['task_id'])):
            updated['tasks'][index] = store.put_json_object({**task, 'status': 'superseded', 'updated_at': _utc_now_iso()})
    if not valid:
        # The recovery dispatch is a real write, not routing bookkeeping: it
        # consumes the same gate as every other phased dispatch, so a paused
        # request gains no reconciliation task through `continue` either
        # (independent re-review N1, F06's contract).
        task = revision_compose_task(store, updated, operation_id=change.get('operation_id'),
                                   reason=change.get('description') or 'Resume reconciliation against current inputs',
                                   selected_resource_ids=selected_resource_ids)
        eligibility.guard(store, updated, 'dispatch.compose', context={'task': task,
            'targets': (task.get('collaboration_binding') or {}).get('write_scope')})
        updated['tasks'].append(store.put_json_object(task))
    store._commit_locked(base_revision=document['revision_id'], document=updated,
                         operation_id=updated['change']['operation_id'], blobs=[])


def _continue_project(project_dir: Path | str, *, selected_resource_ids=None) -> dict:
    """Run runnable local work; return the stable pending Host tasks.

    Reuse pending work. Reconcile changed inputs before producing existing
    pages; an explicitly resumed cancelled revision gets a new task identity.
    """
    store = Store(Path(project_dir).expanduser())
    initial = store.load_document()
    if selected_resource_ids is not None:
        from .resource_catalog import load_catalog
        from .method_resources import resolve_root
        resources = load_catalog(resolve_root())
        if (not isinstance(selected_resource_ids, (list, tuple)) or any(
                not isinstance(mid, str) or mid not in resources or not resources[mid]['readable']
                for mid in selected_resource_ids)):
            raise ServiceError("selected_resource_ids", "must name registered readable resource IDs")
    if initial.get("collaboration") is None:
        from .collaboration_migration import describe
        return _response(status="needs_input", document=initial, requested_action="continue",
            findings=[{"code": "migration_required", "migration": describe(project_dir)}],
            next_action="describe_and_apply_migration")
    from .content_production import completion_status
    initial_completion = completion_status(store, initial)
    if initial_completion['state'] == 'completed':
        return {**_response(status='completed', document=initial, requested_action='continue',
            next_action=initial_completion['next_action'], result_refs=initial_completion['outputs']), 'completion': initial_completion}
    if initial_completion.get('responsible_role') == 'design':
        # A planning-only request does not authorize content production or a
        # blueprint. Uncommitted proposals remain available by their returned ref.
        return {**_response(status='needs_input', document=initial, requested_action='continue',
            next_action=initial_completion['next_action'], findings=initial_completion['missing']),
            'completion': initial_completion}
    if selected_resource_ids is not None and _pending_host_tasks(initial, store, include_trials=False):
        raise ServiceError("selected_resource_ids", "pending Tasks are frozen; finish or formally retire them before selecting resources for a new dispatch")
    _recover_input_revision(store, selected_resource_ids=selected_resource_ids)
    tasks_mod.reissue_changed_method_tasks(store)
    document = _retire_missing_page_inputs(store, store.load_document())
    pending = _pending_host_tasks(document, store, include_trials=False)
    if any(t["kind"] == "blueprint" for t in pending):
        if document["policy"].get("user_stop"):
            raise tasks_mod.CallBlocked("policy/user_stop", "user stopped external calls")
        if tasks_mod.project_has_unknown_calls(document, store):
            raise tasks_mod.CallBlocked("call_allowances", "resolve unknown calls before continuing")
    for summary in pending:
        if summary["kind"] == "blueprint" and summary["status"] == "awaiting_host" and not summary["call_allowances"]:
            tasks_mod.repair_empty_allowance(store, task_id=summary["task_id"])
    document = store.load_document()
    pending = _pending_host_tasks(document, store, include_trials=False)
    if pending:
        return _response(
            status="awaiting_host",
            document=document,
            requested_action="continue",
            pending_tasks=pending,
            next_action="submit_host_results",
        )
    if collaboration_required(document):
        # Phased content production (CONTRACTS §5/§6.3). This plans content
        # phases only; entry-level eligibility enforcement is T04's card.
        from . import content_production
        completion = content_production.completion_status(store, document)
        if completion["state"] == "completed":
            return {**_response(status="completed", document=document, requested_action="continue",
                next_action="return_requested_content", result_refs=completion["outputs"]), "completion": completion}
        phase_status = content_production.content_phase_status(store, document)
        if phase_status.get("action") == "dispatch":
            task = content_production.next_phase_task(store, document, selected_resource_ids=selected_resource_ids)
            document = store.load_document()
            pending = _pending_host_tasks(document, store, include_trials=False)
            return _response(
                status="awaiting_host",
                document=document,
                requested_action="continue",
                pending_tasks=pending or ([task_summary(store, document, task)] if task else []),
                next_action="submit_host_results",
            )
        if phase_status.get("action") in ("await_decision", "blocked"):
            return _response(
                status="needs_input",
                document=document,
                requested_action="continue",
                findings=[{"code": "decision_needed", "phase": phase_status.get("phase"),
                           "topic": phase_status.get("topic"),
                           "detail": phase_status.get("reason"),
                           "proposal_refs": phase_status.get("proposal_refs")}],
                next_action="record_direction_decision",
            )
    elif not (document.get("pages") or []):
        task = open_compose_task(store, document, selected_resource_ids=selected_resource_ids, operation_id=_new_operation_id("compose"))
        document = store.load_document()
        pending = _pending_host_tasks(document, store, include_trials=False)
        assert pending, "compose task must be pending right after creation"
        return _response(
            status="awaiting_host",
            document=document,
            requested_action="continue",
            pending_tasks=pending,
            next_action="submit_host_results",
        )
    # A completed old run already has a current final review. In-progress old
    # runs and all new runs complete each page's preview/review before moving on.
    from .editing import review_status, page_visual_summary
    already_final = bool(document['outputs'].get('pptx')) and review_status(store, document) == 'pass'
    existing_report_failed = False
    if document['outputs'].get('render_report'):
        import json
        report = store.read_object_json(document['outputs']['render_report'])
        existing_report_failed = json.loads(store.read_object_bytes(report['file'])).get('status') == 'fail'
    for entry in document.get("pages") or []:
        if entry.get('page') and entry.get('blueprint'):
            from .models import ModelError
            from .production import adopted_blueprint_design, resolve_page_design
            try:
                resolve_page_design(store, document, entry, require_current=True)
            except ModelError as exc:
                if exc.path != 'blueprint/content_basis':
                    raise
                bound = adopted_blueprint_design(store, document, entry)
                if bound and bound['recipe_ref'] is not None:
                    return _response(status='needs_input', document=document, requested_action='continue',
                        findings=[{'code': 'blueprint_basis_changed', 'page_id': entry['page_id'],
                            'blueprint_ref': entry['blueprint'], 'recipe_ref': bound['recipe_ref'],
                            'detail': 'The retained original image has a different consumed manuscript basis; preview a bounded new visual change with its fixed recipe.'}],
                        next_action='preview_bounded_visual_change')
                # A formal old bitmap remains immutable history, never fresh
                # evidence for the edited Page. Any replacement still needs
                # the real current image scope, pre-review and bounded credit;
                # a copy-only instruction receives that named admission gap.
                task = open_blueprint_task(store, document, entry, selected_resource_ids=selected_resource_ids)
                current = store.load_document()
                return _response(status='awaiting_host', document=current, requested_action='continue',
                    pending_tasks=[task_summary(store, current, task)],
                    findings=[{'code': 'blueprint_basis_changed', 'page_id': entry['page_id'],
                        'retained_blueprint_ref': entry['blueprint']}], next_action='codex_generate_blueprint')
        if entry.get("page") and not entry.get("blueprint"):
            task = open_blueprint_task(store, document, entry, selected_resource_ids=selected_resource_ids)
            document = store.load_document()
            return _response(status="awaiting_host", document=document, requested_action="continue",
                             pending_tasks=[task_summary(store, document, task)], next_action="codex_generate_blueprint")
        if not entry.get("svg"):
            task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='reconstruct', page_ids=[entry['page_id']],
                instruction='实际阅读原始蓝图并记录上游期待；核对正文，必要纠正写新 Page。按授权资产与有效设计重建可编辑 SVG。保存原图，提交 reconstruct 信封；不得把预览图冒充原始蓝图。')
            document = store.load_document()
            return _response(status='awaiting_host', document=document, requested_action='continue',
                             pending_tasks=[task_summary(store, document, task)], next_action='codex_reconstruct_svg')
        if already_final or existing_report_failed:
            continue
        if not entry.get('svg_preview'):
            from .pipeline import preview_svg_page, NeedsTool, RendererError
            from .compiler.svg import SvgError
            try:
                preview_svg_page(project_dir, entry['page_id'])
            except NeedsTool as exc:
                return _response(status='needs_tool', document=document, requested_action='continue',
                                 findings=[str(exc)], next_action='configure_reported_tool')
            except RendererError as exc:
                return _response(status='needs_input', document=document, requested_action='continue',
                                 findings=[{'code': 'renderer_execution_failed', 'page_id': entry['page_id'],
                                            'message': str(exc)}], next_action='repair_renderer_execution')
            except ConflictError:
                return _continue_project(project_dir, selected_resource_ids=selected_resource_ids)
            except SvgError as exc:
                task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='reconstruct', page_ids=[entry['page_id']],
                    instruction=f'存量 SVG 编译失败：{exc.diagnostic}. 阅读原 Page 和蓝图，提交本页修正后的 SVG；旧 SVG 保留为历史。')
                document = store.load_document()
                return _response(status='awaiting_host', document=document, requested_action='continue',
                                 pending_tasks=[task_summary(store, document, task)],
                                 findings=[exc.diagnostic], next_action='codex_reconstruct_svg')
            document = store.load_document()
            entry = next(e for e in document['pages'] if e['page_id'] == entry['page_id'])
        page_check = page_visual_summary(store, document, entry)
        if page_check['status'] == 'pass':
            continue
        completed_reviews = [store.read_object_json(ref) for ref in document.get('tasks') or []]
        same_input_reviews = [task for task in completed_reviews
                              if task.get('kind') == 'review' and task.get('status') == 'completed'
                              and task.get('review_stage') == 'page_visual'
                              and task.get('scope_pages') == [entry['page_id']]
                              and task.get('produced_against') == content_identity(document)]
        if len(same_input_reviews) >= 2 and page_check['status'] in ('fail', 'needs_review'):
            return _response(status='needs_input', document=document, requested_action='continue',
                             findings=[{'code': 'review_no_progress', 'page_id': entry['page_id'],
                                        'detail': '同一页、同一产物的重复审阅仍有未关闭发现；补充本页修复证据或明确合理差异决定',
                                        'unresolved': page_check}], next_action='review_no_progress')
        if page_check['status'] in ('fail', 'needs_review') and (
                page_check['open_must_fix'] or page_check['unclosed_prior_findings']):
            def candidate_sha(ref):
                obj = store.read_object_json(ref)
                return obj['file']['sha256'] if obj.get('schema_version') == 'deck_artifact.v1' else ref['sha256']
            for ref in document.get('tasks') or []:
                prior = store.read_object_json(ref)
                if (prior.get('kind') != 'repair' or prior.get('review_stage') != 'page_visual'
                        or prior.get('scope_pages') != [entry['page_id']]
                        or prior.get('status') != 'completed'):
                    continue
                prior_hashes = {candidate_sha(item) for item in prior.get('inputs') or []}
                if candidate_sha(entry['page']) in prior_hashes and candidate_sha(entry['svg']) in prior_hashes:
                    return _response(status='needs_input', document=document, requested_action='continue',
                                     findings=[page_check], next_action='repair_no_progress')
        if page_check['status'] == 'fail':
            task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='repair', page_ids=[entry['page_id']],
                                  review_stage='page_visual',
                                  instruction='本页逐页审图有 must_fix：对照 Page、原始蓝图、当前 SVG 与预览，只返修本页 Page/SVG；保留旧产物及具体发现。')
            document = store.load_document()
            return _response(status='awaiting_host', document=document, requested_action='continue',
                             pending_tasks=[task_summary(store, document, task)],
                             findings=[page_check], next_action='repair_page_visual')
        task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='review', page_ids=[entry['page_id']],
                              review_stage='page_visual',
                              instruction='实际打开本页 Page、原始蓝图、SVG 预览，核对正文、数字、模块、图标语义、连线方向和遮挡；提交 blueprint_content、blueprint_fidelity、readability 三类记录。关闭旧发现时，replaces 必须保持同一 review_id、finding_id、page_id、kind 和 review_stage。must_fix 需本页新产物与复核证据；needs_judgment 可用具体理由、观察与证据接受合理差异。不得把原图文字当事实源。')
        document = store.load_document()
        return _response(status='awaiting_host', document=document, requested_action='continue',
                         pending_tasks=[task_summary(store, document, task)],
                         findings=[page_check], next_action='codex_review_page_visual')
    from .pipeline import output_matches_current_svg
    if not output_matches_current_svg(store, document):
        from .pipeline import produce, NeedsTool, RendererError
        from .compiler.svg import SvgError
        try:
            produce(project_dir)
        except NeedsTool as exc:
            return _response(status='needs_tool',document=document,requested_action='continue',findings=[str(exc)],next_action='configure_reported_tool')
        except RendererError as exc:
            return _response(status='needs_input', document=document, requested_action='continue',
                             findings=[{'code': 'renderer_execution_failed', 'message': str(exc)}],
                             next_action='repair_renderer_execution')
        except SvgError as exc:
            page_id = exc.diagnostic.get('page_id')
            if page_id not in {entry['page_id'] for entry in document['pages']}:
                raise
            task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='reconstruct', page_ids=[page_id],
                instruction=f'存量 SVG 编译失败：{exc.diagnostic}. 阅读原 Page 和蓝图，提交本页修正后的 SVG；旧 SVG 保留为历史。')
            document = store.load_document()
            return _response(status='awaiting_host', document=document, requested_action='continue',
                             pending_tasks=[task_summary(store, document, task)],
                             findings=[exc.diagnostic], next_action='codex_reconstruct_svg')
        document = store.load_document()
    report_artifact = store.read_object_json(document['outputs']['render_report'])
    report = store.read_object_json(report_artifact['file'])
    if report['status'] == 'fail':
        from .models import canonical_json_bytes, sha256_bytes
        sig = sha256_bytes(canonical_json_bytes(report['findings']))[:16]
        for ref in document.get('tasks') or []:
            prior = store.read_object_json(ref)
            if prior.get('kind') != 'repair' or prior.get('status') != 'completed' \
                    or f'findings-sig:{sig}' not in (prior.get('instruction') or ''):
                continue
            def _content_sha(ref):
                # Artifact objects are re-created every round even when bytes
                # are identical, so stagnation must compare CONTENT hashes.
                try:
                    obj = store.read_object_json(ref)
                    if obj.get('schema_version') == 'deck_artifact.v1':
                        return obj['file']['sha256']
                except Exception:
                    pass
                return ref.get('sha256')

            prior_inputs = {_content_sha(item) for item in (prior.get('inputs') or [])}
            # Round-B: progress means ANY repair-candidate object moved — the
            # page copy or its blueprint/SVG bytes. Outputs and previews are
            # downstream products re-created on every produce and must not
            # mask candidate-level stagnation (an SVG-only fix is real
            # progress even when the page text did not move).
            candidate_inputs = set()
            for entry in document['pages']:
                for slot in ('page', 'blueprint', 'svg'):
                    ref = entry.get(slot)
                    if ref:
                        candidate_inputs.add(_content_sha(ref))
            candidate_unchanged = candidate_inputs <= prior_inputs
            if candidate_unchanged:
                # Same findings, same repair candidate (page content untouched):
                # another identical repair round would make no progress. Stop
                # and explain instead of looping (spec 08.6/08.7); stopping is
                # not a pass.
                return _response(status='needs_input', document=document, requested_action='continue',
                                 findings=report['findings'], next_action='repair_no_progress')
        task = open_host_task(store, selected_resource_ids=selected_resource_ids,kind='repair',page_ids=[e['page_id'] for e in document['pages']],
                              instruction=f'修复实际 PPT 回读问题，修改对应 Page 或 SVG；保留失败输出。检查报告见输入。findings-sig:{sig}')
        return _response(status='awaiting_host',document=store.load_document(),requested_action='continue',
                         pending_tasks=[task_summary(store,store.load_document(),task)],findings=report['findings'],next_action='repair_readback')
    from .editing import review_status, check_summary
    from .models import input_alignment as _input_alignment
    from .review import final_review_units, describe_review_units
    status = review_status(store, document)
    if status != 'pass':
        repeated_final = [store.read_object_json(ref) for ref in document.get('tasks') or []]
        if (status in ('fail', 'needs_review') and sum(
                task.get('kind') == 'review' and task.get('status') == 'completed' and
                task.get('review_stage', 'final') == 'final' and
                task.get('produced_against') == content_identity(document)
                for task in repeated_final) >= 2):
            return _response(status='needs_input', document=document, requested_action='continue',
                             findings=[{'code': 'review_no_progress',
                                        'detail': '同一产物重复审阅仍有未关闭发现；补充页级修复证据或明确合理差异决定'}],
                             next_action='review_no_progress')
        if status == 'fail':
            task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='repair', page_ids=[e['page_id'] for e in document['pages']],
                instruction='实际打开每页原图、SVG预览及PPT真实渲染，核对正文/模块/图标/数字/方向/Logo。'
                            '存在 must_fix：先修复对象，再按缺口补足审阅；subjects 必须包含当前 PPTX 与发现所在页的当前 Page；'
                            '未实际检查不能 pass，问题返回具体对象。')
        else:
            summary = check_summary(store, document)
            units = final_review_units(document, summary, input_alignment=_input_alignment(document))
            task = open_host_task(store, selected_resource_ids=selected_resource_ids, kind='review', page_ids=[e['page_id'] for e in document['pages']],
                review_units=units,
                instruction=describe_review_units(units))
        return _response(status='awaiting_host',document=store.load_document(),requested_action='continue',
                         pending_tasks=[task_summary(store,store.load_document(),task)],next_action='codex_review_renderings')
    return _response(status='ready_for_export',document=document,requested_action='continue',
                     result_refs=[document['outputs']['pptx']],next_action='export')


def _review_dispatch_scope(store, document, stage, page_ids, units):
    """Compare actual unit scope without changing an existing Task contract."""
    from jsonschema import Draft202012Validator
    from . import models
    from .method_resources import method_ids_for
    if units is None:
        if stage == 'preproduction':
            from .content_review import required_units
            kinds = required_units(store, document)
        else:
            from .review import PAGE_VISUAL_KINDS, REVIEW_DIMENSIONS
            kinds = PAGE_VISUAL_KINDS if stage == 'page_visual' else REVIEW_DIMENSIONS
        units = [{'kind': kind, 'page_ids': page_ids, 'reason': 'missing'} for kind in kinds]
    validator = Draft202012Validator(models.load_schema('task')['properties']['review_units'])
    error = next(validator.iter_errors(units), None)
    if error is not None:
        path = '/'.join(str(part) for part in error.absolute_path)
        raise models.ModelError('task/review_units' + ('/' + path if path else ''), error.message)
    method_ids_for('review', intent=stage, review_units=units)
    grouped = {}
    for unit in units:
        grouped.setdefault((unit['kind'], unit['reason']), set()).update(unit['page_ids'])
    return frozenset((kind, reason, frozenset(pages)) for (kind, reason), pages in grouped.items())


@tasks_mod._project_transaction
def open_host_task(store, *, kind, page_ids, instruction, base_revision=None, page_hash=None,
                   review_stage=None, review_units=None, review_subject=None, extra_inputs=(), executor_type=None,
                   phase=None, selected_resource_ids=None):
    document = store.load_document()
    if base_revision is not None and base_revision != document['revision_id']:
        from .store import ConflictError
        raise ConflictError('revision', 'project changed; reload before submitting feedback')
    if page_hash is not None and not any(e['page_id'] in page_ids and e['page']['sha256'] == page_hash for e in document['pages']):
        from .store import ConflictError
        raise ConflictError('page_hash', 'feedback page changed')
    if kind not in ('reconstruct', 'repair', 'review'):
        raise ServiceError('kind', 'unsupported local host task')
    if review_stage is not None and (review_stage not in ('preproduction', 'page_visual', 'final', 'original_image') or kind not in ('repair', 'review')):
        raise ServiceError('review_stage', 'only review or repair supports preproduction/page_visual/final')
    if not isinstance(instruction, str) or not instruction.strip():
        raise ServiceError('instruction', 'must not be empty')
    if review_subject is not None:
        from .outline_review import require_outline, UNITS
        if (review_subject != 'outline' or kind != 'review' or review_stage != 'preproduction'
                or page_ids or not review_units or
                not {unit['kind'] for unit in review_units} <= set(UNITS)
                or any(unit['page_ids'] for unit in review_units)):
            raise ServiceError('review_subject', 'explicit outline review requires empty pages and argument/progression units')
        require_outline(store, document)
    if (not page_ids and review_subject != 'outline') or len(set(page_ids)) != len(page_ids) or not set(page_ids) <= {e['page_id'] for e in document['pages']}:
        raise ServiceError('scope_pages', 'must name existing distinct pages')
    if review_stage == 'original_image' and (kind != 'review' or len(page_ids) != 1):
        raise ServiceError('original_review', 'original_image requires one page and a review Task')
    if review_stage == 'page_visual' and len(page_ids) != 1:
        raise ServiceError('scope_pages', 'page_visual must target exactly one page')
    host_layers = {"reconstruct": ["svg", "blueprint"], "repair": ["page_copy", "svg"],
                   "review": ["review"]}[kind]
    host_targets = {"page_ids": list(page_ids), "layers": host_layers}
    if review_subject == 'outline':
        from .outline_review import review_targets
        from .native_review import recovery_task_ids
        host_targets = review_targets(store, document)
        if recovery_task_ids(store, document, subject='outline'):
            raise tasks_mod.TaskConflict('review/outline', 'recover the original completion before dispatching another review')
    eligibility.guard(store, document, "dispatch.host_task",
                      context={"targets": host_targets})
    entries = [e for e in document['pages'] if e['page_id'] in page_ids]
    from .production import design_handoff_protocol_fields
    protocol = design_handoff_protocol_fields(store, document, entries) if review_stage not in ('preproduction', 'original_image') else {}
    review_scope = (_review_dispatch_scope(store, document, review_stage, page_ids, review_units)
                    if kind == 'review' else None)
    for ref in document['tasks']:
        task = store.read_object_json(ref)
        if task.get('review_subject') == review_subject and task.get('stage_request', {}).get('mode') != 'trial' and task['kind'] == kind and task['scope_pages'] == page_ids and task['instruction'] == instruction and task.get('review_stage', 'final') == (review_stage or 'final') and task['status'] in ('awaiting_host','running') and (task.get('collaboration_binding') or {}).get('executor_type', 'host') == (executor_type or 'host') and all(task.get(key) == value for key, value in protocol.items()):
            if kind == 'review' and _review_dispatch_scope(
                    store, document, task.get('review_stage'), task['scope_pages'], task.get('review_units')) != review_scope:
                continue
            if kind == 'review' and review_stage in ('preproduction', 'original_image') and not tasks_mod.task_inputs_current(store, document, task):
                continue
            if review_stage == 'original_image' and any(ref not in task.get('inputs', []) for ref in extra_inputs):
                continue
            if selected_resource_ids is not None:
                raise ServiceError("selected_resource_ids", "existing Task is frozen; use formal reissue")
            return task
    inputs = [ref for e in entries for slot,ref in e.items() if slot != 'page_id' and ref]
    inputs += [ref for ref in document['outputs'].values() if ref]
    inputs += [ref for ref in extra_inputs if ref]
    methods = method_resources(kind, intent=review_stage)
    task = tasks_mod.new_task(task_id=uuid.uuid4().hex[:12],operation_id=_new_operation_id(kind),kind=kind,
        method_release=method_release(methods),
        scope_pages=page_ids,instruction=instruction,inputs=inputs,dependencies=[{'kind':'content','identity':e['page_id'],'sha256':e['page']['sha256']} for e in entries],
        dispatch_revision=document['revision_id'],produced_against=content_identity(document),
        review_stage=review_stage,review_units=review_units)
    if review_stage == 'original_image':
        from .models import require_writer
        require_writer(document, 'original-review.v1')
    task.update(protocol)
    if review_subject == 'outline':
        task['review_subject'] = 'outline'
        task['required_capabilities'] = [*task.get('required_capabilities', []), 'outline_review.v1']
    from . import collaboration_binding
    collaboration_binding.stamp_task(
        store, document, task,
        phase=phase or ("review" if kind == "review" else "production"),
        executor_type=executor_type or "host", page_ids=page_ids,
        adoption_policy="within_scope", action="dispatch.host_task",
        action_targets={"page_ids": list(page_ids), "layers": host_layers},
        selected_resource_ids=selected_resource_ids)
    from .business_review import prepare_task
    prepare_task(store, document, task)
    from .models import validate_task_semantics
    validate_task_semantics(task)
    updated=bump_revision(document,{'operation_id':_new_operation_id('dispatch'),'kind':'task_update','description':instruction,'read_set':[]})
    if protocol:
        from .models import require_writer
        require_writer(updated, 'rc3.v1')
    if review_subject == 'outline':
        from .models import require_writer
        require_writer(updated, 'outline-review.v1')
    updated['tasks'].append(store.put_json_object(task))
    store._commit_locked(base_revision=document['revision_id'],document=updated,operation_id=updated['change']['operation_id'],blobs=[])
    return task


# ---------------------------------------------------------------------------
# Inputs show/update (spec v1.1 §5): the persistent way to record changed
# task facts and materials. The update transaction saves inputs, supersedes
# open tasks and dispatches compose/intent=input_revision in one commit.

_INPUT_PATCH_FIELDS = {"task_patch", "source_changes", "reason", "mode"}
_INPUT_TASK_PATCH_FIELDS = {"title", "brief", "audience", "scenario",
                            "presentation_mode", "page_limit", "existing_decisions"}
_PRESENTATION_MODES = ("live", "read_alone", "mixed")


def inputs_show(project_dir: Path | str) -> dict:
    """The current task, sources, content basis and alignment in one read."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    return {
        "status": "ok",
        "project_id": document.get("project_id"),
        "revision_id": document["revision_id"],
        "task": document.get("task") or {},
        "sources": document.get("sources") or [],
        "content_basis": document.get("content_basis"),
        "input_digest": compute_input_digest(document),
        "input_alignment": input_alignment(document),
    }




def _input_request_digest(document, patch, base_revision, patch_dir):
    """Bind raw JSON and lexical relative-path context, before any material IO."""
    import os
    relative = False
    changes = patch.get('source_changes')
    if isinstance(changes, dict):
        for key in ('add', 'replace'):
            items = changes.get(key)
            if isinstance(items, list):
                for item in items:
                    path = item.get('path') if isinstance(item, dict) else None
                    if isinstance(path, str) and not os.path.isabs(os.path.expanduser(path)):
                        relative = True
    return sha256_bytes(canonical_json_bytes({
        'protocol': 'inputs-update-request.v1', 'kind': 'inputs.update',
        'project_id': document['project_id'], 'base_revision': base_revision, 'patch': patch,
        'relative_path_base': os.path.abspath(os.path.expanduser(str(patch_dir))) if relative else None}))


def _recover_input_request(store, operation_id, digest, patch, patch_dir, *, content=False, selected_resource_ids=None):
    """Common atomic/legacy occupancy check, with no filesystem normalization."""
    from . import operations
    lookup = operations.resolve_operation(store, operation_id)
    if lookup.state == 'committed':
        expected_kind = 'content.inputs' if content else 'input_update'
        if lookup.stored_kind != expected_kind:
            if content:
                raise operations.OperationError('operation_type_conflict', 'operation_id',
                    'operation belongs to another operation type', exit_code=5, operation_id=operation_id,
                    operation_state='committed')
            raise InputRevisionConflict('operation_id', 'operation belongs to another operation type',
                                        cause='operation_type_conflict', operation_id=operation_id)
        if lookup.record['request_digest'] != digest:
            if content:
                raise operations.OperationError('operation_payload_conflict', 'operation_id',
                    'operation was committed with a different request', exit_code=5, operation_id=operation_id,
                    operation_state='committed')
            raise InputRevisionConflict('operation_id', 'operation was committed with a different request',
                                        cause='operation_payload_conflict', operation_id=operation_id)
        if content:
            return operations._recover_lookup(store, operation_id, lookup, digest)
        return {**lookup.result, 'current_revision_id': lookup.head_revision, 'replayed': True}
    if lookup.state == 'unknown' and lookup.reason != 'legacy_receipt_only':
        raise operations.lookup_error(lookup, operation_id)
    legacy = operations.read_legacy_record(store, operation_id, head_revision=lookup.head_revision)
    if legacy is not None:
        if selected_resource_ids is not None:
            raise InputRevisionConflict('operation_id', 'legacy operation has no resource selection basis',
                                        cause='operation_payload_conflict', operation_id=operation_id)
        if content:
            raise operations.OperationError('operation_type_conflict', 'operation_id',
                'operation belongs to another operation type', exit_code=5, operation_id=operation_id)
        changes = patch.get('source_changes')
        # Old path/upload normalization depended on the then-current filesystem.
        # It cannot safely be reconstructed after that state has disappeared.
        if isinstance(changes, dict) and any(changes.get(k) for k in ('add', 'replace')):
            raise operations.lookup_error(lookup, operation_id)
        normalized = _normalize_input_patch(patch, patch_dir=patch_dir)
        old_digest = sha256_bytes(canonical_json_bytes(normalized))
        if legacy['request_sha256'] != old_digest:
            raise InputRevisionConflict('operation_id', 'operation was recorded with a different patch',
                                        cause='operation_payload_conflict', operation_id=operation_id)
        return {**legacy['result'], 'current_revision_id': lookup.head_revision, 'replayed': True}
    if lookup.state == 'unknown':
        raise operations.lookup_error(lookup, operation_id)
    return None


def _commit_input_receipt(store, document, base_revision, operation_id, digest, result):
    from . import operations
    from .models import require_writer
    require_writer(document, 'content-ops.v1')
    receipt = {'format': 'operation_receipt.v1', 'request_digest': digest, 'response': result}
    store._commit_locked(base_revision=base_revision, document=document, operation_id=operation_id,
                         blobs=[], operation_receipt=receipt)
    record = {'operation_id': operation_id, 'kind': 'input_update', 'project_id': document['project_id'],
              'base_revision': base_revision, 'committed_revision_id': document['revision_id'],
              'request_digest': digest}
    warning = operations.publish_index(store, record)
    return {**result, **({'journal_warning': warning} if warning else {})}


def _write_input_operation(store: Store, operation_id: str, request_digest: str, result: dict) -> None:
    directory = store.deck_root / "operations"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{operation_id}.json"
    record = {
        "kind": "input_update",
        "operation_id": operation_id,
        "request_sha256": request_digest,
        "result": result,
    }
    from .store import _atomic_write_bytes
    _atomic_write_bytes(path, canonical_json_bytes(record))


def _normalize_input_patch(patch: dict, *, patch_dir: Path, upload_project=None) -> dict:
    """Validate and resolve one inputs-update patch; paths become absolute."""
    if not isinstance(patch, dict):
        raise ServiceError("(patch)", "patch must be a JSON object")
    unknown = sorted(set(patch) - _INPUT_PATCH_FIELDS)
    if unknown:
        raise ServiceError("(patch)", f"unknown patch fields: {unknown}")
    reason = patch.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ServiceError("(patch)/reason", "a one-line summary of what changed is required")
    reason = reason.strip()
    mode = patch.get("mode", "auto")
    if mode not in ("auto", "trial"):
        raise ServiceError("(patch)/mode", "input reconciliation runs auto or as an explicit trial")

    task_patch = patch.get("task_patch", {})
    if not isinstance(task_patch, dict):
        raise ServiceError("(patch)/task_patch", "must be an object")
    unknown_task = sorted(set(task_patch) - _INPUT_TASK_PATCH_FIELDS)
    if unknown_task:
        raise ServiceError("(patch)/task_patch", f"unknown task fields: {unknown_task}")
    normalized_task: dict = {}
    for field in ("title", "brief"):
        if field in task_patch:
            value = task_patch[field]
            if not isinstance(value, str) or not value.strip():
                raise ServiceError(f"(patch)/task_patch/{field}", "must be a non-empty string")
            normalized_task[field] = value
    for field in ("audience", "scenario"):
        if field in task_patch:
            value = task_patch[field]
            if not isinstance(value, str):
                raise ServiceError(f"(patch)/task_patch/{field}", "must be a string (empty string clears)")
            normalized_task[field] = value
    if "presentation_mode" in task_patch:
        value = task_patch["presentation_mode"]
        if value not in _PRESENTATION_MODES:
            raise ServiceError("(patch)/task_patch/presentation_mode", "must be live, read_alone or mixed")
        normalized_task["presentation_mode"] = value
    if "page_limit" in task_patch:
        value = task_patch["page_limit"]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
            raise ServiceError("(patch)/task_patch/page_limit", "must be a positive integer or null")
        normalized_task["page_limit"] = value
    if "existing_decisions" in task_patch:
        value = task_patch["existing_decisions"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ServiceError("(patch)/task_patch/existing_decisions", "must be an array of strings")
        normalized_task["existing_decisions"] = value

    source_changes = patch.get("source_changes", {})
    if not isinstance(source_changes, dict):
        raise ServiceError("(patch)/source_changes", "must be an object")
    unknown_source = sorted(set(source_changes) - {"add", "replace", "remove", "metadata"})
    if unknown_source:
        raise ServiceError("(patch)/source_changes", f"unknown fields: {unknown_source}")
    for key, value in source_changes.items():
        if not isinstance(value, list):
            raise ServiceError(f"(patch)/source_changes/{key}", "must be an array")

    def _resolve(item: dict, where: str) -> dict:
        path_value = item.get("path")
        upload_digest = None
        if 'upload_id' in item:
            if path_value or upload_project is None:
                raise ServiceError(where, "choose an uploaded material or a local path")
            from .source_uploads import resolve, show
            path_value = str(resolve(upload_project, item['upload_id']))
            upload_digest = show(upload_project, upload_id=item['upload_id'])['sha256']
        if not isinstance(path_value, str) or not path_value:
            raise ServiceError(f"{where}/path", "must be a non-empty path string")
        resolved = Path(path_value).expanduser()
        if not resolved.is_absolute():
            resolved = patch_dir / resolved
        note = item.get("usage_note")
        if "usage_note" in item and not isinstance(note, str):
            raise ServiceError(f"{where}/usage_note", "must be a string")
        result = {"path": str(resolved.resolve())}
        if upload_digest:
            result['upload_sha256'] = upload_digest
        if note is not None:
            result['usage_note'] = note
        return result

    add = []
    for index, item in enumerate(source_changes.get("add") or []):
        if not isinstance(item, dict):
            raise ServiceError(f"(patch)/source_changes/add[{index}]", "must be an object")
        add.append(_resolve(item, f"(patch)/source_changes/add[{index}]"))
    replace = []
    for index, item in enumerate(source_changes.get("replace") or []):
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str) or not item["source_id"]:
            raise ServiceError(f"(patch)/source_changes/replace[{index}]", "needs a source_id")
        entry = _resolve(item, f"(patch)/source_changes/replace[{index}]")
        entry["source_id"] = item["source_id"]
        replace.append(entry)
    remove = source_changes.get("remove") or []
    if not isinstance(remove, list) or not all(isinstance(item, str) for item in remove):
        raise ServiceError("(patch)/source_changes/remove", "must be an array of source ids")
    overlap = sorted({item["source_id"] for item in replace} & set(remove))
    if overlap:
        raise ServiceError("(patch)/source_changes",
                           f"the same source id cannot be replaced and removed: {overlap}")
    metadata = []
    for index, item in enumerate(source_changes.get("metadata") or []):
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str) or not item["source_id"]:
            raise ServiceError(f"(patch)/source_changes/metadata[{index}]", "needs a source_id")
        unknown_meta = sorted(set(item) - {"source_id", "usage_note", "name"})
        if unknown_meta:
            raise ServiceError(f"(patch)/source_changes/metadata[{index}]", f"unknown fields: {unknown_meta}")
        for key in ('usage_note', 'name'):
            if key in item and not isinstance(item[key], str):
                raise ServiceError(f"(patch)/source_changes/metadata[{index}]/{key}", "must be a string")
        metadata.append({"source_id": item["source_id"],
                         "usage_note": item.get("usage_note"),
                         "name": item.get("name")})

    return {
        "task_patch": normalized_task,
        "source_changes": {"add": add, "replace": replace, "remove": remove, "metadata": metadata},
        "reason": reason,
        "mode": mode,
    }


def _read_patch_material(path_str: str):
    """Read one patch-named material; failures reject the whole request."""
    return read_source_snapshot(path_str)


def inputs_update(
    project_dir: Path | str,
    *,
    patch: dict,
    base_revision: str,
    operation_id: str,
    patch_dir: Path | str | None = None,
    _recoverable_workbench: bool = False,
    selected_resource_ids=None,
) -> dict:
    """Save changed inputs; supersede open tasks; dispatch the input revision.

    Idempotent by operation id: the same request replays its original result
    without re-reading sources; the same id with different content, or a
    stale base revision, is refused with ``input_revision_conflict`` (exit 5).
    """
    from . import operations
    from .models import require_writer
    from .snapshots import capture_head, ReadModelError

    if not isinstance(patch, dict):
        raise ServiceError('(patch)', 'patch must be a JSON object')
    try:
        operations.validate_id(operation_id, new=_recoverable_workbench)
    except operations.OperationError as exc:
        if _recoverable_workbench:
            raise
        raise ServiceError('operation_id', 'invalid operation identifier') from exc
    if not isinstance(base_revision, str) or not base_revision:
        raise ServiceError('base_revision', 'must be a nonempty revision identifier')
    store = Store(Path(project_dir).expanduser())
    patch_dir = Path(patch_dir).expanduser() if patch_dir is not None else Path.cwd()
    try:
        current = capture_head(store)
    except ReadModelError as exc:
        raise operations.lookup_error(operations.OperationLookup('unknown', reason='history_unreadable'), operation_id) from exc
    business_digest = None
    if _recoverable_workbench:
        if not store.workbench_protocol_required(current):
            raise ServiceError('(project)', 'recoverable content inputs require workbench.v3')
        business_digest = operations.request_digest(current, 'content.inputs', base_revision, {'input': patch})
    request_digest = (_input_request_digest(current, patch, base_revision, patch_dir)
                      if not _recoverable_workbench else business_digest)
    if selected_resource_ids is not None:
        request_digest = sha256_bytes(canonical_json_bytes({"input_digest": request_digest,
            "selected_resource_ids": selected_resource_ids}))
        if _recoverable_workbench:
            business_digest = request_digest
    existing = _recover_input_request(store, operation_id, request_digest, patch, patch_dir,
                                      content=_recoverable_workbench, selected_resource_ids=selected_resource_ids)
    if existing is not None:
        return existing
    normalized = _normalize_input_patch(patch, patch_dir=patch_dir, upload_project=store.project_root)

    # Stage every new material before taking the lock; any failure rejects the
    # whole request and leaves current state untouched (§5.3 step 2).
    staged_add: list[tuple[dict, Any]] = []
    staged_replace: list[tuple[dict, Any]] = []
    def read_confirmed_material(item):
        material = _read_patch_material(item['path'])
        if item.get('upload_sha256') and material[0].original_sha256 != item['upload_sha256']:
            from .operations import OperationError
            raise OperationError('material_upload_changed', 'file', 'uploaded material changed before confirmation; original input was not modified', http_status=409)
        return material
    for item in normalized["source_changes"]["add"]:
        staged_add.append((item, read_confirmed_material(item)))
    for item in normalized["source_changes"]["replace"]:
        staged_replace.append((item, read_confirmed_material(item)))

    with store._locked():
        record = _recover_input_request(store, operation_id, request_digest, patch, patch_dir,
                                        content=_recoverable_workbench, selected_resource_ids=selected_resource_ids)
        if record is not None:
            return record
        document = store.load_document()
        try:
            eligibility.guard(store, document, "content.inputs_update",
                              context={"targets": {"layers": ["narrative"]}})
        except eligibility.EligibilityBlocked as exc:
            exc.operation_id = operation_id
            raise
        if document["revision_id"] != base_revision:
            raise InputRevisionConflict(
                "(base-revision)",
                f"base {base_revision!r} is not current (now {document['revision_id']!r}); "
                "re-run inputs show and rebase the patch",
            )
        if selected_resource_ids is not None:
            # Validate against the final revision scope before source blobs or
            # superseded Tasks are persisted. The builder is read-only.
            revision_compose_task(store, document, operation_id=operation_id,
                                  reason=normalized['reason'], selected_resource_ids=selected_resource_ids)
        old_digest = compute_input_digest(document)

        new_task = {**(document.get("task") or {}), **normalized["task_patch"]}
        if 'presentation_mode' in normalized['task_patch']:
            new_task['presentation_mode_source'] = 'provided'
        new_sources = [dict(entry) for entry in document.get("sources") or []]
        by_id = {entry["source_id"]: entry for entry in new_sources}
        diff = {"task_fields_changed": sorted(normalized["task_patch"]),
                "sources_added": [], "sources_replaced": [], "sources_removed": [],
                "sources_metadata": [], "noops": []}

        def _resolve_same(entry: dict, path: Path, sha: str | None) -> bool:
            try:
                same_path = Path(entry.get("original_uri") or "").expanduser().resolve() == path.resolve()
            except OSError:
                same_path = entry.get("original_uri") == str(path)
            return same_path and sha is not None and entry.get("original_sha256") == sha

        for item, (extract, data) in staged_add:
            path = Path(item["path"])
            noop_target = next((entry for entry in new_sources
                                if _resolve_same(entry, path, extract.original_sha256)), None)
            if noop_target is not None:
                diff["noops"].append({"path": item["path"], "source_id": noop_target["source_id"]})
                continue
            source_id = _new_source_id({entry["source_id"] for entry in new_sources})
            new_sources.append(_entry_from_extract(store, path, extract, source_id,
                                                   usage_note=item.get("usage_note") or "", data=data))
            by_id[source_id] = new_sources[-1]
            diff["sources_added"].append(source_id)

        for item, (extract, data) in staged_replace:
            source_id = item["source_id"]
            if source_id not in by_id:
                raise ServiceError(f"(patch)/source_changes/replace/{source_id}",
                                   "replace must name an existing source id")
            path = Path(item["path"])
            entry = by_id[source_id]
            replacement = _entry_from_extract(store, path, extract, source_id,
                                              usage_note=item.get("usage_note", entry.get("usage_note", "")), data=data)
            for key in ('external_use', 'restriction'):
                replacement[key] = entry[key]
            new_sources[new_sources.index(entry)] = replacement
            by_id[source_id] = replacement
            diff["sources_replaced"].append(source_id)

        for source_id in normalized["source_changes"]["remove"]:
            if source_id not in by_id:
                raise ServiceError(f"(patch)/source_changes/remove/{source_id}",
                                   "remove must name an existing source id")
            new_sources = [entry for entry in new_sources if entry["source_id"] != source_id]
            diff["sources_removed"].append(source_id)

        for item in normalized["source_changes"]["metadata"]:
            source_id = item["source_id"]
            if source_id not in by_id:
                raise ServiceError(f"(patch)/source_changes/metadata/{source_id}",
                                   "metadata must name an existing source id")
            entry = by_id[source_id]
            if item.get("usage_note") is not None:
                entry["usage_note"] = item["usage_note"]
                diff["sources_metadata"].append(source_id)
            if item.get("name") is not None:
                if not isinstance(item["name"], str) or not item["name"]:
                    raise ServiceError("(patch)/source_changes/metadata/name", "must be a non-empty string")
                entry["name"] = item["name"]

        probe = {"task": new_task, "sources": new_sources}
        new_digest = compute_input_digest(probe)
        if new_digest == old_digest:
            if selected_resource_ids is not None:
                raise ServiceError("selected_resource_ids", "unchanged inputs do not dispatch a new Task")
            result = {"status": "unchanged", "input_digest": new_digest,
                      "input_alignment": input_alignment(document),
                      "revision_id": document["revision_id"], "diff": diff,
                      "reason": normalized["reason"]}
            bumped = bump_revision(document, {
                "operation_id": operation_id, "kind": "input_update",
                "description": "inputs update (unchanged business inputs)", "read_set": []})
            bumped["sources"] = new_sources
            result["revision_id"] = bumped["revision_id"]
            if _recoverable_workbench:
                require_writer(bumped, 'content-ops.v1')
                return operations.commit_locked(store, document=bumped, base_revision=document['revision_id'],
                    operation_id=operation_id, kind='content.inputs', digest=business_digest, result=result)
            return _commit_input_receipt(store, bumped, document["revision_id"],
                                         operation_id, request_digest, result)

        new_document = bump_revision(document, {
            "operation_id": operation_id, "kind": "input_update",
            "description": normalized["reason"], "read_set": []})
        new_document["task"] = new_task
        new_document["sources"] = new_sources
        if document.get("pages") and not document.get("content_basis"):
            # First update on a legacy project: pin the basis the existing
            # content was actually built on (§5.3 step 4).
            new_document["content_basis"] = {"input_digest": old_digest,
                                             "input_revision_id": None,
                                             "resolved_by_task_id": None}
        superseded_ids = []
        for index, ref in enumerate(new_document.get("tasks") or []):
            task = store.read_object_json(ref)
            if task.get("status") in ("awaiting_host", "running") and \
                    task.get("kind") in tasks_mod.HOST_TASK_KINDS:
                superseded_ids.append(task["task_id"])
                new_document["tasks"][index] = store.put_json_object(
                    {**task, "status": "superseded", "updated_at": _utc_now_iso()})
        from .content_impact import analyze_input_change
        content_impact_result = analyze_input_change(store, document, new_document)
        task = revision_compose_task(store, new_document, operation_id=operation_id,
                                     reason=normalized["reason"], impact=content_impact_result,
                                     selected_resource_ids=selected_resource_ids)
        if normalized.get("mode", "auto") == "trial":
            if not new_document.get("pages"):
                from .operations import OperationError
                raise OperationError("content_invalid", "(patch)/mode",
                                     "an explicit trial reconciles existing pages; this project has none yet")
            task["instruction"] += (" 当前为显式 trial：除 content_update 外还须提交完整 content_plan_input；"
                                    "结果保存为候选，采用前不改动当前正文、页序或产物。")
            # B03: the material-impact judgement comes back as an immutable
            # content_update candidate; the registration itself stays honest
            # (needs_reconciliation) and never claims alignment up front.
            task["stage_request"] = {"mode": "trial", "stage": "content", "references": []}
            task["required_capabilities"] = [*task.get("required_capabilities", []),
                                              "candidate_result", "content_candidate"]
        new_document["tasks"] = list(new_document.get("tasks") or []) + [store.put_json_object(task)]
        alignment = input_alignment(new_document)
        result = {
            "status": "updated",
            "input_digest": new_digest,
            "input_alignment": alignment,
            "mode": normalized.get("mode", "auto"),
            "revision_id": new_document['revision_id'],
            "superseded_tasks": superseded_ids,
            "diff": diff,
            "content_impact": content_impact_result,
            "reason": normalized["reason"],
            "pending_tasks": [task_summary(store, new_document, task)],
            "next_action": "submit_host_results",
        }
        if _recoverable_workbench:
            require_writer(new_document, 'content-ops.v1')
            return operations.commit_locked(store, document=new_document, base_revision=document['revision_id'],
                operation_id=operation_id, kind='content.inputs', digest=business_digest, result=result)
        return _commit_input_receipt(store, new_document, document["revision_id"],
                                     operation_id, request_digest, result)


def _entry_from_extract(store: Store, path: Path, extract, source_id: str, *, data: bytes, usage_note: str = "") -> dict:
    from dataclasses import asdict

    extraction = asdict(extract)
    extraction["original_file"] = store.put_blob(data, ext=extract.format)
    extract_ref = store.put_json_object(extraction)
    entry = {
        "source_id": source_id,
        "name": Path(str(path)).name,
        "original_uri": extract.original_uri,
        "original_sha256": extract.original_sha256,
        "format": extract.format,
        "extract": extract_ref,
        "external_use": "unspecified",
        "restriction": "",
        "locator_scheme": {
            "text": "line", "json": "pointer", "pdf": "page", "docx": "paragraph",
            "pptx": "slide", "image": "region",
        }.get(extract.format_kind, "none"),
    }
    if usage_note:
        entry["usage_note"] = usage_note
    return entry


@after_action
def accept_result(
    project_dir: Path | str,
    *,
    task_id: str,
    operation_id: str,
    produced_against: str,
    result_path: Path | str | None = None,
    result_payload: dict | None = None,
    adapter_context: TrustedContext | None = None,
    review_receipt_selector: dict | None = None,
    response_protocol: str | None = None,
) -> dict:
    """Receive one Host result envelope; prevalidation is all-or-nothing."""
    _validate_task_response_protocol(response_protocol)
    store = Store(Path(project_dir).expanduser())
    if result_payload is not None:
        envelope_raw = result_payload
    elif result_path is not None:
        envelope_raw = json.loads(Path(result_path).expanduser().read_text("utf-8"))
    else:
        raise ServiceError("(result)", "provide --result file or inline payload")
    outcome = tasks_mod.accept_result(
        store,
        task_id=task_id,
        operation_id=operation_id,
        produced_against=produced_against,
        envelope_raw=envelope_raw,
        adapter_context=adapter_context,
        review_receipt_selector=review_receipt_selector,
    )
    document = store.load_document()
    current_revision = document["revision_id"]
    if response_protocol and outcome["revision_id"] != current_revision:
        from .snapshots import load_snapshot
        document = load_snapshot(store, outcome["revision_id"])
    if outcome["status"] == "already_applied":
        from .snapshots import load_snapshot
        applied = load_snapshot(store, outcome["revision_id"])
        response = _response(
            status="already_applied",
            document=applied,
            requested_action="task accept",
            result_refs=outcome.get("result_refs") or [],
        )
    else:
        response = _response(
            status="candidate_ready" if outcome["status"] == "candidate_ready" else "accepted",
            document=document,
            requested_action="task accept",
            pending_tasks=_pending_host_tasks(document, store) if response_protocol is None else None,
            next_action=outcome.get("next_action"),
            result_refs=outcome.get("result_refs") or [],
        )
    response["current_revision_id"] = current_revision
    for key in ("candidate_ids", "candidate_refs", "result_kind", "current_artifacts_changed", "current_content_changed", "new_page_hashes", "unchanged_reason", "impact_summary", "work_complete", "operation_result", "journal_warning", "same_revision",
                # compose.v2 phased results (CONTRACTS §11.5) project their write
                # set and invalidation to adapters without a second truth.
                "variant", "adopted", "changed_layers", "page_refs", "plan_ref", "narrative_ref", "proposal_refs",
                "adopted_refs", "invalidated_refs", "invalidated_outputs", "invalidated_reviews",
                "effective_scope", "plan_note", "page_count", "creates_confirmation",
                "authorizes_production"):
        if key in outcome:
            response[key] = outcome[key]
    if response_protocol:
        receipt_document = applied if outcome["status"] == "already_applied" else document
        receipt_task = tasks_mod._lookup_task(receipt_document, task_id, store)
        return _task_receipt(response, receipt_task)
    return response


def preview_draft_import(project_dir, *, draft_payload, preserve_mainline=True):
    """Pure complete-manuscript write-set preview for an explicit UI request."""
    _validate_draft(draft_payload)
    from .project_initialization import _manuscript_write_set
    store = Store(project_dir)
    doc = store.load_document()
    write_set = _manuscript_write_set(store, doc, draft_payload, preserve_mainline=preserve_mainline)
    scope = {'subject': 'pages', 'page_ids': write_set['page_ids'], 'page_manifest_ref': None,
        'external_artifact_ref': None, 'layers': write_set['layers'],
        'allow_page_membership_change': write_set['allow_page_membership_change'],
        'allow_page_order_change': write_set['allow_page_order_change'], 'purpose': 'working'}
    return {'status': 'planned', 'project_id': doc['project_id'], 'revision_id': doc['revision_id'],
        'write_set': write_set, 'required_scope': scope, 'persistence': 'none',
        'creates_confirmation': False, 'authorizes_production': False}


def import_draft(project_dir, *, draft_path=None, draft_payload=None, base_revision=None,
                 operation_id=None, instruction_evidence=None, request_input=None,
                 preserve_mainline=True, adapter_context=None):
    """Use the shared source-bound manuscript transaction, never compose.v1."""
    if draft_payload is None:
        if draft_path is None:
            raise ServiceError("draft", "provide a draft payload or file")
        draft_payload = json.loads(Path(draft_path).expanduser().read_text("utf-8"))
    _validate_draft(draft_payload)
    store = Store(project_dir)
    if not (store.deck_root / "current.json").exists():
        return create(project_dir, brief=draft_payload.get("brief") or "Import this manuscript preserving its mainline",
            title=draft_payload.get("title") or "Imported manuscript", draft=draft_payload,
            request_input=request_input, adapter_context=adapter_context)
    if request_input is not None:
        raise ServiceError("request_input", "start/replace the explicit scoped request before importing into an existing project")
    if base_revision is None or operation_id is None:
        raise ServiceError("base_revision", "existing-project import requires base_revision and operation_id")
    from .project_initialization import adopt_manuscript
    result = adopt_manuscript(store, draft_payload, base_revision=base_revision, operation_id=operation_id,
        evidence=instruction_evidence, preserve_mainline=preserve_mainline, adapter_context=adapter_context)
    doc = store.load_document()
    return {**_response(status=result["status"], document=doc, requested_action="import draft",
        result_refs=result.get("page_refs")), **result}


def _svg_referenced_asset_ids(store, svg_ref):
    """Asset ids the stored SVG actually embeds (image hrefs).

    Returns None when the SVG is missing or unreadable: callers then fall back
    to the conservative effective allowance so a dependency change is never
    silently missed.
    """
    import xml.etree.ElementTree as ET
    if not svg_ref:
        return None
    try:
        artifact = store.read_object_json(svg_ref)
        data = store.read_object_bytes(artifact['file'])
        root = ET.fromstring(data)
        referenced = set()
        for node in root.iter():
            if node.tag.rsplit('}', 1)[-1] != 'image':
                continue
            href = node.get('href') or node.get('{http://www.w3.org/1999/xlink}href')
            if href:
                referenced.add(href)
        return referenced
    except Exception:  # noqa: BLE001 - unreadable svg must not narrow invalidation
        return None


def _rendering_state(store, document, entry):
    """The design slice a page's SVG/previews actually depend on (spec 08.8).

    Only assets the page's own SVG embeds count; being merely permitted by the
    page's allowance does not make an asset a rendering dependency.
    """
    from .models import canonical_json_bytes
    from .production import resolve_page_rendering_design, style_font_fingerprint
    effective = resolve_page_rendering_design(store, document, entry)
    style = effective['styles'][0]
    assets_by_id = {a['asset_id']: a for a in document['design_context'].get('assets') or []}
    referenced = _svg_referenced_asset_ids(store, entry.get('svg'))
    if referenced is None:
        used = effective.get('allowed_asset_ids') or []
    else:
        used = [aid for aid in sorted(referenced) if aid in assets_by_id]
    assets = sorted((aid, (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
                    for aid in used)
    fonts = style_font_fingerprint(
        effective, style,
        lambda aid: (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
    return canonical_json_bytes({'style': style, 'assets': assets, 'fonts': fonts,
                                 **({'recipe_parameters': effective['recipe_parameters']}
                                    if 'recipe_parameters' in effective else {})})


def _apply_rendering_invalidation(store, new_document, old_document, old_design, new_design):
    """Clear SVG/previews (and outputs) only on pages whose real rendering
    dependencies changed; blueprints are preserved as history (spec 08.8)."""
    from .models import canonical_json_bytes
    canvas_changed = canonical_json_bytes(old_design.get('canvas') or {}) != \
        canonical_json_bytes(new_design.get('canvas') or {})
    old_entries = {e['page_id']: e for e in (old_document.get('pages') or [])}
    invalidated = []
    for index, entry in enumerate(new_document['pages']):
        old_entry = old_entries.get(entry['page_id']) or {}
        if canvas_changed or \
                _rendering_state(store, old_document, old_entry) != \
                _rendering_state(store, new_document, entry):
            invalidated.append(index)
    for index in invalidated:
        slot_entry = new_document['pages'][index]
        slot_entry['svg'] = slot_entry['svg_preview'] = slot_entry['ppt_preview'] = None
    if invalidated:
        new_document['outputs'] = {key: None for key in new_document['outputs']}
    affected = {new_document['pages'][index]['page_id'] for index in invalidated}
    review_affected = set(affected)
    for entry in new_document['pages']:
        from .production import resolve_page_rendering_design
        before = resolve_page_rendering_design(store, old_document, old_entries[entry['page_id']])
        after = resolve_page_rendering_design(store, new_document, entry)
        if before.get('allowed_asset_ids') != after.get('allowed_asset_ids'):
            review_affected.add(entry['page_id'])
    for index, ref in enumerate(new_document.get('tasks') or []):
        task = store.read_object_json(ref)
        scope = set(task.get('scope_pages') or [])
        if task.get('status') not in ('awaiting_host', 'running'):
            continue
        if task.get("kind") == "blueprint":
            from .production import stored_blueprint_request
            from .tasks import task_inputs_current
            prepared, _ = stored_blueprint_request(store, task)
            if prepared and "asset_inputs" in prepared.get("resolved_design_context", {}):
                # SVG allowance fallback is not this prepared image's actual
                # attachment dependency. Retire only its consumed inputs.
                if not task_inputs_current(store, new_document, task):
                    new_document["tasks"][index] = store.put_json_object(
                        {**task, "status": "superseded", "updated_at": _utc_now_iso()})
                continue
        if scope & affected or (task.get('kind') in ('review', 'repair') and scope & review_affected):
            new_document['tasks'][index] = store.put_json_object(
                {**task, 'status': 'superseded', 'updated_at': _utc_now_iso()})
    return invalidated


def import_asset(
    project_dir: Path | str,
    *,
    asset_id: str,
    kind: str,
    file_path: Path | str,
    external_use: str = "allowed",
) -> dict:
    """Store real media as an asset Artifact and register it in design_context."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    eligibility.guard(store, document, "asset.import",
                      context={"targets": {"layers": ["design"]}})
    source = Path(file_path).expanduser().resolve()
    if not source.is_file():
        raise ServiceError(f"(asset {asset_id})", f"asset file not found: {source}")
    design = dict(document.get("design_context") or {})
    normalized = normalize_design_assets(
        store,
        {
            **design,
            "assets": [
                {
                    "asset_id": asset_id,
                    "kind": kind,
                    "file": str(source),
                    "external_use": external_use,
                }
            ],
        },
        base_dir=source.parent,
    )
    assets = [entry for entry in design.get("assets") or [] if entry.get("asset_id") != asset_id]
    assets += [entry for entry in normalized.get("assets") or [] if entry.get("asset_id") == asset_id]
    allowed = list(design.get("allowed_asset_ids") or [])
    if external_use == "allowed" and asset_id not in allowed:
        allowed.append(asset_id)
    if external_use != "allowed" and asset_id in allowed:
        allowed.remove(asset_id)
    new_design = {**design, "assets": assets, "allowed_asset_ids": allowed}
    operation_id = _new_operation_id("asset")
    new_document = bump_revision(
        document,
        {
            "operation_id": operation_id,
            "kind": "design_update",
            "description": f"asset {asset_id} registered ({kind}, {external_use})",
            "read_set": [],
        },
    )
    new_document["design_context"] = new_design
    from .models import validate_document_semantics

    validate_document_semantics(new_document)
    # AC-S13/AC-S08-scope: new bytes under the same asset_id invalidate only
    # the pages whose real rendering dependencies changed; unused assets and
    # unrelated pages keep their SVG/previews and current outputs.
    _apply_rendering_invalidation(store, new_document, document, design, new_design)
    validate_document_semantics(new_document)
    store.commit_change(
        base_revision=document["revision_id"], document=new_document, operation_id=operation_id
    )
    document = store.load_document()
    return _response(
        status="registered",
        document=document,
        requested_action="import asset",
    )


def update_design(
    project_dir: Path | str,
    *,
    design_context: dict,
    base_revision: str | None = None,
) -> dict:
    """Commit a new design_context version with real-dependency invalidation.

    A default-style change clears SVG/previews only on pages whose effective
    style depends on it; pages pinned to another style_ref and styles no page
    uses stay untouched. A physical canvas change invalidates every page
    (group regression). Original blueprints are always preserved as history.
    """
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    if base_revision is not None and base_revision != document["revision_id"]:
        from .store import ConflictError
        raise ConflictError("revision", "project changed; reload before updating design")
    eligibility.guard(store, document, "design.update",
                      context={"targets": {"layers": ["design"]}})
    old_design = document.get("design_context") or {}
    new_design = dict(design_context)
    operation_id = _new_operation_id("design")
    new_document = bump_revision(
        document,
        {
            "operation_id": operation_id,
            "kind": "design_update",
            "description": "design_context updated (styles/canvas)",
            "read_set": [],
        },
    )
    new_document["design_context"] = new_design
    from .models import validate_document_semantics
    from .production import resolve_design as _resolve_design

    validate_document_semantics(new_document)
    for asset in new_design.get('assets') or []:
        try:
            resource = store.read_object_json(asset['artifact'])
            store.read_object_bytes(resource['file'])
        except (KeyError, ValueError, StoreError) as exc:
            raise ServiceError('design_context/assets',
                               f"asset {asset.get('asset_id')!r} is unreadable; restore or replace its artifact before updating design: {exc}") from exc
    # Validate every page resolves under the new design before committing.
    for entry in new_document["pages"]:
        page = store.read_object_json(entry["page"])
        _resolve_design(page, new_design, new_design.get("assets") or [])
    _apply_rendering_invalidation(store, new_document, document, old_design, new_design)
    validate_document_semantics(new_document)
    store.commit_change(
        base_revision=document["revision_id"], document=new_document, operation_id=operation_id
    )
    document = store.load_document()
    return _response(
        status="updated",
        document=document,
        requested_action="update design",
    )


def task_start(project_dir: Path | str, *, task_id: str, execution_ref: str,
               supported_protocols=None, capabilities=None, response_protocol=None) -> dict:
    """Actual claim by a named execution; a second executor conflicts."""
    _validate_task_response_protocol(response_protocol)
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    eligibility.guard(store, document, "task.start",
                      context={"task": task,
                               "targets": {"page_ids": task.get("scope_pages") or []}})
    declaration = {"supported_protocols": supported_protocols, "capabilities": capabilities}
    if task.get("protocol_version"):
        from .generation import check_host
        check_host(task, declaration)
    if task.get('kind') == 'style_analyze' and not tasks_mod.task_inputs_current(store, document, task):
        raise tasks_mod.StaleInputContext('(task)', 'visual analysis inputs changed; create a new analysis before claiming')
    if task.get('stage_request', {}).get('target_reference_ref') and not tasks_mod.task_inputs_current(store, document, task):
        raise tasks_mod.StaleInputContext('(task)', 'target original image changed; preview a new style trial before claiming')
    if (task.get('kind') in ('reconstruct', 'repair', 'review')
            and 'content_requirements_v1' in (task.get('required_capabilities') or [])
            and not tasks_mod.task_inputs_current(store, document, task)):
        raise tasks_mod.StaleInputContext('(task)', 'adopted visual inputs changed before claim')
    if task.get("status") == "running" and task.get("execution_ref") != execution_ref:
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", "another execution already claimed this task"
        )
    if task.get("status") in ("completed", "cancelled", "superseded"):
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", f"task already {task.get('status')}; cannot start"
        )
    updated_task = {
        **task,
        "status": "running",
        "execution_ref": execution_ref,
        "updated_at": _utc_now_iso(),
    }
    if store.workbench_protocol_required(document) and task.get("status") != "running":
        updated_task["execution_started_at"] = updated_task["updated_at"]
    if task.get("protocol_version"):
        updated_task["host_protocol"] = declaration
        if task.get("status") == "running" and task.get("host_protocol") == declaration:
            if response_protocol:
                return _task_receipt(_response(status=task["status"], document=document,
                                               requested_action="task start"), task)
            return task_status(project_dir, task_id=task_id)
    return _commit_task_update(store, document, task, updated_task, "task claimed",
                               response_protocol=response_protocol)


def task_cancel(project_dir: Path | str, *, task_id: str, reason: str = "", response_protocol=None) -> dict:
    """User stop; later submissions are late results, facts stay."""
    _validate_task_response_protocol(response_protocol)
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    eligibility.guard(store, document, "task.cancel", context={"task": task})
    if task.get("status") in ("completed", "cancelled", "superseded"):
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", f"task already {task.get('status')}; cancel refused"
        )
    updated_task = {**task, "status": "cancelled", "updated_at": _utc_now_iso()}
    response = _commit_task_update(store, document, task, updated_task, reason or "cancelled by user",
                                   response_protocol=response_protocol)
    response["status"] = "cancelled"
    return response


def task_status(project_dir: Path | str, *, task_id: str) -> dict:
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    return _response(
        status=task.get("status") or "unknown",
        document=document,
        requested_action="task status",
        pending_tasks=[task_summary(store, document, task)],
    )


def _commit_task_update(
    store: Store, document: dict, old_task: dict, updated_task: dict, description: str,
    *, response_protocol=None
) -> dict:
    from .models import validate_task_semantics

    validate_task_semantics(updated_task)
    if updated_task.get("execution_started_at"):
        from .models import require_writer
        require_writer(document, "run-desk.v1")
    task_ref = store.put_json_object(updated_task)
    operation_id = _new_operation_id("task")
    bumped = bump_revision(
        document,
        {
            "operation_id": operation_id,
            "kind": "task_update",
            "description": description,
            "read_set": [],
        },
    )
    bumped = tasks_mod._replace_task_ref(bumped, old_task, task_ref, store)
    store.commit_change(
        base_revision=document["revision_id"], document=bumped, operation_id=operation_id
    )
    # A negotiated receipt describes this committed write, not a newer head.
    # Keep legacy work-order projection behavior for unnegotiated consumers.
    refreshed = bumped if response_protocol else store.load_document()
    response = _response(
        status=updated_task.get("status") or "updated",
        document=refreshed,
        requested_action="task update",
        pending_tasks=_pending_host_tasks(refreshed, store) if response_protocol is None else None,
    )
    return _task_receipt(response, updated_task) if response_protocol else response
