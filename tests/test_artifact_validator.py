from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.artifact_validator import sha256_file, validate_artifact_descriptor, validate_artifact_manifest  # noqa: E402


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc"
    b"\xff\x1f\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)
PNG_2X2 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc"
    b"\xff\x1f\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ArtifactValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm_artifact_validator_"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _write_pptx(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as pptx:
            pptx.writestr(
                "[Content_Types].xml",
                "<Types><Override PartName=\"/ppt/presentation.xml\"/>"
                "<Override PartName=\"/ppt/slides/slide1.xml\"/></Types>",
            )
            pptx.writestr("ppt/presentation.xml", "<p:presentation/>")
            pptx.writestr(
                "ppt/slides/slide1.xml",
                "<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" "
                "xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\"><a:t>Ready</a:t></p:sld>",
            )

    def _artifact(self, rel: str, *, kind: str, media_type: str) -> dict:
        path = self.temp_dir / rel
        return {
            "artifact_id": path.stem,
            "kind": kind,
            "path": rel,
            "media_type": media_type,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "validation_status": "validated",
            "editability": "native",
        }

    def test_accepts_supported_artifact_signatures(self) -> None:
        (self.temp_dir / "deck.html").write_text("<!doctype html><html></html>", encoding="utf-8")
        (self.temp_dir / "deck.pdf").write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF\n")
        (self.temp_dir / "page.png").write_bytes(PNG_2X2)
        (self.temp_dir / "page.jpg").write_bytes(b"\xff\xd8\xff\xe0jpeg\xff\xd9")
        (self.temp_dir / "page.svg").write_text("<svg></svg>", encoding="utf-8")
        self._write_pptx(self.temp_dir / "deck.pptx")

        manifest = {
            "source_fingerprint": "a" * 64,
            "artifacts": [
                self._artifact("deck.html", kind="deck_html", media_type="text/html"),
                self._artifact("deck.pdf", kind="deck_pdf", media_type="application/pdf"),
                self._artifact("page.png", kind="page_png", media_type="image/png"),
                self._artifact("page.jpg", kind="page_jpeg", media_type="image/jpeg"),
                self._artifact("page.svg", kind="page_svg", media_type="image/svg+xml"),
                self._artifact(
                    "deck.pptx",
                    kind="deck_pptx",
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            ],
        }

        result = validate_artifact_manifest(self.temp_dir, manifest, expected_source_fingerprint="a" * 64)

        self.assertTrue(result["valid"], result.get("errors"))
        self.assertEqual(6, result["artifact_count"])

    def test_rejects_path_escape(self) -> None:
        result = validate_artifact_descriptor(
            self.temp_dir,
            {
                "artifact_id": "escape",
                "kind": "deck_html",
                "path": "../escape.html",
                "media_type": "text/html",
                "sha256": "a" * 64,
                "bytes": 1,
                "validation_status": "validated",
            },
        )

        self.assertFalse(result["valid"])
        self.assertTrue(any("run-relative" in error for error in result["errors"]))

    def test_rejects_checksum_mismatch_and_empty_artifact(self) -> None:
        empty = self.temp_dir / "empty.pdf"
        empty.write_bytes(b"")
        result = validate_artifact_descriptor(
            self.temp_dir,
            {
                "artifact_id": "empty",
                "kind": "deck_pdf",
                "path": "empty.pdf",
                "media_type": "application/pdf",
                "sha256": "0" * 64,
                "bytes": 10,
                "validation_status": "validated",
            },
        )

        self.assertFalse(result["valid"])
        self.assertIn("artifact is empty.", result["errors"])
        self.assertIn("sha256 mismatch.", result["errors"])

    def test_rejects_magic_mismatch(self) -> None:
        (self.temp_dir / "bad.pdf").write_text("plain text", encoding="utf-8")
        artifact = self._artifact("bad.pdf", kind="deck_pdf", media_type="application/pdf")

        result = validate_artifact_descriptor(self.temp_dir, artifact)

        self.assertFalse(result["valid"])
        self.assertIn("pdf artifact has invalid signature.", result["errors"])

    def test_rejects_placeholder_content(self) -> None:
        (self.temp_dir / "placeholder.html").write_bytes(
            b"<!doctype html><html>deck-master bundled generation placeholder</html>"
        )
        artifact = self._artifact("placeholder.html", kind="deck_html", media_type="text/html")

        result = validate_artifact_descriptor(self.temp_dir, artifact)

        self.assertFalse(result["valid"])
        self.assertIn("artifact points to bundled placeholder content.", result["errors"])

    def test_rejects_tiny_png_preview(self) -> None:
        (self.temp_dir / "tiny.png").write_bytes(PNG_1X1)
        artifact = self._artifact("tiny.png", kind="page_png", media_type="image/png")

        result = validate_artifact_descriptor(self.temp_dir, artifact)

        self.assertFalse(result["valid"])
        self.assertTrue(any("too small" in error for error in result["errors"]))

    def test_rejects_non_client_deliverable_manifest_for_client_context(self) -> None:
        (self.temp_dir / "deck.html").write_text("<!doctype html><html><section>Smoke</section></html>", encoding="utf-8")
        manifest = {
            "source_fingerprint": "a" * 64,
            "source_mode": "contract_smoke",
            "non_client_deliverable": True,
            "page_count": 1,
            "artifacts": [self._artifact("deck.html", kind="deck_html", media_type="text/html")],
        }

        result = validate_artifact_manifest(
            self.temp_dir,
            manifest,
            expected_source_fingerprint="a" * 64,
            allow_non_client_deliverable=False,
        )

        self.assertFalse(result["valid"])
        self.assertIn("manifest is marked non-client-deliverable: contract_smoke.", result["errors"])

    def test_rejects_stale_manifest_fingerprint(self) -> None:
        (self.temp_dir / "deck.html").write_text("<!doctype html><html></html>", encoding="utf-8")
        manifest = {
            "source_fingerprint": "a" * 64,
            "artifacts": [self._artifact("deck.html", kind="deck_html", media_type="text/html")],
        }

        result = validate_artifact_manifest(self.temp_dir, manifest, expected_source_fingerprint="b" * 64)

        self.assertFalse(result["valid"])
        self.assertIn("manifest source_fingerprint is stale.", result["errors"])


if __name__ == "__main__":
    unittest.main()
