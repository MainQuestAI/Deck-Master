from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.build import run_build
from runtime.final_readiness import compute_final_readiness, final_readiness_clearance, read_final_readiness
from runtime.run_state import create_run, write_json
from quality.overrides import create_override


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

    def test_stale_customer_visible_safety_is_warning_in_fixture(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)
        self._write_customer_visible_safety_gate(blocks=False)

        readiness = compute_final_readiness(self.run_dir)

        self.assertTrue(readiness["ready"])
        self.assertTrue(any("需要重新扫描当前产物" in item for item in readiness["warnings"]))

    def test_stale_customer_visible_safety_blocks_production(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)
        self._write_customer_visible_safety_gate(blocks=False)
        write_json(self.run_dir / "request.json", {"run_id": "final-ready", "run_mode": "production"})

        readiness = compute_final_readiness(
            self.run_dir,
            run_mode="production",
            dev_allow_unsetup=True,
        )

        codes = {item["code"] for item in readiness["blockers"]}
        self.assertIn("final_customer_visible_safety_stale", codes)
        clearance = final_readiness_clearance(self.run_dir)
        self.assertIn("重新扫描当前产物", clearance["reason"])

    def test_customer_visible_safety_blocker_is_user_facing_clearance_reason(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)
        safety_path = self.run_dir / "quality_reports" / "customer_visible_safety_gate.json"
        self._write_customer_visible_safety_gate(blocks=True)
        safety_payload = json.loads(safety_path.read_text(encoding="utf-8"))
        artifact = self.run_dir / "build" / "deck.html"
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        safety_payload.update(
            {
                "artifact": "build/deck.html",
                "artifact_path": "build/deck.html",
                "artifact_run_relative": "build/deck.html",
                "artifact_sha256": digest,
            }
        )
        safety_path.write_text(json.dumps(safety_payload), encoding="utf-8")

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

    def test_p1_quality_gate_override_allows_final_readiness(self) -> None:
        self._write_baseline(gate_blocks=True)
        create_override(
            self.run_dir,
            "quality_block",
            "P1",
            "Accepted for client export.",
            "review-lead",
        )
        run_build(self.run_dir)

        readiness = compute_final_readiness(self.run_dir)

        self.assertTrue(readiness["ready"], readiness["blockers"])
        self.assertTrue(any("active P1 overrides" in item for item in readiness["warnings"]))

    def test_stale_quality_gate_warns_without_blocking_current_artifact(self) -> None:
        self._write_baseline(gate_blocks=True)
        run_build(self.run_dir)
        gate = self.run_dir / "quality_reports" / "draft_gate.json"
        payload = json.loads(gate.read_text(encoding="utf-8"))
        payload["artifact_path"] = "build/deck.pptx"
        payload["artifact_sha256"] = "0" * 64
        gate.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        readiness = compute_final_readiness(self.run_dir)

        self.assertTrue(readiness["ready"], readiness["blockers"])
        self.assertTrue(any("stale for the current artifact" in item for item in readiness["warnings"]))
        gate_summary = next(item for item in readiness["quality_gates"] if item["gate"] == "draft")
        self.assertFalse(gate_summary["current"])

    def test_stale_render_gate_does_not_count_as_current_in_production(self) -> None:
        self._write_baseline()
        run_build(self.run_dir)
        quality_dir = self.run_dir / "quality_reports"
        write_json(
            quality_dir / "render_gate.json",
            {
                "gate": "render",
                "status": "rework_required",
                "blocks_delivery": True,
                "artifact_path": "build/old-deck.pptx",
                "artifact_run_relative": "build/old-deck.pptx",
                "artifact_sha256": "0" * 64,
                "findings": [],
            },
        )
        write_json(self.run_dir / "request.json", {"run_id": "final-ready", "run_mode": "production"})

        readiness = compute_final_readiness(
            self.run_dir,
            run_mode="production",
            dev_allow_unsetup=True,
        )

        self.assertIn("final_current_artifact_gate_missing", {item["code"] for item in readiness["blockers"]})
        render_gate = next(item for item in readiness["quality_gates"] if item["gate"] == "render")
        self.assertFalse(render_gate["current"])
        self.assertTrue(any("stale for the current artifact" in item for item in readiness["warnings"]))

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

    def test_high_density_completed_profile_skips_standard_preview_state_blocker(self) -> None:
        run_dir = self.temp_dir / "hd-final"
        run_dir.mkdir()
        write_json(run_dir / "request.json", {"run_id": "hd-final", "run_mode": "production"})
        write_json(
            run_dir / "high_density_build" / "status.json",
            {
                "schema_version": "deck_high_density_status.v2",
                "run_id": "hd-final",
                "builder_profile": "high_density",
                "status": "completed",
                "current_stage": "pptx",
                "next_action": {"kind": "complete"},
            },
        )
        pptx = run_dir / "high_density_build" / "pptx" / "deck_high_density.pptx"
        pptx.parent.mkdir(parents=True)
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr("ppt/presentation.xml", "<p:presentation xmlns:p=\"x\"/>")
            package.writestr(
                "ppt/slides/slide1.xml",
                "<p:sld xmlns:p=\"x\" xmlns:a=\"x\"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Final slide</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>",
            )
        write_json(
            run_dir / "quality_reports" / "customer_visible_safety_gate.json",
            {
                "schema_version": "deck_customer_visible_safety_gate.v1",
                "run_id": "hd-final",
                "gate": "customer_visible_safety",
                "status": "pass",
                "blocks_delivery": False,
                "findings": [],
                "page_findings": [],
            },
        )

        readiness = compute_final_readiness(run_dir, run_mode="production", dev_allow_unsetup=True)

        self.assertFalse(readiness["ready"])
        self.assertEqual("blocked", readiness["status"])
        self.assertEqual("high_density_build/pptx/deck_high_density.pptx", readiness["final_artifact"]["path"])
        self.assertNotIn("final_run_state_not_ready", {item["code"] for item in readiness["blockers"]})
        self.assertIn("final_current_artifact_gate_missing", {item["code"] for item in readiness["blockers"]})


if __name__ == "__main__":
    unittest.main()
