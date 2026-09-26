"""Browser regressions for six Review 1 findings; synthetic UI data only."""
from pathlib import Path
import json
import hashlib
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'validation'
URL = 'http://127.0.0.1:8766/'
results = []

def shot(page, name, width):
    path = OUT / f'round1-after-{name}-{width}.png'
    page.screenshot(path=str(path), full_page=True)
    return path.name

def action(page, name):
    page.get_by_role('button', name=name, exact=True).click()

def go(page, route):
    page.goto(URL + '#' + route)

def task(page):
    return page.evaluate('JSON.parse(JSON.stringify(currentStyleTask()))')

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, height in [(1280, 800), (1440, 900)]:
        ctx = browser.new_context(viewport={'width': width, 'height': height}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        evidence = []
        go(page, 'page/12/image')
        original_image = page.locator('#mark-surface svg').evaluate('(e)=>e.outerHTML')
        original_prompt = page.locator('.page-split > section').nth(1).inner_text()
        go(page, 'page/12/svg')
        assert page.locator('#main [data-sample-arrow="reverse"]').count() == 1
        evidence.append(shot(page, 'p12-svg-defect', width))
        action(page, '标注与意见')
        page.locator('#page-note').fill('中间箭头应从诊断指向处理，保留原图和文字。')
        action(page, '保存意见')
        assert page.evaluate('state.tasks.length') == 0
        action(page, '仅重建 SVG'); action(page, '加入待交接')
        assert page.evaluate('state.tasks[0].targetStage') == 'svg'
        assert '诊断指向处理' in page.evaluate('state.tasks[0].note')
        action(page, '模拟接手'); action(page, '模拟返回候选'); action(page, '查看候选并比较')
        assert page.locator('#modal [data-artifact-ref="p12/svg/v2"]').count() == 1
        assert page.locator('#modal [data-artifact-ref="p12/svg/v3"]').count() == 1
        assert page.locator('#modal .comparison > section').nth(0).locator('[data-sample-arrow="reverse"]').count() == 1
        assert page.locator('#modal .comparison > section').nth(1).locator('[data-sample-arrow="reverse"]').count() == 0
        evidence.append(shot(page, 'p12-svg-candidate', width))
        action(page, '采用这个样本候选')
        go(page, 'page/12/svg')
        assert '当前版本 · v3' in page.inner_text('body') and '已采用 v3' in page.inner_text('body')
        assert page.locator('#main [data-sample-arrow="reverse"]').count() == 0
        evidence.append(shot(page, 'p12-svg-adopted', width))
        go(page, 'page/12/ppt')
        assert '旧版 v2 · 上游 SVG 已变化，待更新' in page.inner_text('body')
        assert page.locator('#main [data-sample-arrow="reverse"]').count() == 1
        go(page, 'page/12/image')
        assert page.locator('#mark-surface svg').evaluate('(e)=>e.outerHTML') == original_image
        action(page, '执行提示词')
        assert page.locator('.page-split > section').nth(1).inner_text() == original_prompt
        page.reload()
        assert page.locator('#mark-surface svg').evaluate('(e)=>e.outerHTML') == original_image
        assert page.evaluate("artifact(pages[11],'svg').version") == 3
        # R1-03/04: a color-only request survives reload and remains immutable on retry.
        go(page, 'style')
        page.locator('#style-requirement').fill('请让这一页更清楚')
        page.locator('.fine-settings > summary').first.click()
        for dimension in ['type', 'density', 'lines']:
            page.locator(f'[data-dimension="{dimension}"]').uncheck()
        action(page, '先试第 8 页 →')
        first = task(page)
        assert first['targetStage'] == 'image' and first['pages'] == [8]
        assert first['style']['reference']['page'] == 7 and first['style']['reference']['version'] == 2
        assert first['style']['dimensions'] == ['color']
        go(page, 'overview'); action(page, '继续处理 →'); page.reload()
        assert task(page) == first
        action(page, '复制交接文本')
        page.wait_for_function("currentStyleTask().status === 'copied'")
        copied = page.evaluate('navigator.clipboard.readText()')
        assert '固定风格参考：第 7 页原图 v2' in copied
        assert '实际执行范围：第 8 页' in copied and '目标层：image（原图）' in copied
        assert '风格维度：色板\n' in copied and '风格维度：色板、' not in copied
        assert '必须保留：事实、数字、标题、出处、职责、内容与叙事结构' in copied
        assert f'请求：DEMO-{first["id"]}' in copied and '固定目标产物：p08/image/v2' in copied
        evidence.append(shot(page, 'fixed-style-request', width))
        action(page, '模拟 Host 接手'); action(page, '模拟候选返回')
        first_candidate = task(page)['candidates']
        evidence.append(shot(page, 'style-decisions', width))
        action(page, '保留当前')
        assert task(page)['status'] == 'kept'
        assert page.evaluate("artifact(pages[7],'image').version") == 2
        go(page, 'overview'); assert '候选已返回，等你比较' not in page.inner_text('body')
        go(page, 'style'); action(page, '调整要求再试')
        page.locator('#style-requirement').fill('只同步色板，保留原来的模块圆角和内容。')
        action(page, '保存第 8 页的新请求 →')
        second = task(page)
        assert second['id'] != first['id'] and second['retryOf'] == first['id']
        old = page.evaluate(f'state.tasks.find(t=>t.id==={first["id"]})')
        assert old['status'] == 'kept' and old['candidates'] == first_candidate
        assert old['style']['requirement'] == '请让这一页更清楚'
        assert page.evaluate("artifact(pages[7],'image').version") == 2
        go(page, 'page/8/image'); action(page, '固定双层比较'); go(page, 'style')
        action(page, '模拟 Host 接手'); action(page, '模拟候选返回')
        base_svg = page.locator('.candidate-compare > section').nth(0).locator('svg').evaluate('(e)=>e.outerHTML')
        action(page, '采用这个候选 · 仅第 8 页')
        assert page.locator('.candidate-compare > section').nth(0).locator('svg').evaluate('(e)=>e.outerHTML') == base_svg
        assert '原图 v2 · p08/image/v2' in page.locator('.compare-column-head').first.inner_text()
        # R1-05: all current labels agree; old downstream and fixed request basis remain old.
        go(page, 'page/8/image')
        assert '固定左侧：原图 / v2' in page.inner_text('body')
        assert page.locator('#main [data-artifact-ref="p08/image/v2"]').count() == 1
        action(page, '退出双层比较')
        assert '当前版本 · v3' in page.inner_text('body') and '实际生成原图 · 已采用 v3' in page.inner_text('body')
        assert 'gen-008-v3 · 提示词 v3' in page.inner_text('body')
        assert '当前版本 · v2' not in page.inner_text('body')
        evidence.append(shot(page, 'p8-current-v3', width))
        for stage in ['svg', 'ppt']:
            go(page, 'page/8/' + stage)
            assert '当前版本 · v2' in page.inner_text('body')
            assert '旧版 v2 · 上游原图已变化，待更新' in page.inner_text('body')
        # R1-06: repeated continuation resolves to the same P9 request, carrying the frozen style.
        go(page, 'style'); action(page, '将余下 1 页加入待交接')
        assert page.evaluate('state.tasks.filter(t=>t.style&&t.pages[0]===9).length') == 1
        ninth = page.evaluate('state.tasks.find(t=>t.style&&t.pages[0]===9)')
        assert ninth['style'] == second['style']
        go(page, 'style'); action(page, '查看第 9 页请求')
        assert task(page)['id'] == ninth['id']
        go(page, 'runs')
        row = page.locator('.run-item').filter(has_text=f'DEMO-{second["id"]}')
        row.get_by_role('button', name='查看固定请求', exact=True).click()
        action(page, '查看第 9 页请求')
        assert page.evaluate('state.tasks.filter(t=>t.style&&t.pages[0]===9).length') == 1
        action(page, '复制交接文本');page.wait_for_function("currentStyleTask().status === 'copied'")
        copied9 = page.evaluate('navigator.clipboard.readText()')
        assert '实际执行范围：第 9 页' in copied9 and '固定目标产物：p09/image/v2' in copied9
        assert '风格维度：色板\n' in copied9 and '固定风格参考：第 7 页原图 v2' in copied9
        evidence.append(shot(page, 'p9-existing-request', width))
        for route in ['projects', 'overview', 'content', 'gallery', 'style', 'runs', 'page/12/svg']:
            go(page, route)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
        assert not errors, errors
        ctx.close()
        # R1-02 uses fresh contexts to ensure terminal outcomes cannot borrow an adopted state.
        for outcome in ['failed', 'cancelled']:
            ctx = browser.new_context(viewport={'width': width, 'height': height})
            page = ctx.new_page();page.on('pageerror', lambda e: errors.append(str(e)))
            go(page, 'style');action(page, '先试第 8 页 →')
            original = task(page)
            if outcome == 'failed':
                action(page, '模拟 Host 接手');action(page, '模拟失败')
            else:
                action(page, '取消本次试做')
            go(page, 'overview');action(page, '继续处理 →');page.reload()
            assert task(page)['status'] == outcome
            assert '当前原图保留' in page.inner_text('body')
            assert '原图已采用' not in page.inner_text('body')
            assert page.get_by_role('button', name='调整要求再试', exact=True).is_visible()
            evidence.append(shot(page, 'style-'+outcome, width))
            action(page, '调整要求再试')
            page.locator('#style-requirement').fill('重试仅调整颜色，保持内容。')
            action(page, '保存第 8 页的新请求 →')
            assert task(page)['id'] != original['id']
            assert page.evaluate(f'state.tasks.find(t=>t.id==={original["id"]}).status') == outcome
            assert page.evaluate("artifact(pages[7],'image').version") == 2
            ctx.close()
        assert not errors, errors
        results.append({'viewport':f'{width}x{height}','status':'passed','page_errors':errors,'evidence':evidence,'findings_closed':['R1-01','R1-02','R1-03','R1-04','R1-05','R1-06']})
    browser.close()
result={'scope':'synthetic localStorage prototype only; no model, CLI or production acceptance','status':'passed','browser':'Chromium','results':results,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app.js','style.css','index.html']},'checks':['P12 visible SVG arrow defect and repaired SVG v3, same image/prompt v2 and stale PPT v2','saved SVG opinion joins exactly one rebuild request','failure/cancellation refresh and explicit new request','keep current closes decision; edited retry preserves old request/candidate','color-only fixed P7 reference and P8/P9 actual scope survive clipboard/reload','P8 current v3 labels agree; request compare baseline stays v2','P9 continuation reuses existing request','7 routes have no horizontal overflow at both desktop viewports']}
(OUT/'round1-fixes-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
