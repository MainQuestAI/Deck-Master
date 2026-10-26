"""Isolated fixture replay of external finding closure and explicit reopening."""
import copy
import json
from pathlib import Path

import pytest

from deck_master import review_handoff, content_review, service
from deck_master.store import Store
from deck_master.tasks import _adopt_review
from rc3_fixtures import source_snapshot, authorize_scope, evidence_for, submit_host_fixture
from test_external_review_handoff import record, adopt
from test_workbench_reads import commit

@pytest.mark.parametrize('path', ['direct_r01', 'r02_then_r01_r02'])
def test_public_reopen_preserves_other_closed_findings(tmp_path, path):
    isolated = tmp_path
    project, external = record(Path(isolated))
    imported = adopt(project, external)
    store = Store(project)
    doc = store.load_document()
    owner_ref = imported['review_refs'][0]
    owner = store.read_object_json(owner_ref)
    old_page = doc['pages'][0]['page']
    page = store.read_object_json(old_page)
    page['customer_visible']['body_blocks'][0]['text'] += ' Synthetic restored all six qualifications.'
    new_page = store.put_json_object(page)
    doc['pages'][0]['page'] = new_page
    fixed = copy.deepcopy(owner)
    fixed.update(replaces=owner_ref, status='pass')
    fixed['subjects'] = [new_page if ref == old_page else ref for ref in fixed['subjects']]
    for dep in fixed['dependencies']:
        if dep['kind'] == 'content' and dep['identity'] == 'page:p1':
            dep['sha256'] = new_page['sha256']
    for finding in fixed['findings']:
        finding.update(resolution='fixed', evidence=[new_page])
    commit(store, doc, 'synthetic-repair-page')
    doc = store.load_document()
    fixed_ref = _adopt_review(store, fixed)
    doc['reviews'].append(store.put_json_object(fixed_ref))
    commit(store, doc, 'synthetic-close-all')
    closed_before = [row['closed'] for row in review_handoff.repair_handoff(external_report=external, project=project)['findings']]

    doc = store.load_document()
    reopened = copy.deepcopy(fixed)
    reopened.update(replaces=doc['reviews'][-1], status='fail')
    reopened['findings'] = [reopened['findings'][0 if path == 'direct_r01' else 1]]
    reopened['findings'][0].update(resolution='open', actual='Synthetic recheck demonstrates the qualification remains missing')
    reopened['observations'] = ['Synthetic explicit recheck reopens R01 on exactly the same current manuscript.']
    scope = copy.deepcopy(doc['collaboration']['request']['scope'])
    scope['layers'] = ['review']
    authorize_scope(project, actions=['dispatch.host_task', 'task.start', 'task.accept'], scope=scope,
        max_external_calls=0, max_candidate_count=0, adoption_policy='within_scope',
        evidence=evidence_for(project, text='Synthetic explicit one-page review recheck authorization; no model calls.', locator='synthetic:reopened-review'))
    units = content_review.required_units(store, store.load_document())
    if path == 'direct_r01':
        task = service.open_host_task(store, kind='review', page_ids=['p1'],
            review_stage='preproduction', instruction='Synthetic explicit same-manuscript R01 recheck',
            review_units=[{'kind':kind, 'page_ids':['p1'], 'reason':'missing'} for kind in units])
    else:
        dispatched = content_review.dispatch_preproduction_review(project, page_ids=['p1'], force_units=units,
            instruction='Synthetic explicit same-manuscript R02 recheck omitting R01')
        assert dispatched['status'] == 'review_dispatched'
        task = dispatched['task']
    current = store.load_document()
    subjects = [ref for ref in (current.get('narrative'), current.get('content_plan')) if ref] + [current['pages'][0]['page']]
    deps = [{'kind':'content', 'identity':key, 'sha256':current[key]['sha256']}
            for key in ('narrative','content_plan') if current.get(key)] + [{'kind':'content','identity':'page:p1','sha256':new_page['sha256']}]
    reopened['subjects'], reopened['dependencies'] = subjects, deps
    rows = [reopened]
    for kind in units:
        if kind != reopened['kind']:
            row = copy.deepcopy(reopened)
            row.update(kind=kind, review_id='synthetic-current-' + kind, replaces=None, status='pass', findings=[])
            rows.append(row)
    result = submit_host_fixture(project, task_id=task['task_id'],
        execution_ref='synthetic-r01-recheck',
        host_declaration={'supported_protocols':[task['protocol_version']] if task.get('protocol_version') else [],
                          'capabilities':task.get('required_capabilities') or []},
        result_payload={'kind':'review','files':[],'pages':[],'page_order':[],'artifact_specs':[],
                        'reviews':rows,'usage_events':[],'notes':'Synthetic reopened original finding, no model quality claim'})
    assert result['status'] == 'accepted'

    if path == 'r02_then_r01_r02':
        before_read = source_snapshot(project)
        intermediate = review_handoff.repair_handoff(external_report=external, project=project)
        assert [row['closed'] for row in intermediate['findings']] == [True, False, True, True, True, True]
        assert content_review.preproduction_status(store, store.load_document())['status'] == 'blocked'
        assert before_read == source_snapshot(project)
        current = store.load_document()
        previous_ref = next(ref for ref in reversed(current['reviews'])
                            if (row := store.read_object_json(ref))['review_id'] == owner['review_id']
                            and row['kind'] == owner['kind'])
        dispatched = content_review.dispatch_preproduction_review(project, page_ids=['p1'], force_units=units,
            instruction='Synthetic explicit descendant recheck reopens R01 and R02 after R01 was omitted')
        assert dispatched['status'] == 'review_dispatched'
        task = dispatched['task']
        packets = [store.read_object_json(ref) for ref in task['inputs']]
        packet = next(value for value in packets if value.get('schema_version') == 'content_review_packet.v1')
        frozen_owners = packet['review_scope']['owners']
        assert {'kind': owner['kind'], 'review_ref': previous_ref} in frozen_owners
        rows = []
        for frozen_owner in frozen_owners:
            row = store.read_object_json(frozen_owner['review_ref'])
            row.update(replaces=frozen_owner['review_ref'], subjects=subjects, dependencies=deps,
                       observations=['Synthetic second public recheck under every frozen historical owner.'])
            if row['kind'] == owner['kind']:
                # The root owner still needs its R02 recheck. Only the actual
                # descendant reopens R01, proving traversal across its omission.
                indexes = [0, 1] if frozen_owner['review_ref'] == previous_ref else [1]
                row.update(status='fail', findings=[copy.deepcopy(fixed['findings'][i]) for i in indexes])
                for finding in row['findings']:
                    finding.update(resolution='open', actual='Synthetic qualification remains missing at the current endpoint')
            else:
                row.update(status='pass', findings=[])
            rows.append(row)
        for kind in units:
            if not any(row['kind'] == kind for row in rows):
                row = copy.deepcopy(reopened)
                row.update(kind=kind, review_id='synthetic-second-current-' + kind,
                           replaces=None, status='pass', findings=[])
                rows.append(row)
        result = submit_host_fixture(project, task_id=task['task_id'], execution_ref='synthetic-r01-r02-recheck',
            host_declaration={'supported_protocols': [task['protocol_version']] if task.get('protocol_version') else [],
                              'capabilities': task.get('required_capabilities') or []},
            result_payload={'kind': 'review', 'files': [], 'pages': [], 'page_order': [], 'artifact_specs': [],
                            'reviews': rows, 'usage_events': [], 'notes': 'Synthetic two-step omission/reopen diagnostic only'})
        assert result['status'] == 'accepted'

    before_read = source_snapshot(project)
    handoff = review_handoff.repair_handoff(external_report=external, project=project)
    assert closed_before == [True] * 6
    if path == 'direct_r01':
        assert [row['closed'] for row in handoff['findings']] == [False, True, True, True, True, True]
    else:
        assert [row['closed'] for row in handoff['findings']] == [False, False, True, True, True, True]
    assert not handoff['all_findings_closed']
    assert content_review.preproduction_status(store, store.load_document())['status'] == 'blocked'
    assert before_read == source_snapshot(project)
