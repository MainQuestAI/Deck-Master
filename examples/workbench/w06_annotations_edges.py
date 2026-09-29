"""W06 geometry, tiny coordinate digest, conflict and cross-origin recovery proof.

Only synthetic material is used. Network failures are explicit browser route
injections. Services are stopped by this script; no real model is invoked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from playwright.sync_api import expect, sync_playwright

from deck_master import annotation_service, editing, samples
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True); args = parser.parse_args()
    root = Path(args.out).resolve(); root.mkdir(parents=True, exist_ok=False)
    local = root / 'local-only'; local.mkdir(); project = root / 'synthetic-project'
    samples.create_gallery_sample(project, readonly=False); store = Store(project); first = store.load_document()
    annotation_service.save(project, input={'schema_version': 'annotation_batch.v1', 'project_id': first['project_id'], 'annotations': [{
        'schema_version': 'annotation.v1', 'project_id': first['project_id'], 'base_revision': first['revision_id'],
        'scope': 'page', 'page_id': 'p02', 'page_ref': first['pages'][1]['page'], 'intent': 'fixture', 'body': '明确标记的合成初始化意见', 'status': 'open', 'location': {'kind': 'whole'}}]},
        base_revision=first['revision_id'], operation_id=str(uuid.uuid4()))
    checks = []
    def check(name, condition=True):
        assert condition, name
        checks.append({'name': name, 'status': 'pass'})
    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(); context = browser.new_context(viewport={'width': 1440, 'height': 1080}, accept_downloads=True)
            tab = context.new_page(); errors = []; tab.on('pageerror', lambda error: errors.append(str(error)))
            def click(name):
                tab.get_by_role('button', name=name, exact=True).click()
                if name in ('逐页稿', '原图', 'SVG', 'PPT', '预备提示词', '实际提示词'):
                    expect(tab.get_by_role('navigation', name='页面层').get_by_role('button', name=name, exact=True)).to_have_attribute('aria-current', 'page')
            def write(value): tab.get_by_role('textbox', name='个人草稿', exact=True).fill(value)
            def records(): return tab.evaluate("async()=> (await(await fetch('/api/annotations')).json()).annotations")
            def saved(n): expect(tab.get_by_role('checkbox', name=f'选入意见 {n}', exact=True)).to_be_visible(timeout=15000)
            tab.goto(url + '/v2/'); tab.get_by_role('button', name='第 2 页', exact=False).first.click(); click('SVG')
            expect(tab.locator('.annotation-overlay')).to_be_attached()
            click('比较此页版本'); tab.get_by_role('combobox', name='选择同页比较版本').select_option(first['revision_id']); click('固定比较这个版本')
            expect(tab.locator('.fixed-page-pair')).to_have_class('fixed-page-pair is-comparing')
            canvas = tab.locator('[aria-label="页面内容"] canvas.page-image')
            canvas.scroll_into_view_if_needed()
            # Measure independently from imageRect's implementation.
            box = canvas.bounding_box(); dimensions = canvas.evaluate('(c)=>[c.width,c.height]')
            scale = min(box['width'] / dimensions[0], box['height'] / dimensions[1]); width = dimensions[0] * scale; height = dimensions[1] * scale
            left = box['x'] + (box['width'] - width) / 2; top = box['y'] + (box['height'] - height) / 2
            check('real-comparison-canvas-has-letterbox', box['height'] - height > 10 or box['width'] - width > 10)
            click('点标注'); canvas.scroll_into_view_if_needed()
            # Recompute after tool controls scroll the document.
            box = canvas.bounding_box(); left = box['x'] + (box['width'] - width) / 2; top = box['y'] + (box['height'] - height) / 2
            tab.mouse.click(box['x'] + 2, box['y'] + 2)
            check('letterbox-click-does-not-create-region', not tab.locator('.annotation-region').count())
            tab.mouse.click(left + width * .25, top + height * .75)
            expect(tab.locator('.annotation-region')).to_have_count(1)
            write('SVG 原画布区域'); click('保存意见'); saved(2)
            loc = records()[-1]['annotation']['location']
            check('svg-viewbox-and-letterbox-normalized-coordinate', loc['canvas'] == {'width': 960, 'height': 540} and abs(loc['x'] - .25) < .005 and abs(loc['y'] - .75) < .005)
            click('删除区域 1'); click('框选'); canvas.scroll_into_view_if_needed()
            box = canvas.bounding_box(); left = box['x'] + (box['width'] - width) / 2; top = box['y'] + (box['height'] - height) / 2
            tab.mouse.move(left + width * .2, top + height * .2); tab.mouse.down(); tab.mouse.move(left + width * .4, top + height * .4); tab.mouse.up()
            expect(tab.locator('.annotation-region')).to_have_count(1); click('删除区域 1')
            tab.get_by_text('用百分比定位区域', exact=True).click()
            tab.get_by_label('横向起点 %', exact=True).fill('0.001'); click('添加百分比区域')
            write('极小百分比仍可核实与恢复'); click('保存意见'); saved(3)
            check('tiny-fraction-canonical-digest-matches-python', abs(records()[-1]['annotation']['location']['x'] - .00001) < 1e-12)
            expect(tab.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            with tab.expect_download() as event: click('下载草稿恢复文件')
            recovery = local / 'geometry-recovery.json'; event.value.save_as(recovery)
            check('coordinate-recovery-file-preserves-raw-normalized-range', json.loads(recovery.read_text())['draft']['content']['annotation']['regions'][0]['x'] == .00001)
            tab.screenshot(path=str(root / 'svg-letterbox.png'), full_page=True)
            click('结束固定比较'); click('逐页稿'); click('整页意见'); write('计划正文改为清楚的判断。'); click('保存意见'); saved(4)
            tab.get_by_role('checkbox', name='选入意见 4', exact=True).check(); click('加入修改计划')
            expect(tab.get_by_role('button', name='确认计划并创建交接')).to_be_visible()
            # Simulate an independent current-content change after impact preview.
            doc = store.load_document(); entry = doc['pages'][1]; page = store.read_object_json(entry['page']); page['customer_visible']['title'] = '另一窗口的新标题'
            editing.edit_page(project, page=page, base_revision=doc['revision_id'], page_hash=entry['page']['sha256'], operation_id='synthetic-independent-change')
            before = store.current_revision_id(); click('确认计划并创建交接')
            expect(tab.get_by_role('dialog')).to_contain_text('本次未提交，输入已保留')
            check('stale-plan-conflict-keeps-both-bases-and-creates-no-task', store.current_revision_id() == before and not store.load_document().get('changes'))
            expect(tab.get_by_role('textbox', name='未提交的本机草稿')).to_have_value('计划正文改为清楚的判断。'); click('关闭')
            # Pending copied to project journal survives a real service restart and
            # different origin. Query timeout never authorizes a new operation.
            click('原图'); click('查看当前版本')
            expect(tab.get_by_role('heading', name='第 2 页 · 另一窗口的新标题', exact=True)).to_be_visible()
            click('整页意见'); tab.get_by_role('combobox', name='意见作用范围').select_option('page'); write('跨端口原请求')
            requests = []
            def absent(route): requests.append(route.request.post_data_json); route.abort('failed')
            tab.route('**/api/annotations/batch', absent); click('保存意见')
            pending = tab.get_by_role('region', name='待核实的业务保存'); expect(pending).to_contain_text('尚未确认保存结果')
            write('跨端口后写草稿'); expect(tab.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            route_hash = tab.url.split('#', 1)[1]
            server.stop(); replacement = WorkbenchServer(project); new_url = replacement.start().rstrip('/'); server = replacement
            assert url != new_url
            second = context.new_page(); second.goto(new_url + '/v2/#' + route_hash)
            expect(second.get_by_role('region', name='待核实的业务保存')).to_be_visible()
            expect(second.get_by_role('textbox', name='个人草稿', exact=True)).to_have_value('跨端口后写草稿')
            check('project-ack-pending-and-late-draft-survive-port-change')
            second.route('**/api/operations/*', lambda route: route.abort('failed'))
            second.get_by_role('button', name='核实保存结果', exact=True).click()
            expect(second.get_by_role('region', name='待核实的业务保存')).to_contain_text('核实未完成')
            check('query-timeout-does-not-change-id-or-enable-new-save', len(requests) == 1 and second.get_by_role('button', name='保存意见', exact=True).is_disabled())
            second.unroute('**/api/operations/*'); second.get_by_role('button', name='核实保存结果', exact=True).click()
            expect(second.get_by_role('button', name='重放已保存的原请求')).to_be_visible()
            second.get_by_role('button', name='重放已保存的原请求').click()
            expect(second.get_by_role('region', name='待核实的业务保存')).not_to_be_visible()
            check('cross-origin-replay-remains-original-request', annotation_service.list_annotations(project)['annotations'][-1]['annotation']['body'] == '跨端口原请求')
            # Unacknowledged pending data is origin-local until explicitly exported/imported.
            second.get_by_role('button', name='整页意见', exact=True).click()
            second.get_by_role('textbox', name='个人草稿', exact=True).fill('只在本机冻结的请求')
            expect(second.locator('.draft-state')).to_have_text('已保存到项目，可跨端口恢复')
            second.route('**/api/drafts/save', lambda route: route.abort('failed'))
            second.route('**/api/annotations/batch', lambda route: route.abort('failed'))
            second.get_by_role('button', name='保存意见', exact=True).click()
            expect(second.get_by_role('region', name='待核实的业务保存')).to_contain_text('尚未确认保存结果')
            second.get_by_role('textbox', name='个人草稿', exact=True).fill('尚未同步的后写内容')
            with second.expect_download() as download:
                second.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            pending_file = local / 'unacknowledged-pending-recovery.json'; download.value.save_as(pending_file)
            frozen = json.loads(pending_file.read_text())['draft']['pending']
            check('unacknowledged-recovery-contains-frozen-request-and-late-text', bool(frozen) and json.loads(pending_file.read_text())['draft']['content']['text'] == '尚未同步的后写内容')
            server.stop(); replacement = WorkbenchServer(project); third_url = replacement.start().rstrip('/'); server = replacement
            assert third_url not in (url, new_url)
            third = context.new_page(); third.goto(third_url + '/v2/#' + route_hash)
            expect(third.get_by_role('region', name='待核实的业务保存')).not_to_be_visible()
            expect(third.get_by_role('textbox', name='个人草稿', exact=True)).not_to_have_value('尚未同步的后写内容')
            check('unacknowledged-origin-buffer-is-not-claimed-cross-port')
            third.get_by_label('导入草稿恢复文件', exact=True).set_input_files(str(pending_file))
            expect(third.get_by_role('region', name='待核实的业务保存')).to_be_visible()
            expect(third.get_by_role('textbox', name='个人草稿', exact=True)).to_have_value('尚未同步的后写内容')
            third.get_by_role('button', name='核实保存结果', exact=True).click()
            expect(third.get_by_role('button', name='重放已保存的原请求')).to_be_visible()
            third.get_by_role('button', name='重放已保存的原请求').click()
            expect(third.get_by_role('region', name='待核实的业务保存')).not_to_be_visible()
            check('explicit-recovery-import-replays-original-business-payload', annotation_service.list_annotations(project)['annotations'][-1]['annotation']['body'] == '只在本机冻结的请求')
            second = third
            # The standalone geometry recovery digest remains importable across origins.
            second.get_by_role('button', name='SVG', exact=True).click()
            second.get_by_label('导入草稿恢复文件', exact=True).set_input_files(str(recovery))
            expect(second.locator('#toast')).to_contain_text('已导入项目')
            check('tiny-coordinate-recovery-file-imports-across-origin')
            check('no-uncaught-browser-errors', not errors)
            browser_version = browser.version; browser.close()
    finally: server.stop()
    (root / 'checks.json').write_text(json.dumps({'status': 'verified', 'evidence': 'real browser with synthetic project and injected faults', 'browser': browser_version, 'checks': checks}, ensure_ascii=False, indent=2))
    print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}))


if __name__ == '__main__': main()
