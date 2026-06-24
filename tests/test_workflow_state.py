"""Tests for the Workflow State Resolver (A2)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.state import WorkflowStateResolver, resolve_workflow_state  # noqa: E402

REGISTRY = load_registry()


def _touch(path: Path, content: dict | None = None, *, after: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if after:
        time.sleep(after)
    if content is None:
        path.write_text("{}\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(content), encoding="utf-8")


def _stages_by_id(state):
    return {s["stage_id"]: s for s in state["stages"]}


# --- empty / new run ---


def test_empty_run_all_not_started_or_entry_blocked(tmp_path):
    state = resolve_workflow_state(tmp_path, run_id="run-1", registry=REGISTRY)
    stages = _stages_by_id(state)
    # deck-init has no required previous and no required artifacts → ready
    assert stages["deck-init"]["status"] in {"ready", "in_progress"}
    # everything after is entry_blocked
    for sid in (
        "deck-brief",
        "deck-planner",
        "deck-sourcing",
        "deck-producer",
        "deck-builder",
        "deck-quality",
        "deck-review",
        "deck-learn",
    ):
        assert stages[sid]["status"] == "entry_blocked", sid
    assert state["current_skill_stage"] == "deck-init"
    assert state["recommended_next_skill"] == "deck-brief"  # init next is brief


def test_runtime_stage_field_separated_from_skill_stage(tmp_path):
    seen = {}

    def runtime_stage(root: Path) -> str:
        seen["called"] = True
        return "needs_brief"

    state = resolve_workflow_state(
        tmp_path, run_id="r", registry=REGISTRY, runtime_stage_fn=runtime_stage
    )
    assert seen.get("called") is True
    assert state["runtime_stage"] == "needs_brief"
    # current_skill_stage is the contract view, independent of runtime_stage
    assert state["current_skill_stage"] == "deck-init"
    assert state["runtime_stage"] != state["current_skill_stage"]


# --- partial run ---


def test_partial_run_blocks_downstream(tmp_path):
    _touch(tmp_path / "deck_project.json")
    _touch(tmp_path / "material_inventory.json")
    _touch(tmp_path / "workspace_policy.json")
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    stages = _stages_by_id(state)
    assert stages["deck-init"]["status"] == "completed"
    assert stages["deck-init"]["exit_valid"] is True
    # deck-brief entry now open (no required_decisions blocking in A2)
    assert stages["deck-brief"]["entry_valid"] is True
    assert stages["deck-brief"]["status"] == "ready"
    assert state["current_skill_stage"] == "deck-brief"


def test_brief_outputs_present_marks_awaiting_approval(tmp_path):
    # init complete
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(tmp_path / f)
    # brief outputs
    _touch(tmp_path / "deck_brief.json", {"thesis": "x"})
    _touch(tmp_path / "claim_map.json", {"claims": []})
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    stages = _stages_by_id(state)
    # brief is approval-required → awaiting_approval (not auto completed)
    assert stages["deck-brief"]["status"] == "awaiting_approval"
    assert state["approval_required"] is True
    # planner entry still blocked because brief not COMPLETED
    assert stages["deck-planner"]["status"] == "entry_blocked"


# --- completed run ---


def test_automatic_stage_completes(tmp_path):
    # producer is automatic (approval_required=false)
    # build a minimal chain up through sourcing completion is heavy; instead
    # verify automatic stages complete when their outputs exist in isolation
    # by checking builder/quality automatic transitions directly.
    # plant producer outputs (page packages) and builder outputs
    _touch(tmp_path / "page_packages" / "p1.json", {"page": 1})
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    stages = _stages_by_id(state)
    # producer exit requires page_packages/ dir present with files → exit_valid
    assert stages["deck-producer"]["exit_valid"] is True
    # producer approval_required False → completed
    assert stages["deck-producer"]["status"] == "completed"


# --- stale propagation ---


def test_upstream_change_marks_downstream_stale(tmp_path):
    # complete init + brief outputs (brief awaiting_approval)
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(tmp_path / f)
    _touch(tmp_path / "deck_brief.json", {"v": 1})
    _touch(tmp_path / "claim_map.json", {})
    # planner outputs depend on brief; create planner outputs AFTER brief
    time.sleep(0.02)
    _touch(tmp_path / "narrative_plan.json", {"v": 1})
    _touch(tmp_path / "page_tasks.json", {"v": 1})

    state0 = resolve_workflow_state(tmp_path, registry=REGISTRY)
    s0 = _stages_by_id(state0)
    # planner's staleness_dependencies include deck_brief.json; if we now touch
    # brief AFTER planner outputs, planner becomes stale.
    time.sleep(0.02)
    _touch(tmp_path / "deck_brief.json", {"v": 2})

    state1 = resolve_workflow_state(tmp_path, registry=REGISTRY)
    s1 = _stages_by_id(state1)
    assert s1["deck-planner"]["stale"] is True
    assert s1["deck-planner"]["status"] == "stale"
    assert "deck-planner" in state1["stale_skills"]
    # and the stale artifact surfaces
    assert "deck_brief.json" in state1["stale_artifacts"]


# --- determinism / rebuild ---


def test_resolver_is_deterministic(tmp_path):
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(tmp_path / f)
    a = resolve_workflow_state(tmp_path, registry=REGISTRY)
    b = resolve_workflow_state(tmp_path, registry=REGISTRY)
    # source_fingerprint stable
    assert a["source_fingerprint"] == b["source_fingerprint"]
    # every stage output_fingerprint stable
    for sa, sb in zip(a["stages"], b["stages"]):
        assert sa["output_fingerprint"] == sb["output_fingerprint"]


def test_snapshot_writer_roundtrip(tmp_path):
    resolver = WorkflowStateResolver(registry=REGISTRY)
    state = resolver.write_snapshot(tmp_path, run_id="snap")
    written = json.loads((tmp_path / "workflow" / "workflow_state.json").read_text())
    assert written["run_id"] == "snap"
    assert written["schema_version"] == "deck_workflow_state.v1"
    assert written["source_fingerprint"] == state["source_fingerprint"]


def test_schema_version_and_required_fields(tmp_path):
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    assert state["schema_version"] == "deck_workflow_state.v1"
    assert len(state["stages"]) == 9
    for key in (
        "schema_version",
        "run_id",
        "current_skill_stage",
        "runtime_stage",
        "stages",
        "recommended_next_skill",
        "generated_at",
        "source_fingerprint",
    ):
        assert key in state
    # source_fingerprint is sha256 hex
    assert len(state["source_fingerprint"]) == 64
    int(state["source_fingerprint"], 16)


def test_missing_artifacts_aggregated(tmp_path):
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    # deck-init has no required outputs; deck-brief entry requires deck_project etc.
    assert isinstance(state["missing_artifacts"], list)


def test_resolver_ignores_unknown_extra_files(tmp_path):
    # a corrupt/foreign json should not crash the resolver
    (tmp_path / "workflow").mkdir()
    _touch(tmp_path / "workflow" / "bogus_handoff.json", {"junk": True})
    _touch(tmp_path / "deck_project.json")
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    assert state["schema_version"] == "deck_workflow_state.v1"


def test_allowed_and_blocked_actions(tmp_path):
    _touch(tmp_path / "deck_project.json")
    _touch(tmp_path / "material_inventory.json")
    _touch(tmp_path / "workspace_policy.json")
    _touch(tmp_path / "deck_brief.json", {"v": 1})
    _touch(tmp_path / "claim_map.json", {})
    state = resolve_workflow_state(tmp_path, registry=REGISTRY)
    # brief awaiting approval → approve/reject allowed, advance blocked
    assert "approve" in state["allowed_actions"]
    assert any(ba["action"] == "advance:deck-brief" for ba in state["blocked_actions"])
