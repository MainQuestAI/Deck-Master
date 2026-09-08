from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from uat.sc1_1_engineering_matrix import build_matrix, record_result, summarize

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 40


def test_all_current_and_inherited_cases_start_not_run():
    matrix = build_matrix(ROOT, SHA)
    assert len([c for c in matrix['cases'] if c['suite'] == 'SC1.1']) == 64
    assert len([c for c in matrix['cases'] if c.get('disposition')]) == 88
    assert matrix['unmapped_inherited_ids'] == ['A-13', 'I-08', 'Q-13']
    assert all(c['status'] == 'not_run' for c in matrix['cases'])
    assert summarize(matrix)['engineering_status'] == 'in_progress'


def evidence(tmp_path):
    p = tmp_path / 'evidence.json'
    p.write_text('{"executed":true}')
    return p


def test_spec_check_never_promotes_product_case(tmp_path):
    matrix = build_matrix(ROOT, SHA)
    with pytest.raises(ValueError, match='spec self-check'):
        record_result(matrix, 'SC1.1:GOV-01', 'passed', SHA, 'python validate_spec.py', 'ok', [evidence(tmp_path)], 'L1', {'python':'3.12'})


def test_missing_evidence_and_wrong_sha_rejected(tmp_path):
    matrix = build_matrix(ROOT, SHA)
    with pytest.raises(ValueError, match='candidate SHA'):
        record_result(matrix, 'SC1.1:CMP-01', 'passed', 'b'*40, 'real compile', 'ok', [evidence(tmp_path)], 'L2', {'renderer':'LibreOffice'})
    with pytest.raises(ValueError, match='evidence'):
        record_result(matrix, 'SC1.1:CMP-01', 'passed', SHA, 'real compile', 'ok', [], 'L2', {'renderer':'LibreOffice'})


def test_l1_cannot_pass_l2_and_mapping_does_not_auto_pass(tmp_path):
    matrix = build_matrix(ROOT, SHA)
    with pytest.raises(ValueError, match='tier'):
        record_result(matrix, 'SC1.1:CMP-01', 'passed', SHA, 'pytest unit', 'ok', [evidence(tmp_path)], 'L1', {'python':'3.12'})
    record_result(matrix, 'SC1.1:CMP-01', 'passed', SHA, 'real compile', 'ok', [evidence(tmp_path)], 'L2', {'renderer':'LibreOffice'})
    assert len([c for c in matrix['cases'] if c['status'] == 'passed']) == 1
    assert summarize(matrix)['engineering_status'] == 'in_progress'


def test_evidence_mutation_invalidates_pass(tmp_path):
    matrix = build_matrix(ROOT, SHA)
    p = evidence(tmp_path)
    record_result(matrix, 'SC1.1:GOV-01', 'passed', SHA, 'rg actual entrypoints', 'ok', [p], 'L1', {'git':'2'})
    p.write_text('changed')
    assert 'SC1.1:GOV-01' in summarize(matrix)['invalid_evidence_cases']


def test_no_automatic_human_signoff():
    result = summarize(build_matrix(ROOT, SHA))
    assert result['pending_user_reviews'] == ['SC1.1:UAT-02', 'SC1.1:UAT-03', 'SC1.1:UAT-04']
