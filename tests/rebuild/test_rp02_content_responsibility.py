"""RP-02: synthetic, zero-call Content trials through real immutable tasks."""
import copy
import uuid

import pytest

from deck_master import changes, eligibility, method_resources, service, tasks
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store
from test_content_candidates import (dispatch_content_trial, start_task, accept,
                                     page_envelope, adopt, content_intent)
from test_content_ops import prepare_editorial_project


@pytest.fixture
def unreviewed(tmp_path):
    path = tmp_path / 'unreviewed'
    create_sample(path, page_count=3, readonly=False)
    prepare_editorial_project(path, review=False)
    return path, Store(path)


def test_unreviewed_content_trial_reads_both_protocols_then_adopts(unreviewed):
    path, store = unreviewed
    before = copy.deepcopy(store.load_document())
    assert not eligibility.preproduction_state(store, before)['satisfied']
    task = dispatch_content_trial(path, store)
    assert task['collaboration_binding']['phase'] == 'page_copy'
    assert task['collaboration_binding']['write_scope']['layers'] == ['page_copy']
    assert not task['call_allowances']
    assert 'page-writing' in {row['id'] for row in task['method_manifest']}
    assert 'blueprint-svg' not in {row['id'] for row in task['method_manifest']}
    for protocol in (None, 'work_context.v2'):
        result = method_resources.read_skill_methods('deck-content', project=path,
            task_id=task['task_id'], read_protocol=protocol)
        order = result['tasks'][0] if protocol else result['dispatch']['work_order']
        assert order['task_id'] == task['task_id']
        assert order['method_basis_status'] == 'current'
        if protocol:
            assert result['context_ready']
            assert result['bodies']
        with pytest.raises(ValueError, match='does not execute'):
            method_resources.read_skill_methods('deck-design', project=path,
                task_id=task['task_id'], read_protocol=protocol)
    start_task(path, task)
    result = accept(path, task, page_envelope(store, task))
    assert result['status'] == 'candidate_ready'
    assert store.load_document()['pages'] == before['pages']
    assert store.load_document()['outputs'] == before['outputs']
    adopt(path, store, result['candidate_ids'])
    after = store.load_document()
    assert after['pages'][0]['page'] != before['pages'][0]['page']
    assert after['pages'][1:] == before['pages'][1:]
    assert not any(after['outputs'].values())
    assert not eligibility.preproduction_state(store, after)['satisfied']


def test_content_exception_does_not_waive_visual_or_auto_changes(unreviewed):
    path, store = unreviewed
    for mode, layer in [('auto', 'content'), ('trial', 'original_image')]:
        value = content_intent(store, mode=mode)
        value['targets'][0]['layer'] = layer
        if layer == 'original_image':
            value['targets'][0]['artifact_ref'] = store.load_document()['pages'][0]['blueprint']
            value['max_calls'] = 1
        plan = changes.plan(path, input=value)
        with pytest.raises(eligibility.EligibilityBlocked):
            changes.commit(path, plan_id=plan['plan_id'], base_revision=store.current_revision_id(),
                           operation_id=str(uuid.uuid4()))


def test_old_design_manifest_is_retired_not_rewritten(unreviewed):
    path, store = unreviewed
    task = dispatch_content_trial(path, store)
    old = copy.deepcopy(task)
    from deck_master import collaboration_binding, content_production
    binding = old['collaboration_binding']
    old['collaboration_binding'] = collaboration_binding.build_binding(store, store.load_document(),
        phase='production', executor_type='host',
        write_scope=content_production.write_scope_for(store, store.load_document(), 'production', page_ids=['p01']),
        adoption_policy='candidate_only', authorization_ref=binding['authorization_ref'])
    entries = method_resources.method_resources('repair')
    old['method_manifest'] = [{k: row[k] for k in ('id', 'relative_path', 'sha256')} for row in entries]
    old['method_release'] = method_resources.method_release(entries)
    document = store.load_document()
    original_ref = store.put_json_object(old)
    updated = bump_revision(copy.deepcopy(document), {'operation_id': 'historical-task-fixture',
        'kind': 'task_update', 'description': 'Synthetic historical RP-02 contract', 'read_set': []})
    updated['tasks'] = [original_ref if store.read_object_json(ref)['task_id'] == old['task_id'] else ref
                        for ref in updated['tasks']]
    store.commit_change(document=updated, base_revision=document['revision_id'], operation_id='historical-task-fixture')
    assert tasks.task_method_contract_changed(old)
    assert method_resources.resolve_task_methods(old)['basis_status'] == 'basis_changed'
    refreshed = tasks.reissue_changed_method_tasks(store)
    records = [store.read_object_json(ref) for ref in refreshed['tasks']]
    retired = next(t for t in records if t['task_id'] == old['task_id'])
    replacement = records[-1]
    assert retired['status'] == 'superseded'
    assert retired['method_manifest'] == old['method_manifest']
    assert store.read_object_json(original_ref) == old
    assert replacement['task_id'] != old['task_id']
    assert replacement['collaboration_binding']['phase'] == 'page_copy'
    assert not tasks.task_method_contract_changed(replacement)
    start_task(path, replacement)
    assert accept(path, replacement, page_envelope(store, replacement))['status'] == 'candidate_ready'
