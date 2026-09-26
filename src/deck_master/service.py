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

import json
import uuid
from pathlib import Path
from typing import Any

from . import tasks as tasks_mod
from .content import normalize_design_assets, check_page
from .errors import InputRevisionConflict, SourceUnreadable, SourceUnsupported
from .method_resources import method_release, method_resources
from .models import bump_revision, canonical_json_bytes, compute_input_digest, content_identity, input_alignment, new_document, sha256_bytes, validate_document_semantics
from .sources import discover_sources, read_source_snapshot
from .store import Store, StoreError, ConflictError
from .production import project_prompt, resolve_design
from .review import PAGE_VISUAL_KINDS

AUTO_VIEW = "auto_view_then_production"
CONTINUE_PRODUCTION = "continue_production"
PRODUCTION_PENDING = "production_pending"


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


def _document_hash(document: dict) -> str:
    return sha256_bytes(canonical_json_bytes(document))


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
) -> dict:
    """Create the project; register real sources; optionally import a draft."""
    if project_format not in (None, "workbench.v3"):
        raise ServiceError("project_format", "unsupported project format")
    if draft is not None:
        _validate_draft(draft)
    # presentation_mode stays a user-provided fact only when the caller actually
    # chose one; the default must never be reported as user-confirmed (§3.1).
    if presentation_mode is None:
        presentation_mode_source = "default"
        presentation_mode = "live"
    else:
        presentation_mode_source = "provided"
    project_dir = Path(project_dir).expanduser()
    store = Store(project_dir)
    discovered = discover_sources(sources or [], out_dir=project_dir)
    # Phase 1 reads and validates every material before any state is written;
    # a failure here must not leave even a layout shell behind (§4).
    extracts: list = []
    for source_path in discovered["adopted"]:
        try:
            extract, data = read_source_snapshot(source_path)
        except (SourceUnreadable, SourceUnsupported) as exc:
            if source_path.resolve() in discovered['explicit']:
                raise
            discovered['errored'].append({'path': str(source_path), 'code': exc.error_code, 'detail': str(exc)})
            continue
        extracts.append((source_path, extract, data))
    store.ensure_layout()
    operation_id = _new_operation_id("create")

    source_entries: list[dict] = []
    seen_ids: set[str] = set()
    for source_path, extract, data in extracts:
        source_entries.append(
            _entry_from_extract(store, source_path, extract, _new_source_id(seen_ids), data=data))
        seen_ids.add(source_entries[-1]["source_id"])
    source_manifest = {
        "sources_adopted": [
            {"source_id": entry["source_id"], "name": entry["name"]}
            for entry in source_entries
        ],
        "sources_skipped": discovered["skipped"],
        "sources_errored": discovered["errored"],
    }

    design = normalize_design_assets(store, design or {}, base_dir=project_dir)
    document = new_document(
        project_id=project_dir.name,
        task={
            "title": title or "Deck task",
            "brief": brief,
            "audience": audience,
            "scenario": scenario,
            "presentation_mode": presentation_mode,
            "presentation_mode_source": presentation_mode_source,
            "page_limit": page_limit,
            "existing_decisions": existing_decisions or [],
        },
        design_context=design,
        sources=source_entries,
        operation_id=operation_id,
    )
    if project_format == "workbench.v3":
        document["compatibility"] = {"project_format": "workbench.v3", "minimum_writer": "content-plan.v1"}
    store.init_project(document, operation_id=operation_id)

    if draft:
        _adopt_draft(store, draft)
        document = store.load_document()
        return {**_response(
            status="created",
            document=document,
            requested_action="create",
            pending_tasks=_pending_host_tasks(document, store),
            next_action=AUTO_VIEW,
            result_refs=[entry["page"] for entry in document.get("pages") or []],
        ), **source_manifest}
    document = store.load_document()
    task = open_compose_task(store, document, operation_id=_new_operation_id("compose"))
    document = store.load_document()
    return {**_response(
        status="created",
        document=document,
        requested_action="create",
        pending_tasks=[task_summary(store, document, task)],
        next_action="submit_host_results",
    ), **source_manifest}


def _validate_draft(payload):
    pages = payload.get('pages') if isinstance(payload, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ServiceError('(draft)/pages', 'draft must carry a non-empty pages array')
    ids = [check_page(page)['page_id'] for page in pages]
    order = payload.get('page_order') or ids
    if len(set(ids)) != len(ids) or len(order) != len(ids) or set(order) != set(ids):
        raise ServiceError('(draft)/page_order', 'must list each unique page exactly once')


def _adopt_draft(store: Store, draft_payload: dict) -> dict:
    """Validate a complete page array and adopt it through the compose path.

    Both ``create --draft`` and ``import-draft`` share this single lineage so
    imported copy and Host-composed copy behave identically downstream.
    """
    _validate_draft(draft_payload)
    pages = draft_payload.get("pages") if isinstance(draft_payload, dict) else None
    page_order = draft_payload.get("page_order") if isinstance(draft_payload, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ServiceError("(draft)/pages", "draft must carry a non-empty pages array")
    envelope = {
        "kind": "compose",
        "files": [],
        "pages": pages,
        "page_order": page_order or [page.get("page_id") for page in pages],
        "artifact_specs": draft_payload.get("artifact_specs") or [],
        "reviews": draft_payload.get("reviews") or [],
        "usage_events": [],
        "notes": draft_payload.get("notes") or "import draft",
    }
    if draft_payload.get("content_plan") is not None:
        envelope["content_plan"] = draft_payload["content_plan"]
    document = store.load_document()
    task = open_compose_task(store, document, operation_id=_new_operation_id("draft"),
                            intent="import_draft" if document.get("compatibility") else "initial")
    outcome = tasks_mod.accept_result(
        store,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        envelope_raw=envelope,
    )
    return outcome


def _input_compose_task(document, *, operation_id, reason):
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
    )
    from .content_plan import protocol_fields
    task.update(protocol_fields(document, intent))
    return task


def open_compose_task(store: Store, document: dict, *, operation_id: str,
                      intent: str = "initial", input_revision_id: str | None = None) -> dict:
    """Open a compose Host task against the current content identity."""
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
    )
    from .content_plan import protocol_fields
    task.update(protocol_fields(document, intent))
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


def _pending_host_tasks(document: dict, store: Store) -> list[dict]:
    pending = []
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("status") in ("awaiting_host", "running"):
            pending.append(task_summary(store, document, task))
    return pending


@tasks_mod._project_transaction
def _retire_missing_page_inputs(store: Store, document: dict | None = None) -> dict:
    """Recover older runs whose open visual task outlived its SVG/preview."""
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
    if not changed:
        return document
    bumped = bump_revision(updated, {'operation_id': _new_operation_id('retire'),
                                    'kind': 'task_update',
                                    'description': 'retire page task with missing SVG or preview',
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


def task_summary(store: Store, document: dict, task: dict) -> dict:
    """The Host work order: identity, inputs, resolved design, method entrypoints."""
    dispatched = _dispatch_snapshot(store, document, task)
    methods = method_resources(task.get("kind") or "", intent=task.get("intent"))
    summary = {
        "task_id": task["task_id"],
        "operation_id": task["operation_id"],
        "kind": task["kind"],
        "intent": task.get("intent"),
        "method_release": task.get("method_release"),
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
        "project_context": _project_context(store, document, task, dispatched),
        "staging_dir": str(store.staging_dir / task['operation_id']),
    }
    if task.get("review_units") is not None:
        summary["review_plan"] = {"units": task["review_units"]}
    for key in ("protocol_version", "required_capabilities", "host_protocol", "generation_requests", "generation_attempts"):
        if key in task:
            summary[key] = task[key]
    if task.get('status') in ('superseded', 'cancelled', 'completed', 'failed'):
        if task.get('status') == 'superseded':
            summary['invalidated_reason'] = 'task inputs or page scope changed; continue creates a current task'
        return summary
    if task.get("protocol_version") == "compose.v1":
        from .content_plan import projection, source_version
        summary["content_plan_contract"] = {"schema_version": "content_plan_input.v1", "required": True,
            "sources": [{"source_id": s["source_id"], "source_version": source_version(s)} for s in dispatched["sources"]],
            "prior": projection(store, dispatched),
            "instruction": "Return content_plan with every resulting page goal, chapter, versioned source locator and unresolved fact; Page remains the body-copy truth."}
    summary['source_reading'] = []
    for source in dispatched.get('sources') or []:
        ref=source.get('extract')
        if ref and ref['path'].endswith('.json'):
            extract=store.read_object_json(ref)
            summary['source_reading'].append({
                'source_id': source['source_id'], **extract,
                'extract_path': str(store.project_root / ref['path']),
                'original_path': str(store.project_root / extract['original_file']['path'])
                if extract.get('original_file') else extract['original_uri'],
            })
    if task.get('kind') in ('reconstruct','repair','review'):
        summary['page_entries'] = [e for e in document['pages'] if e['page_id'] in task['scope_pages']]
        summary['reference_images'] = []
        summary['page_design_contexts'] = {}
        for entry in summary['page_entries']:
            page=store.read_object_json(entry['page'])
            effective,_=resolve_design(page,document['design_context'],document['design_context'].get('assets',[]))
            summary['page_design_contexts'][entry['page_id']]=effective
            if entry['blueprint']:
                from PIL import Image
                import io
                original=store.read_object_json(entry['blueprint'])
                with Image.open(io.BytesIO(store.read_object_bytes(original['file']))) as image:
                    dimensions=list(image.size)
                summary['reference_images'].append({'page_id':entry['page_id'],'artifact':entry['blueprint'],'file':original['file'],'dimensions':dimensions,'requirement':'Read this exact immutable image before reconstructing; matching page text alone does not establish visual fidelity.'})
        summary['outputs'] = document['outputs']
        summary['staging_dir'] = str(store.staging_dir / task['operation_id'])
        if task.get('review_stage') == 'page_visual':
            from .editing import _current_artifact_digests
            digests = _current_artifact_digests(store, document)
            summary['page_visual_requirements'] = []
            summary['prior_page_visual_findings'] = []
            for entry in summary['page_entries']:
                page = store.read_object_json(entry['page'])
                effective, _ = resolve_design(page, document['design_context'],
                                              document['design_context'].get('assets') or [])
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
        for ref in task.get("inputs") or []:
            try:
                candidate = store.read_object_json(ref)
            except (StoreError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if candidate.get("schema_version") == "deck_blueprint_request.v1":
                summary["production_request"] = candidate
                page = store.read_object_json(next(p["page"] for p in document["pages"] if p["page_id"] == candidate["page_id"]))
                summary["resolved_design_context"], _ = resolve_design(page, document["design_context"], document["design_context"].get("assets") or [])
                break
        if task.get("protocol_version"):
            from .generation import prepared_input
            summary["generation_input"] = prepared_input(store, document, task)
    return summary


@tasks_mod._project_transaction
def open_blueprint_task(store: Store, document: dict, page_entry: dict) -> dict:
    """Dispatch one Codex ImageGen task with one service-owned allowance."""
    current = store.load_document()
    if content_identity(current) != content_identity(document):
        raise tasks_mod.TaskConflict("(blueprint)", "inputs changed before dispatch")
    document = current
    for ref in document.get("tasks") or []:
        existing = store.read_object_json(ref)
        if existing.get("kind") == "blueprint" and existing.get("status") in ("awaiting_host", "running") and existing.get("scope_pages") == [page_entry["page_id"]]:
            return existing
    page_ref = page_entry["page"]
    page = store.read_object_json(page_ref)
    design = document.get("design_context") or {}
    request = project_prompt(page, design, design.get("assets") or [])
    request["permitted_asset_files"] = _resolve_permitted_asset_files(store, request["projection"]["permitted_assets"])
    request_ref = store.put_json_object(request)
    operation_id = _new_operation_id("blueprint")
    methods = method_resources("blueprint")
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
    task, _ = tasks_mod.reserve_allowances(store, document, task, 1)
    from .generation import protocol_fields
    task.update(protocol_fields(document))
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


def continue_project(project_dir: Path | str) -> dict:
    try:
        return _continue_project(project_dir)
    except tasks_mod.CallBlocked as exc:
        document = Store(Path(project_dir)).load_document()
        return _response(status="needs_input", document=document, requested_action="continue",
                         findings=[{"code": "external_call_blocked", "field": exc.path, "message": exc.detail}],
                         next_action="resolve_external_call_block")
    except StoreError as exc:
        if not exc.path.startswith('asset:'):
            raise
        document = Store(Path(project_dir)).load_document()
        return _response(status='needs_input', document=document, requested_action='continue',
                         findings=[{'code': 'broken_asset_reference', 'field': exc.path,
                                    'message': exc.detail}], next_action='restore_or_replace_asset')


@tasks_mod._project_transaction
def _recover_input_revision(store):
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
        task = _input_compose_task(updated, operation_id=change.get('operation_id'),
                                   reason=change.get('description') or 'Resume reconciliation against current inputs')
        updated['tasks'].append(store.put_json_object(task))
    store._commit_locked(base_revision=document['revision_id'], document=updated,
                         operation_id=updated['change']['operation_id'], blobs=[])


def _continue_project(project_dir: Path | str) -> dict:
    """Run runnable local work; return the stable pending Host tasks.

    Reuse pending work. Reconcile changed inputs before producing existing
    pages; an explicitly resumed cancelled revision gets a new task identity.
    """
    store = Store(Path(project_dir).expanduser())
    _recover_input_revision(store)
    document = _retire_missing_page_inputs(store, store.load_document())
    pending = _pending_host_tasks(document, store)
    if any(t["kind"] == "blueprint" for t in pending):
        if document["policy"].get("user_stop"):
            raise tasks_mod.CallBlocked("policy/user_stop", "user stopped external calls")
        if tasks_mod.project_has_unknown_calls(document, store):
            raise tasks_mod.CallBlocked("call_allowances", "resolve unknown calls before continuing")
    for summary in pending:
        if summary["kind"] == "blueprint" and summary["status"] == "awaiting_host" and not summary["call_allowances"]:
            tasks_mod.repair_empty_allowance(store, task_id=summary["task_id"])
    document = store.load_document()
    pending = _pending_host_tasks(document, store)
    if pending:
        return _response(
            status="awaiting_host",
            document=document,
            requested_action="continue",
            pending_tasks=pending,
            next_action="submit_host_results",
        )
    if not (document.get("pages") or []):
        task = open_compose_task(store, document, operation_id=_new_operation_id("compose"))
        document = store.load_document()
        pending = _pending_host_tasks(document, store)
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
        if entry.get("page") and not entry.get("blueprint"):
            task = open_blueprint_task(store, document, entry)
            document = store.load_document()
            return _response(status="awaiting_host", document=document, requested_action="continue",
                             pending_tasks=[task_summary(store, document, task)], next_action="codex_generate_blueprint")
        if not entry.get("svg"):
            task = open_host_task(store, kind='reconstruct', page_ids=[entry['page_id']],
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
                return _continue_project(project_dir)
            except SvgError as exc:
                task = open_host_task(store, kind='reconstruct', page_ids=[entry['page_id']],
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
            task = open_host_task(store, kind='repair', page_ids=[entry['page_id']],
                                  review_stage='page_visual',
                                  instruction='本页逐页审图有 must_fix：对照 Page、原始蓝图、当前 SVG 与预览，只返修本页 Page/SVG；保留旧产物及具体发现。')
            document = store.load_document()
            return _response(status='awaiting_host', document=document, requested_action='continue',
                             pending_tasks=[task_summary(store, document, task)],
                             findings=[page_check], next_action='repair_page_visual')
        task = open_host_task(store, kind='review', page_ids=[entry['page_id']],
                              review_stage='page_visual',
                              instruction='实际打开本页 Page、原始蓝图、SVG 预览，核对正文、数字、模块、图标语义、连线方向和遮挡；提交 blueprint_content、blueprint_fidelity、readability 三类记录。关闭旧发现时，replaces 必须保持同一 review_id、finding_id、page_id、kind 和 review_stage。must_fix 需本页新产物与复核证据；needs_judgment 可用具体理由、观察与证据接受合理差异。不得把原图文字当事实源。')
        document = store.load_document()
        return _response(status='awaiting_host', document=document, requested_action='continue',
                         pending_tasks=[task_summary(store, document, task)],
                         findings=[page_check], next_action='codex_review_page_visual')
    if not document['outputs'].get('pptx'):
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
            task = open_host_task(store, kind='reconstruct', page_ids=[page_id],
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
        task = open_host_task(store,kind='repair',page_ids=[e['page_id'] for e in document['pages']],
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
            task = open_host_task(store, kind='repair', page_ids=[e['page_id'] for e in document['pages']],
                instruction='实际打开每页原图、SVG预览及PPT真实渲染，核对正文/模块/图标/数字/方向/Logo。'
                            '存在 must_fix：先修复对象，再按缺口补足审阅；subjects 必须包含当前 PPTX 与发现所在页的当前 Page；'
                            '未实际检查不能 pass，问题返回具体对象。')
        else:
            summary = check_summary(store, document)
            units = final_review_units(document, summary, input_alignment=_input_alignment(document))
            task = open_host_task(store, kind='review', page_ids=[e['page_id'] for e in document['pages']],
                review_units=units,
                instruction=describe_review_units(units))
        return _response(status='awaiting_host',document=store.load_document(),requested_action='continue',
                         pending_tasks=[task_summary(store,store.load_document(),task)],next_action='codex_review_renderings')
    return _response(status='ready_for_export',document=document,requested_action='continue',
                     result_refs=[document['outputs']['pptx']],next_action='export')


@tasks_mod._project_transaction
def open_host_task(store, *, kind, page_ids, instruction, base_revision=None, page_hash=None,
                   review_stage=None, review_units=None):
    document = store.load_document()
    if base_revision is not None and base_revision != document['revision_id']:
        from .store import ConflictError
        raise ConflictError('revision', 'project changed; reload before submitting feedback')
    if page_hash is not None and not any(e['page_id'] in page_ids and e['page']['sha256'] == page_hash for e in document['pages']):
        from .store import ConflictError
        raise ConflictError('page_hash', 'feedback page changed')
    if kind not in ('reconstruct', 'repair', 'review'):
        raise ServiceError('kind', 'unsupported local host task')
    if review_stage is not None and (review_stage not in ('page_visual', 'final') or kind not in ('repair', 'review')):
        raise ServiceError('review_stage', 'only review or repair supports page_visual/final')
    if not isinstance(instruction, str) or not instruction.strip():
        raise ServiceError('instruction', 'must not be empty')
    if not page_ids or len(set(page_ids)) != len(page_ids) or not set(page_ids) <= {e['page_id'] for e in document['pages']}:
        raise ServiceError('scope_pages', 'must name existing distinct pages')
    if review_stage == 'page_visual' and len(page_ids) != 1:
        raise ServiceError('scope_pages', 'page_visual must target exactly one page')
    for ref in document['tasks']:
        task = store.read_object_json(ref)
        if task['kind'] == kind and task['scope_pages'] == page_ids and task['instruction'] == instruction and task.get('review_stage', 'final') == (review_stage or 'final') and task['status'] in ('awaiting_host','running'):
            return task
    entries = [e for e in document['pages'] if e['page_id'] in page_ids]
    inputs = [ref for e in entries for slot,ref in e.items() if slot != 'page_id' and ref]
    inputs += [ref for ref in document['outputs'].values() if ref]
    methods = method_resources(kind)
    task = tasks_mod.new_task(task_id=uuid.uuid4().hex[:12],operation_id=_new_operation_id(kind),kind=kind,
        method_release=method_release(methods),
        scope_pages=page_ids,instruction=instruction,inputs=inputs,dependencies=[{'kind':'content','identity':e['page_id'],'sha256':e['page']['sha256']} for e in entries],
        dispatch_revision=document['revision_id'],produced_against=content_identity(document),
        review_stage=review_stage,review_units=review_units)
    updated=bump_revision(document,{'operation_id':_new_operation_id('dispatch'),'kind':'task_update','description':instruction,'read_set':[]})
    updated['tasks'].append(store.put_json_object(task))
    store._commit_locked(base_revision=document['revision_id'],document=updated,operation_id=updated['change']['operation_id'],blobs=[])
    return task


# ---------------------------------------------------------------------------
# Inputs show/update (spec v1.1 §5): the persistent way to record changed
# task facts and materials. The update transaction saves inputs, supersedes
# open tasks and dispatches compose/intent=input_revision in one commit.

_INPUT_PATCH_FIELDS = {"task_patch", "source_changes", "reason"}
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


def _read_input_operation(store: Store, operation_id: str) -> dict | None:
    import re as _re
    from .store import OPERATION_ID_PATTERN

    if not _re.fullmatch(OPERATION_ID_PATTERN, operation_id or ""):
        raise ServiceError("(operation-id)", "operation ids must match [A-Za-z0-9][A-Za-z0-9_.-]*")
    path = store.deck_root / "operations" / f"{operation_id}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text("utf-8"))
    if record.get("kind") != "input_update":
        raise InputRevisionConflict(
            f"(operation {operation_id})",
            "operation id already used by a different operation type",
        )
    # Receipts are written before the atomic Document pointer. An interrupted
    # commit is a replay only when its revision is in committed history.
    expected = record['result']['revision_id']
    document = store.load_document()
    while document['revision_id'] != expected:
        parent = document.get('parent_revision_id')
        if not parent:
            return None
        document = store.load_document(parent)
    return record


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


def _normalize_input_patch(patch: dict, *, patch_dir: Path) -> dict:
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
        if not isinstance(path_value, str) or not path_value:
            raise ServiceError(f"{where}/path", "must be a non-empty path string")
        resolved = Path(path_value).expanduser()
        if not resolved.is_absolute():
            resolved = patch_dir / resolved
        note = item.get("usage_note")
        if "usage_note" in item and not isinstance(note, str):
            raise ServiceError(f"{where}/usage_note", "must be a string")
        result = {"path": str(resolved.resolve())}
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
) -> dict:
    """Save changed inputs; supersede open tasks; dispatch the input revision.

    Idempotent by operation id: the same request replays its original result
    without re-reading sources; the same id with different content, or a
    stale base revision, is refused with ``input_revision_conflict`` (exit 5).
    """
    from .errors import InputRevisionConflict

    store = Store(Path(project_dir).expanduser())
    store.ensure_layout()
    patch_dir = Path(patch_dir).expanduser() if patch_dir else Path.cwd()
    normalized = _normalize_input_patch(patch, patch_dir=patch_dir)
    request_digest = sha256_bytes(canonical_json_bytes(normalized))
    existing = _read_input_operation(store, operation_id)
    if existing is not None:
        if existing.get("request_sha256") == request_digest:
            return existing["result"]
        raise InputRevisionConflict(
            f"(operation {operation_id})",
            "operation id already applied with a different patch",
        )

    # Stage every new material before taking the lock; any failure rejects the
    # whole request and leaves current state untouched (§5.3 step 2).
    staged_add: list[tuple[dict, Any]] = []
    staged_replace: list[tuple[dict, Any]] = []
    for item in normalized["source_changes"]["add"]:
        staged_add.append((item, _read_patch_material(item["path"])))
    for item in normalized["source_changes"]["replace"]:
        staged_replace.append((item, _read_patch_material(item["path"])))

    with store._locked():
        record = _read_input_operation(store, operation_id)
        if record is not None:
            if record.get("request_sha256") == request_digest:
                return record["result"]
            raise InputRevisionConflict(
                f"(operation {operation_id})",
                "operation id already applied with a different patch",
            )
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise InputRevisionConflict(
                "(base-revision)",
                f"base {base_revision!r} is not current (now {document['revision_id']!r}); "
                "re-run inputs show and rebase the patch",
            )
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
        names_changed = new_sources != document.get('sources', [])
        if new_digest == old_digest:
            result = {"status": "unchanged", "input_digest": new_digest,
                      "input_alignment": input_alignment(document),
                      "revision_id": document["revision_id"], "diff": diff,
                      "reason": normalized["reason"]}
            if names_changed:
                bumped = bump_revision(document, {
                    "operation_id": operation_id, "kind": "input_update",
                    "description": "inputs update (display names only)", "read_set": []})
                bumped["sources"] = new_sources
                result["revision_id"] = bumped["revision_id"]
            _write_input_operation(store, operation_id, request_digest, result)
            if names_changed:
                store._commit_locked(base_revision=document["revision_id"], document=bumped,
                                     operation_id=operation_id, blobs=[])
            return result

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
        task = _input_compose_task(new_document, operation_id=operation_id, reason=normalized["reason"])
        new_document["tasks"] = list(new_document.get("tasks") or []) + [store.put_json_object(task)]
        alignment = input_alignment(new_document)
        result = {
            "status": "updated",
            "input_digest": new_digest,
            "input_alignment": alignment,
            "revision_id": new_document['revision_id'],
            "superseded_tasks": superseded_ids,
            "diff": diff,
            "reason": normalized["reason"],
            "pending_tasks": [task_summary(store, new_document, task)],
            "next_action": "submit_host_results",
        }
        _write_input_operation(store, operation_id, request_digest, result)
        store._commit_locked(base_revision=document["revision_id"], document=new_document,
                             operation_id=operation_id, blobs=[])
        return result


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


def accept_result(
    project_dir: Path | str,
    *,
    task_id: str,
    operation_id: str,
    produced_against: str,
    result_path: Path | str | None = None,
    result_payload: dict | None = None,
) -> dict:
    """Receive one Host result envelope; prevalidation is all-or-nothing."""
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
    )
    document = store.load_document()
    current_revision = document["revision_id"]
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
            status="accepted",
            document=document,
            requested_action="task accept",
            pending_tasks=_pending_host_tasks(document, store),
            next_action=outcome.get("next_action"),
            result_refs=outcome.get("result_refs") or [],
        )
    response["current_revision_id"] = current_revision
    for key in ("new_page_hashes", "unchanged_reason", "impact_summary", "work_complete", "operation_result", "journal_warning", "same_revision"):
        if key in outcome:
            response[key] = outcome[key]
    return response


def import_draft(
    project_dir: Path | str,
    *,
    draft_path: Path | str | None = None,
    draft_payload: dict | None = None,
) -> dict:
    """Receive a complete Page list; adopt only if the whole draft validates."""
    if draft_payload is None:
        if draft_path is None:
            raise ServiceError("(draft)", "provide --input draft file or inline payload")
        draft_payload = json.loads(Path(draft_path).expanduser().read_text("utf-8"))
    _validate_draft(draft_payload)
    pages = draft_payload.get("pages") if isinstance(draft_payload, dict) else None
    page_order = draft_payload.get("page_order") if isinstance(draft_payload, dict) else None
    if not isinstance(pages, list) or not pages:
        raise ServiceError("(draft)/pages", "draft must carry a non-empty pages array")

    project_dir = Path(project_dir).expanduser()
    store = Store(project_dir)
    store.ensure_layout()
    if store.current_revision_id() is None:
        # Draft without create: build the Document shell from the draft first.
        document = new_document(
            project_id=project_dir.name,
            task={
                "title": draft_payload.get("title") or "Imported draft",
                "brief": draft_payload.get("brief") or "Draft import.",
            },
            operation_id=_new_operation_id("draft"),
        )
        store.init_project(document, operation_id=document["change"]["operation_id"])
    outcome = _adopt_draft(store, draft_payload)
    document = store.load_document()
    return _response(
        status="accepted",
        document=document,
        requested_action="import draft",
        pending_tasks=_pending_host_tasks(document, store),
        next_action=outcome.get("next_action") or AUTO_VIEW,
        result_refs=outcome.get("result_refs") or [],
    )


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


def _rendering_state(store, page, design, svg_ref=None):
    """The design slice a page's SVG/previews actually depend on (spec 08.8).

    Only assets the page's own SVG embeds count; being merely permitted by the
    page's allowance does not make an asset a rendering dependency.
    """
    from .models import canonical_json_bytes
    from .production import resolve_design, style_font_fingerprint
    effective, style = resolve_design(page, design, design.get('assets') or [])
    assets_by_id = {a['asset_id']: a for a in design.get('assets') or []}
    referenced = _svg_referenced_asset_ids(store, svg_ref)
    if referenced is None:
        used = effective.get('allowed_asset_ids') or []
    else:
        used = [aid for aid in sorted(referenced) if aid in assets_by_id]
    assets = sorted((aid, (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
                    for aid in used)
    fonts = style_font_fingerprint(
        design, style,
        lambda aid: (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
    return canonical_json_bytes({'style': style, 'assets': assets, 'fonts': fonts})


def _apply_rendering_invalidation(store, new_document, old_document, old_design, new_design):
    """Clear SVG/previews (and outputs) only on pages whose real rendering
    dependencies changed; blueprints are preserved as history (spec 08.8)."""
    from .models import canonical_json_bytes
    canvas_changed = canonical_json_bytes(old_design.get('canvas') or {}) != \
        canonical_json_bytes(new_design.get('canvas') or {})
    old_entries = {e['page_id']: e for e in (old_document.get('pages') or [])}
    invalidated = []
    for index, entry in enumerate(new_document['pages']):
        page = store.read_object_json(entry['page'])
        old_entry = old_entries.get(entry['page_id']) or {}
        if canvas_changed or \
                _rendering_state(store, page, old_design, old_entry.get('svg')) != \
                _rendering_state(store, page, new_design, entry.get('svg')):
            invalidated.append(index)
    for index in invalidated:
        slot_entry = new_document['pages'][index]
        slot_entry['svg'] = slot_entry['svg_preview'] = slot_entry['ppt_preview'] = None
    if invalidated:
        new_document['outputs'] = {key: None for key in new_document['outputs']}
    affected = {new_document['pages'][index]['page_id'] for index in invalidated}
    review_affected = set(affected)
    for entry in new_document['pages']:
        page = store.read_object_json(entry['page'])
        before, _ = resolve_design(page, old_design, old_design.get('assets') or [])
        after, _ = resolve_design(page, new_design, new_design.get('assets') or [])
        if before.get('allowed_asset_ids') != after.get('allowed_asset_ids'):
            review_affected.add(entry['page_id'])
    for index, ref in enumerate(new_document.get('tasks') or []):
        task = store.read_object_json(ref)
        scope = set(task.get('scope_pages') or [])
        if task.get('status') not in ('awaiting_host', 'running'):
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
               supported_protocols=None, capabilities=None) -> dict:
    """Actual claim by a named execution; a second executor conflicts."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    declaration = {"supported_protocols": supported_protocols, "capabilities": capabilities}
    if task.get("protocol_version"):
        from .generation import check_host
        check_host(task, declaration)
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
    if task.get("protocol_version"):
        updated_task["host_protocol"] = declaration
        if task.get("status") == "running" and task.get("host_protocol") == declaration:
            return task_status(project_dir, task_id=task_id)
    return _commit_task_update(store, document, task, updated_task, "task claimed")


def task_cancel(project_dir: Path | str, *, task_id: str, reason: str = "") -> dict:
    """User stop; later submissions are late results, facts stay."""
    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    task = tasks_mod._lookup_task(document, task_id, store)
    if task.get("status") in ("completed", "cancelled", "superseded"):
        raise tasks_mod.TaskConflict(
            f"(task {task_id})", f"task already {task.get('status')}; cancel refused"
        )
    updated_task = {**task, "status": "cancelled", "updated_at": _utc_now_iso()}
    response = _commit_task_update(store, document, task, updated_task, reason or "cancelled by user")
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
    store: Store, document: dict, old_task: dict, updated_task: dict, description: str
) -> dict:
    from .models import validate_task_semantics

    validate_task_semantics(updated_task)
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
    refreshed = store.load_document()
    return _response(
        status=updated_task.get("status") or "updated",
        document=refreshed,
        requested_action="task update",
        pending_tasks=_pending_host_tasks(refreshed, store),
    )
