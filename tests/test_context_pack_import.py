"""Tests for Package B — Agent Context Pack Contract."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is in sys.path for cross-module imports (runtime.*, etc.)
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.context_intake.context_pack import (
    SCHEMA_VERSION,
    ContextPackError,
    import_context_pack,
    validate_context_pack,
)
from scripts.runtime.run_state import create_run, read_json, CONTEXT_MANIFEST_NAME
from scripts.narrative.claim_graph import build_claim_evidence_graph


def _valid_pack(**overrides) -> dict:
    base = {
        "schema_version": SCHEMA_VERSION,
        "run_id": "test-run",
        "created_by": "codex",
        "created_at": "2026-06-12T00:00:00Z",
        "sources": [
            {
                "source_id": "src_001",
                "source_type": "customer_material",
                "origin_type": "pdf",
                "origin_path": "/tmp/customer.pdf",
                "title": "客户现状材料",
                "summary": "客户当前多渠道会员数据分散。",
                "sensitivity": "normal",
                "evidence_candidates": [
                    {
                        "evidence_id": "ev_001",
                        "evidence_type": "customer_material",
                        "claim_hint": "缺少统一会员运营闭环",
                        "quote_or_excerpt": "会员数据分散在不同渠道。",
                        "location": "page 12",
                        "publication_status": "safe_to_use",
                        "sensitivity": "normal",
                    }
                ],
            }
        ],
        "global_constraints": ["客户名称需脱敏。"],
    }
    base.update(overrides)
    return base


class ContextPackValidationTest(unittest.TestCase):

    def test_valid_pack(self) -> None:
        result = validate_context_pack(_valid_pack())
        self.assertTrue(result["valid"])

    def test_missing_schema_version(self) -> None:
        pack = _valid_pack()
        del pack["schema_version"]
        result = validate_context_pack(pack)
        self.assertFalse(result["valid"])
        self.assertIn("schema_version", " ".join(result["errors"]))

    def test_wrong_schema_version(self) -> None:
        result = validate_context_pack(_valid_pack(schema_version="wrong.v1"))
        self.assertFalse(result["valid"])

    def test_missing_run_id(self) -> None:
        pack = _valid_pack()
        del pack["run_id"]
        result = validate_context_pack(pack)
        self.assertFalse(result["valid"])

    def test_duplicate_source_id(self) -> None:
        sources = [
            {"source_id": "src_001", "source_type": "pdf"},
            {"source_id": "src_001", "source_type": "pdf"},
        ]
        result = validate_context_pack(_valid_pack(sources=sources))
        self.assertFalse(result["valid"])
        self.assertIn("Duplicate source_id", " ".join(result["errors"]))

    def test_invalid_sensitivity(self) -> None:
        sources = [{"source_id": "src_001", "source_type": "pdf", "sensitivity": "ultra"}]
        result = validate_context_pack(_valid_pack(sources=sources))
        self.assertFalse(result["valid"])

    def test_invalid_publication_status(self) -> None:
        sources = [{
            "source_id": "src_001",
            "source_type": "pdf",
            "evidence_candidates": [
                {"evidence_id": "ev_001", "publication_status": "top_secret"}
            ],
        }]
        result = validate_context_pack(_valid_pack(sources=sources))
        self.assertFalse(result["valid"])

    def test_duplicate_evidence_id_in_source(self) -> None:
        sources = [{
            "source_id": "src_001",
            "source_type": "pdf",
            "evidence_candidates": [
                {"evidence_id": "ev_001"},
                {"evidence_id": "ev_001"},
            ],
        }]
        result = validate_context_pack(_valid_pack(sources=sources))
        self.assertFalse(result["valid"])
        self.assertIn("Duplicate evidence_id", " ".join(result["errors"]))

    def test_high_sensitivity_warning(self) -> None:
        sources = [{
            "source_id": "src_001",
            "source_type": "pdf",
            "sensitivity": "high",
            "evidence_candidates": [
                {"evidence_id": "ev_001", "sensitivity": "high"}
            ],
        }]
        result = validate_context_pack(_valid_pack(sources=sources))
        self.assertTrue(result["valid"])
        self.assertTrue(any("high sensitivity" in w for w in result["warnings"]))

    def test_not_an_object(self) -> None:
        result = validate_context_pack([])  # type: ignore[arg-type]
        self.assertFalse(result["valid"])


class ContextPackImportTest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_ctx_pack_test_")
        self.runs_dir = Path(self._tmp) / "runs"
        self.runs_dir.mkdir()
        self.run_dir = create_run(self.runs_dir, {"project_name": "Test"}, run_id="ctx-test")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_valid_pack(self) -> None:
        pack = _valid_pack()
        result = import_context_pack(self.run_dir, pack)
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["added"], ["src_001"])
        # context_manifest.json should exist.
        manifest = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        self.assertEqual(len(manifest["sources"]), 1)
        self.assertEqual(manifest["sources"][0]["source_id"], "src_001")
        self.assertEqual(len(manifest["sources"][0]["evidence_candidates"]), 1)

    def test_import_rejects_duplicate_without_merge(self) -> None:
        pack = _valid_pack()
        import_context_pack(self.run_dir, pack)
        result = import_context_pack(self.run_dir, pack)
        self.assertEqual(result["rejected"], ["src_001"])
        self.assertEqual(result["added"], [])

    def test_import_merge_updates_existing(self) -> None:
        pack = _valid_pack()
        import_context_pack(self.run_dir, pack)
        # Update summary in second import.
        updated_sources = [
            {**pack["sources"][0], "summary": "更新后的摘要"}
        ]
        pack2 = _valid_pack(sources=updated_sources, created_at="2026-06-12T01:00:00Z")
        result = import_context_pack(self.run_dir, pack2, merge=True)
        self.assertEqual(result["updated"], ["src_001"])
        manifest = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        self.assertEqual(manifest["sources"][0]["summary"], "更新后的摘要")

    def test_import_invalid_pack_raises(self) -> None:
        with self.assertRaises(ContextPackError):
            import_context_pack(self.run_dir, {"schema_version": "wrong"})

    def test_bad_json_does_not_overwrite_manifest(self) -> None:
        # First import good pack.
        import_context_pack(self.run_dir, _valid_pack())
        manifest_before = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        # Try importing invalid JSON - simulate by passing bad dict.
        with self.assertRaises(ContextPackError):
            import_context_pack(self.run_dir, {"schema_version": "wrong"})
        manifest_after = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        self.assertEqual(manifest_before, manifest_after)

    def test_high_sensitivity_marked_in_manifest(self) -> None:
        sources = [{
            "source_id": "src_sensitive",
            "source_type": "internal_memo",
            "sensitivity": "high",
            "evidence_candidates": [
                {"evidence_id": "ev_s1", "sensitivity": "high", "publication_status": "internal_only"}
            ],
        }]
        pack = _valid_pack(sources=sources)
        import_context_pack(self.run_dir, pack)
        manifest = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        src = manifest["sources"][0]
        self.assertEqual(src["sensitivity"], "high")
        self.assertEqual(src["publication_status"], "internal_only")

    def test_context_pack_stored_in_context_packs_dir(self) -> None:
        pack = _valid_pack()
        result = import_context_pack(self.run_dir, pack)
        pack_file = self.run_dir / "context_packs" / f"{result['pack_id']}.json"
        self.assertTrue(pack_file.exists())

    def test_global_constraints_merged(self) -> None:
        pack = _valid_pack(global_constraints=["constraint A"])
        import_context_pack(self.run_dir, pack)
        pack2 = _valid_pack(
            global_constraints=["constraint B"],
            sources=[{"source_id": "src_002", "source_type": "pdf"}],
            created_at="2026-06-12T02:00:00Z",
        )
        import_context_pack(self.run_dir, pack2)
        manifest = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)
        self.assertIn("constraint A", manifest["constraints"])
        self.assertIn("constraint B", manifest["constraints"])

    def test_event_written_after_import(self) -> None:
        from scripts.runtime.events import read_events
        import_context_pack(self.run_dir, _valid_pack())
        events = read_events(self.run_dir)
        import_events = [
            e for e in events
            if e.get("step") == "context_pack.imported"
            or e.get("action") == "context_pack.imported"
        ]
        self.assertTrue(len(import_events) >= 1)


class ContextPackClaimGraphTest(unittest.TestCase):
    """Verify claim-evidence graph can consume imported evidence candidates."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_ctx_graph_test_")
        self.runs_dir = Path(self._tmp) / "runs"
        self.runs_dir.mkdir()
        self.run_dir = create_run(self.runs_dir, {"project_name": "Graph"}, run_id="graph-test")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_evidence_candidates_in_graph(self) -> None:
        pack = _valid_pack()
        import_context_pack(self.run_dir, pack)
        manifest = read_json(self.run_dir / CONTEXT_MANIFEST_NAME)

        claim_map = {
            "run_id": "graph-test",
            "claims": [
                {
                    "claim_id": "claim_01",
                    "claim": "客户需要统一会员运营闭环",
                    "evidence_refs": ["src_001", "ev_001"],
                }
            ],
        }
        page_tasks = {"tasks": []}

        graph = build_claim_evidence_graph(claim_map, page_tasks, context_manifest=manifest)

        # The evidence list should include the base source evidence AND the candidate.
        ev_ids = [e["evidence_id"] for e in graph["evidence"]]
        self.assertTrue(len(ev_ids) >= 2, f"Expected >=2 evidence entries, got {ev_ids}")
        # Candidate evidence should carry candidate_id.
        candidate_entries = [e for e in graph["evidence"] if e.get("candidate_id") == "ev_001"]
        self.assertEqual(len(candidate_entries), 1)


if __name__ == "__main__":
    unittest.main()
