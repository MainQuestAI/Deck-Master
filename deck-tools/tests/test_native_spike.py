"""C15 evaluation spike tests comparing pure-Python python-pptx emitter against Node/pptxgenjs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import time
import zipfile

from lxml import etree
from PIL import Image, ImageChops, ImageDraw
from pptx import Presentation
import pytest

from deck_tools import native
from deck_tools.atoms import visible_atoms
from deck_tools.jobs import projection
from deck_tools.native import spike_emitter
from deck_tools.render import render_deck, resolve_fonts
from deck_tools.sanitize import pptx as sanitize_pptx


def _system_font() -> str:
    res = subprocess.run(['fc-match', '-f', '%{family}', 'sans-serif'], capture_output=True, text=True, check=False)
    family = res.stdout.strip().split(',')[0].strip() if res.returncode == 0 else ''
    return family or 'DejaVu Sans'


def _make_sample_page(tmp_path: Path, page_id: str = 'p1', font: str | None = None, idx: int = 0):
    font = font or _system_font()
    page_dir = tmp_path / 'native' / page_id
    page_dir.mkdir(parents=True, exist_ok=True)
    source = page_dir / 'source.png'
    img = Image.new('RGB', (1280, 720), 'white')
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 120, 260, 260), fill='#225588')
    img.save(source)
    asset = page_dir / 'assets' / 'crop.png'
    asset.parent.mkdir(exist_ok=True)
    img.crop((40, 120, 180, 240)).save(asset)

    page = {
        'id': page_id,
        'content': {
            'title': f'合成基准页 {idx + 1}',
            'body_blocks': [{
                'id': 'matrix',
                'type': 'table',
                'columns': [{'id': 'a', 'label': '合成项目'}, {'id': 'b', 'label': '合成数值'}],
                'rows': [{'id': 'one', 'cells': [
                    {'column_id': 'a', 'display_text': f'试验项 {idx + 1}'},
                    {'column_id': 'b', 'display_text': str(42 + idx)},
                ]}],
            }],
        },
        'notes': f'第 {idx + 1} 页合成讲稿\n第二行讲稿',
        'source_image': str(source),
        'plan': str(page_dir / 'plan.json'),
    }
    atoms = visible_atoms(projection(page))
    cell = lambda a: {'text': a['text'], 'atom_id': a['atom_id']}
    plan = {
        'schema': 'deck.native_plan.v1',
        'page': page_id,
        'canvas_px': {'w': 1280, 'h': 720},
        'background': 'F8FAFC',
        'ops': [
            {
                'op': 'shape', 'type': 'rect', 'bbox': [24, 24, 920, 72],
                'fill': 'DCE7F3', 'line': {'color': '225588', 'width': 2}, 'radius': 10, 'flip': {'h': True},
            },
            {
                'op': 'text', **cell(atoms[0]), 'bbox': [44, 34, 860, 52],
                'size': 32, 'color': '14213D', 'weight': 'bold', 'font': font, 'align': 'left', 'valign': 'center',
            },
            {
                'op': 'icon', 'icon_id': 'tabler-outline/anchor', 'bbox': [980, 32, 56, 56], 'color': '225588',
            },
            {
                'op': 'image', 'file': 'assets/crop.png', 'bbox': [980, 120, 140, 120],
            },
            {
                'op': 'arrow', 'start': [920, 290], 'end': [1140, 320],
                'color': '225588', 'width': 3, 'arrowheads': {'end': 'triangle'},
            },
            {
                'op': 'table', 'bbox': [24, 140, 860, 200],
                'col_widths': [540, 320], 'row_heights': [70, 130],
                'size': 20, 'font': font, 'valign': 'center',
                'line': {'color': '94A3B8', 'width': 1},
                'header_style': {'fill': '225588', 'color': 'FFFFFF', 'weight': 'bold', 'valign': 'center'},
                'cells': [[cell(atoms[1]), cell(atoms[2])], [cell(atoms[3]), cell(atoms[4])]],
            },
            {
                'op': 'shape', 'type': 'custom', 'bbox': [24, 420, 860, 90],
                'points': [[860, 0], [860, 65], [820, 90], [24, 90], [0, 65], [0, 0]],
                'closed': True, 'fill': 'E2E8F0', 'line': {'color': '225588', 'width': 2, 'arrowheads': {'end': 'triangle'}},
            },
        ],
    }
    native.write_json(page['plan'], plan)
    return page, plan


def test_spike_emitter_covers_all_six_primitives_and_passes_readback_and_sanitize(tmp_path):
    page, _ = _make_sample_page(tmp_path)
    out, findings, warnings = spike_emitter.generate([page], tmp_path / 'spike.pptx', mode='single')
    assert out.is_file()
    assert len(findings) == 1
    assert warnings == []

    # Verify exact 16:9 standard EMU dimensions.
    prs = Presentation(str(out))
    assert prs.slide_width == 12192000
    assert prs.slide_height == 6858000
    assert len(prs.slides) == 1
    assert prs.slides[0].notes_slide.notes_text_frame.text == page['notes']

    # Verify native readback passes with zero missing atoms or notes mismatch.
    report = native.readback(out, [page])
    assert report == {'status': 'pass', 'findings': []}

    # Verify export sanitizer accepts the generated PPTX cleanly.
    cleaned = sanitize_pptx(out.read_bytes(), 'deck.pptx', notes=[{'page_id': 'p1', 'notes': page['notes']}])
    assert cleaned[:2] == b'PK'

    # Verify SVG icon + rendered PNG companion + custom geometry + East Asian font tags exist in XML.
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
        slide_xml = etree.fromstring(archive.read('ppt/slides/slide1.xml'))
        svgs = [n for n in names if n.startswith('ppt/media/') and n.endswith('.svg')]
        pngs = [n for n in names if n.startswith('ppt/media/') and n.endswith('.png')]
        assert len(svgs) == 1
        assert len(pngs) == 2  # icon companion PNG + crop image PNG
        companions = native._svg_companion_pngs({n: archive.read(n) for n in names})
        assert len(companions) == 1
        assert archive.read(companions[0][0]).startswith(b'\x89PNG\r\n\x1a\n')
        assert slide_xml.find('.//a:custGeom', native.NS) is not None
        assert slide_xml.find('.//a:prstGeom[@prst="roundRect"]', native.NS) is not None
        assert slide_xml.find('.//a:ea', native.NS) is not None


def test_spike_emitter_27_page_benchmark_parity_and_speed_vs_node(tmp_path):
    font = _system_font()
    pages = []
    for i in range(27):
        page, _ = _make_sample_page(tmp_path, page_id=f'p{i + 1}', font=font, idx=i)
        pages.append(page)

    t0 = time.perf_counter()
    py_out, _, py_warnings = spike_emitter.generate(pages, tmp_path / 'py-27.pptx', mode='deck')
    py_elapsed = time.perf_counter() - t0
    assert py_warnings == []
    assert native.readback(py_out, pages) == {'status': 'pass', 'findings': []}
    cleaned = sanitize_pptx(
        py_out.read_bytes(),
        'deck.pptx',
        notes=[{'page_id': p['id'], 'notes': p['notes']} for p in pages],
    )
    assert cleaned[:2] == b'PK'

    t1 = time.perf_counter()
    node_out, _, node_warnings = native.generate(pages, tmp_path / 'node-27.pptx', mode='deck')
    node_elapsed = time.perf_counter() - t1
    assert node_warnings == []
    assert native.readback(node_out, pages) == {'status': 'pass', 'findings': []}

    py_prs = Presentation(str(py_out))
    node_prs = Presentation(str(node_out))
    assert len(py_prs.slides) == len(node_prs.slides) == 27
    # Sanity: pure-Python emitter must not be dramatically slower than Node.
    assert py_elapsed < max(15.0, node_elapsed * 4)


@pytest.mark.render
def test_spike_emitter_visual_diff_against_node_via_soffice(tmp_path):
    font = _system_font()
    page, plan = _make_sample_page(tmp_path, page_id='p1', font=font, idx=0)
    py_out, _, _ = spike_emitter.generate([page], tmp_path / 'py.pptx', mode='single')
    node_out, _, _ = native.generate([page], tmp_path / 'node.pptx', mode='single')

    resolved = resolve_fonts([{'shapes': [{'kind': 'text', 'font_family': font, 'bold': False}]}])
    py_imgs = render_deck(py_out, tmp_path / 'py-render', fonts=resolved)
    node_imgs = render_deck(node_out, tmp_path / 'node-render', fonts=resolved)
    assert len(py_imgs) == len(node_imgs) == 1

    with Image.open(py_imgs[0]) as a, Image.open(node_imgs[0]) as b:
        a_rgb = a.convert('RGB')
        b_rgb = b.convert('RGB').resize(a_rgb.size)
        diff = ImageChops.difference(a_rgb, b_rgb)
        histogram = diff.histogram()
        total_channels = a_rgb.size[0] * a_rgb.size[1] * 3
        mean_abs_diff = sum((idx % 256) * count for idx, count in enumerate(histogram)) / total_channels
        # Visually equivalent rendering: mean per-channel pixel diff under 12/255 (<5%).
        assert mean_abs_diff < 12.0, f'visual drift too high: mean_abs_diff={mean_abs_diff:.2f}'
