"""Actual reading typography and native select label space."""
import pytest
from pr188_design_fixtures import manuscript_url  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('width,touch', [(390, True), (1280, True), (1440, False)])
def test_reading_type_and_pager_label(manuscript_url, width, touch, tmp_path):
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 844}, has_touch=touch)
        info = page.request.get(manuscript_url+'api/project').json()
        page.goto(manuscript_url+'studio/#'+urlencode({'project':info['project_identity'], 'surface':'page', 'page':'p30', 'layer':'content', 'revision':info['revision_id']}))
        expect(page.locator('.page-manuscript')).to_be_visible()
        assert page.locator('.page-manuscript>p').first.evaluate('e=>getComputedStyle(e).lineHeight') == '28px'
        metrics = page.locator('.page-pager select').evaluate('''e=>{const s=getComputedStyle(e),c=document.createElement('canvas').getContext('2d');c.font=s.font;return {available:e.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight),text:c.measureText(e.selectedOptions[0].textContent).width}}''')
        assert metrics['available'] >= metrics['text'], metrics
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(tmp_path/f'reading-{width}.png'))
        browser.close()
