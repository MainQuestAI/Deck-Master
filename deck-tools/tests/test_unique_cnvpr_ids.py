"""Duplicate cNvPr ids are invalid on a slide and make the 形状-N fallback collide.

The package is synthetic. Slide 1 is a shape plus a table that share id 4, with a
grouped shape whose id is the numeric form 04. Slide 2 is a picture plus a table
that share id 6. Slide 3 already has unique ids. A layout part repeats id 4 and
must stay untouched: only slide parts are renumbered.
"""
import io
import json
import subprocess
import sys
import zipfile

from lxml import etree

from deck_tools.sanitize import attach_hint_findings, pptx

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _xml(body):
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{body}'


def _slide(body, timing):
    return _xml(
        f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}">'
        f"<p:cSld><p:spTree>{body}</p:spTree></p:cSld>{timing}</p:sld>"
    )


def _tree(identity):
    return (
        f'<p:nvGrpSpPr><p:cNvPr id="{identity}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr/>"
    )


def _shape(identity, text, title=""):
    title_attr = f' title="{title}"' if title else ""
    return (
        "<p:sp><p:nvSpPr>"
        f'<p:cNvPr id="{identity}"{title_attr}/><p:cNvSpPr/><p:nvPr/>'
        "</p:nvSpPr><p:spPr/>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody>"
        "</p:sp>"
    )


def _table(identity, text):
    return (
        "<p:graphicFrame><p:nvGraphicFramePr>"
        f'<p:cNvPr id="{identity}"/><p:cNvGraphicFramePr/><p:nvPr/>'
        "</p:nvGraphicFramePr><p:xfrm/>"
        f'<a:graphic><a:graphicData uri="urn:example:table">'
        f'<a:cNvPr id="{identity}"/>'
        f"<a:t>{text}</a:t>"
        "</a:graphicData></a:graphic></p:graphicFrame>"
    )


def _picture(identity):
    return (
        "<p:pic><p:nvPicPr>"
        f'<p:cNvPr id="{identity}"><a:hlinkClick r:id="rId9"/></p:cNvPr>'
        "<p:cNvPicPr/><p:nvPr/></p:nvPicPr>"
        '<p:blipFill><a:blip r:embed="rId1"/></p:blipFill><p:spPr/></p:pic>'
    )


def synthetic_duplicate_cnvpr_pptx():
    """Two colliding pages plus one already-unique page and an untouched layout."""
    slide1 = _slide(
        _tree("1")
        + _shape("4", "shape-dup")
        + _table("4", "table-dup")
        + "<p:grpSp>"
        + _tree("4")
        + _shape("04", "renumbered-target")
        + "</p:grpSp>"
        + "<p:cxnSp><p:nvCxnSpPr>"
        + '<p:cNvPr id="5" title="角色"/>'
        + '<p:cNvCxnSpPr><a:stCxn id="4" idx="2"/><a:endCxn id="04" idx="3"/></p:cNvCxnSpPr>'
        + "<p:nvPr/></p:nvCxnSpPr><p:spPr/></p:cxnSp>",
        "<p:timing>"
        '<p:tnLst><p:par><p:cTn><p:childTnLst><p:set><p:cBhvr><p:tgtEl>'
        '<p:spTgt spid="4"/>'
        '<p:spTgt spid="04"><p:subSp spid="04"/></p:spTgt>'
        '<p:inkTgt spid="04"/>'
        "</p:tgtEl></p:cBhvr></p:set></p:childTnLst></p:cTn></p:par></p:tnLst>"
        "<p:bldLst>"
        '<p:bldP spid="4"/>'
        '<p:bldP spid="04"/>'
        '<p:bldDgm spid="04"/>'
        '<p:bldGraphic spid="04"/>'
        '<p:bldOleChart spid="04"/>'
        "</p:bldLst></p:timing>",
    )
    slide2 = _slide(
        _tree("1") + _picture("6") + _table("6", "picture-table"),
        '<p:timing><p:tnLst><p:par><p:cTn><p:childTnLst><p:set><p:cBhvr><p:tgtEl>'
        '<p:spTgt spid="6"/>'
        "</p:tgtEl></p:cBhvr></p:set></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>",
    )
    slide3 = _slide(
        _tree("1")
        + _shape("8", "unique-a")
        + _shape("9", "unique-b")
        + "<p:cxnSp><p:nvCxnSpPr>"
        + '<p:cNvPr id="3"/>'
        + '<p:cNvCxnSpPr><a:stCxn id="8" idx="1"/><a:endCxn id="9" idx="0"/></p:cNvCxnSpPr>'
        + "<p:nvPr/></p:nvCxnSpPr><p:spPr/></p:cxnSp>",
        "",
    )
    layout = _xml(
        f'<p:sldLayout xmlns:p="{P}" xmlns:a="{A}">'
        "<p:cSld><p:spTree>"
        + _tree("4")
        + _shape("4", "layout-shape")
        + "</p:spTree></p:cSld></p:sldLayout>"
    )
    presentation = _xml(
        f'<p:presentation xmlns:p="{P}" xmlns:r="{R}">'
        '<p:sldIdLst>'
        '<p:sldId id="256" r:id="rId1"/>'
        '<p:sldId id="257" r:id="rId2"/>'
        '<p:sldId id="258" r:id="rId3"/>'
        "</p:sldIdLst></p:presentation>"
    )
    rels = _xml(
        f'<Relationships xmlns="{REL}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide3.xml"/>'
        "</Relationships>"
    )
    types = _xml(
        f'<Types xmlns="{CT}">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        '<Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        '<Override PartName="/ppt/slides/slide3.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        "</Types>"
    )
    parts = {
        "[Content_Types].xml": types,
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": rels,
        "ppt/slides/slide1.xml": slide1,
        "ppt/slides/slide2.xml": slide2,
        "ppt/slides/slide3.xml": slide3,
        "ppt/slideLayouts/slideLayout1.xml": layout,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in parts.items():
            archive.writestr(name, body.encode("utf-8"))
    return buffer.getvalue()


def _local(element):
    return element.tag.rsplit("}", 1)[-1]


def _slide_root(package, name):
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        return etree.fromstring(archive.read(name))


def _cnvprs(root):
    return [element for element in root.iter() if _local(element) == "cNvPr"]


def _direct_cnvpr(element):
    for child in element:
        for grand in child:
            if _local(grand) == "cNvPr":
                return grand
    return None


def _by_text(root, text):
    owners = {"sp", "pic", "cxnSp", "graphicFrame", "grpSp"}
    for node in root.iter():
        if _local(node) == "t" and node.text == text:
            current = node.getparent()
            while current is not None:
                if _local(current) in owners:
                    ident = _direct_cnvpr(current)
                    if ident is not None:
                        return ident
                current = current.getparent()
    raise AssertionError(text)


def _attr_values(root, local_name, attr):
    return [
        element.get(attr)
        for element in root.iter()
        if _local(element) == local_name
    ]


def _assert_unique_fallback_names(root, titled=None):
    titled = titled or {}
    ids = []
    for node in _cnvprs(root):
        ids.append(node.get("id"))
        expected = titled.get(node.get("id"), "形状-" + node.get("id"))
        assert node.get("name") == expected
        assert node.get("title") == node.get("name")
    assert len(ids) == len(set(ids))
    assert all(ids)


def test_duplicate_cnvpr_ids_become_unique_and_references_follow():
    found = []
    cleaned = pptx(synthetic_duplicate_cnvpr_pptx(), "deck.pptx", findings=found)
    slide1 = _slide_root(cleaned, "ppt/slides/slide1.xml")
    slide2 = _slide_root(cleaned, "ppt/slides/slide2.xml")
    slide3 = _slide_root(cleaned, "ppt/slides/slide3.xml")
    layout = _slide_root(cleaned, "ppt/slideLayouts/slideLayout1.xml")
    presentation = _slide_root(cleaned, "ppt/presentation.xml")

    shape = _by_text(slide1, "shape-dup")
    table = _by_text(slide1, "table-dup")
    target = _by_text(slide1, "renumbered-target")
    assert shape.get("id") == "4"
    assert table.get("id") != "4"
    assert target.get("id") not in {"4", "04"}
    assert _attr_values(slide1, "stCxn", "id") == ["4"]
    assert _attr_values(slide1, "stCxn", "idx") == ["2"]
    assert _attr_values(slide1, "endCxn", "id") == [target.get("id")]
    assert _attr_values(slide1, "endCxn", "idx") == ["3"]
    assert "04" not in _attr_values(slide1, "spTgt", "spid")
    assert "4" in _attr_values(slide1, "spTgt", "spid")
    assert target.get("id") in _attr_values(slide1, "spTgt", "spid")
    for local_name in ("subSp", "inkTgt", "bldDgm", "bldGraphic", "bldOleChart"):
        assert _attr_values(slide1, local_name, "spid") == [target.get("id")]
    assert _attr_values(slide1, "bldP", "spid") == ["4", target.get("id")]
    drawing = [
        element for element in _cnvprs(slide1)
        if element.tag == f"{{{A}}}cNvPr"
    ]
    assert len(drawing) == 1 and drawing[0].get("id") not in {"4", "04"}
    group_ids = [
        _direct_cnvpr(element).get("id")
        for element in slide1.iter()
        if _local(element) == "grpSp"
    ]
    assert group_ids and "4" not in group_ids
    _assert_unique_fallback_names(slide1, titled={"5": "角色"})

    picture = _direct_cnvpr(next(element for element in slide2.iter() if _local(element) == "pic"))
    picture_table = _by_text(slide2, "picture-table")
    assert picture.get("id") == "6"
    assert picture_table.get("id") != "6"
    assert _attr_values(slide2, "spTgt", "spid") == ["6"]
    blip = next(element for element in slide2.iter() if _local(element) == "blip")
    link = next(element for element in slide2.iter() if _local(element) == "hlinkClick")
    assert blip.get(f"{{{R}}}embed") == "rId1"
    assert link.get(f"{{{R}}}id") == "rId9"
    _assert_unique_fallback_names(slide2)

    assert [node.get("id") for node in _cnvprs(slide3)] == ["1", "8", "9", "3"]
    assert _attr_values(slide3, "stCxn", "id") == ["8"]
    assert _attr_values(slide3, "stCxn", "idx") == ["1"]
    assert _attr_values(slide3, "endCxn", "id") == ["9"]
    _assert_unique_fallback_names(slide3)

    assert [node.get("id") for node in _cnvprs(layout)] == ["4", "4"]
    assert [node.get("name") for node in _cnvprs(layout)] == ["形状-4", "形状-4"]
    assert [element.get("id") for element in presentation.iter() if _local(element) == "sldId"] == [
        "256", "257", "258",
    ]

    assert [item["part"] for item in found] == [
        "ppt/slides/slide1.xml",
        "ppt/slides/slide2.xml",
    ]
    assert [item["ids"] for item in found] == [["4", "04"], ["6"]]
    assert all(item["code"] == "duplicate_cnvpr_id" and item["level"] == "hint" for item in found)

    report = {"status": "pass", "findings": []}
    attach_hint_findings(report, found)
    assert report["status"] == "pass"
    assert report["findings"] == []
    assert [item["code"] for item in report["warnings"]] == ["duplicate_cnvpr_id", "duplicate_cnvpr_id"]
    failing = {"status": "fail", "findings": [{"code": "missing_visible_atom"}]}
    attach_hint_findings(failing, found)
    assert failing["status"] == "fail"
    assert [item["code"] for item in failing["findings"]] == ["missing_visible_atom"]
    untouched = {"status": "pass", "findings": []}
    attach_hint_findings(untouched, [])
    assert "warnings" not in untouched

    again = []
    second = pptx(cleaned, "deck.pptx", findings=again)
    assert again == []
    for name in ("ppt/slides/slide1.xml", "ppt/slides/slide2.xml", "ppt/slides/slide3.xml"):
        before = _cnvprs(_slide_root(cleaned, name))
        after = _cnvprs(_slide_root(second, name))
        assert [(node.get("id"), node.get("name")) for node in before] == [
            (node.get("id"), node.get("name")) for node in after
        ]


def test_sanitize_cli_emits_hint_without_failing(tmp_path):
    source = tmp_path / "in.pptx"
    output = tmp_path / "out.pptx"
    source.write_bytes(synthetic_duplicate_cnvpr_pptx())
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"path": str(source), "output": str(output)}))
    result = subprocess.run(
        [sys.executable, "-m", "deck_tools", "sanitize", str(job)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["findings"]["status"] == "pass"
    assert payload["findings"]["findings"] == []
    assert {item["code"] for item in payload["findings"]["warnings"]} == {"duplicate_cnvpr_id"}
    assert all(item["level"] == "hint" for item in payload["findings"]["warnings"])
    assert output.is_file()
