"""U01 navigation in Chromium against real loopback reads; synthetic data."""
from pathlib import Path
import shutil
import copy
import uuid

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_action_targets import add_handoffs
from test_candidates import candidate
from test_content_candidates import dispatch_content_ops_trial, start_task, accept, changeset_envelope
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


@pytest.fixture
def action_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'browser-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for navigation checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, server, path, store
            assert errors == []
        finally:
            browser.close()
            server.stop()


def test_grouped_todo_lists_every_task_then_opens_the_selected_task(action_browser):
    page, server, path, store = action_browser
    add_handoffs(store)
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='去交接', exact=True).click()
    page.get_by_role('heading', name='待办对象', exact=True).wait_for()
    assert page.locator('.action-target').count() == 2
    page.screenshot(path=str(path.parent / 'grouped-tasks.png'))
    page.locator('.action-target').nth(1).get_by_role('button', name='查看这个对象').click()
    page.get_by_role('heading', name='当前任务', exact=True).wait_for()
    assert 'task=handoff-1' in page.url
    assert store.read_current() == before


def test_multi_candidate_todo_and_historical_candidate_reads(action_browser):
    page, server, path, store = action_browser
    ids = [candidate(store, width=20), candidate(store, width=24)]
    revision = store.current_revision_id()
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.get_by_role('heading', name='待办对象', exact=True).wait_for()
    assert page.locator('.action-target').count() == 2
    page.locator('.action-target').nth(1).get_by_role('button', name='查看这个对象').click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="' + ids[1] + '"]')
    assert 'page=p01' in page.url and 'layer=svg' in page.url
    assert store.read_current() == before
    old_url = page.url
    doc = copy.deepcopy(store.load_document())
    doc['policy']['user_stop'] = True
    commit(store, doc, str(uuid.uuid4()))
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/candidates' in request.url else None)
    page.goto(old_url)
    page.reload()
    page.wait_for_selector('.candidate-desk[data-candidate-id="' + ids[1] + '"]')
    page.get_by_text('历史版本 · 只读', exact=True).wait_for()
    assert requests and all('revision=' + revision in url for url in requests)
    assert page.get_by_role('button', name='预览采用这个候选', exact=True).is_disabled()


def test_changeset_todo_opens_fixed_deck_comparison_without_fake_page(action_browser):
    page, server, path, store = action_browser
    task = dispatch_content_ops_trial(path, store, 'merge', ('p01', 'p02'))
    start_task(path, task)
    accept(path, task, changeset_envelope(store, task, 'merge'))
    before = store.read_current()
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.get_by_role('heading', name='整稿正文变更集比较', exact=True).wait_for()
    assert 'surface=content' in page.url and 'candidate=' in page.url and '&page=' not in page.url
    page.locator('.changeset-page').filter(has_text='Synthetic derived page 0').locator('summary').click()
    page.get_by_role('heading', name='固定基准正文', exact=True).wait_for()
    assert 'Synthetic derived page 0' in page.locator('[data-side="candidate"]').inner_text()
    assert 'Synthetic derived page 0' not in page.locator('[data-side="current"]').inner_text()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(path.parent / 'changeset-mobile.png'))
    assert store.read_current() == before


def test_foreign_project_link_keeps_the_loaded_work_surface(action_browser):
    from playwright.sync_api import expect
    page, server, path, store = action_browser
    before = store.read_current()
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("revision => {location.hash = new URLSearchParams({project:'0'.repeat(64),surface:'overview',revision})}", store.current_revision_id())
    expect(page.locator('.notice')).to_contain_text('这个链接属于另一个项目')
    assert page.get_by_role('heading', name='制作总览', exact=True).is_visible()
    assert store.read_current() == before
