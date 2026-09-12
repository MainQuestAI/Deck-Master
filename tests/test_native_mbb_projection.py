import copy,json,sys
from pathlib import Path
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from test_sc1_1_native_host_chain import new_run
from build.build_route import persist_route,resolve_build_route
from high_density.content import load_mbb_plan,write_mbb_plan,select_mbb_storyline,seal_mbb_plan,record_mbb_user_decision
from build.native_content import ensure_native_content
from native_pptx.contracts import ContractError,assert_v2
from workflow.actions import stage_action_result,commit_action_result,read_current_revision

def setup(tmp):
 r=new_run(tmp,'direct_svg');req=json.loads((r/'request.json').read_text());persist_route(r,resolve_build_route(req,run_dir=r))
 p=json.loads((r/'page_packages/P001.json').read_text());n={'run_id':r.name,'candidates':[{'candidate_id':'chosen','title':'Selected synthetic storyline'}],'selected_candidate_id':'chosen','selection_decision_ref':'workflow/decision_log.jsonl#synthetic-decision','beats':[{'beat_id':'P001','page_title':'one'}]}
 change(r,n,'initial');return r,p,n

def change(r,n,label):
 env={'schema_version':'deck_stage_action.v1','action_id':label,'task_id':label,'scope_pages':['P001'],'permission':'runtime','input_fingerprint':label}
 stage_action_result(r,env,{'narrative':json.dumps(n)});commit_action_result(r,env,current_input_fingerprint=label,targets={'narrative':r/'narrative_plan.json'})

def test_native_mbb_is_versioned_projection_not_new_selection(tmp_path):
 r,p,n=setup(tmp_path);view=load_mbb_plan(r,packages=[p]);assert view['schema_version']=='deck_mbb_projection.v1';assert_v2('mbb_projection',view)
 assert view['selected_candidate_id']=='chosen';assert view['selection_decision_ref']==n['selection_decision_ref'];assert view['source_revision']==read_current_revision(r)['revision_id']
 assert not (r/'high_density_build/mbb/selection_receipt.json').exists()

def test_null_narrative_choice_stays_null(tmp_path):
 r,p,n=setup(tmp_path);n.update(selected_candidate_id=None,selection_decision_ref='');change(r,n,'null-choice');v=load_mbb_plan(r,packages=[p]);assert v['selected_candidate_id'] is None

def test_prepare_refreshes_requested_projection_and_ignores_tampering(tmp_path):
 from build.narrative_mbb import PROJECTION_PATH
 r,p,n=setup(tmp_path);first=load_mbb_plan(r,packages=[p]);path=r/PROJECTION_PATH
 corrupt=copy.deepcopy(first);corrupt['selected_candidate_id']='tampered';path.write_text(json.dumps(corrupt))
 assert load_mbb_plan(r,packages=[p])['selected_candidate_id']=='chosen'
 n['beats'][0]['page_title']='two';change(r,n,'revision-two')
 from runtime.build import prepare_build
 prepare_build(r);second=json.loads(path.read_text())
 assert second['source_narrative_sha256']!=first['source_narrative_sha256'];assert second['projection_sha256']!=first['projection_sha256'];assert second['source_revision']==read_current_revision(r)['revision_id']
 assert second['selected_candidate_id']=='chosen'

@pytest.mark.parametrize('entry',[lambda r:write_mbb_plan(r,{}),lambda r:select_mbb_storyline(r,'other'),lambda r:seal_mbb_plan(r),lambda r:record_mbb_user_decision(r,'other',attestor_id='user')])
def test_legacy_writes_cannot_change_native_authority(tmp_path,entry):
 r,p,n=setup(tmp_path);before=(r/'narrative_plan.json').read_bytes()
 with pytest.raises(ContractError,match='public Narrative'):entry(r)
 assert (r/'narrative_plan.json').read_bytes()==before

def test_projection_cache_cannot_escape_run(tmp_path):
 from build.narrative_mbb import PROJECTION_PATH
 r,p,n=setup(tmp_path);outside=tmp_path/'outside.json';outside.write_text('untouched');target=r/PROJECTION_PATH;target.parent.mkdir(parents=True);target.symlink_to(outside)
 with pytest.raises(ContractError,match='escapes'):load_mbb_plan(r,packages=[p])
 assert outside.read_text()=='untouched'
