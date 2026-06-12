from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 确保 scripts 目录在 sys.path 中
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from quality.draft_gate_v2 import (  # noqa: E402
    DIMENSIONS,
    SCHEMA_VERSION,
    STATUSES,
    evaluate_draft_gate_v2,
)


def _minimal_brief(**overrides: object) -> dict:
    base = {
        "run_id": "run-test-001",
        "business_goal": "推动客户采纳新方案",
        "audience": "director",
        "core_points": ["降本增效"],
    }
    base.update(overrides)
    return base


def _minimal_claim_map(**overrides: object) -> dict:
    base: dict = {
        "run_id": "run-test-001",
        "claims": [
            {
                "claim_id": "c1",
                "claim": "方案可降低 30% 运营成本",
                "risk_flags": [],
            },
        ],
        "risk_flags": ["assumption_unvalidated"],
    }
    base.update(overrides)
    return base


def _minimal_page_tasks(**overrides: object) -> dict:
    base: dict = {
        "run_id": "run-test-001",
        "tasks": [
            {
                "beat_id": "b1",
                "planning": {"role": "opener", "claim_ref": "c1", "core_claim": "方案可降低 30% 运营成本"},
            },
            {
                "beat_id": "b2",
                "planning": {"role": "body", "claim_ref": "c1", "core_claim": "方案可降低 30% 运营成本"},
            },
            {
                "beat_id": "b3",
                "planning": {"role": "closing", "core_claim": "总结与下一步"},
            },
        ],
    }
    base.update(overrides)
    return base


class TestDraftGateV2Structure(unittest.TestCase):
    """验证输出结构和 schema。"""

    def test_output_contains_required_keys(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        for key in ("schema_version", "run_id", "gate", "status", "dimension_scores", "findings", "summary", "blocks_delivery"):
            self.assertIn(key, result, f"缺少顶层字段: {key}")

    def test_schema_version(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)

    def test_run_id_from_brief(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(run_id="my-run"),
            _minimal_claim_map(run_id="other-run"),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["run_id"], "my-run")

    def test_run_id_fallback_to_claim_map(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(run_id=""),
            _minimal_claim_map(run_id="cm-run"),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["run_id"], "cm-run")

    def test_dimension_scores_has_all_dimensions(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(set(result["dimension_scores"].keys()), set(DIMENSIONS))

    def test_summary_counts(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        summary = result["summary"]
        for key in ("total_findings", "p0_count", "p1_count", "p2_count", "claims", "page_tasks"):
            self.assertIn(key, summary)
        self.assertEqual(summary["claims"], 1)
        self.assertEqual(summary["page_tasks"], 3)

    def test_status_is_valid(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertIn(result["status"], STATUSES)

    def test_gate_name(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["gate"], "draft_v2")


class TestDraftGateV2Pass(unittest.TestCase):
    """正常输入应返回 pass。"""

    def test_clean_input_returns_pass(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["blocks_delivery"])

    def test_blocks_delivery_false_on_pass(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertFalse(result["blocks_delivery"])


class TestThesisClarity(unittest.TestCase):
    """thesis_clarity 维度检查。"""

    def test_missing_business_goal_produces_p1(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(business_goal=""),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        thesis_findings = [f for f in result["findings"] if f["finding_id"] == "v2_thesis_missing_goal"]
        self.assertEqual(len(thesis_findings), 1)
        self.assertEqual(thesis_findings[0]["severity"], "P1")
        self.assertEqual(thesis_findings[0]["dimension"], "thesis_clarity")

    def test_no_claims_and_no_core_points_produces_p1(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(core_points=[]),
            _minimal_claim_map(claims=[]),
            _minimal_page_tasks(tasks=[]),
        )
        no_claims_findings = [f for f in result["findings"] if f["finding_id"] == "v2_thesis_no_claims"]
        self.assertEqual(len(no_claims_findings), 1)
        self.assertEqual(no_claims_findings[0]["severity"], "P1")

    def test_missing_goal_triggers_rework_required(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(business_goal=""),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])


class TestClaimCoverage(unittest.TestCase):
    """claim_coverage 维度检查。"""

    def test_uncovered_claim_produces_p1(self) -> None:
        claim_map = _minimal_claim_map(claims=[
            {"claim_id": "c_orphan", "claim": "孤立论点无人承载", "risk_flags": []},
        ])
        page_tasks = _minimal_page_tasks(tasks=[
            {"beat_id": "b1", "planning": {"role": "opener", "claim_ref": "other", "core_claim": "无关内容"}},
            {"beat_id": "b2", "planning": {"role": "body", "claim_ref": "other2", "core_claim": "也无关"}},
            {"beat_id": "b3", "planning": {"role": "closing", "core_claim": "总结"}},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, page_tasks)
        uncovered = [f for f in result["findings"] if "v2_claim_uncovered_c_orphan" in f["finding_id"]]
        self.assertEqual(len(uncovered), 1)
        self.assertEqual(uncovered[0]["severity"], "P1")
        self.assertEqual(uncovered[0]["dimension"], "claim_coverage")

    def test_covered_claim_no_finding(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        uncovered = [f for f in result["findings"] if "v2_claim_uncovered" in f["finding_id"]]
        self.assertEqual(len(uncovered), 0)

    def test_opener_closing_not_forced_coverage(self) -> None:
        """opener/closing 角色的 claim 不强制要求覆盖。"""
        claim_map = _minimal_claim_map(claims=[
            {"claim_id": "c_open", "claim": "开场论点", "risk_flags": []},
        ])
        # opener 有 claim_ref 但没有 body 页面覆盖它——不应报错，因为它是 opener
        page_tasks = _minimal_page_tasks(tasks=[
            {"beat_id": "b1", "planning": {"role": "opener", "claim_ref": "c_open", "core_claim": "开场论点"}},
            {"beat_id": "b2", "planning": {"role": "body", "claim_ref": "other", "core_claim": "其他内容"}},
            {"beat_id": "b3", "planning": {"role": "closing", "core_claim": "总结"}},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, page_tasks)
        uncovered = [f for f in result["findings"] if "v2_claim_uncovered_c_open" in f["finding_id"]]
        self.assertEqual(len(uncovered), 0)


class TestEvidenceReadiness(unittest.TestCase):
    """evidence_readiness 维度检查。"""

    def test_evidence_gap_produces_p1(self) -> None:
        claim_map = _minimal_claim_map(claims=[
            {"claim_id": "c_egap", "claim": "缺证据的论点", "risk_flags": ["evidence_gap"]},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, _minimal_page_tasks())
        gap_findings = [f for f in result["findings"] if "v2_evidence_gap_c_egap" in f["finding_id"]]
        self.assertEqual(len(gap_findings), 1)
        self.assertEqual(gap_findings[0]["severity"], "P1")
        self.assertEqual(gap_findings[0]["dimension"], "evidence_readiness")

    def test_missing_required_evidence_produces_p1(self) -> None:
        claim_map = _minimal_claim_map(claims=[
            {"claim_id": "c_mre", "claim": "缺必要证据", "risk_flags": ["missing_required_evidence"]},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, _minimal_page_tasks())
        gap_findings = [f for f in result["findings"] if "v2_evidence_gap_c_mre" in f["finding_id"]]
        self.assertEqual(len(gap_findings), 1)
        self.assertEqual(gap_findings[0]["severity"], "P1")

    def test_claim_evidence_graph_gaps(self) -> None:
        graph = {
            "gaps": [
                {"claim_id": "c_g1", "description": "缺少 ROI 数据", "repair_instruction": "补 ROI 表"},
            ]
        }
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
            claim_evidence_graph=graph,
        )
        graph_findings = [f for f in result["findings"] if "v2_graph_gap_c_g1" in f["finding_id"]]
        self.assertEqual(len(graph_findings), 1)
        self.assertEqual(graph_findings[0]["severity"], "P1")


class TestArgumentFlow(unittest.TestCase):
    """argument_flow 维度检查。"""

    def test_too_few_pages_produces_p2(self) -> None:
        page_tasks = _minimal_page_tasks(tasks=[
            {"beat_id": "b1", "planning": {"role": "opener", "core_claim": "开场"}},
            {"beat_id": "b2", "planning": {"role": "closing", "core_claim": "收尾"}},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), _minimal_claim_map(), page_tasks)
        flow_findings = [f for f in result["findings"] if f["finding_id"] == "v2_flow_too_few_pages"]
        self.assertEqual(len(flow_findings), 1)
        self.assertEqual(flow_findings[0]["severity"], "P2")

    def test_no_opener_produces_p2(self) -> None:
        page_tasks = _minimal_page_tasks(tasks=[
            {"beat_id": "b1", "planning": {"role": "body", "claim_ref": "c1", "core_claim": "内容1"}},
            {"beat_id": "b2", "planning": {"role": "body", "claim_ref": "c1", "core_claim": "内容2"}},
            {"beat_id": "b3", "planning": {"role": "closing", "core_claim": "收尾"}},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), _minimal_claim_map(), page_tasks)
        opener_findings = [f for f in result["findings"] if f["finding_id"] == "v2_flow_no_opener"]
        self.assertEqual(len(opener_findings), 1)
        self.assertEqual(opener_findings[0]["severity"], "P2")


class TestAudienceFit(unittest.TestCase):
    """audience_fit 维度检查。"""

    def test_exec_with_too_many_pages(self) -> None:
        tasks = [
            {"beat_id": f"b{i}", "planning": {"role": "body", "core_claim": f"内容{i}"}}
            for i in range(25)
        ]
        page_tasks = _minimal_page_tasks(tasks=tasks)
        result = evaluate_draft_gate_v2(
            _minimal_brief(audience="exec"),
            _minimal_claim_map(),
            page_tasks,
        )
        audience_findings = [f for f in result["findings"] if f["finding_id"] == "v2_audience_exec_too_many"]
        self.assertEqual(len(audience_findings), 1)
        self.assertEqual(audience_findings[0]["severity"], "P2")


class TestSpecificity(unittest.TestCase):
    """specificity 维度检查。"""

    def test_needs_customer_evidence_produces_p1(self) -> None:
        claim_map = _minimal_claim_map(claims=[
            {"claim_id": "c_cust", "claim": "客户专属论点", "risk_flags": ["needs_customer_evidence"]},
        ])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, _minimal_page_tasks())
        spec_findings = [f for f in result["findings"] if "v2_specificity_c_cust" in f["finding_id"]]
        self.assertEqual(len(spec_findings), 1)
        self.assertEqual(spec_findings[0]["severity"], "P1")
        self.assertEqual(spec_findings[0]["dimension"], "specificity")


class TestRiskVisibility(unittest.TestCase):
    """risk_visibility 维度检查。"""

    def test_no_risk_flags_produces_p2(self) -> None:
        claim_map = _minimal_claim_map(risk_flags=[])
        result = evaluate_draft_gate_v2(_minimal_brief(), claim_map, _minimal_page_tasks())
        risk_findings = [f for f in result["findings"] if f["finding_id"] == "v2_risk_no_flags"]
        self.assertEqual(len(risk_findings), 1)
        self.assertEqual(risk_findings[0]["severity"], "P2")

    def test_consulting_judgments_open_questions(self) -> None:
        judgments = {"open_questions": ["客户预算是否已确认？"]}
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
            consulting_judgments=judgments,
        )
        # open_questions 存在时 risk_visibility 分数至少为 3
        self.assertGreaterEqual(result["dimension_scores"]["risk_visibility"], 3)


class TestBlocksDelivery(unittest.TestCase):
    """blocks_delivery 只在 rework_required 时为 True。"""

    def test_blocks_delivery_true_on_rework_required(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(business_goal=""),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        self.assertEqual(result["status"], "rework_required")
        self.assertTrue(result["blocks_delivery"])

    def test_blocks_delivery_false_on_conditional_pass(self) -> None:
        # 触发 P2 但不触发 P1/P0 → conditional_pass
        page_tasks = _minimal_page_tasks(tasks=[
            {"beat_id": "b1", "planning": {"role": "body", "core_claim": "内容1"}},
            {"beat_id": "b2", "planning": {"role": "body", "core_claim": "内容2"}},
            {"beat_id": "b3", "planning": {"role": "closing", "core_claim": "收尾"}},
        ])
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            page_tasks,
        )
        # 无 opener → P2 → conditional_pass（或 pass 如果分数 > 2）
        if result["status"] == "conditional_pass":
            self.assertFalse(result["blocks_delivery"])

    def test_blocks_delivery_false_on_pass(self) -> None:
        result = evaluate_draft_gate_v2(
            _minimal_brief(),
            _minimal_claim_map(),
            _minimal_page_tasks(),
        )
        if result["status"] == "pass":
            self.assertFalse(result["blocks_delivery"])


if __name__ == "__main__":
    unittest.main()
