from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team.opportunity import (
    attach_run,
    create_opportunity,
    list_opportunities,
    opportunities_dir,
)


class OpportunityModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_create_opportunity_structure(self) -> None:
        opp = create_opportunity(
            self.temp_dir,
            client_name="Acme",
            industry="manufacturing",
            opp_id="opp_test_001",
        )
        self.assertEqual(opp["schema_version"], "deck_opportunity.v1")
        self.assertEqual(opp["opp_id"], "opp_test_001")
        self.assertEqual(opp["client_name"], "Acme")
        self.assertEqual(opp["industry"], "manufacturing")
        self.assertEqual(opp["runs"], [])
        self.assertEqual(opp["outcomes"], [])
        self.assertIn("created_at", opp)

        opp_root = opportunities_dir(self.temp_dir) / "opp_test_001"
        self.assertTrue((opp_root / "opportunity.json").is_file())
        for sub in ("runs", "exports", "outcomes"):
            self.assertTrue((opp_root / sub).is_dir())

    def test_create_opportunity_auto_id(self) -> None:
        opp = create_opportunity(self.temp_dir, client_name="Beta")
        self.assertTrue(opp["opp_id"].startswith("opp_"))
        self.assertEqual(opp["client_name"], "Beta")

    def test_attach_run(self) -> None:
        create_opportunity(self.temp_dir, "Acme", opp_id="opp_a")
        result = attach_run(self.temp_dir, "opp_a", "run_001")
        self.assertIn("run_001", result["runs"])

        marker = opportunities_dir(self.temp_dir) / "opp_a" / "runs" / "run_001.json"
        self.assertTrue(marker.is_file())

    def test_attach_run_idempotent(self) -> None:
        create_opportunity(self.temp_dir, "Acme", opp_id="opp_b")
        attach_run(self.temp_dir, "opp_b", "run_001")
        result = attach_run(self.temp_dir, "opp_b", "run_001")
        # 重复 attach 不应产生重复条目
        self.assertEqual(result["runs"].count("run_001"), 1)

    def test_attach_run_unknown_opp_raises(self) -> None:
        with self.assertRaises(ValueError):
            attach_run(self.temp_dir, "no-such-opp", "run_x")

    def test_list_opportunities(self) -> None:
        create_opportunity(self.temp_dir, "Acme", opp_id="opp_1")
        create_opportunity(self.temp_dir, "Globex", opp_id="opp_2")
        items = list_opportunities(self.temp_dir)
        ids = {o["opp_id"] for o in items}
        self.assertEqual(ids, {"opp_1", "opp_2"})

    def test_list_opportunities_empty(self) -> None:
        ws = self.temp_dir / "fresh"
        ws.mkdir()
        self.assertEqual(list_opportunities(ws), [])

    def test_opportunity_aggregates_run_history(self) -> None:
        """一个 opportunity 可聚合多个 run，按附加顺序保留。"""
        create_opportunity(self.temp_dir, "Acme", opp_id="opp_agg")
        attach_run(self.temp_dir, "opp_agg", "run_A")
        attach_run(self.temp_dir, "opp_agg", "run_B")
        attach_run(self.temp_dir, "opp_agg", "run_C")

        opps = list_opportunities(self.temp_dir)
        target = next(o for o in opps if o["opp_id"] == "opp_agg")
        self.assertEqual(target["runs"], ["run_A", "run_B", "run_C"])

        runs_dir = opportunities_dir(self.temp_dir) / "opp_agg" / "runs"
        for rid in ("run_A", "run_B", "run_C"):
            self.assertTrue((runs_dir / f"{rid}.json").is_file())


if __name__ == "__main__":
    unittest.main()
