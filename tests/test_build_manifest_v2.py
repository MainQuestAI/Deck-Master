"""Tests for Build Manifest v2 & Builder boundary (B4)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build.manifest import (  # noqa: E402
    BuildManifestError,
    CUSTOMER_WHITELIST,
    PreviewInputBlocked,
    SCHEMA_VERSION,
    build_manifest_v2,
    customer_payload_sha256,
    legacy_preview_adapter,
    package_sha256,
    whitelist_project,
)
from production.page_package import PageContent, build_page_package  # noqa: E402

BACKEND_OK = {
    "name": "ppt-master",
    "production_capable": True,
    "contract_versions": ["deck_page_package.v1", "deck_build_manifest.v2"],
}

_FIXED_NOW = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)


def _pkg(pid="p1", order=1, *, internal=None):
    c = PageContent(page_id=pid, order=order, title=f"Title {pid}",
                    body_blocks=[{"type": "text", "text": "body"}],
                    asset_bindings=[{"asset_id": "a1", "slot": "hero", "sha256": "a" * 64}])
    return build_page_package(
        run_id="r", content=c, internal_only=internal or {},
        source_fingerprint="f" * 64, now=_FIXED_NOW,
    )


def test_build_manifest_v2_required_fields():
    bm = build_manifest_v2(
        run_id="r", packages=[_pkg("p1", 1), _pkg("p2", 2)],
        builder_backend=BACKEND_OK, output_profile="production_html",
    )
    assert bm["schema_version"] == SCHEMA_VERSION
    for key in ("schema_version", "run_id", "status", "source_fingerprint",
                "builder_backend", "output_profile", "pages", "required_outputs", "created_at"):
        assert key in bm
    assert len(bm["pages"]) == 2
    for pb in bm["pages"]:
        assert len(pb["page_package_sha256"]) == 64
        assert len(pb["customer_payload_sha256"]) == 64
        assert pb["approved_assets"]


def test_whitelist_projection_drops_internal_only():
    pkg = _pkg(internal={"review_notes": ["secret"], "production_rationale": "why"})
    projected = whitelist_project(pkg)
    assert "internal_only" not in projected
    # all projected keys are whitelisted
    assert set(projected.keys()) <= set(CUSTOMER_WHITELIST)


def test_customer_payload_sha256_excludes_internal():
    pkg = _pkg(internal={"review_notes": ["secret note xyz"]})
    h1 = customer_payload_sha256(pkg)
    # mutate internal_only; customer payload hash must be unchanged
    pkg["internal_only"] = {"agent_instructions": ["completely different xyz"]}
    h2 = customer_payload_sha256(pkg)
    assert h1 == h2


def test_internal_field_leakage_into_build_payload_blocked():
    # build_manifest_v2 must refuse a package whose internal_only is non-empty
    # is NOT refused at manifest (projection strips it), but assert_no_internal
    # only fires if internal_only present in PAYLOAD. Verify whitelist removes it.
    pkg = _pkg(internal={"agent_instructions": ["x"]})
    payload = whitelist_project(pkg)
    assert "internal_only" not in payload
    bm = build_manifest_v2(run_id="r", packages=[pkg], builder_backend=BACKEND_OK, output_profile="production_html")
    # the recorded customer_payload_sha256 is over the stripped payload (no internal)
    assert bm["pages"][0]["customer_payload_sha256"] == customer_payload_sha256(pkg)


def test_production_direct_preview_input_blocked():
    from build.manifest import block_direct_preview

    with pytest.raises(PreviewInputBlocked, match="preview_manifest"):
        block_direct_preview(production=True)
    # non-production (fixture/dev) allowed to use preview
    block_direct_preview(production=False)


def test_legacy_preview_adapter_explicit_and_flagged():
    preview = {
        "pages": [
            {"page_id": "p1", "page_title": "Old Title", "body": "old body"},
            {"page_id": "p2", "page_title": "Old 2"},
        ]
    }
    packages = legacy_preview_adapter(preview, run_id="r")
    assert len(packages) == 2
    assert all(p.get("legacy_inferred") is True for p in packages)
    assert all(p.get("status") == "draft" for p in packages)
    assert packages[0]["customer_visible"]["title"] == "Old Title"


def test_legacy_adapter_requires_pages():
    with pytest.raises(BuildManifestError, match="no pages"):
        legacy_preview_adapter({"pages": []}, run_id="r")


def test_backend_contract_version_check():
    bad_backend = {"name": "x", "production_capable": True, "contract_versions": []}
    with pytest.raises(BuildManifestError, match="contract versions"):
        build_manifest_v2(run_id="r", packages=[_pkg()], builder_backend=bad_backend, output_profile="production_html")


def test_backend_not_production_capable():
    bad = {"name": "x", "production_capable": False, "contract_versions": ["deck_page_package.v1"]}
    with pytest.raises(BuildManifestError, match="production_capable"):
        build_manifest_v2(run_id="r", packages=[_pkg()], builder_backend=bad, output_profile="production_html")


def test_missing_required_page_rejected():
    with pytest.raises(BuildManifestError, match="missing required"):
        build_manifest_v2(
            run_id="r", packages=[_pkg("p1", 1)],
            builder_backend=BACKEND_OK, output_profile="production_html",
            required_page_ids=["p1", "p2"],
        )


def test_package_hash_changes_with_content():
    p1 = _pkg("p1", 1)
    h1 = package_sha256(p1)
    p1["customer_visible"]["title"] = "Changed"
    h2 = package_sha256(p1)
    assert h1 != h2


def test_source_fingerprint_stable_and_64hex():
    pkgs = [_pkg("p1", 1)]
    bm1 = build_manifest_v2(run_id="r", packages=pkgs, builder_backend=BACKEND_OK, output_profile="production_html")
    bm2 = build_manifest_v2(run_id="r", packages=pkgs, builder_backend=BACKEND_OK, output_profile="production_html")
    assert bm1["source_fingerprint"] == bm2["source_fingerprint"]
    assert len(bm1["source_fingerprint"]) == 64
