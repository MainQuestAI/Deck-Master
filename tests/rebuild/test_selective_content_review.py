"""RP-12 synthetic review dispatch and receiver checks, no model calls."""
from copy import deepcopy
import json

import pytest

from deck_master import content_review, models, native_review, tasks
from test_native_review import native, FixtureSession
from test_content_preproduction_review import _deck


def change_page(store, field):
    doc = store.load_document()
    changed = deepcopy(doc)
    page = store.read_object_json(changed['pages'][0]['page'])
    if field == 'speech':
        page['speaker_notes'] += ' 新增讲述提示。'
    else:
        page['customer_visible']['title'] += ' 新内容'
    changed['pages'][0]['page'] = store.put_json_object(page)
    changed = models.bump_revision(changed, {'operation_id': 'change-' + field, 'kind': 'task_update',
        'description': 'Synthetic isolated manuscript change', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='change-' + field)


def recheck_owners(monkeypatch):
    original = FixtureSession.review
    def review(self, prompt, schema):
        observation = original(self, prompt, schema)
        data = self.calls[-1]
        rows = [{'kind': owner['review']['kind'], 'status': 'pass', 'findings': [],
                 'observations': ['Synthetic exact owner recheck'], 'replaces': owner['ref']}
                for owner in data['prior_reviews']]
        observation['raw_final_message'] = json.dumps({'reviews': rows})
        return observation
    monkeypatch.setattr(FixtureSession, 'review', review)


def test_notes_only_recheck_freezes_speech_and_retains_other_valid_reviews(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    native_review.run(project)
    old = store.load_document()['reviews']
    change_page(store, 'speech')
    state = content_review.preproduction_status(store, store.load_document())
    assert state['missing_units'] == ['speech']
    recheck_owners(monkeypatch)
    result = native_review.run(project)
    assert result['preproduction']['status'] == 'pass'
    packet = native.calls[-1]['packet']
    assert packet['required_units'] == ['speech']
    assert {row['kind'] for row in packet['review_scope']['owners']} == {'speech'}
    assert len(packet['manuscript']['pages']) == 2
    assert packet['materials'] and packet['narrative'] and packet['plan']
    assert store.load_document()['reviews'][:len(old)] == old
    assert len(store.load_document()['reviews']) == len(old) + 1
    assert {row['review']['kind'] for row in native.calls[-1]['prior_reviews']} == {'speech'}


def test_visible_copy_change_requires_all_affected_units(tmp_path, native):
    project, store = _deck(tmp_path)
    native_review.run(project)
    change_page(store, 'copy')
    result = content_review.dispatch_preproduction_review(project)
    assert set(result['units']) == {'argument', 'page_copy', 'progression', 'speech'}


def test_receiver_rejects_missing_or_extra_frozen_units_and_owners(tmp_path, native):
    project, store = _deck(tmp_path)
    native_review.run(project)
    change_page(store, 'speech')
    result = content_review.dispatch_preproduction_review(project)
    packet = result['review_draft']
    task = {'inputs': [result['review_draft_ref']],
            'review_units': [{'kind': 'speech'}]}
    good = {'kind': 'speech', 'replaces': packet['review_scope']['owners'][0]['review_ref']}
    document = store.load_document()
    content_review._require_unit_coverage(store, document, [good], task)
    for bad in ([], [good, {'kind': 'argument'}], [{'kind': 'speech'}], [good, good]):
        with pytest.raises(tasks.EnvelopeError):
            content_review._require_unit_coverage(store, document, bad, task)
    # An old Task without a frozen packet cannot self-narrow its review_units.
    with pytest.raises(tasks.EnvelopeError, match='missing units'):
        content_review._require_unit_coverage(store, document, [good], {'review_units': [{'kind': 'speech'}]})


def test_already_valid_review_dispatch_does_not_create_redundant_task(tmp_path, native):
    project, store = _deck(tmp_path)
    native_review.run(project)
    before = store.load_document()
    assert content_review.dispatch_preproduction_review(project)['status'] == 'already_reviewed'
    assert store.load_document() == before
