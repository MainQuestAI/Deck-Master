"""Synthetic runs exercise actual task dispatch, budget ledgers and commits."""
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from build.native_budget import read_native_task_budgets, set_native_task_budgets
from build.native_tasks import dispatch_native_task, record_native_failure
from native_pptx.contracts import ContractError
from production.page_package import PageContent, PagePackageIndex, build_page_package
from runtime.build import run_build
from test_sc1_1_native_host_chain import new_run
from workflow.actions import ActionStaleError, check_action_budget, read_current_revision, read_revision_state, recover_projections


def setup_run(tmp_path, *, mode="direct_svg", two_pages=False):
    root = new_run(tmp_path, mode)
    if two_pages:
        package = build_page_package(run_id=root.name, content=PageContent(
            page_id="P002", order=2, title="Second page", body_blocks=[], visual_spec={"page_role": "cover"}),
            status="ready_for_build")
        PagePackageIndex(root).write(package)
    tasks = run_build(root)["pages"]
    return root, tasks


def authorization(root, limits, **changes):
    return dict(limits=limits, expected_revision=read_current_revision(root).get("revision_id", ""),
                reason="Synthetic user authorized exact ceiling", actor={"id": "test-local-user", "role": "user"}, **changes)


def request(root):
    return json.loads(read_revision_state(root)["request.json"])


def package(root, page_id):
    return next(item for item in PagePackageIndex(root).list_packages() if item["page_id"] == page_id)


def test_exhausted_task_gets_only_explicit_extra_attempt_and_keeps_history(tmp_path):
    root, tasks = setup_run(tmp_path, two_pages=True)
    first, other = tasks
    for _ in range(3):
        record_native_failure(root, action_id=first["action_id"], task_id=first["task_id"], reason="Synthetic failed attempt")
    with pytest.raises(ContractError, match="budget exhausted"):
        dispatch_native_task(root, "svg", [package(root, "P001")])
    old_issued = {p: p.read_bytes() for p in (root / "build/native_tasks/issued").glob("*.json")}
    result = set_native_task_budgets(root, **authorization(root, {first["task_id"]: 4}))
    assert result["authorization"]["changes"][0]["used_at_authorization"] == 3
    assert result["authorization"]["changes"][0]["previous_max_actions"] == 3
    assert result["authorization"]["actor_authenticated"] is False
    assert all(p.read_bytes() == original for p, original in old_issued.items())
    from build.native_engine import NativeEngineError, submit_approved_svg
    with pytest.raises(NativeEngineError, match="budget exhausted"):
        submit_approved_svg(root, "P001", "<svg/>", action_id=first["action_id"],
                            produced_against=first["produced_against"])
    assert check_action_budget(root, first["task_id"], max_actions=4)["used"] == 3
    statuses = read_native_task_budgets(root, task_ids=[first["task_id"], other["task_id"]])["tasks"]
    assert [(item["max_actions"], item["used"]) for item in statuses] == [(4, 3), (3, 0)]
    next_task = dispatch_native_task(root, "svg", [package(root, "P001")])["pages"][0]
    assert next_task["task_id"] == first["task_id"] and next_task["action_id"] != first["action_id"]
    assert next_task["budget"]["max_actions"] == 4 and next_task["remaining_budget"] == 1
    record_native_failure(root, action_id=next_task["action_id"], task_id=next_task["task_id"], reason="Last authorized attempt failed")
    with pytest.raises(ContractError, match="budget exhausted"):
        dispatch_native_task(root, "svg", [package(root, "P001")])
    assert check_action_budget(root, first["task_id"], max_actions=4)["used"] == 4


@pytest.mark.parametrize("mode", ["direct_svg", "image_blueprint"])
def test_budget_setting_does_not_upgrade_or_replace_an_outstanding_action(tmp_path, mode):
    root, (old,) = setup_run(tmp_path, mode=mode)
    before = (root / "build/native_tasks/issued" / f"{old['action_id']}.json").read_bytes()
    set_native_task_budgets(root, **authorization(root, {old["task_id"]: 4}))
    again = run_build(root)["pages"][0]
    assert again == old
    assert (root / "build/native_tasks/issued" / f"{old['action_id']}.json").read_bytes() == before
    state = read_native_task_budgets(root, task_ids=[old["task_id"]])["tasks"][0]
    assert state["max_actions"] == 4 and state["issued_max_actions"] == 3 and state["used"] == 0


def test_batch_replay_is_noop_and_stale_new_authorization_is_rejected(tmp_path):
    root, tasks = setup_run(tmp_path, two_pages=True)
    args = authorization(root, {task["task_id"]: 4 for task in tasks})
    first = set_native_task_budgets(root, **args)
    revision = read_current_revision(root)["revision_id"]
    replay = set_native_task_budgets(root, **args)
    assert replay["status"] == "already_applied" and replay["receipt"] == first["receipt"]
    assert read_current_revision(root)["revision_id"] == revision
    assert len(request(root)["native_task_budget_authorizations"]) == 1
    unchanged = set_native_task_budgets(root, **{**args, "expected_revision": revision})
    assert unchanged["status"] == "unchanged"
    with pytest.raises(ActionStaleError):
        set_native_task_budgets(root, **{**args, "reason": "Different stale request"})
    with pytest.raises(ContractError, match="only retain or increase"):
        set_native_task_budgets(root, **authorization(root, {tasks[0]["task_id"]: 3}))


def test_mixed_increase_and_unchanged_default_remains_readable_and_replayable(tmp_path):
    root, tasks = setup_run(tmp_path, two_pages=True)
    first, other = tasks
    args = authorization(root, {first["task_id"]: 4, other["task_id"]: 3})
    issued = {p: p.read_bytes() for p in (root / "build/native_tasks/issued").glob("*.json")}
    result = set_native_task_budgets(root, **args)
    assert result["status"] == "applied"
    assert request(root)["native_task_budget_limits"] == {first["task_id"]: 4}
    assert result["authorization"]["requested_limits"] == args["limits"]
    assert [change["task_id"] for change in result["authorization"]["changes"]] == [first["task_id"]]
    statuses = read_native_task_budgets(root, task_ids=list(args["limits"]))["tasks"]
    assert [(item["max_actions"], item["issued_max_actions"], item["used"]) for item in statuses] == [(4, 3, 0), (3, 3, 0)]
    revision = read_current_revision(root)
    replay = set_native_task_budgets(root, **args)
    assert replay["status"] == "already_applied" and replay["receipt"] == result["receipt"]
    assert read_current_revision(root) == revision
    assert all(path.read_bytes() == contents for path, contents in issued.items())
    assert run_build(root)["pages"] == tasks


@pytest.mark.parametrize("value", [True, False, 0, 21, -1, 4.0, "4", None])
def test_only_integer_bounded_ceilings_allowed(tmp_path, value):
    root, (task,) = setup_run(tmp_path)
    revision = read_current_revision(root)
    with pytest.raises(ContractError, match="integer between 1 and 20"):
        set_native_task_budgets(root, **authorization(root, {task["task_id"]: value}))
    assert read_current_revision(root) == revision


@pytest.mark.parametrize("bad", ["../native_svg_P001", "native_svg_P002", "native_reconstruct_P001", "arbitrary"])
def test_budget_target_requires_actual_task_ownership(tmp_path, bad):
    root, _ = setup_run(tmp_path)
    with pytest.raises(ValueError):
        set_native_task_budgets(root, **authorization(root, {bad: 4}))


def test_local_actor_and_reason_are_required(tmp_path):
    root, (task,) = setup_run(tmp_path)
    args = authorization(root, {task["task_id"]: 4})
    for change in [{"actor": {"id": "agent", "role": "agent"}}, {"actor": {}}, {"reason": " "}]:
        with pytest.raises(ContractError):
            set_native_task_budgets(root, **{**args, **change})
    assert not (root / "delivery/final_approval.json").exists()


def test_reconstruct_override_does_not_increase_imagegen_budget(tmp_path):
    from PIL import Image
    from build.native_tasks import submit_blueprint
    root, (image_task,) = setup_run(tmp_path, mode="image_blueprint")
    image = tmp_path / "controlled-blueprint.png"
    Image.new("RGB", (1672, 941), "white").save(image)
    submit_blueprint(root, "P001", action_id=image_task["action_id"],
                     produced_against=image_task["produced_against"], image_path=image,
                     observation={"tool": "imagegen", "request_id": "synthetic-unit-only", "description": "Controlled unit input, not actual UAT"})
    task = run_build(root)["pages"][0]
    assert task["task_id"] == "native_reconstruct_P001"
    set_native_task_budgets(root, **authorization(root, {task["task_id"]: 4}))
    state = read_native_task_budgets(root, task_ids=[image_task["task_id"], task["task_id"]])["tasks"]
    assert [(item["kind"], item["max_actions"], item["used"]) for item in state] == [("imagegen", 3, 1), ("reconstruct", 4, 0)]


def test_competing_budget_writes_use_revision_cas(tmp_path, monkeypatch):
    import workflow.actions as actions
    root, (task,) = setup_run(tmp_path)
    args = authorization(root, {task["task_id"]: 4})
    barrier = Barrier(2)
    actual_stage = actions.stage_action_result

    def stage_together(*values, **kwargs):
        staged = actual_stage(*values, **kwargs)
        barrier.wait(timeout=10)
        return staged

    monkeypatch.setattr(actions, "stage_action_result", stage_together)

    def submit(limit):
        try:
            return set_native_task_budgets(root, **{**args, "limits": {task["task_id"]: limit}})["status"]
        except ActionStaleError:
            return "stale"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, [4, 5]))
    assert sorted(results) == ["applied", "stale"]
    assert len(request(root)["native_task_budget_authorizations"]) == 1
    assert check_action_budget(root, task["task_id"], max_actions=5)["used"] == 0


def test_failure_during_budget_staging_is_rechecked_under_commit_lock(tmp_path, monkeypatch):
    import workflow.actions as actions
    root, (task,) = setup_run(tmp_path)
    args = authorization(root, {task["task_id"]: 4})
    actual_stage = actions.stage_action_result

    def fail_after_staging(*values, **kwargs):
        staged = actual_stage(*values, **kwargs)
        record_native_failure(root, action_id=task["action_id"], task_id=task["task_id"], reason="Concurrent real failure ledger write")
        return staged

    monkeypatch.setattr(actions, "stage_action_result", fail_after_staging)
    with pytest.raises(ActionStaleError, match="used budget changed"):
        set_native_task_budgets(root, **args)
    assert read_native_task_budgets(root, task_ids=[task["task_id"]])["tasks"][0]["max_actions"] == 3
    monkeypatch.setattr(actions, "stage_action_result", actual_stage)
    result = set_native_task_budgets(root, **args)
    assert result["authorization"]["changes"][0]["used_at_authorization"] == 1


def test_actual_host_commit_wins_over_staged_budget_without_losing_output(tmp_path, monkeypatch):
    import workflow.actions as actions
    from build.native_engine import submit_approved_svg
    from high_density.content import load_content_lock
    from high_density.svg import compile_svg
    from test_sc1_1_native_host_chain import host_scene
    root, (task,) = setup_run(tmp_path)
    args = authorization(root, {task["task_id"]: 4})
    scene = host_scene(root, load_content_lock(root, "P001"))
    svg = compile_svg(scene, tmp_path / "controlled.svg").read_text()
    actual_stage = actions.stage_action_result

    def host_commit_after_budget_stage(*values, **kwargs):
        staged = actual_stage(*values, **kwargs)
        if values[1]["task_id"] == "native_budget_authorization":
            submit_approved_svg(root, "P001", svg, action_id=task["action_id"],
                                produced_against=task["produced_against"], scene=scene)
        return staged

    monkeypatch.setattr(actions, "stage_action_result", host_commit_after_budget_stage)
    with pytest.raises(ActionStaleError):
        set_native_task_budgets(root, **args)
    committed = read_revision_state(root)
    assert committed["high_density_build/svg/P001.svg"].decode() == svg
    assert "native_task_budget_authorizations" not in json.loads(committed["request.json"])
    assert check_action_budget(root, task["task_id"], max_actions=3)["used"] == 1


def test_raw_override_cannot_skip_authorization_history(tmp_path):
    root = new_run(tmp_path, "direct_svg")
    path = root / "request.json"
    value = json.loads(path.read_text())
    value["native_task_budget_limits"] = {"native_svg_P001": 20}
    path.write_text(json.dumps(value))
    with pytest.raises(ContractError, match="authorization history"):
        run_build(root)


def test_incomplete_authorization_history_cannot_raise_dispatch_budget(tmp_path):
    root = new_run(tmp_path, "direct_svg")
    path = root / "request.json"
    value = json.loads(path.read_text())
    value["native_task_budget_limits"] = {"native_svg_P001": 20}
    value["native_task_budget_authorizations"] = [{
        "schema_version": "deck_native_task_budget_authorization.v1", "actor_authenticated": False,
        "changes": [{"task_id": "native_svg_P001", "max_actions": 20}],
    }]
    path.write_text(json.dumps(value))
    with pytest.raises(ContractError, match="authorization history"):
        run_build(root)
    assert not list((root / "build/native_tasks/issued").glob("*.json"))


@pytest.mark.parametrize("changed", ["run", "requested", "page", "previous", "identity"])
def test_schema_valid_but_inconsistent_authorization_history_is_rejected(tmp_path, changed):
    from build.native_budget import native_task_budget_limit
    root, (task,) = setup_run(tmp_path)
    set_native_task_budgets(root, **authorization(root, {task["task_id"]: 4}))
    value = request(root)
    record = value["native_task_budget_authorizations"][0]
    if changed == "run":
        record["run_id"] = "another-run"
    elif changed == "requested":
        record["requested_limits"][task["task_id"]] = 20
        from workflow.actions import fingerprint_payload
        identity = {key: record[key] for key in ("source_revision", "requested_limits", "reason", "actor")}
        record["authorization_id"] = "native_budget_" + fingerprint_payload(identity)[:32]
    elif changed == "page":
        record["changes"][0]["page_id"] = "P002"
    elif changed == "previous":
        record["changes"][0]["previous_max_actions"] = 2
    else:
        record["authorization_id"] = "native_budget_wrong"
    with pytest.raises(ContractError, match="authorization history"):
        native_task_budget_limit(value, task["task_id"])


def test_committed_budget_survives_projection_failure_and_dispatch_uses_snapshot(tmp_path):
    root, (task,) = setup_run(tmp_path)
    args = authorization(root, {task["task_id"]: 4})
    original_replace = Path.replace

    def interrupt_projection(path, target):
        if Path(target) == root / "request.json":
            raise KeyboardInterrupt("committed budget before projection")
        return original_replace(path, target)

    with patch.object(Path, "replace", interrupt_projection), pytest.raises(KeyboardInterrupt):
        set_native_task_budgets(root, **args)
    assert set_native_task_budgets(root, **args)["status"] == "already_applied"
    projection = json.loads((root / "request.json").read_text())
    projection["native_max_actions"] = 20
    (root / "request.json").write_text(json.dumps(projection))
    record_native_failure(root, action_id=task["action_id"], task_id=task["task_id"], reason="End previous issued action")
    new = run_build(root)["pages"][0]
    assert new["budget"]["max_actions"] == 4
    assert new["remaining_budget"] == 3
    recover_projections(root)
    assert json.loads((root / "request.json").read_text())["native_task_budget_limits"] == {task["task_id"]: 4}
