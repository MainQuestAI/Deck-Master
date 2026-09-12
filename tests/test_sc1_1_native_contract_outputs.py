from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build.native_contracts import write_task_readiness, validate_contract


def probe():
    return {'checked_at':'2026-09-09T00:00:00Z','checks':{k:{'status':'verified'} for k in ['compile_smoke','render_smoke','fonts','rsvg_convert']}}


def test_unknown_host_is_unknown_not_missing(tmp_path):
    result=write_task_readiness(tmp_path,probe(),task_kind='image_blueprint_build')
    assert result['status']=='unknown'
    assert result['required_missing']==[]
    assert 'host.image_generation' in result['required_unknown']
    validate_contract('task_readiness',result)


def test_compile_ready_has_real_hash_bound_probe_file(tmp_path):
    result=write_task_readiness(tmp_path,probe(),task_kind='compile_approved_svg')
    assert result['status']=='ready'
    assert all(c['evidence_refs'] for c in result['components'] if c['requirement']=='required')
    assert (tmp_path/'build/task_readiness.json').is_file()
    result['components'][0]['evidence_refs']=[]
    with pytest.raises(Exception):validate_contract('task_readiness',result)


def test_missing_renderer_blocks_build_even_compiler_imports(tmp_path):
    p=probe();p['checks']['render_smoke']={'status':'unverified','error':'missing soffice'}
    result=write_task_readiness(tmp_path,p,task_kind='direct_svg_build')
    assert result['status']=='blocked'
    assert 'deck_native.renderer' in result['required_missing']


def test_actual_native_compile_emits_bound_request_and_readiness(tmp_path):
    """Real production kernel/render from approved content and host SVG+Scene."""
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from test_sc1_1_native_host_chain import new_run, host_scene
    from build.native_engine import submit_approved_svg
    from high_density.content import load_content_lock
    from high_density.svg import compile_svg
    from runtime.build import run_build
    from native_pptx.contracts import sha256_file
    root=new_run(tmp_path,'direct_svg')
    task=run_build(root)['pages'][0]
    scene=host_scene(root,load_content_lock(root,'P001'))
    svg=compile_svg(scene,tmp_path/'host.svg').read_text()
    submit_approved_svg(root,'P001',svg,action_id=task['action_id'],produced_against=task['produced_against'],scene=scene)
    assert run_build(root)['status']=='completed'
    request=json.loads((root/'build/native_compile_request.json').read_text())
    validate_contract('native_compile_request',request)
    assert [p['order'] for p in request['pages']]==[1]
    for page in request['pages']:
        for name in ['svg_ref','scene_ref','content_lock_ref','asset_manifest_ref','approval_ref']:
            ref=page[name]
            assert sha256_file(root/ref['path'])==ref['sha256']
    readiness=json.loads((root/'build/task_readiness.json').read_text())
    validate_contract('task_readiness',readiness)
    assert readiness['task_kind']=='compile_approved_svg'
    request['pages'][0]['svg_ref']['sha256']='wrong'
    with pytest.raises(Exception):validate_contract('native_compile_request',request)


def test_legacy_mapping_is_not_labelled_native_contain(tmp_path):
    from build.native_contracts import write_compile_request
    with pytest.raises(Exception,match='legacy HD'):
        write_compile_request(tmp_path,revision='initial',fingerprint='0'*64,packages=[],scenes=[],locks={},svg_paths={},assets={},native_canvas=False)
