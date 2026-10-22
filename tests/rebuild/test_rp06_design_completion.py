"""RP-06: synthetic routing and design outputs; no model/visual acceptance."""
import uuid

import pytest

from deck_master import collaboration, content_production, method_resources, service, styles
from test_rc3_design_feasibility import authorized, evidence, value


@pytest.mark.parametrize('text', [
    '先写正文，再设计样页', '请先策划再写正文，再做设计和审查', '审阅正文，然后设计样页',
    'Write the manuscript and design a sample page',
    'Review the manuscript, then rewrite it',
])
def test_compound_actions_route_to_master_and_reader_accepts(text):
    assert method_resources.route_request(text)['skill'] == 'deck-master'
    assert method_resources.read_skill_methods('deck-master', entry_mode='natural', text=text)['skill'] == 'deck-master'


@pytest.mark.parametrize(('text', 'skill'), [
    ('deck-content 写正文，再设计样页', 'deck-content'),
    ('只审阅正文，不设计样页', 'deck-review'),
    ('写正文，不要设计样页', 'deck-content'),
    ('只写正文，不要设计和审查', 'deck-content'),
    ('Write the manuscript; do not design and review it', 'deck-content'),
    ('请为审核流程设计样页，不改正文', 'deck-design'),
    ('Write the manuscript about review and approval procedures', 'deck-content'),
])
def test_single_responsibility_negation_and_subject_nouns(text, skill):
    assert method_resources.route_request(text)['skill'] == skill


def test_unconfirmed_proposal_completes_response_without_adoption_or_project_write(tmp_path):
    project, store, _ = authorized(tmp_path)
    before = store.load_document()
    result = styles.propose(project, input=value(store, ids=['p1', 'p2']))
    assert result['completion']['state'] == 'completed'
    assert result['completion']['outputs'] == [result['proposal_ref']]
    assert result['completion']['adoption'] == 'not_implied'
    assert result['completion']['production_authority'] == 'not_implied'
    assert store.load_document() == before
    # An orphan/uncommitted proposal is not silently discovered by continue.
    continued = service.continue_project(project)
    assert continued['status'] == 'needs_input'
    assert continued['next_action'] == 'prepare_requested_design'
    assert store.load_document() == before


def test_confirmed_current_plan_completes_continue_without_production(tmp_path):
    project, store, _ = authorized(tmp_path)
    result = styles.propose(project, input=value(store, ids=['p1', 'p2']))
    confirmed = styles.confirm(project, proposal_id=result['proposal_id'],
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    before = store.load_document()
    continued = service.continue_project(project)
    assert continued['status'] == 'completed'
    assert continued['next_action'] == 'return_requested_design'
    assert continued['completion']['outputs'] == [confirmed['recipe_ref']]
    reader = method_resources.read_skill_methods('deck-design', project=project)
    assert reader['context']['completion'] == continued['completion']
    assert store.load_document() == before
    assert not before['tasks'] and not before['outputs'].get('pptx')


def test_partial_proposal_does_not_complete_requested_scope(tmp_path):
    project, store, _ = authorized(tmp_path)
    proposed = styles.propose(project, input=value(store, ids=['p1']))
    assert proposed['completion']['state'] == 'in_progress'


def test_plan_from_other_request_is_not_current_completion(tmp_path):
    project, store, _ = authorized(tmp_path)
    result = styles.propose(project, input=value(store, ids=['p1', 'p2']))
    styles.confirm(project, proposal_id=result['proposal_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    before = store.load_document()
    request = before['collaboration']['request']
    new_evidence = evidence(store)
    new_evidence['source_ref'] = store.put_json_object({'synthetic_l1': 'A different design request, not the old proposal.'})
    collaboration.start_request(project, input={'intent': 'design_trial', 'content_intent': None,
        'instruction_evidence': new_evidence, 'scope': request['scope'], 'replace_request_id': request['request_id']},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    collaboration.grant(project, input={'mode': 'execute', 'actions': ['design.propose'],
        'scope': request['scope'], 'max_external_calls': 0, 'max_candidate_count': 0,
        'instruction_evidence': new_evidence}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert content_production.completion_status(store, store.load_document())['state'] != 'completed'


def test_real_sample_authorization_is_not_relabelled_as_pure_plan(tmp_path):
    project, store, _ = authorized(tmp_path, actions=('style.trial',))
    result = content_production.completion_status(store, store.load_document())
    assert result['state'] != 'completed'
    assert result['checks'][0]['kind'] != 'requested_design_plan'


def test_changed_page_basis_invalidates_plan_but_unrelated_revision_does_not(tmp_path):
    import copy
    from deck_master import models
    project, store, _ = authorized(tmp_path)
    result = styles.propose(project, input=value(store, ids=['p1', 'p2']))
    styles.confirm(project, proposal_id=result['proposal_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    before = store.load_document()
    # Commit synthetic source state; no customer material or model approval.
    updated = models.bump_revision(copy.deepcopy(before), {'operation_id': 'unrelated-test',
        'kind': 'task_update', 'description': 'L1 unrelated revision', 'read_set': []})
    store.commit_change(base_revision=before['revision_id'], document=updated, operation_id='unrelated-test')
    assert content_production.completion_status(store, store.load_document())['state'] == 'completed'
    before = store.load_document()
    updated = models.bump_revision(copy.deepcopy(before), {'operation_id': 'changed-page-test',
        'kind': 'task_update', 'description': 'L1 changed page basis', 'read_set': []})
    page = store.read_object_json(updated['pages'][0]['page'])
    page['customer_visible']['title'] = 'A changed current design input'
    updated['pages'][0]['page'] = store.put_json_object(page)
    store.commit_change(base_revision=before['revision_id'], document=updated, operation_id='changed-page-test')
    result = content_production.completion_status(store, store.load_document())
    assert result['state'] != 'completed'
    assert any(row['code'] == 'design_basis_changed' for row in result['missing'])
