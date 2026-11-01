"""File-only adapters for native compilation, rendering and readback."""
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .compiler import CompileOptions, SvgInput, compile_deck
from .compiler.svg import parse_svg
from .render import readback, render_deck, resolve_fonts, _table_readback
from .atoms import visible_atoms
from .sanitize import pptx


def projection(page):
    # Rust calls nested bullet entries children; the retained reader uses items.
    from copy import deepcopy
    content = deepcopy(page["content"])
    def nested(items):
        for item in items:
            if "children" in item:
                item["items"] = item.pop("children")
                nested(item["items"])
    for block in content.get("body_blocks", []):
        if block["type"] == "bullets":
            nested(block.get("items", []))
    return {"page_id": page["id"], "customer_visible": content,
            "speaker_notes": page.get("notes", ""), "visual_spec": {}}


def compile_job(job, *, preview=False):
    pages = job["pages"]
    canvas = job["canvas"]
    assets = job.get("assets", {})
    parsed = [parse_svg(Path(p["svg"]).read_bytes(), page_id=p["id"], assets=assets)
              for p in pages]
    fonts = resolve_fonts(parsed)
    # Validate requested fonts even when a page contains no text in that family.
    for name in job.get("fonts", []):
        fonts.update(resolve_fonts([{"shapes": [{"kind": "text", "font_family": name, "bold": False}]}]))
    output = Path(job["output"])
    result = compile_deck(
        [SvgInput(p["id"], Path(p["svg"]), p.get("notes", "")) for p in pages],
        CompileOptions(width_px=canvas["slide_width_in"] * 96,
                       height_px=canvas["slide_height_in"] * 96,
                       fonts=fonts, assets={p["id"]: assets for p in pages}), output)
    manifest = json.loads(result.manifest_path.read_text())
    findings = readback(result.pptx_path, manifest["pages"], [projection(p) for p in pages])
    answer = {"pptx": str(result.pptx_path), "findings": findings}
    if job.get("humanizer"):
        _verify_humanized_text(result.pptx_path, pages, manifest["pages"])
        answer["humanizer"] = {"stage": "pptx", "text_readback": "equal"}
    if preview:
        images = render_deck(result.pptx_path, output / "render", fonts=fonts)
        if len(images) != len(pages):
            raise RuntimeError("渲染页数与输入不一致；请检查 LibreOffice 输出")
        answer["preview"] = str(images[0])
    else:
        cleaned = pptx(result.pptx_path.read_bytes(), "deck.pptx",
                       notes=[{"page_id": p["id"], "notes": p.get("notes", "")} for p in pages])
        result.pptx_path.write_bytes(cleaned)
    return answer


def _verify_humanized_text(path, pages, sources):
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
          "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        for index, (page, source) in enumerate(zip(pages, sources, strict=True), 1):
            root = _table_readback(ET.fromstring(archive.read(f"ppt/slides/slide{index}.xml")), source)
            actual = {}
            for shape in root.findall(".//p:sp", ns):
                identity = shape.find("p:nvSpPr/p:cNvPr", ns)
                text = "".join(node.text or "" for node in shape.findall(".//a:t", ns))
                if text and identity is not None:
                    name = identity.get("name")
                    actual[name] = actual.get(name, "") + text
            expected = {a["atom_id"]: a["text"] for a in visible_atoms(projection(page)) if a.get("text")}
            if actual != expected:
                raise RuntimeError(f"{page['id']}：PPT 文字与 Humanizer 处理后的正文不同；请按最新正文重建 SVG")
