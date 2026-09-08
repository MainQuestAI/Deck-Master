import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from quality.gate_policy import _report_satisfies_gate, _semantic_review_input_current
from quality.external_review import _page_packages_content_fingerprint


def test_semantic_gate_name_is_exact():
    assert _report_satisfies_gate('semantic_review','external_semantic')
    assert not _report_satisfies_gate('semantic_review','external_semantic_visual')
    assert not _report_satisfies_gate('semantic_review','semantic_review_fake')


def test_semantic_review_binds_model_and_evidence(tmp_path):
    (tmp_path/'page_packages').mkdir()
    (tmp_path/'page_packages/P001.json').write_text('{"page_id":"P001"}')
    (tmp_path/'solution_model.json').write_text('{"owner":"inventory"}')
    legacy={'content_fingerprint':_page_packages_content_fingerprint(tmp_path)}
    assert not _semantic_review_input_current(tmp_path,legacy)
    from quality_review_v2_helpers import canonical_gate
    report=canonical_gate(tmp_path)
    assert _semantic_review_input_current(tmp_path,report)
    (tmp_path/'solution_model.json').write_text('{"owner":"orders"}')
    assert not _semantic_review_input_current(tmp_path,report)


def test_semantic_review_becomes_stale_after_original_evidence_changes(tmp_path):
    from quality_review_v2_helpers import canonical_gate
    (tmp_path/'sources').mkdir()
    (tmp_path/'sources/original.txt').write_text('Original evidence')
    report=canonical_gate(tmp_path)
    assert _semantic_review_input_current(tmp_path,report)
    (tmp_path/'sources/original.txt').write_text('Changed evidence')
    assert not _semantic_review_input_current(tmp_path,report)
