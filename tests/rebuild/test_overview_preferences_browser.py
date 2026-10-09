"""U03 real browser restoration, concurrent edits, unknown saves and clears."""
import copy
import json
import uuid
from urllib.parse import urlencode

import pytest

from deck_master import overview_state, ui_journal
from test_batch_actions_browser import batch_browser  # noqa: F401
from test_ui_state_clear import plan as clear_plan, commit as clear_commit
from test_workbench_actions import commit

pytestmark = pytest.mark.browser


def fixed_url(page, project, revision, **preferences):
    info = ui_journal.project_info(project)
    return page.url.split('#')[0] + '#' + urlencode({'project': info['project_identity'], 'surface': 'overview', 'revision': revision, **preferences})


def saved(page):
    from playwright.sync_api import expect
    expect(page.locator('.overview-preference-status')).to_have_text('总览阅读偏好已保存')


def test_refresh_cross_surface_and_explicit_url_restore_only_reading_preferences(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p03')
    page.get_by_role('button', name='只看需要处理 3 页', exact=True).click()
    page.get_by_role('button', name='页面 · 升序', exact=True).click()
    saved(page)
    page.get_by_role('checkbox', name='选择第 03 页', exact=True).check()
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    page.get_by_role('button', name='制作总览', exact=True).click()
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p03')
    expect(page.locator('.matrix th[aria-sort]')).to_have_attribute('aria-sort', 'descending')
    # D1：选择随个人阅读状态保留，跨工作面切换与刷新都不清空。
    expect(page.get_by_role('checkbox', name='选择第 03 页', exact=True)).to_be_checked()
    page.reload()
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p03')
    expect(page.get_by_role('checkbox', name='选择第 03 页', exact=True)).to_be_checked()
    old = overview_state.get(project, revision=before['revision_id'])
    page.goto(fixed_url(page, project, before['revision_id'], q='p01', filter='all', sort='ascending'))
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p01')
    assert overview_state.get(project, revision=before['revision_id']) == old
    assert store.read_current() == before


def test_new_revision_defaults_and_old_link_keeps_its_fixed_preferences(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    old_revision = store.current_revision_id()
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p02')
    saved(page)
    old_url = page.url
    commit(store, copy.deepcopy(store.load_document()), str(uuid.uuid4()))
    current = store.read_current()
    page.goto(fixed_url(page, project, current['revision_id']))
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('')
    assert page.get_by_role('checkbox', name='选择第 01 页', exact=True).count()
    page.goto(old_url)
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p02')
    expect(page.get_by_text('历史版本 · 只读', exact=True)).to_be_visible()
    assert overview_state.get(project, revision=old_revision)['record']['state']['search'] == 'p02'
    assert store.read_current() == current


def test_two_actual_windows_keep_conflicting_input_and_require_explicit_choice(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p01')
    saved(page)
    second = page.context.new_page()
    second.goto(fixed_url(page, project, before['revision_id']))
    expect(second.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p01')
    second.get_by_role('searchbox', name='搜索页码或标题').fill('p02')
    saved(second)
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p03')
    expect(page.locator('.overview-preference-status')).to_contain_text('另一个窗口修改或清理了偏好')
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p03')
    page.get_by_role('button', name='核实总览偏好', exact=True).click()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.get_by_role('heading', name='总览阅读偏好：选择保留哪一份', exact=True).wait_for()
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    page.locator('dialog[open]').screenshot(path=str(project.parent / 'overview-conflict-mobile.png'))
    page.get_by_role('button', name='明确保存此窗口偏好', exact=True).click()
    saved(page)
    assert overview_state.get(project, revision=before['revision_id'])['record']['state']['search'] == 'p03'
    second.close()
    assert store.read_current() == before


def test_lost_preference_response_is_verified_without_replaying_or_losing_later_input(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    requests = []
    def lose(route):
        requests.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 200
        route.abort('failed')
    page.route('**/api/overview', lose)
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p01')
    expect(page.locator('.overview-preference-status')).to_contain_text('保存尚未确认')
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p02')
    page.unroute('**/api/overview', lose)
    page.get_by_role('button', name='核实总览偏好', exact=True).click()
    saved(page)
    assert len(requests) == 1 and requests[0]['state']['search'] == 'p01'
    assert overview_state.get(project, revision=before['revision_id'])['record']['state']['search'] == 'p02'
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p02')
    assert not page.locator('dialog[open]').count()
    assert store.read_current() == before


def test_delayed_initial_save_after_clear_cannot_resurrect_preferences(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    pending = []
    page.route('**/api/overview', lambda route: pending.append(route))
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p03')
    expect(page.locator('.overview-preference-status')).to_contain_text('正在保存')
    assert pending
    clear_commit(project, clear_plan(project))
    result = pending[0].fetch()
    assert result.status == 409
    pending[0].fulfill(response=result)
    expect(page.locator('.overview-preference-status')).to_contain_text('修改或清理了偏好')
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p03')
    assert overview_state.get(project, revision=before['revision_id'])['record'] is None
    assert store.read_current() == before


def test_navigation_keeps_unconfirmed_input_and_damaged_state_does_not_break_overview(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    pending = []
    page.route('**/api/overview', lambda route: pending.append(route))
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p03')
    expect(page.locator('.overview-preference-status')).to_contain_text('正在保存')
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    page.get_by_role('button', name='制作总览', exact=True).click()
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p03')
    pending[0].fulfill(response=pending[0].fetch())
    saved(page)
    page.unroute('**/api/overview')
    overview_state._file(store).write_text('{broken')
    page.goto(fixed_url(page, project, before['revision_id']))
    page.reload()
    expect(page.locator('.overview-preference-status')).to_contain_text('暂不可读')
    assert page.get_by_role('checkbox', name='选择第 01 页', exact=True).count()
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p02')
    expect(page.get_by_role('button', name='下载总览偏好副本', exact=True)).to_be_visible()
    assert overview_state._file(store).read_text() == '{broken'
    assert store.read_current() == before


def test_old_core_uses_session_state_and_malformed_explicit_url_keeps_surface(batch_browser):
    from playwright.sync_api import expect
    page, server, project, store = batch_browser
    before = store.read_current()
    def old_health(route):
        result = route.fetch()
        data = result.json()
        data['ui_capabilities'].remove('ui_overview.v1')
        route.fulfill(response=result, body=json.dumps(data))
    page.route('**/api/health', old_health)
    requests = []
    page.on('request', lambda request: requests.append(request.url) if '/api/overview' in request.url else None)
    page.reload()
    expect(page.locator('.overview-preference-status')).to_contain_text('本窗口会话')
    page.get_by_role('searchbox', name='搜索页码或标题').fill('p02')
    page.get_by_role('button', name='内容与来源', exact=True).click()
    page.get_by_role('heading', name='内容与来源', exact=True).wait_for()
    page.get_by_role('button', name='制作总览', exact=True).click()
    expect(page.get_by_role('searchbox', name='搜索页码或标题')).to_have_value('p02')
    page.evaluate("() => { location.hash += '&filter=invalid'; }")
    expect(page.locator('.notice')).to_contain_text('筛选或排序无效')
    assert page.get_by_role('heading', name='制作总览', exact=True).is_visible()
    assert requests == [] and store.read_current() == before
