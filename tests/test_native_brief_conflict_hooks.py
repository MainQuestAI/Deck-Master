import json,sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
import pytest
from test_sc1_brief_declared_conflicts import inputs
from build.native_engine import prepare_native_run,run_native_compile,submit_approved_svg,NativeEngineError,_assert_brief_conflicts_resolved
from build.native_tasks import submit_blueprint,current_task_fingerprint
from runtime.next_step import resolve_next_step

def blocked_run(tmp_path):
    context,extract=inputs(tmp_path)
    (tmp_path/'context_manifest.json').write_text(json.dumps(context))
    (tmp_path/'deck_brief.json').write_text(json.dumps({'constraints':extract['constraints'],'source_conflicts':[]}))
    (tmp_path/'request.json').write_text(json.dumps({'run_id':tmp_path.name,'profile':'native','run_mode':'production'}))
    # Existing approved content cannot bypass the new upstream conflict.
    (tmp_path/'page_packages').mkdir()
    (tmp_path/'page_packages/P001.json').write_text('{"page_id":"P001","status":"ready_for_build"}')
    return tmp_path

@pytest.mark.parametrize('entry',['prepare','runtime_prepare','compile','svg','blueprint','commit_callback'])
def test_all_native_mutation_entries_block_declared_conflict(tmp_path,entry):
    root=blocked_run(tmp_path)
    with pytest.raises(NativeEngineError) as error:
        if entry=='prepare':prepare_native_run(root)
        elif entry=='runtime_prepare':
            from runtime.build import prepare_build
            prepare_build(root)
        elif entry=='compile':run_native_compile(root)
        elif entry=='svg':submit_approved_svg(root,'P001','<svg/>',action_id='host1',produced_against='old')
        elif entry=='blueprint':submit_blueprint(root,'P001',action_id='host1',produced_against='old',image_path=root/'no-image.png',observation={})
        else:current_task_fingerprint(root,'host1','P001','old')
    assert error.value.code=='NDC_SOURCE_CONFLICT'

def test_next_step_exposes_resolution_instead_of_build(tmp_path):
    state=resolve_next_step(blocked_run(tmp_path))
    assert state['runtime_stage']=='blocked_source_conflicts'
    assert state['next_command']==''
    assert state['blocking_issues'][0]['conflict_id']=='db'

def test_old_package_run_without_brief_has_no_new_dependency(tmp_path):
    _assert_brief_conflicts_resolved(tmp_path)
