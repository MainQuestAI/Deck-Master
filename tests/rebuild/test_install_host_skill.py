"""T9: Codex skill registration, rollback and legacy companion migration.

Everything runs against an isolated CODEX_HOME / prefix — never the real
``~/.codex/skills``. Releases are fabricated (release.json + skill tree +
venv/bin launcher shims are not needed for activation-level tests).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from deck_master import install
from deck_master.errors import HostSkillConflict


def _make_release(prefix: Path, release_id: str, *, with_skill: bool = True) -> Path:
    release = prefix / ".deck-master" / "releases" / release_id
    release.mkdir(parents=True, exist_ok=True)
    (release / "release.json").write_text(json.dumps({"status": "candidate_ready",
                                                      "release_id": release_id}))
    if with_skill:
        skill = release / "skill" / "deck-master"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            "---\nname: deck-master\ndescription: synthetic release skill\n---\n\n# Deck Master\n",
            encoding="utf-8")
    return release


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    return {"tmp": tmp_path, "prefix": tmp_path / "prefix", "codex": tmp_path / "codex-home"}


def test_fresh_activation_registers_managed_link(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _make_release(prefix, "r1")
    result = install.activate(prefix, "r1")
    link = codex / "skills" / "deck-master"
    assert result["cli_active"] is True
    assert result["host_skill"] == "registered"
    assert os.readlink(link) == str(prefix / ".deck-master" / "current" / "skill" / "deck-master")
    assert (link / "SKILL.md").is_file(), "the linked SKILL.md must be readable"
    assert result["skill_release_id"] == "r1"


def test_occupied_skill_path_refused_before_current_switch(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _make_release(prefix, "r1")
    _make_release(prefix, "r2")
    install.activate(prefix, "r1")
    # The user (or another tool) replaced the managed link with a real directory.
    link = codex / "skills" / "deck-master"
    link.unlink()
    link.mkdir()
    with pytest.raises(HostSkillConflict) as exc:
        install.activate(prefix, "r2")
    assert "deck-master" in exc.value.path
    assert os.readlink(prefix / ".deck-master" / "current") == "releases/r1", \
        "current must not switch when the host path conflicts"


def test_foreign_symlink_refused(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    other = isolated["tmp"] / "other-skill"
    other.mkdir()
    (codex / "skills").mkdir(parents=True)
    os.symlink(other, codex / "skills" / "deck-master")
    _make_release(prefix, "r1")
    with pytest.raises(HostSkillConflict):
        install.activate(prefix, "r1")
    assert not (prefix / ".deck-master" / "current").exists()


def test_no_host_registration_reports_separately(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _make_release(prefix, "r1")
    result = install.activate(prefix, "r1", register_host=False)
    assert result["cli_active"] is True
    assert result["host_skill"] == "host_unregistered"
    assert not (codex / "skills" / "deck-master").exists()


def test_rollback_to_skillless_release_retires_link(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _make_release(prefix, "new", with_skill=True)
    _make_release(prefix, "old", with_skill=False)
    install.activate(prefix, "old")   # skillless old core first
    install.activate(prefix, "new")   # previous=old, current=new, link registered
    link = codex / "skills" / "deck-master"
    assert link.is_symlink()
    result = install.rollback(prefix)
    assert result["host_skill"] == "host_skill_unregistered"
    assert not link.exists(), "no dangling link may remain"
    assert os.readlink(prefix / ".deck-master" / "current") == "releases/old"
    # Coming back re-registers automatically.
    result = install.rollback(prefix)
    assert result["host_skill"] == "registered"
    assert os.readlink(link) == str(prefix / ".deck-master" / "current" / "skill" / "deck-master")


def _build_legacy_layout(prefix: Path, codex: Path) -> None:
    current = prefix / ".deck-master" / "current"
    current.mkdir(parents=True)
    (current / "companion-manifest.json").write_text(json.dumps({
        "schema_version": 3,
        "adoption_policy": "bundled_symlink_only",
        "release": "main-cc8cf46",
    }))
    skills = codex / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    for index in range(15):
        name = f"deck-legacy-{index}" if index else "deck-master"
        os.symlink(str(prefix / ".deck-master" / "current" / "skills" / name), skills / name)
    # A dangling deck-* link pointing elsewhere and a third-party skill: untouched.
    os.symlink("/nonexistent/elsewhere/deck-x", skills / "deck-foreign-target")
    os.symlink("/nonexistent/gstack", skills / "gstack-something")
    (skills / "artifact-template-demo").mkdir()


def test_legacy_companion_migration_moves_and_prunes(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _build_legacy_layout(prefix, codex)
    _make_release(prefix, "r1")
    result = install.activate(prefix, "r1")
    migration = result["migration"]
    assert migration["migrated"] is True
    legacy = Path(migration["moved"]["to"])
    assert legacy.is_dir() and (legacy / "companion-manifest.json").is_file()
    removed = set(migration["removed_links"])
    assert "deck-master" in removed and len(removed) == 15
    assert len([name for name in removed if name.startswith("deck-legacy-")]) == 14
    skills = codex / "skills"
    assert "deck-foreign-target" in migration["skipped_entries"]
    assert "gstack-something" in migration["skipped_entries"]
    assert "artifact-template-demo" in migration["skipped_entries"]
    assert (skills / "deck-foreign-target").is_symlink()
    assert (skills / "gstack-something").is_symlink()
    assert (skills / "artifact-template-demo").is_dir()
    link = skills / "deck-master"
    assert os.readlink(link) == str(prefix / ".deck-master" / "current" / "skill" / "deck-master")
    # Idempotent: a rerun migrates nothing and keeps the same link.
    again = install.activate(prefix, "r1")
    assert again["migration"]["migrated"] is False
    assert again["migration"]["removed_links"] == []
    assert os.readlink(link) == str(prefix / ".deck-master" / "current" / "skill" / "deck-master")


def test_user_owned_current_without_manifest_is_refused(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    current = prefix / ".deck-master" / "current"
    (current / "subdir").mkdir(parents=True)
    (current / "subdir" / "keep.txt").write_text("user data", encoding="utf-8")
    _make_release(prefix, "r1")
    with pytest.raises(HostSkillConflict):
        install.activate(prefix, "r1")
    assert (current / "subdir" / "keep.txt").is_file(), "user-owned current is untouched"
    assert not (prefix / ".deck-master" / "current.json").exists()
    assert (prefix / ".deck-master" / "current").is_dir() and \
        not (prefix / ".deck-master" / "current").is_symlink(), "current was not switched"


def test_unknown_companion_manifest_is_refused(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    current = prefix / ".deck-master" / "current"
    current.mkdir(parents=True)
    (current / "companion-manifest.json").write_text(json.dumps({
        "schema_version": 99, "adoption_policy": "something_else"}))
    _make_release(prefix, "r1")
    with pytest.raises(HostSkillConflict):
        install.activate(prefix, "r1")
    assert (current / "companion-manifest.json").is_file()


def test_skillless_release_activation_reports_unregistered(isolated) -> None:
    prefix, codex = isolated["prefix"], isolated["codex"]
    _make_release(prefix, "oldcore", with_skill=False)
    result = install.activate(prefix, "oldcore")
    assert result["cli_active"] is True
    assert result["host_skill"] == "host_skill_unregistered"
    assert not (codex / "skills" / "deck-master").exists()
