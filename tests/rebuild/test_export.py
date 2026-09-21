"""T15 export evidence: review/delivery purposes (AC-R09), honest status
reporting (T15.03), and editability claims (AC-K16 export side)."""
import json
from pathlib import Path

import pytest

import deck_master.cli as cli
import deck_master.service as service
from deck_master.editing import export_project, review_status
from deck_master.models import bump_revision, sha256_bytes
from deck_master.store import Store, StoreError

REQUIRED = ('content', 'blueprint_content', 'blueprint_fidelity', 'conversion',
            'readability', 'privacy')


def _deck(tmp_path: Path) -> tuple[Path, Store]:
    project = tmp_path / 'proj'
    service.create(project, brief='导出验收', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': '导出一页', 'body_blocks': [
            {'id': 'b1', 'type': 'paragraph', 'text': '正文。'}]},
        'visual_spec': {'intent': 'export', 'reference_mode': 'new_design'}}]})
    store = Store(project)
    work = store.staging_dir / 'pptx'
    work.mkdir(parents=True, exist_ok=True)
    pptx_file = work / 'deck.pptx'
    pptx_file.write_bytes(b'real-current-pptx')
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    bumped = bump_revision(document, {'operation_id': 'attach-pptx', 'kind': 'task_update',
                                      'description': 'outputs', 'read_set': []})
    bumped['outputs']['pptx'] = adopt_artifact(store, pptx_file, 'pptx')
    store.commit_change(base_revision=document['revision_id'], document=bumped, operation_id='attach-pptx')
    return project, Store(project)


def _review(store, document, kind, status, *, seed, findings=()):
    page_ref = document['pages'][0]['page']
    review = {
        'schema_version': 'deck_review.v1', 'review_id': f'rv-{seed}', 'kind': kind, 'status': status,
        'subjects': [document['outputs']['pptx'], page_ref],
        'dependencies': [{'kind': 'content', 'identity': 'page:p1', 'sha256': page_ref['sha256']}],
        'reviewer': {'type': 'host_self', 'id': 'host-1', 'execution_ref': None,
                     'independence_confirmed': False},
        'observations': ['实际检查记录'],
        'findings': list(findings),
        'created_at': '2026-09-21T00:00:00Z', 'replaces': None,
    }
    ref = store.put_json_object(review)
    bumped = bump_revision(store.load_document(), {'operation_id': f'rv-{seed}', 'kind': 'task_update',
                                                   'description': 'review', 'read_set': []})
    bumped['reviews'] = list(bumped.get('reviews') or []) + [ref]
    store.commit_change(base_revision=document['revision_id'], document=bumped, operation_id=f'rv-{seed}')


def _must_fix():
    return [{'finding_id': 'f-1', 'kind': 'conversion', 'impact': 'must_fix', 'page_id': 'p1',
             'element_refs': ['atom:p1:block:b1:text'], 'message': '正文缺失', 'expected': '有',
             'actual': '无', 'evidence': [], 'resolution': 'open'}]


def _passing_deck(tmp_path):
    project, store = _deck(tmp_path)
    for kind in REQUIRED:
        _review(store, store.load_document(), kind, 'pass', seed=f'pass-{kind}')
    return project, store


# ---------------------------------------------------------------------------
# AC-R09: review shows failing work honestly; delivery refuses unresolved fixes.


def test_review_export_of_failing_deck_marks_unresolved(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    _review(store, document, 'conversion', 'fail', seed='fail', findings=_must_fix())

    outcome = export_project(project, output_dir=tmp_path / 'review-out', purpose='review')
    assert outcome['status'] == 'exported'
    report = json.loads((tmp_path / 'review-out' / 'delivery.json').read_text('utf-8'))
    assert report['purpose'] == 'review'
    assert report['revision_id'] == store.load_document()['revision_id']
    assert report['review_status'] == 'fail'
    assert report['unresolved']['failed_dimensions'] == ['conversion:p1']
    assert sorted(report['unresolved']['missing_dimensions']) == sorted(
        f'{kind}:p1' for kind in REQUIRED if kind != 'conversion')
    # Exported bytes are the real current objects.
    pptx = store.read_object_json(store.load_document()['outputs']['pptx'])
    assert (tmp_path / 'review-out' / 'deck.pptx').read_bytes() == \
        store.read_object_bytes(pptx['file'])
    assert report['editability'] == 'editable_shapes_and_text'
    assert report['evidence_level'] == 'engineering'


def test_delivery_export_rejected_with_specific_reason(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    _review(store, document, 'conversion', 'fail', seed='fail', findings=_must_fix())
    with pytest.raises(StoreError, match='conversion:p1'):
        export_project(project, output_dir=tmp_path / 'delivery-out', purpose='delivery')
    assert not (tmp_path / 'delivery-out').exists(), 'a refused export leaves no partial package'


def test_working_alias_matches_review_semantics(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    _review(store, document, 'readability', 'fail', seed='fail', findings=_must_fix())
    export_project(project, output_dir=tmp_path / 'alias-out', purpose='working')
    report = json.loads((tmp_path / 'alias-out' / 'delivery.json').read_text('utf-8'))
    assert report['purpose'] == 'review', 'working is an accepted alias, canonically reported as review'
    assert report['review_status'] == 'fail'
    assert report['unresolved']['failed_dimensions'] == ['readability:p1']


def test_review_and_delivery_of_passing_current_deck(tmp_path):
    project, store = _passing_deck(tmp_path)
    assert review_status(store, store.load_document()) == 'pass'
    review_out = export_project(project, output_dir=tmp_path / 'pass-review', purpose='review')
    delivery_out = export_project(project, output_dir=tmp_path / 'pass-delivery', purpose='delivery')
    for outcome in (review_out, delivery_out):
        report = json.loads((Path(outcome['output_dir']) / 'delivery.json').read_text('utf-8'))
        assert report['review_status'] == 'pass'
        assert report['unresolved']['missing_dimensions'] == []
        assert report['unresolved']['failed_dimensions'] == []
    assert (tmp_path / 'pass-delivery' / 'deck.pptx').is_file()
    assert not (tmp_path / 'pass-delivery' / 'project').exists(), 'delivery packs the deck, not the portable project'
    assert (tmp_path / 'pass-review' / 'project' / '.deckmaster' / 'current.json').is_file()


def test_missing_human_reviews_reported_not_evaluated(tmp_path):
    # Six required checks pass but no human/professional review exists: the
    # export must say not_evaluated, never a fabricated human pass.
    project, store = _passing_deck(tmp_path)
    export_project(project, output_dir=tmp_path / 'human-missing', purpose='delivery')
    report = json.loads((tmp_path / 'human-missing' / 'delivery.json').read_text('utf-8'))
    assert report['professional_evidence'] == {
        'professional_use': 'not_evaluated', 'desktop_editing': 'not_evaluated'}
    assert report['desktop_editing'] == 'not_evaluated'


def test_recorded_human_review_status_is_reported_verbatim(tmp_path):
    project, store = _passing_deck(tmp_path)
    _review(store, store.load_document(), 'professional_use', 'pass', seed='human')
    export_project(project, output_dir=tmp_path / 'human-present', purpose='delivery')
    report = json.loads((tmp_path / 'human-present' / 'delivery.json').read_text('utf-8'))
    assert report['professional_evidence']['professional_use'] == 'pass'
    assert report['professional_evidence']['desktop_editing'] == 'not_evaluated'


def test_cli_export_exit_zero_is_not_professional_pass(tmp_path, capsys):
    project, store = _deck(tmp_path)
    document = store.load_document()
    _review(store, document, 'conversion', 'fail', seed='fail', findings=_must_fix())
    exit_code = cli.main(['export', '--project', str(project),
                          '--out', str(tmp_path / 'cli-out'), '--purpose', 'review'])
    assert exit_code == 0, 'exporting a failing deck for review is allowed'
    report = json.loads((tmp_path / 'cli-out' / 'delivery.json').read_text('utf-8'))
    assert report['review_status'] == 'fail'
    assert report['evidence_level'] == 'engineering'
    assert report['unresolved']['failed_dimensions'], 'exit 0 carries the real unresolved list'
    capsys.readouterr()
