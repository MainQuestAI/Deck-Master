from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from manifest import ManifestError, load_manifest, preview_file_path, update_page_decision


SAMPLE_RUN = ROOT / "examples" / "preview-run"


class ManifestTests(unittest.TestCase):
    def copy_sample(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        run_dir = temp_dir / "run"
        shutil.copytree(SAMPLE_RUN, run_dir)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return run_dir

    def test_load_manifest_sorts_pages(self) -> None:
        run_dir = self.copy_sample()
        data = load_manifest(run_dir)
        self.assertEqual(["page_001", "page_002", "page_003"], [page["page_id"] for page in data["pages"]])

    def test_update_page_decision_persists(self) -> None:
        run_dir = self.copy_sample()
        update_page_decision(run_dir, "page_001", "approved", "Ready for export.")
        data = load_manifest(run_dir)
        page = next(page for page in data["pages"] if page["page_id"] == "page_001")
        self.assertEqual("approved", page["decision"])
        self.assertEqual("Ready for export.", page["notes"])
        self.assertIn("updated_at", data)

    def test_rejects_preview_path_traversal(self) -> None:
        run_dir = self.copy_sample()
        manifest_path = run_dir / "preview_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["pages"][0]["preview_path"] = "../secret.png"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ManifestError):
            load_manifest(run_dir)

    def test_preview_file_stays_under_run_dir(self) -> None:
        run_dir = self.copy_sample()
        data = load_manifest(run_dir)
        path = preview_file_path(run_dir, data["pages"][0])
        self.assertTrue(str(path).startswith(str(run_dir.resolve())))


if __name__ == "__main__":
    unittest.main()
