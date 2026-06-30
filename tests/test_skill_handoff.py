"""Tests for the Skill Handoff Runtime (A3)."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.handoff import (  # noqa: E402
    ACCEPTED,
    AWAITING_APPROVAL,
    CONSUMED,
    HandoffError,
    HandoffRuntime,
    SUPERSEDED,
)

REGISTRY = load_registry()


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
                actor={"id": "test", "role": "operator"},
                required=True,
                input_fingerprint=fp,
            )


def _seed_init(run: Path, *, answer: bool = True) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (run / f).write_text("{}\n", encoding="utf-8")
    if answer:
        _answer_required(run, "deck-init")


def _seed_brief(run: Path, *, thesis="t", answer: bool = True) -> None:
    _seed_init(run)
    (run / "deck_brief.json").write_text(json.dumps({"thesis": thesis}), encoding="utf-8")
    (run / "claim_map.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    if answer:
        _answer_required(run, "deck-brief")


def test_prepare_refuses_when_exit_validation_fails(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    # no init artifacts → deck-init exit invalid
    with pytest.raises(HandoffError, match="exit validation failed"):
        rt.prepare(tmp_path, "deck-init", run_id="r")


def test_prepare_creates_handoff_for_init(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    rec = rt.prepare(tmp_path, "deck-init", run_id="r")
    assert rec["from_stage"] == "deck-init"
    assert rec["to_stage"] == "deck-brief"
    assert rec["status"] == ACCEPTED  # init is automatic
    assert rec["approval_policy"]["required"] is False
    # output fingerprint present and 64-hex
    assert len(rec["output_fingerprint"]) == 64
    # written to handoffs dir
    assert (tmp_path / "workflow/handoffs" / f'{rec["handoff_id"]}.json').exists()


def test_prepare_brief_is_awaiting_approval(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    rec = rt.prepare(tmp_path, "deck-brief", run_id="r")
    assert rec["status"] == AWAITING_APPROVAL
    assert rec["approval_policy"]["required"] is True


def test_prepare_brief_blocks_when_forcing_questions_unanswered(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path, answer=False)
    with pytest.raises(HandoffError, match="blocking"):
        rt.prepare(tmp_path, "deck-brief", run_id="r")


def test_idempotent_prepare_returns_same(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    a = rt.prepare(tmp_path, "deck-brief", run_id="r")
    b = rt.prepare(tmp_path, "deck-brief", run_id="r")
    assert a["handoff_id"] == b["handoff_id"]
    assert a["idempotency_key"] == b["idempotency_key"]
    # only one handoff file
    files = list((tmp_path / "workflow/handoffs").glob("*.json"))
    assert len([f for f in files if f.name != ".handoff.lock"]) == 1


def test_supersede_on_upstream_change_retains_old(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path, thesis="v1")
    first = rt.prepare(tmp_path, "deck-brief", run_id="r")
    # upstream change → different fingerprint
    time.sleep(0.02)
    _seed_brief(tmp_path, thesis="v2")
    second = rt.prepare(tmp_path, "deck-brief", run_id="r")
    assert second["handoff_id"] != first["handoff_id"]
    assert second.get("supersedes") == first["handoff_id"]
    # old record retained and marked superseded
    old = rt.inspect(tmp_path, first["handoff_id"])
    assert old["status"] == SUPERSEDED


def test_accept_consume_lifecycle(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    rec = rt.prepare(tmp_path, "deck-brief", run_id="r")
    assert rec["status"] == AWAITING_APPROVAL
    accepted = rt.accept(tmp_path, rec["handoff_id"], actor="boss")
    assert accepted["status"] == ACCEPTED
    assert accepted["accepted_by"] == "boss"
    consumed = rt.consume(tmp_path, rec["handoff_id"])
    assert consumed["status"] == CONSUMED


def test_reject_carries_repair_owner(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    rec = rt.prepare(tmp_path, "deck-brief", run_id="r")
    rejected = rt.reject(
        tmp_path, rec["handoff_id"], reason="narrative wrong", repair_owner_stage="deck-planner"
    )
    assert rejected["status"] == "rejected"
    assert rejected["repair_owner_stage"] == "deck-planner"
    assert rejected["rejected_reason"] == "narrative wrong"


def test_accept_rejects_invalid_transition(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_brief(tmp_path)
    rec = rt.prepare(tmp_path, "deck-brief", run_id="r")
    rt.accept(tmp_path, rec["handoff_id"], actor="x")
    # cannot accept again from ACCEPTED
    with pytest.raises(HandoffError):
        rt.accept(tmp_path, rec["handoff_id"], actor="x")


def test_current_is_projection_only(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    rec = rt.prepare(tmp_path, "deck-init", run_id="r")
    proj = rt.current(tmp_path)
    assert proj is not None
    assert proj["handoff_id"] == rec["handoff_id"]
    # direct edit of current_handoff.json does not change truth source
    (tmp_path / "workflow/current_handoff.json").write_text(
        json.dumps({"handoff_id": "fake", "status": ACCEPTED}), encoding="utf-8"
    )
    # but a re-prepare recomputes projection from the handoffs dir
    rt.prepare(tmp_path, "deck-init", run_id="r")  # idempotent
    # projection must reflect the real latest, not the tampered value
    proj2 = HandoffRuntime(registry=REGISTRY).current(tmp_path)
    assert proj2["handoff_id"] == rec["handoff_id"]


def test_list_and_inspect(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    rec = rt.prepare(tmp_path, "deck-init", run_id="r")
    items = rt.list(tmp_path)
    assert len(items) == 1
    got = rt.inspect(tmp_path, rec["handoff_id"])
    assert got["handoff_id"] == rec["handoff_id"]
    with pytest.raises(HandoffError):
        rt.inspect(tmp_path, "no-such-handoff")


def test_concurrent_prepare_is_safe(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    results: list[dict] = []
    errors: list[BaseException] = []

    def worker():
        try:
            results.append(rt.prepare(tmp_path, "deck-init", run_id="r"))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # no matter the interleaving, exactly one handoff file (idempotent)
    files = [f for f in (tmp_path / "workflow/handoffs").glob("*.json")]
    assert len(files) == 1
    assert not errors


def test_corrupt_handoff_file_ignored_by_list(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    rt.prepare(tmp_path, "deck-init", run_id="r")
    bad = tmp_path / "workflow/handoffs" / "corrupt.json"
    bad.write_text("{ not json", encoding="utf-8")
    items = rt.list(tmp_path)
    # corrupt file ignored, valid one still returned
    assert len(items) == 1


def test_bad_hash_on_artifact_ref_recomputed(tmp_path):
    rt = HandoffRuntime(registry=REGISTRY)
    _seed_init(tmp_path)
    rec = rt.prepare(tmp_path, "deck-init", run_id="r")
    # tamper with stored sha256 on one artifact ref
    path = tmp_path / "workflow/handoffs" / f'{rec["handoff_id"]}.json'
    data = json.loads(path.read_text())
    data["output_artifacts"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    # recompute fingerprint should differ; preparing again with same files is idempotent by fingerprint
    again = rt.prepare(tmp_path, "deck-init", run_id="r")
    assert again["handoff_id"] == rec["handoff_id"]  # idempotent
