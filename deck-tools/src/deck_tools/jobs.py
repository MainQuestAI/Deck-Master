"""File-only adapters for SVG, native, and mixed-mode PPTX compilation, rendering and readback."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import zipfile

from lxml import etree
from pptx import Presentation

from .atoms import visible_atoms
from .compiler import CompileOptions, SvgInput, compile_deck
from .compiler.native import emit_svg_slide, normalize_notes, notes_records
from .compiler.svg import parse_svg
from .readback_core import (
    check_notes_and_count,
    missing_visible_atoms,
    slide_text_objects,
)
from .render import readback, render_deck, resolve_fonts
from .sanitize import attach_hint_findings, pptx


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
    nodes = []

    def label_nodes(labels):
        for label in labels:
            if label.get("id"):
                nodes.append({"node_id": label["id"]})
            label_nodes(label.get("children", []))

    label_nodes(content.get("labels", []))
    return {
        "page_id": page["id"],
        "customer_visible": content,
        "speaker_notes": page.get("notes", ""),
        "visual_spec": {"nodes": nodes, "edges": []},
    }


def _readback_mixed(pptx_path: Path, pages: list[dict], parsed_svgs: dict[str, dict]) -> dict:
    from .native.readback import _omitted_column_label_ids

    raw = pptx_path.read_bytes()
    actual_notes = notes_records(raw)
    findings = check_notes_and_count(
        actual_notes,
        [(page["id"], page.get("notes", "")) for page in pages],
        normalize_notes=normalize_notes,
    )
    with zipfile.ZipFile(pptx_path) as archive:
        for index, (page, _note_row) in enumerate(zip(pages, actual_notes), 1):
            slide_xml = f"ppt/slides/slide{index}.xml"
            if slide_xml not in archive.namelist():
                findings.append({"page_id": page["id"], "code": "missing_slide"})
                continue
            root = etree.fromstring(archive.read(slide_xml))
            projected = projection(page)
            atoms = visible_atoms(projected)
            is_svg = page["id"] in parsed_svgs
            if not is_svg:
                omitted = _omitted_column_label_ids(page)
                if omitted:
                    atoms = [atom for atom in atoms if atom["atom_id"] not in omitted]
            missing = missing_visible_atoms(
                slide_text_objects(root, merge_same_atom=is_svg),
                atoms,
                allow_split_spans=is_svg,
            )
            for atom in missing:
                findings.append(
                    {
                        "page_id": page["id"],
                        "code": "missing_visible_atom",
                        "atom_id": atom["atom_id"],
                        "text": atom["text"],
                    }
                )
    return {
        "status": "fail" if findings else "pass",
        "findings": findings,
        "visual_review": "not_evaluated",
        "desktop_editing": "not_evaluated",
    }


def _compile_mixed_job(job: dict, *, preview: bool) -> dict:
    from .native.generate import (
        emit_native_slide,
        ensure_svg_content_type_and_notes_order,
        select_blank_layout,
    )
    from .native.plan import _resolve_native_fonts, read_json

    pages = job["pages"]
    canvas = job["canvas"]
    assets = job.get("assets", {})
    template_path = job.get("theme")

    parsed_svgs: dict[str, dict] = {}
    native_plans: dict[str, dict] = {}
    icon_license = False
    for page in pages:
        if "svg" in page:
            svg_bytes = Path(page["svg"]).read_bytes()
            icon_license = icon_license or b'data-icon-license="lucide-1.49.0"' in svg_bytes
            parsed = parse_svg(svg_bytes, page_id=page["id"], assets=assets)
            parsed["speaker_notes"] = normalize_notes(page.get("notes", ""))
            parsed_svgs[page["id"]] = parsed
        elif "plan" in page:
            native_plans[page["id"]] = read_json(page["plan"])
        else:
            raise ValueError(f"页面 {page.get('id')} 既缺少 svg 也缺少 plan")

    fonts = resolve_fonts(list(parsed_svgs.values())) if parsed_svgs else {}
    if native_plans:
        fonts.update(_resolve_native_fonts(list(native_plans.values())))
    for name in job.get("fonts", []):
        fonts.update(resolve_fonts([{"shapes": [{"kind": "text", "font_family": name, "bold": False}]}]))

    width_px = canvas["slide_width_in"] * 96
    height_px = canvas["slide_height_in"] * 96
    pres = Presentation(str(template_path)) if template_path else Presentation()
    if not template_path:
        pres.slide_width = round(width_px * 9525)
        pres.slide_height = round(height_px * 9525)
    blank_layout = select_blank_layout(pres)
    svg_counter = [0]
    warnings: list[dict] = []

    for page in pages:
        page_id = page["id"]
        if page_id in parsed_svgs:
            emit_svg_slide(pres, parsed_svgs[page_id], width_px, height_px, fonts, blank_layout=blank_layout)
        else:
            emit_native_slide(
                pres,
                page,
                native_plans[page_id],
                svg_counter=svg_counter,
                warnings=warnings,
                blank_layout=blank_layout,
            )

    output = Path(job["output"])
    output.mkdir(parents=True, exist_ok=True)
    target = output / "deck.pptx"
    with tempfile.TemporaryDirectory(prefix="deck-mixed-", dir=output) as temp:
        candidate = Path(temp) / "candidate.pptx"
        pres.save(str(candidate))
        ensure_svg_content_type_and_notes_order(
            candidate, set_default_theme_font=not bool(template_path)
        )
        if icon_license:
            license_path = Path(__file__).parent / "resources" / "icons" / "lucide" / "LICENSE.txt"
            with zipfile.ZipFile(candidate) as source:
                files = {item.filename: source.read(item) for item in source.infolist() if not item.is_dir()}
            if "docProps/core.xml" in files:
                core = etree.fromstring(files["docProps/core.xml"])
                key = "{http://purl.org/dc/elements/1.1/}description"
                desc = core.find(key)
                if desc is None:
                    desc = etree.SubElement(core, key)
                desc.text = (desc.text or "") + "\nLucide 1.49.0 icon license:\n" + license_path.read_text()
                files["docProps/core.xml"] = etree.tostring(core, encoding="utf-8", xml_declaration=True)
                with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as dest:
                    for name, data in files.items():
                        dest.writestr(name, data)
        hints = []
        cleaned = pptx(
            candidate.read_bytes(),
            "deck.pptx",
            notes=[{"page_id": p["id"], "notes": p.get("notes", "")} for p in pages],
            findings=hints,
        )
        target.write_bytes(cleaned)

    report = _readback_mixed(target, pages, parsed_svgs)
    if warnings:
        report.setdefault("warnings", []).extend(warnings)
    attach_hint_findings(report, hints)
    answer = {"pptx": str(target), "findings": report}
    if preview:
        images = render_deck(target, output / "render", fonts=fonts, page_count=len(pages))
        if len(images) != len(pages):
            raise RuntimeError("渲染页数与输入不一致；请检查 LibreOffice 输出")
        answer["preview"] = str(images[0])
    return answer


def compile_job(job, *, preview=False):
    pages = job["pages"]
    if any("plan" in page for page in pages):
        return _compile_mixed_job(job, preview=preview)
    canvas = job["canvas"]
    assets = job.get("assets", {})
    template_path = job.get("theme")
    parsed = [parse_svg(Path(p["svg"]).read_bytes(), page_id=p["id"], assets=assets) for p in pages]
    fonts = resolve_fonts(parsed)
    # Validate requested fonts even when a page contains no text in that family.
    for name in job.get("fonts", []):
        fonts.update(resolve_fonts([{"shapes": [{"kind": "text", "font_family": name, "bold": False}]}]))
    output = Path(job["output"])
    result = compile_deck(
        [SvgInput(p["id"], Path(p["svg"]), p.get("notes", "")) for p in pages],
        CompileOptions(
            width_px=canvas["slide_width_in"] * 96,
            height_px=canvas["slide_height_in"] * 96,
            fonts=fonts,
            assets={p["id"]: assets for p in pages},
            template_path=Path(template_path) if template_path else None,
        ),
        output,
    )
    manifest = json.loads(result.manifest_path.read_text())
    findings = readback(result.pptx_path, manifest["pages"], [projection(p) for p in pages])
    answer = {"pptx": str(result.pptx_path), "findings": findings}
    if preview:
        images = render_deck(result.pptx_path, output / "render", fonts=fonts, page_count=len(pages))
        if len(images) != len(pages):
            raise RuntimeError("渲染页数与输入不一致；请检查 LibreOffice 输出")
        answer["preview"] = str(images[0])
    else:
        hints = []
        cleaned = pptx(
            result.pptx_path.read_bytes(),
            "deck.pptx",
            notes=[{"page_id": p["id"], "notes": p.get("notes", "")} for p in pages],
            findings=hints,
        )
        result.pptx_path.write_bytes(cleaned)
        attach_hint_findings(answer["findings"], hints)
    return answer
