"""File-only native reconstruction: no project database or adoption state."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import posixpath
import struct
import sys
import tempfile
import zipfile
import zlib

from lxml import etree
from PIL import Image, ImageDraw

from .. import sanitize
from ..atoms import visible_atoms
from ..jobs import projection
from ..render import NeedsTool, executable, render_deck, run

ICONS = Path(__file__).resolve().parents[1] / 'resources' / 'icons' / 'tabler-outline'
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
SLIDE_WIDTH_EMU = round(13.333 * 914400)


def emu_per_px(plan):
    """EMU per source-image pixel: slide width is fixed, height follows the source aspect ratio."""
    return SLIDE_WIDTH_EMU / plan['canvas_px']['w']


def native_pptx_dir():
    installed = Path(sys.prefix).parent / 'native-pptx'
    development = Path(__file__).resolve().parents[3] / 'native-pptx'
    for directory in (installed, development):
        if (directory / 'render.cjs').is_file():
            return directory
    raise NeedsTool('找不到 native-pptx；请重新运行安装脚本')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('坐标和尺寸必须是有限数字')
    return value


def inside_box(bbox, w, h):
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError('bbox 必须是 [x,y,w,h]')
    x, y, width, height = map(number, bbox)
    if min(x, y, width, height) < 0 or x + width > w or y + height > h:
        raise ValueError('bbox 超出原图画布')


def icon_file(icon_id):
    prefix = 'tabler-outline/'
    if not isinstance(icon_id, str) or not icon_id.startswith(prefix):
        raise ValueError('图标必须来自 Tabler outline')
    name = icon_id[len(prefix):]
    candidate = (ICONS / f'{name}.svg').resolve()
    if not candidate.is_relative_to(ICONS.resolve()) or '/' in name or not candidate.is_file():
        raise ValueError(f'图标不存在：{icon_id}')
    return candidate


def validate_plan(plan, page):
    if plan.get('schema') != 'deck.native_plan.v1' or plan.get('page') != page['id']:
        raise ValueError('plan 格式或页编号不匹配')
    if 'notes' in plan:
        raise ValueError('讲稿通过 page.notes 传入，不写进 plan')
    w, h = number(plan['canvas_px']['w']), number(plan['canvas_px']['h'])
    if min(w, h) <= 0:
        raise ValueError('画布尺寸必须大于零')
    atoms = {a['atom_id']: a['text'] for a in visible_atoms(projection(page)) if a['text'] is not None}
    covered = set()

    def text(item):
        atom = item.get('atom_id')
        if atom not in atoms or item.get('text') != atoms[atom]:
            raise ValueError(f'文字必须与当前 content 的 atom 一致：{atom}')
        covered.add(atom)

    def margin(item):
        if 'margin' not in item:
            return
        value = item['margin']
        values = value if isinstance(value, list) else [value] * 4
        if len(values) != 4 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
            for v in values
        ):
            raise ValueError('margin 必须是非负有限数字或 [上,右,下,左] 四个非负有限数字（原图像素）')

    for op in plan['ops']:
        kind = op['op']
        if kind not in ('text', 'shape', 'arrow', 'icon', 'image', 'table'):
            raise ValueError(f'不支持的原语：{kind}')
        if kind == 'arrow':
            for point in (op['start'], op['end']):
                if len(point) != 2:
                    raise ValueError('箭头端点必须是 [x,y]')
                inside_box([*point, 0, 0], w, h)
        else:
            inside_box(op['bbox'], w, h)
        if kind == 'shape' and 'radius' in op and op['type'] not in ('rect', 'roundRect'):
            raise ValueError('圆角只用于矩形')
        if kind == 'text':
            text(op)
        elif kind == 'table':
            margin(op)
            margin(op.get('header_style', {}))
            widths, heights, rows = op['col_widths'], op['row_heights'], op['cells']
            if len(rows) != len(heights) or not widths or not heights or any(len(r) != len(widths) for r in rows):
                raise ValueError('表格单元格、列宽和行高不匹配')
            if any(number(v) <= 0 for v in [*widths, *heights]):
                raise ValueError('表格行高和列宽必须大于零')
            if not math.isclose(sum(widths), op['bbox'][2]) or not math.isclose(sum(heights), op['bbox'][3]):
                raise ValueError('表格行高和列宽合计必须等于 bbox')
            for row in rows:
                for cell in row:
                    margin(cell)
                    text(cell)
        elif kind == 'icon':
            icon_file(op['icon_id'])
        elif kind == 'image':
            if any(key in op for key in ('text', 'atom_id', 'cells', 'content')):
                raise ValueError('image 不能承载正文，请用原生文字或表格')
            if op['bbox'][2] * op['bbox'][3] > w * h * 0.4:
                raise ValueError('单张图片面积不能超过画布的 40%')
        elif kind == 'shape' and op['type'] == 'custom':
            points = op['points']
            if len(points) < 2:
                raise ValueError('custom 至少需要两个点')
            for point in points:
                if len(point) != 2:
                    raise ValueError('custom 点必须是 bbox 内的 [x,y]')
                inside_box([*point, 0, 0], op['bbox'][2], op['bbox'][3])
        if kind not in ('text', 'table', 'image') and any(key in op for key in ('text', 'atom_id', 'content')):
            raise ValueError('上屏文字必须使用 text 或 table 原语')
    if covered != set(atoms):
        raise ValueError('plan 缺少正文 atom：' + '、'.join(sorted(set(atoms) - covered)))
    return {'page': page['id'], 'atoms': len(covered)}


def _transparent_png():
    """1×1 transparent PNG used as the Office fallback for an SVG icon.

    PptxGenJS 4.0.1 writes each SVG twice: the SVG part, and a PNG companion
    it intends to replace with a placeholder once Node's fs module has loaded.
    That replacement is not added to the media promise list until the load
    finishes. A deck whose media are only in-memory SVGs therefore finishes
    Promise.all immediately and stores the SVG XML in ppt/media/image-*.png.
    A deck that also reads a raster file waits long enough for the placeholder,
    which is why a full build can succeed while an icon-only subset fails in
    sanitize with "invalid PNG payload".
    """
    def chunk(kind, payload):
        crc = zlib.crc32(kind + payload) & 0xffffffff
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', crc)

    header = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b'\x00\x00\x00\x00\x00')
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', pixels) + chunk(b'IEND', b'')


def _part_name(source_part, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _svg_companion_pngs(files):
    """PNG parts that a slide blip uses only as the fallback for an SVG part."""
    companions = set()
    for name, data in files.items():
        if not name.startswith('ppt/slides/_rels/slide') or not name.endswith('.xml.rels'):
            continue
        source = name.replace('/_rels/', '/')[:-len('.rels')]
        rels = etree.fromstring(data)
        targets = {}
        for rel in rels:
            rid = rel.get('Id')
            target = rel.get('Target')
            if rid and target and rel.get('TargetMode') != 'External':
                targets[rid] = _part_name(source, target)
        slide = etree.fromstring(files[source])
        for element in slide.iter():
            if etree.QName(element).localname != 'blip':
                continue
            png_rid = None
            for key, value in element.attrib.items():
                if etree.QName(key).localname == 'embed':
                    png_rid = value
            svg_rid = None
            for child in element.iter():
                if etree.QName(child).localname != 'svgBlip':
                    continue
                for key, value in child.attrib.items():
                    if etree.QName(key).localname == 'embed':
                        svg_rid = value
            png_part = targets.get(png_rid)
            svg_part = targets.get(svg_rid)
            if not png_part or not svg_part or svg_part not in files:
                continue
            if png_part.lower().endswith('.png') and svg_part.lower().endswith('.svg'):
                companions.add(png_part)
    return companions


def _repair_svg_png_companions(files):
    placeholder = None
    for name in _svg_companion_pngs(files):
        data = files.get(name)
        if data is None or data.startswith(b'\x89PNG\r\n\x1a\n') or not data.lstrip().startswith(b'<'):
            continue
        if placeholder is None:
            placeholder = _transparent_png()
        files[name] = placeholder


def postprocess(pptx_path, plans):
    with zipfile.ZipFile(pptx_path) as archive:
        # PptxGenJS emits an empty embeddings directory even without embedded files.
        files = {item.filename: archive.read(item) for item in archive.infolist() if not item.is_dir()}
    for index, plan in enumerate(plans, 1):
        emu = emu_per_px(plan)
        name = f'ppt/slides/slide{index}.xml'
        root = etree.fromstring(files[name])
        root.find('p:cSld', NS).set('name', plan['page'])
        for para in root.findall('.//a:p', NS):
            for duplicate in para.findall('a:pPr', NS)[1:]:
                para.remove(duplicate)
        for cell in root.findall('.//a:tcPr', NS):
            if cell.get('anchor') == 'mid':
                cell.set('anchor', 'ctr')
        ops = {f'native_{i}': op for i, op in enumerate(plan['ops'])}
        for frame in root.findall('.//p:graphicFrame', NS):
            op = ops.get(frame.find('p:nvGraphicFramePr/p:cNvPr', NS).get('name'))
            if op is None or op['op'] != 'table':
                continue
            for row, height in zip(frame.findall('.//a:tr', NS), op['row_heights']):
                row.set('h', str(round(height * emu)))
            frame.find('p:xfrm/a:ext', NS).set('cy', str(round(op['bbox'][3] * emu)))
        for shape in root.findall('.//p:sp', NS):
            op = ops.get(shape.find('p:nvSpPr/p:cNvPr', NS).get('name'))
            if op is None or op['op'] != 'shape':
                continue
            props = shape.find('p:spPr', NS)
            if op['type'] == 'custom':
                for old in list(props):
                    if etree.QName(old).localname in ('prstGeom', 'custGeom'):
                        props.remove(old)
                geometry = etree.Element(f'{{{NS["a"]}}}custGeom')
                for tag in ('avLst', 'gdLst', 'ahLst', 'cxnLst'):
                    etree.SubElement(geometry, f'{{{NS["a"]}}}{tag}')
                etree.SubElement(geometry, f'{{{NS["a"]}}}rect', l='0', t='0', r='r', b='b')
                paths = etree.SubElement(geometry, f'{{{NS["a"]}}}pathLst')
                path = etree.SubElement(paths, f'{{{NS["a"]}}}path',
                                        w=str(round(op['bbox'][2] * emu)),
                                        h=str(round(op['bbox'][3] * emu)),
                                        fill='none' if op.get('fill', 'none') == 'none' else 'norm', stroke='1')
                for i, (x, y) in enumerate(op['points']):
                    command = etree.SubElement(path, f'{{{NS["a"]}}}{"moveTo" if i == 0 else "lnTo"}')
                    etree.SubElement(command, f'{{{NS["a"]}}}pt', x=str(round(x * emu)), y=str(round(y * emu)))
                if op.get('closed'):
                    etree.SubElement(path, f'{{{NS["a"]}}}close')
                props.insert(1, geometry)
            elif op['type'] in ('rect', 'roundRect') and op.get('radius') and min(op['bbox'][2:]) > 0:
                geometry = props.find('a:prstGeom', NS)
                geometry.set('prst', 'roundRect')
                adjustments = geometry.find('a:avLst', NS)
                for child in list(adjustments):
                    adjustments.remove(child)
                radius = min(0.5, op['radius'] / min(op['bbox'][2:]))
                etree.SubElement(adjustments, f'{{{NS["a"]}}}gd', name='adj', fmla=f'val {round(radius * 100000)}')
        files[name] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    root = etree.fromstring(files['ppt/presentation.xml'])
    notes = root.find('p:notesMasterIdLst', NS)
    if notes is not None:
        root.remove(notes)
        master = root.find('p:sldMasterIdLst', NS)
        root.insert(list(root).index(master) + 1 if master is not None else 0, notes)
    files['ppt/presentation.xml'] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    _repair_svg_png_companions(files)
    with zipfile.ZipFile(pptx_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def generate(pages, output, *, mode):
    plans = [read_json(page['plan']) for page in pages]
    # Adopted deck plans were validated on result; content drift is reported by readback.
    findings = []
    if mode == 'single':
        findings = [validate_plan(plan, page) for plan, page in zip(plans, pages)]
    directory = native_pptx_dir()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='deck-native-') as temp:
        job = Path(temp) / 'job.json'
        write_json(job, {'mode': mode, 'pages': [{**p, 'plan': str(Path(p['plan']).resolve())} for p in pages],
                         'output': str(output), 'icons_dir': str(ICONS)})
        run([executable('node'), str(directory / 'render.cjs'), str(job)], cwd=directory)
    postprocess(output, plans)
    return output, findings


def page_directory(work, page_id):
    root = (Path(work) / 'native').resolve()
    destination = (root / page_id).resolve()
    if not page_id or destination == root or not destination.is_relative_to(root):
        raise ValueError('页编号必须位于 native 目录下')
    return destination


def crop(job):
    page = job['page']
    destination = page_directory(job['work'], page['id']) / 'assets'
    target = (destination / f'{job["id"]}.png').resolve()
    if not target.is_relative_to(destination.resolve()):
        raise ValueError('裁图编号必须位于本页 assets 目录下')
    with Image.open(page['source_image']) as image:
        inside_box(job['box'], *image.size)
        x, y, w, h = job['box']
        destination.mkdir(parents=True, exist_ok=True)
        image.crop((x, y, x + w, y + h)).save(target)
    return {'file': str(target)}


def render(job):
    page = job['page']
    directory = Path(job['output']).resolve() if 'output' in job else page_directory(job['work'], page['id'])
    pptx, findings = generate([page], directory / 'page.pptx', mode='single')
    # Isolated conversion avoids picking up PNGs from an earlier, longer deck.
    with tempfile.TemporaryDirectory(prefix='deck-native-render-') as temp:
        images = render_deck(pptx, temp, fonts={})
        if len(images) != 1:
            raise RuntimeError('单页渲染没有得到一张 PNG')
        preview = directory / 'render.png'
        with Image.open(images[0]) as image:
            image.save(preview)
    comparison = directory / 'side-by-side.png'
    with Image.open(page['source_image']) as source, Image.open(preview) as rendered:
        source = source.convert('RGB')
        rendered = rendered.convert('RGB').resize(source.size)
        combined = Image.new('RGB', (source.width * 2, source.height + 30), 'white')
        combined.paste(source, (0, 30))
        combined.paste(rendered, (source.width, 30))
        labels = ImageDraw.Draw(combined)
        labels.text((10, 8), 'source', fill='black')
        labels.text((source.width + 10, 8), 'render', fill='black')
        combined.save(comparison)
    return {'pptx': str(pptx), 'render_png': str(preview), 'side_by_side': str(comparison),
            'findings': findings[0]}


def _slide_text_objects(root):
    """One string per shape or table cell. Runs inside one object stay together."""
    objects = []
    for element in [*root.findall('.//p:sp', NS), *root.findall('.//a:tc', NS)]:
        parts = element.xpath('.//a:t/text()', namespaces=NS)
        text = ''.join(''.join(parts).split())
        if text:
            objects.append(text)
    return objects


def _take_span(text, mask, needle):
    length = len(needle)
    start = 0
    while start <= len(text) - length:
        index = text.find(needle, start)
        if index < 0:
            return False
        if any(mask[index:index + length]):
            start = index + 1
            continue
        for offset in range(length):
            mask[index + offset] = 1
        return True
    return False


def _missing_visible_atoms(objects, atoms):
    """Mark consumed characters inside one text object.

    Longest atom first, so a short atom is missing when its only copy sits
    inside a longer atom on the slide. Objects are not concatenated: drawing
    20, 202, and 2 must not be read as one string. Deleting a match is also
    wrong, because removing 中间 from 甲中间乙 would invent 甲乙.
    """
    masks = [bytearray(len(text)) for text in objects]
    missing = []
    needles = []
    for atom in atoms:
        raw = atom.get('text')
        if not raw:
            continue
        needle = ''.join(raw.split())
        if needle:
            needles.append((needle, atom))
    needles.sort(key=lambda item: len(item[0]), reverse=True)
    for needle, atom in needles:
        if not any(_take_span(text, mask, needle) for text, mask in zip(objects, masks)):
            missing.append(atom)
    return missing


def readback(pptx, pages):
    from ..compiler.native import notes_records, normalize_notes
    findings = []
    notes = notes_records(Path(pptx).read_bytes())
    if len(notes) != len(pages):
        findings.append({'code': 'slide_count_mismatch', 'actual': len(notes), 'expected': len(pages)})
    with zipfile.ZipFile(pptx) as archive:
        for index, (page, actual) in enumerate(zip(pages, notes), 1):
            if actual['page_id'] != page['id']:
                findings.append({'page_id': page['id'], 'code': 'notes_page_identity_mismatch'})
            if actual['notes'] != normalize_notes(page.get('notes', '')):
                findings.append({'page_id': page['id'], 'code': 'speaker_notes_mismatch'})
            root = etree.fromstring(archive.read(f'ppt/slides/slide{index}.xml'))
            for atom in _missing_visible_atoms(_slide_text_objects(root), visible_atoms(projection(page))):
                findings.append({'page_id': page['id'], 'code': 'missing_visible_atom',
                                 'atom_id': atom['atom_id'], 'text': atom['text']})
    return {'status': 'fail' if findings else 'pass', 'findings': findings}


def assemble(job):
    output = (Path(job['work']) / 'native' / 'deck.pptx').resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.deck-', suffix='.pptx', delete=False) as temp:
        temporary = Path(temp.name)
    try:
        generate(job['pages'], temporary, mode='deck')
        temporary.write_bytes(sanitize.pptx(
            temporary.read_bytes(), 'deck.pptx',
            notes=[{'page_id': p['id'], 'notes': p.get('notes', '')} for p in job['pages']]))
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    directory = output.parent / 'deck-render'
    with tempfile.TemporaryDirectory(prefix='deck-native-deck-') as temp:
        images = render_deck(output, temp, fonts={})
        if len(images) != len(job['pages']):
            raise RuntimeError('整套渲染页数与输入不一致')
        directory.mkdir(exist_ok=True)
        previews = []
        for i, image in enumerate(images, 1):
            target = directory / f'page-{i}.png'
            target.write_bytes(image.read_bytes())
            previews.append(str(target))
    return {'pptx': str(output), 'render_pngs': previews, 'findings': readback(output, job['pages'])}


def dispatch(command, job):
    if command == 'validate-plan':
        return validate_plan(read_json(job['page']['plan']), job['page'])
    return {'crop': crop, 'render': render, 'assemble': assemble}[command](job)
