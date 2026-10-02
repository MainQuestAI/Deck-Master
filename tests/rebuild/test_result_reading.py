"""Personal projections, pagination, CAS and clear; synthetic result records."""
import copy
import pytest
from deck_master import result_reading, workbench, run_desk
from deck_master.local_state import LocalStateConflict
from deck_master.samples import create_sample
from deck_master.store import Store
from test_workbench_actions import synthetic_task, commit
from test_ui_state_clear import plan as clear_plan, commit as clear_commit


@pytest.fixture
def store(tmp_path):
    project=tmp_path/'reading';create_sample(project,page_count=2,readonly=False);store=Store(project)
    doc=copy.deepcopy(store.load_document());doc['tasks']=[]
    for i in range(35):
        task=synthetic_task(doc,f'read-{i}','completed',result_refs=[doc['pages'][0]['page']]);task['scope_pages']=['p01']
        doc['tasks'].append(store.put_json_object(task))
    commit(store,doc,'result-fixture');return store


def test_shared_projection_filters_before_pagination_and_preserves_business(store):
    project=store.project_root;doc=store.load_document();reading=result_reading.get(project)
    before=copy.deepcopy(doc)
    for ref in doc['tasks'][:31]:
        task=store.read_object_json(ref)
        reading=result_reading.mark(project,project_identity=reading['project_identity'],revision=doc['revision_id'],task_id=task['task_id'],result_key=result_reading.key(task),expected_etag=reading['etag'])
    summary=workbench.workbench_summary(project,reading=reading)
    action=next(a for a in summary['next_actions']['actions'] if a['kind']=='review_results')
    targets=workbench.action_targets(project,action['action_id'],revision=doc['revision_id'],reading=reading)
    rows=run_desk.listing(project,attention=True,reading=reading)
    assert targets['total']==rows['pagination']['total']==4
    assert {t['object_id'] for t in targets['targets']}=={t['task_id'] for t in rows['tasks']}
    assert run_desk.listing(project,attention=True)['pagination']['total']==35
    assert store.load_document()==before
    # New result is unread, without changing the prior receipt.
    changed=copy.deepcopy(doc);task=store.read_object_json(changed['tasks'][0]);task['result_refs']=[doc['pages'][1]['page']];changed['tasks'][0]=store.put_json_object(task)
    commit(store,changed,'new-result')
    assert run_desk.listing(project,attention=True,reading=reading)['pagination']['total']==5


def test_reading_cas_clear_backup_and_stale_snapshot(store):
    project=store.project_root;doc=store.load_document();task=store.read_object_json(doc['tasks'][0]);old=result_reading.get(project)
    args=dict(project_identity=old['project_identity'],revision=doc['revision_id'],task_id=task['task_id'],result_key=result_reading.key(task),expected_etag=old['etag'])
    marked=result_reading.mark(project,**args)
    with pytest.raises(LocalStateConflict):result_reading.get(project,expected_etag=old['etag'])
    with pytest.raises(LocalStateConflict):result_reading.mark(project,**args)
    plan=clear_plan(project);assert any(i['kind']=='result_reading' for i in plan['items'])
    cleared=clear_commit(project,plan)
    import json
    backup=json.loads((project/cleared['backup_ref']).read_text());assert any(r['kind']=='result_reading' and r['record']['seen']==marked['seen'] for r in backup['records'])
    assert result_reading.get(project)['seen']==[]
    with pytest.raises(LocalStateConflict):result_reading.mark(project,**{**args,'expected_etag':marked['etag']})
    assert store.load_document()==doc


def test_http_projection_snapshot_and_origin(store):
    from deck_master.web import WorkbenchServer
    from test_web import _get_json, _post_json, _session_token
    server=WorkbenchServer(store.project_root);url=server.start().rstrip('/')
    try:
        reading=_get_json(url+'/api/result-reading')[2]
        summary=_get_json(url+'/api/view/summary?personal=1')[2]
        assert summary['reading_etag']==reading['etag']
        task=store.read_object_json(store.load_document()['tasks'][0])
        body=dict(project_identity=reading['project_identity'],revision=summary['revision_id'],task_id=task['task_id'],result_key=result_reading.key(task),expected_etag=reading['etag'])
        assert _post_json(url+'/api/result-reading',body,None,None)[0]==403
        assert _post_json(url+'/api/result-reading',body,_session_token(url),url)[0]==200
        assert _get_json(url+'/api/tasks?limit=30&personal=1&reading_etag='+reading['etag'])[0]==409
    finally:server.stop()



def test_legacy_reading_import_is_explicit_and_verifies_saved_results(store):
    import json
    from deck_master import ui_journal
    project=store.project_root;doc=store.load_document();reading=result_reading.get(project)
    task=store.read_object_json(doc['tasks'][0]);bad=store.read_object_json(doc['tasks'][1])
    draft={'schema_version':'ui_draft.v1','draft_id':'legacy-reading','project_id':doc['project_id'],
        'project_identity':reading['project_identity'],'target':{'scope':'project','page_id':None,'layer':'notes'},
        'base_revision':doc['revision_id'],'base_ref':None,'content':{'run_desk':{'seen':[
            json.dumps([task['task_id'],[r['sha256'] for r in task['result_refs']]]),
            json.dumps([bad['task_id'],['0'*64]]),'bad json']}},'pending':None}
    # Existing project draft requires its fixed document reference.
    refs=ui_journal._base_refs(store,doc,draft['target']);draft['base_ref']=refs[0] if refs else None
    saved=ui_journal.save(project,draft=draft)
    assert result_reading.get(project)['seen']==[]
    imported=result_reading.import_legacy(project,draft_id=draft['draft_id'],project_identity=reading['project_identity'],expected_etag=reading['etag'])
    assert imported['verified_count']==1 and imported['reading']['seen']==[result_reading.key(task)]
    assert ui_journal.get(project,draft['draft_id'])['record']==saved['record']
