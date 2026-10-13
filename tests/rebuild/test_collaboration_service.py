"""T02 slice 3: the single collaboration write path — request start/replace,
decision and authorization records, revocation and pause/resume, with
assurance computed only from the adapter context (CONTRACTS §2–§4)."""
import hashlib

import pytest

from deck_master import collaboration, service
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import ConflictError, Store


def _ref(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _stored_ref(store, seed: str) -> dict:
    """A real store object: formal records may only reference stored refs."""
    return store.put_json_object({"fixture": seed})


def _scope(**over) -> dict:
    scope = {"subject": "pages", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["narrative"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "exploratory"}
    scope.update(over)
    return scope


def _declared(store, kind: str = "host_attested_instruction", **over) -> dict:
    evidence = {"kind": kind, "source_ref": _stored_ref(store, "source"),
                "source_locator": "chat:msg-1",
                "actor_id": None, "transport_receipt_ref": None, "presentation_ref": None}
    evidence.update(over)
    return evidence


def _project(tmp_path, *, migrate=True):
    project = tmp_path / "proj"
    service.create(project, brief="collaboration contracts")
    store = Store(project)
    if migrate:
        document = store.load_document()
        bumped = bump_revision(document, {"operation_id": "bootstrap-collaboration",
                                          "kind": "collaboration_update",
                                          "description": "bootstrap region", "read_set": []})
        bumped["collaboration"] = {
            "schema_version": "collaboration.v1",
            "authority_policy": "traceable",
            "quality_profile": {"content_review_requirement": "independent_model_or_human",
                                "requirement_origin": "default_new_argument",
                                "override_decision_ref": None},
            "request": None, "decisions": [], "authorizations": [],
        }
        require_writer(bumped, "collaboration.v1")
        store.commit_change(base_revision=document["revision_id"], document=bumped,
                            operation_id="bootstrap-collaboration")
    return project, Store(project)


def _start(project, store, *, operation_id="op-start-1", intent="content_only",
           content_intent="plan_only", replace_request_id=None, **extra) -> dict:
    payload = {"intent": intent, "content_intent": content_intent,
               "instruction_evidence": _declared(store), "scope": _scope(**extra.pop("scope", {})),
               "replace_request_id": replace_request_id}
    payload.update(extra)
    return collaboration.start_request(project, input=payload,
                                       base_revision=store.load_document()["revision_id"],
                                       operation_id=operation_id)


# ---------------------------------------------------------------------------
# Evidence assurance


def test_assurance_is_never_client_settable(tmp_path):
    store = Store(tmp_path / "scratch")
    store.ensure_layout()
    with pytest.raises(ModelError, match="never client-settable"):
        collaboration.resolve_evidence({**_declared(store), "assurance": "verified_user"})
    # An unverified user_event claim is honestly downgraded, not upgraded.
    downgraded = collaboration.resolve_evidence(_declared(store, "user_event"))
    assert downgraded["kind"] == "host_attested_instruction"
    assert downgraded["assurance"] == "host_attested"


def test_verified_user_event_requires_receipt_and_action_binding(tmp_path):
    store = Store(tmp_path / "scratch")
    store.ensure_layout()
    receipt = _stored_ref(store, "receipt")
    declared = _declared(store, "user_event", transport_receipt_ref=receipt)
    binding = collaboration.write_digest(collaboration.ACTION_REQUEST_START, {"intent": "content_only"})
    adapter = {"verified_user_events": [
        {"receipt_ref": receipt, "actor_id": "u-123", "action_binding": binding}]}
    evidence = collaboration.resolve_evidence(declared, adapter, action_binding=binding)
    assert evidence["assurance"] == "verified_user" and evidence["actor_id"] == "u-123"
    # The same verified event replayed for a different write payload downgrades.
    other_binding = collaboration.write_digest(collaboration.ACTION_REQUEST_START,
                                               {"intent": "full_deck"})
    evidence = collaboration.resolve_evidence(declared, adapter, action_binding=other_binding)
    assert evidence["assurance"] == "host_attested"
    # A different receipt does not verify.
    declared = _declared(store, "user_event", transport_receipt_ref=_stored_ref(store, "other-receipt"))
    evidence = collaboration.resolve_evidence(declared, adapter, action_binding=binding)
    assert evidence["assurance"] == "host_attested"
    # Without a transport receipt a source match alone never upgrades.
    evidence = collaboration.resolve_evidence(_declared(store, "user_event"), adapter,
                                              action_binding=binding)
    assert evidence["assurance"] == "host_attested"


# ---------------------------------------------------------------------------
# Request lifecycle


def test_collaboration_writes_require_the_migrated_writer(tmp_path):
    project, store = _project(tmp_path, migrate=False)
    with pytest.raises(ModelError, match="migration_required"):
        _start(project, store)


def test_start_request_records_and_dedupes_by_source(tmp_path):
    project, store = _project(tmp_path)
    first = _start(project, store)
    assert first["status"] == "accepted" and first["request_id"].startswith("req-")
    revision_after_first = store.load_document()["revision_id"]
    # Same sources under a new operation id return the existing request.
    again = _start(project, store, operation_id="op-start-2")
    assert again["status"] == "already_started" and again["request_id"] == first["request_id"]
    assert store.load_document()["revision_id"] == revision_after_first
    # A different request while one is open requires the explicit replace id.
    with pytest.raises(ModelError, match="explicitly replaced"):
        _start(project, store, operation_id="op-start-3", intent="full_deck",
               content_intent=None)
    replaced = _start(project, store, operation_id="op-start-4", intent="full_deck",
                      content_intent=None, replace_request_id=first["request_id"])
    assert replaced["status"] == "accepted" and replaced["request_id"] != first["request_id"]
    # History still holds the superseded request record.
    previous = store.load_document(revision_after_first)
    assert previous["collaboration"]["request"]["request_id"] == first["request_id"]


def test_request_scope_shape_is_validated_on_commit(tmp_path):
    project, store = _project(tmp_path)
    with pytest.raises(ModelError, match="collaboration/request"):
        collaboration.start_request(
            project, input={"intent": "content_only", "content_intent": "plan_only",
                            "instruction_evidence": _declared(store),
                            "scope": {"subject": "pages"}},  # missing scope fields
            base_revision=store.load_document()["revision_id"], operation_id="op-bad-scope")


# ---------------------------------------------------------------------------
# Decisions


def test_decision_requires_open_request_and_lands_in_region(tmp_path):
    project, store = _project(tmp_path)
    with pytest.raises(ModelError, match="requires the current open work request"):
        collaboration.record_decision(
            project, input={"topic": "direction", "value": "按培训路径",
                            "disposition": "accepted", "authority_mode": "direct_user",
                            "instruction_evidence": _declared(store), "scope": _scope()},
            base_revision=store.load_document()["revision_id"], operation_id="op-dec-0")
    _start(project, store)
    outcome = collaboration.record_decision(
        project, input={"topic": "direction", "value": "按培训路径",
                        "disposition": "accepted", "authority_mode": "direct_user",
                        "instruction_evidence": _declared(store), "scope": _scope()},
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-1")
    assert outcome["status"] == "accepted" and outcome["assurance"] == "host_attested"
    described = collaboration.describe(project)
    assert described["decisions"][0]["decision_id"] == outcome["decision_id"]
    assert described["decisions"][0]["topic"] == "direction"


def test_delegated_decision_requires_active_covering_delegation(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    with pytest.raises(ModelError, match="must reference an authorization"):
        collaboration.record_decision(
            project, input={"topic": "style", "value": "暖色", "disposition": "accepted",
                            "authority_mode": "delegated", "delegation_ref": _ref("missing"),
                            "instruction_evidence": _declared(store), "scope": _scope()},
            base_revision=store.load_document()["revision_id"], operation_id="op-dec-x")
    grant = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["design.propose"],
                        "scope": _scope(layers=["design"]), "delegated_topics": ["style"],
                        "max_external_calls": 0, "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-grant-d1")
    accepted = collaboration.record_decision(
        project, input={"topic": "style", "value": "暖色", "disposition": "accepted",
                        "authority_mode": "delegated",
                        "delegation_ref": grant["authorization_ref"],
                        "instruction_evidence": _declared(store), "scope": _scope(layers=["design"])},
        base_revision=store.load_document()["revision_id"], operation_id="op-dec-2")
    assert accepted["status"] == "accepted"
    with pytest.raises(ModelError, match="covering this topic"):
        collaboration.record_decision(
            project, input={"topic": "direction", "value": "换主线", "disposition": "accepted",
                            "authority_mode": "delegated",
                            "delegation_ref": grant["authorization_ref"],
                            "instruction_evidence": _declared(store), "scope": _scope()},
            base_revision=store.load_document()["revision_id"], operation_id="op-dec-3")


# ---------------------------------------------------------------------------
# Authorizations


def test_sub_authorization_cannot_exceed_parent(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    parent = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["design.propose"],
                        "scope": _scope(layers=["design"]), "delegated_topics": ["style"],
                        "max_external_calls": 0, "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-parent")
    parent_ref = parent["authorization_ref"]

    def child(operation_id, **over):
        payload = {"mode": "execute", "actions": ["design.propose"],
                   "scope": _scope(layers=["design"]),
                   "parent_authorization_ref": parent_ref,
                   "max_external_calls": 1, "instruction_evidence": _declared(store)}
        payload.update(over)
        return collaboration.grant(project, input=payload,
                                   base_revision=store.load_document()["revision_id"],
                                   operation_id=operation_id)

    with pytest.raises(ModelError, match="cannot exceed the parent's layers"):
        child("op-child-layers", scope=_scope(layers=["design", "blueprint"]))
    with pytest.raises(ModelError, match="beyond its parent delegation"):
        child("op-child-pages", scope=_scope(layers=["design"], page_ids=["p1"]))
    ok = child("op-child-ok")
    assert ok["status"] == "accepted"


def test_revoke_writes_new_version_and_keeps_history(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["design.propose"],
                        "scope": _scope(layers=["design"]), "delegated_topics": ["style"],
                        "max_external_calls": 0, "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-grant")
    original_ref = grant["authorization_ref"]
    revoked = collaboration.revoke_authorization(
        project, authorization_id=grant["authorization_id"], reason="范围撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke")
    assert revoked["status"] == "accepted" and revoked["revoked_ref"] != original_ref
    assert store.read_object_json(original_ref)["status"] == "active"  # history intact
    described = collaboration.describe(project)
    current = described["authorizations"][-1]
    assert current["status"] == "revoked" and current["replaces"] == original_ref
    again = collaboration.revoke_authorization(
        project, authorization_id=grant["authorization_id"], reason="范围撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke-2")
    assert again["status"] == "already_revoked"


# ---------------------------------------------------------------------------
# Pause / resume and replay


def test_pause_and_resume_are_recorded_with_reasons(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    with pytest.raises(ModelError, match="records its reason"):
        collaboration.pause_request(
            project, reason="  ", base_revision=store.load_document()["revision_id"],
            operation_id="op-pause-bad")
    paused = collaboration.pause_request(
        project, reason="等新材料", base_revision=store.load_document()["revision_id"],
        operation_id="op-pause")
    assert paused["status"] == "accepted"
    assert collaboration.describe(project)["request"]["paused"] is True
    again = collaboration.pause_request(
        project, reason="等新材料", base_revision=store.load_document()["revision_id"],
        operation_id="op-pause-2")
    assert again["status"] == "already_paused"
    resumed = collaboration.resume_request(
        project, instruction_evidence=_declared(store),
        base_revision=store.load_document()["revision_id"], operation_id="op-resume")
    assert resumed["status"] == "accepted"
    assert collaboration.describe(project)["request"]["paused"] is False


def test_operation_replay_and_conflict(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    payload = {"topic": "tradeoff", "value": "六页", "disposition": "accepted",
               "authority_mode": "direct_user", "instruction_evidence": _declared(store),
               "scope": _scope()}
    first = collaboration.record_decision(
        project, input=payload, base_revision=store.load_document()["revision_id"],
        operation_id="op-replay")
    assert first["status"] == "accepted"
    replay = collaboration.record_decision(
        project, input=payload, base_revision=store.load_document()["revision_id"],
        operation_id="op-replay")
    assert replay["status"] == "already_applied"
    assert replay["applied_revision_id"] == first["revision_id"]
    with pytest.raises(ConflictError):
        collaboration.record_decision(
            project, input={**payload, "value": "八页"},
            base_revision=store.load_document()["revision_id"], operation_id="op-replay")
