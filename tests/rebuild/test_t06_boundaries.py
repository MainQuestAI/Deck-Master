"""Behavioral regressions for T06 dispatch, permissions and call accounting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from deck_master import collaboration, eligibility, generation, service, tasks
from deck_master.models import ModelError, bump_revision, default_design_context
from deck_master.production import project_prompt
from deck_master.store import Store, StoreError
from rc3_fixtures import authorize_scope, claim_fixture_task, evidence_for, settle_fidelity_review, source_snapshot

DRAFT = Path(__file__).resolve().parents[2] / 'docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/compose.json'


def setup_project(tmp_path, limit=None, *, draft=None, design=None):
    """Current L1 fixture: real manuscript/request/grant/fidelity, no image call."""
    root = tmp_path / 'project'
    manuscript = draft or {'pages': json.loads(DRAFT.read_text())['pages']}
    ids = [p['page_id'] for p in manuscript['pages']]
    scope = {'subject': 'deck', 'page_ids': ids, 'page_manifest_ref': None,
        'external_artifact_ref': None,
        'layers': ['page_copy', 'plan', 'speech', 'blueprint', 'svg', 'review', 'output', 'design'],
        'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}
    service.create(root, brief='L1 synthetic dispatch/accounting regression', draft=manuscript,
        design=design, request_input={'intent': 'full_deck', 'scope': scope})
    store = Store(root)
    policy(store, external_call_limit=limit)
    authorize_scope(root, actions=['dispatch.blueprint', 'dispatch.host_task', 'allowance.allocate',
        'allowance.repair', 'call.begin', 'generation.dispatch'], scope=scope,
        max_external_calls=32, max_candidate_count=0, adoption_policy='within_scope',
        evidence=evidence_for(root, text='L1 explicitly authorize scoped blueprint protocol and synthetic ledger events. No real provider, native output, fee, or human review is claimed.',
            locator='synthetic-l1:t06-accounting'))
    settle_fidelity_review(root, page_ids=ids, execution_ref='L1-t06-fidelity', scenario='Fixed manuscript dispatch accounting')
    return store


def policy(store, **changes):
    doc = store.load_document()
    new = bump_revision(doc, dict(operation_id=uuid.uuid4().hex, kind='policy_update', description='L1 explicit test policy', read_set=[]))
    new['policy'] = {**doc['policy'], **changes}
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=new['change']['operation_id'])
    # Policy is a registered basis. A fresh explicit instruction updates this
    # same authorization identity; it does not rewrite old workorders/credit.
    for ref in store.load_document()['collaboration']['authorizations']:
        record = store.read_object_json(ref)
        if 'dispatch.blueprint' not in record['actions']:
            continue
        values = {key: record[key] for key in ('authorization_id', 'mode', 'actions', 'scope',
            'max_external_calls', 'max_candidate_count', 'adoption_policy', 'budget_key', 'budget_parent_ref')}
        collaboration.grant(store.project_root, input={**values, 'replaces': ref,
            'instruction_evidence': evidence_for(store.project_root,
                text='L1 explicit changed-policy instruction retains scoped authority and prior call facts.',
                locator='synthetic-l1:t06-policy:' + store.current_revision_id())},
            base_revision=store.current_revision_id(), operation_id=uuid.uuid4().hex)


def dispatch(store):
    doc = store.load_document()
    return service.open_blueprint_task(store, doc, doc['pages'][0])


def _current(store, task):
    return tasks._lookup_task(store.load_document(), task['task_id'], store)


def _request(store, task):
    current = _current(store, task)
    if current.get('generation_requests'):
        return store.read_object_json(current['generation_requests'][-1])['request_id']
    prepared = generation.prepared_input(store, store.load_document(), current)
    return generation.freeze(store.project_root, task_id=task['task_id'], input=prepared,
        base_revision=store.current_revision_id(), operation_id=uuid.uuid4().hex)['request_id']


def _begin(store, task, allowance='call-1', execution='owner'):
    return tasks.call_begin(store, task_id=task['task_id'], allowance_id=allowance,
        execution_ref=execution, request_id=_request(store, task))


def claim_begin(store, task):
    claim_fixture_task(store.project_root, _current(store, task), execution_ref='owner')
    return _begin(store, task)


def settle(store, task, outcome, report=None, invocation=None, allowance='call-1'):
    current = _current(store, task)
    attempts = [store.read_object_json(ref) for ref in current.get('generation_attempts', [])]
    attempt = next((a for a in attempts if a['allowance_id'] == allowance), None)
    # Deliberate L1 Host-reported observation: never native/tool-observed proof.
    data = json.dumps({'evidence_level': 'L1_SYNTHETIC', 'reported': report.decode()}).encode() if report else None
    return tasks.call_settle(store, task_id=task['task_id'], allowance_id=allowance, outcome=outcome,
        report_bytes=data, invocation_ref=invocation, attempt_id=attempt['attempt_id'] if attempt else None)


@pytest.mark.parametrize('state', ['cancelled', 'completed'])
def test_global_limit_keeps_terminal_consumption(tmp_path, state):
    s = setup_project(tmp_path, 1); t = dispatch(s); claim_begin(s, t)
    settle(s, t, 'consumed', b'sent failed', 'inv-1')
    d = s.load_document(); old = tasks._lookup_task(d, t['task_id'], s)
    service._commit_task_update(s, d, old, {**old, 'status': state}, 'test terminal')
    before = s.current_revision_id()
    assert service.continue_project(s.project_root)['status'] == 'needs_input'
    assert s.current_revision_id() == before


def test_released_slot_reusable_and_unlimited(tmp_path):
    s = setup_project(tmp_path, 1); t = dispatch(s); claim_begin(s, t)
    settle(s, t, 'not_sent')
    tasks.allocate_call_allowances(s, task_id=t['task_id'], count=1)
    policy(s, external_call_limit=None)
    service.task_cancel(s.project_root, task_id=t['task_id'])
    fresh = dispatch(s)
    tasks.allocate_call_allowances(s, task_id=fresh['task_id'], count=4)
    assert _current(s, t)['call_allowances'][0]['state'] == 'released'


def test_zero_limit_no_task_and_retry(tmp_path):
    s = setup_project(tmp_path, 0); before = s.load_document()
    for _ in range(2):
        assert service.continue_project(s.project_root)['status'] == 'needs_input'
        assert s.load_document() == before
    policy(s, external_call_limit=1)
    first = service.continue_project(s.project_root)['pending_tasks'][0]
    assert service.continue_project(s.project_root)['pending_tasks'][0]['task_id'] == first['task_id']


def test_failed_commit_never_publishes_empty_task(tmp_path, monkeypatch):
    s = setup_project(tmp_path); before = s.load_document()
    def fail(**kwargs):
        raise StoreError('injected', 'before pointer swap')
    monkeypatch.setattr(s, '_commit_locked', fail)
    with pytest.raises(StoreError): dispatch(s)
    assert s.load_document() == before


def test_interrupted_bound_empty_task_repaired_or_rejected_when_stale(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s)
    d = s.load_document()
    service._commit_task_update(s, d, t, {**t, 'call_allowances': []}, 'L1 interrupted current dispatch after binding')
    r = service.continue_project(s.project_root)['pending_tasks'][0]
    assert r['task_id'] == t['task_id'] and len(r['call_allowances']) == 1
    d = s.load_document(); old = tasks._lookup_task(d, t['task_id'], s)
    service._commit_task_update(s, d, old, {**old, 'call_allowances': [], 'produced_against': '0'*64}, 'stale')
    before = s.current_revision_id()
    with pytest.raises(tasks.TaskConflict): service.continue_project(s.project_root)
    assert s.current_revision_id() == before


def test_claim_stop_unknown_and_idempotence(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s)
    with pytest.raises(generation.GenerationError, match='requires generation.v1'):
        tasks.call_begin(s, task_id=t['task_id'], allowance_id='call-1', execution_ref='owner')
    with pytest.raises(generation.GenerationError, match='begun attempt'):
        settle(s, t, 'consumed', b'not begun')
    claim_fixture_task(s.project_root, t, execution_ref='owner')
    _request(s, t)
    for owner in ('wrong', '', None):
        with pytest.raises(tasks.TaskConflict):
            _begin(s, t, execution=owner)
    stopped = setup_project(tmp_path / 'stopped')
    stop_task = dispatch(stopped)
    claim_fixture_task(stopped.project_root, stop_task, execution_ref='owner')
    _request(stopped, stop_task)
    policy(stopped, user_stop=True)
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        _begin(stopped, stop_task)
    assert 'user_stop' in blocked.value.decision['reason_codes']
    assert service.continue_project(stopped.project_root)['status'] == 'needs_input'
    claim_begin(s, t); before = s.current_revision_id()
    assert _begin(s, t)['status'] == 'already_started'
    assert before == s.current_revision_id()
    settle(s, t, 'unknown'); before = s.current_revision_id()
    assert settle(s, t, 'unknown')['status'] == 'already_settled'
    assert s.current_revision_id() == before
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        tasks.allocate_call_allowances(s, task_id=t['task_id'], count=1)
    assert 'budget_unknown' in blocked.value.decision['reason_codes']
    assert service.continue_project(s.project_root)['status'] == 'needs_input'
    with pytest.raises(tasks.EnvelopeError): settle(s, t, 'consumed')
    settle(s, t, 'consumed', b'real report', 'inv-1')
    before = s.current_revision_id()
    assert settle(s, t, 'consumed', b'real report', 'inv-1')['status'] == 'already_settled'
    assert s.current_revision_id() == before
    with pytest.raises(tasks.TaskConflict): settle(s, t, 'consumed', b'different', 'inv-1')
    with pytest.raises(tasks.TaskConflict): settle(s, t, 'not_sent', b'report')


def test_cancelled_late_cost_and_duplicate_invocation(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s); claim_begin(s, t)
    service.task_cancel(s.project_root, task_id=t['task_id'])
    settle(s, t, 'consumed', b'late report', 'same-inv')
    second = dispatch(s); claim_begin(s, second)
    with pytest.raises(tasks.TaskConflict): settle(s, second, 'consumed', b'late report', 'same-inv')
    assert tasks._lookup_task(s.load_document(), t['task_id'], s)['status'] == 'cancelled'


def test_settlement_enriches_missing_invocation(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s); claim_begin(s, t)
    settle(s, t, 'consumed', b'report')
    settle(s, t, 'consumed', b'report', 'inv')
    with pytest.raises(tasks.TaskConflict): settle(s, t, 'consumed', b'report', 'different-inv')


@pytest.mark.parametrize('permission', ['restricted', 'unspecified'])
def test_restricted_assets_never_dispatched(tmp_path, permission):
    logo = tmp_path/'logo.svg'; logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    s = setup_project(tmp_path, design={
        'assets':[dict(asset_id='logo',kind='logo',file=str(logo),external_use='allowed')],
        'allowed_asset_ids':['logo']})
    before = s.load_document()
    design = json.loads(json.dumps(before['design_context']))
    design['assets'][0]['external_use'] = permission
    # Current design writes validate every effective page before publishing;
    # the forbidden asset cannot become a generation input or a new Task.
    with pytest.raises(ModelError, match='not allowed for external use'):
        service.update_design(s.project_root, design_context=design, base_revision=before['revision_id'])
    assert s.load_document() == before
    assert not [s.read_object_json(ref) for ref in before['tasks']
        if s.read_object_json(ref)['kind'] == 'blueprint']
    # The permission predicate itself also refuses the exact submitted view.
    page = s.read_object_json(before['pages'][0]['page'])
    with pytest.raises(ModelError, match='not allowed for external use'):
        project_prompt(page, design, design['assets'])
    # Explicit L1 fault injection also retains the dispatch defense for a
    # previously persisted invalid design. No fake Task/authority is inserted.
    injected = bump_revision(before, dict(operation_id=uuid.uuid4().hex,
        kind='design_update', description='L1 persisted invalid asset-policy fixture', read_set=[]))
    injected['design_context'] = design
    s.commit_change(base_revision=before['revision_id'], document=injected,
        operation_id=injected['change']['operation_id'])
    before_dispatch = s.load_document()
    snapshot = source_snapshot(s.project_root)
    with pytest.raises(ModelError, match='not allowed for external use'):
        dispatch(s)
    assert s.load_document() == before_dispatch
    assert source_snapshot(s.project_root) == snapshot


def test_effective_overrides_and_canvas(tmp_path):
    page = json.loads(DRAFT.read_text())['pages'][0]; design = default_design_context()
    design['canvas'].update(width_px=1200, height_px=900, slide_width_in=10, slide_height_in=7.5)
    design['allowed_asset_ids'] = ['logo']; assets = [dict(asset_id='logo',kind='logo',external_use='allowed')]
    page['visual_spec']['design_overrides'] = dict(language='en-US', body_font_id='heading', allowed_asset_ids=[])
    r = project_prompt(page, design, assets)
    assert r['projection']['permitted_assets'] == []
    assert r['projection']['language'] == 'en-US'
    assert r['projection']['style']['typography']['body_font_id'] == 'heading'
    assert '1200x900' in r['prompt'] and '16:9' not in r['prompt']
    page['visual_spec']['design_overrides']['allowed_asset_ids'] = ['unknown']
    with pytest.raises(ModelError): project_prompt(page, design, assets)
    page['visual_spec']['design_overrides'] = dict(body_font_id='unknown')
    with pytest.raises(ModelError): project_prompt(page, design, assets)


def test_cli_waiting_and_budget_exit_three(tmp_path):
    s = setup_project(tmp_path, 0)
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]/'src')}
    def run():
        return subprocess.run([sys.executable,'-m','deck_master.cli','continue','--project',str(s.project_root)], env=env, capture_output=True, text=True)
    r = run(); assert r.returncode == 3 and json.loads(r.stdout)['status'] == 'needs_input' and not r.stderr
    policy(s, external_call_limit=1)
    r = run(); assert r.returncode == 3 and json.loads(r.stdout)['status'] == 'awaiting_host'


def test_two_processes_compete_for_last_slot(tmp_path):
    s = setup_project(tmp_path, 1)
    # Two independent active work orders; allocation itself must serialize.
    ids = [s.load_document()['pages'][0]['page_id']]
    first = service.open_host_task(s, kind='repair', page_ids=ids, instruction='L1 race workorder A')
    second = service.open_host_task(s, kind='repair', page_ids=ids, instruction='L1 race workorder B')
    code = '''import sys,time
from pathlib import Path
from deck_master.tasks import allocate_call_allowances,CallBlocked
from deck_master.store import Store
from deck_master.eligibility import EligibilityBlocked
while not Path(sys.argv[3]).exists(): time.sleep(.01)
try: allocate_call_allowances(Store(sys.argv[1]),task_id=sys.argv[2],count=1)
except (CallBlocked,EligibilityBlocked): sys.exit(3)
'''
    env = {**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'src')}
    barrier = tmp_path/'go'
    processes = [subprocess.Popen([sys.executable,'-c',code,str(s.project_root),t['task_id'],str(barrier)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for t in (first,second)]
    barrier.touch()
    results = [p.communicate(timeout=15) for p in processes]
    assert sorted(p.returncode for p in processes) == [0,3], results
    assert sum(len(s.read_object_json(r).get('call_allowances',[])) for r in s.load_document()['tasks']) == 1


def test_envelope_cannot_bypass_settlement_checks(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s)
    event = dict(allowance_id='call-1',outcome='consumed',invocation_ref='bypass',evidence_file_ids=[])
    with pytest.raises(tasks.TaskConflict): tasks._settled_allowances(t,[event],{},s)
    claim_begin(s,t)
    current=tasks._lookup_task(s.load_document(),t['task_id'],s)
    with pytest.raises(tasks.EnvelopeError): tasks._settled_allowances(current,[event],{},s)


def test_unknown_release_and_late_product_refused(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s); claim_begin(s,t)
    settle(s,t,'unknown')
    with pytest.raises(tasks.EnvelopeError): settle(s,t,'not_sent')
    settle(s,t,'not_sent',b'verified not sent')
    service.task_cancel(s.project_root,task_id=t['task_id'])
    before_pages=s.load_document()['pages']
    with pytest.raises(tasks.TaskConflict):
        service.accept_result(s.project_root,task_id=t['task_id'],operation_id=t['operation_id'],
                              produced_against=t['produced_against'],result_payload={'kind':'blueprint','files':[]})
    assert s.load_document()['pages']==before_pages


def test_unknown_blocks_other_reserved_call_but_not_inflight_settlement(tmp_path):
    s=setup_project(tmp_path); t=dispatch(s)
    tasks.allocate_call_allowances(s,task_id=t['task_id'],count=2)
    claim_begin(s,t)
    _begin(s, t, 'call-2')
    settle(s,t,'unknown')
    with pytest.raises(tasks.CallBlocked, match='resolve unknown calls'):
        _begin(s, t, 'call-3')
    settle(s, t, 'consumed', b'L1 returned report', allowance='call-2')


def test_page_empty_permissions_remove_prompt_and_files(tmp_path):
    logo=tmp_path/'logo.svg';logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    draft={'pages': json.loads(DRAFT.read_text())['pages']};draft['pages'][0]['visual_spec']['design_overrides']={'allowed_asset_ids':[]}
    s=setup_project(tmp_path,draft=draft,design={'assets':[dict(asset_id='logo',kind='logo',file=str(logo),external_use='allowed')],'allowed_asset_ids':['logo']})
    t=service.continue_project(s.project_root)['pending_tasks'][0]
    assert t['production_request']['permitted_asset_files']==[]
    assert t['production_request']['projection']['permitted_assets']==[]
    assert t['resolved_design_context']['assets']==[]


def test_cli_storage_conflict_is_five(capsys):
    from deck_master.cli import _fail
    from deck_master.store import ConflictError
    assert _fail(ConflictError('current','moved'))==5
    assert json.loads(capsys.readouterr().err)['error']['code']=='conflict'


def test_interrupted_bound_task_is_not_rebound_by_a_budget_change(tmp_path):
    s = setup_project(tmp_path, 1)
    t = dispatch(s)
    d = s.load_document()
    service._commit_task_update(s, d, t, {**t, 'call_allowances': []}, 'L1 interrupted allocation fixture')
    policy(s, external_call_limit=0)
    assert service.continue_project(s.project_root)['status'] == 'needs_input'
    policy(s, external_call_limit=1)
    before = s.load_document()
    with pytest.raises(eligibility.EligibilityBlocked):
        tasks.allocate_call_allowances(s, task_id=t['task_id'], count=1)
    assert s.load_document() == before and _current(s, t)['call_allowances'] == []
    service.task_cancel(s.project_root, task_id=t['task_id'])
    fresh = service.continue_project(s.project_root)['pending_tasks'][0]
    assert fresh['task_id'] != t['task_id'] and len(fresh['call_allowances']) == 1
    assert fresh['collaboration_binding'] and fresh['protocol_version'] == 'generation.v1'


def test_pointer_failure_preserves_old_project(tmp_path,monkeypatch):
    import deck_master.store as store_module
    s=setup_project(tmp_path);before=s.load_document();write=store_module._atomic_write_bytes
    def fail_pointer(path,data):
        if path.name=='current.json': raise OSError('injected pointer failure')
        return write(path,data)
    monkeypatch.setattr(store_module,'_atomic_write_bytes',fail_pointer)
    with pytest.raises(OSError): dispatch(s)
    assert s.load_document()==before
