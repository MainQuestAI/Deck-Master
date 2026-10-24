"""PR188 review counterexamples: real browser geometry and selected paint."""
from urllib.parse import urlencode

import pytest
from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.fixture(scope='module')
def server_url(tmp_path_factory):
    project = tmp_path_factory.mktemp('pr188-controls') / 'project'
    create_gallery_sample(project, page_count=30, readonly=False)
    server = WorkbenchServer(project)
    try:
        yield server.start()
    finally:
        server.stop()


@pytest.mark.parametrize('entry', ['v2', 'studio'])
@pytest.mark.parametrize('width', [390, 768, 1280, 1440])
@pytest.mark.parametrize('touch', [False, True])
def test_pager_text_target_and_disabled_endpoints(server_url, entry, width, touch, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 900}, has_touch=touch, reduced_motion='reduce')
        info = page.request.get(server_url + 'api/project').json()
        page.goto(server_url + entry + '/#' + urlencode({
            'project': info['project_identity'], 'surface': 'page', 'page': 'p01',
            'layer': 'content', 'revision': info['revision_id']}))
        pager = page.locator('.page-pager')
        expect(pager).to_be_visible()
        prev, nxt = pager.get_by_role('button', name='上一页'), pager.get_by_role('button', name='下一页')
        expect(prev).to_be_disabled()
        expect(nxt).to_be_enabled()
        for button in (prev, nxt):
            metrics = button.evaluate('e=>({font:parseFloat(getComputedStyle(e).fontSize),w:e.getBoundingClientRect().width,h:e.offsetHeight,after:getComputedStyle(e,"::after").content,scroll:e.scrollWidth,client:e.clientWidth})')
            assert metrics['font'] >= 12, metrics
            assert metrics['w'] >= 44 and metrics['h'] >= (44 if touch or width <= 560 else 32), metrics
            assert metrics['scroll'] <= metrics['client'] and metrics['after'] in ('none', 'normal'), metrics
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        pager.locator('select').select_option('p30')
        expect(page.locator('.page-pager').get_by_role('button', name='下一页')).to_be_disabled()
        expect(page.locator('.page-pager').get_by_role('button', name='上一页')).to_be_enabled()
        page.screenshot(path=str(tmp_path / f'pager-{entry}-{width}-{touch}.png'))
        browser.close()


def test_pressed_controls_have_distinct_paint(server_url):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(reduced_motion='reduce')
        info = page.request.get(server_url + 'api/project').json()
        page.goto(server_url + 'studio/#' + urlencode({'project': info['project_identity'], 'surface': 'overview', 'revision': info['revision_id']}))
        expect(page.locator('.matrix')).to_be_visible()
        page.get_by_label('选择第 01 页', exact=True).check()
        reconstruct = page.locator('button[aria-pressed]').filter(has_text='重建 SVG')
        # Use the product's actual action handler, not just an ARIA mutation.
        if reconstruct.count() == 0:
            reconstruct = page.locator('button[aria-pressed]').filter(has_text='SVG').first
        reconstruct.click()
        expect(reconstruct).to_have_attribute('aria-pressed', 'true')
        colors = reconstruct.evaluate('e=>[e,...e.parentElement.querySelectorAll("button[aria-pressed=false]")].map(b=>{const s=getComputedStyle(b);return [s.backgroundColor,s.borderColor,s.color,s.boxShadow]})')
        assert len(colors) > 1 and all(colors[0] != item for item in colors[1:]), colors
        # Shared recipe covers every retained container, including disabled and hover.
        result = page.evaluate('''() => {
          const selectors=['batch-actions','versions','reading-mode','style-source','icon-mode','content-adjustment','segmented','page-tools-switcher','runs-subareas','studio-overview-actions'];
          return selectors.map(name=>{
            const group=document.createElement('div');group.className=name;
            group.innerHTML='<button aria-pressed="false">普通</button><button aria-pressed="true">选中</button><button aria-pressed="false" disabled>禁用</button><button aria-pressed="true" disabled>禁用选中</button>';
            document.querySelector('main').append(group);
            const paint=[...group.children].map(b=>{const s=getComputedStyle(b);return [s.backgroundColor,s.borderColor,s.color,s.fontWeight].join('|')});
            group.remove();return {name,paint};
          });
        }''')
        for item in result:
            assert item['paint'][0] != item['paint'][1] and item['paint'][2] != item['paint'][3], item
        reconstruct.hover()
        colors = reconstruct.evaluate('e=>[e,...e.parentElement.querySelectorAll("button[aria-pressed=false]")].map(b=>{const s=getComputedStyle(b);return [s.backgroundColor,s.borderColor,s.color,s.boxShadow]})')
        assert all(colors[0] != item for item in colors[1:]), colors
        browser.close()
