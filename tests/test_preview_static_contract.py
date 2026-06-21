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


if __name__ == "__main__":
    unittest.main()
