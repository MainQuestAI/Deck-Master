"""Tests for Sourcing Plan v2."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sourcing.plan import (  # noqa: E402
    ALL_DECISIONS,
    SCHEMA_VERSION,
    build_sourcing_plan_v2,
    migrate_v1,
)
from sourcing.reader import read_sourcing_plan  # noqa: E402


def _page(pid="p1", evidence=None):
    return {
        "beat_id": pid,
        "page_task_id": f"task-{pid}",
        "order": 1,
        "planning": {"claim_ids": ["c1"], "evidence_need": evidence or []},
    }


def _candidate(asset_key: str, score: float, *, trace: str, source_path: str = ""):
    return {
        "candidate_id": f"candidate-{asset_key}",
        "slide_id": f"slide-{asset_key}",
        "asset_key": asset_key,
        "title": asset_key,
        "text_summary": "summary",
        "page_number": 1,
        "score": score,
        "confidence": score,
        "source_asset_id": "a" * 64,
        "source_display_name": "Safe source",
        "screenshot_ref": "",
        "candidate_origin": "ppt_library",
        "reuse_policy": "reuse_or_adapt",
        "query_trace_id": trace,
        "source_path": source_path,
    }


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
    assert {p["page_task_id"] for p in plan["pages"]} == {"task-p1", "task-p2", "task-p3"}


def test_zero_candidates_falls_to_generate_or_manual():
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page()], allow_generate=True)
    assert plan["pages"][0]["decision"] == "generate"
    plan2 = build_sourcing_plan_v2(run_id="r", page_tasks=[_page()], allow_generate=False)
    assert plan2["pages"][0]["decision"] in {"manual", "evidence"}


def test_one_candidate_reuses():
    candidate = _candidate("asset-a", 0.9, trace="trace-p1")
    candidate.update({"source_authority": "analyst", "freshness_status": "fresh"})
    lib = {"by_beat": {"p1": [candidate]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    assert plan["pages"][0]["decision"] == "reuse"
    assert plan["pages"][0]["source_authority"] == "analyst"
    assert plan["pages"][0]["freshness_status"] == "fresh"


def test_multiple_candidates_picks_best():
    lib = {"by_beat": {"p1": [
        _candidate("asset-low", 0.4, trace="trace-p1"),
        _candidate("asset-high", 0.95, trace="trace-p1") | {"source_authority": "primary"},
    ]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    selected = plan["pages"][0]["selected_sources"][0]
    assert selected["confidence"] == 0.95


def test_permission_blocked_marks_page_blocked():
    candidate = _candidate("asset-a", 0.9, trace="trace-p1")
    candidate["permission_status"] = "blocked"
    lib = {"by_beat": {"p1": [candidate]}}
    plan = build_sourcing_plan_v2(run_id="r", page_tasks=[_page("p1")], library_results=lib)
    assert plan["pages"][0]["decision"] == "blocked"
    assert plan["pages"][0]["permission_status"] == "blocked"
    assert plan["status"] == "blocked"
    assert plan["coverage"]["blocked_pages"] == 1


def test_stale_evidence_missing_surfaces_gap():
    plan = build_sourcing_plan_v2(
        run_id="r", page_tasks=[_page("p1", evidence=["case_study"])], allow_generate=False,
    )
    page = plan["pages"][0]
    assert page["decision"] == "evidence"
    assert "case_study" in page["missing_evidence"]
    assert plan["approval_readiness"]["ready"] is False


def test_six_decision_classes_exist_in_schema():
    assert set(ALL_DECISIONS) == {"reuse", "adapt", "generate", "evidence", "manual", "blocked"}


def test_incomplete_page_coverage_status_draft():
    candidate = _candidate("asset-a", 0.9, trace="trace-p1")
    candidate["permission_status"] = "pending"
    lib = {"by_beat": {"p1": [candidate]}}
    plan = build_sourcing_plan_v2(
        run_id="r",
        page_tasks=[_page("p1"), _page("p2")],
        library_results=lib,
    )
    assert plan["approval_readiness"]["ready"] is False
    assert plan["status"] in {"draft", "blocked", "awaiting_approval"}


def test_v1_migration_safe():
    v1 = {
        "run_id": "r",
        "source": "ppt_library",
        "decisions": [
            {
                "beat_id": "p1",
                "page_task_id": "task-p1",
                "source_decision": "reuse",
                "decision_reason": "legacy reuse",
                "selected_candidate": _candidate("asset-a", 0.8, trace="trace-p1"),
            },
            {"beat_id": "p2", "source_decision": "manual_placeholder"},
            {"beat_id": "p3", "source_decision": "generate"},
        ],
    }
    v2 = migrate_v1(v1)
    assert v2["schema_version"] == SCHEMA_VERSION
    assert v2["migrated_from"] == "deck_sourcing_plan.v1"
    assert len(v2["pages"]) == 3
    by_page = {p["page_id"]: p for p in v2["pages"]}
    assert by_page["p1"]["decision"] == "reuse"
    assert by_page["p1"]["reason"] == "legacy reuse"
    assert by_page["p2"]["decision"] == "manual"
    assert by_page["p3"]["decision"] == "generate"
    assert len(v2["source_fingerprint"]) == 64


def test_v1_migration_unknown_decision_falls_back_manual():
    v1 = {"run_id": "r", "decisions": [{"beat_id": "p1", "source_decision": "what_is_this"}]}
    v2 = migrate_v1(v1)
    assert v2["pages"][0]["decision"] == "manual"


def test_global_greedy_allocation_uses_score_before_page_order():
    pages = [_page("p1"), _page("p2")]
    pages[1]["order"] = 2
    selection = {
        "schema_version": "deck_master_ppt_library_selection.v2",
        "selections": [
            {
                "beat_id": "p1",
                "page_task_id": "task-p1",
                "query_trace_id": "trace-p1",
                "candidates": [
                    _candidate("shared", 0.9, trace="trace-p1"),
                    _candidate("p1-backup", 0.8, trace="trace-p1"),
                ],
            },
            {
                "beat_id": "p2",
                "page_task_id": "task-p2",
                "query_trace_id": "trace-p2",
                "candidates": [
                    _candidate("shared", 0.95, trace="trace-p2"),
                    _candidate("p2-backup", 0.7, trace="trace-p2"),
                ],
            },
        ],
    }

    plan = build_sourcing_plan_v2(run_id="r", page_tasks={"tasks": pages}, library_results=selection)
    selected = {page["page_id"]: page["selected_sources"][0]["asset_key"] for page in plan["pages"]}

    assert selected == {"p1": "p1-backup", "p2": "shared"}


def test_global_greedy_tie_uses_page_order_then_candidate_rank():
    pages = [_page("p1"), _page("p2")]
    pages[0]["order"] = 2
    selection = {"by_beat": {
        "p1": [
            _candidate("shared", 0.9, trace="trace-p1"),
            _candidate("p1-backup", 0.9, trace="trace-p1"),
        ],
        "p2": [_candidate("shared", 0.9, trace="trace-p2")],
    }}

    plan = build_sourcing_plan_v2(run_id="r", page_tasks={"tasks": pages}, library_results=selection)
    selected = {page["page_id"]: page["selected_sources"][0]["asset_key"] for page in plan["pages"]}

    assert selected == {"p1": "p1-backup", "p2": "shared"}


def test_selected_source_preserves_identity_and_drops_unsafe_fields():
    candidate = _candidate("asset-a", 0.9, trace="", source_path="/Users/private/source.pptx")
    candidate["screenshot_path"] = "/private/previews/slide.png"
    selection = {
        "selections": [{
            "beat_id": "p1",
            "page_task_id": "task-p1",
            "query_trace_id": "trace-p1",
            "candidates": [candidate],
        }],
    }

    plan = build_sourcing_plan_v2(run_id="r", page_tasks={"tasks": [_page()]}, library_results=selection)
    selected = plan["pages"][0]["selected_sources"][0]

    assert selected["asset_key"] == "asset-a"
    assert selected["query_trace_id"] == "trace-p1"
    assert selected["page_task_id"] == "task-p1"
    assert "source_path" not in selected
    assert "screenshot_path" not in selected


def test_candidate_without_asset_identity_becomes_gap_with_warning():
    candidate = _candidate("asset-a", 0.9, trace="trace-p1")
    candidate["asset_key"] = ""

    plan = build_sourcing_plan_v2(
        run_id="r",
        page_tasks={"tasks": [_page()]},
        library_results={"by_beat": {"p1": [candidate]}},
    )

    assert plan["pages"][0]["decision"] == "generate"
    assert any("CANDIDATE_IDENTITY_MISSING" in warning for warning in plan["warnings"])


def test_selection_page_task_identity_mismatch_becomes_gap():
    selection = {
        "selections": [{
            "beat_id": "p1",
            "page_task_id": "wrong-task",
            "query_trace_id": "trace-p1",
            "candidates": [_candidate("asset-a", 0.9, trace="trace-p1")],
        }],
    }

    plan = build_sourcing_plan_v2(
        run_id="r",
        page_tasks={"tasks": [_page()]},
        library_results=selection,
    )

    assert plan["pages"][0]["decision"] == "generate"
    assert any("PAGE_TASK_ID_MISMATCH" in warning for warning in plan["warnings"])


def test_repeat_source_requires_explicit_page_policy_and_warns():
    pages = [_page("p1"), _page("p2")]
    pages[1].update({"order": 2, "allow_repeat_source": True})
    selection = {"by_beat": {
        "p1": [_candidate("shared", 0.9, trace="trace-p1")],
        "p2": [_candidate("shared", 0.8, trace="trace-p2")],
    }}

    plan = build_sourcing_plan_v2(run_id="r", page_tasks={"tasks": pages}, library_results=selection)

    assert [p["selected_sources"][0]["asset_key"] for p in plan["pages"]] == ["shared", "shared"]
    assert any("REPEAT_SOURCE_ALLOWED" in warning for warning in plan["warnings"])


def test_canonical_reader_migrates_legacy_without_writing(tmp_path):
    path = tmp_path / "sourcing_plan.json"
    path.write_text(
        '{"schema_version":"deck_sourcing_plan.v1","run_id":"r","decisions":'
        '[{"beat_id":"p1","source_decision":"generate"}]}',
        encoding="utf-8",
    )
    before = path.read_bytes()

    plan = read_sourcing_plan(path)

    assert plan["schema_version"] == SCHEMA_VERSION
    assert plan["pages"][0]["decision"] == "generate"
    assert path.read_bytes() == before
