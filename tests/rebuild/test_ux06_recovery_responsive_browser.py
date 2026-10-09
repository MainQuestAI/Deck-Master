"""UX-06 恢复异常与响应式反例（FINAL-REPAIR-PLAN AC19–AC22，随实施追加）。

- AC20/F13：创建成功但打开失败后，主动作是"打开已创建的项目"而不是重新
  创建同一位置；修复路由后可打开同一项目，不重复创建、不覆盖。
- AC21/F13：styles.analyze 的待核实条目显示业务名称"截图风格分析"并有核实
  入口（此前显示为空段）。
- AC22/F15/D4：390px 下从零写图标要求可沿可见路径完成——拖拽工具与精确
  框选标注为桌面入口并保持隐藏，可见说明告知桌面入口；整页意见全程可用。
  关闭模态后焦点回到触发按钮由既有 test_page_shortcuts"连接状态"模态流程
  覆盖。
"""
import base64
import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

import copy
import uuid as uuid_lib
from xml.etree import ElementTree

from deck_master import icons
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store

# 与 test_icon_quality.icon_store 一致的合成 SVG 图层写入方式，为 F02 提供真实可读 SVG。
SVG_LAYER = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><text x="30" y="80" font-family="Arial" font-size="24">SYNTHETIC SVG LAYER</text></svg>'


def add_svg_layers(store):
    doc = store.load_document(); new = copy.deepcopy(doc)
    for entry in new['pages']:
        root = icons.tree(SVG_LAYER)
        root[0].set('font-family', 'Arial')
        original = store.read_object_json(entry['blueprint'])['file']['sha256']
        root.set('data-blueprint-sha256', original)
        artifact = store.read_object_json(entry['blueprint'])
        artifact['role'] = 'svg'; artifact['media_type'] = 'image/svg+xml'
        artifact['file'] = store.put_blob(ElementTree.tostring(root), ext='svg')
        entry['svg'] = store.put_json_object(artifact)
    new = bump_revision(new, {'operation_id': str(uuid_lib.uuid4()), 'kind': 'artifact_adoption',
                              'description': 'synthetic svg layers', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id=new['change']['operation_id'])
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser

PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


@pytest.fixture
def ux06_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux06-project'
    create_sample(path, page_count=2, readonly=False)
    store = Store(path)
    add_svg_layers(store)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-06 checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store, context
            assert errors == []
        finally:
            browser.close()
            server.stop()


def test_created_project_reopens_after_open_failure_without_recreating(ux06_browser):
    from playwright.sync_api import expect
    from deck_master import local_runtime
    page, server, path, store, context = ux06_browser
    import tempfile
    from pathlib import Path as P
    reg = P(tempfile.mkdtemp()) / 'registry.json'
    descriptor = local_runtime.descriptor(registry=reg)
    launcher = local_runtime.ensure(descriptor)
    try:
        await_recovery(page, launcher['url'], reg.parent)
    finally:
        local_runtime.stop(descriptor)

def await_recovery(page, root, parent_dir):
    from playwright.sync_api import expect
    page.goto(root)
    expect(page.get_by_role('button', name='新建项目', exact=True)).to_be_visible()

    page.get_by_role('button', name='新建项目', exact=True).click()
    dialog = page.locator('dialog[open]')
    dialog.get_by_label('项目名称（必填）').fill('恢复路径验证')
    dialog.get_by_label('用途（必填）').fill('验证创建成功后的打开恢复路径。')
    dialog.get_by_label('受众（必填）').fill('第一次使用工作台的人')
    dialog.get_by_label('保存到哪个文件夹（必填）').fill(str(parent_dir))
    dialog.get_by_label('新项目文件夹名（必填）').fill('recovery-target')

    # 打开这一步失败：项目已创建并登记，但打开请求丢失。
    open_calls, create_calls, opened_entry = [], [], []
    def lose_open(route):
        open_calls.append(route.request.post_data_json)
        route.fulfill(status=500, content_type='application/json',
                      body=json.dumps({'error': {'code': 'open_failed', 'message': '项目服务返回的位置无效，请从工作台重新打开。'}}))
    def count_create(route):
        create_calls.append(route.request.post_data_json)
        route.continue_()
    page.route('**/api/projects/open', lose_open)
    page.route('**/api/projects/create', count_create)
    dialog.get_by_role('button', name='创建项目', exact=True).click()
    form_error = page.locator('dialog[open] form > .field-error')
    expect(form_error).to_contain_text('重新打开')
    assert len(open_calls) == 1 and len(create_calls) == 1
    created_entry = create_calls[0] and open_calls[0] and open_calls[0].get('entry_id')

    # 主动作是「登记并打开这个位置」；登记按路径幂等，恢复点击打开的是同一个
    # 登记条目，create 不再被调用。
    recovery = page.locator('dialog[open]').get_by_role('button', name='登记并打开这个位置', exact=True)
    expect(recovery).to_be_visible()
    page.on('request', lambda request: opened_entry.append(request.url) if '/api/projects/create' in request.url else None)
    page.unroute('**/api/projects/open')
    recovery.click()
    page.wait_for_url(lambda pattern: '#project=' in page.url, timeout=20000)
    assert created_entry is not None and not opened_entry, '恢复路径不得再次创建'
    # 新建项目 0 页：初始工作面是"内容与来源"。
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for(timeout=20000)


def test_lost_create_response_offers_register_and_open_without_recreating(ux06_browser):
    """AC20：创建响应丢失时按已存在的位置核实——只登记并打开，不重复创建。"""
    from playwright.sync_api import expect
    from deck_master import local_runtime
    from deck_master.samples import create_sample as make_project
    page, server, path, store, context = ux06_browser
    import tempfile
    from pathlib import Path as P
    reg = P(tempfile.mkdtemp()) / 'registry.json'
    descriptor = local_runtime.descriptor(registry=reg)
    launcher = local_runtime.ensure(descriptor)
    target = reg.parent / 'lost-response-target'
    try:
        page.goto(launcher['url'])
        expect(page.get_by_role('button', name='新建项目', exact=True)).to_be_visible()
        page.get_by_role('button', name='新建项目', exact=True).click()
        dialog = page.locator('dialog[open]')
        dialog.get_by_label('项目名称（必填）').fill('响应丢失核实')
        dialog.get_by_label('用途（必填）').fill('核实创建响应丢失后的恢复动作。')
        dialog.get_by_label('受众（必填）').fill('第一次使用工作台的人')
        dialog.get_by_label('保存到哪个文件夹（必填）').fill(str(reg.parent))
        dialog.get_by_label('新项目文件夹名（必填）').fill('lost-response-target')
        # 位置已经真实存在：创建请求可能已执行，只是响应丢失。
        make_project(target, page_count=2, readonly=False)
        attempts = []
        page.route('**/api/projects/create', lambda route: (attempts.append(route.request.url), route.abort()))
        dialog.get_by_role('button', name='创建项目', exact=True).click()
        form_error = page.locator('dialog[open] form > .field-error')
        expect(form_error).to_contain_text('未能核实这次创建的结果')
        create_attempts = len(attempts)

        # 恢复动作只登记已存在的位置并打开，不再创建。
        page.route('**/api/projects/register', lambda route: route.abort(), times=1)
        page.locator('dialog[open]').get_by_role('button', name='登记并打开这个位置', exact=True).click()
        expect(page.locator('dialog[open]').get_by_role('button', name='登记并打开这个位置', exact=True)).to_be_enabled()
        assert len(attempts) == create_attempts
        page.locator('dialog[open]').get_by_role('button', name='登记并打开这个位置', exact=True).click()
        page.wait_for_url(lambda pattern: '#project=' in page.url, timeout=20000)
        assert len(attempts) == create_attempts, '恢复路径不得再次创建'
    finally:
        local_runtime.stop(descriptor)


def test_modal_close_returns_focus_to_the_surface_heading_when_trigger_is_removed(ux06_browser):
    """UX-06b：模态关闭后触发器已被重绘移除时，焦点回到工作面标题而不是 body。"""
    from playwright.sync_api import expect
    from deck_master import local_runtime
    page, server, path, store, context = ux06_browser
    import tempfile
    from pathlib import Path as P
    reg = P(tempfile.mkdtemp()) / 'registry.json'
    descriptor = local_runtime.descriptor(registry=reg)
    launcher = local_runtime.ensure(descriptor)
    try:
        page.goto(launcher['url'])
        expect(page.get_by_role('button', name='新建项目', exact=True)).to_be_visible()
        status = page.evaluate("""async p => {
          const {token} = await (await fetch('/api/session')).json();
          const response = await fetch('/api/projects/register', {method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Deck-Token': token}, body: JSON.stringify({path: p})});
          return response.status;
        }""", str(path))
        assert status == 200, status
        page.get_by_role('button', name='刷新项目列表', exact=True).click()
        card = page.locator('.project-card').first
        expect(card).to_be_visible()
        card.get_by_role('button', name='从列表移除', exact=True).click()
        dialog = page.locator('dialog[open]')
        dialog.get_by_role('button', name='移除条目', exact=True).click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(page.locator('.project-card')).to_have_count(0)
        # 触发器（列表行按钮）已被重绘移除：焦点回退到工作面标题。
        expect(page.locator('#view-title')).to_be_focused()
    finally:
        local_runtime.stop(descriptor)


def test_pending_style_analysis_shows_business_name_and_verify(ux06_browser):
    from playwright.sync_api import expect
    page, server, path, store, context = ux06_browser
    url = server.start()
    page.route('**/api/styles/references*', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'references': [{'reference': {'reference_id': 'ref-1', 'width': 96, 'height': 64},
                                         'preview': {'schema_version': 'deck_artifact.v1', 'artifact_id': 'reference-' + 64 * 'a',
                                         'file': {'path': f'.deckmaster/objects/ab/{64 * "a"}.png', 'sha256': 64 * 'a'}}}], 'fonts': []})))
    page.route('**/api/thumbnails*', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'status': 'ready', 'url': '/api/thumbnail-file?cache_key=' + 'a' * 64})))
    page.route('**/api/thumbnail-file*', lambda route: route.fulfill(status=200, content_type='image/png', body=PNG_1PX))
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    page.get_by_label('选用参考截图 1').check()
    page.get_by_label('截图风格要求').fill('分析这张截图的配色与文字层级。')
    page.route('**/api/styles/analyze', lambda route: route.abort())
    page.get_by_role('button', name='分析截图', exact=True).click()
    pending = page.locator('.business-pending')
    expect(pending).to_contain_text('截图风格分析')
    expect(pending).to_contain_text('核实保存结果')
    # 待核实条目给出真实目标：要求摘要与引用范围，而不是只有业务名称。
    expect(pending).to_contain_text('原请求目标：分析这张截图的配色与文字层级。')


def test_narrow_screen_icon_requirement_path_is_visible_and_completable(ux06_browser):
    from playwright.sync_api import expect
    from deck_master import annotation_service
    page, server, path, store, context = ux06_browser
    url = server.start()
    # SVG 图层上的区域意见（桌面入口产生）：窄屏下仍应在图标面板可选中。
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'],
                                         'annotations': [{'schema_version': 'annotation.v1', 'project_id': doc['project_id'],
                                                          'base_revision': doc['revision_id'], 'scope': 'artifact', 'page_id': 'p01',
                                                          'page_ref': entry['page'], 'layer': 'original_image', 'artifact_ref': entry['blueprint'],
                                                          'intent': 'clarify', 'body': '图标间距需要与正文对齐。', 'status': 'open',
                                                          'location': {'kind': 'whole'}}]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: args[1], layer: args[2], revision: args[3]})}",
                  [identity, 'p01', 'original_image', store.current_revision_id()])
    # D4-A:390px 工具在全高面板中,经由画面旁「工具」入口打开(D5-A 独立容器)。
    page.get_by_role('button', name='工具', exact=True).click()
    expect(page.get_by_role('dialog', name='单页工具面板')).to_be_visible()
    page.locator('.annotations-panel').wait_for(timeout=15000)
    panel = page.locator('.annotations-panel')

    # 拖拽工具与精确框选隐藏（D4：精确框选属于桌面入口）；可见说明告知桌面
    # 入口，整页意见路径保持可执行。
    assert not page.get_by_role('button', name='框选模式', exact=True).count()
    page.get_by_text('范围与标注工具', exact=True).click()
    expect(page.get_by_text('点标注与框选需要桌面宽度；窄屏可用「整页意见」文字描述位置。', exact=True)).to_be_visible()

    # 从零写图标要求可完成：整页意见 → 选入修改要求 → 预览影响，全程 390px。
    page.get_by_role('button', name='整页意见', exact=True).click()
    panel.get_by_role('textbox', name='意见正文', exact=True).fill('整图中的徽标位置描述：右上角状态图标需要与正文对齐。')
    panel.get_by_role('button', name='保存意见', exact=True).click()
    expect(panel.locator('.field-error[data-success]')).to_be_visible()
    saved_group = panel.locator('section.saved-group').filter(has_text='本页整页意见')
    saved_group.get_by_label('选入意见 1', exact=True).check()
    requirement = panel.get_by_role('textbox', name='修改要求', exact=True)
    expect(requirement).to_have_value(re.compile('整图中的徽标位置描述'))
    panel.get_by_role('button', name='预览修改影响', exact=True).click()
    expect(panel.locator('.change-plan-preview')).to_contain_text('结果先作为候选返回')

    # 图标流程与窄屏组合：切到 SVG 层，图标面板在 390px 下仍可操作——已保存的
    # 意见可在面板选入，未选入时给出诚实下一步而不是静默复制。
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: args[1], layer: 'svg', revision: args[2]})}",
                  [identity, 'p01', store.current_revision_id()])
    # 换层会重新挂载单页:面板回到关闭态,再次经「工具」入口打开图标面,
    # 并显式切到「图标优化」面(五工具一次只显示一个活动面)。
    page.get_by_role('button', name='工具', exact=True).click()
    page.get_by_role('button', name='图标优化', exact=True).click()
    workbench = page.locator('.icon-workbench')
    workbench.wait_for(timeout=15000)
    expect(workbench.get_by_label('图标处理方式')).to_be_visible()
    expect(workbench.get_by_label('建议的标准图标')).to_be_visible()
    handoff = workbench.get_by_role('button', name='复制给 Agent 的图标要求', exact=True)
    handoff.click()
    expect(workbench.get_by_role('status')).to_contain_text('请先框选、保存意见并在这里选入。')
    opinion = workbench.locator('label').filter(has_text='图标间距需要与正文对齐').locator('input[type=checkbox]')
    expect(opinion).to_have_count(1)
    opinion.check()
    expect(opinion).to_be_checked()
    page.evaluate("() => {window.iconCopy = null; Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => {window.iconCopy = text;}}});}")
    handoff.click()
    expect(workbench.get_by_role('status')).to_contain_text('图标要求已复制。尚未启动任务')
    payload = page.evaluate('JSON.parse(window.iconCopy)')
    assert payload['page_id'] == 'p01' and len(payload['annotation_refs']) == 1
    assert payload['opinions'][0]['body'] == '图标间距需要与正文对齐。'
    assert payload['opinions'][0]['layer'] == 'original_image'

    # P03a/UAC25 前半：刚才在 390px 从零写的整页意见以同一条正式 ref 进入同一图标
    # 面板——不因没有 layer/artifact_ref 被排除；选入后复制沿用合法 page 字段，
    # 不补造 layer/artifact_ref。
    page_record = next(record for record in page.request.get(url.rstrip('/') + '/api/annotations').json()['annotations']
                       if record['annotation']['body'].startswith('整图中的徽标位置'))
    page_choice = workbench.locator('label').filter(has_text='整图中的徽标位置').locator('input[type=checkbox]')
    expect(page_choice).to_have_count(1)
    page_label = workbench.locator('label').filter(has_text='整图中的徽标位置')
    expect(page_label).to_contain_text('整页文字定位')
    opinion.uncheck()
    page_choice.check()
    prior_ref = payload['annotation_refs'][0]['sha256']
    handoff.click()
    # 第二次复制前状态行已是「已复制」：以剪贴板 ref 变化为准，避免读到上次的 payload。
    page.wait_for_function("src => window.iconCopy && JSON.parse(window.iconCopy).annotation_refs[0]?.sha256 !== src", arg=prior_ref, timeout=15000)
    payload2 = page.evaluate('JSON.parse(window.iconCopy)')
    assert payload2['page_id'] == 'p01' and len(payload2['annotation_refs']) == 1
    assert payload2['annotation_refs'][0] == page_record['ref']
    assert payload2['opinions'][0]['body'].startswith('整图中的徽标位置')
    assert 'layer' not in payload2['opinions'][0] and 'artifact_ref' not in payload2['opinions'][0]
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')


def test_complete_draft_restore_reaches_icon_consumer_through_real_entry(ux06_browser):
    """E01/E02 补充(UAC08/22 前半):带意见/要求/icon_ui/试作的完整草稿经真实
    恢复入口替换当前 editor;图标消费方按当前草稿重新核验,不残留旧选择。"""
    from playwright.sync_api import expect
    from urllib.parse import urlencode
    from deck_master import annotation_service
    page, server, path, store, context = ux06_browser
    url = server.start()
    # 意见经服务预置(保存意见会推进版本,UI 只在最新修订上操作)。
    doc = store.load_document()
    entry = doc['pages'][0]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'scope': 'page', 'page_id': 'p01', 'page_ref': entry['page'], 'intent': 'clarify',
            'body': '恢复完整草稿的原始意见', 'status': 'open', 'location': {'kind': 'whole'}}
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'],
                                         'annotations': [note]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    identity = page.request.get(url.rstrip('/') + '/api/project').json()['project_identity']
    revision = store.current_revision_id()
    page.goto(url.split('#')[0] + '#' + urlencode({'project': identity, 'surface': 'page',
                                                   'page': 'p01', 'layer': 'svg', 'revision': revision}))
    def face(name):
        page.get_by_role('button', name=name, exact=True).click()
    # ① 意见面:填意见正文(入草稿)、选入预置意见,填修改要求。
    face('意见')
    page.get_by_label('意见正文', exact=True).fill('恢复完整草稿的原始意见')
    page.get_by_label('选入意见 1', exact=True).check()
    page.get_by_label('修改要求', exact=True).fill('完整恢复的要求：保留数字')
    # ② 图标面:标准方式 + 明确选一个标准图标 + 在图标面勾选意见(icon_ui 入草稿)。
    face('图标优化')
    page.get_by_label('图标处理方式').select_option('standard')
    page.get_by_label('建议的标准图标').select_option(index=1)
    page.locator('.icon-opinions input[type=checkbox]').first.check()
    # ③ 试作面:两层折叠(本页候选与试作 → 试作表单);要求框为「本页试作短要求」。
    face('试作与候选')
    page.get_by_text('本页候选与试作', exact=True).click()
    page.get_by_text('仅重建或修复本页 SVG', exact=True).click()
    page.get_by_label('本页试作短要求', exact=True).fill('完整恢复的试作要求')
    # ④ 笔记面:保存完整草稿 v1。
    face('笔记')
    page.get_by_label('个人草稿', exact=True).fill('完整恢复的笔记')
    page.get_by_role('button', name='保存个人草稿', exact=True).click()
    expect(page.locator('.draft-state').first).to_contain_text('已保存到项目', timeout=20000)
    records = page.request.get(url.split('#')[0] + 'api/drafts').json()['records']
    v1 = next(r['draft'] for r in records if r['draft']['content']['icon_ui'])
    assert v1['content']['icon_ui']['annotation_refs'] and v1['content']['trial']['instruction'] == '完整恢复的试作要求'
    # ⑤⑥ 真实恢复入口:恢复列表由编辑器 load 构建,先 reload 再展开恢复详情;
    # saved 状态直接恢复,不弹保留输入弹窗。
    page.reload()
    face('笔记')
    page.get_by_text('恢复、下载与版本详情', exact=True).click()
    page.get_by_label('恢复项目中的个人草稿').select_option(v1['draft_id'])
    expect(page.get_by_label('意见正文', exact=True)).to_have_value('恢复完整草稿的原始意见', timeout=20000)
    expect(page.get_by_label('修改要求', exact=True)).to_have_value('完整恢复的要求：保留数字')
    expect(page.get_by_label('个人草稿', exact=True)).to_have_value('完整恢复的笔记')
    # ⑦ 图标消费方按当前草稿重新核验(E02):asset 与选入意见都回到 v1。
    face('图标优化')
    expect(page.get_by_label('建议的标准图标')).to_have_value(v1['content']['icon_ui']['asset'])
    expect(page.locator('.icon-opinions input[type=checkbox]')).to_be_checked()
    # ⑧ 试作面同样回到 v1 配置。
    face('试作与候选')
    page.get_by_text('本页候选与试作', exact=True).click()
    page.get_by_text('仅重建或修复本页 SVG', exact=True).click()
    expect(page.get_by_label('本页试作短要求', exact=True)).to_have_value('完整恢复的试作要求')
