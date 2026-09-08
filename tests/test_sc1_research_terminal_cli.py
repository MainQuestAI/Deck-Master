"""Real public continuation must retain exhausted research without replay."""
import json
import subprocess
import sys
from pathlib import Path
import pytest
from tests.test_sc1_research_runtime import setup, outcome
from context_intake.research_runtime import dispatch_research, submit_research, research_status
from workflow.actions import read_current_revision

CLI=Path(__file__).resolve().parents[1]/'scripts/deck_master.py'
def command(root,*args):
 p=subprocess.run([sys.executable,str(CLI),*args,'--run-dir',str(root)],capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 return json.loads(p.stdout)

@pytest.mark.parametrize('status',['inconclusive','capability_unavailable'])
def test_terminal_research_gap_survives_real_next_step_without_mutation(tmp_path,status):
 root,task=setup(tmp_path);a=dispatch_research(root,'r1');result=outcome(task,a,status)
 result['open_questions']=['Customer interface applicability remains unknown']
 submit_research(root,result);before=read_current_revision(root)
 for _ in range(2):
  n=command(root,'next-step')
  assert n['runtime_stage']=='blocked_research_gap'
  assert n['next_command']==''
  r=n['host_task']['research_status']
  assert r['status']==status and r['affected_refs']==['solution.inventory']
  assert r['open_questions']==result['open_questions']
  assert r['questions']==task['questions']
  assert n['blocking_issues']
 auto=command(root,'workflow-autopilot','--dev-allow-unsetup','--mode','review-only','--max-steps','1')
 assert auto['final_stage']=='blocked_research_gap'
 assert auto['host_task']['research_status']['status']==status
 assert auto['host_task']['research_status']['affected_refs']==['solution.inventory']
 assert auto['blocking_issues'] and auto['next_command']==''
 assert auto['steps']==[]
 assert read_current_revision(root)==before
 assert research_status(root,'r1')['actions_used']==1

def test_executed_research_falls_through_without_repeating_tool_action(tmp_path):
 root,task=setup(tmp_path);a=dispatch_research(root,'r1');submit_research(root,outcome(task,a))
 before=read_current_revision(root)
 n=command(root,'next-step')
 assert n['runtime_stage']!='blocked_research_gap'
 assert 'research dispatch' not in n['next_command']
 assert read_current_revision(root)==before
 assert research_status(root,'r1')['actions_used']==1

def test_pending_cli_resume_reuses_action_without_consuming_budget(tmp_path):
 root,task=setup(tmp_path)
 a=command(root,'research','dispatch','--task-id','r1')
 before=read_current_revision(root)
 n=command(root,'next-step')
 assert n['runtime_stage']=='awaiting_agent_execution'
 assert n['host_task']['research_status']['pending_action']['action_id']==a['action_id']
 b=command(root,'research','dispatch','--task-id','r1')
 assert b['action_id']==a['action_id'] and b['resumed']
 assert read_current_revision(root)==before
 assert research_status(root,'r1')['actions_used']==1
