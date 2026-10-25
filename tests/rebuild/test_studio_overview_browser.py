"""Approved overview controls operate the formal plan and connection state."""
import json
import os
from pathlib import Path

import pytest
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


def test_studio_overview_action_buttons_and_compact_sync_recovery(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    original = store.load_document()
    output = Path(os.environ.get('STUDIO_OVERVIEW_EVIDENCE', str(tmp_path / 'evidence')))
    output.mkdir(parents=True, exist_ok=True)
    server = WorkbenchServer(project)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width':1440, 'height':900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(server.start() + 'studio/')
            modes = page.get_by_role('group', name='选页制作动作', exact=True)
            expect(modes).to_be_hidden()
            expect(page.get_by_label('批量动作', exact=True)).to_have_count(0)
            expect(page.get_by_label('所选页的制作要求', exact=True)).to_be_hidden()
            expect(page.get_by_role('region', name='所选页制作', exact=True)).to_be_hidden()
            first_row = page.locator('.matrix tbody tr:not(.chapter-row)').first
            expect(first_row).to_be_visible()
            expect(first_row).to_be_in_viewport()
            assert first_row.evaluate('n=>n.getBoundingClientRect().bottom') <= 900
            more=page.locator('.todo-more')
            if more.count():
                more.locator('summary').click();expect(more.locator('.todo-row').first).to_be_visible()
                more.locator('summary').click()
            page.get_by_role('button', name='个人记录与提交恢复', exact=True).click()
            expect(page.get_by_role('textbox', name='个人草稿', exact=True)).to_be_visible()
            page.get_by_role('button', name='个人记录与提交恢复', exact=True).click()
            page.get_by_role('button', name='状态说明', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('工程检查和人工认可分别记录')
            page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).click()
            pager = page.get_by_role('navigation', name='逐页制作分页', exact=True)
            expect(page.locator('.matrix tbody tr:not(.chapter-row)')).to_have_count(15)
            expect(pager.get_by_role('button', name='上一组页面', exact=True)).to_be_disabled()
            page.locator('.matrix tbody input[type=checkbox]:enabled').first.check()
            expect(modes).to_be_visible()
            expect(modes.get_by_role('button')).to_have_count(4)
            selected_id = page.locator('.matrix tbody input[type=checkbox]:checked').get_attribute('aria-label')
            pager.get_by_role('button', name='下一组页面', exact=True).click()
            expect(page.locator('.matrix tbody tr:not(.chapter-row)')).to_have_count(9)
            expect(pager.get_by_role('button', name='下一组页面', exact=True)).to_be_disabled()
            pager.get_by_role('button', name='上一组页面', exact=True).click()
            expect(page.locator('.matrix tbody input[type=checkbox]:checked')).to_have_count(1)
            assert page.locator('.matrix tbody input[type=checkbox]:checked').get_attribute('aria-label') == selected_id
            page.get_by_label('所选页的制作要求', exact=True).fill('保留全部事实，改善层级和间距')
            page.get_by_role('button', name='按所选页设置调用上限', exact=True).click()
            with page.expect_response(lambda r: r.url.endswith('/api/changes/plan') and r.request.method == 'POST') as response:
                page.get_by_role('button', name='预览所选页试作', exact=True).click()
            receipt = response.value.json()
            assert response.value.ok and len(receipt['plan']['actions']) == 1
            assert receipt['plan']['actions'][0]['stage'] == 'blueprint'
            expect(page.get_by_role('button', name='保存并交接所选试作', exact=True)).to_be_visible()
            modes.get_by_role('button', name='SVG 重建', exact=True).click()
            expect(modes.get_by_role('button', name='SVG 重建', exact=True)).to_have_attribute('aria-pressed', 'true')
            expect(page.get_by_role('button', name='保存并交接所选试作', exact=True)).to_be_hidden()
            assert store.load_document() == original
            modes.get_by_role('button', name='原图试作', exact=True).click()
            geometry = []
            for width, height in [(1440,900),(1280,800),(390,844)]:
                page.set_viewport_size({'width':width, 'height':height})
                page.evaluate('window.scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                boxes = modes.get_by_role('button').evaluate_all('(items)=>items.map(n=>({width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height}))')
                assert all(b['height'] >= (44 if width <= 560 else 32) and b['width'] >= 32 for b in boxes)
                geometry.append({'width':width, 'height':height, 'action_boxes':boxes})
                page.screenshot(path=str(output / f'overview-{width}.png'), full_page=True)
            page.get_by_role('button', name='清除选择', exact=True).click()
            expect(modes).to_be_hidden()
            page.set_viewport_size({'width':1440, 'height':900})
            page.evaluate('window.scrollTo(0,0)')
            route = page.url
            context.set_offline(True)
            page.evaluate('window.dispatchEvent(new Event("focus"))')
            notice = page.locator('.runtime-sync-row')
            expect(notice).to_be_visible()
            expect(notice).to_contain_text('同步中断 · 已读内容与草稿保留')
            assert notice.bounding_box()['height'] < 110
            page.screenshot(path=str(output / 'sync-interrupted-1440.png'))
            notice.get_by_role('button', name='查看详情', exact=True).click()
            expect(page.get_by_role('dialog')).to_contain_text('本机服务暂时无法连接')
            page.get_by_role('dialog').get_by_role('button', name='关闭', exact=True).click()
            context.set_offline(False)
            notice.get_by_role('button', name='重试同步', exact=True).click()
            expect(notice).to_be_hidden()
            assert page.url == route and store.load_document() == original and not errors
            (output / 'results.json').write_text(json.dumps({'passed':True,'geometry':geometry,'plan':receipt,'business_unchanged':True,'errors':errors},ensure_ascii=False,indent=2))
        finally:
            browser.close()
            server.stop()
