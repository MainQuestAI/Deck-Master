"""CLI build options remain authoritative after projection recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

from build.build_route import persist_route, resolve_build_route
from test_sc1_1_native_host_chain import new_run
from workflow.actions import (
    commit_action_result, create_action_envelope, read_current_revision,
    read_revision_state, recover_projections, stage_action_result,
)

def versioned_run(tmp_path):
    root = new_run(tmp_path, "direct_svg")
    request = json.loads((root / "request.json").read_text())
    persist_route(root, resolve_build_route(request))
    envelope = create_action_envelope(
        action_id="initial-content", task_id="initial-content", scope_pages=["P001"],
        permission="runtime", input_fingerprint="initial-content",
    )
    stage_action_result(root, envelope, {"request.json": json.dumps(request)})
    commit_action_result(root, envelope, current_input_fingerprint="initial-content",
                         targets={"request.json": root / "request.json"})
    return root


def test_cli_options_survive_recovery_and_bind_a_new_revision(tmp_path):
    root = versioned_run(tmp_path)
    before = read_current_revision(root)["revision_id"]
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/deck_master.py"), "build", "prepare",
         "--run-dir", str(root), "--output-profile", "production_pptx",
         "--review-depth", "independent-main"],
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "DECK_MASTER_DEV_SKIP_SETUP": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert read_current_revision(root)["revision_id"] != before
    committed = json.loads(read_revision_state(root)["request.json"])
    assert committed["output_profile"] == "production_pptx"
    assert committed["review_depth"] == "independent_main"
    recover_projections(root)
    assert json.loads((root / "request.json").read_text()) == committed
    assert json.loads((root / "build/build_manifest.json").read_text())["output_profile"] == "production_pptx"


def test_competing_cli_options_do_not_lose_the_winning_request(tmp_path, monkeypatch):
    from deck_master import _persist_build_options
    import workflow.actions as actions
    root = versioned_run(tmp_path)
    staged = Barrier(2)
    stage = actions.stage_action_result

    def stage_together(*args, **kwargs):
        value = stage(*args, **kwargs)
        staged.wait(timeout=10)
        return value

    monkeypatch.setattr(actions, "stage_action_result", stage_together)

    def submit(profile):
        try:
            _persist_build_options(root, Namespace(output_profile=profile, review_depth="independent-main"))
            return profile
        except actions.ActionStaleError:
            return "stale"

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(submit, ["client_delivery", "production_pptx"]))
    assert outcomes.count("stale") == 1
    winner = next(value for value in outcomes if value != "stale")
    assert json.loads(read_revision_state(root)["request.json"])["output_profile"] == winner
    recover_projections(root)
    assert json.loads((root / "request.json").read_text())["output_profile"] == winner


def test_options_and_first_route_commit_together(tmp_path):
    from deck_master import _persist_build_options
    # Start from a separate revisioned run before its first route selection.
    source = tmp_path / "first-selection"
    source.mkdir()
    request = {"run_id": source.name, "run_mode": "production"}
    (source / "request.json").write_text(json.dumps(request))
    envelope = create_action_envelope(action_id="base", task_id="base", scope_pages=["P001"], permission="runtime", input_fingerprint="base")
    stage_action_result(source, envelope, {"request.json": json.dumps(request)})
    commit_action_result(source, envelope, current_input_fingerprint="base", targets={"request.json": source / "request.json"})
    _persist_build_options(source, Namespace(profile="direct-svg", output_profile="production_pptx"))
    current = read_revision_state(source)
    assert json.loads(current["request.json"])["profile"] == "direct-svg"
    assert json.loads(current["build/route.json"])["authoring_mode"] == "direct_svg"
    assert json.loads(current["build/route.json"])["selection_origin"] == "user_explicit"
    # Repeating the same options is idempotent and cannot silently switch engines.
    revision = read_current_revision(source)["revision_id"]
    _persist_build_options(source, Namespace(profile="direct-svg", output_profile="production_pptx"))
    assert read_current_revision(source)["revision_id"] == revision
    with pytest.raises(ValueError, match="route conflict"):
        _persist_build_options(source, Namespace(profile="legacy-ppt-master"))
    assert read_current_revision(source)["revision_id"] == revision
