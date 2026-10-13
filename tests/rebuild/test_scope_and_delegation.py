"""T04 slice 4: request isolation, scope binding and delegation (AC-R01–R03, R07).

A new request advances only itself; a replaced request's authority stops being
usable unless the new request explicitly lists it as background work. Execute
grants bind a fixed page set and layers, and a delegate materializes into real
page ids from a fixed Plan — never an empty set that would mean "all pages".
Withdrawing an authority chain withdraws the derived budgets and tasks.
"""
import json

import pytest

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _binding, _commit_task, _declared, _grant, _page, _project, _scope, _start,
    _strip_binding, _task)

from deck_master import collaboration, collaboration_budget, dependency_slices, eligibility, service
from deck_master.models import ModelError, canonical_json_bytes, sha256_bytes
from deck_master.store import Store


def _plan_object(store, document, page_order) -> dict:
    """A committed content_plan.v2 whose page_order is the fixed page set."""
    roles = [{"page_id": page_id, "role": "detail", "audience_question": "q",
              "intended_takeaway": "t", "narrative_node_ids": [], "source_links": [],
              "required_qualifications": [], "content_profile": "simple",
              "density_rationale": "r", "timing_seconds": None, "transition_to_next": None}
             for page_id in page_order]
    plan = {"schema_version": "content_plan.v2", "plan_id": "plan-fixed", "version": 1,
            "project_id": document["project_id"], "task_id": "t", "origin": "host_composed",
            "basis": {"revision_id": "plan-basis-1", "input_digest": "0" * 64},
            "previous_ref": None, "mode": "planned", "narrative_ref": None,
            "imported_manuscript": None,
            "input": {"schema_version": "content_plan_input.v2", "chapters": [],
                      "page_order": list(page_order), "page_roles": roles,
                      "page_budget": {"exact": len(page_order), "target": None, "max": None},
                      "time_budget": {"total_seconds": None, "speaking_seconds": None,
                                      "interaction_seconds": None, "constraint": "unspecified"},
                      "speech_policy": {"mode": "none", "source": "default", "output": "none"},
                      "issues": [], "tradeoff_issue_ids": []},
            "page_links": []}
    return store.put_json_object(plan)


# ---------------------------------------------------------------------------
# Request isolation


def test_replace_cuts_the_previous_authority(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store, intent="full_deck")
    grant = _grant(project, store, actions=("dispatch.blueprint",),
                   scope=_scope(page_ids=["p1", "p2"]))
    assert dependency_slices.authorization_effectiveness(
        store, store.load_document(), grant["authorization_ref"])["effective"] is True
    # A new, narrower request replaces it.
    replaced = _start(project, store, operation_id="op-start-2", intent="design_trial",
                      content_intent=None, scope=_scope(page_ids=["p1"], layers=["design"]),
                      replace_request_id=first["request_id"])
    assert replaced["request_id"] != first["request_id"]
    after = store.load_document()
    state = dependency_slices.authorization_effectiveness(store, after, grant["authorization_ref"])
    assert state["effective"] is False
    assert "request_superseded" in state["reasons"]
    # And a blueprint dispatch can no longer borrow the old grant.
    decision = eligibility.evaluate(store, after, after, "dispatch.blueprint",
                                    {"targets": {"page_ids": ["p1"], "layers": ["blueprint"]}})
    assert decision["allowed"] is False
    assert "scope_exceeded" in decision["reason_codes"]


def test_replace_reports_the_prior_disposition(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store, intent="full_deck")
    grant = _grant(project, store, actions=("dispatch.blueprint",))
    document = store.load_document()
    _commit_task(store, _task(document, status="awaiting_host", scope_pages=("p1",),
                              binding=_binding(document, authorization_ref=grant["authorization_ref"])))
    replaced = _start(project, store, operation_id="op-start-2", intent="edit",
                      content_intent=None, scope=_scope(page_ids=["p1"], layers=["page_copy"]),
                      replace_request_id=first["request_id"])
    assert replaced["prior_request_disposition"]["request_id"] == first["request_id"]
    assert replaced["prior_request_disposition"]["disposition"] == "superseded"
    assert grant["authorization_id"] in replaced["paused_authorizations"]
    assert replaced["affected_tasks"] == ["task-1"]


def test_explicit_background_list_keeps_the_old_work_alive(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store, intent="full_deck")
    grant = _grant(project, store, actions=("dispatch.blueprint",))
    document = store.load_document()
    _commit_task(store, _task(document, status="awaiting_host", scope_pages=("p1",),
                              binding=_binding(document, authorization_ref=grant["authorization_ref"])))
    _start(project, store, operation_id="op-start-2", intent="edit", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["page_copy"]),
           replace_request_id=first["request_id"],
           background_request_ids=[first["request_id"]])
    after = store.load_document()
    state = dependency_slices.authorization_effectiveness(store, after, grant["authorization_ref"])
    assert state["effective"] is True, state
    task = next(store.read_object_json(ref) for ref in after["tasks"]
                if store.read_object_json(ref).get("task_id") == "task-1")
    binding_state = eligibility.task_binding_state(store, after, task)
    assert binding_state["status"] == "valid"
    assert binding_state.get("background_request_id") == first["request_id"]


def test_replace_reports_unbound_active_tasks_honestly(tmp_path):
    """A task without a binding (the pre-upgrade shape, injected here because
    the real dispatch path now stamps one) must appear in the replace report
    (affected + an explicit unbound entry), never be silently missing or
    credited as covered."""
    project, store = _project(tmp_path)
    first = _start(project, store, intent="full_deck")
    _grant(project, store, actions=("dispatch.host_task",), scope=_scope(page_ids=["p1", "p2"]))
    task = service.open_host_task(store, kind="repair", page_ids=["p1"],
                                  instruction="repair p1 (dispatched without a binding)")
    assert task.get("collaboration_binding")  # the real entry writes one now
    task = _strip_binding(store, task["task_id"])
    replaced = _start(project, store, operation_id="op-start-2", intent="edit", content_intent=None,
                      scope=_scope(page_ids=["p1"], layers=["page_copy"]),
                      replace_request_id=first["request_id"])
    assert task["task_id"] in replaced["affected_tasks"]
    unbound = next(entry for entry in replaced["unbound_tasks"]
                   if entry["task_id"] == task["task_id"])
    assert unbound["status"] == "awaiting_host"
    assert unbound["reason"] == "no_collaboration_binding"
    assert "only settled call facts remain" in unbound["handling"]
    # And the report is honest about the consequence: the task can no longer be
    # accepted as production.
    decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                    "task.accept", {"task": task})
    assert decision["allowed"] is False


def test_review_only_never_borrows_an_old_full_deck_grant(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store, intent="full_deck")
    _grant(project, store, actions=("dispatch.blueprint", "page.edit"),
           scope=_scope(page_ids=["p1", "p2"]))
    _start(project, store, operation_id="op-start-2", intent="review_only", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["review"], purpose="review"),
           replace_request_id=first["request_id"])
    document = store.load_document()
    from deck_master.editing import edit_page
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        edit_page(project, page=_page("p1", "改稿。"), base_revision=document["revision_id"],
                  page_hash=entry["page"]["sha256"], operation_id="op-edit")
    assert "scope_exceeded" in excinfo.value.payload()["error"]["reason_codes"]


def test_execute_grant_binds_pages_and_layers(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"],
                                        layers=["plan", "blueprint", "page_copy"]))
    _grant(project, store, actions=("dispatch.blueprint",),
           scope=_scope(page_ids=["p1"], layers=["plan", "blueprint"]))
    document = store.load_document()
    inside = eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                  {"targets": {"page_ids": ["p1"], "layers": ["blueprint"]}})
    assert inside["allowed"] is True, inside["reason_codes"]
    outside_page = eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                        {"targets": {"page_ids": ["p2"], "layers": ["blueprint"]}})
    assert "scope_exceeded" in outside_page["reason_codes"]
    outside_layer = eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                         {"targets": {"page_ids": ["p1"], "layers": ["output"]}})
    assert "scope_exceeded" in outside_layer["reason_codes"]
    # The request says nothing about the output layer either, so a compile for
    # this request is out of scope as well.
    compile_decision = eligibility.evaluate(store, document, document, "compile.ppt")
    assert "scope_exceeded" in compile_decision["reason_codes"]


# ---------------------------------------------------------------------------
# Delegation materialization


def test_delegate_materializes_real_page_ids_from_a_fixed_plan(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=[], page_manifest_ref=None,
                                        layers=["plan", "blueprint", "page_copy"]))
    plan_ref = _plan_object(store, store.load_document(), ["p1", "p2"])
    parent = _grant(project, store, mode="delegate", actions=("dispatch.blueprint",),
                    scope=_scope(subject="deck", page_ids=[], layers=["plan", "blueprint"]),
                    delegated_topics=("direction",), max_external_calls=0,
                    constraints={"future_pages": {"selector": "adopted_plan_for_this_request",
                                                  "max_pages": 2,
                                                  "max_pages_basis": "provided"}},
                    operation_id="op-delegate")
    # The parent names no pages and cannot call directly.
    assert parent["assurance"] == "host_attested"
    document = store.load_document()
    assert eligibility.authorization_budget(store, document, parent["authorization_ref"])["ceiling"] == 0

    first = collaboration_budget.materialize_execution(
        project, parent_authorization_ref=parent["authorization_ref"],
        plan_ref=plan_ref, page_order=["p1", "p2"], budget_template="initial_per_page",
        operation_id="op-materialize-1", base_revision=store.load_document()["revision_id"],
        instruction_evidence=_declared(store))
    record = store.read_object_json(first["authorization_ref"])
    assert record["scope"]["page_ids"] == ["p1", "p2"]           # real ids, never empty
    assert record["budget_parent_ref"] == parent["authorization_ref"]
    assert record["max_external_calls"] == 2                     # one bounded credit per page
    assert record["budget_template"] == "initial_per_page"
    assert record["parent_authorization_ref"] == parent["authorization_ref"]


def test_materialization_refuses_an_empty_page_set(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=[]))
    parent = _grant(project, store, mode="delegate", actions=("dispatch.blueprint",),
                    scope=_scope(subject="deck", page_ids=[], layers=["blueprint"]),
                    delegated_topics=("direction",), max_external_calls=0)
    with pytest.raises(ModelError, match="not 'all pages'"):
        collaboration_budget.materialize_execution(
            project, parent_authorization_ref=parent["authorization_ref"],
            operation_id="op-materialize-empty", base_revision=store.load_document()["revision_id"],
            instruction_evidence=_declared(store))


def test_child_outside_the_parent_pages_is_refused(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"]))
    parent = _grant(project, store, mode="delegate", actions=("dispatch.blueprint",),
                    scope=_scope(page_ids=["p1"]), delegated_topics=("direction",),
                    max_external_calls=1, operation_id="op-delegate")
    with pytest.raises(ModelError, match="outside the parent delegation"):
        collaboration_budget.materialize_execution(
            project, parent_authorization_ref=parent["authorization_ref"],
            plan_ref=None, page_order=["p2"], operation_id="op-materialize-bad",
            base_revision=store.load_document()["revision_id"],
            instruction_evidence=_declared(store))


def test_chain_withdrawal_stops_the_derived_grant(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    parent = _grant(project, store, mode="delegate", actions=("call.begin",),
                    scope=_scope(page_ids=["p1"]), delegated_topics=("direction",),
                    max_external_calls=1, operation_id="op-delegate")
    child = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]),
                   max_external_calls=1, parent_authorization_ref=parent["authorization_ref"],
                   budget_parent_ref=parent["authorization_ref"], operation_id="op-child")
    document = store.load_document()
    assert dependency_slices.authorization_effectiveness(store, document,
                                                        child["authorization_ref"])["effective"]
    collaboration.revoke_authorization(project, authorization_id=parent["authorization_id"],
                                       reason="范围撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    after = store.load_document()
    state = dependency_slices.authorization_effectiveness(store, after, child["authorization_ref"])
    assert state["effective"] is False
    assert "parent_ineffective" in state["reasons"]
    decision = eligibility.evaluate(store, after, after, "call.begin")
    assert decision["allowed"] is False
    assert set(decision["reason_codes"]) & {"authorization_revoked", "authority_insufficient"}
    detail = next(r for r in decision["reasons"] if r["code"] in decision["reason_codes"])
    assert "parent_ineffective" in json.dumps(detail, ensure_ascii=False), detail
