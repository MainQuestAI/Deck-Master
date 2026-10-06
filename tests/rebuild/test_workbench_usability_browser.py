"""Task-first controls remain discoverable on a real workbench service."""
import pytest
from playwright.sync_api import expect
from test_deep_quality_browser import workbench  # noqa: F401
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
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).not_to_be_visible()
    page.get_by_text('页面操作', exact=True).click()
    expect(page.get_by_role('button', name='比较此页版本', exact=True)).to_be_visible()
    page.get_by_label('阅读缩放', exact=True).select_option('1.25')
    page.get_by_label('阅读缩放', exact=True).press('Escape')
    expect(page.locator('.page-actions')).not_to_have_attribute('open', '')
    expect(page.locator('.page-actions > summary')).to_be_focused()
    assert 'surface=page' in page.url
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
    page.get_by_text('阅读设置', exact=True).click()
    page.get_by_role('button', name='2 列', exact=True).click()
    expect(page.locator('.gallery-reading-settings')).to_have_attribute('open', '')
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
        expect(page.locator('.annotations-panel')).to_be_visible()
        expect(page.get_by_role('button', name='整页意见', exact=True)).to_be_disabled()
        expect(page.get_by_label('意见正文', exact=True)).not_to_be_editable()
        expect(page.get_by_role('button', name='保存意见', exact=True)).to_be_disabled()
    finally:
        server.stop()
