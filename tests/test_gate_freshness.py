from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.gate_freshness import artifact_identity, report_currentity
from quality.gate_policy import current_artifact, resolve_required_gates
from quality.overrides import create_override


def _page_packages_sha(run_dir: Path) -> str:
    """SC-1.1 P1-06: full content fingerprint over every package file (the
    gate compares this value, not just the index sha)."""

    index = Path(run_dir) / "page_packages" / "index.json"
    if not index.exists():
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("{}\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256()
    for package_file in sorted((Path(run_dir) / "page_packages").glob("*.json")):
        digest.update(package_file.name.encode("utf-8"))
        digest.update(hashlib.sha256(package_file.read_bytes()).digest())
    return digest.hexdigest()


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
        self.assertEqual("unbound", result["status"])
        self.assertEqual("artifact SHA-256 binding is missing", result["reason"])

    def test_path_only_binding_is_unbound_even_when_path_matches(self) -> None:
        result = report_currentity(
            self.run_dir,
            {"gate": "render", "artifact_path": "build/deck.pptx"},
            self.artifact,
        )

        self.assertFalse(result["current"])
        self.assertEqual("unbound", result["status"])

    def test_path_only_binding_is_unbound_when_path_is_wrong(self) -> None:
        result = report_currentity(
            self.run_dir,
            {"gate": "render", "artifact_path": "build/old.pptx"},
            self.artifact,
        )

        self.assertFalse(result["current"])
        self.assertEqual("unbound", result["status"])

    def test_wrong_sha_binding_is_stale(self) -> None:
        result = report_currentity(
            self.run_dir,
            {
                "gate": "render",
                "artifact_path": "build/deck.pptx",
                "artifact_sha256": "0" * 64,
            },
            self.artifact,
        )

        self.assertFalse(result["current"])
        self.assertEqual("stale", result["status"])

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

    def test_current_artifact_prefers_render_result_over_old_delivery_lineage(self) -> None:
        old_artifact = self.run_dir / "delivery" / "old.pptx"
        old_artifact.parent.mkdir(exist_ok=True)
        old_artifact.write_bytes(b"old")
        (self.run_dir / "render_results").mkdir()
        (self.run_dir / "render_results" / "render_result.json").write_text(
            json.dumps({"status": "completed", "artifact_path": "build/deck.pptx"}),
            encoding="utf-8",
        )
        (self.run_dir / "delivery" / "final_version_lineage.json").write_text(
            json.dumps({"artifact_run_relative": "delivery/old.pptx"}),
            encoding="utf-8",
        )

        self.assertEqual(self.artifact.resolve(), current_artifact(self.run_dir))

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

    def test_unbound_and_stale_findings_do_not_block_current_artifact(self) -> None:
        result = resolve_required_gates(
            self.run_dir,
            self.artifact,
            builder_profile="high_density",
            output_profile="production_pptx",
            run_mode="production",
            reports=[
                {"gate": "render", "status": "failed", "blocks_delivery": True, "findings": [{"finding_id": "old-p0", "severity": "P0"}], "artifact_path": "build/deck.pptx"},
                {"gate": "delivery", "status": "failed", "blocks_delivery": True, "findings": [{"finding_id": "old-p0-delivery", "severity": "P0"}], "artifact_path": "build/deck.pptx", "artifact_sha256": "0" * 64},
            ],
        )

        self.assertFalse(result["required_gate_satisfied"])
        self.assertEqual([], result["current_blockers"])
        self.assertEqual([], result["blocking_findings"])
        self.assertTrue(result["unbound_reports"])
        self.assertTrue(result["stale_reports"])

    def test_current_required_gates_satisfy_policy(self) -> None:
        identity = artifact_identity(self.run_dir, self.artifact)
        reports = [
            {"gate": gate, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
            for gate in ("render", "delivery", "customer_visible_safety")
        ]
        # SC-1 C3: production additionally requires a current semantic review.
        reports.append(
            {
                "gate": "external_semantic",
                "status": "pass",
                "blocks_delivery": False,
                "findings": [],
                "based_on_sha256": _page_packages_sha(self.run_dir),
                # index-only runs: content fingerprint equals the index sha so
                # the P1-06 fingerprint rule can be satisfied in this fixture
                "content_fingerprint": _page_packages_sha(self.run_dir),
                **identity,
            }
        )

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

    def test_active_p1_override_is_reported_separately_from_current_blockers(self) -> None:
        create_override(self.run_dir, "draft-p1", "P1", "accepted for this run", "reviewer")

        result = resolve_required_gates(
            self.run_dir,
            self.artifact,
            builder_profile="high_density",
            output_profile="production_pptx",
            run_mode="production",
            reports=[
                {
                    "gate": "draft",
                    "status": "rework_required",
                    "blocks_delivery": True,
                    "findings": [{"finding_id": "draft-p1", "severity": "P1", "message": "draft issue"}],
                }
            ],
            include_non_required_blockers=True,
        )

        assert result["current_blockers"] == []
        assert [item["finding_id"] for item in result["overridden_p1"]] == ["draft-p1"]


if __name__ == "__main__":
    unittest.main()
