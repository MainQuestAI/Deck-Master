from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.case import BenchmarkCaseError, load_benchmark_case  # noqa: E402


def _valid_case() -> dict:
    return {
        "schema_version": "deck_benchmark_case.v1",
        "case_id": "retail_fixture",
        "case_name": "Retail fixture benchmark",
        "target_pages": 12,
        "workspace": "benchmarks/workspaces/retail",
        "runs_dir": "benchmark_runs",
        "inputs": {
            "context_pack": "context_pack.json",
            "baseline_manual_hours": 12.5,
        },
        "workflow": {
            "planning_mode": "narrative_v2",
        },
        "success_targets": {
            "context_to_preview_minutes": 45,
        },
        "scoring": {
            "weights": {
                "efficiency": 0.5,
                "page_acceptance": 0.5,
            }
        },
    }


def _real_metadata_case() -> dict:
    payload = _valid_case()
    payload["case_id"] = "real_retail_growth"
    payload["case_type"] = "real_metadata"
    payload["workflow"]["library_mode"] = "production"
    payload["source_material"] = {
        "classification": "private_local_reference",
        "raw_source_policy": "local_path_only",
        "local_source_paths": ["~/deck-master-local-benchmarks/real_retail_growth/raw"],
        "submitted_material_types": ["brief", "notes"],
        "excluded_from_repo": True,
    }
    return payload


class BenchmarkCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.case_dir = self.temp_dir / "benchmarks" / "cases" / "retail_fixture"
        self.case_dir.mkdir(parents=True)
        self.case_path = self.case_dir / "benchmark_case.json"
        (self.case_dir / "context_pack.json").write_text("{}", encoding="utf-8")

    def _write_case(self, payload: dict) -> None:
        self.case_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_load_valid_case_resolves_paths(self) -> None:
        self._write_case(_valid_case())

        case = load_benchmark_case(self.case_path)

        self.assertEqual("retail_fixture", case.data["case_id"])
        self.assertEqual([], case.warnings)
        self.assertEqual((self.temp_dir / "benchmarks").resolve(), case.benchmark_dir)
        self.assertEqual((self.case_dir / "context_pack.json").resolve(), case.resolved_paths["context_pack"])
        self.assertEqual(
            (self.temp_dir / "benchmarks" / "workspaces" / "retail").resolve(),
            case.resolved_paths["workspace"],
        )
        self.assertEqual((self.temp_dir / "benchmarks" / "benchmark_runs").resolve(), case.resolved_paths["runs_dir"])

    def test_missing_baseline_manual_hours_is_invalid(self) -> None:
        payload = _valid_case()
        del payload["inputs"]["baseline_manual_hours"]
        self._write_case(payload)

        with self.assertRaises(BenchmarkCaseError) as ctx:
            load_benchmark_case(self.case_path)

        self.assertIn("baseline_manual_hours", str(ctx.exception))

    def test_bad_schema_version_is_invalid(self) -> None:
        payload = _valid_case()
        payload["schema_version"] = "deck_benchmark_case.v0"
        self._write_case(payload)

        with self.assertRaises(BenchmarkCaseError) as ctx:
            load_benchmark_case(self.case_path)

        self.assertIn("deck_benchmark_case.v1", str(ctx.exception))

    def test_weights_sum_warning_does_not_invalidate_case(self) -> None:
        payload = _valid_case()
        payload["scoring"]["weights"] = {"efficiency": 0.8, "page_acceptance": 0.1}
        self._write_case(payload)

        case = load_benchmark_case(self.case_path)

        self.assertEqual(1, len(case.warnings))
        self.assertIn("scoring.weights", case.warnings[0])

    def test_real_metadata_case_requires_local_source_policy(self) -> None:
        payload = _real_metadata_case()
        payload["source_material"]["raw_source_policy"] = "committed_copy"
        self._write_case(payload)

        with self.assertRaises(BenchmarkCaseError) as ctx:
            load_benchmark_case(self.case_path)

        self.assertIn("local_path_only", str(ctx.exception))

    def test_real_metadata_case_rejects_embedded_private_content(self) -> None:
        payload = _real_metadata_case()
        payload["source_material"]["source_excerpt"] = "Private customer text"
        self._write_case(payload)

        with self.assertRaises(BenchmarkCaseError) as ctx:
            load_benchmark_case(self.case_path)

        self.assertIn("must not embed", str(ctx.exception))

    def test_real_metadata_case_rejects_fixture_library_mode(self) -> None:
        payload = _real_metadata_case()
        payload["workflow"]["library_mode"] = "fixture"
        self._write_case(payload)

        with self.assertRaises(BenchmarkCaseError) as ctx:
            load_benchmark_case(self.case_path)

        self.assertIn("library_mode=fixture", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
