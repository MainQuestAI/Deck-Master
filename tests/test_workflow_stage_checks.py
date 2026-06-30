from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from planning.brief_intake import build_request  # noqa: E402
from planning.narrative_planner import plan_narrative  # noqa: E402
from skills.manifest import load_registry  # noqa: E402
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.questions import QuestionResolver  # noqa: E402

REGISTRY = load_registry()


def _answer_required(run: Path, stage_id: str) -> None:
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
                actor={"id": "boss", "role": "approver"},
                required=True,
                input_fingerprint=fp,
            )


def test_planner_exit_blocked_when_required_modules_missing(tmp_path):
    request = build_request(brief="短版企业方案", industry="enterprise", target_pages="3")
    plan = plan_narrative(request)
    (tmp_path / "narrative_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "page_tasks.json").write_text(json.dumps({"tasks": []}, ensure_ascii=False), encoding="utf-8")
    _answer_required(tmp_path, "deck-planner")

    validation = QuestionResolver(registry=REGISTRY).exit_validation(tmp_path, "deck-planner")

    assert validation.valid is False
    modules_check = next(item for item in validation.checks if item["check"] == "required_modules_coverage")
    assert modules_check["status"] == "fail"
    assert "平台规划/架构" in modules_check["missing_modules"]


def test_sourcing_exit_blocked_when_authority_permission_unconfirmed(tmp_path):
    sourcing_plan = {
        "schema_version": "deck_sourcing_plan.v2",
        "run_id": "r",
        "pages": [
            {
                "page_id": "p1",
                "decision": "reuse",
                "reason": "history fit",
                "source_authority": "unknown",
                "freshness_status": "pending",
                "permission_status": "pending",
                "selected_sources": [{"slide_id": "s1"}],
            }
        ],
    }
    (tmp_path / "sourcing_plan.json").write_text(json.dumps(sourcing_plan, ensure_ascii=False), encoding="utf-8")
    _answer_required(tmp_path, "deck-sourcing")

    validation = QuestionResolver(registry=REGISTRY).exit_validation(tmp_path, "deck-sourcing")

    assert validation.valid is False
    integrity = next(item for item in validation.checks if item["check"] == "sourcing_risk_closure")
    assert integrity["status"] == "fail"
    assert integrity["authority_gap_pages"] == ["p1"]
    assert integrity["permission_gap_pages"] == ["p1"]
