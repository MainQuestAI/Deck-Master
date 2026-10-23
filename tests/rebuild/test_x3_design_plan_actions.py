"""Request-scoped plan UI; synthetic fixtures, no production/model calls."""
import shutil
import uuid

import pytest

from deck_master import service, styles, workbench
from test_rc3_design_feasibility import authorized, value


def plan_project(tmp_path, confirmed=True, **kwargs):
    project, store, _ = authorized(tmp_path, **kwargs)
    if confirmed:
        proposed = styles.propose(project, input=value(store, ids=['p1', 'p2']))
        styles.confirm(project, proposal_id=proposed['proposal_id'],
                       base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    return project, store


@pytest.mark.parametrize('confirmed', [False, True])
def test_plan_request_keeps_missing_images_but_never_recommends_production(tmp_path, confirmed):
    project, store = plan_project(tmp_path, confirmed)
    before = store.load_document()
    result = service.continue_project(project)
    assert result['status'] == ('completed' if confirmed else 'needs_input')
    summary = workbench.workbench_summary(project)
    assert len(summary['pages']) == 2
    assert all(p['stages']['blueprint']['existence'] == 'not_generated' for p in summary['pages'])
    assert not any(a['kind'] in ('prepare_stage', 'refresh_stage') for a in summary['next_actions'].get('actions', []))
    assert store.load_document() == before and not before['tasks']


def production_project(tmp_path, kind):
    if kind == 'sample':
        from deck_master import collaboration
        from test_rc3_design_feasibility import evidence, scope
        project, store = plan_project(tmp_path, confirmed=False, actions=('style.trial',),
            request_scope=scope(['p1', 'p2'], layers=['design', 'blueprint']))
        collaboration.grant(project, input={'mode': 'execute', 'actions': ['style.trial'],
            'scope': store.load_document()['collaboration']['request']['scope'],
            'max_external_calls': 1, 'max_candidate_count': 1, 'instruction_evidence': evidence(store)},
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
        return project, store
    from deck_master.store import Store
    from test_rc3_design_recipes import page
    project = tmp_path / 'full-deck'
    service.create(project, brief='Synthetic full deck including images',
        draft={'pages': [page('p1'), page('p2')]}, project_format='workbench.v3')
    return project, Store(project)


@pytest.mark.parametrize('kind', ['sample', 'full_deck'])
def test_actual_production_requests_retain_missing_stage_recommendations(tmp_path, kind):
    project, store = production_project(tmp_path, kind)
    before = store.load_document()
    summary = workbench.workbench_summary(project)
    actions = summary['next_actions']['actions']
    assert any(a['kind'] == 'prepare_stage' and a['layer'] == 'blueprint' and
               set(a['page_ids']) == {'p1', 'p2'} for a in actions)
    assert store.load_document() == before


@pytest.mark.browser
@pytest.mark.parametrize('route', ['studio', 'v2'])
@pytest.mark.parametrize('kind', ['completed_plan', 'incomplete_plan', 'sample', 'full_deck'])
def test_both_workbenches_share_request_scoped_primary_actions(tmp_path, route, kind):
    from urllib.parse import urlencode
    from playwright.sync_api import sync_playwright, expect
    from deck_master.web import WorkbenchServer
    if kind.endswith('_plan'):
        project, store = plan_project(tmp_path, confirmed=kind == 'completed_plan')
    else:
        project, store = production_project(tmp_path, kind)
    before = store.load_document()
    server = WorkbenchServer(project)
    url = server.start()
    try:
        with sync_playwright() as runtime:
            executable = shutil.which('chromium') or shutil.which('chromium-browser')
            browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            info = page.request.get(url + 'api/project').json()
            link = url + route + '/#' + urlencode({'project': info['project_identity'], 'surface': 'overview'})
            page.goto(link)
            if kind.endswith('_plan'):
                label = '查看本次设计方案' if kind == 'completed_plan' else '准备本次设计方案'
                heading = '本次设计方案已完成' if kind == 'completed_plan' else '设计方案准备中'
                expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
                expect(page.get_by_role('heading', name='2 页原图待生成', exact=True)).to_have_count(0)
                page.screenshot(path=str(tmp_path / f'x3-{route}-{kind}-overview.png'), full_page=True)
                page.get_by_role('button', name=label, exact=True).click()
                page.wait_for_url('**surface=style*')
                page.goto(link)
            else:
                expect(page.get_by_role('heading', name='2 页原图待生成', exact=True)).to_be_visible()
            page.get_by_role('button', name='查看本次工作与范围', exact=True).click()
            dialog = page.get_by_role('dialog')
            if kind.endswith('_plan'):
                expect(dialog.get_by_role('button', name=label, exact=True)).to_be_visible()
                expect(dialog.get_by_role('button', name='读取下一工作单', exact=True)).to_have_count(0)
                page.screenshot(path=str(tmp_path / f'x3-{route}-{kind}-control.png'), full_page=True)
                dialog.get_by_role('button', name=label, exact=True).click()
                page.wait_for_url('**surface=style*')
            else:
                expect(dialog.get_by_role('button', name='读取下一工作单', exact=True)).to_be_visible()
            page.screenshot(path=str(tmp_path / f'x3-{route}-{kind}.png'), full_page=True)
            summary = page.request.get(url + 'api/view/summary').json()
            assert all(p['stages']['blueprint']['existence'] == 'not_generated' for p in summary['pages'])
            assert store.load_document() == before and errors == []
            browser.close()
    finally:
        server.stop()
