"""Synthetic reviews exercise concurrent imports through real gate policy."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from quality_review_v2_helpers import canonical_gate
from test_external_review_currentity import blocked, policy


@pytest.mark.parametrize("severity", ["P0", "P1"])
def test_concurrent_pass_cannot_erase_current_blocking_review(tmp_path, monkeypatch, severity):
    from quality import external_review
    from quality.gate_policy import load_gate_reports

    seeded = canonical_gate(tmp_path)
    passing = copy.deepcopy(seeded["canonical_review"])
    failing = blocked(seeded, "semantic", severity)["canonical_review"]
    gate_path = tmp_path / "quality_reports/external_semantic_session_reviewer_gate.json"
    assert gate_path.exists()
    pass_at_write = threading.Event()
    blocker_persisted = threading.Event()
    actual_write = external_review.write_json

    def interleaved_write(path, payload):
        if path == gate_path and payload.get("status") == "pass":
            pass_at_write.set()
            # Without serialization, the blocking import completes between
            # the pass replacement check and its write and is lost forever.
            blocker_persisted.wait(timeout=0.4)
        actual_write(path, payload)
        if path == gate_path and payload.get("blocks_delivery"):
            blocker_persisted.set()

    monkeypatch.setattr(external_review, "write_json", interleaved_write)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(external_review.import_external_review, tmp_path, passing, replace=True)
        assert pass_at_write.wait(timeout=5)
        second = executor.submit(external_review.import_external_review, tmp_path, failing, replace=True)
        first.result(timeout=5)
        second.result(timeout=5)

    reports = load_gate_reports(tmp_path)
    result = policy(tmp_path, reports)
    assert not result["satisfied"]
    assert any(item["finding_id"] == "retained-finding" for item in result["current_blockers"])
