"""Real import admission and atomic refusal; all authored inputs are L1 synthetic."""
from copy import deepcopy
import uuid

import pytest

from deck_master import collaboration, eligibility, service
from deck_master.store import Store
from rc3_fixtures import evidence_for, source_snapshot


def _page(pid):
    return {'schema_version': 'deck_page_package.v2', 'page_id': pid,
        'customer_visible': {'title': 'L1 fixed copy ' + pid, 'body_blocks': []},
        'speaker_notes': 'L1 original cue ' + pid,
        'visual_spec': {'intent': 'L1 synthetic imported manuscript', 'reference_mode': 'new_design'}}


def _request(project, store, *, ids, layers=('page_copy', 'plan'), membership=False, order=False):
    doc = store.load_document()
    scope = {'subject': 'pages', 'page_ids': ids, 'page_manifest_ref': None,
        'external_artifact_ref': None, 'layers': list(layers),
        'allow_page_membership_change': membership, 'allow_page_order_change': order,
        'purpose': 'working'}
    collaboration.start_request(project, input={'intent': 'edit', 'content_intent': None,
        'scope': scope, 'replace_request_id': doc['collaboration']['request']['request_id'],
        'instruction_evidence': evidence_for(project, text='L1 edit only the explicit selected layers and pages',
            locator='L1:import-scope:' + str(uuid.uuid4()))}, base_revision=doc['revision_id'],
        operation_id=str(uuid.uuid4()))


@pytest.mark.parametrize('outline_max', [None, 9])
def test_provided_outline_cannot_relax_the_actual_document_hard_page_limit(tmp_path, outline_max):
    from deck_master.models import ModelError
    project = tmp_path / 'limited'
    service.create(project, brief='L1 explicit two-page hard maximum', page_limit=2,
        draft={'pages': [_page('p1'), _page('p2')]})
    store = Store(project)
    before = store.load_document()
    outline = deepcopy(store.read_object_json(before['content_plan'])['input'])
    outline['page_budget']['max'] = outline_max
    # An unconstrained/looser outline never changes the independent Task fact.
    legal = tmp_path / 'legal'
    service.create(legal, brief='L1 retain actual hard maximum', page_limit=2,
        draft={'pages': [_page('p1'), _page('p2')], 'content_plan': outline})
    assert Store(legal).load_document()['task']['page_limit'] == 2
    outline['page_order'].append('p3')
    outline['page_roles'].append({**deepcopy(outline['page_roles'][0]), 'page_id': 'p3'})
    payload = {'pages': [_page('p1'), _page('p2'), _page('p3')], 'content_plan': outline}
    tree = source_snapshot(project)
    with pytest.raises(ModelError, match='hard maximum'):
        service.import_draft(project, draft_payload=payload, base_revision=before['revision_id'],
            operation_id=str(uuid.uuid4()))
    assert source_snapshot(project) == tree
    new = tmp_path / 'over-limit'
    with pytest.raises(ModelError, match='hard maximum'):
        service.create(new, brief='L1 must refuse three pages under the original two-page limit',
            page_limit=2, draft=payload)
    assert not new.exists()


@pytest.mark.parametrize('attempt', ['omit_unselected', 'remove', 'reorder', 'add', 'speech', 'unselected_plan'])
def test_import_refuses_the_complete_out_of_scope_write_set_without_any_store_write(tmp_path, attempt):
    project = tmp_path / 'project'
    service.create(project, brief='L1 retain both fixed pages', draft={'pages': [_page('p1'), _page('p2')]})
    store = Store(project)
    ids = ['p1'] if attempt in ('omit_unselected', 'speech', 'unselected_plan') else ['p1', 'p2']
    _request(project, store, ids=ids)
    before = store.load_document()
    pages = [store.read_object_json(entry['page']) for entry in before['pages']]
    pages[0]['customer_visible']['title'] += ' revised'
    payload = {'pages': pages}
    if attempt in ('omit_unselected', 'remove'):
        payload['pages'] = pages[:1]
    elif attempt == 'reorder':
        payload['page_order'] = ['p2', 'p1']
    elif attempt == 'add':
        payload['pages'].append(_page('p3'))
    elif attempt == 'speech':
        pages[0]['speaker_notes'] += ' Added speech outside the request.'
        # Imported segments are real ranges and must cover the changed notes.
        pages[0]['content_mapping']['speech_segments'][0]['end_codepoint'] = len(pages[0]['speaker_notes'])
    else:
        from test_compose_v2_phases import _plan_input
        payload['content_plan'] = _plan_input(before, ['p1', 'p2'])
    tree = source_snapshot(project)
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        service.import_draft(project, draft_payload=payload, base_revision=before['revision_id'],
            operation_id=str(uuid.uuid4()))
    assert 'scope_exceeded' in blocked.value.decision['reason_codes']
    assert store.load_document() == before and source_snapshot(project) == tree


def test_complete_manuscript_can_change_one_page_and_retain_the_unselected_original(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='L1 retain both fixed pages', draft={'pages': [_page('p1'), _page('p2')]})
    store = Store(project)
    _request(project, store, ids=['p1'])
    before = store.load_document()
    pages = [store.read_object_json(entry['page']) for entry in before['pages']]
    pages[0]['customer_visible']['title'] += ' revised'
    tree = source_snapshot(project)
    preview = service.preview_draft_import(project, draft_payload={'pages': pages})
    from deck_master.collaboration_api import invoke, http_action
    envelope, status, code = invoke(project, 'draft.preview', {'draft_payload': {'pages': pages}},
        expected_project_id=before['project_id'])
    assert (status, code) == (200, 0)
    assert http_action('POST', '/api/projects/' + before['project_id'] + '/draft/preview')[1] == 'draft.preview'
    assert envelope['result'] == preview
    assert preview['required_scope']['page_ids'] == ['p1']
    assert source_snapshot(project) == tree
    operation_id = str(uuid.uuid4())
    response = service.import_draft(project, draft_payload={'pages': pages},
        base_revision=before['revision_id'], operation_id=operation_id)
    after = store.load_document()
    assert response['status'] == 'accepted'
    assert after['pages'][1] == before['pages'][1]
    assert [entry['page_id'] for entry in after['pages']] == ['p1', 'p2']
    assert after['collaboration'] == before['collaboration']
    assert response['write_set']['page_ids'] == ['p1']
    assert response['write_set']['layers'] == ['page_copy', 'plan']
    assert response['write_set']['added_page_ids'] == response['write_set']['removed_page_ids'] == []
    assert preview['write_set'] == response['write_set']
    replay = service.import_draft(project, draft_payload={'pages': pages},
        base_revision=before['revision_id'], operation_id=operation_id)
    assert replay['status'] == 'already_applied' and store.load_document() == after


def test_import_cannot_clear_an_existing_narrative_under_copy_plan_scope(tmp_path):
    from test_compose_v2_phases import _deck_with_pages
    project, store = _deck_with_pages(tmp_path)
    _request(project, store, ids=['p1'], layers=('page_copy', 'plan', 'speech', 'review'))
    before = store.load_document()
    assert before['narrative']
    payload = {'pages': [store.read_object_json(entry['page']) for entry in before['pages']]}
    tree = source_snapshot(project)
    with pytest.raises(eligibility.EligibilityBlocked):
        service.import_draft(project, draft_payload=payload, base_revision=before['revision_id'],
            operation_id=str(uuid.uuid4()))
    assert store.load_document() == before and source_snapshot(project) == tree


def test_import_cannot_clear_real_output_or_visual_refs_under_copy_plan_scope(tmp_path):
    from test_export import _deck
    project, store = _deck(tmp_path)
    _request(project, store, ids=['p1'], layers=('page_copy', 'plan', 'speech'))
    before = store.load_document()
    assert before['outputs']['pptx'] and before['pages'][0]['svg']
    payload = {'pages': [store.read_object_json(entry['page']) for entry in before['pages']]}
    payload['pages'][0]['customer_visible']['title'] += ' revised'
    tree = source_snapshot(project)
    with pytest.raises(eligibility.EligibilityBlocked):
        service.import_draft(project, draft_payload=payload, base_revision=before['revision_id'],
            operation_id=str(uuid.uuid4()))
    assert store.load_document() == before and source_snapshot(project) == tree


def test_explicit_full_scope_can_replace_membership_notes_and_order_atomically(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='L1 fixed input', draft={'pages': [_page('p1'), _page('p2')]})
    store = Store(project)
    _request(project, store, ids=['p1', 'p2', 'p3'], layers=('page_copy', 'plan', 'speech'),
        membership=True, order=True)
    before = store.load_document()
    replacement = deepcopy(_page('p1'))
    replacement['speaker_notes'] += ' Explicitly replaced cue.'
    response = service.import_draft(project, draft_payload={'pages': [replacement, _page('p3')],
        'page_order': ['p3', 'p1']}, base_revision=before['revision_id'], operation_id=str(uuid.uuid4()))
    after = store.load_document()
    assert [entry['page_id'] for entry in after['pages']] == ['p3', 'p1']
    assert response['write_set']['added_page_ids'] == ['p3']
    assert response['write_set']['removed_page_ids'] == ['p2']
    assert response['write_set']['allow_page_membership_change'] is True
    assert 'speech' in response['write_set']['layers']
    assert after['collaboration'] == before['collaboration']
