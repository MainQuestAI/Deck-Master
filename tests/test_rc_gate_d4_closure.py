from __future__ import annotations

import copy
import hashlib
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

    def _write_real_v2_artifacts(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        selection_dir = run_dir / "external" / "ppt_library"
        selection_dir.mkdir(parents=True, exist_ok=True)
        candidate = {
            "candidate_id": "candidate-001",
            "slide_id": "slide-001",
            "asset_key": "canonical:slide-001",
            "title": "Reusable page",
            "text_summary": "Safe summary",
            "page_number": 1,
            "score": 0.9,
            "confidence": 0.9,
            "source_asset_id": hashlib.sha256(b"source").hexdigest(),
            "source_display_name": "Reference Deck.pptx",
            "screenshot_ref": "",
            "candidate_origin": "ppt_library",
            "reuse_policy": "reuse_or_adapt",
        }
        selection = {
            "schema_version": "deck_master_ppt_library_selection.v2",
            "run_id": "private-customer-run",
            "status": "library_degraded",
            "source": "ppt_library",
            "preview_degraded": True,
            "warnings": [],
            "selections": [
                {
                    "beat_id": "beat-001",
                    "page_task_id": "page-001",
                    "query_trace_id": hashlib.sha256(b"query").hexdigest(),
                    "role_original": "opener",
                    "role_strategy": "passthrough",
                    "role_mapped": "opener",
                    "retrieval_method": "role_selection",
                    "fallback_reason": "",
                    "preview_status": "missing",
                    "preview_degraded": True,
                    "candidates": [candidate],
                }
            ],
            "by_beat": {"beat-001": [candidate]},
        }
        (selection_dir / "library_results.v2.json").write_text(json.dumps(selection), encoding="utf-8")
        sourcing = {
            "schema_version": "deck_sourcing_plan.v2",
            "run_id": "private-customer-run",
            "status": "approved",
            "source_fingerprint": hashlib.sha256(b"sourcing").hexdigest(),
            "pages": [
                {
                    "page_id": "beat-001",
                    "page_task_id": "page-001",
                    "decision": "reuse",
                    "reason": "approved source",
                    "confidence": 0.9,
                    "evidence_need": [],
                    "selected_sources": [
                        {
                            "asset_key": "canonical:slide-001",
                            "query_trace_id": hashlib.sha256(b"query").hexdigest(),
                            "page_task_id": "page-001",
                        }
                    ],
                    "permission_status": "approved",
                }
            ],
            "created_at": "2026-07-11T00:00:00+00:00",
        }
        (run_dir / "sourcing_plan.json").write_text(json.dumps(sourcing), encoding="utf-8")

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
        self._write_real_v2_artifacts(self.temp_dir)
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

    def test_real_uat_rejects_home_repo_non_temp_and_symlink(self) -> None:
        for unsafe_dir in (Path.home(), ROOT):
            check = rc_gate._real_workflow_uat_check(unsafe_dir)
            self.assertEqual("fail", check["status"])
            self.assertIn("UAT_COPY", check["details"]["failures"][0])

        link = self.temp_dir / "linked-run"
        link.symlink_to(Path.home(), target_is_directory=True)
        check = rc_gate._real_workflow_uat_check(link)
        self.assertEqual("fail", check["status"])
        self.assertIn("SYMLINK", check["details"]["failures"][0])

    def test_real_uat_rejects_symlinks_anywhere_inside_copy(self) -> None:
        outside = self.temp_dir / "outside"
        outside.mkdir()
        (outside / "external.json").write_text("{}", encoding="utf-8")
        for case in ("request", "preview", "nested"):
            with self.subTest(case=case):
                run_dir = self.temp_dir / f"run-{case}"
                self._write_real_v2_artifacts(run_dir)
                if case == "request":
                    (run_dir / "request.json").symlink_to(outside / "external.json")
                elif case == "preview":
                    (run_dir / "preview_manifest.json").symlink_to(outside / "external.json")
                else:
                    (run_dir / "context").mkdir()
                    (run_dir / "context" / "linked").symlink_to(outside, target_is_directory=True)
                check = rc_gate._real_workflow_uat_check(run_dir)
                self.assertEqual("fail", check["status"])
                self.assertIn("UAT_COPY_INTERNAL_SYMLINK_REJECTED", check["details"]["failures"])

    def test_real_uat_accepts_real_v2_artifacts(self) -> None:
        self._write_real_v2_artifacts(self.temp_dir)
        with mock.patch(
            "runtime.rc_gate.run_real_workflow_smoke",
            return_value={
                "status": "pass",
                "summary": {"checks": 4, "passed": 4, "warnings": 0, "failed": 0},
                "phases": {"run_artifacts": "pass", "companion_uat": "pass"},
            },
        ):
            check = rc_gate._real_workflow_uat_check(self.temp_dir)

        self.assertEqual("pass", check["status"], check)
        self.assertEqual("deck_master_ppt_library_selection.v2", check["details"]["artifacts"]["selection_schema"])
        self.assertEqual("deck_sourcing_plan.v2", check["details"]["artifacts"]["sourcing_schema"])

    def test_real_uat_allows_generate_page_without_selected_source(self) -> None:
        self._write_real_v2_artifacts(self.temp_dir)
        sourcing_path = self.temp_dir / "sourcing_plan.json"
        sourcing = json.loads(sourcing_path.read_text(encoding="utf-8"))
        sourcing["pages"][0]["decision"] = "generate"
        sourcing["pages"][0]["selected_sources"] = []
        sourcing_path.write_text(json.dumps(sourcing), encoding="utf-8")
        with mock.patch(
            "runtime.rc_gate.run_real_workflow_smoke",
            return_value={
                "status": "pass",
                "summary": {"checks": 1, "passed": 1, "warnings": 0, "failed": 0},
                "phases": {"run_artifacts": "pass"},
            },
        ):
            check = rc_gate._real_workflow_uat_check(self.temp_dir)
        self.assertEqual("pass", check["status"], check)

    def test_real_uat_rejects_selection_sourcing_identity_mismatches(self) -> None:
        for case in ("missing_asset", "cross_page", "trace_mismatch"):
            with self.subTest(case=case):
                run_dir = self.temp_dir / f"identity-{case}"
                self._write_real_v2_artifacts(run_dir)
                selection_path = run_dir / "external" / "ppt_library" / "library_results.v2.json"
                sourcing_path = run_dir / "sourcing_plan.json"
                selection = json.loads(selection_path.read_text(encoding="utf-8"))
                sourcing = json.loads(sourcing_path.read_text(encoding="utf-8"))
                selected = sourcing["pages"][0]["selected_sources"][0]
                expected_code = ""
                if case == "missing_asset":
                    selected["asset_key"] = "canonical:missing"
                    expected_code = "SOURCING_SELECTION_CANDIDATE_MISSING"
                elif case == "trace_mismatch":
                    selected["query_trace_id"] = hashlib.sha256(b"other-query").hexdigest()
                    expected_code = "SOURCING_SELECTION_TRACE_MISMATCH"
                else:
                    second_candidate = copy.deepcopy(selection["selections"][0]["candidates"][0])
                    second_candidate["candidate_id"] = "candidate-002"
                    second_candidate["slide_id"] = "slide-002"
                    second_candidate["asset_key"] = "canonical:slide-002"
                    second_candidate["source_asset_id"] = hashlib.sha256(b"source-2").hexdigest()
                    second_selection = copy.deepcopy(selection["selections"][0])
                    second_selection["beat_id"] = "beat-002"
                    second_selection["page_task_id"] = "page-002"
                    second_selection["query_trace_id"] = hashlib.sha256(b"query-2").hexdigest()
                    second_selection["candidates"] = [second_candidate]
                    selection["selections"].append(second_selection)
                    second_page = copy.deepcopy(sourcing["pages"][0])
                    second_page["page_id"] = "beat-002"
                    second_page["page_task_id"] = "page-002"
                    second_page["selected_sources"][0]["page_task_id"] = "page-002"
                    sourcing["pages"].append(second_page)
                    expected_code = "SOURCING_SELECTION_CROSS_PAGE"
                selection_path.write_text(json.dumps(selection), encoding="utf-8")
                sourcing_path.write_text(json.dumps(sourcing), encoding="utf-8")
                check = rc_gate._real_workflow_uat_check(run_dir)
                self.assertEqual("fail", check["status"])
                self.assertIn(expected_code, check["details"]["failures"])

    def test_real_uat_rejects_missing_or_v1_artifacts(self) -> None:
        missing = rc_gate._real_workflow_uat_check(self.temp_dir)
        self.assertEqual("fail", missing["status"])
        self.assertIn("SELECTION_V2_MISSING", missing["details"]["failures"])

        self._write_real_v2_artifacts(self.temp_dir)
        selection_path = self.temp_dir / "external" / "ppt_library" / "library_results.v2.json"
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        selection["schema_version"] = "deck_master_ppt_library_selection.v1"
        selection_path.write_text(json.dumps(selection), encoding="utf-8")
        check = rc_gate._real_workflow_uat_check(self.temp_dir)
        self.assertEqual("fail", check["status"])
        self.assertIn("SELECTION_V2_REQUIRED", check["details"]["failures"])

        self._write_real_v2_artifacts(self.temp_dir)
        sourcing_path = self.temp_dir / "sourcing_plan.json"
        sourcing = json.loads(sourcing_path.read_text(encoding="utf-8"))
        sourcing["schema_version"] = "deck_sourcing_plan.v1"
        sourcing_path.write_text(json.dumps(sourcing), encoding="utf-8")
        check = rc_gate._real_workflow_uat_check(self.temp_dir)
        self.assertEqual("fail", check["status"])
        self.assertIn("SOURCING_V2_REQUIRED", check["details"]["failures"])

    def test_real_uat_rejects_duplicate_asset_and_unsafe_selection(self) -> None:
        self._write_real_v2_artifacts(self.temp_dir)
        sourcing_path = self.temp_dir / "sourcing_plan.json"
        sourcing = json.loads(sourcing_path.read_text(encoding="utf-8"))
        duplicate = dict(sourcing["pages"][0])
        duplicate["page_id"] = "beat-002"
        duplicate["page_task_id"] = "page-002"
        duplicate["selected_sources"] = [dict(duplicate["selected_sources"][0], page_task_id="page-002")]
        sourcing["pages"].append(duplicate)
        sourcing_path.write_text(json.dumps(sourcing), encoding="utf-8")
        check = rc_gate._real_workflow_uat_check(self.temp_dir)
        self.assertEqual("fail", check["status"])
        self.assertIn("SOURCING_DUPLICATE_ASSET_KEY", check["details"]["failures"])

        for field in ("source_path", "source_file"):
            with self.subTest(field=field):
                self._write_real_v2_artifacts(self.temp_dir)
                selection_path = self.temp_dir / "external" / "ppt_library" / "library_results.v2.json"
                selection = json.loads(selection_path.read_text(encoding="utf-8"))
                selection["selections"][0]["candidates"][0][field] = "/Users/example/private.pptx"
                selection_path.write_text(json.dumps(selection), encoding="utf-8")
                check = rc_gate._real_workflow_uat_check(self.temp_dir)
                self.assertEqual("fail", check["status"])
                self.assertIn("SELECTION_UNSAFE_CONTENT", check["details"]["failures"])

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
        self.assertIn("run_id", report)
        self.assertNotIn("/Users/", json.dumps(report))
        self.assertIn("library_results/selection.json", json.dumps(report))

        report["metrics"]["source_file"] = "/private/tmp/private-client/input.pptx"
        with self.assertRaises(ValueError):
            write_uat_report(run_dir, "unsafe", report)
        self.assertFalse((run_dir / "uat_reports" / "unsafe.json").exists())


if __name__ == "__main__":
    unittest.main()
