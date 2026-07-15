"""Tests for the Workflow Approval & Preauthorization Runtime (A4)."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.approval import (  # noqa: E402
    ApprovalError,
    ApprovalRuntime,
    APPROVED,
    PENDING,
    REJECTED,
    REVOKED,
    STALE,
)
from workflow.handoff import HandoffRuntime  # noqa: E402
from workflow.policy import (  # noqa: E402
    FINAL_EXPORT_TRANSITION,
    PolicyError,
    PreauthorizationRuntime,
    transition_key,
)

REGISTRY = load_registry()
BOSS = {"id": "boss", "role": "approver"}


def _answer_required(run: Path, stage_id: str) -> None:
    from workflow.questions import QuestionResolver  # noqa: E402

    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract(stage_id)
    fp = qr.input_fingerprint(contract, run)
    log = DecisionLog()
    for question in contract.forcing_questions:
        if question.get("required"):
            log.record(
                run,
                run_id="r",
                stage_id=stage_id,
                question_id=question["question_id"],
                answer="answered",
                actor=BOSS,
                required=True,
                input_fingerprint=fp,
            )


def _seed_brief(run: Path, thesis="t") -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (run / f).write_text("{}\n", encoding="utf-8")
    _answer_required(run, "deck-init")
    (run / "deck_brief.json").write_text(json.dumps({"thesis": thesis}), encoding="utf-8")
    (run / "claim_map.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    _answer_required(run, "deck-brief")


def _seed_through_review(run: Path) -> None:
    # minimal artifacts so every stage's exit artifacts exist through deck-review
    for f in (
        "deck_project.json",
        "material_inventory.json",
        "workspace_policy.json",
        "deck_brief.json",
        "claim_map.json",
        "narrative_plan.json",
        "page_tasks.json",
        "sourcing_plan.json",
        "build_manifest.json",
        "artifact_manifest.json",
        "render_result.json",
        "quality_report.json",
        "customer_visible_safety_gate.json",
        "delivery/final_readiness.json",
    ):
        path = run / f
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    (run / "page_packages").mkdir()
    (run / "page_packages" / "p1.json").write_text("{}\n", encoding="utf-8")
    _answer_required(run, "deck-review")


# --- preauthorization ---


def test_preauth_cannot_cover_final_export(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    with pytest.raises(PolicyError, match="non-bypassable"):
        preauth.create(
            tmp_path,
            run_id="r",
            actor=BOSS,
            mode="preauthorized",
            allowed_transitions=[FINAL_EXPORT_TRANSITION],
        )


def test_preauth_create_and_active(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    t = transition_key("deck-brief", "deck-planner")
    p = preauth.create(
        tmp_path, run_id="r", actor=BOSS, mode="preauthorized",
        allowed_transitions=[t], ttl_seconds=60,
    )
    assert p.is_active()
    assert p.covers(t)
    assert preauth.active_for(tmp_path, t) is not None


def test_preauth_expires(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY, now=datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc))
    t = transition_key("deck-brief", "deck-planner")
    p = preauth.create(
        tmp_path, run_id="r", actor=BOSS, mode="preauthorized",
        allowed_transitions=[t], ttl_seconds=60,
    )
    # advance clock past expiry
    preauth2 = PreauthorizationRuntime(registry=REGISTRY, now=datetime(2026, 6, 24, 11, 0, tzinfo=timezone.utc))
    assert preauth2.active_for(tmp_path, t) is None


def test_preauth_revoked(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    t = transition_key("deck-brief", "deck-planner")
    p = preauth.create(tmp_path, run_id="r", actor=BOSS, mode="preauthorized", allowed_transitions=[t])
    preauth.revoke(tmp_path, p.policy_id, by_actor=BOSS)
    assert preauth.active_for(tmp_path, t) is None


def test_preauth_rejects_unknown_transition(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    with pytest.raises(PolicyError, match="unknown transition"):
        preauth.create(
            tmp_path, run_id="r", actor=BOSS, mode="preauthorized",
            allowed_transitions=["deck-foo->deck-bar"],
        )


# --- approval ---


def _brief_handoff(run: Path) -> str:
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(run, "deck-brief", run_id="r")
    return rec["handoff_id"]


def test_high_impact_transition_blocked_without_approval(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    _brief_handoff(tmp_path)
    cleared, reason = ap.is_transition_cleared(tmp_path, "deck-brief", run_id="r")
    assert cleared is False
    assert "approval required" in reason or "no handoff" in reason or "approved" in reason


def test_approve_clears_transition(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS)
    decision = ap.approve(tmp_path, req["approval_id"], actor=BOSS)
    assert decision["decision"] == APPROVED
    cleared, _ = ap.is_transition_cleared(tmp_path, "deck-brief", run_id="r")
    assert cleared is True


def test_reject_carries_repair_owner(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS)
    rejected = ap.reject(tmp_path, req["approval_id"], actor=BOSS, reason="bad narrative")
    assert rejected["decision"] == REJECTED
    # default repair owner is the rejected stage itself (go fix its output)
    assert rejected["repair_owner_stage"] == "deck-brief"
    assert rejected["reason"] == "bad narrative"


def test_preauth_clears_high_impact_transition(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    t = transition_key("deck-brief", "deck-planner")
    preauth.create(tmp_path, run_id="r", actor=BOSS, mode="preauthorized", allowed_transitions=[t])
    ap = ApprovalRuntime(registry=REGISTRY, preauth_runtime=preauth)
    _seed_brief(tmp_path)
    _brief_handoff(tmp_path)
    cleared, reason = ap.is_transition_cleared(tmp_path, "deck-brief", run_id="r")
    assert cleared is True
    assert "preauthorized" in reason


def test_approval_stale_on_fingerprint_change(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path, thesis="v1")
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS)
    ap.approve(tmp_path, req["approval_id"], actor=BOSS)
    # upstream change → new handoff with different fingerprint, old approval stale
    time.sleep(0.02)
    _seed_brief(tmp_path, thesis="v2")
    HandoffRuntime(registry=REGISTRY).prepare(tmp_path, "deck-brief", run_id="r")
    stale_ids = ap.refresh_stale(tmp_path)
    assert req["approval_id"] in stale_ids
    cleared, _ = ap.is_transition_cleared(tmp_path, "deck-brief", run_id="r")
    assert cleared is False  # old approval no longer clears


def test_revoke_invalidates_approval(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS)
    ap.approve(tmp_path, req["approval_id"], actor=BOSS)
    ap.revoke(tmp_path, req["approval_id"], actor=BOSS, reason="changed mind")
    cleared, _ = ap.is_transition_cleared(tmp_path, "deck-brief", run_id="r")
    assert cleared is False


def test_final_export_requires_human_approval(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_through_review(tmp_path)
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-review", run_id="r")
    assert rec["approval_policy"]["non_bypassable"] is True
    # not cleared without approval
    cleared, reason = ap.is_transition_cleared(tmp_path, "deck-review", run_id="r")
    assert cleared is False
    assert "human approval" in reason or "no handoff" in reason or "explicit" in reason


def test_final_export_cannot_be_preauthorized(tmp_path):
    preauth = PreauthorizationRuntime(registry=REGISTRY)
    ap = ApprovalRuntime(registry=REGISTRY, preauth_runtime=preauth)
    _seed_through_review(tmp_path)
    HandoffRuntime(registry=REGISTRY).prepare(tmp_path, "deck-review", run_id="r")
    # even with an attempt to preauth the export gate, it must fail (tested above)
    cleared, _ = ap.is_transition_cleared(tmp_path, "deck-review", run_id="r")
    assert cleared is False


def test_final_export_cleared_by_human_approval(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_through_review(tmp_path)
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-review", run_id="r")
    req = ap.request(tmp_path, rec["handoff_id"], run_id="r", actor=BOSS)
    ap.approve(tmp_path, req["approval_id"], actor=BOSS)
    cleared, _ = ap.is_transition_cleared(tmp_path, "deck-review", run_id="r")
    assert cleared is True


def test_final_export_preauth_id_rejected_on_approve(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_through_review(tmp_path)
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-review", run_id="r")
    req = ap.request(tmp_path, rec["handoff_id"], run_id="r", actor=BOSS)
    with pytest.raises(ApprovalError, match="final client export"):
        ap.approve(tmp_path, req["approval_id"], actor=BOSS, preauthorization_id="policy_fake")


def test_duplicate_decision_rejected(tmp_path):
    ap = ApprovalRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS)
    ap.approve(tmp_path, req["approval_id"], actor=BOSS)
    with pytest.raises(ApprovalError):
        ap.approve(tmp_path, req["approval_id"], actor=BOSS)


def test_expired_approval_blocked(tmp_path):
    past = datetime(2026, 6, 24, 10, 0, tzinfo=timezone.utc)
    ap = ApprovalRuntime(registry=REGISTRY, now=past)
    _seed_brief(tmp_path)
    hid = _brief_handoff(tmp_path)
    req = ap.request(tmp_path, hid, run_id="r", actor=BOSS, ttl_seconds=60)
    # advance clock
    ap2 = ApprovalRuntime(registry=REGISTRY, now=past + timedelta(hours=2))
    with pytest.raises(ApprovalError, match="expired"):
        ap2.approve(tmp_path, req["approval_id"], actor=BOSS)
