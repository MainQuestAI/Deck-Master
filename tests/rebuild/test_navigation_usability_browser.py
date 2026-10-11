"""Real Chromium checks on synthetic projects; no production acceptance claim."""
import pytest
from test_ui_design_browser import workbench_page  # noqa: F401

pytestmark = pytest.mark.browser


def test_mobile_gallery_reads_on_page_and_restores_desktop_preference(workbench_page):
    from playwright.sync_api import expect
    page = workbench_page
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.get_by_role('button', name='整稿画廊', exact=True).click()
    page.locator('.gallery-viewport').wait_for()
    expect(page.get_by_role('button', name='联系表', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='联系表', exact=True)).to_have_attribute('aria-pressed', 'true')
    page.locator('.slide-tile canvas').first.wait_for()
    actual_columns = page.locator('.gallery').evaluate('(node) => node.style.getPropertyValue("--gallery-columns")')
    expect(page.locator('[aria-label="联系表列数"] button[aria-pressed="true"]')).to_have_text(actual_columns + ' 列')
    selection = page.locator('.slide-tile .tile-select input').first
    selection.focus(); selection.press('Space')
    expect(selection).to_be_checked(); expect(selection).to_be_focused()
    page.keyboard.press('Space')
    expect(selection).not_to_be_checked(); expect(selection).to_be_focused()
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('.gallery-viewport')).to_have_attribute('data-mode', 'continuous')
    settings = page.get_by_role('button', name='筛选与阅读设置', exact=True)
    expect(settings).to_be_visible()
    # Keep the 44px CSS target; Chromium may round a fractional Y subtraction
    # to 43.999969px. The subpixel epsilon only covers that measured rounding.
    geometry = settings.evaluate('node=>({minimum:parseFloat(getComputedStyle(node).minHeight),height:node.getBoundingClientRect().height})')
    assert geometry['minimum'] >= 44 and geometry['height'] >= 44 - .01, geometry
    expect(page.locator('[aria-label="画廊选页制作"]')).to_have_count(0)
    settings.click()
    expect(page.get_by_role('dialog', name='画廊筛选与阅读设置')).to_be_visible()
    expect(page.get_by_role('combobox', name='筛选章节', exact=True)).to_be_visible()
    expect(page.get_by_role('combobox', name='筛选页面状态', exact=True)).to_be_visible()
    assert page.locator('[aria-label="联系表列数"]').is_hidden()
    page.get_by_role('button', name='关闭', exact=True).click()
    expect(settings).to_be_focused()
    page.locator('.slide-tile canvas').first.wait_for()
    expect(page.locator('.slide-tile canvas').first).to_be_in_viewport()
    assert page.locator('.gallery-viewport').evaluate('(node) => getComputedStyle(node).overflowY') == 'visible'
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    first_id = page.locator('.slide-tile').first.get_attribute('data-page-id')
    page.evaluate('() => scrollTo(0, 2000)')
    expect(page.locator('.slide-tile').first).not_to_have_attribute('data-page-id', first_id)
    assert page.locator('.slide-tile').count() <= 4
    pool = page.evaluate("async () => (await import('/v2/images.js')).imagePool.snapshot()")
    assert pool['large'] <= 4 and pool['network_peak'] <= 6 and pool['decode_peak'] <= 2
    page.set_viewport_size({'width': 1440, 'height': 900})
    expect(page.locator('.gallery-viewport')).to_have_attribute('data-mode', 'grid')
    expect(page.get_by_role('button', name='联系表', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='联系表', exact=True)).to_have_attribute('aria-pressed', 'true')
    assert errors == []


def test_history_modes_keep_reading_and_page_comparison_fixed(workbench_page):
    from playwright.sync_api import expect
    page = workbench_page
    page.get_by_role('button', name='任务与交付', exact=True).click()
    # 版本记录在「版本」子区：任务与交付一次只呈现一个工作上下文。
    page.get_by_role('button', name='版本', exact=True).click()
    page.get_by_role('heading', name='版本记录', exact=True).wait_for()
    selected = page.locator('.studio-version-list button[aria-pressed="true"]')
    selected_revision = selected.get_attribute('data-version-id')
    url = page.url
    page.get_by_role('checkbox', name='显示全部历史记录', exact=True).check()
    expect(page.get_by_text('已显示全部类型的记录；任务和个人状态记录也会列出。', exact=True)).to_be_visible()
    assert selected.get_attribute('data-version-id') == selected_revision and page.url == url
    assert 'R ' not in page.locator('.studio-version-list button').first.inner_text()
    page.get_by_role('button', name='逐页查看与固定比较', exact=True).click()
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).to_be_visible()
    page.get_by_role('button', name='比较此页版本', exact=True).click()
    page.get_by_role('combobox', name='选择同页比较版本').wait_for()
    fixed = page.locator('[aria-label="页面内容"]').get_attribute('data-revision')
    all_history = page.get_by_role('checkbox', name='显示这页全部历史记录', exact=True)
    all_history.check()
    expect(all_history).to_be_enabled()
    assert page.locator('[aria-label="页面内容"]').get_attribute('data-revision') == fixed


def test_mobile_gallery_settings_keep_selection_focus_and_production_targets(workbench_page, tmp_path):
    """A fresh 390px entry reads artwork before setup; hidden selections remain actionable."""
    import json
    import os
    from pathlib import Path
    from urllib.parse import urlsplit
    from playwright.sync_api import expect
    page = workbench_page
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_viewport_size({'width':390, 'height':844})
    page.get_by_role('button', name='整稿画廊', exact=True).click()
    canvas = page.locator('.slide-tile canvas').first
    canvas.wait_for()
    assert page.evaluate('scrollY') == 0
    rect = canvas.bounding_box()
    assert rect['y'] >= 0 and rect['y'] + rect['height'] <= 844, rect
    assert page.locator('.nav button').evaluate_all('(nodes)=>nodes.every(n=>n.getBoundingClientRect().height>=44)')
    expect(page.get_by_role('group', name='画廊选页制作')).to_have_count(0)
    out = Path(os.environ.get('STUDIO_NAVIGATION_EVIDENCE', str(tmp_path/'evidence')))
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out/'gallery-empty-390.png'))
    (out/'gallery-first-viewport.json').write_text(json.dumps({'width':390,'height':844,'scrollY':page.evaluate('scrollY'),'canvas':rect},indent=2))
    search = page.get_by_role('textbox', name='搜索页面', exact=True)
    search.fill('02')
    page.locator('.slide-tile[data-page-id="p02"]').get_by_role('checkbox').check()
    production = page.get_by_role('group', name='画廊选页制作')
    expect(production).to_contain_text('已选 1 页')
    expect(production.locator('button')).to_have_count(4)
    assert production.locator('button').evaluate_all('(nodes)=>nodes.every(n=>n.getBoundingClientRect().height>=44)')
    search.fill('')
    settings = page.get_by_role('button', name='筛选与阅读设置', exact=True)
    settings.click()
    dialog = page.get_by_role('dialog', name='画廊筛选与阅读设置')
    state = dialog.get_by_role('combobox', name='筛选页面状态', exact=True)
    state.focus(); state.select_option('missing')
    expect(state).to_be_focused()
    expect(state).to_have_value('missing')
    page.screenshot(path=str(out/'gallery-settings-390.png'))
    page.keyboard.press('Escape')
    expect(dialog).to_be_hidden()
    expect(page.get_by_role('button', name='筛选与阅读设置 · 已筛选', exact=True)).to_be_focused()
    expect(page.locator('.gallery-legend')).to_contain_text('筛选外选中 1 页')
    expect(production).to_contain_text('已选 1 页')
    page.screenshot(path=str(out/'gallery-hidden-selection-390.png'))
    origin = urlsplit(page.url)
    before = page.request.get(origin.scheme+'://'+origin.netloc+'/api/view/summary').json()['revision_id']
    production.locator('[data-gallery-action="blueprint"]').click()
    expect(page.get_by_role('heading',name='制作总览',exact=True)).to_be_visible()
    expect(page.locator('.batch-actions')).to_have_attribute('data-selection','selected')
    expect(page.locator('.overview-selection-summary')).to_contain_text('已选 1 页')
    expect(page.get_by_role('checkbox',name='选择第 02 页',exact=True)).to_be_checked()
    expect(page.locator('.matrix tbody input[type=checkbox]:checked')).to_have_count(1)
    assert 'revision='+before in page.url
    page.reload()
    expect(page.locator('.overview-selection-summary')).to_contain_text('已选 1 页')
    expect(page.get_by_role('checkbox',name='选择第 02 页',exact=True)).to_be_checked()
    assert page.request.get(origin.scheme+'://'+origin.netloc+'/api/view/summary').json()['revision_id']==before
    assert errors == []


@pytest.mark.parametrize('layer', ['svg', 'ppt'])
@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900)])
def test_fixed_history_images_share_a_row_with_candidate_entry(workbench_page, tmp_path, layer, width, height):
    """Real historical refs and images; synthetic SVG/PPT previews, no Host claim."""
    import uuid
    from urllib.parse import urlencode
    from deck_master.models import bump_revision
    from deck_master.store import Store
    from playwright.sync_api import expect
    page = workbench_page
    store = Store(tmp_path / 'sample')
    before = store.load_document()
    operation = str(uuid.uuid4())
    after = bump_revision(before, {'operation_id':operation, 'kind':'task_update',
        'description':'Synthetic history comparison snapshot; same registered images', 'read_set':[]})
    store.commit_change(base_revision=before['revision_id'], document=after, operation_id=operation)
    from urllib.parse import urlsplit
    origin = urlsplit(page.url)
    base = origin.scheme + '://' + origin.netloc + '/'
    studio = base + 'studio/'
    info = page.request.get(base + 'api/project').json()
    page.set_viewport_size({'width':width, 'height':height})
    page.goto(studio + '#' + urlencode({'project':info['project_identity'], 'surface':'page',
        'page':'p06', 'layer':layer, 'revision':after['revision_id']}))
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).to_be_visible()
    page.get_by_role('button', name='比较此页版本', exact=True).click()
    all_history = page.get_by_role('checkbox', name='显示这页全部历史记录', exact=True)
    all_history.check()
    expect(all_history).to_be_enabled()
    selected = page.get_by_role('combobox', name='选择同页比较版本', exact=True)
    expect(selected.locator('option[value="' + before['revision_id'] + '"]')).to_have_count(1)
    selected.select_option(before['revision_id'])
    expect(selected).to_have_value(before['revision_id'])
    page.get_by_role('button', name='固定比较这个版本', exact=True).click()
    left = page.locator('[aria-label="页面内容"]')
    right = page.locator('[aria-label="比较版本内容"]')
    expect(left).to_have_attribute('data-revision', after['revision_id'])
    expect(right).to_have_attribute('data-revision', before['revision_id'])
    left.locator('canvas.page-image').wait_for()
    right.locator('canvas.page-image').wait_for()
    expect(page.locator('.page-trial-entry')).not_to_have_attribute('open', '')
    # D4-A/§4.1:试作与候选进入五工具容器。本场景开着固定比较,≤1439px 按既有
    # 规则折单列,此时入口在双方之下;断言保留:双方同排、画面完整、入口可见。
    page.get_by_role('button', name='试作与候选', exact=True).click()
    expect(page.locator('.page-trial-entry')).to_be_visible()
    rect = page.evaluate('''() => {
      const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
      return {entry:box('.page-trial-entry'), left:box('[aria-label="页面内容"]'), right:box('[aria-label="比较版本内容"]')};
    }''')
    assert abs(rect['left']['y'] - rect['right']['y']) < 1, rect
    assert rect['left']['x'] < rect['right']['x'], rect
    assert rect['entry']['y'] >= max(rect['left']['bottom'], rect['right']['bottom']), rect
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth'), page.evaluate('''() => [...document.querySelectorAll('body *')].filter(n => n.getBoundingClientRect().right > innerWidth + 1).map(n => ({tag:n.tagName, cls:n.className, text:n.textContent.slice(0,80), right:n.getBoundingClientRect().right})).slice(0,15)''')


def test_host_handoff_clipboard_failure_remains_pending(workbench_page):
    from playwright.sync_api import expect
    page = workbench_page
    handoff = {'status': 'awaiting_host', 'task_id': 'task-synthetic-handoff',
               'revision_id': 'synthetic-revision', 'handoff': '固定的完整制作要求'}
    page.route('**/api/compose/handoff', lambda route: route.fulfill(json=handoff))
    page.evaluate("""async () => {
      navigator.clipboard.writeText = async () => { throw new Error('clipboard denied'); };
      const {Project} = await import('/v2/project.js');
      await Project.prototype.handoff.call({setNotice: () => {}}, null);
    }""")
    page.get_by_role('button', name='复制给 Deck Master Agent', exact=True).click()
    expect(page.get_by_text('自动复制未完成；请打开完整交接说明后选中复制。任务仍待接手。', exact=True)).to_be_visible()
    expect(page.get_by_role('textbox', name='交接说明', exact=True)).to_be_visible()
    expect(page.get_by_role('textbox', name='交接说明', exact=True)).to_have_value(handoff['handoff'])
    page.evaluate("() => navigator.clipboard.writeText = async text => { window.copiedHandoff = text; }")
    page.get_by_role('button', name='复制给 Deck Master Agent', exact=True).click()
    expect(page.get_by_text('交接说明已复制 · 待接手。请在 Codex 中发送；复制不会开始制作。', exact=True)).to_be_visible()
    assert page.evaluate('() => window.copiedHandoff') == handoff['handoff']


@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900)])
def test_artwork_and_save_row_share_the_first_screen(workbench_page, width, height):
    from urllib.parse import urlencode
    page = workbench_page
    from urllib.parse import urlsplit
    origin = urlsplit(page.url)
    base = origin.scheme + '://' + origin.netloc + '/'
    studio = base + 'studio/'
    info = page.request.get(base + 'api/project').json()
    revision = page.request.get(base + 'api/view/summary').json()['revision_id']
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(studio + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p02', 'layer': 'svg', 'revision': revision}))
    image = page.locator('.page-reading canvas:visible').first
    image.wait_for()
    page.get_by_role('button', name='整页意见', exact=True).click()
    artwork = image.bounding_box()
    assert artwork['y'] >= 0 and artwork['y'] + artwork['height'] <= height, artwork
    body = page.get_by_role('textbox', name='意见正文', exact=True).bounding_box()
    save = page.get_by_role('button', name='保存意见', exact=True).bounding_box()
    # Keep actual layout headroom; one CSS pixel only absorbs device rounding.
    assert body['y'] + body['height'] <= height - 8 + 1 and save['y'] + save['height'] <= height - 8 + 1, (body, save)
    assert page.get_by_role('button', name='保存意见', exact=True).evaluate('''n => {
      const r=n.getBoundingClientRect();return n.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
    }''')
    # The default fit keeps exactly one scroll container over the artwork.
    assert page.evaluate('() => { const vp = document.querySelector(".page-image-viewport"); return vp.scrollHeight <= vp.clientHeight + 1; }')


@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900)])
def test_plain_task_entry_opens_tasks_without_a_delivery_detour(workbench_page, width, height):
    import urllib.parse
    from urllib.parse import urlencode
    from playwright.sync_api import expect
    page = workbench_page
    from urllib.parse import urlsplit
    origin = urlsplit(page.url)
    base = origin.scheme + '://' + origin.netloc + '/'
    studio = base + 'studio/'
    info = page.request.get(base + 'api/project').json()
    revision = page.request.get(base + 'api/view/summary').json()['revision_id']
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(studio + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p02', 'layer': 'ppt', 'revision': revision}))
    page.locator('.page-head').wait_for()
    # Switching to the task surface must not carry the page's layer (the delivery
    # area used to treat a leftover "ppt" as "open the export desk") nor a stale task.
    page.locator('.nav button[title="任务与交付"]').click()
    page.locator('#view-title').wait_for()
    params = dict(urllib.parse.parse_qsl(page.url.split('#')[1]))
    assert params['surface'] == 'runs' and params['layer'] == 'original_image' and 'task' not in params, params
    expect(page.locator('#view-title')).to_be_focused()


@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900), (390, 844)])
def test_page_opinion_editor_stays_with_artwork_before_trial_form(workbench_page, width, height):
    from playwright.sync_api import expect
    from urllib.parse import urlencode
    page = workbench_page
    from urllib.parse import urlsplit
    origin = urlsplit(page.url)
    base = origin.scheme + '://' + origin.netloc + '/'
    studio = base + 'studio/'
    info = page.request.get(base + 'api/project').json()
    revision = page.request.get(base + 'api/view/summary').json()['revision_id']
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(page.url.split('#')[0] + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p02', 'layer': 'svg', 'revision': revision}))
    image = page.locator('.page-reading canvas:visible').first
    image.wait_for()
    # D4-A:390px 下意见在全高工具面板里,先通过画面旁「工具」入口打开(D5 独立容器)。
    if width < 1280:
        page.get_by_role('button', name='意见', exact=True).click()
        expect(page.get_by_role('dialog', name='单页工具面板')).to_be_visible()
    editor = page.get_by_role('textbox', name='意见正文', exact=True)
    expect(editor).to_be_editable()
    expect(page.locator('.page-trial-entry')).to_be_hidden()
    assert page.get_by_role('textbox', name='本页试作短要求', exact=True).is_hidden()
    if width >= 1280:
        assert image.bounding_box()['y'] < height - 100
        assert editor.bounding_box()['y'] + editor.bounding_box()['height'] < height
    page.get_by_role('button', name='整页意见', exact=True).click()
    editor.fill('保留正文，调整图标线宽。')
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.locator('.saved-annotations')).to_contain_text('保留正文，调整图标线宽。')
    if width < 1280:
        page.get_by_role('button', name='回到画面', exact=True).click()
    page.get_by_role('button', name='试作与候选', exact=True).click()
    page.get_by_text('本页候选与试作', exact=True).click()
    expect(page.get_by_role('button', name='刷新本页候选', exact=True)).to_be_visible()
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900)])
def test_selected_internal_style_keeps_main_action_in_first_view(workbench_page, tmp_path, width, height):
    import json
    import os
    from pathlib import Path
    from playwright.sync_api import expect
    page = workbench_page
    page.set_viewport_size({'width': width, 'height': height})
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('button', name='项目页面', exact=True).click()
    page.get_by_role('combobox', name='风格参考原图', exact=True).select_option('p01')
    page.get_by_role('combobox', name='当前风格试作目标', exact=True).select_option('p02')
    page.locator('.style-reference canvas:visible').wait_for()
    page.locator('.style-calibration > .style-primary-phase .style-target-card.is-selected canvas:visible').first.wait_for()
    check = page.get_by_role('button', name='检查风格要求', exact=True)
    expect(check).to_be_enabled()
    page.evaluate('() => scrollTo(0,0)')
    assert check.bounding_box()['y'] + check.bounding_box()['height'] < height
    field = page.get_by_role('textbox', name='风格短要求', exact=True)
    assert field.bounding_box()['y'] + field.bounding_box()['height'] < height
    out=Path(os.environ.get('STUDIO_NAVIGATION_EVIDENCE', str(tmp_path/'evidence')))
    out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/f'style-selected-{width}.png'))
    (out/f'style-selected-{width}.json').write_text(json.dumps({'width':width,'height':height,'action':check.bounding_box(),'requirement':field.bounding_box()},indent=2))
    check.click()
    expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled()


@pytest.mark.parametrize('selected', [False, True])
@pytest.mark.parametrize('read_error', [False, True])
def test_current_version_read_blocks_obsolete_actions_and_restores_controls(tmp_path, selected, read_error):
    """An old task view cannot supersede a pending current-version read."""
    import uuid
    from playwright.sync_api import expect
    from test_pr103_complete_browser import browser_for, Flow, confirm, dispatch, commit

    flow = Flow(tmp_path)
    dispatch(flow, confirm(flow))
    with browser_for(flow.project) as (page, _):
        page.get_by_role('button', name='任务与交付', exact=True).click()
        expect(page.locator('#runs-tasks')).to_be_visible()
        if selected:
            page.get_by_role('button', name='查看这项任务', exact=True).first.click()
            expect(page.locator('.run-detail')).to_be_visible()
        old_revision = flow.store.load_document()['revision_id']
        commit(flow.store, flow.store.load_document(), str(uuid.uuid4()))
        current = flow.store.load_document()
        page.reload()
        expect(page.get_by_role('button', name='查看当前版本', exact=True)).to_be_visible()
        held = []

        def hold_current_read(route):
            if 'revision=' + current['revision_id'] in route.request.url:
                held.append((route, route.fetch()))
                page.evaluate('window.heldCurrentRead=true')
            else:
                route.continue_()

        page.route('**/api/tasks?*', hold_current_read)
        page.get_by_role('button', name='查看当前版本', exact=True).click()
        page.wait_for_function('()=>window.heldCurrentRead===true')
        target = page.get_by_role('button', name='待决定', exact=True)
        box = target.bounding_box()
        # Real pointer input must not activate the obsolete snapshot's handler.
        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        expect(page.locator('.navigation-status')).to_be_visible()
        expect(page.locator('#main')).to_have_attribute('aria-busy', 'true')
        assert page.locator('#main').evaluate('(node)=>node.inert')
        assert 'area=decisions' not in page.url
        for route, response in held:
            if read_error:
                route.fulfill(status=503, json={'error': {'code': 'operation_unavailable', 'message': '当前版本暂不可读'}})
            else:
                route.fulfill(response=response)
        page.wait_for_function('()=>!document.querySelector("#main").inert')
        expect(page.locator('.navigation-status')).to_be_hidden()
        expect(page.locator('#main')).not_to_have_attribute('aria-busy', 'true')
        if read_error:
            expect(page.locator('.notice')).to_contain_text('当前版本暂不可读')
        else:
            assert 'revision=' + current['revision_id'] in page.url
        page.get_by_role('button', name='待决定', exact=True).click()
        expect(page.locator('#runs-decisions')).to_be_visible()
        expected_revision = old_revision if read_error else current['revision_id']
        assert 'revision=' + expected_revision in page.url and 'area=decisions' in page.url
        assert flow.store.load_document() == current
        page.unroute_all(behavior='ignoreErrors')
