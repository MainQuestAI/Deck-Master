from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from manifest import (
    ManifestError,
    load_manifest,
    migrate_page_to_review_status,
    preview_file_path,
    sync_legacy_decision,
    update_page_decision,
    update_page_review,
    update_page_source_decision,
)


SAMPLE_RUN = ROOT / "examples" / "preview-run"


def _make_minimal_manifest(decision: str = "needs_review") -> dict:
    """Create a minimal valid manifest dict with one page."""
    return {
        "run_id": "test-run",
        "title": "Test",
        "status": "draft",
        "pages": [
            {
                "page_id": "p1",
                "order": 1,
                "source_type": "generated",
                "preview_path": "links/p1.svg",
                "narrative_role": "intro",
                "decision": decision,
                "notes": "",
            }
        ],
    }


class MigrationUnitTests(unittest.TestCase):
    """Unit tests for migrate_page_to_review_status and sync_legacy_decision."""

    def test_approved_maps_correctly(self) -> None:
        page = {"decision": "approved"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("approved", result["review_status"])
        self.assertEqual("none", result["action_intent"])

    def test_keep_maps_correctly(self) -> None:
        page = {"decision": "keep"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("approved", result["review_status"])
        self.assertEqual("reuse", result["action_intent"])

    def test_replace_maps_correctly(self) -> None:
        page = {"decision": "replace"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("needs_review", result["review_status"])
        self.assertEqual("replace", result["action_intent"])

    def test_rejected_maps_correctly(self) -> None:
        page = {"decision": "rejected"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("rejected", result["review_status"])
        self.assertEqual("none", result["action_intent"])

    def test_needs_review_maps_correctly(self) -> None:
        page = {"decision": "needs_review"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("needs_review", result["review_status"])
        self.assertEqual("none", result["action_intent"])

    def test_existing_review_status_not_overwritten(self) -> None:
        page = {
            "decision": "approved",
            "review_status": "needs_review",
            "action_intent": "replace",
        }
        result = migrate_page_to_review_status(page)
        # Should keep existing values
        self.assertEqual("needs_review", result["review_status"])
        self.assertEqual("replace", result["action_intent"])

    def test_unknown_decision_defaults_to_needs_review(self) -> None:
        page = {"decision": "unknown_value"}
        result = migrate_page_to_review_status(page)
        self.assertEqual("needs_review", result["review_status"])
        self.assertEqual("none", result["action_intent"])

    def test_missing_decision_defaults_to_needs_review(self) -> None:
        page: dict = {}
        result = migrate_page_to_review_status(page)
        self.assertEqual("needs_review", result["review_status"])
        self.assertEqual("none", result["action_intent"])

    def test_sync_legacy_approved_reuse_to_keep(self) -> None:
        page = {"review_status": "approved", "action_intent": "reuse"}
        sync_legacy_decision(page)
        self.assertEqual("keep", page["decision"])

    def test_sync_legacy_approved_none_to_approved(self) -> None:
        page = {"review_status": "approved", "action_intent": "none"}
        sync_legacy_decision(page)
        self.assertEqual("approved", page["decision"])

    def test_sync_legacy_approved_adapt_to_approved(self) -> None:
        page = {"review_status": "approved", "action_intent": "adapt"}
        sync_legacy_decision(page)
        self.assertEqual("approved", page["decision"])

    def test_sync_legacy_rejected_to_rejected(self) -> None:
        page = {"review_status": "rejected", "action_intent": "none"}
        sync_legacy_decision(page)
        self.assertEqual("rejected", page["decision"])

    def test_sync_legacy_needs_review_replace_to_replace(self) -> None:
        page = {"review_status": "needs_review", "action_intent": "replace"}
        sync_legacy_decision(page)
        self.assertEqual("replace", page["decision"])

    def test_sync_legacy_needs_review_none_to_needs_review(self) -> None:
        page = {"review_status": "needs_review", "action_intent": "none"}
        sync_legacy_decision(page)
        self.assertEqual("needs_review", page["decision"])

    def test_sync_legacy_needs_evidence_to_needs_review(self) -> None:
        page = {"review_status": "needs_evidence", "action_intent": "request_evidence"}
        sync_legacy_decision(page)
        self.assertEqual("needs_review", page["decision"])

    def test_sync_legacy_fallback_approved(self) -> None:
        page = {"review_status": "approved", "action_intent": "manual_placeholder"}
        sync_legacy_decision(page)
        self.assertEqual("approved", page["decision"])

    def test_sync_legacy_fallback_rejected(self) -> None:
        page = {"review_status": "rejected", "action_intent": "reuse"}
        sync_legacy_decision(page)
        self.assertEqual("rejected", page["decision"])

    def test_sync_legacy_fallback_needs_review(self) -> None:
        page = {"review_status": "needs_review", "action_intent": "adapt"}
        sync_legacy_decision(page)
        self.assertEqual("needs_review", page["decision"])


class LoadManifestMigrationTests(unittest.TestCase):
    """Integration tests: loading old manifests auto-migrates pages."""

    def copy_sample(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        run_dir = temp_dir / "run"
        shutil.copytree(SAMPLE_RUN, run_dir)
        manifest_path = run_dir / "preview_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][1]["decision"] = "keep"
        manifest["pages"][2]["decision"] = "replace"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return run_dir

    def test_load_auto_migrates_pages(self) -> None:
        run_dir = self.copy_sample()
        data = load_manifest(run_dir)
        # page_001 has decision=needs_review
        p1 = next(p for p in data["pages"] if p["page_id"] == "page_001")
        self.assertEqual("needs_review", p1["review_status"])
        self.assertEqual("none", p1["action_intent"])

        # page_002 has decision=keep
        p2 = next(p for p in data["pages"] if p["page_id"] == "page_002")
        self.assertEqual("approved", p2["review_status"])
        self.assertEqual("reuse", p2["action_intent"])

        # page_003 has decision=replace
        p3 = next(p for p in data["pages"] if p["page_id"] == "page_003")
        self.assertEqual("needs_review", p3["review_status"])
        self.assertEqual("replace", p3["action_intent"])

    def test_legacy_decision_preserved_after_migration(self) -> None:
        run_dir = self.copy_sample()
        data = load_manifest(run_dir)
        p2 = next(p for p in data["pages"] if p["page_id"] == "page_002")
        self.assertEqual("keep", p2["decision"])


class UpdatePageReviewTests(unittest.TestCase):
    """Tests for the new update_page_review function."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = self.temp_dir / "run"
        self.run_dir.mkdir()
        manifest = _make_minimal_manifest("needs_review")
        (self.run_dir / "preview_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_update_page_review_sets_fields_and_syncs_decision(self) -> None:
        page = update_page_review(self.run_dir, "p1", "approved", "reuse", "Looks good.")
        self.assertEqual("approved", page["review_status"])
        self.assertEqual("reuse", page["action_intent"])
        self.assertEqual("keep", page["decision"])  # approved+reuse → keep
        self.assertEqual("Looks good.", page["notes"])
        self.assertIn("reviewed_at", page)

    def test_update_page_review_approved_none(self) -> None:
        page = update_page_review(self.run_dir, "p1", "approved", "none")
        self.assertEqual("approved", page["decision"])

    def test_update_page_review_rejected(self) -> None:
        page = update_page_review(self.run_dir, "p1", "rejected", "none", "Nope.")
        self.assertEqual("rejected", page["decision"])
        self.assertEqual("rejected", page["review_status"])

    def test_update_page_review_needs_review_replace(self) -> None:
        page = update_page_review(self.run_dir, "p1", "needs_review", "replace")
        self.assertEqual("replace", page["decision"])

    def test_update_page_review_needs_evidence(self) -> None:
        page = update_page_review(self.run_dir, "p1", "needs_evidence", "request_evidence")
        self.assertEqual("needs_review", page["decision"])
        self.assertEqual("needs_evidence", page["review_status"])
        self.assertEqual("request_evidence", page["action_intent"])

    def test_update_page_review_invalid_status_raises(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            update_page_review(self.run_dir, "p1", "invalid_status")
        self.assertIn("Invalid review_status", str(ctx.exception))

    def test_update_page_review_invalid_intent_raises(self) -> None:
        with self.assertRaises(ManifestError) as ctx:
            update_page_review(self.run_dir, "p1", "approved", "bad_intent")
        self.assertIn("Invalid action_intent", str(ctx.exception))

    def test_update_page_review_persists_to_disk(self) -> None:
        update_page_review(self.run_dir, "p1", "approved", "reuse", "Saved.")
        data = load_manifest(self.run_dir)
        p1 = next(p for p in data["pages"] if p["page_id"] == "p1")
        self.assertEqual("approved", p1["review_status"])
        self.assertEqual("reuse", p1["action_intent"])
        self.assertEqual("keep", p1["decision"])

    def test_update_page_source_decision_persists_generation_intent(self) -> None:
        page = update_page_source_decision(
            self.run_dir,
            "p1",
            "generate",
            review_status="needs_review",
            action_intent="generate",
        )
        self.assertEqual("generate", page["source_decision"])
        self.assertEqual("needs_review", page["review_status"])
        self.assertEqual("generate", page["action_intent"])
        self.assertEqual("needs_review", page["decision"])


class UpdatePageDecisionBackwardCompatTests(unittest.TestCase):
    """Ensure update_page_decision still works with legacy signature."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = self.temp_dir / "run"
        self.run_dir.mkdir()
        manifest = _make_minimal_manifest("needs_review")
        (self.run_dir / "preview_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_legacy_call_still_works(self) -> None:
        page = update_page_decision(self.run_dir, "p1", "approved", "Ready.")
        self.assertEqual("approved", page["decision"])
        self.assertEqual("Ready.", page["notes"])
        # Should also have review_status/action_intent set
        self.assertEqual("approved", page["review_status"])
        self.assertEqual("none", page["action_intent"])

    def test_legacy_keep_maps_review_fields(self) -> None:
        page = update_page_decision(self.run_dir, "p1", "keep", "")
        self.assertEqual("keep", page["decision"])
        self.assertEqual("approved", page["review_status"])
        self.assertEqual("reuse", page["action_intent"])

    def test_new_params_override_and_sync(self) -> None:
        page = update_page_decision(
            self.run_dir, "p1", "approved", "Note",
            review_status="approved", action_intent="reuse",
        )
        # sync_legacy_decision should override decision to "keep"
        self.assertEqual("keep", page["decision"])
        self.assertEqual("approved", page["review_status"])
        self.assertEqual("reuse", page["action_intent"])


if __name__ == "__main__":
    unittest.main()
