from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.events import append_event, read_events
from runtime.run_state import RunStateError, create_run, load_request, run_status, write_artifact


class RuntimeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_create_run_writes_request_and_event_log(self) -> None:
        run_dir = create_run(self.temp_dir, {"project_name": "Retail", "business_goal": "Goal"}, run_id="retail")

        self.assertEqual("retail", load_request(run_dir)["run_id"])
        self.assertEqual("request_ready", run_status(run_dir))
        self.assertEqual("run.created", read_events(run_dir)[0]["action"])

    def test_duplicate_run_requires_force(self) -> None:
        create_run(self.temp_dir, {"project_name": "Retail", "business_goal": "Goal"}, run_id="retail")
        with self.assertRaises(RunStateError):
            create_run(self.temp_dir, {"project_name": "Retail", "business_goal": "Goal"}, run_id="retail")

    def test_write_artifact_advances_status(self) -> None:
        run_dir = create_run(self.temp_dir, {"project_name": "Retail", "business_goal": "Goal"}, run_id="retail")
        write_artifact(run_dir, "narrative_plan.json", {"beats": []}, action="narrative.plan.created")
        append_event(run_dir, "custom.event")

        self.assertEqual("planned", run_status(run_dir))
        self.assertEqual(["run.created", "narrative.plan.created", "custom.event"], [event["action"] for event in read_events(run_dir)])


if __name__ == "__main__":
    unittest.main()
