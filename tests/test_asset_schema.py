from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so `assets` package is importable
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from assets.schema import (
    ASSET_SCHEMA_VERSION,
    SCHEMA_VERSION,
    compute_canonical_slide_id,
    compute_file_sha256,
    create_slide_asset,
    load_asset_graph,
    register_asset,
    save_asset_graph,
)
from assets.canonical_id import candidate_to_canonical_id, normalize_title


class TestCanonicalSlideId(unittest.TestCase):
    """canonical ID 计算稳定性与 fallback 行为。"""

    def test_same_input_stable_output(self):
        """相同输入 → 稳定输出。"""
        id1 = compute_canonical_slide_id(
            file_sha256="abc123",
            page_number=3,
            normalized_title="market overview",
        )
        id2 = compute_canonical_slide_id(
            file_sha256="abc123",
            page_number=3,
            normalized_title="market overview",
        )
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("slide_"))
        self.assertEqual(len(id1), len("slide_") + 16)

    def test_different_inputs_different_ids(self):
        """不同输入 → 不同 ID。"""
        id1 = compute_canonical_slide_id(file_sha256="aaa", page_number=1, normalized_title="a")
        id2 = compute_canonical_slide_id(file_sha256="bbb", page_number=1, normalized_title="a")
        self.assertNotEqual(id1, id2)

    def test_file_move_hash_page_stable(self):
        """文件移动后 hash+页码不变 → ID 稳定（不依赖路径）。"""
        # canonical ID 只依赖 hash/page/title，不包含路径
        id_before = compute_canonical_slide_id(
            file_sha256="deadbeef" * 8,
            page_number=5,
            normalized_title="strategy",
        )
        id_after = compute_canonical_slide_id(
            file_sha256="deadbeef" * 8,
            page_number=5,
            normalized_title="strategy",
        )
        self.assertEqual(id_before, id_after)

    def test_missing_sha256_uses_fallback_source_ref(self):
        """缺 file_sha256 → 使用 fallback_source_ref。"""
        id_with_fallback = compute_canonical_slide_id(
            file_sha256="",
            page_number=1,
            normalized_title="intro",
            fallback_source_ref="/some/path.pptx",
        )
        id_without_fallback = compute_canonical_slide_id(
            file_sha256="",
            page_number=1,
            normalized_title="intro",
            fallback_source_ref="",
        )
        # 有 fallback 和没有 fallback 应该产生不同 ID
        self.assertNotEqual(id_with_fallback, id_without_fallback)
        self.assertTrue(id_with_fallback.startswith("slide_"))

    def test_missing_title_uses_text_summary_fallback(self):
        """缺 title → 使用 text summary 前 120 字。"""
        long_summary = "A" * 200
        id_with_summary = compute_canonical_slide_id(
            file_sha256="hash123",
            page_number=1,
            normalized_title="",
            fallback_text_summary=long_summary,
        )
        id_no_summary = compute_canonical_slide_id(
            file_sha256="hash123",
            page_number=1,
            normalized_title="",
            fallback_text_summary="",
        )
        self.assertNotEqual(id_with_summary, id_no_summary)
        # 验证只用前 120 字：超过 120 字的额外内容不影响 ID
        id_shorter_summary = compute_canonical_slide_id(
            file_sha256="hash123",
            page_number=1,
            normalized_title="",
            fallback_text_summary="A" * 120,
        )
        self.assertEqual(id_with_summary, id_shorter_summary)


class TestNormalizeTitle(unittest.TestCase):
    """normalize_title 行为。"""

    def test_basic_normalization(self):
        self.assertEqual(normalize_title("  Hello   World  "), "hello world")

    def test_empty_string(self):
        self.assertEqual(normalize_title(""), "")

    def test_tabs_and_newlines(self):
        self.assertEqual(normalize_title("foo\tbar\nbaz"), "foo bar baz")


class TestCandidateToCanonicalId(unittest.TestCase):
    """candidate_to_canonical_id 从候选字典提取字段。"""

    def test_standard_fields(self):
        candidate = {
            "file_sha256": "abcdef1234567890",
            "page_number": 2,
            "title": "Growth Metrics",
        }
        cid = candidate_to_canonical_id(candidate)
        expected = compute_canonical_slide_id(
            file_sha256="abcdef1234567890",
            page_number=2,
            normalized_title="growth metrics",
        )
        self.assertEqual(cid, expected)

    def test_fallback_field_names(self):
        """支持 slide_index / page_title / source_pptx / excerpt 等别名。"""
        candidate = {
            "slide_index": 4,
            "page_title": "Team Overview",
            "source_pptx": "/decks/team.pptx",
            "excerpt": "Our team consists of...",
        }
        cid = candidate_to_canonical_id(candidate)
        expected = compute_canonical_slide_id(
            file_sha256="",
            page_number=4,
            normalized_title="team overview",
            fallback_source_ref="/decks/team.pptx",
            fallback_text_summary="Our team consists of...",
        )
        self.assertEqual(cid, expected)


class TestCreateSlideAsset(unittest.TestCase):
    """create_slide_asset 结构与 health_flags。"""

    def test_missing_screenshot_flag(self):
        """缺截图 → missing_screenshot 标记。"""
        asset = create_slide_asset("slide_abc", page_number=1, title="Test")
        self.assertIn("missing_screenshot", asset["health_flags"])
        self.assertFalse(asset["screenshot_available"])

    def test_with_screenshot_no_flag(self):
        """有截图 → 无 missing_screenshot 标记。"""
        asset = create_slide_asset("slide_abc", screenshot_path="/tmp/shot.png")
        self.assertNotIn("missing_screenshot", asset["health_flags"])
        self.assertTrue(asset["screenshot_available"])

    def test_workspace_relative_path_priority(self):
        """workspace_relative_path 优先于 external_path 和 source_path。"""
        asset = create_slide_asset(
            "slide_x",
            source_path="/abs/path.pptx",
            workspace_relative_path="slides/a.pptx",
            external_path="/ext/b.pptx",
        )
        self.assertIn("workspace_relative_path", asset)
        self.assertNotIn("external_path", asset)
        self.assertNotIn("source_path", asset)

    def test_external_path_when_no_workspace(self):
        """无 workspace_relative_path 时使用 external_path。"""
        asset = create_slide_asset(
            "slide_x",
            source_path="/abs/path.pptx",
            external_path="/ext/b.pptx",
        )
        self.assertIn("external_path", asset)
        self.assertNotIn("source_path", asset)

    def test_schema_version_set(self):
        asset = create_slide_asset("slide_x")
        self.assertEqual(asset["schema_version"], ASSET_SCHEMA_VERSION)


class TestComputeFileSha256(unittest.TestCase):
    """compute_file_sha256 行为。"""

    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"hello world")
            tmp_path = f.name
        try:
            h = compute_file_sha256(tmp_path)
            self.assertEqual(len(h), 64)  # SHA256 hex length
            self.assertNotEqual(h, "")
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file_returns_empty(self):
        self.assertEqual(compute_file_sha256("/nonexistent/path/file.bin"), "")


class TestAssetGraphPersistence(unittest.TestCase):
    """load / save / register 的持久化行为。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_load_empty_graph_when_no_file(self):
        """空目录 → 返回空 graph。"""
        graph = load_asset_graph(self.tmp_dir)
        self.assertEqual(graph["schema_version"], SCHEMA_VERSION)
        self.assertEqual(graph["assets"], [])

    def test_load_corrupted_json_returns_empty_graph(self):
        """损坏 JSON → 返回空 graph。"""
        assets_dir = Path(self.tmp_dir) / "assets"
        assets_dir.mkdir()
        (assets_dir / "asset_graph.json").write_text("{broken json!!!", encoding="utf-8")
        graph = load_asset_graph(self.tmp_dir)
        self.assertEqual(graph["schema_version"], SCHEMA_VERSION)
        self.assertEqual(graph["assets"], [])

    def test_load_non_dict_json_returns_empty_graph(self):
        """JSON 是 list 而非 dict → 返回空 graph。"""
        assets_dir = Path(self.tmp_dir) / "assets"
        assets_dir.mkdir()
        (assets_dir / "asset_graph.json").write_text("[1,2,3]", encoding="utf-8")
        graph = load_asset_graph(self.tmp_dir)
        self.assertEqual(graph["schema_version"], SCHEMA_VERSION)
        self.assertEqual(graph["assets"], [])

    def test_save_atomic_write(self):
        """save_asset_graph 原子写入：先写 .tmp 再 replace。"""
        graph = {"schema_version": SCHEMA_VERSION, "assets": [{"id": "test"}]}
        result_path = save_asset_graph(self.tmp_dir, graph)

        self.assertTrue(result_path.exists())
        # .tmp 文件不应残留
        tmp_path = result_path.with_suffix(".json.tmp")
        self.assertFalse(tmp_path.exists())

        loaded = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], SCHEMA_VERSION)
        self.assertEqual(len(loaded["assets"]), 1)

    def test_register_new_asset_adds_to_graph(self):
        """register_asset 新 asset → 添加到 graph。"""
        asset = create_slide_asset("slide_new", page_number=1, title="New Slide")
        result = register_asset(self.tmp_dir, asset)

        self.assertEqual(result["canonical_slide_id"], "slide_new")
        graph = load_asset_graph(self.tmp_dir)
        self.assertEqual(len(graph["assets"]), 1)
        self.assertEqual(graph["assets"][0]["canonical_slide_id"], "slide_new")

    def test_register_duplicate_merges(self):
        """register_asset 重复 canonical_slide_id → 合并更新。"""
        asset_v1 = create_slide_asset("slide_dup", page_number=1, title="Old Title")
        register_asset(self.tmp_dir, asset_v1)

        asset_v2 = create_slide_asset(
            "slide_dup",
            page_number=1,
            title="Updated Title",
            screenshot_path="/new/shot.png",
        )
        result = register_asset(self.tmp_dir, asset_v2)

        graph = load_asset_graph(self.tmp_dir)
        # 仍然只有 1 个 asset
        self.assertEqual(len(graph["assets"]), 1)
        # title 已更新
        self.assertEqual(result["title"], "Updated Title")
        # screenshot 已更新
        self.assertEqual(result["screenshot_path"], "/new/shot.png")
        # canonical_slide_id 不变
        self.assertEqual(result["canonical_slide_id"], "slide_dup")

    def test_register_preserves_extra_fields_on_merge(self):
        """合并时保留已有字段（如 metadata 中的历史数据），同时更新新字段。"""
        asset_v1 = create_slide_asset(
            "slide_merge",
            page_number=2,
            title="Original",
            metadata={"created_by": "agent_a"},
        )
        register_asset(self.tmp_dir, asset_v1)

        asset_v2 = create_slide_asset(
            "slide_merge",
            page_number=2,
            title="Updated",
            metadata={"updated_by": "agent_b"},
        )
        result = register_asset(self.tmp_dir, asset_v2)

        # metadata 被整体替换（update 语义）
        self.assertEqual(result["metadata"], {"updated_by": "agent_b"})
        self.assertEqual(result["title"], "Updated")


if __name__ == "__main__":
    unittest.main()
