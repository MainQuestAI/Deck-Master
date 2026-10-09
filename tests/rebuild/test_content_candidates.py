"""B03 content candidate trials; synthetic evidence, no Host or model calls.

Covers the three result kinds (artifact/page/content_update): explicit trial
dispatch, candidate-only returns that leave current state untouched, adoption
reusing the local content-update invalidation, and the conflict/atomicity
gates (fixed basis, overlapping changesets, late results, replay).
"""
import copy
import json
import uuid
from pathlib import Path

import pytest

from deck_master import candidates, changes, content_ops, operations, service, tasks
from deck_master.models import input_alignment
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def project(tmp_path):
    path = tmp_path / 'content-candidates'
    create_sample(path, page_count=3, readonly=False)
    return path, Store(path)


def content_intent(store, page='p01', *, mode='trial', intent='content', instruction='Tighten the copy'):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == page)
    return {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
            'base_revision': doc['revision_id'], 'intent': intent, 'instruction': instruction,
            'annotation_refs': [], 'max_calls': 0, 'mode': mode,
            'targets': [{'page_id': page, 'page_ref': entry['page'], 'layer': 'content',
                         'artifact_ref': entry['page']}]}


def dispatch_content_trial(path, store, page='p01'):
    plan = changes.plan(path, input=content_intent(store, page))
    result = changes.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                            operation_id=str(uuid.uuid4()))['operation_result']
    return tasks._lookup_task(store.load_document(), result['task_ids'][0], store)


def start_task(path, task, capabilities=None):
    service.task_start(path, task_id=task['task_id'], execution_ref='synthetic-content-host',
                       supported_protocols=[task.get('protocol_version') or 'changes.v1'],
                       capabilities=capabilities if capabilities is not None else task['required_capabilities'])


def page_envelope(store, task, title_suffix=' (rewritten)'):
    entry = next(e for e in store.load_document()['pages'] if e['page_id'] == task['scope_pages'][0])
    page = copy.deepcopy(store.read_object_json(entry['page']))
    page['customer_visible']['title'] += title_suffix
    return {'kind': task['kind'], 'pages': [page]}


def accept(path, task, envelope):
    return service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'],
                                 produced_against=task['produced_against'], result_payload=envelope)


def content_ops_value(store, action, ids, *, mode=None):
    doc = store.load_document(); entries = {e['page_id']: e for e in doc['pages']}
    value = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'content_plan_ref': doc.get('content_plan'),
             'action': action, 'instruction': 'Explicit synthetic content trial',
             'targets': [{'page_id': pid, 'page_ref': entries[pid]['page']} for pid in ids]}
    if mode:
        value['mode'] = mode
    return value


def dispatch_content_ops_trial(path, store, action, ids):
    plan = content_ops.plan(path, input=content_ops_value(store, action, ids, mode='trial'))
    result = content_ops.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                                operation_id=str(uuid.uuid4()))['operation_result']
    return tasks._lookup_task(store.load_document(), result['task_ids'][0], store)


def changeset_envelope(store, task, action):
    doc = store.load_document(); entries = {e['page_id']: e for e in doc['pages']}; ids = task['scope_pages']
    outline = copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])
    upserts, removed = [], []
    if action == 'rewrite':
        for pid in ids:
            page = copy.deepcopy(store.read_object_json(entries[pid]['page']))
            page['customer_visible']['title'] += ' Rewritten'
            upserts.append(page)
        order = list(entries)
    else:
        removed = ids
        for index in range(1 if action == 'merge' else 2):
            page = copy.deepcopy(store.read_object_json(entries[ids[0]]['page']))
            page['page_id'] = f'derived-{index}'
            page['customer_visible']['title'] = f'Synthetic derived page {index}'
            upserts.append(page)
        old_goals = {g['page_id']: g for g in outline['goals']}
        new_goals = []
        for page in upserts:
            goal = copy.deepcopy(old_goals[ids[0]])
            goal['goal_id'] = 'goal-' + page['page_id']; goal['page_id'] = page['page_id']
            new_goals.append(goal)
        outline['goals'] = [g for g in outline['goals'] if g['page_id'] not in ids] + new_goals
        outline['chapters'] = [{'chapter_id': 'synthetic-content', 'title': 'Synthetic chapter',
                                'goal_ids': [g['goal_id'] for g in outline['goals']]}]
        order = [pid for pid in entries if pid not in ids] + [p['page_id'] for p in upserts]
    return {'kind': 'compose', 'content_update': {'input_digest': task['input_digest'],
            'upsert_pages': upserts, 'remove_page_ids': removed, 'page_order': order,
            'impact_summary': 'Explicit synthetic selected-page change; other facts preserved.'},
            'content_plan': outline}


def adopt(path, store, ids, operation_id=None):
    value = candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                         'project_id': store.load_document()['project_id'],
                                         'base_revision': store.current_revision_id(),
                                         'candidate_ids': ids})['plan']
    return candidates.adopt(path, input=value, base_revision=value['base_revision'],
                            operation_id=operation_id or str(uuid.uuid4()))['operation_result']


# ---------------------------------------------------------------- AC01


def test_single_page_content_trial_records_candidate_without_touching_current(project):
    path, store = project
    task = dispatch_content_trial(path, store)
    assert task['stage_request']['mode'] == 'trial' and task['stage_request']['stage'] == 'content'
    assert 'content_candidate' in task['required_capabilities'] and 'candidate_result' in task['required_capabilities']
    before = copy.deepcopy(store.load_document())

    # an old Host without the content capability is refused before any call
    from deck_master.generation import GenerationError
    with pytest.raises(GenerationError, match='this task requires'):
        start_task(path, task, capabilities=[c for c in task['required_capabilities'] if c != 'content_candidate'])

    start_task(path, task)
    result = accept(path, task, page_envelope(store, task))
    after = store.load_document()
    assert result['status'] == 'candidate_ready' and result['result_kind'] == 'page'
    assert result['current_content_changed'] is False
    assert after['pages'] == before['pages'] and after['content_plan'] == before['content_plan']
    assert after['outputs'] == before['outputs']
    assert len(after['candidates']) == 1
    assert after['compatibility']['minimum_writer'] == 'workbench-quality.v1'
    candidate = store.read_object_json(after['candidates'][0])
    assert candidate['result_kind'] == 'page' and candidate['stage'] == 'content'
    assert candidate['page_id'] == 'p01' and candidate['target_ref'] == before['pages'][0]['page']
    assert candidate['attempt_ref'] is None
    # the candidate binds to its frozen request: the committed change plan
    change = store.read_object_json(task['change_binding']['change_ref'])
    assert candidate['request_ref'] == change['plan_ref']
    assert store.read_object_json(candidate['result_ref'])['page_id'] == 'p01'


def test_content_trial_requires_explicit_content_intent(project):
    path, store = project
    # trial on the content layer is only meaningful for an explicit content intent
    with pytest.raises(operations.OperationError, match='content trials require intent'):
        changes.plan(path, input=content_intent(store, intent='repair'))
    # auto mode keeps its original direct-write semantics
    plan = changes.plan(path, input=content_intent(store, mode='auto'))
    assert plan['plan']['actions'][0]['mode'] == 'auto'


def test_content_ops_trial_records_changeset_candidate(project):
    path, store = project
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p02',))
    assert task['stage_request'] == {'mode': 'trial', 'stage': 'content', 'references': []}
    assert {'candidate_result', 'content_candidate'} <= set(task['required_capabilities'])
    before = copy.deepcopy(store.load_document())
    start_task(path, task)
    result = accept(path, task, changeset_envelope(store, task, 'rewrite'))
    after = store.load_document()
    assert result['status'] == 'candidate_ready' and result['result_kind'] == 'content_update'
    assert result['current_content_changed'] is False
    assert after['pages'] == before['pages'] and after['content_plan'] == before['content_plan']
    assert after['outputs'] == before['outputs'] and after['tasks'][-1] != before['tasks'][-1]
    candidate = store.read_object_json(after['candidates'][0])
    assert candidate['result_kind'] == 'content_update' and 'page_id' not in candidate
    assert candidate['request_ref'] == task['content_operation_ref']
    assert candidate['content_basis']['input_digest'] == task['input_digest']
    assert [p['page_id'] for p in candidate['content_basis']['page_sequence']] == [p['page_id'] for p in before['pages']]
    assert store.read_object_json(candidate['result_ref'])['page_order'] == [p['page_id'] for p in before['pages']]


def test_inputs_trial_registers_version_stays_unreconciled_then_records_candidate(project, tmp_path):
    path, store = project
    material = tmp_path / 'material.md'
    material.write_text('# 更新的材料\n- 新增事实：试点范围扩大到三个区域。\n')
    patch = {'reason': 'add pilot scope material', 'mode': 'trial',
             'source_changes': {'add': [{'path': str(material)}]}}
    doc = store.load_document()
    result = content_ops.inputs(path, input=patch, base_revision=doc['revision_id'],
                                operation_id=str(uuid.uuid4()))['operation_result']
    assert result['status'] == 'updated' and result['mode'] == 'trial'
    assert result['input_alignment'] == 'needs_reconciliation'
    updated = store.load_document()
    assert len(updated['sources']) == len(doc['sources']) + 1
    task = tasks._lookup_task(updated, result['pending_tasks'][0]['task_id'], store)
    assert task['stage_request']['mode'] == 'trial' and task['kind'] == 'compose'
    before = copy.deepcopy(updated)
    start_task(path, task)
    envelope = {'kind': 'compose', 'content_update': {
        'input_digest': task['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
        'page_order': [p['page_id'] for p in updated['pages']],
        'unchanged_reason': '新材料只影响背景，不改当前页正文。'},
        'content_plan': copy.deepcopy(store.read_object_json(updated['content_plan'])['input'])}
    accepted = accept(path, task, envelope)
    assert accepted['result_kind'] == 'content_update' and accepted['current_content_changed'] is False
    assert store.load_document()['pages'] == before['pages']
    assert input_alignment(store.load_document()) == 'needs_reconciliation'
    # adoption is what may claim alignment
    cid = accepted['candidate_ids'][0]
    adopted = adopt(path, store, [cid])
    assert adopted['status'] == 'adopted'
    assert input_alignment(store.load_document()) == 'current'


def test_content_writer_floor_locks_out_older_cores(project, monkeypatch):
    path, store = project
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    accept(path, task, page_envelope(store, task))
    assert store.load_document()['compatibility']['minimum_writer'] == 'workbench-quality.v1'
    monkeypatch.setattr('deck_master.store.SUPPORTED_WRITERS',
                        ('generation.v1', 'content-plan.v1', 'changes.v1', 'candidates.v1',
                         'run-desk.v1', 'style-recipes.v1', 'content-ops.v1'))
    with pytest.raises(Exception, match='unsupported minimum writer'):
        Store(path).load_document()


# ---------------------------------------------------------------- AC02


def test_show_and_list_distinguish_result_kinds(project):
    from test_candidates import candidate as svg_candidate
    path, store = project
    svg_candidate(store)
    page_task = dispatch_content_trial(path, store, 'p01')
    start_task(path, page_task)
    page_result = accept(path, page_task, page_envelope(store, page_task))
    merge_task = dispatch_content_ops_trial(path, store, 'merge', ('p02', 'p03'))
    start_task(path, merge_task)
    merge_result = accept(path, merge_task, changeset_envelope(store, merge_task, 'merge'))

    listing = candidates.listing(path)
    kinds = {row['result_kind'] for row in listing['candidates']}
    assert kinds == {'artifact', 'page', 'content_update'}
    shown = candidates.show(path, candidate_id=page_result['candidate_ids'][0])
    assert shown['result_kind'] == 'page' and 'page' in shown and 'artifact' not in shown
    assert shown['page']['page_id'] == 'p01'
    merged = candidates.show(path, candidate_id=merge_result['candidate_ids'][0])
    assert merged['result_kind'] == 'content_update' and merged['content_update']['remove_page_ids'] == ['p02', 'p03']
    assert {m['relation'] for m in merged['mapping']} == {'derived', 'retained', 'removed'}
    artifact = candidates.show(path, candidate_id=listing['candidates'][0]['candidate']['candidate_id'])
    assert artifact['result_kind'] == 'artifact' and 'artifact' in artifact and 'page' not in artifact


def test_page_candidate_adoption_reuses_content_invalidation(project):
    path, store = project
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    result = accept(path, task, page_envelope(store, task))
    cid = result['candidate_ids'][0]
    before = store.load_document()
    plan = candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                        'project_id': before['project_id'], 'base_revision': before['revision_id'],
                                        'candidate_ids': [cid]})['plan']
    selection = plan['selections'][0]
    assert selection['result_kind'] == 'page' and selection['stage'] == 'content'
    assert selection['downstream'] == ['svg', 'svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability']
    assert selection['target_ref'] == before['pages'][0]['page']

    adopted = adopt(path, store, [cid])
    after = store.load_document()
    assert adopted['status'] == 'adopted'
    entry = after['pages'][0]
    assert entry['page'] == store.read_object_json(after['candidates'][0])['result_ref']
    assert entry['page'] != before['pages'][0]['page']
    # changed page keeps its blueprint as history; svg/previews clear for rebuild
    assert entry['blueprint'] == before['pages'][0]['blueprint']
    assert entry['svg'] is None and entry['svg_preview'] is None and entry['ppt_preview'] is None
    assert not any(after['outputs'].values())
    # untouched pages keep every slot
    assert after['pages'][1] == before['pages'][1] and after['pages'][2] == before['pages'][2]
    # the old page stays readable from history
    assert store.read_object_json(before['pages'][0]['page'])['page_id'] == 'p01'
    # the plan rebinds to the new page identity
    plan_projection = store.read_object_json(after['content_plan'])
    assert plan_projection['page_links'][0]['page_ref'] == entry['page']
    assert [p['page_id'] for p in after['pages']] == [p['page_id'] for p in before['pages']]
    assert input_alignment(after) == input_alignment(before)


def test_changeset_adoption_maps_pages_supersedes_and_aligns(project):
    path, store = project
    # an active task on p02 will be superseded by the merge adoption
    doc = store.load_document()
    service.open_blueprint_task(store, doc, doc['pages'][1])
    active = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                  if store.read_object_json(ref)['status'] == 'awaiting_host')
    task = dispatch_content_ops_trial(path, store, 'merge', ('p02', 'p03'))
    start_task(path, task)
    result = accept(path, task, changeset_envelope(store, task, 'merge'))
    cid = result['candidate_ids'][0]

    plan = candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                        'project_id': store.load_document()['project_id'],
                                        'base_revision': store.current_revision_id(),
                                        'candidate_ids': [cid]})['plan']
    selection = plan['selections'][0]
    assert selection['result_kind'] == 'content_update'
    assert {m['relation'] for m in selection['mapping']} == {'derived', 'retained', 'removed'}
    assert selection['page_order'] == ['p01', 'derived-0']
    assert active['task_id'] in selection['superseded_tasks']

    before = store.load_document()
    adopted = adopt(path, store, [cid])
    after = store.load_document()
    assert adopted['status'] == 'adopted'
    assert [p['page_id'] for p in after['pages']] == ['p01', 'derived-0']
    assert after['pages'][0] == before['pages'][0]
    assert after['pages'][1]['blueprint'] is None
    assert not any(after['outputs'].values())
    assert input_alignment(after) == 'current'
    assert after['content_basis']['resolved_by_task_id'] == task['task_id']
    derivation = store.read_object_json(after['page_derivations'][-1])
    assert derivation['kind'] == 'merge' and [t['page_id'] for t in derivation['source_pages']] == ['p02', 'p03']
    superseded = store.read_object_json(next(ref for ref in after['tasks']
                                              if store.read_object_json(ref)['task_id'] == active['task_id']))
    assert superseded['status'] == 'superseded'
    # removed pages and their artifacts stay readable from history
    assert store.read_object_json(before['pages'][1]['page'])['page_id'] == 'p02'


# ---------------------------------------------------------------- AC03


def test_page_candidate_basis_change_blocks_adoption(project):
    path, store = project
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    result = accept(path, task, page_envelope(store, task))
    cid = result['candidate_ids'][0]
    # a direct edit moves the page under the candidate
    doc = store.load_document(); entry = doc['pages'][0]
    page = copy.deepcopy(store.read_object_json(entry['page']))
    page['customer_visible']['title'] += ' edited concurrently'
    preview = content_ops.plan(path, input={'schema_version': 'content_operation_input.v1',
                                            'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
                                            'content_plan_ref': doc.get('content_plan'), 'action': 'edit',
                                            'instruction': 'concurrent edit',
                                            'customer_visible': page['customer_visible'],
                                            'targets': [{'page_id': 'p01', 'page_ref': entry['page']}]})
    content_ops.commit(path, plan_id=preview['plan_id'], base_revision=doc['revision_id'],
                       operation_id=str(uuid.uuid4()))
    state = candidates.show(path, candidate_id=cid)
    assert state['generation_basis']['status'] == 'changed'
    assert state['generation_basis']['changed_fields'] == ['page_ref']
    with pytest.raises(candidates.AdoptionConflict):
        adopt(path, store, [cid])
    current = store.load_document()
    assert current['pages'][0]['page'] != store.read_object_json(current['candidates'][0])['result_ref']
    assert all(record['candidate_id'] != cid for record in current.get('candidate_adoptions') or [])


def test_trial_result_replay_returns_original_candidate(project):
    path, store = project
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    envelope = page_envelope(store, task)
    first = accept(path, task, envelope)
    replay = accept(path, task, envelope)
    assert replay['status'] == 'already_applied'
    assert replay['operation_result']['candidate_ids'] == first['candidate_ids']
    assert len(store.load_document()['candidates']) == 1


def test_cancelled_content_trial_late_result_keeps_current(project):
    path, store = project
    before = copy.deepcopy(store.load_document())
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    service.task_cancel(path, task_id=task['task_id'], reason='user stopped the rewrite')
    with pytest.raises(Exception):
        accept(path, task, page_envelope(store, task))
    after = store.load_document()
    assert after['pages'] == before['pages'] and after.get('candidates') is None
    assert tasks._lookup_task(after, task['task_id'], store)['status'] == 'cancelled'


def test_batch_adoption_is_all_or_none(project):
    path, store = project
    first = dispatch_content_trial(path, store, 'p01')
    start_task(path, first)
    accept(path, first, page_envelope(store, first, ' (one)'))
    second = dispatch_content_trial(path, store, 'p02')
    start_task(path, second)
    accept(path, second, page_envelope(store, second, ' (two)'))
    ids = [store.read_object_json(ref)['candidate_id'] for ref in store.load_document()['candidates']]
    # invalidate the second candidate's page basis before adopting the batch
    doc = store.load_document(); entry = doc['pages'][1]
    page = copy.deepcopy(store.read_object_json(entry['page']))
    page['customer_visible']['title'] += ' moved'
    preview = content_ops.plan(path, input={'schema_version': 'content_operation_input.v1',
                                            'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
                                            'content_plan_ref': doc.get('content_plan'), 'action': 'edit',
                                            'instruction': 'invalidate second basis',
                                            'customer_visible': page['customer_visible'],
                                            'targets': [{'page_id': 'p02', 'page_ref': entry['page']}]})
    content_ops.commit(path, plan_id=preview['plan_id'], base_revision=doc['revision_id'],
                       operation_id=str(uuid.uuid4()))
    with pytest.raises(candidates.AdoptionConflict):
        adopt(path, store, ids)
    current = store.load_document()
    assert current.get('candidate_adoptions') is None
    for index, cid in enumerate(ids):
        assert current['pages'][index]['page'] != store.read_object_json(current['candidates'][index])['result_ref']


def test_overlapping_changesets_and_mixed_batches_are_refused(project):
    path, store = project
    first = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, first)
    accept(path, first, changeset_envelope(store, first, 'rewrite'))
    second = dispatch_content_ops_trial(path, store, 'rewrite', ('p02',))
    start_task(path, second)
    accept(path, second, changeset_envelope(store, second, 'rewrite'))
    ids = [store.read_object_json(ref)['candidate_id'] for ref in store.load_document()['candidates']]
    with pytest.raises(operations.OperationError, match='one changeset per adoption'):
        candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                     'project_id': store.load_document()['project_id'],
                                     'base_revision': store.current_revision_id(), 'candidate_ids': ids})
    page_task = dispatch_content_trial(path, store, 'p03')
    start_task(path, page_task)
    accept(path, page_task, page_envelope(store, page_task))
    page_cid = store.read_object_json(store.load_document()['candidates'][-1])['candidate_id']
    with pytest.raises(operations.OperationError, match='atomically'):
        candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                     'project_id': store.load_document()['project_id'],
                                     'base_revision': store.current_revision_id(),
                                     'candidate_ids': [ids[0], page_cid]})
    # a single changeset still plans and adopts cleanly
    adopted = adopt(path, store, [ids[0]])
    assert adopted['status'] == 'adopted'
    assert store.read_object_json(store.load_document()['pages'][0]['page'])['customer_visible']['title'].endswith('Rewritten')


def test_changeset_candidate_conflicts_with_later_input_update(project, tmp_path):
    path, store = project
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, task)
    result = accept(path, task, changeset_envelope(store, task, 'rewrite'))
    cid = result['candidate_ids'][0]
    state = candidates.show(path, candidate_id=cid)
    assert state['content_basis']['status'] == 'current'
    # a later input registration moves the fixed basis; adoption is refused
    material = tmp_path / 'new-material.md'
    material.write_text('# 后到的材料\n- 调整目标受众。\n')
    doc = store.load_document()
    content_ops.inputs(path, input={'reason': 'later material', 'source_changes': {'add': [{'path': str(material)}]}},
                       base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    state = candidates.show(path, candidate_id=cid)
    assert state['content_basis']['status'] == 'changed'
    assert 'input_digest' in state['content_basis']['changed_fields']
    with pytest.raises(candidates.AdoptionConflict):
        adopt(path, store, [cid])
    # the candidate stays recorded and recoverable through a fresh trial
    assert cid in [store.read_object_json(ref)['candidate_id'] for ref in store.load_document()['candidates']]


def test_http_serves_content_candidate_kinds(project):
    from test_workbench_services import auth, http
    from deck_master.web import WorkbenchServer
    path, store = project
    task = dispatch_content_trial(path, store)
    start_task(path, task)
    result = accept(path, task, page_envelope(store, task))
    server = WorkbenchServer(path)
    url = server.start().rstrip('/')
    try:
        status, listing = http(url, '/api/candidates')
        assert status == 200 and {row['result_kind'] for row in listing['candidates']} == {'page'}
        status, shown = http(url, '/api/candidates/' + result['candidate_ids'][0])
        assert status == 200 and shown['result_kind'] == 'page' and shown['page']['page_id'] == 'p01'
        status, planned = http(url, '/api/candidates/plan', data={'input': {
            'schema_version': 'candidate_selection.v1', 'project_id': listing['project_id'],
            'base_revision': listing['revision_id'], 'candidate_ids': result['candidate_ids']}},
            headers={**auth(url), 'Content-Type': 'application/json'})
        assert status == 200 and planned['plan']['selections'][0]['result_kind'] == 'page', planned
    finally:
        server.stop()


# ------------------------------------------------- review-round fixes (P0/P1/P2)


def test_malformed_content_plan_is_refused_and_cannot_poison_registry(project):
    path, store = project
    before = copy.deepcopy(store.load_document())
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, task)
    envelope = changeset_envelope(store, task, 'rewrite')
    envelope['content_plan'] = {'garbage': True}
    with pytest.raises(Exception) as caught:
        accept(path, task, envelope)
    assert 'content_plan' in str(caught.value)
    after = store.load_document()
    assert after.get('candidates') is None
    assert after['pages'] == before['pages']
    # the registry stays readable: the poisoned record was never persisted
    assert candidates.listing(path)['candidates'] == []


def test_changeset_without_required_plan_is_refused_at_record(project):
    path, store = project
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, task)
    envelope = changeset_envelope(store, task, 'rewrite')
    envelope.pop('content_plan')
    with pytest.raises(Exception, match='content_plan'):
        accept(path, task, envelope)
    assert store.load_document().get('candidates') is None


def test_plan_goal_identity_drift_is_refused_at_record(project):
    path, store = project
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, task)
    envelope = changeset_envelope(store, task, 'rewrite')
    # a valid-shaped outline that drops the goal identity of a retained page
    envelope['content_plan'] = copy.deepcopy(envelope['content_plan'])
    retained = next(g for g in envelope['content_plan']['goals'] if g['page_id'] == 'p02')
    retained['goal_id'] = 'goal-rewritten-retained'
    # the host-result scope gate rejects goal drift before the record path;
    # either way nothing is persisted
    with pytest.raises(Exception, match='unselected page goals'):
        accept(path, task, envelope)
    assert store.load_document().get('candidates') is None


def test_inputs_trial_on_empty_project_is_refused(tmp_path):
    path = tmp_path / 'empty'
    # create without a draft makes a real zero-page project
    service.create(path, brief='empty project trial', project_format='workbench.v3')
    assert Store(path).load_document()['pages'] == []
    material = tmp_path / 'empty-material.md'
    material.write_text('# 空项目材料\n- 一条事实。\n')
    with pytest.raises(Exception, match='none yet'):
        content_ops.inputs(path, input={'reason': 'trial on empty', 'mode': 'trial',
                                        'source_changes': {'add': [{'path': str(material)}]}},
                           base_revision=Store(path).current_revision_id(), operation_id=str(uuid.uuid4()))
    # auto mode still dispatches the initial compose on an empty project
    ok = content_ops.inputs(path, input={'reason': 'auto still works',
                                         'source_changes': {'add': [{'path': str(material)}]}},
                            base_revision=Store(path).current_revision_id(), operation_id=str(uuid.uuid4()))
    assert ok['operation_result']['status'] == 'updated'


def test_out_of_order_returns_across_pages_record_independently(project):
    path, store = project
    first = dispatch_content_trial(path, store, 'p01')
    second = dispatch_content_trial(path, store, 'p02')
    start_task(path, second)
    start_task(path, first)
    # the later page returns first
    second_result = accept(path, second, page_envelope(store, second, ' (two)'))
    first_result = accept(path, first, page_envelope(store, first, ' (one)'))
    recorded = [store.read_object_json(ref)['candidate_id'] for ref in store.load_document()['candidates']]
    assert recorded == [*second_result['candidate_ids'], *first_result['candidate_ids']]
    # one plan can adopt both page candidates; the other page keeps its slots
    before = copy.deepcopy(store.load_document())
    adopted = adopt(path, store, [*second_result['candidate_ids'], *first_result['candidate_ids']])
    assert adopted['status'] == 'adopted'
    after = store.load_document()
    assert after['pages'][0]['page'] != before['pages'][0]['page']
    assert after['pages'][1]['page'] != before['pages'][1]['page']
    assert after['pages'][2] == before['pages'][2]


def test_changeset_adoption_replays_same_operation(project):
    path, store = project
    task = dispatch_content_ops_trial(path, store, 'rewrite', ('p01',))
    start_task(path, task)
    result = accept(path, task, changeset_envelope(store, task, 'rewrite'))
    cid = result['candidate_ids'][0]
    value = candidates.plan(path, input={'schema_version': 'candidate_selection.v1',
                                         'project_id': store.load_document()['project_id'],
                                         'base_revision': store.current_revision_id(),
                                         'candidate_ids': [cid]})['plan']
    operation_id = str(uuid.uuid4())
    first = candidates.adopt(path, input=value, base_revision=value['base_revision'],
                             operation_id=operation_id)
    replay = candidates.adopt(path, input=value, base_revision=value['base_revision'],
                              operation_id=operation_id)
    assert replay['operation_result'] == first['operation_result']
    assert replay['committed_revision_id'] == first['committed_revision_id']
    assert [p['page_id'] for p in store.load_document()['pages']] == ['p01', 'p02', 'p03']


def test_noop_page_adoption_keeps_outputs_and_plan_version(project):
    path, store = project
    task = dispatch_content_trial(path, store, 'p01')
    start_task(path, task)
    # the candidate returns the identical page content: nothing to invalidate
    entry = next(e for e in store.load_document()['pages'] if e['page_id'] == 'p01')
    page = copy.deepcopy(store.read_object_json(entry['page']))
    result = accept(path, task, {'kind': task['kind'], 'pages': [page]})
    cid = result['candidate_ids'][0]
    before = store.load_document()
    plan_version = store.read_object_json(before['content_plan'])['version']
    adopt(path, store, [cid])
    after = store.load_document()
    assert after['pages'][0]['page'] == before['pages'][0]['page']
    assert after['outputs'] == before['outputs']
    assert store.read_object_json(after['content_plan'])['version'] == plan_version
    assert all(record['candidate_id'] == cid for record in after['candidate_adoptions'])


def test_malformed_content_plan_via_inputs_trial_is_refused(project, tmp_path):
    """The original P0 vector: the inputs-trial path skips validate_host_result,
    so the record-side plan validation is the only gate on that route."""
    path, store = project
    material = tmp_path / 'material.md'
    material.write_text('# 材料\n- 一条事实。\n')
    doc = store.load_document()
    result = content_ops.inputs(path, input={'reason': 'inputs trial', 'mode': 'trial',
                                             'source_changes': {'add': [{'path': str(material)}]}},
                                base_revision=doc['revision_id'],
                                operation_id=str(uuid.uuid4()))['operation_result']
    task = tasks._lookup_task(store.load_document(), result['pending_tasks'][0]['task_id'], store)
    start_task(path, task)
    envelope = {'kind': 'compose', 'content_update': {
        'input_digest': task['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
        'page_order': [p['page_id'] for p in store.load_document()['pages']],
        'unchanged_reason': '无影响。'},
        'content_plan': {'garbage': True}}
    with pytest.raises(Exception) as caught:
        accept(path, task, envelope)
    assert 'content_plan' in str(caught.value)
    assert store.load_document().get('candidates') is None
    assert candidates.listing(path)['candidates'] == []


def test_svg_repair_trial_survives_sibling_auto_slot_write(project):
    """The routing regression guard: an SVG trial at stage='repair' must read
    freshness through the generation basis (which does not include the svg
    slot itself), so a sibling auto result writing the same slot does not
    stale the trial's late return."""
    from test_candidates import start as svg_start, envelope as svg_envelope, accept as svg_accept
    path, store = project
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'Improve the spacing.',
             'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
             'targets': [{'page_id': 'p01', 'page_ref': entry['page'], 'layer': 'svg',
                          'artifact_ref': entry.get('svg'), 'stage': 'repair'}]}
    plan = changes.plan(path, input=value)
    trial_result = changes.commit(path, plan_id=plan['plan_id'], base_revision=doc['revision_id'],
                                  operation_id=str(uuid.uuid4()))['operation_result']
    trial = tasks._lookup_task(store.load_document(), trial_result['task_ids'][0], store)
    assert trial['stage_request']['stage'] == 'repair'
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    auto_value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
                  'base_revision': doc['revision_id'], 'intent': 'repair',
                  'instruction': 'auto sibling', 'annotation_refs': [], 'max_calls': 0, 'mode': 'auto',
                  'targets': [{'page_id': 'p01', 'page_ref': entry['page'], 'layer': 'svg',
                               'artifact_ref': entry.get('svg'), 'stage': 'repair'}]}
    plan = changes.plan(path, input=auto_value)
    auto = changes.commit(path, plan_id=plan['plan_id'], base_revision=doc['revision_id'],
                          operation_id=str(uuid.uuid4()))['operation_result']
    auto_task = tasks._lookup_task(store.load_document(), auto['task_ids'][0], store)
    svg_start(store, trial)
    svg_start(store, auto_task)
    from test_candidates import accept as svg_accept
    svg_accept(store, auto_task, svg_envelope(store, auto_task, 40))
    result = svg_accept(store, trial)
    assert result['status'] == 'candidate_ready' and result['result_kind'] == 'artifact'
    assert candidates.listing(path)['candidates']
