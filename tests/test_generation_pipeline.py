"""Full pipeline test: page_tasks → sourcing v2 → generation tasks → UAT.

This test proves that the codebase's own upstream output satisfies the
downstream module's real contract — not just that each module works with
hand-crafted fixtures.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from generation.task_builder import create_generation_tasks
from sourcing.plan import build_sourcing_plan_v2
from uat.generation_tool import run_generation_tool_uat


def _page_tasks(run_id: str) -> dict:
    """Build a minimal but complete page_tasks fixture with planning fields."""
    return {
        "run_id": run_id,
        "pages": [
            {
                "beat_id": "beat_01_opener",
                "page_task_id": "task_01",
                "order": 1,
                "planning": {
                    "page_title": "Opening Hook",
                    "role": "opener",
                    "core_claim": "Digital transformation is not optional",
                    "content_goal": "Establish urgency and vision",
                    "visual_need": "Bold opener slide with key metric",
                    "workspace_refs": ["structure-assets/page_archetypes.md#opener"],
                    "quality_requirements": ["Must state the core claim", "Must include a metric"],
                    "claim_ids": ["claim_01"],
                    "evidence_need": "Industry transformation rate",
                },
                "generation": {
                    "generation_brief": "Create an opener slide with a bold metric about digital transformation urgency.",
                    "status": "pending",
                },
                "claim_ids": ["claim_01"],
            },
            {
                "beat_id": "beat_02_solution",
                "page_task_id": "task_02",
                "order": 2,
                "planning": {
                    "page_title": "Solution Architecture",
                    "role": "architecture",
                    "core_claim": "The platform architecture scales",
                    "content_goal": "Show the solution architecture",
                    "visual_need": "Architecture diagram slide",
                    "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
                    "quality_requirements": ["Must show the architecture", "Must label components"],
                    "claim_ids": ["claim_02"],
                    "evidence_need": "",
                },
                "generation": {
                    "generation_brief": "Create an architecture slide showing the platform components.",
                    "status": "pending",
                },
                "claim_ids": ["claim_02"],
            },
        ],
    }


def _library_results(run_id: str) -> dict:
    """Build library results with one candidate for page 2 (adapt) and none for page 1 (generate)."""
    return {
        "schema_version": "deck_master_ppt_library_selection.v2",
        "run_id": run_id,
        "status": "library_ready",
        "source": "ppt_library",
        "preview_degraded": False,
        "warnings": [],
        "selections": [
            {
                "beat_id": "beat_01_opener",
                "page_task_id": "task_01",
                "query_trace_id": "trace_01",
                "retrieval_method": "role_selection",
                "preview_status": "ready",
                "preview_degraded": False,
                "candidates": [],
            },
            {
                "beat_id": "beat_02_solution",
                "page_task_id": "task_02",
                "query_trace_id": "trace_02",
                "retrieval_method": "role_selection",
                "preview_status": "ready",
                "preview_degraded": False,
                "candidates": [
                    {
                        "asset_key": "canonical:arch-001",
                        "slide_id": "slide-arch-001",
                        "title": "Platform Architecture",
                        "score": 0.92,
                        "confidence": 0.88,
                        "reuse_policy": "reuse_or_adapt",
                        "reuse_safe": True,
                        "candidate_origin": "ppt_library",
                        "source_authority": "verified",
                        "freshness_status": "fresh",
                    },
                ],
            },
        ],
    }


class GenerationPipelineTest(unittest.TestCase):
    """Verify the full pipeline produces UAT-passing generation tasks."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm-pipeline-"))
        self.run_id = "pipeline-test"
        # UAT reads run_id from request.json
        (self.temp_dir / "request.json").write_text(
            json.dumps({"run_id": self.run_id}), encoding="utf-8"
        )

    def test_page_tasks_to_sourcing_to_generation_tasks_to_uat(self) -> None:
        page_tasks = _page_tasks(self.run_id)
        library_results = _library_results(self.run_id)

        # Step 1: Build sourcing plan
        sourcing_plan = build_sourcing_plan_v2(
            run_id=self.run_id,
            page_tasks=page_tasks,
            library_results=library_results,
        )
        self.assertEqual("deck_sourcing_plan.v2", sourcing_plan["schema_version"])
        self.assertEqual(2, len(sourcing_plan["pages"]))

        page1 = sourcing_plan["pages"][0]
        page2 = sourcing_plan["pages"][1]
        # Page 1 has no candidates → generate
        self.assertEqual("generate", page1["decision"])
        self.assertEqual("NO_CANDIDATE_GENERATE", page1["reason"])
        self.assertEqual("not_required", page1["permission_status"])
        # Page 2 has a candidate with reuse_safe=True and clear preview → reuse
        self.assertEqual("reuse", page2["decision"])
        self.assertEqual("ROLE_SELECTION_PREVIEW_READY", page2["reason"])

        # Verify field passthrough from page_tasks to sourcing plan
        self.assertEqual("opener", page1["role"])
        self.assertEqual("Establish urgency and vision", page1["content_goal"])
        self.assertTrue(page1["generation_brief"])
        self.assertTrue(page1["visual_need"])
        self.assertEqual(["structure-assets/page_archetypes.md#opener"], page1["workspace_refs"])
        self.assertEqual(["Must state the core claim", "Must include a metric"], page1["quality_requirements"])
        self.assertEqual(["preview_path", "artifact_path"], page1["expected_outputs"])

        # Step 2: Create generation tasks
        result = create_generation_tasks(sourcing_plan, str(self.temp_dir))
        tasks = result["tasks"]
        self.assertTrue(len(tasks) >= 1, "At least one generation task should be created")

        # Step 3: Verify each task has the required UAT fields
        for task in tasks:
            self.assertEqual("deck_generation_task.v1", task["schema_version"])
            self.assertEqual(self.run_id, task["run_id"])
            self.assertTrue(task["workspace_refs"], "workspace_refs must be non-empty")
            self.assertTrue(task["quality_requirements"], "quality_requirements must be non-empty")
            self.assertTrue(task["expected_outputs"], "expected_outputs must be non-empty")
            self.assertTrue(task["generation_brief"], "generation_brief must be non-empty")

        # Step 4: Verify index has schema_version
        index_path = self.temp_dir / "generation_tasks" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual("deck_generation_task_index.v1", index["schema_version"])
        self.assertEqual(self.run_id, index["run_id"])

        # Step 5: Run the Generation Tool UAT
        uat_result = run_generation_tool_uat(self.temp_dir, write=False)
        self.assertEqual("pass", uat_result["status"],
                         f"UAT should pass: {json.dumps(uat_result.get('findings', []), indent=2)}")
        enhanced = uat_result.get("metrics", {}).get("enhanced_task_count", 0)
        self.assertEqual(len(tasks), enhanced,
                         f"All tasks should be enhanced: {enhanced}/{len(tasks)}")


if __name__ == "__main__":
    unittest.main()
