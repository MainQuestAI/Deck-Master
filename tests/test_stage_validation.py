"""Tests for the Stage entry/exit validator (A2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skills.manifest import load_registry  # noqa: E402
from workflow.validator import (  # noqa: E402
    artifact_present,
    resolve_artifact_files,
    validate_entry,
    validate_exit,
)

REGISTRY = load_registry()


def _touch(p: Path, content="{}") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_resolve_plain_filename(tmp_path):
    assert resolve_artifact_files(tmp_path, "deck_brief.json") == []
    _touch(tmp_path / "deck_brief.json")
    assert resolve_artifact_files(tmp_path, "deck_brief.json") == [tmp_path / "deck_brief.json"]


def test_resolve_glob_pattern(tmp_path):
    _touch(tmp_path / "page_packages" / "p1.json")
    _touch(tmp_path / "page_packages" / "p2.json")
    files = resolve_artifact_files(tmp_path, "page_packages/*.json")
    assert len(files) == 2


def test_resolve_directory_marker(tmp_path):
    assert resolve_artifact_files(tmp_path, "page_packages/") == []
    _touch(tmp_path / "page_packages" / "p1.json")
    assert len(resolve_artifact_files(tmp_path, "page_packages/")) == 1


def test_artifact_present_helper(tmp_path):
    assert artifact_present(tmp_path, "x.json") is False
    _touch(tmp_path / "x.json")
    assert artifact_present(tmp_path, "x.json") is True


def test_entry_blocks_when_previous_not_completed(tmp_path):
    contract = REGISTRY.contract("deck-brief")  # requires deck-init done
    report = validate_entry(contract, tmp_path, previous_completed=False)
    assert report.valid is False
    assert any("previous stage" in b for b in report.blockers)


def test_entry_passes_with_artifacts_and_previous(tmp_path):
    for f in ("deck_project.json", "material_inventory.json"):
        _touch(tmp_path / f)
    contract = REGISTRY.contract("deck-brief")
    report = validate_entry(contract, tmp_path, previous_completed=True)
    assert report.valid is True
    assert report.missing == []


def test_exit_detects_missing_outputs(tmp_path):
    contract = REGISTRY.contract("deck-init")
    report = validate_exit(contract, tmp_path)
    assert report.valid is False
    # missing deck_project.json, material_inventory.json, workspace_policy.json
    assert "deck_project.json" in report.missing


def test_exit_passes_when_all_outputs_present(tmp_path):
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(tmp_path / f)
    contract = REGISTRY.contract("deck-init")
    report = validate_exit(contract, tmp_path)
    assert report.valid is True


def test_exit_for_producer_accepts_page_package_dir(tmp_path):
    _touch(tmp_path / "page_packages" / "p1.json")
    contract = REGISTRY.contract("deck-producer")
    report = validate_exit(contract, tmp_path)
    assert report.valid is True
