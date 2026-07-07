from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.builder_backend import external_dependency_statuses  # noqa: E402


class OpenSourcePreviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_oss_preview_"))
        self.home = self.temp_dir / "home"
        self.home.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _write_demo_run(self, page_count: int = 10) -> Path:
        run_dir = self.temp_dir / "runs" / "oss-demo"
        run_dir.mkdir(parents=True)
        for name in ("request.json", "narrative_plan.json", "page_tasks.json", "sourcing_plan.json"):
            (run_dir / name).write_text("{}\n", encoding="utf-8")
        manifest = {
            "run_id": "oss-demo",
            "title": "Retail Transformation Demo",
            "status": "draft",
            "pages": [
                {
                    "page_id": f"page_{index:03d}",
                    "order": index,
                    "title": f"Demo Page {index}",
                    "source_type": "fixture",
                    "preview_path": f"links/page_{index:03d}.svg",
                    "decision": "needs_review",
                }
                for index in range(1, page_count + 1)
            ],
        }
        (run_dir / "preview_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return run_dir

    def test_external_dependencies_only_report_production_backend(self) -> None:
        with mock.patch.dict(os.environ, {"DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE": ""}, clear=False):
            statuses = external_dependency_statuses(render_runtime_ready=False)

        self.assertEqual({"ppt-master"}, {item["name"] for item in statuses})
        backend = statuses[0]
        self.assertIn(backend["binding_status"], {"unbound", "bound_verified", "bound_verified_runtime_blocked"})

    def test_product_capability_manifest_separates_pdpm_from_production_backend(self) -> None:
        manifest = json.loads((ROOT / "product-capability-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual({"deck-builder": "ppt-master"}, manifest["backend_dependencies"])
        self.assertEqual("ppt-deck-pro-max", manifest["suite_skill_dependencies"]["deck-producer"])
        self.assertIn("ppt-deck-pro-max", manifest["compatibility_skills"])

    def test_preview_gate_passes_fixture_demo_without_backend_binding(self) -> None:
        run_dir = self._write_demo_run()
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deck_master.py"),
                "preview-gate",
                "--run-dir",
                str(run_dir),
                "--expect-unconfigured-backend-ok",
            ],
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home), "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("deck_master_preview_gate.v1", payload["schema_version"])
        self.assertEqual("pass", payload["status"])
        checks = {item["check_id"]: item for item in payload["checks"]}
        self.assertEqual("pass", checks["preview_pages"]["status"])
        self.assertEqual("pass", checks["unconfigured_backend_not_ready"]["status"])


if __name__ == "__main__":
    unittest.main()
