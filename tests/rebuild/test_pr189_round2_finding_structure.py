"""Omitted findings do not erase explicit replacement ancestry or root evidence."""
from copy import deepcopy

import pytest

from deck_master import content_review, eligibility
from deck_master.review import finding_closed
from test_pr189_finding_endpoints import chain
from test_review import ref
from test_scoped_preproduction_eligibility import reviewed_scope


@pytest.mark.parametrize('mode', ['close_after_omission', 'omit_after_fixed', 'refix_after_omission',
                                  'reopen_after_omission', 'refix_after_reopen'])
@pytest.mark.parametrize('reverse', [False, True])
def test_replacement_chain_crosses_a_review_omitting_this_finding(mode, reverse):
    owner, fixed, opened, artifacts = chain()
    omitted = deepcopy(fixed)
    omitted.update(ref=ref('omitted'), findings=[], replaces=owner['ref'])
    if mode == 'close_after_omission':
        fixed['replaces'] = omitted['ref']
        rows = [owner, omitted, fixed]
    else:
        omitted['replaces'] = fixed['ref']
        rows = [owner, fixed, omitted]
        if mode in ('reopen_after_omission', 'refix_after_reopen'):
            opened['replaces'] = omitted['ref']
            rows.append(opened)
        if mode in ('refix_after_omission', 'refix_after_reopen'):
            refixed = deepcopy(fixed)
            refixed.update(ref=ref('refixed'), replaces=rows[-1]['ref'])
            rows.append(refixed)
    assert finding_closed(list(reversed(rows)) if reverse else rows, owner, owner['findings'][0], artifacts) is (mode != 'reopen_after_omission')


def test_omitted_intermediate_cannot_drop_the_original_owners_dependency():
    owner, fixed, _, artifacts = chain()
    owner['dependencies'].append({'kind': 'source', 'identity': 's1', 'sha256': ref('source')['sha256']})
    artifacts['source:s1'] = ref('source')['sha256']
    omitted = deepcopy(fixed)
    omitted.update(ref=ref('omitted'), findings=[], replaces=owner['ref'])
    fixed['replaces'] = omitted['ref']
    assert not finding_closed([owner, omitted, fixed], owner, owner['findings'][0], artifacts)


def test_endpoint_can_restore_dependencies_omitted_by_a_historical_intermediate():
    owner, fixed, _, artifacts = chain()
    dependency = {'kind': 'source', 'identity': 's1', 'sha256': ref('source')['sha256']}
    owner['dependencies'].append(dependency)
    artifacts['source:s1'] = dependency['sha256']
    omitted = deepcopy(fixed)
    omitted.update(ref=ref('omitted'), findings=[], replaces=owner['ref'])
    fixed['replaces'] = omitted['ref']
    fixed['dependencies'].append(dependency)
    assert finding_closed([owner, omitted, fixed], owner, owner['findings'][0], artifacts)


def test_cycle_through_an_omitted_finding_is_not_a_closure():
    owner, fixed, _, artifacts = chain()
    omitted = deepcopy(fixed)
    omitted.update(ref=ref('omitted'), findings=[], replaces=owner['ref'])
    owner['replaces'] = omitted['ref']
    assert not finding_closed([owner, fixed, omitted], owner, owner['findings'][0], artifacts)


def test_blocking_records_keep_full_identity_and_count_explicit_logical_owners(tmp_path):
    _, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    current = content_review.preproduction_status(store, doc, page_ids=['p1'])
    owner = store.read_object_json(current['review_refs'][0])
    owner.update(review_id='round2-owner', status='fail', replaces=None, findings=[{
        'finding_id': 'same-local-id', 'kind': 'content', 'impact': 'must_fix', 'resolution': 'open',
        'page_id': 'p1', 'element_refs': [], 'message': 'Synthetic unresolved qualification',
        'expected': 'supported', 'actual': 'unsupported', 'evidence': []}])
    owner_ref = store.put_json_object(owner)
    followup = {**deepcopy(owner), 'replaces': owner_ref, 'observations': ['Synthetic explicit recheck remains open']}
    followup_ref = store.put_json_object(followup)
    unrelated = {**deepcopy(owner), 'observations': ['Synthetic same local review/finding ids, distinct unlinked owner']}
    unrelated_ref = store.put_json_object(unrelated)
    doc = {**doc, 'reviews': [*doc['reviews'], owner_ref, followup_ref, unrelated_ref]}
    status = content_review.preproduction_status(store, doc, page_ids=['p1'])
    assert status['blocking_record_count'] == 3
    assert status['logical_finding_count'] == 2
    rows = status['blocking_findings']
    assert {row['review_ref']['sha256'] for row in rows} == {owner_ref['sha256'], followup_ref['sha256'], unrelated_ref['sha256']}
    assert all(row['page_id'] == 'p1' and row['review_stage'] == 'preproduction' for row in rows)
    assert [row['logical_owner_ref'] for row in rows] == [owner_ref, owner_ref, unrelated_ref]
    decision = eligibility.evaluate(store, doc, doc, 'dispatch.blueprint', {'targets': {'page_ids': ['p1'], 'layers': ['blueprint']}})
    blocked = next(row for row in decision['reasons'] if row['code'] == 'preproduction_blocked')
    assert blocked['open_findings'] == blocked['blocking_record_count'] == 3
    assert blocked['logical_finding_count'] == 2
