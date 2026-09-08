from pathlib import Path
from unittest.mock import patch

import pytest

from workflow.actions import (
    ActionEnvelopeError, action_applied, commit_action_result, create_action_envelope,
    read_revision_state, stage_action_result,
)


def commit(root, action, files):
    envelope = create_action_envelope(action_id=action, task_id="t", scope_pages=["P001"], input_fingerprint="fp")
    stage_action_result(root, envelope, files)
    return commit_action_result(root, envelope, current_input_fingerprint="fp", targets={p: root / p for p in files})


def test_repeat_delta_preserves_other_page(tmp_path):
    commit(tmp_path, "a", {"a": "old-a", "b": "old-b"})
    commit(tmp_path, "b", {"a": "new-a"})
    commit(tmp_path, "c", {"b": "new-b"})
    commit(tmp_path, "d", {"a": "new-a"})
    assert read_revision_state(tmp_path)["b"] == b"new-b"


@pytest.mark.parametrize("action", ["../escape", "/tmp/escape", "..", "a/b"])
def test_unsafe_action_rejected_before_staging(tmp_path, action):
    with pytest.raises((ValueError, ActionEnvelopeError)):
        commit(tmp_path, action, {"out": "x"})


def test_external_target_rejected(tmp_path):
    envelope = create_action_envelope(action_id="a", task_id="t", scope_pages=["P001"], input_fingerprint="fp")
    stage_action_result(tmp_path, envelope, {"x": "bad"})
    with pytest.raises(ActionEnvelopeError):
        commit_action_result(tmp_path, envelope, current_input_fingerprint="fp", targets={"x": tmp_path.parent / "escape"})


def test_receipt_survives_projection_interruption(tmp_path):
    commit(tmp_path, "a", {"a": "old-a", "b": "old-b"})
    replace = Path.replace
    def interrupted(self, target):
        if Path(target) == tmp_path / "b":
            raise KeyboardInterrupt("simulated death")
        return replace(self, target)
    with patch.object(Path, "replace", interrupted), pytest.raises(KeyboardInterrupt):
        commit(tmp_path, "b", {"a": "new-a", "b": "new-b"})
    assert action_applied(tmp_path, "b")["status"] == "applied"
    from workflow.actions import revision_read, revision_input_path, recover_projections
    with revision_read(tmp_path):
        assert revision_input_path(tmp_path, tmp_path / "a").read_text() == "new-a"
        assert revision_input_path(tmp_path, tmp_path / "b").read_text() == "new-b"
    recover_projections(tmp_path)
    assert (tmp_path / "b").read_text() == "new-b"


def test_snapshot_captures_preexisting_inputs(tmp_path):
    (tmp_path / "page_packages").mkdir()
    (tmp_path / "page_packages/P001.json").write_text('{"page_id":"P001"}')
    commit(tmp_path, "a", {"out": "new"})
    assert "page_packages/P001.json" in read_revision_state(tmp_path)


def test_read_scope_does_not_move_mid_operation(tmp_path):
    from workflow.actions import revision_read, revision_input_path
    commit(tmp_path, "a", {"a": "old"})
    with revision_read(tmp_path):
        commit(tmp_path, "b", {"a": "new"})
        assert revision_input_path(tmp_path, tmp_path / "a").read_text() == "old"


def test_symlink_and_page_scope_rejected(tmp_path):
    envelope = create_action_envelope(action_id="a", task_id="t", scope_pages=["P001"], input_fingerprint="fp")
    stage_action_result(tmp_path, envelope, {"svg": "bad"})
    with pytest.raises(ActionEnvelopeError):
        commit_action_result(tmp_path, envelope, current_input_fingerprint="fp", targets={"svg": tmp_path / "high_density_build/svg/P002.svg"})
    (tmp_path / "link").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ActionEnvelopeError):
        commit_action_result(tmp_path, envelope, current_input_fingerprint="fp", targets={"svg": tmp_path / "link/escape"})


def test_budget_uses_committed_receipt_after_process_interruption(tmp_path):
    from workflow.actions import check_action_budget, record_action_failure
    replace = Path.replace
    def interrupted(self, target):
        if Path(target) == tmp_path / 'a':
            raise KeyboardInterrupt('interrupted after pointer switch')
        return replace(self, target)
    with patch.object(Path, 'replace', interrupted), pytest.raises(KeyboardInterrupt):
        commit(tmp_path, 'a', {'a': 'new'})
    assert check_action_budget(tmp_path, 't', max_actions=1)['exhausted']
    assert record_action_failure(tmp_path, action_id='a', task_id='t', reason='late exception')['status'] == 'applied'
    assert check_action_budget(tmp_path, 't', max_actions=2)['used'] == 1


def test_real_package_reader_reads_complete_committed_snapshot(tmp_path):
    import json
    from production.page_package import PagePackageIndex
    from workflow.actions import revision_read
    old = {'page_id': 'P001', 'order': 1, 'customer_visible': {'title': 'old'}}
    new = {**old, 'customer_visible': {'title': 'new'}}
    commit(tmp_path, 'a', {'page_packages/P001.json': json.dumps(old)})
    replace = Path.replace
    def interrupted(self, target):
        if Path(target) == tmp_path / 'page_packages/P001.json':
            raise KeyboardInterrupt('before projection')
        return replace(self, target)
    with patch.object(Path, 'replace', interrupted), pytest.raises(KeyboardInterrupt):
        commit(tmp_path, 'b', {'page_packages/P001.json': json.dumps(new)})
    assert json.loads((tmp_path/'page_packages/P001.json').read_text()) == old
    with revision_read(tmp_path):
        assert PagePackageIndex(tmp_path).list_packages()[0]['customer_visible']['title'] == 'new'
