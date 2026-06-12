from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assets.feedback import (
    append_feedback,
    append_feedback_dedup,
    get_asset_feedback_summary,
    is_duplicate_feedback,
    read_feedback,
)


class AssetFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    # --- append_feedback ---

    def test_append_feedback_writes_jsonl(self) -> None:
        entry = append_feedback(
            self.temp_dir,
            event_type="preview_approved",
            canonical_slide_id="slide-001",
            run_id="run-A",
            page_id="p1",
            notes="looks good",
        )
        jsonl_path = self.temp_dir / "assets" / "asset_feedback.jsonl"
        self.assertTrue(jsonl_path.exists())
        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(1, len(lines))
        self.assertEqual("preview_approved", entry["event_type"])
        self.assertEqual("slide-001", entry["canonical_slide_id"])
        self.assertIn("timestamp", entry)

    def test_append_feedback_with_payload(self) -> None:
        entry = append_feedback(
            self.temp_dir,
            event_type="delivered",
            canonical_slide_id="slide-002",
            payload={"channel": "email", "recipient": "client-x"},
        )
        self.assertEqual({"channel": "email", "recipient": "client-x"}, entry["payload"])

    def test_append_feedback_invalid_event_type_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            append_feedback(self.temp_dir, event_type="invalid_event", canonical_slide_id="s1")
        self.assertIn("Invalid feedback event_type", str(ctx.exception))

    def test_append_feedback_empty_canonical_slide_id_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            append_feedback(self.temp_dir, event_type="delivered", canonical_slide_id="")
        self.assertIn("canonical_slide_id is required", str(ctx.exception))

    # --- read_feedback ---

    def test_read_feedback_returns_all_entries(self) -> None:
        append_feedback(self.temp_dir, "preview_approved", "s1", run_id="r1")
        append_feedback(self.temp_dir, "preview_rejected", "s2", run_id="r2")
        entries = read_feedback(self.temp_dir)
        self.assertEqual(2, len(entries))
        self.assertEqual("s1", entries[0]["canonical_slide_id"])
        self.assertEqual("s2", entries[1]["canonical_slide_id"])

    def test_read_feedback_skips_bad_jsonl_lines(self) -> None:
        jsonl_path = self.temp_dir / "assets" / "asset_feedback.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_path.write_text(
            '{"event_type":"delivered","canonical_slide_id":"good"}\n'
            'NOT-VALID-JSON\n'
            '{"event_type":"exported_internal","canonical_slide_id":"also-good"}\n',
            encoding="utf-8",
        )
        entries = read_feedback(self.temp_dir)
        self.assertEqual(2, len(entries))
        self.assertEqual("good", entries[0]["canonical_slide_id"])
        self.assertEqual("also-good", entries[1]["canonical_slide_id"])

    def test_read_feedback_empty_when_no_file(self) -> None:
        entries = read_feedback(self.temp_dir)
        self.assertEqual([], entries)

    # --- get_asset_feedback_summary ---

    def test_get_asset_feedback_summary_counts(self) -> None:
        append_feedback(self.temp_dir, "preview_approved", "s1")
        append_feedback(self.temp_dir, "preview_approved", "s1")
        append_feedback(self.temp_dir, "preview_rejected", "s1")
        append_feedback(self.temp_dir, "exported_internal", "s1")
        append_feedback(self.temp_dir, "exported_client", "s1")
        append_feedback(self.temp_dir, "delivered", "s1")
        # Different slide — should not count
        append_feedback(self.temp_dir, "preview_approved", "s-other")

        summary = get_asset_feedback_summary(self.temp_dir, "s1")
        self.assertEqual("s1", summary["canonical_slide_id"])
        self.assertEqual(2, summary["approval_count"])
        self.assertEqual(1, summary["rejection_count"])
        self.assertEqual(2, summary["export_count"])
        self.assertEqual(1, summary["delivered_count"])
        self.assertEqual(6, summary["total_events"])
        self.assertIsNotNone(summary["latest_event"])
        self.assertEqual("delivered", summary["latest_event"]["event_type"])

    def test_get_asset_feedback_summary_no_events(self) -> None:
        summary = get_asset_feedback_summary(self.temp_dir, "nonexistent")
        self.assertEqual(0, summary["total_events"])
        self.assertIsNone(summary["latest_event"])

    # --- is_duplicate_feedback ---

    def test_is_duplicate_feedback_detects_duplicate(self) -> None:
        append_feedback(self.temp_dir, "preview_approved", "s1", run_id="r1", page_id="p1")
        self.assertTrue(
            is_duplicate_feedback(self.temp_dir, "preview_approved", "s1", "r1", "p1")
        )

    def test_is_duplicate_feedback_returns_false_for_new(self) -> None:
        append_feedback(self.temp_dir, "preview_approved", "s1", run_id="r1", page_id="p1")
        self.assertFalse(
            is_duplicate_feedback(self.temp_dir, "preview_approved", "s1", "r2", "p1")
        )

    # --- append_feedback_dedup ---

    def test_append_feedback_dedup_skips_duplicate(self) -> None:
        first = append_feedback_dedup(
            self.temp_dir, "preview_approved", "s1", run_id="r1", page_id="p1"
        )
        second = append_feedback_dedup(
            self.temp_dir, "preview_approved", "s1", run_id="r1", page_id="p1"
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        entries = read_feedback(self.temp_dir)
        self.assertEqual(1, len(entries))

    def test_append_feedback_dedup_allows_distinct_events(self) -> None:
        append_feedback_dedup(self.temp_dir, "preview_approved", "s1", run_id="r1", page_id="p1")
        result = append_feedback_dedup(self.temp_dir, "preview_rejected", "s1", run_id="r1", page_id="p1")
        self.assertIsNotNone(result)
        entries = read_feedback(self.temp_dir)
        self.assertEqual(2, len(entries))


if __name__ == "__main__":
    unittest.main()
