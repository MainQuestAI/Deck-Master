"""Issued host actions bind validated SVG/Scene pairs to current inputs."""

import pytest
from build.native_engine import NativeEngineError, _svg_input_fingerprint, submit_approved_svg
from build.native_tasks import dispatch_native_task
from high_density.content import load_content_lock
from high_density.svg import compile_svg
from production.page_package import PagePackageIndex
from workflow import actions
from runtime.build import run_build
from test_sc1_1_native_host_chain import new_run, host_scene


def prepared(tmp_path):
    root = new_run(tmp_path, "direct_svg")
    task = run_build(root)["pages"][0]
    scene = host_scene(root, load_content_lock(root, "P001"))
    svg = compile_svg(scene, tmp_path / "host.svg").read_text()
    return root, task, scene, svg


def submit(root, task, scene, svg):
    return submit_approved_svg(root, "P001", svg, action_id=task["action_id"], produced_against=task["produced_against"], scene=scene)


def test_fingerprint_changes_with_package_content(tmp_path):
    root, task, _, _ = prepared(tmp_path)
    package = root / "page_packages/P001.json"
    envelope = actions.create_action_envelope(
        action_id="update_package", task_id="update_package", scope_pages=["P001"],
        input_fingerprint="approved-package-change", permission="runtime",
    )
    actions.stage_action_result(root, envelope, {"page_packages/P001.json": package.read_text() + "\n"})
    actions.commit_action_result(root, envelope, current_input_fingerprint="approved-package-change",
                                 targets={"page_packages/P001.json": package})
    assert task["produced_against"] != _svg_input_fingerprint(root, "P001")


def test_late_result_rejected_when_inputs_moved_on(tmp_path):
    root, task, scene, svg = prepared(tmp_path)
    package = root / "page_packages/P001.json"
    envelope = actions.create_action_envelope(
        action_id="update_package", task_id="update_package", scope_pages=["P001"],
        input_fingerprint="approved-package-change", permission="runtime",
    )
    actions.stage_action_result(root, envelope, {"page_packages/P001.json": package.read_text() + "\n"})
    actions.commit_action_result(root, envelope, current_input_fingerprint="approved-package-change",
                                 targets={"page_packages/P001.json": package})
    with pytest.raises(NativeEngineError, match="input fingerprint is stale"):
        submit(root, task, scene, svg)
    assert not (root / "high_density_build/svg/P001.svg").exists()


def test_replay_same_output_idempotent_conflict_rejected(tmp_path):
    root, task, scene, svg = prepared(tmp_path)
    assert submit(root, task, scene, svg)["status"] == "svg_staged"
    assert submit(root, task, scene, svg)["status"] == "already_applied"
    with pytest.raises(NativeEngineError) as result:
        submit(root, task, scene, svg + "\n")
    assert result.value.code == "NDC_ACTION_CONFLICT"


def test_missing_produced_against_rejected(tmp_path):
    root, task, scene, svg = prepared(tmp_path)
    with pytest.raises(NativeEngineError) as result:
        submit_approved_svg(root, "P001", svg, action_id=task["action_id"], scene=scene)
    assert result.value.code == "NDC_MISSING_INPUT_FINGERPRINT"


def test_replay_after_other_action_does_not_misreport(tmp_path):
    root, task, scene, svg = prepared(tmp_path)
    submit(root, task, scene, svg)
    next_task = dispatch_native_task(root, "svg", PagePackageIndex(root).list_packages())["pages"][0]
    assert next_task["action_id"] != task["action_id"]
    submit(root, next_task, scene, svg + "\n")
    assert submit(root, task, scene, svg)["status"] == "already_applied"
    assert (root / "high_density_build/svg/P001.svg").read_text() == svg + "\n"


def test_compatibility_projection_does_not_replace_committed_input(tmp_path):
    root, task, _, _ = prepared(tmp_path)
    package = root / "page_packages/P001.json"
    package.write_text(package.read_text() + "\n")
    assert task["produced_against"] == _svg_input_fingerprint(root, "P001")
