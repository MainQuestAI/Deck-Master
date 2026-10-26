"""Current-work navigation exposes its actual target outside the containing dialog."""
import shutil
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import workbench
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_pr187_review_regressions import native, reviewed_production  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('width', [390, 1280])
@pytest.mark.parametrize('kind', ['secondary', 'optional'])
def test_dialog_navigation_reveals_fixed_targets(tmp_path, native, route, width, kind):
    if kind == 'optional':
        project, store, reading = reviewed_production(tmp_path)
    else:
        project = tmp_path / 'gallery'
        create_gallery_sample(project, page_count=24, readonly=False)
        store, reading = Store(project), None
    before = store.load_document()
    work = workbench.workbench_summary(project, reading=reading, protocol='workbench_summary.v2')['current_work']
    action = (work['optional'][0] if kind == 'optional' else
              next(a for a in work['next']['actions'] if a['action_id'] != work['next']['primary_action']['action_id']))
    targets = workbench.action_targets(project, action['action_id'], revision=before['revision_id'])
    assert targets['total'] > 1
    server = WorkbenchServer(project)
    try:
        url = server.start()
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': width, 'height': 844})
            errors, writes = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' and not request.url.endswith('/api/ui-state') else None)
            identity = page.request.get(url + 'api/project').json()['project_identity']
            page.goto(url + route + '/#' + urlencode({'project': identity, 'surface': 'overview'}))
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            dialog = page.get_by_role('dialog')
            expect(dialog.locator('.todo-priority h2')).to_have_text(work['next']['title'])
            group = dialog.locator('.current-work-optional' if kind == 'optional' else '.todo-secondary')
            if kind == 'optional':
                expect(group).not_to_have_attribute('open', '')
            if not group.evaluate('element => element.open'):
                group.locator(':scope > summary').click()
            group.get_by_role('button').first.click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role('heading', name='待办对象', exact=True)).to_be_visible()
            expect(page.locator('.action-target')).to_have_count(targets['total'])
            assert set(page.locator('.action-target').evaluate_all('nodes => nodes.map(n => n.dataset.targetId)')) == {t['target_id'] for t in targets['targets']}
            assert not errors and not writes and store.load_document() == before
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path / f'{route}-{kind}-{width}.png'))
            browser.close()
    finally:
        server.stop()
