"""Synthetic 100-page production UI image-lease regression (#198)."""
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master.samples import create_sample
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('route', ['v2', 'studio'])
def test_all_hundred_overview_images_release_departed_leases(tmp_path, route):
    project = tmp_path / 'project'
    create_sample(project, page_count=100, readonly=False)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                page.goto(server.start() + route + '/')
                expect(page.get_by_role('heading', name='制作总览', exact=True)).to_be_visible()
                # The real initial chapter projection replaces the table rows
                # after the heading appears; start the lease walk once it commits.
                expect(page.locator('.chapter-row')).to_have_text(['工作台使用示例'])
                for index in range(100):
                    if route == 'studio' and index and index % 15 == 0:
                        page.get_by_role('button', name='下一组页面', exact=True).click()
                    row = page.locator('tr[data-page-id]').nth(index % 15 if route == 'studio' else index)
                    row.scroll_into_view_if_needed()
                    expect(row.locator('[data-image-state="ready"]')).to_have_count(1, timeout=20000)
                    assert page.locator('[data-image-state="failed"]').count() == 0
                stats = page.evaluate("async () => (await import('/v2/images.js')).imagePool.snapshot()")
                assert stats['pinned'] <= (15 if route == 'studio' else 48), stats
                assert stats['evictions'] > 0, stats
                if route == 'studio':
                    for _ in range(6):
                        page.get_by_role('button', name='上一组页面', exact=True).click()
                    first = page.locator('tr[data-page-id]').first
                    first.scroll_into_view_if_needed()
                    expect(first.locator('[data-image-state="ready"]')).to_have_count(1, timeout=20000)
                if route == 'v2':
                    page.set_viewport_size({'width': 1440, 'height': 12000})
                    for index in (0, 99):
                        row = page.locator('tr[data-page-id]').nth(index)
                        row.locator('button.title-button').focus()
                        expect(row.locator('[data-image-state="ready"]')).to_have_count(1, timeout=20000)
                    assert page.locator('[data-image-state="failed"]').count() == 0
                page.get_by_role('button', name='内容与页序', exact=True).click()
                expect(page.get_by_role('heading', name='内容与页序', exact=True)).to_be_visible()
                page.wait_for_function("async () => (await import('/v2/images.js')).imagePool.snapshot().pinned === 0")
            finally:
                browser.close()
    finally:
        server.stop()


def test_draft_persist_serializes_once_and_keeps_two_synchronous_writes(tmp_path):
    create_sample(tmp_path / 'draft-project', page_count=1)
    server = WorkbenchServer(tmp_path / 'draft-project')
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            try:
                page = browser.new_page()
                page.goto(server.start() + 'v2/drafts.js')
                results = page.evaluate('''async () => {
                  const {DraftEditor} = await import('/v2/drafts.js');
                  const stringify = JSON.stringify, setItem = Storage.prototype.setItem;
                  const results = [];
                  for (const failAt of [0, 1, 2]) {
                    let serializations = 0; const writes = [];
                    const editor = new DraftEditor({project_id:'synthetic',project_identity:'synthetic'},
                      {scope:'project',page_id:null,layer:'notes'},'revision',null);
                    Object.assign(editor,{draft:{draft_id:'synthetic'},etag:'etag',status:'dirty',pendingSave:null,
                      bufferKey:'synthetic-buffer',activeKey:'synthetic-active'});
                    JSON.stringify = (...args) => {serializations++; return stringify(...args);};
                    Storage.prototype.setItem = function(key, value) {
                      writes.push([key, value]);
                      if (writes.length === failAt) throw new Error('synthetic quota failure');
                      return setItem.call(this, key, value);
                    };
                    try {DraftEditor.prototype.persist.call(editor);}
                    finally {JSON.stringify = stringify; Storage.prototype.setItem = setItem;}
                    results.push({serializations,writes,error:editor.storageError});
                  }
                  return results;
                }''')
                assert [r['serializations'] for r in results] == [1, 1, 1]
                assert [len(r['writes']) for r in results] == [2, 1, 2]
                assert results[0]['writes'][0][1] == results[0]['writes'][1][1]
                assert not results[0]['error'] and results[1]['error'] and results[2]['error']
            finally:
                browser.close()
    finally:
        server.stop()
