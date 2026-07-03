"""Tests for Package A — Skill Packaging & Installation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest
from typing import Any
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from scripts.skills.installer import (
    SKILL_NAME,
    SkillInstallError,
    backend_bind,
    backend_status,
    backend_unbind,
    backend_verify,
    CAPABILITY_LOCK_NAME,
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
from scripts.skills.manifest import load_registry
from scripts.runtime.builder_backend import inspect_builder_backend_package
from scripts.runtime.builder_backend import builder_backend_status
try:
    from runtime.setup_status import setup_status as runtime_setup_status
except ModuleNotFoundError:  # pragma: no cover - package-import fallback.
    from scripts.runtime.setup_status import setup_status as runtime_setup_status
import scripts.deck_master as deck_master


_REPO_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = load_registry()


class SkillInstallationTest(unittest.TestCase):
    """Skill install / validate / uninstall against a temp agent skill dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_skill_test_")
        self._previous_backend_override = os.environ.pop("DECK_MASTER_PPT_MASTER_BACKEND", None)
        self._tmp_home = Path(self._tmp) / "home"
        self._tmp_home.mkdir()
        self._home_patch = mock.patch.dict(os.environ, {"HOME": str(self._tmp_home)}, clear=False)
        self._home_patch.start()
        self._log_patch = mock.patch(
            "scripts.skills.installer.INSTALL_LOG_DIR",
            Path(self._tmp) / ".deck-master",
        )
        self._log_patch.start()
        self.agent_dir = Path(self._tmp) / "agent_skills"
        self.agent_dir.mkdir()
        self.source_dir = Path(self._tmp) / ".deck-master" / "current" / "skills" / SKILL_NAME
        shutil.copytree(_REPO_ROOT / "skills" / SKILL_NAME, self.source_dir)

    def _write_full_ppt_master_skill(
        self,
        *,
        manifest: bool = False,
        manifest_schema: str = "deck_master_backend_manifest.v1",
        missing_operation: str | None = None,
        missing_key_script: str | None = None,
        include_workflows: bool = True,
        contracts_as_list: bool = False,
        smoke_passes: bool = True,
    ) -> Path:
        path = self.agent_dir / "ppt-master"
        path.mkdir()
        (path / "SKILL.md").write_text(
            "---\nname: ppt-master\ndescription: Full standalone PPT Master\n---\n# PPT Master\n",
            encoding="utf-8",
        )

        for dirname in ("references", "templates", "scripts") + (("workflows",) if include_workflows else tuple()):
            child = path / dirname
            child.mkdir()
            (child / "marker.txt").write_text("keep", encoding="utf-8")

        key_scripts = ("project_manager.py", "finalize_svg.py", "svg_to_pptx.py")
        for name in key_scripts:
            if missing_key_script == name:
                continue
            (path / "scripts" / name).write_text("# generated for test\n", encoding="utf-8")
        if manifest:
            (path / "scripts" / "deck_master_backend_smoke.py").write_text(
                (
                    "import json\n"
                    "import sys\n"
                    "from pathlib import Path\n"
                    "out = Path(sys.argv[sys.argv.index('--output-dir') + 1]) if '--output-dir' in sys.argv else Path('.')\n"
                    "exports = out / 'exports'\n"
                    "exports.mkdir(parents=True, exist_ok=True)\n"
                    "render_dir = out / 'render_results'\n"
                    "render_dir.mkdir(parents=True, exist_ok=True)\n"
                    "pptx = exports / 'smoke.pptx'\n"
                    "pptx.write_bytes(b'pptx')\n"
                    "render_result = render_dir / 'render_result.json'\n"
                    "render_result.write_text(json.dumps({\n"
                    "  'schema_version': 'deck_render_result.v2',\n"
                    "  'run_id': 'smoke-run',\n"
                    "  'tool': 'ppt-master',\n"
                    "  'status': 'completed',\n"
                    "  'artifact_path': str(pptx),\n"
                    "  'page_count': 1,\n"
                    "  'source_fingerprint': 'a' * 64,\n"
                    "  'artifacts': [{'artifact_id': 'deck_pptx', 'kind': 'deck_pptx', 'path': str(pptx), 'media_type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'sha256': 'b' * 64, 'bytes': 4, 'validation_status': 'validated', 'editability': 'flat_image'}]\n"
                    "}, ensure_ascii=False), encoding='utf-8')\n"
                    "print(json.dumps({'status': 'pass', 'contract_smoke_output': {'render_result_path': str(render_result), 'fake_pptx_path': str(pptx)}}))\n"
                    if smoke_passes
                    else "raise SystemExit(1)\n"
                ),
                encoding="utf-8",
            )

        if manifest:
            operations = ["render", "smoke", "writeback"]
            if missing_operation:
                operations.remove(missing_operation)
            manifest_data = {
                "schema_version": manifest_schema,
                "name": "ppt-master",
                "kind": "deck_master_backend_manifest",
                "operations": operations,
                "runtime": {
                    "operations": operations,
                    "smoke_command": "python3 scripts/deck_master_backend_smoke.py",
                    "default_command": "python3 scripts/project_manager.py",
                },
                "contracts": (
                    ["deck_render_result.v1", "deck_render_result.v2"]
                    if contracts_as_list
                    else {"outputs": ["deck_render_result.v1", "deck_render_result.v2"]}
                ),
                "writeback": {"canonical_artifact": "render_results/render_result.json"},
                "skill_root": "skills/ppt-master",
            }
            (path / "deck-master-backend.json").write_text(
                json.dumps(manifest_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return path

    def _write_bound_backend_repo(
        self,
        *,
        manifest: bool = True,
        manifest_schema: str = "deck_master_backend_manifest.v1",
        missing_operation: str | None = None,
        missing_key_script: str | None = None,
        include_workflows: bool = True,
        contracts_as_list: bool = False,
        smoke_passes: bool = True,
    ) -> Path:
        skill_root = self._write_full_ppt_master_skill(
            manifest=manifest,
            manifest_schema=manifest_schema,
            missing_operation=missing_operation,
            missing_key_script=missing_key_script,
            include_workflows=include_workflows,
            contracts_as_list=contracts_as_list,
            smoke_passes=smoke_passes,
        )
        repo = Path(self._tmp) / "backend_repo"
        if repo.exists():
            shutil.rmtree(repo)
        (repo / "skills").mkdir(parents=True)
        shutil.copytree(skill_root, repo / "skills" / "ppt-master")
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "deck-master-test"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", "test backend binding"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return repo

    def _run_backend_cli(self, *args: str) -> dict[str, Any]:
        command = [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "deck_master.py"),
            *args,
        ]
        env = os.environ.copy()
        env["HOME"] = str(self._tmp_home)
        result = subprocess.run(
            command,
            cwd=str(_REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        return json.loads(result.stdout)

    def tearDown(self) -> None:
        self._log_patch.stop()
        self._home_patch.stop()
        if self._previous_backend_override is not None:
            os.environ["DECK_MASTER_PPT_MASTER_BACKEND"] = self._previous_backend_override
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
        self.assertFalse(result["production_capable"])
        self.assertEqual("external_full_package", result["backend_type"])

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
        self.assertIn("blocking_summary", result)
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
        self.assertEqual("ready", result["task_readiness"]["ppt_master_adapter"])
        self.assertEqual("blocked", result["task_readiness"]["ppt_master_backend"])
        self.assertEqual("ready", result["task_readiness"]["deck_builder"])
        self.assertFalse(result["production_backend_ready"])
        self.assertFalse(result["client_delivery_ready"])
        self.assertTrue(result["blocking_summary"])
        self.assertEqual("blocked_backend_uncertified", result["capabilities"]["ppt_master.render.v1"])
        self.assertEqual("blocked_backend_uncertified", result["capabilities"]["ppt_master.handback.v1"])

    def test_inspect_builder_backend_package_valid_manifest_is_production_capable(self) -> None:
        path = self._write_full_ppt_master_skill(manifest=True, include_workflows=True)
        result = inspect_builder_backend_package(path)

        self.assertTrue(result["production_capable"])
        self.assertEqual("deck_master_backend_manifest.v1", result["capability_schema"])

    def test_inspect_builder_backend_package_rejects_wrong_schema(self) -> None:
        path = self._write_full_ppt_master_skill(
            manifest=True,
            manifest_schema="random.schema.v1",
            include_workflows=True,
        )
        result = inspect_builder_backend_package(path)

        self.assertFalse(result["production_capable"])
        self.assertIn("schema", " ".join(str(reason) for reason in result["reasons"]).lower())

    def test_inspect_builder_backend_package_rejects_missing_operation(self) -> None:
        path = self._write_full_ppt_master_skill(
            manifest=True,
            missing_operation="writeback",
            include_workflows=True,
        )
        result = inspect_builder_backend_package(path)

        self.assertFalse(result["production_capable"])
        self.assertIn("lacks operations", " ".join(result["reasons"]))

    def test_inspect_builder_backend_package_rejects_missing_key_script(self) -> None:
        path = self._write_full_ppt_master_skill(
            manifest=True,
            missing_key_script="svg_to_pptx.py",
            include_workflows=True,
        )
        result = inspect_builder_backend_package(path)

        self.assertFalse(result["production_capable"])
        self.assertIn("key script missing", " ".join(result["reasons"]))

    def test_inspect_builder_backend_package_rejects_invalid_contracts_block(self) -> None:
        path = self._write_full_ppt_master_skill(
            manifest=True,
            contracts_as_list=True,
            include_workflows=True,
        )
        result = inspect_builder_backend_package(path)

        self.assertFalse(result["production_capable"])
        self.assertIn("contracts block is invalid", " ".join(result["reasons"]))

    def test_inspect_builder_backend_package_rejects_failing_smoke(self) -> None:
        path = self._write_full_ppt_master_skill(
            manifest=True,
            smoke_passes=False,
            include_workflows=True,
        )
        result = inspect_builder_backend_package(path)

        self.assertFalse(result["production_capable"])
        self.assertIn("smoke command failed", " ".join(result["reasons"]))

    def test_inspect_skill_link_prefers_env_backend_override_for_ppt_master(self) -> None:
        override_root = self._write_full_ppt_master_skill(manifest=True, include_workflows=True)
        with mock.patch.dict("os.environ", {"DECK_MASTER_PPT_MASTER_BACKEND": str(override_root)}):
            result = inspect_skill_link("codex", str(self.agent_dir), skill_name="ppt-master")

        self.assertTrue(result["valid"])
        self.assertEqual("env_backend_override", result["status"])
        self.assertEqual("env_backend_override", result["source_type"])
        self.assertTrue(result["production_capable"])
        self.assertIn("backend_status", result)
        self.assertNotEqual("ready", result["status"])

    def test_builder_backend_status_treats_runtime_blocked_binding_as_blocked(self) -> None:
        dependency_status = {
            "name": "ppt-master",
            "dependency_kind": "external_repo",
            "binding_status": "bound_verified_runtime_blocked",
            "repo_label": "unit/repo",
            "repo_path": "/tmp/repo",
            "skill_path": "/tmp/repo/skills/ppt-master",
            "git_sha": "abc",
            "git_branch": "main",
            "worktree_dirty": False,
            "verified": True,
            "verified_at": "2026-01-01T00:00:00Z",
            "validated_capabilities": ["render", "smoke", "writeback"],
            "summary": "PPT Master 已绑定且已完成验证。",
        }

        with mock.patch(
            "scripts.runtime.builder_backend._binding_status_for_name",
            return_value=dependency_status,
        ), mock.patch("scripts.runtime.builder_backend._candidate_paths", return_value=[]):
            status = builder_backend_status()

        self.assertEqual("blocked", status["status"])
        self.assertTrue(status["binding_verified"])
        self.assertFalse(status["runtime_ready"])
        self.assertFalse(status["render_capable"])
        self.assertFalse(status["production_capable"])
        self.assertEqual("bound_verified_runtime_blocked", status["dependency_status"]["binding_status"])

    def test_suite_status_keeps_render_and_client_delivery_blocked_when_backend_certified(self) -> None:
        fake_target = {
            "status": "ready",
            "skill": "deck-master",
            "production_capable": True,
            "backend_status": {"production_capable": True},
        }

        def fake_inspect_skill_link(target: str, agent_skill_dir: str | None = None, source_skill_dir: str | None = None, *, skill_name: str = "deck-master", required: bool = True) -> dict[str, Any]:
            if skill_name == "ppt-master":
                return {
                    **fake_target,
                    "skill": skill_name,
                    "production_capable": True,
                }
            return {
                "status": "ready",
                "skill": skill_name,
                "source_type": "bundled",
            }

        with mock.patch(
            "scripts.skills.installer.external_dependency_statuses",
            return_value=[{
                "name": "ppt-master",
                "dependency_kind": "external_repo",
                "binding_status": "bound_verified_runtime_blocked",
                "repo_label": "",
                "repo_path": "/tmp/repo",
                "skill_path": "",
                "git_sha": "abc",
                "git_branch": "main",
                "worktree_dirty": False,
                "verified": True,
                "verified_at": "2026-01-01T00:00:00Z",
                "validated_capabilities": ["render", "smoke", "writeback"],
                "summary": "PPT Master 已绑定且已完成验证。",
            }],
        ), mock.patch(
            "scripts.skills.installer.backend_dependency_statuses",
            return_value=[{
                "name": "ppt-master",
                "dependency_kind": "external_repo",
                "binding_status": "bound_verified_runtime_blocked",
                "repo_label": "",
                "repo_path": "/tmp/repo",
                "skill_path": "",
                "git_sha": "abc",
                "git_branch": "main",
                "worktree_dirty": False,
                "verified": True,
                "verified_at": "2026-01-01T00:00:00Z",
                "validated_capabilities": ["render", "smoke", "writeback"],
                "summary": "PPT Master 已绑定且已完成验证。",
            }],
        ), mock.patch("scripts.skills.installer.backend_render_runtime_ready", return_value=False), mock.patch(
            "scripts.skills.installer.inspect_skill_link",
            side_effect=fake_inspect_skill_link,
        ):
            result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertTrue(result["production_backend_ready"])
        self.assertEqual("ready", result["task_readiness"]["ppt_master_backend"])
        self.assertEqual("blocked_runtime_not_wired", result["capabilities"]["ppt_master.render.v1"])
        self.assertEqual("blocked_runtime_not_wired", result["capabilities"]["ppt_master.handback.v1"])
        self.assertEqual("blocked", result["task_readiness"]["render"])
        self.assertEqual("blocked", result["task_readiness"]["client_delivery"])
        self.assertFalse(result["client_delivery_ready"])

    def test_suite_status_keeps_client_delivery_blocked_when_runtime_ready(self) -> None:
        def fake_inspect_skill_link(target: str, agent_skill_dir: str | None = None, source_skill_dir: str | None = None, *, skill_name: str = "deck-master", required: bool = True) -> dict[str, Any]:
            return {
                "status": "ready",
                "skill": skill_name,
                "required": required,
                "source_type": "mocked",
                "production_capable": skill_name == "ppt-master",
            }

        verified_backend = {
            "name": "ppt-master",
            "dependency_kind": "external_repo",
            "binding_status": "bound_verified",
            "repo_label": "unit/repo",
            "repo_path": "/tmp/repo",
            "skill_path": "/tmp/repo/skills/ppt-master",
            "git_sha": "abc",
            "git_branch": "main",
            "worktree_dirty": False,
            "verified": True,
            "verified_at": "2026-01-01T00:00:00Z",
            "validated_capabilities": ["render", "smoke", "writeback"],
            "summary": "PPT Master 已绑定且已完成验证。",
        }
        with mock.patch(
            "scripts.skills.installer.external_dependency_statuses",
            return_value=[verified_backend],
        ), mock.patch(
            "scripts.skills.installer.backend_dependency_statuses",
            return_value=[verified_backend],
        ), mock.patch("scripts.skills.installer.backend_render_runtime_ready", return_value=True), mock.patch(
            "scripts.skills.installer.inspect_skill_link",
            side_effect=fake_inspect_skill_link,
        ), mock.patch.dict(
            os.environ,
            {"DECK_MASTER_RC_GATE_REPORT": str(Path(self._tmp) / "missing-rc-gate-report.json")},
            clear=False,
        ):
            result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertEqual("ready", result["task_readiness"]["render"])
        self.assertEqual("blocked", result["task_readiness"]["client_delivery"])
        self.assertFalse(result["client_delivery_ready"])
        self.assertIn("rc_gate_report", result["client_delivery_evidence"]["missing"])

    def test_suite_status_marks_client_delivery_ready_with_rc_gate_evidence(self) -> None:
        def fake_inspect_skill_link(target: str, agent_skill_dir: str | None = None, source_skill_dir: str | None = None, *, skill_name: str = "deck-master", required: bool = True) -> dict[str, Any]:
            return {
                "status": "ready",
                "skill": skill_name,
                "required": required,
                "source_type": "mocked",
                "production_capable": skill_name == "ppt-master",
            }

        verified_backend = {
            "name": "ppt-master",
            "dependency_kind": "external_repo",
            "binding_status": "bound_verified",
            "repo_label": "unit/repo",
            "repo_path": "/tmp/repo",
            "skill_path": "/tmp/repo/skills/ppt-master",
            "git_sha": "backend-sha",
            "git_branch": "main",
            "worktree_dirty": False,
            "verified": True,
            "verified_at": "2026-01-01T00:00:00Z",
            "validated_capabilities": ["render", "smoke", "writeback"],
            "summary": "PPT Master 已绑定且已完成验证。",
        }
        verified_bridge = {
            "name": "ppt-deck-pro-max",
            "dependency_kind": "generation_bridge",
            "binding_status": "bound_verified",
            "repo_label": "unit/bridge",
            "repo_path": "/tmp/bridge",
            "skill_path": "",
            "git_sha": "bridge-sha",
            "git_branch": "main",
            "worktree_dirty": False,
            "verified": True,
            "verified_at": "2026-01-01T00:00:00Z",
            "validated_capabilities": ["dispatch_import", "generation_result_export"],
            "summary": "Bridge 已固定。",
        }
        report_path = Path(self._tmp) / "rc_gate_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_rc_gate_report.v1",
                    "status": "pass",
                    "checks": [
                        {
                            "check_id": "external_dependency_closure",
                            "status": "pass",
                            "details": {
                                "dependencies": {
                                    "ppt-master": {
                                        "binding_status": "bound_verified",
                                        "git_sha": "backend-sha",
                                        "verified": True,
                                    },
                                    "ppt-deck-pro-max": {
                                        "binding_status": "bound_verified",
                                        "git_sha": "bridge-sha",
                                        "verified": True,
                                    },
                                }
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with mock.patch(
            "scripts.skills.installer.external_dependency_statuses",
            return_value=[verified_backend, verified_bridge],
        ), mock.patch(
            "scripts.skills.installer.backend_dependency_statuses",
            return_value=[verified_backend],
        ), mock.patch("scripts.skills.installer.backend_render_runtime_ready", return_value=True), mock.patch(
            "scripts.skills.installer.inspect_skill_link",
            side_effect=fake_inspect_skill_link,
        ), mock.patch.dict(os.environ, {"DECK_MASTER_RC_GATE_REPORT": str(report_path)}, clear=False):
            result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertTrue(result["production_backend_ready"])
        self.assertEqual("ready", result["task_readiness"]["render"])
        self.assertEqual("ready", result["task_readiness"]["client_delivery"])
        self.assertTrue(result["client_delivery_ready"])
        self.assertTrue(result["client_delivery_evidence"]["dependency_snapshot_matches"])

    def test_suite_status_requires_binding_for_production_backend_truth(self) -> None:
        def fake_inspect_skill_link(target: str, agent_skill_dir: str | None = None, source_skill_dir: str | None = None, *, skill_name: str = "deck-master", required: bool = True) -> dict[str, Any]:
            return {
                "status": "ready",
                "skill": skill_name,
                "required": bool(required),
                "source_type": "mocked",
                "production_capable": True,
            }

        with mock.patch("scripts.skills.installer.external_dependency_statuses", return_value=[{
            "name": "ppt-master",
            "dependency_kind": "external_repo",
            "binding_status": "unbound",
            "repo_label": "",
            "repo_path": "",
            "skill_path": "",
            "git_sha": "",
            "git_branch": "",
            "worktree_dirty": False,
            "verified": False,
            "verified_at": "",
            "validated_capabilities": [],
            "summary": "No formal backend binding found for PPT Master.",
        }]), mock.patch("scripts.skills.installer.inspect_skill_link", side_effect=fake_inspect_skill_link):
            result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertFalse(result["production_backend_ready"])
        self.assertEqual("blocked", result["task_readiness"]["ppt_master_backend"])
        self.assertEqual("blocked_backend_uncertified", result["capabilities"]["ppt_master.render.v1"])
        self.assertEqual("blocked_backend_uncertified", result["capabilities"]["ppt_master.handback.v1"])

    def test_release_lock_includes_external_dependencies(self) -> None:
        release_root = Path(self._tmp) / "release"
        build_release_tree(release_root)
        capability_lock = json.loads((release_root / CAPABILITY_LOCK_NAME).read_text(encoding="utf-8"))

        self.assertIn("external_dependencies", capability_lock)
        dependencies = capability_lock["external_dependencies"]
        self.assertIsInstance(dependencies, list)
        self.assertIn("ppt-master", {item["name"] for item in dependencies})
        self.assertIn("ppt-deck-pro-max", {item["name"] for item in dependencies})
        self.assertEqual("ppt-master", dependencies[0]["name"])
        self.assertIn("dependency_kind", dependencies[0])
        self.assertIn("binding_status", dependencies[0])
        self.assertIn("repo_label", dependencies[0])
        self.assertIn("verified", dependencies[0])
        self.assertIn("external_dependency_status", capability_lock)
        external = capability_lock["external_dependency_status"]
        self.assertIsInstance(external, list)
        self.assertEqual("ppt-master", external[0]["name"])
        self.assertIn("dependency_kind", external[0])
        self.assertIn("binding_status", external[0])
        self.assertIn("repo_label", external[0])
        self.assertIn("verified", external[0])
        self.assertEqual(dependencies, external)

        bridge = next(item for item in dependencies if item["name"] == "ppt-deck-pro-max")
        self.assertEqual("generation_bridge", bridge["dependency_kind"])
        self.assertEqual("https://github.com/MainQuestAI/PPT-Deck-Pro-Max.git", bridge["repo"])
        self.assertEqual("codex/deck-master-bridge", bridge["git_branch"])
        self.assertEqual("9444d88f573c3afa567bfb1763041325ef765313", bridge["git_sha"])
        self.assertEqual("9444d88f", bridge["short_sha"])
        self.assertEqual("bound_verified", bridge["binding_status"])
        self.assertTrue(bridge["verified"])
        self.assertEqual(
            ["dispatch_import", "generation_result_export", "result_import_contract"],
            bridge["validated_capabilities"],
        )

    def test_suite_and_setup_status_report_generation_bridge_snapshot(self) -> None:
        config_path = Path.home() / ".deck-master" / "config.json"
        install_root = config_path.parent
        install_root.mkdir(parents=True, exist_ok=True)
        default_runs = install_root / "runs"
        default_runs.mkdir(exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_master_setup.v1",
                    "setup_completed_at": "2026-01-01T00:00:00Z",
                    "install_root": str(install_root),
                    "active_workspace": "",
                    "default_runs_dir": str(default_runs),
                    "review_cockpit_url": "http://127.0.0.1:5050",
                    "agent_targets": [],
                    "setup_status": {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        def fake_inspect_skill_link(
            target: str,
            agent_skill_dir: str | None = None,
            source_skill_dir: str | None = None,
            *,
            skill_name: str = "deck-master",
            required: bool = True,
        ) -> dict[str, Any]:
            return {
                "status": "ready",
                "skill": skill_name,
                "required": required,
                "source_type": "mocked",
                "production_capable": skill_name == "ppt-master",
            }

        with mock.patch("scripts.skills.installer.inspect_skill_link", side_effect=fake_inspect_skill_link):
            suite = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        setup = runtime_setup_status(run_mode="dev", include_suite=False)
        for payload in (suite, setup):
            bridge = next(
                item for item in payload["external_dependency_status"]
                if item["name"] == "ppt-deck-pro-max"
            )
            self.assertEqual("generation_bridge", bridge["dependency_kind"])
            self.assertEqual("https://github.com/MainQuestAI/PPT-Deck-Pro-Max.git", bridge["source"])
            self.assertEqual("9444d88f573c3afa567bfb1763041325ef765313", bridge["git_sha"])
            self.assertEqual("9444d88f", bridge["short_sha"])
            self.assertIn("PPT Deck Pro Max generation bridge pinned", bridge["summary"])
            self.assertFalse(payload["client_delivery_ready"])

    def test_release_lock_preserves_runtime_blocked_binding_truth(self) -> None:
        repo = self._write_bound_backend_repo()
        bind_result = backend_bind("ppt-master", str(repo))
        self.assertTrue(bind_result["verified"])

        with mock.patch.dict(os.environ, {"DECK_MASTER_PPT_MASTER_RUNTIME_WIRED": "0"}, clear=False):
            release_root = Path(self._tmp) / "release-runtime-blocked"
            result = build_release_tree(release_root)

        self.assertEqual("built", result["status"])
        capability_lock = json.loads((release_root / CAPABILITY_LOCK_NAME).read_text(encoding="utf-8"))
        dependencies = capability_lock["external_dependencies"]
        self.assertEqual("bound_verified_runtime_blocked", dependencies[0]["binding_status"])
        self.assertEqual(dependencies, capability_lock["external_dependency_status"])

    def test_backend_bind_verify_unbind_cycle(self) -> None:
        repo = self._write_bound_backend_repo()

        bound = backend_bind(name="ppt-master", repo_path=str(repo))
        self.assertEqual("ppt-master", bound["name"])
        self.assertTrue(bound["verified"])
        self.assertIn("verified_at", bound)
        status = backend_status()
        self.assertTrue(status["production_bound_verified"])
        self.assertIn(status["binding_status"], {"bound_verified", "bound_verified_runtime_blocked"})

        manifest_path = repo / "skills" / "ppt-master" / "deck-master-backend.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["operations"] = ["render", "smoke"]
        payload["runtime"]["operations"] = ["render", "smoke"]
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        verified = backend_verify("ppt-master")
        self.assertFalse(verified["verified"])

        unbound = backend_unbind("ppt-master")
        self.assertEqual("unbound", unbound["status"])
        after_unbound = backend_status()
        self.assertFalse(after_unbound["production_bound_verified"])
        self.assertEqual("unbound", after_unbound["binding_status"])

    def test_backend_cli_bind_status_verify_unbind_cycle(self) -> None:
        repo = self._write_bound_backend_repo()
        initial = self._run_backend_cli("backend", "status")
        self.assertEqual("unbound", initial["binding_status"])

        bound = self._run_backend_cli("backend", "bind", "ppt-master", "--repo", str(repo))
        self.assertEqual("ppt-master", bound["name"])
        self.assertTrue(bound["verified"])
        registry_path = self._tmp_home / ".deck-master" / "backend_bindings.json"
        self.assertTrue(registry_path.exists())
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        self.assertEqual("deck_backend_bindings.v1", registry["schema_version"])
        self.assertEqual(1, len(registry["bindings"]))
        self.assertEqual("ppt-master", registry["bindings"][0]["name"])
        self.assertEqual(str(repo.resolve()), registry["bindings"][0]["repo_path"])

        status = self._run_backend_cli("backend", "status")
        self.assertIn(status["binding_status"], {"bound_verified", "bound_verified_runtime_blocked"})
        self.assertTrue(status["production_bound_verified"])

        verified = self._run_backend_cli("backend", "verify", "ppt-master")
        self.assertEqual(str(repo.resolve()), verified["repo_path"])

        unbound = self._run_backend_cli("backend", "unbind", "ppt-master")
        self.assertEqual("unbound", unbound["status"])

    def test_setup_status_uses_backend_binding_truth(self) -> None:
        config_path = Path.home() / ".deck-master" / "config.json"
        install_root = config_path.parent
        install_root.mkdir(parents=True, exist_ok=True)
        default_runs = install_root / "runs"
        default_runs.mkdir(exist_ok=True)
        config = {
            "schema_version": "deck_master_setup.v1",
            "setup_completed_at": "2026-01-01T00:00:00Z",
            "install_root": str(install_root),
            "active_workspace": "",
            "default_runs_dir": str(default_runs),
            "review_cockpit_url": "http://127.0.0.1:5050",
            "agent_targets": [],
            "setup_status": {},
        }
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        dependency_status = [{
            "name": "ppt-master",
            "dependency_kind": "external_repo",
            "binding_status": "bound_verified_runtime_blocked",
            "repo_label": "unit/repo",
            "repo_path": "/tmp/repo",
            "skill_path": "/tmp/repo/skills/ppt-master",
            "git_sha": "abc",
            "git_branch": "main",
            "worktree_dirty": False,
            "verified": True,
            "verified_at": "2026-01-01T00:00:00Z",
            "validated_capabilities": ["render", "smoke", "writeback"],
            "summary": "PPT Master 已绑定且已完成验证。",
        }]
        with mock.patch(
            "runtime.setup_status.inspect_suite_status",
            return_value={
                "status": "ready",
                "full_suite_ready": True,
                "production_backend_ready": True,
                "client_delivery_ready": False,
                "external_dependency_status": dependency_status,
                "capabilities": {},
                "task_readiness": {"render": "blocked"},
                "blocking_summary": [],
            },
        ):
            result = runtime_setup_status(run_mode="dev", include_suite=False)

        self.assertEqual("ready", result["status"])
        self.assertTrue(result["production_backend_ready"])
        self.assertEqual("bound_verified_runtime_blocked", result["external_dependency_status"][0]["binding_status"])
        self.assertIn("external_dependency_status", result)

    def test_suite_status_treats_env_backend_override_as_diagnostic_only(self) -> None:
        def fake_inspect_skill_link(
            target: str,
            agent_skill_dir: str | None = None,
            source_skill_dir: str | None = None,
            *,
            skill_name: str = "deck-master",
            required: bool = True,
        ) -> dict[str, Any]:
            if skill_name == "ppt-master":
                return {
                    "status": "env_backend_override",
                    "skill": skill_name,
                    "valid": True,
                    "required": True,
                    "source_type": "env_backend_override",
                    "production_capable": True,
                }
            return {
                "status": "ready",
                "skill": skill_name,
                "required": required,
                "source_type": "mocked",
                "production_capable": True,
            }

        with mock.patch(
            "scripts.skills.installer.external_dependency_statuses",
            return_value=[{
                "name": "ppt-master",
                "dependency_kind": "external_repo",
                "binding_status": "bound_verified",
                "repo_label": "",
                "repo_path": "",
                "skill_path": "",
                "git_sha": "",
                "git_branch": "",
                "worktree_dirty": False,
                "verified": True,
                "verified_at": "2026-01-01T00:00:00Z",
                "validated_capabilities": ["render", "smoke", "writeback"],
                "summary": "PPT Master 已绑定且已完成验证。",
            }],
        ), mock.patch("scripts.skills.installer.inspect_skill_link", side_effect=fake_inspect_skill_link):
            result = inspect_suite_status(targets=["codex"], agent_skill_dir=str(self.agent_dir))

        self.assertEqual("degraded_ready", result["status"])
        self.assertIn("ppt-master", result["target_readiness"]["codex"]["blocked_required"])
        self.assertTrue(result["production_backend_ready"])
        self.assertEqual("ready", result["task_readiness"]["ppt_master_backend"])
        self.assertEqual("blocked", result["task_readiness"]["ppt_master_adapter"])

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
        self.assertEqual(_REGISTRY.suite_version, release_manifest["suite_version"])
        self.assertTrue(release_manifest["self_contained"])
        self.assertEqual("bin/deck-master", release_manifest["entrypoint"])

        companion = json.loads((release_root / "companion-manifest.json").read_text(encoding="utf-8"))
        revision = (release_root / "REVISION").read_text(encoding="utf-8").strip()
        self.assertTrue(revision)
        self.assertEqual(_REGISTRY.suite_version, companion["suite_version"])
        self.assertEqual(revision, companion["git_commit"])
        self.assertEqual(f"main-{revision}", companion["release_id"])

        capability_lock = json.loads((release_root / "deck_capability_lock.json").read_text(encoding="utf-8"))
        self.assertEqual("deck_capability_lock.v1", capability_lock["schema_version"])
        self.assertEqual(_REGISTRY.suite_version, capability_lock["suite_version"])
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
        companion = json.loads((release_root / "companion-manifest.json").read_text(encoding="utf-8"))
        revision = (release_root / "REVISION").read_text(encoding="utf-8").strip()
        self.assertTrue(revision)
        self.assertEqual(revision, companion["git_commit"])
        self.assertEqual(f"main-{revision}", companion["release_id"])
        for skill_name in product_capability_manifest()["required_capabilities"]:
            self.assertTrue((release_root / "skills" / skill_name / "SKILL.md").exists(), skill_name)
        self.assertTrue((release_root / "skills" / "deck-learn" / "SKILL.md").exists())
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

    def test_root_product_capability_manifest_matches_runtime_truth(self) -> None:
        manifest = json.loads((_REPO_ROOT / "product-capability-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(product_capability_manifest(), manifest)

    def test_ppt_master_render_v2_contract_copy_matches_runtime_contract(self) -> None:
        canonical = _REPO_ROOT / "docs" / "contracts" / "render-result.v2.schema.json"
        capability_copy = _REPO_ROOT / "product_capabilities" / "ppt-master" / "contracts" / "render-result.v2.schema.json"

        self.assertEqual(canonical.read_text(encoding="utf-8"), capability_copy.read_text(encoding="utf-8"))

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

    def test_release_install_cli_calls_staged_installer(self) -> None:
        parser = deck_master.build_parser()

        for argv, expected_smoke in ((["release-install"], True), (["release-install", "--no-smoke"], False)):
            with self.subTest(argv=argv), mock.patch(
                "scripts.deck_master.install_release_tree",
                return_value={"status": "installed", "activated": True},
            ) as install:
                args = parser.parse_args(argv)
                result = args.func(args)

            self.assertEqual("installed", result["status"])
            install.assert_called_once_with(run_smoke=expected_smoke)

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
        self.assertEqual("ready", result["suite_status"]["task_readiness"]["ppt_master_adapter"])
        self.assertEqual("blocked", result["suite_status"]["task_readiness"]["render"])

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

    def test_setup_status_v2_schema_holds_minimum_public_fields(self) -> None:
        schema_path = _REPO_ROOT / "docs" / "contracts" / "setup-status.v2.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        for key in {
            "workspace_entry_ready",
            "production_backend_ready",
            "client_delivery_ready",
            "external_dependency_status",
            "blocking_summary",
            "setup_blocking_summary",
            "workspace_blocking_summary",
            "suite_blocking_summary",
            "client_delivery_blocking_summary",
            "full_suite_ready",
        }:
            self.assertIn(key, schema["properties"], key)
        for key in {
            "workspace_entry_ready",
            "production_backend_ready",
            "client_delivery_ready",
            "external_dependency_status",
            "blocking_summary",
            "setup_blocking_summary",
            "workspace_blocking_summary",
            "suite_blocking_summary",
            "client_delivery_blocking_summary",
        }:
            self.assertIn(key, schema["required"], key)

        dependency_schema = schema["$defs"]["dependency_status_entry"]
        for key in {
            "name",
            "dependency_kind",
            "binding_status",
            "repo_label",
            "git_sha",
            "short_sha",
            "verified",
            "validated_capabilities",
            "summary",
        }:
            self.assertIn(key, dependency_schema["properties"], key)
            self.assertIn(key, dependency_schema["required"])
        self.assertEqual(
            [
                "unbound",
                "bound_blocked",
                "bound_verified_runtime_blocked",
                "bound_verified",
            ],
            dependency_schema["properties"]["binding_status"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
