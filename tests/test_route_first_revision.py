import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from workflow.actions import create_action_envelope,stage_action_result,commit_action_result,read_current_revision,read_revision_state
from build.build_route import persist_route,resolve_build_route,load_persisted_route

def baseline(root):
    (root/'request.json').write_text(json.dumps({'run_mode':'production'}))
    e=create_action_envelope(action_id='first',task_id='first',scope_pages=['P001'],permission='runtime',input_fingerprint='x')
    stage_action_result(root,e,{'narrative_plan.json':'{}'})
    commit_action_result(root,e,current_input_fingerprint='x',targets={'narrative_plan.json':root/'narrative_plan.json'})

def test_first_route_after_content_snapshot_is_authoritative(tmp_path):
    baseline(tmp_path);old=read_current_revision(tmp_path)['revision_id'];route=resolve_build_route({'run_mode':'production','profile':'native'})
    assert persist_route(tmp_path,route)==route
    assert load_persisted_route(tmp_path)==route
    assert read_current_revision(tmp_path)['revision_id']!=old
    assert json.loads(read_revision_state(tmp_path)['build/route.json'])==route
    assert read_revision_state(tmp_path)['narrative_plan.json']==b'{}'
    with pytest.raises(ValueError,match='conflict'):
        persist_route(tmp_path,resolve_build_route({'run_mode':'fixture','profile':'legacy-ppt-master'}))

def test_concurrent_first_routes_have_one_winner(tmp_path):
    baseline(tmp_path);barrier=Barrier(2)
    routes=[resolve_build_route({'profile':p,'run_mode':'production'}) for p in ['native','legacy-ppt-master']]
    def call(route):
        barrier.wait()
        try:return persist_route(tmp_path,route)
        except ValueError:return 'conflict'
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(call,routes))
    assert results.count('conflict')==1
    winner=next(r for r in results if r!='conflict')
    assert load_persisted_route(tmp_path)==winner
    assert json.loads(read_revision_state(tmp_path)['build/route.json'])==winner

@pytest.mark.parametrize('change',[{'origin_run_mode':'fixture'},{'density':'high'},{'authoring_mode':'direct_svg'}])
def test_first_route_fields_cannot_be_overridden(tmp_path,change):
    baseline(tmp_path);route=resolve_build_route({'run_mode':'production','profile':'native'});persist_route(tmp_path,route)
    revision=read_current_revision(tmp_path)['revision_id']
    with pytest.raises(ValueError,match='conflict'):persist_route(tmp_path,{**route,**change})
    assert read_current_revision(tmp_path)['revision_id']==revision
    assert load_persisted_route(tmp_path)==route

def test_identical_concurrent_persistence_is_idempotent(tmp_path):
    baseline(tmp_path);barrier=Barrier(2);route=resolve_build_route({'run_mode':'production'})
    def call(_):barrier.wait();return persist_route(tmp_path,route)
    with ThreadPoolExecutor(2) as pool:assert list(pool.map(call,range(2)))==[route,route]
    revision=read_current_revision(tmp_path)['revision_id']
    assert persist_route(tmp_path,route)==route
    assert read_current_revision(tmp_path)['revision_id']==revision
