from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrate.preview_builder import (  # noqa: E402
    build_orchestration_plan_from_sourcing,
    build_preview_from_sourcing,
)


class GenerationPreviewSourcingV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_dir = Path(tempfile.mkdtemp(prefix="dm-d3b-preview-"))
        self.addCleanup(lambda: shutil.rmtree(self.run_dir, ignore_errors=True))
        self._write_request("fixture")

    def _write_request(self, run_mode: str) -> None:
        (self.run_dir / "request.json").write_text(
            json.dumps({"run_id": "run", "run_mode": run_mode}),
            encoding="utf-8",
        )

    @staticmethod
    def _page(
        page_id: str,
        decision: str,
        *,
        selected_sources: list[dict] | None = None,
        order: int = 1,
    ) -> dict:
        return {
            "page_id": page_id,
            "page_task_id": f"task-{page_id}",
            "order": order,
            "page_title": f"Title {page_id}",
            "decision": decision,
            "reason": f"Reason {page_id}",
            "confidence": 0.8,
            "claim_ids": [f"claim-{page_id}"],
            "evidence_need": [f"evidence-{page_id}"],
            "selected_sources": selected_sources or [],
        }

    @staticmethod
    def _plan(pages: list[dict]) -> dict:
        return {
            "schema_version": "deck_sourcing_plan.v2",
            "run_id": "run",
            "title": "Sourcing v2 Preview",
            "pages": pages,
        }

    def test_preview_uses_v2_sources_and_safe_customer_visible_identity(self) -> None:
        screenshot = self.run_dir / "preview_assets" / "ppt_library" / "slide-001.svg"
        screenshot.parent.mkdir(parents=True)
        screenshot.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        primary = {
            "asset_key": "canonical:slide-001",
            "query_trace_id": "trace-001",
            "page_task_id": "task-beat-001",
            "slide_id": "slide-001",
            "page_number": 4,
            "source_asset_id": "source-001",
            "source_display_name": "Safe Source.pptx",
            "screenshot_ref": "preview_assets/ppt_library/slide-001.svg",
            "source_file": "/Users/private/Customer Secret.pptx",
        }
        alternative = {
            "asset_key": "canonical:slide-002",
            "query_trace_id": "trace-001",
            "page_task_id": "task-beat-001",
            "source_asset_id": "source-002",
            "source_display_name": "Alternative Source.pptx",
        }

        manifest = build_preview_from_sourcing(
            self._plan([self._page("beat-001", "adapt", selected_sources=[primary, alternative])]),
            self.run_dir,
        )
        page = manifest["pages"][0]

        self.assertEqual("preview_assets/ppt_library/slide-001.svg", page["source_preview_asset"])
        self.assertTrue((self.run_dir / page["preview_path"]).exists())
        self.assertEqual("task-beat-001", page["page_task_id"])
        self.assertEqual("trace-001", page["query_trace_id"])
        self.assertEqual("canonical:slide-001", page["asset_key"])
        self.assertEqual("source-001", page["source_asset_id"])
        self.assertEqual("Safe Source.pptx", page["source_display_name"])
        self.assertEqual("canonical:slide-001", page["selected_candidate"]["asset_key"])
        self.assertNotIn("source_file", page["selected_candidate"])
        self.assertEqual([alternative], page["alternatives"])
        self.assertNotIn("source_pptx", page)
        self.assertNotIn("source_file", page)
        self.assertNotIn("/Users/private", json.dumps(page))

    def test_missing_and_invalid_screenshot_refs_use_stable_placeholders(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as outside_file:
            outside_file.write(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
            outside_path = Path(outside_file.name)
        self.addCleanup(lambda: outside_path.unlink(missing_ok=True))
        escaping_link = self.run_dir / "preview_assets" / "ppt_library" / "escape.svg"
        escaping_link.parent.mkdir(parents=True)
        escaping_link.symlink_to(outside_path)
        missing = {
            "asset_key": "canonical:missing",
            "query_trace_id": "trace-missing",
            "page_task_id": "task-missing",
            "screenshot_ref": "preview_assets/ppt_library/missing.png",
        }
        invalid = {
            "asset_key": "canonical:invalid",
            "query_trace_id": "trace-invalid",
            "page_task_id": "task-invalid",
            "screenshot_ref": "../private/preview.png",
        }
        escaping = {
            "asset_key": "canonical:escaping",
            "query_trace_id": "trace-escaping",
            "page_task_id": "task-escaping",
            "screenshot_ref": "preview_assets/ppt_library/escape.svg",
        }
        plan = self._plan(
            [
                self._page("missing", "reuse", selected_sources=[missing], order=1),
                self._page("invalid", "reuse", selected_sources=[invalid], order=2),
                self._page("escaping", "reuse", selected_sources=[escaping], order=3),
            ]
        )

        first = build_orchestration_plan_from_sourcing(plan, self.run_dir)
        second = build_orchestration_plan_from_sourcing(plan, self.run_dir)

        first_assets = {page["page_id"]: page["preview_asset"] for page in first["pages"]}
        second_assets = {page["page_id"]: page["preview_asset"] for page in second["pages"]}
        self.assertEqual(first_assets, second_assets)
        self.assertNotEqual("preview_assets/ppt_library/escape.svg", first_assets["escaping"])
        for asset in first_assets.values():
            self.assertTrue(asset.startswith("preview_assets/"))
            self.assertTrue((self.run_dir / asset).is_file())

    def test_production_and_benchmark_block_manual_or_blocked_v2_pages(self) -> None:
        for run_mode in ("production", "benchmark"):
            for decision in ("manual", "blocked"):
                with self.subTest(run_mode=run_mode, decision=decision):
                    self._write_request(run_mode)
                    with self.assertRaises(ValueError) as ctx:
                        build_preview_from_sourcing(
                            self._plan([self._page(f"{run_mode}-{decision}", decision)]),
                            self.run_dir,
                        )
                    self.assertIn(decision, str(ctx.exception))

    def test_legacy_v1_preview_flows_only_through_canonical_reader(self) -> None:
        legacy = {
            "schema_version": "deck_sourcing_plan.v1",
            "run_id": "run",
            "title": "Legacy Preview",
            "decisions": [
                {
                    "beat_id": "legacy-001",
                    "page_task_id": "legacy-task-001",
                    "order": 1,
                    "page_title": "Legacy page",
                    "source_decision": "adapt",
                    "selected_candidate": {
                        "slide_id": "legacy-slide",
                        "source_file": "/Users/private/Legacy Secret.pptx",
                        "source_asset_id": "legacy-source",
                        "source_display_name": "Legacy Safe Name.pptx",
                    },
                }
            ],
        }

        manifest = build_preview_from_sourcing(legacy, self.run_dir)
        page = manifest["pages"][0]

        self.assertEqual("adapt", page["source_decision"])
        self.assertEqual("legacy-source", page["source_asset_id"])
        self.assertEqual("Legacy Safe Name.pptx", page["source_display_name"])
        self.assertNotIn("source_pptx", page)
        self.assertNotIn("source_file", json.dumps(page))


if __name__ == "__main__":
    unittest.main()
