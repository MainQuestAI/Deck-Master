"""Unit tests for v0.9.6 Render Tool UAT contracts."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

render_uat = importlib.import_module("scripts.uat.render_tool")


class RenderToolUATTest(unittest.TestCase):
    def _run_dir(self, root: Path, run_id: str = "retail-demo") -> Path:
        run_dir = root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "request.json").write_text(
            json.dumps({"run_id": run_id}, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "exports").mkdir()
        (run_dir / "export_queue.json").write_text(
            json.dumps({"run_id": run_id, "slides": [{"beat_id": "beat-001"}]}),
            encoding="utf-8",
        )
        return run_dir

    def _render_result(
        self,
        run_dir: Path,
        *,
        artifact_exists: bool = True,
        page_count: int = 1,
    ) -> Path:
        artifact_path = run_dir / "exports" / "retail-demo.pptx"
        if artifact_exists:
            artifact_path.write_bytes(b"fake-pptx")

        render_result = {
            "schema_version": "deck_render_result.v1",
            "run_id": "retail-demo",
            "tool": "ppt-master",
            "status": "completed",
            "artifact_path": "exports/retail-demo.pptx",
            "preview_dir": "exports/previews",
            "page_count": page_count,
            "errors": [],
        }
        path = run_dir / "render_result.json"
        path.write_text(json.dumps(render_result, ensure_ascii=False), encoding="utf-8")
        return path

    def test_valid_render_result_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._render_result(run_dir)

            report = render_uat.run_render_tool_uat(
                run_dir=run_dir,
                input_path=input_path,
            )

            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["metrics"]["artifact_exists"])
            self.assertEqual(report["metrics"]["page_count"], 1)

    def test_missing_artifact_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._render_result(run_dir, artifact_exists=False)

            report = render_uat.run_render_tool_uat(
                run_dir=run_dir,
                input_path=input_path,
            )

            self.assertEqual(report["status"], "fail")
            self.assertFalse(report["metrics"]["artifact_exists"])

    def test_page_count_delta_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(Path(tmp))
            input_path = self._render_result(run_dir, page_count=3)

            report = render_uat.run_render_tool_uat(
                run_dir=run_dir,
                input_path=input_path,
            )

            self.assertEqual(report["status"], "warning")
            self.assertEqual(report["metrics"]["expected_page_count"], 1)
            self.assertEqual(report["metrics"]["page_count_delta"], 2)
            self.assertTrue(
                any("page_count" in finding["finding_id"] for finding in report["findings"])
            )


if __name__ == "__main__":
    unittest.main()
