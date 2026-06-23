from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.build import run_build
from runtime.final_readiness import compute_final_readiness, final_readiness_clearance, read_final_readiness
from runtime.run_state import create_run, write_json


class FinalReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = create_run(
            self.temp_dir,
            {"project_name": "Final Readiness", "business_goal": "Ship", "run_mode": "fixture"},
            run_id="final-ready",
        )
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _write_baseline(self, *, pages: list[dict] | None = None, gate_blocks: bool = False) -> None:
        pages = pages or [
            {
                "page_id": "page_001",
                "order": 1,
                "title": "One",
                "preview_path": "preview/page_001.html",
                "decision": "approved",
                "review_status": "approved",
            },
            {
                "page_id": "page_002",
                "order": 2,
                "title": "Two",
                "preview_path": "preview/page_002.html",
                "decision": "approved",
                "review_status": "approved",
            },
        ]
        write_json(self.run_dir / "context_manifest.json", {"run_id": "final-ready", "sources": []})
        write_json(self.run_dir / "deck_brief.json", {"run_id": "final-ready", "objective": "Ship"})
        write_json(self.run_dir / "claim_map.json", {"run_id": "final-ready", "claims": []})
        write_json(self.run_dir / "narrative_plan.json", {"run_id": "final-ready", "beats": []})
        write_json(self.run_dir / "page_tasks.json", {"run_id": "final-ready", "tasks": []})
        write_json(self.run_dir / "sourcing_plan.json", {"run_id": "final-ready", "decisions": []})
        write_json(
            self.run_dir / "preview_manifest.json",
            {"run_id": "final-ready", "title": "Final Readiness", "pages": pages},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(
            quality_dir / "draft_gate.json",
            {
                "schema_version": "deck_quality_report.v1",
                "gate": "draft",
                "status": "rework_required" if gate_blocks else "pass",
                "blocks_delivery": gate_blocks,
                "findings": [
                    {
                        "finding_id": "quality_block",
                        "severity": "P1",
                        "message": "Quality gate blocks delivery.",
                    }
                ] if gate_blocks else [],
                "page_findings": [],
            },
        )

    def _write_customer_visible_safety_gate(self, *, blocks: bool) -> None:
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(
            quality_dir / "customer_visible_safety_gate.json",
            {
                "schema_version": "deck_customer_visible_safety_gate.v1",
                "run_id": "final-ready",
                "gate": "customer_visible_safety",
                "status": "rework_required" if blocks else "pass",
                "artifact": "build/deck.pptx",
                "summary": {
                    "scanned_items": 1,
                    "forbidden_hits": 1 if blocks else 0,
                    "p0_count": 1 if blocks else 0,
                    "findings": 1 if blocks else 0,
                    "page_findings": 1 if blocks else 0,
                },
                "findings": [
                    {
                        "finding_id": "customer_visible_forbidden_001",
                        "severity": "P0",
                        "term": "证书墙",
                        "scope": "slide",
                        "package_path": "ppt/slides/slide1.xml",
                        "message": "最终 PPT 包含客户不可见的内部制作语言：证书墙",
                        "repair_instruction": "删除或改写该词。",
                    }
                ] if blocks else [],
                "page_findings": [],
                "blocks_delivery": blocks,
            },
        )

    def test_ready_run_writes_final_readiness(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)

        self.assertTrue(readiness["ready"])
        self.assertEqual("ready", readiness["status"])
        self.assertEqual("build/deck.html", readiness["final_artifact"]["path"])
        self.assertEqual(2, readiness["page_counts"]["approved"])
        self.assertTrue((self.run_dir / "delivery" / "final_readiness.json").exists())
        self.assertEqual(readiness["run_id"], read_final_readiness(self.run_dir)["run_id"])
        self.assertTrue(any("客户可见内容安全检查" in item for item in readiness["warnings"]))

    def test_production_missing_customer_visible_safety_gate_blocks_readiness(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)
        write_json(self.run_dir / "request.json", {"run_id": "final-ready", "run_mode": "production"})

        readiness = compute_final_readiness(
            self.run_dir,
            run_mode="production",
            dev_allow_unsetup=True,
        )

        codes = {item["code"] for item in readiness["blockers"]}
        self.assertIn("final_customer_visible_safety_missing", codes)

    def test_customer_visible_safety_blocker_is_user_facing_clearance_reason(self) -> None:
        self._write_baseline()
        self._write_customer_visible_safety_gate(blocks=True)
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)
        clearance = final_readiness_clearance(self.run_dir)

        self.assertFalse(readiness["ready"])
        self.assertIn("内部制作语言", clearance["reason"])

    def test_missing_render_blocks_readiness(self) -> None:
        self._write_baseline()

        readiness = compute_final_readiness(self.run_dir)

        self.assertFalse(readiness["ready"])
        codes = {item["code"] for item in readiness["blockers"]}
        self.assertIn("final_render_missing", codes)
        self.assertIn("final_lineage_missing", codes)

    def test_run_state_blocker_uses_user_facing_message(self) -> None:
        readiness = compute_final_readiness(self.run_dir)

        blocker = next(item for item in readiness["blockers"] if item["code"] == "final_run_state_not_ready")
        self.assertIn("项目背景与输入资料", blocker["message"])
        self.assertNotIn("Run state is", blocker["message"])

    def test_quality_gate_blocks_readiness(self) -> None:
        self._write_baseline(gate_blocks=True)
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)

        self.assertFalse(readiness["ready"])
        codes = {item["code"] for item in readiness["blockers"]}
        self.assertIn("final_run_state_not_ready", codes)
        self.assertIn("final_quality_gate_blocked", codes)
        self.assertIn("final_delivery_validation_blocked", codes)

    def test_page_count_mismatch_blocks_readiness(self) -> None:
        self._write_baseline(
            pages=[
                {
                    "page_id": "page_001",
                    "order": 1,
                    "title": "One",
                    "preview_path": "preview/page_001.html",
                    "decision": "approved",
                    "review_status": "approved",
                },
                {
                    "page_id": "page_002",
                    "order": 2,
                    "title": "Two",
                    "preview_path": "preview/page_002.html",
                    "decision": "rejected",
                    "review_status": "rejected",
                },
            ]
        )
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)

        self.assertFalse(readiness["ready"])
        self.assertIn("final_page_count_mismatch", {item["code"] for item in readiness["blockers"]})

    def test_no_write_option_keeps_file_absent(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir, write=False)

        self.assertTrue(readiness["ready"])
        self.assertFalse((self.run_dir / "delivery" / "final_readiness.json").exists())
        self.assertTrue((self.run_dir / "delivery" / "final_version_lineage.json").exists())

    def test_schema_version(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)

        self.assertEqual("deck_final_readiness.v1", readiness["schema_version"])
        json.dumps(readiness)


if __name__ == "__main__":
    unittest.main()
