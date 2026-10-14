"""RC3-01: actual preproduction method consumption and immutable history.

The provider in this module is an explicitly synthetic L1 helper. These tests
verify dispatch/read boundaries, never model quality or independent execution.
"""
import json
from pathlib import Path

import pytest

from deck_master import content_review, method_resources, service
from deck_master.errors import MethodResourceMissing
from deck_master.models import sha256_bytes
from synthetic_review_provider import dispatch_with_synthetic_provider
from test_content_preproduction_review import _deck, _independent_adapter


def _dispatch(tmp_path):
    project, store = _deck(tmp_path)
    outcome = dispatch_with_synthetic_provider(
        project, adapter_context=_independent_adapter(store, store.load_document()))
    assert outcome["status"] == "review_dispatched"
    return project, store, outcome


def test_preproduction_work_order_consumes_five_actual_methods_and_complete_packet(tmp_path):
    project, store, outcome = _dispatch(tmp_path)
    task = outcome["task"]
    result = method_resources.read_task_methods(project, task["task_id"])
    assert result["status"] == "current"
    assert [item["id"] for item in result["methods"]] == [
        "source-reading", "content-methods", "content-examples", "content-calibration", "review-and-repair"]
    summary = service.task_summary(store, store.load_document(), task)
    assert result["current_method_release"] == summary["method_release"] == task["method_release"]
    for item, dispatched in zip(result["methods"], summary["method_resources"], strict=True):
        raw = Path(item["path"]).read_bytes()
        assert raw == item["content"].encode("utf-8")
        assert sha256_bytes(raw) == item["sha256"] == dispatched["sha256"]
    packet = store.read_object_json(outcome["review_draft_ref"])
    document = store.load_document()
    assert packet["narrative"] == store.read_object_json(document["narrative"])
    assert packet["plan"] == store.read_object_json(document["content_plan"])
    assert packet["task"] == document["task"]
    assert packet["manuscript"]["page_order"] == [entry["page_id"] for entry in document["pages"]]
    for candidate in packet["manuscript"]["pages"]:
        page = store.read_object_json(candidate["page_ref"])
        assert candidate["customer_visible"] == page["customer_visible"]
        assert candidate["speaker_notes"] == page["speaker_notes"]
        assert candidate["content_mapping"] == page["content_mapping"]
    for material in packet["materials"]:
        assert material["extract"] == store.read_object_json(material["extract_ref"])


def test_changed_or_missing_calibration_cannot_relabel_an_old_preproduction_task(tmp_path, monkeypatch):
    project, store, outcome = _dispatch(tmp_path)
    task = outcome["task"]
    initial = method_resources.read_task_methods(project, task["task_id"])
    current_before = (store.project_root / ".deckmaster/current.json").read_bytes()
    task_ref = next(ref for ref in store.load_document()["tasks"]
                    if store.read_object_json(ref)["task_id"] == task["task_id"])
    task_before = store.read_object_bytes(task_ref)
    packet_before = store.read_object_bytes(outcome["review_draft_ref"])
    installed_methods = tmp_path / "another-method-installation"
    for item in initial["methods"]:
        target = installed_methods / item["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item["content"].encode("utf-8"))
    calibration = installed_methods / "references/content-calibration.md"
    calibration.write_bytes(calibration.read_bytes() + b"\nnew calibration revision\n")
    monkeypatch.setattr(method_resources, "resolve_root", lambda: installed_methods)
    changed = method_resources.read_task_methods(project, task["task_id"])
    assert changed["status"] == "basis_changed"
    assert changed["dispatch_method_release"] == initial["dispatch_method_release"]
    assert changed["current_method_release"] != initial["dispatch_method_release"]
    calibration.unlink()
    with pytest.raises(MethodResourceMissing, match="content-calibration"):
        method_resources.read_task_methods(project, task["task_id"])
    assert (store.project_root / ".deckmaster/current.json").read_bytes() == current_before
    assert store.read_object_bytes(task_ref) == task_before
    assert store.read_object_bytes(outcome["review_draft_ref"]) == packet_before


def test_default_provider_gap_keeps_complete_reviewable_manuscript(tmp_path):
    project, store = _deck(tmp_path)
    document_before = store.load_document()
    outcome = content_review.dispatch_preproduction_review(project)
    assert outcome["status"] == "needs_reviewer"
    assert outcome["requirement"] == "independent_model_or_human"
    assert outcome["review_draft"]["manuscript"]["page_order"] == ["p1", "p2"]
    assert store.read_object_json(outcome["review_draft_ref"]) == outcome["review_draft"]
    assert store.load_document() == document_before


def test_current_r2_anchor_and_prior_evaluation_bytes_are_separate():
    report = Path(__file__).resolve().parents[2] / "docs/reports/content-collaboration-v1.2"
    manifest = json.loads((report / "fixtures/manifest.json").read_text(encoding="utf-8"))
    current = manifest["current_inputs"]["anchors/content-anchors.md"]
    assert current["sha256"] == "3f58b7392b30ceb4304699071cc12cc6b4eff487af512b48e4121a1e43efb2bc"
    assert sha256_bytes((report / "anchors/content-anchors.md").read_bytes()) == current["sha256"]
    assert current["evaluation_status_at_import"] == "NOT_RUN"
    prior = manifest["historical_reviewed_inputs"]["anchors/content-anchors.md"]
    assert prior["sha256"] == "42774a7006dec5e8e319cfbd9c58d0cf9c3cc52f1e67793d81cfb9133643ad4c"
    assert sha256_bytes((report / prior["archived_path"]).read_bytes()) == prior["sha256"]
    expected_evaluations = {
        "evaluator-a.md": "2f54746075e7e960b1ab7063739c129c5e23c9afafeb3d53884a07a00b3b03d9",
        "evaluator-b.md": "25c8ae255c44a7f67499055de14df68037cae04adca07b7ef0b00f1f1342ab88",
        "evaluator-c.md": "acce344fd1c007b654a821ae6e2c4c202c70d24b092af1badcaff473051415e1",
        "evaluator-d.md": "e41b78cb648693595880e67a86947a68237b37a7fc820eee90ef04533cf2392b",
        "adjudication.md": "b75a1df7ed1b10dfbe0f4065980d0bfcfcbd52e2480090f97c0ee0fda7d31f41",
    }
    for name, digest in expected_evaluations.items():
        assert sha256_bytes((report / "evaluation" / name).read_bytes()) == digest
    for relative, entry in manifest["historical_artifacts"].items():
        raw = (report / relative).read_bytes()
        assert sha256_bytes(raw) == entry["sha256"]
        assert len(raw) == entry["bytes"]
    assert len(manifest["historical_artifacts"]) == 6
