"""Real service and Chromium: polling must retain an unchanged design preview."""
import shutil
import pytest
from deck_master.web import WorkbenchServer
from deck_master.models import bump_revision
from test_styles import flow  # noqa: F401
from test_design_entry_basis import without_original

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('delayed', [False, True, 'input', 'revision'])
def test_initial_preview_survives_same_snapshot_poll(flow, delayed):
    from playwright.sync_api import sync_playwright, expect
    before = without_original(flow)
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'))
        page = browser.new_page()
        held = []
        try:
            page.goto(server.start() + 'studio/')
            page.locator('.sidebar').get_by_role('button', name='风格校准', exact=True).click()
            panel = page.locator('.initial-design')
            expect(panel).not_to_have_attribute('open', '')
            panel.locator('summary').click()
            preview = panel.get_by_role('button', name='预览无参考初始试作', exact=True)
            submit = panel.get_by_role('button', name='保存并交接初始试作', exact=True)
            basis = panel.get_by_label('本轮制作依据')
            expect(preview).to_be_enabled()
            page.evaluate("""() => {
                window.pollEvents = 0;
                document.querySelector('.shell').addEventListener('summary-refreshed', () => window.pollEvents++);
            }""")
            if delayed:
                def hold(route):
                    held.append((route, route.fetch()))
                    page.evaluate('window.planHeld = true')
                page.route('**/api/design/initial-plan', hold)
            preview.click()
            if delayed:
                page.wait_for_function('() => window.planHeld === true')
            else:
                expect(basis).to_be_visible()
            # Focus uses the production SummaryPoll refresh and real HTTP reads.
            count = page.evaluate('window.pollEvents')
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            page.wait_for_function('(n) => window.pollEvents > n', arg=count)
            if delayed == 'input':
                panel.get_by_label('初始设计要求').fill('Retire pending preview')
            elif delayed == 'revision':
                doc = flow.store.load_document()
                new = bump_revision(doc, {'operation_id':'pending-change', 'kind':'task_update', 'description':'Synthetic pending revision change', 'read_set':[]})
                flow.store.commit_change(base_revision=doc['revision_id'], document=new, operation_id='pending-change')
                count = page.evaluate('window.pollEvents')
                page.evaluate("window.dispatchEvent(new Event('focus'))")
                page.wait_for_function('(n) => window.pollEvents > n', arg=count)
            if delayed:
                route, response = held.pop()
                route.fulfill(response=response)
                # Wait for the preview callback's finally block, not an early
                # absence assertion that could pass before the response lands.
                if delayed == 'input':
                    expect(preview).to_be_enabled()
                if isinstance(delayed, str):
                    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                    expect(basis).to_have_count(0)
                    expect(submit).to_be_disabled()
                    return
            expect(basis).to_be_visible()
            expect(submit).to_be_enabled()
            expect(panel).to_have_attribute('open', '')
            assert flow.store.load_document() == before
            # Changed local requirements retire the prior plan immediately.
            panel.get_by_label('初始设计要求').fill('Changed fixed requirements')
            expect(basis).to_have_count(0)
            expect(submit).to_be_disabled()
            page.unroute('**/api/design/initial-plan')
            preview.click()
            expect(basis).to_be_visible()
            # A genuine immutable revision change retires the fixed plan too.
            doc = flow.store.load_document()
            new = bump_revision(doc, {'operation_id':'poll-change', 'kind':'task_update', 'description':'Synthetic revision change', 'read_set':[]})
            flow.store.commit_change(base_revision=doc['revision_id'], document=new, operation_id='poll-change')
            count = page.evaluate('window.pollEvents')
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            page.wait_for_function('(n) => window.pollEvents > n', arg=count)
            expect(basis).to_have_count(0)
            expect(submit).to_be_disabled()
            expect(preview).to_be_disabled()
        finally:
            browser.close()
            server.stop()
