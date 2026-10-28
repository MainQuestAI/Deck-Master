"""Shared current queues over real immutable candidate results; synthetic only."""
import copy

from deck_master import candidates, run_desk, workbench
from deck_master.models import validate_schema
from candidate_fixtures import store, candidate, adopt, plan, dispatch  # noqa: F401
from test_workbench_actions import commit


def actions(summary, kind):
    return [a for a in summary['next_actions'].get('actions', []) if a['kind'] == kind]


def test_twenty_one_stale_candidates_do_not_bury_one_current_candidate(store):
    old_id = candidate(store, 'p01')
    current_id = candidate(store, 'p02')
    doc = store.load_document()
    original = next(store.read_object_json(r) for r in doc['candidates'] if store.read_object_json(r)['candidate_id'] == old_id)
    old_task_index = next(i for i,r in enumerate(doc['tasks']) if store.read_object_json(r)['task_id'] == original['task_id'])
    old_task = store.read_object_json(doc['tasks'][old_task_index])
    # Synthetic retained history: distinct immutable candidate identities, all
    # bound to the real dispatched result and its original consumed basis.
    for index in range(20):
        clone = {**copy.deepcopy(original), 'candidate_id': f'old-candidate-{index}'}
        validate_schema('candidate', clone)
        ref = store.put_json_object(clone)
        doc['candidates'].append(ref); old_task['candidate_refs'].append(ref)
    doc['tasks'][old_task_index] = store.put_json_object(old_task)
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = 'Changed p01 manuscript; p02 retained'
    doc['pages'][0]['page'] = store.put_json_object(page)
    commit(store, doc, 'synthetic-stale-history')
    before = store.read_current()
    summary = workbench.workbench_summary(store.project_root)
    compare = actions(summary, 'compare_candidates')
    assert len(compare) == 1 and compare[0]['page_ids'] == ['p02']
    assert summary['candidates']['count'] == 22
    assert summary['candidates']['pending_count'] == 1
    assert summary['candidates']['stale_count'] == 21
    assert summary['candidates']['historical_count'] == 21
    assert summary['candidates']['actionable_count'] == 1
    targets = workbench.action_targets(store.project_root, compare[0]['action_id'], revision=summary['revision_id'])
    assert [t['object_id'] for t in targets['targets']] == [current_id]
    assert targets['targets'][0]['current_relation'] == 'current'
    rows = candidates.listing(store.project_root)['candidates']
    assert len(rows) == 22
    assert {r['candidate']['candidate_id'] for r in rows if r['selection_allowed']} == {current_id}
    assert sum(r['current_relation']['status'] == 'historical' for r in rows) == 21
    desk = run_desk.detail(store.project_root, task_id=original['task_id'])['task']
    assert desk['status'] == 'completed' and desk['current_relation']['status'] == 'historical'
    assert desk['pending_candidate_refs'] == [] and desk['human_actions'] == []
    assert store.read_current() == before
    assert workbench.workbench_summary(store.project_root) == summary


def test_adopted_successor_retires_failed_recommendation_without_rewriting_failure(store):
    current_id = candidate(store, 'p01')
    adopt(store, plan(store, [current_id]))
    doc = store.load_document()
    current = next(t for r in doc['tasks'] if (t:=store.read_object_json(r)).get('candidate_refs'))
    failed = {**copy.deepcopy(current), 'task_id':'synthetic-previous-failed',
              'operation_id':'synthetic-failed', 'status':'failed', 'candidate_refs':[], 'result_refs':[]}
    validate_schema('task', failed)
    doc['tasks'].insert(0, store.put_json_object(failed))
    commit(store, doc, 'synthetic-prior-failure')
    before = store.read_current()
    desk = run_desk.detail(store.project_root, task_id=failed['task_id'])['task']
    assert desk['status'] == 'failed'
    relation = desk['current_relation']
    assert relation['status'] == relation['state'] == 'historical'
    assert relation['reason'] == 'adopted_successor'
    assert relation['successor_task_id'] == relation['successor_id'] == current['task_id']
    assert desk['human_actions'] == []
    summary = workbench.workbench_summary(store.project_root)
    assert not actions(summary, 'inspect_failure')
    assert store.read_current() == before


def test_snapshot_damage_invalidates_warm_relationship_projection(store):
    candidate(store, 'p01')
    doc = store.load_document()
    task = next(t for r in doc['tasks'] if (t:=store.read_object_json(r)).get('candidate_refs'))
    first = workbench.workbench_summary(store.project_root)
    assert actions(first, 'compare_candidates')[0]['enabled']
    path = store.revisions_dir / (task['dispatch_revision'] + '.json')
    original = path.read_bytes()
    try:
        path.write_text('{broken snapshot')
        damaged = workbench.workbench_summary(store.project_root)
        assert not actions(damaged, 'compare_candidates')[0]['enabled']
        path.write_bytes(original)
        assert actions(workbench.workbench_summary(store.project_root), 'compare_candidates')[0]['enabled']
    finally:
        path.write_bytes(original)


def test_large_candidate_history_checks_shared_basis_once_per_snapshot(store, monkeypatch):
    candidate(store, 'p01')
    doc = store.load_document()
    original = store.read_object_json(doc['candidates'][0])
    index = next(i for i, ref in enumerate(doc['tasks'])
                 if store.read_object_json(ref)['task_id'] == original['task_id'])
    task = store.read_object_json(doc['tasks'][index])
    for number in range(499):
        item = {**copy.deepcopy(original), 'candidate_id': f'history-result-{number}'}
        ref = store.put_json_object(item)
        doc['candidates'].append(ref)
        task['candidate_refs'].append(ref)
    doc['tasks'][index] = store.put_json_object(task)
    commit(store, doc, 'synthetic-shared-basis-history')
    calls = []
    assess = candidates.basis_state

    def counted(*args, **kwargs):
        calls.append(args[2]['candidate_id'])
        return assess(*args, **kwargs)

    monkeypatch.setattr(candidates, 'basis_state', counted)
    summary = workbench.workbench_summary(store.project_root)
    assert len(calls) == 1
    assert summary['candidates']['pending_count'] == 500
    assert actions(summary, 'compare_candidates')[0]['enabled']
    calls.clear()
    row = run_desk.detail(store.project_root, task_id=task['task_id'])['task']
    assert len(calls) == 1 and len(row['pending_candidate_refs']) == 500
    # A changed Page creates a new read scope; no previous "current" result
    # survives. The retained outputs stay unchanged and are still available.
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = 'Changed after shared-basis read'
    doc['pages'][0]['page'] = store.put_json_object(page)
    commit(store, doc, 'synthetic-shared-basis-page-change')
    calls.clear()
    summary = workbench.workbench_summary(store.project_root)
    assert len(calls) == 1
    assert summary['candidates']['historical_count'] == 500
    assert not actions(summary, 'compare_candidates')
    assert len(store.load_document()['candidates']) == 500


def test_genuine_current_failure_remains_actionable(store):
    task = dispatch(store)
    doc = store.load_document()
    index = next(i for i,r in enumerate(doc['tasks']) if store.read_object_json(r)['task_id'] == task['task_id'])
    doc['tasks'][index] = store.put_json_object({**task,'status':'failed'})
    commit(store, doc, 'synthetic-current-failure')
    row = run_desk.detail(store.project_root, task_id=task['task_id'])['task']
    assert row['current_relation']['status'] == 'current'
    assert row['human_actions'] == ['inspect_failure']
    summary = workbench.workbench_summary(store.project_root)
    failure = actions(summary,'inspect_failure')[0]
    target = workbench.action_targets(store.project_root, failure['action_id'], revision=summary['revision_id'])['targets'][0]
    assert target['object_id'] == task['task_id']
    assert target['task_kind'] == task['kind'] and target['created_at'] == task['created_at']
    assert target['current_relation'] == 'current'


def test_replaced_request_is_history_unless_explicitly_retained_as_background(store):
    from deck_master import collaboration
    from rc3_fixtures import evidence_for
    cid = candidate(store, 'p01')
    doc = store.load_document(); prior = doc['collaboration']['request']
    collaboration.start_request(store.project_root, input={
        'intent':'full_deck','content_intent':None,'scope':prior['scope'],
        'replace_request_id':prior['request_id'],
        'instruction_evidence':evidence_for(store.project_root,text='Synthetic new request; do not adopt earlier candidates automatically.',locator='L1:ui-current:new-request')},
        base_revision=doc['revision_id'],operation_id='ui-current-new-request')
    summary = workbench.workbench_summary(store.project_root)
    assert not actions(summary,'compare_candidates')
    selected = candidates.show(store.project_root,candidate_id=cid)
    assert selected['generation_basis']['status'] == 'current'
    assert selected['current_relation'] == {'status':'historical','reason':'request_replaced'}
    # A retained historical result is not recommended, but explicit selection
    # must still reach the ordinary request/basis/authorization preview gates.
    assert candidates.listing(store.project_root)['candidates'][0]['selection_allowed']
    doc = store.load_document()
    doc['collaboration']['request']['background_request_ids'] = [prior['request_id']]
    commit(store,doc,'synthetic-explicit-background')
    selected = candidates.show(store.project_root,candidate_id=cid)
    assert selected['current_relation']['status'] == 'background'
    assert actions(workbench.workbench_summary(store.project_root),'compare_candidates')[0]['enabled']
