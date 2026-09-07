"""SC-1 PR-03 tests: full material reading, research tasks, brief/judgment fixes.

Acceptance mapping (docs/specs/sc1-solution-core-independence/acceptance/cases.json):
- I-01: a constraint at the very end of the material reaches constraint
  candidates (F05 — head truncation must not hide tail constraints).
- I-02: a partially unread source is registered as unread, never "full".
- I-05: non-text sources produce host extraction handoff tasks.
- R-01/R-02: research task construction with redaction guard and budget caps.
- R-03/R-04: executed research requires a real query log; inconclusive is a
  first-class terminal state; results merge back into the same manifest.
- S-02: claims with only unreviewed references are flagged, not treated as
  supported (F02).
- S-01: production brief consumes the Agent's structured extraction and is
  labelled; rule-based compilation is labelled fixture_rules.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from context_intake import local_sources  # noqa: E402
from context_intake.research_task import (  # noqa: E402
    build_research_task,
    ingest_research_result,
    validate_research_result,
)
from conversation.brief_compiler import compile_deck_brief  # noqa: E402
from narrative.judgment_builder import build_judgments  # noqa: E402
from planning.claim_map import build_claim_map  # noqa: E402


def _write_material(tmp: Path, body: str) -> Path:
    path = tmp / "material.md"
    path.write_text(body, encoding="utf-8")
    return path


class LocalSourceReadingTests(unittest.TestCase):
    def test_tail_constraint_is_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = "第一部分：项目背景介绍。\n" * 40 + "补充约束：方案必须在 9 月 30 日前完成合规审批，不得使用未授权数据。"
            path = _write_material(Path(tmp), body)
            record = local_sources.source_record(path)
            candidates = record["constraint_candidates"]
            self.assertTrue(candidates, "constraint candidates must exist")
            tail_texts = [item["text"] for item in candidates if item["region"] == "tail"]
            self.assertTrue(any("9 月 30 日" in text for text in tail_texts))

    def test_summary_is_navigation_only_and_not_head_truncation_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = "开头内容。\n" * 50
            path = _write_material(Path(tmp), body)
            record = local_sources.source_record(path)
            self.assertEqual("navigation_only", record["summary_role"])

    def test_unreadable_host_source_registered_as_unread_with_extract_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4 fake")
            manifest = local_sources.build_context_manifest([path], run_id="run-i05")
            self.assertEqual(0, manifest["reading_coverage"]["sources_full"])
            unread = manifest["reading_coverage"]["unread_sources"]
            self.assertEqual(1, len(unread))
            self.assertTrue(manifest["host_extract_tasks"])
            self.assertEqual("pdf", manifest["host_extract_tasks"][0]["media_type"])

    def test_text_source_is_registered_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_material(Path(tmp), "完整可读文本。")
            record = local_sources.source_record(path)
            self.assertEqual("full", record["reading"]["coverage"])
            self.assertEqual([], record["reading"]["unread_ranges"])
            self.assertEqual([], record["reading"]["failures"])


class ResearchTaskTests(unittest.TestCase):
    def test_build_task_validates_fields_and_budget(self) -> None:
        task = build_research_task(
            question="客户所在行业的合规审批周期基准是多少？",
            affects=["claim_02", "solution_model.compliance_stage"],
            source_priority=["official_regulator", "industry_association"],
            public_query_context=["2026 医疗器械合规审批 周期 基准"],
        )
        self.assertEqual("deck_research_task.v1", task["schema_version"])
        self.assertEqual(2, task["budget"]["max_rounds"])
        with self.assertRaises(ValueError):
            build_research_task(question="", affects=["claim_01"])
        with self.assertRaises(ValueError):
            build_research_task(question="q", affects=[])
        with self.assertRaises(ValueError):
            build_research_task(question="q", affects=["claim_01"], max_rounds=5)

    def test_query_context_redaction_guard(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_research_task(
                question="q",
                affects=["claim_01"],
                public_query_context=["/Users/alice/private/客户材料.docx 采购流程"],
            )
        self.assertIn("unredacted", str(ctx.exception))

    def test_executed_requires_query_log_and_sources(self) -> None:
        errors = validate_research_result({"status": "executed", "task_id": "t1"})
        self.assertTrue(any("query/reading log" in item for item in errors))
        ok = validate_research_result(
            {
                "status": "executed",
                "task_id": "t1",
                "query_log": [{"query": "q", "round": 1}],
                "sources": [{"title": "regulator page", "url": "https://example.gov/a", "excerpt": "基准为 8-12 周"}],
                "result_summary": "found",
            }
        )
        self.assertEqual([], ok)
        self.assertEqual([], validate_research_result({"status": "inconclusive", "task_id": "t2", "open_questions": ["x"]}))
        self.assertEqual([], validate_research_result({"status": "capability_unavailable", "task_id": "t3"}))
        with self.assertRaises(ValueError):
            ingest_research_result({"sources": []}, {"status": "executed", "task_id": "t1"})

    def test_results_merge_into_same_manifest_with_provenance(self) -> None:
        manifest = {
            "schema_version": "deck_context_manifest.v1",
            "sources": [{"source_id": "src1", "name": "local.md"}],
        }
        merged = ingest_research_result(
            manifest,
            {
                "status": "executed",
                "task_id": "task-r1",
                "question": "q",
                "result_summary": "8-12 周",
                "query_log": [{"query": "q", "round": 1}],
                "sources": [
                    {
                        "source_id": "web1",
                        "title": "监管指引",
                        "url": "https://example.gov/guide",
                        "accessed_at": "2026-09-07T00:00:00+00:00",
                        "excerpt": "审批周期基准 8-12 周",
                        "applicability_bounds": ["仅适用于 A 类设备"],
                    }
                ],
                "counter_evidence": ["某 2024 报告口径不同，需同口径比较"],
                "open_questions": [],
            },
        )
        self.assertEqual(2, len(merged["sources"]))
        research_source = merged["sources"][1]
        self.assertEqual("research", research_source["kind"])
        self.assertEqual("externally_verified_candidate", research_source["provenance"]["fact_kind"])
        self.assertEqual("task-r1", merged["research_meta"][0]["task_id"])
        self.assertEqual("executed", merged["research_meta"][0]["status"])


class BriefCompilerTests(unittest.TestCase):
    def _request(self) -> dict:
        return {"run_id": "run-s01", "project_name": "P", "business_goal": "提升续费率", "must_cover_topics": []}

    def test_agent_extract_is_labeled_and_consumed(self) -> None:
        extract = {
            "goal_decision": "以客户健康度分层驱动续费",
            "audience": "客户高管",
            "current_state": "续费依赖个人跟进",
            "key_problems": ["续费预测缺失", "健康度口径不一致"],
            "constraints": ["Q4 内上线"],
            "non_goals": ["不做新 CRM"],
            "acceptance": ["续费率可按季度观测"],
        }
        brief = compile_deck_brief(self._request(), {"sources": []}, {}, agent_extract=extract)
        self.assertEqual("agent_extract", brief["brief_mode"])
        self.assertEqual("以客户健康度分层驱动续费", brief["business_goal"])
        self.assertEqual(2, len(brief["core_points"]))
        self.assertEqual(["Q4 内上线"], brief["constraints"])

    def test_rule_path_is_labeled_fixture_rules(self) -> None:
        brief = compile_deck_brief(self._request(), {"sources": [], "summary": ""}, {})
        self.assertEqual("fixture_rules", brief["brief_mode"])


class JudgmentEvidenceTests(unittest.TestCase):
    def test_unreviewed_references_are_not_support(self) -> None:
        sources = [{"source_id": "abc123"}, {"source_id": "def456"}]
        claims = [
            {"claim_id": "c1", "claim": "x", "risk_flags": [], "evidence_refs": ["abc123"]},
            {"claim_id": "c2", "claim": "y", "risk_flags": [], "evidence_refs": ["def456"]},
        ]
        result = build_judgments({"run_id": "r"}, {"core_points": []}, {"claims": claims}, context_manifest={"sources": sources})
        evidence = [j for j in result["judgments"] if j["topic"] == "evidence_sufficiency"][0]
        self.assertIn("evidence_unreviewed", evidence["risk_flags"])
        self.assertIn("needs_customer_evidence", evidence["risk_flags"])

    def test_reviewed_evidence_counts_as_support(self) -> None:
        sources = [{"source_id": "abc123"}]
        claims = [
            {
                "claim_id": "c1",
                "claim": "x",
                "evidence": [{"source_id": "abc123", "evidence_status": "reviewed"}],
            }
        ]
        result = build_judgments({"run_id": "r"}, {"core_points": []}, {"claims": claims}, context_manifest={"sources": sources})
        evidence = [j for j in result["judgments"] if j["topic"] == "evidence_sufficiency"][0]
        self.assertNotIn("needs_customer_evidence", evidence["risk_flags"])
        self.assertNotIn("evidence_unreviewed", evidence["risk_flags"])

    def test_claim_map_marks_candidate_refs_unreviewed(self) -> None:
        manifest = {
            "sources": [
                {"source_id": "s1", "name": "客户会议记录.md", "summary": "会议转写摘录", "excerpt": "会议 转写"},
            ]
        }
        brief = {"business_goal": "g", "core_points": ["论点一"], "must_cover_topics": []}
        claim_map = build_claim_map(brief, manifest)
        self.assertEqual(["evidence_unreviewed"], claim_map["claims"][0]["risk_flags"])


if __name__ == "__main__":
    unittest.main()
