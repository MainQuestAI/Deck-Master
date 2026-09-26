"""Prototype-only browser behavior checks. Run while localhost:8766 is serving."""
from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import os
VIEWPORT = dict(zip(("width", "height"), map(int, os.environ.get("PROTOTYPE_VIEWPORT", "1280x800").split("x"))))

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport=VIEWPORT)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8766/#gallery')
    page.get_by_role('button', name='PPT 预览 12/24', exact=True).click()
    assert page.locator('.empty-artifact').count() == 12
    page.goto('http://127.0.0.1:8766/#style')
    page.get_by_role('button', name='先试第 8 页 →', exact=True).click()
    assert page.get_by_role('button', name='模拟候选返回', exact=True).is_disabled()
    page.get_by_role('button', name='模拟 Host 接手', exact=True).click()
    page.get_by_role('button', name='模拟候选返回', exact=True).click()
    page.get_by_role('button', name='采用这个候选 · 仅第 8 页', exact=True).click()
    page.goto('http://127.0.0.1:8766/#page/8/svg')
    assert '旧版 v2 · 上游原图已变化，待更新' in page.inner_text('body')
    page.goto('http://127.0.0.1:8766/#page/7/svg')
    assert '旧版 v2 · 上游原图已变化，待更新' not in page.inner_text('body')
    page.goto('http://127.0.0.1:8766/#page/8/image')
    page.get_by_role('button', name='标注与意见', exact=True).click()
    page.locator('#page-note').fill('整页意见不需要框选，保持信息结构。')
    page.reload()
    page.get_by_role('button', name='标注与意见', exact=True).click()
    assert page.locator('#page-note').input_value() == '整页意见不需要框选，保持信息结构。'
    page.get_by_role('button', name='框选模式（可选）', exact=True).click()
    box = page.locator('#mark-surface').bounding_box()
    page.mouse.move(box['x'] + box['width']*.2, box['y'] + box['height']*.2)
    page.mouse.down()
    page.mouse.move(box['x'] + box['width']*.6, box['y'] + box['height']*.6)
    page.mouse.up()
    assert page.locator('.region-overlay').count() == 1
    page.reload()
    page.get_by_role('button', name='标注与意见', exact=True).click()
    assert page.locator('.region-overlay').count() == 1
    page.get_by_role('button', name='加入修改', exact=True).click()
    assert '待交接 · 轮到你' in page.inner_text('body')
    page.goto('http://127.0.0.1:8766/#page/21/image')
    assert page.get_by_text('尚未生成原图', exact=True).count() == 1
    page.goto('http://127.0.0.1:8766/#page/19/prompt')
    assert page.get_by_text('历史未记录执行提示词', exact=True).count() >= 1
    for route in ['projects', 'overview', 'content', 'gallery', 'style', 'runs', 'page/8/image']:
        page.goto('http://127.0.0.1:8766/#'+route)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
    assert not errors, errors
    result = {'scope': 'synthetic interactive prototype only', 'browser': 'Chromium', 'viewport': str(VIEWPORT['width'])+'x'+str(VIEWPORT['height']), 'checks': ['PPT missing 12 slots', 'explicit host claim before result', 'style candidate adoption', 'page-local downstream staleness', 'text and region draft restoration', 'handoff stays queued', 'unknown historic prompt', 'all 7 routes without horizontal overflow'], 'page_errors': errors, 'status': 'passed'}
    Path(__file__).with_name('smoke-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
    browser.close()
