"""SC-1.1 batch-1.1 tests (failing-first): persisted build route.

Acceptance mapping (review secondary item 1 / spec 02 section 2.2):
- The route is FIXED per run: once `build/route.json` is written, later
  request changes (e.g. a stale `--profile` flag) must not re-route the run.
- `authoring_mode` is read from the request when present; `direct_svg` is a
  first-class request field, not only a profile alias.
- Old runs without a persisted route keep their legacy behaviour: an HD run
  continues via the HD path; a run with old backend traces resolves
  legacy_ppt_master instead of being silently re-routed to native.
- `prepare_native_run` persists the resolved route.
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

from build.build_route import ROUTE_SCHEMA_VERSION, load_persisted_route, persist_route, resolve_build_route  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


class RouteResolutionTests(unittest.TestCase):
    def test_authoring_mode_read_from_request(self) -> None:
        route = resolve_build_route({"authoring_mode": "direct_svg"})
        self.assertEqual("direct_svg", route["authoring_mode"])
        self.assertEqual("deck_native", route["engine_id"])

    def test_dashed_cli_value_normalized(self) -> None:
        route = resolve_build_route({"authoring_mode": "image-blueprint"})
        self.assertEqual("image_blueprint", route["authoring_mode"])

    def test_unknown_authoring_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_build_route({"authoring_mode": "magic"})


class PersistedRouteTests(unittest.TestCase):
    def _run(self, tmp: Path) -> Path:
        run_dir = tmp / "run-route"
        run_dir.mkdir(parents=True)
        return run_dir

    def test_persisted_route_wins_over_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            persist_route(run_dir, resolve_build_route({"profile": "native"}))
            # a later, conflicting request flag must not re-route the run
            route = resolve_build_route({"profile": "legacy-ppt-master"}, run_dir=run_dir)
            self.assertEqual("deck_native", route["engine_id"])

    def test_load_persisted_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            self.assertEqual({}, load_persisted_route(run_dir))
            persisted = persist_route(run_dir, resolve_build_route({"profile": "native", "authoring_mode": "direct_svg"}))
            loaded = load_persisted_route(run_dir)
            self.assertEqual(ROUTE_SCHEMA_VERSION, loaded["schema_version"])
            self.assertEqual("direct_svg", loaded["authoring_mode"])
            self.assertEqual(persisted["engine_id"], loaded["engine_id"])

    def test_old_hd_run_without_route_resolves_hd_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            (run_dir / "high_density_build").mkdir()
            (run_dir / "high_density_build" / "status.json").write_text('{"builder_profile": "high_density"}', encoding="utf-8")
            route = resolve_build_route({}, run_dir=run_dir)
            self.assertEqual("deck_native", route["engine_id"], "HD runs reuse the native kernel")
            self.assertEqual("high", route["density"])

    def test_prepare_native_run_persists_route(self) -> None:
        import test_high_density_builder as hd_helpers

        with tempfile.TemporaryDirectory() as tmp:
            run, _ = hd_helpers._make_run(Path(tmp), mode="fixture", page_count=1)
            hd_helpers._blueprint(run, "P001")
            hd_helpers.prepare_high_density(run)
            hd_helpers.run_high_density(run)
            write_json(run / "request.json", {"run_id": run.name, "run_mode": "fixture", "profile": "native"})
            from build.native_engine import prepare_native_run

            prepare_native_run(run)
            persisted = load_persisted_route(run)
            self.assertEqual("deck_native", persisted.get("engine_id"), "prepare_native_run must persist the fixed route")
            self.assertTrue((run / "build" / "route.json").exists())


if __name__ == "__main__":
    unittest.main()
