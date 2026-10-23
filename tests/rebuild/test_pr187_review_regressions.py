"""PR187 formal-interface synthetic regressions; no model quality claim."""
import pytest
from deck_master import outline_review, native_review, tasks, workbench
from test_outline_review import outline_project
from test_content_preproduction_review import _deck
from test_rp14_effective_requirements import decision
from test_native_review import FixtureSession, _review_task
from test_x3_design_plan_actions import production_project


@pytest.fixture
def native(monkeypatch):
    FixtureSession.calls, FixtureSession.status = [], 'pass'
    FixtureSession.corrupt, FixtureSession.before_finish = False, None
    monkeypatch.setattr(native_review, 'CodexReviewSession', FixtureSession)
    return FixtureSession


@pytest.mark.parametrize('pages', [False, True])
def test_outline_requirements_cover_plan_roles(tmp_path, pages):
    project, store = (_deck if pages else outline_project)(tmp_path)
    ref = decision(project, store, 'retain-plan-condition', layers=('plan',))
    packet = outline_review.packet(store, store.load_document())
    assert ref in [row['ref'] for row in packet['effective_requirements']['argument']['decisions']]
    assert packet['manuscript'] == {'pages': [], 'page_order': []}
    assert packet['subjects'] == [store.load_document()[key] for key in ('narrative', 'content_plan')]


@pytest.mark.parametrize('pages', [False, True])
def test_outline_accepted_pass_expires_on_requirement(tmp_path, native, pages):
    project, store = (_deck if pages else outline_project)(tmp_path)
    native_review.run(project, subject='outline')
    task = _review_task(store)
    assert outline_review.status(store, store.load_document())['status'] == 'pass'
    decision(project, store, 'new-plan-condition', layers=('plan',))
    assert not tasks.task_inputs_current(store, store.load_document(), task)
    gate = outline_review.status(store, store.load_document())
    assert gate['status'] == 'missing' and gate['production_qualified'] is False
    assert len(native.calls) == 1


def test_old_pass_does_not_mask_ready_recovery(tmp_path, native, monkeypatch):
    from deck_master import service
    project, store = outline_project(tmp_path)
    native_review.run(project, subject='outline')
    import json
    original = native.review
    def recheck(self, prompt, schema):
        observation = original(self, prompt, schema)
        packet = self.calls[-1]['packet']
        owner = packet['review_scope']['owners'][0]
        finding = {'finding_id': 'new-must-fix', 'kind': 'content', 'impact': 'must_fix',
            'resolution': 'open', 'resolution_reason': '', 'page_id': None, 'element_refs': ['node:n1'],
            'message': 'Required condition missing', 'expected': 'retain condition',
            'actual': 'condition missing', 'evidence': packet['subjects']}
        observation['raw_final_message'] = json.dumps({'reviews': [{'kind': 'argument',
            'status': 'fail', 'observations': ['Synthetic rereview'], 'findings': [finding],
            'replaces': owner['review_ref']}]})
        return observation
    monkeypatch.setattr(native, 'review', recheck)
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise OSError('synthetic failure after ready')
        patch.setattr(service, 'accept_result', fail)
        with pytest.raises(OSError):
            native_review.run(project, subject='outline', force_units=['argument'])
    task = _review_task(store)
    before = store.load_document()
    assert outline_review.dispatch(project)['status'] == 'recovery_available'
    assert native_review.run(project, subject='outline')['status'] == 'recovery_available'
    assert store.load_document() == before
    recovered = native_review.recover(project, task_id=task['task_id'])
    assert recovered['model_called'] is False
    assert recovered['preproduction']['status'] == 'blocked'
    assert len(native.calls) == 2


def scoped_project(tmp_path):
    from deck_master import collaboration
    from test_content_preproduction_review import _scope, _instruction
    project, store = production_project(tmp_path, 'full_deck')
    doc = store.load_document()
    collaboration.start_request(project, input={'intent': 'design_trial', 'content_intent': None,
        'instruction_evidence': _instruction(store, 'only-p1'),
        'scope': _scope(subject='pages', page_ids=['p1'], layers=['blueprint'], allow_page_membership_change=False),
        'replace_request_id': doc['collaboration']['request']['request_id']},
        base_revision=doc['revision_id'], operation_id='only-p1-request')
    return project, store


def test_request_action_members_are_scoped_before_aggregation(tmp_path):
    project, store = scoped_project(tmp_path)
    summary = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    legacy = workbench.workbench_summary(project)
    legacy_action = next(a for a in legacy['next_actions']['actions'] if a['kind'] == 'prepare_stage')
    assert legacy_action['page_ids'] == ['p1', 'p2']
    action = next(a for a in summary['current_work']['next']['actions'] if a['kind'] == 'prepare_stage')
    assert action['page_ids'] == ['p1'] and action['object_count'] == 1
    targets = workbench.action_targets(project, action['action_id'], revision=summary['revision_id'])
    assert targets['total'] == 1 and targets['targets'][0]['page_ids'] == ['p1']


def reviewed_production(tmp_path):
    from deck_master import result_reading, eligibility
    from test_eligibility_enforcement import _start, _grant
    project, store = _deck(tmp_path)
    _start(project, store, operation_id='full-production-request')
    _grant(project, store, actions=['dispatch.blueprint', 'allowance.allocate'])
    native_review.run(project)
    doc = store.load_document()
    assert eligibility.evaluate(store, doc, doc, 'dispatch.blueprint',
        {'targets': {'page_ids': ['p1', 'p2'], 'layers': ['blueprint']}})['allowed']
    reading = result_reading.get(project)
    for ref in store.load_document()['tasks']:
        task = store.read_object_json(ref)
        if task.get('result_refs'):
            reading = result_reading.mark(project, project_identity=reading['project_identity'],
                revision=store.current_revision_id(), task_id=task['task_id'],
                result_key=result_reading.key(task), expected_etag=reading['etag'])
    return project, store, reading


def test_passed_read_reviews_do_not_displace_production(tmp_path, native):
    project, store, reading = reviewed_production(tmp_path)
    summary = workbench.workbench_summary(project, reading=reading, protocol='workbench_summary.v2')
    work = summary['current_work']
    assert work['next']['action'] == 'prepare_stage'
    assert work['next']['primary_action']['page_ids'] == ['p1', 'p2']
    assert any(a['kind'] == 'review_quality' for a in work['optional'])


@pytest.mark.parametrize('change', ['narrative_source', 'plan_source', 'version_only', 'unrelated_page'])
def test_outline_source_repair_uses_semantics_at_formal_acceptance(tmp_path, native, monkeypatch, change):
    import json
    from deck_master import models
    from test_content_preproduction_review import _source_link
    from test_workbench_reads import commit
    project, store = _deck(tmp_path)
    original = native.review
    def respond(self, prompt, schema):
        observation = original(self, prompt, schema)
        payload = json.loads(observation['raw_final_message'])
        repair = len(self.calls) > 1
        for row in payload['reviews']:
            row['replaces'] = next((owner['review_ref'] for owner in self.calls[-1]['packet']['review_scope']['owners']
                                   if owner['kind'] == row['kind']), None)
            if row['kind'] != 'argument':
                continue
            row['status'] = 'pass' if repair else 'fail'
            row['findings'] = [{'finding_id': 'source-link', 'kind': 'content', 'impact': 'must_fix',
                'resolution': 'fixed' if repair else 'open', 'resolution_reason': 'Corrected existing source association' if repair else 'Unresolved',
                'page_id': None, 'element_refs': ['node:n1'], 'message': 'Source association incorrect',
                'expected': 'Correct existing source locator', 'actual': 'Missing or incorrect link',
                'evidence': [store.load_document()['narrative'], store.load_document()['content_plan']]}]
        observation['raw_final_message'] = json.dumps(payload)
        return observation
    monkeypatch.setattr(native, 'review', respond)
    native_review.run(project, subject='outline')
    assert outline_review.status(store, store.load_document())['status'] == 'blocked'
    doc = store.load_document()
    narrative, plan = [store.read_object_json(doc[k]) for k in ('narrative', 'content_plan')]
    if change == 'narrative_source':
        narrative['nodes'][0]['source_links'] = [_source_link(store, doc)]
    elif change == 'plan_source':
        plan['input']['page_roles'][0]['source_links'] = [_source_link(store, doc, locator='L2')]
    elif change == 'version_only':
        narrative['version'] += 1
        narrative['previous_ref'] = doc['narrative']
        plan['version'] += 1
        plan['previous_ref'] = doc['content_plan']
    else:
        page = store.read_object_json(doc['pages'][0]['page'])
        page['customer_visible']['title'] += ' unrelated change'
        doc['pages'][0]['page'] = store.put_json_object(page)
    models.validate_narrative_semantics(narrative)
    doc['narrative'] = store.put_json_object(narrative)
    plan['narrative_ref'] = doc['narrative']
    models.validate_content_plan_semantics(plan)
    doc['content_plan'] = store.put_json_object(plan)
    commit(store, doc, 'synthetic-source-repair-' + change)
    if change in ('version_only', 'unrelated_page'):
        with pytest.raises(tasks.EnvelopeError, match='not closed'):
            native_review.run(project, subject='outline')
        assert outline_review.status(store, store.load_document())['status'] == 'blocked'
    else:
        assert native_review.run(project, subject='outline')['preproduction']['status'] == 'pass'
    assert len(native.calls) == 2


@pytest.mark.browser
@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('case', ['scope', 'read_pass'])
def test_scoped_or_read_pass_primary_click(tmp_path, native, route, case):
    import shutil
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright, expect
    from deck_master.web import WorkbenchServer
    if case == 'scope':
        project, store = scoped_project(tmp_path)
    else:
        project, store, _ = reviewed_production(tmp_path)
    before = store.load_document()
    server = WorkbenchServer(project)
    url = server.start()
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            identity = page.request.get(url + 'api/project').json()['project_identity']
            page.goto(url + route + '/#' + urlencode({'project': identity, 'surface': 'overview'}))
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            dialog = page.get_by_role('dialog')
            expect(dialog.get_by_role('heading', name=('1' if case == 'scope' else '2') + ' 页原图待生成', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='查看待补页', exact=True).click()
            if case == 'scope':
                page.wait_for_url('**page=p1*')
                assert 'layer=original_image' in page.url
                expect(page.get_by_role('region', name='页面内容')).to_be_visible()
            else:
                expect(page.get_by_role('heading', name='待办对象', exact=True)).to_be_visible()
                expect(page.locator('.action-target')).to_have_count(2)
                page.locator('.action-target').first.get_by_role('button', name='查看这个对象').click()
                page.wait_for_url('**page=p1*')
            page.screenshot(path=str(tmp_path / f'pr187-{route}-{case}.png'), full_page=True)
            assert not errors and store.load_document() == before
            browser.close()
    finally:
        server.stop()


def test_outline_reader_and_old_incomplete_packet_are_not_retroactive(tmp_path):
    from deck_master import effective_requirements, method_resources
    from synthetic_review_provider import synthetic_context, synthetic_runtime_call
    project, store = outline_project(tmp_path)
    ref = decision(project, store, 'frozen-plan-rule', layers=('plan',))
    task = synthetic_runtime_call(outline_review.dispatch, project, adapter_context=synthetic_context())['task']
    reader = method_resources.read_skill_methods('deck-review', project=project, task_id=task['task_id'], read_protocol='work_context.v2')
    view = reader['context']['effective_requirements']
    assert ref in [row['ref'] for row in view['argument']['decisions']]
    assert effective_requirements.task_requirements_current(store, store.load_document(), task)
    # Exact historical-bug packet: no Page subjects, but p1 requirement omitted.
    old = dict(task)
    old['inputs'] = []
    for item in task['inputs']:
        value = store.read_object_json(item)
        if isinstance(value, dict) and value.get('schema_version') == 'content_review_packet.v1':
            for unit in value['effective_requirements'].values():
                unit['decisions'] = [row for row in unit['decisions'] if row['ref'] != ref]
                unit['review_scope']['page_ids'] = []
            item = store.put_json_object(value)
        old['inputs'].append(item)
    assert not effective_requirements.task_requirements_current(store, store.load_document(), old)


def test_new_effective_requirement_keeps_review_attention(tmp_path, native):
    project, store, reading = reviewed_production(tmp_path)
    decision(project, store, 'new-p1-condition', layers=('page_copy',))
    work = workbench.workbench_summary(project, reading=reading, protocol='workbench_summary.v2')['current_work']
    assert work['review']['status'] == 'missing'
    assert work['next']['action'] == 'review_quality'
    assert any(action['kind'] == 'prepare_stage' for action in work['next']['actions'])
