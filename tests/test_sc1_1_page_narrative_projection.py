import copy,json
from pathlib import Path
from build.native_content import build_native_content_lock,ensure_native_content
from test_sc1_1_native_host_chain import new_run
from production.page_package import PagePackageIndex
from workflow.actions import stage_action_result,commit_action_result,read_current_revision

def test_page_edit_keeps_other_lock_but_global_change_invalidates(tmp_path):
 root=new_run(tmp_path,'direct_svg');p=json.loads((root/'page_packages/P001.json').read_text())
 n={'run_id':root.name,'governing_thought':'先可见后自动化','pages':[{'page_id':'P001','title':'one'},{'page_id':'P002','title':'two'}]}
 a=build_native_content_lock(p,n);edited=copy.deepcopy(n);edited['pages'][1]['title']='changed'
 assert build_native_content_lock(p,edited)['content_lock_sha256']==a['content_lock_sha256']
 edited['governing_thought']='replace systems'
 assert build_native_content_lock(p,edited)['content_lock_sha256']!=a['content_lock_sha256']
 unknown={'unrecognized_plan':[{'title':'one'}]}
 assert build_native_content_lock(p,unknown)['content_lock_sha256']!=build_native_content_lock(p,{'unrecognized_plan':[{'title':'two'}]})['content_lock_sha256']

def test_old_lock_survives_unrelated_edit_from_verified_snapshot(tmp_path):
 import build.native_content as content
 from native_pptx.contracts import sha256_json
 root=new_run(tmp_path,'direct_svg');p=json.loads((root/'page_packages/P001.json').read_text())
 n={'run_id':root.name,'pages':[{'page_id':'P001','title':'one'},{'page_id':'P002','title':'two'}]}
 old=build_native_content_lock(p,n);old['lineage'].pop('narrative_page_projection_sha256',None);old['lineage'].pop('narrative_projection_version',None);old['lineage']['narrative_sha256']=sha256_json(n);old['source_fingerprint']=sha256_json({'package':p,'narrative':n});old['content_lock_sha256']=sha256_json({k:v for k,v in old.items() if k not in {'created_at','content_lock_sha256'}})
 lock=root/'high_density_build/content_locks/P001.content_lock.json';lock.parent.mkdir(parents=True);lock.write_text(json.dumps(old));(root/'narrative_plan.json').write_text(json.dumps(n))
 # A real revision preserves the original Narrative, then a later revision replaces it.
 env={'schema_version':'deck_stage_action.v1','action_id':'baseline','task_id':'baseline','scope_pages':['P001'],'permission':'runtime','input_fingerprint':'base'}
 stage_action_result(root,env,{'narrative':json.dumps(n)});commit_action_result(root,env,current_input_fingerprint='base',targets={'narrative':root/'narrative_plan.json'})
 changed=copy.deepcopy(n);changed['pages'][1]['title']='changed';env={**env,'action_id':'edit','input_fingerprint':'edit'}
 stage_action_result(root,env,{'narrative':json.dumps(changed)});commit_action_result(root,env,current_input_fingerprint='edit',targets={'narrative':root/'narrative_plan.json'})
 before=lock.read_bytes();revision=read_current_revision(root)['revision_id'];ensure_native_content(root,[p])
 assert lock.read_bytes()==before
 assert read_current_revision(root)['revision_id']==revision


def test_old_lock_without_narrative_is_not_reissued(tmp_path):
 from native_pptx.contracts import sha256_json
 root=new_run(tmp_path,'direct_svg');p=json.loads((root/'page_packages/P001.json').read_text());old=build_native_content_lock(p)
 old['source_fingerprint']=sha256_json({'package':p,'narrative':None});old['content_lock_sha256']=sha256_json({k:v for k,v in old.items() if k not in {'created_at','content_lock_sha256'}})
 path=root/'high_density_build/content_locks/P001.content_lock.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(old));before=path.read_bytes();ensure_native_content(root,[p]);assert path.read_bytes()==before
