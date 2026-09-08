"""Native host freshness must follow the committed snapshot after real death."""
from contextlib import nullcontext
from pathlib import Path
import signal
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tests import test_revision_process_recovery as process_helpers
from tests.test_sc1_1_native_host_chain import new_run, host_scene
from build.native_engine import submit_approved_svg, _svg_input_fingerprint
from build.native_tasks import current_task_fingerprint
from high_density.content import load_content_lock
from high_density.svg import compile_svg
from runtime.build import run_build
from workflow import actions


@pytest.mark.parametrize('outer_old_read', [False, True])
def test_old_host_result_is_rejected_after_committed_input_projection_sigkill(tmp_path, outer_old_read):
    root = new_run(tmp_path, 'direct_svg')
    task = run_build(root)['pages'][0]
    lock = load_content_lock(root, 'P001')
    scene = host_scene(root, lock)
    svg = compile_svg(scene, tmp_path / 'old.svg').read_text()
    seed = process_helpers.staged(root, 'baseline', {'audit-marker': 'unchanged'})
    actions.commit_action_result(root, seed['envelope'], current_input_fingerprint='approved-fp', targets={'audit-marker': root / 'audit-marker'})
    original_revision = actions.read_current_revision(root)['revision_id']
    package_file = root / 'page_packages/P001.json'
    import json
    original = package_file.read_text()
    package = json.loads(original)
    package['customer_visible']['title'] = 'New approved scope'
    config = process_helpers.staged(root, 'change', {'page_packages/P001.json': json.dumps(package)})
    with actions.revision_read(root) if outer_old_read else nullcontext():
        process = process_helpers.start(root, 'after_pointer', config)
        try:
            process_helpers.ready(process)
            process.kill()
            process.communicate(timeout=10)
            assert process.returncode == -signal.SIGKILL
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        assert package_file.read_text() == original
        assert actions.read_current_revision(root)['revision_id'] != original_revision
        # The same callback used while holding the commit lock must override
        # any older reader snapshot retained by an outer operation.
        commit_lock = actions._acquire_run_lock(root)
        try:
            fresh = current_task_fingerprint(root, task['action_id'], 'P001', task['produced_against'])
        finally:
            actions._release_run_lock(commit_lock)
        assert fresh != task['produced_against']
        with pytest.raises(Exception, match='stale'):
            submit_approved_svg(root, 'P001', svg, action_id=task['action_id'], produced_against=task['produced_against'], scene=scene)
    assert _svg_input_fingerprint(root, 'P001') != task['produced_against']
    state = actions.read_revision_state(root)
    assert json.loads(state['page_packages/P001.json'])['customer_visible']['title'] == 'New approved scope'
    assert 'high_density_build/svg/P001.svg' not in state
    assert not actions.action_applied(root, task['action_id'])
