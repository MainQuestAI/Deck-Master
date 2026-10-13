"""T04 slice 4: bounded budgets and exhausted-vs-withdrawn semantics (AC-R07).

The deck budget is computed and displayed, not dictated by the user: N agreed
pages, K reusable, at most N-K first generation calls, retries 0. A local edit
that asks for usable artwork gets one bounded rebuild per page that must really
be redrawn. Credits are per page and never refresh; the last legal call can
still be accepted after the budget is exhausted, while a withdrawal blocks the
not-yet-adopted result.
"""
import pytest

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _binding, _commit_task, _declared, _grant, _page, _project, _scope, _start, _task)
from test_scope_and_delegation import _plan_object  # noqa: E402

from deck_master import (collaboration, collaboration_budget, dependency_slices,
                         eligibility, service)
from deck_master.models import ModelError
from deck_master.store import Store


def _task_with_allowances(store, *, allowances, binding=None, task_id="task-1"):
    document = store.load_document()
    task = _task(document, task_id=task_id, kind="blueprint", status="running",
                 scope_pages=("p1",), allowances=allowances, binding=binding)
    _commit_task(store, task, operation_id=f"commit-{task_id}")
    return task


def _with_blueprint(store, page_id="p1"):
    """Give one page a reusable original image (the K in N-K)."""
    document = store.load_document()
    artifact = store.put_json_object({
        "schema_version": "deck_artifact.v1", "artifact_id": f"bp-{page_id}",
        "role": "blueprint", "page_id": page_id,
        "file": store.put_blob(b"png-bytes", ext="png"), "media_type": "image/png"})
    import uuid
    operation_id = f"blueprint-{uuid.uuid4().hex[:8]}"
    from deck_master.models import bump_revision
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "artifact_adoption",
                                      "description": "reusable blueprint", "read_set": []})
    entry = next(e for e in bumped["pages"] if e["page_id"] == page_id)
    entry["blueprint"] = artifact
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return artifact


# ---------------------------------------------------------------------------
# initial_per_page


def test_initial_per_page_counts_selected_and_reused_pages(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"]))
    _with_blueprint(store, "p1")
    plan = collaboration_budget.initial_per_page_plan(
        store, store.load_document(), request_id="req-1", page_order=["p1", "p2"])
    assert plan["pages_selected"] == 2 and plan["pages_reused"] == 1
    assert plan["first_generation_upper_bound"] == 1
    assert plan["max_external_calls"] == 1
    assert plan["retry_budget"] == 0
    assert plan["credits"] == [{"page_id": "p2", "budget_key": "req-1:initial:p2", "calls": 1}]
    assert "选定 2 页，复用 1 页，首次生成最多 1 次" in plan["display"]
    assert "额外重试为 0" in plan["display"]


def test_initial_per_page_needs_a_fixed_page_set(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=[]))
    with pytest.raises(ModelError, match="no fixed page set"):
        collaboration_budget.initial_per_page_plan(store, store.load_document(),
                                                   request_id="req-1")


def test_a_sample_trial_never_expands_into_the_deck_budget(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="design_trial", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["design"], purpose="exploratory"))
    document = store.load_document()
    # A second page is outside the trial request; no computed deck budget can
    # be materialized from it.
    decision = eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                    {"targets": {"page_ids": ["p2"], "layers": ["blueprint"]}})
    assert "scope_exceeded" in decision["reason_codes"]
    trial_plan = collaboration_budget.initial_per_page_plan(
        store, document, request_id="req-1", page_order=["p1"])
    assert trial_plan["max_external_calls"] == 1     # the sample's own trial budget only


# ---------------------------------------------------------------------------
# edit_rebuild_per_page


def _change_plan(store, actions):
    document = store.load_document()
    entries = {e["page_id"]: e for e in document["pages"]}
    plan_actions = []
    for page_id, layer, slot in actions:
        plan_actions.append({"action_id": f"action-{len(plan_actions) + 1}",
                             "page_id": page_id, "page_ref": entries[page_id]["page"],
                             "layer": layer, "target_ref": entries[page_id].get(slot),
                             "kind": "repair", "write_slots": [slot],
                             "max_calls": int(slot == "blueprint"),
                             "downstream": []})
    return {"schema_version": "change_plan.v1", "project_id": document["project_id"],
            "base_revision": document["revision_id"], "input": {}, "payload_digest": "0" * 64,
            "actions": plan_actions, "max_calls": sum(a["max_calls"] for a in plan_actions),
            "content_identity": "0" * 64, "effects": ""}


def test_edit_rebuild_bounds_each_page_once_and_zero_for_cheap_layers(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="edit", content_intent=None,
           scope=_scope(page_ids=["p1", "p2"], layers=["page_copy", "svg", "blueprint"]))
    plan = _change_plan(store, [("p1", "blueprint", "blueprint"), ("p2", "svg", "svg")])
    budget = collaboration_budget.edit_rebuild_plan(
        store, store.load_document(), request_id="req-edit", change_plan=plan,
        scope=_scope(page_ids=["p1", "p2"], layers=["page_copy", "svg", "blueprint"]))
    assert budget["must_redraw_page_ids"] == ["p1"]
    assert budget["reused_page_ids"] == ["p2"]            # an SVG-only change: 0 calls
    assert budget["first_rebuild_upper_bound"] == 1
    assert budget["retry_budget"] == 0
    assert budget["credits"] == [{"page_id": "p1", "budget_key": "req-edit:rebuild:p1", "calls": 1}]
    assert "必须重画 1 页" in budget["display"] and "重试 0" in budget["display"]


def test_edit_scope_gaps_are_listed_not_rebuilt(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="edit", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["page_copy", "blueprint"]))
    plan = _change_plan(store, [("p1", "blueprint", "blueprint"), ("p2", "blueprint", "blueprint")])
    budget = collaboration_budget.edit_rebuild_plan(
        store, store.load_document(), request_id="req-edit", change_plan=plan,
        scope=_scope(page_ids=["p1"], layers=["page_copy", "blueprint"]))
    assert budget["must_redraw_page_ids"] == ["p1"]
    assert budget["scope_gaps"] == [{"page_id": "p2", "reason": "page_outside_authorized_scope"}]
    assert "范围外缺口 1 页（不自动重做）" in budget["display"]


def test_text_only_edit_has_no_image_budget(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="edit", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    plan = _change_plan(store, [("p1", "content", "page")])
    budget = collaboration_budget.edit_rebuild_plan(
        store, store.load_document(), request_id="req-text", change_plan=plan,
        scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    assert budget["max_external_calls"] == 0 and budget["credits"] == []
    document = store.load_document()
    decision = eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                    {"targets": {"page_ids": ["p1"], "layers": ["blueprint"]}})
    assert "scope_exceeded" in decision["reason_codes"]


# ---------------------------------------------------------------------------
# Exhaustion versus withdrawal


def test_exhausted_budget_accepts_the_last_result_and_refuses_new_calls(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = _task_with_allowances(store, allowances=[{"allowance_id": "call-1",
                                                     "state": "consumed",
                                                     "execution_ref": "host-1",
                                                     "invocation_ref": None, "evidence": []}],
                                 binding=_binding(store.load_document(),
                                                  authorization_ref=grant["authorization_ref"],
                                                  budget_key="req-1:initial:p1"))
    document = store.load_document()
    assert eligibility.authorization_budget(
        store, document, grant["authorization_ref"])["state"] == "exhausted"
    # The last legal result can still be accepted and the request closed out.
    accept = eligibility.evaluate(store, document, document, "task.accept", {"task": task})
    assert accept["allowed"] is True, accept["reason_codes"]
    # A new call is refused — exhaustion is not a withdrawal.
    allocate = eligibility.evaluate(store, document, document, "allowance.allocate",
                                    {"task": task,
                                     "targets": {"page_ids": ["p1"]}})
    assert "budget_exhausted" in allocate["reason_codes"]
    assert "only blocks new calls" in allocate["next_action"]


def test_withdrawal_refuses_adoption_while_exhaustion_does_not(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]),
                   max_external_calls=1)
    task = _task_with_allowances(store, allowances=[{"allowance_id": "call-1",
                                                     "state": "consumed",
                                                     "execution_ref": "host-1",
                                                     "invocation_ref": None, "evidence": []}],
                                 binding=_binding(store.load_document(),
                                                  authorization_ref=grant["authorization_ref"]))
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    document = store.load_document()
    adoption = eligibility.evaluate(store, document, document, "task.accept", {"task": task})
    assert adoption["allowed"] is False
    assert "authorization_revoked" in adoption["reason_codes"]
    # Settlement stays possible: the withdrawal blocks adoption, not the facts.
    settle = eligibility.evaluate(store, document, document, "call.settle", {"task": task})
    assert settle["allowed"] is True and settle["facts_only"] is True


def test_candidate_adoption_needs_adoption_authority_not_image_budget(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    adoption = _grant(project, store, actions=("candidate.adopt",),
                      scope=_scope(page_ids=["p1"]), max_external_calls=0,
                      operation_id="op-grant-adopt")
    document = store.load_document()
    decision = eligibility.evaluate(store, document, document, "candidate.adopt",
                                    {"targets": {"page_ids": ["p1"], "layers": ["page_copy"]}})
    assert decision["allowed"] is True, decision["reason_codes"]
    # The adoption authorization itself consumes nothing.
    assert eligibility.authorization_budget(
        store, document, adoption["authorization_ref"])["used"] == 0
    assert not any(entry.get("state") in ("reserved", "in_flight", "consumed", "unknown")
                   for ref in document["tasks"] for entry in
                   (store.read_object_json(ref).get("call_allowances") or []))


def test_child_grants_share_one_ceiling_instead_of_copying_it(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"]))
    parent = _grant(project, store, mode="delegate", actions=("call.begin",),
                    scope=_scope(page_ids=["p1", "p2"]), delegated_topics=("direction",),
                    max_external_calls=2, operation_id="op-parent")
    children = [_grant(project, store, actions=("call.begin",),
                       scope=_scope(page_ids=[page_id]), max_external_calls=2,
                       parent_authorization_ref=parent["authorization_ref"],
                       budget_parent_ref=parent["authorization_ref"],
                       operation_id=f"op-child-{page_id}")
                for page_id in ("p1", "p2")]
    document = store.load_document()
    for child in children:
        budget = eligibility.authorization_budget(store, document, child["authorization_ref"])
        assert budget["ceiling"] == 2      # the shared root's ceiling, not 2 + 2
        assert set(budget["chain_ids"]) == {parent["authorization_id"],
                                            *[c["authorization_id"] for c in children]}
    # Usage anywhere in the chain spends the one shared ceiling.
    for index, page_id in enumerate(("p1", "p2")):
        child_ref = children[index]["authorization_ref"]
        _task_with_allowances(store, allowances=[{"allowance_id": "call-1",
                                                  "state": "consumed", "execution_ref": "h",
                                                  "invocation_ref": None, "evidence": []}],
                              binding=_binding(store.load_document(),
                                               authorization_ref=child_ref),
                              task_id=f"task-{page_id}")
    document = store.load_document()
    budget = eligibility.authorization_budget(store, document, children[0]["authorization_ref"])
    assert budget["used"] == 2 and budget["remaining"] == 0 and budget["state"] == "exhausted"


def test_repeated_materialization_never_refreshes_a_consumed_credit(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=[], layers=["blueprint"]))
    plan_ref = _plan_object(store, store.load_document(), ["p1"])
    parent = _grant(project, store, mode="delegate", actions=("dispatch.blueprint",),
                    scope=_scope(subject="deck", page_ids=[], layers=["blueprint"]),
                    delegated_topics=("direction",), max_external_calls=0,
                    constraints={"future_pages": {"selector": "adopted_plan_for_this_request",
                                                  "max_pages": 1,
                                                  "max_pages_basis": "provided"}},
                    operation_id="op-delegate")
    first = collaboration_budget.materialize_execution(
        project, parent_authorization_ref=parent["authorization_ref"], plan_ref=plan_ref,
        page_order=["p1"], budget_template="initial_per_page", operation_id="op-mat-1",
        base_revision=store.load_document()["revision_id"], instruction_evidence=_declared(store))
    record = store.read_object_json(first["authorization_ref"])
    # Spend the credit through the real ledger.
    _task_with_allowances(store, allowances=[{"allowance_id": "call-1", "state": "consumed",
                                              "execution_ref": "host-1", "invocation_ref": None,
                                              "evidence": []}],
                          binding={"request_id": store.load_document()["collaboration"]["request"]["request_id"],
                                   "phase": "production", "executor_type": "host",
                                   "authorization_ref": first["authorization_ref"],
                                   "decision_refs": [],
                                   "write_scope": record["scope"],
                                   "adoption_policy": "candidate_only",
                                   "eligibility_basis": [],
                                   "budget_key": f"{record['budget_key'].split(':initial:')[0]}:initial:p1"},
                          task_id="task-credit")
    # A restart, a new operation id and a repeated grant all re-derive the same
    # credit — and it is already consumed.
    with pytest.raises(ModelError, match="already consumed"):
        collaboration_budget.materialize_execution(
            project, parent_authorization_ref=parent["authorization_ref"], plan_ref=plan_ref,
            page_order=["p1"], budget_template="initial_per_page", operation_id="op-mat-2",
            base_revision=store.load_document()["revision_id"], instruction_evidence=_declared(store))
