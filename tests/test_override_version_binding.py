"""Explicitly synthetic approval records; never authorize a real customer Run."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from quality.overrides import create_override, has_active_override
from quality.gate_policy import resolve_required_gates


def _artifact(root):
    f=root/'build/deck.pptx'; f.parent.mkdir(parents=True,exist_ok=True); f.write_bytes(b'synthetic A'); return f


def test_same_finding_cannot_reuse_artifact_a_override_for_b(tmp_path):
    artifact=_artifact(tmp_path)
    create_override(tmp_path,'f','P1','synthetic A only','synthetic reviewer')
    assert has_active_override(tmp_path,'f')
    artifact.write_bytes(b'synthetic B')
    report={'gate':'render','status':'failed','blocks_delivery':True,'artifact_path':'build/deck.pptx','artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'findings':[{'finding_id':'f','severity':'P1'}]}
    result=resolve_required_gates(tmp_path,artifact,run_mode='production',reports=[report])
    assert result['current_blockers'], 'A override must not suppress new B finding'
    assert not result['overridden_p1']


def test_draft_override_stales_on_source_change_and_final_artifact(tmp_path):
    d=tmp_path/'page_packages';d.mkdir();p=d/'P001.json';p.write_text('{"text":"A"}')
    create_override(tmp_path,'f','P1','synthetic source A','synthetic reviewer')
    assert has_active_override(tmp_path,'f')
    p.write_text('{"text":"B"}')
    assert not has_active_override(tmp_path,'f')
    p.write_text('{"text":"A"}');_artifact(tmp_path)
    assert not has_active_override(tmp_path,'f')


def test_old_unbound_override_cannot_authorize_native_artifact(tmp_path):
    _artifact(tmp_path);(tmp_path/'build/route.json').write_text('{"engine":"native"}')
    q=tmp_path/'quality_reports';q.mkdir();(q/'overrides.json').write_text(json.dumps([{'target_id':'f','severity':'P1','status':'active','scope':'client_export','reason':'synthetic legacy','approver':'test','expires_at':'2099-01-01T00:00:00+00:00'}]))
    assert not has_active_override(tmp_path,'f')


def test_scope_mismatch_cannot_authorize_client_export(tmp_path):
    _artifact(tmp_path)
    create_override(tmp_path,'f','P1','synthetic internal only','test',scope='internal_review')
    assert not has_active_override(tmp_path,'f')


import pytest

@pytest.mark.parametrize("relative", ["narrative_plan.json", "deck_brief.json", "context_manifest.json", "solution_model.json", "sources/raw.txt", "diagram_views/P001.json"])
def test_draft_override_binds_actual_public_inputs(tmp_path, relative):
    source = tmp_path / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('synthetic A')
    create_override(tmp_path, 'f', 'P1', 'synthetic input A only', 'test')
    assert has_active_override(tmp_path, 'f')
    source.write_text('synthetic B')
    assert not has_active_override(tmp_path, 'f')


def test_native_unbound_override_cannot_use_missing_route_projection(tmp_path):
    from build.build_route import persist_route, resolve_build_route, load_persisted_route
    from workflow.actions import create_action_envelope, stage_action_result, commit_action_result
    request = {'run_mode': 'production', 'profile': 'direct-svg'}
    (tmp_path / 'request.json').write_text(json.dumps(request))
    persist_route(tmp_path, resolve_build_route(request, run_dir=tmp_path))
    envelope = create_action_envelope(action_id='baseline', task_id='baseline', scope_pages=['P001'], permission='runtime', input_fingerprint='baseline')
    stage_action_result(tmp_path, envelope, {'narrative_plan.json': '{}'})
    commit_action_result(tmp_path, envelope, current_input_fingerprint='baseline', targets={'narrative_plan.json': tmp_path / 'narrative_plan.json'})
    quality = tmp_path / 'quality_reports'
    quality.mkdir(exist_ok=True)
    (quality / 'overrides.json').write_text(json.dumps([{'target_id': 'f', 'severity': 'P1', 'status': 'active', 'scope': 'client_export'}]))
    assert not has_active_override(tmp_path, 'f')
    (tmp_path / 'build/route.json').unlink()
    assert load_persisted_route(tmp_path)['engine_id'] == 'deck_native'
    assert not has_active_override(tmp_path, 'f')
