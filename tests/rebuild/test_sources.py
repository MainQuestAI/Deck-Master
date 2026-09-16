"""T03 sources tests: material reading across formats (AC-C01, AC-C08).

Every format proves it can locate the relevant copy; missing tools report
``needs_tool`` with the format named — never an empty success. Image pages
dispatch to visual reading (pending_visual).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from deck_master.sources import read_source, tail_constraint


def _write(tmp_path: Path, name: str, content) -> Path:
    path = tmp_path / name
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


MATERIAL_TEXT = "\n".join(
    [
        "# 季度处理对照",
        "第一季度人工处理 3120 单，条件自动处理 480 单。",
        "",
        "（材料尾部约束，关键）本材料为合成输入，不可回写。",
    ]
)


def test_txt_and_md_reading_keep_positions_and_hash(tmp_path: Path) -> None:
    for name in ("brief.txt", "brief.md"):
        path = _write(tmp_path, name, MATERIAL_TEXT)
        extract = read_source(path)
        assert extract.status == "read"
        assert extract.original_sha256 is not None
        assert len(extract.original_sha256) == 64
        locators = [item["locator"] for item in extract.locators]
        assert "L1" in locators and "L3" in locators
        # AC-C01: the tail constraint is the last content line and stays in the real input.
        assert "不可回写" in tail_constraint(extract)


def test_json_reading_keeps_numbers_zero_and_nesting(tmp_path: Path) -> None:
    payload = {
        "quarters": [
            {"q": "Q1", "manual": 3120, "auto": 480, "ratio": 0.0},
            {"q": "Q2", "manual": 2690, "auto": 910},
        ],
        "unit": "单",
    }
    path = _write(tmp_path, "data.json", json.dumps(payload, ensure_ascii=False))
    extract = read_source(path)
    assert extract.status == "read"
    values = {item["locator"]: item["text"] for item in extract.locators}
    assert values["/quarters/0/manual"] == "3120"
    assert values["/quarters/0/ratio"] == "0.0"
    assert "/quarters/1/auto" in values


def test_invalid_json_is_explicit_not_empty_success(tmp_path: Path) -> None:
    path = _write(tmp_path, "broken.json", b"{not json")
    extract = read_source(path)
    assert extract.status == "needs_tool"
    assert "invalid JSON" in extract.detail
    assert extract.text == ""


def _pdf_stream(text: str) -> bytes:
    return f"BT /F1 14 Tf 72 720 Td ({text}) Tj ET\n".encode("ascii")


def _minimal_pdf(text: str) -> bytes:
    stream = _pdf_stream(text)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer << /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref "
        + str(xref_at).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)


def test_pdf_reading(tmp_path: Path) -> None:
    path = _write(tmp_path, "report.pdf", _minimal_pdf("Total 3120"))
    extract = read_source(path)
    if extract.status == "needs_tool":
        assert "pdftotext" in extract.detail
        return
    assert "3120" in extract.text
    locators = [item["locator"] for item in extract.locators]
    assert "page-1" in locators


def test_pdf_without_tool_needs_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import deck_master.sources as sources

    monkeypatch.setattr(sources.shutil, "which", lambda name: None)
    path = _write(tmp_path, "report.pdf", _minimal_pdf("Total 3120"))
    extract = read_source(path)
    assert extract.status == "needs_tool"
    assert "pdftotext" in extract.detail
    assert extract.original_sha256 is not None


def test_docx_reading(tmp_path: Path) -> None:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{ns}"><w:body>'
        "<w:p><w:r><w:t>季度处理量对照</w:t></w:r></w:p>"
        "<w:tbl>"
        "<w:tr>"
        "<w:tc><w:p><w:r><w:t>季度</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>3120</w:t></w:r></w:p></w:tc>"
        "</w:tr>"
        "</w:tbl>"
        "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        "</Types>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
    path = _write(tmp_path, "note.docx", buffer.getvalue())
    extract = read_source(path)
    assert extract.status == "read"
    texts = [item.get("text", "") for item in extract.locators]
    assert any("季度处理量对照" in text for text in texts)
    assert any("3120" in text for text in texts)
    assert any(item.get("kind") == "table" for item in extract.locators)


def test_pptx_reading(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "幻灯片一：条件自动处理"
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1)).table
    table.cell(0, 0).text = "季度"
    table.cell(0, 1).text = "处理量"
    table.cell(1, 0).text = "第一季度"
    table.cell(1, 1).text = "3120单"
    path = tmp_path / "deck.pptx"
    presentation.save(str(path))
    extract = read_source(path)
    assert extract.status == "read"
    locators = [item["locator"] for item in extract.locators]
    assert "slide-1" in locators
    assert "3120单" in extract.text


def test_image_dispatches_to_visual_reading(tmp_path: Path) -> None:
    path = _write(tmp_path, "photo.png", b"\x89PNG\r\n\x1a\nplaceholder-bytes")
    extract = read_source(path)
    assert extract.status == "pending_visual"
    assert extract.detail
    assert extract.original_sha256 is not None


def test_unknown_format_names_itself(tmp_path: Path) -> None:
    path = _write(tmp_path, "data.xyz", b"whatever")
    extract = read_source(path)
    assert extract.status == "needs_tool"
    assert ".xyz" in extract.detail


def test_tail_constraint_is_last_content(tmp_path: Path) -> None:
    text = "开头说明\n中间正文\n（尾部约束）不得包含真实客户名。"
    path = _write(tmp_path, "brief.txt", text)
    extract = read_source(path)
    assert tail_constraint(extract).endswith("不得包含真实客户名。")


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        read_source("/nonexistent/material.txt")


def test_hash_matches_file_bytes(tmp_path: Path) -> None:
    path = _write(tmp_path, "brief.txt", MATERIAL_TEXT)
    extract = read_source(path)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert extract.original_sha256 == expected
