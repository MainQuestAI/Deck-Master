"""W03 browser faults and actual older-core compatibility.

The compatibility adapter serves only the new static UI and forwards GETs to
an unmodified older core. It never fabricates health or accepts writes.
"""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import threading
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from deck_master import editing, local_runtime as runtime, registry, samples, ui_journal, service
from deck_master.models import bump_revision
from deck_master.pipeline import artifact
from deck_master.store import Store

OLDER_CORE = '09f4486a453d2132a18dbefd10f99ef7317e8fd5'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(args.out).absolute(); root.mkdir(parents=True, exist_ok=False)
    (root / 'screenshots').mkdir()
    project = root / 'synthetic-editable'
    samples.create_sample(project, page_count=2, readonly=False)
    readonly = root / 'synthetic-readonly'
    samples.create_sample(readonly, page_count=1)
    store = Store(project)
    doc = store.load_document()
    page_value = store.read_object_json(doc['pages'][0]['page'])
    hostile = '<img data-pwn="yes" src=x onerror="window.injected=true">'
    page_value['customer_visible']['title'] = hostile
    page_value['customer_visible']['body_blocks'] = [
        {'id': 'p', 'type': 'paragraph', 'text': '<script>window.injected=true</script>'},
        {'id': 'b', 'type': 'bullets', 'items': [{'id': 'b1', 'text': '一级', 'children': [{'id': 'b2', 'text': '二级可见'}]}]},
    ]
    editing.edit_page(project, page=page_value, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='hostile-title')
    svg = root / 'untrusted.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><script>window.injected=true;fetch("http://127.0.0.1:9/forbidden")</script><rect width="320" height="180" fill="white"/><text x="20" y="90">Synthetic unsafe SVG test</text></svg>')
    doc = store.load_document()
    doc['pages'][0]['blueprint'] = artifact(store, svg, 'blueprint', page_id='p01')
    updated = bump_revision(doc, {'operation_id': 'unsafe-svg', 'kind': 'task_update', 'description': 'Explicit security fixture', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='unsafe-svg')
    revision = store.current_revision_id()
    prompt_project = root / 'prepared-prompts'
    samples.create_sample(prompt_project, page_count=1, readonly=False)
    prompt_store = Store(prompt_project)
    prompt_doc = prompt_store.load_document()
    service.open_blueprint_task(prompt_store, prompt_doc, prompt_doc['pages'][0])
    prompt_doc = prompt_store.load_document()
    prompt_page = prompt_store.read_object_json(prompt_doc['pages'][0]['page'])
    prompt_page['visual_spec']['intent'] = '第二份明确区分的合成制作方向'
    editing.edit_page(prompt_project, page=prompt_page, base_revision=prompt_doc['revision_id'], page_hash=prompt_doc['pages'][0]['page']['sha256'], operation_id='prompt-new-basis')
    prompt_doc = prompt_store.load_document()
    service.open_blueprint_task(prompt_store, prompt_doc, prompt_doc['pages'][0])


    # Archive a known commit without touching another checkout or branch.
    older = root / 'older-core'; older.mkdir()
    archive = subprocess.run(['git', 'archive', OLDER_CORE, 'src/deck_master', 'skills/deck-master', 'pyproject.toml'], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        for member in tar.getmembers():
            target = older / member.name
            if member.isdir(): target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
            else: raise AssertionError('unexpected archive entry')
    old_project = root / 'old-project'
    script = """import json,sys\nfrom deck_master import service\nfrom deck_master.web import WorkbenchServer\nservice.create(sys.argv[1],brief='Old project read compatibility',title='旧项目读取验证',audience='使用者')\ns=WorkbenchServer(sys.argv[1]);url=s.start()\nprint(json.dumps({'url':url}),flush=True)\ntry: input()\nfinally: s.stop()\n"""
    env = {**os.environ, 'PYTHONPATH': str(older / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    old = subprocess.Popen([sys.executable, '-c', script, str(old_project)], cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    descriptors = [runtime.descriptor(project=project), runtime.descriptor(project=readonly), runtime.descriptor(project=prompt_project)]
    proxy = None
    checks = {}; failures = []
    try:
        line = old.stdout.readline()
        assert line, old.stderr.read()
        old_url = json.loads(line)['url']; old_target = urlsplit(old_url)
        static = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'
        forwarded = []
        class Adapter(BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def do_GET(self):
                path = urlsplit(self.path).path
                if path.startswith('/v2/'):
                    file = static / (path[4:] or 'index.html')
                    assert file.resolve().is_relative_to(static)
                    data = file.read_bytes(); self.send_response(200)
                    self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                else:
                    forwarded.append({'method': 'GET', 'path': path})
                    conn = http.client.HTTPConnection(old_target.hostname, old_target.port, timeout=5)
                    try:
                        conn.request('GET', self.path); response = conn.getresponse(); data = response.read()
                        self.send_response(response.status); self.send_header('Content-Type', response.getheader('Content-Type'))
                        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                    finally: conn.close()
            def do_POST(self):
                forwarded.append({'method': 'POST', 'path': self.path})
                self.send_error(405)
        proxy = ThreadingHTTPServer(('127.0.0.1', 0), Adapter)
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
        states = [runtime.ensure(desc) for desc in descriptors]
        config = root / 'config' / 'projects.json'
        registry.register(config, readonly)
        launcher_desc = runtime.descriptor(registry=config); descriptors.append(launcher_desc)
        launch = runtime.ensure(launcher_desc)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
            page = context.new_page(); page.on('pageerror', lambda err: failures.append(str(err)))
            page.goto(f'http://127.0.0.1:{proxy.server_port}/v2/')
            expect(page.get_by_role('heading', name='当前核心尚不支持新版工作台', exact=True)).to_be_visible()
            assert forwarded == [{'method': 'GET', 'path': '/api/health'}]
            checks['new_ui_actual_old_core'] = {'commit': OLDER_CORE, 'upgrade_screen': True, 'api_reads': forwarded.copy(), 'writes': 0,
                'transport': 'new static files plus GET-only proxy to unmodified old core'}
            page.screenshot(path=str(root / 'screenshots' / 'old-core-upgrade.png'), full_page=True)
            # Release old service; current core opens the exact old v1 project.
            old.stdin.write('\n'); old.stdin.flush(); old.wait(timeout=10)
            before = (old_project / '.deckmaster/current.json').read_bytes()
            old_desc = runtime.descriptor(project=old_project); descriptors.append(old_desc)
            new_state = runtime.ensure(old_desc)
            page.goto(new_state['url'] + 'v2/')
            expect(page.get_by_role('heading', name='内容与来源', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='整理内容并生成大纲', exact=True)).to_be_visible()
            assert (old_project / '.deckmaster/current.json').read_bytes() == before
            checks['new_ui_new_core_old_project_without_migration'] = True
            page.get_by_role('button', name='查看待交接任务，1 项', exact=True).click()
            page.get_by_role('button', name='查看这项任务', exact=True).click()
            expect(page.get_by_role('heading', name='当前任务', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='交接这项内容整理', exact=True)).to_be_visible()
            assert '&task=' in page.url
            page.reload()
            expect(page.get_by_role('heading', name='当前任务', exact=True)).to_be_visible()
            checks['task_deep_link_reload'] = True


            page.goto(states[0]['url'])
            expect(page.locator('#meta-pages')).to_have_text('2')
            expect(page.locator('#page-title')).to_have_text(hostile)
            assert '/v2/' not in page.url
            checks['legacy_ui_new_core_default_preserved'] = True
            requests = []
            page.on('request', lambda request: requests.append(request.url))
            page.goto(states[0]['url'] + 'v2/')
            page.get_by_role('button', name='第 1 页 · ' + hostile, exact=True).click()
            expect(page.get_by_label('个人草稿', exact=True)).to_be_editable()
            assert page.locator('[data-pwn]').count() == 0
            expect(page.locator('.page-image')).to_be_visible()
            page.wait_for_function('document.querySelector(".page-image")?.naturalWidth > 0')
            assert page.evaluate('window.injected === undefined')
            assert not any('/forbidden' in url for url in requests)
            page.get_by_role('button', name='逐页稿', exact=True).click()
            expect(page.get_by_text('二级可见', exact=True)).to_be_visible()
            expect(page.get_by_text('<script>window.injected=true</script>', exact=True)).to_be_visible()
            assert page.locator('[data-pwn]').count() == 0
            checks['html_and_svg_scripts_inert'] = True
            page.get_by_role('link', name='跳到工作区', exact=True).focus()
            page.keyboard.press('Enter')
            expect(page.locator('#main')).to_be_focused()
            assert '#project=' in page.url
            checks['skip_link_does_not_break_route'] = True

            # Keep read content while the next real service GET is unavailable.
            page.route('**/api/view/summary*', lambda route: route.abort('failed'))
            page.get_by_role('button', name='整稿画廊', exact=True).click()
            expect(page.get_by_text('二级可见', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='重试读取', exact=True)).to_be_visible()
            page.unroute('**/api/view/summary*'); page.get_by_role('button', name='重试读取', exact=True).click()
            expect(page.get_by_role('heading', name='整稿画廊', exact=True)).to_be_visible()
            checks['disconnection_preserves_last_read_surface'] = True

            quota = browser.new_context(accept_downloads=True)
            quota.add_init_script("""const setItem = Storage.prototype.setItem; Storage.prototype.setItem = function(k,v) { if (this === localStorage) throw new DOMException('Full', 'QuotaExceededError'); return setItem.call(this,k,v); };""")
            qpage = quota.new_page(); qpage.route('**/api/drafts/save', lambda route: route.abort('failed'))
            qpage.goto(states[0]['url'] + 'v2/')
            qpage.get_by_role('button', name='第 2 页 · 材料如何成为内容', exact=True).click()
            qpage.get_by_label('个人草稿', exact=True).fill('缓冲配额失败仍可下载')
            expect(qpage.get_by_text('浏览器缓冲未保存。输入仍在此页，请立即下载恢复文件或复制内容。', exact=True)).to_be_visible()
            expect(qpage.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            expect(qpage.get_by_label('个人草稿', exact=True)).to_have_value('缓冲配额失败仍可下载')
            with qpage.expect_download() as download:
                qpage.get_by_role('button', name='下载草稿恢复文件', exact=True).click()
            file = root / 'quota-recovery.json'; download.value.save_as(file)
            assert json.loads(file.read_text())['draft']['content']['text'] == '缓冲配额失败仍可下载'
            assert ui_journal.list_drafts(project)['records'] == []
            checks['quota_and_network_failure_export_recovery'] = True
            second_page_url = qpage.url
            quota.close()

            # Same-origin tabs keep unsent buffers under separate window keys.
            one = context.new_page(); one.goto(second_page_url)
            one.get_by_label('个人草稿', exact=True).fill('两个窗口共同读取的已保存基准')
            expect(one.get_by_text('已保存到项目，可跨端口恢复', exact=True)).to_be_visible()
            two = context.new_page(); two.goto(one.url)
            expect(two.get_by_label('个人草稿', exact=True)).to_have_value('两个窗口共同读取的已保存基准')
            for tab, text in [(one, '窗口 A 尚未同步'), (two, '窗口 B 尚未同步')]:
                tab.route('**/api/drafts/save', lambda route: route.abort('failed'))
                tab.get_by_label('个人草稿', exact=True).fill(text)
                expect(tab.get_by_text('保存结果待核实，后写内容仅在本机保留', exact=True)).to_be_visible()
            one.reload(); two.reload()
            expect(one.get_by_label('个人草稿', exact=True)).to_have_value('窗口 A 尚未同步')
            expect(two.get_by_label('个人草稿', exact=True)).to_have_value('窗口 B 尚未同步')
            one.get_by_label('恢复本机保留的草稿副本', exact=True).select_option(label='窗口 B 尚未同步')
            expect(one.get_by_label('个人草稿', exact=True)).to_have_value('窗口 B 尚未同步')
            one.get_by_label('恢复本机保留的草稿副本', exact=True).select_option(label='窗口 A 尚未同步')
            expect(one.get_by_label('个人草稿', exact=True)).to_have_value('窗口 A 尚未同步')
            checks['selecting_local_copy_preserves_both_sides'] = True
            one.close(); two.close()
            checks['same_origin_tabs_preserve_distinct_unsent_buffers'] = True

            # Use genuine launcher/sample routes. A cancelled native picker result
            # is fault-injected, separately from the real OS-dialog limitation.
            page.goto(launch['url'] + 'v2/')
            page.get_by_role('button', name='选择项目文件夹', exact=True).click()
            page.get_by_label('项目文件夹', exact=True).fill('preserved-input')
            page.route('**/api/directories/pick', lambda route: route.fulfill(json={'status': 'cancelled', 'path': None}), times=1)
            page.get_by_role('button', name='浏览文件夹', exact=True).click()
            expect(page.get_by_label('项目文件夹', exact=True)).to_have_value('preserved-input')
            expect(page.get_by_text('已取消选择，当前项目保持。', exact=True)).to_be_visible()
            assert len(registry.listing(config)['projects']) == 1
            page.keyboard.press('Escape')
            checks['picker_cancel_keeps_input_and_registry'] = 'browser route fault injection; native dialog not driven'
            page.goto(states[1]['url'] + 'v2/')
            page.get_by_role('button', name='第 1 页 · 项目目标与阅读顺序', exact=True).click()
            expect(page.get_by_label('个人草稿', exact=True)).not_to_be_editable()
            expect(page.get_by_role('button', name='保存个人草稿', exact=True)).to_be_disabled()
            assert ui_journal.list_drafts(readonly)['records'] == []
            checks['sample_readonly'] = True
            page.goto(states[2]['url'] + 'v2/')
            page.get_by_role('button', name='第 1 页 · 项目目标与阅读顺序', exact=True).click()
            page.get_by_role('button', name='预备提示词', exact=True).click()
            select = page.get_by_label('选择草稿绑定的预备提示词', exact=True)
            expect(select.locator('option')).to_have_count(3)
            select.select_option(index=1)
            page.get_by_label('个人草稿', exact=True).fill('仅属于第一份预备稿')
            expect(page.get_by_text('已保存到项目，可跨端口恢复', exact=True)).to_be_visible()
            select.select_option(index=2)
            expect(page.get_by_label('个人草稿', exact=True)).to_have_value('')
            page.get_by_label('个人草稿', exact=True).fill('仅属于第二份预备稿')
            expect(page.get_by_text('已保存到项目，可跨端口恢复', exact=True)).to_be_visible()
            records = ui_journal.list_drafts(prompt_project)['records']
            assert len(records) == 2 and records[0]['draft']['base_ref'] != records[1]['draft']['base_ref']
            checks['multiple_prepared_prompts_require_explicit_draft_basis'] = True
            assert store.current_revision_id() == revision
            assert not failures, failures
            browser.close()
        report = {'checks': checks, 'evidence_level': 'real Chromium and real local cores; explicit fault injection where labeled',
                  'model_calls': 0, 'native_directory_dialog': 'unverified: CUA inventory timed out before dialog was opened',
                  'real_home_changed': False, 'release': False}
        (root / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': 'verified', 'checks': len(checks), 'report': str(root / 'checks.json')}))
    finally:
        if proxy: proxy.shutdown(); proxy.server_close()
        if old.poll() is None:
            old.stdin.write('\n'); old.stdin.flush()
            try: old.wait(timeout=10)
            except subprocess.TimeoutExpired: old.terminate(); old.wait(timeout=10)
        for desc in reversed(descriptors): runtime.stop(desc)


if __name__ == '__main__':
    main()
