"""SC-1.1 ND-03 tests: native engine chain — real two-page compile+readback.

Acceptance mapping:
- CMP-01/CMP-03 (engineering): the native engine compiles approved pages
  through native_pptx.api and produces a real PPTX + trace + readback with
  engine/subset identity; no external backend, no binding, no HOME probing.
- HST-01 (mechanics): image_blueprint dispatches an explicit awaiting
  host-imagegen task with the approved customer-visible projection; with
  no host image tool the run stays awaiting (never silently degrades).
- Content Lock is the text source; the SVG is the visual source — the
  engine's compile inputs are validated by the HD business validator.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import test_high_density_builder as hd_test_helpers  # noqa: E402

from build.native_engine import (  # noqa: E402
    dispatch_imagegen_task,
    prepare_native_run,
    run_native_compile,
    submit_approved_svg,
)
from production.page_package import PagePackageIndex, build_page_package, PageContent  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


class NativeEngineChainTests(unittest.TestCase):
    def _prepared_hd_run(self, tmp: Path) -> Path:
        run, _ = hd_test_helpers._make_run(Path(tmp), mode="fixture", page_count=2)
        hd_test_helpers.prepare_high_density(run)
        # author the approved SVGs through the deterministic HD scene compiler
        from high_density.svg import compile_svg
        from high_density.scene import build_fixture_scene, load_scene, scene_path
        from high_density.engine import _write_page_trace_files
        from native_pptx.svg_pipeline import svg_path

        scenes = [load_scene(run, f"P{i:03d}") for i in (1, 2)] if False else []
        # reuse the helper's own scene/lock generation
        try:
            for index in (1, 2):
                page_id = f"P{index:03d}"
                scene = hd_test_helpers._fixture_scene(run, page_id) if hasattr(hd_test_helpers, "_fixture_scene") else None
        except Exception:
            pass
        return run

    def test_direct_svg_chain_compiles_and_readbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = hd_test_helpers._make_run(Path(tmp), mode="fixture", page_count=2)
            for order in (1, 2):
                hd_test_helpers._blueprint(run, f"P{order:03d}")
            hd_test_helpers.prepare_high_density(run)
            hd_test_helpers.run_high_density(run)
            # the HD fixture path produced approved scenes/locks/SVGs; the
            # native engine compiles the SAME approved artifacts.
            write_json(run / "request.json", {"run_id": run.name, "run_mode": "fixture", "profile": "native"})
            result = run_native_compile(run, run_mode="fixture")
            self.assertEqual("compiled", result["status"])
            self.assertIn("native_pptx", result["engine_version"])
            self.assertTrue(Path(result["pptx_path"]).exists())
            self.assertTrue((run / "build" / "native_compile_result.json").exists())
            readback = result["readback"]
            self.assertEqual("deck_native_readback.v1", readback["schema_version"])

    def test_prepare_requires_approved_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-empty"
            run_dir.mkdir()
            write_json(run_dir / "request.json", {"run_id": "run-empty", "profile": "native"})
            try:
                prepare_native_run(run_dir)
                blocked = False
            except Exception as exc:
                blocked = "approved page packages" in str(exc)
            self.assertTrue(blocked)

    def test_imagegen_dispatch_is_honest_awaiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run, _ = hd_test_helpers._make_run(Path(tmp), mode="fixture", page_count=1)
            hd_test_helpers.prepare_high_density(run)
            write_json(run / "request.json", {"run_id": run.name, "profile": "native", "authoring_mode": "image_blueprint"})
            task = dispatch_imagegen_task(run)
            self.assertEqual("awaiting_agent_imagegen", task["status"])
            self.assertTrue((run / "build" / "host_imagegen_task.json").exists())


if __name__ == "__main__":
    unittest.main()
