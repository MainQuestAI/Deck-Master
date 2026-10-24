"""RP-09: real browser reads immutable recipes; synthetic content, zero model calls."""
import shutil
import uuid

import pytest
from deck_master import styles
from deck_master.web import WorkbenchServer
from test_rc3_design_feasibility import authorized, value
from test_styles import flow, confirm, value as old_value  # noqa: F401
from test_visual_styles import completed
from test_rc3_design_recipes import input_value

pytestmark = pytest.mark.browser


def save_recipe(project, store, data):
    proposal = styles.propose(project, input=data)
    return styles.confirm(project, proposal_id=proposal['proposal_id'],
                          base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']['recipe_id']


@pytest.mark.parametrize('route', ['studio/', 'v2/'])
@pytest.mark.parametrize('intent', ['initial_design', 'feasibility'])
def test_v3_without_originals_is_readable_and_reopens_without_dispatch(tmp_path, route, intent):
    from playwright.sync_api import sync_playwright, expect
    project, store, _ = authorized(tmp_path, actions=('design.propose',), current_manuscript=True)
    rid = save_recipe(project, store, value(store, intent=intent))
    before = store.load_document()
    assert all(p['blueprint'] is None for p in before['pages'])
    server = WorkbenchServer(project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1280, 'height':800})
        errors, plans = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: plans.append(r.post_data_json) if r.url.endswith('/api/styles/plan') else None)
        try:
            page.goto(server.start()+route)
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('button', name='浏览所有设计规范', exact=True).click()
            if route == 'studio/':
                page.locator(f'[data-recipe-id="{rid}"]').get_by_role('button').click()
            else:
                page.get_by_label('已确认的风格版本', exact=True).select_option(rid)
            expect(page.locator('.style-calibration')).to_contain_text('style_recipe.v3')
            expect(page.locator('.style-calibration')).to_contain_text('关系不随位置调整改变')
            expect(page.locator('.style-calibration')).to_contain_text('不代表当前全稿方向或生产许可')
            page.screenshot(path=str(tmp_path / 'recipe.png'), full_page=True)
            assert page.get_by_label('先试哪一页', exact=True).last.locator('option').all_text_contents() == ['第 1 页 · 人工确认后提交']
            if route == 'studio/':
                page.locator('.style-calibration > .studio-style-stages').get_by_role('button', name='3 · 试作与采用', exact=False).click()
            else:
                page.locator('.style-calibration > details.style-phase').nth(2).locator('summary').click()
            trial = page.locator('.style-calibration > .style-phase').nth(2).get_by_role('button', name='预览单页试作', exact=True)
            if intent == 'feasibility':
                expect(trial).to_be_disabled()
            else:
                expect(trial).to_be_enabled()
                trial.click()
                expect(page.locator('.style-calibration')).to_contain_text('最多 1 次图像调用')
                assert plans[-1]['input'] == {'recipe_id':rid, 'page_ids':['p1'], 'max_calls':1}
            assert store.load_document() == before
            page.reload()
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('button', name='浏览所有设计规范', exact=True).click()
            expect(page.get_by_label('已确认的风格版本').locator(f'option[value="{rid}"]')).to_have_count(1)
            assert store.load_document() == before and not errors
        finally:
            browser.close()
            server.stop()


def test_mixed_recipe_catalog_preserves_types_and_paging(flow):
    from playwright.sync_api import sync_playwright, expect
    ids = [confirm(flow, old_value(flow, instruction=f'页面规范 {n}'))['recipe_id'] for n in range(6)]
    ref, _, _ = completed(flow)
    v2 = save_recipe(flow.project, flow.store, {'schema_version':'style_input.v2',
        'project_id':flow.store.load_document()['project_id'], 'base_revision':flow.store.current_revision_id(),
        'visual_style_ref':ref, 'target_page_ids':['p02'], 'instruction':'独立截图规范'})
    historical_revision = flow.store.current_revision_id()
    v3 = save_recipe(flow.project, flow.store, input_value(flow.store.load_document(), ids=['p02','p03']))
    before = flow.store.load_document()
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button', name='风格校准', exact=True).click()
            page.get_by_role('button', name='浏览所有设计规范', exact=True).click()
            expect(page.locator('.studio-recipe-card')).to_have_count(6)
            page.get_by_role('button',name='下一组规范',exact=True).click()
            expect(page.locator('.studio-recipe-card')).to_have_count(2)
            page.locator(f'[data-recipe-id="{v2}"]').get_by_role('button').click()
            expect(page.locator('.style-calibration')).to_contain_text('style_recipe.v2')
            expect(page.locator('.style-calibration')).to_contain_text('独立截图参考')
            page.get_by_label('搜索已确认风格规范').fill('初始设计')
            expect(page.locator('.studio-recipe-card')).to_have_count(1)
            page.locator(f'[data-recipe-id="{v3}"]').get_by_role('button').click()
            expect(page.locator('.style-calibration')).to_contain_text('style_recipe.v3')
            assert page.get_by_label('先试哪一页',exact=True).last.locator('option').count() == 2
            page.get_by_label('搜索已确认风格规范').fill('页面规范 0')
            page.locator(f'[data-recipe-id="{ids[0]}"]').get_by_role('button').click()
            expect(page.locator('.style-calibration')).to_contain_text('style_recipe.v1')
            expect(page.get_by_role('button',name='以此版本修改要求',exact=True)).to_be_visible()
            page.evaluate('(revision) => {const q=new URLSearchParams(location.hash.slice(1));q.set("revision",revision);location.hash=q.toString();}', historical_revision)
            page.get_by_role('button', name='浏览所有设计规范', exact=True).click()
            expect(page.get_by_label('已确认的风格版本').locator('option')).to_have_count(8)
            expect(page.get_by_label('已确认的风格版本').locator(f'option[value="{v3}"]')).to_have_count(0)
            assert flow.store.load_document() == before and not errors
        finally:
            browser.close()
            server.stop()
