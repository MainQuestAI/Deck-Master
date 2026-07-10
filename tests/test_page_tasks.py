from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative
from planning.page_tasks import build_page_tasks


def _sample_judgments() -> dict:
    return {
        "schema_version": "deck_consulting_judgments.v1",
        "run_id": "test-run",
        "judgments": [
            {
                "judgment_id": "judgment_business_problem",
                "topic": "business_problem",
                "statement": "客户核心问题是全渠道库存不透明导致履约效率低。",
                "rationale": "会议转写和 brief 指向核心业务问题。",
                "confidence": 0.7,
                "source_refs": ["context_manifest.json"],
                "risk_flags": [],
            },
            {
                "judgment_id": "judgment_solution_approach",
                "topic": "solution_approach",
                "statement": "方案路径涵盖统一库存中台、智能补货和末端配送优化三个模块。",
                "rationale": "从 4 个论点和 3 个核心要点推导出方案路径。",
                "confidence": 0.75,
                "source_refs": ["deck_brief.json", "claim_map.json"],
                "risk_flags": [],
            },
        ],
        "open_questions": [],
    }


def _sample_claim_graph() -> dict:
    return {
        "schema_version": "deck_claim_evidence_graph.v1",
        "run_id": "test-run",
        "claims": [
            {
                "claim_id": "claim_01",
                "type": "core",
                "statement": "全渠道库存实时可视化可将缺货率降低30%。",
                "supporting_evidence": ["evidence_001"],
                "assumptions": [],
                "risks": [],
                "required_evidence": ["customer_data"],
                "page_refs": ["beat_02_problem", "beat_10_case"],
            },
            {
                "claim_id": "claim_02",
                "type": "core",
                "statement": "最后一公里优化可缩短配送时间20%。",
                "supporting_evidence": [],
                "assumptions": ["assumption_001"],
                "risks": ["risk_001"],
                "required_evidence": ["logistics_data"],
                "page_refs": ["beat_11_roi"],
            },
        ],
        "evidence": [
            {
                "evidence_id": "evidence_001",
                "source_ref": "meeting_transcript_01",
                "evidence_type": "meeting_quote",
                "summary": "客户提到当前缺货率约15%。",
                "confidence": 0.8,
                "publication_status": "safe_to_use",
            },
        ],
        "assumptions": [],
        "risks": [],
        "page_refs": {
            "claim_01": ["beat_02_problem", "beat_10_case"],
            "claim_02": ["beat_11_roi"],
        },
        "gaps": [
            {
                "claim_id": "claim_02",
                "description": "论点 '最后一公里优化' 需要 1 项证据但当前为 0。",
                "required_evidence": ["logistics_data"],
                "repair_instruction": "补充以下证据：logistics_data",
            },
        ],
    }


class PageTasksTests(unittest.TestCase):
    def test_page_task_identity_uses_stable_fallback_order(self) -> None:
        plan = {
            "run_id": "identity-run",
            "beats": [
                {"beat_id": "beat_1", "page_task_id": "explicit"},
                {"beat_id": "beat_2", "task_id": "task"},
                {"beat_id": "beat_3", "page_id": "page"},
                {"beat_id": "beat_4"},
            ],
        }

        result = build_page_tasks(plan)

        self.assertEqual(
            ["explicit", "task", "page", "beat_4"],
            [task["page_task_id"] for task in result["tasks"]],
        )

    def test_page_task_identity_rejects_missing_or_duplicate_ids(self) -> None:
        invalid_plans = [
            {"beats": [{"page_task_id": "task_1"}]},
            {"beats": [{"beat_id": "beat_1"}, {"beat_id": "beat_1"}]},
            {
                "beats": [
                    {"beat_id": "beat_1", "page_task_id": "task_1"},
                    {"beat_id": "beat_2", "page_task_id": "task_1"},
                ]
            },
        ]

        for plan in invalid_plans:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                build_page_tasks(plan)

    # ------------------------------------------------------------------ #
    # Backward compatibility
    # ------------------------------------------------------------------ #

    def test_backward_compat_old_signature(self) -> None:
        """build_page_tasks works with only narrative_plan (no new args)."""
        request = build_request(brief="通用方案", target_pages="auto")
        plan = plan_narrative(request)
        result = build_page_tasks(plan)
        self.assertIn("tasks", result)
        self.assertGreaterEqual(len(result["tasks"]), 1)
        for task in result["tasks"]:
            self.assertIn("planning", task)
            self.assertIn("retrieval", task)
            self.assertIn("sourcing", task)
            self.assertIn("generation", task)

    def test_backward_compat_with_claim_map_only(self) -> None:
        """build_page_tasks with claim_map but no claim_graph/judgments."""
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        plan = plan_narrative(request)
        claim_map = {
            "claims": [
                {"claim": "全渠道库存可降低缺货率", "risk_flags": []},
                {"claim": "最后一公里优化提升体验", "risk_flags": ["evidence_gap"]},
            ]
        }
        result = build_page_tasks(plan, claim_map=claim_map)
        self.assertEqual(len(result["tasks"]), len(plan["beats"]))

    # ------------------------------------------------------------------ #
    # Enhanced fields from narrative planner v2
    # ------------------------------------------------------------------ #

    def test_enhanced_fields_present_in_tasks(self) -> None:
        """Tasks include decision_intent, argument_chain, evidence_policy when judgments provided."""
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        judgments = _sample_judgments()
        plan = plan_narrative(request, judgments=judgments)
        result = build_page_tasks(plan, judgments=judgments)

        for task in result["tasks"]:
            planning = task["planning"]
            self.assertIn("argument_chain", planning)
            self.assertIsInstance(planning["argument_chain"], list)
            self.assertIn("evidence_policy", planning)
            self.assertIsInstance(planning["evidence_policy"]["required"], bool)
            self.assertIn("customer_specificity_level", planning)

        # Problem beat should have decision_intent.
        problem_task = next(t for t in result["tasks"] if t["planning"]["role"] == "problem")
        self.assertIn("decision_intent", problem_task["planning"])
        self.assertIn("全渠道库存不透明", problem_task["planning"]["decision_intent"])

    # ------------------------------------------------------------------ #
    # Claim graph integration
    # ------------------------------------------------------------------ #

    def test_claim_graph_associates_claim_ids(self) -> None:
        """When claim_graph is provided, tasks get claim_ids from page_refs."""
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        claim_graph = _sample_claim_graph()
        plan = plan_narrative(request, claim_graph=claim_graph)
        result = build_page_tasks(plan, claim_graph=claim_graph)

        # Task for beat_02_problem should have claim_01.
        problem_task = next(t for t in result["tasks"] if t["beat_id"] == "beat_02_problem")
        self.assertIn("claim_ids", problem_task)
        self.assertIn("claim_01", problem_task["claim_ids"])
        self.assertIn("claim_ids", problem_task["planning"])

        # Task for beat_11_roi should have claim_02.
        roi_task = next(t for t in result["tasks"] if t["beat_id"] == "beat_11_roi")
        self.assertIn("claim_ids", roi_task)
        self.assertIn("claim_02", roi_task["claim_ids"])

    def test_claim_graph_provides_evidence_info(self) -> None:
        """claim_graph enriches tasks with available_evidence and evidence_gaps."""
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        claim_graph = _sample_claim_graph()
        plan = plan_narrative(request, claim_graph=claim_graph)
        result = build_page_tasks(plan, claim_graph=claim_graph)

        # beat_02_problem has claim_01 which has evidence_001.
        problem_task = next(t for t in result["tasks"] if t["beat_id"] == "beat_02_problem")
        self.assertIn("available_evidence", problem_task["planning"])
        evidence_ids = [e["evidence_id"] for e in problem_task["planning"]["available_evidence"]]
        self.assertIn("evidence_001", evidence_ids)

        # beat_11_roi has claim_02 which has a gap.
        roi_task = next(t for t in result["tasks"] if t["beat_id"] == "beat_11_roi")
        self.assertIn("evidence_gaps", roi_task["planning"])
        gap_claim_ids = [g["claim_id"] for g in roi_task["planning"]["evidence_gaps"]]
        self.assertIn("claim_02", gap_claim_ids)

    # ------------------------------------------------------------------ #
    # Full pipeline: judgments + claim_graph + workspace_archetypes
    # ------------------------------------------------------------------ #

    def test_full_pipeline_integration(self) -> None:
        """Full integration: narrative planner v2 + page tasks with all optional inputs."""
        request = build_request(
            brief="零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送",
            industry="retail",
            target_pages="auto",
        )
        judgments = _sample_judgments()
        claim_graph = _sample_claim_graph()
        workspace_archetypes = {
            "archetypes": [
                {"role": "case", "ref": "archetype_case_study"},
            ],
        }

        plan = plan_narrative(
            request,
            judgments=judgments,
            claim_graph=claim_graph,
            workspace_archetypes=workspace_archetypes,
        )
        result = build_page_tasks(
            plan,
            claim_graph=claim_graph,
            judgments=judgments,
        )

        self.assertEqual(len(result["tasks"]), len(plan["beats"]))

        # Case beat should have workspace_refs.
        case_task = next(t for t in result["tasks"] if t["planning"]["role"] == "case")
        self.assertIn("workspace_refs", case_task["planning"])
        self.assertIn("archetype_case_study", case_task["planning"]["workspace_refs"])

        # All tasks should have structural enhanced fields.
        for task in result["tasks"]:
            p = task["planning"]
            self.assertIn("argument_chain", p)
            self.assertIn("evidence_policy", p)
            self.assertIn("customer_specificity_level", p)


if __name__ == "__main__":
    unittest.main()
