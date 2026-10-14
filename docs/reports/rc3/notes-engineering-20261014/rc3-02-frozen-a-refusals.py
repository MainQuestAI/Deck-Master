import hashlib,json,subprocess
from pathlib import Path
from deck_master.store import Store

root=Path('/tmp/pytest-of-agent/pytest-104/test_actual_completed_visual_n0/project')
store=Store(root); document=store.load_document()
assert document['compatibility']['minimum_writer']=='rc3.v1'
assert document['outputs']['pptx'] is not None
python=Path('/workspace/work/rc3/baseline-a/venv/bin/python')
scratch=Path('/workspace/work/rc3/notes-old-writer-probe'); scratch.mkdir(exist_ok=True)
page=store.read_object_json(document['pages'][0]['page'])
page_file=scratch/'page.json'; page_file.write_text(json.dumps(page,ensure_ascii=False))
result_file=scratch/'review.json'; result_file.write_text(json.dumps({'kind':'review','reviews':[]}))
def hashes():
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before=hashes()
base=document['revision_id']; page_sha=document['pages'][0]['page']['sha256']
historical=document
while historical.get('parent_revision_id') and historical.get('compatibility',{}).get('minimum_writer')=='rc3.v1':
 historical=store.load_document(historical['parent_revision_id'])
assert historical.get('compatibility',{}).get('minimum_writer')!='rc3.v1'
commands={
 'continue_compile':['continue','--project',str(root),'--json'],
 'assemble':['stages','assemble','--project',str(root),'--base-revision',base,'--operation-id','old-assemble','--json'],
 'claim':['task','start','--project',str(root),'--task-id','old-task','--execution-ref','old-host','--json'],
 'accept':['task','accept','--project',str(root),'--task-id','old-task','--operation-id','old-accept','--produced-against','a'*64,'--result',str(result_file),'--json'],
 'edit':['edit','--project',str(root),'--page',str(page_file),'--base-revision',base,'--page-hash',page_sha,'--operation-id','old-edit'],
 'restore':['history','restore','--project',str(root),'--revision',historical['revision_id'],'--base-revision',base,'--operation-id','old-restore'],
 'historical_delivery':['export','--project',str(root),'--revision',historical['revision_id'],'--out',str(scratch/'old-delivery'),'--purpose','delivery']}
out={}
for key,args in commands.items():
 response=subprocess.run([str(python),'-I','-m','deck_master',*args],capture_output=True,text=True)
 assert response.returncode!=0, (key,response.stdout)
 out[key]={'command_args':args,'returncode':response.returncode,'stdout':response.stdout,'stderr':response.stderr}
after=hashes(); assert before==after
report={'status':'PASS','scope':'Actual frozen A CLI refusals on current protected notes/PPTX project; synthetic content/authority, no human/desktop claim',
 'old_installation_manifest_sha256':hashlib.sha256(Path('/workspace/work/rc3/baseline-a/manifest.json').read_bytes()).hexdigest(),
 'old_python':str(python),'protected_revision':base,'protected_floor':'rc3.v1','current_pptx_ref':document['outputs']['pptx'],
 'historical_selected_revision':historical['revision_id'],'historical_selected_floor':historical.get('compatibility',{}).get('minimum_writer'),
 'current_pointer_sha256':before['.deckmaster/current.json'],'project_file_count':len(before),'project_hashes_unchanged':before==after,
 'cli_outcomes':out,'desktop':'NOT_RUN','human':'NOT_RUN'}
Path('/workspace/work/rc3/reviews/rc3-02-frozen-a-refusals.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','cli_refusals':len(out),'project_files_unchanged':len(before)}))
