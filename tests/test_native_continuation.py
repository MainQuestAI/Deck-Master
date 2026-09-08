from test_sc1_1_native_host_chain import new_run
from runtime.build import run_build
from runtime.next_step import resolve_next_step
from runtime.run_state_resolver import _resolve_stage


def test_native_next_step_uses_issued_task_without_old_hd_workflow(tmp_path):
    root = new_run(tmp_path, 'direct_svg')
    first = run_build(root)
    result = resolve_next_step(root)
    assert result['runtime_stage'] == 'awaiting_agent_execution'
    assert result['host_task']['pages'][0]['action_id'] == first['pages'][0]['action_id']
    assert _resolve_stage(root, 'production')[0] == result['runtime_stage']
    assert resolve_next_step(root) == result


def test_native_old_manifest_without_revision_is_not_complete(tmp_path):
    from runtime.run_state import write_json
    from runtime.build import build_status
    root=new_run(tmp_path,'direct_svg')
    run_build(root)
    write_json(root/'build/build_manifest.json',{'pages':[]})
    write_json(root/'render_results/render_result.json',{'status':'completed','artifact_path':'old.pptx'})
    assert build_status(root)['status']=='stale'


def test_native_quality_path_is_resolved_against_run(tmp_path,monkeypatch):
    from build.native_state import native_continuation
    import runtime.build, quality.gate_policy
    root=new_run(tmp_path,'direct_svg');run_build(root)
    artifact=root/'build/result.pptx';artifact.write_bytes(b'not a pptx; mocked policy boundary')
    monkeypatch.setattr(runtime.build,'build_status',lambda root:{'status':'completed','artifact_path':'build/result.pptx','page_count':1})
    seen=[]
    def policy(root,path,**kwargs):
        seen.append(path)
        return {'required_gate_satisfied':True,'current_blockers':[]}
    monkeypatch.setattr(quality.gate_policy,'resolve_required_gates',policy)
    result=native_continuation(root)
    assert seen==[artifact.resolve()]
    assert str(artifact.resolve()) in result['next_command']

def test_native_semantic_review_prepares_v2_from_packages_without_hd_brief(tmp_path):
    from deck_master import build_parser, command_prepare_quality_review
    root=new_run(tmp_path,'direct_svg');run_build(root)
    assert not (root/'deck_brief.json').exists()
    args=build_parser().parse_args(['prepare-quality-review','--run-dir',str(root)])
    result=command_prepare_quality_review(args)
    task=result['tasks'][0]
    assert task['schema_version']=='deck_external_quality_review_task.v2'
    assert task['required_page_ids']==['P001']
    assert task['based_on']['input_fingerprint']
    assert len(task['review_dimensions'])==6
