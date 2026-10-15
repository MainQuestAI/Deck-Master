"""Unreadable proof stays blocked while read-only recovery remains available."""
import json

import pytest

from deck_master import collaboration, eligibility, exports, icons, pipeline, production, ui_journal
from deck_master.models import ModelError
from rc3_fixtures import source_snapshot
from test_icon_quality import confirm, dispatch, icon_store  # noqa: F401


def test_corrupt_task_cannot_erase_project_reading_or_establish_production_proof(icon_store):
    store = icon_store
    assert eligibility.preproduction_state(store, store.load_document())['satisfied'] is True
    recipe = confirm(store)
    task = dispatch(store, recipe)[0]
    doc = store.load_document()
    task_ref = next(ref for ref in doc['tasks'] if store.read_object_json(ref)['task_id'] == task['task_id'])
    damaged = store.project_root / task_ref['path']
    damaged.write_bytes(b'{broken task')
    original = source_snapshot(store.project_root)
    state = eligibility.preproduction_state(store, doc)
    assert state['status'] == 'unreadable' and state['satisfied'] is False
    assert set(state['missing_units']) == set(state['units'])
    described = collaboration.describe(store.project_root)
    info = ui_journal.project_info(store.project_root)
    assert info['revision_id'] == described['revision_id'] == doc['revision_id']
    for action in ('dispatch.blueprint', 'export.delivery'):
        card = next(card for card in described['blocking_cards'] if card['action'] == action)
        assert card['decision']['allowed'] is False
        if action == 'dispatch.blueprint':
            assert 'unreadable' in json.dumps(card['decision'])
    assert icons.listing(store.project_root, include_stale=True)['proposals'][0]['status'] == 'dispatch_unknown'
    with pytest.raises(ModelError, match='generation lineage'):
        production.resolve_page_rendering_design(store, doc, doc['pages'][0])
    with pytest.raises(eligibility.EligibilityBlocked):
        pipeline.produce(store.project_root)
    with pytest.raises(eligibility.EligibilityBlocked):
        exports.create(store.project_root, purpose='delivery')
    assert source_snapshot(store.project_root) == original
    assert damaged.read_bytes() == b'{broken task'
