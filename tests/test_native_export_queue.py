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
 artifact=tmp_path/'build/out/deck.pptx';artifact.parent.mkdir(parents=True);artifact.write_bytes(b'actual-artifact')
 preview=artifact.parent/'p1.png';preview.write_bytes(b'actual-preview')
 digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 (artifact.parent/'native_readback.json').write_text(json.dumps({'status':'pass','pptx_sha256':digest(artifact),'pages':[{'page_id':'p1'}]}))
 rr={'build_revision':'rev1','artifact_path':'build/out/deck.pptx','page_count':1,'page_previews':[{'page_id':'p1','preview_path':'build/out/p1.png'}],'artifacts':[{'kind':'deck_pptx','path':'build/out/deck.pptx','sha256':digest(artifact)},{'kind':'page_png','page_id':'p1','path':'build/out/p1.png','sha256':digest(preview)}]}
 (tmp_path/'render_results').mkdir();(tmp_path/'render_results/render_result.json').write_text(json.dumps(rr))
 monkeypatch.setattr(eq,'final_readiness_clearance',lambda r:{'ready':True})
 monkeypatch.setattr(eq,'_get_blocking_findings',lambda r,p:[])
 return artifact,rr

def test_native_no_preview_manifest_requires_final_approval(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 q=eq.export_queue(tmp_path,{'approved'})
 assert q['pages']==[] and q['blocked_count']==1
 assert 'approval' in q['blocked_pages'][0]['quality_block_reason'].lower()
 assert not (tmp_path/'preview_manifest.json').exists()

def test_native_approved_fixture_maps_actual_page_artifact(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',lambda r:{'ready':True})
 q=eq.export_queue(tmp_path,{'approved'})
 assert q['blocked_count']==0 and len(q['pages'])==1
 assert q['pages'][0]['source_pptx']=='build/out/deck.pptx'
 assert q['pages'][0]['source_slide_index']==1
 assert q['source_manifest'].endswith('page_packages/index.json')

@pytest.mark.parametrize('damage',['revision','page_order','artifact','preview'])
def test_native_export_rejects_stale_artifact_mapping(tmp_path,monkeypatch,damage):
 artifact,rr=setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',lambda r:{'ready':True})
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
 monkeypatch.setattr(eq,'final_approval_clearance',lambda r:{'ready':True})
 monkeypatch.setattr(eq,'_get_blocking_findings',lambda r,p:[{'severity':'P0','finding_id':'bad-source','message':'wrong source'}])
 q=eq.export_queue(tmp_path,{'approved'},allow_quality_override=True)
 assert not q['pages'] and 'bad-source' in q['blocked_pages'][0]['quality_block_reason']

def test_native_stale_readiness_survives_file_approval(tmp_path,monkeypatch):
 setup_native(tmp_path,monkeypatch)
 monkeypatch.setattr(eq,'final_approval_clearance',lambda r:{'ready':True})
 monkeypatch.setattr(eq,'final_readiness_clearance',lambda r:{'ready':False,'reason':'stale inputs'})
 q=eq.export_queue(tmp_path,{'approved'})
 assert not q['pages'] and q['blocked_pages'][0]['quality_block_reason']=='stale inputs'
