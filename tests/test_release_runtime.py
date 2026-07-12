from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skills import installer  # noqa: E402


class ReleaseRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_release_runtime_"))
        self.install_root = self.temp_dir / ".deck-master"
        self.install_patch = mock.patch.object(installer, "INSTALL_LOG_DIR", self.install_root)
        self.install_patch.start()
        self.addCleanup(self.install_patch.stop)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _fake_runtime_install(self, release_root: Path, version: str = "3.12.8") -> dict[str, str]:
        runtime_python = release_root / installer.RELEASE_PYTHON_RELATIVE
        runtime_python.parent.mkdir(parents=True, exist_ok=True)
        runtime_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        runtime_python.chmod(0o755)
        installer._record_release_runtime(release_root, version)
        return {
            "python_requirement": installer.RUNTIME_PYTHON_REQUIREMENT,
            "python_version": version,
            "interpreter": installer.RELEASE_PYTHON_RELATIVE,
        }

    def _tree_snapshot(self, root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }

    def test_jsonschema_is_declared_once_as_a_runtime_dependency(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

        runtime_matches = [item for item in project["dependencies"] if item.startswith("jsonschema")]
        dev_matches = [
            item
            for item in project["optional-dependencies"]["dev"]
            if item.startswith("jsonschema")
        ]

        self.assertEqual(["jsonschema>=4.23,<5"], runtime_matches)
        self.assertEqual([], dev_matches)

    def test_release_build_contains_install_source_and_release_local_launcher(self) -> None:
        release_root = self.temp_dir / "release"

        installer.build_release_tree(release_root)

        self.assertTrue((release_root / "pyproject.toml").is_file())
        self.assertEqual(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            (release_root / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertFalse((release_root / ".venv").exists())
        launcher = (release_root / "bin" / "deck-master").read_text(encoding="utf-8")
        self.assertIn('exec "$RELEASE_ROOT/.venv/bin/python"', launcher)
        self.assertNotIn("exec python3", launcher)

        manifest = json.loads((release_root / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(">=3.12,<3.13", manifest["runtime"]["python_requirement"])
        self.assertIsNone(manifest["runtime"]["python_version"])
        self.assertEqual(".venv/bin/python", manifest["runtime"]["interpreter"])
        self.assertNotIn(str(ROOT), json.dumps(manifest))

    def test_release_sha_enumeration_excludes_runtime_venv(self) -> None:
        release_root = self.temp_dir / "release"
        installer.build_release_tree(release_root)
        runtime_file = release_root / ".venv" / "lib" / "private-runtime.py"
        runtime_file.parent.mkdir(parents=True)
        runtime_file.write_text("runtime", encoding="utf-8")

        installer._write_sha256sums(release_root)

        checksums = (release_root / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertNotIn(".venv/", checksums)

    def test_runtime_install_cleanup_preserves_runtime_packages(self) -> None:
        release_root = self.temp_dir / "release"
        (release_root / "build").mkdir(parents=True)
        (release_root / "scripts" / "deck_master.egg-info").mkdir(parents=True)
        legitimate_package = release_root / "scripts" / "build"
        legitimate_package.mkdir(parents=True)
        (legitimate_package / "__init__.py").write_text("", encoding="utf-8")
        venv_metadata = release_root / ".venv" / "lib" / "dependency.egg-info"
        venv_metadata.mkdir(parents=True)

        installer._clean_runtime_build_artifacts(release_root)

        self.assertFalse((release_root / "build").exists())
        self.assertFalse((release_root / "scripts" / "deck_master.egg-info").exists())
        self.assertTrue((legitimate_package / "__init__.py").exists())
        self.assertTrue(venv_metadata.exists())

    def test_runtime_python_override_takes_precedence_and_must_be_312(self) -> None:
        with mock.patch.dict(os.environ, {"DECK_MASTER_PYTHON": "/opt/python-override"}), mock.patch.object(
            installer.shutil,
            "which",
            return_value="/usr/local/bin/python3.12",
        ) as which, mock.patch.object(installer, "_probe_python_version", return_value="3.12.8"):
            executable, version = installer._resolve_runtime_python()

        self.assertEqual("/opt/python-override", executable)
        self.assertEqual("3.12.8", version)
        which.assert_not_called()

        expected = (
            "Deck Master installed releases require Python 3.12. Set DECK_MASTER_PYTHON\n"
            "to a Python 3.12 executable or install python3.12. No release was activated."
        )
        for invalid_version in ("3.11.9", "3.13.0", "3.14.1", ""):
            with self.subTest(version=invalid_version), mock.patch.dict(
                os.environ,
                {"DECK_MASTER_PYTHON": "/opt/invalid-python"},
            ), mock.patch.object(installer, "_probe_python_version", return_value=invalid_version):
                with self.assertRaises(installer.SkillInstallError) as ctx:
                    installer._resolve_runtime_python()
            self.assertEqual(expected, str(ctx.exception))

    def test_runtime_python_symlink_is_resolved_before_venv_creation(self) -> None:
        python312 = shutil.which("python3.12")
        if not python312:
            self.skipTest("python3.12 is required for symlink resolution regression")
        real_python = Path(python312).resolve()
        python_alias = self.temp_dir / "python3.12"
        python_alias.symlink_to(real_python)

        with mock.patch.dict(os.environ, {"DECK_MASTER_PYTHON": str(python_alias)}):
            executable, version = installer._resolve_runtime_python()

        self.assertEqual(str(real_python), executable)
        self.assertTrue(version.startswith("3.12."))

    def test_runtime_python_falls_back_to_python312(self) -> None:
        with mock.patch.dict(os.environ, {"DECK_MASTER_PYTHON": ""}), mock.patch.object(
            installer.shutil,
            "which",
            return_value="/opt/python3.12",
        ) as which, mock.patch.object(installer, "_probe_python_version", return_value="3.12.8"):
            executable, version = installer._resolve_runtime_python()

        self.assertEqual("/opt/python3.12", executable)
        self.assertEqual("3.12.8", version)
        which.assert_called_once_with("python3.12")

    def test_uninstalled_release_smoke_uses_disposable_copy(self) -> None:
        release_root = self.temp_dir / "release"
        installer.build_release_tree(release_root)
        before = self._tree_snapshot(release_root)
        staged_paths: list[Path] = []

        def fake_install(staged_release: Path) -> dict[str, str]:
            staged_paths.append(staged_release)
            return self._fake_runtime_install(staged_release)

        with mock.patch.object(installer, "_install_release_runtime", side_effect=fake_install), mock.patch.object(
            installer,
            "_probe_python_version",
            return_value="3.12.8",
        ):
            result = installer.verify_release_tree(release_root, run_smoke=True)

        self.assertTrue(result["valid"], result["errors"])
        self.assertTrue(result["runtime"]["disposable_stage"])
        self.assertEqual(str(release_root.resolve()), result["release_root"])
        self.assertEqual(before, self._tree_snapshot(release_root))
        self.assertFalse((release_root / ".venv").exists())
        self.assertEqual(1, len(staged_paths))
        self.assertNotEqual(release_root.resolve(), staged_paths[0].resolve())
        self.assertFalse(staged_paths[0].exists())

    def test_release_install_runtime_failure_preserves_current(self) -> None:
        current = self.install_root / "current"
        current.mkdir(parents=True)
        (current / "keep.txt").write_text("active", encoding="utf-8")

        with mock.patch.object(
            installer,
            "_install_release_runtime",
            side_effect=installer.SkillInstallError("dependency install failed"),
        ):
            result = installer.install_release_tree()

        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["activated"])
        self.assertEqual("active", (current / "keep.txt").read_text(encoding="utf-8"))
        self.assertTrue(Path(result["staged_release"]).exists())
        self.assertEqual("dependency install failed", result["runtime_install"]["error"])

    def test_release_install_missing_python_uses_exact_error_and_preserves_current(self) -> None:
        current = self.install_root / "current"
        current.mkdir(parents=True)
        (current / "keep.txt").write_text("active", encoding="utf-8")

        with mock.patch.object(
            installer,
            "_install_release_runtime",
            side_effect=installer.SkillInstallError(installer.RUNTIME_PYTHON_ERROR),
        ):
            with self.assertRaises(installer.SkillInstallError) as ctx:
                installer.install_release_tree()

        self.assertEqual(installer.RUNTIME_PYTHON_ERROR, str(ctx.exception))
        self.assertEqual("active", (current / "keep.txt").read_text(encoding="utf-8"))

    def test_release_install_activates_runtime_and_writes_global_shim(self) -> None:
        with mock.patch.object(installer, "_install_release_runtime", side_effect=self._fake_runtime_install), mock.patch.object(
            installer,
            "_probe_python_version",
            return_value="3.12.8",
        ):
            result = installer.install_release_tree(run_smoke=True)

        self.assertEqual("installed", result["status"])
        current = self.install_root / "current"
        self.assertTrue((current / ".venv" / "bin" / "python").exists())
        manifest = json.loads((current / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("3.12.8", manifest["runtime"]["python_version"])

        shim = self.install_root / "bin" / "deck-master"
        shim_text = shim.read_text(encoding="utf-8")
        self.assertTrue(os.access(shim, os.X_OK))
        self.assertIn('exec "$DECK_MASTER_HOME/current/.venv/bin/python"', shim_text)
        self.assertIn('"$DECK_MASTER_HOME/current/scripts/deck_master.py"', shim_text)

    def test_release_install_activation_failure_does_not_leave_first_install_shim(self) -> None:
        with mock.patch.object(installer, "_install_release_runtime", side_effect=self._fake_runtime_install), mock.patch.object(
            installer,
            "_probe_python_version",
            return_value="3.12.8",
        ), mock.patch.object(
            installer,
            "_activate_staged_release",
            side_effect=installer.SkillInstallError("forced activation failure"),
        ):
            with self.assertRaises(installer.SkillInstallError):
                installer.install_release_tree(run_smoke=True)

        self.assertFalse((self.install_root / "bin" / "deck-master").exists())

    def test_release_install_activation_failure_preserves_existing_shim(self) -> None:
        shim = self.install_root / "bin" / "deck-master"
        shim.parent.mkdir(parents=True)
        shim.write_text("existing shim\n", encoding="utf-8")

        with mock.patch.object(installer, "_install_release_runtime", side_effect=self._fake_runtime_install), mock.patch.object(
            installer,
            "_probe_python_version",
            return_value="3.12.8",
        ), mock.patch.object(
            installer,
            "_activate_staged_release",
            side_effect=installer.SkillInstallError("forced activation failure"),
        ):
            with self.assertRaises(installer.SkillInstallError):
                installer.install_release_tree(run_smoke=True)

        self.assertEqual("existing shim\n", shim.read_text(encoding="utf-8"))

    def test_rollback_verification_failure_restores_previously_active_current(self) -> None:
        current = self.install_root / "current"
        previous = self.install_root / "previous"
        current.mkdir(parents=True)
        previous.mkdir(parents=True)
        (current / "marker.txt").write_text("active-before-rollback", encoding="utf-8")
        (previous / "marker.txt").write_text("invalid-previous", encoding="utf-8")
        shim = self.install_root / "bin" / "deck-master"
        shim.parent.mkdir(parents=True)
        shim.write_text("existing shim\n", encoding="utf-8")
        failed = {
            "schema_version": "deck_master_release_verification.v1",
            "release_root": str(current),
            "valid": False,
            "status": "failed",
            "errors": [{"code": "forced_failure"}],
            "warnings": [],
            "smoke": {"skipped": False, "status": "failed"},
        }

        with mock.patch.object(installer, "verify_release_tree", return_value=failed):
            with self.assertRaises(installer.SkillInstallError):
                installer.rollback_release_tree()

        self.assertEqual("active-before-rollback", (current / "marker.txt").read_text(encoding="utf-8"))
        self.assertEqual("existing shim\n", shim.read_text(encoding="utf-8"))

    def test_activation_record_failure_restores_previously_active_current(self) -> None:
        current = self.install_root / "current"
        staged = self.install_root / "staging" / "release-test"
        current.mkdir(parents=True)
        staged.mkdir(parents=True)
        (current / "marker.txt").write_text("active", encoding="utf-8")
        (staged / "marker.txt").write_text("candidate", encoding="utf-8")

        with mock.patch.object(Path, "write_text", side_effect=OSError("activation record failed")):
            with self.assertRaises(installer.SkillInstallError):
                installer._activate_staged_release(staged)

        self.assertEqual("active", (current / "marker.txt").read_text(encoding="utf-8"))

    def test_source_development_python_compatibility_is_preserved(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('requires-python = ">=3.11,<3.14"', pyproject)


if __name__ == "__main__":
    unittest.main()
