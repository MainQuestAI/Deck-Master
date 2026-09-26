"""Review round follow-up: default simplicity, saved request, annotation and creation."""
from pathlib import Path
import json
import os
VIEWPORT = dict(zip(("width", "height"), map(int, os.environ.get("PROTOTYPE_VIEWPORT", "1440x900").split("x"))))
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch()
    ctx=browser.new_context(viewport=VIEWPORT,permissions=['clipboard-read','clipboard-write'])
    page=ctx.new_page()
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8766/#overview')
    assert page.get_by_role('button',name='看 24 页原图 →',exact=True).is_visible()
    page.screenshot(path='validation/revised-overview-1440.png')
    page.goto('http://127.0.0.1:8766/#style')
    assert not page.locator('.fine-settings').first.evaluate('(e)=>e.open')
    assert not page.locator('[data-dimension="color"]').is_visible()
    page.locator('#style-requirement').fill('保留这页事实，参考第7页的图形风格。')
    page.screenshot(path='validation/revised-style-1440.png')
    page.get_by_role('button',name='先试第 8 页 →',exact=True).click()
    assert '已保存' in page.inner_text('body')
    page.get_by_role('button',name='复制交接文本',exact=True).click()
    page.wait_for_function("document.body.innerText.includes('已复制，尚未开始')")
    page.goto('http://127.0.0.1:8766/#overview')
    page.get_by_role('button',name='继续处理 →',exact=True).click()
    assert '已复制，尚未开始' in page.inner_text('body')
    page.reload()
    assert '已复制，尚未开始' in page.inner_text('body')
    page.screenshot(path='validation/revised-handoff-1440.png')
    page.get_by_role('button',name='模拟 Host 接手',exact=True).click()
    page.get_by_role('button',name='模拟候选返回',exact=True).click()
    assert page.locator('.compare-column-head').count()==2
    assert '当前采用' in page.locator('.compare-column-head').nth(0).inner_text()
    assert '候选' in page.locator('.compare-column-head').nth(1).inner_text()
    page.screenshot(path='validation/revised-candidate-1440.png')
    page.get_by_role('button',name='采用这个候选 · 仅第 8 页',exact=True).click()
    assert '第 9 页还没有执行' in page.inner_text('body')
    page.goto('http://127.0.0.1:8766/#page/8/image')
    page.get_by_role('button',name='标注与意见',exact=True).click()
    page.get_by_role('button',name='框选模式（可选）',exact=True).click()
    page.keyboard.press('Escape')
    assert page.get_by_role('button',name='阅读模式',exact=True).evaluate('(e)=>e.classList.contains("active")')
    count=page.evaluate('state.tasks.length')
    page.locator('#page-note').fill('保持内容，只修正标题对齐。')
    page.get_by_role('button',name='保存意见',exact=True).click()
    assert page.evaluate('state.tasks.length')==count
    assert '意见已保存' in page.locator('#note-save-status').inner_text()
    page.get_by_role('button',name='加入修改',exact=True).click()
    assert page.evaluate('state.tasks.length')==count+1
    page.goto('http://127.0.0.1:8766/#projects')
    page.get_by_role('button',name='新建项目',exact=True).click()
    page.get_by_role('button',name='保存模拟项目',exact=True).click()
    assert page.locator('#project-name-error').inner_text()=='请填写项目名称。'
    assert page.locator('#project-brief-error').inner_text()!=''
    page.get_by_role('button',name='取消',exact=True).click()
    assert page.evaluate('state.projectDrafts.length')==0
    page.get_by_role('button',name='新建项目',exact=True).click()
    page.locator('#project-name').fill('区域服务方案（测试样本）')
    page.locator('#project-brief').fill('帮助区域负责人决定试点范围。')
    page.locator('#project-materials').fill('调研纪要，仅作材料说明演示。')
    page.screenshot(path='validation/revised-new-project-1440.png')
    page.get_by_role('button',name='保存模拟项目',exact=True).click()
    assert '没有逐页稿、原图、SVG 或 PPT' in page.inner_text('#modal')
    page.get_by_role('button',name='保存首轮制作请求（模拟）',exact=True).click()
    assert page.get_by_role('button',name='复制首轮交接文本',exact=True).is_visible()
    page.get_by_role('button',name='关闭',exact=True).click()
    assert page.locator('.draft-project').count()==1
    assert not errors,errors
    result={'scope':'synthetic prototype review revision','viewport':str(VIEWPORT['width'])+'x'+str(VIEWPORT['height']),'status':'passed','page_errors':errors,'checks':['overview gallery primary CTA','simple style default with collapsed details','saved trial request and copied-not-started feedback','return to request from overview and reload','fixed current/candidate columns with request labels','adopt only page 8','Esc cancels selection mode','save opinion creates no task; add change does','empty-name and empty-brief validation','cancel creates no project','simulated new project has no invented artifacts','new project preparation and first handoff request']}
    Path('validation/revision-smoke-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
    browser.close()
