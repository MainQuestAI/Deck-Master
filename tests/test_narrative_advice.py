"""Tests for Package C — Narrative Advisory Contract."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.advisory.narrative import (
    RESULT_SCHEMA_VERSION,
    NarrativeAdviceError,
    apply_narrative_advice,
    import_narrative_advice,
    prepare_narrative_advice_task,
    validate_narrative_advice,
)
from scripts.runtime.run_state import create_run, read_json, write_json


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "NarrTest"}, run_id="narr-test")
    # Create required artifacts.
    write_json(run_dir / "deck_brief.json", {
        "run_id": "narr-test", "objective": "Test deck", "audience": "client",
    })
    write_json(run_dir / "claim_map.json", {
        "run_id": "narr-test", "claims": [
            {"claim_id": "claim_01", "claim": "客户需要统一运营闭环"},
        ],
    })
    write_json(run_dir / "page_tasks.json", {
        "tasks": [
            {
                "beat_id": "beat_001",
                "planning": {
                    "decision_intent": "reuse",
                    "core_claim": "现有系统已够用",
                    "evidence_need": [],
                },
            },
            {
                "beat_id": "beat_004",
                "planning": {
                    "decision_intent": "generate",
                    "core_claim": "库存可视化价值",
                    "evidence_need": [],
                },
            },
        ]
    })
    write_json(run_dir / "claim_evidence_graph.json", {
        "schema_version": "deck_claim_evidence_graph.v1",
        "run_id": "narr-test",
        "claims": [],
        "evidence": [],
        "gaps": [],
    })
    return run_dir


def _valid_advice(**overrides) -> dict:
    base = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_id": "narr-test",
        "advisor": "codex",
        "created_at": "2026-06-12T00:00:00Z",
        "core_thesis_rewrite": "客户缺少跨渠道运营闭环。",
        "business_tension": "增长依赖多渠道触达，但运营数据分散。",
        "objection_map": [
            {
                "objection": "客户认为现有系统够用",
                "response_strategy": "用数据割裂证明统一运营中台必要性。",
                "evidence_needed": ["渠道数据割裂截图"],
            }
        ],
        "page_recommendations": [
            {
                "beat_id": "beat_004",
                "action": "strengthen_claim",
                "reason": "页面只讲能力，没有证明业务价值。",
                "suggested_core_claim": "库存可视化提升履约效率。",
                "evidence_needed": ["履约时效", "缺货率"],
            }
        ],
        "deck_level_risks": [
            {
                "risk_id": "risk_001",
                "severity": "P1",
                "message": "ROI 页面缺少客户指标。",
            }
        ],
    }
    base.update(overrides)
    return base


class NarrativeAdviceValidationTest(unittest.TestCase):

    def test_valid_advice(self) -> None:
        result = validate_narrative_advice(_valid_advice())
        self.assertTrue(result["valid"], result.get("errors"))

    def test_missing_schema_version(self) -> None:
        adv = _valid_advice()
        del adv["schema_version"]
        result = validate_narrative_advice(adv)
        self.assertFalse(result["valid"])

    def test_wrong_schema_version(self) -> None:
        result = validate_narrative_advice(_valid_advice(schema_version="wrong.v1"))
        self.assertFalse(result["valid"])

    def test_missing_run_id(self) -> None:
        adv = _valid_advice()
        del adv["run_id"]
        result = validate_narrative_advice(adv)
        self.assertFalse(result["valid"])

    def test_missing_advisor(self) -> None:
        adv = _valid_advice()
        del adv["advisor"]
        result = validate_narrative_advice(adv)
        self.assertFalse(result["valid"])

    def test_invalid_page_action(self) -> None:
        adv = _valid_advice()
        adv["page_recommendations"] = [
            {"beat_id": "beat_001", "action": "invalid_action"}
        ]
        result = validate_narrative_advice(adv)
        self.assertFalse(result["valid"])
        self.assertIn("invalid_action", " ".join(result["errors"]))

    def test_invalid_risk_severity(self) -> None:
        adv = _valid_advice()
        adv["deck_level_risks"] = [
            {"risk_id": "risk_x", "severity": "P9", "message": "test"}
        ]
        result = validate_narrative_advice(adv)
        self.assertFalse(result["valid"])

    def test_not_an_object(self) -> None:
        result = validate_narrative_advice([])  # type: ignore[arg-type]
        self.assertFalse(result["valid"])


class NarrativeAdviceImportTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_narr_test_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_valid_advice(self) -> None:
        result = import_narrative_advice(self.run_dir, _valid_advice())
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["advisor"], "codex")
        # Result file should exist.
        result_path = self.run_dir / "advisor_results" / "narrative_advice.json"
        self.assertTrue(result_path.exists())

    def test_import_invalid_advice_raises(self) -> None:
        with self.assertRaises(NarrativeAdviceError):
            import_narrative_advice(self.run_dir, {"schema_version": "wrong"})

    def test_import_rejects_run_id_mismatch(self) -> None:
        with self.assertRaises(NarrativeAdviceError) as ctx:
            import_narrative_advice(self.run_dir, _valid_advice(run_id="other-run"))
        self.assertIn("run_id mismatch", str(ctx.exception))
        self.assertFalse((self.run_dir / "advisor_results" / "narrative_advice.json").exists())

    def test_event_written_after_import(self) -> None:
        from scripts.runtime.events import read_events
        import_narrative_advice(self.run_dir, _valid_advice())
        events = read_events(self.run_dir)
        narr_events = [e for e in events if e.get("step") == "narrative_advice.imported"]
        self.assertTrue(len(narr_events) >= 1)


class NarrativeAdviceApplyTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_narr_apply_")
        self.run_dir = _setup_run(Path(self._tmp))
        # Import advice first.
        import_narrative_advice(self.run_dir, _valid_advice())

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_dry_run_creates_diff_only(self) -> None:
        adv = _valid_advice()
        result = apply_narrative_advice(self.run_dir, adv, dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        # Diff should exist.
        diff_path = self.run_dir / "advisor_results" / "narrative_advice_diff.json"
        self.assertTrue(diff_path.exists())
        # page_tasks should be unchanged.
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        beat_004 = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_004")
        self.assertEqual(beat_004["planning"]["core_claim"], "库存可视化价值")

    def test_apply_rejects_run_id_mismatch(self) -> None:
        with self.assertRaises(NarrativeAdviceError) as ctx:
            apply_narrative_advice(self.run_dir, _valid_advice(run_id="other-run"))
        self.assertIn("run_id mismatch", str(ctx.exception))
        diff_path = self.run_dir / "advisor_results" / "narrative_advice_diff.json"
        self.assertFalse(diff_path.exists())

    def test_apply_updates_page_tasks(self) -> None:
        adv = _valid_advice()
        result = apply_narrative_advice(self.run_dir, adv)
        self.assertEqual(result["status"], "applied")
        # Check beat_004 was updated.
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        beat_004 = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_004")
        self.assertEqual(beat_004["planning"]["core_claim"], "库存可视化提升履约效率。")
        self.assertEqual(beat_004["planning"]["decision_intent"], "strengthen_claim")
        self.assertIn("履约时效", beat_004["planning"]["evidence_need"])

    def test_apply_writes_narrative_gate(self) -> None:
        adv = _valid_advice()
        apply_narrative_advice(self.run_dir, adv)
        gate_path = self.run_dir / "quality_reports" / "external_narrative_gate.json"
        self.assertTrue(gate_path.exists())
        gate = read_json(gate_path)
        self.assertEqual(gate["gate"], "external_narrative")
        self.assertEqual(gate["summary"]["p1_count"], 1)

    def test_apply_adds_gaps_to_claim_graph(self) -> None:
        adv = _valid_advice()
        apply_narrative_advice(self.run_dir, adv)
        graph = read_json(self.run_dir / "claim_evidence_graph.json")
        narrative_gaps = [g for g in graph["gaps"] if g.get("source") == "narrative_advice"]
        self.assertEqual(len(narrative_gaps), 1)
        self.assertEqual(narrative_gaps[0]["severity"], "P1")

    def test_apply_section_filter(self) -> None:
        adv = _valid_advice()
        # Only apply risks, not page-recommendations.
        result = apply_narrative_advice(
            self.run_dir, adv, apply_sections=["risks"]
        )
        self.assertEqual(result["status"], "applied")
        # beat_004 should be unchanged.
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        beat_004 = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_004")
        self.assertEqual(beat_004["planning"]["core_claim"], "库存可视化价值")
        # But narrative gate should be written.
        gate_path = self.run_dir / "quality_reports" / "external_narrative_gate.json"
        self.assertTrue(gate_path.exists())


class NarrativeAdviceTaskTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_narr_task_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_prepare_task(self) -> None:
        result = prepare_narrative_advice_task(self.run_dir)
        self.assertEqual(result["status"], "prepared")
        task_path = self.run_dir / "advisor_tasks" / "narrative_advice_task.json"
        self.assertTrue(task_path.exists())
        task = read_json(task_path)
        self.assertEqual(task["schema_version"], "deck_narrative_advice_task.v1")


if __name__ == "__main__":
    unittest.main()
