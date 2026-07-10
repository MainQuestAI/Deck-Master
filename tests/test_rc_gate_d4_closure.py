from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from runtime import rc_gate  # noqa: E402
from uat.report import build_check, build_uat_report, write_uat_report  # noqa: E402


class RCGateD4ClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_rc_d4_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_unknown_tier_fails_closed(self) -> None:
        with self.assertRaises(rc_gate.RCGateError):
            rc_gate.build_rc_gate_report(tier="typo")

    def test_ci_contract_checks_cover_bridge_sourcing_status_and_fixture_policy(self) -> None:
        with mock.patch(
            "runtime.rc_gate.build_benchmark_aggregate_report",
            side_effect=AssertionError("CI must not read local benchmark evidence"),
        ):
            report = rc_gate.build_rc_gate_report(
                benchmark_dir=ROOT / "benchmarks",
                skip_browser_smoke=True,
                tier="ci",
            )

        self.assertEqual("pass", report["status"])
        checks = {check["check_id"]: check for check in report["checks"]}
        for check_id in (
            "bridge_v2_contract",
            "sourcing_v2_contract",
            "library_status_v2_contract",
            "strict_fixture_policy",
        ):
            self.assertEqual("pass", checks[check_id]["status"], checks[check_id])
            self.assertTrue(checks[check_id]["required"])
        self.assertNotIn("source_file", json.dumps(report, ensure_ascii=False))
        self.assertNotIn("source_path", json.dumps(report, ensure_ascii=False))

    def test_full_tier_requires_real_uat_evidence(self) -> None:
        report = rc_gate.build_rc_gate_report(
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
            tier="full",
            uat_run_dir=None,
        )

        checks = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["real_workflow_uat"]["status"])
        self.assertTrue(checks["real_workflow_uat"]["required"])

    def test_full_tier_treats_uat_warning_as_failure(self) -> None:
        with mock.patch(
            "runtime.rc_gate.run_real_workflow_smoke",
            return_value={
                "schema_version": "deck_real_workflow_smoke.v1",
                "status": "warning",
                "summary": {"checks": 2, "passed": 1, "warnings": 1, "failed": 0},
                "phases": {"run_artifacts": "pass", "companion_uat": "warning"},
            },
        ):
            check = rc_gate._real_workflow_uat_check(self.temp_dir)

        self.assertEqual("fail", check["status"])
        self.assertEqual("warning", check["details"]["uat_status"])

    def test_rc_evidence_scan_fails_closed_for_paths_fields_and_customer_marker(self) -> None:
        unsafe_report = {
            "schema_version": rc_gate.SCHEMA_VERSION,
            "status": "pass",
            "tier": "ci",
            "created_at": "2026-07-11T00:00:00+00:00",
            "benchmark_dir": "benchmarks",
            "summary": {"checks": 1, "required_failures": 0, "optional_warnings": 0},
            "checks": [
                {
                    "check_id": "unsafe",
                    "status": "pass",
                    "required": True,
                    "summary": "private-client evidence",
                    "details": {"source_path": "/Users/example/private-client/input.pptx"},
                }
            ],
        }
        output_dir = self.temp_dir / "rc"
        with mock.patch("runtime.rc_gate.build_rc_gate_report", return_value=unsafe_report):
            with self.assertRaises(rc_gate.RCGateError):
                rc_gate.write_rc_gate_report(
                    output_dir,
                    tier="ci",
                    evidence_forbidden_markers=["private-client"],
                )

        self.assertFalse((output_dir / "rc_gate_report.json").exists())
        self.assertFalse((output_dir / "rc_gate_report.md").exists())

    def test_uat_refs_are_sanitized_and_unsafe_payload_fails_closed(self) -> None:
        run_dir = self.temp_dir / "run"
        run_dir.mkdir()
        (run_dir / "request.json").write_text(json.dumps({"run_id": "uat-run"}), encoding="utf-8")
        check = build_check(
            "unsafe-ref",
            False,
            "warning",
            "Input needs review.",
            refs=["/Users/example/private-client/input.pptx", "library_results/selection.json"],
        )
        report = build_uat_report(run_dir, "ppt_library", [check], {}, [])
        self.assertNotIn("/Users/", json.dumps(report))
        self.assertIn("library_results/selection.json", json.dumps(report))

        report["metrics"]["source_file"] = "/private/tmp/private-client/input.pptx"
        with self.assertRaises(ValueError):
            write_uat_report(run_dir, "unsafe", report)
        self.assertFalse((run_dir / "uat_reports" / "unsafe.json").exists())


if __name__ == "__main__":
    unittest.main()
