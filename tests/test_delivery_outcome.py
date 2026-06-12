from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from delivery.outcome import record_delivery_outcome


class DeliveryOutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = temp_dir / "run-outcome"
        self.run_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

    # ---- 记录 delivered ----
    def test_record_delivered(self) -> None:
        outcome = record_delivery_outcome(
            self.run_dir,
            delivered=True,
            advanced_to_next_stage=True,
        )

        self.assertTrue(outcome["delivered"])
        self.assertIsNotNone(outcome["delivered_at"])
        self.assertTrue(outcome["advanced_to_next_stage"])
        self.assertEqual("run-outcome", outcome["run_id"])
        self.assertEqual("deck_delivery_outcome.v1", outcome["schema_version"])

    # ---- 记录 customer reaction ----
    def test_record_customer_reaction(self) -> None:
        outcome = record_delivery_outcome(
            self.run_dir,
            delivered=True,
            customer_reaction="positive",
            notes="Client wants follow-up deck.",
        )

        self.assertEqual("positive", outcome["customer_reaction"])
        self.assertEqual("Client wants follow-up deck.", outcome["notes"])

    # ---- outcome 文件写入 ----
    def test_outcome_file_written(self) -> None:
        record_delivery_outcome(
            self.run_dir,
            delivered=False,
            customer_reaction="",
        )

        outcome_path = self.run_dir / "delivery" / "delivery_outcome.json"
        self.assertTrue(outcome_path.exists())

        data = json.loads(outcome_path.read_text(encoding="utf-8"))
        self.assertFalse(data["delivered"])
        self.assertIsNone(data["delivered_at"])
        self.assertEqual("deck_delivery_outcome.v1", data["schema_version"])

    # ---- typed event 写入 ----
    def test_typed_event_written(self) -> None:
        record_delivery_outcome(
            self.run_dir,
            delivered=True,
            advanced_to_next_stage=False,
        )

        events_path = self.run_dir / "events.jsonl"
        self.assertTrue(events_path.exists())

        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 1)

        event = json.loads(lines[-1])
        self.assertEqual("step_completed", event["event_type"])
        self.assertEqual("delivery.outcome.recorded", event["step"])
        self.assertIn("delivered=True", event["message"])

    # ---- not delivered 时 delivered_at 为 None ----
    def test_not_delivered_has_none_timestamp(self) -> None:
        outcome = record_delivery_outcome(self.run_dir, delivered=False)

        self.assertFalse(outcome["delivered"])
        self.assertIsNone(outcome["delivered_at"])

    # ---- 多次调用覆盖 outcome ----
    def test_overwrite_outcome(self) -> None:
        record_delivery_outcome(self.run_dir, delivered=False)
        record_delivery_outcome(self.run_dir, delivered=True, customer_reaction="great")

        outcome_path = self.run_dir / "delivery" / "delivery_outcome.json"
        data = json.loads(outcome_path.read_text(encoding="utf-8"))
        self.assertTrue(data["delivered"])
        self.assertEqual("great", data["customer_reaction"])


if __name__ == "__main__":
    unittest.main()
