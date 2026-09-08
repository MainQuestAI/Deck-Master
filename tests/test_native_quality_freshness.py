import json
from quality.gate_policy import _report_satisfies_gate, _semantic_review_input_current
from quality.external_review import _page_packages_content_fingerprint


def test_semantic_gate_name_is_exact():
    assert _report_satisfies_gate('semantic_review','external_semantic')
    assert not _report_satisfies_gate('semantic_review','external_semantic_visual')
    assert not _report_satisfies_gate('semantic_review','semantic_review_fake')


def test_semantic_review_binds_model_and_evidence(tmp_path):
    (tmp_path/'page_packages').mkdir()
    (tmp_path/'page_packages/P001.json').write_text('{}')
    (tmp_path/'solution_model.json').write_text('{"owner":"inventory"}')
    report={'content_fingerprint':_page_packages_content_fingerprint(tmp_path)}
    assert _semantic_review_input_current(tmp_path,report)
    (tmp_path/'solution_model.json').write_text('{"owner":"orders"}')
    assert not _semantic_review_input_current(tmp_path,report)
