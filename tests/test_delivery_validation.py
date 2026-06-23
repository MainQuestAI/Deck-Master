from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from delivery.validate import validate_delivery, _compute_hash


class DeliveryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = temp_dir / "run-test"
        self.run_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

    def _write_pptx(self, path: Path, *, slide_count: int = 1) -> None:
        with zipfile.ZipFile(path, "w") as pptx:
            pptx.writestr("[Content_Types].xml", "<Types/>")
            pptx.writestr("ppt/presentation.xml", "<p:presentation/>")
            for index in range(1, slide_count + 1):
                pptx.writestr(
                    f"ppt/slides/slide{index}.xml",
                    "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
                    "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
                    f"<a:t>Slide {index}</a:t></p:sld>",
                )

    def _write_html(self, path: Path) -> None:
        path.write_text("<!doctype html><html></html>", encoding="utf-8")

    # ---- artifact 不存在 → P0 ----
    def test_missing_artifact_returns_p0(self) -> None:
        missing = self.run_dir / "output.pptx"
        report = validate_delivery(self.run_dir, missing)

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(report["blocks_delivery"])
        self.assertEqual(1, len(report["findings"]))
        self.assertEqual("P0", report["findings"][0]["severity"])
        self.assertEqual("delivery_artifact_missing", report["findings"][0]["finding_id"])

    # ---- 页数不匹配 → P1 ----
    def test_page_count_mismatch_returns_p1(self) -> None:
        artifact = self.run_dir / "output.pptx"
        self._write_pptx(artifact, slide_count=1)
        report = validate_delivery(self.run_dir, artifact, expected_page_count=10)

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(report["blocks_delivery"])
        self.assertEqual("delivery_page_count_mismatch", report["findings"][0]["finding_id"])

    # ---- 正常 pass（无 expected page count）----
    def test_pass_when_artifact_exists_no_expected_pages(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)

        report = validate_delivery(self.run_dir, artifact)

        self.assertEqual("pass", report["status"])
        self.assertFalse(report["blocks_delivery"])
        self.assertEqual(0, len(report["findings"]))

    # ---- lineage 文件写入 ----
    def test_lineage_file_written(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)

        validate_delivery(self.run_dir, artifact, expected_page_count=0)

        lineage_path = self.run_dir / "delivery" / "final_version_lineage.json"
        self.assertTrue(lineage_path.exists())

        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        self.assertEqual("deck_final_version_lineage.v1", lineage["schema_version"])
        self.assertEqual("run-test", lineage["run_id"])
        self.assertEqual(str(artifact.resolve()), lineage["artifact_path"])
        self.assertEqual("output.html", lineage["artifact_run_relative"])
        self.assertIn("artifact_hash", lineage)
        self.assertTrue(lineage["artifact_validation"]["valid"])
        self.assertIn("gates_checked", lineage)

    # ---- hash 计算 ----
    def test_hash_computation(self) -> None:
        artifact = self.run_dir / "hash_test.bin"
        content = b"deterministic-content-for-hash"
        artifact.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        actual = _compute_hash(artifact)

        self.assertEqual(expected, actual)

    # ---- quality reports 被读取 ----
    def test_quality_reports_read(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)

        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        gate_report = {"status": "pass", "blocks_delivery": False}
        (quality_dir / "draft_gate.json").write_text(
            json.dumps(gate_report), encoding="utf-8"
        )

        report = validate_delivery(self.run_dir, artifact)

        self.assertEqual("pass", report["status"])
        gates = report["lineage"]["gates_checked"]
        self.assertEqual(1, len(gates))
        self.assertEqual("draft", gates[0]["gate"])
        self.assertEqual("pass", gates[0]["status"])

    # ---- schema version correct ----
    def test_schema_version(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)

        report = validate_delivery(self.run_dir, artifact)

        self.assertEqual("deck_delivery_validation.v1", report["schema_version"])
        self.assertEqual("delivery_validation", report["gate"])

    def test_invalid_pptx_parse_blocks_delivery(self) -> None:
        artifact = self.run_dir / "output.pptx"
        artifact.write_bytes(b"fake-pptx-content")

        report = validate_delivery(self.run_dir, artifact, expected_page_count=1)

        self.assertEqual("rework_required", report["status"])
        finding_ids = {finding["finding_id"] for finding in report["findings"]}
        self.assertIn("delivery_artifact_invalid", finding_ids)
        self.assertIn("delivery_artifact_parse_failed", finding_ids)

    def test_artifact_outside_run_blocks_delivery(self) -> None:
        outside = self.run_dir.parent / "outside.html"
        self._write_html(outside)

        report = validate_delivery(self.run_dir, outside)

        self.assertEqual("rework_required", report["status"])
        self.assertEqual("delivery_artifact_path_unsafe", report["findings"][0]["finding_id"])

    def test_invalid_artifact_manifest_blocks_delivery(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)
        build_dir = self.run_dir / "build"
        build_dir.mkdir()
        (build_dir / "bad.pdf").write_text("not-pdf", encoding="utf-8")
        (build_dir / "artifact_manifest.json").write_text(
            json.dumps(
                {
                    "source_fingerprint": "a" * 64,
                    "artifacts": [
                        {
                            "artifact_id": "bad_pdf",
                            "kind": "deck_pdf",
                            "path": "build/bad.pdf",
                            "media_type": "application/pdf",
                            "sha256": hashlib.sha256((build_dir / "bad.pdf").read_bytes()).hexdigest(),
                            "bytes": (build_dir / "bad.pdf").stat().st_size,
                            "validation_status": "validated",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        report = validate_delivery(self.run_dir, artifact)

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(any(f["finding_id"] == "delivery_artifact_manifest_invalid" for f in report["findings"]))

    def test_stale_source_fingerprint_blocks_delivery(self) -> None:
        artifact = self.run_dir / "output.html"
        self._write_html(artifact)
        build_dir = self.run_dir / "build"
        render_dir = self.run_dir / "render_results"
        build_dir.mkdir()
        render_dir.mkdir()
        (build_dir / "build_manifest.json").write_text(json.dumps({"source_fingerprint": "a" * 64}), encoding="utf-8")
        (build_dir / "artifact_manifest.json").write_text(json.dumps({"source_fingerprint": "b" * 64, "artifacts": []}), encoding="utf-8")
        (render_dir / "render_result.json").write_text(json.dumps({"source_fingerprint": "b" * 64}), encoding="utf-8")

        report = validate_delivery(self.run_dir, artifact)

        self.assertEqual("rework_required", report["status"])
        self.assertTrue(any(f["finding_id"] == "delivery_source_fingerprint_stale" for f in report["findings"]))


if __name__ == "__main__":
    unittest.main()
