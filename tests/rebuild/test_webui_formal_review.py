"""PR130 formal review: synthetic Runtime integration and actual Chromium regressions."""
import copy
import json
import shutil
import uuid
from urllib.parse import urlencode

import pytest
from playwright.sync_api import sync_playwright, expect
from deck_master import collaboration, content_insight as ui, method_library_view as library, service, ui_journal
from deck_master.web import WorkbenchServer
from test_compose_v2_phases import (_project, _request, _dispatch, _submit, _framing_narrative,
    _accept_argument, _adopt_direction, _page, _plan_input, _scope, _instruction)
from test_webui_content_insight import candidate, bytes_at
from test_webui_acceptance_matrix import commit_fixture


def test_plan_only_method_preview_matches_real_argument_dispatch(tmp_path):
    project, store = _project(tmp_path)
    commit_fixture(store, lambda d: d.update(tasks=[]), 'isolated-framing-request')
    _request(project, store, content_intent='plan_only', layers=['narrative', 'plan'])
    task = _dispatch(store, phase='framing')
    _submit(project, task, {'narrative': _framing_narrative(store.load_document()['project_id'])}, 'framing')
    before = bytes_at(project)
    value = library.preview(project, {'context': {'mode': 'project', 'revision': store.current_revision_id()},
                                     'selected_resource_ids': ['content-m04']})
    assert bytes_at(project) == before
    # Real continuation supplies argument-only targets; preview must agree.
    service.continue_project(project, selected_resource_ids=['content-m04'])
    tasks = [store.read_object_json(r) for r in store.load_document()['tasks']]
    assert any(t.get('status') == 'awaiting_host' and t.get('collaboration_binding', {}).get('phase') == 'argument' for t in tasks)
    assert value['dispatch_status'] == 'new_content_task_possible'
    assert value['preparation_only'] and value['selection_status'] == 'validated'


def verified_candidate(tmp_path):
    from synthetic_review_provider import synthetic_user_context, synthetic_runtime_call
    project, store = _project(tmp_path)
    commit_fixture(store, lambda d: d['collaboration'].update(authority_policy='verified_user'))
    def verified(function, action, payload, operation):
        declared = _instruction(store, operation)
        declared.update(kind='user_event', transport_receipt_ref=store.put_json_object({'receipt': operation}))
        payload['instruction_evidence'] = declared
        context = synthetic_user_context(store, store.load_document(),
            action_binding=collaboration.write_digest(action, payload), declared=declared)
        return synthetic_runtime_call(function, project, input=payload, adapter_context=context,
            base_revision=store.current_revision_id(), operation_id=operation)
    verified(collaboration.start_request, collaboration.ACTION_REQUEST_START,
        {'intent': 'content_only', 'content_intent': 'plan_only', 'scope': _scope(), 'replace_request_id': None}, 'verified-request')
    _, result = _accept_argument(project, store)
    ref = result['result_refs'][0]
    decision = verified(collaboration.record_decision, collaboration.ACTION_DECISION_RECORD,
        {'topic': 'direction', 'authority_mode': 'direct_user', 'disposition': 'accepted',
         'scope': _scope(layers=['narrative']), 'value': {'selected': ref['sha256']},
         'subject_refs': [{'artifact_kind': 'narrative', 'artifact_ref': ref, 'projection': 'direction'}]}, 'verified-decision')
    return project, store, ref, decision['decision_ref']


def test_verified_existing_decision_adoption_independent_of_new_decision_channel(tmp_path):
    from test_web import _get_json, _post_json
    project, store, ref, decision_ref = verified_candidate(tmp_path)
    before = bytes_at(project)
    admission = ui.argument(project, ref['sha256'])['data']['adoption']
    assert bytes_at(project) == before
    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try:
        token = _get_json(url+'/api/session')[2]['token']
        status, result = _post_json(url+f'/api/projects/{store.load_document()["project_id"]}/collaboration/proposal-adoptions',
            {'base_revision': store.current_revision_id(), 'operation_id': str(uuid.uuid4()),
             'proposal_ref': ref, 'decision_ref': decision_ref, 'write_scope': admission['write_scope']}, token=token, origin=url)
        assert status == 200 and result['status'] == 'accepted'
    finally:
        server.stop()
    assert not admission['can_record_direction_decision']
    assert admission['decision_reason_codes'] == ['authority_channel_unavailable']
    assert admission['can_adopt'] and not admission['needs_decision']
    assert admission['existing_decision_ref'] == decision_ref
    commit_fixture(store, lambda d: d['collaboration'].update(decisions=[]), 'no-covering-decision')
    blocked = ui.argument(project, ref['sha256'])['data']['adoption']
    assert not blocked['can_adopt'] and not blocked['can_record_direction_decision']


def test_atom_source_damage_is_local_and_matches_single_atom_reads(tmp_path):
    project, store = _project(tmp_path); _request(project, store)
    _, out = _accept_argument(project, store); _adopt_direction(project, store, out['result_refs'][0])
    task = _dispatch(store, phase='page_copy'); doc = store.load_document(); page = _page(store, doc, 'p1')
    page['customer_visible']['body_blocks'].append({'id': 'b2', 'type': 'paragraph', 'text': '独立的完好原子'})
    page['content_mapping']['visible_links'].append({'element_ref': 'atom:p1:block:b2:text', 'narrative_node_ids': ['n1'], 'source_links': []})
    # b3 shares b1's broken source, exercising cached failure attribution too.
    page['customer_visible']['body_blocks'].append({'id': 'b3', 'type': 'paragraph', 'text': '同一损坏来源'})
    link = copy.deepcopy(page['content_mapping']['visible_links'][1]); link['element_ref'] = 'atom:p1:block:b3:text'
    page['content_mapping']['visible_links'].append(link)
    _submit(project, task, {'pages': [page], 'page_order': ['p1'], 'plan_input': _plan_input(doc, ['p1'])}, 'page_copy')
    (project/doc['sources'][0]['extract']['path']).write_bytes(b'broken')
    before = bytes_at(project); full = ui.evidence(project, 'p1')
    values = {e['element_ref']: e for e in full['data']['elements']}
    for block, expected in [('b1', 'unreadable'), ('b2', 'recorded'), ('b3', 'unreadable')]:
        atom = f'atom:p1:block:{block}:text'
        single = ui.evidence(project, 'p1', element_ref=atom)['data']['elements'][0]
        assert values[atom] == single
        assert single['mapping_status'] == expected
    assert full['status'] == 'partial' and bytes_at(project) == before


def test_unrelated_broken_narrative_does_not_invent_unreadable_plan(tmp_path):
    project, store, _, ref = candidate(tmp_path)
    _, result = _accept_argument(project, store); other = result['result_refs'][0]
    # Give B a distinct formal current Ref, without a Plan for A.
    narrative = store.read_object_json(other); narrative['narrative_id'] = 'broken-B'
    bad = store.put_json_object(narrative)
    commit_fixture(store, lambda d: d.update(narrative=bad))
    (project/bad['path']).write_bytes(b'broken')
    value = ui.argument(project, ref['sha256'])
    assert value['data']['plan_status'] == 'absent' and value['data']['plans'] == []
    assert any(g['ref'] == bad and g['field'] == 'narrative' for g in value['issues'])
    assert not any(g['ref'] == bad and g['field'] == 'plan' for g in value['issues'])


@pytest.mark.browser
@pytest.mark.parametrize('late_failure', [False, True])
@pytest.mark.parametrize('next_action', ['resource', 'repreview', 'leave'])
def test_method_body_latest_selection_owns_body_status_and_focus(tmp_path, late_failure, next_action):
    project, store, _, _ = candidate(tmp_path); server = WorkbenchServer(project); url = server.start()
    info = ui_journal.project_info(project); held = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox']); page = browser.new_page()
            page.goto(url+'studio/#'+urlencode({'project': info['project_identity'], 'revision': store.current_revision_id(),
                'surface': 'content', 'content_area': 'methods', 'layer': 'content'}))
            page.get_by_label('准备上下文').select_option('independent')
            expect(page.locator('#content-area-methods')).to_contain_text('准备已核对')
            page.locator('label.method-entry').filter(has_text='content-m04 ·').locator('input').click()
            expect(page.get_by_role('button', name='阅读 content-m04', exact=True)).to_be_visible()
            page.locator('label.method-entry').filter(has_text='case-e04-walkthrough ·').locator('input').click()
            expect(page.get_by_role('checkbox', name='E04｜方法讲解与取舍 · 案例', exact=True)).to_be_checked()
            expect(page.get_by_role('button', name='阅读 content-m04', exact=True)).to_be_visible()
            page.route('**/api/method-library/resources/content-m04?*', lambda route: held.append((route, route.fetch())))
            page.get_by_role('button', name='阅读 content-m04', exact=True).click()
            page.get_by_role('button', name='阅读 example-e04-after', exact=True).click()
            body = page.locator('#content-area-methods > section > pre')
            expect(body).not_to_be_empty(); expected = body.inner_text()
            search = page.get_by_role('searchbox', name='筛选方法或案例'); search.focus()
            assert len(held) == 1
            if next_action == 'repreview':
                page.get_by_role('button', name='重新核对准备', exact=True).click()
                expect(page.get_by_role('button', name='阅读 example-e04-after', exact=True)).to_be_visible()
                expected = ''; search.focus()
            elif next_action == 'leave':
                page.get_by_role('button', name='制作总览', exact=True).click()
                expect(page.locator('#content-area-methods')).to_have_count(0)
            route, response = held.pop()
            if late_failure:
                route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': {'code': 'late_resource_error', 'message': '迟到失败不得覆盖'}}))
            else:
                route.fulfill(response=response)
            # Wait until the browser has processed the released response.
            page.wait_for_timeout(150)
            if next_action != 'leave':
                expect(body).to_have_text(expected); expect(search).to_be_focused()
                expect(page.locator('#content-area-methods')).not_to_contain_text('迟到失败不得覆盖')
            else:
                expect(page.locator('#content-area-methods')).to_have_count(0)
                expect(page.locator('main')).not_to_contain_text('迟到失败不得覆盖')
            browser.close()
    finally:
        server.stop()
