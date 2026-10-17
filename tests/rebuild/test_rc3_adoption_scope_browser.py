"""Candidate adoption must distinguish request scope from grant scope; L1."""
import shutil
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import collaboration
from deck_master.web import WorkbenchServer
from rc3_fixtures import evidence_for
from test_rc3_candidate_adoption_handoff import trial, grant_adoption

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('batch', [False, True])
@pytest.mark.parametrize('gap', ['page', 'layer', 'intent', 'authorization_only'])
def test_adoption_preview_routes_request_gaps_without_recording_unusable_grant(tmp_path, batch, gap):
    path, store, cid = trial(tmp_path)
    doc = store.load_document()
    request = doc['collaboration']['request']
    if gap == 'authorization_only':
        grant_adoption(path, store, {**request['scope'], 'page_ids': ['p02'], 'layers': ['svg']})
    else:
        scope = {**request['scope']}
        if gap == 'page':
            scope['page_ids'] = ['p02']
        elif gap == 'layer':
            scope['layers'] = ['review']
        collaboration.start_request(path, input={
            'intent': 'review_only' if gap == 'intent' else 'edit', 'scope': scope,
            'replace_request_id': request['request_id'],
            'instruction_evidence': evidence_for(path, text='L1 explicit restricted request; do not widen it.',
                                                 locator='L1:restricted-adoption')},
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    before = store.load_document()
    requests, errors = [], []
    server = WorkbenchServer(path)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 390 if batch else 1440, 'height': 900})
        page.set_default_timeout(5000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda req: requests.append(req.url) if req.method == 'POST' else None)
        try:
            url = server.start()
            page.goto(url)
            page.get_by_role('button', name='查看本次工作与范围', exact=True).wait_for()
            route = dict(parse_qsl(urlsplit(page.url).fragment))
            route.update(revision=before['revision_id'])
            route.update({'surface': 'runs', 'area': 'decisions'} if batch else {
                'surface': 'page', 'page': 'p01', 'layer': 'svg', 'candidate': cid})
            page.goto(url + '#' + urlencode(route))
            root = page.locator('.candidate-batch' if batch else '.candidate-desk')
            if batch:
                root.get_by_role('button', name='选全部候选', exact=True).click()
            root.get_by_role('button', name='预览所选候选的采用影响' if batch else '预览采用这个候选', exact=True).click()
            action = root.get_by_role('button', name='采用所选候选' if batch else '采用这个候选', exact=True)
            if gap == 'authorization_only':
                expect(action).to_be_enabled()
                action.click()
                expect(page.get_by_role('dialog', name='授权采用所选候选')).to_be_visible()
            else:
                expect(root).to_contain_text('请先在“本次工作与范围”明确替换或扩大请求')
                expect(action).to_be_disabled()
                assert page.get_by_role('dialog', name='授权采用所选候选').count() == 0
            assert store.load_document() == before
            assert not any('/collaboration/authorizations' in url or '/candidates/adopt' in url for url in requests)
            assert not errors
        finally:
            browser.close()
            server.stop()
