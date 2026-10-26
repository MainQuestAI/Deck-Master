"""Synthetic historical defects: scoped re-review must retain blocking owners.

These records exercise interpretation, not real reviewer/model acceptance.
"""
from copy import deepcopy

import pytest

from deck_master import content_review, models, review as review_mod, tasks
from test_scoped_preproduction_eligibility import reviewed_scope


def historical_owner(tmp_path, *, page_id=None, impact='must_fix'):
    project, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    status = content_review.preproduction_status(store, doc, page_ids=['p1'])
    review = deepcopy(store.read_object_json(status['review_refs'][0]))
    p2 = next(row for row in doc['pages'] if row['page_id'] == 'p2')
    p1 = next(row for row in doc['pages'] if row['page_id'] == 'p1')
    review.update(review_id='historical-p2-defect', status='fail' if impact=='must_fix' else 'needs_review', replaces=None,
                  findings=[{'finding_id':'deck-defect', 'kind':'content', 'impact':impact,
                    'resolution':'open', 'page_id':page_id, 'element_refs':[], 'message':'Synthetic historical defect',
                    'expected':'supported claim', 'actual':'unsupported claim', 'evidence':[]}])
    review['dependencies'] = [dict(dep, identity='page:p2', sha256=p2['page']['sha256'])
        if dep['kind']=='content' and dep['identity']=='page:p1' else dep for dep in review['dependencies']]
    review['subjects'] = [p2['page'] if ref==p1['page'] else ref for ref in review['subjects']]
    owner = store.put_json_object(review)
    doc = {**doc, 'reviews': [*doc['reviews'], owner]}
    return project, store, doc, review, owner


@pytest.mark.parametrize('impact', ['must_fix', 'needs_judgment'])
def test_scoped_packet_retains_exact_other_page_owner_of_open_deck_finding(tmp_path, impact):
    project, store, doc, review, owner = historical_owner(tmp_path, impact=impact)
    status = content_review.preproduction_status(store, doc, page_ids=['p1'])
    assert status['status'] == 'blocked'
    assert any(row['finding_id']=='deck-defect' for row in status['blocking_findings'])
    doc = models.bump_revision(doc, {'operation_id':'historical-defect', 'kind':'task_update',
        'description':'Synthetic immutable historical defect', 'read_set':[]})
    store.commit_change(base_revision=store.current_revision_id(), document=doc, operation_id='historical-defect')
    result = content_review.dispatch_preproduction_review(project, page_ids=['p1'])
    packet = store.read_object_json(result['review_draft_ref'])
    assert {'kind':review['kind'], 'review_ref':owner} in packet['review_scope']['owners']
    assert store.read_object_json(owner) == review
    # Coverage validates exact frozen owner identity, not a generic passing row.
    task = result['task']
    assert task['scope_pages'] == ['p1']
    assert result['review_draft_ref'] in task['inputs']
    replacements = [{'kind':row['kind'], 'replaces':row['review_ref']} for row in packet['review_scope']['owners']]
    content_review._require_unit_coverage(store, doc, replacements, task)
    with pytest.raises(tasks.EnvelopeError, match='each frozen historical owner'):
        content_review._require_unit_coverage(store, doc, [row for row in replacements if row['replaces']!=owner], task)


def test_outside_local_finding_and_unrelated_units_do_not_expand_scope(tmp_path):
    _, store, doc, review, owner = historical_owner(tmp_path, page_id='p2')
    assert content_review.preproduction_status(store, doc, page_ids=['p1'])['status']=='pass'
    assert owner not in [row['review_ref'] for row in content_review._review_scope_owners(store, doc, [review['kind']], ['p1'])]
    assert content_review._review_scope_owners(store, doc, [], ['p1']) == []
    assert content_review._review_scope_owners(store, doc, [review['kind']], []) == []
    deck_review = {**review, 'findings':[{**review['findings'][0], 'page_id':None}]}
    deck_owner = store.put_json_object(deck_review)
    doc = {**doc, 'reviews':[*doc['reviews'], deck_owner]}
    unrelated = next(kind for kind in content_review.required_units(store, doc) if kind != review['kind'])
    assert deck_owner not in [row['review_ref'] for row in content_review._review_scope_owners(store, doc, [unrelated], ['p1'])]


def test_only_full_current_manuscript_closes_deck_finding_and_retires_outside_owner(tmp_path):
    _, store, doc, review, owner = historical_owner(tmp_path, impact='needs_judgment')
    p1 = next(row for row in doc['pages'] if row['page_id']=='p1')['page']
    closed = deepcopy(review)
    closed.update(status='pass', replaces=owner, observations=['Synthetic full-manuscript variance recheck'])
    closed['findings'] = [{**review['findings'][0], 'resolution':'accepted_variance',
        'resolution_reason':'Synthetic justified variance', 'evidence':[p1]}]
    partial_ref = store.put_json_object(closed)
    partial = {**doc, 'reviews':[*doc['reviews'], partial_ref]}
    artifacts = content_review._current_artifact_digests(store, doc)
    records = [{**store.read_object_json(ref), 'ref':ref} for ref in partial['reviews']]
    assert not review_mod.finding_closed(records, {**review,'ref':owner}, review['findings'][0], artifacts)
    assert owner in [row['review_ref'] for row in content_review._review_scope_owners(store, partial, [review['kind']], ['p1'])]
    # Current complete subjects/dependencies are required even for an accepted variance.
    closed['subjects'].append(p1)
    closed['dependencies'].append({'kind':'content', 'identity':'page:p1', 'sha256':p1['sha256']})
    full_ref = store.put_json_object(closed)
    complete = {**doc, 'reviews':[*doc['reviews'], full_ref]}
    records = [{**store.read_object_json(ref), 'ref':ref} for ref in complete['reviews']]
    assert review_mod.finding_closed(records, {**review,'ref':owner}, review['findings'][0], artifacts)
    assert owner not in [row['review_ref'] for row in content_review._review_scope_owners(store, complete, [review['kind']], ['p1'])]
