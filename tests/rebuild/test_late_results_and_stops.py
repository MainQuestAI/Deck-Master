"""T04 slice 5: late results and the four distinct stop facts (AC-R05).

Withdrawal before a call, during a call and before acceptance are three formal
trajectories. In every one: no new call starts, an already-started call keeps
its real cost, and a result without eligibility is never adopted over the
current draft. A single task cancel is not a permanent scope withdrawal, an
ordinary continue neither widens scope nor revives a withdrawal, and the
project stop policy is its own fact.
"""
import pytest

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _allowance, _binding, _commit_task, _declared, _grant, _page, _project, _scope,
    _start, _strip_binding, _task)
from deck_master import collaboration, dependency_slices, eligibility, service
from deck_master.models import bump_revision, canonical_json_bytes, sha256_bytes
from deck_master.store import Store


def _running_call(store, project, *, budget_key=None, task_id="task-1", grant=None):
    """A claimed task with one begun (in-flight) call."""
    document = store.load_document()
    binding = _binding(document, authorization_ref=(grant or {}).get("authorization_ref"),
                       budget_key=budget_key)
    task = _task(document, task_id=task_id, kind="compose", status="running",
                 scope_pages=("p1",), allowances=[_allowance("call-1")], binding=binding)
    _commit_task(store, task, operation_id=f"commit-{task_id}")
    service.task_start(project, task_id=task_id, execution_ref="host-1")
    from deck_master import tasks as tasks_mod
    tasks_mod.call_begin(Store(project), task_id=task_id, allowance_id="call-1",
                         execution_ref="host-1")
    return task


def _submit(project, store, task, *, outcome="consumed"):
    staging = store.staging_dir / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "evidence.json").write_bytes(b'{"call": "consumed"}')
    envelope = {"kind": task["kind"],
                "files": [{"file_id": "ev1", "path": "evidence.json",
                           "media_type": "application/json"}],
                "pages": [_page("p1", "晚到结果。")], "page_order": ["p1"],
                "artifact_specs": [], "reviews": [],
                "usage_events": ([{"allowance_id": "call-1", "outcome": outcome,
                                   "evidence_file_ids": ["ev1"]}] if outcome else []),
                "notes": "late"}
    return service.accept_result(project, task_id=task["task_id"],
                                 operation_id=task["operation_id"],
                                 produced_against=task["produced_against"],
                                 result_payload=envelope)


def _page_text(store, page_id="p1"):
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == page_id)
    return store.read_object_json(entry["page"])["customer_visible"]["body_blocks"][0]["text"]


def _allowance_state(store, task_id="task-1", allowance_id="call-1"):
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref).get("task_id") == task_id)
    return next(entry["state"] for entry in task["call_allowances"]
                if entry["allowance_id"] == allowance_id)


# ---------------------------------------------------------------------------
# The three withdrawal trajectories


def test_withdrawal_before_start_refuses_the_new_call(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    document = store.load_document()
    task = _task(document, kind="compose", status="running", scope_pages=("p1",),
                 allowances=[_allowance("call-1")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    _commit_task(store, task)
    service.task_start(project, task_id="task-1", execution_ref="host-1")
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="范围撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    from deck_master import tasks as tasks_mod
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        tasks_mod.call_begin(Store(project), task_id="task-1", allowance_id="call-1",
                             execution_ref="host-1")
    assert "authorization_revoked" in excinfo.value.payload()["error"]["reason_codes"]
    # Nothing was spent: the slot stays reserved (releasing an unused
    # reservation is the existing ledger's concern, not a new budget rule) and
    # no consumed cost exists.
    assert _allowance_state(store) == "reserved"
    assert all(entry["state"] == "reserved"
               for ref in store.load_document()["tasks"]
               for entry in (store.read_object_json(ref).get("call_allowances") or []))


def test_withdrawal_during_the_call_settles_the_fact_and_refuses_adoption(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = _running_call(store, project, grant=grant)
    assert _allowance_state(store) == "in_flight"
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="调用中撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    before = _page_text(store)
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        _submit(project, store, task)
    error = excinfo.value.payload()["error"]
    assert "authorization_revoked" in error["reason_codes"]
    assert error["next_action"]
    assert _page_text(store) == before == "第一页。"
    assert _allowance_state(store) == "consumed"       # the in-flight call is real cost


def test_withdrawal_before_accept_keeps_the_cost(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = _running_call(store, project, grant=grant)
    from deck_master import tasks as tasks_mod
    tasks_mod.call_settle(store, task_id="task-1", allowance_id="call-1",
                          outcome="consumed", report_bytes=b'{"call": "consumed"}')
    assert _allowance_state(store) == "consumed"
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="接纳前撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    before = _page_text(store)
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        _submit(project, store, task, outcome=None)
    assert "authorization_revoked" in excinfo.value.payload()["error"]["reason_codes"]
    assert _page_text(store) == before
    assert _allowance_state(store) == "consumed"       # settled cost survives the refusal


def test_a_revoked_result_is_never_adopted_later(tmp_path):
    """A second attempt (after re-reading) also fails: withdrawal is not a wait."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = _running_call(store, project, grant=grant)
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    for attempt in range(2):
        with pytest.raises(eligibility.EligibilityBlocked):
            _submit(project, store, task)
    assert _page_text(store) == "第一页。"


# ---------------------------------------------------------------------------
# The unconditional backstop: a real dispatch without a binding cannot adopt


def _inject_historical_allowance(store, task_id, allowance):
    """Give a real task a call slot that already happened (MIGRATION §3.5:
    an in-flight call keeps settling after the upgrade)."""
    import uuid
    from deck_master import tasks as tasks_mod
    document = store.load_document()
    task = next(store.read_object_json(ref) for ref in document["tasks"]
                if store.read_object_json(ref).get("task_id") == task_id)
    updated = {**task, "call_allowances": [*(task.get("call_allowances") or []), allowance]}
    task_ref = store.put_json_object(updated)
    operation_id = f"inject-{uuid.uuid4().hex[:8]}"
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update",
                                      "description": "historical consumed call", "read_set": []})
    bumped = tasks_mod._replace_task_ref(bumped, task, task_ref, store)
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)




def _real_repair_task(project, store, page_id="p1"):
    """A task dispatched through the real entry, then stripped to the legacy
    shape. The real dispatch path now stamps a collaboration binding (T03), so
    the unconditional backstop is exercised by removing it the way a
    pre-upgrade task would look (MIGRATION §3.5: such a task may only settle
    the call facts it already has)."""
    task = service.open_host_task(store, kind="repair", page_ids=[page_id],
                                  instruction="repair p1 after a late result")
    assert task.get("collaboration_binding")  # the real entry writes one now
    return _strip_binding(store, task["task_id"])


def test_real_dispatch_without_binding_cannot_be_accepted(tmp_path):
    """P1 regression: a task from the real dispatch path (no binding yet) can
    never write production state, authorized or not, revoked or not."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    _grant(project, store, actions=("dispatch.host_task",),
           scope=_scope(page_ids=["p1"]))
    task = _real_repair_task(project, store)
    before = _page_text(store)
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        _submit(project, store, task, outcome=None)
    error = excinfo.value.payload()["error"]
    assert error["reason_codes"] == ["decision_needed"]
    assert "no collaboration binding" in error["message"]
    assert "bound task" in error["next_action"]
    assert "settle" in error["message"]
    assert _page_text(store) == before == "第一页。"


def test_real_dispatch_without_binding_refused_even_after_a_revocation(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("dispatch.host_task", "call.begin"),
                   scope=_scope(page_ids=["p1"]))
    task = _real_repair_task(project, store)
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        _submit(project, store, task, outcome=None)
    assert "decision_needed" in excinfo.value.payload()["error"]["reason_codes"]
    decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                    "task.accept", {"task": task})
    assert decision["allowed"] is False


def test_real_dispatch_without_binding_settles_its_historical_cost_only(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    _grant(project, store, actions=("dispatch.host_task",), scope=_scope(page_ids=["p1"]))
    task = _real_repair_task(project, store)
    _inject_historical_allowance(store, task["task_id"],
                                 {"allowance_id": "call-hist", "state": "consumed",
                                  "execution_ref": "host-old", "invocation_ref": None,
                                  "evidence": []})
    with pytest.raises(eligibility.EligibilityBlocked):
        _submit(project, store, task, outcome=None)
    # The cost that already happened is untouched by the refusal…
    current = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                   if store.read_object_json(ref).get("task_id") == task["task_id"])
    states = {entry["allowance_id"]: entry["state"] for entry in current["call_allowances"]}
    assert states == {"call-hist": "consumed"}
    # …and the fact channels stay open for that very task.
    fresh = {**task, "call_allowances": current["call_allowances"]}
    assert eligibility.evaluate(store, store.load_document(), store.load_document(),
                                "call.settle", {"task": fresh})["allowed"] is True
    assert eligibility.evaluate(store, store.load_document(), store.load_document(),
                                "task.cancel", {"task": fresh})["allowed"] is True
    # Production stays refused.
    assert eligibility.evaluate(store, store.load_document(), store.load_document(),
                                "task.accept", {"task": fresh})["allowed"] is False


def test_record_only_acceptance_is_limited_to_observation_tasks(tmp_path):
    """A production task can never use the record-only door: the envelope alone
    does not decide, the task kind does (review/analysis only)."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    review_envelope = {"kind": "repair", "files": [],
                       "artifact_specs": [], "usage_events": [],
                       "reviews": [{"schema_version": "deck_review.v1",
                                    "review_id": "r-1", "kind": "readability",
                                    "review_stage": "final", "status": "pass",
                                    "reviewer": {"type": "host_self", "assurance": "host_attested"},
                                    "subjects": [], "dependencies": [],
                                    "observations": ["observed"], "findings": []}]}
    production = _task(document, kind="repair", status="running", scope_pages=("p1",))
    assert eligibility.evaluate(store, document, document, "task.accept",
                                {"task": production, "record_only": False})["allowed"] is False
    # The caller's own record_only computation refuses a production task…
    from deck_master.tasks import _record_only
    assert _record_only(review_envelope, production) is False
    # …and an observation task with the very same envelope stays a fact channel.
    review_task = _task(document, kind="review", status="running", scope_pages=("p1",))
    assert _record_only(review_envelope, review_task) is True


# ---------------------------------------------------------------------------
# cancel is not a withdrawal; continue neither widens nor revives


def test_task_cancel_is_not_a_scope_withdrawal(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"]))
    _grant(project, store, actions=("dispatch.host_task",), scope=_scope(page_ids=["p1", "p2"]))
    task = service.open_host_task(store, kind="review", page_ids=["p1"],
                                  instruction="review p1", review_stage="page_visual")
    cancelled = service.task_cancel(project, task_id=task["task_id"], reason="这一件先停")
    assert cancelled["status"] == "cancelled"
    # The scope is still open: another page's work can be dispatched, and the
    # same page can be re-dispatched with a new task identity.
    again = service.open_host_task(store, kind="review", page_ids=["p1"],
                                   instruction="new review of p1", review_stage="page_visual")
    assert again["task_id"] != task["task_id"]
    assert again["status"] == "awaiting_host"
    # And the project scope is still authorized.
    decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                    "dispatch.host_task")
    assert "authorization_revoked" not in decision["reason_codes"]


def test_continue_neither_widens_nor_revives(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="edit", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    collaboration.record_decision(
        project, input={"topic": "direction", "subject_refs": [], "value": "不改主线",
                        "disposition": "rejected", "authority_mode": "direct_user",
                        "scope": _scope(page_ids=["p1"]),
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-reject")
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    before = store.load_document()
    service.continue_project(project)
    after = store.load_document()
    # No new authorization appeared and the withdrawal still holds.
    assert dependency_slices.authorization_effectiveness(
        store, after, grant["authorization_ref"])["effective"] is False
    for ref in after["collaboration"]["decisions"]:
        assert store.read_object_json(ref)["disposition"] in ("rejected", "deferred")
    # The request scope did not grow either.
    assert after["collaboration"]["request"]["scope"] == before["collaboration"]["request"]["scope"]


def test_pause_stops_new_calls_but_not_settlement(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = _running_call(store, project, grant=grant)
    collaboration.pause_request(project, reason="先停一下",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    document = store.load_document()
    from deck_master import tasks as tasks_mod
    document = store.load_document()
    document["tasks"]  # keep the read explicit for the assertion below
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        tasks_mod.call_begin(Store(project), task_id="task-1", allowance_id="call-2",
                             execution_ref="host-1")
    assert "request_paused" in excinfo.value.payload()["error"]["reason_codes"]
    settle = eligibility.evaluate(store, document, document, "call.settle", {"task": task})
    assert settle["allowed"] is True and settle["facts_only"] is True
    tasks_mod.call_settle(store, task_id="task-1", allowance_id="call-1", outcome="consumed",
                          report_bytes=b'{"call": "consumed"}')
    assert _allowance_state(store) == "consumed"


def test_user_stop_is_its_own_stop_fact(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    # The stop policy is recorded before the grant, so the grant's basis stays
    # current and the only gap is the stop fact itself.
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "stop-op", "kind": "policy_update",
                                      "description": "user stop", "read_set": []})
    bumped["policy"] = {**document["policy"], "user_stop": True}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="stop-op")
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                    "call.begin")
    assert "user_stop" in decision["reason_codes"]
    assert decision["decision_card_ref_or_projection"]["state"] == "user_stop"
    # Lifting the stop fact re-enables calls without touching the request.
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "stop-off", "kind": "policy_update",
                                      "description": "stop lifted", "read_set": []})
    bumped["policy"] = {**document["policy"], "user_stop": False}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="stop-off")
    lifted = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                  "call.begin")
    assert "user_stop" not in lifted["reason_codes"]
    # Lifting the stop is itself a policy change: the grant recorded against the
    # stopped policy needs re-recording (its registered policy basis moved),
    # which is the same rule the resolver applies to every policy change.
    assert "basis_stale" in lifted["reason_codes"]
    _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]),
           operation_id="op-grant-after-lift")
    allowed = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                   "call.begin")
    assert allowed["allowed"] is True, allowed["reason_codes"]
    assert grant["authorization_id"]


def test_restore_does_not_revive_a_withdrawal(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    active_revision = store.load_document()["revision_id"]
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    started = store.load_document()
    assert sha256_bytes(canonical_json_bytes(started)) != active_revision
    # Restoring the revision where the authorization was still active restores
    # content/visual facts only — the withdrawal stays.
    from deck_master.editing import restore
    restore(project, revision_id=active_revision,
            base_revision=store.load_document()["revision_id"], operation_id="op-restore")
    after = store.load_document()
    assert after["compatibility"]["minimum_writer"] == "collaboration.v1"
    state = dependency_slices.authorization_effectiveness(store, after, grant["authorization_ref"])
    assert state["effective"] is False
    assert set(state["reasons"]) & {"authorization_revoked", "not_in_current_control"}
    decision = eligibility.evaluate(store, after, after, "call.begin")
    assert decision["allowed"] is False
