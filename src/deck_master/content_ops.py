"""Bounded editorial transactions; reuse input reconciliation and compose adoption."""
from __future__ import annotations

import copy
import re
import uuid

from . import content_plan, operations
from .content import check_page
from .local_state import project_path
from .models import bump_revision, content_identity, require_writer, validate_schema
from .snapshots import committed_snapshots, load_snapshot
from .store import Store

HOST_ACTIONS = {'rewrite', 'merge', 'split'}


def fail(field, message, *, conflict=False):
    raise operations.OperationError('content_basis_changed' if conflict else 'content_invalid', field, message,
                                    exit_code=5 if conflict else 2)


def _check(store, doc, value):
    validate_schema('content_operation_input', value)
    if doc.get('compatibility', {}).get('project_format') != 'workbench.v3':
        fail('project', 'content operations require a workbench.v3 project')
    if value['project_id'] != doc['project_id']:
        fail('project_id', 'request belongs to another project')
    if value['base_revision'] != doc['revision_id'] or value['content_plan_ref'] != doc.get('content_plan'):
        fail('base_revision', 'Document or content plan changed; preserve input and replan', conflict=True)
    ids = [t['page_id'] for t in value['targets']]
    if len(ids) != len(set(ids)):
        fail('targets', 'select unique page identities')
    entries = {e['page_id']: e for e in doc['pages']}
    if any(t['page_id'] not in entries or entries[t['page_id']]['page'] != t['page_ref'] for t in value['targets']):
        fail('targets', 'selected Page basis changed; no pages were edited', conflict=True)
    action = value['action']
    allowed = {'page_order'} if action == 'reorder' else {'customer_visible'} if action == 'edit' else {'content_plan'} if action == 'outline' else set()
    if set(value) - {'schema_version', 'project_id', 'base_revision', 'content_plan_ref', 'action', 'targets', 'instruction'} != allowed:
        fail('input', 'provide exactly the payload for the selected action')
    if not value['instruction'].strip():
        fail('instruction', 'state the intended editorial change')
    if action in {'edit', 'split'} and len(ids) != 1:
        fail('targets', 'this action needs exactly one selected page')
    if action in {'remove', 'rewrite'} and not ids or action == 'merge' and len(ids) < 2:
        fail('targets', 'select the explicit pages required by this action')
    if action in {'reorder', 'outline'} and ids:
        fail('targets', 'whole-outline operations bind the Document and ContentPlan instead')
    if action == 'remove' and len(ids) >= len(entries):
        fail('targets', 'retain at least one page in this content plan')
    if action == 'reorder' and set(value['page_order']) != set(entries):
        fail('page_order', 'list every existing page exactly once')
    if action == 'edit':
        page = copy.deepcopy(store.read_object_json(entries[ids[0]]['page']))
        page['customer_visible'] = copy.deepcopy(value['customer_visible']); check_page(page)
    if action == 'outline':
        if not doc.get('content_plan'):
            fail('content_plan', 'first obtain an explicit content plan from compose; derived titles are not a plan')
        content_plan.validate_input(store, doc, value['content_plan'], doc['pages'])
    return ids


def _superseded(store, doc, ids):
    return [t for ref in doc['tasks'] if (t := store.read_object_json(ref))['status'] in ('awaiting_host', 'running', 'blocked')
            and (t['kind'] == 'compose' or set(t['scope_pages']) & set(ids) or t['kind'] in ('render', 'export')
                 or t['kind'] == 'review' and not t['scope_pages'])]


def _plan(store, doc, value):
    ids = _check(store, doc, value); action = value['action']; host = action in HOST_ACTIONS
    actual = True
    if action == 'edit':
        entry = next(p for p in doc['pages'] if p['page_id'] == ids[0])
        actual = store.read_object_json(entry['page'])['customer_visible'] != value['customer_visible']
    elif action == 'reorder':
        actual = value['page_order'] != [p['page_id'] for p in doc['pages']]
    elif action == 'outline':
        actual = value['content_plan'] != store.read_object_json(doc['content_plan'])['input']
    return {'schema_version': 'content_operation_plan.v1', 'project_id': doc['project_id'],
            'base_revision': doc['revision_id'], 'input': copy.deepcopy(value),
            'impact': {'changed_pages': ids if action != 'remove' and actual else [], 'removed_pages': ids if action in ('remove', 'merge', 'split') else [],
                       'superseded_tasks': [t['task_id'] for t in _superseded(store, doc, ids)] if actual else [],
                       'host_required': host, 'preserved_originals_need_review': actual and action in ('edit', 'rewrite'),
                       'deck_outputs_invalidated': actual and action != 'outline', 'image_calls': 0}}


@operations.public
def plan(project, *, input):
    store = Store(project_path(project)); doc = load_snapshot(store); value = _plan(store, doc, input)
    validate_schema('content_operation_plan', value); ref = store.put_json_object(value)
    return {'plan_id': 'content-plan-' + ref['sha256'], 'plan_ref': ref, 'plan': value}


def _read_plan(store, plan_id):
    if not isinstance(plan_id, str) or not re.fullmatch(r'content-plan-[a-f0-9]{64}', plan_id):
        fail('plan_id', 'use the immutable content operation plan ID')
    sha = plan_id.removeprefix('content-plan-'); ref = {'path': f'.deckmaster/objects/{sha[:2]}/{sha}.json', 'sha256': sha}
    value = store.read_object_json(ref); validate_schema('content_operation_plan', value)
    return value, ref


def _revise_outline(store, doc, updated, value, operation_id):
    previous_ref = doc.get('content_plan')
    if not previous_ref:
        return
    previous = store.read_object_json(previous_ref); revised = copy.deepcopy(previous)
    revised.update(version=previous['version'] + 1, previous_ref=previous_ref, origin='user_edited', task_id=None, operation_id=operation_id)
    if value['action'] == 'outline':
        revised['input'] = copy.deepcopy(value['content_plan'])
    else:
        ids = [p['page_id'] for p in updated['pages']]
        by_page = {g['page_id']: g for g in revised['input']['goals']}
        if not set(ids) <= set(by_page):
            fail('content_plan', 'content plan does not cover these Pages; reconcile the outline first', conflict=True)
        revised['input']['goals'] = [by_page[pid] for pid in ids]
        goals = {g['goal_id'] for g in revised['input']['goals']}
        chapters = []
        for chapter in revised['input']['chapters']:
            chapter['goal_ids'] = [gid for gid in chapter['goal_ids'] if gid in goals]
            if chapter['goal_ids']:
                chapters.append(chapter)
        revised['input']['chapters'] = chapters
    goals = {g['page_id']: g['goal_id'] for g in revised['input']['goals']}
    revised['page_links'] = [{'page_id': e['page_id'], 'page_ref': e['page'], 'goal_id': goals[e['page_id']]} for e in updated['pages']]
    # Preserve source-reading input digest. A manual edit is not reconciliation.
    revised['basis']['revision_id'] = doc['revision_id']; revised['basis']['produced_against'] = content_identity(doc)
    validate_schema('content_plan', revised); updated['content_plan'] = store.put_json_object(revised)


@operations.public
def commit(project, *, plan_id, base_revision, operation_id):
    operations.validate_id(operation_id, new=True); store = Store(project_path(project)); planned, plan_ref = _read_plan(store, plan_id)
    with store._locked():
        doc = store.load_document(); digest = operations.request_digest(doc, 'content.commit', base_revision, {'plan_id': plan_id, 'plan': planned})
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if base_revision != doc['revision_id'] or planned != _plan(store, doc, planned['input']):
            fail('base_revision', 'content plan changed; no pages were changed', conflict=True)
        value = planned['input']; action = value['action']; ids = [t['page_id'] for t in value['targets']]
        updated = bump_revision(copy.deepcopy(doc), {'operation_id': operation_id, 'kind': 'content_update', 'description': value['instruction'], 'read_set': []})
        require_writer(updated, 'content-ops.v1')
        superseded = set(planned['impact']['superseded_tasks'])
        from .tasks import _utc_now_iso
        for i, ref in enumerate(updated['tasks']):
            task = store.read_object_json(ref)
            if task['task_id'] in superseded:
                updated['tasks'][i] = store.put_json_object({**task, 'status': 'superseded', 'updated_at': _utc_now_iso()})
        task_ids = []
        if action in HOST_ACTIONS:
            from .service import _input_compose_task
            task = _input_compose_task(updated, operation_id=operation_id, reason=value['instruction'])
            task['scope_pages'] = ids; task['content_operation_ref'] = plan_ref; task['inputs'].append(plan_ref)
            task['required_capabilities'].append('content_operations')
            task['instruction'] = ('明确的内容操作 ' + action + '：' + value['instruction'] + '\n仅处理所选页。rewrite 保留原 page_id；merge/split 返回全新 page_id，移除所选旧页。'
                                   '未选页正文及目标不得改变。提交完整 content_plan 和 content_update，包含具体影响依据；不生成图片。')
            updated['tasks'].append(store.put_json_object(task)); task_ids = [task['task_id']]
        else:
            if action == 'edit':
                entry = next(e for e in updated['pages'] if e['page_id'] == ids[0]); page = copy.deepcopy(store.read_object_json(entry['page']))
                page['customer_visible'] = copy.deepcopy(value['customer_visible']); page = check_page(page)
                ref = store.put_json_object(page)
                if ref != entry['page']:
                    entry['page'] = ref; entry['svg'] = entry['svg_preview'] = entry['ppt_preview'] = None
            elif action == 'reorder':
                by_id = {p['page_id']: p for p in updated['pages']}; updated['pages'] = [by_id[pid] for pid in value['page_order']]
            elif action == 'remove':
                updated['pages'] = [p for p in updated['pages'] if p['page_id'] not in ids]
            if planned['impact']['deck_outputs_invalidated']:
                updated['outputs'] = dict.fromkeys(doc['outputs'])
            if updated['pages'] != doc['pages'] or action == 'outline' and value['content_plan'] != store.read_object_json(doc['content_plan'])['input']:
                _revise_outline(store, doc, updated, value, operation_id)
        result = {'status': 'dispatched' if task_ids else 'edited', 'revision_id': updated['revision_id'], 'plan_ref': plan_ref,
                  'action': action, 'task_ids': task_ids, 'impact': planned['impact'], 'image_calls': 0,
                  'page_order': [p['page_id'] for p in updated['pages']], 'annotation_policy': 'retain_original_basis'}
        return operations.commit_locked(store, document=updated, base_revision=base_revision, operation_id=operation_id,
                                        kind='content.commit', digest=digest, result=result)


def validate_host_result(store, doc, task, content_update, outline):
    """Scope and identity constraints add to the existing input_revision gate."""
    if not task.get('content_operation_ref'):
        return
    from .generation import check_host
    check_host(task)
    planned = store.read_object_json(task['content_operation_ref']); validate_schema('content_operation_plan', planned)
    if planned['project_id'] != doc['project_id']:
        fail('task', 'content request belongs to another project')
    if outline is not None:
        validate_schema('content_plan_input', outline)
    value = planned['input']; selected = {t['page_id'] for t in value['targets']}; action = value['action']
    if task['scope_pages'] != [t['page_id'] for t in value['targets']] or action not in HOST_ACTIONS:
        fail('task', 'content task scope does not match the frozen request')
    updates = content_update.get('upsert_pages', []); added = {p['page_id'] for p in updates}; removed = set(content_update.get('remove_page_ids', []))
    if not (content_update.get('impact_summary') or content_update.get('unchanged_reason') or '').strip():
        fail('impact_summary', 'explain the specific editorial impact')
    if action == 'rewrite':
        if not added <= selected or removed:
            fail('upsert_pages', 'rewrite preserves page identities and changes only selected pages')
    else:
        if removed != selected or action == 'merge' and len(added) != 1 or action == 'split' and len(added) < 2:
            fail('page_ids', 'merge/split must replace exactly the selected source identities with new pages')
        historical = {e['page_id'] for snap in committed_snapshots(store) for e in snap['pages']}
        if added & historical:
            fail('page_ids', 'new derived pages cannot reuse any historical page identity')
    if doc.get('content_plan') and outline:
        previous = store.read_object_json(doc['content_plan'])['input']; before = {g['page_id']: g for g in previous['goals']}; after = {g['page_id']: g for g in outline['goals']}
        if any(after.get(pid) != goal for pid, goal in before.items() if pid not in selected):
            fail('content_plan', 'unselected page goals and source links must remain unchanged')
    if action == 'rewrite' and content_update['page_order'] != [p['page_id'] for p in doc['pages']]:
        fail('page_order', 'rewrite does not reorder pages')
    if action in ('merge', 'split'):
        before = [p['page_id'] for p in doc['pages'] if p['page_id'] not in selected]
        if [pid for pid in content_update['page_order'] if pid not in added] != before:
            fail('page_order', 'retain relative order of unselected pages')


def bind_derivation(store, doc, updated, task, page_refs):
    if not task.get('content_operation_ref'):
        return
    planned = store.read_object_json(task['content_operation_ref']); value = planned['input']
    if value['action'] not in ('merge', 'split'):
        return
    record = {'schema_version': 'page_derivation.v1', 'project_id': doc['project_id'], 'kind': value['action'],
              'task_id': task['task_id'], 'operation_id': task['operation_id'], 'source_revision': planned['base_revision'],
              'source_pages': value['targets'], 'result_pages': [{'page_id': pid, 'page_ref': ref} for pid, ref in page_refs.items()],
              'annotation_policy': 'retain_original_basis'}
    validate_schema('page_derivation', record); updated['page_derivations'] = [*doc.get('page_derivations', []), store.put_json_object(record)]
    require_writer(updated, 'content-ops.v1')


@operations.public
def source(project, *, source_id, revision=None, locator=None, extract_sha256=None):
    store = Store(project_path(project)); doc = load_snapshot(store, revision)
    sources = [s for s in doc['sources'] if s['source_id'] == source_id and (not extract_sha256 or s['extract']['sha256'] == extract_sha256)]
    if not sources and extract_sha256:
        selected_revision = doc['revision_id']; within_snapshot = False
        for previous in committed_snapshots(store):
            within_snapshot |= previous['revision_id'] == selected_revision
            if not within_snapshot:
                continue
            if (found := [s for s in previous['sources'] if s['source_id'] == source_id and s['extract']['sha256'] == extract_sha256]):
                doc, sources = previous, found; break
    if not sources:
        fail('source_id', 'this source version is not in committed project history')
    entry = sources[0]; extract = store.read_object_json(entry['extract'])
    records = [item for key in ('locators', 'tables', 'image_pages') for item in extract.get(key, [])]
    exact = [item for item in records if locator is not None and item.get('locator') == locator]
    return {'project_id': doc['project_id'], 'revision_id': doc['revision_id'], 'source_id': source_id,
            'name': entry.get('name', source_id), 'usage_note': entry.get('usage_note', ''), 'source_version': content_plan.source_version(entry),
            'extraction_status': extract['status'], 'reading_claim': 'extraction_only_not_host_impact_judgment',
            'location': 'exact' if exact else 'material_only', 'requested_locator': locator, 'matches': exact,
            'text': extract.get('text', ''), 'locators': records, 'original_file': extract.get('original_file')}


@operations.public
def inputs(project, *, input, base_revision, operation_id):
    from .service import inputs_update
    operations.validate_id(operation_id, new=True)
    return inputs_update(project_path(project), patch=input, base_revision=base_revision, operation_id=operation_id,
                         _recoverable_workbench=True)


@operations.public
def lineage(project, *, page_id, revision=None):
    store = Store(project_path(project)); doc = load_snapshot(store, revision)
    records = []
    for ref in doc.get('page_derivations', []):
        record = store.read_object_json(ref); validate_schema('page_derivation', record)
        if record['project_id'] != doc['project_id']:
            fail('page_derivations', 'derivation belongs to another project')
        if any(e['page_id'] == page_id for e in record['result_pages']):
            records.append({'ref': ref, 'derivation': record})
    return {'project_id': doc['project_id'], 'revision_id': doc['revision_id'], 'page_id': page_id,
            'records': records, 'relation': 'known' if records else 'unknown', 'annotation_policy': 'retain_original_basis'}
