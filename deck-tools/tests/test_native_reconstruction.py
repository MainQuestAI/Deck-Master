"""Synthetic file-only reconstruction, including the actual Node generator."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from lxml import etree
from PIL import Image, ImageDraw
from pptx import Presentation
import pytest

from deck_tools import native
from deck_tools.atoms import visible_atoms
from deck_tools.compiler.native import notes_records
from deck_tools.sanitize import OperationError, pptx as sanitize_pptx
from deck_tools.render import RendererError
from deck_tools.jobs import projection
from deck_tools.vendor.cyberppt.test_select_icon import SelectIconTests  # noqa: F401


@pytest.fixture
def sample(tmp_path):
    directory = tmp_path / 'native' / 'p1'
    directory.mkdir(parents=True)
    source = tmp_path / 'source.png'
    image = Image.new('RGB', (800, 450), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 80, 200, 200), fill='#225588')
    image.save(source)
    asset = directory / 'assets' / 'sample.png'
    asset.parent.mkdir()
    image.crop((10, 80, 110, 180)).save(asset)
    page = {'id': 'p1', 'content': {'title': '合成方案', 'body_blocks': [
        {'id': 'matrix', 'type': 'table', 'columns': [{'id': 'a', 'label': '合成项目'}, {'id': 'b', 'label': '合成数值'}],
         'rows': [{'id': 'one', 'cells': [{'column_id': 'a', 'display_text': '试验甲'}, {'column_id': 'b', 'display_text': '42'}]}]}]},
        'notes': '合成讲稿第一行\n合成讲稿第二行', 'source_image': str(source), 'plan': str(directory / 'plan.json')}
    atoms = visible_atoms(projection(page))
    cell = lambda a: {'text': a['text'], 'atom_id': a['atom_id']}
    plan = {'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450}, 'background': 'FFFFFF', 'ops': [
        {'op': 'shape', 'type': 'rect', 'bbox': [10, 10, 600, 50], 'fill': 'CCDDEE', 'line': {'color': '225588', 'width': 2}, 'radius': 8, 'flip': {'h': True}},
        {'op': 'text', **cell(atoms[0]), 'bbox': [20, 15, 500, 40], 'size': 28, 'color': '225588', 'weight': 'bold', 'align': 'left', 'valign': 'center'},
        {'op': 'icon', 'icon_id': 'tabler-outline/anchor', 'bbox': [650, 10, 40, 40], 'color': '225588'},
        {'op': 'image', 'file': 'assets/sample.png', 'bbox': [650, 70, 100, 100]},
        {'op': 'arrow', 'start': [620, 200], 'end': [720, 220], 'color': '225588', 'width': 2, 'arrowheads': {'end': 'triangle'}},
        {'op': 'table', 'bbox': [20, 100, 550, 120], 'col_widths': [350, 200], 'row_heights': [45, 75], 'size': 18, 'valign': 'center',
         'header_style': {'fill': '225588', 'color': 'FFFFFF', 'weight': 'bold', 'valign': 'center'},
         'cells': [[cell(atoms[1]), cell(atoms[2])], [cell(atoms[3]), cell(atoms[4])]]},
        {'op': 'shape', 'type': 'custom', 'bbox': [20, 260, 550, 60], 'points': [[550, 0], [550, 45], [530, 60], [20, 60], [0, 45], [0, 0]],
         'fill': 'none', 'line': {'color': '225588', 'width': 2, 'arrowheads': {'end': 'triangle'}}},
    ]}
    native.write_json(page['plan'], plan)
    return tmp_path, page, plan


def _second_page(page, plan):
    second = {**page, 'id': 'p2', 'plan': str(Path(page['plan']).with_name('second.json')),
              'notes': '整套第二页合成讲稿'}
    atoms = dict(zip(
        (a['atom_id'] for a in visible_atoms(projection(page))),
        (a['atom_id'] for a in visible_atoms(projection(second))), strict=True))
    plan = deepcopy(plan)
    plan['page'] = second['id']
    for op in plan['ops']:
        items = [cell for row in op['cells'] for cell in row] if op['op'] == 'table' else [op]
        for item in items:
            if 'atom_id' in item:
                item['atom_id'] = atoms[item['atom_id']]
    native.write_json(second['plan'], plan)
    return second


def test_validate_plan_covers_current_content(sample):
    _, page, plan = sample
    assert native.validate_plan(plan, page) == {'page': 'p1', 'atoms': 5}


def test_canvas_not_original_warns_only_when_pixels_differ(tmp_path):
    source = tmp_path / 'source.png'
    Image.new('RGB', (1672, 941), 'white').save(source)
    page, plan = _plan(
        {'title': '合成页'},
        [_text('atom:p1:title', '合成页', [20, 20, 400, 40])],
    )
    page['source_image'] = str(source)
    plan['canvas_px'] = {'w': 1280, 'h': 720}
    result = native.validate_plan(plan, page)
    assert [item['code'] for item in result['warnings']] == ['canvas_not_original']
    warning = result['warnings'][0]
    assert warning['level'] == 'warning'
    assert warning['plan_px'] == {'w': 1280, 'h': 720}
    assert warning['image_px'] == {'w': 1672, 'h': 941}
    assert '不阻止' in warning['message']
    plan['canvas_px'] = {'w': 1672, 'h': 941}
    matched = native.validate_plan(plan, page)
    assert 'canvas_not_original' not in [item['code'] for item in matched.get('warnings', [])]
    assert 'warnings' not in matched
    plan['canvas_px'] = {'w': 1280, 'h': 720}
    page['source_image'] = str(tmp_path / 'missing.png')
    skipped = native.validate_plan(plan, page)
    assert 'canvas_not_original' not in [item['code'] for item in skipped.get('warnings', [])]
    unread = tmp_path / 'notes.txt'
    unread.write_text('not an image', encoding='utf-8')
    page['source_image'] = str(unread)
    skipped = native.validate_plan(plan, page)
    assert 'canvas_not_original' not in [item['code'] for item in skipped.get('warnings', [])]


def _plan(content, ops, omitted=None):
    plan = {
        'schema': 'deck.native_plan.v1', 'page': 'p1',
        'canvas_px': {'w': 800, 'h': 450}, 'background': 'FFFFFF', 'ops': ops,
    }
    if omitted is not None:
        plan['omitted'] = omitted
    return {'id': 'p1', 'content': content, 'notes': ''}, plan


def _text(atom_id, text, bbox, size=24, **extra):
    return {'op': 'text', 'text': text, 'atom_id': atom_id, 'bbox': bbox, 'size': size,
            'color': '225588', **extra}


def _warning_codes(page, plan):
    result = native.validate_plan(plan, page)
    return result, [item['code'] for item in result.get('warnings', [])]


def test_repeated_long_atom_warns_and_keeps_exit_code(tmp_path):
    sentence = '一二三 四五六七八'
    page, plan = _plan(
        {'title': '合成页', 'body_blocks': [{'id': 'note', 'type': 'paragraph', 'text': sentence}]},
        [
            _text('atom:p1:title', '合成页', [20, 20, 300, 40]),
            _text('atom:p1:block:note:text', sentence, [20, 80, 400, 40]),
            _text('atom:p1:block:note:text', sentence, [20, 140, 400, 40]),
        ],
    )
    result, codes = _warning_codes(page, plan)
    assert codes == ['repeated_atom']
    assert result['warnings'][0]['level'] == 'warning'
    assert result['warnings'][0]['count'] == 2
    assert result['warnings'][0]['atom_id'] == 'atom:p1:block:note:text'
    plan['ops'][2]['repeat'] = True
    result, codes = _warning_codes(page, plan)
    assert codes == []
    assert 'warnings' not in result
    job = tmp_path / 'job.json'
    native.write_json(tmp_path / 'plan.json', plan)
    page['plan'] = str(tmp_path / 'plan.json')
    plan['ops'][2].pop('repeat')
    native.write_json(page['plan'], plan)
    native.write_json(job, {'page': page})
    completed = subprocess.run(
        [sys.executable, '-m', 'deck_tools', 'validate-plan', str(job)],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    answer = json.loads(completed.stdout)
    assert [item['code'] for item in answer['warnings']] == ['repeated_atom']


def test_short_repeat_and_per_card_column_titles_are_not_repeated_atoms():
    label = '合成列的分组标题'
    left = '左侧卡片里的合成说明'
    right = '右侧卡片里的合成说明'
    page, plan = _plan(
        {'title': '短名', 'body_blocks': [{
            'id': 'matrix', 'type': 'table',
            'columns': [{'id': 'name', 'label': label}],
            'rows': [
                {'id': 'left', 'cells': [{'column_id': 'name', 'display_text': left}]},
                {'id': 'right', 'cells': [{'column_id': 'name', 'display_text': right}]},
            ],
        }]},
        [
            _text('atom:p1:title', '短名', [20, 16, 200, 36]),
            _text('atom:p1:title', '短名', [240, 16, 200, 36]),
            _text('atom:p1:column:matrix:name:label', label, [160, 70, 200, 30], size=22),
            _text('atom:p1:column:matrix:name:label', label, [480, 70, 200, 30], size=22),
            _text('atom:p1:cell:matrix:left:name:display_text', left, [160, 120, 200, 40], size=28),
            _text('atom:p1:cell:matrix:right:name:display_text', right, [480, 120, 200, 40], size=28),
        ],
    )
    result, codes = _warning_codes(page, plan)
    assert codes == []
    assert 'warnings' not in result
    plan['ops'][3]['bbox'] = [160, 110, 200, 30]
    result, codes = _warning_codes(page, plan)
    assert codes == ['repeated_atom']
    assert result['warnings'][0]['atom_id'] == 'atom:p1:column:matrix:name:label'


def test_card_above_table_can_mark_the_second_drawing():
    sentence = '上图和下表各画一次的合成句子'
    page, plan = _plan(
        {'title': '合成页', 'body_blocks': [{
            'id': 'matrix', 'type': 'table',
            'columns': [{'id': 'item', 'label': '项目'}],
            'rows': [{'id': 'one', 'cells': [{'column_id': 'item', 'display_text': sentence}]}],
        }]},
        [
            _text('atom:p1:title', '合成页', [20, 16, 300, 36]),
            _text('atom:p1:cell:matrix:one:item:display_text', sentence, [40, 70, 360, 40]),
            {'op': 'table', 'bbox': [40, 200, 360, 80], 'col_widths': [360], 'row_heights': [36, 44],
             'cells': [[
                 {'text': '项目', 'atom_id': 'atom:p1:column:matrix:item:label'},
             ], [
                 {'text': sentence, 'atom_id': 'atom:p1:cell:matrix:one:item:display_text'},
             ]]},
        ],
    )
    _result, codes = _warning_codes(page, plan)
    assert codes == ['repeated_atom']
    plan['ops'][1]['repeat'] = True
    _result, codes = _warning_codes(page, plan)
    assert codes == []


def test_orphan_column_label_warns_for_a_small_label_over_separate_groups():
    left = '左侧卡片标题'
    right = '右侧卡片标题'
    content = {'title': '合成页', 'body_blocks': [{
        'id': 'matrix', 'type': 'table',
        'columns': [{'id': 'name', 'label': '模块'}],
        'rows': [
            {'id': 'left', 'cells': [{'column_id': 'name', 'display_text': left}]},
            {'id': 'right', 'cells': [{'column_id': 'name', 'display_text': right}]},
        ],
    }]}
    label = _text('atom:p1:column:matrix:name:label', '模块', [20, 80, 80, 24], size=14)
    ops = [
        _text('atom:p1:title', '合成页', [20, 16, 300, 36]),
        label,
        _text('atom:p1:cell:matrix:left:name:display_text', left, [160, 80, 200, 40], size=32),
        _text('atom:p1:cell:matrix:right:name:display_text', right, [480, 80, 200, 40], size=32),
    ]
    _result, codes = _warning_codes(*_plan(content, ops))
    assert codes == ['orphan_column_label']
    label['size'] = 36
    _result, codes = _warning_codes(*_plan(content, ops))
    assert codes == []
    label['size'] = 14
    ops[3]['bbox'] = [160, 140, 200, 40]
    _result, codes = _warning_codes(*_plan(content, ops))
    assert codes == []


def test_column_label_can_be_omitted_with_a_reason_and_other_atoms_cannot():
    sentence = '仍然要画出来的合成单元格'
    content = {'title': '合成页', 'body_blocks': [{
        'id': 'matrix', 'type': 'table',
        'columns': [{'id': 'name', 'label': '模块'}],
        'rows': [{'id': 'one', 'cells': [{'column_id': 'name', 'display_text': sentence}]}],
    }]}
    drawn = [
        _text('atom:p1:title', '合成页', [20, 16, 300, 36]),
        _text('atom:p1:cell:matrix:one:name:display_text', sentence, [40, 80, 360, 40]),
    ]
    omitted = [{'atom_id': 'atom:p1:column:matrix:name:label', 'reason': '原图没有单独画出这一列名'}]
    result, codes = _warning_codes(*_plan(content, drawn, omitted))
    assert codes == []
    assert result['atoms'] == 2
    cell_page, cell_plan = _plan(
        content, drawn,
        [{'atom_id': 'atom:p1:cell:matrix:one:name:display_text', 'reason': '想省掉正文'}],
    )
    with pytest.raises(ValueError, match='只有表格列名'):
        native.validate_plan(cell_plan, cell_page)
    blank_page, blank_plan = _plan(
        content, drawn,
        [{'atom_id': 'atom:p1:column:matrix:name:label', 'reason': '  '}],
    )
    with pytest.raises(ValueError, match='写明理由'):
        native.validate_plan(blank_plan, blank_page)
    missing_page, missing_plan = _plan(content, drawn)
    with pytest.raises(ValueError, match='缺少正文 atom'):
        native.validate_plan(missing_plan, missing_page)


@pytest.mark.parametrize('radius', [0, 8])
def test_validate_plan_rejects_radius_on_ellipse(sample, radius):
    _, page, plan = sample
    plan['ops'][0].update(type='ellipse', radius=radius)
    with pytest.raises(ValueError):
        native.validate_plan(plan, page)


@pytest.mark.parametrize('shape_type', ['rect', 'roundRect'])
@pytest.mark.parametrize('dimension', [2, 3])
def test_generator_skips_radius_adjustment_for_zero_size(sample, shape_type, dimension):
    work, page, plan = sample
    plan['ops'][0]['type'] = shape_type
    plan['ops'][0]['bbox'][dimension] = 0
    native.write_json(page['plan'], plan)
    output, _, _ = native.generate([page], work / 'zero-size.pptx', mode='single')
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read('ppt/slides/slide1.xml'))
    shape = root.xpath('//p:sp[p:nvSpPr/p:cNvPr/@name="native_0"]', namespaces=native.NS)[0]
    geometry = shape.find('p:spPr/a:prstGeom', native.NS)
    assert geometry.get('prst') == shape_type
    assert geometry.find('a:avLst/a:gd', native.NS) is None


@pytest.mark.parametrize('target', ['table', 'header', 'cell'])
@pytest.mark.parametrize('value', [-1, [1, 2, 3], [1, 2, -3, 4], '8', True, None, float('inf'), [0, 0, float('nan'), 0]])
def test_validate_plan_rejects_invalid_table_margin(sample, target, value):
    _, page, plan = sample
    table = next(op for op in plan['ops'] if op['op'] == 'table')
    item = {'table': table, 'header': table['header_style'], 'cell': table['cells'][1][0]}[target]
    item['margin'] = value
    with pytest.raises(ValueError):
        native.validate_plan(plan, page)


@pytest.mark.parametrize('fault', ['missing_atom', 'outside', 'background_image', 'unknown_icon', 'changed_text', 'image_text', 'composite'])
def test_validate_plan_rejects_invalid_input(sample, fault):
    _, page, original = sample
    plan = deepcopy(original)
    if fault == 'missing_atom':
        del plan['ops'][1]
    elif fault == 'outside':
        plan['ops'][1]['bbox'][0] = 790
    elif fault == 'background_image':
        plan['ops'][3]['bbox'] = [0, 0, 800, 450]
    elif fault == 'unknown_icon':
        plan['ops'][2]['icon_id'] = 'tabler-outline/synthetic-missing-icon'
    elif fault == 'changed_text':
        page['content']['title'] = '修改后的合成标题'
    elif fault == 'image_text':
        plan['ops'][3]['text'] = '图里不能放正文'
    else:
        plan['ops'].append({'op': 'loop', 'bbox': [20, 250, 500, 50]})
    with pytest.raises(ValueError):
        native.validate_plan(plan, page)


@pytest.mark.parametrize('mode', ['single', 'deck'])
def test_generator_readback_and_shared_xml_postprocessing(sample, mode):
    work, page, plan = sample
    pages = [page] if mode == 'single' else [page, _second_page(page, plan)]
    output, _, _ = native.generate(pages, work / f'{mode}.pptx', mode=mode)
    presentation = Presentation(output)
    assert len(presentation.slides) == len(pages)
    with zipfile.ZipFile(output) as archive:
        assert 'ppt/embeddings/' not in archive.namelist()
        for i, (slide, expected) in enumerate(zip(presentation.slides, pages), 1):
            root = etree.fromstring(archive.read(f'ppt/slides/slide{i}.xml'))
            assert root.findall('.//a:t', native.NS)
            assert [e.text for e in root.findall('.//a:t', native.NS)] == [a['text'] for a in visible_atoms(projection(page))]
            assert len(root.findall('.//p:pic', native.NS)) == sum(op['op'] in ('icon', 'image') for op in plan['ops'])
            assert slide.notes_slide.notes_text_frame.text == expected['notes']
            assert slide.name == expected['id']
            assert {e.get('typeface') for e in root.findall('.//a:rPr/a:latin', native.NS)} == {'Noto Sans CJK SC'}
            assert {tc.get('anchor') for tc in root.findall('.//a:tcPr', native.NS)} == {'ctr'}
            for row, margins in zip(root.findall('.//a:tr', native.NS), ([5, 8, 5, 8], [7, 9, 7, 9])):
                for tc in row.findall('a:tc/a:tcPr', native.NS):
                    assert int(tc.get('marL')) > 0
                    for side, px in zip(('marT', 'marR', 'marB', 'marL'), margins):
                        assert int(tc.get(side)) == pytest.approx(px * native.emu_per_px(plan), abs=2)
            body = root.find('.//p:sp/p:txBody/a:bodyPr', native.NS)
            assert [int(body.get(side)) for side in ('tIns', 'rIns', 'bIns', 'lIns')] == [0, 0, 0, 0]
            assert [int(tr.get('h')) for tr in root.findall('.//a:tr', native.NS)] == [round(h * native.emu_per_px(plan)) for h in [45, 75]]
            custom = root.xpath('//p:sp[p:nvSpPr/p:cNvPr/@name="native_6"]', namespaces=native.NS)[0]
            assert custom.find('p:spPr/a:custGeom', native.NS) is not None
            assert custom.find('p:spPr/a:ln/a:tailEnd', native.NS).get('type') == 'triangle'
        theme = archive.read('ppt/theme/theme1.xml').decode()
        assert theme.count('typeface="Noto Sans CJK SC"') >= 2
        pres = etree.fromstring(archive.read('ppt/presentation.xml'))
        assert list(pres).index(pres.find('p:notesMasterIdLst', native.NS)) < list(pres).index(pres.find('p:sldIdLst', native.NS))


@pytest.mark.parametrize('canvas_width', [800, 1672])
@pytest.mark.parametrize('table_margin,header_margin,cell_margin', [
    (4, None, None),
    ([1, 2, 3, 4], 6, [0, 2, 3, 4]),
    (3, 0, 0),
    (None, None, [140, 3, 4, 5]),
])
def test_generator_table_margin_overrides(sample, canvas_width, table_margin, header_margin, cell_margin):
    work, page, plan = sample
    plan['canvas_px']['w'] = canvas_width
    table = next(op for op in plan['ops'] if op['op'] == 'table')
    if table_margin is not None:
        table['margin'] = table_margin
    if header_margin is not None:
        table['header_style']['margin'] = header_margin
    if cell_margin is not None:
        table['cells'][0][0]['margin'] = cell_margin
        table['cells'][1][0]['margin'] = cell_margin
    native.write_json(page['plan'], plan)
    output, _, _ = native.generate([page], work / 'margins.pptx', mode='single')
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read('ppt/slides/slide1.xml'))
    for r, row in enumerate(root.findall('.//a:tr', native.NS)):
        expected = [5, 8, 5, 8] if r == 0 else [7, 9, 7, 9]
        if table_margin is not None:
            expected = table_margin
        if r == 0 and header_margin is not None:
            expected = header_margin
        for c, tc in enumerate(row.findall('a:tc/a:tcPr', native.NS)):
            pixels = cell_margin if c == 0 and cell_margin is not None else expected
            margins = pixels if isinstance(pixels, list) else [pixels] * 4
            for side, px in zip(('marT', 'marR', 'marB', 'marL'), margins):
                assert int(tc.get(side)) == pytest.approx(px * native.emu_per_px(plan), abs=2)



def _with_canvas(page, plan, w, h, name):
    path = Path(page['plan']).parent / f'{name}.json'
    native.write_json(path, {**plan, 'canvas_px': {'w': w, 'h': h}})
    return {**page, 'plan': str(path)}


def test_generator_fixes_slide_width_and_keeps_source_aspect(sample):
    work, page, plan = sample
    wide = _with_canvas(page, plan, 1672, 941, 'wide')
    output, _, _ = native.generate([wide], work / 'wide.pptx', mode='single')
    presentation = Presentation(output)
    assert presentation.slide_width == pytest.approx(13.333 * 914400, abs=2)
    assert presentation.slide_height == pytest.approx(13.333 * 914400 * 941 / 1672, abs=2)
    table = next(shape for shape in presentation.slides[0].shapes if shape.has_table)
    assert table.left == pytest.approx(20 * 13.333 * 914400 / 1672, abs=2)


def test_deck_mode_rejects_mixed_canvas_sizes(sample):
    work, page, plan = sample
    other = _with_canvas(page, plan, 1672, 941, 'other')
    with pytest.raises(RendererError, match='画布尺寸必须一致'):
        native.generate([page, other], work / 'mixed.pptx', mode='deck')

def test_postprocessor_repairs_duplicate_paragraph_properties(sample):
    work, page, plan = sample
    output, _, _ = native.generate([page], work / 'duplicate.pptx', mode='single')
    with zipfile.ZipFile(output) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    root = etree.fromstring(files['ppt/slides/slide1.xml'])
    para = root.find('.//a:p', native.NS)
    etree.SubElement(para, f'{{{native.NS["a"]}}}pPr')
    etree.SubElement(para, f'{{{native.NS["a"]}}}pPr')
    root.find('.//a:tcPr', native.NS).set('anchor', 'mid')
    root.find('.//a:tr', native.NS).set('h', '1')
    files['ppt/slides/slide1.xml'] = etree.tostring(root)
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    native.postprocess(output, [plan])
    with zipfile.ZipFile(output) as archive:
        root = etree.fromstring(archive.read('ppt/slides/slide1.xml'))
    assert all(len(p.findall('a:pPr', native.NS)) <= 1 for p in root.findall('.//a:p', native.NS))
    assert root.find('.//a:tcPr', native.NS).get('anchor') == 'ctr'
    assert int(root.find('.//a:tr', native.NS).get('h')) == round(45 * native.emu_per_px(plan))


def test_crop_and_validate_plan_json_entrypoint(sample):
    work, page, _ = sample
    def invoke(command, job):
        path = work / 'job.json'
        native.write_json(path, job)
        result = subprocess.run([sys.executable, '-m', 'deck_tools', command, str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    cropped = invoke('crop', {'work': str(work), 'page': page, 'id': 'cropped', 'box': [10, 80, 100, 100]})
    with Image.open(cropped['file']) as image:
        assert image.size == (100, 100)
        assert image.getpixel((1, 1)) == (34, 85, 136)
    assert invoke('validate-plan', {'page': page})['atoms'] == 5


@pytest.mark.parametrize('existing_deck', [None, b'synthetic existing deck'])
def test_assemble_rejects_private_notes_with_adapter_error(sample, existing_deck):
    work, page, _ = sample
    page['notes'] = '合成路径 /Users/x/demo'
    job = work / 'job.json'
    native.write_json(job, {'work': str(work), 'pages': [page]})
    output = work / 'native' / 'deck.pptx'
    if existing_deck is not None:
        output.write_bytes(existing_deck)
    result = subprocess.run([sys.executable, '-m', 'deck_tools', 'assemble', str(job)], capture_output=True, text=True)
    assert result.returncode == 4
    assert 'notes.body' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not result.stdout
    if existing_deck is None:
        assert not output.exists()
        assert not list(output.parent.glob('*.pptx'))
    else:
        assert output.read_bytes() == existing_deck
        assert list(output.parent.glob('*.pptx')) == [output]


def test_icon_only_assemble_sanitizes_png_companions(tmp_path, monkeypatch):
    """An icon-only subset used to store SVG XML in image-1-1.png."""
    plan_path = tmp_path / 'plan.json'
    page = {'id': 'p1', 'content': {'title': '合成图标页'}, 'notes': '合成讲稿', 'plan': str(plan_path)}
    plan = {'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450},
            'background': 'FFFFFF', 'ops': [
                {'op': 'icon', 'icon_id': 'tabler-outline/anchor', 'bbox': [20, 20, 40, 40], 'color': '225588'}]}
    native.write_json(plan_path, plan)
    second_plan = tmp_path / 'second.json'
    second = {**page, 'id': 'p2', 'plan': str(second_plan), 'notes': '第二页讲稿'}
    native.write_json(second_plan, {**plan, 'page': 'p2'})
    pages = [page, second]

    def fake_render(pptx, directory, fonts):
        assert Path(pptx).is_file()
        made = []
        for index in range(len(pages)):
            image = Path(directory) / f'slide-{index}.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\nunused')
            made.append(image)
        return made

    monkeypatch.setattr(native, 'render_deck', fake_render)
    result = native.assemble({'work': str(tmp_path), 'pages': pages})
    output = Path(result['pptx'])
    assert output == (tmp_path / 'native' / 'deck.pptx').resolve()
    source = etree.fromstring(native.icon_file('tabler-outline/anchor').read_bytes())
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        pngs = [name for name in names if name.startswith('ppt/media/') and name.endswith('.png')]
        svgs = [name for name in names if name.startswith('ppt/media/') and name.endswith('.svg')]
        assert 'ppt/media/image-1-1.png' in pngs
        assert pngs and len(pngs) == len(svgs)
        for name in pngs:
            assert archive.read(name).startswith(b'\x89PNG\r\n\x1a\n')
        for name in svgs:
            icon = etree.fromstring(archive.read(name))
            assert icon.xpath('//*[local-name()="path"]/@d') == source.xpath('//*[local-name()="path"]/@d')
    raster = tmp_path / 'raster.png'
    Image.new('RGB', (8, 8), '#225588').save(raster)
    plan['ops'].append({'op': 'image', 'file': str(raster), 'bbox': [80, 20, 8, 8]})
    native.write_json(plan_path, plan)
    mixed, _, _ = native.generate([page], tmp_path / 'mixed.pptx', mode='deck')
    payload = raster.read_bytes()
    with zipfile.ZipFile(mixed) as archive:
        stored = [archive.read(name) for name in archive.namelist()
                  if name.startswith('ppt/media/') and name.endswith('.png')]
        assert payload in stored
        assert all(item.startswith(b'\x89PNG\r\n\x1a\n') for item in stored)


def test_png_repair_does_not_replace_an_xml_image_asset(tmp_path):
    plan_path = tmp_path / 'plan.json'
    bad = tmp_path / 'bad.png'
    bad.write_bytes(b'<!-- not a png -->')
    page = {'id': 'p1', 'content': {'title': '合成图标页'}, 'notes': '合成讲稿', 'plan': str(plan_path)}
    plan = {'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450},
            'background': 'FFFFFF', 'ops': [
                {'op': 'icon', 'icon_id': 'tabler-outline/anchor', 'bbox': [20, 20, 40, 40], 'color': '225588'},
                {'op': 'image', 'file': str(bad), 'bbox': [80, 20, 8, 8]}]}
    native.write_json(plan_path, plan)
    output, _, _ = native.generate([page], tmp_path / 'mixed.pptx', mode='deck')
    with zipfile.ZipFile(output) as archive:
        payloads = [archive.read(name) for name in archive.namelist()
                    if name.startswith('ppt/media/') and name.endswith('.png')]
        assert b'<!-- not a png -->' in payloads
        assert any(item.startswith(b'\x89PNG\r\n\x1a\n') for item in payloads)
    with pytest.raises(OperationError):
        sanitize_pptx(output.read_bytes(), 'deck.pptx', notes=[{'page_id': 'p1', 'notes': '合成讲稿'}])


@pytest.mark.render
def test_svg_icon_png_fallback_is_rendered_not_the_red_x(tmp_path, monkeypatch):
    """A raster beside the icon makes PptxGenJS store its shared red-X PNG."""
    plan_path = tmp_path / 'plan.json'
    raster = tmp_path / 'raster.png'
    Image.new('RGB', (8, 8), '#225588').save(raster)
    page = {'id': 'p1', 'content': {}, 'notes': '合成讲稿', 'plan': str(plan_path)}
    # Wide box, square icon: the fallback keeps the SVG aspect at the display width.
    plan = {'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450},
            'background': 'FFFFFF', 'ops': [
                {'op': 'icon', 'icon_id': 'tabler-outline/anchor', 'bbox': [20, 20, 60, 30], 'color': '225588'},
                {'op': 'image', 'file': str(raster), 'bbox': [100, 20, 8, 8]}]}
    native.write_json(plan_path, plan)

    def fake_render(pptx, directory, fonts):
        assert Path(pptx).is_file()
        image = Path(directory) / 'slide.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\nunused')
        return [image]

    monkeypatch.setattr(native, 'render_deck', fake_render)
    result = native.assemble({'work': str(tmp_path), 'pages': [page]})
    assert result['findings']['status'] == 'pass'
    assert 'warnings' not in result['findings']
    with zipfile.ZipFile(result['pptx']) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    companions = native._svg_companion_pngs(files)
    assert len(companions) == 1
    png_name, svg_name, extent = companions[0]
    data = files[png_name]
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(data) != 1594
    assert not hashlib.sha1(data).hexdigest().startswith('7fb30585')
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        assert image.format == 'PNG'
        expected = max(1, round(extent[0] / 914400 * 192))
        assert expected > 1
        assert image.size == (expected, expected)
        assert image.convert('RGBA').getchannel('A').getextrema()[1] > 0
    others = [name for name in files if name.startswith('ppt/media/') and name.endswith('.png') and name != png_name]
    assert len(others) == 1
    with Image.open(io.BytesIO(files[others[0]])) as image:
        assert image.size == (8, 8)
    source = etree.fromstring(native.icon_file('tabler-outline/anchor').read_bytes())
    icon = etree.fromstring(files[svg_name])
    assert icon.xpath('//*[local-name()="path"]/@d') == source.xpath('//*[local-name()="path"]/@d')


def test_omitted_column_label_passes_assemble_readback_and_other_atoms_stay_required(tmp_path, monkeypatch):
    label = '模块'
    cell = '仍然要画出来的合成单元格'
    page = {'id': 'p1', 'content': {'title': '合成页', 'body_blocks': [{
        'id': 'matrix', 'type': 'table',
        'columns': [{'id': 'name', 'label': label}],
        'rows': [{'id': 'one', 'cells': [{'column_id': 'name', 'display_text': cell}]}],
    }]}, 'notes': '合成讲稿', 'plan': str(tmp_path / 'plan.json')}
    atoms = {atom['text']: atom for atom in visible_atoms(projection(page))}

    def drawn(texts):
        return [{
            'op': 'text', 'text': text, 'atom_id': atoms[text]['atom_id'],
            'bbox': [20, 20 + index * 60, 400, 40], 'size': 24, 'color': '225588',
        } for index, text in enumerate(texts)]

    plan = {
        'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450},
        'background': 'FFFFFF',
        'omitted': [{'atom_id': atoms[label]['atom_id'], 'reason': '原图没有单独画出这一列名'}],
        'ops': drawn(['合成页', cell]),
    }
    native.write_json(page['plan'], plan)

    def fake_render(pptx, directory, fonts):
        assert Path(pptx).is_file()
        image = Path(directory) / 'slide.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\nunused')
        return [image]

    monkeypatch.setattr(native, 'render_deck', fake_render)
    passed = native.assemble({'work': str(tmp_path), 'pages': [page]})
    assert passed['findings'] == {'status': 'pass', 'findings': []}
    plan['ops'] = drawn(['合成页'])
    native.write_json(page['plan'], plan)
    missed = native.assemble({'work': str(tmp_path), 'pages': [page]})
    missing = [item['atom_id'] for item in missed['findings']['findings']
               if item['code'] == 'missing_visible_atom']
    assert missing == [atoms[cell]['atom_id']]
    assert missed['findings']['status'] == 'fail'


def test_readback_reports_short_atom_hidden_inside_longer_text(tmp_path, monkeypatch):
    plan_path = tmp_path / 'plan.json'
    page = {'id': 'p1', 'content': {'title': '甲', 'body_blocks': [
        {'id': 'body', 'type': 'paragraph', 'text': '试验甲'}]}, 'notes': '合成讲稿', 'plan': str(plan_path)}
    atoms = {atom['text']: atom for atom in visible_atoms(projection(page))}
    longer = atoms['试验甲']
    plan = {'schema': 'deck.native_plan.v1', 'page': 'p1', 'canvas_px': {'w': 800, 'h': 450},
            'background': 'FFFFFF', 'ops': [
                {'op': 'text', 'text': longer['text'], 'atom_id': longer['atom_id'],
                 'bbox': [20, 20, 400, 48], 'size': 28, 'color': '225588'}]}
    native.write_json(plan_path, plan)
    with pytest.raises(ValueError):
        native.validate_plan(plan, page)

    def fake_render(pptx, directory, fonts):
        assert Path(pptx).is_file()
        image = Path(directory) / 'slide.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\nunused')
        return [image]

    monkeypatch.setattr(native, 'render_deck', fake_render)
    result = native.assemble({'work': str(tmp_path), 'pages': [page]})
    assert Path(result['pptx']).is_file()
    missing = [item['text'] for item in result['findings']['findings']
               if item['code'] == 'missing_visible_atom']
    assert missing == ['甲']
    both = deepcopy(plan)
    both['ops'].append({'op': 'text', 'text': atoms['甲']['text'], 'atom_id': atoms['甲']['atom_id'],
                        'bbox': [20, 80, 80, 40], 'size': 28, 'color': '225588'})
    native.write_json(plan_path, both)
    output, deck_findings, _ = native.generate([page], tmp_path / 'both.pptx', mode='deck')
    assert deck_findings == []
    report = native.readback(output, [page])
    assert not any(item['code'] == 'missing_visible_atom' for item in report['findings'])


def _text_page(tmp_path, blocks, ops):
    plan_path = tmp_path / 'plan.json'
    page = {'id': 'p1', 'content': {'body_blocks': blocks}, 'notes': '合成讲稿', 'plan': str(plan_path)}
    native.write_json(plan_path, {'schema': 'deck.native_plan.v1', 'page': 'p1',
                                   'canvas_px': {'w': 800, 'h': 450}, 'background': 'FFFFFF', 'ops': ops})
    output, deck_findings, _ = native.generate([page], tmp_path / 'page.pptx', mode='deck')
    assert deck_findings == []
    return page, output


def test_readback_matches_overlapping_values_inside_separate_text_objects(tmp_path):
    blocks = [{'id': name, 'type': 'paragraph', 'text': text}
              for name, text in (('wide', '202'), ('mid', '20'), ('narrow', '2'))]
    page = {'id': 'p1', 'content': {'body_blocks': blocks}, 'notes': '', 'plan': ''}
    ops = []
    for index, atom in enumerate(visible_atoms(projection(page))):
        ops.append({'op': 'text', 'text': atom['text'], 'atom_id': atom['atom_id'],
                    'bbox': [20, 20 + index * 60, 160, 40], 'size': 24, 'color': '225588'})
    page, output = _text_page(tmp_path, blocks, ops)
    report = native.readback(output, [page])
    assert not any(item['code'] == 'missing_visible_atom' for item in report['findings'])


def test_readback_does_not_join_characters_around_a_consumed_span(tmp_path):
    blocks = [{'id': 'gap', 'type': 'paragraph', 'text': '甲乙'}]
    page = {'id': 'p1', 'content': {'title': '中间', 'body_blocks': blocks}, 'notes': '合成讲稿', 'plan': ''}
    ops = [{'op': 'text', 'text': '甲中间乙', 'bbox': [20, 20, 300, 40], 'size': 24, 'color': '225588'}]
    page, output = _text_page(tmp_path, [{'id': 'gap', 'type': 'paragraph', 'text': '甲乙'}], ops)
    page['content']['title'] = '中间'
    report = native.readback(output, [page])
    missing = [item['text'] for item in report['findings'] if item['code'] == 'missing_visible_atom']
    assert '甲乙' in missing


def test_generator_lookup_installed_then_development(tmp_path, monkeypatch):
    installed = tmp_path / 'share/deck/native-pptx'
    installed.mkdir(parents=True)
    (installed / 'render.cjs').write_text('// synthetic installed script')
    monkeypatch.setattr(native.sys, 'prefix', str(tmp_path / 'share/deck/venv'))
    assert native.native_pptx_dir() == installed
    (installed / 'render.cjs').unlink()
    assert native.native_pptx_dir().name == 'native-pptx'
    assert native.native_pptx_dir().parent.name == 'deck-tools'


@pytest.mark.render
def test_render_and_assemble_real_synthetic_source(sample):
    work, page, plan = sample
    pages = [page, _second_page(page, plan)]
    job = work / 'job.json'
    for current in pages:
        native.write_json(job, {'work': str(work), 'page': current})
        result = subprocess.run([sys.executable, '-m', 'deck_tools', 'render', str(job)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        answer = json.loads(result.stdout)
        for key in ('render_png', 'side_by_side'):
            with Image.open(answer[key]) as image:
                assert image.width > 0 and image.height > 0
        with Image.open(answer['side_by_side']) as image:
            assert image.size == (1600, 480)
        assert answer['findings'] == {'page': current['id'], 'atoms': 5}
        assert not (native.page_directory(work, current['id']) / 'status.json').exists()
    native.write_json(job, {'work': str(work), 'pages': pages})
    result = subprocess.run([sys.executable, '-m', 'deck_tools', 'assemble', str(job)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout)
    assert Path(answer['pptx']) == work / 'native/deck.pptx'
    assert len(answer['render_pngs']) == 2
    assert answer['findings'] == {'status': 'pass', 'findings': []}
    assert all(Path(image).is_file() for image in answer['render_pngs'])
    output = Path(answer['pptx'])
    assert [(r['page_id'], r['notes']) for r in notes_records(output.read_bytes())] == [
        (p['id'], p['notes']) for p in pages]
    presentation = Presentation(output)
    assert all(any(shape.has_table for shape in slide.shapes) for slide in presentation.slides)
    with zipfile.ZipFile(output) as archive:
        assert not any(name.startswith('docProps/') for name in archive.namelist())
        icons = [name for name in archive.namelist() if name.startswith('ppt/media/') and name.endswith('.svg')]
        assert len(icons) == 2
        source = etree.fromstring(native.icon_file('tabler-outline/anchor').read_bytes())
        for name in icons:
            icon = etree.fromstring(archive.read(name))
            assert icon.tag == source.tag
            assert icon.xpath('//*[local-name()="path"]/@d') == source.xpath('//*[local-name()="path"]/@d')
