"""SC-1.1 batch-3 tests: semantic gate hardening (P1-06).

- A v1 review (even with empty findings and scope=semantic) imports as
  legacy and can NEVER satisfy the native production semantic_review gate.
- A v2 review binds a per-package-FILE content fingerprint: editing a page
  package without touching index.json stales the review.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.external_review import import_external_review  # noqa: E402
from quality.gate_freshness import artifact_identity  # noqa: E402
from quality.gate_policy import resolve_required_gates  # noqa: E402


def _run(tmp: Path) -> tuple[Path, Path]:
    root = tmp / "run-sem"
    (root / "build").mkdir(parents=True)
    (root / "page_packages").mkdir(parents=True)
    artifact = root / "build" / "deck.pptx"
    artifact.write_bytes(b"pptx")
    (root / "page_packages" / "P001.json").write_text('{"page_id": "P001"}', encoding="utf-8")
    (root / "page_packages" / "index.json").write_text("{}\n", encoding="utf-8")
    (root / "request.json").write_text('{"run_id": "run-sem"}', encoding="utf-8")
    return root, artifact


def _base_reports(root: Path, artifact: Path) -> list[dict]:
    identity = artifact_identity(root, artifact)
    return [
        {"gate": g, "status": "pass", "blocks_delivery": False, "findings": [], **identity}
        for g in ("render", "delivery", "customer_visible_safety")
    ]


class LegacyV1GateTests(unittest.TestCase):
    def test_v1_empty_findings_import_never_satisfies_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = _run(Path(tmp))
            v1 = {
                "schema_version": "deck_external_quality_review.v1",
                "run_id": "run-sem",
                "reviewer": "old-reviewer",
                "scope": "semantic",
                "findings": [],
            }
            imported = import_external_review(root, v1)
            gate_path = imported["gate_report"]
            gate = json.loads((root / "quality_reports" / gate_path).read_text(encoding="utf-8"))
            self.assertTrue(gate.get("legacy_v1"))
            reports = _base_reports(root, artifact) + [gate]
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertIn("semantic_review", result["missing_required_gates"], "v1 legacy review must not satisfy the production gate")


class ContentFingerprintTests(unittest.TestCase):
    def test_package_edit_without_index_change_stales_review(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root, artifact = _run(Path(tmp))
            v2 = _v2_report(root)
            imported = import_external_review(root, v2, replace=True)
            gate = json.loads((root / "quality_reports" / imported["gate_report"]).read_text(encoding="utf-8"))
            self.assertTrue(gate.get("content_fingerprint"))
            reports = _base_reports(root, artifact) + [gate]
            result = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertNotIn("semantic_review", result["missing_required_gates"])
            # edit the package CONTENT without touching index.json
            (root / "page_packages" / "P001.json").write_text('{"page_id": "P001", "edited": true}', encoding="utf-8")
            result2 = resolve_required_gates(root, artifact, run_mode="production", reports=reports)
            self.assertIn("semantic_review", result2["missing_required_gates"], "content edit must stale the review")


def _v2_report(root: Path) -> dict:
    from quality.external_review import RESULT_SCHEMA_VERSION_V2, REVIEW_DIMENSIONS_V2, _page_packages_content_fingerprint

    packages_sha = hashlib.sha256((root / "page_packages" / "index.json").read_bytes()).hexdigest()
    content_fingerprint = _page_packages_content_fingerprint(root)
    return {
        "schema_version": RESULT_SCHEMA_VERSION_V2,
        "run_id": "run-sem",
        "run_mode": "production",
        "based_on": {"page_packages_index_sha256": packages_sha, "content_fingerprint": content_fingerprint},
        "review_action_id": "review-1",
        "scope": "semantic",
        "review_kind": "full_deck",
        "reviewer_session_id": "session-reviewer",
        "producer_session_id": "session-producer",
        "host_execution_ref": "host-1",
        "reviewed_inputs": {"page_packages": "page_packages/"},
        "coverage": {"required_page_ids": ["P001"], "reviewed_page_ids": ["P001"], "skipped": []},
        "dimension_scores": {dim: 4 for dim in REVIEW_DIMENSIONS_V2},
        "observations": [{"dimension": dim, "page_id": "P001", "observation": f"obs {dim}"} for dim in REVIEW_DIMENSIONS_V2],
        "findings": [],
        "summary": {"reported_status": "pass", "conclusion": "clean"},
    }


if __name__ == "__main__":
    unittest.main()
