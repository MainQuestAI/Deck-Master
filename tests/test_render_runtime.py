from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from runtime.render import (  # noqa: E402
    CANONICAL_RENDER_RESULT,
    RENDER_SESSION_NAME,
    find_render_result,
    render_fixture_html,
    render_status,
)
from runtime.run_state import create_run, read_json, write_json  # noqa: E402


class RenderRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_render_runtime_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.run_dir = create_run(
            self.temp_dir,
            {"run_id": "render-run", "project_name": "Render Run", "run_mode": "fixture"},
            run_id="render-run",
        )
        write_json(
            self.run_dir / "preview_manifest.json",
            {
                "run_id": "render-run",
                "pages": [
                    {"page_id": "beat_01", "order": 1, "title": "Opening", "preview_path": "links/beat_01.svg"}
                ],
            },
        )

    def test_render_fixture_html_writes_canonical_result(self) -> None:
        result = render_fixture_html(self.run_dir, fixture_safe=True)

        self.assertEqual("completed", result["status"])
        self.assertTrue((self.run_dir / "rendered" / "index.html").exists())
        self.assertTrue((self.run_dir / RENDER_SESSION_NAME).exists())
        render_result = read_json(self.run_dir / CANONICAL_RENDER_RESULT)
        self.assertEqual("deck_render_result.v1", render_result["schema_version"])
        self.assertEqual("rendered/index.html", render_result["artifact_path"])
        self.assertEqual(1, render_result["page_count"])
        status = render_status(self.run_dir)
        self.assertEqual("present", status["status"])
        self.assertEqual("canonical", status["source"])

    def test_find_render_result_reads_legacy_only_as_fallback(self) -> None:
        legacy_path = self.run_dir / "render_result.json"
        write_json(
            legacy_path,
            {
                "schema_version": "deck_render_result.v1",
                "run_id": "render-run",
                "tool": "ppt-master",
                "status": "completed",
                "artifact_path": "legacy.pptx",
            },
        )

        path, payload, source = find_render_result(self.run_dir)

        self.assertEqual(legacy_path, path)
        self.assertEqual("legacy", source)
        self.assertEqual("legacy.pptx", payload["artifact_path"])


if __name__ == "__main__":
    unittest.main()
