"""Synthetic public-API regressions; not model or independent-review evidence."""
import uuid

import pytest

from deck_master import collaboration, content_ops, content_production, eligibility, service
from deck_master.store import Store
from rc3_fixtures import authorize_scope, evidence_for, source_snapshot
from test_content_ops import value


def setup_edit(tmp_path, *, layers=None, page_ids=("p1",), membership=False):
    project = tmp_path / 'edit'
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'Unvalidated pilot', 'body_blocks': []},
        'visual_spec': {'intent': 'Synthetic fixed manuscript', 'reference_mode': 'new_design'}}
    service.create(project, brief='Synthetic content only, no production', draft={'pages': [{**page, 'page_id': pid} for pid in page_ids]},
        request_input={'intent': 'content_only', 'content_intent': 'write_only'})
    store = Store(project)
    scope = {**store.load_document()['collaboration']['request']['scope'], 'layers': layers or ['page_copy', 'plan'],
        'allow_page_membership_change': membership, 'allow_page_order_change': False}
    evidence = evidence_for(project, text='Synthetic bounded copy edit, retain unvalidated qualifier', locator='L1:edit')
    collaboration.start_request(project, input={'intent': 'edit', 'content_intent': None,
        'scope': scope, 'instruction_evidence': evidence}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    return project, store, scope, evidence


def status(store):
    before = source_snapshot(store.project_root)
    result = content_production.completion_status(store, store.load_document())
    assert source_snapshot(store.project_root) == before
    return result


def allow(project, store, scope, evidence):
    collaboration.record_decision(project, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'direct_user', 'value': 'Synthetic fixture direction, not real approval',
        'scope': scope, 'instruction_evidence': evidence, 'subject_refs': []},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    return authorize_scope(project, actions=['content.operation'], scope=scope,
        max_external_calls=0, max_candidate_count=0, adoption_policy='within_scope', evidence=evidence)


def test_rejected_edit_projects_exact_direction_gap_and_next_owner(tmp_path):
    project, store, scope, _ = setup_edit(tmp_path)
    planned = content_ops.plan(project, input=value(store, ids=('p1',)))
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked, match='direction') as caught:
        content_ops.commit(project, plan_id=planned['plan_id'], base_revision=before['revision_id'], operation_id=str(uuid.uuid4()))
    assert store.load_document() == before
    result = planned['completion']
    assert result['state'] == 'awaiting_decision'
    assert result['missing'] == caught.value.decision['reasons']
    assert result['missing'][0]['topics'] == ['direction']
    assert result['next_action'] == caught.value.decision['next_action']
    assert result['responsible_role'] == 'user'
    assert result['effective_scope'] == scope
    assert result['checks'][0]['status'] == 'not_evaluated'


def test_authorized_edit_commits_without_claiming_whole_request_or_review_pass(tmp_path):
    project, store, scope, evidence = setup_edit(tmp_path)
    allow(project, store, scope, evidence)
    ready = status(store)
    assert ready['state'] == 'in_progress'
    assert ready['missing'] == []
    assert ready['next_action'] == 'inspect_requested_content'
    planned = content_ops.plan(project, input=value(store, ids=('p1',)))
    committed = content_ops.commit(project, plan_id=planned['plan_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert committed['operation_result']['status'] == 'edited'
    result = status(store)
    assert result['state'] == 'in_progress'
    assert result['next_action'] == 'inspect_requested_content'
    assert result['responsible_role'] == 'content'
    assert result['missing'] == []
    assert result['checks'][0]['status'] == 'not_evaluated'
    assert store.load_document()['pages'][0]['page'] in result['outputs']
    assert not store.load_document()['outputs'].get('pptx')


def test_pause_wins_over_missing_direction(tmp_path):
    project, store, _, _ = setup_edit(tmp_path)
    collaboration.pause_request(project, reason='Synthetic pause', base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    result = status(store)
    assert result['state'] == 'awaiting_decision'
    assert result['missing'][0]['code'] == 'request_paused'
    assert result['next_action'] == 'resume the request explicitly (resume never widens scope) or cancel it'


def test_completed_write_only_still_returns_without_visual_production(tmp_path):
    project, store, _, _ = setup_edit(tmp_path)
    doc = store.load_document()
    # Read the real prior imported snapshot, not a fabricated completed state.
    prior = store.load_document(doc['parent_revision_id'])
    result = content_production.completion_status(store, prior)
    assert result['state'] == 'completed'
    assert result['responsible_role'] == 'caller'
    assert result['next_action'] == 'return_requested_content'
    assert result['checks'][0]['status'] == 'pass'
    assert not prior['tasks'] and not prior['outputs'].get('pptx')


def test_reader_without_concrete_operation_keeps_inspection_responsibility(tmp_path):
    from deck_master import method_resources, workbench
    project, store, _, _ = setup_edit(tmp_path)
    expected = status(store)
    before = source_snapshot(project)
    read = method_resources.read_skill_methods('deck-content', project=project)
    assert read['context']['completion'] == expected
    work = workbench.workbench_summary(project, protocol='workbench_summary.v2')['current_work']
    assert work['next']['action'] == expected['next_action']
    assert work['next']['responsible_role'] == 'content'
    assert expected['next_action'] == 'inspect_requested_content'
    assert expected['missing'] == []
    assert source_snapshot(project) == before


def test_revoked_grant_is_not_replaced_by_an_inspect_or_write_permission(tmp_path):
    project, store, scope, evidence = setup_edit(tmp_path)
    allow(project, store, scope, evidence)
    grant = store.read_object_json(store.load_document()['collaboration']['authorizations'][-1])
    collaboration.revoke_authorization(project, authorization_id=grant['authorization_id'],
        reason='Synthetic withdrawal', base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    result = content_ops.plan(project, input=value(store, ids=('p1',)))['completion']
    assert result['state'] == 'awaiting_decision'
    assert result['missing'][0]['code'] == 'authorization_revoked'
    assert result['next_action'] == 'the withdrawal stands; a new authorization requires a new explicit user instruction'


def test_external_review_handoff_and_source_failure_do_not_change_edit_state(tmp_path):
    from deck_master import external_review
    from deck_master.errors import SourceUnreadable
    project, store, scope, evidence = setup_edit(tmp_path)
    allow(project, store, scope, evidence)
    before = source_snapshot(project)
    text = tmp_path / 'controlled.md'
    text.write_text('Controlled synthetic pilot: unvalidated, human review required. No measured saving.')
    review_scope = {**scope, 'subject': 'deck', 'page_ids': []}
    reviewed = external_review.evaluate(text, scope=review_scope)
    assert reviewed['status'] == 'needs_reviewer'
    assert reviewed['next_action'] == 'review_the_readable_packet'
    assert reviewed['external_report']['report']['source_unchanged'] is True
    assert reviewed['external_report']['report']['reviews'] == []
    with pytest.raises(SourceUnreadable):
        service.create(tmp_path / 'failed', brief='Synthetic missing source', sources=[tmp_path / 'absent.md'])
    assert not (tmp_path / 'failed/.deckmaster/current.json').exists()
    assert source_snapshot(project) == before
    assert status(store)['checks'][0]['status'] == 'not_evaluated'


def test_write_only_without_adopted_direction_remains_waiting(tmp_path):
    project = tmp_path / 'no-direction'
    service.create(project, brief='Synthetic write-only request without adopted direction',
        request_input={'intent': 'content_only', 'content_intent': 'write_only'})
    result = status(Store(project))
    assert result['state'] == 'awaiting_decision'
    assert result['missing'] == [{'code': 'content_requirement',
        'detail': 'write_only needs adopted direction or an imported manuscript'}]
    assert result['next_action'] == 'write_only needs adopted direction or an imported manuscript'
    assert result['outputs'] == []


def test_content_edit_projection_does_not_take_over_visual_scope(tmp_path):
    project, store, scope, evidence = setup_edit(tmp_path)
    request_id = store.load_document()['collaboration']['request']['request_id']
    collaboration.start_request(project, input={'intent': 'edit', 'content_intent': None,
        'scope': {**scope, 'layers': ['design']}, 'replace_request_id': request_id,
        'instruction_evidence': evidence_for(project, text='Synthetic new visual-only edit', locator='L1:visual')},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    result = status(store)
    assert result['state'] == 'in_progress'
    assert result['missing'] == []
    assert result['next_action'] is None  # Existing non-content responsibility, outside this fix.


@pytest.mark.parametrize('case', ['page_copy_only', 'one_of_two_pages', 'unused_membership'])
def test_legal_narrow_edit_never_projects_request_ceiling_as_action(tmp_path, case):
    from deck_master import editing, method_resources, workbench
    project, store, scope, evidence = setup_edit(tmp_path,
        layers=['page_copy'] if case == 'page_copy_only' else None,
        page_ids=('p1', 'p2') if case == 'one_of_two_pages' else ('p1',),
        membership=case == 'unused_membership')
    actual_scope = {**scope, 'page_ids': ['p1'], 'allow_page_membership_change': False}
    if case == 'page_copy_only':
        doc = store.load_document()
        page = store.read_object_json(doc['pages'][0]['page'])
        page['customer_visible']['title'] = 'Actual bounded copy edit, still unvalidated'
        result = editing.edit_page(project, page=page, base_revision=doc['revision_id'],
            page_hash=doc['pages'][0]['page']['sha256'], operation_id=str(uuid.uuid4()))
    else:
        allow(project, store, actual_scope, evidence)
        planned = content_ops.plan(project, input=value(store, ids=('p1',)))
        assert planned['completion']['state'] == 'in_progress'
        assert planned['completion']['missing'] == []
        result = content_ops.commit(project, plan_id=planned['plan_id'],
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    assert result['status'] == 'edited'
    completion = status(store)
    assert completion['state'] == 'in_progress'
    assert completion['missing'] == []
    assert completion['next_action'] == 'inspect_requested_content'
    reader = method_resources.read_skill_methods('deck-content', project=project)
    assert reader['context']['completion'] == completion
    work = workbench.workbench_summary(project, protocol='workbench_summary.v2')['current_work']
    assert work['delivery'] == completion
    assert work['next']['action'] == 'inspect_requested_content'
    assert work['blockers'] == []


def test_concrete_plan_still_reports_real_extra_layer_violation(tmp_path):
    project, store, _, _ = setup_edit(tmp_path, layers=['page_copy'])
    preview = content_ops.plan(project, input=value(store, ids=('p1',)))
    result = preview['completion']
    assert result['state'] == 'awaiting_decision'
    assert result['missing'][0]['code'] == 'scope_exceeded'
    assert result['missing'][0]['target_layers'] == ['page_copy', 'plan']
    with pytest.raises(eligibility.EligibilityBlocked) as caught:
        content_ops.commit(project, plan_id=preview['plan_id'],
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert result['missing'] == caught.value.decision['reasons']
    assert result['next_action'] == caught.value.decision['next_action']
    assert status(store)['next_action'] == 'inspect_requested_content'
