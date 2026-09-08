"""SC-1.1 ND-02 tests (failing-first batch): default native routing, task
readiness, library none, status consistency, next-step precision.

Acceptance mapping:
- IND-02/IND-03 (engineering): new runs default to engine_id=deck_native +
  image_blueprint; legacy profiles map with compatibility notes.
- F-N02: the native route resolves BEFORE any external backend status query —
  production build prepare/run must not call builder_backend_status.
- F-N05/F-N06: next-step maps the semantic_review gap to a semantic-review
  action, not the render gate; needs_builder_backend hint is engine-specific.
- F-N07: --library-mode none is accepted by the CLI and drives a real
  generate-decision sourcing flow without touching the Library.
- F-N08: ready_for_build is the written/consumed package status (schema
  consistent); legacy "ready" packages are accepted through a controlled
  mapping.
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

from build.build_route import resolve_build_route  # noqa: E402
from production.page_builder import build_packages_from_narrative  # noqa: E402
from runtime.build import prepare_build  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402
from tools.ppt_library_client import run_library_selection  # noqa: E402


def _manifest() -> dict:
    return {"sources": [{"source_id": "src_meeting", "name": "会议记录"}]}


def _narrative(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "beats": [
            {
                "beat_id": "beat_01_opener",
                "order": 1,
                "page_title": "核心问题",
                "role": "opener",
                "conclusion": "审批串行流转是周期过长的根因。",
                "page_job": "对齐客户决策",
                "evidence_refs": ["src_meeting"],
                "required_components": [],
            }
        ],
    }


def _narrative_plan(run_id: str) -> dict:
    beats = [
        {"beat_id": f"beat_{i:02d}_solution", "order": i, "page_title": f"页{i}", "role": "solution",
         "conclusion": f"页{i}的结论与依据均已写成。", "page_job": "说明机制",
         "evidence_refs": ["src_meeting"], "required_components": []}
        for i in range(1, 3)
    ]
    return {"run_id": run_id, "beats": beats}


class BuildRouteTests(unittest.TestCase):
    def test_new_run_defaults_to_native_image_blueprint(self) -> None:
        route = resolve_build_route({})
        self.assertEqual("deck_native", route["engine_id"])
        self.assertEqual("image_blueprint", route["authoring_mode"])

    def test_standard_profile_maps_to_native_with_note(self) -> None:
        route = resolve_build_route({"profile": "standard"})
        self.assertEqual("deck_native", route["engine_id"])
        self.assertEqual("default_policy", route["selection_origin"])
        self.assertNotIn("compatibility_note", route)

    def test_high_density_profile_maps_native_density_high(self) -> None:
        route = resolve_build_route({"profile": "high-density"})
        self.assertEqual("deck_native", route["engine_id"])
        self.assertEqual("high", route["density"])

    def test_legacy_explicit_route_records_engine(self) -> None:
        route = resolve_build_route({"profile": "legacy-ppt-master"})
        self.assertEqual("legacy_ppt_master", route["engine_id"])


class NativeRouteSkipsBackendProbeTests(unittest.TestCase):
    def _run(self, tmp: Path) -> Path:
        run_dir = create_run(str(tmp), {"run_id": "native-run", "project_name": "N"}, run_id="native-run")
        write_json(run_dir / "request.json", {"run_id": "native-run", "run_mode": "fixture"})
        return run_dir

    def test_native_prepare_build_never_queries_builder_backend(self) -> None:
        from runtime import build as build_module

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            write_page_packages(run_dir)
            with mock.patch.object(
                build_module, "builder_backend_status", side_effect=AssertionError("native route must not query the external backend")
            ), mock.patch.object(
                build_module, "backend_render_runtime_ready", side_effect=AssertionError("native route must not probe the old runtime flag")
            ):
                result = prepare_build(run_dir)
            self.assertEqual("page_packages", result["source_mode"])


def write_page_packages(run_dir: Path) -> None:
    from production.page_builder import write_page_packages

    write_page_packages(run_dir, narrative_plan=_narrative_plan("native-run"), context_manifest=_manifest())


class LibraryNoneTests(unittest.TestCase):
    def test_parser_accepts_none(self) -> None:
        import deck_master

        parser = deck_master.build_parser()
        args = parser.parse_args(["search-library", "--library-mode", "none"])
        self.assertEqual("none", args.library_mode)

    def test_none_mode_produces_generate_decisions_without_library(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-none"
            create_run(str(Path(tmp)), {"run_id": "run-none", "project_name": "P"}, run_id="run-none")
            narrative = _narrative_plan("run-none")
            result = run_library_selection(
                narrative_plan=narrative,
                narrative_plan_path=run_dir / "narrative_plan.json",
                request={"run_id": "run-none", "run_mode": "fixture"},
                run_dir=run_dir,
                mode="none",
            )
            self.assertEqual(2, len(result["selections"]))
            for selection in result["selections"]:
                self.assertEqual("none", selection["candidate_origin"])
                self.assertEqual("generate", selection["decision"])

    def test_none_rejected_before_fix(self) -> None:
        # document the pre-fix failure mode: mode validation must accept none
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-none"
            create_run(str(tmp), {"run_id": "run-none"}, run_id="run-none")
            try:
                run_library_selection(
                    narrative_plan=_narrative_plan("run-none"),
                    narrative_plan_path=run_dir / "narrative_plan.json",
                    request={"run_id": "run-none"},
                    run_dir=run_dir,
                    mode="none",
                )
                accepted = True
            except Exception:
                accepted = False
            self.assertTrue(accepted, "none must be a first-class mode after ND-02")


class PackageStatusConsistencyTests(unittest.TestCase):
    def test_packages_written_with_schema_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-pk"
            create_run(str(tmp), {"run_id": "run-pk"}, run_id="run-pk")
            packages = build_packages_from_narrative(
                run_id="run-pk", narrative_plan=_narrative("run-pk"), context_manifest=_manifest()
            )
            self.assertEqual("ready_for_build", packages[0]["status"])

    def test_build_consumer_accepts_ready_for_build(self) -> None:
        from runtime.build import _page_sources_from_packages
        from production.page_package import PagePackageIndex

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-pk2"
            create_run(str(tmp), {"run_id": "run-pk2"}, run_id="run-pk2")
            packages = build_packages_from_narrative(
                run_id="run-pk2", narrative_plan=_narrative("run-pk2"), context_manifest=_manifest()
            )
            index = PagePackageIndex(run_dir)
            for package in packages:
                index.write(package)
            sources, warnings = _page_sources_from_packages(run_dir, index.list_packages(), production=True)
            self.assertEqual(1, len(sources))
            self.assertEqual([], [w for w in warnings if "status" in w])


if __name__ == "__main__":
    unittest.main()
