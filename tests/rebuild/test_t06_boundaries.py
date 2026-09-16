"""Behavioral regressions for T06 dispatch, permissions and call accounting."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from deck_master import service, tasks
from deck_master.models import ModelError, bump_revision, default_design_context
from deck_master.production import project_prompt
from deck_master.store import Store, StoreError

DRAFT = Path(__file__).resolve().parents[2] / 'docs/specs/deck-master-rebuild-v1/examples/roundtrips/result-envelope/compose.json'


def setup_project(tmp_path, limit=None):
    root = tmp_path / 'project'
    service.create(root, brief='regression', draft=json.loads(DRAFT.read_text()))
    store = Store(root)
    policy(store, external_call_limit=limit)
    return store


def policy(store, **changes):
    doc = store.load_document()
    new = bump_revision(doc, dict(operation_id=uuid.uuid4().hex, kind='policy_update', description='test policy', read_set=[]))
    new['policy'] = {**doc['policy'], **changes}
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=new['change']['operation_id'])


def dispatch(store):
    doc = store.load_document()
    return service.open_blueprint_task(store, doc, doc['pages'][0])


def claim_begin(store, task):
    service.task_start(store.project_root, task_id=task['task_id'], execution_ref='owner')
    return tasks.call_begin(store, task_id=task['task_id'], allowance_id='call-1', execution_ref='owner')


def settle(store, task, outcome, report=None, invocation=None):
    return tasks.call_settle(store, task_id=task['task_id'], allowance_id='call-1', outcome=outcome,
                             report_bytes=report, invocation_ref=invocation)


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
    s = setup_project(tmp_path, 1); t = dispatch(s)
    settle(s, t, 'not_sent')
    tasks.allocate_call_allowances(s, task_id=t['task_id'], count=1)
    policy(s, external_call_limit=None)
    tasks.allocate_call_allowances(s, task_id=t['task_id'], count=5)


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


def test_legacy_empty_task_repaired_or_rejected_when_stale(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s)
    d = s.load_document()
    service._commit_task_update(s, d, t, {**t, 'call_allowances': []}, 'simulate old dispatch')
    r = service.continue_project(s.project_root)['pending_tasks'][0]
    assert r['task_id'] == t['task_id'] and len(r['call_allowances']) == 1
    d = s.load_document(); old = tasks._lookup_task(d, t['task_id'], s)
    service._commit_task_update(s, d, old, {**old, 'call_allowances': [], 'produced_against': '0'*64}, 'stale')
    before = s.current_revision_id()
    with pytest.raises(tasks.TaskConflict): service.continue_project(s.project_root)
    assert s.current_revision_id() == before


def test_claim_stop_unknown_and_idempotence(tmp_path):
    s = setup_project(tmp_path); t = dispatch(s)
    with pytest.raises(tasks.TaskConflict):
        tasks.call_begin(s, task_id=t['task_id'], allowance_id='call-1', execution_ref='owner')
    with pytest.raises(tasks.TaskConflict): settle(s, t, 'consumed', b'not begun')
    service.task_start(s.project_root, task_id=t['task_id'], execution_ref='owner')
    for owner in ('wrong', '', None):
        with pytest.raises(tasks.TaskConflict):
            tasks.call_begin(s, task_id=t['task_id'], allowance_id='call-1', execution_ref=owner)
    policy(s, user_stop=True)
    with pytest.raises(tasks.CallBlocked):
        tasks.call_begin(s, task_id=t['task_id'], allowance_id='call-1', execution_ref='owner')
    assert service.continue_project(s.project_root)['status'] == 'needs_input'
    policy(s, user_stop=False)
    claim_begin(s, t); before = s.current_revision_id()
    assert tasks.call_begin(s, task_id=t['task_id'], allowance_id='call-1', execution_ref='owner')['status'] == 'already_started'
    assert before == s.current_revision_id()
    settle(s, t, 'unknown'); before = s.current_revision_id()
    assert settle(s, t, 'unknown')['status'] == 'already_settled'
    assert s.current_revision_id() == before
    with pytest.raises(tasks.CallBlocked): tasks.allocate_call_allowances(s, task_id=t['task_id'], count=1)
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
    root = tmp_path/'p'
    service.create(root, brief='test', draft=json.loads(DRAFT.read_text()), design={
        'assets':[dict(asset_id='logo',kind='logo',file=str(logo),external_use=permission)], 'allowed_asset_ids':['logo']})
    s = Store(root); before = s.current_revision_id()
    with pytest.raises(ModelError): service.continue_project(root)
    assert before == s.current_revision_id()


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
    d = s.load_document(); first = service.open_compose_task(s,d,operation_id='race-a')
    second = service.open_compose_task(s,s.load_document(),operation_id='race-b')
    code = '''import sys,time
from pathlib import Path
from deck_master.tasks import allocate_call_allowances,CallBlocked
from deck_master.store import Store
while not Path(sys.argv[3]).exists(): time.sleep(.01)
try: allocate_call_allowances(Store(sys.argv[1]),task_id=sys.argv[2],count=1)
except CallBlocked: sys.exit(3)
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
    tasks.call_begin(s,task_id=t['task_id'],allowance_id='call-2',execution_ref='owner')
    settle(s,t,'unknown')
    with pytest.raises(tasks.CallBlocked):
        tasks.call_begin(s,task_id=t['task_id'],allowance_id='call-3',execution_ref='owner')
    tasks.call_settle(s,task_id=t['task_id'],allowance_id='call-2',outcome='consumed',report_bytes=b'real return')


def test_page_empty_permissions_remove_prompt_and_files(tmp_path):
    logo=tmp_path/'logo.svg';logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    draft=json.loads(DRAFT.read_text());draft['pages'][0]['visual_spec']['design_overrides']={'allowed_asset_ids':[]}
    root=tmp_path/'p'
    service.create(root,brief='page scope',draft=draft,design={'assets':[dict(asset_id='logo',kind='logo',file=str(logo),external_use='allowed')],'allowed_asset_ids':['logo']})
    t=service.continue_project(root)['pending_tasks'][0]
    assert t['production_request']['permitted_asset_files']==[]
    assert t['production_request']['projection']['permitted_assets']==[]
    assert t['resolved_design_context']['assets']==[]


def test_cli_storage_conflict_is_five(capsys):
    from deck_master.cli import _fail
    from deck_master.store import ConflictError
    assert _fail(ConflictError('current','moved'))==5
    assert json.loads(capsys.readouterr().err)['error']['code']=='conflict'


def test_orphan_recovers_after_authorized_budget_change(tmp_path):
    s=setup_project(tmp_path,0);d=s.load_document();page=d['pages'][0]
    from deck_master.models import content_identity
    t=tasks.new_task(task_id='legacy-empty',operation_id='legacy-dispatch',kind='blueprint',scope_pages=[page['page_id']],instruction='old task',inputs=[page['page']],dependencies=[],dispatch_revision=d['revision_id'],produced_against=content_identity(d))
    new=bump_revision(d,dict(operation_id='old-dispatch',kind='task_update',description='old empty task',read_set=[]))
    new['tasks']=d['tasks']+[s.put_json_object(t)]
    s.commit_change(base_revision=d['revision_id'],document=new,operation_id='old-dispatch')
    assert service.continue_project(s.project_root)['status']=='needs_input'
    policy(s,external_call_limit=1)
    pending=service.continue_project(s.project_root)['pending_tasks'][0]
    assert pending['task_id']=='legacy-empty' and len(pending['call_allowances'])==1
    assert pending['produced_against']==content_identity(s.load_document())


def test_pointer_failure_preserves_old_project(tmp_path,monkeypatch):
    import deck_master.store as store_module
    s=setup_project(tmp_path);before=s.load_document();write=store_module._atomic_write_bytes
    def fail_pointer(path,data):
        if path.name=='current.json': raise OSError('injected pointer failure')
        return write(path,data)
    monkeypatch.setattr(store_module,'_atomic_write_bytes',fail_pointer)
    with pytest.raises(OSError): dispatch(s)
    assert s.load_document()==before
