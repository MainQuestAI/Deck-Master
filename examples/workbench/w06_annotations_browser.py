"""Real browser W06 UI proof over a synthetic project; no model invocation.

Fault interception is explicitly simulated. --wait-for-host leaves the browser
open for an external, real CLI Host to read and claim the generated handoff.
It never impersonates that Host. Raw requests/project paths stay local-only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform

from playwright.sync_api import expect, sync_playwright

from deck_master import editing, samples
from deck_master.models import content_identity
from deck_master.store import Store
from deck_master.web import WorkbenchServer

TEXT = 'A🙂e\u0301\r\n中\n重复摘录🙂'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--wait-for-host', action='store_true')
    args = parser.parse_args()
    root = Path(args.out).expanduser().resolve(); root.mkdir(parents=True, exist_ok=False)
    raw = root / 'local-only'; raw.mkdir()
    project = root / 'synthetic-project'; samples.create_gallery_sample(project, readonly=False)
    store = Store(project); initial = store.load_document(); first = store.read_object_json(initial['pages'][0]['page'])
    first['customer_visible']['subtitle'] = TEXT
    editing.edit_page(project, page=first, base_revision=initial['revision_id'], page_hash=initial['pages'][0]['page']['sha256'], operation_id='synthetic-unicode-setup')
    baseline = store.load_document(); identity = content_identity(baseline); checks = []

    def check(name, condition=True):
        assert condition, name
        checks.append({'name': name, 'status': 'pass'})

    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1080}, permissions=['clipboard-read', 'clipboard-write'])
            tab = context.new_page(); errors = []; tab.on('pageerror', lambda error: errors.append(str(error)))
            def click(name):
                tab.get_by_role('button', name=name, exact=True).click()
                if name in ('逐页稿', '原图', 'SVG', 'PPT', '预备提示词', '实际提示词'):
                    expect(tab.get_by_role('navigation', name='页面层').get_by_role('button', name=name, exact=True)).to_have_attribute('aria-current', 'page')
            def notes(): return tab.evaluate("async()=> (await(await fetch('/api/annotations')).json()).annotations")
            def write(text): tab.get_by_role('textbox', name='个人草稿', exact=True).fill(text)
            def saved(count): expect(tab.get_by_role('checkbox', name=f'选入意见 {count}', exact=True)).to_be_visible(timeout=15000)
            def draft_saved(): expect(tab.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            tab.goto(url + '/v2/')
            tab.get_by_role('button', name='第 1 页', exact=False).first.click()
            expect(tab.locator('.annotation-overlay')).to_be_attached()
            canvas = tab.locator('[aria-label="页面内容"] canvas.page-image')
            box = canvas.bounding_box(); tab.mouse.move(box['x'] + 10, box['y'] + 10); tab.mouse.down(); tab.mouse.move(box['x'] + 60, box['y'] + 60); tab.mouse.up()
            check('default-reading-drag-creates-no-opinion', not tab.locator('.annotation-region').count() and not notes())
            # In-place zoom and scrolling use coordinates of the contained image.
            tab.get_by_role('combobox', name='阅读缩放').select_option('2')
            tab.locator('.page-image-viewport').evaluate('(node)=>{node.scrollLeft=180;node.scrollTop=80}')
            click('点标注'); expect(tab.get_by_role('combobox', name='阅读缩放')).to_be_disabled()
            overlay = tab.locator('.annotation-overlay'); overlay.click(position={'x': 300, 'y': 180})
            expected = overlay.bounding_box(); x = 300 / expected['width']; y = 180 / expected['height']
            check('explicit-point-mode-locks-zoom', tab.locator('.annotation-region').count() == 1)
            click('框选'); tab.get_by_text('用百分比定位区域', exact=True).click()
            tab.get_by_label('横向起点 %', exact=True).fill('90'); click('添加百分比区域')
            expect(tab.locator('.annotations-panel .field-error').last).to_contain_text('百分比范围')
            check('out-of-bounds-keyboard-range-keeps-input', tab.get_by_label('横向起点 %', exact=True).input_value() == '90')
            tab.get_by_label('横向起点 %', exact=True).fill('10'); click('添加百分比区域')
            write('明确两处位置的布局。'); click('保存意见'); saved(2)
            recorded = notes()
            check('zoom-scroll-coordinate-is-original-normalized', abs(recorded[0]['annotation']['location']['x'] - x) < .005 and abs(recorded[0]['annotation']['location']['y'] - y) < .005)
            check('multi-regions-save-as-separate-version-bound-opinions', len(recorded) == 2 and recorded[1]['annotation']['location'] == {'kind': 'rect', 'canvas': {'width': 960, 'height': 540}, 'x': .1, 'y': .1, 'width': .2, 'height': .2})
            check('saving-opinions-does-not-create-tasks-or-change-content', store.load_document()['tasks'] == baseline['tasks'] and content_identity(store.load_document()) == identity)
            click('删除区域 2'); check('rectangle-can-be-deleted', tab.locator('.annotation-region').count() == 1)
            tab.get_by_role('button', name='框选', exact=True).focus(); tab.keyboard.press('Escape')
            check('escape-cancels-last-unsaved-range-and-keeps-page', not tab.locator('.annotation-region').count() and '/v2/' in tab.url and 'surface=page' in tab.url)
            # New current revisions never relabel the opinion's original basis.
            prior = tab.locator('.page-workbench').element_handle()
            click('回到意见 1 的原版本'); prior.wait_for_element_state('hidden')
            expect(tab.locator('.page-workbench')).to_be_visible()
            check('opinion-link-returns-fixed-original-version', recorded[0]['annotation']['base_revision'] in tab.url)
            # Page, chapter and project whole opinions share the same atomic service.
            click('整页意见')
            for scope, count in [('page', 3), ('chapter', 4), ('project', 5)]:
                tab.get_by_role('combobox', name='意见作用范围').select_option(scope); write('整页意见 ' + scope); click('保存意见'); saved(count)
            check('whole-scope-conditional-identities', [r['annotation']['scope'] for r in notes()[-3:]] == ['page', 'chapter', 'project'])
            # A dropped ACK must retain the original request independently of late text.
            sent = []
            def drop_ack(route):
                sent.append(route.request.post_data_json); response = route.fetch(); assert response.ok; route.abort('failed')
            tab.route('**/api/annotations/batch', drop_ack)
            write('原请求的意见'); click('保存意见')
            pending = tab.get_by_role('region', name='待核实的业务保存')
            expect(pending).to_contain_text('尚未确认保存结果'); write('后写草稿，不能替换原请求')
            expect(tab.get_by_role('button', name='保存意见', exact=True)).to_be_disabled()
            check('unknown-response-globally-pauses-new-business-save')
            draft_saved(); tab.reload(); expect(pending).to_be_visible()
            click('核实保存结果'); expect(pending).not_to_be_visible(); saved(6)
            expect(tab.get_by_role('textbox', name='个人草稿', exact=True)).to_have_value('后写草稿，不能替换原请求')
            check('reload-recovery-queries-original-commit-and-keeps-later-draft', notes()[-1]['annotation']['body'] == '原请求的意见')
            tab.unroute('**/api/annotations/batch', drop_ack)
            # No server request: query 404 permits only the persisted exact replay.
            absent_requests = []
            def absent(route): absent_requests.append(route.request.post_data_json); route.abort('failed')
            tab.route('**/api/annotations/batch', absent); click('整页意见'); write('未送达的原内容'); click('保存意见')
            expect(pending).to_contain_text('尚未确认保存结果'); write('第三版个人草稿'); click('核实保存结果')
            expect(tab.get_by_role('button', name='重放已保存的原请求')).to_be_visible()
            tab.unroute('**/api/annotations/batch', absent)
            replayed = []
            def observe(route): replayed.append(route.request.post_data_json); route.continue_()
            tab.route('**/api/annotations/batch', observe); click('重放已保存的原请求'); saved(7)
            tab.unroute('**/api/annotations/batch', observe)
            check('not-found-replay-retains-original-id-payload', replayed == absent_requests and notes()[-1]['annotation']['body'] == '未送达的原内容')
            expect(tab.get_by_role('textbox', name='个人草稿', exact=True)).to_have_value('第三版个人草稿')
            check('later-draft-is-not-sent-by-replay')
            (raw / 'fault-requests.json').write_text(json.dumps({'lost_ack': sent, 'not_found': absent_requests, 'replay': replayed}, ensure_ascii=False, indent=2))
            # Unicode selection uses the original stored string, not textarea normalization.
            click('逐页稿'); click('文本意见')
            tab.get_by_text('正文原文与精确选段', exact=True).click()
            select = tab.get_by_role('combobox', name='选择原文文本对象'); select.select_option(index=1)
            tab.get_by_text('定位原文选段', exact=True).click()
            tab.get_by_label('选段起点', exact=True).fill('1'); tab.get_by_label('选段终点', exact=True).fill('7'); click('校验原文选段')
            expect(tab.locator('.annotation-region')).to_have_count(1)
            write('保留组合字和原换行，只改表述。'); click('保存意见'); saved(8)
            text_note = notes()[-1]['annotation']
            check('unicode-codepoint-emoji-combining-crlf-preserved', text_note['location']['range']['excerpt'] == ''.join(list(TEXT)[1:7]))
            tab.get_by_role('checkbox', name='选入意见 8', exact=True).check()
            before_plan = store.current_revision_id(); click('加入修改计划')
            expect(tab.get_by_role('button', name='确认计划并创建交接')).to_be_visible()
            check('plan-preview-is-read-only-and-precise', store.current_revision_id() == before_plan and '最多 0 次' in tab.locator('.change-plan-preview').inner_text() and '逐页稿' in tab.locator('.change-plan-preview').inner_text())
            write('把本页副标题改成：使用明确的证据说明判断。')
            expect(tab.get_by_role('button', name='确认计划并创建交接')).not_to_be_visible()
            check('changed-payload-invalidates-preview-before-commit')
            click('加入修改计划'); click('确认计划并创建交接')
            handoff = tab.get_by_role('region', name='持久修改交接'); expect(handoff).to_contain_text('待交接 · 尚未开始')
            payload = tab.evaluate("async()=> {const c=await(await fetch('/api/changes')).json();return await(await fetch('/api/changes/'+c.changes.at(-1).change_id+'/handoff')).json()}")
            check('commit-creates-unclaimed-durable-handoff', payload['status'] == 'awaiting_host' and payload['handoff']['tasks'][0]['execution_ref'] is None)
            # Explicit clipboard denial must show manual text without a copied claim.
            tab.evaluate("()=>{window.originalClipboardWrite = navigator.clipboard.writeText.bind(navigator.clipboard); navigator.clipboard.writeText=()=>Promise.reject(new Error('synthetic denied'));}")
            click('复制交接说明'); expect(tab.get_by_role('textbox', name='手动复制交接说明')).to_have_value(payload['text'])
            check('clipboard-failure-keeps-complete-manual-handoff'); click('关闭')
            tab.evaluate('()=>{navigator.clipboard.writeText=window.originalClipboardWrite;}'); click('复制交接说明')
            expect(handoff).to_contain_text('已复制、未接手')
            check('successful-copy-does-not-start-host', store.load_document()['tasks'] and tab.evaluate('async()=>await navigator.clipboard.readText()') == payload['text'])
            click('制作总览'); click('任务与交付'); expect(handoff).to_contain_text('已复制、未接手')
            check('handoff-survives-navigation-and-returns-from-runs')
            tab.screenshot(path=str(root / 'handoff-unclaimed.png'), full_page=True)
            (raw / 'host-handoff.json').write_text(json.dumps({'project': str(project), 'url': url, 'handoff': payload}, ensure_ascii=False, indent=2))
            if args.wait_for_host:
                print(json.dumps({'phase': 'awaiting-real-host', 'handoff_file': str(raw / 'host-handoff.json')}), flush=True)
                expect(handoff).to_contain_text('已接手 · 处理中', timeout=240000)
                started = tab.evaluate("async()=> {const c=await(await fetch('/api/changes')).json();return await(await fetch('/api/changes/'+c.changes.at(-1).change_id+'/handoff')).json()}")
                check('external-cli-host-claim-refreshes-real-execution-reference', bool(started['handoff']['tasks'][0]['execution_ref']))
                (raw / 'host-started.json').write_text(json.dumps(started, ensure_ascii=False, indent=2))
                tab.screenshot(path=str(root / 'handoff-claimed.png'), full_page=True)
            click('取消这项任务'); expect(handoff).to_contain_text('取消已确认')
            check('cancel-is-displayed-only-after-service-confirmation')
            check('no-uncaught-browser-errors', not errors)
            browser_version = browser.version; browser.close()
    finally:
        server.stop()
    report = {'status': 'verified', 'evidence': 'synthetic project, actual Chromium UI and same-origin HTTP; network/clipboard faults explicitly injected',
              'real_host_wait': args.wait_for_host, 'browser': browser_version, 'python': platform.python_version(), 'checks': checks,
              'residuals': ['Actual model calls and professional quality acceptance are not implied by UI or Host claim.']}
    (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}))


if __name__ == '__main__':
    main()
