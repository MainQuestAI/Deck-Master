"""Inherited N2: real dispatch binds a child; withdrawing its parent blocks adoption."""

from test_eligibility_enforcement import _project, _start, _scope, _grant
from deck_master import collaboration, eligibility, service


def test_real_host_task_is_withdrawn_when_bound_execute_grants_delegate_parent_is_revoked(tmp_path):
    project, store = _project(tmp_path)
    scope = _scope(page_ids=["p1"], layers=["review"])
    _start(project, store, intent="edit", scope=scope)
    actions = ("dispatch.host_task", "task.start", "task.accept")
    parent = _grant(project, store, actions=actions, mode="delegate", scope=scope, operation_id="grant-parent", max_external_calls=2)
    child = _grant(
        project,
        store,
        actions=actions,
        mode="execute",
        scope=scope,
        operation_id="grant-child",
        max_external_calls=1,
        parent_authorization_ref=parent["authorization_ref"],
    )
    task = service.open_host_task(store, kind="review", page_ids=["p1"], instruction="检查完整当前稿")
    assert task["collaboration_binding"]["authorization_ref"] == child["authorization_ref"]
    assert eligibility.task_binding_state(store, store.load_document(), task)["status"] == "valid"
    service.task_start(
        project,
        task_id=task["task_id"],
        execution_ref="synthetic-rc3-independent-host",
        supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
        capabilities=task.get("required_capabilities", []),
    )
    collaboration.revoke_authorization(
        project,
        authorization_id=parent["authorization_id"],
        reason="synthetic user withdrawal",
        base_revision=store.current_revision_id(),
        operation_id="revoke-parent",
    )
    state = eligibility.task_binding_state(store, store.load_document(), task)
    assert state["status"] == "withdrawn"
    assert "ancestor_authorization_revoked" in state["reasons"]
    current = store.load_document()
    decision = eligibility.evaluate(store, current, current, "task.accept", context={"task": task})
    assert not decision["allowed"] and "authorization_revoked" in decision["reason_codes"]
