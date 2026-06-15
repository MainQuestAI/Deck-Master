from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from workspace.foundation import (
    MANIFEST_NAME,
    STANDARD_DIRS,
    STANDARD_FILES,
    WorkspaceError,
    init_workspace,
    repair_workspace,
    register_workspace,
    validate_workspace,
)


class WorkspaceFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    # ------------------------------------------------------------------ #
    # init_workspace
    # ------------------------------------------------------------------ #

    def test_init_creates_all_dirs_and_files(self) -> None:
        ws = self.temp_dir / "my-workspace"
        manifest = init_workspace(ws, "Test WS")

        self.assertEqual("deck_workspace.v1", manifest["schema_version"])
        self.assertEqual("Test WS", manifest["name"])
        self.assertTrue((ws / MANIFEST_NAME).is_file())

        for rel in STANDARD_DIRS:
            self.assertTrue((ws / rel).is_dir(), f"Missing dir: {rel}")

        for rel in STANDARD_FILES:
            self.assertTrue((ws / rel).is_file(), f"Missing file: {rel}")

        self.assertTrue((ws / "assets/asset_graph.json").is_file())
        self.assertTrue((ws / "assets/asset_feedback.jsonl").is_file())

    def test_init_manifest_schema_version(self) -> None:
        ws = self.temp_dir / "ws"
        manifest = init_workspace(ws, "Schema Check")
        self.assertEqual("deck_workspace.v1", manifest["schema_version"])
        self.assertIsNone(manifest["reference_ppt"])
        self.assertIsNone(manifest["registered_at"])

    def test_init_duplicate_raises(self) -> None:
        ws = self.temp_dir / "dup"
        init_workspace(ws, "First")
        with self.assertRaises(WorkspaceError):
            init_workspace(ws, "Second")

    # ------------------------------------------------------------------ #
    # register_workspace
    # ------------------------------------------------------------------ #

    def test_register_existing_workspace(self) -> None:
        ws = self.temp_dir / "reg"
        init_workspace(ws, "Reg Test")
        result = register_workspace(ws)
        self.assertEqual("deck_workspace.v1", result["schema_version"])

    def test_register_with_missing_reference_ppt_raises(self) -> None:
        ws = self.temp_dir / "reg-ppt"
        init_workspace(ws, "PPT Test")
        with self.assertRaises(WorkspaceError):
            register_workspace(ws, reference_ppt="/nonexistent/file.pptx")

    def test_register_with_valid_reference_ppt(self) -> None:
        ws = self.temp_dir / "reg-valid-ppt"
        init_workspace(ws, "Valid PPT")

        # Create a fake pptx file (just bytes, python-pptx not required).
        fake_ppt = self.temp_dir / "ref.pptx"
        fake_ppt.write_bytes(b"fake-pptx-content")

        result = register_workspace(ws, reference_ppt=fake_ppt)
        self.assertEqual(str(fake_ppt.resolve()), result["reference_ppt"])
        self.assertIsNotNone(result["reference_ppt_hash"])
        self.assertIsNotNone(result["registered_at"])
        # pages may be None since python-pptx is not installed
        self.assertIn("reference_ppt_pages", result)

    def test_register_without_manifest_raises(self) -> None:
        empty_ws = self.temp_dir / "no-manifest"
        empty_ws.mkdir()
        with self.assertRaises(WorkspaceError):
            register_workspace(empty_ws)

    # ------------------------------------------------------------------ #
    # validate_workspace
    # ------------------------------------------------------------------ #

    def test_validate_complete_workspace(self) -> None:
        ws = self.temp_dir / "valid"
        init_workspace(ws, "Complete")
        report = validate_workspace(ws)

        self.assertEqual("deck_workspace_validation.v1", report["schema_version"])
        self.assertEqual("valid", report["status"])
        self.assertEqual([], report["missing_items"])

    def test_validate_missing_files_pending_review(self) -> None:
        ws = self.temp_dir / "incomplete"
        init_workspace(ws, "Incomplete")
        # Remove a standard file.
        (ws / "quality/scoring_rubric.md").unlink()

        report = validate_workspace(ws)
        self.assertEqual("pending_manual_review", report["status"])
        self.assertIn("quality/scoring_rubric.md", report["missing_items"])

    def test_validate_missing_manifest(self) -> None:
        empty_ws = self.temp_dir / "empty"
        empty_ws.mkdir()
        report = validate_workspace(empty_ws)
        self.assertEqual("pending_manual_review", report["status"])
        self.assertIn(MANIFEST_NAME, report["missing_items"])

    def test_validate_bad_manifest_json(self) -> None:
        ws = self.temp_dir / "bad-json"
        ws.mkdir()
        (ws / MANIFEST_NAME).write_text("{invalid json!!", encoding="utf-8")

        report = validate_workspace(ws)
        self.assertEqual("pending_manual_review", report["status"])
        # Should mention invalid JSON in missing_items.
        self.assertTrue(
            any("invalid JSON" in item or MANIFEST_NAME in item for item in report["missing_items"]),
            f"Expected manifest error in missing_items: {report['missing_items']}",
        )

    def test_validate_warns_on_missing_reference_ppt(self) -> None:
        ws = self.temp_dir / "warn-ref"
        init_workspace(ws, "Warn Ref")

        # Manually set a reference_ppt that doesn't exist on disk.
        manifest_path = ws / MANIFEST_NAME
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["reference_ppt"] = "/tmp/nonexistent_ref.pptx"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")

        report = validate_workspace(ws)
        self.assertEqual("valid", report["status"])  # structure is complete
        self.assertTrue(len(report["warnings"]) > 0)
        self.assertTrue(any("not found" in w for w in report["warnings"]))

    def test_repair_workspace_creates_missing_standard_items(self) -> None:
        ws = self.temp_dir / "repair"
        ws.mkdir()

        report = repair_workspace(ws, name="Repair Test")

        self.assertEqual("valid", report["status"])
        self.assertTrue((ws / MANIFEST_NAME).is_file())
        self.assertTrue((ws / "quality/delivery_checklist.md").is_file())
        self.assertTrue((ws / "assets/asset_graph.json").is_file())
        self.assertTrue((ws / "assets/asset_feedback.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
