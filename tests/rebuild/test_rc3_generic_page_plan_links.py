"""S07: synthetic Page adoption keeps derived v2 Plan links current.

These are local protocol fixtures, never human/model quality evidence.
"""
from copy import deepcopy

import pytest

from deck_master import collaboration, collaboration_binding, content_plan, content_production, editing, eligibility, service
from deck_master.models import bump_revision, content_identity
from deck_master.store import ConflictError
from deck_master.store import Store
from deck_master import tasks
from rc3_fixtures import claim_fixture_task, evidence_for
from test_compose_v2_phases import _deck_with_pages


def _imported(tmp_path):
    project = tmp_path / 'project'
    pages = [{
        'schema_version': 'deck_page_package.v2', 'page_id': f'p{i}',
        'customer_visible': {'title': f'Neutral page {i}', 'body_blocks': [
            {'id': 'b1', 'type': 'paragraph', 'text': f'ENGINEERING_ONLY fact {i} token A'}]},
        'speaker_notes': f'Neutral note {i}.\n\nRetain ending.\n',
        'visual_spec': {'intent': 'Neutral local protocol fixture', 'reference_mode': 'new_design'},
    } for i in range(1, 7)]
    service.create(project, brief='ENGINEERING_ONLY retain this six-page manuscript',
                   draft={'pages': pages})
    store = Store(project)
    _request(project, store)
    return project, store


def _request(project, store, *, page_ids=None, layers=None, operation_id='s07-request'):
    document = store.load_document()
    return collaboration.start_request(project, input={
        'intent': 'full_deck', 'content_intent': None,
        'replace_request_id': document['collaboration']['request']['request_id'],
        'scope': {'subject': 'pages', 'page_ids': page_ids or ['p5'],
                  'page_manifest_ref': None, 'external_artifact_ref': None,
                  'layers': layers or ['page_copy', 'speech', 'design', 'blueprint', 'svg', 'review', 'output'],
                  'allow_page_membership_change': False, 'allow_page_order_change': False,
                  'purpose': 'working'},
        'instruction_evidence': evidence_for(project,
            text='ENGINEERING_ONLY edit only selected pages, retain order/notes/mainline; no image calls.',
            locator='L1:S07-bounded-request')},
        base_revision=document['revision_id'], operation_id=operation_id)


def _task(project, store, *, kind='repair', page_id='p5'):
    task = service.open_host_task(store, kind=kind, page_ids=[page_id],
        instruction='ENGINEERING_ONLY change token A to B within the actual Page scope')
    claim_fixture_task(project, task, execution_ref='L1:S07-neutral-host')
    return task


def _envelope(store, task, *, changed=True):
    document = store.load_document()
    entries = {entry['page_id']: entry for entry in document['pages']}
    page = store.read_object_json(entries[task['scope_pages'][0]]['page'])
    if changed:
        page['customer_visible']['body_blocks'][0]['text'] += ' token B'
    return {'kind': task['kind'], 'pages': [page]}


def _accept(project, task, envelope):
    return service.accept_result(project, result_payload=envelope,
        **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')})


def test_imported_six_page_p5_repair_keeps_all_plan_links_current(tmp_path):
    project, store = _imported(tmp_path)
    task = _task(project, store)
    before = store.load_document()
    old_ref = before['content_plan']
    old_plan = store.read_object_json(old_ref)
    old_bytes = store.read_object_bytes(old_ref)
    assert before['narrative'] is None
    assert before['collaboration']['request']['scope']['page_ids'] == ['p5']
    assert before['collaboration']['decisions'] == before['collaboration']['authorizations'] == []
    result = _accept(project, task, _envelope(store, task))
    after = store.load_document()
    plan = store.read_object_json(after['content_plan'])
    assert result['status'] == 'accepted'
    assert [a['page_id'] for a, b in zip(after['pages'], before['pages']) if a['page'] != b['page']] == ['p5']
    assert {link['page_id']: link['page_ref'] for link in plan['page_links']} == {
        entry['page_id']: entry['page'] for entry in after['pages']}
    assert content_plan.projection(store, after)['applicability'] == 'current'
    assert content_production.content_phase_status(store, after)['action'] == 'complete'
    assert after['narrative'] == before['narrative']
    assert after['collaboration'] == before['collaboration']
    assert plan['input'] == old_plan['input']
    assert plan['version'] == old_plan['version'] + 1
    assert plan['previous_ref'] == old_ref and plan['task_id'] == task['task_id']
    assert store.read_object_bytes(old_ref) == old_bytes
    allowed = {'version', 'previous_ref', 'task_id', 'page_links'}
    assert {k: v for k, v in plan.items() if k not in allowed} == {
        k: v for k, v in old_plan.items() if k not in allowed}
    for entry, previous in zip(after['pages'], before['pages']):
        if entry['page_id'] != 'p5':
            assert entry == previous
        assert store.read_object_json(entry['page'])['speaker_notes'] == store.read_object_json(previous['page'])['speaker_notes']
    completed = tasks._lookup_task(after, task['task_id'], store)
    assert completed['status'] == 'completed'
    assert completed['result_refs'] == result['result_refs']
    assert after['content_plan'] in result['result_refs']
    assert _accept(project, task, _envelope_from_result(store, task, result))['status'] == 'already_applied'
    assert store.load_document() == after


def _envelope_from_result(store, task, result):
    return {'kind': task['kind'], 'pages': [store.read_object_json(result['result_refs'][0])]}


def _fixture(tmp_path, mode):
    if mode == 'imported_mapping':
        return _imported(tmp_path)
    project, store = _deck_with_pages(tmp_path)
    _request(project, store, page_ids=['p1'])
    return project, store


def _record_fixture_revision(store, document, description):
    """Explicit historical fixture setup, never presented as a public edit."""
    before = store.load_document()
    updated = bump_revision(deepcopy(document), {'operation_id': description,
        'kind': 'task_update', 'description': 'L1 synthetic setup: ' + description, 'read_set': []})
    store.commit_change(base_revision=before['revision_id'], document=updated, operation_id=description)


def _historical_compose(project, store):
    """An already-dispatched generic carrier; current compose dispatch is v2.

    Only the carrier is recorded by fixture code. The real accept path, current
    Request, Page scope, link refresh and commit are exercised without patches.
    """
    document = store.load_document()
    ids = [e['page_id'] for e in document['pages']]
    task = tasks.new_task(task_id='historical-generic-compose', operation_id='s07-generic-compose',
        kind='compose', scope_pages=ids, instruction='L1 recorded generic Page-only compose task',
        inputs=[e['page'] for e in document['pages']], dependencies=[],
        dispatch_revision=document['revision_id'], produced_against=content_identity(document))
    collaboration_binding.stamp_task(store, document, task, phase='production', executor_type='host',
        page_ids=ids, adoption_policy='within_scope', action='dispatch.host_task',
        action_targets={'page_ids': ids, 'layers': ['page_copy', 'svg']})
    document['tasks'].append(store.put_json_object(task))
    _record_fixture_revision(store, document, 'record-historical-generic-compose')
    claim_fixture_task(project, task, execution_ref='L1:S07-historical-generic-host')
    return task


@pytest.mark.parametrize('mode', ['bound', 'imported_mapping'])
@pytest.mark.parametrize('kind', ['compose', 'repair', 'reconstruct'])
def test_generic_page_adoption_refreshes_only_derived_plan_fields(tmp_path, mode, kind):
    project, store = _fixture(tmp_path, mode)
    pid = 'p5' if mode == 'imported_mapping' else 'p1'
    if kind == 'compose':
        ids = [e['page_id'] for e in store.load_document()['pages']]
        _request(project, store, page_ids=ids, operation_id='s07-full-fixed-membership')
        task = _historical_compose(project, store)
        document = store.load_document()
        pages = [store.read_object_json(e['page']) for e in document['pages']]
        next(p for p in pages if p['page_id'] == pid)['customer_visible']['title'] += ' token B'
        envelope = {'kind': kind, 'pages': pages, 'page_order': ids}
    else:
        task = _task(project, store, kind=kind, page_id=pid)
        envelope = _envelope(store, task)
    before = store.load_document()
    old_plan = store.read_object_json(before['content_plan'])
    result = _accept(project, task, envelope)
    after = store.load_document()
    plan = store.read_object_json(after['content_plan'])
    assert result['status'] == 'accepted'
    assert plan['mode'] == mode and plan['input'] == old_plan['input']
    assert plan['basis'] == old_plan['basis'] and plan['narrative_ref'] == old_plan['narrative_ref']
    assert plan['previous_ref'] == before['content_plan']
    assert plan['task_id'] == task['task_id'] and plan['version'] == old_plan['version'] + 1
    assert {link['page_id']: link['page_ref'] for link in plan['page_links']} == {
        entry['page_id']: entry['page'] for entry in after['pages']}
    assert content_plan.projection(store, after)['applicability'] == 'current'
    assert after['narrative'] == before['narrative'] and after['collaboration'] == before['collaboration']
    assert [e['page_id'] for e in after['pages']] == [e['page_id'] for e in before['pages']]
    assert after['content_plan'] in result['result_refs']


@pytest.mark.parametrize('mode', ['bound', 'imported_mapping'])
def test_unchanged_page_return_does_not_version_plan(tmp_path, mode):
    project, store = _fixture(tmp_path, mode)
    task = _task(project, store, page_id='p5' if mode == 'imported_mapping' else 'p1')
    before = store.load_document()
    result = _accept(project, task, _envelope(store, task, changed=False))
    after = store.load_document()
    assert result['status'] == 'accepted'
    assert after['content_plan'] == before['content_plan']
    assert after['content_plan'] not in result['result_refs']


@pytest.mark.parametrize('mutation', ['remove', 'reorder'])
def test_page_only_generic_compose_cannot_rewrite_plan_membership_or_order(tmp_path, mutation):
    project, store = _imported(tmp_path)
    ids = [e['page_id'] for e in store.load_document()['pages']]
    _request(project, store, page_ids=ids, operation_id='s07-full-fixed-membership')
    task = _historical_compose(project, store)
    before = store.load_document()
    pages = [store.read_object_json(e['page']) for e in before['pages']]
    if mutation == 'remove':
        pages = pages[:-1]
    else:
        pages = pages[::-1]
    envelope = {'kind': 'compose', 'pages': pages, 'page_order': [p['page_id'] for p in pages]}
    with pytest.raises(content_plan.ContentPlanError, match='membership and order'):
        _accept(project, task, envelope)
    assert store.load_document() == before


@pytest.mark.parametrize('failure', ['outside_page', 'editorial_plan', 'missing_page_copy_layer'])
def test_actual_result_scope_is_checked_before_derived_maintenance(tmp_path, failure):
    project, store = _imported(tmp_path)
    if failure == 'missing_page_copy_layer':
        _request(project, store, layers=['blueprint', 'svg'], operation_id='s07-visual-only-request')
        task = _task(project, store, kind='reconstruct')
    else:
        task = _task(project, store)
    envelope = _envelope(store, task)
    if failure == 'outside_page':
        envelope['pages'].append(store.read_object_json(store.load_document()['pages'][3]['page']))
    if failure == 'editorial_plan':
        envelope['content_plan'] = deepcopy(store.read_object_json(store.load_document()['content_plan'])['input'])
        envelope['content_plan']['page_roles'][0]['role'] = 'An unauthorized new editorial role'
    before = store.load_document()
    pointer = (store.deck_root / 'current.json').read_bytes()
    with pytest.raises(eligibility.EligibilityBlocked):
        _accept(project, task, envelope)
    assert store.load_document() == before
    assert (store.deck_root / 'current.json').read_bytes() == pointer
    assert tasks._lookup_task(before, task['task_id'], store)['status'] == 'running'


@pytest.mark.parametrize('mode', ['bound', 'imported_mapping'])
def test_stale_mapping_refuses_whole_adoption_without_healing_old_links(tmp_path, mode):
    project, store = _fixture(tmp_path, mode)
    document = store.load_document()
    plan = store.read_object_json(document['content_plan'])
    page = store.read_object_json(document['pages'][0]['page'])
    page['customer_visible']['title'] += ' historical mismatched link'
    plan['page_links'][0]['page_ref'] = store.put_json_object(page)
    document['content_plan'] = store.put_json_object(plan)
    _record_fixture_revision(store, document, 'record-stale-plan-link')
    task = _task(project, store, page_id='p5' if mode == 'imported_mapping' else 'p1')
    before = store.load_document()
    with pytest.raises(content_plan.ContentPlanError, match='existing mapping is stale'):
        _accept(project, task, _envelope(store, task))
    assert store.load_document() == before
    assert tasks._lookup_task(before, task['task_id'], store)['result_refs'] == []


@pytest.mark.parametrize('basis_change', ['source', 'narrative'])
def test_derived_refresh_does_not_rebase_plan_inputs_or_narrative(tmp_path, basis_change):
    project, store = _fixture(tmp_path, 'bound')
    document = store.load_document()
    if basis_change == 'source':
        document['sources'][0]['original_sha256'] = 'a' * 64
    else:
        narrative = store.read_object_json(document['narrative'])
        narrative['version'] += 1
        narrative['nodes'][0]['statement'] += ' recorded subsequent direction'
        document['narrative'] = store.put_json_object(narrative)
    _record_fixture_revision(store, document, 'record-subsequent-' + basis_change)
    before = store.load_document()
    old_plan = store.read_object_json(before['content_plan'])
    if basis_change == 'source':
        with pytest.raises(eligibility.EligibilityBlocked, match='inputs changed'):
            _task(project, store, page_id='p1')
        assert store.load_document() == before
        assert content_plan.projection(store, before)['applicability'] == 'basis_changed'
        return
    task = _task(project, store, page_id='p1')
    before = store.load_document()
    _accept(project, task, _envelope(store, task))
    after = store.load_document()
    plan = store.read_object_json(after['content_plan'])
    assert plan['input'] == old_plan['input'] and plan['basis'] == old_plan['basis']
    assert plan['narrative_ref'] == old_plan['narrative_ref']
    assert after['sources'] == before['sources'] and after['narrative'] == before['narrative']
    assert content_plan.projection(store, after)['applicability'] == 'basis_changed'


@pytest.mark.parametrize('plan_kind', ['absent', 'v1', 'planned'])
def test_non_bound_plans_are_preserved_without_conversion(tmp_path, plan_kind):
    project, store = _imported(tmp_path)
    document = store.load_document()
    if plan_kind == 'absent':
        document.pop('content_plan')
    else:
        plan = store.read_object_json(document['content_plan'])
        if plan_kind == 'planned':
            plan.update(mode='planned', page_links=[], imported_manuscript=None)
            plan['input']['chapters'] = [{'chapter_id': 'c1', 'title': 'Recorded planned structure',
                                          'page_ids': plan['input']['page_order']}]
        else:
            goals = [{'goal_id': e['page_id'], 'page_id': e['page_id'], 'purpose': 'Historical purpose',
                      'source_links': [], 'unresolved_facts': ['L1 basis unknown']} for e in document['pages']]
            plan = {'schema_version': 'content_plan.v1', 'plan_id': 'historical-v1', 'version': 1,
                'project_id': document['project_id'], 'task_id': 'historical-task', 'origin': 'user_imported',
                'basis': {**plan['basis'], 'produced_against': content_identity(document)}, 'previous_ref': None,
                'input': {'schema_version': 'content_plan_input.v1', 'input_summary': 'Historical mapping',
                    'chapters': [{'chapter_id': 'c1', 'title': 'Historical', 'goal_ids': [g['goal_id'] for g in goals]}],
                    'goals': goals, 'unresolved_facts': ['L1 historical mapping']},
                'page_links': [{'goal_id': e['page_id'], 'page_id': e['page_id'], 'page_ref': e['page']} for e in document['pages']]}
        document['content_plan'] = store.put_json_object(plan)
    _record_fixture_revision(store, document, 'record-' + plan_kind + '-plan')
    task = _task(project, store)
    before = store.load_document()
    result = _accept(project, task, _envelope(store, task))
    after = store.load_document()
    assert result['status'] == 'accepted' and after.get('content_plan') == before.get('content_plan')
    assert len(result['result_refs']) == 1


def test_direct_edit_stays_current_and_supersedes_pending_repair(tmp_path):
    project, store = _imported(tmp_path)
    task = _task(project, store)
    envelope = _envelope(store, task)
    before = store.load_document()
    entry = before['pages'][4]
    result = editing.edit_page(project, page=envelope['pages'][0], base_revision=before['revision_id'],
        page_hash=entry['page']['sha256'], operation_id='s07-direct-edit')
    after = store.load_document()
    assert result['status'] == 'edited'
    assert content_plan.projection(store, after)['applicability'] == 'current'
    assert content_production.content_phase_status(store, after)['action'] == 'complete'
    assert tasks._lookup_task(after, task['task_id'], store)['status'] == 'superseded'
    with pytest.raises(tasks.TaskConflict):
        _accept(project, task, envelope)
    final = store.load_document()
    assert final['pages'] == after['pages'] and final['content_plan'] == after['content_plan']


def test_lost_ack_replays_exact_plan_and_page_after_later_revision(tmp_path, monkeypatch):
    project, store = _imported(tmp_path)
    task = _task(project, store)
    envelope = _envelope(store, task)
    original = tasks.write_operation_journal
    def crash(*args, **kwargs):
        raise SystemExit('L1 crash after real pointer swap')
    monkeypatch.setattr(tasks, 'write_operation_journal', crash)
    with pytest.raises(SystemExit, match='real pointer swap'):
        _accept(project, task, envelope)
    applied = store.load_document()
    expected = applied['change']['operation_receipt']['response']
    assert expected['result_refs'][-1] == applied['content_plan']
    _record_fixture_revision(store, applied, 'later-unrelated-task-revision')
    later = store.load_document()
    monkeypatch.setattr(tasks, 'write_operation_journal', original)
    replay = _accept(project, task, envelope)
    assert replay['status'] == 'already_applied' and replay['operation_result'] == expected
    assert store.load_document() == later
    conflict = deepcopy(envelope)
    conflict['pages'][0]['customer_visible']['title'] += ' conflicting replay'
    with pytest.raises(tasks.TaskConflict, match='different result or request binding'):
        _accept(project, task, conflict)
    assert store.load_document() == later


def test_plan_refresh_and_page_result_remain_inside_existing_cas(tmp_path, monkeypatch):
    project, store = _imported(tmp_path)
    task = _task(project, store)
    before = store.load_document()
    original = Store._commit_locked
    def stale_cas(self, **kwargs):
        if kwargs.get('operation_id') == task['operation_id']:
            raise ConflictError('base_revision', 'L1 actual commit boundary rejects stale CAS')
        return original(self, **kwargs)
    monkeypatch.setattr(Store, '_commit_locked', stale_cas)
    with pytest.raises(ConflictError, match='stale CAS'):
        _accept(project, task, _envelope(store, task))
    assert store.load_document() == before
    assert tasks._lookup_task(before, task['task_id'], store)['status'] == 'running'
