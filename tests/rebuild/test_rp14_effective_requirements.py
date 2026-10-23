"""RP-14: synthetic ledger/packet checks; no model or real Host acceptance."""
import pytest

from deck_master import collaboration, content_review, effective_requirements, method_resources, tasks
from synthetic_review_provider import dispatch_with_synthetic_provider, accept_with_synthetic_provider
from test_content_preproduction_review import _deck, _instruction, _scope, _independent_adapter, _dispatch_and_reviews


def decision(project, store, name, *, pages=('p1',), topic='manuscript', layers=('page_copy',), **extra):
    return collaboration.record_decision(
        project, input={'decision_id': name, 'topic': topic, 'disposition': 'accepted',
                        'authority_mode': 'direct_user', 'value': {'requirement': name},
                        'scope': _scope(subject='pages', page_ids=list(pages), layers=list(layers)),
                        'instruction_evidence': _instruction(store, name), **extra},
        base_revision=store.load_document()['revision_id'], operation_id=f'op-{name}-{len(store.load_document()["collaboration"]["decisions"])}')['decision_ref']


def projected(store, *, page='p1', unit='page_copy'):
    return effective_requirements.project_requirements(store, store.load_document(), page_ids=[page], unit=unit)


def test_packet_shares_current_requirements_with_reader_and_excludes_retired(tmp_path):
    project, store = _deck(tmp_path)
    old = decision(project, store, 'copy-constraint')
    current = decision(project, store, 'copy-constraint', replaces=old, value={'requirement': 'new wording'})
    withdrawn = decision(project, store, 'withdraw-me')
    decision(project, store, 'withdraw-me', replaces=withdrawn, disposition='rejected')
    decision(project, store, 'other-page', pages=('p2',))
    document = store.load_document()
    packet = content_review.build_review_packet(store, document, page_ids=['p1'])
    view = packet['effective_requirements']['page_copy']
    assert view['task_facts']['audience'] == '新接单员工'
    assert view['task_facts']['brief'] == '培训材料'
    assert view['request']['scope']['purpose'] == 'working'
    assert view['request']['instruction_evidence']['source_content'] == {'fixture': 'instruction'}
    refs = [row['ref'] for row in view['decisions']]
    assert current in refs and old not in refs and withdrawn not in refs
    assert all(row['decision']['decision_id'] not in {'withdraw-me', 'other-page'} for row in view['decisions'])
    full_packet = content_review.build_review_packet(store, document)
    read = method_resources.read_skill_methods('deck-content', project=project)
    assert read['context']['effective_requirements'] == full_packet['effective_requirements']


def test_pending_review_tracks_only_its_page_requirements_and_reissues(tmp_path):
    project, store = _deck(tmp_path)
    outcome = dispatch_with_synthetic_provider(project, page_ids=['p1'], adapter_context=_independent_adapter(store, store.load_document()))
    task = outcome['task']
    assert tasks.task_inputs_current(store, store.load_document(), task)
    decision(project, store, 'unrelated', pages=('p2',))
    assert tasks.task_inputs_current(store, store.load_document(), task)
    decision(project, store, 'applicable')
    assert not tasks.task_inputs_current(store, store.load_document(), task)
    next_task = dispatch_with_synthetic_provider(project, page_ids=['p1'], adapter_context=_independent_adapter(store, store.load_document()))['task']
    assert next_task['task_id'] != task['task_id']
    assert tasks.task_inputs_current(store, store.load_document(), next_task)


def test_speech_and_visual_requirements_do_not_invalidate_copy_unit(tmp_path):
    project, store = _deck(tmp_path)
    task = dispatch_with_synthetic_provider(project, page_ids=['p1'], adapter_context=_independent_adapter(store, store.load_document()))['task']
    decision(project, store, 'speech-rule', topic='speech', layers=('speech',))
    assert effective_requirements.task_requirements_current(store, store.load_document(), task, unit='page_copy')
    assert not effective_requirements.task_requirements_current(store, store.load_document(), task, unit='speech')
    before = projected(store)
    decision(project, store, 'visual-rule', topic='style', layers=('design',))
    assert projected(store) == before


def test_accepted_review_checks_dispatch_requirements_by_covered_unit(tmp_path):
    project, store = _deck(tmp_path)
    task = dispatch_with_synthetic_provider(project, page_ids=['p1'], adapter_context=_independent_adapter(store, store.load_document()))['task']
    ref = {'sha256': 'synthetic-result'}
    owners = {ref['sha256']: [task]}
    review = {'kind': 'page_copy', 'dependencies': [{'kind': 'content', 'identity': 'page:p1'}]}
    assert effective_requirements.accepted_requirements_current(store, store.load_document(), review, ref, owners)
    decision(project, store, 'unrelated', pages=('p2',))
    assert effective_requirements.accepted_requirements_current(store, store.load_document(), review, ref, owners)
    decision(project, store, 'new-copy')
    assert not effective_requirements.accepted_requirements_current(store, store.load_document(), review, ref, owners)


@pytest.mark.parametrize('disposition', ['deferred', 'rejected'])
def test_nonaccepted_requirement_never_enters_projection(tmp_path, disposition):
    project, store = _deck(tmp_path)
    before = projected(store)
    decision(project, store, 'not-accepted', disposition=disposition)
    assert projected(store) == before


@pytest.mark.parametrize('change_before_accept', [True, False])
def test_real_acceptance_boundary_and_consumption_recheck_current_requirements(tmp_path, change_before_accept):
    project, store = _deck(tmp_path)
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    def submit():
        return accept_with_synthetic_provider(
            project, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], adapter_context=adapter,
            result_payload={'kind': 'review', 'pages': [], 'page_order': [],
                            'artifact_specs': [], 'reviews': reviews, 'usage_events': [], 'notes': 'synthetic RP14'})
    if change_before_accept:
        decision(project, store, 'concurrent-copy-change')
        with pytest.raises(tasks.StaleInputContext):
            submit()
        assert content_review.preproduction_status(store, store.load_document())['status'] != 'pass'
    else:
        assert submit()['status'] == 'accepted'
        assert content_review.preproduction_status(store, store.load_document())['status'] == 'pass'
        speech_ref = next(ref for ref in store.load_document()['reviews'] if store.read_object_json(ref).get('kind') == 'speech')
        speech_review = store.read_object_json(speech_ref)
        assert effective_requirements.accepted_requirements_current(store, store.load_document(), speech_review, speech_ref, {})
        decision(project, store, 'speech-only-change', topic='speech', layers=('speech',))
        assert not effective_requirements.accepted_requirements_current(store, store.load_document(), speech_review, speech_ref, {})
        status = content_review.preproduction_status(store, store.load_document())
        assert status['missing_units'] == ['speech']


def test_frozen_packet_not_recomputed_when_delegated_effectiveness_expires(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    decision(project, store, 'time-bounded-requirement')
    task = dispatch_with_synthetic_provider(project, page_ids=['p1'],
        adapter_context=_independent_adapter(store, store.load_document()))['task']
    # Simulate Runtime effectiveness becoming false without mutating history
    # (e.g. the existing delegated authorization expiry path).
    monkeypatch.setattr(effective_requirements.dependency_slices, 'accepted_decision', lambda *a, **kw: False)
    assert not effective_requirements.task_requirements_current(store, store.load_document(), task)


def test_reader_v2_returns_same_scoped_requirements(tmp_path):
    from deck_master.work_context import PROTOCOL
    project, store = _deck(tmp_path)
    task = dispatch_with_synthetic_provider(project, page_ids=['p1'],
        adapter_context=_independent_adapter(store, store.load_document()))['task']
    decision(project, store, 'other-page', pages=('p2',))
    v1 = method_resources.read_skill_methods('deck-review', project=project, task_id=task['task_id'])
    v2 = method_resources.read_skill_methods('deck-review', project=project, task_id=task['task_id'], read_protocol=PROTOCOL)
    assert v2['context']['effective_requirements'] == v1['context']['effective_requirements']
