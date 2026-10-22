"""L1 scoped review admission through real requests, reviews and dispatch."""
import pytest

from deck_master import content_review, eligibility, service
from rc3_fixtures import settle_fidelity_review
from test_eligibility_enforcement import _project, _start, _scope, _grant
from test_rc3_notes_visual_inputs import _seed_imported_plan


def reviewed_scope(tmp_path):
    project, store = _project(tmp_path)
    _seed_imported_plan(store)
    _start(project, store)
    settle_fidelity_review(project, page_ids=['p1', 'p2'], execution_ref='L1-before-scope', scenario='all-page initial requirement')
    _start(project, store, operation_id='narrow-request', scope=_scope(page_ids=['p1']))
    assert content_review.preproduction_status(store, store.load_document(), page_ids=['p1'])['status'] == 'missing'
    _grant(project, store, actions=['dispatch.blueprint', 'allowance.allocate', 'change.commit'], scope=_scope(page_ids=['p1']))
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        content_review.dispatch_preproduction_review(project, page_ids=['p1', 'p2'])
    assert 'scope_exceeded' in denied.value.decision['reason_codes']
    settle_fidelity_review(project, page_ids=['p1'], execution_ref='L1-current-scope', scenario='review current authorized p1 only')
    return project, store


def test_current_scoped_review_admits_only_scoped_production(tmp_path):
    project, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    assert content_review.preproduction_status(store, doc, page_ids=['p1'])['status'] == 'pass'
    assert content_review.preproduction_status(store, doc)['status'] == 'missing'
    for action in ('change.commit', 'style.trial', 'style.expand'):
        scoped = eligibility.evaluate(store, doc, doc, action,
            {'targets': {'page_ids': ['p1'], 'layers': ['blueprint']}})
        assert scoped['preproduction']['satisfied']
        assert 'preproduction_blocked' not in scoped['reason_codes']
    entry = next(page for page in doc['pages'] if page['page_id'] == 'p1')
    task = service.open_blueprint_task(store, doc, entry)
    assert task['scope_pages'] == ['p1']
    assert task['status'] == 'awaiting_host'
    assert task['collaboration_binding']['phase'] == 'production'
    outside = next(page for page in doc['pages'] if page['page_id'] == 'p2')
    with pytest.raises(eligibility.EligibilityBlocked) as denied:
        service.open_blueprint_task(store, doc, outside)
    assert 'scope_exceeded' in denied.value.decision['reason_codes']


@pytest.mark.parametrize('action', ['compile.ppt', 'stage.assemble'])
def test_full_deck_operations_cannot_use_scoped_review(tmp_path, action):
    _, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    result = eligibility.evaluate(store, doc, doc, action, {'targets': {'page_ids': ['p1'], 'layers': ['output'], 'subject': 'deck'}})
    assert not result['preproduction']['satisfied']
    assert 'preproduction_blocked' in result['reason_codes']


def test_unknown_or_empty_action_target_never_reuses_partial_pass(tmp_path):
    _, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    for targets in ({}, {'page_ids': []}, {'page_ids': ['unknown']}):
        result = eligibility.evaluate(store, doc, doc, 'dispatch.blueprint', {'targets': targets})
        assert not result['preproduction']['satisfied']
        assert not result['allowed']


@pytest.mark.parametrize('finding_page,blocked', [(None, True), ('p1', True), ('p2', False)])
def test_scoped_pass_preserves_unresolved_deck_and_target_findings(tmp_path, finding_page, blocked):
    _, store = reviewed_scope(tmp_path)
    doc = store.load_document()
    current = content_review.preproduction_status(store, doc, page_ids=['p1'])
    # Immutable historical defect fixture, not a new passing review or closure.
    # It is deliberately separate from the real accepted scoped pass above.
    review = store.read_object_json(current['review_refs'][0])
    review = {**review, 'review_id': 'historical-unresolved-defect', 'status': 'fail', 'replaces': None,
              'findings': [{'finding_id': 'scope-defect', 'kind': 'content', 'impact': 'must_fix',
                  'resolution': 'open', 'page_id': finding_page, 'element_refs': [],
                  'message': 'L1 unresolved historical defect', 'expected': 'supported claim',
                  'actual': 'unsupported claim', 'evidence': []}]}
    doc = {**doc, 'reviews': [*doc['reviews'], store.put_json_object(review)]}
    result = eligibility.evaluate(store, doc, doc, 'dispatch.blueprint',
        {'targets': {'page_ids': ['p1'], 'layers': ['blueprint']}})
    assert result['preproduction']['satisfied'] is (not blocked)
    assert ('preproduction_blocked' in result['reason_codes']) is blocked
    if blocked:
        assert result['preproduction']['blocking_findings'][0]['finding_id'] == 'scope-defect'
