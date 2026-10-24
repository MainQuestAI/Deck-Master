"""Task-first controls remain discoverable on a real workbench service."""
import pytest
from playwright.sync_api import expect
from test_deep_quality_browser import workbench, open_opinion_composer  # noqa: F401
from test_icon_quality import icon_store  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width,height', [(390, 844), (1280, 800), (1440, 900)])
def test_reading_prioritizes_artwork_and_preserves_fixed_layers(workbench, width, height):
    page, _, store, _, goto, _ = workbench
    page.set_viewport_size({'width': width, 'height': height})
    goto()
    canvas = page.locator('.page-image-viewport')
    expect(canvas).to_be_visible()
    if width == 390:
        # Image decoding and the reading controller's next-frame fit are distinct.
        # Measure the actual fitted canvas, after the controller reports its mode.
        expect(canvas).to_have_attribute('data-reading-mode', 'fit')
        box = canvas.bounding_box()
        assert box['y'] + box['height'] < height, box
        layers = page.get_by_label('查看制作图层', exact=True)
        expect(layers).to_be_visible()
        layers.select_option('content')
        expect(page.locator('.page-copy')).to_be_visible()
        assert 'revision=' + store.current_revision_id() in page.url
    else:
        expect(page.locator('.chain')).to_be_visible()
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')


def test_optional_tools_do_not_arm_annotation_and_keep_keyboard_return(workbench):
    page, _, _, _, goto, _ = workbench
    goto()
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).to_be_visible()
    fixed_url = page.url
    reading = page.get_by_role('group', name='单页图稿阅读')
    reading.get_by_role('button', name='原生 100% 阅读', exact=True).click()
    canvas = page.locator('.page-reading canvas:visible').first
    native_width = canvas.bounding_box()['width']
    reading.get_by_role('button', name='放大图稿', exact=True).click()
    assert abs(canvas.bounding_box()['width'] - native_width * 1.25) < 1
    fullscreen = reading.get_by_role('button', name='全屏阅读', exact=True)
    fullscreen.click()
    page.wait_for_function('() => Boolean(document.fullscreenElement)')
    page.keyboard.press('Escape')
    page.wait_for_function('() => !document.fullscreenElement')
    expect(reading.get_by_role('button', name='全屏阅读', exact=True)).to_be_focused()
    assert page.url == fixed_url
    assert 'surface=page' in page.url
    page.get_by_role('button', name='意见', exact=True).click()
    save = page.get_by_role('button', name='保存意见', exact=True)
    expect(save).to_be_disabled()
    page.get_by_text('范围与标注工具', exact=True).click()
    expect(save).to_be_disabled()
    page.get_by_role('button', name='框选模式', exact=True).click()
    expect(page.get_by_role('button', name='框选模式', exact=True)).to_have_attribute('aria-pressed', 'true')
    page.get_by_role('button', name='框选模式', exact=True).press('Escape')
    expect(save).to_be_disabled()
    assert 'surface=page' in page.url


def test_gallery_reading_preferences_remain_open_and_restore(workbench):
    page, _, _, _, goto, _ = workbench
    goto('gallery')
    expect(page.locator('.gallery-viewport')).to_be_visible()
    # §4.4：阅读方式与「并排比较」在工具条上直接可见，不再藏进「阅读设置」。
    expect(page.get_by_role('button', name='连续阅读', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='并排比较', exact=True)).to_be_visible()
    page.get_by_role('button', name='连续阅读', exact=True).click()
    expect(page.locator('.gallery-viewport')).to_have_attribute('data-mode', 'continuous')
    page.get_by_role('button', name='联系表', exact=True).click()
    page.get_by_role('button', name='2 列', exact=True).click()
    expect(page.get_by_role('button', name='2 列', exact=True)).to_have_attribute('aria-pressed', 'true')
    page.get_by_label('搜索页面', exact=True).fill('01')
    expect(page.locator('.gallery-legend')).to_contain_text('显示 1 /')


def test_readonly_workbench_does_not_offer_a_live_opinion_entry(workbench, tmp_path):
    from urllib.parse import urlencode
    from deck_master.samples import create_gallery_sample
    from deck_master.web import WorkbenchServer
    page = workbench[0]
    root = tmp_path / 'readonly'
    create_gallery_sample(root, page_count=24, readonly=True)
    server = WorkbenchServer(root)
    try:
        url = server.start()
        info = page.request.get(url + 'api/project').json()
        page.goto(url + '#' + urlencode({'project': info['project_identity'], 'surface': 'page',
                                        'page': 'p01', 'layer': 'original_image'}))
        page.get_by_role('button',name='意见',exact=True).click()
        expect(page.locator('.annotations-panel')).to_be_visible()
        expect(page.get_by_role('button', name='整页意见', exact=True)).to_be_disabled()
        open_opinion_composer(page)
        expect(page.get_by_label('意见正文', exact=True)).not_to_be_editable()
        expect(page.get_by_role('button', name='保存意见', exact=True)).to_be_disabled()
    finally:
        server.stop()


def test_mobile_reading_actions_keep_fixed_comparison_and_resize_focus(workbench):
    """Mobile actions use the same fixed-page commands; no hidden-control clicks."""
    page, _, store, _, goto, errors = workbench
    before = store.load_document()
    page.set_viewport_size({'width':390, 'height':844})
    goto()
    entry = page.get_by_role('button', name='阅读设置', exact=True)
    entry.click()
    menu = page.get_by_role('dialog', name='阅读设置', exact=True)
    expect(menu).to_be_visible()
    for control in menu.get_by_role('button').all():
        assert control.bounding_box()['height'] >= 44
    page.keyboard.press('Escape')
    expect(menu).not_to_be_visible()
    expect(entry).to_be_focused()
    entry.click()
    page.set_viewport_size({'width':1440, 'height':900})
    expect(menu).not_to_be_visible()
    expect(page.get_by_role('button', name='返回整稿画廊', exact=True)).to_be_focused()
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).to_be_visible()
    page.set_viewport_size({'width':390, 'height':844})
    entry.click()
    menu.get_by_role('button', name='比较此页版本', exact=True).click()
    expect(menu).not_to_be_visible()
    selected = page.get_by_role('combobox', name='选择同页比较版本', exact=True)
    expect(selected.locator('option').nth(1)).to_be_attached()
    selected.select_option(index=1)
    page.get_by_role('button', name='固定比较这个版本', exact=True).click()
    expect(page.locator('.page-columns.with-fixed-compare')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.page-columns.with-fixed-compare')).to_have_count(0)
    expect(entry).to_be_focused()
    assert 'surface=page' in page.url and 'revision=' + before['revision_id'] in page.url
    entry.click()
    menu.get_by_role('button', name='以本页为风格参考', exact=True).click()
    expect(page.get_by_role('heading', name='风格校准', exact=True)).to_be_visible()
    expect(page.get_by_role('dialog')).not_to_be_visible()
    assert store.load_document() == before and errors == []
