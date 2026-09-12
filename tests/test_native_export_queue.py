import hashlib,json,sys
from pathlib import Path
from contextlib import nullcontext
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import orchestrate.export_queue as eq

def setup_native(tmp_path,monkeypatch):
 import build.build_route as routes
 import build.native_engine as engine
 import workflow.actions as actions
 monkeypatch.setattr(routes,'load_persisted_route',lambda r:{'engine_id':'deck_native'})
 monkeypatch.setattr(actions,'revision_read',lambda r:nullcontext('rev1'))
 monkeypatch.setattr(engine,'_approved_packages',lambda r:[{'page_id':'p1','order':1,'customer_visible':{'title':'Native page'},'status':'ready_for_build'}])
 (tmp_path/'request.json').write_text(json.dumps({'run_id':tmp_path.name,'run_mode':'production'}))
 artifact=tmp_path/'build/out/deck.pptx';artifact.parent.mkdir(parents=True);artifact.write_bytes(b'actual-artifact')
 preview=artifact.parent/'p1.png';preview.write_bytes(b'actual-preview')
 digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 (artifact.parent/'native_readback.json').write_text(json.dumps({'status':'pass','pptx_sha256':digest(artifact),'pages':[{'page_id':'p1'}]}))
 rr={'build_revision':'rev1','artifact_path':'build/out/deck.pptx','page_count':1,'page_previews':[{'page_id':'p1','preview_path':'build/out/p1.png'}],'artifacts':[{'kind':'deck_pptx','path':'build/out/deck.pptx','sha256':digest(artifact)},{'kind':'page_png','page_id':'p1','path':'build/out/p1.png','sha256':digest(preview)}]}
 (tmp_path/'render_results').mkdir();(tmp_path/'render_results/render_result.json').write_text(json.dumps(rr))
 monkeypatch.setattr(eq,'final_readiness_clearance',lambda r:{'ready':True,'readiness':{'final_artifact':{'path':'build/out/deck.pptx','hash':digest(artifact)}}})
 monkeypatch.setattr(eq,'resolve_required_gates',lambda *args,**kwargs:{'required_gate_satisfied':True})
 monkeypatch.setattr(eq,'_get_blocking_findings',lambda r,p:[])
 return artifact,rr

def approval_for(root):
 return {'ready':True,'approval':{'final_artifact':{'path':'build/out/deck.pptx','sha256':hashlib.sha256((root/'build/out/deck.pptx').read_bytes()).hexdigest()}}}

def test_native_no_preview_manifest_requires_final_approval(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 q=eq.export_queue(tmp_path,{'approved'})
 assert q['pages']==[] and q['blocked_count']==1
 assert 'approval' in q['blocked_pages'][0]['quality_block_reason'].lower()
 assert not (tmp_path/'preview_manifest.json').exists()

def test_native_approved_fixture_maps_actual_page_artifact(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',approval_for)
 q=eq.export_queue(tmp_path,{'approved'})
 assert q['blocked_count']==0 and len(q['pages'])==1
 assert q['pages'][0]['source_pptx']=='build/out/deck.pptx'
 assert q['pages'][0]['source_slide_index']==1
 assert q['source_manifest'].endswith('page_packages/index.json')

@pytest.mark.parametrize('damage',['revision','page_order','artifact','preview'])
def test_native_export_rejects_stale_artifact_mapping(tmp_path,monkeypatch,damage):
 artifact,rr=setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',approval_for)
 if damage=='revision':rr['build_revision']='old'
 if damage=='page_order':(artifact.parent/'native_readback.json').write_text(json.dumps({'status':'pass','pptx_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'pages':[{'page_id':'other'}]}))
 if damage=='artifact':artifact.write_bytes(b'changed')
 if damage=='preview':(artifact.parent/'p1.png').write_bytes(b'changed')
 (tmp_path/'render_results/render_result.json').write_text(json.dumps(rr))
 q=eq.export_queue(tmp_path,{'approved'})
 assert q['pages']==[] and q['blocked_count']==1

def test_native_final_gate_cannot_be_disabled(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 q=eq.export_queue(tmp_path,{'approved'},enforce_final_readiness=False)
 assert q['pages']==[] and q['blocked_count']==1

def test_native_quality_blocker_survives_file_approval(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',approval_for)
 monkeypatch.setattr(eq,'_get_blocking_findings',lambda r,p:[{'severity':'P0','finding_id':'bad-source','message':'wrong source'}])
 q=eq.export_queue(tmp_path,{'approved'},allow_quality_override=True)
 assert not q['pages'] and 'bad-source' in q['blocked_pages'][0]['quality_block_reason']

def test_native_stale_readiness_survives_file_approval(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',approval_for)
 monkeypatch.setattr(eq,'final_readiness_clearance',lambda r:{'ready':False,'reason':'stale inputs'})
 q=eq.export_queue(tmp_path,{'approved'})
 assert not q['pages'] and q['blocked_pages'][0]['quality_block_reason']=='stale inputs'


def write_test_approval(root, artifact):
 """Synthetic historical approval solely as a regression input, not user consent."""
 from runtime.final_approval import final_approval_clearance
 from runtime.final_readiness import final_readiness_clearance
 rel=artifact.relative_to(root).as_posix();sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
 (root/'delivery').mkdir(exist_ok=True)
 (root/'delivery/final_readiness.json').write_text(json.dumps({'ready':True,'status':'ready','final_artifact':{'path':rel,'hash':sha},'blockers':[]}))
 (root/'final_artifact_approval.json').write_text(json.dumps({'schema_version':'deck_final_artifact_approval.v1','run_id':root.name,'approval_id':'test','handoff_id':'test','decision':'approved','approver':{'id':'regression-test'},'approved_at':'2026-09-09T00:00:00Z','final_artifact':{'path':rel,'sha256':sha}}))
 folder=root/'workflow/approvals';folder.mkdir(parents=True,exist_ok=True)
 (folder/'test.json').write_text(json.dumps({'decision':'approved','handoff_id':'test','to_stage':'client_export'}))
 return final_approval_clearance,final_readiness_clearance


def test_native_selected_artifact_cannot_reuse_another_artifacts_approval(tmp_path,monkeypatch):
 artifact,rr=setup_native(tmp_path,monkeypatch)
 old=artifact.parent/'previous.pptx';old.write_bytes(b'previous-approved-artifact')
 approval,readiness=write_test_approval(tmp_path,old)
 monkeypatch.setattr(eq,'final_approval_clearance',approval)
 monkeypatch.setattr(eq,'final_readiness_clearance',readiness)
 assert approval(tmp_path)['ready']  # old approval is internally valid
 queue=eq.export_queue(tmp_path,{'approved'})
 assert not queue['pages']
 assert 'selected native artifact' in queue['blocked_pages'][0]['quality_block_reason']


def test_native_historical_ready_file_does_not_replace_current_required_gates(tmp_path,monkeypatch):
 artifact,rr=setup_native(tmp_path,monkeypatch)
 from quality.gate_policy import resolve_required_gates
 monkeypatch.setattr(eq,'resolve_required_gates',resolve_required_gates)
 approval,readiness=write_test_approval(tmp_path,artifact)
 monkeypatch.setattr(eq,'final_approval_clearance',approval)
 monkeypatch.setattr(eq,'final_readiness_clearance',readiness)
 assert approval(tmp_path)['ready']
 queue=eq.export_queue(tmp_path,{'approved'})
 assert not queue['pages']
 assert 'required quality gates' in queue['blocked_pages'][0]['quality_block_reason']
