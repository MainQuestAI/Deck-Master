from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from deck_master import command_render  # noqa: E402
from runtime.build import BuildError, build_status, prepare_build, run_build  # noqa: E402
from runtime.run_state import RunStateError, create_run, read_json, write_json  # noqa: E402
from validators.companion_tools import validate_render_result  # noqa: E402


class BuildRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_build_runtime_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.run_dir = create_run(
            self.temp_dir,
            {"run_id": "build-run", "project_name": "Build Run", "run_mode": "production"},
            run_id="build-run",
        )

    def _write_preview(self, page_count: int, *, missing_source: bool = False) -> None:
        pages: list[dict[str, object]] = []
        for index in range(1, page_count + 1):
            page_id = f"beat_{index:03d}"
            source = f"links/{page_id}.svg"
            if not missing_source:
                (self.run_dir / source).write_text(
                    f"<svg><text>Page {index}</text></svg>",
                    encoding="utf-8",
                )
            pages.append(
                {
                    "page_id": page_id,
                    "beat_id": page_id,
                    "order": page_count - index + 1,
                    "title": f"页面 {index}",
                    "preview_path": source,
                }
            )
        write_json(self.run_dir / "preview_manifest.json", {"run_id": "build-run", "pages": pages})

    def test_prepare_build_writes_manifest_with_fingerprint_and_ordered_pages(self) -> None:
        self._write_preview(3)

        result = prepare_build(self.run_dir)

        self.assertEqual("prepared", result["status"])
        manifest = read_json(self.run_dir / "build" / "build_manifest.json")
        self.assertEqual("deck_build_manifest.v1", manifest["schema_version"])
        self.assertEqual(3, manifest["page_count"])
        self.assertEqual(64, len(manifest["source_fingerprint"]))
        self.assertEqual(["beat_003", "beat_002", "beat_001"], [page["page_id"] for page in manifest["pages"]])

    def test_run_build_writes_required_artifacts_and_render_result_v2(self) -> None:
        self._write_preview(3)

        result = run_build(self.run_dir)

        self.assertEqual("completed", result["status"])
        self.assertTrue((self.run_dir / "build" / "deck.html").exists())
        self.assertTrue((self.run_dir / "build" / "deck.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertTrue((self.run_dir / "build" / "pages" / "beat_001.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        with zipfile.ZipFile(self.run_dir / "build" / "deck.pptx") as pptx:
            slides = [name for name in pptx.namelist() if name.startswith("ppt/slides/slide")]
        self.assertEqual(3, len(slides))

        artifact_manifest = read_json(self.run_dir / "build" / "artifact_manifest.json")
        self.assertEqual("deck_artifact_manifest.v1", artifact_manifest["schema_version"])
        self.assertTrue(artifact_manifest["validation"]["valid"], artifact_manifest["validation"].get("errors"))
        artifact_kinds = {artifact["kind"] for artifact in artifact_manifest["artifacts"]}
        self.assertEqual({"deck_html", "deck_pdf", "deck_pptx", "page_png"}, artifact_kinds)
        for artifact in artifact_manifest["artifacts"]:
            self.assertEqual(64, len(artifact["sha256"]))
            self.assertGreater(artifact["bytes"], 0)
            self.assertTrue(artifact["media_type"])
            self.assertIn(artifact["editability"], {"native", "flat_image"})

        render_result = read_json(self.run_dir / "render_results" / "render_result.json")
        self.assertEqual("deck_render_result.v2", render_result["schema_version"])
        self.assertEqual(3, render_result["page_count"])
        self.assertEqual("build/deck.html", render_result["artifact_path"])
        self.assertEqual("build/pages", render_result["preview_dir"])
        self.assertEqual(3, len(render_result["page_previews"]))
        validation = validate_render_result(render_result)
        self.assertTrue(validation["valid"], validation.get("errors"))

        status = build_status(self.run_dir)
        self.assertEqual("completed", status["status"])
        self.assertEqual(3, status["page_count"])
        self.assertTrue(status["artifact_validation"]["valid"], status["artifact_validation"].get("errors"))

    def test_build_status_detects_corrupt_artifacts(self) -> None:
        self._write_preview(1)
        run_build(self.run_dir)
        (self.run_dir / "build" / "deck.pdf").write_text("corrupt", encoding="utf-8")

        status = build_status(self.run_dir)

        self.assertEqual("invalid", status["status"])
        validation = status["artifact_validation"]
        self.assertFalse(validation["valid"])
        self.assertTrue(any("deck_pdf" in error for error in validation["errors"]))

    def test_command_render_uses_build_runtime_for_production(self) -> None:
        self._write_preview(1)

        result = command_render(
            Namespace(run_dir=str(self.run_dir), run_id=None, runs_dir=None, fixture_safe=False, format="html")
        )

        self.assertEqual("deck_build_run_result.v1", result["schema_version"])
        render_result = read_json(self.run_dir / "render_results" / "render_result.json")
        self.assertEqual("deck_render_result.v2", render_result["schema_version"])

    def test_command_render_fixture_safe_keeps_legacy_fixture_renderer(self) -> None:
        self._write_preview(1)
        request = read_json(self.run_dir / "request.json")
        request["run_mode"] = "fixture"
        write_json(self.run_dir / "request.json", request)

        result = command_render(
            Namespace(run_dir=str(self.run_dir), run_id=None, runs_dir=None, fixture_safe=True, format="html")
        )

        self.assertEqual("deck_render_command_result.v1", result["schema_version"])
        render_result = read_json(self.run_dir / "render_results" / "render_result.json")
        self.assertEqual("deck_render_result.v1", render_result["schema_version"])
        self.assertTrue((self.run_dir / "rendered" / "index.html").exists())

    def test_command_render_fixture_safe_blocks_production(self) -> None:
        self._write_preview(1)

        with self.assertRaises(RunStateError):
            command_render(
                Namespace(run_dir=str(self.run_dir), run_id=None, runs_dir=None, fixture_safe=True, format="html")
            )

    def test_run_build_handles_12_and_60_page_decks(self) -> None:
        for page_count in (12, 60):
            with self.subTest(page_count=page_count):
                run_dir = create_run(
                    self.temp_dir,
                    {"run_id": f"build-{page_count}", "project_name": "Scale", "run_mode": "production"},
                    run_id=f"build-{page_count}",
                )
                pages: list[dict[str, object]] = []
                for index in range(1, page_count + 1):
                    page_id = f"page_{index:03d}"
                    source = f"links/{page_id}.svg"
                    (run_dir / source).write_text("<svg/>", encoding="utf-8")
                    pages.append({"page_id": page_id, "order": index, "title": f"Page {index}", "preview_path": source})
                write_json(run_dir / "preview_manifest.json", {"run_id": f"build-{page_count}", "pages": pages})

                result = run_build(run_dir)

                self.assertEqual(page_count, result["page_count"])
                self.assertEqual(page_count + 3, len(result["artifacts"]))
                with zipfile.ZipFile(run_dir / "build" / "deck.pptx") as pptx:
                    slides = [name for name in pptx.namelist() if name.startswith("ppt/slides/slide")]
                self.assertEqual(page_count, len(slides))

    def test_prepare_build_records_missing_source_warning(self) -> None:
        self._write_preview(1, missing_source=True)

        result = prepare_build(self.run_dir)

        self.assertEqual(["page source missing: links/beat_001.svg"], result["warnings"])

    def test_prepare_build_prefers_run_relative_preview_path_over_external_source(self) -> None:
        source = "links/beat_001.svg"
        (self.run_dir / source).write_text("<svg><text>Page 1</text></svg>", encoding="utf-8")
        write_json(
            self.run_dir / "preview_manifest.json",
            {
                "run_id": "build-run",
                "pages": [
                    {
                        "page_id": "beat_001",
                        "order": 1,
                        "title": "页面 1",
                        "preview_path": source,
                        "source_preview_asset": "/tmp/external-source.svg",
                    }
                ],
            },
        )

        result = prepare_build(self.run_dir)

        self.assertEqual("prepared", result["status"])
        manifest = read_json(self.run_dir / "build" / "build_manifest.json")
        self.assertEqual(source, manifest["pages"][0]["source_path"])
        self.assertEqual([], result["warnings"])

    def test_prepare_build_rejects_path_traversal(self) -> None:
        write_json(
            self.run_dir / "preview_manifest.json",
            {
                "run_id": "build-run",
                "pages": [{"page_id": "escape", "order": 1, "preview_path": "../outside.svg"}],
            },
        )

        with self.assertRaises(BuildError):
            prepare_build(self.run_dir)


if __name__ == "__main__":
    unittest.main()
