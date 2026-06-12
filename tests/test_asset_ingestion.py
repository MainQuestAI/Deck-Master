from __future__ import annotations
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so `assets` package is importable
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from assets.ingest_library_results import ingest_library_results
from assets.schema import load_asset_graph, create_slide_asset, register_asset
from assets.canonical_id import candidate_to_canonical_id
from runtime.events import read_events


def _write_selection(run_dir: Path, data: dict) -> None:
    lr = run_dir / "library_results"
    lr.mkdir(parents=True, exist_ok=True)
    (lr / "selection.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestIngestLibraryResults(unittest.TestCase):
    """P3-B: library result ingestion 行为覆盖。"""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.run_dir = self.tmp_dir / "runs" / "run-001"
        self.run_dir.mkdir(parents=True)
        self.workspace_dir = self.tmp_dir / "workspace"
        self.workspace_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_register_by_beat_candidates(self):
        """正常候选注册为 asset，并写入 asset_refs.json。"""
        _write_selection(self.run_dir, {
            "by_beat": {
                "beat-1": [
                    {
                        "file_sha256": "aaa",
                        "page_number": 1,
                        "title": "Market Overview",
                        "source_pptx": "/decks/market.pptx",
                        "screenshot_path": "/shots/1.png",
                        "confidence": 0.9,
                        "source_project": "proj-x",
                    },
                    {
                        "file_sha256": "bbb",
                        "page_number": 2,
                        "title": "Growth",
                        "source_pptx": "/decks/growth.pptx",
                        "screenshot_path": "/shots/2.png",
                        "score": 0.8,
                    },
                ],
            },
        })

        result = ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        self.assertEqual(result["run_id"], "run-001")
        self.assertEqual(result["registered_count"], 2)
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["asset_refs"]), 2)
        self.assertEqual(result["asset_refs"][0]["beat_id"], "beat-1")

        # workspace graph 应有 2 个 asset
        graph = load_asset_graph(self.workspace_dir)
        self.assertEqual(len(graph["assets"]), 2)

        # asset_refs.json 已写入
        refs_path = self.run_dir / "asset_refs.json"
        self.assertTrue(refs_path.exists())
        refs_data = json.loads(refs_path.read_text(encoding="utf-8"))
        self.assertEqual(refs_data["run_id"], "run-001")
        self.assertEqual(len(refs_data["asset_refs"]), 2)

        # event 已写入
        events = read_events(self.run_dir)
        artifact_events = [e for e in events if e.get("event_type") == "artifact_written"]
        self.assertGreaterEqual(len(artifact_events), 1)

    def test_empty_result_writes_warn_event(self):
        """空 by_beat / candidates → registered_count=0，写 step_completed warn event。"""
        _write_selection(self.run_dir, {"by_beat": {}, "candidates": []})

        result = ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        self.assertEqual(result["registered_count"], 0)
        events = read_events(self.run_dir)
        warn_events = [
            e for e in events
            if e.get("event_type") == "step_completed" and e.get("severity") == "warn"
        ]
        self.assertGreaterEqual(len(warn_events), 1)

    def test_invalid_json_does_not_touch_workspace_graph(self):
        """损坏的 selection.json → 返回错误，不修改已有 workspace asset graph。"""
        # 预置一个合法 asset graph
        existing_asset = create_slide_asset("slide_existing", page_number=1, title="Existing")
        register_asset(self.workspace_dir, existing_asset)
        before = load_asset_graph(self.workspace_dir)

        # 写入坏 JSON
        lr = self.run_dir / "library_results"
        lr.mkdir(parents=True)
        (lr / "selection.json").write_text("{not valid json!!!", encoding="utf-8")

        result = ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        self.assertEqual(result["registered_count"], 0)
        self.assertGreaterEqual(len(result["errors"]), 1)
        self.assertIn("Invalid JSON", result["errors"][0])

        after = load_asset_graph(self.workspace_dir)
        self.assertEqual(len(after["assets"]), len(before["assets"]))
        self.assertEqual(after["assets"][0]["canonical_slide_id"], "slide_existing")

    def test_missing_screenshot_sets_health_flag(self):
        """缺截图 → 通过 create_slide_asset 的 health_flags 标记 missing_screenshot。"""
        _write_selection(self.run_dir, {
            "by_beat": {
                "beat-x": [{
                    "file_sha256": "ccc",
                    "page_number": 3,
                    "title": "No Shot",
                    "source_pptx": "/decks/x.pptx",
                    # 故意不带 screenshot_path
                }],
            },
        })

        ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        graph = load_asset_graph(self.workspace_dir)
        asset = next(a for a in graph["assets"] if a["title"] == "No Shot")
        self.assertIn("missing_screenshot", asset["health_flags"])
        self.assertFalse(asset["screenshot_available"])

    def test_duplicate_candidate_collapses_to_same_id(self):
        """同一 candidate 出现在 by_beat 和顶层 candidates → 只注册一次。"""
        dup = {
            "file_sha256": "dup-hash",
            "page_number": 1,
            "title": "Duplicate Slide",
            "source_pptx": "/decks/dup.pptx",
            "screenshot_path": "/shots/dup.png",
        }
        _write_selection(self.run_dir, {
            "by_beat": {"beat-a": [dup]},
            "candidates": [dup],
        })

        result = ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        self.assertEqual(result["registered_count"], 1)
        graph = load_asset_graph(self.workspace_dir)
        self.assertEqual(len(graph["assets"]), 1)
        self.assertEqual(len(result["asset_refs"]), 1)

    def test_no_workspace_dir_still_writes_asset_refs(self):
        """无 workspace_dir → 不写 graph，但仍写 asset_refs.json 与 event。"""
        _write_selection(self.run_dir, {
            "by_beat": {
                "beat-z": [{
                    "file_sha256": "zzz",
                    "page_number": 1,
                    "title": "Orphan",
                    "source_pptx": "/decks/z.pptx",
                    "screenshot_path": "/shots/z.png",
                }],
            },
        })

        result = ingest_library_results(self.run_dir, workspace_dir=None)

        self.assertEqual(result["registered_count"], 1)
        refs_path = self.run_dir / "asset_refs.json"
        self.assertTrue(refs_path.exists())
        refs_data = json.loads(refs_path.read_text(encoding="utf-8"))
        self.assertEqual(len(refs_data["asset_refs"]), 1)

        # workspace 没有创建任何 graph
        ws_graph = self.tmp_dir / "nope-workspace" / "assets" / "asset_graph.json"
        self.assertFalse(ws_graph.exists())

    def test_missing_selection_returns_error_without_crash(self):
        """完全缺失 selection.json → 友好返回错误，不抛异常，且不写产物。"""
        result = ingest_library_results(self.run_dir, workspace_dir=self.workspace_dir)

        self.assertEqual(result["registered_count"], 0)
        self.assertIn("selection.json not found", result["errors"])
        # 早期失败路径不应产生 asset_refs.json（避免误导下游）
        refs_path = self.run_dir / "asset_refs.json"
        self.assertFalse(refs_path.exists())


if __name__ == "__main__":
    unittest.main()
