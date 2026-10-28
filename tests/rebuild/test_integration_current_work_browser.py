"""The current-work projection and selection workspace share one primary action."""
import re

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from candidate_fixtures import store as candidate_store, dispatch  # noqa: F401


pytestmark = pytest.mark.browser


@pytest.mark.parametrize('route', ['studio', 'v2'])
def test_same_identity_poll_preserves_selected_workspace_and_its_primary_action(tmp_path, route):
    project = tmp_path / 'selection-poll'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    before = store.load_document()
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.start() + route + '/')
            primary = page.locator('.overview [data-current-work] [data-priority-action]')
            expect(primary).to_have_class(re.compile(r'\bprimary\b'))
            selected = page.locator('.matrix tbody input[type=checkbox]:enabled').first
            selected.check()
            expect(primary).not_to_have_class(re.compile(r'\bprimary\b'))
            requirement = page.get_by_label('所选页的制作要求', exact=True)
            requirement.fill('保留原始来源与页面范围，只调整本次选页的版式。')
            saved_text = requirement.input_value()
            selected_id = selected.get_attribute('aria-label')
            page.evaluate('''() => {
              window.integrationMatrix = document.querySelector('.matrix');
              window.integrationRequirement = document.querySelector('[aria-label="所选页的制作要求"]');
              window.integrationWork = document.querySelector('.overview [data-current-work]');
              const root = document.querySelector('#app');
              root.addEventListener('summary-refreshed', () => {window.integrationPollApplied = true;}, {once:true});
              root.dispatchEvent(new CustomEvent('business-state-changed'));
            }''')
            page.wait_for_function('() => window.integrationPollApplied === true')
            expect(primary).not_to_have_class(re.compile(r'\bprimary\b'))
            expect(requirement).to_have_value(saved_text)
            expect(page.locator('.matrix tbody input[type=checkbox]:checked')).to_have_count(1)
            assert page.locator('.matrix tbody input[type=checkbox]:checked').get_attribute('aria-label') == selected_id
            assert page.evaluate('''() =>
              window.integrationMatrix === document.querySelector('.matrix') &&
              window.integrationRequirement === document.querySelector('[aria-label="所选页的制作要求"]') &&
              window.integrationWork.isConnected &&
              window.integrationWork === document.querySelector('.overview [data-current-work]')''')
            page.get_by_role('button', name='清除选择', exact=True).click()
            expect(primary).to_have_class(re.compile(r'\bprimary\b'))
            assert store.load_document() == before and errors == []
            browser.close()
    finally:
        server.stop()


@pytest.mark.parametrize('route_name', ['studio', 'v2'])
def test_route_load_pairs_delayed_work_with_paused_control_before_first_render(candidate_store, route_name):
    from deck_master import collaboration, workbench

    store = candidate_store
    dispatch(store)
    artifact_revision = store.current_revision_id()
    original = workbench.workbench_summary(store.project_root, protocol='workbench_summary.v2')['current_work']
    assert original['next']['action'] == 'handoff'
    server = WorkbenchServer(store.project_root)
    state = {'project_reads': 0, 'summary_reads': 0, 'paused': False}
    held = []
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            # Record the first rendered work, so a later healthy poll cannot
            # hide an incorrect initial handoff action.
            page.add_init_script('''(() => {
              const observer = new MutationObserver(() => {
                const panel = document.querySelector('.overview [data-current-work]');
                const evidence = panel?.querySelector('.evidence-json');
                if (!evidence || window.integrationFirstPanelSeen) return;
                // Pin the very first panel before opening lazy evidence. Never
                // query a later panel after a healthy poll has replaced it.
                window.integrationFirstPanelSeen = true;
                window.integrationFirstHistory = Boolean(document.querySelector('.history-banner'));
                window.integrationFirstVersion = document.querySelector('.topbar .version')?.textContent;
                window.integrationFoldedEvidence = evidence.textContent;
                observer.disconnect();
                const details = evidence.closest('details');
                details.addEventListener('toggle', () => queueMicrotask(() => {
                  window.integrationFirstWork = JSON.parse(evidence.textContent);
                }), {once:true});
                details.open = true;
              });
              observer.observe(document, {subtree:true, childList:true});
            })();''')

            def control_read(route):
                state['project_reads'] += 1
                # start() establishes r1; loadRoute() then performs this second
                # control read alongside the summary whose response is delayed.
                if state['project_reads'] == 2 and not state['paused']:
                    held.append(route)
                else:
                    route.continue_()

            def summary_read(route):
                state['summary_reads'] += 1
                if state['summary_reads'] != 2:
                    route.continue_()
                    return
                old_response = route.fetch()
                old_work = old_response.json()['current_work']
                assert old_work['identity']['control_revision_id'] == artifact_revision
                collaboration.pause_request(store.project_root, reason='Synthetic pause during initial route read',
                    base_revision=artifact_revision, operation_id='integration-route-pause')
                state['paused'] = True
                for pending in held:
                    pending.fulfill(response=pending.fetch())
                held.clear()
                route.fulfill(response=old_response)

            page.route('**/api/project*', control_read)
            page.route('**/api/view/summary*', summary_read)
            page.goto(server.start() + route_name + '/')
            page.wait_for_function('() => Boolean(window.integrationFirstWork)')
            assert page.evaluate('window.integrationFoldedEvidence') == ''
            rendered = page.evaluate('window.integrationFirstWork')
            paused = store.load_document()
            expected = workbench.workbench_summary(store.project_root, revision=artifact_revision,
                protocol='workbench_summary.v2')['current_work']
            assert state['paused'] and not held
            assert paused['collaboration']['request']['paused'] is True
            assert rendered['identity']['artifact_revision_id'] == artifact_revision
            assert rendered['identity']['control_revision_id'] == paused['revision_id']
            assert rendered['next'] == expected['next']
            assert rendered['next']['action'] != 'handoff'
            assert page.evaluate('window.integrationFirstHistory') is True
            assert page.evaluate('window.integrationFirstVersion') == '历史稿'
            expect(page.locator('.overview [data-current-work]').get_by_role(
                'button', name=expected['next']['label'], exact=True)).to_be_visible()
            assert 'revision=' + artifact_revision in page.url
            assert store.load_document() == paused and not errors
            browser.close()
    finally:
        server.stop()
