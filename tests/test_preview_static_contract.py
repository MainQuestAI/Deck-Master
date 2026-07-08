"""Static UI contract tests for preview workbench interactions."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "scripts" / "preview" / "static" / "index.html"
APP_JS = ROOT / "scripts" / "preview" / "static" / "app.js"


class PreviewStaticContractTests(unittest.TestCase):
    def test_shell_state_adapter_covers_setup_and_project_selection(self) -> None:
        """Regression: main shell state must own setup and project-selection entry states."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function deriveShellState()", script)
        self.assertIn("Setup 未就绪", script)
        self.assertIn("待选择项目", script)
        self.assertIn("工作台还未准备完成", script)
        self.assertIn("先选择一个方案项目", script)

    def test_left_rail_is_labeled_as_task_directory(self) -> None:
        """Regression: left rail should read as task directory instead of raw page dump."""

        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="queue-panel-label"', html)
        self.assertIn(">任务目录<", html)

    def test_language_toggle_is_disabled_until_i18n_ready(self) -> None:
        """Regression: ISSUE-001 — no-op language toggle looked clickable.

        Found by /qa on 2026-06-22.
        Report: .gstack/qa-reports/qa-report-localhost-2026-06-22.md
        """

        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="lang-toggle"', html)
        self.assertIn('disabled title="语言切换将在后续迭代开放"', html)

    def test_preview_shell_has_no_external_font_requests(self) -> None:
        """Regression: the local workbench must not depend on third-party fonts."""

        html = INDEX_HTML.read_text(encoding="utf-8")
        blocked_hosts = ("fonts.googleapis.com", "fonts.gstatic.com", "api.fontshare.com")
        for host in blocked_hosts:
            with self.subTest(host=host):
                self.assertNotIn(host, html)

    def test_stage_workspace_surfaces_selected_page_context(self) -> None:
        """Regression: ISSUE-002 — page selection looked like a dead click in stage mode.

        Found by /qa on 2026-06-22.
        Report: .gstack/qa-reports/qa-report-localhost-2026-06-22.md
        """

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("当前选中页面（待就绪）", script)
        self.assertIn("当前选中页面", script)
        self.assertIn("等待生成完成", script)

    def test_review_desk_identity_and_safe_display_contract(self) -> None:
        """Regression: v0.3 shell must not surface machine commands as user copy."""

        html = INDEX_HTML.read_text(encoding="utf-8")
        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("Deck Master Review Desk", html)
        self.assertIn(">Review Desk<", html)
        self.assertIn("function safeDisplayText(", script)
        self.assertIn("unsafeVisibleTextPattern", script)
        self.assertIn("诊断命令由执行器管理，仅展示可执行状态。", script)
        self.assertNotIn("setup.next_command ||", script)
        self.assertNotIn("runState.next_command ||", script)

    def test_setup_entry_uses_workspace_readiness_not_delivery_readiness(self) -> None:
        """Regression: workspace entry must not be blocked by client delivery readiness."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function workspaceEntryReady()", script)
        self.assertIn("setup.workspace_entry_ready", script)
        self.assertIn("function clientDeliveryReady()", script)
        self.assertIn("client_delivery_blocking_summary", script)
        self.assertNotIn("setup.production_ready", script)

    def test_quality_and_alert_cards_route_visible_copy_through_safe_display(self) -> None:
        """Regression: risk summaries and next actions must not bypass safe display filtering."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("detail: safeDisplayText(", script)
        self.assertIn("safeDisplayText(risk.summary || \"\", \"当前存在质量风险。\")", script)
        self.assertIn("safeDisplayText(risk.repair_instruction || \"\", \"当前没有修复说明\")", script)

    def test_run_level_visible_text_routes_through_safe_display(self) -> None:
        """Regression: run-level visible text must not expose paths, commands, or internal files."""

        script = APP_JS.read_text(encoding="utf-8")
        self.assertIn("function safeErrorMessage(", script)
        self.assertIn("function safeDeliveryDetail(", script)
        self.assertIn("stageBlockerSummary(stage, \"当前还没有页面进入可逐页处理状态。\")", script)
        self.assertIn("safeDeliveryDetail(delivery.detail", script)
        self.assertIn("safeDeliveryDetail(deliveryPreview.detail", script)
        self.assertIn("safeDisplayText(item.message, \"当前存在待处理动作。\")", script)
        self.assertIn("safeDisplayText(item, \"当前仍有前置项需要处理。\")", script)
        self.assertIn("safeErrorMessage(error, \"方案项目创建失败，请先确认 setup 状态。\")", script)
        self.assertNotIn("detail: error.message", script)
        self.assertNotIn("setFeedback(error.message", script)
        self.assertNotIn("textContent = error.message", script)
        self.assertNotIn("stage.blocking_reason ||", script)
        self.assertNotIn("delivery.detail ||", script)
        self.assertNotIn("deliveryPreview.detail ||", script)

    def test_decision_rail_order_prioritizes_actions_before_context_blocks(self) -> None:
        """Regression: redesigned decision rail keeps actions before context and approval."""

        html = INDEX_HTML.read_text(encoding="utf-8")
        actions_pos = html.index("decision-block-actions")
        role_pos = html.index('id="page-role-content"')
        source_pos = html.index('id="page-source-content"')
        risk_pos = html.index('id="page-risk-content"')
        approval_pos = html.index('id="approval-content"')
        self.assertLess(actions_pos, role_pos)
        self.assertLess(role_pos, source_pos)
        self.assertLess(source_pos, risk_pos)
        self.assertLess(risk_pos, approval_pos)


if __name__ == "__main__":
    unittest.main()
