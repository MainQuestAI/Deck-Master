"""RP-16 synthetic semantic judgments, never evidence of real model vision."""
import json

import pytest

from deck_master import content_review, native_review, review_evidence
from test_native_review import native, FixtureSession
from test_content_preproduction_review import _deck
from test_selective_content_review import change_page


def test_checklist_keeps_exact_page_refs_and_requires_contextual_judgment(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    packet = content_review.build_review_packet(store, document)
    checklist = packet['page_copy_checklist']
    assert checklist['unit'] == 'page_copy'
    assert checklist['task'] == document['task']
    assert [p['page_ref'] for p in checklist['pages']] == [p['page'] for p in document['pages']]
    assert checklist['visibility_contract'] == 'customer_visible_only.v1'
    assert set(checklist['impact_guidance']) == {'must_fix', 'needs_judgment', 'advisory'}
    # It is input to a semantic reviewer; no keyword classifier manufactures pass/fail.
    assert 'findings' not in checklist and 'status' not in checklist
    assert any('keyword' in question for question in checklist['questions'])
    change_page(store, 'copy')
    newer = content_review.build_review_packet(store, store.load_document())
    assert newer['page_copy_checklist']['pages'][0]['page_ref'] != checklist['pages'][0]['page_ref']
    assert newer['page_copy_checklist']['pages'][0]['page_ref'] == newer['manuscript']['pages'][0]['page_ref']


def test_audience_finding_uses_normal_page_copy_gate_and_does_not_get_lost(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    _visible_title(store, '此处补充三条来源，Owner稿待压缩')
    original = FixtureSession.review
    def review(self, prompt, schema):
        observed = original(self, prompt, schema)
        packet = self.calls[-1]['packet']
        assert packet['page_copy_checklist']['unit'] == 'page_copy'
        judgment = json.loads(observed['raw_final_message'])
        row = next(row for row in judgment['reviews'] if row['kind'] == 'page_copy')
        row['status'] = 'fail'
        row['findings'] = [{'finding_id': 'audience-p1-title', 'kind': 'content', 'impact': 'must_fix',
            'page_id': 'p1', 'element_refs': ['atom:p1:title'],
            'message': 'Synthetic audience review: a production note replaces the customer action',
            'expected': 'Evidence-backed audience action, without author instructions',
            'actual': packet['manuscript']['pages'][0]['customer_visible']['title'],
            'evidence': [packet['manuscript']['pages'][0]['page_ref']],
            'resolution': 'open', 'resolution_reason': ''}]
        observed['raw_final_message'] = json.dumps(judgment)
        return observed
    monkeypatch.setattr(FixtureSession, 'review', review)
    result = native_review.run(project)
    assert result['preproduction']['status'] != 'pass'
    finding = result['preproduction']['blocking_findings'][0]
    assert finding['kind'] == 'page_copy' and finding['finding_id'] == 'audience-p1-title'
    # Another unit cannot erase the actual owner or its located finding.
    packet = content_review.dispatch_preproduction_review(project)['review_draft']
    assert packet['required_units'] == ['page_copy']
    assert len(packet['review_scope']['owners']) == 1


def _visible_title(store, title):
    from copy import deepcopy
    from deck_master import models
    doc = store.load_document()
    changed = deepcopy(doc)
    page = store.read_object_json(changed['pages'][0]['page'])
    page['customer_visible']['title'] = title
    changed['pages'][0]['page'] = store.put_json_object(page)
    changed = models.bump_revision(changed, {'operation_id': 'audience-terms', 'kind': 'task_update',
        'description': 'Synthetic audience terms', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='audience-terms')


def test_legitimate_source_assumption_timecode_not_automatically_rejected(tmp_path, native):
    project, store = _deck(tmp_path)
    _visible_title(store, '来源：公开年报；假设汇率不变；视频时间码02:14')
    # The fixture supplies an explicitly completed synthetic reviewer judgment.
    # This asserts no blanket keyword ban, not actual semantic/vision approval.
    result = native_review.run(project)
    assert result['preproduction']['status'] == 'pass'
    assert all(store.read_object_json(ref)['findings'] == [] for ref in store.load_document()['reviews'])


def test_unexecuted_or_empty_completion_is_not_a_clean_pass(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    assert content_review.preproduction_status(store, store.load_document())['status'] == 'missing'
    original = FixtureSession.review
    def empty(self, prompt, schema):
        observed = original(self, prompt, schema)
        observed['raw_final_message'] = json.dumps({'reviews': []})
        return observed
    monkeypatch.setattr(FixtureSession, 'review', empty)
    with pytest.raises(review_evidence.EvidenceRejected):
        native_review.run(project)
    assert not store.load_document()['reviews']
    assert content_review.preproduction_status(store, store.load_document())['status'] != 'pass'


def test_same_page_version_flows_through_packet_design_and_frozen_prompt(tmp_path):
    from deck_master import generation, production, service
    from test_rc3_notes_visual_inputs import _blueprint_with_imported_plan
    project, store, task = _blueprint_with_imported_plan(tmp_path)
    document = store.load_document()
    packet = content_review.build_review_packet(store, document)
    page_id = task['scope_pages'][0]
    packet_page = next(page for page in packet['manuscript']['pages'] if page['page_id'] == page_id)
    check_page = next(page for page in packet['page_copy_checklist']['pages'] if page['page_id'] == page_id)
    prepared, _ = production.stored_blueprint_request(store, task)
    service.task_start(project, task_id=task['task_id'], execution_ref='rp16-synthetic-freeze',
        supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    frozen = generation.freeze(project, task_id=task['task_id'],
        input=generation.prepared_input(store, store.load_document(), task),
        base_revision=store.current_revision_id(), operation_id='rp16-freeze')
    assert packet_page['page_ref'] == check_page['page_ref'] == frozen['input']['page']['page_ref']
    # The existing design projection materializes absent optional fields.
    expected_visible = {'subtitle': '', 'labels': [], 'footnotes': [], 'callouts': [],
                        **packet_page['customer_visible']}
    assert expected_visible == prepared['projection']['customer_visible']
    assert frozen['input']['prompt'] == prepared['prompt']
    assert frozen['input']['design_context']['content_requirements']['text_visibility'] == packet['page_copy_checklist']['visibility_contract']
    # Freeze constructs an inspectable request; there is no generated-image evidence.
    assert not store.read_object_json(store.load_document()['tasks'][0]).get('generation_attempts')
