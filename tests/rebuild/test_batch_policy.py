"""Exercise shipped action policy against actual summary and plan contracts."""
import copy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from deck_master import changes, ui_journal, workbench
from deck_master.samples import create_sample
from deck_master.store import Store

MODULE = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2/batch-policy.js'


def js(expression):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to exercise the shipped batch policy')
    script = 'import {batchExclusion,batchInput} from ' + json.dumps(MODULE.as_uri()) + ';console.log(JSON.stringify(' + expression + '));'
    return json.loads(subprocess.run([node, '--input-type=module', '-e', script], capture_output=True, text=True, check=True).stdout)


@pytest.fixture
def context(tmp_path):
    project = tmp_path / 'batch-policy'
    create_sample(project, page_count=3, readonly=False)
    summary = workbench.workbench_summary(project)
    app = {'info': ui_journal.project_info(project), 'summary': summary, 'latest': summary,
           'route': {'revision': summary['revision_id']}, 'readonly': False,
           'health': {'ui_capabilities': ['ui_draft.v1']}, 'business': {'entries': {'size': 0}}}
    return project, app


@pytest.mark.parametrize(('action', 'ids', 'calls'), [('blueprint', ['p01', 'p03'], 2), ('reconstruct', ['p02', 'p03'], 0)])
def test_actual_summary_builds_server_accepted_exact_scope_without_writes(context, action, ids, calls):
    project, app = context
    store = Store(project)
    before = store.load_document()
    summary = app['summary']
    reference = {'page_id': 'p02', 'revision_id': summary['revision_id'], 'artifact_ref': summary['pages'][1]['stages']['blueprint']['ref']}
    value = js('batchInput(' + ','.join(json.dumps(item) for item in [summary, ids, action, 'Preserve every fact; adjust spacing.', calls, reference]) + ')')
    result = changes.plan(project, input=value)['plan']
    assert [item['page_id'] for item in result['actions']] == ids
    assert all(item['stage'] == action and item['mode'] == 'trial' for item in result['actions'])
    assert result['max_calls'] == calls
    assert result['input']['references'] == ([{**reference, 'role': 'reference'}] if action == 'blueprint' else [])
    assert store.load_document() == before


@pytest.mark.parametrize('case', ['readonly', 'stale_revision', 'unsupported', 'missing_receipts', 'missing_content', 'missing_original', 'changed_original', 'missing_svg', 'unknown_execution', 'unreadable_task', 'pending_receipt', 'reference_is_target'])
def test_eligibility_distinguishes_action_specific_and_recovery_requirements(context, case):
    project, original = context
    app = copy.deepcopy(original)
    page = app['summary']['pages'][0]
    action, reference = 'blueprint', None
    if case == 'readonly':
        app['readonly'] = True
    elif case == 'stale_revision':
        app['latest']['revision_id'] = 'different'
    elif case == 'unsupported':
        next(item for item in app['info']['effective_actions'] if item['action'] == 'changes')['writable'] = False
    elif case == 'missing_receipts':
        app['health']['ui_capabilities'] = []
    elif case == 'missing_content':
        page['stages']['content']['existence'] = 'unreadable'
    elif case == 'missing_original':
        action = 'reconstruct'
        page['stages']['blueprint']['file'] = None
    elif case == 'changed_original':
        action = 'reconstruct'
        page['stages']['blueprint']['applicability']['status'] = 'basis_changed'
    elif case == 'missing_svg':
        action = 'repair'
    elif case == 'unknown_execution':
        page['attention'] = {'items': [{'kind': 'verify_execution'}]}
    elif case == 'unreadable_task':
        app['latest']['unreadable_tasks'] = 1
    elif case == 'pending_receipt':
        app['business']['entries']['size'] = 1
    else:
        action, reference = 'style', {'page_id': page['page_id']}
    expression = 'batchExclusion(' + ','.join(json.dumps(item) for item in [app, page, action, reference]) + ')'
    assert js(expression)
    assert js('batchExclusion(' + ','.join(json.dumps(item) for item in [original, original['summary']['pages'][0], 'blueprint']) + ')') is None
