"""Tests for Forcing Questions & Decision Log (B1)."""
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
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.questions import QuestionResolver  # noqa: E402

REGISTRY = load_registry()


def _seed_brief_inputs(run: Path) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (run / f).write_text("{}\n", encoding="utf-8")
    (run / "deck_brief.json").write_text(json.dumps({"thesis": "x"}), encoding="utf-8")
    (run / "claim_map.json").write_text(json.dumps({"c": []}), encoding="utf-8")


def test_no_question_gaps_when_all_required_answered(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    fp0 = qr.input_fingerprint(contract, tmp_path)
    # answer all required questions for deck-brief
    dl = DecisionLog()
    for q in contract.forcing_questions:
        if q["required"]:
            dl.record(
                tmp_path, run_id="r", stage_id="deck-brief",
                question_id=q["question_id"], answer="ans",
                actor={"id": "boss", "role": "approver"},
                required=True,
                assumption_allowed=bool(q.get("assumption_allowed", False)),
                input_fingerprint=fp0,
            )
    gaps = qr.gaps(tmp_path, "deck-brief")
    assert gaps == []
    ev = qr.exit_validation(tmp_path, "deck-brief")
    assert ev.valid is True
    assert ev.blocking == []


def test_required_unanswered_blocks_exit(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    ev = qr.exit_validation(tmp_path, "deck-brief")
    assert ev.valid is False
    # blocking_questions check failed
    blk = [c for c in ev.checks if c["check"] == "blocking_questions"][0]
    assert blk["status"] == "fail"
    assert len(blk["open"]) >= 1
    # the gap is required, not assumption-only
    gaps = qr.gaps(tmp_path, "deck-brief")
    assert all(g.required for g in gaps)


def test_only_gap_questions_returned(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    fp0 = qr.input_fingerprint(contract, tmp_path)
    dl = DecisionLog()
    # answer the first required question only
    first_req = next(q for q in contract.forcing_questions if q["required"])
    dl.record(
        tmp_path, run_id="r", stage_id="deck-brief",
        question_id=first_req["question_id"], answer="ans",
        actor={"id": "boss", "role": "approver"},
        required=True, input_fingerprint=fp0,
    )
    gaps = qr.gaps(tmp_path, "deck-brief")
    ids = {g.question_id for g in gaps}
    assert first_req["question_id"] not in ids
    # other required questions still present
    assert len(ids) >= 1


def test_assumption_allowed_distinguishable(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    # at least one brief question allows assumption
    assumption_qs = [q for q in contract.forcing_questions if q.get("assumption_allowed")]
    assert assumption_qs  # brief has assumption_allowed questions per A1 contracts


def test_stale_answer_resurfaces_as_gap(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    fp0 = qr.input_fingerprint(contract, tmp_path)
    dl = DecisionLog()
    for q in contract.forcing_questions:
        if q["required"]:
            dl.record(
                tmp_path, run_id="r", stage_id="deck-brief",
                question_id=q["question_id"], answer="ans",
                actor={"id": "boss", "role": "approver"},
                required=True, input_fingerprint=fp0,
            )
    assert qr.gaps(tmp_path, "deck-brief") == []
    # upstream change: modify an INPUT artifact of deck-brief
    time.sleep(0.02)
    (tmp_path / "material_inventory.json").write_text(json.dumps({"changed": True}), encoding="utf-8")
    gaps = qr.gaps(tmp_path, "deck-brief")
    assert len(gaps) >= 1
    assert all(g.stale for g in gaps)  # all resurfaced gaps are stale


def test_decision_log_append_only(tmp_path):
    dl = DecisionLog()
    for i in range(3):
        dl.record(
            tmp_path, run_id="r", stage_id="deck-brief",
            question_id="brief.decision_object", answer=f"a{i}",
            actor={"id": "boss", "role": "approver"},
            required=True, input_fingerprint="x" * 64,
        )
    log = (tmp_path / "workflow/decision_log.jsonl").read_text().strip().splitlines()
    assert len(log) == 3  # append-only, no overwrite
    latest = dl.latest(tmp_path, "deck-brief", "brief.decision_object")
    assert latest["answer"] == "a2"


def test_vague_answer_triggers_follow_up(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    fp0 = qr.input_fingerprint(contract, tmp_path)
    dl = DecisionLog()
    dl.record(
        tmp_path,
        run_id="r",
        stage_id="deck-brief",
        question_id="brief.decision_object",
        answer="待定",
        actor={"id": "boss", "role": "approver"},
        required=True,
        input_fingerprint=fp0,
    )
    gap = next(g for g in qr.gaps(tmp_path, "deck-brief") if g.question_id == "brief.decision_object")
    assert gap.answer_status == "needs_follow_up"
    assert gap.challenge_round == 1


def test_second_vague_answer_escalates_to_human_judgment(tmp_path):
    _seed_brief_inputs(tmp_path)
    qr = QuestionResolver(registry=REGISTRY)
    contract = REGISTRY.contract("deck-brief")
    fp0 = qr.input_fingerprint(contract, tmp_path)
    dl = DecisionLog()
    for _ in range(2):
        dl.record(
            tmp_path,
            run_id="r",
            stage_id="deck-brief",
            question_id="brief.decision_object",
            answer="都可以",
            actor={"id": "boss", "role": "approver"},
            required=True,
            input_fingerprint=fp0,
        )
    gap = next(g for g in qr.gaps(tmp_path, "deck-brief") if g.question_id == "brief.decision_object")
    assert gap.answer_status == "needs_human_judgment"
    assert gap.challenge_round == 2


def test_no_question_happy_path_for_init(tmp_path):
    # deck-init has no required forcing questions in the contract? it has
    # init.scan_scope + init.privacy_boundary required. Verify they surface.
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (tmp_path / f).write_text("{}\n", encoding="utf-8")
    qr = QuestionResolver(registry=REGISTRY)
    ev = qr.exit_validation(tmp_path, "deck-init")
    # artifacts present but required questions unanswered -> blocked
    assert ev.valid is False
    assert "init.scan_scope" in ev.blocking
