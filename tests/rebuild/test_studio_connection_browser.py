"""Connection facts come from a fresh read; a retry keeps the requested route."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode

import pytest

from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


def test_studio_offline_connection_retries_without_losing_fixed_route(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    before = store.load_document()
    evidence = Path(os.environ.get('STUDIO_CONNECTION_EVIDENCE', str(tmp_path / 'evidence')))
    evidence.mkdir(parents=True, exist_ok=True)
    server = WorkbenchServer(project)
    url = server.start()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            identity = page.request.get(url + 'api/project').json()['project_identity']
            route = {'project': identity, 'surface': 'page', 'page': 'p02',
                     'layer': 'content', 'revision': before['revision_id'], 'zoom': '1'}
            page.goto(url + 'studio/#' + urlencode(route))
            expect(page.locator('#view-title')).to_contain_text('第 2 页')
            page.get_by_role('button', name='连接状态', exact=True).click()
            dialog = page.get_by_role('dialog')
            expect(dialog).to_contain_text('已连接')
            dialog.get_by_role('button', name='关闭', exact=True).click()

            context.set_offline(True)
            page.get_by_role('button', name='连接状态', exact=True).click()
            expect(dialog).to_contain_text('未能连接')
            expect(dialog).not_to_contain_text('已连接')
            page.screenshot(path=str(evidence / 'connection-offline.png'))
            expect(dialog.get_by_role('button', name='重新读取当前工作面')).to_be_disabled()
            expect(page).to_have_url(re.compile('page=p02'))
            context.set_offline(False)
            dialog.get_by_role('button', name='核实连接', exact=True).click()
            expect(dialog.get_by_role('status')).to_contain_text('已连接')
            page.screenshot(path=str(evidence / 'connection-restored.png'))
            dialog.get_by_role('button', name='重新读取当前工作面').click()
            expect(dialog).not_to_be_visible()
            expect(page.locator('#view-title')).to_contain_text('第 2 页')
            expect(page).to_have_url(re.compile('revision=' + before['revision_id']))

            context.set_offline(True)
            page.get_by_role('navigation', name='项目工作区').get_by_role('button', name='内容与来源', exact=True).click()
            expect(page.get_by_role('button', name='重试读取', exact=True)).to_be_visible()
            expect(page.locator('#view-title')).to_contain_text('第 2 页')
            page.screenshot(path=str(evidence / 'route-retained-offline.png'))
            context.set_offline(False)
            page.get_by_role('button', name='重试读取', exact=True).click()
            expect(page.locator('#view-title')).to_have_text('内容与来源')
            expect(page).to_have_url(re.compile('surface=content'))
            expect(page).to_have_url(re.compile('revision=' + before['revision_id']))
            page.screenshot(path=str(evidence / 'route-retried.png'))
            assert store.load_document() == before
            assert not errors
            (evidence / 'results.json').write_text(json.dumps({'passed': True, 'route': route, 'final_url': page.url, 'document_unchanged': store.load_document() == before, 'errors': errors}, ensure_ascii=False, indent=2))
        finally:
            browser.close()
            server.stop()
