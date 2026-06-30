from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from planning.brief_intake import build_request
from planning.narrative_planner import plan_narrative


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


def _sample_workspace_archetypes() -> dict:
    return {
        "archetypes": [
            {"role": "opener", "ref": "archetype_opener_standard"},
            {"role": "case", "ref": "archetype_case_study_detail"},
            {"role": "roi", "ref": "archetype_roi_value_table"},
        ],
        "problem": "archetype_problem_pain_point",
        "solution": ["archetype_solution_overview", "archetype_capability_matrix"],
    }


class NarrativePlannerTests(unittest.TestCase):
    def test_retail_golden_plan_contains_required_topics(self) -> None:
        request = build_request(
            brief="零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送",
            industry="retail",
            target_pages="auto",
        )
        plan = plan_narrative(request)

        self.assertGreaterEqual(len(plan["beats"]), 10)
        text = "\n".join(f"{beat['page_title']} {beat['reuse_query']}" for beat in plan["beats"])
        for keyword in ("全渠道", "库存可视化", "最后一公里", "目标架构", "案例", "价值"):
            self.assertIn(keyword, text)

    def test_production_default_uses_generic_beats_without_retail_terms(self) -> None:
        request = build_request(
            brief="企业内容治理和智能知识运营方案",
            industry="enterprise",
            target_pages="auto",
        )
        plan = plan_narrative(request, planner_mode="production_narrative")
        text = "\n".join(beat["page_title"] for beat in plan["beats"])

        self.assertNotIn("全渠道场景", text)
        self.assertNotIn("库存可视化", text)
        self.assertNotIn("最后一公里配送", text)
        self.assertIn("业务场景闭环", text)

    def test_page_count_can_be_explicit(self) -> None:
        request = build_request(brief="通用解决方案", target_pages="30")
        plan = plan_narrative(request)
        self.assertEqual(30, len(plan["beats"]))
        self.assertEqual("solution", plan["density"])

    # ------------------------------------------------------------------ #
    # Backward compatibility
    # ------------------------------------------------------------------ #

    def test_backward_compat_no_optional_args(self) -> None:
        """plan_narrative without judgments/claim_graph/workspace_archetypes works as before."""
        request = build_request(brief="通用方案", target_pages="auto")
        plan = plan_narrative(request)
        self.assertIn("beats", plan)
        self.assertGreaterEqual(len(plan["beats"]), 1)
        # argument_chain and evidence_policy are always present (structural).
        for beat in plan["beats"]:
            self.assertIn("argument_chain", beat)
            self.assertIn("evidence_policy", beat)
            self.assertIn("customer_specificity_level", beat)
            # decision_intent may be empty string when no judgments.
            self.assertNotIn("decision_intent", beat)
            # workspace_refs absent when no archetypes.
            self.assertNotIn("workspace_refs", beat)
            # claim_ids absent when no claim_graph.
            self.assertNotIn("claim_ids", beat)

    # ------------------------------------------------------------------ #
    # Judgments integration
    # ------------------------------------------------------------------ #

    def test_judgments_add_decision_intent(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        judgments = _sample_judgments()
        plan = plan_narrative(request, judgments=judgments)

        # opener/problem beats should have decision_intent referencing business_problem.
        problem_beats = [b for b in plan["beats"] if b["role"] in ("opener", "problem")]
        self.assertTrue(len(problem_beats) > 0)
        for beat in problem_beats:
            self.assertIn("decision_intent", beat)
            self.assertIn("全渠道库存不透明", beat["decision_intent"])

        # solution/architecture beats should reference solution_approach.
        solution_beats = [b for b in plan["beats"] if b["role"] in ("solution", "architecture")]
        self.assertTrue(len(solution_beats) > 0)
        for beat in solution_beats:
            self.assertIn("decision_intent", beat)
            self.assertIn("统一库存中台", beat["decision_intent"])

    def test_judgments_enrich_brief(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        judgments = _sample_judgments()
        plan = plan_narrative(request, judgments=judgments)

        problem_beat = next(b for b in plan["beats"] if b["role"] == "problem")
        self.assertIn("判断依据", problem_beat["brief"])

    # ------------------------------------------------------------------ #
    # Claim graph integration
    # ------------------------------------------------------------------ #

    def test_claim_graph_associates_claims_to_beats(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        claim_graph = _sample_claim_graph()
        plan = plan_narrative(request, claim_graph=claim_graph)

        # beat_02_problem should have claim_01.
        problem_beat = next((b for b in plan["beats"] if b["beat_id"] == "beat_02_problem"), None)
        self.assertIsNotNone(problem_beat)
        self.assertIn("claim_ids", problem_beat)
        self.assertIn("claim_01", problem_beat["claim_ids"])

        # beat_11_roi should have claim_02.
        roi_beat = next((b for b in plan["beats"] if b["beat_id"] == "beat_11_roi"), None)
        self.assertIsNotNone(roi_beat)
        self.assertIn("claim_ids", roi_beat)
        self.assertIn("claim_02", roi_beat["claim_ids"])

    def test_claim_graph_sets_evidence_policy(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        claim_graph = _sample_claim_graph()
        plan = plan_narrative(request, claim_graph=claim_graph)

        for beat in plan["beats"]:
            policy = beat["evidence_policy"]
            self.assertIsInstance(policy["required"], bool)
            self.assertIsInstance(policy["allowed_evidence_types"], list)
            self.assertIn(policy["missing_evidence_action"], ("manual_placeholder", "generate"))

    # ------------------------------------------------------------------ #
    # Workspace archetypes
    # ------------------------------------------------------------------ #

    def test_workspace_archetypes_written_to_beats(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        archetypes = _sample_workspace_archetypes()
        plan = plan_narrative(request, workspace_archetypes=archetypes)

        # Opener beat should have archetype ref from list.
        opener = next(b for b in plan["beats"] if b["role"] == "opener")
        self.assertIn("workspace_refs", opener)
        self.assertIn("archetype_opener_standard", opener["workspace_refs"])

        # Problem beat should have direct role-keyed ref.
        problem = next(b for b in plan["beats"] if b["role"] == "problem")
        self.assertIn("workspace_refs", problem)
        self.assertIn("archetype_problem_pain_point", problem["workspace_refs"])

        # Solution beat should have list refs.
        solution = next(b for b in plan["beats"] if b["role"] == "solution")
        self.assertIn("workspace_refs", solution)
        self.assertIn("archetype_solution_overview", solution["workspace_refs"])

    # ------------------------------------------------------------------ #
    # Argument chain & specificity always present
    # ------------------------------------------------------------------ #

    def test_argument_chain_present_for_all_roles(self) -> None:
        request = build_request(brief="通用方案", target_pages="auto")
        plan = plan_narrative(request)
        for beat in plan["beats"]:
            self.assertIsInstance(beat["argument_chain"], list)
            self.assertGreaterEqual(len(beat["argument_chain"]), 1)

    def test_customer_specificity_levels(self) -> None:
        request = build_request(brief="零售方案", industry="retail", target_pages="auto")
        plan = plan_narrative(request)
        valid_levels = {"generic", "industry_specific", "client_specific"}
        for beat in plan["beats"]:
            self.assertIn(beat["customer_specificity_level"], valid_levels)

        # case/roi should be client_specific.
        case_beats = [b for b in plan["beats"] if b["role"] == "case"]
        for b in case_beats:
            self.assertEqual(b["customer_specificity_level"], "client_specific")

    def test_required_modules_status_is_exposed(self) -> None:
        request = build_request(brief="企业级解决方案", industry="enterprise", target_pages="auto")
        plan = plan_narrative(request)

        self.assertIn("coverage_matrix", plan)
        self.assertIn("required_modules_status", plan)
        self.assertIn("missing_modules", plan)
        self.assertGreaterEqual(len(plan["required_modules_status"]), 10)
        self.assertFalse(plan["missing_modules"])

    def test_small_page_budget_surfaces_missing_modules(self) -> None:
        request = build_request(brief="超短版方案", industry="enterprise", target_pages="3")
        plan = plan_narrative(request)

        self.assertTrue(plan["missing_modules"])
        labels = {item["label"] for item in plan["required_modules_status"] if item["status"] == "missing"}
        self.assertIn("平台规划/架构", labels)
        self.assertIn("案例/证据", labels)


if __name__ == "__main__":
    unittest.main()
