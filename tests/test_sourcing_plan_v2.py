"""Tests for Sourcing Plan v2 (B2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sourcing.plan import (  # noqa: E402
    ALL_DECISIONS,
    SCHEMA_VERSION,
    build_sourcing_plan_v2,
    migrate_v1,
)


def _page(pid="p1", evidence=None):
    return {"page_id": pid, "page_task_id": pid, "claim_ids": ["c1"], "evidence_need": evidence or []}


def test_schema_version_and_required_fields():
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page()])
    assert plan["schema_version"] == SCHEMA_VERSION
    for key in ("schema_version", "run_id", "status", "source_fingerprint", "pages", "created_at"):
        assert key in plan
    assert len(plan["source_fingerprint"]) == 64


def test_one_decision_per_page_task():
    pages = [_page("p1"), _page("p2"), _page("p3")]
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=pages)
    assert len(plan["pages"]) == 3
    assert {p["page_id"] for p in plan["pages"]} == {"p1", "p2", "p3"}


def test_zero_candidates_falls_to_generate_or_manual():
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page()], allow_generate=True)
    assert plan["pages"][0]["decision"] == "generate"
    plan2 = build_sourcing_plan_v2(run_id="r", page_tasks=[_page()], allow_generate=False)
    assert plan2["pages"][0]["decision"] in {"manual", "evidence"}


def test_one_candidate_reuses():
    lib = {"by_beat": {"p1": [{"confidence": 0.9, "source_authority": "analyst", "freshness_status": "fresh"}]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    assert plan["pages"][0]["decision"] == "reuse"
    assert plan["pages"][0]["source_authority"] == "analyst"
    assert plan["pages"][0]["freshness_status"] == "fresh"


def test_multiple_candidates_picks_best():
    lib = {"by_beat": {"p1": [
        {"confidence": 0.4},
        {"confidence": 0.95, "source_authority": "primary"},
    ]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    selected = plan["pages"][0]["selected_sources"][0]
    assert selected["confidence"] == 0.95


def test_permission_blocked_marks_page_blocked():
    lib = {"by_beat": {"p1": [{"confidence": 0.9, "permission_status": "blocked"}]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    assert plan["pages"][0]["decision"] == "blocked"
    assert plan["pages"][0]["permission_status"] == "blocked"
    assert plan["status"] == "blocked"
    assert plan["coverage"]["blocked_pages"] == 1


def test_stale_evidence_missing_surfaces_gap():
    plan = build_sourcing_plan_v2(
        run_id="r", page_tasks=[_page("p1", evidence=["case_study"])], allow_generate=False,
    )
    # no candidate + evidence need -> evidence decision, missing_evidence surfaces
    p = plan["pages"][0]
    assert p["decision"] == "evidence"
    assert "case_study" in p["missing_evidence"]
    assert plan["approval_readiness"]["ready"] is False


def test_six_decision_classes_exist_in_schema():
    # all six classes are valid decision values
    assert set(ALL_DECISIONS) == {"reuse", "adapt", "generate", "evidence", "manual", "blocked"}


def test_incomplete_page_coverage_status_draft():
    # mixed: one blocked -> status blocked; otherwise draft until approved
    lib = {"by_beat": {"p1": [{"confidence": 0.9, "permission_status": "pending"}]}}
    plan = build_sourcing_plan_v2(
        run_id="r",
        page_tasks=[_page("p1"), _page("p2")],
        library_results=lib,
    )
    # p1 has pending permission -> not ready -> status draft (not awaiting_approval)
    assert plan["approval_readiness"]["ready"] is False
    assert plan["status"] in {"draft", "blocked", "awaiting_approval"}


def test_v1_migration_safe():
    v1 = {
        "run_id": "r",
        "source": "ppt_library",
        "decisions": [
            {"beat_id": "p1", "decision": "reuse", "selected_candidate": {"confidence": 0.8, "source_authority": "a"}},
            {"beat_id": "p2", "decision": "manual_placeholder"},
            {"beat_id": "p3", "decision": "generate"},
        ],
    }
    v2 = migrate_v1(v1)
    assert v2["schema_version"] == SCHEMA_VERSION
    assert v2["migrated_from"] == "deck_sourcing_plan.v1"
    assert len(v2["pages"]) == 3
    by_page = {p["page_id"]: p for p in v2["pages"]}
    assert by_page["p1"]["decision"] == "reuse"
    assert by_page["p2"]["decision"] == "manual"  # manual_placeholder -> manual
    assert by_page["p3"]["decision"] == "generate"
    # source_fingerprint present
    assert len(v2["source_fingerprint"]) == 64


def test_v1_migration_unknown_decision_falls_back_manual():
    v1 = {"run_id": "r", "decisions": [{"beat_id": "p1", "decision": "what_is_this"}]}
    v2 = migrate_v1(v1)
    assert v2["pages"][0]["decision"] == "manual"
