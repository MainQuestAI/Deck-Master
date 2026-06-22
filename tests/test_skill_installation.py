"""Tests for Package A — Skill Packaging & Installation."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.skills.installer import (
    SKILL_NAME,
    SkillInstallError,
    build_release_tree,
    inspect_skill_link,
    install_release_tree,
    rollback_release_tree,
    inspect_suite_status,
    install_skill,
    product_capability_manifest,
    suite_install,
    suite_migration_apply,
    suite_migration_plan,
    suite_migration_rollback,
    uninstall_skill,
    validate_product_capability_manifest,
    validate_skill,
    verify_release_tree,
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

    def _write_full_ppt_master_skill(self) -> Path:
        path = self.agent_dir / "ppt-master"
        path.mkdir()
        (path / "SKILL.md").write_text(
            "---\nname: ppt-master\ndescription: Full standalone PPT Master\n---\n# PPT Master\n",
            encoding="utf-8",
        )
        for dirname in ("references", "scripts", "templates"):
            child = path / dirname
            child.mkdir()
            (child / "marker.txt").write_text("keep", encoding="utf-8")
        return path

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

    def test_inspect_preserves_full_external_ppt_master_real_dir(self) -> None:
        full_package = self._write_full_ppt_master_skill()

        result = inspect_skill_link(
            "codex",
            str(self.agent_dir),
            source_skill_dir=str(_REPO_ROOT / "skills" / "ppt-master"),
            skill_name="ppt-master",
        )

        self.assertTrue(result["valid"])
        self.assertEqual("ready", result["status"])
        self.assertEqual("external_full_package", result["source_type"])
        self.assertEqual(str(full_package.resolve()), result["resolved"])

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
        self.assertFalse(result["full_suite_ready"])
        self.assertFalse(result["target_readiness"]["codex"]["required_ready"])
        self.assertEqual(before, log_path.read_text(encoding="utf-8"))

    def test_suite_install_installs_available_required_skill_and_reports_missing_companions(self) -> None:
        result = suite_install(targets=["codex"], include_optional=False, agent_skill_dir=str(self.agent_dir))

        self.assertEqual("installed", result["status"])
        deck = [item for item in result["results"] if item["skill"] == "deck-master"]
        self.assertTrue(deck)
        self.assertTrue(result["suite_status"]["full_suite_ready"])
        for skill_name in [
            "deck-master",
            "deck-setup",
            "deck-upgrade",
            "deck-doctor",
            "deck-init",
            "deck-brief",
            "deck-planner",
            "deck-sourcing",
            "deck-producer",
            "deck-builder",
            "deck-quality",
            "deck-review",
            "deck-autopilot",
            "ppt-master",
            "ppt-library",
            "ppt-deck-pro-max",
            "ppt-quality-gate",
        ]:
            self.assertTrue((self.agent_dir / skill_name).is_symlink(), f"missing suite link: {skill_name}")

    def test_suite_install_multi_target_reports_full_ready_only_when_all_targets_ready(self) -> None:
        codex_dir = Path(self._tmp) / "codex_skills"
        claude_dir = Path(self._tmp) / "claude_skills"
        with mock.patch.dict(
            "scripts.skills.installer.DEFAULT_AGENT_SKILL_DIRS",
            {"codex": str(codex_dir), "claude-code": str(claude_dir)},
        ):
            result = suite_install(targets=["codex", "claude-code"], include_optional=False)

        self.assertEqual("installed", result["status"])
        suite = result["suite_status"]
        self.assertTrue(suite["full_suite_ready"])
        self.assertTrue(suite["target_readiness"]["codex"]["required_ready"])
        self.assertTrue(suite["target_readiness"]["claude-code"]["required_ready"])
        self.assertEqual("ready", suite["task_readiness"]["full_deck_workflow"])

    def test_suite_status_multi_target_missing_required_blocks_full_ready(self) -> None:
        codex_dir = Path(self._tmp) / "codex_skills"
        claude_dir = Path(self._tmp) / "claude_skills"
        with mock.patch.dict(
            "scripts.skills.installer.DEFAULT_AGENT_SKILL_DIRS",
            {"codex": str(codex_dir), "claude-code": str(claude_dir)},
        ):
            suite_install(targets=["codex"], include_optional=False)
            result = inspect_suite_status(targets=["codex", "claude-code"])

        self.assertFalse(result["full_suite_ready"])
        self.assertTrue(result["target_readiness"]["codex"]["required_ready"])
        self.assertFalse(result["target_readiness"]["claude-code"]["required_ready"])
        self.assertIn("deck-master", result["target_readiness"]["claude-code"]["missing_required"])
        self.assertNotEqual("ready", result["task_readiness"]["full_deck_workflow"])

    def test_suite_status_single_target_ready_remains_full_ready(self) -> None:
        codex_dir = Path(self._tmp) / "codex_skills"
        claude_dir = Path(self._tmp) / "claude_skills"
        with mock.patch.dict(
            "scripts.skills.installer.DEFAULT_AGENT_SKILL_DIRS",
            {"codex": str(codex_dir), "claude-code": str(claude_dir)},
        ):
            suite_install(targets=["codex"], include_optional=False)
            result = inspect_suite_status(targets=["codex"])

        self.assertTrue(result["full_suite_ready"])
        self.assertTrue(result["target_readiness"]["codex"]["required_ready"])
        self.assertEqual("ready", result["task_readiness"]["full_deck_workflow"])
        self.assertEqual("ready", result["task_readiness"]["deck_builder_adapter"])
        self.assertEqual("ready", result["task_readiness"]["ppt_master_backend"])
        self.assertEqual("ready", result["task_readiness"]["deck_builder"])

    def test_release_tree_contains_required_skills_capabilities_and_manifest(self) -> None:
        release_root = Path(self._tmp) / "release"

        result = build_release_tree(release_root)

        self.assertEqual("built", result["status"])
        self.assertTrue((release_root / "bin" / "deck-master").exists())
        self.assertTrue(result["self_contained"])
        self.assertTrue((release_root / "scripts" / "deck_master.py").exists())
        self.assertTrue((release_root / "release-manifest.json").exists())
        self.assertTrue((release_root / "deck_capability_lock.json").exists())
        self.assertTrue((release_root / "SHA256SUMS").exists())

        bin_text = (release_root / "bin" / "deck-master").read_text(encoding="utf-8")
        self.assertNotIn(str(_REPO_ROOT / "scripts" / "deck_master.py"), bin_text)
        self.assertIn("RELEASE_ROOT", bin_text)
        self.assertIn("scripts/deck_master.py", bin_text)

        completed = subprocess.run(
            [str(release_root / "bin" / "deck-master"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

        release_manifest = json.loads((release_root / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("deck_master_release_manifest.v1", release_manifest["schema_version"])
        self.assertTrue(release_manifest["self_contained"])
        self.assertEqual("bin/deck-master", release_manifest["entrypoint"])

        capability_lock = json.loads((release_root / "deck_capability_lock.json").read_text(encoding="utf-8"))
        self.assertEqual("deck_capability_lock.v1", capability_lock["schema_version"])
        self.assertTrue(capability_lock["contracts"])

        checksums = (release_root / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn("scripts/deck_master.py", checksums)
        self.assertIn("release-manifest.json", checksums)
        self.assertIn("deck_capability_lock.json", checksums)

        manifest_path = release_root / "product-capability-manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation = validate_product_capability_manifest(manifest)
        self.assertTrue(validation["valid"], validation["errors"])
        for skill_name in product_capability_manifest()["required_capabilities"]:
            self.assertTrue((release_root / "skills" / skill_name / "SKILL.md").exists(), skill_name)
        for capability_name in ["ppt-master", "ppt-library", "ppt-deck-pro-max", "ppt-quality-gate"]:
            self.assertTrue((release_root / "capabilities" / capability_name / "capability.json").exists(), capability_name)

    def test_verify_release_tree_rejects_tampered_checksum(self) -> None:
        release_root = Path(self._tmp) / "release"
        build_release_tree(release_root)
        (release_root / "release-manifest.json").write_text("{}", encoding="utf-8")

        result = verify_release_tree(release_root, run_smoke=False)

        self.assertFalse(result["valid"])
        codes = {error["code"] for error in result["errors"]}
        self.assertIn("sha256_mismatch", codes)

    def test_suite_install_activates_verified_release_via_staging(self) -> None:
        result = suite_install(targets=["codex"], include_optional=False, agent_skill_dir=str(self.agent_dir))

        self.assertEqual("installed", result["status"])
        self.assertTrue(result["release_install"]["activated"])
        current = Path(self._tmp) / ".deck-master" / "current"
        self.assertTrue((current / "release-activation.json").exists())
        staged = Path(self._tmp) / ".deck-master" / "staging" / f"release-{result['release_install']['release_id']}"
        self.assertFalse(staged.exists())
        self.assertTrue(verify_release_tree(current, run_smoke=True)["valid"])
        for skill_name in product_capability_manifest()["required_capabilities"]:
            self.assertTrue((self.agent_dir / skill_name).is_symlink(), skill_name)

    def test_suite_install_blocks_when_stage_verification_fails_without_touching_current(self) -> None:
        current = Path(self._tmp) / ".deck-master" / "current"
        current.mkdir(parents=True, exist_ok=True)
        (current / "keep.txt").write_text("previous-current", encoding="utf-8")
        verification = {
            "schema_version": "deck_master_release_verification.v1",
            "release_root": "staged",
            "valid": False,
            "status": "failed",
            "errors": [{"code": "forced_failure"}],
            "warnings": [],
            "smoke": {"skipped": True},
        }

        with mock.patch("scripts.skills.installer.verify_release_tree", return_value=verification):
            result = suite_install(targets=["codex"], include_optional=False, agent_skill_dir=str(self.agent_dir))

        self.assertEqual("blocked", result["status"])
        self.assertEqual("previous-current", (current / "keep.txt").read_text(encoding="utf-8"))

    def test_release_rollback_restores_previous_release(self) -> None:
        current = Path(self._tmp) / ".deck-master" / "current"
        build_release_tree(current, force=True)
        original_manifest = (current / "release-manifest.json").read_text(encoding="utf-8")
        install_result = install_release_tree(run_smoke=True)
        self.assertTrue(install_result["activated"])
        self.assertEqual(original_manifest, (Path(self._tmp) / ".deck-master" / "previous" / "release-manifest.json").read_text(encoding="utf-8"))

        rollback = rollback_release_tree()

        self.assertEqual("rolled_back", rollback["status"])
        self.assertTrue(rollback["verification"]["valid"])
        self.assertEqual(original_manifest, (current / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse((current / "release-activation.json").exists())

    def test_suite_migration_apply_and_rollback_real_directory(self) -> None:
        legacy = self.agent_dir / "ppt-master"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text(
            "---\nname: ppt-master\ndescription: Legacy PPT Master\n---\n",
            encoding="utf-8",
        )
        (legacy / "marker.txt").write_text("restore", encoding="utf-8")
        plan = suite_migration_plan(targets=["codex"], agent_skill_dir=str(self.agent_dir))
        ppt_master = next(item for item in plan["actions"] if item["skill"] == "ppt-master")
        self.assertEqual("backup_and_replace_with_symlink", ppt_master["action"])
        plan_file = Path(self._tmp) / "migration-plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        applied = suite_migration_apply(plan_file)

        self.assertEqual("applied", applied["status"])
        self.assertTrue((self.agent_dir / "ppt-master").is_symlink())
        rolled_back = suite_migration_rollback(applied["rollback_id"])
        self.assertEqual("rolled_back", rolled_back["status"])
        self.assertTrue((self.agent_dir / "ppt-master" / "marker.txt").exists())

    def test_suite_install_preserves_full_external_ppt_master_real_dir(self) -> None:
        full_package = self._write_full_ppt_master_skill()

        result = suite_install(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        ppt_master = next(item for item in result["results"] if item["skill"] == "ppt-master")
        self.assertEqual("external_full_package_preserved", ppt_master["status"])
        self.assertFalse(full_package.is_symlink())
        self.assertTrue((full_package / "references" / "marker.txt").exists())
        self.assertEqual("ready", result["suite_status"]["task_readiness"]["render"])

    def test_suite_migration_plan_preserves_full_external_ppt_master_real_dir(self) -> None:
        full_package = self._write_full_ppt_master_skill()
        plan = suite_migration_plan(targets=["codex"], agent_skill_dir=str(self.agent_dir))
        ppt_master = next(item for item in plan["actions"] if item["skill"] == "ppt-master")

        self.assertEqual("preserve_external_full_package", ppt_master["action"])
        self.assertTrue(ppt_master["safe_to_apply"])
        self.assertEqual("external_full_ppt_master_skill", ppt_master["recognized_as"])

        plan_file = Path(self._tmp) / "migration-plan.json"
        plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        applied = suite_migration_apply(plan_file)
        applied_ppt_master = next(item for item in applied["results"] if item["skill"] == "ppt-master")

        self.assertEqual("no_op", applied_ppt_master["status"])
        self.assertFalse(full_package.is_symlink())
        self.assertTrue((full_package / "scripts" / "marker.txt").exists())

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
