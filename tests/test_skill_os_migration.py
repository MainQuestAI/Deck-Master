"""Tests for Legacy Run & Compatibility Migration (C3)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.migration import LegacyBootstrap  # noqa: E402

REGISTRY = load_registry()
NOW = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)


def _touch(p: Path, content="{}") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _legacy_run_with_brief(run: Path) -> None:
    """A pre-Skill-OS run: artifacts present, no workflow/ bookkeeping."""
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json",
              "deck_brief.json", "claim_map.json"):
        _touch(run / f)


def test_legacy_bootstrap_does_not_forge_approval(tmp_path):
    _legacy_run_with_brief(tmp_path)
    bs = LegacyBootstrap(registry=REGISTRY, now=NOW)
    state = bs.infer_run(tmp_path)
    # brief has artifacts -> exit_valid, but approval_required -> awaiting_approval
    brief = next(s for s in state["stages"] if s["stage_id"] == "deck-brief")
    assert brief["exit_valid"] is True
    assert brief["status"] == "awaiting_approval"
    assert state["approval_required"] is True
    # invariant: no forged approvals
    assert state.get("approval_status") != "approved"


def test_bootstrap_writes_marker_and_snapshot(tmp_path):
    _legacy_run_with_brief(tmp_path)
    bs = LegacyBootstrap(registry=REGISTRY, now=NOW)
    record = bs.bootstrap(tmp_path, run_id="legacy-1")
    marker = json.loads((tmp_path / "workflow/legacy_bootstrap.json").read_text())
    assert marker["schema_version"] == "deck_legacy_bootstrap.v1"
    assert marker["forged_approvals"] == 0
    assert "deck-brief" in marker["high_impact_awaiting"]
    assert (tmp_path / "workflow/workflow_state.json").exists()
    assert record["rollback_possible"] is True


def test_bootstrap_creates_no_handoffs_or_approvals(tmp_path):
    _legacy_run_with_brief(tmp_path)
    LegacyBootstrap(registry=REGISTRY, now=NOW).bootstrap(tmp_path)
    # no handoff/approval records synthesized
    assert not (tmp_path / "workflow/handoffs").is_dir() or not list((tmp_path / "workflow/handoffs").glob("*"))
    assert not (tmp_path / "workflow/approvals").is_dir() or not list((tmp_path / "workflow/approvals").glob("*"))


def test_rollback_removes_skill_os_bookkeeping_only(tmp_path):
    _legacy_run_with_brief(tmp_path)
    bs = LegacyBootstrap(registry=REGISTRY, now=NOW)
    bs.bootstrap(tmp_path)
    result = bs.rollback(tmp_path)
    assert result["rolled_back"] is True
    assert not (tmp_path / "workflow/legacy_bootstrap.json").exists()
    # original run artifacts untouched
    for f in ("deck_brief.json", "claim_map.json", "deck_project.json"):
        assert (tmp_path / f).exists()


def test_rollback_idempotent(tmp_path):
    bs = LegacyBootstrap(registry=REGISTRY, now=NOW)
    r1 = bs.rollback(tmp_path)
    assert r1["rolled_back"] is False  # nothing to remove


def test_inference_report(tmp_path):
    _legacy_run_with_brief(tmp_path)
    rep = LegacyBootstrap(registry=REGISTRY, now=NOW).inference_report(tmp_path)
    assert rep["forged_approvals"] == 0
    assert "deck-brief" in rep["high_impact_awaiting"]
    assert rep["current_skill_stage"] == "deck-brief"


def test_empty_legacy_run_bootstraps_to_init(tmp_path):
    state = LegacyBootstrap(registry=REGISTRY, now=NOW).infer_run(tmp_path)
    assert state["current_skill_stage"] == "deck-init"
    init = next(s for s in state["stages"] if s["stage_id"] == "deck-init")
    assert init["status"] in {"ready", "in_progress"}


def test_legacy_run_through_sourcing_all_high_impact_awaiting(tmp_path):
    # artifacts through sourcing present, no approvals anywhere
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json",
              "deck_brief.json", "claim_map.json", "narrative_plan.json", "page_tasks.json",
              "sourcing_plan.json"):
        _touch(tmp_path / f)
    state = LegacyBootstrap(registry=REGISTRY, now=NOW).infer_run(tmp_path)
    stages = {s["stage_id"]: s for s in state["stages"]}
    # brief/planner/sourcing all have exit artifacts but must be awaiting_approval
    for sid in ("deck-brief", "deck-planner", "deck-sourcing"):
        assert stages[sid]["status"] == "awaiting_approval", sid
