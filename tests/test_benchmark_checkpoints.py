from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.checkpoints import (  # noqa: E402
    CHECKPOINTS_NAME,
    calculate_human_review_minutes,
    read_benchmark_checkpoints,
    write_benchmark_checkpoint,
)
from runtime.events import read_events  # noqa: E402


class BenchmarkCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.run_dir = self.temp_dir / "runs" / "retail-demo"
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "request.json").write_text(
            json.dumps({"run_id": "retail-demo"}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_checkpoint_writes_file_and_typed_event(self) -> None:
        payload = write_benchmark_checkpoint(
            self.run_dir,
            "context_ready",
            timestamp="2026-06-12T10:00:00+00:00",
            note="Context pack imported.",
        )

        path = self.run_dir / CHECKPOINTS_NAME
        self.assertTrue(path.exists())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload, saved)
        self.assertEqual("deck_benchmark_checkpoints.v1", saved["schema_version"])
        self.assertEqual("retail-demo", saved["run_id"])
        self.assertEqual("2026-06-12T10:00:00+00:00", saved["checkpoints"]["context_ready"]["timestamp"])
        self.assertEqual("Context pack imported.", saved["checkpoints"]["context_ready"]["note"])

        events = read_events(self.run_dir)
        self.assertEqual(1, len(events))
        self.assertEqual("deck_event.v1", events[0]["schema_version"])
        self.assertEqual("manual_action", events[0]["event_type"])
        self.assertEqual("benchmark_checkpoint.context_ready", events[0]["step"])
        self.assertEqual("benchmark.checkpoint.recorded", events[0]["action"])
        self.assertEqual(["benchmark_checkpoints.json"], events[0]["refs"])

    def test_read_missing_checkpoints_returns_empty_payload(self) -> None:
        payload = read_benchmark_checkpoints(self.run_dir)

        self.assertEqual("deck_benchmark_checkpoints.v1", payload["schema_version"])
        self.assertEqual("retail-demo", payload["run_id"])
        self.assertEqual({}, payload["checkpoints"])

    def test_human_review_minutes(self) -> None:
        write_benchmark_checkpoint(
            self.run_dir,
            "human_review_started",
            timestamp="2026-06-12T10:00:00+00:00",
        )
        write_benchmark_checkpoint(
            self.run_dir,
            "human_review_completed",
            timestamp="2026-06-12T11:30:00+00:00",
        )

        self.assertEqual(90.0, calculate_human_review_minutes(self.run_dir))


if __name__ == "__main__":
    unittest.main()
