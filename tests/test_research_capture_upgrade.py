import hashlib
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from context_intake.reading import verify_source_bytes

def sample(tmp_path):
    old={'source_id':'r','kind':'research','media_type':'web','sha256':hashlib.sha256(b'excerpt').hexdigest(),'excerpt':'excerpt','reading':{'coverage':'partial'},'provenance':{'task_id':'t','url':'https://example.com/source'}}
    f=tmp_path/'capture.txt';f.write_text('Full observed source including terminal conditions\n')
    new={'source_id':'r','origin_ref':old['provenance']['url'],'file_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'capture_supersedes_sha256':old['sha256'],'extraction':{'snapshot_ref':str(f),'status':'complete','read_units':1,'total_units':1,'unread_regions':[],'tool_ref':'actual-host-observation','method':'web.open'}}
    return old,new,f

def test_research_capture_upgrade(tmp_path):
    old,new,_=sample(tmp_path);verify_source_bytes(new,old)

@pytest.mark.parametrize('case',['local','url','oldsha','bytes','excerpt','partial'])
def test_research_capture_upgrade_rejects_invalid(tmp_path,case):
    old,new,f=sample(tmp_path)
    if case=='local':old['kind']='text'
    if case=='url':new['origin_ref']='https://example.com/other'
    if case=='oldsha':new['capture_supersedes_sha256']='0'*64
    if case=='bytes':f.write_text('tampered')
    if case=='excerpt':f.write_text(old['excerpt']);new['file_sha256']=old['sha256']
    if case=='partial':new['extraction']['status']='partial'
    with pytest.raises(ValueError):verify_source_bytes(new,old)

def test_formal_cli_capture_preserves_history_and_replay(tmp_path):
    import json,subprocess
    from runtime.run_state import create_run
    from context_intake.context_pack import validate_context_pack
    old,new,f=sample(tmp_path)
    root=create_run(tmp_path,{'run_mode':'production'},run_id='capture-cli')
    (root/'context_manifest.json').write_text(json.dumps({'sources':[old]}))
    new.update(title='Synthetic observed page',source_type='web',origin_type='authorized_web',summary='Navigation only',evidence_candidates=[],sensitivity='normal',publication_status='safe_to_use')
    refs=[{'ref':new['origin_ref'],'sha256':new['file_sha256']}]
    pack={'schema_version':'deck_context_pack.v2','run_id':root.name,'run_mode':'production','based_on':{'input_refs':refs,'input_fingerprint':hashlib.sha256(json.dumps(refs,sort_keys=True).encode()).hexdigest()},'sources':[new],'global_constraints':[],'conflicts':[],'research_meta':{'task_id':'t','status':'executed','execution_refs':['synthetic-capture-test'],'summary':'Synthetic capture recovery, not customer approval','open_questions':[]}}
    assert validate_context_pack(pack)['valid']
    inp=tmp_path/'pack.json';inp.write_text(json.dumps(pack));cli=Path(__file__).resolve().parents[1]/'scripts/deck_master.py'
    cmd=[sys.executable,str(cli),'import-context-pack','--run-dir',str(root),'--input',str(inp),'--merge','--dev-allow-unsetup']
    p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stderr
    source=json.loads((root/'context_manifest.json').read_text())['sources'][0]
    assert source['reading']['coverage']=='full'
    assert source['sha256']==new['file_sha256']
    assert source['research_excerpt_capture']['sha256']==old['sha256']
    assert source['provenance']==old['provenance']
    pointer=(root/'build/current_revision.json').read_bytes()
    replay=subprocess.run(cmd,capture_output=True,text=True);assert replay.returncode==0,replay.stderr
    assert json.loads(replay.stdout)['status']=='idempotent'
    assert (root/'build/current_revision.json').read_bytes()==pointer
    pack['sources'][0]['capture_supersedes_sha256']='invalid'
    assert not validate_context_pack(pack)['valid']
