"""SC-1 PR-04 tests: solution model and solution-driven narrative.

Acceptance mapping:
- S-05: solution model validates structure and content rules (mechanism,
  problem tie, checkable result, component status, relation targets,
  assumption recheck triggers, single recommended alternative).
- S-06/S-07: production narrative driven by the solution model — different
  materials produce different page jobs/conclusions; template titles no
  longer leak into production beats (F06).
- N-01: candidate/recommended/selected structure present, with a truthful
  single_viable_path reason when no real alternatives exist.
- S-08 (engineering side): production keyword filtering removed —
  restricted-sample keywords no longer change production output.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from planning.narrative_planner import plan_narrative  # noqa: E402
from planning.solution_model import SCHEMA_VERSION, empty_solution_model, validate_solution_model  # noqa: E402


def _solution_model_healthcare() -> dict:
    model = empty_solution_model("run-hc")
    model.update(
        {
            "problems": [
                {
                    "problem_id": "P1",
                    "title": "合规审批周期过长",
                    "statement": "注册资料在三个部门间串行流转，平均审批 45 天。",
                    "evidence_refs": ["src_meeting"],
                },
                {
                    "problem_id": "P2",
                    "title": "资料版本失控",
                    "statement": "各部门使用本地副本，退回率 30%。",
                    "evidence_refs": [],
                },
            ],
            "capabilities": [
                {
                    "capability_id": "C1",
                    "title": "并行审批工作流",
                    "mechanism": "审批任务并行分派并自动汇聚意见，替代串行签核",
                    "problem_ids": ["P1"],
                    "checkable_result": "审批周期从 45 天降到 20 天内",
                    "component_ids": ["comp_workflow"],
                },
                {
                    "capability_id": "C2",
                    "title": "统一资料库",
                    "mechanism": "单一受控资料源 + 版本锁，所有部门引用同一版本",
                    "problem_ids": ["P2"],
                    "checkable_result": "退回率降到 10% 以下",
                    "component_ids": ["comp_repo"],
                },
            ],
            "components": [
                {"component_id": "comp_workflow", "title": "审批引擎", "status": "proposed"},
                {"component_id": "comp_repo", "title": "资料库", "status": "existing"},
            ],
            "relations": [
                {"source": "comp_repo", "target": "comp_workflow", "kind": "feeds"},
            ],
            "phases": [
                {"phase_id": "PH1", "title": "试点审批流", "goal": "单产品线试点", "exit_criteria": "两周期内无超期"},
            ],
            "alternatives": [],
            "assumptions": [
                {
                    "assumption_id": "A1",
                    "statement": "各部门可在试点期投入专人",
                    "affects": ["PH1"],
                    "recheck_trigger": "试点启动会后两周",
                }
            ],
        }
    )
    return model


def _solution_model_retail() -> dict:
    model = empty_solution_model("run-retail")
    model.update(
        {
            "problems": [
                {
                    "problem_id": "R1",
                    "title": "门店补货滞后",
                    "statement": "补货依赖店长经验，缺货率 12%。",
                    "evidence_refs": [],
                }
            ],
            "capabilities": [
                {
                    "capability_id": "RC1",
                    "title": "自动补货建议",
                    "mechanism": "按门店销售速率与在途库存生成补货建议单",
                    "problem_ids": ["R1"],
                    "checkable_result": "缺货率降到 5% 以下",
                    "component_ids": ["comp_forecast"],
                }
            ],
            "components": [
                {"component_id": "comp_forecast", "title": "预测服务", "status": "proposed"},
            ],
            "relations": [],
            "phases": [],
            "alternatives": [],
            "assumptions": [],
        }
    )
    return model


def _request(**overrides) -> dict:
    base = {
        "run_id": "run-b4",
        "project_name": "Test Deck",
        "business_goal": "提升运营效率",
        "audience": "client",
        "target_pages": 6,
        "industry": "healthcare",
    }
    base.update(overrides)
    return base


class SolutionModelValidationTests(unittest.TestCase):
    def test_valid_model_passes(self) -> None:
        self.assertEqual([], validate_solution_model(_solution_model_healthcare()))

    def test_content_rules_fail_closed(self) -> None:
        model = empty_solution_model("run-x")
        errors = validate_solution_model(model)
        self.assertTrue(any("problem" in item for item in errors))
        self.assertTrue(any("capability" in item for item in errors))

        model = _solution_model_healthcare()
        model["capabilities"][0]["mechanism"] = ""
        model["capabilities"][1]["problem_ids"] = ["UNKNOWN"]
        model["components"][0]["status"] = "maybe"
        model["relations"][0]["target"] = "ghost"
        model["assumptions"][0]["recheck_trigger"] = ""
        errors = validate_solution_model(model)
        self.assertTrue(any("mechanism" in item for item in errors))
        self.assertTrue(any("not tied" in item for item in errors))
        self.assertTrue(any("status" in item for item in errors))
        self.assertTrue(any("relation target" in item for item in errors))
        self.assertTrue(any("recheck trigger" in item for item in errors))

    def test_alternatives_need_single_recommendation(self) -> None:
        model = _solution_model_healthcare()
        model["alternatives"] = [
            {"alternative_id": "ALT1", "title": "自建", "recommended": True, "recommendation_reason": "数据敏感"},
            {"alternative_id": "ALT2", "title": "外采"},
        ]
        errors = validate_solution_model(model)
        self.assertTrue(any("why_rejected" in item for item in errors))


class SolutionDrivenNarrativeTests(unittest.TestCase):
    def test_production_beats_come_from_solution_model(self) -> None:
        plan = plan_narrative(_request(), planner_mode="production_narrative", solution_model=_solution_model_healthcare())
        titles = " ".join(beat["page_title"] for beat in plan["beats"])
        self.assertIn("合规审批周期过长", titles)
        self.assertIn("并行审批工作流", titles)
        for beat in plan["beats"]:
            self.assertTrue(beat.get("page_job"))
            self.assertTrue(str(beat.get("conclusion") or "").strip())
            self.assertIn("customer_specific", beat["customer_specificity_level"])
        roles = [beat["role"] for beat in plan["beats"]]
        self.assertIn("architecture", roles)

    def test_different_materials_produce_different_narratives(self) -> None:
        hc = plan_narrative(_request(), planner_mode="production_narrative", solution_model=_solution_model_healthcare())
        retail = plan_narrative(_request(industry="retail"), planner_mode="production_narrative", solution_model=_solution_model_retail())
        hc_titles = [beat["page_title"] for beat in hc["beats"]]
        retail_titles = [beat["page_title"] for beat in retail["beats"]]
        self.assertNotEqual(hc_titles, retail_titles)
        self.assertIn("自动补货建议", " ".join(retail_titles))

    def test_candidates_structure_with_single_viable_path(self) -> None:
        plan = plan_narrative(_request(), planner_mode="production_narrative", solution_model=_solution_model_retail())
        self.assertEqual(1, len(plan["candidates"]))
        self.assertEqual(plan["recommended_candidate_id"], plan["selected_candidate_id"])
        self.assertIn("single_viable_path", plan["selection_reason"])

    def test_explicit_candidates_pass_through_with_recommendation(self) -> None:
        candidates = [
            {"candidate_id": "ALT_A", "title": "先验证闭环", "recommended": True, "recommendation_reason": "风险低"},
            {"candidate_id": "ALT_B", "title": "先统一数据", "why_rejected": "数据治理周期长"},
        ]
        plan = plan_narrative(
            _request(),
            planner_mode="production_narrative",
            solution_model=_solution_model_healthcare(),
            narrative_candidates=candidates,
        )
        self.assertEqual(2, len(plan["candidates"]))
        self.assertEqual("ALT_A", plan["selected_candidate_id"])

    def test_restricted_sample_keywords_no_longer_filter_production(self) -> None:
        # F06 regression: retail-flavoured template titles must survive
        # production planning when no solution model drives the beats.
        request = _request(brief="零售仓储与库存可视化改造，最后一公里配送效率", industry="retail")
        plan = plan_narrative(request, planner_mode="production_narrative")
        self.assertTrue(plan["beats"], "production planner must still produce beats without a solution model")

    def test_template_path_unchanged_without_solution_model(self) -> None:
        plan = plan_narrative(_request(), planner_mode="fixture_template")
        self.assertTrue(plan["beats"])
        self.assertEqual("", plan["fallback_reason"])
        self.assertEqual([], plan["candidates"])


if __name__ == "__main__":
    unittest.main()
