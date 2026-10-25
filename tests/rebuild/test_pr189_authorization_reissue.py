"""Method refresh cannot revive a task's ineffective frozen authorization."""
import copy
import shutil
import uuid

import pytest

from deck_master import eligibility, method_resources, tasks
from deck_master.models import bump_revision
from test_ancestor_authorization_boundary import ACTIONS, chain_task
from test_eligibility_enforcement import _grant


@pytest.mark.parametrize('state', ['missing', 'superseded', 'invalidated', 'expired', 'revoked'])
def test_invalid_bound_authority_keeps_reason_and_cannot_be_reissued(tmp_path, monkeypatch, state):
    project, store, chain, task, scope = chain_task(tmp_path)
    installed = tmp_path / 'changed-methods'
    shutil.copytree(method_resources.resolve_root(), installed)
    method = installed / 'references/review-and-repair.md'
    method.write_bytes(method.read_bytes() + b'\nSynthetic changed method for recovery.\n')
    monkeypatch.setattr(method_resources, 'resolve_root', lambda: installed)
    assert tasks.task_method_contract_changed(task)
    bound = chain[-1]['authorization_ref']
    current = store.load_document()
    updated = bump_revision(copy.deepcopy(current), {'operation_id': uuid.uuid4().hex,
        'kind': 'task_update', 'description': 'Synthetic ineffective original authorization', 'read_set': []})
    refs = updated['collaboration']['authorizations']
    if state == 'missing':
        refs.remove(bound)
    else:
        record = store.read_object_json(bound)
        record.update(replaces=bound)
        if state == 'expired':
            record['expires_at'] = '2000-01-01T00:00:00Z'
        else:
            record['status'] = state
        refs.append(store.put_json_object(record))
    store.commit_change(document=updated, base_revision=current['revision_id'],
                        operation_id=updated['change']['operation_id'])
    _grant(project, store, actions=ACTIONS, scope=scope,
        operation_id='synthetic-new-unrelated-grant', max_external_calls=0)
    before = store.load_document()
    binding = eligibility.task_binding_state(store, before, task)
    assert binding['status'] == ('withdrawn' if state == 'revoked' else 'invalid')
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        tasks.reissue_changed_method_tasks(store)
    assert ('authorization_revoked' in error.value.decision['reason_codes']) is (state == 'revoked')
    assert store.load_document() == before
    assert len(before['tasks']) == len(current['tasks'])
