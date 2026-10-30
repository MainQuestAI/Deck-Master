"""Read-only preparation using the same catalog and selector as dispatch."""
import json

from . import content_production, eligibility, method_resources as methods, models
from .content_insight import fail, records, snapshot
from .resource_catalog import CATALOG_PATH, PUBLIC_SKILLS, validate_catalog, safe_file, select
from .snapshots import READ_FAILURES


def digest(value):
    return models.sha256_bytes(models.canonical_json_bytes(value))


def catalog():
    root = methods.resolve_root()
    import json
    try:
        raw = safe_file(root, CATALOG_PATH).read_bytes()
        rows = validate_catalog(json.loads(raw))
    except (ValueError, OSError) as exc:
        fail(f'Method catalog unavailable: {exc}', code='method_catalog_unavailable', status=503)
    return root, rows, models.sha256_bytes(raw)


def preview(project, request):
    if not isinstance(request, dict) or set(request) - {'context', 'selected_resource_ids', 'expected_basis', 'business_framing'}:
        fail('Invalid preview fields')
    business_framing = request.get('business_framing', False)
    if type(business_framing) is not bool:
        fail('business_framing must be a boolean preparation option')
    ctx = request.get('context'); chosen = request.get('selected_resource_ids')
    if not isinstance(ctx, dict) or not isinstance(chosen, list) or len(chosen) > 100 or any(not isinstance(i, str) for i in chosen):
        fail('Provide context and registered resource IDs')
    root, rows, catalog_digest = catalog()
    for mid in chosen:
        if mid not in rows or not rows[mid]['readable']:
            fail(f'Unknown or unreadable resource: {mid}', code='method_preview_invalid_selection')
    reasons = []; phase = None; units = None; kind = None; intent = None
    project_id = revision = None; phase_state = {}; pending = []; gaps = []
    if ctx.get('mode') == 'independent':
        if set(ctx) != {'mode', 'role', 'phase', 'review_units'} or ctx['role'] not in PUBLIC_SKILLS:
            fail('Invalid independent context')
        role, phase, units = ctx['role'], ctx['phase'], ctx['review_units']
        if phase is not None and phase not in {'framing', 'argument', 'page_copy', 'speech', 'review', 'production', 'design', 'delivery', 'input_revision'}:
            fail('Invalid phase')
        if not isinstance(units, list) or any(not isinstance(u, str) for u in units):
            fail('Invalid review units')
        if units or role == 'deck-review':
            try:
                methods.method_ids_for('review', review_units=units)
            except models.ModelError as exc:
                fail(str(exc), code='method_preview_invalid_selection')
        if role == 'deck-review' and phase is None:
            phase = 'review'
        status, dispatch, valid = 'read_only', 'not_applicable', True
        basis = {'context': ctx}
    elif ctx.get('mode') == 'project':
        if 'business_framing' in request:
            fail('Project preparation uses the actual project contract; do not override it')
        if set(ctx) != {'mode', 'revision'} or not isinstance(ctx['revision'], str) or not ctx['revision']:
            fail('Project preparation requires a fixed revision')
        store, doc = snapshot(project, ctx['revision'])
        business_framing = models.writer_at_least(doc, 'business-framing.v1')
        project_id, revision = doc['project_id'], doc['revision_id']
        work = (doc.get('collaboration') or {}).get('request') or {}
        role, kind, intent = 'deck-content', 'compose', work.get('content_intent')
        tasks, gaps = records(store, doc, 'tasks')
        pending = [ref for ref, t in tasks if t['status'] in ('queued', 'awaiting_host', 'running')]
        if revision != store.current_revision_id(): reasons.append('historical_revision')
        if pending: reasons.append('existing_task_frozen')
        if not work or work.get('closed') or work.get('intent') not in ('full_deck', 'content_only'):
            reasons.append('no_new_phase')
        else:
            try:
                phase_state = content_production.content_phase_status(store, doc)
                phase = phase_state.get('phase')
                if phase_state.get('action') != 'dispatch':
                    reasons.append('request_completed' if phase_state.get('action') == 'complete' else 'awaiting_decision')
            except READ_FAILURES:
                reasons.append('basis_unreadable')
        if gaps: reasons.append('basis_unreadable')
        if phase and not eligibility.evaluate(store, doc, store.load_document(), 'dispatch.compose',
                context={'targets': content_production.phase_dispatch_targets(doc, phase=phase,
                    page_ids=phase_state.get('page_ids'))})['allowed']:
            reasons.append('policy_blocked')
        valid = bool(phase) and not reasons
        status = 'new_content_task' if valid else 'frozen_pending_task' if pending else 'no_new_phase'
        dispatch = 'new_content_task_possible' if valid else 'cannot_dispatch'
        basis = {'context': ctx, 'request': work, 'phase': phase_state, 'pending': pending, 'reasons': reasons}
    else:
        fail('Unknown preview mode')
    if business_framing:
        basis['business_framing'] = True
    context_digest = digest(basis)
    expected = request.get('expected_basis')
    if expected is not None and expected != {'catalog_digest': catalog_digest, 'context_digest': context_digest}:
        fail('Preparation basis changed; re-preview retained IDs', code='method_preview_basis_changed', status=409)
    defaults = []; resolved = []; dependencies = []; titles = {}; damaged = {}
    if valid:
        try:
            selected = select(rows, chosen, role=role, kind=kind, phase=phase, review_units=units)
            defaults = list(methods.method_ids_for(kind, intent=intent, phase=phase,
                business_framing=business_framing)) if kind else list(
                ('collaboration-routing', *methods.method_ids_for('review', review_units=units,
                    business_framing=business_framing))
                if role == 'deck-review' else ('collaboration-routing', *methods.method_ids_for('compose', phase=phase,
                    business_framing=business_framing))
                if role == 'deck-content' and phase else methods.role_method_ids(role, business_framing=business_framing))
            if business_framing:
                defaults = list(select(rows, defaults, role=role, kind=kind, phase=phase, review_units=units))
            ids = list(dict.fromkeys([*defaults, *selected]))
            dependencies = [i for i in selected if i not in chosen and i not in defaults]
        except ValueError as exc:
            fail(str(exc), code='method_preview_invalid_selection')
        for mid in ids:
            try:
                data = safe_file(root, rows[mid]['relative_path']).read_bytes()
                text = data.decode('utf-8')
                if rows[mid]['relative_path'].endswith('.md'):
                    titles[mid] = next((line.lstrip('#').strip() for line in text.splitlines() if line.startswith('# ')), mid)
                resolved.append({'id': mid, 'relative_path': rows[mid]['relative_path'], 'sha256': models.sha256_bytes(data)})
            except UnicodeError:
                damaged[mid] = 'resource_invalid_utf8'
            except (ValueError, OSError):
                damaged[mid] = 'resource_unavailable'
        reasons.extend(f'{reason}:{mid}' for mid, reason in damaged.items())
    hashes = {r['id']: r['sha256'] for r in resolved}; entries = []
    for mid, row in rows.items():
        allowed = valid and row['readable']; why = []
        if allowed:
            try: select(rows, [mid], role=role, kind=kind, phase=phase, review_units=units)
            except ValueError: allowed = False; why = ['outside_role_phase_scope']
        elif not valid: why = list(reasons) or ['context_unavailable']
        if not row['readable']: why = ['resource_not_readable']
        if mid in damaged: allowed = False; why = [damaged[mid]]
        entries.append({'id': mid, 'display_name': titles.get(mid, mid), 'description': '', 'kind': row['kind'],
                        'sha256': hashes.get(mid), 'selectable': allowed, 'reason_codes': why})
    preview_digest = digest({'basis': context_digest, 'catalog': catalog_digest, 'selected': chosen, 'manifest': resolved, 'damaged': damaged})
    handoff = {'schema_version': 'method_preparation_handoff.v1',
        'project_id': project_id, 'revision_id': revision,
        'context': ctx, 'role': role, 'phase': phase, 'review_units': units or [],
        'explicit_ids': chosen, 'catalog_digest': catalog_digest,
        'context_digest': context_digest, 'preparation_only': True,
        'effective_context': {'role': role, 'kind': kind, 'intent': intent, 'phase': phase,
                              'review_units': units or [], 'request_scope': (work.get('scope') if ctx['mode'] == 'project' else None)},
        'preview_request': {'context': ctx, 'selected_resource_ids': chosen,
                            'expected_basis': {'catalog_digest': catalog_digest, 'context_digest': context_digest}},
        'preview_digest': preview_digest, 'resolved_manifest': resolved,
        'default_ids': defaults, 'dependency_ids': dependencies, 'phase_state': phase_state,
        'recovery': {'surface': 'content', 'content_area': 'methods',
                     'context': ctx, 'selected_resource_ids': chosen,
                     'preview_endpoint': '/api/method-library/preview',
                     'resource_endpoint': '/api/method-library/resources/{id}',
                     'instructions': '重新执行 preview_request 并核对 preview_digest，再按返回 catalog_digest/sha256 读取每个资源。已有 Task 必须读其冻结工作单，不得用此准备覆盖 manifest。'}}
    if business_framing:
        handoff['effective_context']['business_framing'] = True
        if ctx['mode'] == 'independent':
            handoff['preview_request']['business_framing'] = True
            handoff['recovery']['business_framing'] = True
    text = ('方法准备，尚未应用；不是任务派发或生产许可。请制作工具先重新核对项目版本、请求、范围和资源字节，再按正式流程处理。\n'
            + f'职责：{role}；阶段：{phase or "未确定"}；审阅范围：{", ".join(units or []) or "不适用"}。\n'
            + ('独立阅读，不绑定项目，不产生派发许可。\n' if ctx['mode'] == 'independent'
               else f'固定项目：{project_id}；版本：{revision}。\n')
            + '选择的资源 ID：' + ', '.join(chosen) + '\n固定准备依据：' + preview_digest
            + '\n恢复入口：内容与页序 → 更多 → 方法与案例；重新执行 preview_request 核对准备依据，并按返回 catalog_digest/sha256 读取每个资源。'
            + '\n```json\n' + json.dumps(handoff, ensure_ascii=False, indent=2) + '\n```')
    return {'schema_version': 'ui_method_preview.v1', 'project_id': project_id, 'revision_id': revision,
        'context_status': status, 'browse_status': 'partial' if gaps or damaged else 'available', 'dispatch_status': dispatch,
        'reason_codes': reasons, 'preparation_only': True, 'selection_status': 'validated' if valid and not damaged else 'not_evaluated',
        'context': ctx, 'catalog_digest': catalog_digest, 'context_digest': context_digest, 'entries': entries,
        'explicit_ids': chosen, 'default_ids': defaults, 'dependency_ids': dependencies, 'resolved_manifest': resolved,
        'preview_digest': preview_digest, 'handoff': {'status': 'preparation_only', 'copy_allowed': valid and not damaged, 'text': text if valid and not damaged else ''}}


def resource(mid, *, catalog_digest, sha256=None):
    root, rows, current = catalog()
    row = rows.get(mid)
    if not row or not row['readable']:
        fail('Unknown or unreadable resource', code='insight_object_not_reachable', status=404)
    if catalog_digest != current:
        fail('Catalog changed', code='method_preview_basis_changed', status=409)
    try:
        path = safe_file(root, row['relative_path'])
    except (ValueError, OSError):
        fail('Resource unavailable; re-preview retained IDs', code='method_resource_unreadable', status=503)
    if path.stat().st_size > 1024 * 1024:
        fail('Resource exceeds 1 MiB preview limit', code='method_preview_body_too_large', status=413)
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024: fail('Resource exceeds preview limit', status=413)
    actual_sha256 = models.sha256_bytes(raw)
    if sha256 is not None and actual_sha256 != sha256:
        fail('Resource bytes changed', code='method_preview_basis_changed', status=409)
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        fail('Resource is not valid UTF-8', code='method_resource_unreadable', status=422)
    return {'id': mid, 'kind': row['kind'], 'sha256': actual_sha256, 'catalog_digest': current,
            'content': text, 'preparation_only': True}
