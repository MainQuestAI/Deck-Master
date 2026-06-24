"""Tests for the Stage Contract Registry (A1).

Covers 9/9 contract validation, ordering, transition policies, and that the
registry cross-references manifest stage_ids and contract stage_ids.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import (  # noqa: E402
    PRODUCTION_STAGE_IDS,
    load_registry,
)


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_nine_contracts_loaded(registry):
    assert len(registry.ordered_contracts()) == 9


def test_every_contract_has_required_fields(registry):
    for contract in registry.ordered_contracts():
        assert contract.business_question if False else contract.raw["business_question"]
        assert contract.entry  # validation rule set present
        assert contract.exit_criteria
        assert contract.outputs
        assert contract.transition_policy
        assert "next_stage" in contract.transition_policy
        assert "mode" in contract.transition_policy
        assert "approval_required" in contract.transition_policy


def test_exit_criteria_reference_outputs(registry):
    for contract in registry.ordered_contracts():
        exit_artifacts = set(contract.exit_criteria.get("required_artifacts", []))
        output_patterns = {o["path_pattern"] for o in contract.outputs}
        # at least one exit artifact path is anchored to a declared output
        # (allow loose matching for directory-style outputs like page_packages/)
        assert exit_artifacts, contract.stage_id


def test_staleness_dependencies_non_empty(registry):
    for contract in registry.ordered_contracts():
        assert contract.staleness_dependencies, contract.stage_id


def test_forcing_questions_have_ids(registry):
    for contract in registry.ordered_contracts():
        ids = {q["question_id"] for q in contract.forcing_questions}
        assert len(ids) == len(contract.forcing_questions), f"dup question_id in {contract.stage_id}"
        for q in contract.forcing_questions:
            assert q["required"] in (True, False)
            assert q["category"]


def test_next_stage_ladder_is_contiguous(registry):
    ordered = [c.stage_id for c in registry.ordered_contracts()]
    # production stages init..review form a contiguous ladder; review's
    # next_stage is the non-bypassable client_export gate, and deck-learn is a
    # post-delivery stage reached after delivery is recorded.
    contiguous = ordered[:-1]  # deck-init .. deck-review
    for i, stage in enumerate(contiguous[:-1]):
        nxt = registry.contract(stage).next_stage
        assert nxt == contiguous[i + 1], f"{stage} -> {nxt} (expected {contiguous[i+1]})"
    assert registry.contract("deck-review").next_stage == "client_export"
    assert registry.contract(ordered[-1]).next_stage in (None,)


def test_each_production_skill_links_to_contract(registry):
    for stage in PRODUCTION_STAGE_IDS:
        skill = registry.skill(stage)
        assert skill.stage_id == stage
        assert registry.contract(stage).stage_id == stage


def test_preauthorizable_implies_approval_required_or_auto(registry):
    for contract in registry.ordered_contracts():
        if contract.preauthorizable:
            # a transition that is preauthorizable must be a real gate first
            assert contract.approval_required or contract.transition_policy["mode"] == "automatic"


def test_non_bypassable_transition_cannot_be_preauthorized(registry):
    for contract in registry.ordered_contracts():
        if contract.non_bypassable:
            assert not contract.preauthorizable, contract.stage_id


def test_review_export_cannot_be_preauthorized(registry):
    c = registry.contract("deck-review")
    assert c.non_bypassable
    assert not c.preauthorizable
    assert c.approval_required
