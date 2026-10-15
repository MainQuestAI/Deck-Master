"""T01 delivery professional predicate: positive/negative matrix over the
three delivery entries — export, handoff-check, final-readiness
(AC-P01/P02/P03, content collaboration v1.2 CONTRACTS §8).

The human positive runs through the formal submission entry
(``service.accept_result`` review envelope) so the receipt passes real
schema/acceptance validation. All refusals are asserted at the formal entry
APIs with no delivery output produced; the synthetic identity adapter is a
controlled L1 fixture (CONTRACTS §12.1), never a claim that a human reviewed.
"""
import copy
import io
import json
from pathlib import Path

import pytest
from PIL import Image

import deck_master.cli as cli
from deck_master import service
from deck_master import delivery_eligibility
from deck_master.editing import export_project
from deck_master.handoff import check_handoff
from deck_master.models import bump_revision
from deck_master.pipeline import artifact as adopt_artifact
from deck_master.store import Store, StoreError

from test_export import (_passing_deck, _review, _set_policy,
                         human_professional_reviewer, professional_dependencies,
                         projection_subject, selected_professional_policy)


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
    document = store.load_document()
    data = store.read_object_bytes(projection_subject(store, document))
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
    task = service.open_host_task(store, kind='review',
        page_ids=[entry['page_id'] for entry in document['pages']],
        instruction=f'L1 synthetic final professional predicate: {task_id}/{operation_id}',
        review_stage='final', extra_inputs=review['subjects'])
    assert task['collaboration_binding']['phase'] == 'review'
    assert {'collaboration.v1', 'rc3-entry.v1'} <= set(task['required_capabilities'])
    service.task_start(project, task_id=task['task_id'],
        execution_ref=f'synthetic-l1-host:{operation_id}',
        supported_protocols=[task['protocol_version']], capabilities=task['required_capabilities'])
    claimed = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                   if store.read_object_json(ref)['task_id'] == task['task_id'])
    assert claimed['status'] == 'running'
    assert claimed['execution_ref'] == f'synthetic-l1-host:{operation_id}'
    assert claimed['host_protocol'] == {'supported_protocols': [task['protocol_version']],
                                        'capabilities': task['required_capabilities']}
    return service.accept_result(project, task_id=task['task_id'],
        operation_id=task['operation_id'], produced_against=task['produced_against'],
        result_payload={'kind': 'review', 'files': [], 'reviews': [review]})


def _professional_review(store, document, *, review_id, status, reviewer, deps,
                         findings=(), observations=('已逐页核对整稿正文与来源引用。',),
                         subjects=None, replaces=None):
    selected_subjects = list(subjects if subjects is not None else
        [projection_subject(store, document), document['outputs']['pptx']] +
        [entry['page'] for entry in document['pages']])
    reviewer = copy.deepcopy(reviewer)
    if reviewer.get('identity_receipt') and subjects is None:
        reviewer['identity_receipt']['subjects'] = selected_subjects
    return {
        'schema_version': 'deck_review.v1', 'review_id': review_id,
        'kind': 'professional_use', 'status': status, 'review_stage': 'final',
        'subjects': selected_subjects,
        'dependencies': list(deps), 'reviewer': reviewer,
        'observations': list(observations), 'findings': list(findings),
        'created_at': '2026-10-21T08:00:00Z', 'replaces': replaces,
    }


def _assert_refused_everywhere(tmp_path, project, store, capsys, *, reason):
    """Exact public-file professional gaps block each delivery entry.

    Internal engineering checks remain independently visible; the public raw
    .pptx review does not rewrite the original file's engineering judgments.
    """
    with pytest.raises(StoreError) as failure:
        export_project(project, output_dir=tmp_path / 'delivery-attempt', purpose='delivery')
    assert 'professional_review_required' in failure.value.payload()['error']['reason_codes']
    assert not (tmp_path / 'delivery-attempt').exists(), 'a refused export leaves no package'
    # Current public entries share selected-output policy. Handoff now refuses
    # before writing a report; inspect the same pure predicate for named gaps.
    candidate = _current_deck_file(store, tmp_path)
    with pytest.raises(StoreError) as handoff_failure:
        check_handoff(project, file_path=candidate, purpose='delivery')
    assert 'professional_review_required' in handoff_failure.value.payload()['error']['reason_codes']
    report = delivery_eligibility.describe(project, file_path=candidate)
    assert report['professional']['satisfied'] is False
    assert report['professional']['human_signoff'] is False
    assert reason in report['professional']['gap_reasons'], report['professional']
    assert report['status'] == 'blocked'

    readiness = _final_readiness(project, capsys)
    assert readiness['status'] == 'blocked'
    assert readiness['engineering_ready'] is True
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
    _assert_refused_everywhere(tmp_path, project, store, capsys, reason='status_not_pass')


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
    review = _professional_review(store, document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-stale-extra'),
                                  deps=dependencies)
    assert _accept_review(project, store, review, task_id='review-stale-extra',
                          operation_id='op-stale-extra')['status'] == 'accepted'
    policy = selected_professional_policy(store)
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
    review = _professional_review(store, document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-unresolvable'),
                                  deps=dependencies)
    assert _accept_review(project, store, review, task_id='review-unresolvable',
                          operation_id='op-unresolvable')['status'] == 'accepted'
    policy = selected_professional_policy(store)
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
    review = _professional_review(store, document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-valid-extra'),
                                  deps=dependencies)
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
                               reason='open_must_fix_findings')


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
    policy = selected_professional_policy(store)
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
            subjects=[projection_subject(store, document)],
            observations=['整稿复核不通过：中心论证与任务不匹配。'],
            dependencies=[])
    policy = selected_professional_policy(store)
    assert policy['satisfied'] is False
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')


def test_review_binding_replaced_pptx_is_not_current(tmp_path, synthetic_human_adapter):
    """A review of the previous deck file stays historical after the output is
    replaced; the unified predicate names the stale subject directly. (The
    review is submitted formally first; the output swap simulates the later
    project state a review record must survive.)"""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    review = _professional_review(store, document, review_id='rv-professional', status='pass',
                                  reviewer=human_professional_reviewer(document, event_id='evt-old-deck'),
                                  deps=professional_dependencies(store, document))
    assert _accept_review(project, store, review, task_id='review-old-deck',
                          operation_id='op-old-deck')['status'] == 'accepted'
    new_file = tmp_path / 'deck-v2.pptx'
    from pptx import Presentation
    deck = Presentation(io.BytesIO(store.read_object_bytes(
        store.read_object_json(document['outputs']['pptx'])['file'])))
    deck.slides[0].shapes[0].text_frame.text += '\nA visible second-version change.'
    deck.save(new_file)
    from deck_master.compiler.native import attach_notes
    new_file.write_bytes(attach_notes(new_file.read_bytes(), [{'page_id': 'p1',
        'notes': store.read_object_json(document['pages'][0]['page']).get('speaker_notes', '')}]))
    new_ref = adopt_artifact(store, new_file, 'pptx')
    fresh = store.load_document()
    bumped = bump_revision(fresh, {'operation_id': 'replace-pptx', 'kind': 'task_update',
                                   'description': 'replace', 'read_set': []})
    bumped['outputs']['pptx'] = new_ref
    store.commit_change(base_revision=fresh['revision_id'], document=bumped,
                        operation_id='replace-pptx')
    policy = selected_professional_policy(store)
    assert policy['required'] is True and policy['satisfied'] is False
    assert 'subject_not_current_pptx' in policy['gap_reasons'], policy['gap_reasons']


_ADVISORY_FINDING = {'finding_id': 'pf-1', 'kind': 'content', 'impact': 'advisory',
                     'page_id': 'p1', 'element_refs': [], 'message': '限定可更明确',
                     'expected': '明确', 'actual': '含混', 'evidence': [], 'resolution': 'open'}


def test_newer_fail_masks_older_pass_until_effective_replacement(tmp_path, capsys,
                                                                 synthetic_human_adapter):
    """An earlier pass never masks a newer current fail (F0), and recording a
    replacement is not resolving it (F02): the fail stays blocking until an
    effective human re-review actually retires it."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()

    first_pass = _professional_review(store, document, review_id='rv-prof-a', status='pass',
                                      reviewer=human_professional_reviewer(document, event_id='evt-pass-first'),
                                      deps=professional_dependencies(store, document))
    assert _accept_review(project, store, first_pass, task_id='review-a',
                          operation_id='op-a')['status'] == 'accepted'
    assert selected_professional_policy(store)['human_signoff'] is True

    fail_review = _professional_review(store, store.load_document(), review_id='rv-prof-b', status='fail',
                                       reviewer=human_professional_reviewer(store.load_document(),
                                                                            event_id='evt-fail-second'),
                                       deps=professional_dependencies(store, store.load_document()),
                                       findings=[_ADVISORY_FINDING])
    assert _accept_review(project, store, fail_review, task_id='review-b',
                          operation_id='op-b')['status'] == 'accepted'
    fail_ref = store.load_document()['reviews'][-1]
    policy = selected_professional_policy(store)
    assert policy['satisfied'] is False
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']

    # F02 probe: a host_self / not_evaluated replacement that keeps the finding
    # open is accepted as history but retires nothing.
    inert_replacement = _professional_review(
        store, store.load_document(), review_id='rv-prof-b', status='not_evaluated',
        reviewer={'type': 'host_self', 'id': 'host-1', 'execution_ref': None,
                  'independence_confirmed': False},
        deps=professional_dependencies(store, store.load_document()),
        findings=[_ADVISORY_FINDING], replaces=fail_ref)
    assert _accept_review(project, store, inert_replacement, task_id='review-b-inert',
                          operation_id='op-b-inert')['status'] == 'accepted'
    policy = selected_professional_policy(store)
    assert policy['satisfied'] is False, 'a recorded but ineffective replacement must not retire the fail'
    assert 'professional_review_failed' in policy['gap_reasons'], policy['gap_reasons']
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')

    # An effective human re-review (same logical review, all pass conditions,
    # shared finding kept open with advisory impact) formally retires it.
    effective = _professional_review(
        store, store.load_document(), review_id='rv-prof-b', status='pass',
        reviewer=human_professional_reviewer(store.load_document(), event_id='evt-rejudge',
                                             reviewer_id='reviewer-zhao'),
        deps=professional_dependencies(store, store.load_document()),
        findings=[_ADVISORY_FINDING], replaces=fail_ref)
    assert _accept_review(project, store, effective, task_id='review-b-rejudge',
                          operation_id='op-b-rejudge')['status'] == 'accepted'
    policy = selected_professional_policy(store)
    assert policy['satisfied'] is True and policy['human_signoff'] is True, policy
    assert 'professional_review_failed' not in policy['gap_reasons']
    assert export_project(project, output_dir=tmp_path / 'delivery-ok', purpose='delivery')['status'] == 'exported'


def test_replacement_with_unverified_identity_does_not_retire_fail(tmp_path, capsys,
                                                                  synthetic_human_adapter):
    """F02 variant: a replacement that parrots the human claim without a
    verified receipt is history, not a resolution."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    fail_review = _professional_review(store, document, review_id='rv-prof-b', status='fail',
                                       reviewer=human_professional_reviewer(document, event_id='evt-fail-b'),
                                       deps=professional_dependencies(store, document),
                                       findings=[_ADVISORY_FINDING])
    assert _accept_review(project, store, fail_review, task_id='review-b',
                          operation_id='op-b')['status'] == 'accepted'
    fail_ref = store.load_document()['reviews'][-1]
    bare_human = {'type': 'human_external', 'id': 'reviewer-li', 'execution_ref': None,
                  'independence_confirmed': True}
    replacement = _professional_review(store, store.load_document(), review_id='rv-prof-b', status='pass',
                                       reviewer=bare_human,
                                       deps=professional_dependencies(store, store.load_document()),
                                       findings=[_ADVISORY_FINDING], replaces=fail_ref)
    assert _accept_review(project, store, replacement, task_id='review-b-bare',
                          operation_id='op-b-bare')['status'] == 'accepted'
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')


def test_replacement_with_open_must_fix_does_not_retire_fail(tmp_path, capsys,
                                                            synthetic_human_adapter):
    """F02 variant: an effective-identity replacement still carrying an open
    must-fix finding has not resolved anything and cannot retire the fail."""
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    must_fix = {**_ADVISORY_FINDING, 'impact': 'must_fix'}
    fail_review = _professional_review(store, document, review_id='rv-prof-b', status='fail',
                                       reviewer=human_professional_reviewer(document, event_id='evt-fail-mf'),
                                       deps=professional_dependencies(store, document),
                                       findings=[must_fix])
    assert _accept_review(project, store, fail_review, task_id='review-b',
                          operation_id='op-b')['status'] == 'accepted'
    fail_ref = store.load_document()['reviews'][-1]
    replacement = _professional_review(store, store.load_document(), review_id='rv-prof-b', status='pass',
                                       reviewer=human_professional_reviewer(store.load_document(),
                                                                            event_id='evt-rejudge-mf',
                                                                            reviewer_id='reviewer-zhao'),
                                       deps=professional_dependencies(store, store.load_document()),
                                       findings=[must_fix], replaces=fail_ref)
    assert _accept_review(project, store, replacement, task_id='review-b-mf',
                          operation_id='op-b-mf')['status'] == 'accepted'
    _assert_refused_everywhere(tmp_path, project, store, capsys,
                               reason='professional_review_failed')


def test_positive_human_review_via_formal_submission(tmp_path, capsys, synthetic_human_adapter):
    """AC-P01: a receipt-carrying human professional_use pass, submitted
    through the formal review envelope, satisfies export, handoff-check and
    final-readiness consistently on the same snapshot."""
    project, store = _passing_deck(tmp_path)
    _complete_page_slots(store, tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()

    review = _professional_review(store, document, review_id='rv-professional', status='pass',
        reviewer=human_professional_reviewer(document, event_id='evt-formal-human'),
        deps=professional_dependencies(store, document),
        observations=['L1 synthetic: all fixture pages, source boundaries and intended scenario checked.'])
    outcome = _accept_review(project, store, review)
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
    with pytest.raises(StoreError, match='verified human professional review'):
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
