"""Regression coverage for Review Desk setup gating."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "scripts" / "preview" / "static" / "app.js"


class PreviewWorkspaceGateRegressionTests(unittest.TestCase):
    def test_setup_shell_only_blocks_when_no_project_context_exists(self) -> None:
        """Regression: incomplete workspace repair must not hide existing runs."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function canEnterProjectContext()", script)
        self.assertIn("if (state.setupStatus && !setupReady() && !canEnterProjectContext())", script)
        self.assertIn("当前 workspace 仍有前置项待补齐，但已有方案项目可继续查看。", script)

    def test_boot_and_refresh_always_reload_project_list(self) -> None:
        """Regression: run deep links must still load project metadata when setup is incomplete."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("await loadProjects();", script)
        self.assertNotIn("if (setupReady()) {\n      await loadProjects();\n    }", script)
        self.assertNotIn("async function loadWorkspace() {\n  if (!setupReady()) {", script)
        self.assertNotIn("async function refreshCurrentProject() {\n  await loadSetupStatus({ silent: true });\n  if (!setupReady()) {", script)


if __name__ == "__main__":
    unittest.main()
