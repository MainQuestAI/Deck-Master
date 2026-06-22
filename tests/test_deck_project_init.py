from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workspace.project_init import init_deck_project  # noqa: E402


class DeckProjectInitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_project_init_")
        self.workspace = Path(self._tmp) / "customer_project"

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_init_project_creates_v1_workspace_structure(self) -> None:
        result = init_deck_project(self.workspace, name="Customer Deck")

        self.assertEqual("initialized", result["status"])
        for rel in [
            "00-客户原始需求",
            "01-会议与沟通",
            "02-AI协作过程/有价值",
            "02-AI协作过程/临时过程",
            "03-参考素材/历史方案",
            "03-参考素材/客户素材",
            "03-参考素材/竞品与行业",
            "03-参考素材/截图与证据",
            "04-方案与交付物/deck-master",
            "04-方案与交付物/exports",
            "04-方案与交付物/review",
        ]:
            self.assertTrue((self.workspace / rel).is_dir(), rel)

        project = json.loads((self.workspace / ".deck-master" / "deck_project.json").read_text(encoding="utf-8"))
        self.assertEqual("deck_master_project.v1", project["schema_version"])
        self.assertEqual("Customer Deck", project["name"])
        self.assertTrue((self.workspace / ".deck-master" / "material_inventory.json").exists())
        self.assertTrue((self.workspace / ".deck-master" / "workspace_policy.json").exists())
        self.assertTrue((self.workspace / ".deck-master" / "run_bindings.json").exists())
        self.assertTrue((self.workspace / "workspace_manifest.json").exists())

    def test_init_project_is_idempotent_and_preserves_user_files(self) -> None:
        init_deck_project(self.workspace, name="Customer Deck")
        forbidden = self.workspace / "quality" / "forbidden_terms.md"
        forbidden.write_text("客户自定义禁词\n", encoding="utf-8")

        result = init_deck_project(self.workspace, name="Customer Deck")

        self.assertEqual("already_initialized", result["status"])
        self.assertEqual("客户自定义禁词\n", forbidden.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
