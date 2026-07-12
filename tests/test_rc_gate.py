from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from runtime import rc_gate  # noqa: E402
from runtime.rc_gate import build_rc_gate_report, write_rc_gate_report  # noqa: E402
import server as preview_server  # noqa: E402


class RCGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_rc_gate_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_rc_gate_reports_required_checks_and_skipped_browser_smoke(self) -> None:
        report = build_rc_gate_report(
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
        )

        self.assertEqual("deck_rc_gate_report.v1", report["schema_version"])
        self.assertIn(report["status"], {"pass", "fail"})
        by_id = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("pass", by_id["schema_json_parse"]["status"])
        self.assertEqual("pass", by_id["artifact_validator"]["status"])
        self.assertEqual("pass", by_id["release_smoke"]["status"])
        self.assertEqual("pass", by_id["fixture_e2e"]["status"])
        self.assertEqual("skipped", by_id["browser_smoke"]["status"])
        self.assertIn(by_id["benchmark_aggregate"]["status"], {"pass", "fail"})
        self.assertIn(by_id["external_dependency_closure"]["status"], {"pass", "fail"})

    def test_external_dependency_closure_passes_with_lock_and_report_evidence(self) -> None:
        dependencies = [
            {
                "name": "ppt-master",
                "binding_status": "bound_verified_runtime_blocked",
                "git_sha": "backend-sha",
                "verified": True,
            },
        ]

        def fake_build_release_tree(release_root: Path, *, force: bool = False) -> dict[str, str]:
            release_root.mkdir(parents=True, exist_ok=True)
            (release_root / "deck_capability_lock.json").write_text(
                json.dumps({"external_dependency_status": dependencies}),
                encoding="utf-8",
            )
            return {"status": "built"}

        with mock.patch("runtime.rc_gate.external_dependency_statuses", return_value=dependencies), mock.patch(
            "runtime.rc_gate.build_release_tree",
            side_effect=fake_build_release_tree,
        ):
            check = rc_gate._external_dependency_closure_check({"status": "report_ready"})

        self.assertEqual("external_dependency_closure", check["check_id"])
        self.assertEqual("pass", check["status"])
        self.assertEqual([], check["details"]["failures"])
        self.assertEqual(
            {
                "binding_status": "bound_verified_runtime_blocked",
                "git_sha": "backend-sha",
                "verified": True,
            },
            check["details"]["dependencies"]["ppt-master"],
        )

    def test_rc_gate_ci_tier_skips_local_only_checks_and_passes(self) -> None:
        report = build_rc_gate_report(
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
            tier="ci",
        )

        self.assertEqual("deck_rc_gate_report.v1", report["schema_version"])
        self.assertEqual("ci", report["tier"])
        self.assertEqual("pass", report["status"])
        by_id = {check["check_id"]: check for check in report["checks"]}
        # Reproducible checks still run and pass in a fresh clone.
        self.assertEqual("pass", by_id["schema_json_parse"]["status"])
        self.assertEqual("pass", by_id["artifact_validator"]["status"])
        self.assertEqual("pass", by_id["release_smoke"]["status"])
        self.assertEqual("pass", by_id["fixture_e2e"]["status"])
        self.assertEqual("skipped", by_id["browser_smoke"]["status"])
        # Local-only checks are skipped (not required) so the gate can go green in CI.
        self.assertEqual("skipped", by_id["benchmark_aggregate"]["status"])
        self.assertFalse(by_id["benchmark_aggregate"]["required"])
        # The CI closure still runs a real, required capability-lock consistency check.
        self.assertEqual("pass", by_id["external_dependency_closure"]["status"])
        self.assertTrue(by_id["external_dependency_closure"]["required"])

    def test_external_dependency_closure_ci_check_validates_lock(self) -> None:
        dependencies = [{"name": "ppt-master", "binding_status": "bound_verified", "git_sha": "sha", "verified": True}]

        def fake_build(release_root: Path, *, force: bool = False) -> dict[str, str]:
            release_root.mkdir(parents=True, exist_ok=True)
            (release_root / "deck_capability_lock.json").write_text(
                json.dumps({"external_dependency_status": dependencies}),
                encoding="utf-8",
            )
            return {"status": "built"}

        with mock.patch("runtime.rc_gate.build_release_tree", side_effect=fake_build):
            check = rc_gate._external_dependency_closure_ci_check()
        self.assertEqual("external_dependency_closure", check["check_id"])
        self.assertEqual("pass", check["status"])
        self.assertTrue(check["required"])
        self.assertEqual([], check["details"]["failures"])
        self.assertIn("ppt-master bound_verified assertion", check["details"]["skipped"][0])

        def fake_build_malformed(release_root: Path, *, force: bool = False) -> dict[str, str]:
            release_root.mkdir(parents=True, exist_ok=True)
            (release_root / "deck_capability_lock.json").write_text(
                json.dumps({"external_dependency_status": "not-a-list"}),
                encoding="utf-8",
            )
            return {"status": "built"}

        with mock.patch("runtime.rc_gate.build_release_tree", side_effect=fake_build_malformed):
            check = rc_gate._external_dependency_closure_ci_check()
        self.assertEqual("fail", check["status"])
        self.assertIn("capability lock missing external dependencies", check["details"]["failures"][0])

    def test_browser_smoke_runs_review_desk_when_runtime_available(self) -> None:
        with mock.patch(
            "runtime.rc_gate._run_review_desk_browser_smoke",
            return_value={"run_id": "sample-preview-run", "unsafe_markers": []},
        ):
            check = rc_gate._browser_smoke_check(skip=False, require=False)

        self.assertEqual("browser_smoke", check["check_id"])
        self.assertEqual("pass", check["status"])
        self.assertFalse(check["required"])
        self.assertEqual("sample-preview-run", check["details"]["run_id"])

    def test_review_desk_browser_hides_raw_setup_and_workspace_markers(self) -> None:
        def unsafe_setup_status(**kwargs):
            return {
                "schema_version": "deck_master_setup_status.v2",
                "status": "blocked",
                "install_ready": False,
                "workspace_ready": False,
                "run_ready": False,
                "workspace_entry_ready": False,
                "production_ready": False,
                "production_backend_ready": False,
                "client_delivery_ready": False,
                "config": {
                    "install_root": "/Users/example/.deck-master",
                    "active_workspace": "/Users/example/raw-workspace",
                    "default_runs_dir": "/private/tmp/deck-master-runs",
                },
                "workspace": {"status": "missing"},
                "next_command": "deck-master setup --workspace /Users/example/raw-workspace --output setup-status.json",
                "next_agent_action": "Run raw command from /Users/example/raw-workspace/setup-status.json",
                "setup_blocking_summary": [
                    {
                        "code": "raw_setup_command",
                        "blocking_type": "setup",
                        "message": "raw command: deck-master setup --workspace /Users/example/raw-workspace --output setup-status.json",
                        "repair_owner": "agent",
                    }
                ],
                "workspace_blocking_summary": [
                    {
                        "code": "workspace_path_missing",
                        "blocking_type": "workspace",
                        "message": "workspace path /private/tmp/raw-workspace/request.json is not ready",
                        "repair_owner": "agent",
                    }
                ],
                "blocking_summary": [],
                "suite": {"status": "blocked", "full_suite_ready": False},
                "external_dependency_status": [],
            }

        try:
            details = rc_gate._run_review_desk_browser_smoke(
                setup_status_fixture=unsafe_setup_status,
                expected_title_contains=None,
                expected_visible_text=None,
                forbidden_markers=(
                    "raw command",
                    "/Users/",
                    "/private/",
                    "--workspace",
                    "--run-dir",
                    "deck-master ",
                    ".json",
                ),
            )
        except rc_gate.BrowserSmokeUnavailable as exc:
            self.skipTest(f"Playwright browser runtime is not available: {exc}")

        self.assertEqual("sample-preview-run", details["run_id"])
        self.assertEqual([], details["unsafe_markers"])

    def test_review_desk_browser_hides_raw_workspace_runtime_markers(self) -> None:
        original_workspace_payload = preview_server.build_workspace_payload

        def unsafe_workspace_payload(run_dir):
            payload = original_workspace_payload(run_dir)
            payload["project_stage"]["label"] = "生成中"
            payload["project_stage"]["tone"] = "warning"
            payload["project_stage"]["blocking_reason"] = (
                "deck-master setup --workspace /Users/example/raw-workspace --output setup-status.json"
            )
            payload["stage"] = payload["project_stage"]
            payload["health"]["blocking_reasons"] = [
                "python3 scripts/deck_master.py --run-dir /private/tmp/review-run",
                "/Users/example/raw-workspace/render_result.json",
            ]
            payload["run_summary"]["delivery_preview"]["detail"] = (
                "check render_result.json artifact_path rendered/index.html"
            )
            payload["run_summary"]["next_actions"] = [
                {
                    "action_type": "next_action",
                    "message": "deck-master setup --workspace /Users/example/raw-workspace --output blocked.json",
                }
            ]
            payload["run_summary"]["main_risks"] = []
            return payload

        try:
            details = rc_gate._run_review_desk_browser_smoke(
                setup_status_fixture=rc_gate._safe_smoke_setup_status,
                workspace_payload_fixture=unsafe_workspace_payload,
                expected_visible_text="当前仍有前置项需要处理。",
                forbidden_markers=(
                    "/Users/",
                    "/private/",
                    "--workspace",
                    "--run-dir",
                    "python3 ",
                    "deck-master ",
                    "artifact_path",
                    "render_result",
                    "rendered/index.html",
                    ".json",
                ),
            )
        except rc_gate.BrowserSmokeUnavailable as exc:
            self.skipTest(f"Playwright browser runtime is not available: {exc}")

        self.assertEqual("sample-preview-run", details["run_id"])
        self.assertEqual([], details["unsafe_markers"])

    def test_review_desk_browser_drops_unsafe_preview_urls_and_approval_attributes(self) -> None:
        original_workspace_payload = preview_server.build_workspace_payload

        def unsafe_workspace_payload(run_dir):
            approval_dir = Path(run_dir) / "review_workspace"
            approval_dir.mkdir(parents=True, exist_ok=True)
            (approval_dir / "approval_tasks.json").write_text(
                json.dumps(
                    {
                        "schema_version": "deck_workspace_approval.v1",
                        "tasks": [
                            {
                                "approval_id": "approval-safe_01",
                                "scope_type": "page",
                                "target_id": "page_001",
                                "subject": "页面审批",
                                "reason": "验证 data 属性扫描。",
                                "status": "pending",
                                "submitted_by": "alice",
                                "submitted_at": "2026-06-01T00:00:00+08:00",
                            },
                            {
                                "approval_id": "/private/tmp/raw-approval.json?cmd=deck-master --run-dir /Users/example/run",
                                "scope_type": "javascript:alert(1)?cmd=/private/tmp/scope.json",
                                "target_id": "page_001",
                                "subject": "恶意审批字段",
                                "reason": "恶意属性不得进入 DOM。",
                                "status": "pending",
                                "submitted_by": "alice",
                                "submitted_at": "2026-06-01T00:00:00+08:00",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = original_workspace_payload(run_dir)
            payload["project_stage"]["label"] = "可交付"
            payload["project_stage"]["tone"] = "/private/tmp/raw-stage-tone.json?cmd=deck-master --run-dir /Users/example/run"
            payload["stage"] = payload["project_stage"]
            payload["run_summary"]["delivery_preview"].update(
                {
                    "artifact_ready": True,
                    "artifact_url": "/Users/example/raw-artifact.json?cmd=deck-master%20--run-dir%20/private/tmp/run",
                    "summary": "交付级预览已就绪。",
                    "detail": "可以切换到交付预览查看最终交付形态。",
                }
            )
            payload["queue"]["pages"][0]["preview_url"] = (
                "/private/tmp/raw-preview.json?cmd=python3%20scripts/deck_master.py%20--run-dir%20/Users/example/run"
            )
            payload["queue"]["pages"][0]["status_tone"] = "/Users/example/raw-status-tone.json?cmd=deck-master"
            payload["queue"]["pages"][0]["has_preview"] = True
            return payload

        try:
            details = rc_gate._run_review_desk_browser_smoke(
                setup_status_fixture=rc_gate._safe_smoke_setup_status,
                workspace_payload_fixture=unsafe_workspace_payload,
                exercise_delivery_preview=True,
                forbidden_markers=(
                    "/Users/",
                    "/private/",
                    "--run-dir",
                    "python3 ",
                    "deck-master ",
                    ".json",
                    "cmd=",
                    "javascript:",
                ),
            )
        except rc_gate.BrowserSmokeUnavailable as exc:
            self.skipTest(f"Playwright browser runtime is not available: {exc}")

        attribute_values = details["attribute_values"]
        attribute_text_values = [str(item.get("value") or "") for item in attribute_values]
        attribute_names = {(str(item.get("attribute") or ""), str(item.get("value") or "")) for item in attribute_values}
        joined_values = "\n".join(attribute_text_values)
        self.assertEqual("sample-preview-run", details["run_id"])
        self.assertTrue(details["exercised_delivery_preview"])
        self.assertEqual([], details["unsafe_attribute_values"])
        self.assertTrue(any(str(item.get("attribute") or "") == "class" for item in attribute_values))
        self.assertIn(("data-scope", "page"), attribute_names)
        self.assertIn(("data-approval-id", "approval-safe_01"), attribute_names)
        self.assertNotIn("/Users/", joined_values)
        self.assertNotIn("/private/", joined_values)
        self.assertNotIn(".json", joined_values)
        self.assertNotIn("--run-dir", joined_values)
        self.assertNotIn("cmd=", joined_values)
        self.assertNotIn("javascript:", joined_values)

    def test_browser_smoke_skips_optional_when_runtime_unavailable(self) -> None:
        with mock.patch(
            "runtime.rc_gate._run_review_desk_browser_smoke",
            side_effect=rc_gate.BrowserSmokeUnavailable("missing browser"),
        ):
            check = rc_gate._browser_smoke_check(skip=False, require=False)

        self.assertEqual("skipped", check["status"])
        self.assertFalse(check["required"])
        self.assertIn("missing browser", check["details"]["error"])

    def test_browser_smoke_fails_required_when_runtime_unavailable(self) -> None:
        with mock.patch(
            "runtime.rc_gate._run_review_desk_browser_smoke",
            side_effect=rc_gate.BrowserSmokeUnavailable("missing browser"),
        ):
            check = rc_gate._browser_smoke_check(skip=False, require=True)

        self.assertEqual("fail", check["status"])
        self.assertTrue(check["required"])
        self.assertIn("missing browser", check["details"]["error"])

    def test_write_rc_gate_report_outputs_json_and_markdown(self) -> None:
        result = write_rc_gate_report(
            self.temp_dir / "rc-gate",
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
        )

        self.assertIn(result["status"], {"pass", "fail"})
        self.assertTrue(Path(result["report"]).exists())
        self.assertTrue(Path(result["markdown"]).exists())
        payload = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
        self.assertEqual("deck_rc_gate_report.v1", payload["schema_version"])
        self.assertIn("Deck Master RC Gate Report", Path(result["markdown"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
