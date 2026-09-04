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
from quality.gate_runner import evaluate_render_gate
from quality.pptx_audit import audit_pptx
from runtime.run_state import write_json


class CustomerVisibleSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_pptx_audit_scans_customer_visible_package_text_only(self) -> None:
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
        self.assertIn("doc_props", scopes)
        self.assertIn("chart", scopes)
        self.assertNotIn("slide_master", scopes)
        self.assertNotIn("slide_layout", scopes)
        self.assertFalse(any(hit["term"] == "关键图示" for hit in audit["forbidden_hits"]))
        self.assertFalse(any(hit["term"] == "未使用图表" for hit in audit["forbidden_hits"]))
        chart_hits = [hit for hit in audit["forbidden_hits"] if hit["scope"] == "chart"]
        self.assertEqual([1], [hit["slide_number"] for hit in chart_hits])

    def test_pptx_audit_uses_presentation_order_for_page_roles(self) -> None:
        pptx = self.temp_dir / "reordered.pptx"
        _write_reordered_pptx(pptx)

        audit = audit_pptx(pptx, page_roles={1: "cover", 2: "content"})

        self.assertEqual([], audit["sparse_pages"])
        self.assertEqual([1, 2], [slide["slide_number"] for slide in audit["slides"]])

    def test_customer_visible_safety_gate_blocks_with_structured_findings(self) -> None:
        pptx = self.temp_dir / "unsafe.pptx"
        _write_rich_pptx(pptx)

        report = evaluate_customer_visible_safety_gate(
            "run-unsafe",
            pptx,
            expected_pages=1,
            forbidden_terms=["证书墙", "讲标", "缩略图", "左屏", "评分", "Brief", "关键图示", "未使用图表"],
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
        for business_term in ("制作", "讲标", "投标", "评审", "评分", "内部", "Brief"):
            self.assertNotIn(business_term, terms)
        self.assertIn("客户暗号", terms)
        self.assertIn("本轮禁词", terms)
        self.assertIn("临时禁词", terms)

    def test_workspace_terms_can_tighten_business_language_when_needed(self) -> None:
        run_dir = self.temp_dir / "run"
        (run_dir / "quality").mkdir(parents=True)
        (run_dir / "quality" / "forbidden_terms.md").write_text("讲标\n", encoding="utf-8")

        terms = load_customer_visible_forbidden_terms(run_dir)

        self.assertIn("讲标", terms)

    def test_pptx_audit_allows_sparse_structural_page_roles(self) -> None:
        pptx = self.temp_dir / "visual-role.pptx"
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr(
                "ppt/slides/slide1.xml",
                """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:pic/></p:spTree></p:cSld>
</p:sld>
""",
            )

        default = audit_pptx(pptx)
        role_aware = audit_pptx(pptx, page_roles={1: "visual"})

        self.assertEqual(1, len(default["possible_full_slide_images"]))
        self.assertEqual([], role_aware["possible_full_slide_images"])

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

    def test_render_cli_uses_manifest_page_role_for_visual_page(self) -> None:
        run_dir = self.temp_dir / "run-role"
        run_dir.mkdir()
        write_json(run_dir / "request.json", {"run_id": "run-role", "run_mode": "fixture"})
        write_json(
            run_dir / "preview_manifest.json",
            {"run_id": "run-role", "pages": [{"page_id": "p1", "order": 1, "page_role": "visual"}]},
        )
        pptx = run_dir / "visual.pptx"
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr(
                "ppt/slides/slide1.xml",
                """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:pic/></p:spTree></p:cSld>
</p:sld>
""",
            )

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
                "render",
                "--artifact",
                str(pptx),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads((run_dir / "quality_reports" / "render_gate.json").read_text(encoding="utf-8"))
        self.assertEqual([], report["audit"]["possible_full_slide_images"])
        self.assertEqual("visual", report["audit"]["slides"][0]["page_role"])
        self.assertEqual("visual.pptx", report["artifact_path"])
        self.assertEqual("visual.pptx", report["artifact_run_relative"])
        self.assertEqual(64, len(report["artifact_sha256"]))

    def test_production_render_gate_blocks_missing_page_role_mapping(self) -> None:
        run_dir = self.temp_dir / "run-missing-role"
        run_dir.mkdir()
        write_json(run_dir / "request.json", {"run_id": "run-missing-role", "run_mode": "production"})
        pptx = run_dir / "missing-role.pptx"
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr(
                "ppt/slides/slide1.xml",
                """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Production page text without role metadata.</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
            )

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deck_master.py"),
                "quality-gate",
                "--run-dir",
                str(run_dir),
                "--run-mode",
                "production",
                "--dev-allow-unsetup",
                "render",
                "--artifact",
                str(pptx),
                "--expected-pages",
                "1",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads((run_dir / "quality_reports" / "render_gate.json").read_text(encoding="utf-8"))
        self.assertTrue(report["blocks_delivery"])
        self.assertIn(1, report["audit"]["missing_page_roles"])

    def test_standard_fixture_without_page_role_does_not_block_role_contract(self) -> None:
        run_dir = self.temp_dir / "run-standard-role-migration"
        run_dir.mkdir()
        write_json(run_dir / "request.json", {"run_id": "run-standard-role-migration", "run_mode": "fixture"})
        pptx = run_dir / "standard.pptx"
        with zipfile.ZipFile(pptx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
            package.writestr(
                "ppt/slides/slide1.xml",
                """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Standard builder migration keeps this page on the existing content path without role metadata.</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
            )

        report = evaluate_render_gate(
            "run-standard-role-migration",
            pptx,
            expected_pages=1,
            run_dir=run_dir,
        )

        self.assertFalse(report["audit"]["missing_page_roles"])
        self.assertFalse(any(item["finding_id"].endswith("page_role_missing") for item in report["findings"]))


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
            "ppt/presentation.xml",
            """
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>
""",
        )
        pptx.writestr(
            "ppt/_rels/presentation.xml.rels",
            """
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>
""",
        )
        pptx.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            """
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdChart1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/>
</Relationships>
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
        pptx.writestr(
            "ppt/charts/chart2.xml",
            "<c:chartSpace xmlns:c=\"x\" xmlns:a=\"x\"><a:t>未使用图表</a:t></c:chartSpace>",
        )


def _write_reordered_pptx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as pptx:
        pptx.writestr("[Content_Types].xml", "<Types/>")
        pptx.writestr(
            "ppt/presentation.xml",
            """
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst>
    <p:sldId id="257" r:id="rId2"/>
    <p:sldId id="256" r:id="rId1"/>
  </p:sldIdLst>
</p:presentation>
""",
        )
        pptx.writestr(
            "ppt/_rels/presentation.xml.rels",
            """
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>
</Relationships>
""",
        )
        pptx.writestr(
            "ppt/slides/slide1.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>This content slide has enough visible words to avoid sparse detection when it is mapped to the second display page role.</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
        )
        pptx.writestr(
            "ppt/slides/slide2.xml",
            """
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>Project cover</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>
""",
        )


if __name__ == "__main__":
    unittest.main()
