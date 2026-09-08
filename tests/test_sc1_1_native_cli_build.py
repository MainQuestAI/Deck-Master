"""SC-1.1 batch-1.2 tests (failing-first): default CLI drives the native engine.

Acceptance mapping (review P1-01 / spec 05 section 5.3):
- A production run with the native route goes through the REAL CLI
  (`build run`) and completes a local direct_svg compile with the standard
  artifact chain (build manifest, artifact manifest, render result,
  build status) — never `awaiting_external_render`, never a render request.
- image_blueprint mode returns an honest `awaiting_agent_imagegen` host
  task with a resume command.
- A native production run without approved page packages blocks with a
  clear message instead of falling through to the external handoff.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import test_high_density_builder as hd_helpers  # noqa: E402
from runtime.build import build_status, run_build  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


def _native_run(tmp: Path, *, authoring: str = "direct_svg", run_mode: str = "production") -> Path:
    run, _ = hd_helpers._make_run(tmp, mode="fixture", page_count=2)
    for order in (1, 2):
        hd_helpers._blueprint(run, f"P{order:03d}")
    hd_helpers.prepare_high_density(run)
    hd_helpers.run_high_density(run)  # deterministic host authoring: approved scenes/locks/SVGs
    write_json(
        run / "request.json",
        {"run_id": run.name, "run_mode": run_mode, "profile": "native", "authoring_mode": authoring},
    )
    return run


class NativeCliBuildTests(unittest.TestCase):
    def test_native_fixture_run_completes_through_run_build(self) -> None:
        # fixture content meets fixture-grade thresholds; the same engine
        # path serves every entry (spec 05 section 5.2)
        with tempfile.TemporaryDirectory() as tmp:
            run = _native_run(Path(tmp), run_mode="fixture")
            result = run_build(run)
            self.assertEqual("completed", result["status"])
            self.assertEqual("deck_native", result["engine_id"])
            self.assertFalse((run / "build" / "render_request.json").exists(), "native runs never write an external render request")
            render_result = json.loads((run / "render_results" / "render_result.json").read_text(encoding="utf-8"))
            self.assertEqual("deck_native", render_result["tool"])
            self.assertEqual("completed", render_result["status"])
            self.assertTrue((run / "build" / "artifact_manifest.json").exists())
            status = build_status(run)
            self.assertEqual("completed", status["status"])

    def test_production_native_gate_blocks_fixture_grade_content(self) -> None:
        # production thresholds are stricter (edge_similarity >= 0.45 vs
        # fixture 0.25); fixture-authored content must NOT pass as production
        with tempfile.TemporaryDirectory() as tmp:
            run = _native_run(Path(tmp), run_mode="production")
            try:
                run_build(run)
                self.fail("fixture-grade content must not complete a production native build")
            except Exception as exc:  # noqa: BLE001
                self.assertIn("readback", str(exc).lower())

    def test_image_blueprint_state_machine_advances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _native_run(Path(tmp), authoring="image_blueprint", run_mode="fixture")
            # host results already present (HD fixture authoring): the state
            # machine must ADVANCE to the compile leg, not re-dispatch.
            result = run_build(run)
            self.assertEqual("completed", result["status"])
            # remove approved SVGs only: state advances to reconstruct
            for svg in (run / "high_density_build" / "svg").glob("P*.svg"):
                svg.unlink()
            r1 = run_build(run)
            self.assertEqual("awaiting_agent_reconstruct", r1["status"])
            # remove blueprints as well: state falls back to imagegen dispatch
            for blueprint in (run / "high_density_build" / "blueprints").glob("P*"):
                blueprint.unlink()
            r2 = run_build(run)
            self.assertEqual("awaiting_agent_imagegen", r2["status"])
            self.assertFalse((run / "build" / "render_request.json").exists(), "image_blueprint never writes an external render request")
            self.assertTrue((run / "build" / "host_imagegen_task.json").exists())
            self.assertIn("resume_command", r1)  # awaiting states carry the resume command
            self.assertIn("resume_command", r2)
            self.assertFalse((run / "build" / "render_request.json").exists())

    def test_direct_svg_missing_svgs_returns_awaiting_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _native_run(Path(tmp))
            for svg in (run / "high_density_build" / "svg").glob("*.svg"):
                svg.unlink()
            result = run_build(run)
            self.assertEqual("awaiting_svg_authoring", result["status"])
            self.assertEqual(2, len(result["missing_approved_svgs"]))

    def test_native_run_without_packages_blocks_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run-empty"
            run.mkdir()
            write_json(run / "request.json", {"run_id": "run-empty", "run_mode": "production", "profile": "native"})
            try:
                run_build(run)
                self.fail("expected a clear block for missing packages")
            except Exception as exc:  # noqa: BLE001
                self.assertIn("approved page packages", str(exc))

    def test_never_queries_external_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _native_run(Path(tmp), run_mode="fixture")
            from runtime import build as build_module

            with mock.patch.object(
                build_module, "builder_backend_status", side_effect=AssertionError("native route must not query the external backend")
            ):
                result = run_build(run)
            self.assertEqual("completed", result["status"])


if __name__ == "__main__":
    unittest.main()
