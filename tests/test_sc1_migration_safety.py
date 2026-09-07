"""SC-1 PR-08 tests: A6 install/migrate/rollback integration.

Acceptance mapping:
- M-05: a software rollback never deletes user data — runs and workspaces
  created before and between installs survive release-rollback untouched.
- M-06 / A-06 (partial): unknown hosts are not fabricated — the installer
  rejects unsupported targets instead of pretending support.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from skills.installer import (  # noqa: E402
    SkillInstallError,
    build_release_tree,
    install_release_tree,
    resolve_install_directory,
    rollback_release_tree,
)


def _fake_release_runtime(release_root: Path) -> dict[str, str]:
    import sys as _sys

    from skills import installer as installer_module

    runtime_python = release_root / installer_module.RELEASE_PYTHON_RELATIVE
    runtime_python.parent.mkdir(parents=True, exist_ok=True)
    runtime_python.symlink_to(_sys.executable)
    installer_module._record_release_runtime(release_root, "3.12.8")
    return {
        "python_requirement": installer_module.RUNTIME_PYTHON_REQUIREMENT,
        "python_version": "3.12.8",
        "interpreter": installer_module.RELEASE_PYTHON_RELATIVE,
    }


class RollbackUserSafetyTests(unittest.TestCase):
    def test_rollback_never_touches_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "skills.installer.INSTALL_LOG_DIR", Path(tmp) / ".deck-master"
        ), mock.patch.object(Path, "home", return_value=Path(tmp)), mock.patch(
            "skills.installer._probe_python_version", return_value="3.12.8"
        ), mock.patch(
            "skills.installer._install_release_runtime", side_effect=_fake_release_runtime
        ):
            home = Path(tmp)
            # user data created BEFORE the install (existing customer state)
            user_runs = home / "workspaces" / "client-a" / "runs" / "run-001"
            user_runs.mkdir(parents=True)
            (user_runs / "request.json").write_text('{"run_id": "run-001"}', encoding="utf-8")
            (home / "workspaces" / "client-a" / "assets").mkdir(parents=True)
            feedback = home / "workspaces" / "client-a" / "assets" / "asset_feedback.jsonl"
            feedback.write_text('{"event_type": "preview_approved"}\n', encoding="utf-8")

            current = home / ".deck-master" / "current"
            build_release_tree(current, force=True)
            _fake_release_runtime(current)
            install_result = install_release_tree(run_smoke=True)
            self.assertTrue(install_result["activated"])

            # user creates NEW data after the install
            new_run = home / "workspaces" / "client-a" / "runs" / "run-002"
            new_run.mkdir(parents=True)
            (new_run / "request.json").write_text('{"run_id": "run-002"}', encoding="utf-8")

            # roll the software back
            result = rollback_release_tree()
            self.assertEqual("rolled_back", result["status"])

            # user data — both pre-existing and new — survives untouched
            self.assertTrue((user_runs / "request.json").exists())
            self.assertTrue((new_run / "request.json").exists())
            self.assertEqual(
                '{"event_type": "preview_approved"}\n', feedback.read_text(encoding="utf-8")
            )

    def test_unknown_host_is_rejected_not_faked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(Path, "home", return_value=Path(tmp)):
            with self.assertRaises(SkillInstallError):
                resolve_install_directory("cursor", scope="global")
            with self.assertRaises(SkillInstallError):
                resolve_install_directory("custom", scope="global")


if __name__ == "__main__":
    unittest.main()
