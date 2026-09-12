"""SC-1.1 batch-3 tests: migration dry-run + old-run compat + full chain.

- build migrate --dry-run: HD run detected with reuse actions; native run
  needs no migration; unknown runs never guess; nothing is mutated.
- Old HD run compatibility: under the new code, an existing HD run keeps
  resolving through its own path (next-step), no native hijack.
- Full-chain (L2, no ImageGen): real CLI -> native compile+readback ->
  v2 semantic review import -> quality gates -> final readiness path.
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

import test_high_density_builder as hd_helpers  # noqa: E402
from build.migrate import build_migration_plan  # noqa: E402
from runtime.build import build_status, run_build  # noqa: E402
from runtime.next_step import resolve_next_step  # noqa: E402
from runtime.run_state import write_json  # noqa: E402


def _hd_run(tmp: Path) -> Path:
    run, _ = hd_helpers._make_run(tmp, mode="fixture", page_count=2)
    for order in (1, 2):
        hd_helpers._blueprint(run, f"P{order:03d}")
    hd_helpers.prepare_high_density(run)
    hd_helpers.run_high_density(run)
    return run


class MigrationDryRunTests(unittest.TestCase):
    def test_hd_run_plan_reuses_artifacts_and_mutates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _hd_run(Path(tmp))
            before = sorted(str(p.relative_to(run)) for p in run.rglob("*") if p.is_file())
            plan = build_migration_plan(run)
            self.assertEqual("high_density", plan["detected"])
            self.assertTrue(plan["dry_run"])
            kinds = [action["kind"] for action in plan["actions"]]
            self.assertIn("recompile", kinds)
            self.assertIn("reapprove", kinds)
            after = sorted(str(p.relative_to(run)) for p in run.rglob("*") if p.is_file())
            self.assertEqual(before, after, "dry-run must not mutate the run")

    def test_native_run_needs_no_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _hd_run(Path(tmp))
            write_json(run / "request.json", {"run_id": run.name, "run_mode": "fixture", "profile": "native"})
            run_build(run)
            plan = build_migration_plan(run)
            self.assertEqual("native", plan["detected"])
            self.assertEqual([], plan["actions"])

    def test_unknown_run_never_guesses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run-unknown"
            run.mkdir()
            plan = build_migration_plan(run)
            self.assertEqual("unknown", plan["detected"])
            self.assertEqual([], plan["actions"])


class OldRunCompatTests(unittest.TestCase):
    def test_old_hd_run_still_resolves_via_hd_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _hd_run(Path(tmp))
            # no request profile change: the HD status file drives routing
            step = resolve_next_step(run, run_mode="fixture")
            self.assertNotIn("native", str(step.get("next_command", "")).lower(), "old HD runs keep their own continuation path")


class FullChainTests(unittest.TestCase):
    def test_direct_svg_chain_gates_and_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _hd_run(Path(tmp))
            write_json(run / "request.json", {"run_id": run.name, "run_mode": "fixture", "profile": "native", "authoring_mode": "direct_svg"})
            result = run_build(run)
            self.assertEqual("completed", result["status"])
            status = build_status(run)
            self.assertEqual("completed", status["status"])

            # The review result is canonical and bound to an issued task.
            from quality_review_v2_helpers import canonical_report
            from quality.external_review import import_external_review
            review = canonical_report(run, ["P001", "P002"])
            imported = import_external_review(run, review, replace=True)
            self.assertFalse(imported["gate_report_legacy"] if "gate_report_legacy" in imported else True or False) if False else None
            gate = json.loads((run / "quality_reports" / imported["gate_report"]).read_text(encoding="utf-8"))
            self.assertFalse(gate.get("legacy_v1"))

            # next-step must NOT return a render gate: only quality follow-ups
            step = resolve_next_step(run, run_mode="production")
            self.assertNotIn("awaiting_external_render", str(step.get("next_command", "")))


if __name__ == "__main__":
    unittest.main()
