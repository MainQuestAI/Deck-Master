from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from context_intake.local_sources import build_context_manifest
from conversation.brief_compiler import compile_deck_brief
from conversation.session_builder import build_conversation_session
from planning.brief_intake import build_request
from planning.claim_map import build_claim_map


class ContextConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def write_context(self, text: str = "会议逐字稿：客户关注全渠道库存可视化，需要案例和截图证明。") -> Path:
        path = self.temp_dir / "meeting_transcript.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_context_manifest_records_local_source(self) -> None:
        manifest = build_context_manifest([self.write_context()], workspace="/tmp/workspace", run_id="run-1")

        self.assertEqual("deck_context_manifest.v1", manifest["schema_version"])
        self.assertEqual("runtime_reference", manifest["strategy"])
        self.assertEqual(1, len(manifest["sources"]))
        self.assertEqual("meeting_transcript", manifest["sources"][0]["kind"])
        self.assertIn("全渠道", manifest["summary"])

    def test_conversation_compiles_deck_brief(self) -> None:
        manifest = build_context_manifest([self.write_context()])
        request = build_request(brief=manifest["summary"], industry="retail")
        request["run_id"] = "run-1"
        conversation = build_conversation_session(request, manifest)
        brief = compile_deck_brief(request, manifest, conversation)

        self.assertEqual("run-1", brief["run_id"])
        self.assertEqual("client", brief["audience"])
        self.assertTrue(brief["core_points"])
        self.assertIn("source_refs", brief)

    def test_claim_map_marks_evidence_gap_without_evidence_source(self) -> None:
        context_path = self.write_context("客户希望做一份增长方案。")
        manifest = build_context_manifest([context_path])
        request = build_request(brief="客户增长方案")
        conversation = build_conversation_session(request, manifest)
        brief = compile_deck_brief(request, manifest, conversation)
        claim_map = build_claim_map(brief, manifest)

        self.assertIn("evidence_gap", claim_map["risk_flags"])


if __name__ == "__main__":
    unittest.main()
