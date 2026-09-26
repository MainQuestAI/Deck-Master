from pathlib import Path
from playwright.sync_api import sync_playwright
import json
out=Path('/Users/dingcheng/Deck-Master-workbench-spec/docs/specs/deck-master-workbench-v3/reviews/round2-native-evidence')
res=[]
with sync_playwright() as p:
 b=p.chromium.launch()
 for w,h in [(1440,900),(1280,800)]:
  c=b.new_context(viewport={'width':w,'height':h},permissions=['clipboard-read','clipboard-write']);pg=c.new_page();errors=[];pg.on('pageerror',lambda e:errors.append(str(e)))
  def go(r):pg.goto('http://127.0.0.1:8766/#'+r)
  def act(n):pg.get_by_role('button',name=n,exact=True).first.click()
  def shot(n):pg.screenshot(path=str(out/f'{n}-{w}.png'),full_page=True)
  go('style');act('先试第 8 页 →');act('复制交接文本');pg.wait_for_function("currentStyleTask().status==='copied'")
  act('模拟 Host 接手');act('模拟候选返回');shot('style-returned');act('保留当前');assert '已决定保留当前' in pg.inner_text('body');act('调整要求再试');pg.locator('#style-requirement').fill('只更新色板，保留标题与结构。');act('保存第 8 页的新请求 →');shot('style-retry');assert pg.evaluate('state.tasks.length')==2
  go('page/12/svg');act('标注与意见');pg.locator('#page-note').fill('诊断到处理的箭头应朝右，保持原图。');act('保存意见');act('仅重建 SVG');act('加入待交接');act('模拟接手');act('模拟返回候选');act('查看候选并比较');shot('svg-candidate')
  modal_open=pg.locator('#modal').evaluate('(e)=>e.open');focus_initial=pg.evaluate('document.activeElement.textContent')
  for _ in range(6):pg.keyboard.press('Tab')
  focus_inside=pg.evaluate("!!document.activeElement.closest('#modal')")
  pg.keyboard.press('Escape');assert not pg.locator('#modal').evaluate('(e)=>e.open')
  focus_after=pg.evaluate('({tag:document.activeElement.tagName,text:document.activeElement.textContent?.slice(0,50)})')
  go('projects');act('新建项目');act('保存模拟项目');assert '请填写项目名称' in pg.inner_text('body');shot('project-invalid');pg.keyboard.press('Escape')
  go('overview');matrix=pg.locator('.matrix button').count();pg.locator('.matrix button').first.focus();pg.keyboard.press('ArrowRight');matrix_right=pg.evaluate('({tag:document.activeElement.tagName,text:document.activeElement.textContent})');pg.keyboard.press('Tab');matrix_tab=pg.evaluate('({tag:document.activeElement.tagName,text:document.activeElement.textContent})');shot('matrix-keyboard')
  go('gallery');pg.get_by_role('button',name='SVG 16/24',exact=True).focus();pg.keyboard.press('Enter');focus_after_layer=pg.evaluate('({tag:document.activeElement.tagName,text:document.activeElement.textContent.slice(0,40)})');pg.keyboard.press('Tab');focus_tab_layer=pg.evaluate('({tag:document.activeElement.tagName,text:document.activeElement.textContent.slice(0,40)})');shot('gallery-focus-reset')
  go('content');print('material_buttons',[x for x in pg.get_by_role('button').all_text_contents() if '材料' in x])
  act('添加材料或调整要求');pg.locator('#material-note').fill('请新增面向售后主管的北区上线约束，要求保留 2026 年 10 月开始试点。');shot('material-before');act('创建影响判断请求');shot('material-after');latest=pg.evaluate('JSON.parse(JSON.stringify(state.tasks[0]))');act('复制交接文本');pg.wait_for_timeout(50);copied=pg.evaluate('navigator.clipboard.readText()')
  res.append({'viewport':[w,h],'styleRetryTasks':2,'svgCandidateModalOpen':modal_open,'modalInitialFocus':focus_initial,'focusInsideAfterSixTabs':focus_inside,'focusAfterEscape':focus_after,'matrixButtons':matrix,'matrixRight':matrix_right,'matrixTab':matrix_tab,'galleryFocusAfterChange':focus_after_layer,'galleryFocusAfterTab':focus_tab_layer,'materialTask':latest,'materialClipboard':copied,'errors':errors})
  c.close()
 b.close()
(out/'flows.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps(res,ensure_ascii=False,indent=2))
