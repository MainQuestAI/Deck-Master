from pathlib import Path
import hashlib,json,sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from context_intake.research_runtime import prepare_research, dispatch_research, submit_research, research_status

def setup(tmp_path,limit=2):
 root=tmp_path/'run';root.mkdir();(root/'request.json').write_text('{"run_id":"run","run_mode":"production"}')
 query='public inventory availability reservation documentation'
 auth=dict(scope='public_research',public_query_context=query,allowed_sources=['learn.microsoft.com'],authorization_basis='User explicitly authorized public technical research for this test')
 (root/'authorization.json').write_text(json.dumps(auth)); refs=[dict(ref='request.json',sha256=hashlib.sha256((root/'request.json').read_bytes()).hexdigest())]
 from workflow.actions import fingerprint_payload
 task=dict(schema_version='deck_research_task.v1',run_id='run',run_mode='production',based_on=dict(input_refs=refs,input_fingerprint=fingerprint_payload(refs)),task_id='r1',stage_id='deck-brief',status='prepared',questions=[dict(question_id='q1',question='Private project question',decision_purpose='Choose reservation semantics',affected_refs=['solution.inventory'],preferred_source_types=['official documentation'],freshness_requirement='current',counter_check='Does it guarantee customer results?',stop_when='public design guidance found')],public_query_context=query,authorization_ref='authorization.json',allowed_sources=['learn.microsoft.com'],limits=dict(max_rounds_per_question=limit,max_candidate_sources_per_round=2,max_tool_actions=limit),expected_output_schema='deck_context_pack.v2')
 prepare_research(root,task);return root,task

def outcome(task,action,status='executed'):
 return dict(task_id=task['task_id'],action_id=action['action_id'],status=status,query_log=[dict(tool='web.run',query=task['public_query_context'],observation='Read official documentation')],sources=[dict(url='https://learn.microsoft.com/a',title='Official reference',excerpt='Inventory reservations are configurable.',applicability_bounds=['General product design; not evidence about this customer'])] if status=='executed' else [],result_summary='Design candidate only',counter_evidence=['No verified customer integration facts'],open_questions=['Customer API remains unverified'])

def test_restart_reuses_pending_action_and_exact_result_is_idempotent(tmp_path):
 root,task=setup(tmp_path);a=dispatch_research(root,'r1')
 assert dispatch_research(root,'r1')['action_id']==a['action_id']
 result=outcome(task,a);submit_research(root,result);submit_research(root,result)
 state=research_status(root,'r1');assert state['status']=='executed';assert state['actions_used']==1
 context=json.loads((root/'context_manifest.json').read_text());assert len(context['research_meta'])==1
 assert context['sources'][0]['provenance']['fact_kind']=='externally_verified_candidate'
 assert context['sources'][0]['reading']['coverage']=='partial'
 assert context['research_meta'][0]['affects']==['solution.inventory']
 with pytest.raises(ValueError):submit_research(root,{**result,'result_summary':'changed'})

def test_failure_and_budget_exhaustion_are_finite(tmp_path):
 root,task=setup(tmp_path)
 for expected in ['pending','inconclusive']:
  a=dispatch_research(root,'r1');r=submit_research(root,outcome(task,a,'retryable_error'));assert r['status']==expected
 assert dispatch_research(root,'r1')['status']=='inconclusive'
 assert research_status(root,'r1')['actions_used']==2

@pytest.mark.parametrize('status',['inconclusive','capability_unavailable'])
def test_terminal_results_do_not_claim_execution(tmp_path,status):
 root,task=setup(tmp_path);a=dispatch_research(root,'r1');submit_research(root,outcome(task,a,status))
 assert research_status(root,'r1')['status']==status
 assert json.loads((root/'context_manifest.json').read_text())['sources']==[]

def test_unauthorized_query_source_and_fabricated_action_rejected(tmp_path):
 root,task=setup(tmp_path);a=dispatch_research(root,'r1');r=outcome(task,a)
 with pytest.raises(ValueError):submit_research(root,{**r,'action_id':'unissued'})
 r['query_log'][0]['query']='private internal secret'
 with pytest.raises(ValueError):submit_research(root,r)
 r=outcome(task,a);r['sources'][0]['url']='https://evil.test/source'
 with pytest.raises(ValueError):submit_research(root,r)
 assert research_status(root,'r1')['status']=='pending'

def test_public_projection_is_the_only_dispatched_content(tmp_path):
 root,task=setup(tmp_path)
 dispatched=dispatch_research(root,'r1')
 assert task['questions'][0]['question'] not in json.dumps(dispatched)
 changed={**task,'task_id':'r2','public_query_context':'Private project internal endpoint'}
 with pytest.raises(ValueError,match='authorized public projection'):
  prepare_research(root,changed)

def test_budget_increase_requires_separate_explicit_authorization(tmp_path):
 root,task=setup(tmp_path)
 changed={**task,'task_id':'r2','limits':{**task['limits'],'max_tool_actions':99}}
 with pytest.raises(ValueError,match='explicit matching authorization'):
  prepare_research(root,changed)

def test_next_step_discovers_durable_research_and_is_read_only(tmp_path):
 from runtime.next_step import resolve_next_step
 from workflow.actions import read_current_revision
 root,task=setup(tmp_path)
 before=read_current_revision(root)
 result=resolve_next_step(root)
 assert result['runtime_stage']=='awaiting_agent_execution'
 assert 'research dispatch' in result['next_command']
 assert result['host_task']['research_status']['affected_refs']==['solution.inventory']
 assert read_current_revision(root)==before
 a=dispatch_research(root,'r1')
 assert resolve_next_step(root)['host_task']['research_status']['pending_action']['action_id']==a['action_id']
 submit_research(root,outcome(task,a,'inconclusive'))
 from context_intake.research_runtime import research_continuation
 assert research_continuation(root)['stage']=='blocked_research_gap'
 assert research_status(root,'r1')['status']=='inconclusive'

def test_authorization_below_defaults_is_still_a_hard_ceiling(tmp_path):
 root,task=setup(tmp_path)
 auth=json.loads((root/'authorization.json').read_text())
 auth['limits']={'max_tool_actions':1,'max_rounds_per_question':1,'max_candidate_sources_per_round':2}
 # Create a separate authorized input run, not a mutation of a pinned snapshot.
 other=tmp_path/'limited';other.mkdir()
 (other/'request.json').write_text((root/'request.json').read_text())
 (other/'authorization.json').write_text(json.dumps(auth))
 with pytest.raises(ValueError,match='budget exceeds'):
  prepare_research(other,task)
 assert not (other/'research/tasks/r1.json').exists()
