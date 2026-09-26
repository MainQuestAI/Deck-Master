"""Review 2 regressions for new prototype behavior, independently at both desktop sizes."""
from pathlib import Path
import json
import hashlib
import os
import subprocess
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'validation'
URL='http://127.0.0.1:8766/'
results=[]
def act(page,name): page.get_by_role('button',name=name,exact=True).click()
def go(page,route): page.goto(URL+'#'+route)
def focused(page): return page.evaluate('document.activeElement.dataset.action || document.activeElement.id || document.activeElement.tagName')
def shot(page,name,width):
 page.evaluate('window.scrollTo(0,0)')
 path=OUT/f'round2-after-{name}-{width}.png';page.screenshot(path=str(path),full_page=True);return path.name
with sync_playwright() as p:
 browser=p.chromium.launch()
 for width,height in [(1280,800),(1440,900)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},permissions=['clipboard-read','clipboard-write'])
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));evidence=[]
  go(page,'content');act(page,'添加材料或调整要求')
  act(page,'创建影响判断请求')
  assert page.locator('#material-error').inner_text()=='请填写新增材料或调整要求。'
  assert page.evaluate('state.tasks.length')==0
  user_input='请新增面向售后主管的北区上线约束，要求保留2026年10月开始试点。\n保留三层服务网络。'
  page.locator('#material-note').fill(user_input);act(page,'关闭')
  assert focused(page)=='add-material'
  act(page,'添加材料或调整要求');assert page.locator('#material-note').input_value()==user_input
  act(page,'创建影响判断请求');page.reload()
  assert user_input in page.evaluate('state.tasks[0].note')
  act(page,'复制交接文本');page.wait_for_function("state.tasks[0].status==='copied'")
  assert user_input in page.evaluate('navigator.clipboard.readText()')
  evidence.append(shot(page,'material-kept',width))
  # Local option updates retain the selected keyboard control; routing goes to its heading.
  go(page,'gallery');svg=page.get_by_role('button',name='SVG 16/24',exact=True);svg.focus();page.keyboard.press('Enter')
  assert focused(page)=='gallery-stage-svg'
  assert page.get_by_role('button',name='SVG 16/24',exact=True).get_attribute('aria-pressed')=='true'
  page.keyboard.press('Tab');assert focused(page)=='gallery-stage-ppt'
  page.get_by_role('button',name='连续',exact=True).focus();page.keyboard.press('Enter');assert focused(page)=='layout-continuous'
  act(page,'网格');act(page,'4 列')
  assert page.locator('#gallery-grid').get_attribute('data-effective-columns')=='2'
  assert page.locator('.slide-cover').first.bounding_box()['width']>=280
  act(page,'3 列');assert page.locator('#gallery-grid').get_attribute('data-effective-columns')=='3'
  evidence.append(shot(page,'gallery-columns',width))
  act(page,'制作总览');assert focused(page)=='view-title'
  assert '20 页原图可看' in page.locator('.page-head').inner_text()
  assert page.locator('.page-head button.primary').count()==1
  assert page.locator('.matrix [tabindex="0"]').count()==1
  assert all('第 ' in x and any(stage in x for stage in ['原图','SVG','PPT','提示词','逐页稿']) for x in page.locator('.matrix button').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("aria-label"))'))
  page.get_by_role('button',name='全部 24 页',exact=True).focus()
  page.locator('.matrix [tabindex="0"]').focus();page.keyboard.press('ArrowRight');assert page.evaluate('document.activeElement.dataset.matrix')=='1:1'
  page.keyboard.press('ArrowDown');assert page.evaluate('document.activeElement.dataset.matrix')=='2:1'
  page.keyboard.press('Escape');assert focused(page)=='matrix-all'
  page.locator('.matrix [tabindex="0"]').focus();evidence.append(shot(page,'overview-matrix',width));page.keyboard.press('Enter');assert focused(page)=='view-title'
  assert '#page/2/script' in page.url
  assert page.locator('.chain [aria-current="step"]').inner_text().startswith('02')
  go(page,'page/8/image');act(page,'标注与意见');assert focused(page)=='right-note'
  page.locator('.region-controls summary').focus();page.keyboard.press('Enter')
  for name,value in [('X 起点','10'),('Y 起点','20'),('宽度','30'),('高度','40')]: page.get_by_label('选区'+name+'百分比',exact=True).fill(value)
  page.get_by_role('button',name='应用百分比选区',exact=True).focus();page.keyboard.press('Enter')
  assert focused(page)=='apply-region'
  assert page.evaluate('state.regions[noteKey()]')=={'x':.1,'y':.2,'w':.3,'h':.4}
  evidence.append(shot(page,'keyboard-region',width))
  page.reload();act(page,'标注与意见');assert page.locator('.region-overlay').count()==1
  page.locator('#page-note').focus();page.keyboard.press('ArrowRight');assert '#page/8/image' in page.url
  page.locator('#view-title').focus();page.keyboard.press('ArrowRight');assert '#page/9/image' in page.url
  go(page,'page/19/prompt');assert page.get_by_text('历史未记录执行提示词',exact=True).count()==1
  assert page.get_by_role('button',name='执行提示词',exact=True).count()==0
  assert page.get_by_role('button',name='建立新提示词草稿',exact=True).count()<=1
  evidence.append(shot(page,'prompt19-single',width))
  # No-artifact actions create four same-batch, individually identifiable requests.
  go(page,'page/21/image');act(page,'安排本页原图')
  assert '首次原图' in page.locator('#dialog-title').inner_text()
  assert '当前原图继续可看' not in page.locator('#modal').inner_text()
  assert page.get_by_role('dialog').get_attribute('aria-labelledby')=='dialog-title'
  page.keyboard.press('Escape');assert focused(page)=='queue-image-21'
  go(page,'overview');act(page,'安排缺图页');act(page,'为这 4 页保存生成请求')
  assert '4 条同批模拟请求' in page.locator('#modal').inner_text()
  act(page,'加入待交接')
  batch=page.evaluate('state.tasks.filter(t=>t.batchId)')
  assert len(batch)==4 and sorted(t['pages'][0] for t in batch)==[21,22,23,24]
  assert len(set(t['batchId'] for t in batch))==1 and all(len(t['pages'])==1 for t in batch)
  row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 21 页首次生成原图',exact=True))
  row.get_by_role('button',name='模拟接手',exact=True).click();row.get_by_role('button',name='模拟返回候选',exact=True).click();row.get_by_role('button',name='查看候选并比较',exact=True).click()
  assert page.locator('#modal [data-artifact-ref="p21/image/v1"]').count()==1
  assert page.locator('#modal [data-artifact-ref^="p22/"]').count()==0
  act(page,'采用这个样本候选');go(page,'page/21/image')
  assert page.locator('#mark-surface [data-artifact-ref="p21/image/v1"]').count()==1
  assert page.locator('#main').get_by_text('尚未生成原图',exact=True).count()==0
  page.reload();assert page.locator('#mark-surface [data-artifact-ref="p21/image/v1"]').count()==1
  act(page,'提示词草稿');act(page,'检查影响并重新生成原图');assert '当前原图继续可看' in page.locator('#modal').inner_text();page.keyboard.press('Escape')
  evidence.append(shot(page,'first-image-adopted',width))
  go(page,'style');act(page,'先试第 8 页 →');act(page,'模拟 Host 接手');act(page,'模拟候选返回')
  assert page.locator('.style-layout.comparison-active').count()==1
  canvases=page.locator('.candidate-compare svg');sizes=[canvases.nth(i).bounding_box()['width'] for i in range(2)]
  assert min(sizes)>440, sizes
  facts=page.locator('.style-settings').bounding_box();main=page.locator('.style-main').bounding_box();assert facts['y']>=main['y']+main['height']-1
  evidence.append(shot(page,'candidate-wide',width))
  for label,ref in [('放大当前请求基准原图','p08/image/v2'),('放大本次候选原图','p08/image/v3')]:
   act(page,label);assert page.locator('#modal [data-artifact-ref="'+ref+'"]').count()==1
   assert page.locator('#modal svg').bounding_box()['width']>900
   page.keyboard.press('Tab');assert page.evaluate("document.activeElement.closest('dialog') !== null")
   page.keyboard.press('Escape');assert page.get_by_role('button',name=label,exact=True).evaluate('(e)=>e===document.activeElement')
  page.locator('.reference-detail summary').click();act(page,'放大第 7 页固定参考原图')
  assert page.locator('#modal [data-artifact-ref="p07/image/v2"]').count()==1
  evidence.append(shot(page,'reference-enlarged',width));page.keyboard.press('Escape')
  go(page,'overview');assert page.locator('.handoff-banner .primary').count()==0
  assert page.get_by_role('button',name='安排缺图页',exact=True).is_visible()
  # New semantic classes keep outcome text; measurements cover accepted CSS adjustments.
  go(page,'runs')
  adopted_row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 21 页首次生成原图',exact=True))
  assert adopted_row.locator('.status.ok').inner_text()=='已采用 · 待制作检查'
  running_row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 22 页首次生成原图',exact=True))
  assert '待交接' in running_row.locator('.status.warn').inner_text()
  running_row.get_by_role('button',name='模拟接手',exact=True).click()
  assert '处理中' in running_row.locator('.status.info').inner_text()
  running_row.get_by_role('button',name='模拟失败',exact=True).click()
  assert '失败' in running_row.locator('.status.error').inner_text()
  cancelled_row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 23 页首次生成原图',exact=True))
  cancelled_row.get_by_role('button',name='取消任务',exact=True).click()
  assert cancelled_row.locator('.status').get_attribute('class').strip()=='status'
  style_row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 8 页风格试做',exact=True))
  assert '候选已返回' in style_row.locator('.status.warn').inner_text()
  go(page,'style');act(page,'保留当前');go(page,'runs')
  style_row=page.locator('.run-item').filter(has=page.get_by_role('heading',name='第 8 页风格试做',exact=True))
  assert style_row.locator('.status').get_attribute('class').strip()=='status'
  evidence.append(shot(page,'semantic-states',width))
  go(page,'overview')
  primary_h=page.get_by_role('button',name='看 24 页原图 →',exact=True).bounding_box()['height'];assert primary_h>=44
  go(page,'page/8/image');act(page,'执行提示词')
  assert page.locator('.prompt-block p').first.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')>=16
  assert page.locator('.chain-state').first.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')>=12
  for route in ['projects','overview','content','gallery','style','runs','page/8/image']:
   go(page,route);assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),route
  assert not errors,errors
  results.append({'viewport':f'{width}x{height}','status':'passed','page_errors':errors,'candidate_width_px':sizes,'primary_height_px':primary_h,'evidence':evidence})
  ctx.close()
 browser.close()
# Preserve each existing suite's individual output and result rather than infer broad coverage.
regressions=[]
for viewport in ['1280x800','1440x900']:
 for script in ['smoke.py','revision-smoke.py']:
  completed=subprocess.run(['python3',str(OUT/script)],cwd=ROOT,env={**os.environ,'PROTOTYPE_VIEWPORT':viewport},check=True,capture_output=True,text=True)
  regressions.append({'script':script,**json.loads(completed.stdout.strip().splitlines()[-1])})
completed=subprocess.run(['python3',str(OUT/'round1-fixes.py')],cwd=ROOT,check=True,capture_output=True,text=True)
regressions.append({'script':'round1-fixes.py',**json.loads(completed.stdout.strip().splitlines()[-1])})
result={'scope':'Review 2 accepted changes in the synthetic prototype only; no production acceptance','status':'passed','browser':'Chromium','results':results,'existing_regressions':regressions,'before_evidence':'../reviews/round2-native-evidence/ (frozen Review 2 screenshots)','source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app.js','index.html','style.css']},'checks':['R2-01 custom material input retained through close, request, reload and clipboard; blank rejected','R2-02 local focus retained, real navigation to heading, named modal with return focus','R2-03 one matrix Tab stop with arrow/Enter/Esc, page-layer labels and keyboard region fields','R2-04 single missing-page action and four individually compared same-batch first-image requests; adopted image persists','R2-05 full-width comparison, fixed base/candidate/reference enlargement and gallery 2/3/4 selection with minimum width fallback','R2-06 factual overview, single high-weight CTA, explicit to-do labels and matrix thumbnails','R2-07 one P19 missing history panel without duplicate execution prompt sidebar','R2-08 primary targets >=44px, chain metadata >=12px, prompt text >=16px','R2-09 distinct semantic state classes retaining text']}
(OUT/'round2-fixes-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
