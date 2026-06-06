from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generation.task_builder import create_generation_tasks
from tools.deck_pro_max_client import build_init_command


class GenerationTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_create_tasks_for_generate_and_adapt(self) -> None:
        sourcing = {
            "run_id": "run",
            "decisions": [
                {"beat_id": "b1", "page_title": "生成页", "source_decision": "generate"},
                {"beat_id": "b2", "page_title": "复用页", "source_decision": "reuse"},
                {"beat_id": "b3", "page_title": "改写页", "source_decision": "adapt"},
            ],
        }
        tasks = create_generation_tasks(sourcing, self.temp_dir)

        self.assertEqual(2, len(tasks["tasks"]))
        self.assertTrue((self.temp_dir / "generation_tasks" / "index.json").exists())

    def test_build_deck_pro_max_init_command(self) -> None:
        command = build_init_command(project_dir=Path("/tmp/project"), pages=3)
        self.assertIn("init", command)
        self.assertIn("--production-mode", command)
        self.assertIn("expert", command)


if __name__ == "__main__":
    unittest.main()
