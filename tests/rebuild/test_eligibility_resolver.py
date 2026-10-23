"""T04 slice 1: the pure eligibility resolver (AC-R01/R04 foundations).

Every registered reason code gets at least one counterexample (the code
appears, with a concrete gap and next action) and one positive case (the code
does not appear and the action is allowed). The resolver must be side-effect
free, and historical artifact snapshots must be judged against the *current*
control (CONTRACTS §6/§7/§8).
"""
import hashlib

import pytest

from rc3_fixtures import historical_snapshot

from test_eligibility_enforcement import _settle_preproduction  # noqa: E402  (shared fixture)

from deck_master import collaboration, eligibility, service
from deck_master.models import (bump_revision, canonical_json_bytes,
                                content_identity, require_writer, sha256_bytes)
from deck_master.store import Store


# ---------------------------------------------------------------------------
# Fixtures and helpers


def _ref(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _stored_ref(store, seed: str) -> dict:
    return store.put_json_object({"fixture": seed})


def _declared(store, kind: str = "host_attested_instruction", **over) -> dict:
    evidence = {"kind": kind, "source_ref": _stored_ref(store, "source"),
                "source_locator": "chat:msg-1", "actor_id": None,
                "transport_receipt_ref": None, "presentation_ref": None}
    evidence.update(over)
    return evidence


def _scope(**over) -> dict:
    scope = {"subject": "pages", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["page_copy"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "exploratory"}
    scope.update(over)
    return scope


def _page(pid: str, text: str) -> dict:
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": f"标题{pid}", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": text}]},
            "visual_spec": {"intent": "synthetic", "reference_mode": "new_design"}}


def _project(tmp_path, *, region=True, policy=None, pages=False):
    """A collaboration.v1 project: service.create then the region bootstrap that
    T02's migration apply performs (no production runs yet)."""
    project = tmp_path / "proj"
    if region:
        service.create(project, brief="eligibility resolver",
                       draft={"pages": [_page("p1", "第一页。"), _page("p2", "第二页。")]}
                       if pages else None)
    else:
        project = historical_snapshot(tmp_path, scenario="fixed unmigrated gate trajectory",
            pages=[_page("p1", "第一页。"), _page("p2", "第二页。")] if pages else [])['project']
    store = Store(project)
    if policy:
        _set_policy(store, policy)
    if region:
        document = store.load_document()
        bumped = bump_revision(document, {"operation_id": "bootstrap-collaboration",
                                          "kind": "collaboration_update",
                                          "description": "bootstrap region", "read_set": []})
        bumped["collaboration"] = {
            "schema_version": "collaboration.v1",
            "authority_policy": "traceable",
            "quality_profile": {"content_review_requirement": "fidelity_only",
                                "requirement_origin": "confirmed_manuscript",
                                "override_decision_ref": None},
            "request": None, "decisions": [], "authorizations": [],
        }
        require_writer(bumped, "collaboration.v1")
        store.commit_change(base_revision=document["revision_id"], document=bumped,
                            operation_id="bootstrap-collaboration")
    return project, Store(project)


def _set_policy(store, over):
    import uuid
    operation_id = f"policy-{uuid.uuid4().hex[:10]}"
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "policy_update",
                                      "description": "test policy", "read_set": []})
    bumped["policy"] = {**document["policy"], **over}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return bumped


def _set_quality_profile(store, **over):
    import uuid
    operation_id = f"quality-{uuid.uuid4().hex[:10]}"
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": operation_id,
                                      "kind": "collaboration_update",
                                      "description": "test quality profile", "read_set": []})
    bumped["collaboration"] = {**document["collaboration"],
                               "quality_profile": {**document["collaboration"]["quality_profile"],
                                                   **over}}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return bumped


_FULL_LAYERS = ["narrative", "plan", "page_copy", "speech", "design", "blueprint",
                "svg", "review", "output"]


def _start(project, store, *, operation_id="op-start-1", intent="full_deck",
           content_intent=None, scope=None, **extra):
    payload = {"intent": intent, "content_intent": content_intent,
               "instruction_evidence": _declared(store),
               "scope": scope or _scope(page_ids=["p1", "p2"], layers=list(_FULL_LAYERS)),
               "replace_request_id": extra.pop("replace_request_id", None)}
    payload.update(extra)
    return collaboration.start_request(project, input=payload,
                                       base_revision=store.load_document()["revision_id"],
                                       operation_id=operation_id)


def _decision(project, store, *, topic="manuscript", value="confirmed draft",
              operation_id="op-decision-1", scope=None, disposition="accepted",
              authority_mode="direct_user"):
    return collaboration.record_decision(
        project, input={"topic": topic, "subject_refs": [], "value": value,
                        "disposition": disposition, "authority_mode": authority_mode,
                        "scope": scope or _scope(page_ids=["p1", "p2"],
                                                 layers=list(_FULL_LAYERS)),
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id=operation_id)


def _grant(project, store, *, mode="execute", actions=("call.begin",), scope=None,
           operation_id="op-grant-1", max_external_calls=2, decision_refs=(),
           delegated_topics=(), authorization_id=None, budget_key=None, **extra):
    payload = {"mode": mode, "actions": list(actions),
               "scope": scope or _scope(page_ids=["p1", "p2"], layers=list(_FULL_LAYERS)),
               "decision_refs": list(decision_refs),
               "delegated_topics": list(delegated_topics),
               "max_external_calls": max_external_calls,
               "max_candidate_count": 1,
               "instruction_evidence": _declared(store)}
    if authorization_id:
        payload["authorization_id"] = authorization_id
    if budget_key:
        payload["budget_key"] = budget_key
    payload.update(extra)
    return collaboration.grant(project, input=payload,
                               base_revision=store.load_document()["revision_id"],
                               operation_id=operation_id)


def _task(document, *, allowances=None, binding=None, **over):
    task = {"schema_version": "deck_task.v1", "task_id": "task-1", "operation_id": "op-task-1",
            "kind": "blueprint", "status": "running", "scope_pages": ["p1"],
            "instruction": "generate", "inputs": [], "dependencies": [],
            "dispatch_revision": document["revision_id"],
            "produced_against": content_identity(document), "result_refs": [],
            "error": None, "execution_ref": "host-1", "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "cost_class": "external_generation",
            "usage": {"source": "not_reported", "external_calls": None},
            "call_allowances": list(allowances or [])}
    task.update(over)
    if binding is not None:
        task["collaboration_binding"] = binding
    return task


def _binding(document, *, phase="production", scope=None, authorization_ref=None,
             budget_key=None, basis=None, request_id=None, digest=None):
    scope = scope or _scope(page_ids=["p1"])
    basis = list(basis or [])
    binding = {"request_id": request_id or document["collaboration"]["request"]["request_id"],
               "phase": phase, "executor_type": "host",
               "authorization_ref": authorization_ref, "decision_refs": [],
               "write_scope": scope, "adoption_policy": "candidate_only",
               "eligibility_basis": basis}
    if budget_key:
        binding["budget_key"] = budget_key
    binding["eligibility_digest"] = digest or eligibility.binding_eligibility_digest(
        phase, scope, basis)
    return binding


def _allowance(allowance_id="call-1", state="reserved"):
    return {"allowance_id": allowance_id, "state": state, "execution_ref": "host-1",
            "invocation_ref": None, "evidence": []}


def _commit_task(store, task, *, operation_id=None):
    """Commit a task dict into the document so the ledger sees its allowances."""
    import uuid
    operation_id = operation_id or f"task-commit-{uuid.uuid4().hex[:10]}"
    document = store.load_document()
    ref = store.put_json_object(task)
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update",
                                      "description": "test task", "read_set": []})
    bumped["tasks"] = [*(document.get("tasks") or []), ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return ref


def _fingerprint(store):
    """Everything a pure resolver must not touch."""
    document = store.load_document()
    tasks = [store.read_object_json(ref) for ref in document.get("tasks") or []]
    objects = sorted(str(path.relative_to(store.project_root))
                     for path in store.objects_dir.rglob("*") if path.is_file())
    return {
        "document": sha256_bytes(canonical_json_bytes(document)),
        "revision": document["revision_id"],
        "tasks": [(task.get("task_id"), task.get("status"),
                   sha256_bytes(canonical_json_bytes(task.get("call_allowances") or [])))
                  for task in tasks],
        "objects": objects,
        "current": (store.deck_root / "current.json").read_bytes(),
    }


def _evaluate(store, action, *, targets=None, task=None, context=None, artifact=None, control=None):
    context = dict(context or {})
    if targets is not None:
        context["targets"] = targets
    if task is not None:
        context["task"] = task
    document = control if control is not None else store.load_document()
    return eligibility.evaluate(store, artifact if artifact is not None else document,
                                document, action, context)


# ---------------------------------------------------------------------------
# Catalog and vocabulary


def test_action_catalog_covers_every_contract_boundary():
    for action in ("create", "import_draft", "continue_project", "dispatch.compose",
                   "dispatch.host_task", "dispatch.blueprint", "task.start",
                   "allowance.allocate", "allowance.repair", "call.begin", "task.accept",
                   "page.edit", "asset.import", "design.update", "change.commit",
                   "candidate.select", "candidate.adopt", "style.trial", "style.expand",
                   "content.operation", "compile.svg", "render.preview", "compile.ppt",
                   "compile.repair", "export.delivery", "handoff.delivery",
                   "readiness.final", "restore", "policy.update", "authority.update",
                   "delivery.historical"):
        assert action in eligibility.ACTIONS, action
    minimum = {"request_paused", "scope_exceeded", "decision_needed",
               "authority_insufficient", "authority_channel_unavailable", "basis_stale",
               "authorization_revoked", "budget_exhausted", "input_reconciliation_pending",
               "professional_review_required", "migration_required", "needs_reviewer"}
    assert minimum <= set(eligibility.REASON_ORDER)
    assert set(eligibility.EXTRA_REASON_CODES) <= set(eligibility.REASON_ORDER)
    for code in eligibility.REASON_ORDER:
        assert eligibility.REASON_MEANINGS.get(code), code


def test_unknown_action_is_refused():
    with pytest.raises(Exception, match="unregistered action"):
        eligibility.action_spec("nonsense.action")


# ---------------------------------------------------------------------------
# Purity


def test_evaluate_is_side_effect_free(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    before = _fingerprint(store)
    document = store.load_document()
    for action, context in (
            ("call.begin", {}),
            ("dispatch.blueprint", {}),
            ("export.delivery", {}),
            ("task.accept", {}),
            ("restore", {}),
            ("allowance.allocate", {}),
            ("style.expand", {})):
        eligibility.evaluate(store, document, document, action, context)
    assert _fingerprint(store) == before
    # A blocked action never creates a decision card object, task or allowance.
    decision = _evaluate(store, "style.expand")
    assert decision["reason_codes"] and decision["decision_card_ref_or_projection"] is not None
    assert _fingerprint(store) == before


def test_guard_refuses_legacy_new_writes_but_keeps_readers(tmp_path):
    project, store = _project(tmp_path, region=False)
    document = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as exc:
        eligibility.guard(store, document, "call.begin")
    assert exc.value.decision["enforcement"] == "active"
    assert "migration_required" in exc.value.decision["reason_codes"]
    assert eligibility.guard(store, document, "export.review")["allowed"] is True


def test_guard_raises_the_mapped_admission_error(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        eligibility.guard(store, document, "style.expand",
                          context={"targets": {"page_ids": ["p2"], "layers": ["design"]}})
    error = excinfo.value
    assert error.exit_code == 4 and error.http_status == 409
    assert error.error_code in ("scope_exceeded", "authority_insufficient")
    payload = error.payload()["error"]
    assert payload["reason_codes"] and payload["next_action"]
    assert payload["responsible_role"] in ("user", "runtime", "host", "reviewer", "operator")


# ---------------------------------------------------------------------------
# Request state: closed / paused / intent boundary


def test_request_paused_blocks_production_but_not_reads(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store)
    collaboration.pause_request(project, reason="stop for now",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    blocked = _evaluate(store, "call.begin")
    assert "request_paused" in blocked["reason_codes"]
    assert blocked["responsible_role"] == "user"
    assert "resume" in blocked["next_action"]
    # Reads, display and analysis stay available (§7.1); adopting production
    # results does not ("不再派发/开始/采用其生产任务").
    for action in ("continue_project", "change.plan", "export.review", "review.strict"):
        assert _evaluate(store, action)["reason_codes"] == [], action
    for action in ("task.accept", "allowance.allocate", "dispatch.compose"):
        assert "request_paused" in _evaluate(store, action)["reason_codes"], action
    collaboration.resume_request(project, instruction_evidence=_declared(store),
                                 base_revision=store.load_document()["revision_id"],
                                 operation_id="op-resume")
    allowed = _evaluate(store, "call.begin")
    assert allowed["allowed"] is True and allowed["reason_codes"] == []


def test_request_closed_blocks_production(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "close-op", "kind": "collaboration_update",
                                      "description": "close request", "read_set": []})
    request = {**document["collaboration"]["request"], "closed": True,
               "closed_reason": "completed"}
    bumped["collaboration"] = {**document["collaboration"], "request": request}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="close-op")
    blocked = _evaluate(store, "dispatch.compose")
    assert "request_closed" in blocked["reason_codes"]
    assert "new work request" in blocked["next_action"]
    # A fresh request re-opens production.
    _start(project, store, operation_id="op-start-2", intent="content_only",
           content_intent="plan_only",
           scope=_scope(page_ids=["p1", "p2"], layers=list(_FULL_LAYERS)))
    assert _evaluate(store, "dispatch.compose")["reason_codes"] == []


def test_review_only_never_produces(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="review_only", content_intent=None,
           scope=_scope(page_ids=["p1"], layers=["review"], purpose="review"))
    decision = _evaluate(store, "page.edit", targets={"page_ids": ["p1"], "layers": ["page_copy"]})
    assert "scope_exceeded" in decision["reason_codes"]
    assert "review_only" in decision["reasons"][0]["detail"]
    # Registering the review record itself is exactly what review_only may do.
    assert _evaluate(store, "review.record",
                     targets={"page_ids": [], "layers": ["review"]})["allowed"] is True


def test_plan_only_stops_before_image_production(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="content_only", content_intent="plan_only",
           scope=_scope(page_ids=["p1", "p2"], layers=["narrative", "plan"]))
    decision = _evaluate(store, "style.trial", targets={"page_ids": ["p1"], "layers": ["design"]})
    assert "scope_exceeded" in decision["reason_codes"]
    assert "plan_only" in decision["reasons"][0]["detail"]
    # Planning itself stays reachable.
    assert "scope_exceeded" not in _evaluate(
        store, "dispatch.compose", targets={"page_ids": [], "layers": ["plan"]})["reason_codes"]


# ---------------------------------------------------------------------------
# Scope


def test_scope_exceeded_outside_request_pages(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    blocked = _evaluate(store, "task.accept", targets={"page_ids": ["p2"]})
    assert "scope_exceeded" in blocked["reason_codes"]
    detail = next(r for r in blocked["reasons"] if r["code"] == "scope_exceeded")
    assert detail["target_pages"] == ["p2"] and detail["authorized_pages"] == ["p1"]
    assert "narrow" in blocked["next_action"]
    allowed = _evaluate(store, "task.accept", targets={"page_ids": ["p1"]})
    assert "scope_exceeded" not in allowed["reason_codes"]


def test_empty_page_set_is_never_all_pages(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=[]))
    blocked = _evaluate(store, "task.accept", targets={"page_ids": ["p1"]})
    assert "scope_exceeded" in blocked["reason_codes"]


def test_page_manifest_fixes_the_authorized_page_set(tmp_path):
    project, store = _project(tmp_path)
    document = store.load_document()
    plan = {"schema_version": "content_plan.v2", "plan_id": "plan-1", "version": 1,
            "project_id": document["project_id"], "task_id": "t", "origin": "host_composed",
            "basis": {"revision_id": "plan-basis-1", "input_digest": "0" * 64},
            "previous_ref": None, "mode": "planned", "narrative_ref": None,
            "imported_manuscript": None,
            "input": {"schema_version": "content_plan_input.v2", "chapters": [
                          {"chapter_id": "c1", "title": "L1 fixed page manifest", "page_ids": ["p1", "p2"]}],
                      "page_order": ["p1", "p2"], "page_roles": [
                          {"page_id": "p1", "role": "opening", "audience_question": "q",
                           "intended_takeaway": "t", "narrative_node_ids": [],
                           "source_links": [], "required_qualifications": [],
                           "content_profile": "simple", "density_rationale": "r",
                           "timing_seconds": None, "transition_to_next": None},
                          {"page_id": "p2", "role": "detail", "audience_question": "q",
                           "intended_takeaway": "t", "narrative_node_ids": [],
                           "source_links": [], "required_qualifications": [],
                           "content_profile": "simple", "density_rationale": "r",
                           "timing_seconds": None, "transition_to_next": None}],
                      "page_budget": {"exact": 2, "target": None, "max": None},
                      "time_budget": {"total_seconds": None, "speaking_seconds": None,
                                      "interaction_seconds": None, "constraint": "unspecified"},
                      "speech_policy": {"mode": "none", "source": "default", "output": "none"},
                      "issues": [], "tradeoff_issue_ids": []},
            "page_links": []}
    plan_ref = store.put_json_object(plan)
    _start(project, store, scope=_scope(subject="deck", page_ids=[],
                                        page_manifest_ref=plan_ref))
    assert _evaluate(store, "task.accept", targets={"page_ids": ["p2"]})["allowed"] is True
    assert "scope_exceeded" in _evaluate(
        store, "task.accept", targets={"page_ids": ["p3"]})["reason_codes"]


# ---------------------------------------------------------------------------
# Decisions


def test_decision_needed_then_satisfied_by_an_accepted_decision(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    blocked = _evaluate(store, "policy.update")
    assert blocked["reason_codes"] == ["decision_needed"]
    assert blocked["missing_decision_topics"] == ["policy"]
    card = blocked["decision_card_ref_or_projection"]
    assert card["topics"] == ["policy"] and card["projection"] == "policy"
    assert "record an accepted decision" in blocked["next_action"]
    _decision(project, store, topic="policy", value="keep traceable policy")
    allowed = _evaluate(store, "policy.update")
    assert allowed["allowed"] is True and allowed["missing_decision_topics"] == []


def test_rejected_decision_is_reusable_but_never_satisfies(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _decision(project, store, topic="policy", disposition="rejected")
    blocked = _evaluate(store, "policy.update")
    assert "decision_needed" in blocked["reason_codes"]
    # The rejection is a fact the card route must reuse, not re-ask: the
    # resolver reports the missing decision, never a fresh confirmation loop.
    assert blocked["decision_card_ref_or_projection"]["topics"] == ["policy"]


def test_basis_stale_when_the_accepted_decision_basis_moved(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store, actions=("content.operation",))
    _decision(project, store, topic="direction", value="keep the mainline")
    targets = {"page_ids": ["p1"], "layers": ["page_copy"]}
    assert _evaluate(store, "content.operation", targets=targets)["allowed"] is True
    service.inputs_update(project, patch={"reason": "new audience",
                                          "task_patch": {"audience": "主管阅读"}},
                          base_revision=store.load_document()["revision_id"],
                          operation_id="op-input-audience")
    blocked = _evaluate(store, "content.operation", targets=targets)
    assert "basis_stale" in blocked["reason_codes"]
    assert "re-record" in blocked["next_action"].lower()


def test_delegate_covering_the_topic_satisfies_the_decision(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store, mode="delegate", actions=("import_draft",),
           delegated_topics=("manuscript",), max_external_calls=0,
           operation_id="op-delegate")
    decision = _evaluate(store, "import_draft", targets={"page_ids": ["p1"],
                                                         "layers": ["page_copy"]})
    assert decision["allowed"] is True


# ---------------------------------------------------------------------------
# Authority


def test_authority_insufficient_then_granted(tmp_path):
    project, store = _project(tmp_path, pages=True)
    _start(project, store)
    _settle_preproduction(store, seed="authority-trial")
    blocked = _evaluate(store, "style.trial",
                        targets={"page_ids": ["p1"], "layers": ["design"]})
    assert "authority_insufficient" in blocked["reason_codes"]
    assert "grant an execute authorization" in blocked["next_action"]
    _grant(project, store, actions=("style.trial",))
    allowed = _evaluate(store, "style.trial",
                        targets={"page_ids": ["p1"], "layers": ["design"]})
    assert allowed["allowed"] is True, allowed["reason_codes"]
    assert allowed["authority_assurance"] == "host_attested"


def test_family_action_names_cover_their_entries(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store, actions=("exports.delivery",), scope=_scope(
        subject="deck", page_ids=["p1", "p2"], layers=["output"], purpose="delivery"),
        delivery_binding="process_delegation")
    decision = _evaluate(store, "export.delivery")
    assert "authority_insufficient" not in decision["reason_codes"]
    # A sibling verb is not covered by the family name.
    assert "authority_insufficient" in _evaluate(store, "style.expand")["reason_codes"]


def test_authorization_revoked_is_a_withdrawal_not_budget(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = _grant(project, store, actions=("call.begin",))
    assert _evaluate(store, "call.begin")["allowed"] is True
    collaboration.revoke_authorization(
        project, authorization_id=grant["authorization_id"], reason="wrong scope",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke")
    blocked = _evaluate(store, "call.begin")
    assert "authorization_revoked" in blocked["reason_codes"]
    assert "withdrawal stands" in blocked["next_action"]


def test_authority_channel_unavailable_under_verified_user_policy(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store, actions=("call.begin",))
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "policy-op-2",
                                      "kind": "collaboration_update",
                                      "description": "strict policy", "read_set": []})
    bumped["collaboration"] = {**document["collaboration"], "authority_policy": "verified_user"}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="policy-op-2")
    blocked = _evaluate(store, "call.begin")
    assert "authority_channel_unavailable" in blocked["reason_codes"]
    assert "never downgrade" in blocked["next_action"] or "never" in blocked["next_action"]
    # The same records under traceable policy proceed: the gap is the channel,
    # not the record.
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "policy-op-3",
                                      "kind": "collaboration_update",
                                      "description": "traceable again", "read_set": []})
    bumped["collaboration"] = {**document["collaboration"], "authority_policy": "traceable"}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="policy-op-3")
    allowed = _evaluate(store, "call.begin")
    assert allowed["allowed"] is True and "authority_channel_unavailable" not in allowed["reason_codes"]


# ---------------------------------------------------------------------------
# Budget


def test_budget_exhausted_blocks_new_calls_but_keeps_reserved_slot(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = _grant(project, store, actions=("call.begin", "allowance.allocate"),
                   max_external_calls=1)
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1", "consumed")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"],
                                  budget_key="req-1:initial:p1"))
    _commit_task(store, task)
    blocked = _evaluate(store, "allowance.allocate", task=task)
    assert "budget_exhausted" in blocked["reason_codes"]
    assert "only blocks new calls" in blocked["next_action"]
    # The very same slot may still begin: begin validates its own reservation
    # (CONTRACTS §3.3), it does not need a second remaining credit.
    reserved = _task(document, allowances=[_allowance("call-1", "reserved")],
                     binding=_binding(document, authorization_ref=grant["authorization_ref"],
                                      budget_key="req-1:initial:p1"))
    allowed = _evaluate(store, "call.begin", task=reserved,
                        context={"allowance_id": "call-1"})
    assert "budget_exhausted" not in allowed["reason_codes"]
    # Settlement and adoption of the last legal result stay available.
    assert _evaluate(store, "task.accept", task=task)["reason_codes"] == []


def test_budget_unknown_pauses_new_calls(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = _grant(project, store, actions=("call.begin",), max_external_calls=5)
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-9", "unknown")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    _commit_task(store, task)
    blocked = _evaluate(store, "call.begin", task=task,
                        context={"allowance_id": "call-9"})
    assert "budget_unknown" in blocked["reason_codes"]
    assert "never auto-retry" in blocked["next_action"]


def test_child_authorization_shares_the_parent_budget(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    parent = _grant(project, store, mode="delegate", actions=("call.begin",),
                    delegated_topics=("direction",), max_external_calls=1,
                    operation_id="op-parent")
    child = _grant(project, store, actions=("call.begin",), max_external_calls=1,
                   parent_authorization_ref=parent["authorization_ref"],
                   budget_parent_ref=parent["authorization_ref"],
                   operation_id="op-child")
    document = store.load_document()
    budget = eligibility.authorization_budget(store, document, child["authorization_ref"])
    # The child shares the root ceiling instead of duplicating it.
    assert budget["ceiling"] == 1
    task = _task(document, allowances=[_allowance("call-1", "consumed")],
                 binding=_binding(document, authorization_ref=child["authorization_ref"]))
    _commit_task(store, task)
    blocked = _evaluate(store, "call.begin", task=task, context={"allowance_id": "call-2"})
    assert "budget_exhausted" in blocked["reason_codes"]


# ---------------------------------------------------------------------------
# Inputs, review requirements, delivery policy


def test_input_reconciliation_pending_blocks_production(tmp_path):
    project, store = _project(tmp_path, pages=True)
    _start(project, store)
    _grant(project, store, actions=("dispatch.blueprint", "compile.ppt"),
           scope=_scope(page_ids=["p1", "p2"], layers=["blueprint", "output"]))
    _settle_preproduction(store, seed="input-basis")
    assert _evaluate(store, "compile.ppt")["allowed"] is True
    service.inputs_update(project, patch={"reason": "new material",
                                          "task_patch": {"audience": "主管"}},
                          base_revision=store.load_document()["revision_id"],
                          operation_id="op-input")
    blocked = _evaluate(store, "compile.ppt")
    assert "input_reconciliation_pending" in blocked["reason_codes"]
    assert "reconcile" in blocked["next_action"]
    # A read-only export still reports the input alignment instead of raising.
    assert _evaluate(store, "export.review")["allowed"] is True


def _put_preproduction_review(store, kind, review_id, *, reviewer_type="independent_host",
                              operation_id):
    """One passing preproduction review on the current page bytes (resolver
    fixture style: the review records themselves are settled, never a binding)."""
    document = store.load_document()
    deps = [{"kind": "content", "identity": f"page:{entry['page_id']}",
             "sha256": entry["page"]["sha256"]} for entry in document.get("pages") or []]
    deps.extend({"kind": "content", "identity": role, "sha256": document[role]["sha256"]}
                for role in ("narrative", "content_plan") if document.get(role))
    review_ref = store.put_json_object({
        "schema_version": "deck_review.v1", "review_id": review_id, "kind": kind,
        "review_stage": "preproduction", "status": "pass",
        "reviewer": {"type": reviewer_type, "id": "model-b", "assurance": "host_attested"},
        "subjects": [], "dependencies": deps, "observations": ["independent pass"],
        "findings": [], "replaces": None})
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "review_update",
                                      "description": f"preproduction {kind} review",
                                      "read_set": []})
    bumped["reviews"] = [*(document.get("reviews") or []), review_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)


def test_needs_reviewer_until_independent_preproduction_review(tmp_path):
    project, store = _project(tmp_path, pages=True)
    _set_quality_profile(store, content_review_requirement="independent_model_or_human",
                         requirement_origin="default_new_argument", override_decision_ref=None)
    _start(project, store)
    _grant(project, store, actions=("dispatch.blueprint",),
           scope=_scope(page_ids=["p1", "p2"], layers=["blueprint"]))
    blocked = _evaluate(store, "dispatch.blueprint")
    assert "needs_reviewer" in blocked["reason_codes"]
    assert blocked["missing_decision_topics"] == []
    assert "review draft" in blocked["next_action"]
    # One passing unit is never the whole review: the missing units keep the
    # gate shut (the T03 verdict, not a single-record shortcut).
    from deck_master import content_review
    units = content_review.required_units(store, store.load_document())
    _put_preproduction_review(store, units[0], f"review-pre-{units[0]}",
                              operation_id="review-op-partial")
    partial = _evaluate(store, "dispatch.blueprint")
    assert "needs_reviewer" in partial["reason_codes"], partial["reason_codes"]
    # Only an actually authenticated complete review clears strict review;
    # self-declared stored records cannot acquire stronger assurance at query.
    from synthetic_review_provider import (synthetic_context, dispatch_with_synthetic_provider,
                                           accept_with_synthetic_provider)
    context = synthetic_context()
    task = dispatch_with_synthetic_provider(project, adapter_context=context)['task']
    document = store.load_document()
    subjects = [document[role] for role in ('narrative', 'content_plan') if document.get(role)]
    subjects += [entry['page'] for entry in document['pages']]
    deps = [{'kind': 'content', 'identity': role, 'sha256': document[role]['sha256']}
            for role in ('narrative', 'content_plan') if document.get(role)]
    deps += [{'kind': 'content', 'identity': 'page:' + entry['page_id'], 'sha256': entry['page']['sha256']}
             for entry in document['pages']]
    evidence = store.put_json_object({'evidence_level': 'L1_SYNTHETIC', 'scenario': 'authenticated strict review'})
    reviews = [{'schema_version': 'deck_review.v2', 'review_id': 'authenticated-' + kind,
        'kind': kind, 'review_stage': 'preproduction', 'status': 'pass',
        'subjects': subjects, 'dependencies': deps, 'reviewer': {'type': 'independent_host',
            'id': 'synthetic-independent', 'execution_ref': 'exec-independent', 'independence_confirmed': True,
            'identity_receipt': None, 'evidence_ref': evidence, 'assurance': 'host_attested'},
        'observations': ['Synthetic independent review of the full named manuscript.'], 'findings': [],
        'created_at': '2026-10-17T00:00:00Z', 'replaces': None} for kind in units]
    # The authenticated recheck must explicitly replace the stored, merely
    # self-declared record. Authentication does not erase its owner identity.
    packet = next(store.read_object_json(ref) for ref in task['inputs']
                  if store.read_object_json(ref).get('schema_version') == 'content_review_packet.v1')
    templates = {row['kind']: row for row in reviews}
    reviews = []
    for kind in packet['required_units']:
        owners = [row['review_ref'] for row in packet['review_scope']['owners'] if row['kind'] == kind]
        if not owners:
            reviews.append(templates[kind])
        for ref in owners:
            owner = store.read_object_json(ref)
            assert owner['findings'] == []  # Never silently close a historical finding.
            reviews.append({**templates[kind], 'review_id': owner['review_id'], 'replaces': ref})
    assert accept_with_synthetic_provider(project,
        **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
        result_payload={'kind': 'review', 'files': [], 'reviews': reviews},
        adapter_context=context)['status'] == 'accepted'
    allowed = _evaluate(store, "dispatch.blueprint")
    assert "needs_reviewer" not in allowed["reason_codes"], allowed["reason_codes"]
    assert allowed["preproduction"]["satisfied"] is True


def test_host_self_is_only_accepted_through_the_explicit_override(tmp_path):
    project, store = _project(tmp_path, pages=True)
    # A profile naming host_self without an effective downgrade decision is the
    # independent requirement (T03 requirement_state): the review stays owed.
    _set_quality_profile(store, content_review_requirement="host_self",
                         requirement_origin="explicit_decision",
                         override_decision_ref=_stored_ref(store, "override"))
    _start(project, store)
    _grant(project, store, actions=("dispatch.blueprint",),
           scope=_scope(page_ids=["p1", "p2"], layers=["blueprint"]))
    blocked = _evaluate(store, "dispatch.blueprint")
    assert "needs_reviewer" in blocked["reason_codes"]
    assert blocked["preproduction"]["requirement"] == "independent_model_or_human"
    # A real accepted policy decision makes the downgrade effective; a
    # host-self review of the current manuscript then clears the gate.
    decision = collaboration.record_decision(
        project, input={"topic": "policy", "disposition": "accepted",
                        "authority_mode": "direct_user",
                        "value": {"content_review_requirement": "host_self",
                                  "scope": "this request", "reason": "合成演练"},
                        "scope": _scope(page_ids=["p1", "p2"], layers=["review"]),
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-downgrade-1")
    assert store.load_document()["collaboration"]["quality_profile"]["override_decision_ref"] == decision["decision_ref"]
    from deck_master import content_review
    units = content_review.required_units(store, store.load_document())
    for index, kind in enumerate(units):
        _put_preproduction_review(store, kind, f"review-self-{kind}",
                                  reviewer_type="host_self",
                                  operation_id=f"review-self-{index}")
    allowed = _evaluate(store, "dispatch.blueprint")
    assert allowed["preproduction"]["requirement"] == "host_self"
    assert "needs_reviewer" not in allowed["reason_codes"], allowed["reason_codes"]
    assert "preproduction_blocked" not in allowed["reason_codes"]
    assert allowed["allowed"] is True, allowed["reason_codes"]


def test_professional_review_required_is_independent_of_preproduction(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1", "p2"],
                                        layers=["output"], purpose="delivery"))
    _set_policy(store, {"professional_review_required_for_delivery": True})
    _grant(project, store, actions=("export.delivery",),
           scope=_scope(subject="deck", page_ids=["p1", "p2"], layers=["output"],
                        purpose="delivery"),
           delivery_binding="process_delegation")
    blocked = _evaluate(store, "export.delivery")
    assert "professional_review_required" in blocked["reason_codes"]
    assert "verified human professional review" in blocked["next_action"]
    # An independent model pass never satisfies the human policy.
    review_ref = store.put_json_object({
        "schema_version": "deck_review.v1", "review_id": "review-pro-1",
        "kind": "professional_use", "review_stage": "final", "status": "pass",
        "reviewer": {"type": "independent_host", "id": "model-b", "assurance": "host_attested"},
        "subjects": [], "dependencies": [], "observations": ["looks good"], "findings": []})
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "review-op-2", "kind": "review_update",
                                      "description": "model pass", "read_set": []})
    bumped["reviews"] = [*document["reviews"], review_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="review-op-2")
    still = _evaluate(store, "export.delivery")
    assert "professional_review_required" in still["reason_codes"]
    assert "basis_stale" not in still["reason_codes"]


def test_delivery_without_the_human_policy_is_allowed(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1", "p2"],
                                        layers=["output"], purpose="delivery"))
    _grant(project, store, actions=("export.delivery",),
           scope=_scope(subject="deck", page_ids=["p1", "p2"], layers=["output"],
                        purpose="delivery"),
           delivery_binding="process_delegation")
    allowed = _evaluate(store, "export.delivery")
    assert "professional_review_required" not in allowed["reason_codes"]
    assert allowed["allowed"] is True, allowed["reason_codes"]


def test_readiness_reports_the_delivery_policy_without_raising(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1"],
                                        layers=["output"], purpose="delivery"))
    _set_policy(store, {"professional_review_required_for_delivery": True})
    decision = eligibility.guard(store, store.load_document(), "readiness.final")
    assert decision["allowed"] is False
    assert "professional_review_required" in decision["reason_codes"]


# ---------------------------------------------------------------------------
# Task bindings


def test_binding_invalid_and_stale_are_distinct(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = _grant(project, store, actions=("call.begin",))
    document = store.load_document()
    foreign = _task(document, binding=_binding(document, request_id="req-someone-else",
                                               authorization_ref=grant["authorization_ref"]))
    assert "binding_invalid" in _evaluate(store, "call.begin", task=foreign)["reason_codes"]
    stale = _task(document, binding=_binding(document, authorization_ref=grant["authorization_ref"],
                                             digest="0" * 64))
    assert "binding_stale" in _evaluate(store, "call.begin", task=stale)["reason_codes"]
    valid = _task(document, binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    decision = _evaluate(store, "call.begin", task=valid)
    assert decision["binding"]["status"] == "valid"
    assert "binding_invalid" not in decision["reason_codes"]
    assert "binding_stale" not in decision["reason_codes"]


def test_binding_absent_task_settles_facts_but_never_produces_or_adopts(tmp_path):
    """The unconditional backstop: in a managed project a task without a
    collaboration binding cannot produce or adopt on *any* protocol, because it
    cannot establish whose authority it holds. Already-started call facts still
    settle, and a record-only review acceptance is a fact channel too."""
    project, store = _project(tmp_path)
    _start(project, store)
    _grant(project, store, actions=("call.begin", "allowance.allocate"))
    document = store.load_document()
    for protocol, capabilities in ((None, []), ("compose.v2", ["compose.v2", "collaboration.v1"])):
        task = _task(document, allowances=[_allowance("call-1", "consumed")],
                     protocol_version=protocol, required_capabilities=capabilities)
        for action in ("call.begin", "allowance.allocate", "task.start"):
            decision = _evaluate(store, action, task=task,
                                 context={"allowance_id": "call-1"})
            assert "decision_needed" in decision["reason_codes"], (protocol, action)
            assert decision["binding"]["status"] == "absent"
            assert "settle" in decision["reasons"][0]["detail"]
            assert "bound task" in decision["next_action"]
        adoption = _evaluate(store, "task.accept", task=task)
        assert "decision_needed" in adoption["reason_codes"], protocol
        # Facts already observed stay writable: settlement, cancellation and a
        # record-only review acceptance (an observation, not production).
        assert _evaluate(store, "call.settle", task=task)["allowed"] is True
        assert _evaluate(store, "task.cancel", task=task)["allowed"] is True
        record_only = _evaluate(store, "task.accept", task=task,
                                context={"record_only": True})
        assert record_only["allowed"] is True, record_only["reason_codes"]


def test_a_bound_task_is_judged_by_its_other_gates(tmp_path):
    """With a binding (the post-integration state) the normal gates apply:
    authority, scope and withdrawal — never an invented binding complaint."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1", "reserved")],
                 binding=_binding(document, authorization_ref=None))
    without_grant = _evaluate(store, "call.begin", task=task,
                              context={"allowance_id": "call-1"})
    assert without_grant["binding"]["status"] == "valid"
    assert "decision_needed" not in without_grant["reason_codes"]
    assert "authority_insufficient" in without_grant["reason_codes"]
    grant = _grant(project, store, actions=("call.begin",), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    task = _task(document, allowances=[_allowance("call-1", "reserved")],
                 binding=_binding(document, authorization_ref=grant["authorization_ref"]))
    allowed = _evaluate(store, "call.begin", task=task, context={"allowance_id": "call-1"})
    assert allowed["allowed"] is True, allowed["reason_codes"]
    # The same bound task for an unauthorized page fails on scope, not binding.
    out_of_scope = _evaluate(store, "call.begin", task=task,
                             context={"allowance_id": "call-1",
                                      "targets": {"page_ids": ["p2"]}})
    assert "scope_exceeded" in out_of_scope["reason_codes"]
    assert "decision_needed" not in out_of_scope["reason_codes"]


def test_binding_digest_formula_is_the_t03_contract():
    scope = _scope(page_ids=["p2", "p1"], layers=["svg", "page_copy"])
    basis = [{"kind": "task_fact", "identity": "audience", "projection": "value",
              "ref": None, "sha256": "bb"},
             {"kind": "policy", "identity": "document", "projection": "value",
              "ref": None, "sha256": "aa"}]
    expected = sha256_bytes(canonical_json_bytes({
        "phase": "page_copy",
        "write_scope": {"subject": "pages", "page_ids": ["p1", "p2"],
                        "page_manifest_ref": None, "external_artifact_ref": None,
                        "layers": ["page_copy", "svg"],
                        "allow_page_membership_change": False,
                        "allow_page_order_change": False, "purpose": "exploratory"},
        "basis": ["aa", "bb"],
    }))
    assert eligibility.binding_eligibility_digest("page_copy", scope, basis) == expected
    # Order of the basis list never changes the digest (sorted by value).
    assert eligibility.binding_eligibility_digest("page_copy", scope, list(reversed(basis))) == expected


# ---------------------------------------------------------------------------
# Persistence / read-only


def test_persistence_none_forbids_project_writes(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    blocked = _evaluate(store, "review.record", context={"persistence": "none"},
                        targets={"layers": ["review"]})
    assert "persistence_none" in blocked["reason_codes"]
    assert "outside the project" in blocked["next_action"]
    assert _evaluate(store, "review.strict",
                     context={"persistence": "none"})["allowed"] is True
    assert _evaluate(store, "review.record",
                     context={"persistence": "project"},
                     targets={"layers": ["review"]})["allowed"] is True


# ---------------------------------------------------------------------------
# Historical artifact snapshot x current control


def test_historical_snapshot_is_judged_against_the_current_control(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1"],
                                        layers=["output"], purpose="delivery"))
    old_revision = store.load_document()["revision_id"]
    # The historical revision was relaxed; the current head is strict.
    _set_policy(store, {"professional_review_required_for_delivery": True})
    _grant(project, store, actions=("export.delivery",),
           scope=_scope(subject="deck", page_ids=["p1"], layers=["output"],
                        purpose="delivery"),
           delivery_binding="process_delegation")
    current = store.load_document()
    artifact = store.load_document(old_revision)
    assert artifact["policy"]["professional_review_required_for_delivery"] is False
    decision = eligibility.evaluate(store, artifact, current, "delivery.historical")
    assert "professional_review_required" in decision["reason_codes"]
    assert "basis_stale" not in decision["reason_codes"]
    assert decision["artifact_revision_id"] == old_revision
    assert decision["control_revision_id"] == current["revision_id"]
    # The old relaxed policy never overrides a current withdrawal either.
    assert decision["enforcement"] == "active"


def test_current_policy_can_be_looser_than_the_snapshot(tmp_path):
    """The current control decides: a strict policy stored in the selected
    historical snapshot never resurrects a requirement the head dropped."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(subject="deck", page_ids=["p1"],
                                        layers=["output"], purpose="delivery"))
    _set_policy(store, {"professional_review_required_for_delivery": True})
    old_revision = store.load_document()["revision_id"]
    _set_policy(store, {"professional_review_required_for_delivery": False})
    # The controlling grant is recorded against the current policy, so the
    # comparison isolates the policy dimension, not a stale basis.
    _grant(project, store, actions=("export.delivery",),
           scope=_scope(subject="deck", page_ids=["p1"], layers=["output"],
                        purpose="delivery"),
           delivery_binding="process_delegation")
    current = store.load_document()
    decision = eligibility.evaluate(store, store.load_document(old_revision), current,
                                    "delivery.historical")
    assert "professional_review_required" not in decision["reason_codes"]
    assert decision["allowed"] is True, decision["reason_codes"]
    assert decision["artifact_revision_id"] == old_revision
    assert decision["control_revision_id"] == current["revision_id"]


# ---------------------------------------------------------------------------
# describe: the read-only entry


def test_describe_is_read_only_and_reports_the_selected_revision(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    revision = store.load_document()["revision_id"]
    before = _fingerprint(store)
    decision = eligibility.describe(project, "task.accept",
                                    targets={"page_ids": ["p1"]}, revision=revision)
    assert decision["allowed"] is True
    assert decision["selected_revision_id"] == revision
    assert decision["enforcement"] == "active"
    assert _fingerprint(store) == before
