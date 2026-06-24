"""Skill OS final acceptance (C5).

Asserts the master spec §6 quantitative success criteria as runtime facts,
so "v1.1 ready" cannot be claimed by prose alone — every line is backed by a
machine check.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import PRODUCTION_STAGE_IDS, load_registry  # noqa: E402
from build.manifest import whitelist_project  # noqa: E402
from production.page_package import build_page_package, PageContent  # noqa: E402

REGISTRY = load_registry()


def test_9_production_stage_contracts():
    assert len(REGISTRY.ordered_contracts()) == 9
    assert [c.stage_id for c in REGISTRY.ordered_contracts()] == list(PRODUCTION_STAGE_IDS)


def test_high_impact_transitions_require_approval():
    for sid in ("deck-brief", "deck-planner", "deck-sourcing"):
        assert REGISTRY.contract(sid).approval_required


def test_final_export_non_bypassable_and_not_preauthorizable():
    c = REGISTRY.contract("deck-review")
    assert c.approval_required
    assert c.non_bypassable
    assert not c.preauthorizable


def test_automatic_transitions_not_require_approval():
    for sid in ("deck-init", "deck-producer", "deck-builder", "deck-quality"):
        assert not REGISTRY.contract(sid).approval_required


def test_builder_whitelist_strips_internal_only():
    pkg = build_page_package(
        run_id="r",
        content=PageContent(page_id="p1", order=1, title="t", body_blocks=[{"type": "text", "text": "b"}]),
        internal_only={"review_notes": ["secret xyz"], "agent_instructions": ["do not show xyz"]},
    )
    projected = whitelist_project(pkg)
    assert "internal_only" not in projected


def test_manifest_version_is_1_1_0():
    assert REGISTRY.manifest_version == "1.1.0"
    assert REGISTRY.suite_version == "1.1.0"


def test_contracts_hash_present_and_stable():
    h = REGISTRY.contracts_hash
    assert len(h) == 64
    assert load_registry().contracts_hash == h


def test_compat_aliases_map_to_public_skills():
    amap = REGISTRY.alias_map()
    assert amap["ppt-library"] == "deck-sourcing"
    assert amap["ppt-master"] == "deck-builder"
    assert amap["ppt-quality-gate"] == "deck-quality"
    assert amap["ppt-deck-pro-max"] == "deck-producer"
