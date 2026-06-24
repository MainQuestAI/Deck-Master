"""Tests for Page Package v1 & Producer contract (B3)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from production.page_package import (  # noqa: E402
    InternalLeakError,
    PageContent,
    PagePackageError,
    PagePackageIndex,
    SCHEMA_VERSION,
    build_page_package,
    generation_result_reference,
    strip_internal,
)


def _content(pid="p1", order=1, title="Page One"):
    return PageContent(
        page_id=pid, order=order, title=title,
        body_blocks=[{"type": "text", "text": "hello"}],
        labels=["l1"], footnotes=["fn1"],
        callouts=[{"kind": "stat", "value": "10%"}],
        claim_bindings=["c1"], evidence_bindings=["e1"],
        asset_bindings=[{"asset_id": "a1", "slot": "hero"}],
        citations=[{"source": "analyst", "url": "x"}],
    )


def test_build_page_package_required_fields():
    pkg = build_page_package(run_id="r", content=_content())
    assert pkg["schema_version"] == SCHEMA_VERSION
    for key in ("schema_version", "run_id", "page_id", "order", "status",
                "customer_visible", "visual_spec", "asset_bindings", "citations",
                "internal_only", "provenance", "source_fingerprint"):
        assert key in pkg
    assert len(pkg["source_fingerprint"]) == 64
    cv = pkg["customer_visible"]
    assert cv["title"] == "Page One"
    assert cv["body_blocks"]


def test_customer_visible_and_internal_only_strict_separation():
    internal = {
        "production_rationale": "reuse slide from Q1 deck",
        "agent_instructions": ["do not show to client"],
        "unresolved_questions": ["verify stat"],
        "private_source_refs": ["confidential/internal.pptx"],
        "review_notes": ["check tone"],
    }
    pkg = build_page_package(run_id="r", content=_content(), internal_only=internal)
    # internal_only carries exactly the allowed fields
    assert set(pkg["internal_only"].keys()) <= {
        "production_rationale", "agent_instructions", "unresolved_questions",
        "private_source_refs", "review_notes",
    }
    # customer_visible has none of them
    cv_keys = set(pkg["customer_visible"].keys())
    assert cv_keys.isdisjoint(internal.keys())


def test_internal_leak_detected():
    internal = {"agent_instructions": ["SUPERSECRET internal note xyz"]}
    content = _content()
    content.title = "SUPERSECRET internal note xyz"  # leaked verbatim
    with pytest.raises(InternalLeakError, match="leaked"):
        build_page_package(run_id="r", content=content, internal_only=internal)


def test_no_leak_when_clean():
    internal = {"production_rationale": "internal reasoning about layout"}
    pkg = build_page_package(run_id="r", content=_content(title="Customer Title"), internal_only=internal)
    assert pkg["customer_visible"]["title"] == "Customer Title"


def test_strip_internal_removes_internal_only():
    pkg = build_page_package(run_id="r", content=_content(), internal_only={"review_notes": ["n"]})
    safe = strip_internal(pkg)
    assert "internal_only" not in safe
    # customer_visible intact
    assert safe["customer_visible"]["title"] == pkg["customer_visible"]["title"]
    # original still has internal_only
    assert "internal_only" in pkg


def test_claim_evidence_asset_bindings_present():
    pkg = build_page_package(run_id="r", content=_content())
    assert pkg["claim_bindings"] == ["c1"]
    assert pkg["evidence_bindings"] == ["e1"]
    assert pkg["asset_bindings"] == [{"asset_id": "a1", "slot": "hero"}]
    assert pkg["citations"] == [{"source": "analyst", "url": "x"}]


def test_index_coverage_required_pages(tmp_path):
    idx = PagePackageIndex(tmp_path)
    idx.write(build_page_package(run_id="r", content=_content("p1", 1)))
    idx.write(build_page_package(run_id="r", content=_content("p2", 2)))
    cov = idx.coverage(["p1", "p2", "p3"])
    assert cov["missing_pages"] == ["p3"]
    assert cov["complete"] is False


def test_assert_required_coverage_raises_on_missing(tmp_path):
    idx = PagePackageIndex(tmp_path)
    idx.write(build_page_package(run_id="r", content=_content("p1", 1), status="ready_for_build"))
    with pytest.raises(PagePackageError, match="coverage incomplete"):
        idx.assert_required_coverage(["p1", "p2"])


def test_assert_required_coverage_blocks_on_blocked(tmp_path):
    idx = PagePackageIndex(tmp_path)
    idx.write(build_page_package(run_id="r", content=_content("p1", 1), status="blocked"))
    with pytest.raises(PagePackageError, match="blocked"):
        idx.assert_required_coverage(["p1"])


def test_required_pages_full_coverage_passes(tmp_path):
    idx = PagePackageIndex(tmp_path)
    for i, pid in enumerate(["p1", "p2", "p3"], 1):
        idx.write(build_page_package(run_id="r", content=_content(pid, i), status="ready_for_build"))
    idx.assert_required_coverage(["p1", "p2", "p3"])  # no raise
    cov = idx.coverage(["p1", "p2", "p3"])
    assert cov["complete"] is True


def test_generation_result_reference():
    pkg = build_page_package(run_id="r", content=_content())
    ref = generation_result_reference(pkg, generation_session="gs_001")
    assert ref["page_id"] == "p1"
    assert ref["package_path"] == "page_packages/p1.json"
    assert ref["generation_session"] == "gs_001"
    assert len(ref["source_fingerprint"]) == 64


def test_index_written_and_listed(tmp_path):
    idx = PagePackageIndex(tmp_path)
    idx.write(build_page_package(run_id="r", content=_content("p1", 1)))
    idx.write(build_page_package(run_id="r", content=_content("p2", 2)))
    packages = idx.list_packages()
    assert len(packages) == 2
    assert [p["page_id"] for p in packages] == ["p1", "p2"]  # ordered
    index = json.loads((tmp_path / "page_packages/index.json").read_text())
    assert index["page_count"] == 2
