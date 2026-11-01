"""File-only adapters for native compilation, rendering and readback."""
import json
from pathlib import Path

from .compiler import CompileOptions, SvgInput, compile_deck
from .compiler.svg import parse_svg
from .render import readback, render_deck, resolve_fonts
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
