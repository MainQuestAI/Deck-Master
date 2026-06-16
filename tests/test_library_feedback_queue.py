from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from feedback.library_feedback import (
    LibraryFeedbackError,
    read_library_feedback_events,
    record_library_feedback,
)
from runtime.import_log import read_import_log
from runtime.run_state import create_run


class LibraryFeedbackQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm-lib-feedback-")
        self.run_dir = create_run(Path(self._tmp) / "runs", {"project_name": "Feedback", "run_id": "feedback-run"}, force=True)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_record_library_feedback_writes_run_local_queue(self) -> None:
        result = record_library_feedback(
            self.run_dir,
            run_id="feedback-run",
            page_task_id="page-001",
            beat_id="beat-001",
            candidate_id="slide-001",
            outcome="approved",
        )

        self.assertEqual("pending", result["status"])
        events = read_library_feedback_events(self.run_dir)
        self.assertEqual(1, len(events))
        self.assertEqual("feedback-run/page-001/beat-001/slide-001/approved", events[0]["idempotency_key"])
        logs = read_import_log(self.run_dir)
        self.assertEqual("library_feedback", logs[-1]["import_type"])

    def test_record_library_feedback_rejects_missing_fields(self) -> None:
        with self.assertRaises(LibraryFeedbackError):
            record_library_feedback(
                self.run_dir,
                run_id="feedback-run",
                page_task_id="page-001",
                beat_id="",
                candidate_id="slide-001",
                outcome="approved",
            )

    def test_record_library_feedback_is_idempotent(self) -> None:
        kwargs = {
            "run_id": "feedback-run",
            "page_task_id": "page-001",
            "beat_id": "beat-001",
            "candidate_id": "slide-001",
            "outcome": "approved",
        }
        record_library_feedback(self.run_dir, **kwargs)
        result = record_library_feedback(self.run_dir, **kwargs)

        self.assertEqual("duplicate", result["status"])
        self.assertEqual(1, len(read_library_feedback_events(self.run_dir)))

    def test_apply_is_explicitly_experimental(self) -> None:
        with self.assertRaises(LibraryFeedbackError):
            record_library_feedback(
                self.run_dir,
                run_id="feedback-run",
                page_task_id="page-001",
                beat_id="beat-001",
                candidate_id="slide-001",
                outcome="approved",
                apply=True,
            )


if __name__ == "__main__":
    unittest.main()
