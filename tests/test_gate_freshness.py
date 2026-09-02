from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.gate_freshness import artifact_identity, report_currentity
from quality.gate_policy import resolve_required_gates


class GateFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="deck_gate_freshness_"))
        self.run_dir = self.temp_dir / "run"
        self.run_dir.mkdir()
        self.artifact = self.run_dir / "build" / "deck.pptx"
        self.artifact.parent.mkdir()
        self.artifact.write_bytes(b"current")
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_legacy_artifact_path_is_compared(self) -> None:
        result = report_currentity(
            self.run_dir,
            {"gate": "render", "artifact": "build/old.pptx"},
            self.artifact,
        )

        self.assertFalse(result["current"])
        self.assertEqual("stale", result["status"])
        self.assertEqual("artifact is stale", result["reason"])

    def test_artifact_bound_gate_without_identity_is_not_current(self) -> None:
        result = report_currentity(self.run_dir, {"gate": "delivery", "status": "pass"}, self.artifact)

        self.assertFalse(result["current"])
        self.assertEqual("unbound", result["status"])
        self.assertEqual("artifact identity is missing", result["reason"])

    def test_canonical_identity_matches_current_artifact(self) -> None:
        report = {"gate": "customer_visible_safety", **artifact_identity(self.run_dir, self.artifact)}

        result = report_currentity(self.run_dir, report, self.artifact)

        self.assertTrue(result["current"])
        self.assertEqual("current", result["status"])

    def test_non_artifact_gate_does_not_require_artifact_identity(self) -> None:
        result = report_currentity(self.run_dir, {"gate": "draft", "status": "pass"}, self.artifact)

        self.assertTrue(result["current"])

    def test_unbound_gate_does_not_satisfy_required_gate(self) -> None:
        result = resolve_required_gates(
            self.run_dir,
            self.artifact,
            builder_profile="high_density",
            output_profile="production_pptx",
            run_mode="production",
            reports=[{"gate": "render", "status": "pass", "blocks_delivery": False, "findings": []}],
        )

        self.assertFalse(result["satisfied"])
        self.assertIn("render", result["missing_gates"])
        self.assertEqual("unbound", result["gate_status"][0]["currentity"])

    def test_current_required_gates_satisfy_policy(self) -> None:
        identity = artifact_identity(self.run_dir, self.artifact)
        reports = [
            {"gate": gate, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
            for gate in ("render", "delivery", "customer_visible_safety")
        ]

        result = resolve_required_gates(
            self.run_dir,
            self.artifact,
            builder_profile="high_density",
            output_profile="production_pptx",
            run_mode="production",
            reports=reports,
        )

        self.assertTrue(result["satisfied"])
        self.assertEqual([], result["missing_gates"])


if __name__ == "__main__":
    unittest.main()
