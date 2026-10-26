"""Same-value audit replacement is not a new editorial requirement."""
from datetime import datetime, timedelta

from deck_master import collaboration, content_review, effective_requirements, tasks
from test_content_preproduction_review import _deck, _instruction
from test_rc3_review_policy_workflow import choice, decide


def test_policy_audit_replacement_preserves_task_but_evidence_change_does_not(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    decide(store, choice(store))
    task = content_review.dispatch_preproduction_review(project)['task']
    frozen = [store.read_object_json(ref) for ref in task['inputs'] if ref['path'].endswith('.json')]
    selected = store.load_document()['collaboration']['quality_profile']['override_decision_ref']
    record = store.read_object_json(selected)
    later = (datetime.fromisoformat(record['created_at'].replace('Z', '+00:00')) + timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    monkeypatch.setattr(collaboration, '_now_iso', lambda: later)
    decide(store, choice(store, decision_id=record['decision_id'], replaces=selected))
    current = store.load_document()
    replacement = current['collaboration']['quality_profile']['override_decision_ref']
    assert replacement != selected
    assert store.read_object_json(replacement)['created_at'] != record['created_at']
    assert tasks.task_inputs_current(store, current, task)
    assert content_review.dispatch_preproduction_review(project)['task']['task_id'] == task['task_id']
    assert [store.read_object_json(ref) for ref in task['inputs'] if ref['path'].endswith('.json')] == frozen
    view = effective_requirements.project_requirements(store, current, page_ids=task['scope_pages'], unit='page_copy')
    policy = next(row for row in view['decisions'] if row['decision']['decision_id'] == record['decision_id'])
    assert policy['ref'] == replacement
    assert policy['decision']['replaces'] == selected
    # Only audit fields were ignored. Distinct instruction evidence remains
    # visible and changes the frozen requirement context, even for equal value.
    decide(store, choice(store, decision_id=record['decision_id'], replaces=replacement,
                        instruction_evidence=_instruction(store, 'new-policy-source')))
    assert not tasks.task_inputs_current(store, store.load_document(), task)
