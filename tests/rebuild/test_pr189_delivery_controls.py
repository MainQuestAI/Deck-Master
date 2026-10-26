"""Synthetic exact-file delivery controls; no human or model execution."""
import copy
import uuid

import pytest

from deck_master.models import bump_revision
from test_export import _passing_deck
from test_rc3_selected_delivery import (NOTES, _delivered, _fixed_public_file,
                                       _grant_fixed, _next_request, _refused)


def _request_state(store, state):
    current = store.load_document()
    updated = bump_revision(copy.deepcopy(current), {'operation_id': uuid.uuid4().hex,
        'kind': 'task_update', 'description': 'Synthetic request terminal/pause fixture', 'read_set': []})
    request = updated['collaboration']['request']
    request.update(paused=state == 'paused', pause_reason='Synthetic stop' if state == 'paused' else None,
                   closed=state != 'paused', closed_reason=None if state == 'paused' else state)
    store.commit_change(document=updated, base_revision=current['revision_id'],
                        operation_id=updated['change']['operation_id'])


@pytest.mark.parametrize('location', ['source', 'source_then_replaced', 'current'])
@pytest.mark.parametrize('state', ['paused', 'rejected', 'withdrawn'])
def test_fixed_delivery_respects_source_and_current_stops_without_writing(tmp_path, location, state):
    project, store = _passing_deck(tmp_path, notes=NOTES)
    _fixed_public_file(store, tmp_path, name='materialized')
    _grant_fixed(store)
    fixed = _fixed_public_file(store, tmp_path, name='authorized')
    if location == 'current':
        _next_request(store)
    _request_state(store, state)
    if location == 'source_then_replaced':
        _next_request(store)
    before = store.load_document()
    _refused(project, fixed, tmp_path / 'refused',
             code='request_paused' if state == 'paused' else 'request_closed')
    assert store.load_document() == before


@pytest.mark.parametrize('replace', [False, True])
def test_completed_request_preserves_only_its_fixed_file_delivery(tmp_path, replace):
    project, store = _passing_deck(tmp_path, notes=NOTES)
    _fixed_public_file(store, tmp_path, name='materialized')
    _grant_fixed(store)
    fixed = _fixed_public_file(store, tmp_path, name='authorized')
    _request_state(store, 'completed')
    if replace:
        _next_request(store)
    _delivered(project, fixed, tmp_path / 'delivery')
