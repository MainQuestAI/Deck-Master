"""Explicit synthetic mechanism fixtures; not actual reviewer performance."""
import copy

import pytest

from deck_master import content_review, models, outline_review, service, tasks
from test_content_preproduction_review import _deck, _review
from test_workbench_reads import commit
from synthetic_review_provider import synthetic_context, synthetic_runtime_call, accept_with_synthetic_provider
from rc3_fixtures import claim_fixture_task


def outline_project(tmp_path):
    project, store = _deck(tmp_path)
    doc = store.load_document()
    plan = store.read_object_json(doc['content_plan'])
    plan.update(mode='planned', page_links=[])
    doc['content_plan'] = store.put_json_object(plan)
    doc['pages'] = []
    commit(store, doc, 'synthetic-outline-snapshot')
    return project, store


def test_outline_packet_is_read_only_and_unavailable_channel_is_honest(tmp_path):
    project, store = outline_project(tmp_path)
    before = store.load_document()
    files = {str(p): p.read_bytes() for p in project.rglob('*') if p.is_file()}
    packet = outline_review.packet(store, before)
    assert packet['review_subject'] == 'outline'
    assert packet['manuscript'] == {'pages': [], 'page_order': []}
    assert packet['plan']['input']['page_roles'] and packet['narrative']['nodes']
    assert set(packet['required_units']) == {'argument', 'progression'}
    result = outline_review.dispatch(project)
    assert result['status'] == 'needs_reviewer'
    assert {str(p): p.read_bytes() for p in project.rglob('*') if p.is_file()} == files
    assert store.load_document() == before


def test_empty_pages_require_explicit_valid_outline_subject(tmp_path):
    project, store = outline_project(tmp_path)
    for subject, units in [(None, ['argument']), ('outline', ['page_copy'])]:
        with pytest.raises(service.ServiceError):
            service.open_host_task(store, kind='review', page_ids=[], review_stage='preproduction',
                review_subject=subject, instruction='test',
                review_units=[{'kind': u, 'page_ids': [], 'reason': 'missing'} for u in units])
    doc = store.load_document()
    with pytest.raises(models.ModelError):
        outline_review.require_outline(store, {**doc, 'narrative': None})


def test_dispatch_dedup_accept_and_production_separation(tmp_path):
    project, store = outline_project(tmp_path)
    ctx = synthetic_context()
    outcome = synthetic_runtime_call(outline_review.dispatch, project, adapter_context=ctx)
    task = outcome['task']
    assert task['review_subject'] == 'outline' and task['scope_pages'] == []
    assert 'outline_review.v1' in task['required_capabilities']
    assert store.load_document()['compatibility']['minimum_writer'] == 'outline-review.v1'
    assert synthetic_runtime_call(outline_review.dispatch, project, adapter_context=ctx)['task']['task_id'] == task['task_id']
    claim_fixture_task(project, task, execution_ref='exec-independent')
    doc = store.load_document()
    reviews = [{**_review(store, doc, unit, reviewer={'type': 'independent_host', 'id': 'model-b',
                'execution_ref': 'exec-independent', 'independence_confirmed': True,
                'identity_receipt': None, 'assurance': 'host_attested'}), 'review_subject': 'outline'}
               for unit in outline_review.UNITS]
    payload = {'kind': 'review', 'pages': [], 'page_order': [], 'artifact_specs': [],
               'reviews': reviews, 'usage_events': [], 'notes': 'synthetic mechanism only'}
    accept_with_synthetic_provider(project, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload=payload, adapter_context=ctx)
    assert outline_review.status(store, store.load_document())['status'] == 'pass'
    assert content_review.preproduction_status(store, store.load_document())['status'] == 'no_manuscript'
    assert outline_review.dispatch(project)['status'] == 'already_reviewed'
    changed = copy.deepcopy(store.load_document())
    narrative = store.read_object_json(changed['narrative'])
    narrative['nodes'][0]['statement'] += '（更新条件）'
    changed['narrative'] = store.put_json_object(narrative)
    assert not tasks.task_inputs_current(store, changed, task)


def test_outline_finding_requires_same_owner_current_outline_and_real_change(tmp_path):
    from deck_master.editing import _current_artifact_digests
    from deck_master.review import finding_closed
    project, store = outline_project(tmp_path)
    before = store.load_document()
    finding = {'finding_id': 'cause-1', 'kind': 'content', 'impact': 'must_fix',
               'resolution': 'open', 'page_id': None, 'element_refs': ['node:n1'],
               'message': 'Conclusion exceeds the stated condition', 'expected': 'retain condition',
               'actual': 'condition missing', 'evidence': [before['narrative']]}
    owner = {**_review(store, before, 'argument', reviewer={'type': 'host_self', 'id': 'synthetic-author',
             'execution_ref': 'synthetic-author', 'assurance': 'host_attested'}, status='fail', findings=[finding]),
             'review_subject': 'outline'}
    owner['ref'] = store.put_json_object(owner)
    candidate = {**copy.deepcopy(owner), 'status': 'pass', 'replaces': owner['ref']}
    candidate.pop('ref')
    candidate['findings'][0].update(resolution='fixed', resolution_reason='Restored condition')
    candidate['ref'] = store.put_json_object(candidate)
    assert not finding_closed([owner, candidate], owner, finding, _current_artifact_digests(store, before))
    doc = copy.deepcopy(before)
    narrative = store.read_object_json(doc['narrative'])
    narrative['nodes'][0]['statement'] += '；仅适用于已确认来源。'
    doc['narrative'] = store.put_json_object(narrative)
    plan = store.read_object_json(doc['content_plan'])
    plan['narrative_ref'] = doc['narrative']
    doc['content_plan'] = store.put_json_object(plan)
    commit(store, doc, 'synthetic-outline-repair')
    doc = store.load_document()
    repaired = {**_review(store, doc, 'argument', reviewer=owner['reviewer'], findings=candidate['findings']),
                'review_subject': 'outline', 'replaces': owner['ref']}
    repaired['ref'] = store.put_json_object(repaired)
    artifacts = _current_artifact_digests(store, doc, [*owner['subjects'], *repaired['subjects']])
    assert finding_closed([owner, repaired], owner, finding, artifacts)
    assert not finding_closed([owner, {**repaired, 'replaces': None}], owner, finding, artifacts)
    assert not finding_closed([owner, {**repaired, 'review_subject': None}], owner, finding, artifacts)
    # Changes to unrelated Page/visual/notes facts cannot substitute for this
    # Narrative/Plan closure and its original finding identity.
    assert not finding_closed([owner, {**repaired, 'review_id': 'unrelated'}], owner, finding, artifacts)


def test_native_outline_transport_returns_its_own_gate_and_replay_is_no_call(tmp_path, monkeypatch):
    from deck_master import native_review
    from test_native_review import FixtureSession
    FixtureSession.calls = []
    FixtureSession.status = 'pass'
    FixtureSession.corrupt = False
    FixtureSession.before_finish = None
    monkeypatch.setattr(native_review, 'CodexReviewSession', FixtureSession)
    project, store = outline_project(tmp_path)
    result = native_review.run(project, subject='outline')
    assert result['status'] == 'reviewed'
    assert result['preproduction']['review_subject'] == 'outline'
    assert result['preproduction']['status'] == 'pass'
    assert result['preproduction']['production_qualified'] is False
    assert content_review.preproduction_status(store, store.load_document())['status'] == 'no_manuscript'
    assert native_review.run(project, subject='outline')['status'] == 'already_reviewed'
    assert len(FixtureSession.calls) == 1
    assert FixtureSession.calls[0]['packet']['review_subject'] == 'outline'
