"""RC3-04 explicit L1 transaction trajectories; no model/human approval claims."""
from copy import deepcopy
import uuid

import pytest

from deck_master import (collaboration, collaboration_migration, content_production,
                         content_review, eligibility, models, service, tasks)
from deck_master.store import Store, StoreError
from rc3_fixtures import (authorize_scope, claim_fixture_task, claimed_phase_task,
                         evidence_for, historical_snapshot, source_snapshot)
from test_compose_v2_phases import _deck_with_pages, _submit, _page


def operation():
    return str(uuid.uuid4())


def revision_task(project, store, *, adoption_policy='within_scope'):
    task = content_production.build_phase_task(store, store.load_document(),
        operation_id=operation(), intent='input_revision', adoption_policy=adoption_policy)
    doc = store.load_document()
    changed = models.bump_revision(doc, {'operation_id': operation(), 'kind': 'task_update',
        'description': 'explicit L1 reconciliation dispatch', 'read_set': []})
    changed['tasks'].append(store.put_json_object(task))
    store.commit_change(base_revision=doc['revision_id'], document=changed,
                        operation_id=changed['change']['operation_id'])
    claim_fixture_task(project, task, execution_ref='L1-reconciliation-author')
    return task


def four_layers(store, task):
    doc = store.load_document()
    old = store.read_object_json(doc['pages'][0]['page'])
    narrative = deepcopy(store.read_object_json(doc['narrative']))
    narrative['version'] += 1
    narrative['previous_ref'] = doc['narrative']
    narrative['nodes'][0]['statement'] += '（本轮明确限定）'
    narrative_ref = store.put_json_object(narrative)
    page = deepcopy(old)
    page['customer_visible']['body_blocks'][0]['text'] += ' 本轮只改此处规则表述。'
    page['content_mapping']['narrative_ref'] = narrative_ref
    speech = deepcopy(old)
    speech['speaker_notes'] = '先说明规则，再复述限定；这是预计口播，未实测。'
    speech['content_mapping']['speech_segments'] = [{'segment_id': 'revised', 'start_codepoint': 0,
        'end_codepoint': len(speech['speaker_notes']), 'narrative_node_ids': ['n1'],
        'kind': 'cue', 'estimated_seconds': 18}]
    plan = deepcopy(store.read_object_json(doc['content_plan'])['input'])
    plan['page_roles'][0]['intended_takeaway'] += '；明确本轮限定'
    proposals = [{'layer': layer, 'ref': store.put_json_object(obj)}
                 for layer, obj in [('narrative', narrative), ('plan', plan), ('page_copy', page), ('speech', speech)]]
    # Narrative is global: explicitly provide the retained second page's mapping.
    for entry in doc['pages'][1:]:
        other = deepcopy(store.read_object_json(entry['page']))
        other['content_mapping']['narrative_ref'] = narrative_ref
        proposals.append({'layer': 'page_copy', 'ref': store.put_json_object(other)})
    return {'changed_layers': ['narrative', 'plan', 'page_copy', 'speech'], 'proposals': proposals,
            'diff': {'input_digest': task['input_digest'], 'summary': '四层真实消费并统一依据',
                     'changed_page_ids': [entry['page_id'] for entry in doc['pages']]}}, narrative_ref


def test_four_layers_are_consumed_in_one_content_revision_and_replay(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = revision_task(project, store)
    payload, narrative_ref = four_layers(store, task)
    before = store.load_document()
    out = _submit(project, task, payload, 'input_revision')
    after = store.load_document()
    assert after['parent_revision_id'] == before['revision_id']
    assert after['narrative'] == narrative_ref
    pages = [store.read_object_json(entry['page']) for entry in after['pages']]
    assert '本轮只改此处' in pages[0]['customer_visible']['body_blocks'][0]['text']
    assert pages[0]['speaker_notes'].startswith('先说明规则')
    assert all(page['content_mapping']['narrative_ref'] == narrative_ref for page in pages)
    plan = store.read_object_json(after['content_plan'])
    assert plan['narrative_ref'] == narrative_ref
    assert '本轮限定' in plan['input']['page_roles'][0]['intended_takeaway']
    assert [link['page_ref'] for link in plan['page_links']] == [entry['page'] for entry in after['pages']]
    assert after['content_basis']['resolved_by_task_id'] == task['task_id']
    assert out['adopted'] is True and set(out['changed_layers']) == {'narrative', 'plan', 'page_copy', 'speech'}
    replay = _submit(project, task, payload, 'input_revision')
    assert replay['status'] == 'already_applied' and store.current_revision_id() == after['revision_id']


@pytest.mark.parametrize('bad', ['duplicate_plan', 'wrong_speech_body', 'missing_mapping', 'wrong_plan_order'])
def test_any_bad_layer_rolls_back_all_four_pointers_and_basis(tmp_path, bad):
    project, store = _deck_with_pages(tmp_path)
    task = revision_task(project, store)
    payload, _ = four_layers(store, task)
    if bad == 'duplicate_plan':
        payload['proposals'].append(next(row for row in payload['proposals'] if row['layer'] == 'plan'))
    else:
        layer = 'speech' if bad == 'wrong_speech_body' else ('plan' if bad == 'wrong_plan_order' else 'page_copy')
        proposal = next(row for row in payload['proposals'] if row['layer'] == layer)
        obj = store.read_object_json(proposal['ref'])
        if bad == 'wrong_speech_body':
            obj['customer_visible']['title'] += ' smuggled'
        elif bad == 'wrong_plan_order':
            obj['page_order'] = ['not-a-resulting-page']
        else:
            obj.pop('content_mapping')
        proposal['ref'] = store.put_json_object(obj)
    before = store.load_document()
    with pytest.raises((models.ModelError, StoreError)):
        _submit(project, task, payload, 'input_revision')
    assert store.load_document() == before
    assert tasks._lookup_task(before, task['task_id'], store)['status'] == 'running'


def test_proposal_only_does_not_clear_reconciliation_or_adopt_any_layer(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = revision_task(project, store, adoption_policy='proposal_only')
    payload, _ = four_layers(store, task)
    before = store.load_document()
    result = _submit(project, task, payload, 'input_revision')
    after = store.load_document()
    assert result['adopted'] is False and result['proposal_refs']
    for field in ('narrative', 'content_plan', 'pages', 'content_basis', 'outputs'):
        assert after.get(field) == before.get(field)


def test_notes_only_update_keeps_page_copy_author_in_independence_set(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    doc = store.load_document()
    authors = content_review.author_execution_refs(store, doc, [doc['pages'][0]['page']])
    assert authors
    task = claimed_phase_task(store, doc, operation_id=operation(), phase='speech', page_ids=['p1'])
    content_production._stamp_speech_kind(store, task, 'cue')
    notes = '仅替换这一页备注；正文仍由前一作者完成。'
    _submit(project, task, {'updates': [{'page_id': 'p1', 'page_ref': doc['pages'][0]['page'],
        'speaker_notes': notes, 'speech_segments': [{'segment_id': 's', 'start_codepoint': 0,
        'end_codepoint': len(notes), 'narrative_node_ids': ['n1'], 'kind': 'cue', 'estimated_seconds': 13}]}]}, 'speech')
    current = store.load_document()
    assert authors <= content_review.author_execution_refs(store, current, [current['pages'][0]['page']])


def test_default_new_and_manuscript_import_have_real_entry_control_without_grant(tmp_path):
    project = tmp_path / 'current'
    result = service.create(project, brief='explicit L1 public create')
    store = Store(project); doc = store.load_document()
    assert doc['compatibility']['minimum_writer'] == 'rc3-entry.v1'
    assert doc['collaboration']['request']['instruction_evidence']['source_ref']
    assert doc['collaboration']['authorizations'] == []
    order = result['pending_tasks'][0]
    assert order['protocol_version'] == 'compose.v2' and 'rc3-entry.v1' in order['required_capabilities']
    assert order['collaboration_binding']['eligibility_digest']
    before = source_snapshot(project)
    with pytest.raises(Exception, match='requires compose.v2'):
        service.task_start(project, task_id=order['task_id'], execution_ref='old-host',
            supported_protocols=['compose.v1'], capabilities=[])
    assert source_snapshot(project) == before
    claim_fixture_task(project, order)
    imported = tmp_path / 'manuscript'
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': '原始稿件', 'body_blocks': []},
        'speaker_notes': '保留完整原始备注。',
        'visual_spec': {'intent': 'fixed imported manuscript', 'reference_mode': 'new_design'}}
    service.import_draft(imported, draft_payload={'pages': [page]})
    doc = Store(imported).load_document()
    assert not doc['tasks'] and not doc.get('narrative')
    plan = Store(imported).read_object_json(doc['content_plan'])
    assert plan['mode'] == 'imported_mapping' and plan['imported_manuscript']['source_ref']
    assert Store(imported).read_object_json(doc['pages'][0]['page'])['speaker_notes'] == page['speaker_notes']


def test_rank12_without_region_is_not_a_migration_and_unreadable_tasks_do_not_vanish(tmp_path):
    fixture = historical_snapshot(tmp_path, scenario='fixed rank12 no control', minimum_writer='rc3.v1')
    project = fixture['project']; store = Store(project)
    description = collaboration_migration.describe(project)
    assert description['plan']['needs_migration']
    doc = store.load_document()
    bad = {'path': '.deckmaster/objects/' + 'f' * 2 + '/' + 'f' * 64 + '.json', 'sha256': 'f' * 64}
    changed = models.bump_revision(doc, {'operation_id': operation(), 'kind': 'task_update',
        'description': 'explicit unreadable historical Task fact', 'read_set': []})
    changed['tasks'] = [bad]
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id=changed['change']['operation_id'])
    desc = collaboration_migration.describe(project)
    assert desc['plan']['unknown_calls'] is None and desc['plan']['unreadable_task_refs'] == [bad]
    before = store.load_document()
    with pytest.raises(StoreError, match='unreadable Task'):
        collaboration_migration.apply(project, base_revision=before['revision_id'],
            plan_digest=desc['plan_digest'], operation_id=operation())
    assert store.load_document() == before


def test_running_stale_result_settles_actual_call_fact_before_business_refusal(tmp_path):
    from test_eligibility_enforcement import _project, _start, _grant, _settle_preproduction
    project, store = _project(tmp_path)
    _start(project, store)
    _settle_preproduction(store, seed='L1-late-call-content-basis')
    _grant(project, store, actions=['dispatch.host_task', 'allowance.allocate', 'call.begin'], max_external_calls=1)
    task = service.open_host_task(store, kind='repair', page_ids=['p1'], instruction='L1 actual in-flight fact before stale result')
    claim_fixture_task(project, task, execution_ref='L1-late-host')
    tasks.allocate_call_allowances(store, task_id=task['task_id'], count=1)
    tasks.call_begin(store, task_id=task['task_id'], allowance_id='call-1', execution_ref='L1-late-host')
    doc = store.load_document()
    changed = models.bump_revision(doc, {'operation_id': operation(), 'kind': 'task_update',
        'description': 'explicit L1 concurrent source basis change with running Task', 'read_set': []})
    changed['task']['audience'] = 'changed actual basis'
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id=changed['change']['operation_id'])
    staged = store.staging_dir / task['operation_id']; staged.mkdir(parents=True, exist_ok=True)
    report = b'{"fixture":"observed one tool invocation; synthetic L1, no real model charge claim"}'
    (staged / 'call.json').write_bytes(report)
    envelope = {'kind': 'repair',
        'files': [{'file_id': 'call', 'path': 'call.json', 'media_type': 'application/json'}],
        'usage_events': [{'allowance_id': 'call-1', 'outcome': 'consumed', 'invocation_ref': 'L1-call', 'evidence_file_ids': ['call']}]}
    before = store.load_document()
    assert tasks._lookup_task(before, task['task_id'], store)['status'] == 'running'
    assert not tasks.task_inputs_current(store, before, tasks._lookup_task(before, task['task_id'], store))
    with pytest.raises(tasks.StaleInputContext):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], result_payload=envelope)
    after = store.load_document()
    assert after['pages'] == before['pages'] and after.get('narrative') == before.get('narrative')
    assert after['parent_revision_id'] == before['revision_id']
    fact = tasks._lookup_task(after, task['task_id'], store)['call_allowances'][0]
    assert fact['state'] == 'consumed' and fact['invocation_ref'] == 'L1-call'
    assert fact['evidence_level'] == 'host_reported' and store.read_object_bytes(fact['evidence'][0]) == report


@pytest.mark.parametrize('trial', [False, True])
def test_current_v2_editorial_rewrite_uses_atomic_protocol_and_candidate_when_requested(tmp_path, trial):
    from deck_master import content_ops, candidates
    project, store = _deck_with_pages(tmp_path)
    doc = store.load_document()
    scope = {**doc['collaboration']['request']['scope'], 'page_ids': ['p1'],
        'layers': ['page_copy', 'plan'], 'allow_page_membership_change': False,
        'allow_page_order_change': False}
    evidence = evidence_for(project, text='L1 synthetic bounded rewrite; preserve this page and notes', locator='L1:editorial')
    collaboration.record_decision(project, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'direct_user', 'value': 'Explicit L1 rewrite of selected visible copy only',
        'scope': scope, 'instruction_evidence': evidence, 'subject_refs': []},
        base_revision=store.current_revision_id(), operation_id=operation())
    authorize_scope(project, actions=['content.operation', 'candidate.adopt'], scope=scope,
        max_external_calls=0, max_candidate_count=1, adoption_policy='within_scope', evidence=evidence)
    doc = store.load_document()
    request = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'],
        'base_revision': doc['revision_id'], 'content_plan_ref': doc['content_plan'], 'action': 'rewrite',
        'targets': [{'page_id': 'p1', 'page_ref': doc['pages'][0]['page']}],
        'instruction': 'Explicit L1 selected-page rewrite with actual current Plan', 'mode': 'trial' if trial else 'auto'}
    planned = content_ops.plan(project, input=request)
    committed = content_ops.commit(project, plan_id=planned['plan_id'], base_revision=doc['revision_id'], operation_id=operation())['operation_result']
    task = tasks._lookup_task(store.load_document(), committed['task_ids'][0], store)
    assert task['protocol_version'] == 'compose.v2' and task['content_operation_ref']
    claim_fixture_task(project, task)
    doc = store.load_document()
    page = deepcopy(store.read_object_json(doc['pages'][0]['page']))
    page['customer_visible']['title'] += '：明确下一动作'
    plan_input = deepcopy(store.read_object_json(doc['content_plan'])['input'])
    payload = {'changed_layers': ['page_copy', 'plan'],
        'proposals': [{'layer': 'page_copy', 'ref': store.put_json_object(page)},
                      {'layer': 'plan', 'ref': store.put_json_object(plan_input)}],
        'diff': {'input_digest': task['input_digest'], 'summary': 'Only the selected title gains its next action',
                 'changed_page_ids': ['p1'], 'removed_page_ids': [], 'page_order': ['p1']}}
    before = store.load_document()
    result = _submit(project, task, payload, 'input_revision')
    if trial:
        assert result['status'] == 'candidate_ready'
        assert store.load_document()['pages'] == before['pages']
        assert store.load_document()['content_plan'] == before['content_plan']
        replay = _submit(project, task, payload, 'input_revision')
        assert replay['status'] == 'already_applied'
        selection = candidates.plan(project, input={'schema_version': 'candidate_selection.v1',
            'project_id': before['project_id'], 'base_revision': store.current_revision_id(),
            'candidate_ids': result['candidate_ids']})['plan']
        candidates.adopt(project, input=selection, base_revision=selection['base_revision'], operation_id=operation())
    after = store.load_document()
    assert '明确下一动作' in store.read_object_json(after['pages'][0]['page'])['customer_visible']['title']
    assert store.read_object_json(after['content_plan'])['schema_version'] == 'content_plan.v2'
    assert store.read_object_json(after['content_plan'])['page_links'][0]['page_ref'] == after['pages'][0]['page']


@pytest.mark.parametrize('action', ['merge', 'split'])
@pytest.mark.parametrize('trial', [False, True])
def test_derived_pages_admit_only_the_frozen_source_scope_and_preserve_lineage(tmp_path, action, trial):
    from deck_master import content_ops, candidates
    from test_compose_v2_phases import (_project, _request, _accept_argument, _adopt_direction,
                                       _dispatch, _plan_input)
    project, store = _project(tmp_path)
    _request(project, store, intent='full_deck', content_intent=None)
    _, argument = _accept_argument(project, store)
    _adopt_direction(project, store, argument['result_refs'][0])
    initial = _dispatch(store, phase='page_copy')
    doc = store.load_document()
    original_ids = ['p1', 'p2', 'p3']
    _submit(project, initial, {'pages': [_page(store, doc, pid) for pid in original_ids],
        'page_order': original_ids, 'plan_input': _plan_input(doc, original_ids)}, 'page_copy')
    doc = store.load_document()
    selected = ['p1', 'p2'] if action == 'merge' else ['p1']
    scope = {**doc['collaboration']['request']['scope'], 'page_ids': selected,
        'layers': ['page_copy', 'plan'], 'allow_page_membership_change': True,
        'allow_page_order_change': False}
    evidence = evidence_for(project, text='Explicit L1 bounded derivation; retain all unselected pages',
        locator='L1:bounded-' + action)
    collaboration.record_decision(project, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'direct_user', 'value': 'L1 bounded source-page derivation',
        'scope': scope, 'instruction_evidence': evidence, 'subject_refs': []},
        base_revision=store.current_revision_id(), operation_id=operation())
    authorize_scope(project, actions=['content.operation', 'candidate.adopt'], scope=scope,
        max_external_calls=0, max_candidate_count=1, adoption_policy='within_scope', evidence=evidence)
    doc = store.load_document()
    request = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'],
        'base_revision': doc['revision_id'], 'content_plan_ref': doc['content_plan'], 'action': action,
        'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page']} for entry in doc['pages']
                    if entry['page_id'] in selected],
        'instruction': 'L1 replace only the selected sources with fresh identities; no image calls',
        'mode': 'trial' if trial else 'auto'}
    plan = content_ops.plan(project, input=request)
    response = content_ops.commit(project, plan_id=plan['plan_id'], base_revision=doc['revision_id'],
        operation_id=operation())['operation_result']
    task = tasks._lookup_task(store.load_document(), response['task_ids'][0], store)
    claim_fixture_task(project, task)
    doc = store.load_document()
    added = ['derived-1'] if action == 'merge' else ['derived-1', 'derived-2']
    retained = [pid for pid in original_ids if pid not in selected]
    result_order = added + retained
    outline = _plan_input(doc, result_order)
    original_outline = store.read_object_json(doc['content_plan'])['input']
    outline['page_budget'] = deepcopy(original_outline['page_budget'])
    outline['time_budget'] = deepcopy(original_outline['time_budget'])
    proposals = [{'layer': 'page_copy', 'ref': store.put_json_object(_page(store, doc, pid))} for pid in added]
    proposals.append({'layer': 'plan', 'ref': store.put_json_object(outline)})
    payload = {'changed_layers': ['page_copy', 'plan'], 'proposals': proposals,
        'diff': {'input_digest': task['input_digest'], 'summary': 'L1 bounded derivation with retained facts',
                 'changed_page_ids': added + selected, 'removed_page_ids': selected, 'page_order': result_order}}
    before = store.load_document()
    # Changing an unselected current page still refuses the whole transaction.
    escaped = deepcopy(payload)
    escaped_page = _page(store, doc, 'p3', title='unselected content escape')
    escaped['proposals'].append({'layer': 'page_copy', 'ref': store.put_json_object(escaped_page)})
    escaped['diff']['changed_page_ids'].append('p3')
    with pytest.raises((models.ModelError, StoreError)):
        _submit(project, task, escaped, 'input_revision')
    assert store.load_document() == before
    changed_budget = deepcopy(payload)
    relaxed = deepcopy(outline)
    relaxed['page_budget']['max'] = 99
    changed_budget['proposals'][-1]['ref'] = store.put_json_object(relaxed)
    with pytest.raises((models.ModelError, StoreError)):
        _submit(project, task, changed_budget, 'input_revision')
    assert store.load_document() == before
    result = _submit(project, task, payload, 'input_revision')
    if trial:
        assert result['status'] == 'candidate_ready' and store.load_document()['pages'] == before['pages']
        selection = candidates.plan(project, input={'schema_version': 'candidate_selection.v1',
            'project_id': before['project_id'], 'base_revision': store.current_revision_id(),
            'candidate_ids': result['candidate_ids']})['plan']
        candidates.adopt(project, input=selection, base_revision=selection['base_revision'], operation_id=operation())
    after = store.load_document()
    assert [entry['page_id'] for entry in after['pages']] == result_order
    for entry in before['pages']:
        if entry['page_id'] in retained:
            assert next(row for row in after['pages'] if row['page_id'] == entry['page_id']) == entry
    revised = store.read_object_json(after['content_plan'])
    assert revised['input']['page_budget'] == original_outline['page_budget']
    assert revised['input']['time_budget'] == original_outline['time_budget']
    lineage = store.read_object_json(after['page_derivations'][-1])
    assert lineage['source_pages'] == request['targets'] and lineage['source_revision'] == request['base_revision']
    assert {entry['page_id'] for entry in lineage['result_pages']} == set(added)
    assert tasks._lookup_task(after, task['task_id'], store).get('call_allowances', []) == []


def test_completed_content_request_stops_and_next_request_starts_without_replacement(tmp_path):
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': '固定稿件', 'body_blocks': []},
        'visual_spec': {'intent': 'fixed input for explicit L1 completion', 'reference_mode': 'new_design'}}
    project = tmp_path / 'complete'
    service.create(project, brief='Return only this fixed visible manuscript', draft={'pages': [page]},
        request_input={'intent': 'content_only', 'content_intent': 'write_only'})
    store = Store(project); doc = store.load_document()
    assert doc['collaboration']['request']['closed'] is True
    assert doc['collaboration']['request']['closed_reason'] == 'completed'
    assert service.continue_project(project)['status'] == 'completed'
    assert service.continue_project(project)['revision_id'] == doc['revision_id']
    result = collaboration.start_request(project, input={'intent': 'review_only', 'content_intent': None,
        'scope': {**doc['collaboration']['request']['scope'], 'layers': ['review']},
        'instruction_evidence': {'kind': 'host_attested_instruction', 'text': 'L1 next request: inspect fixed copy only'}},
        base_revision=doc['revision_id'], operation_id=operation())
    assert result['status'] == 'accepted'
    assert not store.load_document()['tasks'] and not store.load_document()['collaboration']['authorizations']


def test_external_independent_import_requires_exact_protected_completion(tmp_path):
    from deck_master import review_import, review_evidence
    from synthetic_review_provider import SyntheticProvider
    from test_rc3_collaboration_adapters import imported_project, external_packet_for_page
    project = imported_project(tmp_path)
    store = Store(project)
    external = external_packet_for_page(tmp_path, project)
    for review in external['report']['reviews']:
        review['reviewer'].update(type='independent_host', execution_ref='L1-external-independent',
                                  independence_confirmed=True)
    external['report_sha256'] = models.sha256_bytes(models.canonical_json_bytes(external['report']))
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    evidence = {'kind': 'host_attested_instruction', 'text': 'L1 explicitly imports this fixed external review'}
    before = store.load_document()
    with pytest.raises(review_evidence.EvidenceRejected):
        review_import.import_report(project, external_report=external, source_bindings=bindings,
            evidence=evidence, base_revision=before['revision_id'], operation_id=operation())
    assert store.load_document() == before
    registry = review_evidence.ProviderRegistry(); provider = SyntheticProvider(); registry.register(provider)
    binding = review_evidence.external_review_binding(store, before, before, external, bindings)
    selector = provider.issue('external-completion', {**binding, 'executor_ref': 'L1-external-independent'},
                              'independent_review_receipts')
    with review_evidence.ProviderRuntime(registry).bound():
        context = registry.external_review_context(store, external_report=external,
            source_bindings=bindings, selector=selector)
        result = review_import.import_report(project, external_report=external, source_bindings=bindings,
            evidence=evidence, base_revision=before['revision_id'], operation_id=operation(), adapter_context=context)
    record = store.read_object_json(result['review_refs'][0])
    assert record['reviewer']['assurance'] == 'host_attested'
    proof = store.read_object_json(record['reviewer']['evidence_ref'])
    assert proof['claims']['result_sha256'] == external['report_sha256']
    assert store.read_object_bytes(proof['raw_event_ref']) == provider.events[selector['event_id']]
    assert record['status'] == 'needs_review'  # real protected provenance alone is never a PASS
