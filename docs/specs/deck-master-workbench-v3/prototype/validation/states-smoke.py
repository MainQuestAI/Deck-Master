"""Synthetic supplementary state flows, not production or Host acceptance."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
URL='http://127.0.0.1:8766/states.html'
result={'scope':'supplementary synthetic state prototype','production_acceptance':False,'host_executed':False,'viewports':[],'limitations':['No service, Host or model calls','Uses isolated localStorage; no cross-origin/server persistence proof','Batch image comparison is explicitly labelled text description, not generated imagery','No production conflict, cancellation, history, export or concurrency verification','System font fallback; bundled font acceptance remains W12']}
with sync_playwright() as p:
    browser=p.chromium.launch()
    for width,height in [(1280,800),(1440,900)]:
        ctx=browser.new_context(viewport={'width':width,'height':height},permissions=['clipboard-read','clipboard-write'])
        page=ctx.new_page();errors=[];external=[];checks=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if not r.url.startswith('http://127.0.0.1:8766/') else None)
        def check(name,condition):
            assert condition,name
            checks.append(name)
        def snap(name):
            check(name+' no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check(name+' primary buttons >=44px',page.locator('main button.primary').evaluate_all('(els)=>els.every(e=>e.getBoundingClientRect().height>=44)'))
            page.locator('#state-feedback').evaluate('(e)=>e.classList.remove("visible")')
            page.screenshot(path=str(HERE/f'states-{name}-{width}.png'),full_page=True)
        def go(scene):
            page.locator(f'[data-scene="{scene}"]').click()
        def act(action):
            page.locator(f'[data-action="{action}"]').first.click()
        def reset():
            page.locator('#reset-sample').click();act('confirm-reset')
        page.goto(URL+'#text')
        check('visible simulation boundary','全部为模拟' in page.inner_text('.state-banner'))
        check('no fake image thumbnail in text-only',page.locator('main img,main svg,main canvas').count()==0)
        page.locator('#text-title').fill('缩短服务响应路径')
        page.locator('#text-body').fill('两个区域先试点。\n用一个入口反馈，保留原始事实。')
        act('save-text');check('saved R17', '正文 R17' in page.inner_text('main'))
        page.reload();check('saved text survives reload',page.locator('#text-title').input_value()=='缩短服务响应路径')
        snap('text')
        act('compare-text');check('fixed old comparison survives reload','把服务流程缩短到三个明确环节' in page.inner_text('#state-dialog'))
        check('dialog named',page.locator('#state-dialog').get_attribute('aria-labelledby')=='dialog-title')
        page.keyboard.press('Escape');check('Escape closes dialog',not page.locator('#state-dialog').is_visible())
        check('dialog returns focus',page.evaluate('document.activeElement.dataset.action')=='compare-text')
        go('unknown');payload=page.locator('.state-grid .state-body').first.inner_text()
        page.locator('#later-draft').fill('后写内容必须保留，增加第三项说明。')
        check('unknown has no replay action',page.locator('[data-action="replay-original"]').count()==0)
        snap('unknown')
        act('check-unknown');check('committed verification keeps later draft',page.locator('#later-draft').input_value()=='后写内容必须保留，增加第三项说明。')
        act('new-later');check('new independent draft', 'sample-draft-42' in page.inner_text('main'))
        check('fixed payload unchanged',page.locator('.state-grid .state-body').first.inner_text()==payload)
        reset();page.locator('#unknown-outcome').select_option('not_committed');act('check-unknown')
        page.locator('#later-draft').fill('重放后也保留的本机草稿');act('replay-original')
        check('verified not-committed replay keeps id and draft', 'sample-op-41' in page.inner_text('main') and page.locator('#later-draft').input_value()=='重放后也保留的本机草稿')
        go('conflict');before=page.locator('.state-grid').inner_text();act('rebase-conflict')
        page.locator('#conflict-new').fill('明确选择两个区域，再补紧急程度分派。')
        page.reload();check('conflict fixed sides preserved after edit and refresh',page.locator('.state-grid').inner_text()==before)
        check('conflict new draft persists',page.locator('#conflict-new').input_value()=='明确选择两个区域，再补紧急程度分派。')
        snap('conflict')
        go('batch');act('compare-batch');act('keep-batch');check('keep old result marked', '第 7 页保留旧结果' in page.inner_text('main'))
        reset();act('compare-batch');act('adopt-batch');check('only page 7 adopted', '只变更第 7 页' in page.inner_text('main'))
        page.locator('#failure-text').fill('第 9 页只减少密度，保留事实与数字。');act('retry-batch')
        check('failed page alone uses new request', 'sample-Q33' in page.inner_text('main') and '成功页不重跑' in page.inner_text('main'))
        act('verify-batch');act('cancel-batch');page.keyboard.press('Escape')
        check('cancel dismiss does not cancel', 'sample-Q31 已取消' not in page.inner_text('main'))
        act('cancel-batch');act('confirm-cancel-batch');act('new-batch-handoff')
        check('timeout verify cancel rehandoff respects late rejection','sample-Q34' in page.inner_text('main') and '晚到结果拒绝采用' in page.inner_text('main'))
        snap('batch')
        go('structure');original=page.locator('.structure-list li').evaluate_all('(els)=>els.map(e=>e.dataset.pageId)')
        page.get_by_role('button',name='下移现状分析',exact=True).focus();page.keyboard.press('Enter')
        moved=page.locator('.structure-list li').evaluate_all('(els)=>els.map(e=>e.dataset.pageId)')
        check('keyboard move keeps stable identity',moved[2]=='p-b2' and sorted(moved)==sorted(original))
        page.get_by_role('button',name='移除交付与衡量',exact=True).click();act('confirm-remove')
        check('remove records historical identity',page.locator('.structure-list li').count()==5 and '移除 p-f6' in page.inner_text('main'))
        page.locator('[data-select-page="p-b2"]').check();page.locator('[data-select-page="p-c3"]').check()
        act('request-structure');act('confirm-request-structure');check('saved request leaves pages unchanged',page.locator('.structure-list li').count()==5)
        act('return-structure');snap('structure-candidate')
        act('adopt-structure');check('impact before adoption','旧意见仍绑定旧页 R18' in page.inner_text('#state-dialog'));act('confirm-adopt-structure')
        check('merge new identity with provenance',page.locator('.structure-list li').count()==4 and 'p-merged-2 ← p-c3, p-b2' in page.inner_text('main') or page.locator('.structure-list li').count()==4 and 'p-merged-2 ← p-b2, p-c3' in page.inner_text('main'))
        check('old annotations remain in history','旧意见未迁移' in page.inner_text('main'))
        page.locator('#structure-mode').select_option('split');page.locator('[data-select-page="p-a1"]').check()
        act('request-structure');act('confirm-request-structure');act('return-structure');act('adopt-structure');act('confirm-adopt-structure')
        check('split new identities with same source',page.locator('[data-page-id="p-split-3-1"]').count()==1 and page.locator('[data-page-id="p-split-3-2"]').count()==1)
        go('history');check('restore unavailable before view',page.locator('[data-action="restore-history"]').count()==0)
        act('view-history');check('view is read-only current R18','当前版本 R18' in page.inner_text('main'))
        act('compare-history');snap('history-compare');act('restore-history');act('confirm-restore')
        check('restoration produces R19 with immutable call facts','当前版本 R19' in page.inner_text('main') and '调用 A7：已完成' in page.inner_text('main') and '调用 A8：取消于 R17' in page.inner_text('main'))
        snap('history-restored')
        check('main prototype localStorage isolated',page.evaluate('Object.keys(localStorage).every(k=>k==="deck-master-state-lab-v1")'))
        check('zero external resource requests',not external)
        check('zero browser errors',not errors)
        result['viewports'].append({'width':width,'height':height,'checks_passed':len(checks),'checks':checks,'page_errors':errors,'external_requests':external})
        ctx.close()
    browser.close()
result['status']='passed'
(HERE/'states-smoke-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'status':'passed','viewports':[(r['width'],r['height'],r['checks_passed']) for r in result['viewports']]},ensure_ascii=False))
