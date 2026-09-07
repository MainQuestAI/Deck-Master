"""SC-1 PR-04 A5 tests: question authority, material self-answer, F03.

Acceptance mapping:
- W-01: a question whose answer already exists in the registered material
  (tail constraint candidates) is marked material_answer_available instead of
  blindly re-asked.
- W-05: user-reserved categories (delivery approval) reject Agent-recorded
  answers; ordinary questions can be answered by the Agent.
- F03: the agent task index distinguishes agent-executable waiting states
  from real stop-and-report conditions.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from workflow.questions import USER_RESERVED_CATEGORIES, QuestionResolver  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class MaterialAnswerTests(unittest.TestCase):
    def test_tail_constraint_answers_material_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "schema_version": "deck_context_manifest.v1",
                "tail_constraint_candidates": [
                    {
                        "source_id": "abc123",
                        "text": "补充约束：方案必须在 9 月 30 日前完成合规审批，不得使用未授权数据。",
                        "region": "tail",
                    }
                ],
                "sources": [],
            }
            (root / "context_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            resolver = QuestionResolver()
            question = {"question_id": "brief.non_negotiable_constraints", "category": "constraint", "prompt": "合规审批与数据授权有哪些硬性约束？"}
            candidate = resolver.material_answer_candidates(root, question)
            self.assertTrue(candidate["answer"], "material-contained answer must be surfaced")
            self.assertEqual("tail", candidate.get("region"))
            self.assertTrue(candidate["evidence_refs"])

    def test_no_manifest_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolver = QuestionResolver()
            candidate = resolver.material_answer_candidates(Path(tmp), {"prompt": "约束是什么"})
            self.assertEqual("", candidate["answer"])


class AnswerAuthorityTests(unittest.TestCase):
    def test_agent_cannot_fill_delivery_approval(self) -> None:
        resolver = QuestionResolver()
        question = {"question_id": "delivery.final_approval", "category": "delivery", "prompt": "批准导出？"}
        with self.assertRaises(ValueError):
            resolver.validate_answer_authority(question, "agent")
        # A user recording the same answer is fine.
        resolver.validate_answer_authority(question, "user")

    def test_agent_can_answer_ordinary_questions(self) -> None:
        resolver = QuestionResolver()
        question = {"question_id": "brief.evidence_gap", "category": "evidence", "prompt": "证据缺口如何补？"}
        resolver.validate_answer_authority(question, "agent")

    def test_reserved_categories_constant(self) -> None:
        self.assertIn("delivery", USER_RESERVED_CATEGORIES)


class F03DocSemanticsTests(unittest.TestCase):
    def test_task_index_distinguishes_agent_executable_waiting(self) -> None:
        text = (ROOT / "docs" / "agent-task-index.md").read_text(encoding="utf-8")
        self.assertIn("awaiting_agent_execution", text)
        self.assertIn("do not stop", text)


if __name__ == "__main__":
    unittest.main()
