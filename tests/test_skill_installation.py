"""Tests for Package A — Skill Packaging & Installation."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.skills.installer import (
    SKILL_NAME,
    SkillInstallError,
    inspect_skill_link,
    inspect_suite_status,
    install_skill,
    suite_install,
    uninstall_skill,
    validate_skill,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillInstallationTest(unittest.TestCase):
    """Skill install / validate / uninstall against a temp agent skill dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_skill_test_")
        self._log_patch = mock.patch(
            "scripts.skills.installer.INSTALL_LOG_DIR",
            Path(self._tmp) / ".deck-master",
        )
        self._log_patch.start()
        self.agent_dir = Path(self._tmp) / "agent_skills"
        self.agent_dir.mkdir()
        self.source_dir = Path(self._tmp) / ".deck-master" / "current" / "skills" / SKILL_NAME
        shutil.copytree(_REPO_ROOT / "skills" / SKILL_NAME, self.source_dir)

    def tearDown(self) -> None:
        self._log_patch.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # install_skill
    # ------------------------------------------------------------------ #

    def test_install_creates_symlink(self) -> None:
        result = install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "installed")
        link = self.agent_dir / SKILL_NAME
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.source_dir.resolve())

    def test_install_idempotent(self) -> None:
        install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        result = install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "already_installed")

    def test_install_creates_parent_dir_if_missing(self) -> None:
        nested = self.agent_dir / "nested" / "path"
        result = install_skill("codex", str(nested), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "installed")
        self.assertTrue((nested / SKILL_NAME).is_symlink())

    def test_install_existing_real_dir_blocks(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertIn("real file or directory", str(ctx.exception))

    def test_install_force_replaces_symlink(self) -> None:
        # Create a symlink to somewhere else.
        other = Path(self._tmp) / "other_skill"
        other.mkdir()
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        # Without --force should fail.
        with self.assertRaises(SkillInstallError):
            install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        # With --force should replace.
        result = install_skill("codex", str(self.agent_dir), force=True, source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "installed")
        self.assertEqual(link.resolve(), self.source_dir.resolve())

    def test_install_force_does_not_delete_real_dir(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        (real / "marker.txt").write_text("keep me", encoding="utf-8")
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("codex", str(self.agent_dir), force=True, source_skill_dir=str(self.source_dir))
        self.assertIn("real directory", str(ctx.exception))
        # Directory should still be intact.
        self.assertTrue((real / "marker.txt").exists())

    def test_install_unsupported_target(self) -> None:
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("unknown-agent", str(self.agent_dir))
        self.assertIn("Unsupported target", str(ctx.exception))

    def test_install_custom_target_requires_explicit_dir(self) -> None:
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("custom", None, source_skill_dir=str(self.source_dir))
        self.assertIn("--agent-skill-dir", str(ctx.exception))

    def test_install_custom_target_with_explicit_dir(self) -> None:
        result = install_skill("custom", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "installed")

    def test_install_defaults_to_installed_skill_dir(self) -> None:
        with mock.patch("scripts.skills.installer.INSTALLED_SKILL_DIR", self.source_dir):
            result = install_skill("codex", str(self.agent_dir))
        self.assertEqual(result["status"], "installed")
        self.assertEqual((self.agent_dir / SKILL_NAME).resolve(), self.source_dir.resolve())

    def test_install_rejects_invalid_skill_package(self) -> None:
        bad_source = Path(self._tmp) / "bad_skill"
        bad_source.mkdir()
        (bad_source / "SKILL.md").write_text("# Missing frontmatter\n", encoding="utf-8")
        with self.assertRaises(SkillInstallError) as ctx:
            install_skill("codex", str(self.agent_dir), source_skill_dir=str(bad_source))
        self.assertIn("YAML frontmatter", str(ctx.exception))

    # ------------------------------------------------------------------ #
    # validate_skill
    # ------------------------------------------------------------------ #

    def test_validate_after_install(self) -> None:
        install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        result = validate_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertTrue(result["valid"])
        self.assertTrue(result["skill_md_exists"])

    def test_inspect_skill_link_is_non_mutating(self) -> None:
        install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        log_path = Path(self._tmp) / ".deck-master" / "install_log.jsonl"
        before = log_path.read_text(encoding="utf-8")

        result = inspect_skill_link("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))

        self.assertTrue(result["valid"])
        self.assertEqual(before, log_path.read_text(encoding="utf-8"))

    def test_validate_not_installed(self) -> None:
        result = validate_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertFalse(result["valid"])
        self.assertIn("not exist", result["error"])

    def test_validate_wrong_target(self) -> None:
        # Symlink to wrong location.
        other = Path(self._tmp) / "wrong_skill"
        other.mkdir()
        (other / "SKILL.md").write_text("wrong", encoding="utf-8")
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        result = validate_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertFalse(result["valid"])
        self.assertIn("expected", result.get("error", ""))

    def test_validate_unsupported_target(self) -> None:
        result = validate_skill("bad-agent", str(self.agent_dir))
        self.assertFalse(result["valid"])
        self.assertIn("Unsupported", result["error"])

    def test_suite_status_reports_missing_companions_without_writing_log(self) -> None:
        install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        log_path = Path(self._tmp) / ".deck-master" / "install_log.jsonl"
        before = log_path.read_text(encoding="utf-8")

        result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertEqual("degraded_ready", result["status"])
        self.assertEqual("blocked", result["task_readiness"]["library_sourcing"])
        self.assertEqual(before, log_path.read_text(encoding="utf-8"))

    def test_suite_install_installs_available_required_skill_and_reports_missing_companions(self) -> None:
        result = suite_install(targets=["codex"], include_optional=False, agent_skill_dir=str(self.agent_dir))

        self.assertIn(result["status"], {"degraded_installed", "installed"})
        deck = [item for item in result["results"] if item["skill"] == "deck-master"]
        self.assertTrue(deck)

    # ------------------------------------------------------------------ #
    # uninstall_skill
    # ------------------------------------------------------------------ #

    def test_uninstall_after_install(self) -> None:
        install_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        result = uninstall_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "uninstalled")
        self.assertFalse((self.agent_dir / SKILL_NAME).exists())

    def test_uninstall_not_installed(self) -> None:
        result = uninstall_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertEqual(result["status"], "not_installed")

    def test_uninstall_refuses_real_dir(self) -> None:
        real = self.agent_dir / SKILL_NAME
        real.mkdir()
        with self.assertRaises(SkillInstallError) as ctx:
            uninstall_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
        self.assertIn("not a symlink", str(ctx.exception))

    def test_uninstall_refuses_foreign_symlink(self) -> None:
        other = Path(self._tmp) / "foreign_skill"
        other.mkdir()
        link = self.agent_dir / SKILL_NAME
        link.symlink_to(other)
        with self.assertRaises(SkillInstallError) as ctx:
            uninstall_skill("codex", str(self.agent_dir), source_skill_dir=str(self.source_dir))
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

    def test_skill_frontmatter_exists(self) -> None:
        skill_md = _REPO_ROOT / "skills" / SKILL_NAME / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "SKILL.md missing YAML frontmatter")
        frontmatter = text.split("---", 2)[1]
        self.assertIn("name: deck-master", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_agent_instructions_reference_exists_in_repo(self) -> None:
        instructions = _REPO_ROOT / "skills" / SKILL_NAME / "references" / "agent-instructions.md"
        self.assertTrue(instructions.exists(), f"Agent instructions not found at {instructions}")

    def test_no_readme_in_skill_package(self) -> None:
        readme = _REPO_ROOT / "skills" / SKILL_NAME / "README.md"
        self.assertFalse(readme.exists(), "README.md should not be bundled inside the skill package")

    def test_openai_metadata_exists(self) -> None:
        metadata = _REPO_ROOT / "skills" / SKILL_NAME / "agents" / "openai.yaml"
        self.assertTrue(metadata.exists(), f"openai.yaml not found at {metadata}")

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
