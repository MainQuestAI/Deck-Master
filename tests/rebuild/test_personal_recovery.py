"""Clear-backup identity, explicit preview and non-overwriting personal restoration."""
import copy
import json
import pytest
from deck_master import personal_recovery as recovery, ui_journal, gallery_state, overview_state, result_reading
from deck_master.local_state import LocalStateConflict, LocalStateError, write_json
from test_result_reading import store
from test_ui_state_clear import save_draft, plan as clear_plan, commit as clear_commit


def prepare(store):
    project=store.project_root;doc=store.load_document();identity=ui_journal.list_drafts(project)['project_identity']
    save_draft(store,project,text='备份中的正文笔记')
    gallery_state.save(project,state={'schema_version':'ui_gallery.v1','project_id':doc['project_id'],'project_identity':identity,
        'revision_id':doc['revision_id'],'layer':'original_image','mode':'grid','columns':3,'selected_page_ids':['p01'],
        'references':[],'filter':{'chapter_id':None,'status':'all'},'anchor':{'page_id':'p01','offset':0},'zoom':{'synchronized':True,'scale':1}})
    overview_state.save(project,state={'schema_version':'ui_overview.v1','project_id':doc['project_id'],'project_identity':identity,
        'revision_id':doc['revision_id'],'filter':'all','search':'','sort':'ascending','selected_page_ids':['p01']})
    ui_journal.save_position(project,position={'schema_version':'ui_position.v1','project_id':doc['project_id'],'project_identity':identity,
        'page_id':'p01','surface':'page','layer':'content','revision':doc['revision_id'],'zoom':1})
    reading=result_reading.get(project);task=store.read_object_json(doc['tasks'][0])
    result_reading.mark(project,project_identity=identity,revision=doc['revision_id'],task_id=task['task_id'],result_key=result_reading.key(task),expected_etag=reading['etag'])
    result=clear_commit(project,clear_plan(project));return result['manifest_digest'][:16]


def test_backup_restores_all_personal_kinds_and_preserves_business(store):
    before=copy.deepcopy(store.load_document());key=prepare(store);project=store.project_root
    value=recovery.plan(project,backup_id=key)
    assert {r['kind'] for r in value['records']}==set(recovery.LABELS)
    assert all(r['action']=='restore' for r in value['records'])
    result=recovery.restore(project,backup_id=key,plan_digest=value['plan_digest'])
    assert result['status']=='restored' and all(r['status']=='restored' for r in result['records'])
    assert ui_journal.list_drafts(project)['records'][0]['draft']['content']['text']=='备份中的正文笔记'
    assert gallery_state.get(project)['record']['state']['selected_page_ids']==['p01']
    assert overview_state.get(project,revision=before['revision_id'])['record']['state']['selected_page_ids']==['p01']
    assert result_reading.get(project)['seen']
    assert ui_journal.read_position(project)['position']['page_id']=='p01'
    assert store.load_document()==before
    # Repeating requires a fresh preview, and cannot duplicate unchanged drafts.
    with pytest.raises(LocalStateConflict):recovery.restore(project,backup_id=key,plan_digest=value['plan_digest'])
    value=recovery.plan(project,backup_id=key);assert all(r['action']=='keep' for r in value['records'])


def test_restore_keeps_new_records_and_copies_conflicting_draft(store):
    key=prepare(store);project=store.project_root;save_draft(store,project,text='清理后的新笔记')
    reading=result_reading.get(project);doc=store.load_document();task=store.read_object_json(doc['tasks'][1])
    marked=result_reading.mark(project,project_identity=reading['project_identity'],revision=doc['revision_id'],task_id=task['task_id'],result_key=result_reading.key(task),expected_etag=reading['etag'])
    value=recovery.plan(project,backup_id=key);rows={r['kind']:r for r in value['records']}
    assert rows['draft']['action']=='copy' and rows['result_reading']['action']=='keep'
    assert rows['draft']['current']['draft']['content']['text']=='清理后的新笔记'
    result=recovery.restore(project,backup_id=key,plan_digest=value['plan_digest'])
    assert result['status']=='restored'
    assert {r['draft']['content']['text'] for r in ui_journal.list_drafts(project)['records']}=={'清理后的新笔记','备份中的正文笔记'}
    assert result_reading.get(project)==marked
    repeated=recovery.plan(project,backup_id=key)
    assert next(r for r in repeated['records'] if r['kind']=='draft')['action']=='keep'
    recovery.restore(project,backup_id=key,plan_digest=repeated['plan_digest'])
    assert len(ui_journal.list_drafts(project)['records'])==2
    recovered=next(r for r in ui_journal.list_drafts(project)['records'] if r['draft']['draft_id'].startswith('recovered-clear-'))
    edited=copy.deepcopy(recovered['draft']);edited['content']['text']='在恢复副本继续写入'
    ui_journal.save(project,draft=edited,expected_etag=recovered['etag'])
    repeated=recovery.plan(project,backup_id=key)
    recovery.restore(project,backup_id=key,plan_digest=repeated['plan_digest'])
    assert {r['draft']['content']['text'] for r in ui_journal.list_drafts(project)['records']}=={'清理后的新笔记','在恢复副本继续写入'}


def test_restore_stale_preview_refuses_before_any_write(store):
    key=prepare(store);project=store.project_root;value=recovery.plan(project,backup_id=key)
    save_draft(store,project,text='预览后的新输入')
    with pytest.raises(LocalStateConflict):recovery.restore(project,backup_id=key,plan_digest=value['plan_digest'])
    assert gallery_state.get(project)['record'] is None
    assert len(ui_journal.list_drafts(project)['records'])==1


@pytest.mark.parametrize('bad',['../position','0'*16,'file:///tmp/private','f'*64])
def test_backup_download_rejects_paths_and_unregistered_ids(store,bad):
    with pytest.raises(LocalStateError):recovery.download(store.project_root,backup_id=bad)


def test_backup_tamper_and_foreign_identity_are_refused(store):
    key=prepare(store);project=store.project_root;raw,name=recovery.download(project,backup_id=key)
    backup=json.loads(raw);assert name.endswith(key+'.json')
    backup['records'][0]['record']['draft']['content']['text']='tampered'
    path=store.deck_root/'workbench'/'clear-backups'/(key+'.json');write_json(path,backup)
    with pytest.raises(LocalStateError):recovery.download(project,backup_id=key)
    assert recovery.listing(project)['backups'][0]['available'] is False


def test_same_project_private_backup_keeps_literal_local_path_text(store):
    project=store.project_root;save_draft(store,project,text='/Users/example/review.md')
    result=clear_commit(project,clear_plan(project));key=result['manifest_digest'][:16]
    value=recovery.plan(project,backup_id=key)
    assert recovery.listing(project)['backups'][0]['available']
    recovery.restore(project,backup_id=key,plan_digest=value['plan_digest'])
    assert ui_journal.list_drafts(project)['records'][0]['draft']['content']['text']=='/Users/example/review.md'


def test_backup_symlink_and_foreign_copy_are_not_downloaded(store,tmp_path):
    from deck_master.samples import create_sample
    key=prepare(store);project=store.project_root
    other=tmp_path/'foreign';create_sample(other,page_count=2,readonly=False)
    other_root=other/'.deckmaster/workbench';other_root.mkdir(parents=True,exist_ok=True)
    (other_root/'clear-backups').mkdir()
    (other_root/'clear-backups'/f'{key}.json').write_bytes((store.deck_root/'workbench/clear-backups'/f'{key}.json').read_bytes())
    (other_root/'clear-log.jsonl').write_bytes((store.deck_root/'workbench/clear-log.jsonl').read_bytes())
    with pytest.raises(LocalStateError):recovery.download(other,backup_id=key)
    path=store.deck_root/'workbench/clear-backups'/f'{key}.json';data=path.read_bytes();path.unlink();target=tmp_path/'external.json';target.write_bytes(data);path.symlink_to(target)
    with pytest.raises(LocalStateError):recovery.download(project,backup_id=key)


def test_http_backup_download_and_restore_require_real_entry_and_auth(store):
    from deck_master.web import WorkbenchServer
    from test_web import _get_json,_post_json,_session_token
    key=prepare(store);server=WorkbenchServer(store.project_root);url=server.start().rstrip('/')
    try:
        assert _get_json(url+'/api/ui-state/backups')[2]['backups'][0]['backup_id']==key
        assert _get_json(url+'/api/ui-state/backups/'+key+'/download')[2]['schema_version']=='ui_clear_backup.v1'
        assert _post_json(url+'/api/ui-state/plan-restore',{'backup_id':key},None,None)[0]==403
        token=_session_token(url);status,plan=_post_json(url+'/api/ui-state/plan-restore',{'backup_id':key},token,url);assert status==200
        assert _post_json(url+'/api/ui-state/restore',{'backup_id':key,'plan_digest':plan['plan_digest']},token,url)[0]==200
    finally:server.stop()
