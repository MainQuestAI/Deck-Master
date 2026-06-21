"""Static UI contract tests for preview workbench interactions."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "scripts" / "preview" / "static" / "index.html"
APP_JS = ROOT / "scripts" / "preview" / "static" / "app.js"


class PreviewStaticContractTests(unittest.TestCase):
    def test_language_toggle_is_disabled_until_i18n_ready(self) -> None:
        """Regression: ISSUE-001 — no-op language toggle looked clickable.

        Found by /qa on 2026-06-22.
        Report: .gstack/qa-reports/qa-report-localhost-2026-06-22.md
        """

        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="lang-toggle"', html)
        self.assertIn('disabled title="语言切换将在后续迭代开放"', html)

    def test_stage_workspace_surfaces_selected_page_context(self) -> None:
        """Regression: ISSUE-002 — page selection looked like a dead click in stage mode.

        Found by /qa on 2026-06-22.
        Report: .gstack/qa-reports/qa-report-localhost-2026-06-22.md
        """

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("当前选中页面（待就绪）", script)
        self.assertIn("当前选中页面", script)
        self.assertIn("等待生成完成", script)


if __name__ == "__main__":
    unittest.main()
