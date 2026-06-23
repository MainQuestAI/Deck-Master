from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.customer_visible_safety import (
    evaluate_customer_visible_safety_gate,
    load_customer_visible_forbidden_terms,
)
from quality.pptx_audit import audit_pptx
from runtime.run_state import write_json


class CustomerVisibleSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_pptx_audit_scans_visible_and_potentially_visible_package_text(self) -> None:
        pptx = self.temp_dir / "unsafe.pptx"
        _write_rich_pptx(pptx)

        audit = audit_pptx(
            pptx,
            expected_pages=1,
            forbidden_terms=["证书墙", "讲标", "缩略图", "左屏", "评分", "Brief", "关键图示"],
        )

        scopes = {hit["scope"] for hit in audit["forbidden_hits"]}
        self.assertIn("slide", scopes)
        self.assertIn("notes", scopes)
        self.assertIn("slide_master", scopes)
        self.assertIn("slide_layout", scopes)
        self.assertIn("chart", scopes)
        self.assertIn("doc_props", scopes)
        self.assertTrue(any(hit["term"] == "关键图示" for hit in audit["forbidden_hits"]))

    def test_customer_visible_safety_gate_blocks_with_structured_findings(self) -> None:
        pptx = self.temp_dir / "unsafe.pptx"
        _write_rich_pptx(pptx)

        report = evaluate_customer_visible_safety_gate(
            "run-unsafe",
            pptx,
            expected_pages=1,
            forbidden_terms=["证书墙", "讲标", "缩略图", "左屏", "评分", "Brief", "关键图示"],
        )

        self.assertEqual("deck_customer_visible_safety_gate.v1", report["schema_version"])
        self.assertEqual("customer_visible_safety", report["gate"])
        self.assertEqual("rework_required", report["status"])
        self.assertTrue(report["blocks_delivery"])
        first = report["findings"][0]
        for key in ("term", "scope", "package_path", "excerpt"):
            self.assertIn(key, first)
        self.assertEqual(report["summary"]["p0_count"], len(report["findings"]))

    def test_forbidden_terms_load_default_workspace_and_cli_extra(self) -> None:
        workspace = self.temp_dir / "workspace"
        run_dir = self.temp_dir / "run"
        (workspace / "quality").mkdir(parents=True)
        (run_dir / "quality").mkdir(parents=True)
        (workspace / "quality" / "forbidden_terms.md").write_text("# comment\n客户暗号\n", encoding="utf-8")
        (run_dir / "quality" / "forbidden_terms.md").write_text("本轮禁词\n", encoding="utf-8")
        write_json(run_dir / "request.json", {"run_id": "run", "workspace": str(workspace)})

        terms = load_customer_visible_forbidden_terms(run_dir, extra_terms=["临时禁词"])

        self.assertIn("证书墙", terms)
        self.assertIn("客户暗号", terms)
        self.assertIn("本轮禁词", terms)
        self.assertIn("临时禁词", terms)

    def test_delivery_cli_writes_customer_visible_safety_gate(self) -> None:
        run_dir = self.temp_dir / "run-cli"
        run_dir.mkdir()
        write_json(run_dir / "request.json", {"run_id": "run-cli", "run_mode": "fixture"})
        write_json(
            run_dir / "preview_manifest.json",
            {"run_id": "run-cli", "pages": [{"page_id": "p1", "decision": "approved"}]},
        )
        pptx = run_dir / "unsafe.pptx"
        _write_rich_pptx(pptx)

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deck_master.py"),
                "quality-gate",
                "--run-dir",
                str(run_dir),
                "--run-mode",
                "fixture",
                "--dev-allow-unsetup",
                "delivery",
                "--artifact",
                str(pptx),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("delivery", payload["gate"])
        safety_path = run_dir / "quality_reports" / "customer_visible_safety_gate.json"
        self.assertTrue(safety_path.exists())
        safety = json.loads(safety_path.read_text(encoding="utf-8"))
        self.assertTrue(safety["blocks_delivery"])


def _write_rich_pptx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as pptx:
        pptx.writestr("[Content_Types].xml", "<Types/>")
        pptx.writestr(
            "docProps/core.xml",
            "<cp:coreProperties xmlns:cp=\"x\"><dc:title xmlns:dc=\"x\">Brief</dc:title></cp:coreProperties>",
        )
        pptx.writestr(
            "ppt/slides/slide1.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:nvSpPr><p:cNvPr id="1" name="关键图示"/></p:nvSpPr>
      <p:txBody><a:p><a:r><a:t>客户正文包含证书墙</a:t></a:r></a:p></p:txBody>
    </p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
        )
        pptx.writestr(
            "ppt/notesSlides/notesSlide1.xml",
            "<p:notes xmlns:p=\"x\" xmlns:a=\"x\"><a:t>内部讲标路径</a:t></p:notes>",
        )
        pptx.writestr(
            "ppt/slideMasters/slideMaster1.xml",
            "<p:sldMaster xmlns:p=\"x\" xmlns:a=\"x\"><a:t>缩略图</a:t></p:sldMaster>",
        )
        pptx.writestr(
            "ppt/slideLayouts/slideLayout1.xml",
            "<p:sldLayout xmlns:p=\"x\" xmlns:a=\"x\"><a:t>左屏</a:t></p:sldLayout>",
        )
        pptx.writestr(
            "ppt/charts/chart1.xml",
            "<c:chartSpace xmlns:c=\"x\" xmlns:a=\"x\"><a:t>评分</a:t></c:chartSpace>",
        )


if __name__ == "__main__":
    unittest.main()
