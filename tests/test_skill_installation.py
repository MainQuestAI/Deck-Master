"""Tests for Package A — Skill Packaging & Installation."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.skills.installer import (
    SKILL_NAME,
    SkillInstallError,
    install_skill,
    uninstall_skill,
    validate_skill,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillInstallationTest(unittest.TestCase):
    """Skill install / validate / uninstall against a temp agent skill dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_skill_test_")
        self.agent_dir = Path(self._tmp) / "agent_skills"
        self.agent_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # install_skill
    # ------------------------------------------------------------------ #

    def test_install_creates_symlink(self) -> None:
        result = install_skill("codex", str(self.agent_dir))
        self.assertEqual(result["status"], "installed")
        link = self.agent_dir / SKILL_NAME
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), _REPO_ROOT / "skills" / SKILL_NAME)

    def test_install_idempotent(self) -> None:
        install_skill("codex", str(self.agent_dir))
        result = install_skill("codex", str(self.agent_dir))
        self.assertEqual(result["status"], "already_installed")

    def test_install_creates_parent_dir_if_missing(self) -> None:
        nested = self.agent_dir / "nested" / "path"
        result = install_skill("codex", str(nested))
        self.assertEqual(result["status"], "installed")
        self.assertTrue((nested / SKILL_NAME).is_symlink())

    def test_install_existing_real_dir_blocks(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("codex", str(self.agent_dir))
        self.assertIn("real file or directory", str(ctx.exception))

    def test_install_force_replaces_symlink(self) -> None:
        # Create a symlink to somewhere else.
        other = Path(self._tmp) / "other_skill"
        other.mkdir()
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        # Without --force should fail.
        with self.assertRaises(SkillInstallError):
            install_skill("codex", str(self.agent_dir))
        # With --force should replace.
        result = install_skill("codex", str(self.agent_dir), force=True)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(link.resolve(), _REPO_ROOT / "skills" / SKILL_NAME)

    def test_install_force_does_not_delete_real_dir(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        (real / "marker.txt").write_text("keep me", encoding="utf-8")
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("codex", str(self.agent_dir), force=True)
        self.assertIn("real directory", str(ctx.exception))
        # Directory should still be intact.
        self.assertTrue((real / "marker.txt").exists())

    def test_install_unsupported_target(self) -> None:
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("unknown-agent", str(self.agent_dir))
        self.assertIn("Unsupported target", str(ctx.exception))

    def test_install_custom_target_requires_explicit_dir(self) -> None:
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("custom", None)
        self.assertIn("--agent-skill-dir", str(ctx.exception))

    def test_install_custom_target_with_explicit_dir(self) -> None:
        result = install_skill("custom", str(self.agent_dir))
        self.assertEqual(result["status"], "installed")

    # ------------------------------------------------------------------ #
    # validate_skill
    # ------------------------------------------------------------------ #

    def test_validate_after_install(self) -> None:
        install_skill("codex", str(self.agent_dir))
        result = validate_skill("codex", str(self.agent_dir))
        self.assertTrue(result["valid"])
        self.assertTrue(result["skill_md_exists"])

    def test_validate_not_installed(self) -> None:
        result = validate_skill("codex", str(self.agent_dir))
        self.assertFalse(result["valid"])
        self.assertIn("not exist", result["error"])

    def test_validate_wrong_target(self) -> None:
        # Symlink to wrong location.
        other = Path(self._tmp) / "wrong_skill"
        other.mkdir()
        (other / "SKILL.md").write_text("wrong", encoding="utf-8")
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        result = validate_skill("codex", str(self.agent_dir))
        self.assertFalse(result["valid"])
        self.assertIn("expected", result.get("error", ""))

    def test_validate_unsupported_target(self) -> None:
        result = validate_skill("bad-agent", str(self.agent_dir))
        self.assertFalse(result["valid"])
        self.assertIn("Unsupported", result["error"])

    # ------------------------------------------------------------------ #
    # uninstall_skill
    # ------------------------------------------------------------------ #

    def test_uninstall_after_install(self) -> None:
        install_skill("codex", str(self.agent_dir))
        result = uninstall_skill("codex", str(self.agent_dir))
        self.assertEqual(result["status"], "uninstalled")
        self.assertFalse((self.agent_dir / SKILL_NAME).exists())

    def test_uninstall_not_installed(self) -> None:
        result = uninstall_skill("codex", str(self.agent_dir))
        self.assertEqual(result["status"], "not_installed")

    def test_uninstall_refuses_real_dir(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        with self.assertRaises(SkillInstallError) as ctx:
            uninstall_skill("codex", str(self.agent_dir))
        self.assertIn("not a symlink", str(ctx.exception))

    def test_uninstall_refuses_foreign_symlink(self) -> None:
        other = Path(self._tmp) / "foreign_skill"
        other.mkdir()
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        with self.assertRaises(SkillInstallError) as ctx:
            uninstall_skill("codex", str(self.agent_dir))
        self.assertIn("not the Deck Master skill", str(ctx.exception))

    def test_uninstall_unsupported_target(self) -> None:
        with self.assertRaises(SkillInstallError):
            uninstall_skill("bad-agent", str(self.agent_dir))

    # ------------------------------------------------------------------ #
    # SKILL.md exists in repo
    # ------------------------------------------------------------------ #

    def test_skill_md_exists_in_repo(self) -> None:
        skill_md = _REPO_ROOT / "skills" / SKILL_NAME / "SKILL.md"
        self.assertTrue(skill_md.exists(), f"SKILL.md not found at {skill_md}")

    def test_agents_md_exists_in_repo(self) -> None:
        agents_md = _REPO_ROOT / "skills" / SKILL_NAME / "AGENTS.md"
        self.assertTrue(agents_md.exists(), f"AGENTS.md not found at {agents_md}")

    # ------------------------------------------------------------------ #
    # Playbooks exist
    # ------------------------------------------------------------------ #

    def test_playbooks_exist(self) -> None:
        playbooks_dir = _REPO_ROOT / "skills" / SKILL_NAME / "playbooks"
        required = [
            "codex-run-solution-deck.md",
            "codex-review-and-repair.md",
            "ppt-library-handoff.md",
            "ppt-deck-pro-max-handoff.md",
            "external-quality-review.md",
            "workspace-learning.md",
        ]
        for name in required:
            self.assertTrue(
                (playbooks_dir / name).exists(),
                f"Missing playbook: {name}",
            )

    # ------------------------------------------------------------------ #
    # Schemas exist and are valid JSON
    # ------------------------------------------------------------------ #

    def test_schemas_exist_and_valid_json(self) -> None:
        schemas_dir = _REPO_ROOT / "skills" / SKILL_NAME / "schemas"
        required = [
            "context_pack.schema.json",
            "narrative_advice_task.schema.json",
            "narrative_advice_result.schema.json",
            "external_quality_review_task.schema.json",
            "external_quality_review_result.schema.json",
            "generation_result.schema.json",
            "workspace_learning_pack.schema.json",
        ]
        for name in required:
            path = schemas_dir / name
            self.assertTrue(path.exists(), f"Missing schema: {name}")
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self.fail(f"Schema {name} is not valid JSON: {exc}")
            self.assertIn("$id", data, f"Schema {name} missing $id")


if __name__ == "__main__":
    unittest.main()
