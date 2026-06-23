from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skills.installer import build_release_tree  # noqa: E402


class InstalledReleaseRCGateRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_installed_rc_gate_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_release_tree_can_run_rc_gate_from_its_own_layout(self) -> None:
        # Regression: installed release rc-gate looked for source-only
        # product_capabilities and missed release-local capabilities.
        # Found by /qa on 2026-06-22.
        release_root = self.temp_dir / "release"
        build_release_tree(release_root, force=True)

        self.assertTrue((release_root / "capabilities" / "ppt-master" / "capability.json").exists())
        self.assertTrue((release_root / "examples" / "briefs" / "retail_digital_transformation.txt").exists())
        self.assertTrue((release_root / "benchmarks" / "cases" / "real_retail_growth" / "benchmark_case.json").exists())

        output_dir = self.temp_dir / "rc-gate"
        completed = subprocess.run(
            [
                str(release_root / "bin" / "deck-master"),
                "rc-gate",
                "--output-dir",
                str(output_dir),
                "--skip-browser-smoke",
            ],
            cwd=self.temp_dir,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

        self.assertEqual(0, completed.returncode, completed.stderr[-2000:])
        payload = json.loads((output_dir / "rc_gate_report.json").read_text(encoding="utf-8"))
        self.assertEqual("fail", payload["status"])
        checks = {check["check_id"]: check for check in payload["checks"]}
        self.assertEqual("fail", checks["benchmark_aggregate"]["status"])
        self.assertEqual("metadata_ready", checks["benchmark_aggregate"]["details"]["status"])


if __name__ == "__main__":
    unittest.main()
