"""#186: deterministic handoff contracts, not evidence of model quality."""
import copy
import json

import pytest

from deck_master import cli, content_review, review_import, review_handoff
from deck_master.models import canonical_json_bytes, sha256_bytes, ModelError
from deck_master.store import Store
from rc3_fixtures import source_snapshot
from test_rc3_collaboration_adapters import imported_project, external_packet_for_page, instruction
from test_workbench_reads import commit


def packet(tmp_path, *, expected='Explain the unknown current capability gap; do not invent ROI'):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = imported_project(tmp_path)
    external = external_packet_for_page(tmp_path, project)
    reviews = external['report'].pop('reviews')
    external['report']['reviews'] = []
    external['report_sha256'] = sha256_bytes(canonical_json_bytes(external['report']))
    review = reviews[0]
    review['status'] = 'fail'
    review['findings'] = [
        {'finding_id': f'R{i:02}', 'kind': 'content', 'impact': 'must_fix', 'page_id': 'p1',
         'element_refs': ['atom:p1:block:body:text'], 'message': 'Synthetic original professional finding',
         'actual': 'Missing comparison' if i == 1 else f'Local omission {i}',
         'expected': expected if i == 1 else f'Restore qualification {i}',
         'evidence': [review['subjects'][0]], 'resolution': 'open'} for i in range(1, 7)]
    contexts = [{'review_id': review['review_id'], 'finding_id': f['finding_id'],
                 'severity': 'F1' if i == 0 else 'F2', 'use_impact': 'Reader cannot decide',
                 'repair_layer': 'page_copy', 'acceptance': f['expected']} for i, f in enumerate(review['findings'])]
    return project, external, reviews, contexts


def record(tmp_path, **kwargs):
    project, external, reviews, contexts = packet(tmp_path, **kwargs)
    result = review_handoff.record_reviews(external_report=external, reviews=reviews, finding_context=contexts)
    return project, result['external_report']


def adopt(project, external, op='explicit-import'):
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    return review_import.import_report(project, external_report=external, source_bindings=bindings,
        evidence=instruction('User explicitly authorizes this original report repair and import'),
        base_revision=Store(project).current_revision_id(), operation_id=op)


def test_read_only_report_and_original_bytes_survive_source_loss(tmp_path, capsys):
    project, external, reviews, contexts = packet(tmp_path / 'source')
    raw = tmp_path / 'original' / 'review.json'
    raw.parent.mkdir()
    raw.write_text('{ "R01": "Unknown current capability; verify it" }\n')
    output = tmp_path / 'reports' / 'standard.json'
    before = source_snapshot(tmp_path / 'source')
    payload = {'external_report': external, 'reviews': reviews, 'finding_context': contexts,
               'original_report_path': str(raw), 'report_output': str(output)}
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(payload))
    assert cli.main(['review', 'record', '--input', str(request)]) == 0
    result = json.loads(capsys.readouterr().out)['result']
    assert source_snapshot(tmp_path / 'source') == before
    report = result['external_report']
    assert report == json.loads(output.read_text())
    assert report['report']['original_report']['sha256'] == sha256_bytes(raw.read_bytes())
    assert report['report']['original_report']['content_utf8'] == raw.read_text()
    for row in external['report']['source_manifest']['files']:
        from urllib.parse import unquote, urlparse
        from pathlib import Path
        Path(unquote(urlparse(row['source_uri']).path)).unlink()
    handoff = review_handoff.repair_handoff(external_report=report)
    assert len(handoff['findings']) == 6 and not handoff['all_findings_closed']
    assert handoff['findings'][0]['context']['severity'] == 'F1'
    assert 'do not invent ROI' in handoff['findings'][0]['finding']['expected']
    assert all(r['verification'] == 'not_verified' for r in handoff['findings'])
    with pytest.raises(Exception, match='unavailable'):
        adopt(project, report)


@pytest.mark.parametrize('invalid', ['duplicate_review', 'duplicate_finding', 'wrong_evidence', 'missing_context', 'source_output'])
def test_invalid_reports_never_write_project(tmp_path, invalid):
    project, external, reviews, contexts = packet(tmp_path / 'source')
    before = source_snapshot(project)
    output = None
    if invalid == 'duplicate_review':
        reviews.append(copy.deepcopy(reviews[0]))
    elif invalid == 'duplicate_finding':
        reviews[0]['findings'].append(copy.deepcopy(reviews[0]['findings'][0]))
    elif invalid == 'wrong_evidence':
        reviews[0]['findings'][0]['evidence'][0]['sha256'] = '0' * 64
    elif invalid == 'missing_context':
        contexts.pop()
    else:
        output = tmp_path / 'source' / 'bad-report.json'
    with pytest.raises(ModelError):
        review_handoff.record_reviews(external_report=external, reviews=reviews,
                                      finding_context=contexts, report_output=output)
    assert source_snapshot(project) == before


def test_two_r01_reports_stay_separate_through_import_packet_and_recheck(tmp_path):
    project, first = record(tmp_path)
    second = copy.deepcopy(first)
    second['report']['reviews'][0]['findings'][0]['expected'] = 'Different original requirement, still unknown'
    second['report']['finding_context'][0]['acceptance'] = 'Different original requirement, still unknown'
    second['report_sha256'] = sha256_bytes(canonical_json_bytes(second['report']))
    imported = adopt(project, first)
    adopt(project, second, 'second-report')
    store = Store(project)
    doc = store.load_document()
    rows = content_review.build_review_packet(store, doc)['external_findings']
    assert len(rows) == 12
    assert len({json.dumps(r['identity'], sort_keys=True) for r in rows}) == 12
    owner = store.read_object_json(imported['review_refs'][0])
    owner_ref = imported['review_refs'][0]
    # Synthetic Store fixture: actual source manuscript changes; no model call.
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['body_blocks'][0]['text'] += ' Restored five local qualifications; capability gap remains unknown.'
    old_page = doc['pages'][0]['page']
    new_page = store.put_json_object(page)
    doc['pages'][0]['page'] = new_page
    replacement = copy.deepcopy(owner)
    replacement['replaces'] = owner_ref
    replacement['subjects'] = [new_page if r == old_page else r for r in replacement['subjects']]
    for dep in replacement['dependencies']:
        if dep['kind'] == 'content' and dep['identity'] == 'page:p1':
            dep['sha256'] = new_page['sha256']
    for finding in replacement['findings'][1:]:
        finding.update(resolution='fixed', evidence=[new_page])
    replacement['findings'][0]['evidence'] = [new_page]
    doc['reviews'].append(store.put_json_object(replacement))
    generic = copy.deepcopy(replacement)
    generic.update(review_id='unrelated-general-pass', replaces=None, status='pass', findings=[])
    doc['reviews'].append(store.put_json_object(generic))
    commit(store, doc, 'synthetic-rechecked-five')
    before = source_snapshot(project)
    handoff = review_handoff.repair_handoff(external_report=first, project=project)
    assert [r['closed'] for r in handoff['findings']] == [False, True, True, True, True, True]
    assert not handoff['all_findings_closed']
    assert not any(r['closed'] for r in review_handoff.repair_handoff(external_report=second, project=project)['findings'])
    assert source_snapshot(project) == before


def test_final_visual_finding_cannot_borrow_content_pass_or_missing_observation(tmp_path):
    project, engineering, reviews, contexts = packet(tmp_path)
    reviews[0].update(kind='readability', review_stage='final')
    for row in contexts:
        row['repair_layer'] = 'output'
        row['acceptance'] = 'Inspect actual final PPT rendering and effective font sizes'
    external = review_handoff.record_reviews(external_report=engineering, reviews=reviews,
                                             finding_context=contexts)['external_report']
    imported = adopt(project, external)
    store = Store(project)
    doc = store.load_document()
    original = store.read_object_json(imported['review_refs'][0])
    candidate = copy.deepcopy(original)
    candidate.update(replaces=imported['review_refs'][0], status='pass', observations=[])
    for finding in candidate['findings']:
        finding['resolution'] = 'fixed'
    # Deliberately invalid synthetic history: no actual final observation.
    # The read model must not trust this asserted pass even if present.
    doc['reviews'].append(store.put_json_object(candidate))
    content_pass = copy.deepcopy(candidate)
    content_pass.update(kind='page_copy', review_stage='preproduction', observations=['Read current text'])
    doc['reviews'].append(store.put_json_object(content_pass))
    commit(store, doc, 'synthetic-unobserved-final')
    handoff = review_handoff.repair_handoff(external_report=external, project=project)
    assert not any(row['closed'] for row in handoff['findings'])
    assert all(row['review_stage'] == 'final' for row in handoff['findings'])
    assert handoff['findings'][0]['reviewer']['type'] == 'host_self'
    assert 'desktop' in handoff['evidence_boundary']


def test_missing_project_still_returns_source_external_list(tmp_path):
    _, external = record(tmp_path / 'sources')
    missing = tmp_path / 'not-a-project'
    handoff = review_handoff.repair_handoff(external_report=external, project=missing)
    assert handoff['project_binding'] == 'unavailable'
    assert len(handoff['findings']) == 6
    assert not missing.exists()


@pytest.mark.parametrize('damage', ['missing', 'empty', 'duplicate', 'missing_acceptance', 'wrong_original_hash'])
def test_rehashed_report_cannot_drop_original_finding_contract(tmp_path, damage):
    project, external = record(tmp_path)
    if damage == 'missing':
        del external['report']['finding_context']
    elif damage == 'empty':
        external['report']['finding_context'] = []
    elif damage == 'duplicate':
        external['report']['finding_context'].append(external['report']['finding_context'][0])
    elif damage == 'missing_acceptance':
        del external['report']['finding_context'][0]['acceptance']
    else:
        external['report']['original_report'] = {'content_utf8': 'actual', 'sha256': '0' * 64, 'size': 6}
    external['report_sha256'] = sha256_bytes(canonical_json_bytes(external['report']))
    before = source_snapshot(project)
    with pytest.raises(ModelError):
        review_handoff.repair_handoff(external_report=external)
    with pytest.raises(ModelError):
        adopt(project, external)
    assert source_snapshot(project) == before
