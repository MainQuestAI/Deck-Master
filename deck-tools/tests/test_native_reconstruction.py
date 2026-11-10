"""Synthetic file-only reconstruction, including the actual Node generator."""
from copy import deepcopy
import hashlib
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


def test_validate_plan_covers_current_content(sample):
    _, page, plan = sample
    assert native.validate_plan(plan, page)['atoms'] == 5


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
    pages = [page] if mode == 'single' else [page, {**page, 'notes': '整套第二页合成讲稿'}]
    output = native.generate(pages, work / f'{mode}.pptx', mode=mode)
    presentation = Presentation(output)
    assert len(presentation.slides) == len(pages)
    with zipfile.ZipFile(output) as archive:
        for i, (slide, expected) in enumerate(zip(presentation.slides, pages), 1):
            root = etree.fromstring(archive.read(f'ppt/slides/slide{i}.xml'))
            assert root.findall('.//a:t', native.NS)
            assert [e.text for e in root.findall('.//a:t', native.NS)] == [a['text'] for a in visible_atoms(projection(page))]
            assert len(root.findall('.//p:pic', native.NS)) == sum(op['op'] in ('icon', 'image') for op in plan['ops'])
            assert slide.notes_slide.notes_text_frame.text == expected['notes']
            assert {e.get('typeface') for e in root.findall('.//a:rPr/a:latin', native.NS)} == {'Noto Sans CJK SC'}
            assert {tc.get('anchor') for tc in root.findall('.//a:tcPr', native.NS)} == {'ctr'}
            assert [int(tr.get('h')) for tr in root.findall('.//a:tr', native.NS)] == [round(h * native.EMU_PX) for h in [45, 75]]
            custom = root.xpath('//p:sp[p:nvSpPr/p:cNvPr/@name="native_6"]', namespaces=native.NS)[0]
            assert custom.find('p:spPr/a:custGeom', native.NS) is not None
            assert custom.find('p:spPr/a:ln/a:tailEnd', native.NS).get('type') == 'triangle'
        theme = archive.read('ppt/theme/theme1.xml').decode()
        assert theme.count('typeface="Noto Sans CJK SC"') >= 2
        pres = etree.fromstring(archive.read('ppt/presentation.xml'))
        assert list(pres).index(pres.find('p:notesMasterIdLst', native.NS)) < list(pres).index(pres.find('p:sldIdLst', native.NS))


def test_postprocessor_repairs_duplicate_paragraph_properties(sample):
    work, page, plan = sample
    output = native.generate([page], work / 'duplicate.pptx', mode='single')
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
    assert int(root.find('.//a:tr', native.NS).get('h')) == 45 * native.EMU_PX


@pytest.mark.parametrize('fault', ['side_by_side', 'note', 'plan_sha256'])
def test_assemble_rejects_unreviewed_or_changed_page(sample, fault):
    work, page, _ = sample
    directory = Path(page['plan']).parent
    status = {'plan_sha256': hashlib.sha256(Path(page['plan']).read_bytes()).hexdigest(),
              'render_png': 'render.png', 'side_by_side': 'side-by-side.png', 'note': '合成页对照完成'}
    (directory / 'render.png').write_bytes(b'synthetic render')
    (directory / 'side-by-side.png').write_bytes(b'synthetic comparison')
    if fault == 'side_by_side':
        (directory / 'side-by-side.png').unlink()
    else:
        status[fault] = ''
    native.write_json(directory / 'status.json', status)
    with pytest.raises(ValueError):
        native.assemble({'work': str(work), 'pages': [page]})


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
    work, page, _ = sample
    job = work / 'job.json'
    native.write_json(job, {'work': str(work), 'page': page})
    result = subprocess.run([sys.executable, '-m', 'deck_tools', 'render', str(job)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout)
    for key in ('render_png', 'side_by_side'):
        with Image.open(answer[key]) as image:
            assert image.width > 0 and image.height > 0
    with Image.open(answer['side_by_side']) as image:
        assert image.size == (1600, 480)
    status_path = Path(page['plan']).parent / 'status.json'
    status = native.read_json(status_path)
    assert not status['note']
    status['note'] = '合成页已逐项对照；此测试只验证生产链，不评价作品。'
    native.write_json(status_path, status)
    native.write_json(job, {'work': str(work), 'pages': [page]})
    result = subprocess.run([sys.executable, '-m', 'deck_tools', 'assemble', str(job)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout)
    assert Path(answer['pptx']) == work / 'native/deck.pptx'
    assert len(answer['render_pngs']) == 1
    assert Path(answer['render_pngs'][0]).is_file()
    assert Presentation(answer['pptx']).slides[0].notes_slide.notes_text_frame.text == page['notes']
