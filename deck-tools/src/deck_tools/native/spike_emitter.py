"""Experimental pure-Python (python-pptx) native PPTX emitter for the C15 evaluation spike.

Covers all 6 native plan primitives (text, shape/custom, arrow, icon with SVG+PNG companion,
image, table) on the standard 12192000 EMU 16:9 canvas without requiring Node.js or pptxgenjs.
"""
from __future__ import annotations

import io
from pathlib import Path
import re
import zipfile

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.util import Emu, Pt

from . import (
    DEFAULT_FONT,
    ICONS,
    NS,
    _render_svg_png,
    _transparent_png,
    _validate_color,
    read_json,
    validate_plan,
)
from ..render import NeedsTool, RendererError

SLIDE_WIDTH_EMU = 12192000
EMU_PER_PT = 12700

_A_NS = NS['a']
_P_NS = NS['p']
_R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_ASVG_NS = 'http://schemas.microsoft.com/office/drawing/2016/SVG/main'
_SVG_EXT_URI = '{96DAC541-7B7A-43D3-8B79-37D633B846F1}'

_ALIGN_MAP = {
    'left': PP_ALIGN.LEFT,
    'center': PP_ALIGN.CENTER,
    'right': PP_ALIGN.RIGHT,
    'justify': PP_ALIGN.JUSTIFY,
}

_VALIGN_MAP = {
    'top': MSO_ANCHOR.TOP,
    'center': MSO_ANCHOR.MIDDLE,
    'mid': MSO_ANCHOR.MIDDLE,
    'bottom': MSO_ANCHOR.BOTTOM,
}

_TC_ANCHOR_MAP = {
    'top': 't',
    'center': 'ctr',
    'mid': 'ctr',
    'bottom': 'b',
}

_ARROWHEAD_MAP = {
    'triangle': 'triangle',
    'arrow': 'arrow',
    'stealth': 'stealth',
    'diamond': 'diamond',
    'oval': 'oval',
    'none': 'none',
}

# Supported OOXML preset geometry names matching PptxGenJS ShapeType keys.
_PRST_ALIASES = {
    'rect': 'rect',
    'roundRect': 'roundRect',
    'ellipse': 'ellipse',
    'oval': 'ellipse',
    'triangle': 'triangle',
    'rtTriangle': 'rtTriangle',
    'diamond': 'diamond',
    'parallelogram': 'parallelogram',
    'trapezoid': 'trapezoid',
    'pentagon': 'pentagon',
    'hexagon': 'hexagon',
    'octagon': 'octagon',
    'chevron': 'chevron',
    'homePlate': 'homePlate',
    'rightArrow': 'rightArrow',
    'leftArrow': 'leftArrow',
    'upArrow': 'upArrow',
    'downArrow': 'downArrow',
    'line': 'line',
    'plus': 'plus',
    'star5': 'star5',
    'can': 'can',
    'cube': 'cube',
    'flowChartProcess': 'flowChartProcess',
    'flowChartDecision': 'flowChartDecision',
    'flowChartTerminator': 'flowChartTerminator',
}

_VALID_PRST = re.compile(r'^[A-Za-z][A-Za-z0-9]*$')


def _hex(value: str) -> str:
    return str(value).lstrip('#').upper()


def _rgb(value: str) -> RGBColor:
    return RGBColor.from_string(_hex(value))


def _is_bold(weight) -> bool:
    if weight == 'bold':
        return True
    if isinstance(weight, (int, float)) and not isinstance(weight, bool):
        return weight >= 600
    return False


def _set_run_fonts(run, family: str) -> None:
    run.font.name = family
    rpr = run._r.get_or_add_rPr()
    for tag in ('latin', 'ea', 'cs'):
        node = rpr.find(f'{{{_A_NS}}}{tag}')
        if node is None:
            node = etree.SubElement(rpr, f'{{{_A_NS}}}{tag}')
        node.set('typeface', family)


def _apply_line_xml(parent_elem, line_spec: dict | None, emu_per_px: float, *, tag: str = 'ln') -> None:
    existing = parent_elem.find(f'{{{_A_NS}}}{tag}')
    if existing is not None:
        parent_elem.remove(existing)
    ln = etree.SubElement(parent_elem, f'{{{_A_NS}}}{tag}')
    if not line_spec or line_spec.get('color') == 'none':
        etree.SubElement(ln, f'{{{_A_NS}}}noFill')
        return
    width_px = line_spec.get('width', 1)
    ln.set('w', str(max(1, round(width_px * emu_per_px))))
    solid = etree.SubElement(ln, f'{{{_A_NS}}}solidFill')
    etree.SubElement(solid, f'{{{_A_NS}}}srgbClr', val=_hex(line_spec.get('color', '000000')))
    arrowheads = line_spec.get('arrowheads') or {}
    start_head = arrowheads.get('start')
    end_head = arrowheads.get('end')
    if start_head and start_head != 'none':
        etree.SubElement(
            ln,
            f'{{{_A_NS}}}headEnd',
            type=_ARROWHEAD_MAP.get(start_head, 'triangle'),
            w='med',
            len='med',
        )
    if end_head and end_head != 'none':
        etree.SubElement(
            ln,
            f'{{{_A_NS}}}tailEnd',
            type=_ARROWHEAD_MAP.get(end_head, 'triangle'),
            w='med',
            len='med',
        )


def _apply_fill_xml(sp_pr, fill_color: str | None, transparency: float = 0) -> None:
    for tag in ('noFill', 'solidFill', 'gradFill', 'blipFill', 'pattFill', 'grpFill'):
        node = sp_pr.find(f'{{{_A_NS}}}{tag}')
        if node is not None:
            sp_pr.remove(node)
    if fill_color == 'none':
        etree.SubElement(sp_pr, f'{{{_A_NS}}}noFill')
        return
    solid = etree.SubElement(sp_pr, f'{{{_A_NS}}}solidFill')
    srgb = etree.SubElement(solid, f'{{{_A_NS}}}srgbClr', val=_hex(fill_color or 'FFFFFF'))
    if transparency and transparency > 0:
        alpha = max(0, min(100000, round((100 - float(transparency)) * 1000)))
        etree.SubElement(srgb, f'{{{_A_NS}}}alpha', val=str(alpha))


def _set_slide_background(slide, hex_color: str) -> None:
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = _rgb(hex_color)


def _add_text_op(slide, op: dict, emu_per_px: float, object_name: str) -> None:
    x, y, w, h = op['bbox']
    box = slide.shapes.add_textbox(
        Emu(round(x * emu_per_px)),
        Emu(round(y * emu_per_px)),
        Emu(round(w * emu_per_px)),
        Emu(round(h * emu_per_px)),
    )
    box.name = object_name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = _VALIGN_MAP.get(op.get('valign') or 'top', MSO_ANCHOR.TOP)

    family = op.get('font') or DEFAULT_FONT
    size_pt = (op.get('size', 16) * emu_per_px) / EMU_PER_PT
    bold = _is_bold(op.get('weight'))
    color = _rgb(op.get('color') or '000000')
    align = _ALIGN_MAP.get(op.get('align') or 'left', PP_ALIGN.LEFT)

    lines = str(op['text']).split('\n')
    for idx, line_text in enumerate(lines):
        para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        para.alignment = align
        para.space_before = Pt(0)
        para.space_after = Pt(0)
        run = para.add_run()
        run.text = line_text
        run.font.size = Pt(size_pt)
        run.font.bold = bold
        run.font.color.rgb = color
        _set_run_fonts(run, family)


def _add_shape_op(slide, op: dict, emu_per_px: float, object_name: str) -> None:
    x, y, w, h = op['bbox']
    shape_type = op['type']
    if shape_type != 'custom':
        prst = _PRST_ALIASES.get(shape_type)
        if prst is None and not _VALID_PRST.match(str(shape_type)):
            raise ValueError(f'不支持的形状：{shape_type}')
        prst = prst or shape_type
    else:
        prst = 'rect'

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Emu(round(x * emu_per_px)),
        Emu(round(y * emu_per_px)),
        Emu(round(w * emu_per_px)),
        Emu(round(h * emu_per_px)),
    )
    shape.name = object_name
    sp_pr = shape._element.spPr

    # Strip default style reference so PowerPoint/LibreOffice never injects theme fill/outline.
    style_node = shape._element.find(f'{{{_P_NS}}}style')
    if style_node is not None:
        shape._element.remove(style_node)

    xfrm = sp_pr.find(f'{{{_A_NS}}}xfrm')
    flip = op.get('flip') or {}
    if flip.get('h'):
        xfrm.set('flipH', '1')
    if flip.get('v'):
        xfrm.set('flipV', '1')

    # Geometry: custom path or preset geometry (+ roundRect corner radius).
    for old in list(sp_pr):
        if etree.QName(old).localname in ('prstGeom', 'custGeom'):
            sp_pr.remove(old)

    if shape_type == 'custom':
        geometry = etree.Element(f'{{{_A_NS}}}custGeom')
        for tag in ('avLst', 'gdLst', 'ahLst', 'cxnLst'):
            etree.SubElement(geometry, f'{{{_A_NS}}}{tag}')
        etree.SubElement(geometry, f'{{{_A_NS}}}rect', l='0', t='0', r='r', b='b')
        paths = etree.SubElement(geometry, f'{{{_A_NS}}}pathLst')
        path_elem = etree.SubElement(
            paths,
            f'{{{_A_NS}}}path',
            w=str(max(1, round(w * emu_per_px))),
            h=str(max(1, round(h * emu_per_px))),
            fill='none' if op.get('fill', 'none') == 'none' else 'norm',
            stroke='1',
        )
        for idx, (px, py) in enumerate(op['points']):
            cmd = etree.SubElement(path_elem, f'{{{_A_NS}}}{"moveTo" if idx == 0 else "lnTo"}')
            etree.SubElement(
                cmd,
                f'{{{_A_NS}}}pt',
                x=str(round(px * emu_per_px)),
                y=str(round(py * emu_per_px)),
            )
        if op.get('closed'):
            etree.SubElement(path_elem, f'{{{_A_NS}}}close')
        sp_pr.insert(1, geometry)
    else:
        effective_prst = prst
        geometry = etree.Element(f'{{{_A_NS}}}prstGeom', prst=effective_prst)
        av_lst = etree.SubElement(geometry, f'{{{_A_NS}}}avLst')
        if effective_prst in ('rect', 'roundRect') and op.get('radius') and min(w, h) > 0:
            geometry.set('prst', 'roundRect')
            ratio = min(0.5, op['radius'] / min(w, h))
            etree.SubElement(av_lst, f'{{{_A_NS}}}gd', name='adj', fmla=f'val {round(ratio * 100000)}')
        sp_pr.insert(1, geometry)

    _apply_fill_xml(sp_pr, op.get('fill', 'FFFFFF'), op.get('transparency', 0))
    _apply_line_xml(sp_pr, op.get('line'), emu_per_px)


def _add_arrow_op(slide, op: dict, emu_per_px: float, object_name: str) -> None:
    x1, y1 = op['start']
    x2, y2 = op['end']
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Emu(round(x1 * emu_per_px)),
        Emu(round(y1 * emu_per_px)),
        Emu(round(x2 * emu_per_px)),
        Emu(round(y2 * emu_per_px)),
    )
    connector.name = object_name
    style_node = connector._element.find(f'{{{_P_NS}}}style')
    if style_node is not None:
        connector._element.remove(style_node)
    _apply_line_xml(
        connector._element.spPr,
        {
            'color': op.get('color', '000000'),
            'width': op.get('width', 1),
            'arrowheads': op.get('arrowheads'),
        },
        emu_per_px,
    )


def _add_icon_op(slide, op: dict, emu_per_px: float, object_name: str, icons_dir: Path, svg_counter: list[int], warnings: list[dict]) -> None:
    x, y, w, h = op['bbox']
    cx = max(1, round(w * emu_per_px))
    cy = max(1, round(h * emu_per_px))
    name = op['icon_id'].removeprefix('tabler-outline/')
    svg_text = (icons_dir / f'{name}.svg').read_text(encoding='utf-8').replace(
        'currentColor', f'#{_hex(op.get("color") or "000000")}'
    )
    svg_bytes = svg_text.encode('utf-8')

    try:
        png_bytes = _render_svg_png(svg_bytes, (cx, cy))
    except NeedsTool:
        png_bytes = _transparent_png()
        warnings.append({
            'level': 'warning',
            'code': 'svg_png_fallback',
            'part': object_name,
            'detail': '缺少 rsvg-convert，图标备用图使用透明占位。装好后重新构建。',
        })
    except (RendererError, OSError):
        png_bytes = _transparent_png()
        warnings.append({
            'level': 'warning',
            'code': 'svg_png_fallback',
            'part': object_name,
            'detail': '图标备用图渲染失败，使用透明占位。',
        })

    pic = slide.shapes.add_picture(
        io.BytesIO(png_bytes),
        Emu(round(x * emu_per_px)),
        Emu(round(y * emu_per_px)),
        Emu(cx),
        Emu(cy),
    )
    pic.name = object_name

    # Attach native SVG vector blip alongside the rendered PNG companion.
    svg_counter[0] += 1
    partname = PackURI(f'/ppt/media/icon-{svg_counter[0]}.svg')
    svg_part = Part(partname, 'image/svg+xml', slide.part.package, svg_bytes)
    rel_id = slide.part.relate_to(svg_part, RT.IMAGE)

    blip = pic._element.find(f'.//{{{_A_NS}}}blip')
    ext_lst = blip.find(f'{{{_A_NS}}}extLst')
    if ext_lst is None:
        ext_lst = etree.SubElement(blip, f'{{{_A_NS}}}extLst')
    ext = etree.SubElement(ext_lst, f'{{{_A_NS}}}ext', uri=_SVG_EXT_URI)
    svg_blip = etree.SubElement(ext, f'{{{_ASVG_NS}}}svgBlip')
    svg_blip.set(f'{{{_R_NS}}}embed', rel_id)


def _add_image_op(slide, op: dict, emu_per_px: float, object_name: str, page: dict) -> None:
    plan_dir = Path(page['plan']).resolve().parent
    asset_path = (plan_dir / op['file']).resolve()
    if not asset_path.is_relative_to(plan_dir) or not asset_path.is_file():
        raise ValueError(f'image 素材路径越出当前任务目录或不存在：{op["file"]}')
    with Image.open(asset_path) as image:
        if image.format not in ('PNG', 'JPEG'):
            raise ValueError(f'image 素材只支持 PNG 或 JPEG：{op["file"]}')
    x, y, w, h = op['bbox']
    pic = slide.shapes.add_picture(
        str(asset_path),
        Emu(round(x * emu_per_px)),
        Emu(round(y * emu_per_px)),
        Emu(round(w * emu_per_px)),
        Emu(round(h * emu_per_px)),
    )
    pic.name = object_name


def _cell_margins_px(value) -> tuple[float, float, float, float]:
    if isinstance(value, list):
        return tuple(float(v) for v in value)
    v = float(value)
    return (v, v, v, v)


def _add_table_op(slide, op: dict, emu_per_px: float, object_name: str) -> None:
    x, y, w, h = op['bbox']
    rows_data = op['cells']
    row_count = len(rows_data)
    col_count = len(op['col_widths'])
    frame = slide.shapes.add_table(
        row_count,
        col_count,
        Emu(round(x * emu_per_px)),
        Emu(round(y * emu_per_px)),
        Emu(round(w * emu_per_px)),
        Emu(round(h * emu_per_px)),
    )
    frame.name = object_name
    table = frame.table

    # Remove default PowerPoint banded style so explicit fills/borders render identically.
    tbl_pr = table._tbl.tblPr
    tbl_pr.set('firstRow', '0')
    tbl_pr.set('bandRow', '0')
    for style_id in tbl_pr.findall(f'{{{_A_NS}}}tableStyleId'):
        tbl_pr.remove(style_id)

    for col_idx, col_w in enumerate(op['col_widths']):
        table.columns[col_idx].width = Emu(round(col_w * emu_per_px))
    for row_idx, row_h in enumerate(op['row_heights']):
        table.rows[row_idx].height = Emu(round(row_h * emu_per_px))

    border_spec = op.get('line') if isinstance(op.get('line'), dict) else {'color': '000000', 'width': 1}
    header_style = op.get('header_style') or {}

    for r_idx, row in enumerate(rows_data):
        for c_idx, cell_spec in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            merged = {**op, **(header_style if r_idx == 0 else {}), **cell_spec}
            margin_src = (
                cell_spec.get('margin')
                if 'margin' in cell_spec
                else (
                    header_style.get('margin')
                    if r_idx == 0 and 'margin' in header_style
                    else (op.get('margin') if 'margin' in op else ([5, 8, 5, 8] if r_idx == 0 else [7, 9, 7, 9]))
                )
            )
            mt, mr, mb, ml = _cell_margins_px(margin_src)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_pr.set('marT', str(round(mt * emu_per_px)))
            tc_pr.set('marR', str(round(mr * emu_per_px)))
            tc_pr.set('marB', str(round(mb * emu_per_px)))
            tc_pr.set('marL', str(round(ml * emu_per_px)))
            tc_pr.set('anchor', _TC_ANCHOR_MAP.get(merged.get('valign') or 'top', 't'))

            for side in ('lnL', 'lnR', 'lnT', 'lnB'):
                _apply_line_xml(tc_pr, border_spec, emu_per_px, tag=side)

            fill_val = cell_spec.get('fill') if 'fill' in cell_spec else (header_style.get('fill') if r_idx == 0 else None)
            if fill_val and fill_val != 'none':
                _apply_fill_xml(tc_pr, fill_val, 0)
            else:
                _apply_fill_xml(tc_pr, 'none', 0)

            tf = cell.text_frame
            tf.word_wrap = True
            family = merged.get('font') or DEFAULT_FONT
            size_pt = (merged.get('size', 16) * emu_per_px) / EMU_PER_PT
            bold = _is_bold(merged.get('weight'))
            color = _rgb(merged.get('color') or '000000')
            align = _ALIGN_MAP.get(merged.get('align') or 'left', PP_ALIGN.LEFT)

            lines = str(cell_spec['text']).split('\n')
            for line_idx, line_text in enumerate(lines):
                para = tf.paragraphs[0] if line_idx == 0 else tf.add_paragraph()
                para.alignment = align
                para.space_before = Pt(0)
                para.space_after = Pt(0)
                run = para.add_run()
                run.text = line_text
                run.font.size = Pt(size_pt)
                run.font.bold = bold
                run.font.color.rgb = color
                _set_run_fonts(run, family)

    # Pin graphicFrame height to exact sum of row_heights in EMU.
    ext = frame._element.find(f'{{{_P_NS}}}xfrm/{{{_A_NS}}}ext')
    if ext is not None:
        ext.set('cy', str(round(h * emu_per_px)))


def _ensure_svg_content_type(pptx_path: Path) -> None:
    """Ensure [Content_Types].xml declares image/svg+xml when SVG icon parts are present."""
    with zipfile.ZipFile(pptx_path) as archive:
        files = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    has_svg = any(name.lower().endswith('.svg') for name in files)
    if not has_svg:
        return
    ct_root = etree.fromstring(files['[Content_Types].xml'])
    ct_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    existing = {
        node.get('Extension', '').lower()
        for node in ct_root.findall(f'{{{ct_ns}}}Default')
    }
    if 'svg' not in existing:
        etree.SubElement(ct_root, f'{{{ct_ns}}}Default', Extension='svg', ContentType='image/svg+xml')
        files['[Content_Types].xml'] = etree.tostring(
            ct_root, xml_declaration=True, encoding='UTF-8', standalone=True
        )
        with zipfile.ZipFile(pptx_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)


def generate(pages: list[dict], output: Path | str, *, mode: str = 'deck', icons_dir: Path = ICONS):
    """Emit a native PPTX purely via python-pptx without Node.js/pptxgenjs."""
    if mode not in ('single', 'deck') or not pages or (mode == 'single' and len(pages) != 1):
        raise ValueError('请选择单页或整套模式并传入对应页面')

    plans = [read_json(page['plan']) for page in pages]
    findings = []
    if mode == 'single':
        findings = [validate_plan(plan, page) for plan, page in zip(plans, pages)]

    canvas = plans[0]['canvas_px']
    for idx, plan in enumerate(plans[1:], 2):
        if plan['canvas_px']['w'] != canvas['w'] or plan['canvas_px']['h'] != canvas['h']:
            raise ValueError(
                f'整套各页画布尺寸必须一致：第 1 页 {canvas["w"]}×{canvas["h"]}，'
                f'第 {idx} 页 {plan["canvas_px"]["w"]}×{plan["canvas_px"]["h"]}'
            )

    emu_per_px = SLIDE_WIDTH_EMU / canvas['w']
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_WIDTH_EMU)
    prs.slide_height = Emu(round(SLIDE_WIDTH_EMU * canvas['h'] / canvas['w']))
    blank_layout = prs.slide_layouts[6]

    svg_counter = [0]
    warnings: list[dict] = []

    for page, plan in zip(pages, plans):
        _validate_color(plan.get('background'), 'background')
        slide = prs.slides.add_slide(blank_layout)
        slide._element.find(f'{{{_P_NS}}}cSld').set('name', plan['page'])
        _set_slide_background(slide, plan['background'])
        for idx, op in enumerate(plan['ops']):
            object_name = f'native_{idx}'
            kind = op['op']
            if kind == 'text':
                _add_text_op(slide, op, emu_per_px, object_name)
            elif kind == 'shape':
                _add_shape_op(slide, op, emu_per_px, object_name)
            elif kind == 'arrow':
                _add_arrow_op(slide, op, emu_per_px, object_name)
            elif kind == 'icon':
                _add_icon_op(slide, op, emu_per_px, object_name, icons_dir, svg_counter, warnings)
            elif kind == 'image':
                _add_image_op(slide, op, emu_per_px, object_name, page)
            elif kind == 'table':
                _add_table_op(slide, op, emu_per_px, object_name)
            else:
                raise ValueError(f'不支持的原语：{kind}')
        slide.notes_slide.notes_text_frame.text = page.get('notes') or ''

    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    _ensure_svg_content_type(output_path)

    if warnings and mode == 'single' and findings:
        findings[0].setdefault('warnings', []).extend(warnings)
    return output_path, findings, warnings
