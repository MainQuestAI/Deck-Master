"""T04 slice 3: every §6.2 boundary consumes the same eligibility judgement.

Each boundary gets a positive case (the action proceeds, or at least passes the
gate and fails later on a real prerequisite) and a counterexample that hits its
own risk (scope, authority, pause, budget, withdrawal). The refusal path is
also checked for its three promises: the draft stays, the calls that happened
are settled as facts, and the answer names a concrete next action.
"""
import json

import pytest

from rc3_fixtures import historical_snapshot, public_project, submit_host_fixture

from deck_master import collaboration, eligibility, service
from deck_master.changes import plan as changes_plan
from deck_master.models import (bump_revision, canonical_json_bytes, content_identity,
                                require_writer, sha256_bytes)
from deck_master.store import Store

FULL_LAYERS = ["narrative", "plan", "page_copy", "speech", "design", "blueprint",
               "svg", "review", "output"]


# ---------------------------------------------------------------------------
# Fixtures


def _ref(seed: str) -> dict:
    import hashlib
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _declared(store) -> dict:
    return {"kind": "host_attested_instruction",
            "source_ref": store.put_json_object({"fixture": "source"}),
            "source_locator": "chat:msg-1", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _scope(**over) -> dict:
    scope = {"subject": "pages", "page_ids": ["p1", "p2"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": list(FULL_LAYERS),
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "exploratory"}
    scope.update(over)
    return scope


def _page(pid: str, text: str) -> dict:
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": f"标题{pid}", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": text}]},
            "visual_spec": {"intent": "synthetic", "reference_mode": "new_design"}}


def _project(tmp_path, *, pages=True, region=True):
    """Current public RC3 input, or an explicitly historical reader fixture."""
    if region:
        project = public_project(tmp_path, create_input={"brief": "enforcement"},
            manuscript={"pages": [_page("p1", "第一页。"), _page("p2", "第二页。")]}
            if pages else None)["project"]
    else:
        project = historical_snapshot(tmp_path, scenario="fixed pre-migration entry safety",
            pages=[_page("p1", "第一页。"), _page("p2", "第二页。")] if pages else [])['project']
    return project, Store(project)


def _start(project, store, *, operation_id="op-start-1", intent="full_deck",
           content_intent=None, scope=None, **extra):
    current = (store.load_document().get("collaboration") or {}).get("request") or {}
    payload = {"intent": intent, "content_intent": content_intent,
               "instruction_evidence": _declared(store),
               "scope": scope or _scope(),
               "replace_request_id": extra.pop("replace_request_id",
                   current.get("request_id") if not current.get("closed") else None)}
    payload.update(extra)
    return collaboration.start_request(project, input=payload,
                                       base_revision=store.load_document()["revision_id"],
                                       operation_id=operation_id)


def _grant(project, store, *, actions, mode="execute", scope=None, operation_id="op-grant-1",
           max_external_calls=2, **extra):
    payload = {"mode": mode, "actions": list(actions),
               "scope": scope or _scope(), "decision_refs": [],
               "delegated_topics": list(extra.pop("delegated_topics", ["direction"] if mode == "delegate" else [])),
               "max_external_calls": max_external_calls, "max_candidate_count": 1,
               "adoption_policy": "within_scope",
               "instruction_evidence": _declared(store)}
    payload.update(extra)
    return collaboration.grant(project, input=payload,
                               base_revision=store.load_document()["revision_id"],
                               operation_id=operation_id)


def _settle_preproduction(store, *, seed="settle"):
    """Submit explicit L1 synthetic fidelity reviews through the real Host flow.

    The host_self label and evidence never claim independence or human/native
    execution. The current confirmed-manuscript policy must permit this path.
    """
    from deck_master import content_review

    document = store.load_document()
    request = document["collaboration"]["request"]
    page_ids = request["scope"]["page_ids"]
    dispatched = content_review.dispatch_preproduction_review(
        store.project_root, page_ids=page_ids,
        instruction=f"L1 synthetic fidelity protocol fixture: {seed}")
    assert dispatched["status"] == "review_dispatched", dispatched
    assert dispatched["requirement"] == "fidelity_only"
    task = dispatched["task"]
    document = store.load_document()
    pages = [entry for entry in document["pages"] if entry["page_id"] in page_ids]
    subjects = [ref for ref in (document.get("narrative"), document.get("content_plan")) if ref]
    subjects += [entry["page"] for entry in pages]
    deps = [{"kind": "content", "identity": key, "sha256": ref["sha256"]}
            for key, ref in (("narrative", document.get("narrative")),
                             ("content_plan", document.get("content_plan"))) if ref]
    deps += [{"kind": "content", "identity": f"page:{entry['page_id']}",
              "sha256": entry["page"]["sha256"]} for entry in pages]
    deps += [{"kind": "source", "identity": source["source_id"],
              "sha256": source["extract"]["sha256"]}
             for source in document.get("sources") or [] if source.get("extract")]
    execution_ref = f"L1-synthetic-fidelity-{seed}"
    evidence = store.put_json_object({"evidence_level": "L1_SYNTHETIC",
        "subjects": subjects, "human_or_native_evidence": False,
        "observation": "Synthetic protocol fixture inspected the bound manuscript objects."})
    reviews = [{
        "schema_version": "deck_review.v2", "review_id": f"review-{seed}-{kind}",
        "kind": kind, "review_stage": "preproduction", "status": "pass",
        "reviewer": {"type": "host_self", "id": "L1-synthetic-fidelity-host",
            "execution_ref": execution_ref, "independence_confirmed": False,
            "identity_receipt": None, "evidence_ref": evidence, "assurance": "host_attested"},
        "subjects": subjects, "dependencies": deps,
        "observations": [f"L1 synthetic fidelity fixture for the {kind} unit"],
        "findings": [], "created_at": "2026-10-15T00:00:00Z", "replaces": None}
        for kind in dispatched["units"]]
    outcome = submit_host_fixture(store.project_root, task_id=task["task_id"],
        execution_ref=execution_ref,
        host_declaration={"supported_protocols": [task["protocol_version"]],
                          "capabilities": task["required_capabilities"]},
        result_payload={"kind": "review", "files": [], "pages": [], "page_order": [],
            "artifact_specs": [], "reviews": reviews, "usage_events": [],
            "notes": "L1 synthetic fidelity test; no independent/human/native review."})
    assert outcome["status"] == "accepted", outcome


def _task(document, *, task_id="task-1", kind="compose", status="running",
          scope_pages=("p1",), allowances=(), binding=None, protocol=None):
    task = {"schema_version": "deck_task.v1", "task_id": task_id, "operation_id": f"op-{task_id}",
            "kind": kind, "status": status, "scope_pages": list(scope_pages),
            "instruction": "x", "inputs": [], "dependencies": [],
            "dispatch_revision": document["revision_id"],
            "produced_against": content_identity(document), "result_refs": [], "error": None,
            "execution_ref": "host-1" if status == "running" else None,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
            "cost_class": "host_reasoning",
            "usage": {"source": "not_reported", "external_calls": None},
            "call_allowances": list(allowances)}
    if protocol:
        task["protocol_version"] = protocol
    if binding:
        task["collaboration_binding"] = binding
    # Hand-built legacy compatible Tasks must prove the unchanged RC3 methods.
    from deck_master import method_resources
    methods = method_resources._read_ids(method_resources.rc3_method_ids_for(
        kind, phase=(task.get("collaboration_binding") or {}).get("phase")))
    task["method_release"] = method_resources.method_release(methods)
    return task


def _binding(document, *, scope=None, authorization_ref=None, budget_key=None):
    scope = scope or _scope(page_ids=["p1"])
    return {"request_id": document["collaboration"]["request"]["request_id"],
            "phase": "production", "executor_type": "host",
            "authorization_ref": authorization_ref, "decision_refs": [],
            "write_scope": scope, "adoption_policy": "candidate_only",
            "eligibility_basis": [],
            "eligibility_digest": eligibility.binding_eligibility_digest("production", scope, []),
            **({"budget_key": budget_key} if budget_key else {})}


def _allowance(allowance_id="call-1", state="reserved"):
    return {"allowance_id": allowance_id, "state": state, "execution_ref": "host-1",
            "invocation_ref": None, "evidence": []}


def _commit_task(store, task, *, operation_id="task-commit"):
    import uuid
    operation_id = f"{operation_id}-{uuid.uuid4().hex[:8]}"
    document = store.load_document()
    ref = store.put_json_object(task)
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update",
                                      "description": "test task", "read_set": []})
    bumped["tasks"] = [*(document.get("tasks") or []), ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return ref


def _stamp_binding(store, task_id, *, phase="production", authorization_ref=None,
                   request_id=None):
    """Stamp a collaboration binding on an already committed task.

    The real dispatch paths write their own bindings (T03); this helper exists
    for tests that need to re-bind a hand-committed or mutated task, and for
    the negative pair of ``_strip_binding`` below.
    """
    import uuid
    from deck_master import tasks as tasks_mod
    document = store.load_document()
    request = document["collaboration"]["request"]
    task = next(store.read_object_json(ref) for ref in document["tasks"]
                if store.read_object_json(ref).get("task_id") == task_id)
    scope = request["scope"]
    binding = {"request_id": request_id or request["request_id"],
               "phase": phase, "executor_type": "host",
               "authorization_ref": authorization_ref, "decision_refs": [],
               "write_scope": scope, "adoption_policy": "candidate_only",
               "eligibility_basis": [],
               "eligibility_digest": eligibility.binding_eligibility_digest(phase, scope, [])}
    updated = {**task, "collaboration_binding": binding}
    from deck_master import method_resources
    if "method_manifest" not in task:
        methods = method_resources._read_ids(method_resources.rc3_method_ids_for(task["kind"], phase=phase))
        updated["method_release"] = method_resources.method_release(methods)
    # Real dispatched Tasks retain their manifest and matching release digest.
    # This helper simulates a binding, not a method refresh.
    task_ref = store.put_json_object(updated)
    operation_id = f"stamp-{uuid.uuid4().hex[:8]}"
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update",
                                      "description": "stamp collaboration binding", "read_set": []})
    bumped = tasks_mod._replace_task_ref(bumped, task, task_ref, store)
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return binding


def _strip_binding(store, task_id):
    """Re-commit a task without its collaboration binding (pre-upgrade shape).

    The unconditional backstop (a task without a binding may only settle the
    call facts it already has) is exercised through this mutation, the way a
    task dispatched before the collaboration writer would look (MIGRATION §3.5).
    """
    import uuid
    from deck_master import tasks as tasks_mod
    document = store.load_document()
    task = next(store.read_object_json(ref) for ref in document["tasks"]
                if store.read_object_json(ref).get("task_id") == task_id)
    updated = {key: value for key, value in task.items() if key != "collaboration_binding"}
    task_ref = store.put_json_object(updated)
    operation_id = f"strip-{uuid.uuid4().hex[:8]}"
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update",
                                      "description": "unbound task (pre-upgrade shape)",
                                      "read_set": []})
    bumped = tasks_mod._replace_task_ref(bumped, task, task_ref, store)
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return updated


def _page_hash(store, page_id="p1"):
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == page_id)
    return store.read_object_json(entry["page"])["customer_visible"]["title"]


def _blocked(exc) -> dict:
    return exc.value.payload()["error"]


# ---------------------------------------------------------------------------
# Creation and routing


def test_continue_reports_a_blocked_dispatch_as_a_decision_card(tmp_path):
    """A write_only request cannot reach image production; continue answers with
    a card instead of dispatching the whole deck (AC-R01)."""
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(layers=["narrative", "plan", "page_copy"]))
    outcome = service.continue_project(project)
    assert outcome["status"] == "completed"
    assert outcome["completion"]["state"] == "completed"
    assert outcome["next_action"] == "return_requested_content"
    # The fixed manuscript is the requested output; stop without production.
    tasks = [store.read_object_json(ref) for ref in store.load_document()["tasks"]]
    assert not any(task["status"] in ("awaiting_host", "running") for task in tasks)


def test_continue_routes_when_the_request_covers_the_work(tmp_path):
    project, store = _project(tmp_path)
    from test_rc3_notes_visual_inputs import _seed_imported_plan
    _seed_imported_plan(store)
    _start(project, store)
    _settle_preproduction(store, seed="continue-routes")
    # Without the execute grant continue answers with a card (never a side
    # effect), and the card names the blocked dispatch.
    blocked = service.continue_project(project)
    assert blocked["status"] == "needs_input"
    assert blocked["eligibility"]["action"] == "dispatch.blueprint"
    assert blocked["eligibility"]["reason_codes"] == ["authority_insufficient"]
    _grant(project, store, actions=("dispatch.blueprint", "allowance.allocate"))
    outcome = service.continue_project(project)
    # With the binding writer in place (T03) the covered work dispatches: the
    # phased task goes out through the gated helper and carries its binding.
    assert outcome["status"] == "awaiting_host"
    dispatched = [store.read_object_json(ref) for ref in store.load_document()["tasks"]]
    pending = [task for task in dispatched if task.get("status") == "awaiting_host"]
    assert pending and pending[0].get("collaboration_binding")


def test_review_only_request_refuses_page_import_and_blueprint_dispatch(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="review_only", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["review"], purpose="review"))
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.import_draft(project, draft_payload={"pages": [_page("p1", "改稿。")]},
            base_revision=store.current_revision_id(), operation_id="refused-review-only-import")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    assert "review_only" in _blocked(excinfo)["message"]
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.open_blueprint_task(store, store.load_document(), entry)
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]


def test_blueprint_dispatch_requires_scope_and_authorization(tmp_path):
    project, store = _project(tmp_path)
    from test_rc3_notes_visual_inputs import _seed_imported_plan
    _seed_imported_plan(store)
    _start(project, store)
    _start(project, store, operation_id="op-narrow-blueprint", scope=_scope(page_ids=["p1"]))
    # RP14 freezes effective request requirements: review the narrowed scope.
    _settle_preproduction(store, seed="blueprint-scope")
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.open_blueprint_task(store, store.load_document(), entry)
    error = _blocked(excinfo)
    assert "authority_insufficient" in error["reason_codes"]
    assert "grant an execute authorization" in error["next_action"]
    assert error["responsible_role"] == "user"
    # With the execute grant the scope/authority gap is gone; the dispatch goes
    # out through the gated helper and carries its phase binding (T03), so the
    # task is accountable instead of stopping on a missing one.
    _grant(project, store, actions=("dispatch.blueprint", "allowance.allocate"))
    task = service.open_blueprint_task(store, store.load_document(), entry)
    assert task["collaboration_binding"]["phase"] == "production"
    assert task["scope_pages"] == ["p1"]
    assert task["status"] == "awaiting_host"


def test_blueprint_dispatch_outside_request_pages_is_refused(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    _grant(project, store, actions=("dispatch.blueprint", "allowance.allocate"),
           scope=_scope(page_ids=["p1"]))
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == "p2")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.open_blueprint_task(store, store.load_document(), entry)
    error = _blocked(excinfo)
    assert error["reason_codes"][0] == "scope_exceeded"
    detail = next(r for r in error["reasons"] if r["code"] == "scope_exceeded")
    assert detail["target_pages"] == ["p2"] and detail["authorized_pages"] == ["p1"]


def test_host_task_dispatch_consumes_the_request_scope(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    task = service.open_host_task(store, kind="review", page_ids=["p1"],
                                  instruction="review p1", review_stage="page_visual")
    assert task["scope_pages"] == ["p1"]
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.open_host_task(store, kind="review", page_ids=["p2"],
                               instruction="review p2", review_stage="page_visual")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]


def test_compose_dispatch_refused_while_paused(tmp_path):
    project, store = _project(tmp_path, pages=False)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(page_ids=[], layers=["narrative", "plan", "page_copy"]))
    collaboration.pause_request(project, reason="stop", base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.open_compose_task(store, store.load_document(), operation_id="op-compose")
    error = _blocked(excinfo)
    assert error["reason_codes"] == ["request_paused"]
    assert "resume" in error["next_action"]
    assert error["decision_card"]["kind"] == "stop_card"


# ---------------------------------------------------------------------------
# Execution and fees


def test_allowance_allocation_and_begin_require_the_execute_grant(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1")],
                 binding=_binding(document, authorization_ref=None))
    _commit_task(store, task)
    # The claim itself is checked against the live control: a paused request
    # stops new production, and the claim is production.
    collaboration.pause_request(project, reason="stop", base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.task_start(project, task_id="task-1", execution_ref="host-1")
    assert _blocked(excinfo)["reason_codes"] == ["request_paused"]
    collaboration.resume_request(project, instruction_evidence=_declared(store),
                                 base_revision=store.load_document()["revision_id"],
                                 operation_id="op-resume")
    started = service.task_start(project, task_id="task-1", execution_ref="host-1")
    assert started["status"] == "running"
    # The call slot needs the execute authorization naming the slot action.
    without_grant = eligibility.evaluate(store, store.load_document(),
                                         store.load_document(), "call.begin",
                                         {"task": task, "allowance_id": "call-1"})
    assert "authority_insufficient" in without_grant["reason_codes"]
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    allowed = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                   "call.begin", {"task": task, "allowance_id": "call-1"})
    assert allowed["allowed"] is True
    assert allowed["authority_assurance"] == "host_attested"
    assert grant["authorization_id"]
    begun = __import__("deck_master.tasks", fromlist=["call_begin"]).call_begin(
        Store(project), task_id="task-1", allowance_id="call-1", execution_ref="host-1")
    assert begun["status"] == "started"


def test_begin_after_withdrawal_is_refused_without_losing_the_slot(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    _commit_task(store, task)
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="withdraw", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.task_start(project, task_id="task-1", execution_ref="host-1")
    assert "authorization_revoked" in _blocked(excinfo)["reason_codes"]


def test_zero_image_scope_cannot_begin_a_call(tmp_path):
    """text-only / 严格只读 requests carry no image-call layer at all."""
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(page_ids=["p1"], layers=["narrative", "page_copy"]))
    _grant(project, store, actions=("call.begin",),
           scope=_scope(page_ids=["p1"], layers=["narrative", "page_copy"]))
    document = store.load_document()
    grant_ref = None
    task = _task(document, kind="blueprint", allowances=[_allowance("call-1")],
                 binding=_binding(document, authorization_ref=grant_ref))
    _commit_task(store, task)
    service.task_start(project, task_id="task-1", execution_ref="host-1")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        eligibility.guard(store, store.load_document(), "call.begin",
                          context={"task": task, "allowance_id": "call-1",
                                   "targets": {"page_ids": ["p1"], "layers": ["blueprint"]}})
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]


# ---------------------------------------------------------------------------
# Adoption: settle-then-refuse


def test_accept_refused_out_of_scope_settles_calls_and_keeps_the_draft(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1", "reserved")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    _commit_task(store, task)
    service.task_start(project, task_id="task-1", execution_ref="host-1")
    from deck_master import tasks as tasks_mod
    tasks_mod.call_begin(Store(project), task_id="task-1", allowance_id="call-1",
                         execution_ref="host-1")
    before_hash = _page_hash(store, "p1")
    before_pages = store.load_document()["pages"]
    # Stage the real execution evidence the settle protocol expects.
    staging = store.staging_dir / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "evidence.json").write_bytes(json.dumps({"call": "consumed"}).encode("utf-8"))
    envelope = {"kind": "compose", "files": [{"file_id": "ev1", "path": "evidence.json",
                                              "media_type": "application/json"}],
                "pages": [_page("p3", "越界页。")],
                "page_order": ["p3"], "artifact_specs": [], "reviews": [],
                "usage_events": [{"allowance_id": "call-1", "outcome": "consumed",
                                  "evidence_file_ids": ["ev1"]}],
                "notes": "late out-of-scope result"}
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        service.accept_result(project, task_id="task-1",
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload=envelope)
    error = _blocked(excinfo)
    assert error["reason_codes"][0] == "scope_exceeded"
    assert error["next_action"]
    # The draft kept its bytes and page set.
    assert _page_hash(store, "p1") == before_hash == "标题p1"
    assert store.load_document()["pages"] == before_pages
    # The call that happened is settled as a fact, not erased by the refusal.
    settled = service.task_status(project, task_id="task-1")
    allowance = settled["pending_tasks"][0]["call_allowances"][0]
    assert allowance["state"] == "consumed"


def test_accept_in_scope_composes_normally(tmp_path):
    # Generic compose returns the whole deck. Keep this positive fixture truly
    # single-page rather than silently dropping p2 from a two-page Plan.
    project = public_project(tmp_path, create_input={'brief': 'in-scope generic compose'},
        manuscript={'pages': [_page('p1', '第一页。')]})['project']
    store = Store(project)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, scope_pages=("p1",),
                 binding=_binding(document, authorization_ref=None))
    _commit_task(store, task)
    service.task_start(project, task_id="task-1", execution_ref="host-1")
    envelope = {"kind": "compose", "files": [], "pages": [_page("p1", "新的一句。")],
                "page_order": ["p1"], "artifact_specs": [], "reviews": [],
                "usage_events": [], "notes": "in-scope page copy"}
    outcome = service.accept_result(project, task_id="task-1",
                                    operation_id=task["operation_id"],
                                    produced_against=task["produced_against"],
                                    result_payload=envelope)
    assert outcome["status"] == "accepted"
    assert _page_hash(store, "p1") == "标题p1"
    page = store.read_object_json(next(e for e in store.load_document()["pages"]
                                       if e["page_id"] == "p1")["page"])
    assert page["customer_visible"]["body_blocks"][0]["text"] == "新的一句。"
    document = store.load_document()
    assert [e['page_id'] for e in document['pages']] == ['p1']
    assert document['pages'][0]['page'] in outcome['result_refs']
    assert document['content_plan'] in outcome['result_refs']
    assert store.read_object_json(document['content_plan'])['page_links'][0]['page_ref'] == document['pages'][0]['page']
    from deck_master.content_plan import projection
    assert projection(store, document)['applicability'] == 'current'


def test_p1_only_generic_compose_cannot_silently_drop_p2_from_existing_plan(tmp_path):
    """The original two-page positive fixture now explicitly proves refusal.

    A Page-only return cannot revise the existing v2 Plan's membership/order.
    """
    from deck_master.content_plan import ContentPlanError
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=['p1']))
    document = store.load_document()
    task = _task(document, scope_pages=('p1',), binding=_binding(document, authorization_ref=None))
    _commit_task(store, task)
    service.task_start(project, task_id='task-1', execution_ref='host-1')
    before = store.load_document()
    page_bytes = [store.read_object_bytes(e['page']) for e in before['pages']]
    pointer = (store.deck_root / 'current.json').read_bytes()
    envelope = {'kind': 'compose', 'files': [], 'pages': [_page('p1', '新的一句。')],
                'page_order': ['p1'], 'artifact_specs': [], 'reviews': [],
                'usage_events': [], 'notes': 'in-scope page copy'}
    with pytest.raises(ContentPlanError, match='membership and order'):
        service.accept_result(project, task_id='task-1', operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload=envelope)
    after = store.load_document()
    assert after == before  # P2, notes, order, Narrative, outputs and every current Ref.
    assert [e['page_id'] for e in after['pages']] == ['p1', 'p2']
    assert [store.read_object_bytes(e['page']) for e in after['pages']] == page_bytes
    assert (store.deck_root / 'current.json').read_bytes() == pointer


# ---------------------------------------------------------------------------
# Change / candidates / design / content operations


def test_change_commit_refuses_pages_outside_the_request(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _start(project, store, operation_id="op-narrow-change", scope=_scope(page_ids=["p1"]))
    # RP14 freezes effective request requirements: review the narrowed scope.
    _settle_preproduction(store, seed="change-scope")
    _grant(project, store, actions=("change.commit",), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p2")
    plan = changes_plan(project, input={
        "schema_version": "change_intent.v1", "project_id": document["project_id"],
        "base_revision": document["revision_id"], "instruction": "改 P2",
        "intent": "content", "targets": [{"page_id": "p2", "layer": "content",
                                           "page_ref": entry["page"],
                                           "artifact_ref": entry["page"]}],
        "max_calls": 0, "annotation_refs": []})
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        store_objects = store
        from deck_master import changes
        changes.commit(project, plan_id=plan["plan_id"],
                       base_revision=store_objects.load_document()["revision_id"],
                       operation_id="6f1b1f2a-2222-4222-8222-222222222222")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    # The same plan for an authorized page commits.
    plan = changes_plan(project, input={
        "schema_version": "change_intent.v1", "project_id": document["project_id"],
        "base_revision": store.load_document()["revision_id"], "instruction": "改 P1",
        "intent": "content", "targets": [{"page_id": "p1", "layer": "content",
                                           "page_ref": next(e for e in store.load_document()["pages"]
                                                            if e["page_id"] == "p1")["page"],
                                           "artifact_ref": next(e for e in store.load_document()["pages"]
                                                                if e["page_id"] == "p1")["page"]}],
        "max_calls": 0, "annotation_refs": []})
    from deck_master import changes
    outcome = changes.commit(project, plan_id=plan["plan_id"],
                             base_revision=store.load_document()["revision_id"],
                             operation_id="6f1b1f2a-3333-4333-8333-333333333333")
    assert outcome["status"] in ("awaiting_host", "committed")
    assert outcome["operation_result"]["task_ids"], outcome


def test_style_proposal_and_design_confirmation_consume_the_gate(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="review_only", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["review"], purpose="review"))
    from deck_master import styles
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        styles.propose(project, input={
            "schema_version": "style_input.v1", "project_id": store.load_document()["project_id"],
            "base_revision": store.load_document()["revision_id"],
            "instruction": "试一版更克制的配色", "targets": []})
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    # With a request that reaches the design layer the same call passes the
    # gate and fails later on the real prerequisite (a reference blueprint),
    # never on an admission refusal.
    _start(project, store, operation_id="op-start-2", intent="full_deck",
           replace_request_id=store.load_document()["collaboration"]["request"]["request_id"])
    _grant(project, store, actions=("style.propose",), scope=_scope(page_ids=["p1"]),
           operation_id="op-grant-style")
    with pytest.raises(Exception) as excinfo:
        styles.propose(project, input={
            "schema_version": "style_input.v1",
            "project_id": store.load_document()["project_id"],
            "base_revision": store.load_document()["revision_id"],
            "instruction": "试一版更克制的配色", "target_page_ids": ["p1"]})
    assert not isinstance(excinfo.value, eligibility.EligibilityBlocked)


def test_content_operation_requires_the_direction_decision(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    _grant(project, store, actions=("content.operation",), scope=_scope(page_ids=["p1"]))
    from deck_master import content_ops
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    planned = content_ops.plan(project, input={
        "schema_version": "content_operation_input.v1", "project_id": document["project_id"],
        "base_revision": document["revision_id"], "content_plan_ref": document["content_plan"],
        "action": "edit", "targets": [{"page_id": "p1", "page_ref": entry["page"]}],
        "instruction": "改一句上屏文案",
        "customer_visible": {"title": "标题p1", "body_blocks": [
            {"id": "b1", "type": "paragraph", "text": "改写后的句子。"}]}})
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        content_ops.commit(project, plan_id=planned["plan_id"],
                           base_revision=store.load_document()["revision_id"],
                           operation_id="7a1b1f2a-1111-4111-8111-111111111111")
    error = _blocked(excinfo)
    assert error["reason_codes"] == ["decision_needed"]
    assert error["decision_card"]["topics"] == ["direction"]


def test_candidate_adoption_refused_after_withdrawal(tmp_path):
    """A real candidate adoption: the trial is dispatched and accepted through
    the real entries (binding stamped as the post-integration state), the plan
    is adoptable while the adoption authorization is effective, and the
    withdrawal refuses the very same adoption with the draft untouched."""
    from deck_master.samples import create_sample
    from candidate_fixtures import accept as trial_accept, dispatch as trial_dispatch, \
        plan as candidate_plan, start as trial_start, adopt as candidate_adopt
    project = tmp_path / "candidate-project"
    create_sample(project, page_count=2, readonly=False)
    store = Store(project)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "bootstrap-collaboration",
                                      "kind": "collaboration_update",
                                      "description": "bootstrap region", "read_set": []})
    bumped["collaboration"] = {
        "schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "fidelity_only",
                            "requirement_origin": "confirmed_manuscript",
                            "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": []}
    require_writer(bumped, "collaboration.v1")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="bootstrap-collaboration")
    scope = _scope(page_ids=["p01", "p02"])
    _start(project, store, scope=scope)
    _settle_preproduction(store, seed="candidate-withdrawal")
    _grant(project, store, actions=("change.commit",), scope=scope,
           operation_id="op-grant-change")
    task = trial_dispatch(store)                       # real change-plan dispatch
    _stamp_binding(store, task["task_id"])             # T03's stamp (simulated)
    trial_start(store, task)
    result = trial_accept(store, task)
    candidate_id = result["candidate_ids"][0]
    adoption_grant = _grant(project, store, actions=("candidate.adopt",), scope=scope,
                            max_external_calls=0, operation_id="op-grant-adopt")
    planned = candidate_plan(store, [candidate_id])
    targets = {"page_ids": [planned["selections"][0]["page_id"]], "layers": ["svg"]}
    before = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                  "candidate.adopt", {"targets": targets})
    assert before["allowed"] is True, before["reason_codes"]
    collaboration.revoke_authorization(
        project, authorization_id=adoption_grant["authorization_id"], reason="撤回采用",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke")
    after = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                 "candidate.adopt", {"targets": targets})
    assert after["allowed"] is False
    assert "authorization_revoked" in after["reason_codes"]
    pages_before = canonical_json_bytes(store.load_document()["pages"])
    selections_before = list(store.load_document().get("candidate_adoptions") or [])
    # Re-reading the current state after the revocation produces a fresh plan
    # (the CAS conflict is the concurrency rule, not an admission gap) — and the
    # adoption itself is then refused by the withdrawal.
    replanned = candidate_plan(store, [candidate_id])
    assert replanned["base_revision"] != planned["base_revision"]
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        candidate_adopt(store, replanned)
    assert "authorization_revoked" in _blocked(excinfo)["reason_codes"]
    assert "withdrawal stands" in _blocked(excinfo)["next_action"]
    assert canonical_json_bytes(store.load_document()["pages"]) == pages_before
    assert list(store.load_document().get("candidate_adoptions") or []) == selections_before


# ---------------------------------------------------------------------------
# Local production and delivery


def test_local_compile_needs_the_output_layer_in_scope(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(page_ids=["p1", "p2"], layers=["narrative", "page_copy"]))
    from deck_master import pipeline
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        pipeline.produce(project)
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    # With the output layer in scope the gate passes; the next error is the
    # real production prerequisite (no SVG/preview yet), not an admission gap.
    _start(project, store, operation_id="op-start-2", intent="full_deck",
           replace_request_id=store.load_document()["collaboration"]["request"]["request_id"],
           scope=_scope(page_ids=["p1", "p2"]))
    _settle_preproduction(store, seed="local-compile")
    with pytest.raises(Exception) as excinfo:
        pipeline.produce(project)
    assert not isinstance(excinfo.value, eligibility.EligibilityBlocked)


def test_preview_render_needs_the_svg_layer(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(page_ids=["p1"], layers=["narrative", "page_copy"]))
    from deck_master import pipeline
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        pipeline.preview_svg_page(project, "p1")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]


def test_local_rendering_entries_use_the_same_layer_strictness(tmp_path):
    """P3 regression: every local rendering entry derives the svg layer, so a
    request without it refuses the render — no entry may silently pass."""
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(page_ids=["p1"], layers=["narrative", "page_copy"]))
    for action in ("render.preview", "compile.svg"):
        decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                        action, {"targets": {"page_ids": ["p1"]}})
        assert "scope_exceeded" in decision["reason_codes"], action
    # Both local rendering entries consume that same action with an svg target.
    from deck_master import candidate_preview, icons
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        candidate_preview.request(project, candidate_id="cand-does-not-exist")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        icons.preview(project, proposal_id="proposal-missing", page_id="p1")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    # With the svg layer in scope both entries pass the gate and fail later on
    # their real prerequisite (a missing candidate/proposal), not on admission.
    _start(project, store, operation_id="op-start-2", intent="full_deck",
           replace_request_id=store.load_document()["collaboration"]["request"]["request_id"],
           scope=_scope(page_ids=["p1"]))
    with pytest.raises(Exception) as excinfo:
        candidate_preview.request(project, candidate_id="cand-does-not-exist")
    assert not isinstance(excinfo.value, eligibility.EligibilityBlocked)


def test_restore_requires_migration_and_current_scope(tmp_path):
    """Restore recovers historical facts under migrated current control.

    Historical writes and persistence=none remain refused through the gate.
    """
    from deck_master import eligibility_entries as entries
    row = entries.classify("operations", "restoration.commit")
    assert row.action == "restore" and row.exempt is None
    project, store = _project(tmp_path, region=False)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "older-revision",
                                      "kind": "task_update",
                                      "description": "older revision", "read_set": []})
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="older-revision")
    older = store.load_document()["revision_id"]
    from deck_master.editing import restore
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        restore(project, revision_id=older, base_revision=store.current_revision_id(),
                operation_id="op-restore-before-migration")
    assert "migration_required" in _blocked(excinfo)["reason_codes"]
    from deck_master import collaboration_migration
    described = collaboration_migration.describe(project)
    collaboration_migration.apply(project, base_revision=store.current_revision_id(),
        plan_digest=described["plan_digest"], operation_id="op-restore-migrate")
    _start(project, store, intent="content_only", content_intent="write_only",
           scope=_scope(layers=["page_copy"]))
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        restore(project, revision_id=older, base_revision=before["revision_id"],
                operation_id="op-restore-outside-scope")
    assert "scope_exceeded" in _blocked(excinfo)["reason_codes"]
    assert store.load_document() == before
    _start(project, store, operation_id="op-restore-current-scope",
           intent="content_only", content_intent="write_only",
           scope=_scope(layers=["narrative", "plan", "page_copy", "speech"]))
    outcome = restore(project, revision_id=older,
                      base_revision=store.load_document()["revision_id"],
                      operation_id="op-restore-report")
    assert outcome["status"] in ("edited", "restored")
    # A strict read-only declaration is still refused through the same path.
    decision = eligibility.evaluate(store, store.load_document(), store.load_document(),
                                    "restore", {"persistence": "none"})
    assert "persistence_none" in decision["reason_codes"]


def test_delivery_export_consumes_the_professional_policy(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1", "p2"],
                                        layers=["output"], purpose="delivery"))
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "policy-op", "kind": "policy_update",
                                      "description": "require human review", "read_set": []})
    bumped["policy"] = {**document["policy"], "professional_review_required_for_delivery": True}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="policy-op")
    _grant(project, store, actions=("export.delivery",),
           scope=_scope(subject="deck", page_ids=["p1", "p2"], layers=["output"],
                        purpose="delivery"),
           delivery_binding="process_delegation")
    from deck_master import exports
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        exports.create(project, purpose="delivery", output_dir=tmp_path / "out")
    error = _blocked(excinfo)
    assert "professional_review_required" in error["reason_codes"]
    assert "verified human professional review" in error["next_action"]
    # Review copies stay exportable: the gate is delivery-only.
    outcome = exports.create(project, purpose="review", output_dir=tmp_path / "out-review")
    assert outcome["status"] == "exported"


def test_handoff_delivery_consumes_the_professional_policy(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1"], layers=["output"],
                                        purpose="delivery"))
    from deck_master import handoff
    candidate = tmp_path / "handoff.pptx"
    candidate.write_bytes(b"pptx-bytes")
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        handoff.check_handoff(project, file_path=candidate, purpose="delivery")
    error = _blocked(excinfo)
    assert "decision_needed" in error["reason_codes"]
    assert error["decision_card"]["kind"] in ("decision_card", "delivery_card")
    # A review-purpose check of the same file stays a report, not a refusal.
    report = handoff.check_handoff(project, file_path=candidate, purpose="review")
    assert report["status"] in ("pass", "fail", "blocked")  # a report, not a refusal


def test_restore_is_not_refused_by_the_current_stop(tmp_path):
    """restore recovers content facts; the withdrawal/pause stays in force."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1", "p2"]))
    from deck_master.editing import edit_page, restore
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    target = document["revision_id"]
    edit_page(project, page=_page("p1", "改过的句子。"), base_revision=document["revision_id"],
              page_hash=entry["page"]["sha256"], operation_id="op-edit")
    collaboration.pause_request(project, reason="等确认",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    outcome = restore(project, revision_id=target,
                      base_revision=store.load_document()["revision_id"],
                      operation_id="op-restore")
    assert outcome["status"] in ("edited", "restored")
    after = store.load_document()
    assert after["collaboration"]["request"]["paused"] is True
    assert after["compatibility"]["minimum_writer"] == "rc3-entry.v1"


def test_control_plane_writes_still_record_while_paused(tmp_path):
    """A decision/grant must remain recordable while the request is paused
    (CONTRACTS §7.1 stops production, not the control plane)."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    collaboration.pause_request(project, reason="等确认",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]),
                   operation_id="op-grant-paused")
    assert grant["status"] == "accepted"
    recorded = collaboration.record_decision(
        project, input={"topic": "direction", "subject_refs": [], "value": "keep",
                        "disposition": "accepted", "authority_mode": "direct_user",
                        "scope": _scope(page_ids=["p1"]),
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-decision-paused")
    assert recorded["status"] == "accepted"
    # And the production boundary stays shut.
    with pytest.raises(eligibility.EligibilityBlocked):
        service.open_blueprint_task(store, store.load_document(),
                                    next(e for e in store.load_document()["pages"]
                                         if e["page_id"] == "p1"))


def test_migration_apply_is_never_refused_by_the_gate(tmp_path):
    project, store = _project(tmp_path, region=False)
    from deck_master import collaboration_migration
    described = collaboration_migration.describe(project)
    outcome = collaboration_migration.apply(project, base_revision=store.load_document()["revision_id"],
                                            plan_digest=described["plan_digest"],
                                            operation_id="op-migrate")
    assert outcome["status"] == "accepted"
    assert store.load_document()["compatibility"]["minimum_writer"] == "rc3-entry.v1"


def test_legacy_readers_and_settlement_survive_but_new_production_requires_migration(tmp_path):
    project, store = _project(tmp_path, region=False)
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as exc:
        service.open_blueprint_task(store, before, entry)
    assert "migration_required" in exc.value.decision["reason_codes"]
    assert store.load_document() == before
    assert service.continue_project(project)["next_action"] == "describe_and_apply_migration"


def test_blocked_actions_never_write(tmp_path):
    """A refused boundary leaves the document byte-identical apart from nothing:
    no task, no allowance, no decision object."""
    project, store = _project(tmp_path)
    _start(project, store, intent="review_only", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["review"], purpose="review"))
    before = store.load_document()
    before_hash = sha256_bytes(canonical_json_bytes(before))
    entry = next(e for e in before["pages"] if e["page_id"] == "p1")
    with pytest.raises(eligibility.EligibilityBlocked):
        service.open_blueprint_task(store, store.load_document(), entry)
    with pytest.raises(eligibility.EligibilityBlocked):
        service.update_design(project, design_context=before["design_context"])
    after = store.load_document()
    assert sha256_bytes(canonical_json_bytes(after)) == before_hash
    assert after == before
