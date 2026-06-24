"""Tests for the canonical Skill Manifest loader (A1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import (  # noqa: E402
    PRODUCTION_STAGE_IDS,
    ManifestError,
    load_registry,
)


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_manifest_version_is_1_1_0(registry):
    assert registry.manifest_version == "1.1.0"


def test_registry_exposes_public_skills(registry):
    names = {s.name for s in registry.public_skills()}
    for stage in PRODUCTION_STAGE_IDS:
        assert stage in names
    # the four ppt-* are private compatibility backends, not public
    assert "ppt-master" not in names


def test_resolve_by_name_and_alias(registry):
    assert registry.resolve("deck-planner").name == "deck-planner"
    assert registry.resolve("autoplan").name == "deck-planner"
    assert registry.resolve("ppt-master").name == "deck-builder"
    assert registry.resolve("render").name == "deck-builder"


def test_resolve_unknown_raises(registry):
    with pytest.raises(KeyError):
        registry.resolve("no-such-skill")


def test_alias_map_complete(registry):
    amap = registry.alias_map()
    assert amap["autoplan"] == "deck-planner"
    assert amap["ppt-library"] == "deck-sourcing"
    # no alias collides with a *public* skill name. Aliases may share a name
    # with a private compatibility backend (e.g. ppt-master is both a private
    # backend and a deck-builder compat alias).
    public_names = {s.name for s in registry.public_skills()}
    assert set(amap).isdisjoint(public_names)


def test_production_stages_have_contracts(registry):
    contracts = {c.stage_id for c in registry.ordered_contracts()}
    assert contracts == set(PRODUCTION_STAGE_IDS)


def test_contract_order_matches_production_ladder(registry):
    ordered = [c.stage_id for c in registry.ordered_contracts()]
    assert ordered == list(PRODUCTION_STAGE_IDS)


def test_high_impact_transitions_require_approval(registry):
    # D8: brief->planner, planner->sourcing, sourcing->producer need approval
    for stage in ("deck-brief", "deck-planner", "deck-sourcing"):
        assert registry.contract(stage).approval_required, stage


def test_client_export_is_non_bypassable_and_not_preauthorizable(registry):
    c = registry.contract("deck-review")
    assert c.approval_required
    assert c.non_bypassable
    assert not c.preauthorizable
    assert c.transition_policy["next_stage"] == "client_export"


def test_automatic_transitions_not_require_approval(registry):
    # D9: init->brief, producer->builder, builder->quality, quality->review auto
    for stage in ("deck-init", "deck-producer", "deck-builder", "deck-quality"):
        c = registry.contract(stage)
        assert c.transition_policy["mode"] == "automatic", stage
        assert not c.approval_required, stage


def test_contracts_hash_is_stable(registry):
    h1 = registry.contracts_hash
    h2 = load_registry().contracts_hash
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


# --- negative cases (corrupt the in-memory manifest and re-validate) ---


def _write(tmp_path: Path, manifest: dict, contracts: dict) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    docs_contracts = tmp_path / "docs" / "contracts"
    docs_contracts.mkdir(parents=True)
    (skills_dir / "manifest.json").write_text(json.dumps(manifest))
    (skills_dir / "stage-contracts.json").write_text(json.dumps(contracts))
    # copy the schema so validation runs
    schema_src = REPO_ROOT / "docs" / "contracts" / "stage-contract.v1.schema.json"
    (docs_contracts / "stage-contract.v1.schema.json").write_text(schema_src.read_text())
    return tmp_path


def _baseline_docs() -> tuple[dict, dict]:
    manifest = json.loads((REPO_ROOT / "skills" / "manifest.json").read_text())
    contracts = json.loads((REPO_ROOT / "skills" / "stage-contracts.json").read_text())
    return manifest, contracts


def _clone_contract(contracts_doc: dict, stage_id: str) -> dict:
    for c in contracts_doc["contracts"]:
        if c["stage_id"] == stage_id:
            return json.loads(json.dumps(c))
    raise KeyError(stage_id)


def test_duplicate_skill_name_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    manifest["skills"].append(dict(manifest["skills"][0]))  # duplicate deck-master
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="duplicate skill name"):
        load_registry(tmp_path)


def test_alias_collision_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    # give deck-doctor the same alias as deck-init
    for s in manifest["skills"]:
        if s["name"] == "deck-doctor":
            s["compat_aliases"] = ["init-workspace"]
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="alias collision"):
        load_registry(tmp_path)


def test_duplicate_stage_order_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    for c in contracts["contracts"]:
        if c["stage_id"] == "deck-learn":
            c["order"] = 1  # collides with deck-init
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="duplicate stage order"):
        load_registry(tmp_path)


def test_missing_production_stage_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    contracts["contracts"] = [
        c for c in contracts["contracts"] if c["stage_id"] != "deck-learn"
    ]
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="missing production stage|declares stage_id"):
        load_registry(tmp_path)


def test_bad_contract_schema_reference_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    # break schema: drop required field on a contract
    for c in contracts["contracts"]:
        if c["stage_id"] == "deck-init":
            del c["lane"]  # required by schema
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="invalid"):
        load_registry(tmp_path)


def test_manifest_stage_id_without_contract_rejected(tmp_path):
    manifest, contracts = _baseline_docs()
    # add a stage_id that has no matching contract
    for s in manifest["skills"]:
        if s["name"] == "deck-doctor":
            s["stage_id"] = "deck-doctor"
    _write(tmp_path, manifest, contracts)
    with pytest.raises(ManifestError, match="declares stage_id"):
        load_registry(tmp_path)
