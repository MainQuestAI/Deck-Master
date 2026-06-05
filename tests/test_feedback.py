from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "feedback"))

from record_deal import record_deal, summarize


QUEUE = ROOT / "examples" / "feedback" / "approved_queue.json"


class FeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.log = self.temp_dir / "deal_results.jsonl"

    def test_record_deal_appends_jsonl(self) -> None:
        record = record_deal(QUEUE, self.log, "retail-demo-001", "won", "Good fit.")

        self.assertTrue(self.log.exists())
        self.assertEqual("retail-demo-001", record["deal_id"])
        self.assertEqual("won", record["outcome"])
        self.assertEqual(1, len(record["pages"]))
        self.assertIn("library::", record["pages"][0]["slide_key"])

    def test_summarize_counts_win_rate(self) -> None:
        record_deal(QUEUE, self.log, "retail-demo-001", "won")
        record_deal(QUEUE, self.log, "retail-demo-002", "lost")
        record_deal(QUEUE, self.log, "retail-demo-003", "unknown")

        summary = summarize(self.log)
        slide = summary["slides"][0]
        self.assertEqual(3, slide["uses"])
        self.assertEqual(1, slide["wins"])
        self.assertEqual(1, slide["losses"])
        self.assertEqual(1, slide["unknown"])
        self.assertEqual(0.5, slide["win_rate"])

    def test_record_rejects_invalid_outcome(self) -> None:
        with self.assertRaises(ValueError):
            record_deal(QUEUE, self.log, "retail-demo-001", "pending")

    def test_summarize_empty_log(self) -> None:
        self.assertEqual({"slides": []}, summarize(self.log))


if __name__ == "__main__":
    unittest.main()
