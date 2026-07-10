from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skills.installer import build_release_tree, _install_release_runtime  # noqa: E402


class InstalledReleaseRCGateRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_installed_rc_gate_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def build_installed_release(self, release_root: Path) -> None:
        python312 = shutil.which("python3.12")
        if not python312:
            self.skipTest("python3.12 is required for installed-release regression tests")
        build_release_tree(release_root, force=True)
        with mock.patch.dict(os.environ, {"DECK_MASTER_PYTHON": python312}):
            _install_release_runtime(release_root)

    def test_release_local_fixture_sourcing_loads_jsonschema(self) -> None:
        release_root = self.temp_dir / "release-sourcing"
        self.build_installed_release(release_root)
        runs_dir = self.temp_dir / "runs"
        env = {
            **os.environ,
            "DECK_MASTER_DEV_SKIP_SETUP": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        plan = subprocess.run(
            [
                str(release_root / "bin" / "deck-master"),
                "plan",
                "--brief-file",
                str(release_root / "examples" / "briefs" / "retail_digital_transformation.txt"),
                "--industry",
                "retail",
                "--run-mode",
                "fixture",
                "--runs-dir",
                str(runs_dir),
                "--run-id",
                "runtime-jsonschema",
            ],
            cwd=release_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(0, plan.returncode, plan.stderr[-2000:])
        run_dir = Path(json.loads(plan.stdout)["run_dir"])

        search = subprocess.run(
            [
                str(release_root / "bin" / "deck-master"),
                "search-library",
                "--run-dir",
                str(run_dir),
                "--library-mode",
                "fixture",
            ],
            cwd=release_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(0, search.returncode, search.stderr[-2000:])

        sourcing = subprocess.run(
            [
                str(release_root / "bin" / "deck-master"),
                "decide-sourcing",
                "--run-dir",
                str(run_dir),
            ],
            cwd=release_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        self.assertEqual(0, sourcing.returncode, sourcing.stderr[-2000:])
        self.assertEqual("sourcing_ready", json.loads(sourcing.stdout)["status"])

    def test_release_tree_can_run_rc_gate_from_its_own_layout(self) -> None:
        # Regression: installed release rc-gate looked for source-only
        # product_capabilities and missed release-local capabilities.
        # Found by /qa on 2026-06-22.
        release_root = self.temp_dir / "release"
        self.build_installed_release(release_root)

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

    def test_release_tree_ci_tier_rc_gate_passes_without_local_evidence(self) -> None:
        # The CI tier must pass on a fresh clone / release tree that has no
        # local-only benchmark results and no bound production backend.
        release_root = self.temp_dir / "release-ci"
        self.build_installed_release(release_root)

        output_dir = self.temp_dir / "rc-gate-ci"
        completed = subprocess.run(
            [
                str(release_root / "bin" / "deck-master"),
                "rc-gate",
                "--tier",
                "ci",
                "--output-dir",
                str(output_dir),
                "--skip-browser-smoke",
                "--force",
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
        self.assertEqual("ci", payload["tier"])
        self.assertEqual("pass", payload["status"])
        checks = {check["check_id"]: check for check in payload["checks"]}
        self.assertEqual("skipped", checks["benchmark_aggregate"]["status"])
        self.assertFalse(checks["benchmark_aggregate"]["required"])
        self.assertEqual("pass", checks["external_dependency_closure"]["status"])
        self.assertTrue(checks["external_dependency_closure"]["required"])



if __name__ == "__main__":
    unittest.main()
