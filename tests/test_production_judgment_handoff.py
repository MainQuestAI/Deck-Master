import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from narrative.judgment_builder import build_judgments

def test_goal_and_unreviewed_sources_do_not_become_problem_or_mechanism():
 r=build_judgments({'run_id':'x','run_mode':'production','business_goal':'提高交付可靠性'},{'core_points':['目标一','目标二']},{'claims':[{'claim':'目标一'},{'claim':'目标二'}]},{'sources':[{'source_id':'s'}]})
 assert r['status']=='needs_agent_analysis'
 for j in r['judgments'][:2]:
  assert j['status']=='needs_agent_analysis' and j['confidence']==0
  assert '提高交付可靠性' not in j['statement']
  assert j['risk_flags']==['professional_analysis_pending']
 assert len(r['agent_tasks'])==2

def test_actual_public_content_is_reused_as_unscored_proposal_not_fact():
 n={'run_id':'x','beats':[{'beat_id':'p','role':'problem','conclusion':'适配关系缺少可核实证据','business_implication':'先由工程确认设备序列与替代件','fact_kind':'analysis_judgment','source_refs':['s'],'evidence_bindings':['s::quote']},{'beat_id':'m','role':'architecture','conclusion':'建议只读工单→核验适配→人工会签','business_implication':'不自动改变客户承诺','fact_kind':'design_suggestion','source_refs':['s'],'evidence_bindings':[]}]}
 r=build_judgments({'run_id':'x','run_mode':'production'},{},{},{'sources':[{'source_id':'s'}]},narrative_plan=n)
 assert r['status']=='proposed_from_narrative'
 for j in r['judgments'][:2]:
  assert j['confidence']==0 and j['status']=='proposed_from_narrative'
  assert j['source_refs'][0].startswith('narrative_plan.json#')
  assert j['risk_flags'] and j['public_inputs'][0]['fact_kind'] in ['analysis_judgment','design_suggestion']
 assert r['judgments'][0]['statement']==n['beats'][0]['conclusion']
 n['beats'][1].pop('business_implication')
 assert build_judgments({'run_id':'x','run_mode':'production'},{},{},{'sources':[{'source_id':'s'}]},narrative_plan=n)['status']=='needs_agent_analysis'

def test_real_cli_goal_only_reports_handoff(tmp_path):
 r=tmp_path/'goal-only';r.mkdir()
 for name,p in {'request.json':{'run_id':r.name,'run_mode':'production','business_goal':'提高交付可靠性'},'deck_brief.json':{'core_points':['提高交付可靠性']},'claim_map.json':{'claims':[]}}.items():(r/name).write_text(json.dumps(p))
 c=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/deck_master.py'),'build-judgments','--run-dir',str(r),'--dev-allow-unsetup'],capture_output=True,text=True)
 assert c.returncode==0,c.stderr
 assert json.loads(c.stdout)['status']=='needs_agent_analysis'
 assert json.loads((r/'consulting_judgments.json').read_text())['agent_tasks']

def test_fixture_keeps_legacy_demonstration_behavior():
 r=build_judgments({'run_id':'x','run_mode':'fixture','business_goal':'fixture goal'},{},{},{})
 assert r['status']=='judgments_ready'
 assert r['judgments'][0]['statement']=='客户核心问题是fixture goal。'

def test_template_roles_and_foreign_sources_cannot_satisfy_professional_handoff():
 n={'run_id':'x','beats':[{'beat_id':'p','role':'problem','core_claim':'提高交付可靠性'},{'beat_id':'a','role':'architecture','conclusion':'建议接口链','business_implication':'业务影响','fact_kind':'design_suggestion','source_refs':['absent']}]}
 r=build_judgments({'run_id':'x','run_mode':'production'},{},{},{'sources':[{'source_id':'s'}]},narrative_plan=n)
 assert r['status']=='needs_agent_analysis' and len(r['agent_tasks'])==2
