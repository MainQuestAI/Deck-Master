"""An in-place formal view edit invalidates actual compile and semantic inputs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build.native_engine import native_build_fingerprint, submit_approved_svg
from high_density.content import load_content_lock
from high_density.svg import compile_svg
from quality.external_review import _page_packages_content_fingerprint
from runtime.build import run_build
from test_sc1_1_native_host_chain import new_run, host_scene
from workflow import actions


def test_committed_view_edit_invalidates_compile_and_semantic_inputs(tmp_path):
    root = new_run(tmp_path, 'direct_svg')
    views = root / 'diagram_views'
    views.mkdir()
    view = views / 'target.json'
    view.write_text(json.dumps({'nodes': ['orders', 'inventory'], 'edges': [['orders', 'inventory']]}))
    task = run_build(root)['pages'][0]
    scene = host_scene(root, load_content_lock(root, 'P001'))
    svg = compile_svg(scene, tmp_path / 'host.svg').read_text()
    submit_approved_svg(root, 'P001', svg, action_id=task['action_id'], produced_against=task['produced_against'], scene=scene)
    before = native_build_fingerprint(root), _page_packages_content_fingerprint(root)
    envelope = actions.create_action_envelope(action_id='change_view', task_id='change_view', scope_pages=['P001'], input_fingerprint='approved-view', permission='runtime')
    actions.stage_action_result(root, envelope, {'diagram_views/target.json': json.dumps({'nodes': ['orders', 'inventory'], 'edges': [['inventory', 'orders']]})})
    actions.commit_action_result(root, envelope, current_input_fingerprint='approved-view', targets={'diagram_views/target.json': view})
    after = native_build_fingerprint(root), _page_packages_content_fingerprint(root)
    assert before[0] != after[0], 'compile still accepts an old diagram relationship'
    assert before[1] != after[1], 'semantic review still accepts an old diagram relationship'
