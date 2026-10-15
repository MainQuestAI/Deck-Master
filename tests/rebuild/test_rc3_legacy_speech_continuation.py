"""Old immutable Page facts remain readable through a legitimate new speech task."""
from copy import deepcopy
import uuid

import pytest

from deck_master import collaboration, collaboration_migration, models, service, tasks
from deck_master.content import atom_ids
from deck_master.store import Store
from rc3_fixtures import historical_snapshot, claim_fixture_task


@pytest.mark.parametrize('recorded_r1_empty_roles', [False, True])
def test_old_mappingless_page_can_resume_speech_without_rewriting_its_original(tmp_path, recorded_r1_empty_roles):
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'L1 actual old manuscript shape', 'body_blocks': [
            {'id': 'body', 'type': 'paragraph', 'text': 'Retain these original words.'}]},
        'speaker_notes': 'Original retained cue.',
        'visual_spec': {'intent': 'L1 historical fixed manuscript', 'reference_mode': 'new_design'}}
    fixture = historical_snapshot(tmp_path, scenario='old RC3 Page without content_mapping',
        pages=[page], minimum_writer='rc3.v1')
    project, store = fixture['project'], Store(fixture['project'])
    original = store.load_document()['pages'][0]
    original_bytes = store.read_object_bytes(original['page'])
    plan = collaboration_migration.describe(project)
    collaboration_migration.apply(project, base_revision=plan['revision_id'], plan_digest=plan['plan_digest'],
        operation_id=str(uuid.uuid4()), instruction_evidence={'kind': 'host_attested_instruction',
            'text': 'L1 technical migration only; no approval or new narrative'})
    doc = store.load_document()
    assert doc['pages'][0] == original and doc.get('narrative') is None
    if recorded_r1_empty_roles:
        # Controlled historical R1 migration fact: earlier imported_mapping
        # Plans allowed no role entries. The Page and all original bytes stay
        # unchanged; current Runtime must read that legal unknown fact too.
        old_plan = store.read_object_json(doc['content_plan'])
        old_plan['input']['page_roles'] = []
        changed = models.bump_revision(deepcopy(doc), {'operation_id': str(uuid.uuid4()),
            'kind': 'task_update', 'description': 'L1 recorded R1 unknown-role Plan shape', 'read_set': []})
        changed['content_plan'] = store.put_json_object(old_plan)
        store.commit_change(base_revision=doc['revision_id'], document=changed,
            operation_id=changed['change']['operation_id'])
    scope = {'subject': 'pages', 'page_ids': ['p1'], 'page_manifest_ref': None,
        'external_artifact_ref': None, 'layers': ['speech', 'plan'],
        'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}
    collaboration.start_request(project, input={'intent': 'content_only', 'content_intent': 'speech_only',
        'scope': scope, 'instruction_evidence': {'kind': 'host_attested_instruction',
            'text': 'L1 write a new cue for p1; keep exact visible copy and visual instructions'}},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    response = service.continue_project(project)
    task = tasks._lookup_task(store.load_document(), response['pending_tasks'][0]['task_id'], store)
    assert task['protocol_version'] == 'compose.v2'
    claim_fixture_task(project, task, execution_ref='L1-legacy-speech-author')
    before = store.load_document()
    cue = 'L1 begin with the original instruction, then ask for the next owner.'
    payload = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'speech',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'], 'usage_events': [],
        'payload': {'updates': [{'page_id': 'p1', 'page_ref': before['pages'][0]['page'],
            'speaker_notes': cue, 'speech_segments': [{'segment_id': 'cue', 'start_codepoint': 0,
                'end_codepoint': len(cue), 'narrative_node_ids': [], 'kind': 'cue', 'estimated_seconds': 12}]}]}}
    outcome = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload=payload)
    assert outcome['status'] == 'accepted'
    after = store.load_document()
    current = store.read_object_json(after['pages'][0]['page'])
    assert current['customer_visible'] == page['customer_visible'] and current['visual_spec'] == page['visual_spec']
    assert current['speaker_notes'] == cue and after.get('narrative') is None
    assert current['content_mapping']['narrative_ref'] is None
    assert {link['element_ref'] for link in current['content_mapping']['visible_links']} == atom_ids(current)
    assert all(not link['source_links'] and not link['narrative_node_ids'] for link in current['content_mapping']['visible_links'])
    assert store.read_object_bytes(original['page']) == original_bytes
    assert {key: after['pages'][0][key] for key in ('blueprint', 'svg', 'svg_preview', 'ppt_preview')} == {
        key: original[key] for key in ('blueprint', 'svg', 'svg_preview', 'ppt_preview')}
    assert after['collaboration']['request']['closed'] is True
    assert service.continue_project(project)['status'] == 'completed'
    assert store.current_revision_id() == after['revision_id']
    assert not tasks._lookup_task(after, task['task_id'], store)['call_allowances']
