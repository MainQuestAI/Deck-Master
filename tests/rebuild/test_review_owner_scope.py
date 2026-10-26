"""RP-12 overlapping historical owner regression; explicit synthetic review."""
import json

import pytest

from deck_master import content_review, native_review
from synthetic_review_provider import synthetic_runtime_call
from test_native_review import native, FixtureSession
from test_content_preproduction_review import _deck, _independent_adapter
from deck_master.store import Store
from test_selective_content_review import change_page


def initial_subset_review(project, monkeypatch):
    store = Store(project)
    dispatched = synthetic_runtime_call(content_review.dispatch_preproduction_review, project,
        page_ids=['p1'], adapter_context=_independent_adapter(store, store.load_document()))
    original = FixtureSession.review
    def fail(self, prompt, schema):
        observation = original(self, prompt, schema)
        rows = json.loads(observation['raw_final_message'])['reviews']
        row = next(row for row in rows if row['kind'] == 'page_copy')
        page_ref = self.calls[-1]['packet']['manuscript']['pages'][0]['page_ref']
        row.update(status='fail', findings=[{'finding_id': 'subset-p1', 'kind': 'content',
            'impact': 'must_fix', 'page_id': 'p1', 'element_refs': ['atom:p1:title'],
            'message': 'Synthetic p1 defect', 'expected': 'Revised title', 'actual': 'Old title',
            'evidence': [page_ref], 'resolution': 'open', 'resolution_reason': ''}])
        observation['raw_final_message'] = json.dumps({'reviews': rows})
        return observation
    with monkeypatch.context() as patch:
        patch.setattr(FixtureSession, 'review', fail)
        native_review.run(project, task_id=dispatched['task']['task_id'])


@pytest.mark.parametrize('pages,has_owner', [(['p1', 'p2'], True), (['p1'], True), (['p2'], False)])
def test_frozen_owners_follow_page_intersection_not_subset(tmp_path, native, monkeypatch, pages, has_owner):
    project, store = _deck(tmp_path)
    initial_subset_review(project, monkeypatch)
    result = content_review.dispatch_preproduction_review(project, page_ids=pages)
    owners = result['review_draft']['review_scope']['owners']
    copy_owners = [owner for owner in owners if owner['kind'] == 'page_copy']
    assert bool(copy_owners) is has_owner
    if has_owner:
        review = store.read_object_json(copy_owners[0]['review_ref'])
        assert review['findings'][0]['finding_id'] == 'subset-p1'


def test_full_scope_recheck_closes_exact_subset_finding_without_losing_owner(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    initial_subset_review(project, monkeypatch)
    change_page(store, 'copy')
    original = FixtureSession.review
    def repaired(self, prompt, schema):
        observation = original(self, prompt, schema)
        data = self.calls[-1]
        owners = data['prior_reviews']
        assert any(owner['review']['findings'] for owner in owners)
        page_ref = data['packet']['manuscript']['pages'][0]['page_ref']
        rows = []
        for owner in owners:
            findings = [{**finding, 'resolution': 'fixed', 'evidence': [page_ref],
                         'resolution_reason': 'Synthetic actual changed p1 title rechecked'}
                        for finding in owner['review']['findings']]
            rows.append({'kind': owner['review']['kind'], 'status': 'pass',
                'observations': ['Synthetic current full-scope recheck'], 'findings': findings,
                'replaces': owner['ref']})
        observation['raw_final_message'] = json.dumps({'reviews': rows})
        return observation
    monkeypatch.setattr(FixtureSession, 'review', repaired)
    result = native_review.run(project)
    assert result['preproduction']['status'] == 'pass'
    assert result['preproduction']['blocking_findings'] == []
    assert len(native.calls[-1]['packet']['manuscript']['pages']) == 2
    assert len(native.calls) == 2
