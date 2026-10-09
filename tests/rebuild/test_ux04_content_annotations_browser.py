"""UX-04 内容与共享单页反例（FINAL-REPAIR-PLAN AC13–AC15）。

- AC13/F06：正文编辑器的同文节点以"块 + 块内位置"区分（不再是无位置的
  全局序号）；分别修改其一，另一节点与业务事实不受影响；改文与影响预览
  同屏可核对；不确认即离开 = 取消，业务版本不变。
- AC15/F10：点/框意见的画布叠层与意见列表用同一产物身份规则——同一产物
  跨快照的意见仍正确定位（旧实现要求快照 revision 相等，列表"适用"而画布
  消失）；其它产物的意见不误叠。
- AC14：章节大纲块直达指定页；材料编辑—影响—确认连续与来源定位由
  test_content_ops.py / w09_content_inputs.py 既有覆盖。
"""
import copy
import re
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master import annotation_service
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_actions import commit

pytestmark = pytest.mark.browser

SAME_TEXT = '重复的句子内容完全一致。'


@pytest.fixture
def ux04_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux04-project'
    create_sample(path, page_count=2, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-04 checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def goto_page(page, url, identity, page_id, layer, revision):
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: args[1], layer: args[2], revision: args[3]})}",
                  [identity, page_id, layer, revision])
    from playwright.sync_api import expect
    expect(page.locator('#view-title')).to_contain_text('第 1 页')


def test_same_text_body_nodes_are_distinguishable_and_editable_separately(ux04_browser):
    from playwright.sync_api import expect
    from deck_master import content_ops
    from test_content_ops import commit as ops_commit, value as ops_value
    page, server, path, store = ux04_browser
    url = server.start()
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    visible = copy.deepcopy(store.read_object_json(entry['page'])['customer_visible'])
    visible['body_blocks'] = [
        {'id': 'b1', 'type': 'paragraph', 'text': SAME_TEXT},
        {'id': 'b2', 'type': 'bullets', 'heading': '发布检查单', 'items': [
            {'id': 'i1', 'text': SAME_TEXT}, {'id': 'i2', 'text': '不同的另一句。'}]},
    ]
    inp = ops_value(store, ids=('p01',))
    inp['customer_visible'] = visible
    ops_commit(path, store, inp)
    revision = store.current_revision_id()
    page.goto(url)
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']

    goto_page(page, url, identity, 'p01', 'content', revision)
    page.locator('.content-editor summary').click()
    expect(page.get_by_label('正文块 1 · 文字')).to_be_visible()
    expect(page.get_by_label('正文块 2 · 发布检查单 · 条目 1 · 文字')).to_be_visible()
    expect(page.get_by_label('正文块 2 · 发布检查单 · 条目 2 · 文字')).to_have_value('不同的另一句。')

    # 具体改动常驻：块位置 + 原文 → 改文，与影响预览同屏，不必自行对照文本框。
    changes = page.locator('.content-changes')
    expect(changes).to_contain_text('本次具体改动（0）')
    # 分别修改其一：另一个同文节点保持原值；影响预览同屏可核对。
    page.get_by_label('正文块 1 · 文字').fill('第一块已改写为新的表述。')
    expect(page.get_by_label('正文块 2 · 发布检查单 · 条目 1 · 文字')).to_have_value(SAME_TEXT)
    expect(changes).to_contain_text('本次具体改动（1）')
    row = changes.locator('.content-change-list li').first
    expect(row.locator('.content-change-label')).to_have_text('正文块 1 · 文字')
    expect(row.locator('.content-change-before')).to_have_text(SAME_TEXT)
    expect(row.locator('.content-change-after')).to_have_text('第一块已改写为新的表述。')
    page.get_by_label('正文块 2 · 发布检查单 · 条目 1 · 文字').fill('第二块按自己的位置单独改写。')
    expect(changes).to_contain_text('本次具体改动（2）')
    expect(changes.locator('.content-change-list li').nth(1).locator('.content-change-before')).to_have_text(SAME_TEXT)
    expect(changes.locator('.content-change-list li').nth(1).locator('.content-change-after')).to_have_text('第二块按自己的位置单独改写。')
    page.get_by_role('button', name='预览正文修改影响', exact=True).click()
    expect(page.locator('.content-operation')).to_contain_text('本次影响预览')
    expect(page.locator('.content-operation')).to_contain_text('修改 1 页')

    # 不确认即离开 = 取消：业务版本与已保存内容不变。
    before = store.read_current()
    page.get_by_role('button', name='制作总览', exact=True).click()
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    assert store.read_current() == before


@pytest.mark.parametrize('location_kind', ['point', 'rect'])
def test_point_overlay_follows_artifact_identity_across_snapshots(ux04_browser, location_kind):
    from playwright.sync_api import expect
    page, server, path, store = ux04_browser
    url = server.start()
    page.goto(url)
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    doc = store.load_document()
    p01 = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    p02 = next(e for e in doc['pages'] if e['page_id'] == 'p02')
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'scope': 'artifact', 'page_id': 'p01', 'page_ref': p01['page'], 'layer': 'original_image',
            'artifact_ref': p01['blueprint'], 'intent': 'clarify', 'body': '跨版本点意见：徽标位置', 'status': 'open',
            'location': {'kind': 'point', 'canvas': {'width': 960, 'height': 540}, 'x': 0.5, 'y': 0.5}}
    foreign = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
               'scope': 'artifact', 'page_id': 'p02', 'page_ref': p02['page'], 'layer': 'original_image',
               'artifact_ref': p02['blueprint'], 'intent': 'clarify', 'body': '另一页的意见不叠到本页', 'status': 'open',
               'location': {'kind': 'point', 'canvas': {'width': 960, 'height': 540}, 'x': 0.2, 'y': 0.2}}
    if location_kind == 'rect':
        note['location'] = {'kind': 'rect', 'canvas': {'width': 960, 'height': 540},
                            'x': 0.3, 'y': 0.3, 'width': 0.2, 'height': 0.2}
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'],
                                         'annotations': [note, foreign]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    # 快照前进（内容不变的版本更新）：同一产物，意见保持适用。
    commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
    revision = store.current_revision_id()
    assert revision != doc['revision_id']

    goto_page(page, url, identity, 'p01', 'original_image', revision)
    page.locator('[data-image-state="ready"] canvas:visible').first.wait_for()
    panel = page.locator('.annotations-panel')
    expect(panel).to_contain_text('跨版本点意见：徽标位置')
    # 同产物跨快照：画布叠层仍然绘制（旧实现要求 revision 相等，画布消失）。
    expect(page.locator('.annotation-mark.saved')).to_have_count(1)
    # 其它产物的意见只出现在"其它页面"分组（展开后可见），不叠到本页画布。
    foreign_group = panel.locator('details.saved-group').filter(has_text='其它页面的局部意见')
    foreign_group.locator('summary').click()
    expect(foreign_group.locator('.saved-opinion').filter(has_text='另一页的意见不叠到本页')).to_be_visible()
    assert page.locator('.annotation-mark.saved').count() == 1
    changed = copy.deepcopy(store.load_document())
    changed['pages'][0]['blueprint'] = store.put_json_object({
        **store.read_object_json(changed['pages'][0]['blueprint']),
        'limitations': ['Synthetic replacement basis; old locations must not overlay it']})
    commit(store, changed, str(uuid.uuid4()))
    page.get_by_role('button', name='制作总览', exact=True).click()
    goto_page(page, url, identity, 'p01', 'original_image', store.current_revision_id())
    page.locator('[data-image-state="ready"] canvas:visible').first.wait_for()
    expect(page.locator('.annotation-mark.saved')).to_have_count(0)


def test_outline_block_reaches_its_pages_and_return_keeps_surface(ux04_browser):
    """AC14：章节大纲块显示页范围并直达逐页稿；返回时工作面与阅读位置保持。"""
    from playwright.sync_api import expect
    page, server, path, store = ux04_browser
    url = server.start()
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    # 大纲块显示章节与页范围（合成样例为单章"第 1–2 页"），并可在章节内指定页直达，
    # 不再固定打开"首个匹配页"。
    outline = page.locator('.outline-block').first
    expect(outline).to_contain_text('第 1–2 页')
    chapter_pages = outline.get_by_label('章节内页面', exact=False)
    assert chapter_pages.locator('option').count() == 2
    chapter_pages.select_option(value='p02')
    outline.get_by_role('button', name='打开所选页', exact=True).click()
    expect(page.locator('#view-title')).to_contain_text('第 2 页')
    assert 'surface=page' in page.url and 'layer=content' in page.url
    # 返回内容与来源：工作面可达，大纲仍在。
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    expect(page.locator('.outline-block').first).to_be_visible()


@pytest.mark.parametrize('width,height', [(1440, 900), (1280, 800), (390, 844)])
def test_icon_opinions_distinguish_same_text_layers_and_old_basis(ux04_browser, width, height):
    from playwright.sync_api import expect
    page, server, path, store = ux04_browser
    page.set_viewport_size({'width': width, 'height': height})
    doc = copy.deepcopy(store.load_document()); entry = doc['pages'][0]
    artifact = {**store.read_object_json(entry['blueprint']), 'role': 'svg', 'media_type': 'image/svg+xml',
                'file': store.put_blob(b'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><rect width="960" height="540" fill="white"/></svg>', ext='svg')}
    entry['svg'] = store.put_json_object(artifact)
    commit(store, doc, str(uuid.uuid4()))
    doc = store.load_document(); entry = doc['pages'][0]
    base = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'],
            'base_revision': doc['revision_id'], 'scope': 'artifact', 'page_id': 'p01',
            'page_ref': entry['page'], 'intent': 'clarify', 'body': '相同的图标意见', 'status': 'open'}
    old = {**base, 'layer': 'original_image', 'artifact_ref': entry['blueprint'],
           'location': {'kind': 'point', 'canvas': {'width': 960, 'height': 540}, 'x': 0.2, 'y': 0.3}}
    svg = {**base, 'layer': 'svg', 'artifact_ref': entry['svg'],
           'location': {'kind': 'rect', 'canvas': {'width': 960, 'height': 540}, 'x': 0.3, 'y': 0.4, 'width': 0.1, 'height': 0.2}}
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'], 'annotations': [old, svg]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    doc = copy.deepcopy(store.load_document())
    artifact = {**store.read_object_json(entry['blueprint']), 'limitations': ['Synthetic changed original basis for identity acceptance']}
    doc['pages'][0]['blueprint'] = store.put_json_object(artifact)
    commit(store, doc, str(uuid.uuid4()))
    doc = store.load_document()
    current = {**old, 'base_revision': doc['revision_id'], 'artifact_ref': doc['pages'][0]['blueprint'], 'location': {'kind': 'whole'}}
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'], 'annotations': [current]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    records = annotation_service.list_annotations(path)['annotations']
    old_record = next(row for row in records if row['annotation'].get('artifact_ref') == old['artifact_ref'])
    old_ref = old_record['ref']
    url = server.start(); page.goto(url)
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    goto_page(page, url, identity, 'p01', 'svg', store.current_revision_id())
    # 图标清单在五工具容器的「图标优化」面:先切面(窄屏先开工具面板)。
    tools_entry = page.get_by_role('button', name='工具', exact=True)
    if tools_entry.is_visible(): tools_entry.click()
    page.get_by_role('button', name='图标优化', exact=True).click()
    labels = page.locator('.icon-opinions label')
    expect(labels).to_have_count(3)
    stale = labels.filter(has_text='旧底稿意见 · 需重新定位')
    expect(stale).to_have_count(1)
    expect(stale).to_contain_text('原图 · 点位 20% / 30%')
    expect(labels.filter(has_text='SVG · 框选')).to_contain_text('与当前产物一致')
    expect(labels.filter(has_text='原图 · 整图文字定位')).to_contain_text('与当前产物一致')
    stale.locator('input').check()
    page.evaluate("() => {window.iconCopy=null;Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.iconCopy=text;}}});}")
    page.get_by_role('button', name='复制给 Agent 的图标要求', exact=True).click()
    expect(page.locator('.icon-workbench [role=status]')).to_contain_text('图标要求已复制')
    payload = page.evaluate('JSON.parse(window.iconCopy)')
    assert payload['annotation_refs'] == [old_ref] and payload['opinions'] == [old_record['annotation']]
    output = Path('output/playwright/pr103-complete/icon-identities'); output.mkdir(parents=True, exist_ok=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert all(label.bounding_box()['height'] >= 44 for label in labels.all())
    page.screenshot(path=str(output/f'same-text-three-bases-{width}.png'), full_page=True)


def test_same_text_ranges_validate_per_node_and_feed_text_annotation(ux04_browser):
    """UAC14/X05:同文两节点各自精确定位——同范围选段在两个对象上都校验通过,
    但 ref/locator 各指各块;「文本意见」模式下选段进入意见区域。"""
    from playwright.sync_api import expect
    from deck_master import content_ops
    from test_content_ops import commit as ops_commit, value as ops_value
    page, server, path, store = ux04_browser
    url = server.start()
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    visible = copy.deepcopy(store.read_object_json(entry['page'])['customer_visible'])
    visible['body_blocks'] = [
        {'id': 'b1', 'type': 'paragraph', 'text': SAME_TEXT},
        {'id': 'b2', 'type': 'bullets', 'heading': '发布检查单', 'items': [
            {'id': 'i1', 'text': SAME_TEXT}, {'id': 'i2', 'text': '不同的另一句。'}]},
    ]
    inp = ops_value(store, ids=('p01',))
    inp['customer_visible'] = visible
    ops_commit(path, store, inp)
    revision = store.current_revision_id()
    page.goto(url)
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    goto_page(page, url, identity, 'p01', 'content', revision)
    page.get_by_text('正文原文与精确选段', exact=True).first.click()
    select = page.get_by_label('选择原文文本对象')
    expect(select).to_be_visible()
    page.locator('.text-range-tools summary').first.click()
    tools = page.locator('.text-range-tools').first
    expect(page.get_by_role('button', name='校验原文选段', exact=True).first).to_be_enabled()
    # 记录到达阅读区的校验结果:两个同文对象的 locator 必须不同。
    page.evaluate("() => {window.__ranges = []; document.querySelector('[aria-label=\"页面内容\"]').addEventListener('text-range-validated', e => window.__ranges.push({ref: e.detail.selection.ref.sha256, locator: e.detail.selection.locator, start: e.detail.selection.start, end: e.detail.selection.end}));}")
    # 文本意见模式先就位:标注工具在折叠区内,先展开再切换。
    page.get_by_text('范围与标注工具', exact=True).click()
    page.get_by_role('button', name='文本意见', exact=True).click()
    # 文本源含标题等更短对象:按选项文本定位两个同文对象,而不是数组序号。
    import json as json_mod
    matching = select.locator('option').evaluate_all(
        '(os) => os.map((o, i) => o.textContent.endsWith(' + json_mod.dumps(SAME_TEXT) + ') ? String(i) : null).filter(Boolean)')
    assert len(matching) == 2, matching
    for index in matching:
        # 切换文本对象会重建选段工具(细节默认收起),每轮重新展开再填起止。
        select.select_option(str(index))
        page.locator('.text-range-tools summary').first.click()
        page.get_by_label('选段起点', exact=True).fill('0')
        page.get_by_label('选段终点', exact=True).fill(str(len(SAME_TEXT)))
        page.get_by_role('button', name='校验原文选段', exact=True).first.click()
        expect(page.locator('.text-range-tools p[role=status]').last).to_contain_text('选段已校验', timeout=20000)
    ranges = page.evaluate('() => window.__ranges')
    assert len(ranges) == 2 and ranges[0]['start'] == ranges[1]['start'] == 0, ranges
    assert ranges[0]['end'] == ranges[1]['end'] == len(SAME_TEXT)
    assert ranges[0]['locator'] != ranges[1]['locator'], 'same text in two nodes must keep distinct locators'
    assert ranges[0]['ref'] == ranges[1]['ref'], 'both belong to the same fixed page artifact'
    # 两次校验都已作为文本选段进入意见区域(区域按各自范围独立计数)。
    expect(page.locator('.annotation-regions .annotation-region')).to_have_count(2)
