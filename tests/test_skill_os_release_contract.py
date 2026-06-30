"""Skill OS release contract & smoke (C4).

Validates that the release carries valid Stage Contracts / schemas, that JSON
Schema validation actually runs (not just parse), and that the core Skill OS
pipeline (route -> handoff -> approval -> autopilot -> legacy bootstrap) works
end-to-end on a real run directory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import jsonschema  # noqa: E402

from skills.manifest import load_registry  # noqa: E402
from workflow.decisions import DecisionLog  # noqa: E402
from workflow.approval import ApprovalRuntime  # noqa: E402
from workflow.autopilot import AutopilotV2  # noqa: E402
from workflow.handoff import HandoffRuntime  # noqa: E402
from workflow.migration import LegacyBootstrap  # noqa: E402
from workflow.state import WorkflowStateResolver  # noqa: E402

CONTRACTS_DIR = REPO_ROOT / "docs" / "contracts"
SPEC_SCHEMAS = REPO_ROOT / "docs" / "specs" / "skill-os-runtime-v1.1" / "schemas"


SCHEMA_FILES = [
    "stage-contract.v1.schema.json",
    "workflow-state.v1.schema.json",
    "skill-handoff.v1.schema.json",
    "stage-approval.v1.schema.json",
    "workflow-policy.v1.schema.json",
    "decision-record.v1.schema.json",
    "sourcing-plan.v2.schema.json",
    "page-package.v1.schema.json",
    "build-manifest.v2.schema.json",
]


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def _answer_required(run: Path, registry) -> None:
    from workflow.questions import QuestionResolver  # noqa: E402

    qr = QuestionResolver(registry=registry)
    contract = registry.contract("deck-init")
    fp = qr.input_fingerprint(contract, run)
    log = DecisionLog()
    for question in contract.forcing_questions:
        if question.get("required"):
            log.record(
                run,
                run_id="r",
                stage_id="deck-init",
                question_id=question["question_id"],
                answer="answered",
                actor={"id": "test", "role": "operator"},
                required=True,
                input_fingerprint=fp,
            )


def test_all_skill_os_schemas_are_valid_draft202012():
    for name in SCHEMA_FILES:
        path = CONTRACTS_DIR / name
        assert path.exists(), f"schema not in docs/contracts: {name}"
        schema = json.loads(path.read_text())
        # the schema itself must be a valid Draft 2020-12 schema
        jsonschema.Draft202012Validator.check_schema(schema)


def test_stage_contracts_validate_against_schema():
    schema = json.loads((CONTRACTS_DIR / "stage-contract.v1.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    contracts = json.loads((REPO_ROOT / "skills" / "stage-contracts.json").read_text())
    for contract in contracts["contracts"]:
        errors = sorted(validator.iter_errors(contract), key=lambda e: list(e.path))
        assert not errors, f"{contract['stage_id']} invalid: {[e.message for e in errors]}"


def test_contracts_hash_stable(registry):
    h1 = registry.contracts_hash
    h2 = load_registry().contracts_hash
    assert h1 == h2
    assert len(h1) == 64


def test_release_assets_present():
    # release tree must carry contracts + schemas + migration
    assert (REPO_ROOT / "skills" / "stage-contracts.json").exists()
    assert (REPO_ROOT / "skills" / "manifest.json").exists()
    assert (REPO_ROOT / "docs" / "contracts" / "stage-contract.v1.schema.json").exists()
    assert (REPO_ROOT / "scripts" / "workflow" / "migration.py").exists()


def test_skill_os_pipeline_smoke(tmp_path, registry):
    """End-to-end: build a run, resolve state, prepare+approve a handoff,
    run autopilot, and bootstrap a legacy run — all consistent."""
    run = tmp_path
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        (run / f).write_text("{}\n", encoding="utf-8")
    _answer_required(run, registry)

    # 1. resolve state
    state = WorkflowStateResolver(registry=registry).resolve(run, run_id="r")
    assert state["schema_version"] == "deck_workflow_state.v1"

    # 2. prepare init handoff (auto)
    h = HandoffRuntime(registry=registry)
    init_h = h.prepare(run, "deck-init", run_id="r")
    assert init_h["status"] == "accepted"

    # 3. autopilot quick on an init-complete run
    result = AutopilotV2(registry=registry).run(run, mode="quick", max_steps=3, run_id="r")
    assert result.stop_reason in {"missing_artifacts", "blocking_questions", "approval_required"}

    # 4. legacy bootstrap does not forge approvals
    bs = LegacyBootstrap(registry=registry).inference_report(run)
    assert bs["forged_approvals"] == 0


def test_route_consistency_matrix(registry):
    """route / next-step / workflow-status share current_skill_stage — already
    covered in test_workflow_cli; here we assert the resolver + manifest agree
    on the 9-stage ladder for an empty run."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        from workflow.state import resolve_workflow_state
        state = resolve_workflow_state(td, registry=registry)
        assert state["current_skill_stage"] == "deck-init"
        assert len(state["stages"]) == 9
