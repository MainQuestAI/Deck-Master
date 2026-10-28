"""RP-08 synthetic mechanism evidence, no model/visual-quality claim."""
import copy
import shutil
from urllib.parse import urlencode

import pytest

from deck_master import candidates, run_desk, tasks, workbench
from deck_master.models import validate_schema
from deck_master.web import WorkbenchServer
from candidate_fixtures import candidate as svg_candidate, dispatch
from candidate_fixtures import store as candidate_store
from test_workbench_actions import commit


def mixed(store):
    cid = svg_candidate(store)
    unknown = dispatch(store, layer='original_image')
    doc = copy.deepcopy(store.load_document())
    original = store.read_object_json(doc['candidates'][0])
    source = tasks._lookup_task(doc, original['task_id'], store)
    source = copy.deepcopy(source)
    for i in range(21):
        old = copy.deepcopy(original)
        old['candidate_id'] = f'old-candidate-{i}'
        old['generation_basis']['design_digest'] = '0' * 64
        ref = store.put_json_object(old)
        doc['candidates'].append(ref)
        source['candidate_refs'].append(ref)
    doc['tasks'] = [store.put_json_object(source) if store.read_object_json(ref)['task_id'] == source['task_id'] else ref for ref in doc['tasks']]
    request = doc['collaboration']['request']['request_id']
    for name, old_request, status in [('old-failed', True, 'failed'), ('current-failed-a', False, 'failed'),
            ('current-failed-b', False, 'failed'), ('current-failed-c', False, 'failed'), ('retired', False, 'superseded'),
            ('followed-failed', False, 'failed'), ('adopted-successor', False, 'completed')]:
        task = copy.deepcopy(source)
        task.update(task_id=name, operation_id='op-'+name, status=status, candidate_refs=[], result_refs=[],
                    scope_pages=['p01', 'p02'], instruction='Shared visible task name')
        task['collaboration_binding']['request_id'] = 'previous-request' if old_request else request
        # Different instructions are not silently treated as the same repair.
        if name.startswith('current-failed'):
            task['instruction'] = 'An unresolved distinct repair'
        if name in ('followed-failed', 'adopted-successor'):
            task['kind'] = 'compose'
        if name == 'adopted-successor':
            task['result_refs'] = [entry['page'] for entry in doc['pages']]
        validate_schema('task', task)
        doc['tasks'].append(store.put_json_object(task))
    unknown = copy.deepcopy(unknown)
    unknown['call_allowances'][0]['state'] = 'unknown'
    unknown['collaboration_binding']['request_id'] = 'previous-request'
    doc['tasks'] = [store.put_json_object(unknown) if store.read_object_json(ref)['task_id'] == unknown['task_id'] else ref for ref in doc['tasks']]
    review = {'schema_version':'deck_review.v1', 'review_id':'open-finding-review',
        'kind':'content', 'status':'fail', 'subjects':[], 'dependencies':[],
        'reviewer':{'type':'human_internal', 'id':'synthetic-fixture', 'execution_ref':None, 'independence_confirmed':False}, 'observations':['Synthetic mechanism fixture only'],
        'created_at':tasks._utc_now_iso(), 'replaces':None}
    review['findings'] = [{'finding_id':'still-open', 'kind':'content', 'impact':'must_fix',
        'page_id':'p01', 'element_refs':[], 'message':'Synthetic unresolved finding',
        'expected':'Preserve source meaning', 'actual':'Requires a separate review',
        'evidence':[doc['pages'][0]['page']], 'resolution':'open'}]
    validate_schema('review', review)
    doc['reviews'].append(store.put_json_object(review))
    commit(store, doc, 'rp08-mixed-evidence')
    return cid, source['task_id'], unknown['task_id']


def test_mixed_actions_and_history_are_consistent(candidate_store, monkeypatch):
    store = candidate_store
    cid, candidate_task, unknown_id = mixed(store)
    before = store.load_document()
    # Shared projection must not call full production eligibility, nor mutate.
    from deck_master import eligibility
    def forbidden(*args, **kwargs):
        pytest.fail('action projection invoked production eligibility')
    monkeypatch.setattr(eligibility, 'guard', forbidden)
    basis_reads = []
    original_state = candidates.basis_state
    def counted(*args, **kwargs):
        basis_reads.append(1)
        return original_state(*args, **kwargs)
    monkeypatch.setattr(candidates, 'basis_state', counted)
    summary = workbench.workbench_summary(store.project_root)
    assert len(basis_reads) == 2  # 22 candidates, only two distinct immutable bases
    assert summary['candidates'] == {'status': 'recorded', 'count': 22, 'pending_count': 1,
        'adopted_count': 0, 'kept_count': 0, 'unreadable_count': 0, 'stale_count': 21,
        'historical_count': 21, 'actionable_count': 1}
    by_kind = {a['kind']: a for a in summary['next_actions']['actions']}
    assert 'replan' not in by_kind
    failed = by_kind['inspect_failure']
    assert failed['object_count'] == 3 and failed['page_ids'] == ['p01', 'p02']
    targets = workbench.action_targets(store.project_root, failed['action_id'], revision=summary['revision_id'])
    assert {r['object_id'] for r in targets['targets']} == {'current-failed-a', 'current-failed-b', 'current-failed-c'}
    assert all(t['display']['relation']['state'] == 'current' for t in targets['targets'])
    assert len({t['display']['operation_id'] for t in targets['targets']}) == 3
    compare = workbench.action_targets(store.project_root, by_kind['compare_candidates']['action_id'], revision=summary['revision_id'])
    assert [r['object_id'] for r in compare['targets']] == [cid]
    rows = {r['task_id']: r for r in run_desk.listing(store.project_root, limit=100)['tasks']}
    for tid in ['old-failed', 'followed-failed', 'retired']:
        assert rows[tid]['human_actions'] == []
        assert rows[tid]['current_relation']['state'] == 'historical'
    assert rows['followed-failed']['current_relation']['successor_id'] == 'adopted-successor'
    assert rows[unknown_id]['current_relation']['state'] == 'unknown'
    assert rows[unknown_id]['human_actions'] == ['verify_unknown_call']
    assert rows[candidate_task]['pending_candidate_refs'] == [before['candidates'][0]]
    assert rows['old-failed']['status'] == 'failed'
    quality = workbench.action_targets(store.project_root, by_kind['review_quality']['action_id'], revision=summary['revision_id'])
    assert any(t['object_id'] == 'open-finding-review' for t in quality['targets'])
    assert store.read_object_json(before['reviews'][-1])['findings'][0]['resolution'] == 'open'
    assert store.load_document() == before
    from deck_master.action_currentness import Projection
    partial = {tid: copy.deepcopy(task) for tid, task in
        ((t['task_id'], t) for t in (store.read_object_json(ref) for ref in before['tasks']))}
    partial['adopted-successor']['result_refs'] = [before['pages'][0]['page']]
    projection = Projection(workbench._ReadContext(store, before), partial)
    assert projection.task(partial['followed-failed'])['state'] == 'current'  # only one of two pages covered
    unbound = copy.deepcopy(partial['current-failed-a'])
    unbound['task_id'] = 'legacy-unknown'; unbound.pop('collaboration_binding')
    assert projection.task(unbound)['state'] == 'unknown'
    # Existing detail freshness agrees with summary, retaining all 22 records.
    assert len(candidates.listing(store.project_root)['candidates']) == 22


@pytest.mark.browser
def test_real_browser_mixed_counts_and_fixed_targets(candidate_store, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    store = candidate_store
    cid, _, _ = mixed(store)
    before = store.load_document()
    summary = workbench.workbench_summary(store.project_root)
    failed = next(a for a in summary['next_actions']['actions'] if a['kind'] == 'inspect_failure')
    server = WorkbenchServer(store.project_root)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            url = server.start()
            identity = page.request.get(url+'api/project').json()['project_identity']
            page.goto(url+'v2/#'+urlencode({'project': identity, 'surface': 'overview'}))
            page.locator('.todo-more > summary').click()
            expect(page.get_by_role('heading', name='3 个任务 · 失败待查看', exact=True)).to_be_visible()
            expect(page.get_by_role('heading', name='1 个候选 · 候选待决定', exact=True)).to_be_visible()
            route = {'project': identity, 'surface': 'overview', 'action': failed['action_id'], 'revision': before['revision_id']}
            page.goto(url+'v2/#'+urlencode(route))
            expect(page.locator('.action-target')).to_have_count(3)
            for name in ['current-failed-a', 'current-failed-b']:
                expect(page.locator('.action-target').filter(has_text='op-'+name)).to_contain_text('当前请求')
            page.screenshot(path=str(tmp_path/'rp08-current-targets.png'), full_page=True)
            page.locator('.action-target').first.get_by_role('button', name='查看这个对象').click()
            page.wait_for_url('**task=current-failed-a*')
            assert before['revision_id'] in page.url
            assert not errors
            browser.close()
    finally:
        server.stop()
    assert store.load_document() == before


def test_current_request_with_changed_dependencies_requires_replan(candidate_store):
    store = candidate_store
    task = dispatch(store)
    doc = copy.deepcopy(store.load_document())
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = 'Changed adopted content'
    doc['pages'][0]['page'] = store.put_json_object(page)
    commit(store, doc, 'rp08-changed-dependencies')
    before = store.load_document()
    summary = workbench.workbench_summary(store.project_root)
    action = next(a for a in summary['next_actions']['actions'] if a['reason_code'] == 'dependency_basis_changed')
    assert action['kind'] == 'replan'
    targets = workbench.action_targets(store.project_root, action['action_id'], revision=summary['revision_id'])
    assert [t['object_id'] for t in targets['targets']] == [task['task_id']]
    row = run_desk.detail(store.project_root, task_id=task['task_id'])['task']
    assert row['status'] == 'awaiting_host' and row['human_actions'] == ['replan']
    assert row['current_relation']['status'] == row['current_relation']['state'] == 'current'
    assert row['current_relation']['reason'] == 'dependency_basis_changed'
    assert store.load_document() == before


def test_unrelated_page_change_does_not_hide_current_candidate(candidate_store):
    store = candidate_store
    cid = svg_candidate(store)
    doc = copy.deepcopy(store.load_document())
    page = store.read_object_json(doc['pages'][1]['page'])
    page['customer_visible']['title'] = 'Independent page edit'
    doc['pages'][1]['page'] = store.put_json_object(page)
    commit(store, doc, 'rp08-unrelated-page')
    summary = workbench.workbench_summary(store.project_root)
    assert summary['candidates']['stale_count'] == 0
    action = next(a for a in summary['next_actions']['actions'] if a['kind'] == 'compare_candidates')
    targets = workbench.action_targets(store.project_root, action['action_id'], revision=summary['revision_id'])
    assert [t['object_id'] for t in targets['targets']] == [cid]
