"""A copied preparation reaches the real method reader without widening speech scope."""
import json
import subprocess
import sys
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright, expect
from deck_master import method_library_view, method_resources, ui_journal
from deck_master.web import WorkbenchServer
from test_webui_content_insight import candidate


def preparation(text):
    return json.loads(text.split('```json\n', 1)[1].split('\n```', 1)[0])


def test_preparation_handoff_keeps_complete_context_and_resource_basis(tmp_path):
    project, store, _, _ = candidate(tmp_path)
    before = store.load_document()
    context = {'mode': 'independent', 'role': 'deck-review', 'phase': 'speech', 'review_units': ['speech']}
    value = method_library_view.preview(project, {'context': context, 'selected_resource_ids': ['writing-profiles']})
    copied = preparation(value['handoff']['text'])
    assert copied['context'] == context
    assert copied['role'] == 'deck-review' and copied['phase'] == 'speech'
    assert copied['review_units'] == ['speech'] and copied['preparation_only']
    assert copied['project_id'] is None and copied['revision_id'] is None
    assert copied['resolved_manifest'] == value['resolved_manifest']
    assert copied['recovery']['context'] == context
    assert copied['recovery']['selected_resource_ids'] == ['writing-profiles']
    assert copied['catalog_digest'] == value['catalog_digest']
    assert copied['context_digest'] == value['context_digest']
    assert copied['preview_digest'] == value['preview_digest']
    assert store.load_document() == before


@pytest.mark.browser
@pytest.mark.parametrize('width', [1440,1280,390])
def test_speech_preparation_real_clipboard_reader_and_draft_restore(tmp_path, width):
    project, store, _, _ = candidate(tmp_path)
    before = store.load_document()
    info = ui_journal.project_info(project)
    server = WorkbenchServer(project)
    try:
        url = server.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'], viewport={'width':width,'height':900})
            page = context.new_page()
            try:
                page.goto(url+'studio/#'+urlencode({'project': info['project_identity'], 'surface': 'content',
                    'content_area': 'methods', 'revision': store.current_revision_id(), 'layer': 'content'}))
                expect(page.locator('#content-area-methods')).to_contain_text('目录可浏览')
                expect(page.get_by_role('button', name='重新核对后复制准备要求', exact=True)).to_be_disabled()
                page.get_by_label('准备上下文').select_option('independent')
                page.get_by_label('方法阅读角色').select_option('deck-review')
                page.get_by_label('方法阅读阶段').select_option('speech')
                expect(page.locator('#content-area-methods')).to_contain_text('审阅范围：口播。')
                expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
                page.locator('[data-resource-id="writing-profiles"] input').check()
                expect(page.get_by_role('button', name='阅读 writing-profiles', exact=True)).to_be_visible()
                # Use the actual browser clipboard API, and restore its prior text.
                page.evaluate('async()=>{window.previousClipboard=await navigator.clipboard.readText()}')
                page.get_by_role('button', name='重新核对后复制准备要求', exact=True).click()
                expect(page.get_by_text('已复制，尚未开始。请在制作工具中发送。', exact=True)).to_be_visible()
                copied = preparation(page.evaluate('navigator.clipboard.readText()'))
                page.evaluate('navigator.clipboard.writeText(window.previousClipboard)')
                assert copied['context']['review_units'] == ['speech']
                assert copied['role'] == 'deck-review' and copied['phase'] == 'speech'
                assert copied['explicit_ids'] == ['writing-profiles']
                # Consume the copied fields through the public read-only CLI, not a mock reader.
                args = [sys.executable, '-m', 'deck_master', 'methods', '--kind', 'review', '--phase', copied['phase'], '--read']
                for unit in copied['review_units']:
                    args.extend(['--review-unit', unit])
                for resource in copied['explicit_ids']:
                    args.extend(['--selected-resource-id', resource])
                read = subprocess.run(args, capture_output=True, text=True, check=True)
                actual = json.loads(read.stdout)['methods']
                expected = set(method_resources.method_ids_for('review', review_units=['speech'])) | {'writing-profiles'}
                assert {item['id'] for item in actual} == expected
                assert not {'source-reading', 'physical-units', 'content-calibration'} & expected
                manifest = {item['id']: item['sha256'] for item in copied['resolved_manifest']}
                assert all(item['sha256'] == manifest[item['id']] and item['content'] for item in actual)
                page.get_by_text('保存与恢复个人准备稿', exact=True).click()
                # DraftEditor autosaves after 600ms. Clipboard/CLI verification
                # may already have completed that save; a saved draft correctly
                # disables its button. Assert persistence instead of racing it.
                expect(page.locator('.method-draft-state')).to_contain_text('已保存')
                expect(page.get_by_role('button', name='保存方法准备稿', exact=True)).to_be_disabled()
                page.reload()
                expect(page.get_by_label('方法阅读阶段')).to_have_value('speech')
                expect(page.locator('#content-area-methods')).to_contain_text('审阅范围：口播。')
                expect(page.locator('[data-resource-id="writing-profiles"] input')).to_be_checked()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert store.load_document() == before
            finally:
                browser.close()
    finally:
        server.stop()
