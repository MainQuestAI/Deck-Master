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
    expect(page.locator('.gallery-filter-disclosure')).not_to_have_attribute('open', '')
    assert page.locator('[aria-label="联系表列数"]').is_hidden()
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
    expect(page.get_by_role('button', name='联系表', exact=True)).to_have_attribute('aria-pressed', 'true')
    assert errors == []


def test_history_modes_keep_reading_and_page_comparison_fixed(workbench_page):
    from playwright.sync_api import expect
    page = workbench_page
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='版本记录', exact=True).wait_for()
    selected = page.get_by_role('combobox', name='阅读历史版本', exact=True)
    selected_revision = selected.input_value()
    url = page.url
    page.get_by_role('checkbox', name='显示全部历史记录', exact=True).check()
    expect(page.get_by_text('已显示全部类型的记录；任务和个人状态记录也会列出。', exact=True)).to_be_visible()
    assert selected.input_value() == selected_revision and page.url == url
    assert 'R ' not in selected.locator('option').first.inner_text()
    page.get_by_role('button', name='逐页查看与固定比较', exact=True).click()
    page.get_by_role('button', name='比较此页版本', exact=True).click()
    page.get_by_role('combobox', name='选择同页比较版本').wait_for()
    fixed = page.locator('[aria-label="页面内容"]').get_attribute('data-revision')
    all_history = page.get_by_role('checkbox', name='显示这页全部历史记录', exact=True)
    all_history.check()
    expect(all_history).to_be_enabled()
    assert page.locator('[aria-label="页面内容"]').get_attribute('data-revision') == fixed


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
    base = page.url.split('#')[0]
    info = page.request.get(base + 'api/project').json()
    page.set_viewport_size({'width':width, 'height':height})
    page.goto(base + '#' + urlencode({'project':info['project_identity'], 'surface':'page',
        'page':'p06', 'layer':layer, 'revision':after['revision_id']}))
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
    rect = page.locator('.fixed-page-pair').evaluate('''node => {
      const boxes = [...node.children].map(n => ({tag:n.tagName, ...n.getBoundingClientRect().toJSON()}));
      return {entry:boxes[0], left:boxes[1], right:boxes[2]};
    }''')
    assert abs(rect['left']['y'] - rect['right']['y']) < 1, rect
    assert rect['left']['x'] < rect['right']['x'], rect
    assert rect['entry']['y'] + rect['entry']['height'] <= rect['left']['y'], rect
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')


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
def test_plain_task_entry_opens_tasks_without_a_delivery_detour(workbench_page, width, height):
    import urllib.parse
    from urllib.parse import urlencode
    from playwright.sync_api import expect
    page = workbench_page
    base = page.url.split('#')[0]
    info = page.request.get(base + 'api/project').json()
    revision = page.request.get(base + 'api/view/summary').json()['revision_id']
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(base + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p02', 'layer': 'ppt', 'revision': revision}))
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
    base = page.url.split('#')[0]
    info = page.request.get(base + 'api/project').json()
    revision = page.request.get(base + 'api/view/summary').json()['revision_id']
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(page.url.split('#')[0] + '#' + urlencode({'project': info['project_identity'], 'surface': 'page', 'page': 'p02', 'layer': 'svg', 'revision': revision}))
    image = page.locator('.page-reading canvas:visible').first
    image.wait_for()
    editor = page.get_by_role('textbox', name='意见正文', exact=True)
    expect(editor).to_be_editable()
    expect(page.locator('.page-trial-entry')).not_to_have_attribute('open', '')
    assert page.get_by_role('textbox', name='本页试作短要求', exact=True).is_hidden()
    if width >= 1280:
        assert image.bounding_box()['y'] < height - 100
        assert editor.bounding_box()['y'] + editor.bounding_box()['height'] < height
    page.get_by_role('button', name='整页意见', exact=True).click()
    editor.fill('保留正文，调整图标线宽。')
    page.get_by_role('button', name='保存意见', exact=True).click()
    expect(page.locator('.saved-annotations')).to_contain_text('保留正文，调整图标线宽。')
    page.get_by_text('本页候选与试作', exact=True).click()
    expect(page.get_by_role('button', name='刷新本页候选', exact=True)).to_be_visible()
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('width,height', [(1280, 800), (1440, 900)])
def test_selected_internal_style_keeps_main_action_in_first_view(workbench_page, width, height):
    from playwright.sync_api import expect
    page = workbench_page
    page.set_viewport_size({'width': width, 'height': height})
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('combobox', name='风格参考来源', exact=True).select_option('page')
    page.get_by_role('combobox', name='风格参考原图', exact=True).select_option('p01')
    page.get_by_role('combobox', name='当前风格试作目标', exact=True).select_option('p02')
    page.locator('.style-reference canvas:visible').wait_for()
    page.locator('.style-primary-target canvas:visible').wait_for()
    check = page.get_by_role('button', name='检查风格要求', exact=True)
    expect(check).to_be_enabled()
    page.evaluate('() => scrollTo(0,0)')
    assert check.bounding_box()['y'] + check.bounding_box()['height'] < height
    field = page.get_by_role('textbox', name='风格短要求', exact=True)
    assert field.bounding_box()['y'] + field.bounding_box()['height'] < height
    check.click()
    expect(page.get_by_role('button', name='确认这版风格要求', exact=True)).to_be_enabled()
