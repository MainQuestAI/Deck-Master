"""Public import counters: share artifact facts, never per-review binding decisions."""
import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from deck_master import content_review, editing, models, review_import, tasks
from deck_master.store import ConflictError, Store
from rc3_fixtures import public_project
from test_rc3_collaboration_adapters import (
    external_packet_for_page, imported_project, instruction,
)


def _packet(tmp_path, count, *, large_deck=False):
    if large_deck:
        pages = [{'schema_version': 'deck_page_package.v2', 'page_id': f'p{index}',
            'customer_visible': {'title': f'Synthetic page {index}', 'body_blocks': [
                {'id': 'body', 'type': 'paragraph', 'text': 'Fixed synthetic manuscript.'}]},
            # Above Store's 16 KiB small-JSON cache: count actual file reads.
            'speaker_notes': 'Synthetic source-bound notes. ' * 800,
            'visual_spec': {'intent': 'Read the copy', 'reference_mode': 'new_design'}}
            for index in range(1, 17)]
        project = public_project(tmp_path,
            create_input={'brief': 'Import this confirmed manuscript', 'audience': 'test reader'},
            manuscript={'pages': pages, 'page_order': [p['page_id'] for p in pages]})['project']
    else:
        project = imported_project(tmp_path)
    external = external_packet_for_page(tmp_path, project)
    template = external['report']['reviews'][0]
    external['report']['reviews'] = [
        {**copy.deepcopy(template), 'review_id': f'synthetic-batch-{index}'}
        for index in range(count)
    ]
    _seal(external)
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    return project, external, bindings


def _seal(external):
    external['report_sha256'] = models.sha256_bytes(models.canonical_json_bytes(external['report']))


def _import(project, external, bindings):
    return review_import.import_report(project, external_report=external,
        source_bindings=bindings, base_revision=Store(project).current_revision_id(),
        operation_id='synthetic-batch-import',
        evidence=instruction('Explicitly import these synthetic source-bound reviews'))


def test_public_import_derives_artifact_once_for_n_and_2n_reviews(tmp_path, monkeypatch, record_property):
    measurements = []
    for count in (2, 4):
        folder = tmp_path / str(count)
        folder.mkdir()
        project, external, bindings = _packet(folder, count, large_deck=True)
        store = Store(project)
        document = store.load_document()
        page_paths = {store._resolve_object_path(entry['page']['path']) for entry in document['pages']}
        assert len(page_paths) == 16
        assert all(path.stat().st_size > 16384 for path in page_paths)
        builds, checked = [], []
        reads = Counter()
        phase = 'import'
        original_build = editing._current_artifact_digests
        original_binding = content_review._require_subject_binding
        original_read = Path.read_bytes
        original_adopt = tasks._adopt_review

        def read(path):
            raw = original_read(path)
            if path in page_paths:
                reads['page_reads'] += 1
                reads['page_bytes'] += len(raw)
                reads[f'{phase}_page_reads'] += 1
            return raw

        def build(*args, **kwargs):
            nonlocal phase
            builds.append(args[1]['revision_id'])
            previous, phase = phase, 'builder'
            try:
                return original_build(*args, **kwargs)
            finally:
                phase = previous

        def binding(*args, **kwargs):
            nonlocal phase
            checked.append((args[2]['review_id'], kwargs.get('artifact_digests')))
            previous, phase = phase, 'binding'
            try:
                return original_binding(*args, **kwargs)
            finally:
                phase = previous

        def adopt(*args, **kwargs):
            nonlocal phase
            previous, phase = phase, 'adopt'
            try:
                return original_adopt(*args, **kwargs)
            finally:
                phase = previous

        with monkeypatch.context() as patch:
            patch.setattr(editing, '_current_artifact_digests', build)
            patch.setattr(content_review, '_current_artifact_digests', build)
            patch.setattr(content_review, '_require_subject_binding', binding)
            patch.setattr(Path, 'read_bytes', read)
            patch.setattr(tasks, '_adopt_review', adopt)
            result = _import(project, external, bindings)
        assert builds == [document['revision_id']]
        assert [row[0] for row in checked] == [review['review_id'] for review in external['report']['reviews']]
        assert checked[0][1] is not None
        assert all(row[1] is checked[0][1] for row in checked)
        assert len(result['review_refs']) == count
        adopted = [store.read_object_json(ref) for ref in result['review_refs']]
        assert all(review['status'] == 'needs_review' and review['reviewer']['type'] == 'host_self'
                   for review in adopted)
        assert reads['builder_page_reads'] >= 16
        assert reads['binding_page_reads'] == 0
        # Each adopted review still verifies its actual Page subject bytes/hash.
        assert reads['adopt_page_reads'] == count
        measurements.append({'reviews': count, 'pages': 16, **reads})
    # Count physical reads of large immutable Page objects over the public call,
    # including commit validation, not just calls to the named artifact helper.
    assert (measurements[0]['page_reads'] - measurements[0]['adopt_page_reads']
            == measurements[1]['page_reads'] - measurements[1]['adopt_page_reads'])
    assert measurements[0]['builder_page_reads'] == measurements[1]['builder_page_reads']
    record_property('public_import_large_page_reads', json.dumps(measurements, sort_keys=True))
    print('public_import_large_page_reads=' + json.dumps(measurements, sort_keys=True))


@pytest.mark.parametrize('damage', ['last_dependencies', 'last_subjects', 'source_bytes'])
def test_public_import_still_rejects_late_bad_binding_and_corrupt_source(tmp_path, damage):
    project, external, bindings = _packet(tmp_path, 4)
    if damage == 'last_dependencies':
        external['report']['reviews'][-1]['dependencies'] = []
        expected, match = ConflictError, 'dependencies'
    elif damage == 'last_subjects':
        # Retain the Page, omit the required ContentPlan only on the last review.
        external['report']['reviews'][-1]['subjects'] = external['report']['reviews'][-1]['subjects'][:1]
        expected, match = models.ModelError, 'subjects'
    else:
        (tmp_path / 'fixed-external-page.json').write_bytes(b'corrupt original source')
        expected, match = ConflictError, 'source_changed'
    _seal(external)
    before = Store(project).load_document()
    with pytest.raises(expected, match=match):
        _import(project, external, bindings)
    assert Store(project).load_document() == before


def test_standalone_subject_binding_still_derives_facts(tmp_path, monkeypatch):
    project, external, _ = _packet(tmp_path, 1)
    store = Store(project)
    document = store.load_document()
    review = copy.deepcopy(external['report']['reviews'][0])
    review['subjects'] = [document['pages'][0]['page'], document['content_plan']]
    calls = []
    original = content_review._current_artifact_digests

    def counted(*args, **kwargs):
        calls.append(args[1]['revision_id'])
        return original(*args, **kwargs)

    monkeypatch.setattr(content_review, '_current_artifact_digests', counted)
    content_review._require_subject_binding(store, document, review, ['p1'])
    assert calls == [document['revision_id']]
    review['dependencies'] = []
    with pytest.raises(models.ModelError, match='dependencies'):
        content_review._require_subject_binding(store, document, review, ['p1'])
    assert len(calls) == 2
