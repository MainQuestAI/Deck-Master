"""Native PPTX generation, OOXML postprocessing, and single-page rendering."""

from __future__ import annotations

from pathlib import Path
import posixpath
import struct
import sys
import tempfile
import zipfile
import zlib

from lxml import etree
from PIL import Image, ImageDraw

from ..render import NeedsTool, RendererError, executable, run
from .plan import (
    ICONS,
    NS,
    _resolve_native_fonts,
    emu_per_px,
    page_directory,
    read_json,
    validate_plan,
    write_json,
)
from .readback import detect_missing_visual_objects


def native_pptx_dir():
    installed = Path(sys.prefix).parent / "native-pptx"
    development = Path(__file__).resolve().parents[3] / "native-pptx"
    for directory in (installed, development):
        if (directory / "render.cjs").is_file():
            return directory
    raise NeedsTool("找不到 native-pptx；请重新运行安装脚本")


def _transparent_png():
    """1×1 transparent PNG kept only when an SVG companion cannot be rendered."""

    def chunk(kind, payload):
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def _part_name(source_part, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _picture_extent(element):
    """Display size in EMU of the picture that owns this blip, or None."""
    pic = element
    while pic is not None and etree.QName(pic).localname != "pic":
        pic = pic.getparent()
    if pic is None:
        return None
    ext = pic.find(".//a:xfrm/a:ext", NS)
    if ext is None:
        return None
    try:
        cx, cy = int(ext.get("cx")), int(ext.get("cy"))
    except (TypeError, ValueError):
        return None
    if cx <= 0 or cy <= 0:
        return None
    return cx, cy


def _svg_companion_pngs(files):
    """(png part, svg part, extent EMU) for each blip that falls back from SVG to PNG."""
    found = {}
    for name, data in files.items():
        if not name.startswith("ppt/slides/_rels/slide") or not name.endswith(".xml.rels"):
            continue
        source = name.replace("/_rels/", "/")[: -len(".rels")]
        rels = etree.fromstring(data)
        targets = {}
        for rel in rels:
            rid = rel.get("Id")
            target = rel.get("Target")
            if rid and target and rel.get("TargetMode") != "External":
                targets[rid] = _part_name(source, target)
        slide = etree.fromstring(files[source])
        for element in slide.iter():
            if etree.QName(element).localname != "blip":
                continue
            png_rid = None
            for key, value in element.attrib.items():
                if etree.QName(key).localname == "embed":
                    png_rid = value
            svg_rid = None
            for child in element.iter():
                if etree.QName(child).localname != "svgBlip":
                    continue
                for key, value in child.attrib.items():
                    if etree.QName(key).localname == "embed":
                        svg_rid = value
            png_part = targets.get(png_rid)
            svg_part = targets.get(svg_rid)
            if not png_part or not svg_part or svg_part not in files:
                continue
            if png_part.lower().endswith(".png") and svg_part.lower().endswith(".svg"):
                found.setdefault(png_part, (svg_part, _picture_extent(element)))
    return [(png, svg, extent) for png, (svg, extent) in found.items()]


def _svg_png_width(extent):
    """Pixel width for the fallback. Height follows the SVG."""
    if extent and extent[0] > 0:
        return max(1, round(extent[0] / 914400 * 192))
    return 256


def _render_svg_png(svg, extent):
    width = _svg_png_width(extent)
    with tempfile.TemporaryDirectory(prefix="deck-svg-png-") as temp:
        source = Path(temp) / "icon.svg"
        target = Path(temp) / "icon.png"
        source.write_bytes(svg)
        run([executable("rsvg-convert"), "-w", str(width), "-o", str(target), str(source)])
        data = target.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RendererError("rsvg-convert 没有写出 PNG")
    return data


def _repair_svg_png_companions(files):
    """Render each SVG companion. A failed render keeps the previous bytes."""
    warnings = []
    placeholder = None
    for name, svg_part, extent in _svg_companion_pngs(files):
        svg = files.get(svg_part)
        if not svg:
            continue
        try:
            files[name] = _render_svg_png(svg, extent)
            continue
        except NeedsTool:
            detail = "缺少 rsvg-convert，这张 SVG 的备用图保留原来的占位。装好后重新构建。"
        except (RendererError, OSError):
            detail = "这张 SVG 的备用图没能渲染，已保留原来的占位。"
        warnings.append(
            {
                "level": "warning",
                "code": "svg_png_fallback",
                "part": name,
                "detail": detail,
            }
        )
        data = files.get(name)
        if data is None or data.startswith(b"\x89PNG\r\n\x1a\n") or not data.lstrip().startswith(b"<"):
            continue
        if placeholder is None:
            placeholder = _transparent_png()
        files[name] = placeholder
    return warnings


def postprocess(pptx_path, plans):
    with zipfile.ZipFile(pptx_path) as archive:
        # PptxGenJS emits an empty embeddings directory even without embedded files.
        files = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    for index, plan in enumerate(plans, 1):
        emu = emu_per_px(plan)
        name = f"ppt/slides/slide{index}.xml"
        root = etree.fromstring(files[name])
        root.find("p:cSld", NS).set("name", plan["page"])
        for para in root.findall(".//a:p", NS):
            for duplicate in para.findall("a:pPr", NS)[1:]:
                para.remove(duplicate)
        for cell in root.findall(".//a:tcPr", NS):
            if cell.get("anchor") == "mid":
                cell.set("anchor", "ctr")
        ops = {f"native_{i}": op for i, op in enumerate(plan["ops"])}
        for frame in root.findall(".//p:graphicFrame", NS):
            op = ops.get(frame.find("p:nvGraphicFramePr/p:cNvPr", NS).get("name"))
            if op is None or op["op"] != "table":
                continue
            for row, height in zip(frame.findall(".//a:tr", NS), op["row_heights"]):
                row.set("h", str(round(height * emu)))
            frame.find("p:xfrm/a:ext", NS).set("cy", str(round(op["bbox"][3] * emu)))
        for shape in root.findall(".//p:sp", NS):
            op = ops.get(shape.find("p:nvSpPr/p:cNvPr", NS).get("name"))
            if op is None or op["op"] != "shape":
                continue
            props = shape.find("p:spPr", NS)
            if op["type"] == "custom":
                for old in list(props):
                    if etree.QName(old).localname in ("prstGeom", "custGeom"):
                        props.remove(old)
                geometry = etree.Element(f'{{{NS["a"]}}}custGeom')
                for tag in ("avLst", "gdLst", "ahLst", "cxnLst"):
                    etree.SubElement(geometry, f'{{{NS["a"]}}}{tag}')
                etree.SubElement(geometry, f'{{{NS["a"]}}}rect', l="0", t="0", r="r", b="b")
                paths = etree.SubElement(geometry, f'{{{NS["a"]}}}pathLst')
                path = etree.SubElement(
                    paths,
                    f'{{{NS["a"]}}}path',
                    w=str(round(op["bbox"][2] * emu)),
                    h=str(round(op["bbox"][3] * emu)),
                    fill="none" if op.get("fill", "none") == "none" else "norm",
                    stroke="1",
                )
                for i, (x, y) in enumerate(op["points"]):
                    command = etree.SubElement(path, f'{{{NS["a"]}}}{"moveTo" if i == 0 else "lnTo"}')
                    etree.SubElement(
                        command,
                        f'{{{NS["a"]}}}pt',
                        x=str(round(x * emu)),
                        y=str(round(y * emu)),
                    )
                if op.get("closed"):
                    etree.SubElement(path, f'{{{NS["a"]}}}close')
                props.insert(1, geometry)
            elif op["type"] in ("rect", "roundRect") and op.get("radius") and min(op["bbox"][2:]) > 0:
                geometry = props.find("a:prstGeom", NS)
                geometry.set("prst", "roundRect")
                adjustments = geometry.find("a:avLst", NS)
                for child in list(adjustments):
                    adjustments.remove(child)
                radius = min(0.5, op["radius"] / min(op["bbox"][2:]))
                etree.SubElement(
                    adjustments,
                    f'{{{NS["a"]}}}gd',
                    name="adj",
                    fmla=f"val {round(radius * 100000)}",
                )
        files[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    root = etree.fromstring(files["ppt/presentation.xml"])
    notes = root.find("p:notesMasterIdLst", NS)
    if notes is not None:
        root.remove(notes)
        master = root.find("p:sldMasterIdLst", NS)
        root.insert(list(root).index(master) + 1 if master is not None else 0, notes)
    files["ppt/presentation.xml"] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    warnings = _repair_svg_png_companions(files)
    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return warnings


def generate(pages, output, *, mode):
    plans = [read_json(page["plan"]) for page in pages]
    # Adopted deck plans were validated on result; content drift is reported by readback.
    findings = []
    if mode == "single":
        findings = [validate_plan(plan, page) for plan, page in zip(plans, pages)]
    directory = native_pptx_dir()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="deck-native-") as temp:
        job = Path(temp) / "job.json"
        write_json(
            job,
            {
                "mode": mode,
                "pages": [{**p, "plan": str(Path(p["plan"]).resolve())} for p in pages],
                "output": str(output),
                "icons_dir": str(ICONS),
            },
        )
        run([executable("node"), str(directory / "render.cjs"), str(job)], cwd=directory)
    warnings = postprocess(output, plans)
    if warnings and mode == "single" and findings:
        findings[0].setdefault("warnings", []).extend(warnings)
    return output, findings, warnings


def render(job):
    from . import render_deck as package_render_deck

    page = job["page"]
    directory = (
        Path(job["output"]).resolve() if "output" in job else page_directory(job["work"], page["id"])
    )
    plans = [read_json(page["plan"])]
    resolved_fonts = _resolve_native_fonts(plans)
    pptx, findings, _warnings = generate([page], directory / "page.pptx", mode="single")
    # Isolated conversion avoids picking up PNGs from an earlier, longer deck.
    with tempfile.TemporaryDirectory(prefix="deck-native-render-") as temp:
        images = package_render_deck(pptx, temp, fonts=resolved_fonts)
        if len(images) != 1:
            raise RuntimeError("单页渲染没有得到一张 PNG")
        preview = directory / "render.png"
        with Image.open(images[0]) as image:
            image.save(preview)
    comparison = directory / "side-by-side.png"
    with Image.open(page["source_image"]) as source, Image.open(preview) as rendered:
        source = source.convert("RGB")
        rendered = rendered.convert("RGB").resize(source.size)
        combined = Image.new("RGB", (source.width * 2, source.height + 30), "white")
        combined.paste(source, (0, 30))
        combined.paste(rendered, (source.width, 30))
        labels = ImageDraw.Draw(combined)
        labels.text((10, 8), "source", fill="black")
        labels.text((source.width + 10, 8), "render", fill="black")
        combined.save(comparison)
    visual_warnings = detect_missing_visual_objects(page.get("source_image"), preview, plans[0])
    if visual_warnings:
        findings[0].setdefault("warnings", []).extend(visual_warnings)
    return {
        "pptx": str(pptx),
        "render_png": str(preview),
        "side_by_side": str(comparison),
        "findings": findings[0],
    }
