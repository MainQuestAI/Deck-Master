"""SC-1 PR-07 tests: C5 paired-run metadata and manual-effort records.

Acceptance mapping:
- E-01 (metadata layer): pairing block validated — pairing_id, both
  versions, run_order must be baseline/upgraded; invalid pairing rejected.
- E-04 (metadata layer): manual_effort entries require phase + minutes +
  failures; partial/best-only records are structurally possible but the
  report carries the full list so aggregates cannot drop failures.
- Baseline data stays untouched; real-sample execution (E-02/E-03/E-05/
  E-06) remains deferred to UAT with real samples (see acceptance-tracking).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from benchmark.case import BenchmarkCaseError, validate_benchmark_case  # noqa: E402


def _base_case(**overrides) -> dict:
    case = {
        "schema_version": "deck_benchmark_case.v1",
        "case_id": "case-x",
        "case_name": "Sample",
        "inputs": {"baseline_manual_hours": 8},
        "workflow": {"planning_mode": "narrative_v2"},
        "success_targets": {"retention_rate": 0.7},
    }
    case.update(overrides)
    return case


class PairingMetadataTests(unittest.TestCase):
    def test_valid_pairing_passes(self) -> None:
        case = _base_case(
            pairing={
                "pairing_id": "pair-01",
                "baseline_version": "0.9.14a4",
                "upgraded_version": "sc1",
                "run_order": "baseline",
                "host_tool_versions": {"imagegen": "v1"},
            }
        )
        self.assertEqual([], validate_benchmark_case(case))

    def test_missing_pairing_fields_rejected(self) -> None:
        with self.assertRaises(BenchmarkCaseError) as ctx:
            validate_benchmark_case(_base_case(pairing={"pairing_id": "p1"}))
        self.assertIn("pairing.baseline_version", str(ctx.exception))

    def test_invalid_run_order_rejected(self) -> None:
        with self.assertRaises(BenchmarkCaseError):
            validate_benchmark_case(
                _base_case(
                    pairing={
                        "pairing_id": "p1",
                        "baseline_version": "a",
                        "upgraded_version": "b",
                        "run_order": "best_of",
                    }
                )
            )

    def test_manual_effort_full_records(self) -> None:
        case = _base_case(
            manual_effort=[
                {"phase": "intake", "minutes": 25, "failures": 1},
                {"phase": "research", "minutes": 40, "failures": 2},
            ]
        )
        self.assertEqual([], validate_benchmark_case(case))
        with self.assertRaises(BenchmarkCaseError):
            validate_benchmark_case(
                _base_case(manual_effort=[{"phase": "intake", "minutes": -5}])
            )
        with self.assertRaises(BenchmarkCaseError):
            validate_benchmark_case(
                _base_case(manual_effort=[{"phase": "intake", "minutes": 10, "failures": "three"}])
            )

    def test_real_metadata_fixture_guard_unchanged(self) -> None:
        case = _base_case(case_type="real_metadata", workflow={"planning_mode": "narrative_v2", "library_mode": "fixture"})
        with self.assertRaises(BenchmarkCaseError) as ctx:
            validate_benchmark_case(case)
        self.assertIn("fixture", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
