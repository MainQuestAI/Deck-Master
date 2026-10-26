"""Synthetic mechanism evidence; no model execution or professional approval."""
import json
from pathlib import Path
from urllib.request import urlopen

import pytest
from jsonschema import Draft202012Validator

from deck_master import cli, service, workbench
from deck_master.web import WorkbenchServer
from test_x3_design_plan_actions import plan_project, production_project


@pytest.mark.parametrize('confirmed', [True, False])
def test_summary_v2_vertical_read_loop(tmp_path, monkeypatch, capsys, confirmed):
    project, store = plan_project(tmp_path, confirmed)
    before = store.load_document()
    before_files = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        raise AssertionError('read attempted dispatch')
    monkeypatch.setattr(service, 'continue_project', forbidden)
    monkeypatch.setattr(service, 'open_host_task', forbidden)
    result = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    schema = json.loads((Path(workbench.__file__).parent / 'resources/contracts/workbench-summary.v2.schema.json').read_text())
    Draft202012Validator(schema).validate(result)
    work = result['current_work']
    assert work['delivery']['state'] == ('completed' if confirmed else 'in_progress')
    assert all(p['stages']['blueprint']['existence'] == 'not_generated' for p in result['pages'])
    assert not any(a['kind'] == 'prepare_stage' for a in work['next']['actions'])
    assert cli.main(['view', '--project', str(project), '--summary', '--summary-protocol', 'workbench_summary.v2', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == result
    server = WorkbenchServer(project)
    url = server.start()
    try:
        with urlopen(url + 'api/view/summary?protocol=workbench_summary.v2') as response:
            assert json.load(response) == result
        with urlopen(url + 'api/view/summary') as response:
            legacy = json.load(response)
        assert legacy['format'] == 'workbench_summary.v1' and 'current_work' not in legacy
    finally:
        server.stop()
    assert store.load_document() == before
    # Service lifetime files are allowed presentation state, never project work.
    for name, value in before_files.items():
        assert (project / name).read_bytes() == value
    assert workbench.workbench_summary(project, protocol='workbench_summary.v2') == result


def test_action_observation_and_negotiation(tmp_path):
    project, store = plan_project(tmp_path)
    before = store.load_document()
    with pytest.raises(workbench.ReadModelError):
        service.continue_project(project, summary_protocol='bad')
    assert store.load_document() == before
    result = service.continue_project(project, summary_protocol='workbench_summary.v2')
    expected = workbench.workbench_summary(project, revision=before['revision_id'], protocol='workbench_summary.v2')
    assert result['current_work'] == expected['current_work']
    assert 'current_work' not in service.continue_project(project)


def test_historical_actions_are_read_only(tmp_path):
    from test_workbench_reads import commit
    project, store = production_project(tmp_path, 'full_deck')
    old = store.load_document()
    commit(store, old, 'new-control-snapshot')
    result = workbench.workbench_summary(project, revision=old['revision_id'], protocol='workbench_summary.v2')
    work = result['current_work']
    assert work['identity']['control_revision_id'] == store.current_revision_id()
    assert work['identity']['artifact_revision_id'] == old['revision_id']
    assert work['next']['action'] == 'read_snapshot' and work['next']['actions'] == []
    assert work['optional']


@pytest.mark.parametrize('skill', ['deck-master', 'deck-content', 'deck-design', 'deck-review'])
def test_four_host_readers_explicitly_negotiate_same_snapshot(tmp_path, skill):
    from deck_master.method_resources import read_skill_methods
    project, store = plan_project(tmp_path)
    old = read_skill_methods(skill, project=project, read_protocol='work_context.v2')
    assert 'current_work' not in old['context']
    result = read_skill_methods(skill, project=project, read_protocol='work_context.v2',
                                summary_protocol='workbench_summary.v2')
    assert result['context']['current_work'] == workbench.workbench_summary(
        project, protocol='workbench_summary.v2')['current_work']


def matrix_project(tmp_path, kind):
    from test_workbench_reads import commit
    from test_outline_review import outline_project
    if kind == 'outline':
        project, store = outline_project(tmp_path)
    else:
        project, store = production_project(tmp_path, 'sample' if kind == 'sample' else 'full_deck')
    doc = store.load_document()
    request = doc['collaboration']['request']
    if kind in ('outline', 'manuscript'):
        request.update(intent='content_only', content_intent='plan_only' if kind == 'outline' else 'write_only')
        request['scope']['layers'] = ['narrative', 'plan', 'page_copy', 'review']
    if kind == 'local_edit':
        request.update(intent='edit', content_intent=None)
        request['scope'].update(subject='pages', page_ids=['p1'], layers=['page_copy', 'review'],
                                allow_page_membership_change=False)
    commit(store, doc, 'synthetic-request-matrix')
    return project, store


@pytest.mark.parametrize('kind', ['outline', 'manuscript', 'sample', 'full_deck', 'local_edit'])
def test_request_matrix_keeps_unrequested_layers_optional(tmp_path, kind):
    project, store = matrix_project(tmp_path, kind)
    before = store.load_document()
    summary = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    work = summary['current_work']
    assert work['scope']['intent'] == before['collaboration']['request']['intent']
    stages = [a for a in work['next']['actions'] if a['kind'] in ('prepare_stage', 'refresh_stage')]
    if kind in ('outline', 'manuscript', 'local_edit'):
        assert stages == []
    elif kind == 'sample':
        assert all(a['layer'] == 'blueprint' for a in stages)
    else:
        assert stages
    if kind == 'outline':
        assert work['next']['action'] == 'review_outline' and work['review']['status'] == 'missing'
        assert summary['page_count'] == 0
    else:
        assert all(p['stages']['blueprint']['existence'] == 'not_generated' for p in summary['pages'])
    assert store.load_document() == before


def test_committed_action_survives_projection_failure(tmp_path, monkeypatch):
    project, store = plan_project(tmp_path)
    def failed(*args, **kwargs):
        raise OSError('unavailable')
    monkeypatch.setattr(workbench, 'workbench_summary', failed)
    result = service.continue_project(project, summary_protocol='workbench_summary.v2')
    assert result['status'] == 'completed'
    assert result['current_work_unavailable']


@pytest.mark.browser
@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('kind', ['outline', 'manuscript', 'sample', 'full_deck', 'local_edit', 'history'])
def test_browser_reads_backend_current_work(tmp_path, route, kind):
    import shutil
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright, expect
    from test_workbench_reads import commit
    project, store = matrix_project(tmp_path, 'full_deck' if kind == 'history' else kind)
    revision = store.current_revision_id()
    if kind == 'history':
        commit(store, store.load_document(), 'synthetic-new-control')
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
            page.goto(url + route + '/#' + urlencode({'project': identity, 'surface': 'overview', 'revision': revision}))
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            work = workbench.workbench_summary(project, revision=revision, protocol='workbench_summary.v2')['current_work']
            dialog = page.get_by_role('dialog')
            expect(dialog.get_by_role('heading', name=work['next']['title'], exact=True)).to_be_visible()
            expect(dialog.get_by_role('button', name=work['next']['label'], exact=True)).to_be_visible()
            page.screenshot(path=str(tmp_path / f'current-work-{route}-{kind}.png'))
            assert errors == [] and store.load_document() == before
            browser.close()
    finally:
        server.stop()

@pytest.mark.parametrize('kind', ['outline', 'manuscript', 'full_deck'])
def test_unresolved_execution_precedes_delivery_or_early_review(tmp_path, kind):
    from deck_master.current_work import project as project_work
    project, store = matrix_project(tmp_path, kind)
    doc = store.load_document()
    summary = workbench.workbench_summary(project)
    action = {'kind': 'verify_execution', 'action_id': 'unknown-original-execution',
              'page_ids': [], 'layer': None, 'enabled': True}
    # Outline-only work may correctly expose no legacy v1 actions; inject the
    # actual unresolved execution fact for this priority-specific scenario.
    summary['next_actions'].update(status='recorded')
    summary['next_actions'].setdefault('actions', []).append(action)
    work = project_work(store, doc, doc, summary)
    assert work['next']['action'] == 'verify_execution'
    assert work['next']['primary_action'] == action
    assert store.load_document() == doc


def test_complete_deck_uses_existing_delivery_authority_without_writes(tmp_path):
    from test_export import _passing_deck
    from deck_master import delivery_eligibility
    project, store = _passing_deck(tmp_path)
    before = {str(p): p.read_bytes() for p in project.rglob('*') if p.is_file()}
    readiness = delivery_eligibility.describe(project)
    assert readiness['status'] == 'ready'
    result = workbench.workbench_summary(project, protocol='workbench_summary.v2')['current_work']
    assert result['delivery']['state'] == 'completed'
    assert result['delivery']['responsible_role'] == 'caller'
    assert result['next']['action'] == 'read_delivery'
    assert readiness['selected_output']['artifact_ref'] in result['delivery']['outputs']
    assert {str(p): p.read_bytes() for p in project.rglob('*') if p.is_file()} == before


@pytest.mark.browser
@pytest.mark.parametrize('route', ['studio', 'v2'])
def test_control_refresh_rebinds_work_without_replacing_fixed_artifact(tmp_path, route):
    import shutil
    from playwright.sync_api import sync_playwright, expect
    from deck_master import collaboration
    project, store = production_project(tmp_path, 'full_deck')
    server = WorkbenchServer(project)
    url = server.start()
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            page.goto(url + route + '/')
            expect(page.get_by_role('heading', name='2 页原图待生成', exact=True)).to_be_visible()
            revision = store.current_revision_id()
            collaboration.pause_request(project, reason='synthetic cross-window pause',
                base_revision=revision, operation_id='reviewer-pause')
            with page.expect_response(lambda response: '/api/project' in response.url):
                page.evaluate("window.dispatchEvent(new Event('focus'))")
            expected = workbench.workbench_summary(project, revision=revision,
                protocol='workbench_summary.v2')['current_work']
            expect(page.get_by_role('heading', name=expected['next']['title'], exact=True)).to_be_visible()
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            dialog = page.get_by_role('dialog')
            expect(dialog.get_by_role('button', name='恢复本次请求', exact=True)).to_be_visible()
            expect(dialog.get_by_role('heading', name=expected['next']['title'], exact=True)).to_be_visible()
            expect(dialog.get_by_role('button', name='查看待补页', exact=True)).to_have_count(0)
            assert 'revision=' + revision in page.url
            browser.close()
    finally:
        server.stop()


@pytest.mark.browser
@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('deliverable', ['deck', 'content'])
def test_completed_primary_action_opens_actual_deliverable(tmp_path, route, deliverable):
    import shutil
    from playwright.sync_api import sync_playwright, expect
    from test_export import _passing_deck
    if deliverable == 'deck':
        project, store = _passing_deck(tmp_path)
    else:
        from test_rc3_studio_control_browser import manuscript_page
        from rc3_fixtures import public_project
        handle = public_project(tmp_path, create_input={'brief': 'Read the requested manuscript', 'title': 'Read output'},
            request_input={'intent': 'content_only', 'content_intent': 'write_only'},
            manuscript={'pages': [manuscript_page('p01', '先核对实际稿件')]})
        project = handle['project']
        from deck_master.store import Store
        store = Store(project)
    before = store.load_document()
    server = WorkbenchServer(project)
    url = server.start()
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            page.goto(url + route + '/')
            page.get_by_role('button', name='阅读本次交付' if deliverable == 'deck' else '阅读本次内容', exact=True).click()
            if deliverable == 'deck':
                expect(page.locator('#runs-files')).to_be_visible()
                expect(page.locator('#runs-tasks')).not_to_be_visible()
            else:
                expect(page.get_by_role('region', name='页面内容')).to_contain_text('先核对真实稿件')
                assert 'page=p01' in page.url and 'layer=content' in page.url
            assert store.load_document() == before
            browser.close()
    finally:
        server.stop()


def test_equal_priority_actions_preserve_existing_layer_order(tmp_path):
    from deck_master.samples import create_gallery_sample
    from deck_master.store import Store
    project = tmp_path / 'layer-order'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    before = store.load_document()
    legacy = workbench.workbench_summary(project)
    work = workbench.workbench_summary(project, protocol='workbench_summary.v2')['current_work']
    legacy_stages = [a for a in legacy['next_actions']['actions'] if a['kind'] == 'prepare_stage']
    current_stages = [a for a in work['next']['actions'] if a['kind'] == 'prepare_stage']
    assert [a['layer'] for a in current_stages] == [a['layer'] for a in legacy_stages]
    assert current_stages[0]['layer'] == 'blueprint'
    assert current_stages[0]['page_ids'] == ['p03', 'p14']
    assert store.load_document() == before
