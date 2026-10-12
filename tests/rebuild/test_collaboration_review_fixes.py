"""T02 review-fix regressions (PR108 independent review):

P1-1 replay-before-CAS ordering, P1-2 version semantics for same-identity
records, P1-3 cross-action verified-event replay, P1-4 service-completed
minimum basis, P1-5 delegation-chain effectiveness, and the P2 fixes
(dangling refs, resume evidence, task binding gate)."""
import hashlib

import pytest

from deck_master import collaboration, collaboration_migration, dependency_slices, service
from deck_master.dependency_slices import (authorization_effectiveness,
                                           decision_effectiveness)
from deck_master.models import ModelError, require_task_binding
from deck_master.store import Store


def _stored_ref(store, seed: str) -> dict:
    return store.put_json_object({"fixture": seed})


def _scope(**over) -> dict:
    scope = {"subject": "pages", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["narrative"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "exploratory"}
    scope.update(over)
    return scope


def _declared(store, kind="host_attested_instruction", **over) -> dict:
    evidence = {"kind": kind, "source_ref": _stored_ref(store, "source"),
                "source_locator": "chat:msg-1", "actor_id": None,
                "transport_receipt_ref": None, "presentation_ref": None}
    evidence.update(over)
    return evidence


def _project(tmp_path, name="proj"):
    project = tmp_path / name
    service.create(project, brief="review fixes")
    store = Store(project)
    document = store.load_document()
    from deck_master.models import bump_revision, require_writer
    bumped = bump_revision(document, {"operation_id": f"bootstrap-{name}",
                                      "kind": "collaboration_update",
                                      "description": "bootstrap", "read_set": []})
    bumped["collaboration"] = {
        "schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "independent_model_or_human",
                            "requirement_origin": "default_new_argument",
                            "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": []}
    require_writer(bumped, "collaboration.v1")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=f"bootstrap-{name}")
    return project, Store(project)


def _start(project, store, operation_id="op-start", intent="content_only",
           replace_request_id=None):
    payload = {"intent": intent,
               "content_intent": "write_only" if intent == "content_only" else None,
               "instruction_evidence": _declared(store), "scope": _scope(),
               "replace_request_id": replace_request_id}
    return collaboration.start_request(
        project, input=payload, base_revision=store.load_document()["revision_id"],
        operation_id=operation_id)


def _decision_input(store, **over):
    payload = {"topic": "direction", "value": "按培训路径", "disposition": "accepted",
               "authority_mode": "direct_user", "instruction_evidence": _declared(store),
               "scope": _scope()}
    payload.update(over)
    return payload


# ---------------------------------------------------------------------------
# P1-1: an identical operation replays its receipt before the CAS check


def test_natural_retry_with_same_base_revision_replays(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    base = store.load_document()["revision_id"]
    payload = _decision_input(store)
    first = collaboration.record_decision(project, input=payload, base_revision=base,
                                          operation_id="op-dec-retry")
    assert first["status"] == "accepted"
    # A retry that still carries the ORIGINAL base revision must replay, not fail CAS.
    retry = collaboration.record_decision(project, input=payload, base_revision=base,
                                          operation_id="op-dec-retry")
    assert retry["status"] == "already_applied"
    assert retry["applied_revision_id"] == first["revision_id"]
    # start_request follows the same order (one input payload, replayed verbatim).
    start_base = store.load_document()["revision_id"]
    replace_payload = {"intent": "edit", "content_intent": None,
                       "instruction_evidence": _declared(store), "scope": _scope(),
                       "replace_request_id": collaboration.describe(project)["request"]["request_id"]}
    started = collaboration.start_request(project, input=replace_payload,
                                          base_revision=start_base,
                                          operation_id="op-replace-retry")
    assert started["status"] == "accepted"
    replay = collaboration.start_request(project, input=replace_payload,
                                         base_revision=start_base,
                                         operation_id="op-replace-retry")
    assert replay["status"] == "already_applied"


def test_migration_apply_replays_before_cas(tmp_path):
    project = tmp_path / "legacy"
    service.create(project, brief="legacy", draft={"pages": [{
        "schema_version": "deck_page_package.v2", "page_id": "p1",
        "customer_visible": {"title": "t", "body_blocks": [{"id": "b1", "type": "paragraph", "text": "x"}]},
        "visual_spec": {"intent": "i", "reference_mode": "new_design"}}]})
    store = Store(project)
    base = store.load_document()["revision_id"]
    description = collaboration_migration.describe(project)
    first = collaboration_migration.apply(project, base_revision=base,
                                          plan_digest=description["plan_digest"],
                                          operation_id="op-migrate-retry")
    assert first["status"] == "accepted"
    replay = collaboration_migration.apply(project, base_revision=base,
                                           plan_digest=description["plan_digest"],
                                           operation_id="op-migrate-retry")
    assert replay["status"] == "already_applied"


# ---------------------------------------------------------------------------
# P1-2: same-identity versions replace, retire and resolve to the head


def test_decision_new_version_retires_old_and_only_head_is_effective(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    first = collaboration.record_decision(
        project, input=_decision_input(store, decision_id="dec-style", topic="style",
                                       value="蓝色"),
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-v1")
    region_refs = store.load_document()["collaboration"]["decisions"]
    old_ref = first["decision_ref"]
    second = collaboration.record_decision(
        project, input=_decision_input(store, decision_id="dec-style", topic="style",
                                       value="红色", replaces=old_ref),
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-v2")
    assert second["status"] == "accepted"
    document = store.load_document()
    # The old slot now holds a superseded retirement version of the same identity.
    retired = store.read_object_json(document["collaboration"]["decisions"][0])
    assert retired["status"] == "superseded" and retired["invalidated_by"] == "op-dec-v2"
    # An outdated pointer resolves to the CURRENT version of the identity
    # (CONTRACTS §3.3), so it reports the head's state, not a stale one.
    old_state = decision_effectiveness(store, document, old_ref)
    new_state = decision_effectiveness(store, document, second["decision_ref"])
    assert old_state["effective"] and new_state["effective"]
    # A record whose identity is no longer referenced is never effective.
    orphan = decision_effectiveness(store, {**document, "collaboration": {
        **document["collaboration"], "decisions": []}}, second["decision_ref"])
    assert not orphan["effective"] and "not_in_current_control" in orphan["reasons"]
    # A duplicate identity without replaces is rejected.
    with pytest.raises(ModelError, match="already exists"):
        collaboration.record_decision(
            project, input=_decision_input(store, decision_id="dec-style", topic="style",
                                           value="绿色"),
            base_revision=store.load_document()["revision_id"], operation_id="op-dec-v3")


def test_regrant_same_identity_then_revoke_hits_the_head(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)

    def grant(operation_id, calls, replaces=None):
        payload = {"mode": "delegate", "actions": ["task.start"],
                   "scope": _scope(), "delegated_topics": ["direction"],
                   "authorization_id": "authz-fixed", "max_external_calls": calls,
                   "instruction_evidence": _declared(store)}
        if replaces is not None:
            payload["replaces"] = replaces
        return collaboration.grant(project, input=payload,
                                   base_revision=store.load_document()["revision_id"],
                                   operation_id=operation_id)

    first = grant("op-g1", 0)
    head_before = store.load_document()["collaboration"]["authorizations"]
    second = grant("op-g2", 2, replaces=first["authorization_ref"])
    assert second["status"] == "accepted"
    refs = store.load_document()["collaboration"]["authorizations"]
    assert len(refs) == len(head_before)  # in-place version replacement
    described = collaboration.describe(project)
    heads = [a for a in described["authorizations"] if a["authorization_id"] == "authz-fixed"]
    assert len(heads) == 1 and heads[0]["max_external_calls"] == 2
    # Revocation acts on the current head, not the retired first version.
    revoked = collaboration.revoke_authorization(
        project, authorization_id="authz-fixed", reason="测试撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-r1")
    assert revoked["status"] == "accepted" and revoked["revoked_ref"] != first["authorization_ref"]
    again = collaboration.revoke_authorization(
        project, authorization_id="authz-fixed", reason="测试撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-r2")
    assert again["status"] == "already_revoked"


# ---------------------------------------------------------------------------
# P1-3: a verified event cannot be replayed onto another write payload


def test_verified_event_replay_across_actions_downgrades(tmp_path):
    project, store = _project(tmp_path)
    receipt = _stored_ref(store, "receipt")
    start_input = {"intent": "content_only", "content_intent": "write_only",
                   "instruction_evidence": _declared(store, "user_event",
                                                     transport_receipt_ref=receipt),
                   "scope": _scope()}
    binding = collaboration.write_digest(collaboration.ACTION_REQUEST_START, start_input)
    adapter = {"verified_user_events": [
        {"receipt_ref": receipt, "actor_id": "u-1", "action_binding": binding}]}
    started = collaboration.start_request(
        project, input=start_input, base_revision=store.load_document()["revision_id"],
        operation_id="op-start-verified", adapter_context=adapter)
    assert started["assurance"] == "verified_user"
    # Replaying the same event for a DIFFERENT action payload stays host-attested.
    decision_input = _decision_input(store, authority_mode="direct_user",
                                     instruction_evidence=_declared(
                                         store, "user_event", transport_receipt_ref=receipt))
    recorded = collaboration.record_decision(
        project, input=decision_input, base_revision=store.load_document()["revision_id"],
        operation_id="op-dec-replay", adapter_context=adapter)
    assert recorded["assurance"] == "host_attested"


# ---------------------------------------------------------------------------
# P1-4: the service completes the registered minimum basis


def test_direction_decision_without_basis_gets_registered_minimum(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    recorded = collaboration.record_decision(
        project, input=_decision_input(store),  # no explicit basis
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-required")
    decision = store.read_object_json(recorded["decision_ref"])
    keys = {dependency_slices.slice_key(dep) for dep in decision["basis"]}
    assert {"task_fact:audience:value", "task_fact:brief:value"} <= keys
    # An audience change now invalidates the decision it was never allowed to omit.
    service.inputs_update(project, patch={"reason": "new audience",
                                          "task_patch": {"audience": "主管阅读"}},
                          base_revision=store.load_document()["revision_id"],
                          operation_id="op-input-aud")
    state = decision_effectiveness(store, store.load_document(), recorded["decision_ref"])
    assert not state["effective"] and "basis_stale" in state["reasons"]


# ---------------------------------------------------------------------------
# P1-5: delegated decisions require a still-effective delegation


def test_delegated_decision_loses_effect_when_delegation_is_revoked(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["task.start"],
                        "scope": _scope(), "delegated_topics": ["direction"],
                        "authorization_id": "authz-d", "max_external_calls": 0,
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-delegate")
    recorded = collaboration.record_decision(
        project, input=_decision_input(store, authority_mode="delegated",
                                       delegation_ref=grant["authorization_ref"]),
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-delegated")
    assert decision_effectiveness(store, store.load_document(),
                                  recorded["decision_ref"])["effective"]
    collaboration.revoke_authorization(
        project, authorization_id="authz-d", reason="范围撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke-d")
    state = decision_effectiveness(store, store.load_document(), recorded["decision_ref"])
    assert not state["effective"] and "delegation_ineffective" in state["reasons"]


def test_delegation_from_superseded_request_is_rejected(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store, operation_id="op-start-r1")
    grant = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["task.start"],
                        "scope": _scope(), "delegated_topics": ["direction"],
                        "authorization_id": "authz-r1", "max_external_calls": 0,
                        "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-grant-r1")
    _start(project, store, operation_id="op-start-r2", intent="edit",
           replace_request_id=first["request_id"])
    with pytest.raises(ModelError, match="superseded request"):
        collaboration.record_decision(
            project, input=_decision_input(store, authority_mode="delegated",
                                           delegation_ref=grant["authorization_ref"]),
            base_revision=store.load_document()["revision_id"], operation_id="op-dec-old")


# ---------------------------------------------------------------------------
# P2 fixes


def test_dangling_subject_ref_is_rejected(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    with pytest.raises(ModelError, match="not in the store"):
        collaboration.record_decision(
            project, input=_decision_input(store, subject_refs=[
                {"artifact_kind": "narrative",
                 "artifact_ref": {"path": ".deckmaster/objects/aa/" + "a" * 64 + ".json",
                                  "sha256": "a" * 64},
                 "projection": "direction"}]),
            base_revision=store.load_document()["revision_id"], operation_id="op-dangl")


def test_resume_requires_instruction_evidence(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    collaboration.pause_request(project, reason="等材料",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-p")
    with pytest.raises(ModelError):
        collaboration.resume_request(project, instruction_evidence=None,
                                     base_revision=store.load_document()["revision_id"],
                                     operation_id="op-r")
    resumed = collaboration.resume_request(
        project, instruction_evidence=_declared(store),
        base_revision=store.load_document()["revision_id"], operation_id="op-r2")
    assert resumed["status"] == "accepted"


def test_task_binding_gate_for_collaboration_projects(tmp_path):
    from deck_master import tasks as tasks_mod
    project, store = _project(tmp_path)
    started = _start(project, store)
    document = store.load_document()
    task = tasks_mod.new_task(
        task_id="t1", operation_id="op-t1", kind="compose", scope_pages=["p1"],
        instruction="x", inputs=[], dependencies=[], dispatch_revision=document["revision_id"],
        produced_against=hashlib.sha256(b"x").hexdigest())
    with pytest.raises(ModelError, match="collaboration binding"):
        require_task_binding(document, task)
    task["collaboration_binding"] = {
        "request_id": started["request_id"], "phase": "page_copy", "executor_type": "host",
        "authorization_ref": None, "decision_refs": [],
        "write_scope": _scope(layers=["page_copy"], purpose="working"),
        "adoption_policy": "within_scope", "eligibility_basis": [],
        "eligibility_digest": hashlib.sha256(b"e").hexdigest(),
    }
    require_task_binding(document, task)
    task["collaboration_binding"] = {**task["collaboration_binding"], "request_id": "req-other"}
    with pytest.raises(ModelError, match="current work request"):
        require_task_binding(document, task)
    # Legacy projects (no collaboration writer) are unaffected.
    legacy = dict(document)
    legacy["compatibility"] = {"project_format": "workbench.v3", "minimum_writer": "workbench-quality.v1"}
    require_task_binding(legacy, {k: v for k, v in task.items() if k != "collaboration_binding"})
