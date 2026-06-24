"""Tests for Workflow Autopilot v2 (B5)."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.autopilot import AutopilotV2  # noqa: E402
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.policy import PreauthorizationRuntime, transition_key  # noqa: E402
from workflow.questions import QuestionResolver  # noqa: E402

NOW = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
REGISTRY = load_registry()
BASE = Path(__file__).resolve().parent


def _touch(p: Path, content="{}") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _answer_required(run: Path, stage_id: str) -> None:
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract(stage_id)
    fp = qr.input_fingerprint(contract, run)
    dl = DecisionLog()
    for q in contract.forcing_questions:
        if q.get("required"):
            dl.record(
                run, run_id="r", stage_id=stage_id,
                question_id=q["question_id"], answer="answered",
                actor={"id": "test", "role": "operator"},
                required=True, input_fingerprint=fp,
            )


def _fresh(name: str) -> Path:
    run = BASE / name
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    return run


def _seed_init(run: Path, *, answer=True) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(run / f)
    if answer:
        _answer_required(run, "deck-init")


def _seed_brief(run: Path, *, answer=True) -> None:
    _seed_init(run)
    _touch(run / "deck_brief.json", json.dumps({"thesis": "x"}))
    _touch(run / "claim_map.json", json.dumps({"c": []}))
    if answer:
        _answer_required(run, "deck-brief")


def _seed_through(run: Path, upto: str) -> None:
    artifacts = {
        "deck-init": ["deck_project.json", "material_inventory.json", "workspace_policy.json"],
        "deck-brief": ["deck_brief.json", "claim_map.json"],
        "deck-planner": ["narrative_plan.json", "page_tasks.json"],
        "deck-sourcing": ["sourcing_plan.json"],
        "deck-producer": ["page_packages/"],
        "deck-builder": ["build_manifest.json", "artifact_manifest.json", "render_result.json"],
        "deck-quality": ["quality_report.json", "customer_visible_safety_gate.json"],
        "deck-review": ["final_readiness.json", "final_artifact_approval.json"],
    }
    order = ["deck-init", "deck-brief", "deck-planner", "deck-sourcing", "deck-producer",
             "deck-builder", "deck-quality", "deck-review"]
    for stage in order:
        for f in artifacts[stage]:
            if f.endswith("/"):
                _touch(run / f / "p1.json")
            else:
                _touch(run / f)
        _answer_required(run, stage)
        if stage == upto:
            break


def test_interactive_stops_at_brief_approval():
    run = _fresh("_ap_brief")
    _seed_brief(run)
    result = AutopilotV2(now=NOW).run(run, mode="interactive", max_steps=4, run_id="r")
    assert result.stop_reason == "approval_required"
    assert any(s.action == "prepare_handoff" for s in result.steps)
    shutil.rmtree(run)


def test_quick_mode_auto_advances_brief():
    run = _fresh("_ap_quick")
    _seed_brief(run)
    result = AutopilotV2(now=NOW).run(run, mode="quick", max_steps=4, run_id="r")
    # quick clears brief approval -> advance; planner has no artifacts -> stop
    assert any(s.action == "advance" and s.stage_before == "deck-brief" for s in result.steps)
    assert result.final_stage == "deck-planner"
    shutil.rmtree(run)


def test_final_export_always_stops():
    run = _fresh("_ap_export")
    _seed_through(run, "deck-review")
    # quick mode auto-advances through approval gates and reaches deck-review,
    # where the final client export transition must ALWAYS stop (never auto-export).
    result = AutopilotV2(now=NOW).run(run, mode="quick", max_steps=10, run_id="r")
    assert result.stop_reason == "final_export_requires_approval"
    assert result.final_stage == "deck-review"
    shutil.rmtree(run)


def test_interactive_stops_at_first_approval_gate():
    run = _fresh("_ap_export_int")
    _seed_through(run, "deck-review")
    result = AutopilotV2(now=NOW).run(run, mode="interactive", max_steps=10, run_id="r")
    # interactive stops at the first high-impact approval (deck-brief), never reaching export
    assert result.stop_reason == "approval_required"
    assert result.final_stage == "deck-brief"
    shutil.rmtree(run)


def test_preauth_valid_clears_brief():
    run = _fresh("_ap_preauth")
    _seed_brief(run)
    t = transition_key("deck-brief", "deck-planner")
    PreauthorizationRuntime(now=NOW).create(
        run, run_id="r", actor={"id": "boss", "role": "approver"},
        mode="preauthorized", allowed_transitions=[t], ttl_seconds=3600,
    )
    result = AutopilotV2(now=NOW).run(run, mode="preauthorized", max_steps=4, run_id="r")
    assert any(s.action == "advance" and s.preauthorization_id for s in result.steps)


def test_preauth_expired_does_not_clear():
    run = _fresh("_ap_preauth_exp")
    _seed_brief(run)
    t = transition_key("deck-brief", "deck-planner")
    PreauthorizationRuntime(now=NOW).create(
        run, run_id="r", actor={"id": "boss", "role": "approver"},
        mode="preauthorized", allowed_transitions=[t], ttl_seconds=60,
    )
    result = AutopilotV2(now=NOW.replace(hour=12)).run(run, mode="preauthorized", max_steps=4, run_id="r")
    assert result.stop_reason == "approval_required"


def test_preauth_out_of_scope_does_not_clear():
    run = _fresh("_ap_preauth_oos")
    _seed_brief(run)
    other = transition_key("deck-planner", "deck-sourcing")
    PreauthorizationRuntime(now=NOW).create(
        run, run_id="r", actor={"id": "boss", "role": "approver"},
        mode="preauthorized", allowed_transitions=[other], ttl_seconds=3600,
    )
    result = AutopilotV2(now=NOW).run(run, mode="preauthorized", max_steps=4, run_id="r")
    assert result.stop_reason == "approval_required"


def test_review_only_blocks_upstream():
    run = _fresh("_ap_ro")
    _seed_brief(run)  # current = deck-brief (upstream)
    result = AutopilotV2(now=NOW).run(run, mode="review-only", max_steps=4, run_id="r")
    assert result.stop_reason == "review_only_blocked_upstream"


def test_repair_mode_only_owner_stage():
    run = _fresh("_ap_repair")
    _seed_brief(run)  # current = deck-brief, repair owner = deck-sourcing
    result = AutopilotV2(now=NOW).run(
        run, mode="repair", max_steps=4, run_id="r", repair_owner_stage="deck-sourcing")
    assert result.stop_reason == "repair_owner_stage_mismatch"


def test_evidence_recorded_per_step():
    run = _fresh("_ap_evidence")
    _seed_brief(run)
    result = AutopilotV2(now=NOW).run(run, mode="interactive", max_steps=4, run_id="r")
    assert len(result.steps) >= 1
    s = result.steps[0]
    assert s.stage_before == "deck-brief"
    assert s.stop_reason == "approval_required"
    assert s.handoff_id


def test_blocking_questions_stop_when_unanswered():
    run = _fresh("_ap_block")
    # seed init artifacts but DON'T answer init forcing questions
    _seed_init(run, answer=False)
    result = AutopilotV2(now=NOW).run(run, mode="quick", max_steps=4, run_id="r")
    assert result.stop_reason == "blocking_questions"


def test_automatic_init_to_brief_advances():
    run = _fresh("_ap_init")
    _seed_init(run)
    result = AutopilotV2(now=NOW).run(run, mode="quick", max_steps=4, run_id="r")
    # init is already complete in the state view (artifacts + questions), so
    # the autopilot's current stage is deck-brief; brief has no artifacts yet
    # -> it stops there, having effectively advanced past init.
    assert result.final_stage == "deck-brief"
    assert result.stop_reason in {"missing_artifacts", "blocking_questions"}
    shutil.rmtree(run)
