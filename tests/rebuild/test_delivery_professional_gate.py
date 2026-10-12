"""T01 delivery professional predicate: positive/negative matrix over the
three delivery entries — export, handoff-check, final-readiness
(AC-P01/P02/P03, content collaboration v1.2 CONTRACTS §8).

The human positive runs through the formal submission entry
(``service.accept_result`` review envelope) so the receipt passes real
schema/acceptance validation. All refusals are asserted at the formal entry
APIs with no delivery output produced; the synthetic identity adapter is a
controlled L1 fixture (CONTRACTS §12.1), never a claim that a human reviewed.
"""
import json
from pathlib import Path

import pytest
from PIL import Image

import deck_master.cli as cli
from deck_master import service
from deck_master import tasks as tasks_mod
from deck_master.delivery_eligibility import professional_policy
from deck_master.editing import export_project
from deck_master.handoff import check_handoff
from deck_master.models import bump_revision, content_identity
from deck_master.pipeline import artifact as adopt_artifact
from deck_master.store import Store, StoreError

from test_export import (_passing_deck, _review, _set_policy,
                         human_professional_reviewer, professional_dependencies)


def _complete_page_slots(store, tmp_path):
    """handoff-check inspects blueprint/svg_preview slots; give the deck real
    ones so engineering handoff can go green independently of the gate."""
    work = tmp_path / 'slots'
    work.mkdir(exist_ok=True)
    png = work / 'page.png'
    Image.new('RGB', (960, 540), 'white').save(png)
    svg = work / 'page.svg'
    svg.write_text('<svg viewBox="0 0 10 10"/>')
    # adopt_artifact may advance the head (thumbnail warming); adopt first,
    # then commit the slot swap against the head it left behind.
    entries = store.load_document()['pages']
    slots = {entry['page_id']: (adopt_artifact(store, png, 'blueprint', page_id=entry['page_id']),
                                adopt_artifact(store, svg, 'svg_preview', page_id=entry['page_id']))
             for entry in entries}
    fresh = store.load_document()
    bumped = bump_revision(fresh, {'operation_id': 'complete-slots', 'kind': 'task_update',
                                   'description': 'slots', 'read_set': []})
    for entry in bumped['pages']:
        entry['blueprint'], entry['svg_preview'] = slots[entry['page_id']]
    store.commit_change(base_revision=fresh['revision_id'], document=bumped,
                        operation_id='complete-slots')


def _current_deck_file(store, tmp_path):
    pptx_ref = store.load_document()['outputs']['pptx']
    data = store.read_object_bytes(store.read_object_json(pptx_ref)['file'])
    candidate = tmp_path / 'candidate.pptx'
    candidate.write_bytes(data)
    return candidate


def _final_readiness(project, capsys):
    assert cli.main(['final-readiness', '--project', str(project)]) == 0
    return json.loads(capsys.readouterr().out)


def _accept_review(project, store, review, *, task_id='review-professional',
                   operation_id='op-professional'):
    """Formal submission entry: dispatch a final review task, then accept the
    envelope carrying the review (service.accept_result → _adopt_review)."""
    document = store.load_document()
    task = tasks_mod.new_task(
        task_id=task_id, operation_id=operation_id, kind='review',
        scope_pages=[entry['page_id'] for entry in document['pages']],
        instruction='review', inputs=[entry['page'] for entry in document['pages']],
        dependencies=[], dispatch_revision=document['revision_id'],
        produced_against=content_identity(document))
    task_ref = store.put_json_object(task)
    dispatch_operation = f'dispatch-{operation_id}'
    bumped = bump_revision(document, {'operation_id': dispatch_operation, 'kind': 'task_update',
                                      'description': 'dispatch review', 'read_set': []})
    bumped['tasks'] = list(bumped.get('tasks') or []) + [task_ref]
    store.commit_change(base_revision=document['revision_id'], document=bumped,
                        operation_id=dispatch_operation)
    dispatched = store.load_document()
    record = next(store.read_object_json(ref) for ref in dispatched['tasks']
                  if store.read_object_json(ref)['task_id'] == task_id)
    return service.accept_result(project, task_id=task_id,
                                 operation_id=record['operation_id'],
                                 produced_against=record['produced_against'],
                                 result_payload={'kind': 'review', 'files': [], 'reviews': [review]})


def _professional_review(document, *, review_id, status, reviewer, dependencies,
                         findings=(), observations=('已逐页核对整稿正文与来源引用。',),
                         subjects=None, replaces=None):
    return {
        'schema_version': 'deck_review.v1', 'review_id': review_id,
        'kind': 'professional_use', 'status': status, 'review_stage': 'final',
        'subjects': list(subjects if subjects is not None else
                         [document['outputs']['pptx']] + [entry['page'] for entry in document['pages']]),
        'dependencies': list(dependencies), 'reviewer': reviewer,
        'observations': list(observations), 'findings': list(findings),
        'created_at': '2026-10-21T08:00:00Z', 'replaces': replaces,
    }


def _assert_refused_everywhere(tmp_path, project, store, capsys, *, reason,
                               engineering_shadowed=False):
    """No entry may satisfy the human policy and no delivery output is produced
    (AC-P02). When a recorded non-pass professional review also degrades the
    shared check summary, the engineering gate refuses first — the named
    professional gap must still be visible in every entry's result."""
    with pytest.raises(StoreError) as failure:
        export_project(project, output_dir=tmp_path / 'delivery-attempt', purpose='delivery')
    message = str(failure.value)
    assert ('professional or human review' in message
            or 'delivery requires every required check' in message), message
    if not engineering_shadowed:
        assert 'professional or human review' in message, message
    reasons = {gap['reason'] for gap in failure.value.payload()['error']['gaps']}
    assert reason in reasons, reasons
    assert not (tmp_path / 'delivery-attempt').exists(), 'a refused export leaves no package'

    report = check_handoff(project, file_path=_current_deck_file(store, tmp_path), purpose='delivery')
    assert report['professional']['satisfied'] is False
    assert report['professional']['human_signoff'] is False
    assert reason in report['professional']['gap_reasons'], report['professional']
    assert 'professional_review_not_satisfied' in report['gaps']
    assert report['status'] == 'blocked'

    readiness = _final_readiness(project, capsys)
    assert readiness['status'] == 'blocked'
    if engineering_shadowed:
        assert readiness['engineering_ready'] is False
        assert readiness['review_status'] in ('not_evaluated', 'fail'), \
            'a recorded non-pass professional review must degrade the shared summary'
    else:
        assert readiness['engineering_ready'] is True, 'engineering pass must stay visible separately'
        assert readiness['review_status'] == 'pass'
    assert readiness['professional']['satisfied'] is False
    assert reason in readiness['professional']['gap_reasons'], readiness['professional']


@pytest.mark.parametrize('reviewer_type,extra', [
    ('host_self', {}),
    ('tool', {'independence_confirmed': True}),
    ('independent_host', {'execution_ref': 'run-123', 'independence_confirmed': True}),
])
def test_non_human_reviewers_cannot_satisfy_human_policy(tmp_path, capsys, synthetic_human_adapter,
                                                         reviewer_type, extra):
    """The old gate let any professional_use kind through regardless of who
    "reviewed"; independent models are not humans (AC-P02, F0)."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    reviewer = {'type': reviewer_type, 'id': f'agent-{reviewer_type}', 'execution_ref': None,
                'independence_confirmed': False, **extra}
    _review(store, document, 'professional_use', 'pass', seed=f'model-{reviewer_type}',
            reviewer=reviewer)
    _assert_refused_everywhere(tmp_path, project, store, capsys, reason='reviewer_not_human')


def test_human_without_verifiable_evidence_cannot_satisfy(tmp_path, capsys):
    """A human reviewer type alone, an unregistered adapter, or a tampered
    receipt binding each leave the strict policy blocked with a named gap."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()

    _review(store, document, 'professional_use', 'pass', seed='human-no-receipt',
            reviewer={'type': 'human_internal', 'id': 'reviewer-li', 'execution_ref': None,
                      'independence_confirmed': True})
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='human_identity_evidence_missing')


def test_unregistered_identity_adapter_cannot_satisfy(tmp_path, capsys):
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='human-unknown-adapter',
            reviewer=human_professional_reviewer(document, adapter_id='unregistered-channel'))
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='identity_adapter_unavailable')


def test_adapter_rejects_mismatched_receipt(tmp_path, capsys, synthetic_human_adapter):
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    reviewer = human_professional_reviewer(document)
    reviewer['identity_receipt']['project_id'] = 'some-other-project'
    _review(store, document, 'professional_use', 'pass', seed='human-wrong-project',
            reviewer=reviewer)
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='receipt_project_mismatch')


def test_replayed_receipt_event_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter):
    """A review reusing a verified event_id for different receipt content is a
    replay, not new evidence; the adapter rejects it and the policy stays
    unsatisfied."""
    synthetic_human_adapter['evt-replay-1'] = 'fingerprint-of-a-different-receipt'
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='human-replay',
            reviewer=human_professional_reviewer(document, event_id='evt-replay-1'))
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='receipt_event_replayed')


@pytest.mark.parametrize('status', ['not_evaluated', 'needs_review', 'not_applicable'])
def test_non_pass_statuses_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter, status):
    """Only an explicit pass satisfies; the old ``status != fail`` shortcut is
    gone (AC-P02: empty/blanket statuses unlock nothing)."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', status, seed=f'status-{status}',
            reviewer=human_professional_reviewer(document, event_id=f'evt-{status}'))
    _assert_refused_everywhere(tmp_path, project, store, capsys, reason='status_not_pass',
                               engineering_shadowed=True)


def test_human_review_of_wrong_kind_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter):
    """Any-kind human review does not satisfy the professional_use gate."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'privacy', 'pass', seed='human-privacy',
            reviewer=human_professional_reviewer(document, event_id='evt-privacy'))
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='no_professional_review')


@pytest.mark.parametrize('seed,deps', [
    ('empty-deps', []),
    ('stale-deps', [{'kind': 'content', 'identity': 'page:p1', 'sha256': 'b' * 64}]),
])
def test_incomplete_dependencies_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter,
                                                seed, deps):
    """``all([])`` never counts as a complete dependency set; the runtime
    minimum is the current PPTX plus every page content digest."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed=seed,
            reviewer=human_professional_reviewer(document, event_id=f'evt-{seed}'),
            dependencies=deps)
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='required_dependencies_incomplete')


def test_stale_extra_declared_dependency_blocks_all_entries(tmp_path, capsys,
                                                            synthetic_human_adapter):
    """F01 (PR107 round 2): the runtime minimum set is only the floor — every
    declared dependency must resolve against the same current artifact map the
    shared check summary uses. A stale extra dependency (style:p1 with a wrong
    sha) is stale everywhere, never "stale in the summary, valid for delivery"."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    dependencies = professional_dependencies(store, document)
    dependencies.append({'kind': 'style', 'identity': 'p1', 'sha256': 'f' * 64})
    review = _professional_review(document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-stale-extra'),
                                  dependencies=dependencies)
    assert _accept_review(project, store, review, task_id='review-stale-extra',
                          operation_id='op-stale-extra')['status'] == 'accepted'
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is False
    assert 'stale_review_dependency' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='stale_review_dependency')


def test_unresolvable_extra_declared_dependency_blocks_all_entries(tmp_path, capsys,
                                                                   synthetic_human_adapter):
    """F01: an extra declared dependency that resolves nowhere (source that
    does not exist) cannot back a valid human pass."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    dependencies = professional_dependencies(store, document)
    dependencies.append({'kind': 'source', 'identity': 'missing-source-1', 'sha256': 'a' * 64})
    review = _professional_review(document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-unresolvable'),
                                  dependencies=dependencies)
    assert _accept_review(project, store, review, task_id='review-unresolvable',
                          operation_id='op-unresolvable')['status'] == 'accepted'
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is False
    assert 'unresolvable_review_dependency' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='unresolvable_review_dependency')


def test_valid_extra_declared_dependencies_still_satisfy(tmp_path, capsys,
                                                         synthetic_human_adapter):
    """F01 positive: complete minimum set plus extra dependencies that all
    resolve and match keep the legitimate human path open — the fix must not
    strand valid reviews."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    from deck_master.editing import _current_artifact_digests
    artifacts = _current_artifact_digests(store, document)
    dependencies = professional_dependencies(store, document)
    dependencies.append({'kind': 'style', 'identity': 'p1', 'sha256': artifacts['style:p1']})
    dependencies.append({'kind': 'artifact', 'identity': 'svg:p1',
                         'sha256': artifacts['artifact:svg:p1']})
    review = _professional_review(document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-valid-extra'),
                                  dependencies=dependencies)
    assert _accept_review(project, store, review, task_id='review-valid-extra',
                          operation_id='op-valid-extra')['status'] == 'accepted'
    exported = export_project(project, output_dir=tmp_path / 'delivery-ok', purpose='delivery')
    assert exported['status'] == 'exported'
    readiness = _final_readiness(project, capsys)
    assert readiness['status'] == 'ready'
    assert readiness['professional']['human_signoff'] is True


def test_empty_observations_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter):
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='no-observations',
            reviewer=human_professional_reviewer(document, event_id='evt-no-obs'),
            observations=['', '   '])
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='no_substantive_observations')


def test_open_must_fix_cannot_satisfy(tmp_path, capsys, synthetic_human_adapter):
    finding = {'finding_id': 'pf-1', 'kind': 'content', 'impact': 'must_fix', 'page_id': 'p1',
               'element_refs': ['atom:p1:block:b1:text'], 'message': '结论缺限定',
               'expected': '带边界', 'actual': '无边界', 'evidence': [], 'resolution': 'open'}
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='pass-with-open-fix',
            reviewer=human_professional_reviewer(document, event_id='evt-open-fix'),
            findings=[finding])
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='open_must_fix_findings',
                               engineering_shadowed=True)


def test_incomplete_fail_on_current_deck_still_blocks(tmp_path, capsys, synthetic_human_adapter):
    """Regression (PR107 review P1-1): a fail bound to the current PPTX keeps
    its blocking power even when its dependency list is incomplete — a fail's
    missing dependencies must never soften it into invisibility while a
    verified human pass exists."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='human-pass-complete',
            reviewer=human_professional_reviewer(document, event_id='evt-pass-complete'))
    _review(store, store.load_document(), 'professional_use', 'fail', seed='human-fail-thin',
            reviewer=human_professional_reviewer(document, event_id='evt-fail-thin'),
            dependencies=[])
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is False
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')


def test_deck_level_fail_without_findings_still_blocks(tmp_path, capsys, synthetic_human_adapter):
    """Regression (PR107 review P1-1, sharper variant): a fail whose subjects
    cite only the deck file and which carries no page findings never enters a
    check_summary dimension, so engineering stays green — the professional
    gate alone must refuse delivery."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    reviewer = human_professional_reviewer(document, event_id='evt-deck-fail')
    _review(store, document, 'professional_use', 'fail', seed='human-deck-fail',
            reviewer=reviewer,
            subjects=[document['outputs']['pptx']],
            observations=['整稿复核不通过：中心论证与任务不匹配。'],
            dependencies=[])
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is False
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')


def test_review_binding_replaced_pptx_is_not_current(tmp_path, synthetic_human_adapter):
    """A review of the previous deck file stays historical after the output is
    replaced; the unified predicate names the stale subject directly."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='human-old-deck',
            reviewer=human_professional_reviewer(document, event_id='evt-old-deck'))
    new_file = tmp_path / 'deck-v2.pptx'
    new_file.write_bytes(
        store.read_object_bytes(store.read_object_json(document['outputs']['pptx'])['file']) + b'\x00')
    new_ref = adopt_artifact(store, new_file, 'pptx')
    fresh = store.load_document()
    bumped = bump_revision(fresh, {'operation_id': 'replace-pptx', 'kind': 'task_update',
                                   'description': 'replace', 'read_set': []})
    bumped['outputs']['pptx'] = new_ref
    store.commit_change(base_revision=fresh['revision_id'], document=bumped,
                        operation_id='replace-pptx')
    policy = professional_policy(store, store.load_document())
    assert policy['required'] is True and policy['satisfied'] is False
    assert 'subject_not_current_pptx' in policy['gap_reasons'], policy['gap_reasons']


def test_newer_fail_masks_older_pass_until_explicit_replacement(tmp_path, synthetic_human_adapter):
    """An earlier pass never masks a newer current fail (F0); only an explicit
    replacement review that re-judges the finding retires the fail."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='human-pass-first',
            reviewer=human_professional_reviewer(document, event_id='evt-pass-first'))
    assert professional_policy(store, store.load_document())['human_signoff'] is True

    _review(store, store.load_document(), 'professional_use', 'fail', seed='human-fail-second',
            reviewer=human_professional_reviewer(document, event_id='evt-fail-second'),
            findings=[{'finding_id': 'pf-1', 'kind': 'content', 'impact': 'must_fix',
                       'page_id': 'p1', 'element_refs': [], 'message': '限定缺失',
                       'expected': '有', 'actual': '无', 'evidence': [], 'resolution': 'open'}])
    fail_ref = store.load_document()['reviews'][-1]
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is False
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']

    replacement = human_professional_reviewer(store.load_document(), event_id='evt-rejudge',
                                              reviewer_id='reviewer-zhao')
    _review(store, store.load_document(), 'professional_use', 'pass', seed='human-fail-second-r2',
            reviewer=replacement,
            findings=[{'finding_id': 'pf-1', 'kind': 'content', 'impact': 'must_fix',
                       'page_id': 'p1', 'element_refs': [], 'message': '限定缺失',
                       'expected': '有', 'actual': '已补齐', 'evidence': [], 'resolution': 'fixed',
                       'resolution_reason': '重审后补上适用边界'}])
    doc = store.load_document()
    record = store.read_object_json(doc['reviews'][-1])
    record['review_id'] = 'rv-human-fail-second'
    record['replaces'] = fail_ref
    changed = bump_revision(doc, {'operation_id': 'rejudge-professional', 'kind': 'task_update',
                                  'description': 'rejudge', 'read_set': []})
    changed['reviews'][-1] = store.put_json_object(record)
    store.commit_change(base_revision=doc['revision_id'], document=changed,
                        operation_id='rejudge-professional')
    policy = professional_policy(store, store.load_document())
    assert policy['satisfied'] is True and policy['human_signoff'] is True, policy
    assert 'professional_review_failed' not in policy['gap_reasons']


def test_positive_human_review_via_formal_submission(tmp_path, capsys, synthetic_human_adapter):
    """AC-P01: a receipt-carrying human professional_use pass, submitted
    through the formal review envelope, satisfies export, handoff-check and
    final-readiness consistently on the same snapshot."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()

    dispatch_operation = 'dispatch-professional'
    task = tasks_mod.new_task(
        task_id='review-professional', operation_id='op-professional', kind='review',
        scope_pages=['p1'], instruction='human professional use review',
        inputs=[document['pages'][0]['page']], dependencies=[],
        dispatch_revision=document['revision_id'],
        produced_against=content_identity(document))
    task_ref = store.put_json_object(task)
    bumped = bump_revision(document, {'operation_id': dispatch_operation, 'kind': 'task_update',
                                      'description': 'dispatch professional review', 'read_set': []})
    bumped['tasks'] = list(bumped.get('tasks') or []) + [task_ref]
    store.commit_change(base_revision=document['revision_id'], document=bumped,
                        operation_id=dispatch_operation)

    dispatched = store.load_document()
    task_record = next(store.read_object_json(ref) for ref in dispatched['tasks']
                       if store.read_object_json(ref)['task_id'] == 'review-professional')
    review = {
        'schema_version': 'deck_review.v1', 'review_id': 'rv-professional',
        'kind': 'professional_use', 'status': 'pass', 'review_stage': 'final',
        'subjects': [dispatched['outputs']['pptx']] + [e['page'] for e in dispatched['pages']],
        'dependencies': professional_dependencies(store, dispatched),
        'reviewer': human_professional_reviewer(dispatched, event_id='evt-formal-human'),
        'observations': ['已逐页核对整稿正文、限定与来源引用，确认可用于目标场景。'],
        'findings': [], 'created_at': '2026-09-21T08:00:00Z', 'replaces': None,
    }
    outcome = service.accept_result(project, task_id='review-professional',
                                    operation_id=task_record['operation_id'],
                                    produced_against=task_record['produced_against'],
                                    result_payload={'kind': 'review', 'files': [], 'reviews': [review]})
    assert outcome['status'] == 'accepted'

    exported = export_project(project, output_dir=tmp_path / 'delivery-ok', purpose='delivery')
    assert exported['status'] == 'exported'
    report = json.loads((tmp_path / 'delivery-ok' / 'delivery.json').read_text('utf-8'))
    assert report['professional'] == {'required': True, 'satisfied': True,
                                      'human_signoff': True, 'gap_reasons': []}

    handoff = check_handoff(project, file_path=_current_deck_file(store, tmp_path),
                            purpose='delivery')
    assert handoff['status'] == 'verified'
    assert handoff['professional']['human_signoff'] is True

    readiness = _final_readiness(project, capsys)
    assert readiness['status'] == 'ready'
    assert readiness['engineering_ready'] is True
    assert readiness['professional']['human_signoff'] is True


def test_policy_false_stays_honest_about_no_human_signoff(tmp_path):
    """AC-P03: with the switch off, delivery follows the other conditions and
    the report must not dress the result up as human approval."""
    project, store = _passing_deck(tmp_path)
    outcome = export_project(project, output_dir=tmp_path / 'delivery-false', purpose='delivery')
    assert outcome['status'] == 'exported'
    report = json.loads((tmp_path / 'delivery-false' / 'delivery.json').read_text('utf-8'))
    assert report['professional'] == {'required': False, 'satisfied': True,
                                      'human_signoff': False, 'gap_reasons': []}
    assert report['professional_evidence']['professional_use'] == 'not_evaluated'


def test_blocked_gate_keeps_review_copy_available_and_labeled(tmp_path):
    """AC-P03: a missing human review blocks delivery but the review copy is
    obtainable and explicitly carries no human approval."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    with pytest.raises(StoreError, match='professional or human review'):
        export_project(project, output_dir=tmp_path / 'no-delivery', purpose='delivery')
    outcome = export_project(project, output_dir=tmp_path / 'review-copy', purpose='review')
    assert outcome['status'] == 'exported'
    report = json.loads((tmp_path / 'review-copy' / 'delivery.json').read_text('utf-8'))
    assert report['purpose'] == 'review'
    assert report['evidence_level'] == 'engineering'
    assert report['professional']['required'] is True
    assert report['professional']['satisfied'] is False
    assert report['professional']['human_signoff'] is False
    assert 'no human approval' in report['notice']
