"""Tests for scripts.team.solution_package — P5A-E Solution Package."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.team.solution_package import (
    apply_solution_package,
    create_solution_package,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TestCreateSolutionPackage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        self.ws.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_minimal_package(self) -> None:
        pkg = create_solution_package(
            self.ws,
            "saas-series-a",
            industry="SaaS",
            best_for="Series A fundraising",
        )
        self.assertEqual(pkg["package_id"], "saas-series-a")
        self.assertEqual(pkg["industry"], "SaaS")
        self.assertEqual(pkg["schema_version"], "deck_solution_package.v1")
        self.assertEqual(pkg["recommended_archetypes"], [])
        self.assertEqual(pkg["claim_patterns"], [])

    def test_package_file_written(self) -> None:
        create_solution_package(self.ws, "test-pkg", industry="FinTech")
        path = self.ws / "packages" / "solution_packages" / "test-pkg.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["package_id"], "test-pkg")
        self.assertEqual(data["industry"], "FinTech")

    def test_create_from_source_run_extracts_archetypes(self) -> None:
        run_dir = Path(self.tmp.name) / "source_run"
        _write_json(run_dir / "narrative_plan.json", {
            "beats": [
                {"role": "hero"},
                {"role": "villain"},
                {"role": "hero"},  # duplicate should be deduplicated
            ],
        })
        pkg = create_solution_package(
            self.ws,
            "pkg-from-run",
            source_run_dir=run_dir,
        )
        self.assertEqual(sorted(pkg["recommended_archetypes"]), ["hero", "villain"])

    def test_create_from_source_run_extracts_claims(self) -> None:
        run_dir = Path(self.tmp.name) / "source_run"
        _write_json(run_dir / "claim_map.json", {
            "claims": [
                {"claim": "Revenue grew 3x", "why_it_matters": "Shows traction"},
                {"claim": "Market is large", "why_it_matters": "TAM validation"},
            ],
        })
        pkg = create_solution_package(
            self.ws,
            "pkg-claims",
            source_run_dir=run_dir,
        )
        self.assertEqual(len(pkg["claim_patterns"]), 2)
        self.assertEqual(pkg["claim_patterns"][0]["claim"], "Revenue grew 3x")

    def test_create_from_source_run_extracts_slide_assets(self) -> None:
        run_dir = Path(self.tmp.name) / "source_run"
        _write_json(run_dir / "asset_refs.json", {
            "asset_refs": [
                {"canonical_slide_id": "slide_001"},
                {"canonical_slide_id": ""},  # empty should be filtered
                {"canonical_slide_id": "slide_002"},
            ],
        })
        pkg = create_solution_package(
            self.ws,
            "pkg-assets",
            source_run_dir=run_dir,
        )
        self.assertEqual(pkg["slide_assets"], ["slide_001", "slide_002"])

    def test_example_runs_stored(self) -> None:
        pkg = create_solution_package(
            self.ws,
            "pkg-examples",
            example_runs=["run_001", "run_002"],
        )
        self.assertEqual(pkg["example_runs"], ["run_001", "run_002"])


class TestApplySolutionPackage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        self.ws.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_apply_writes_to_request_json(self) -> None:
        # Create package
        create_solution_package(
            self.ws,
            "saas-pkg",
            industry="SaaS",
        )
        # Create target run with request.json
        run_dir = Path(self.tmp.name) / "target_run"
        _write_json(run_dir / "request.json", {"brief": "Make a deck"})

        result = apply_solution_package(self.ws, "saas-pkg", run_dir)
        self.assertEqual(result["package_id"], "saas-pkg")

        # Verify request.json was updated
        request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        self.assertIn("solution_package", request)
        self.assertEqual(request["solution_package"]["package_id"], "saas-pkg")
        self.assertEqual(request["solution_package"]["industry"], "SaaS")

    def test_apply_nonexistent_package_raises(self) -> None:
        run_dir = Path(self.tmp.name) / "target_run"
        run_dir.mkdir(parents=True)
        with self.assertRaises(ValueError) as ctx:
            apply_solution_package(self.ws, "nonexistent", run_dir)
        self.assertIn("not found", str(ctx.exception))

    def test_apply_without_request_json_does_not_fail(self) -> None:
        create_solution_package(self.ws, "pkg-no-req")
        run_dir = Path(self.tmp.name) / "empty_run"
        run_dir.mkdir(parents=True)
        # Should not raise even without request.json
        result = apply_solution_package(self.ws, "pkg-no-req", run_dir)
        self.assertEqual(result["package_id"], "pkg-no-req")


if __name__ == "__main__":
    unittest.main()
