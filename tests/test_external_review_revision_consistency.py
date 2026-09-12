"""Synthetic reviews test real revision and import consumers, not approval."""
import json

import pytest

from quality.external_review import ExternalReviewError, prepare_quality_review_v2
from quality.gate_freshness import report_currentity
from quality_review_v2_helpers import canonical_gate
from test_revision_transactions import commit


@pytest.mark.parametrize("scope", ["semantic", "visual", "client-readiness"])
def test_review_cannot_dispatch_new_inputs_with_old_native_render(tmp_path, scope):
    canonical_gate(tmp_path)
    first = commit(tmp_path, "baseline", {"high_density_build/svg/P001.svg": "old SVG"})
    (tmp_path / "deck.pptx").write_bytes(b"old rendered deck")
    folder = tmp_path / "render_results"
    folder.mkdir()
    (folder / "render_result.json").write_text(json.dumps({
        "tool": "deck_native", "build_revision": first["revision_id"],
        "artifact_path": "deck.pptx",
    }))
    old = canonical_gate(tmp_path)
    commit(tmp_path, "changed", {"high_density_build/svg/P001.svg": "new SVG"})
    previous_task = (tmp_path / "quality_review_tasks/semantic_review_task.json").read_bytes()
    with pytest.raises(ExternalReviewError, match="render revision"):
        prepare_quality_review_v2(tmp_path, scope=scope, required_page_ids=["P001"])
    assert not report_currentity(tmp_path, old)["current"]
    assert (tmp_path / "quality_review_tasks/semantic_review_task.json").read_bytes() == previous_task


def test_source_review_before_first_render_remains_available(tmp_path):
    canonical_gate(tmp_path)
    commit(tmp_path, "source", {"high_density_build/svg/P001.svg": "new SVG"})
    task = prepare_quality_review_v2(tmp_path, scope="semantic", required_page_ids=["P001"])
    assert task["scope"] == "semantic"
    assert not any(item["ref"].startswith("render_results/") for item in task["based_on"]["input_refs"])
