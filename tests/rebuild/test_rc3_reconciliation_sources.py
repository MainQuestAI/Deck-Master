"""Reconciliation consumes real sources/mapping, including imported null Narrative."""
from copy import deepcopy

import pytest

from deck_master import content_production, models, service, tasks
from deck_master.store import Store
from rc3_fixtures import claim_fixture_task
from test_compose_v2_phases import _deck_with_pages, _submit
from test_rc3_entry_transactions import operation


@pytest.mark.parametrize('layer', ['page_copy', 'plan', 'narrative', 'speech'])
@pytest.mark.parametrize('fault', ['source', 'version', 'locator'])
def test_reconciliation_rejects_fabricated_source_or_speech_nodes_atomically(tmp_path, layer, fault):
    project, store = _deck_with_pages(tmp_path)
    before_dispatch = store.load_document()
    task = content_production.open_phase_task(store, before_dispatch,
        operation_id=operation(), intent='input_revision', page_ids=['p1'], adoption_policy='within_scope')
    claim_fixture_task(project, task)
    doc = store.load_document()
    page = deepcopy(store.read_object_json(doc['pages'][0]['page']))
    source_link = deepcopy(page['content_mapping']['visible_links'][1]['source_links'][0])
    if fault == 'source':
        source_link['source_id'] = 'nonexistent-source'
    elif fault == 'version':
        source_link['source_version']['original_sha256'] = '0' * 64
    else:
        source_link['locator'] = 'L999'
    if layer == 'page_copy':
        page['content_mapping']['visible_links'][1]['source_links'] = [source_link]
        proposed = page
    elif layer == 'speech':
        page['content_mapping']['speech_segments'][0]['narrative_node_ids'] = ['nonexistent-' + fault]
        proposed = page
    elif layer == 'plan':
        proposed = deepcopy(store.read_object_json(doc['content_plan'])['input'])
        proposed['page_roles'][0]['source_links'] = [source_link]
    else:
        proposed = deepcopy(store.read_object_json(doc['narrative']))
        proposed['nodes'][0]['source_links'] = [source_link]
    payload = {'changed_layers': [layer], 'proposals': [{'layer': layer, 'ref': store.put_json_object(proposed)}],
        'diff': {'input_digest': task['input_digest'], 'summary': 'L1 invalid mapping must not adopt',
            'changed_page_ids': ['p1'] if layer in ('page_copy', 'speech') else []}}
    before = store.load_document()
    with pytest.raises(models.ModelError):
        _submit(project, task, payload, 'input_revision')
    assert store.load_document() == before
    assert tasks._lookup_task(before, task['task_id'], store)['status'] == 'running'


def test_null_narrative_import_can_revise_copy_with_no_claimed_source_or_role(tmp_path):
    project = tmp_path / 'imported'
    original = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'L1 original confirmed manuscript', 'body_blocks': []},
        'speaker_notes': 'L1 original cue with unknown estimate.',
        'visual_spec': {'intent': 'L1 fixed manuscript', 'reference_mode': 'new_design'}}
    service.create(project, brief='L1 fixed manuscript only', draft={'pages': [original]})
    store = Store(project)
    task = content_production.open_phase_task(store, store.load_document(), operation_id=operation(),
        intent='input_revision', page_ids=['p1'], adoption_policy='within_scope')
    claim_fixture_task(project, task)
    before = store.load_document()
    page = store.read_object_json(before['pages'][0]['page'])
    page['customer_visible']['title'] += ' revised without an invented citation'
    payload = {'changed_layers': ['page_copy'], 'proposals': [{'layer': 'page_copy', 'ref': store.put_json_object(page)}],
        'diff': {'input_digest': task['input_digest'], 'summary': 'L1 preserve imported unknown mapping and notes',
            'changed_page_ids': ['p1']}}
    response = _submit(project, task, payload, 'input_revision')
    after = store.load_document()
    assert response['adopted'] is True and after['narrative'] is None
    plan = store.read_object_json(after['content_plan'])
    assert plan['mode'] == 'imported_mapping'
    assert [role['page_id'] for role in plan['input']['page_roles']] == ['p1']
    assert plan['input']['page_roles'][0]['narrative_node_ids'] == []
    assert plan['input']['page_roles'][0]['source_links'] == []
    current = store.read_object_json(after['pages'][0]['page'])
    assert current['speaker_notes'] == original['speaker_notes']
    assert current['content_mapping']['speech_segments'][0]['estimated_seconds'] is None
    assert all(not link['source_links'] for link in current['content_mapping']['visible_links'])


def test_null_narrative_import_cannot_claim_a_new_nonexistent_source(tmp_path):
    project = tmp_path / 'imported'
    original = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'L1 original', 'body_blocks': []},
        'visual_spec': {'intent': 'L1 manuscript', 'reference_mode': 'new_design'}}
    service.create(project, brief='L1 original source bytes remain unknown', draft={'pages': [original]})
    store = Store(project)
    task = content_production.open_phase_task(store, store.load_document(), operation_id=operation(),
        intent='input_revision', page_ids=['p1'], adoption_policy='within_scope')
    claim_fixture_task(project, task)
    before = store.load_document()
    page = store.read_object_json(before['pages'][0]['page'])
    page['content_mapping']['visible_links'][0]['source_links'] = [{'source_id': 'invented',
        'source_version': {'original_sha256': '0' * 64,
            'extract': {'path': '.deckmaster/objects/00/' + '0' * 64 + '.json', 'sha256': '0' * 64}},
        'locator': 'L999'}]
    payload = {'changed_layers': ['page_copy'], 'proposals': [{'layer': 'page_copy', 'ref': store.put_json_object(page)}],
        'diff': {'input_digest': task['input_digest'], 'summary': 'L1 fabricated provenance is rejected', 'changed_page_ids': ['p1']}}
    with pytest.raises(models.ModelError):
        _submit(project, task, payload, 'input_revision')
    assert store.load_document() == before and before['sources'] == []
