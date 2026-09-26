"""Real Chromium proof for W03; isolated synthetic projects, no HOME or models.

Run with PYTHONPATH=src python examples/workbench/w03_browser.py --out <new-dir>.
The JSON report and screenshots are shareable; raw traces stay local because
network traces can contain session headers and selected local paths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import re
import time

from playwright.sync_api import expect, sync_playwright

from deck_master import editing, local_runtime as runtime, registry, samples, ui_journal
from deck_master.models import content_identity
from deck_master.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(args.out).absolute()
    root.mkdir(parents=True, exist_ok=False)
    shots = root / 'screenshots'
    shots.mkdir()
    config = root / 'registry' / 'projects.json'
    project = root / 'one' / 'project'
    other = root / 'two' / 'project'
    samples.create_sample(project, readonly=False)
    samples.create_sample(other, readonly=False)
    registered = registry.register(config, project)
    registry.register(config, other)
    store = Store(project)
    first_revision = store.current_revision_id()
    first_business = (store.read_current(), content_identity(store.load_document()))
    checks = {}
    errors = []
    descriptors = [runtime.descriptor(registry=config), runtime.descriptor(project=project), runtime.descriptor(project=other)]
    started = time.monotonic()

    def record(name, detail=True):
        checks[name] = detail

    def shot(page, name):
        page.screenshot(path=str(shots / (name + '.png')), full_page=True)

    def assert_saved(page, value):
        expect(page.get_by_label('个人草稿', exact=True)).to_have_value(value)
        expect(page.get_by_text('已保存到项目，可跨端口恢复', exact=True)).to_be_visible()

    try:
        launcher_state, state, other_state = [runtime.ensure(desc) for desc in descriptors]
        url, other_url = state['url'], other_state['url']
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True, locale='zh-CN')
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(launcher_state['url'] + 'v2/')
            expect(page.get_by_role('heading', name='项目', exact=True)).to_be_visible()
            assert page.get_by_role('article').count() == 2
            record('explicit_registry_no_scan')
            shot(page, 'launcher-1440')
            page.get_by_role('button', name='选择项目文件夹', exact=True).click()
            expect(page.get_by_label('项目文件夹', exact=True)).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.get_by_role('dialog')).not_to_be_visible()
            expect(page.get_by_role('button', name='选择项目文件夹', exact=True)).to_be_focused()
            record('dialog_escape_focus')

            # Real create, then input revision; the UI must hand off the replacement
            # compose task without creating or dispatching another one.
            page.get_by_role('button', name='新建项目', exact=True).click()
            page.get_by_label('项目名称（必填）', exact=True).fill('浏览器合成新建')
            page.get_by_label('用途（必填）', exact=True).fill('说明工作台阅读与草稿流程')
            page.get_by_label('受众（必填）', exact=True).fill('第一次使用的人')
            page.get_by_label('保存到哪个文件夹（必填）', exact=True).fill(str(root))
            page.get_by_label('新项目文件夹名（必填）', exact=True).fill('created')
            page.get_by_role('button', name='创建项目', exact=True).click()
            expect(page.get_by_role('heading', name='内容与来源', exact=True)).to_be_visible()
            created = root / 'created'
            descriptors.append(runtime.descriptor(project=created))
            created_store = Store(created)
            initial_doc = created_store.load_document()
            initial_compose = [created_store.read_object_json(ref) for ref in initial_doc['tasks']][0]
            source = root / 'synthetic-facts.md'
            source.write_text('# 合成事实\n仅说明工作台流程，没有客户成效。\n')
            page.get_by_role('button', name='补充本机材料', exact=True).click()
            page.get_by_label('材料文件完整路径', exact=True).fill(str(source))
            page.get_by_role('button', name='登记材料', exact=True).click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            expect(page.get_by_text('synthetic-facts.md', exact=True)).to_be_visible()
            latest_doc = created_store.load_document()
            tasks = [created_store.read_object_json(ref) for ref in latest_doc['tasks']]
            eligible = [task for task in tasks if task['status'] == 'awaiting_host']
            assert len(eligible) == 1 and eligible[0]['task_id'] != initial_compose['task_id']
            page.get_by_role('button', name='整理内容并生成大纲', exact=True).click()
            expect(page.get_by_label('交接说明', exact=True)).to_have_value(re.compile(eligible[0]['task_id']))
            expect(page.get_by_text('待交接 · 尚未开始。将下面的说明复制到 Codex 后发送。', exact=True)).to_be_visible()
            page.keyboard.press('Escape')
            assert created_store.current_revision_id() == latest_doc['revision_id']
            record('create_material_handoff', {'one_eligible_task': True, 'task_replaced': True, 'no_model_or_duplicate_dispatch': True})

            page.goto(url + 'v2/')
            expect(page.get_by_role('heading', name='制作总览', exact=True)).to_be_visible()
            assert page.locator('button.primary').count() == 1
            expect(page.get_by_role('button', name='看整稿原图', exact=True)).to_be_visible()
            assert page.locator('.nav .ui-icon').count() == 5
            first_cell = page.get_by_role('button', name='第 1 页 · 项目目标与阅读顺序', exact=True)
            first_cell.focus(); page.keyboard.press('ArrowRight')
            expect(page.get_by_role('button', name='第 1 页 · 项目目标与阅读顺序，逐页稿，可看', exact=True)).to_be_focused()
            page.keyboard.press('Enter')
            expect(page.get_by_label('个人草稿', exact=True)).to_be_editable()
            page.get_by_label('个人草稿', exact=True).fill('第一页的个人内容意见')
            assert_saved(page, '第一页的个人内容意见')
            record('no_host_draft_and_table_keyboard')
            page.get_by_role('button', name='原图', exact=True).click()
            expect(page.get_by_label('个人草稿', exact=True)).to_have_value('')
            page.get_by_label('个人草稿', exact=True).fill('原图意见 A')
            assert_saved(page, '原图意见 A')
            page.get_by_label('阅读缩放', exact=True).select_option('1.25')
            assert_saved(page, '原图意见 A')
            hash_a = page.url.split('#', 1)[1]
            page.reload(); assert_saved(page, '原图意见 A')
            expect(page.get_by_label('阅读缩放', exact=True)).to_have_value('1.25')
            record('layer_isolation_refresh_zoom')
            shot(page, 'page-1440')
            for width, height in [(1280, 800), (1100, 800), (767, 900), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, 'horizontal overflow')
                expect(page.get_by_label('个人草稿', exact=True)).to_be_visible()
                shot(page, 'page-' + str(width))
            record('responsive_1440_1280_1100_767_390')
            page.set_viewport_size({'width': 1440, 'height': 900})

            # Hold an actual ACK while this editor leaves and reopens the page.
            held = []
            def hold_ack(route):
                held.append((route, route.fetch()))
            page.route('**/api/drafts/save', hold_ack, times=1)
            page.get_by_label('个人草稿', exact=True).fill('切页前已发送的原图意见')
            expect(page.get_by_text('正在保存到项目…', exact=True)).to_be_visible()
            page.wait_for_timeout(150)
            page.get_by_label('转到页面', exact=True).select_option('p02')
            expect(page.get_by_role('heading', name='第 2 页 · 材料如何成为内容', exact=True)).to_be_visible()
            page.get_by_label('转到页面', exact=True).select_option('p01')
            expect(page.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            page.get_by_label('个人草稿', exact=True).fill('切回之后的新输入')
            assert len(held) == 1 and held[0][1].status == 200
            held[0][0].fulfill(response=held[0][1])
            page.reload()
            expect(page.get_by_label('个人草稿', exact=True)).to_have_value('切回之后的新输入')
            page.get_by_role('button', name='核实草稿保存', exact=True).click()
            assert_saved(page, '切回之后的新输入')
            record('late_ack_cannot_replace_reopened_local_buffer')

            # A real server ACK is deliberately lost by the browser's transport.
            dropped = []
            def lose_ack(route):
                response = route.fetch()
                assert response.status == 200
                dropped.append(route.request.post_data_json)
                route.abort('failed')
            page.route('**/api/drafts/save', lose_ack, times=1)
            page.get_by_label('个人草稿', exact=True).fill('已经提交但回包丢失')
            expect(page.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            page.get_by_label('个人草稿', exact=True).fill('回包丢失之后又写的内容')
            page.wait_for_timeout(800)
            assert len(dropped) == 1
            server_draft = ui_journal.get(project, dropped[0]['draft']['draft_id'])['record']['draft']
            assert server_draft['content']['text'] == '已经提交但回包丢失'
            page.get_by_role('button', name='核实草稿保存', exact=True).click()
            assert_saved(page, '回包丢失之后又写的内容')
            record('lost_ack_frozen_payload_later_typing')

            # Concurrent windows share the same draft but retain their own ETags.
            second = context.new_page(); second.goto(page.url)
            assert_saved(second, '回包丢失之后又写的内容')
            page.get_by_label('个人草稿', exact=True).fill('窗口一的新稿')
            assert_saved(page, '窗口一的新稿')
            second.get_by_label('个人草稿', exact=True).fill('窗口二保留的冲突稿')
            expect(second.get_by_text('保存冲突，你的本机稿与项目中的稿件都已保留', exact=True)).to_be_visible()
            second.get_by_role('button', name='比较两份草稿', exact=True).click()
            expect(second.get_by_label('你的本机草稿', exact=True)).to_have_value('窗口二保留的冲突稿')
            expect(second.get_by_label('项目中已保存的草稿', exact=True)).to_have_value('窗口一的新稿')
            second.get_by_role('button', name='另存为个人草稿', exact=True).click()
            assert_saved(second, '窗口二保留的冲突稿')
            second.close()
            record('two_window_cas_keep_both')

            # Give the other project the identical page_id and project_id.
            foreign = context.new_page(); foreign.goto(other_url + 'v2/#' + hash_a)
            expect(foreign.get_by_text('这个链接属于另一个项目。请从项目列表打开原项目，当前内容未替换。', exact=True)).to_be_visible()
            foreign.goto(other_url + 'v2/')
            foreign.get_by_role('button', name='第 1 页 · 项目目标与阅读顺序', exact=True).click()
            expect(foreign.get_by_label('个人草稿', exact=True)).to_have_value('')
            foreign.get_by_label('个人草稿', exact=True).fill('项目二的独立原图意见')
            assert_saved(foreign, '项目二的独立原图意见')
            assert ui_journal.project_info(other)['project_identity'] != ui_journal.project_info(project)['project_identity']
            foreign.close()
            record('same_project_and_page_ids_isolated')
            assert (store.read_current(), content_identity(store.load_document())) == first_business
            record('draft_and_position_do_not_change_document')

            # An unsent recovery file is explicit and portable. It is not silently
            # restored at a new port until import has received a project ACK.
            page.route('**/api/drafts/save', lambda route: route.abort('failed'))
            page.get_by_label('个人草稿', exact=True).fill('原端口尚未同步的恢复稿')
            expect(page.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            with page.expect_download() as pending:
                page.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            recovery = root / 'personal-recovery.json'; pending.value.save_as(recovery)
            payload = json.loads(recovery.read_text())
            assert set(payload) == {'schema_version', 'draft', 'digest'}
            assert 'token' not in recovery.read_text().lower()
            runtime.stop(descriptors[1])
            with socket.socket() as occupied:
                occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                occupied.bind(('127.0.0.1', state['port'])); occupied.listen()
                rebooted = runtime.ensure(descriptors[1]); assert rebooted['port'] != state['port']
                fresh = context.new_page(); fresh.goto(rebooted['url'] + 'v2/')
                expect(fresh.get_by_role('heading', name='第 1 页 · 项目目标与阅读顺序', exact=True)).to_be_visible()
                expect(fresh.get_by_label('阅读缩放', exact=True)).to_have_value('1.25')
                # Both ACKed drafts exist; choose explicitly, never auto-overwrite.
                expect(fresh.get_by_label('个人草稿', exact=True)).not_to_have_value('原端口尚未同步的恢复稿')
                fresh.get_by_label('导入草稿恢复文件', exact=True).set_input_files(str(recovery))
                assert_saved(fresh, '原端口尚未同步的恢复稿')
                record('port_change_position_ack_drafts_and_explicit_import')
                shot(fresh, 'recovered-new-port')
                page.close(); page = fresh

            # Historical viewing stays at the original version after current moves.
            doc = store.load_document(); page_value = store.read_object_json(doc['pages'][0]['page'])
            page_value['customer_visible']['title'] = '当前的新标题'
            editing.edit_page(project, page=page_value, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='browser-new-current')
            new_revision = store.current_revision_id()
            page.reload()
            expect(page.get_by_text('历史版本 · 只读', exact=True)).to_be_visible()
            expect(page.get_by_role('heading', name='第 1 页 · 项目目标与阅读顺序', exact=True)).to_be_visible()
            expect(page.get_by_label('个人草稿', exact=True)).not_to_be_editable()
            assert first_revision in page.url and new_revision not in page.url
            record('historical_stale_basis_no_forced_latest')
            shot(page, 'historical-readonly')

            # Explicit unavailable revision must not be silently replaced.
            page.goto(page.url.replace(first_revision, 'missing-version'))
            expect(page.get_by_text(re.compile('这个版本不在当前项目的已提交历史中'))).to_be_visible()
            page.reload()
            expect(page.get_by_role('heading', name='无法读取这个位置', exact=True)).to_be_visible()
            assert 'missing-version' in page.url
            record('missing_revision_no_fallback')
            assert not errors, errors
            record('no_unhandled_javascript_errors')
            context.tracing.stop(path=str(root / 'local-only-trace.zip'))
            browser.close()
        report = {'evidence_level': 'real Chromium / real local service / deterministic synthetic projects',
                  'checks': checks, 'elapsed_seconds': round(time.monotonic() - started, 2),
                  'model_calls': 0, 'real_home_changed': False, 'user_acceptance': 'not measured',
                  'installation_download_and_host_time': 'not measured', 'user_help_requests': 'not measured'}
        (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}, ensure_ascii=False))
    finally:
        for desc in reversed(descriptors):
            runtime.stop(desc)


if __name__ == '__main__':
    main()
