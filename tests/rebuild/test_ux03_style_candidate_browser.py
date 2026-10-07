"""UX-03 风格与候选切片反例（FINAL-REPAIR-PLAN AC09–AC12，随实施追加）。

已覆盖：
- N07/AC05：同名已保存分析/规范在恢复前可区分——选项标签含状态与短尾，
  两份同 V 同要求的规范标签必然不同。
- N08/AC05：同一修改组在交接面板与运行筛选中共享同一短尾与计数，选择前可对上。
- N06：SVG 族任务的快捷阅读进入 SVG 层，按钮名称与层一致。
"""
import shutil
import uuid
from pathlib import Path

import pytest

from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_candidates import content_intent
from deck_master import changes as changes_mod

pytestmark = pytest.mark.browser

import base64
PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')

RECIPE_SHA = 'b' * 64


@pytest.fixture
def ux03_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    path = tmp_path / 'ux03-project'
    create_sample(path, page_count=3, readonly=False)
    store = Store(path)
    server = WorkbenchServer(path)
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for UX-03 checks')
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


def create_change_group(path, store, page_id, instruction):
    plan = changes_mod.plan(path, input=content_intent(store, page_id, instruction=instruction))
    return changes_mod.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                              operation_id=str(uuid.uuid4()))['operation_result']


def test_same_name_saved_recipes_and_groups_are_distinguishable_before_selection(ux03_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux03_browser
    url = server.start()
    create_change_group(path, store, 'p01', '第一组修改要求 AAA')
    create_change_group(path, store, 'p02', '第二组修改要求 BBB')

    def recipe(index):
        return {'recipe': {'schema_version': 'style_recipe.v2', 'recipe_id': f'recipe-{index:016x}',
                           'version': 1, 'input': {'instruction': '同样的风格要求，非常相似。', 'target_page_ids': ['p01'], 'visual_style_ref': {'path': '.deckmaster/objects/ab/' + RECIPE_SHA + '.json', 'sha256': RECIPE_SHA}}},
                'ref': {'path': '.deckmaster/objects/ab/' + RECIPE_SHA + '.json', 'sha256': RECIPE_SHA}}
    page.route('**/api/styles?**', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body='{"recipes": [%s]}' % ','.join(__import__('json').dumps(recipe(i)) for i in range(2))))

    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    page.get_by_text('其它修改组的交接', exact=True).click()
    panel = page.locator('.change-handoffs')
    buttons = panel.locator('.change-list button')
    expect(buttons).to_have_count(2)
    # 同一修改组在交接面板与运行筛选中共享同一短尾（N08）。
    handoff_labels = [buttons.nth(i).inner_text() for i in range(2)]
    assert handoff_labels[0][-6:] != handoff_labels[1][-6:]
    page.get_by_role('combobox', name='按修改组筛选').select_option(index=1)
    selected_label = page.get_by_role('combobox', name='按修改组筛选').locator('option:checked').inner_text()
    assert any(label.split(' · ')[-1] in selected_label for label in handoff_labels), (handoff_labels, selected_label)

    # 两份同 V 同要求的规范：选项标签含目标页数与短尾，恢复前可区分（N07）。
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    restore = page.get_by_text('恢复项目中的截图分析与规范', exact=True)
    restore.scroll_into_view_if_needed()
    restore.click()
    options = page.get_by_label('已确认的截图规范').locator('option')
    expect(options).to_have_count(3)
    labels = [options.nth(i).inner_text() for i in range(1, 3)]
    assert labels[0] != labels[1], '同名规范在恢复前必须可区分'


def test_svg_task_shortcut_opens_the_svg_layer(ux03_browser):
    page, server, path, store = ux03_browser
    from deck_master.models import content_identity
    from deck_master import tasks as tasks_mod
    from test_workbench_actions import commit
    doc = store.load_document()
    task = tasks_mod.new_task(task_id='svg-task-1', operation_id='op-svg-1', kind='reconstruct',
                              scope_pages=['p01'], instruction='重建这一页的 SVG。', inputs=[], dependencies=[],
                              dispatch_revision=doc['revision_id'], produced_against=content_identity(doc),
                              status='completed')
    doc['tasks'].append(store.put_json_object(task))
    commit(store, doc, str(uuid.uuid4()))
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.get_by_role('button', name='任务与交付', exact=True).click()
    page.get_by_role('heading', name='任务与交付', exact=True).wait_for()
    card = page.locator('.run-task').filter(has_text='制作可编辑稿')
    card.get_by_role('button', name='查看这项任务').click()
    page.locator('.run-evidence, .run-detail, #view-title').first.wait_for()
    import re
    shortcut = page.get_by_role('button', name=re.compile(r'^阅读 第 1 页 .* · SVG$'))
    shortcut.click()
    assert 'layer=svg' in page.url, page.url


SPEC_SHA = 'c' * 64
BREAKDOWN_SHA = 'd' * 64


def spec_document():
    return {'schema_version': 'visual_style_spec.v1', 'project_id': 'demo', 'analysis_request_ref': None,
            'references': [], 'palette': {'dominant': []},
            'dimensions': {key: {'summary': f'{key} 维度摘要', 'evidence': [
                {'certainty': 'observed' if key == 'palette' else 'unknown', 'observation': f'{key} 的观察记录'}]}
                for key in ['palette', 'typography', 'composition', 'spacing', 'density', 'lines', 'icons']},
            'font_suggestions': [{'family': 'Synthetic Sans', 'approximate': True, 'reason': '来自截图的近似判断'}],
            'conflicts': [], 'limitations': ['合成规范的局限说明'],
            'breakdown': {'path': f'.deckmaster/objects/ab/{BREAKDOWN_SHA}.png', 'sha256': BREAKDOWN_SHA}}


def v2_recipe(index, page_id='p01'):
    return {'schema_version': 'style_recipe.v2', 'recipe_id': f'recipe-{index:016x}', 'version': 1,
            'input': {'instruction': '同样的风格要求，非常相似。', 'target_page_ids': [page_id],
                      'visual_style_ref': {'path': f'.deckmaster/objects/ab/{SPEC_SHA}.json', 'sha256': SPEC_SHA}},
            'dimensions': {'palette': '借用配色摘要', 'typography': '借用文字层级摘要'}}


def install_style_mocks(page, *, recipes, detail, candidates=()):
    import json
    # 真实服务端把 reference_sources 一并放进 recipe 对象（confirm 从 proposal 拷贝）。
    recipe = detail.get('recipe', {})
    ref = recipe.get('input', {}).get('visual_style_ref')
    if ref:
        detail = {**detail, 'recipe': {**recipe,
                  'reference_sources': {'references': [], 'visual_style_ref': ref,
                                        'spec': spec_document(), 'breakdown': spec_document()['breakdown']}}}
    page.route('**/api/styles?*', lambda route: route.fulfill(
        status=200, content_type='application/json', body=json.dumps({'recipes': recipes})))
    page.route('**/api/styles/recipe-*', lambda route: route.fulfill(
        status=200, content_type='application/json', body=json.dumps(detail)))
    page.route('**/api/candidates?*', lambda route: route.fulfill(
        status=200, content_type='application/json', body=json.dumps({'candidates': list(candidates), 'revision_id': 'r'})))
    page.route('**/api/file*', lambda route: route.fulfill(
        status=200, content_type='application/json', body=json.dumps(spec_document())))
    page.route('**/api/thumbnails*', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'status': 'ready', 'url': '/api/thumbnail-file?cache_key=' + 'a' * 64})))
    page.route('**/api/thumbnail-file*', lambda route: route.fulfill(
        status=200, content_type='image/png', body=PNG_1PX))


def candidate_row(index, page_id, status, recipe_sha):
    sha = f'{index:08x}' + '0' * 56
    return {'candidate': {'candidate_id': f'candidate-{index:016x}', 'page_id': page_id, 'stage': 'blueprint',
                          'created_at': '2026-10-06T09:0%d:00Z' % index, 'result_ref': {'sha256': sha}},
            'ref': {'sha256': sha}, 'status': status,
            'style_recipe_ref': {'sha256': recipe_sha}}


def test_screenshot_recipe_restore_verifies_spec_and_keeps_schema_boundary(ux03_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux03_browser
    recipe_sha = 'e' * 64
    recipes = [{'recipe': v2_recipe(1), 'ref': {'sha256': recipe_sha}}]
    detail = {'recipe': v2_recipe(1), 'ref': {'sha256': recipe_sha}}
    rows = [candidate_row(1, 'p01', 'adopted', recipe_sha), candidate_row(2, 'p01', 'available', recipe_sha)]
    install_style_mocks(page, recipes=recipes, detail=detail, candidates=rows)

    page.goto(server.start())
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    restore = page.get_by_text('恢复项目中的截图分析与规范', exact=True)
    restore.scroll_into_view_if_needed()
    restore.click()
    page.get_by_label('已确认的截图规范').select_option(index=1)
    expect(page.locator('.visual-style p[role=status]')).to_contain_text('已打开所选确认规范')

    # AC10：拆解图直接可见；规范先显示借用/保留摘要；编辑器按需展开。
    expect(page.get_by_text('截图拆解图', exact=True)).to_be_visible()
    expect(page.locator('.visual-breakdown')).to_contain_text('截图拆解图')
    expect(page.locator('.visual-keep-summary')).to_contain_text('借用：配色、文字层级')
    expect(page.locator('.visual-keep-summary')).to_contain_text('保留：')
    assert page.get_by_label('借用截图配色').count() == 0 or not page.get_by_label('借用截图配色').is_visible()
    page.get_by_text('调整借用维度', exact=True).click()
    expect(page.get_by_label('借用截图配色')).to_be_checked()
    expect(page.get_by_label('借用截图文字层级')).to_be_checked()
    expect(page.get_by_label('借用截图构图')).not_to_be_checked()
    expect(page.get_by_label('构图规范')).to_have_value('composition 维度摘要')
    icons_rule = page.locator('.visual-rule').filter(has_text='图标')
    icons_rule.locator('summary').click()
    expect(icons_rule.get_by_text('待核实：icons 的观察记录')).to_be_visible()
    palette_rule = page.locator('.visual-rule').filter(has_text='配色')
    palette_rule.locator('summary').click()
    expect(palette_rule.get_by_text('已观察：palette 的观察记录')).to_be_visible()
    expect(page.get_by_text('字体判断：Synthetic Sans（近似）：来自截图的近似判断', exact=False)).to_be_visible()

    # AC10：样例选择只列已采用候选；同页两候选按钮以短码区分（ST-05）。
    page.locator('.visual-style').get_by_text('3 · 试作与采用', exact=True).click()
    sample = page.get_by_label('已采用的截图风格样例')
    expect(sample.locator('option')).to_have_count(2)
    compare_buttons = page.locator('.visual-style button').filter(has_text='比较 ')
    expect(compare_buttons.first).to_be_visible()
    labels = [compare_buttons.nth(i).inner_text() for i in range(compare_buttons.count())]
    assert len(labels) == 2 and labels[0] != labels[1], labels


def test_screenshot_route_refuses_a_project_recipe_with_a_clear_message(ux03_browser):
    from playwright.sync_api import expect
    page, server, path, store = ux03_browser
    detail = {'recipe': {'schema_version': 'style_recipe.v1', 'recipe_id': 'recipe-legacy', 'version': 1,
                         'input': {'instruction': '项目内配方', 'target_page_ids': ['p01']}}}
    install_style_mocks(page, recipes=[], detail=detail)
    page.goto(server.start())
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    restore = page.get_by_text('恢复项目中的截图分析与规范', exact=True)
    restore.scroll_into_view_if_needed()
    restore.click()
    page.evaluate("""async () => {
      const select = document.querySelector('.visual-style select[aria-label="恢复已确认的截图规范"]');
      const option = document.createElement('option');
      option.value = 'recipe-legacy'; option.textContent = 'V1 · 项目内配方';
      select.append(option); select.value = 'recipe-legacy';
      select.dispatchEvent(new Event('change'));
    }""")
    expect(page.locator('.visual-style p[role=status]')).to_contain_text('这不是截图视觉规范')


def test_candidate_desk_rapid_switch_late_reply_and_decisions_target_displayed_object(ux03_browser):
    """AC11：同页两候选快速切换与晚回包；比较两侧保持固定；采用/保留只针对展示对象。"""
    import json
    import re
    from playwright.sync_api import expect
    from test_candidates import candidate
    page, server, path, store = ux03_browser
    url = server.start()
    cid1 = candidate(store, width=20)
    cid2 = candidate(store, width=24)
    assert cid1 != cid2
    plan_bodies, decision_bodies = [], []
    page.route('**/api/candidates/plan', lambda route: (plan_bodies.append(route.request.post_data_json), route.continue_()))
    page.route('**/api/candidates/decision', lambda route: (decision_bodies.append(route.request.post_data_json), route.continue_()))

    def desk_id():
        return page.locator('.candidate-desk').get_attribute('data-candidate-id')

    page.goto(url)
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("args => {location.hash = new URLSearchParams({project: args[0], surface: 'page', page: 'p01', layer: 'svg', candidate: args[1], revision: args[2]})}",
                  [page.request.get(url.rstrip('/') + '/api/project').json()['project_identity'], cid1, store.current_revision_id()])
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid1)

    # 快速切换：候选 2 正常应用，展示对象随之切换。
    page.get_by_label('选择本页候选').select_option(index=1)
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid2)

    # 采用/保留只针对展示对象：payload 绑定候选 2。
    page.get_by_role('button', name='预览采用这个候选', exact=True).click()
    expect(page.locator('.candidate-impact')).to_contain_text('本次采用 1 页')
    assert plan_bodies and plan_bodies[-1]['input']['candidate_ids'] == [cid2]
    page.get_by_role('button', name='保留当前', exact=True).click()
    expect(page.locator('.candidate-state')).to_contain_text('已保留当前')
    assert decision_bodies and decision_bodies[-1]['input']['candidate_id'] == cid2

    # 切回候选 1，再让候选 2 的状态回包晚到：晚回包被丢弃，展示对象不变。
    page.get_by_role('button', name='刷新候选与当前状态', exact=True).click()
    held = []
    page.route(f'**/api/candidates/{cid2}', lambda route: held.append(route))
    page.get_by_role('button', name='刷新候选与当前状态', exact=True).click()
    page.get_by_label('选择本页候选').select_option(index=0)
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid1)
    assert held, '候选 2 的状态请求应处于挂起状态'
    late_route = held.pop(0)
    late_route.fulfill(response=late_route.fetch())
    page.wait_for_timeout(300)
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid1)
    expect(page.locator('.candidate-state')).to_contain_text('候选可比较')

    # 读取期间动作禁用：先拦截候选 2 的详情，再切换——比较两侧保持候选 1 的
    # 固定画面，保留/采用停用；放行详情后候选 2 才应用。
    held2 = []
    page.unroute(f'**/api/candidates/{cid2}')
    page.route(f'**/api/candidates/{cid2}', lambda route: held2.append(route))
    page.get_by_label('选择本页候选').select_option(index=1)
    expect(page.locator('.candidate-impact')).to_contain_text('正在读取所选候选')
    expect(page.get_by_role('button', name='保留当前', exact=True)).to_be_disabled()
    expect(page.get_by_role('button', name='预览采用这个候选', exact=True)).to_be_disabled()
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid1)
    late2 = held2.pop(0)
    late2.fulfill(response=late2.fetch())
    expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', cid2)


def test_expansion_plan_carries_adopted_sample_and_explains_core_rejection(ux03_browser):
    """AC12：扩展请求绑定仍采用样例与明确选页；核心拒绝时 UI 给出准确解释。

    核心侧拒绝路径（错配方、未选页/参考页、目标基准变化使样例失效）由
    test_styles.py 与 test_visual_style_freshness.py 覆盖；本反例验证 UI 层：
    扩展请求的 payload 绑定样例，style_conflict 显示业务翻译而非原始失败。
    """
    import json
    from playwright.sync_api import expect
    from test_candidates import candidate
    page, server, path, store = ux03_browser
    recipe_sha = 'e' * 64
    recipe = v2_recipe(1)
    recipe['input']['target_page_ids'] = ['p01', 'p03']
    recipes = [{'recipe': recipe, 'ref': {'sha256': recipe_sha}}]
    detail = {'recipe': recipe, 'ref': {'sha256': recipe_sha}}
    rows = [candidate_row(1, 'p01', 'adopted', recipe_sha)]
    install_style_mocks(page, recipes=recipes, detail=detail, candidates=rows)
    plan_posts = []

    def plan_rejection(route):
        plan_posts.append(route.request.post_data_json)
        route.fulfill(status=409, content_type='application/json', body=json.dumps({'error': {
            'code': 'style_conflict', 'field': 'targets',
            'message': 'selected target bases changed; unaffected targets remain readable',
            'details': {'items': [{'page_id': 'p03', 'cause': 'generation_basis_changed'}]}}}))
    page.route('**/api/styles/plan*', plan_rejection)

    page.goto(server.start())
    page.get_by_role('button', name='风格校准', exact=True).click()
    page.get_by_role('heading', name='风格校准', exact=True).wait_for()
    page.get_by_label('风格参考来源').select_option('screenshot')
    restore = page.get_by_text('恢复项目中的截图分析与规范', exact=True)
    restore.scroll_into_view_if_needed()
    restore.click()
    page.get_by_label('已确认的截图规范').select_option(index=1)
    expect(page.locator('.visual-style p[role=status]')).to_contain_text('已打开所选确认规范')

    # 从仍采用样例扩展到明确选页：请求绑定样例与目标页。
    page.locator('.visual-style').get_by_text('4 · 扩展', exact=True).click()
    sample = page.get_by_label('已采用的截图风格样例')
    expect(sample.locator('option')).to_have_count(2)
    sample.select_option(index=1)
    expansion = page.get_by_label('本次扩展到', exact=False)
    expansion.check()
    page.get_by_role('button', name='预览所选页扩展', exact=True).click()
    expect(page.locator('.visual-style p[role=status]')).to_contain_text('风格要求或目标页基准已变化')
    assert plan_posts, '扩展计划请求应已发出'
    sent = plan_posts[-1]['input']
    assert sent['adopted_candidate_id'] == 'candidate-0000000000000001' and sent['page_ids'] == ['p03']
