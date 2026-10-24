"""RP-27 parity with independent graph construction and closure traversal."""

import copy
from unittest.mock import patch
import pytest
from deck_master import editing, review, stages, delivery_eligibility, exports
from review_reuse_helpers import assembled_inputs
from test_export import _passing_deck


def test_assembly_builds_one_graph_without_skipping_pages(tmp_path, monkeypatch):
    store, doc = assembled_inputs(tmp_path / "project", 4)
    original = editing._current_artifact_digests
    with (
        patch.object(editing, "_current_artifact_digests", wraps=original) as graph,
        patch.object(review, "evaluate_page_visual", wraps=review.evaluate_page_visual) as pages,
    ):
        stages.require_assembly_ready(store, doc)
    assert graph.call_count == 1 and pages.call_count == 4
    # The last page still rejects a bad original/SVG provenance binding.
    damaged = copy.deepcopy(doc)
    artifact = store.read_object_json(damaged["pages"][-1]["svg_preview"])
    artifact["derived_from"] = [doc["pages"][0]["svg"]]
    damaged["pages"][-1]["svg_preview"] = store.put_json_object(artifact)
    with pytest.raises(stages.operations.OperationError, match="preview does not belong"):
        stages.require_assembly_ready(store, damaged)


def test_context_rejects_other_output_notes_policy_and_control(tmp_path):
    store, doc = assembled_inputs(tmp_path / "project", 2)
    context = editing.ReviewReadContext(store, doc)
    assert context.require(store, copy.deepcopy(doc)) is context
    for key, value in [
        ("outputs", {"pptx": doc["pages"][0]["svg"]}),
        ("notes_overlay", {"p01": "changed"}),
        ("policy", {**doc["policy"], "professional_review_required_for_delivery": True}),
        ("reviews", []),
    ]:
        changed = {**doc, key: value}
        with pytest.raises(ValueError, match="different snapshot"):
            context.require(store, changed)
    for entry in doc["pages"]:
        assert editing.page_visual_summary(store, doc, entry) == editing.page_visual_summary(store, doc, entry, read_context=context)


def test_selected_output_uses_copy_and_matches_uncached_policy(tmp_path):
    _, store = _passing_deck(tmp_path, notes="Synthetic notes overlay")
    doc = store.load_document()
    doc["policy"]["professional_review_required_for_delivery"] = True
    context = editing.ReviewReadContext(store, doc)
    before = copy.deepcopy(context.artifacts)
    output_hashes = []
    for policy in ("pptx_notes", "pure_reading"):
        selected = delivery_eligibility.selected_output(store, doc, notes_policy=policy)
        output_hashes.append(selected["file_sha256"])
        assert delivery_eligibility.professional_policy(
            store, doc, selected_output=selected, read_context=context
        ) == delivery_eligibility.professional_policy(store, doc, selected_output=selected)
        assert context.artifacts == before
    assert len(set(output_hashes)) == 2
    with patch.object(editing, "_current_artifact_digests", wraps=editing._current_artifact_digests) as graph:
        exports._facts(store, doc, control=doc)
    assert graph.call_count == 1


def test_multiowner_history_closure_index_matches_uncached(monkeypatch):
    from test_review import make_document, make_review, finding, ref, current_artifacts, PPTX_REF, PAGE_REF

    reviews = []
    for owner_id in ("a", "b"):
        old = make_review(
            "content",
            seed=owner_id,
            subjects=[ref("old-page"), ref("old-ppt")],
            findings=[finding("same-id")],
            dependencies=[{"kind": "content", "identity": "page:p1", "sha256": ref("old-page")["sha256"]}],
        )
        old["ref"] = ref("owner-" + owner_id)
        reviews.append(old)
        if owner_id == "a":
            new = make_review(
                "content",
                seed=owner_id,
                replaces=old["ref"],
                subjects=[PAGE_REF, PPTX_REF],
                findings=[finding("same-id", resolution="fixed", evidence=[ref("proof")])],
            )
            new["ref"] = ref("replacement-a")
            reviews.append(new)
    artifacts = current_artifacts()
    index = review.replacement_index(reviews)
    assert review.finding_closed(reviews, reviews[0], reviews[0]["findings"][0], artifacts, replacements=index)
    assert not review.finding_closed(reviews, reviews[-1], reviews[-1]["findings"][0], artifacts, replacements=index)
    original = review.finding_closed
    with patch.object(review, "replacement_index", wraps=review.replacement_index) as builds:
        actual = review.evaluate_current(make_document(), reviews, artifacts)
    assert builds.call_count == 1
    monkeypatch.setattr(review, "finding_closed", lambda rs, owner, f, a, **kw: original(rs, owner, f, a))
    assert review.evaluate_current(make_document(), reviews, artifacts) == actual
    assert actual["dimensions"]["content:p1"]["open_must_fix"] == ["same-id"]
