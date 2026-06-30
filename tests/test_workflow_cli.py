"""Tests for the Skill OS workflow CLI (A5).

Exercises the ``deck-master workflow ...`` command group end-to-end through
the real CLI entrypoint, plus the four-state-entry consistency requirement
(run-state / next-step / route-skill / workflow status share current_skill_stage).
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import deck_master  # noqa: E402
from runtime.skill_route import (  # noqa: E402
    manifest_public_skills,
    route_for_input_type,
    route_for_skill_name,
)
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.questions import QuestionResolver  # noqa: E402
from skills.manifest import load_registry  # noqa: E402

DM = ["python", "deck_master.py"]  # not used; we call funcs directly
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
                actor={"id": "test", "role": "operator"},
                required=True,
                input_fingerprint=fp,
            )


def _seed_init(run: Path) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (run / f).write_text("{}\n", encoding="utf-8")
    _answer_required(run, "deck-init")


def _seed_brief(run: Path) -> None:
    _seed_init(run)
    (run / "deck_brief.json").write_text(json.dumps({"thesis": "x"}), encoding="utf-8")
    (run / "claim_map.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    _answer_required(run, "deck-brief")


def _run_cli(argv: list[str]) -> tuple[int, dict | None, str]:
    parser = deck_master.build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.func(args)
        return 0, payload, ""
    except SystemExit as exc:  # pragma: no cover
        return int(exc.code or 0), None, ""
    except Exception as exc:  # noqa: BLE001
        return 2, None, str(exc)


# --- workflow status / stages ---


def test_workflow_status_cli(tmp_path):
    _seed_init(tmp_path)
    code, payload, _ = _run_cli(["workflow", "status", "--run-dir", str(tmp_path), "--dev-allow-unsetup"])
    assert code == 0
    assert payload["schema_version"] == "deck_workflow_state.v1"
    assert payload["current_skill_stage"] == "deck-brief"  # init completed -> brief next
    assert len(payload["stages"]) == 9


def test_workflow_stages_cli(tmp_path):
    _seed_init(tmp_path)
    code, payload, _ = _run_cli(["workflow", "stages", "--run-dir", str(tmp_path), "--dev-allow-unsetup"])
    assert code == 0
    assert len(payload["stages"]) == 9
    assert payload["stages"][0]["stage_id"] == "deck-init"


# --- handoff cli ---


def test_workflow_handoff_prepare_and_list_cli(tmp_path):
    _seed_init(tmp_path)
    code, prep, _ = _run_cli(
        ["workflow", "handoff", "prepare", "--from-stage", "deck-init",
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    assert code == 0
    assert prep["from_stage"] == "deck-init"
    assert prep["status"] == "accepted"
    code, listed, _ = _run_cli(
        ["workflow", "handoff", "list", "--run-dir", str(tmp_path), "--dev-allow-unsetup"]
    )
    assert code == 0
    assert len(listed["handoffs"]) == 1


def test_workflow_handoff_prepare_refuses_on_invalid_exit_cli(tmp_path):
    code, _, err = _run_cli(
        ["workflow", "handoff", "prepare", "--from-stage", "deck-init",
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    assert code == 2  # exit-validation failure surfaces as error
    assert "exit validation" in err


def test_workflow_handoff_accept_reject_cli(tmp_path):
    _seed_brief(tmp_path)
    _, prep, _ = _run_cli(
        ["workflow", "handoff", "prepare", "--from-stage", "deck-brief",
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    assert prep["status"] == "awaiting_approval"
    code, acc, _ = _run_cli(
        ["workflow", "handoff", "accept", "--handoff-id", prep["handoff_id"],
         "--run-dir", str(tmp_path), "--dev-allow-unsetup"]
    )
    assert code == 0
    assert acc["status"] == "accepted"


# --- approval cli ---


def test_workflow_approval_request_approve_cli(tmp_path):
    _seed_brief(tmp_path)
    _, prep, _ = _run_cli(
        ["workflow", "handoff", "prepare", "--from-stage", "deck-brief",
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    code, req, _ = _run_cli(
        ["workflow", "approval", "request", "--handoff-id", prep["handoff_id"],
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    assert code == 0
    assert req["decision"] == "pending"
    code, dec, _ = _run_cli(
        ["workflow", "approval", "approve", "--approval-id", req["approval_id"],
         "--run-dir", str(tmp_path), "--dev-allow-unsetup"]
    )
    assert code == 0
    assert dec["decision"] == "approved"
    # transition now cleared
    code, status, _ = _run_cli(
        ["workflow", "approval", "status", "--from-stage", "deck-brief",
         "--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    )
    assert status["cleared"] is True


# --- preauth cli ---


def test_workflow_preauth_create_and_revoke_cli(tmp_path):
    code, pol, _ = _run_cli(
        ["workflow", "preauth", "create", "--run-dir", str(tmp_path), "--run-id", "r",
         "--mode", "preauthorized", "--allowed-transitions", "deck-brief->deck-planner",
         "--dev-allow-unsetup"]
    )
    assert code == 0
    assert pol["mode"] == "preauthorized"
    code, revoked, _ = _run_cli(
        ["workflow", "preauth", "revoke", "--policy-id", pol["policy_id"],
         "--run-dir", str(tmp_path), "--dev-allow-unsetup"]
    )
    assert code == 0
    assert revoked["revoked"] is True


def test_workflow_preauth_rejects_final_export_cli(tmp_path):
    code, _, err = _run_cli(
        ["workflow", "preauth", "create", "--run-dir", str(tmp_path), "--run-id", "r",
         "--mode", "preauthorized", "--allowed-transitions", "deck-review->client-export",
         "--dev-allow-unsetup"]
    )
    assert code == 2
    assert "non-bypassable" in err


# --- old commands still work (compat) ---


def test_route_skill_input_type_compat(tmp_path):
    code, payload, _ = _run_cli(["route-skill", "--input-type", "raw_materials"])
    assert code == 0
    assert payload["recommended_skill"] == "deck-brief"
    assert payload["source"] == "input_type"


def test_route_skill_alias_compat(tmp_path):
    # manifest-driven route resolves a compat alias
    payload = route_for_skill_name("autoplan")
    assert payload["recommended_skill"] == "deck-planner"
    assert payload["source"] == "manifest_skill_name"


# --- four-state-entry consistency ---


def test_four_state_entries_share_current_skill_stage(tmp_path):
    _seed_brief(tmp_path)
    common = ["--run-dir", str(tmp_path), "--run-id", "r", "--dev-allow-unsetup"]
    _, rs, _ = _run_cli(["run-state"] + common)
    _, ns, _ = _run_cli(["next-step"] + common)
    _, rt, _ = _run_cli(["route-skill"] + common)
    _, wf, _ = _run_cli(["workflow", "status"] + common)
    stage = wf["current_skill_stage"]
    assert stage  # non-empty
    assert rs["current_skill_stage"] == stage
    assert ns["current_skill_stage"] == stage
    assert rt["current_skill_stage"] == stage


# --- manifest-driven route ---


def test_manifest_public_skills_complete():
    skills = set(manifest_public_skills())
    for stage in ("deck-init", "deck-brief", "deck-planner", "deck-sourcing",
                  "deck-producer", "deck-builder", "deck-quality", "deck-review",
                  "deck-learn"):
        assert stage in skills


def test_route_for_skill_name_resolves_aliases():
    assert route_for_skill_name("ppt-master")["recommended_skill"] == "deck-builder"
    assert route_for_skill_name("render")["recommended_skill"] == "deck-builder"
    assert route_for_skill_name("ppt-library")["recommended_skill"] == "deck-sourcing"


def test_route_for_skill_name_unknown_falls_back():
    payload = route_for_skill_name("no-such-skill")
    assert payload["recommended_skill"] == "deck-master"


def test_route_for_input_type_unchanged():
    # existing behavior preserved
    assert route_for_input_type("raw_materials")["recommended_skill"] == "deck-brief"
    assert route_for_input_type("approved_preview")["recommended_skill"] == "deck-builder"
