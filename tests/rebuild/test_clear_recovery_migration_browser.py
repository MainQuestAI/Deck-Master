"""Real old/new browser recovery migration; no generation or business writes.

The JS fixture is byte-for-byte personal-maintenance.js from
 e6d5a572b99d7d0d5c9bf37bb95c335d4b9a35bc, SHA256
 edc515e25579b40480fd769c4ca2ef287a67b92bd88fbaf4276fa5b726b15756.
It is served only to the named old test page, never installed as runtime code.
"""
import hashlib
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import ui_journal as journal
from deck_master.web import WorkbenchServer
from test_ui_state_clear import project, store, save_draft  # noqa: F401
from test_pr189_clear_end_browser import open_panel
from test_pr189_clear_ownership_browser import click

pytestmark = pytest.mark.browser
LEGACY = Path(__file__).with_name('fixtures') / 'personal-maintenance-localstorage-e6d5a572.js'
LEGACY_SHA256 = 'edc515e25579b40480fd769c4ca2ef287a67b92bd88fbaf4276fa5b726b15756'
DB = 'deck-master:personal-clear'


@pytest.fixture
def session(project):
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            context = browser.new_context()
            try:
                yield context, server.start() + 'studio/'
            finally:
                context.close()
                browser.close()
    finally:
        server.stop()


def legacy_key(project):
    return 'deck-master:v3:personal-clear:' + journal.list_drafts(project)['project_identity']


def legacy_raw(page, key):
    return page.evaluate('key => localStorage.getItem(key)', key)


def recovery_row(page, identity):
    return page.evaluate('''async identity => {
      const databases = await indexedDB.databases();
      if (!databases.some(db => db.name === 'deck-master:personal-clear')) return null;
      return new Promise((resolve,reject) => {
        const open=indexedDB.open('deck-master:personal-clear');
        open.onerror=()=>reject(open.error);
        open.onsuccess=()=>{
          const db=open.result;
          if(!db.objectStoreNames.contains('records')){db.close();resolve(null);return;}
          const tx=db.transaction('records','readonly'), get=tx.objectStore('records').get(identity);
          tx.oncomplete=()=>{const row=get.result??null;db.close();resolve(row);};
          tx.onabort=()=>{db.close();reject(tx.error||new Error('fixture read aborted'));};
        };
      });
    }''', identity)


def old_page(context, url):
    data = LEGACY.read_bytes()
    assert hashlib.sha256(data).hexdigest() == LEGACY_SHA256
    page = context.new_page()
    def serve_old(route):
        route.fulfill(status=200, content_type='text/javascript', headers={'Cache-Control': 'no-store'}, body=data)
    page.route('**/v2/personal-maintenance.js', serve_old)
    page.goto(url)
    return page, serve_old


def retain_old_request(page, project):
    panel = open_panel(page)
    click(panel, '生成清理计划')
    expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
    sent = []
    def unavailable(route):
        sent.append(route.request.post_data_json)
        route.abort('failed')
    page.route('**/api/ui-state/commit-clear', unavailable)
    click(panel, '确认清理并保留备份')
    expect(panel).to_contain_text('清理结果待核实')
    raw = legacy_raw(page, legacy_key(project))
    record = json.loads(raw)
    assert len(sent) == 1 and record['request'] == sent[0]
    page.unroute('**/api/ui-state/commit-clear', unavailable)
    return record, raw


def migrate(page, old_handler):
    page.unroute('**/v2/personal-maintenance.js', old_handler)
    page.reload()
    panel = open_panel(page)
    expect(panel.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
    return panel


def test_legacy_pending_survives_unavailable_clear_reload_and_empty_marker(project, store, session):
    save_draft(store, project)
    before = store.load_document()
    context, url = session
    page, old_handler = old_page(context, url)
    record, raw = retain_old_request(page, project)
    key, identity = legacy_key(project), record['project_identity']
    panel = migrate(page, old_handler)
    assert recovery_row(page, identity) == {'initialized': True, 'pending': record, 'legacy': raw}
    assert legacy_raw(page, key) == raw
    attempted = []
    def unavailable(route):
        attempted.append(route.request.post_data_json)
        route.abort('failed')
    # The application shell remains loadable; the clear transport is unavailable
    # across reload. No successful reply or terminal outcome is fabricated.
    page.route('**/api/ui-state/commit-clear', unavailable)
    with page.expect_request('**/api/ui-state/commit-clear'):
        click(panel, '核实并重试原清理')
    expect(panel.get_by_role('button', name='核实并重试原清理', exact=True)).to_be_enabled()
    expect(panel).to_contain_text('清理结果待核实')
    page.reload()
    panel = open_panel(page)
    expect(panel.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
    assert attempted == [record['request']]
    assert recovery_row(page, identity)['pending'] == record
    assert legacy_raw(page, key) == raw
    click(panel, '核实原清理结果')
    expect(panel).to_contain_text('未发现执行证据')
    assert len(journal.list_drafts(project)['records']) == 1
    page.unroute('**/api/ui-state/commit-clear', unavailable)
    with page.expect_request('**/api/ui-state/commit-clear') as retry:
        click(panel, '核实并重试原清理')
    expect(panel).to_contain_text('已清理')
    assert retry.value.post_data_json == record['request']
    assert retry.value.headers.get('x-deck-clear-recovery') == 'indexeddb.v1'
    assert recovery_row(page, identity) == {'initialized': True, 'pending': None, 'legacy': raw}
    assert legacy_raw(page, key) == raw
    assert journal.list_drafts(project)['records'] == []
    assert store.load_document() == before
    # The old bytes stay as migration evidence. They must never resurrect the
    # completed request after refresh, even once a new draft exists.
    save_draft(store, project, 'after-migration', text='must not be cleared by old replay')
    page.reload()
    panel = open_panel(page)
    expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_enabled()
    expect(panel.get_by_role('button', name='核实原清理结果', exact=True)).to_be_hidden()
    assert recovery_row(page, identity)['pending'] is None
    assert legacy_raw(page, key) == raw
    assert [row['draft']['draft_id'] for row in journal.list_drafts(project)['records']] == ['after-migration']


def test_corrupt_legacy_blocks_migration_without_rewriting_evidence(project, store, session):
    save_draft(store, project)
    context, url = session
    page = context.new_page()
    key = legacy_key(project)
    raw = '{"project_identity": "damaged legacy evidence"'
    page.add_init_script('localStorage.setItem(' + json.dumps(key) + ',' + json.dumps(raw) + ');')
    posts = []
    page.on('request', lambda req: posts.append(req.url) if req.url.endswith('/commit-clear') else None)
    page.goto(url)
    panel = open_panel(page)
    expect(panel).to_contain_text('恢复记录')
    expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
    expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_disabled()
    assert legacy_raw(page, key) == raw
    assert posts == []
    assert len(journal.list_drafts(project)['records']) == 1
    page.reload()
    panel = open_panel(page)
    expect(panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
    assert legacy_raw(page, key) == raw and posts == []


def test_old_page_after_new_initialization_is_rejected_and_preserves_both_evidences(project, store, session):
    save_draft(store, project)
    context, url = session
    old, _ = old_page(context, url)
    old_panel = open_panel(old)
    click(old_panel, '生成清理计划')
    expect(old_panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
    new = context.new_page()
    new.goto(url)
    new_panel = open_panel(new)
    expect(new_panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_enabled()
    identity = journal.list_drafts(project)['project_identity']
    initial = recovery_row(new, identity)
    assert initial == {'initialized': True, 'pending': None, 'legacy': None}
    with old.expect_response('**/api/ui-state/commit-clear') as response:
        click(old_panel, '确认清理并保留备份')
    assert response.value.status == 409
    assert response.value.json()['error']['code'] == 'clear_recovery_upgrade_required'
    raw = legacy_raw(old, legacy_key(project))
    assert json.loads(raw)['request']['operation_id']
    assert len(journal.list_drafts(project)['records']) == 1
    # Do not silently merge an old client's subsequent operation into an
    # initialized new-client slot, including an initialized empty slot.
    new.reload()
    new_panel = open_panel(new)
    expect(new_panel).to_contain_text('恢复记录')
    expect(new_panel.get_by_role('button', name='生成清理计划', exact=True)).to_be_disabled()
    assert recovery_row(new, identity) == initial
    assert legacy_raw(new, legacy_key(project)) == raw
    assert len(journal.list_drafts(project)['records']) == 1


def test_abort_of_end_intent_transaction_keeps_migrated_request_and_sends_no_post(project, store, session):
    save_draft(store, project)
    context, url = session
    page, old_handler = old_page(context, url)
    record, raw = retain_old_request(page, project)
    panel = migrate(page, old_handler)
    click(panel, '核实原清理结果')
    expect(panel).to_contain_text('未发现执行证据')
    expect(panel.get_by_role('button', name='结束旧操作并重新计划', exact=True)).to_be_enabled()
    posts = []
    page.on('request', lambda req: posts.append(req.url) if req.method == 'POST' and
            any(req.url.endswith('/' + action) for action in ('end-clear', 'commit-clear')) else None)
    page.evaluate('''() => {
      const original=IDBObjectStore.prototype.put;
      window.clearAbortInjected=false;
      IDBObjectStore.prototype.put=function(value,...args){
        const result=original.call(this,value,...args);
        if(this.name==='records' && this.transaction.db.name==='deck-master:personal-clear' &&
           value?.pending?.end_inspection_digest && !window.clearAbortInjected){
          window.clearAbortInjected=true;this.transaction.abort();
        }
        return result;
      };
    }''')
    click(panel, '结束旧操作并重新计划')
    page.wait_for_function('() => window.clearAbortInjected===true')
    expect(panel.get_by_role('button', name='核实原清理结果', exact=True)).to_be_enabled()
    expect(panel).to_contain_text('清理结果待核实')
    assert posts == []
    assert recovery_row(page, record['project_identity']) == {'initialized': True, 'pending': record, 'legacy': raw}
    assert legacy_raw(page, legacy_key(project)) == raw
    assert len(journal.list_drafts(project)['records']) == 1


@pytest.mark.parametrize('stage', ['migration', 'first_claim'])
def test_aborted_publication_keeps_original_evidence_and_never_posts(project, store, session, stage):
    save_draft(store, project)
    context, url = session
    identity = journal.list_drafts(project)['project_identity']
    if stage == 'migration':
        page, old_handler = old_page(context, url)
        record, raw = retain_old_request(page, project)
        page.unroute('**/v2/personal-maintenance.js', old_handler)
    else:
        page = context.new_page()
        page.goto(url)
        panel = open_panel(page)
        click(panel, '生成清理计划')
        expect(panel.get_by_role('button', name='确认清理并保留备份', exact=True)).to_be_enabled()
        record, raw = None, None
    abort = '''() => {
      const original=IDBObjectStore.prototype.put;
      window.publicationAborted=false;
      IDBObjectStore.prototype.put=function(value,...args){
        const result=original.call(this,value,...args);
        if(this.name==='records' && this.transaction.db.name==='deck-master:personal-clear' &&
           value?.pending){
          window.publicationAborted=true;this.transaction.abort();
        }
        return result;
      };
    }'''
    posts = []
    page.on('request', lambda req: posts.append(req.url) if req.url.endswith('/commit-clear') else None)
    if stage == 'migration':
        page.add_init_script('(' + abort + ')()')
        page.reload()
        panel = open_panel(page)
    else:
        page.evaluate(abort)
        click(panel, '确认清理并保留备份')
    page.wait_for_function('() => window.publicationAborted === true')
    expect(panel).to_contain_text('恢复记录')
    assert posts == []
    assert recovery_row(page, identity) == (None if stage == 'migration' else
        {'initialized': True, 'pending': None, 'legacy': None})
    assert legacy_raw(page, legacy_key(project)) == raw
    assert len(journal.list_drafts(project)['records']) == 1
    # A fresh page with working storage can still read the original evidence.
    recovered = context.new_page()
    recovered.goto(url)
    recovered_panel = open_panel(recovered)
    expect(recovered_panel.get_by_role('button', name='核实原清理结果' if record else '生成清理计划', exact=True)).to_be_enabled()
    assert recovery_row(recovered, identity)['pending'] == record
