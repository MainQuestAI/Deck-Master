from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.rc_gate import build_rc_gate_report, write_rc_gate_report  # noqa: E402


class RCGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_rc_gate_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_rc_gate_blocks_metadata_only_benchmarks(self) -> None:
        report = build_rc_gate_report(
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
        )

        self.assertEqual("deck_rc_gate_report.v1", report["schema_version"])
        self.assertEqual("fail", report["status"])
        by_id = {check["check_id"]: check for check in report["checks"]}
        self.assertEqual("pass", by_id["schema_json_parse"]["status"])
        self.assertEqual("pass", by_id["artifact_validator"]["status"])
        self.assertEqual("pass", by_id["release_smoke"]["status"])
        self.assertEqual("pass", by_id["fixture_e2e"]["status"])
        self.assertEqual("skipped", by_id["browser_smoke"]["status"])
        self.assertEqual("fail", by_id["benchmark_aggregate"]["status"])
        self.assertEqual("metadata_ready", by_id["benchmark_aggregate"]["details"]["status"])

    def test_write_rc_gate_report_outputs_json_and_markdown(self) -> None:
        result = write_rc_gate_report(
            self.temp_dir / "rc-gate",
            benchmark_dir=ROOT / "benchmarks",
            skip_browser_smoke=True,
        )

        self.assertEqual("fail", result["status"])
        self.assertTrue(Path(result["report"]).exists())
        self.assertTrue(Path(result["markdown"]).exists())
        payload = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
        self.assertEqual("deck_rc_gate_report.v1", payload["schema_version"])
        self.assertIn("Deck Master RC Gate Report", Path(result["markdown"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
