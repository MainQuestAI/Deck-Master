"""Collaboration control objects: the single write path for the work request,
decisions and authorizations (content collaboration v1.2 CONTRACTS §2–§4).

Assurance is computed here from the transport adapter context; client
payloads can never set it. These functions own record correctness, the writer
boundary, CAS and operation replay. Scope/budget enforcement across every
production entry point is T04's card and is not claimed here: an authorization
record becoming effective for an action is still decided by the eligibility
resolver that T04 builds on top of these records.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import models, tasks as tasks_mod
from .editing import operation_revision
from .models import ModelError, bump_revision, canonical_json_bytes, sha256_bytes
from .store import ConflictError, Store, StoreError

WRITE_CHANGE_KIND = "collaboration_update"
_ACTION_REQUEST = "collaboration.start_request"
_ACTION_DECISION = "collaboration.record_decision"
_ACTION_GRANT = "collaboration.grant"
_ACTION_REVOKE = "collaboration.revoke"
_ACTION_PAUSE = "collaboration.pause_request"
_ACTION_RESUME = "collaboration.resume_request"

ASSURANCE_RANK = {"unverified": 0, "host_attested": 1, "verified_user": 2}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_id(prefix: str, operation_id: str) -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, operation_id).hex[:12]}"


def payload_digest(action: str, payload: dict) -> str:
    return sha256_bytes(canonical_json_bytes({"action": action, "payload": payload}))


# ---------------------------------------------------------------------------
# Evidence: assurance comes from the adapter context, never from the client


def _verified_event(evidence: dict, adapter_context) -> dict | None:
    """Match the declared receipt/source against the adapter's verified user
    events. The adapter itself (issuer signature, actor binding, nonce,
    expiry) is T07's trusted transport; this is the record-side contract."""
    if not adapter_context:
        return None
    events = adapter_context.get("verified_user_events") or []
    receipt = evidence.get("transport_receipt_ref") or {}
    declared_source = evidence.get("source_ref") or {}
    for event in events:
        if not isinstance(event, dict):
            continue
        event_receipt = event.get("receipt_ref") or {}
        if receipt.get("path") and (event_receipt.get("path"), event_receipt.get("sha256")) == (
                receipt.get("path"), receipt.get("sha256")):
            return event
        if not receipt:
            event_source = event.get("source_ref") or {}
            if (event_source.get("path"), event_source.get("sha256")) == (
                    declared_source.get("path"), declared_source.get("sha256")):
                return event
    return None


def resolve_evidence(declared: dict, adapter_context=None, *, where: str = "evidence") -> dict:
    """Compute the recorded Evidence (CONTRACTS §4).

    A declared ``user_event`` is only verified_user when a matching trusted
    adapter event exists; otherwise it is honestly downgraded to a traceable
    host-attested instruction. Any client-supplied ``assurance`` is rejected
    outright — assurance is never client-settable.
    """
    if not isinstance(declared, dict):
        raise ModelError(where, "evidence must be an object")
    if "assurance" in declared:
        raise ModelError(f"{where}/assurance",
                         "assurance is computed by the runtime adapter context and is never client-settable")
    kind = declared.get("kind")
    source_ref = declared.get("source_ref")
    if not isinstance(source_ref, dict) or not source_ref.get("path") or not source_ref.get("sha256"):
        raise ModelError(f"{where}/source_ref", "evidence requires a source Ref")
    evidence = {
        "kind": kind,
        "assurance": "unverified",
        "source_ref": source_ref,
        "source_locator": declared.get("source_locator"),
        "actor_id": declared.get("actor_id"),
        "transport_receipt_ref": declared.get("transport_receipt_ref"),
        "presentation_ref": declared.get("presentation_ref"),
    }
    if kind == "user_event":
        event = _verified_event(evidence, adapter_context)
        if event is None:
            evidence["kind"] = "host_attested_instruction"
            evidence["assurance"] = "host_attested"
        else:
            evidence["assurance"] = "verified_user"
            if event.get("actor_id"):
                evidence["actor_id"] = event["actor_id"]
    elif kind == "host_attested_instruction":
        evidence["assurance"] = "host_attested"
    elif kind in ("approved_document", "imported_unknown"):
        evidence["assurance"] = "unverified"
    elif kind == "delegated":
        evidence["assurance"] = "host_attested"
    else:
        raise ModelError(f"{where}/kind", f"unknown evidence kind {kind!r}")
    models.validate_evidence_semantics(evidence, where)
    return evidence


# ---------------------------------------------------------------------------
# Shared write mechanics


def _require_region(store, document) -> dict:
    if not models.writer_at_least(document, "collaboration.v1"):
        raise ModelError(
            "collaboration",
            "migration_required: this project predates the collaboration writer; "
            "run collaboration migration apply before any collaboration write",
        )
    region = document.get("collaboration")
    if region is None:
        raise ModelError("collaboration", "collaboration region missing at the collaboration.v1 writer boundary")
    return region


def replay_or_conflict(store, document, operation_id, action, payload_digest_value):
    prior = operation_revision(store, document, operation_id)
    if prior is None:
        return None
    change = prior.get("change") or {}
    if change.get("kind") == WRITE_CHANGE_KIND and change.get("payload_digest") == payload_digest_value:
        return {
            "status": "already_applied",
            "revision_id": document["revision_id"],
            "applied_revision_id": prior["revision_id"],
        }
    raise ConflictError("operation_id", "different payload already applied")


def commit_collaboration_change(store, document, *, operation_id, action, digest,
                                description, updated) -> str:
    change = {
        "operation_id": operation_id,
        "kind": WRITE_CHANGE_KIND,
        "description": description,
        "read_set": [],
        "payload_digest": digest,
    }
    # Bump the mutated copy; the parent link and CAS still use the loaded document.
    bumped = bump_revision(updated, change)
    models.require_writer(bumped, "collaboration.v1")
    store._commit_locked(base_revision=document["revision_id"], document=bumped,
                         operation_id=operation_id, blobs=[])
    return bumped["revision_id"]


def _request_source_key(request: dict) -> str:
    evidence = request.get("instruction_evidence") or {}
    locator = evidence.get("source_locator")
    source = evidence.get("source_ref") or {}
    variant = request.get("variant") or {}
    return sha256_bytes(canonical_json_bytes({
        "locator": locator or source.get("sha256"),
        "intent": request.get("intent"),
        "content_intent": request.get("content_intent"),
        "scope": request.get("scope"),
        "variant_id": variant.get("variant_id"),
    }))


# ---------------------------------------------------------------------------
# Public service functions


def describe(project) -> dict:
    """Read-only collaboration projection (CONTRACT §12 show)."""
    store = Store(Path(project).expanduser())
    document = store.load_document()
    region = document.get("collaboration")
    result = {
        "project_id": document["project_id"],
        "revision_id": document["revision_id"],
        "minimum_writer": (document.get("compatibility") or {}).get("minimum_writer"),
        "migrated": region is not None,
        "authority_policy": None,
        "quality_profile": None,
        "request": None,
        "decisions": [],
        "authorizations": [],
    }
    if region is None:
        return result
    result["authority_policy"] = region.get("authority_policy")
    result["quality_profile"] = region.get("quality_profile")
    result["request"] = region.get("request")
    for ref in region.get("decisions") or []:
        result["decisions"].append(store.read_object_json(ref))
    for ref in region.get("authorizations") or []:
        result["authorizations"].append(store.read_object_json(ref))
    return result


def start_request(project, *, input: dict, base_revision: str, operation_id: str,
                  adapter_context=None) -> dict:
    """Start or replace the current work request (CONTRACT §2, §12 start/replace).

    Deduplication: the same instruction source with the same normalized
    intent/scope maps to the same source key, so retries under a new operation
    id return the existing request instead of creating a second one.
    """
    store = Store(Path(project).expanduser())

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        declared = input.get("instruction_evidence")
        evidence = resolve_evidence(declared, adapter_context,
                                    where="collaboration/request/instruction_evidence")
        current = region.get("request")
        replace_request_id = input.get("replace_request_id")
        candidate = {
            "request_id": _stable_id("req", operation_id),
            "intent": input.get("intent"),
            "content_intent": input.get("content_intent"),
            "instruction_evidence": evidence,
            "scope": input.get("scope"),
            "paused": False,
            "pause_reason": None,
            "closed": False,
            "closed_reason": None,
            "background_request_ids": list(input.get("background_request_ids") or []),
            "variant": input.get("variant"),
        }
        if current is not None and not current.get("closed"):
            if _request_source_key(current) == _request_source_key(candidate):
                return {"status": "already_started", "request_id": current["request_id"],
                        "revision_id": document["revision_id"]}
            if replace_request_id != current.get("request_id"):
                raise ModelError(
                    "collaboration/request",
                    "an open request must be explicitly replaced: pass replace_request_id "
                    "naming the current request",
                )
        elif replace_request_id is not None and (current is None or current.get("request_id") != replace_request_id):
            raise ModelError("collaboration/request/replace_request_id",
                             "replace_request_id must name the current open request")
        digest = payload_digest(_ACTION_REQUEST, {"input": input, "evidence": evidence})
        replay = replay_or_conflict(store, document, operation_id, _ACTION_REQUEST, digest)
        if replay:
            return replay
        updated_region = {**region, "request": candidate}
        updated = {**document, "collaboration": updated_region}
        committed = commit_collaboration_change(store, document, operation_id=operation_id, action=_ACTION_REQUEST,
                            digest=digest, description="start work request", updated=updated)
        return {"status": "accepted", "request_id": candidate["request_id"],
                "effective_scope": candidate["scope"],
                "assurance": evidence["assurance"],
                "revision_id": committed}

    return locked(store)


def record_decision(project, *, input: dict, base_revision: str, operation_id: str,
                    adapter_context=None) -> dict:
    """Record a decision as an immutable object referenced by the region
    (CONTRACT §3.1). client assurance upgrades are rejected by resolve_evidence."""
    store = Store(Path(project).expanduser())

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        request = region.get("request")
        if request is None or request.get("closed"):
            raise ModelError("collaboration/request", "a decision requires the current open work request")
        topic = input.get("topic")
        delegation_ref = input.get("delegation_ref")
        authority_mode = input.get("authority_mode")
        if authority_mode == "delegated":
            _validate_delegation(store, region, delegation_ref, topic)
        evidence = resolve_evidence(input.get("instruction_evidence"), adapter_context,
                                    where="collaboration/decision/evidence")
        decision = {
            "schema_version": "collaboration_decision.v1",
            "decision_id": input.get("decision_id") or _stable_id("dec", operation_id),
            "project_id": document["project_id"],
            "request_id": request["request_id"],
            "topic": topic,
            "subject_refs": list(input.get("subject_refs") or []),
            "scope": input.get("scope") or request.get("scope"),
            "value": input.get("value"),
            "disposition": input.get("disposition"),
            "authority_mode": authority_mode,
            "evidence": evidence,
            "delegation_ref": delegation_ref,
            "basis": list(input.get("basis") or []),
            "status": "active",
            "replaces": input.get("replaces"),
            "invalidated_by": None,
            "created_at": _now_iso(),
        }
        models.validate_decision_semantics(decision)
        digest = payload_digest(_ACTION_DECISION, {"input": input, "evidence": evidence})
        replay = replay_or_conflict(store, document, operation_id, _ACTION_DECISION, digest)
        if replay:
            return replay
        decision_ref = store.put_json_object(decision)
        updated_region = {**region, "decisions": list(region.get("decisions") or []) + [decision_ref]}
        updated = {**document, "collaboration": updated_region}
        committed = commit_collaboration_change(store, document, operation_id=operation_id, action=_ACTION_DECISION,
                            digest=digest,
                            description=f"record decision {decision['decision_id']} ({topic})",
                            updated=updated)
        return {"status": "accepted", "decision_ref": decision_ref,
                "decision_id": decision["decision_id"], "assurance": evidence["assurance"],
                "revision_id": committed}

    return locked(store)


def grant(project, *, input: dict, base_revision: str, operation_id: str,
          adapter_context=None) -> dict:
    """Record an execute/delegate authorization (CONTRACT §3.2). Sub- grants
    cannot exceed their parent delegation's scope, topics or evidence level."""
    store = Store(Path(project).expanduser())

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        request = region.get("request")
        if request is None or request.get("closed"):
            raise ModelError("collaboration/request", "a grant requires the current open work request")
        evidence = resolve_evidence(input.get("instruction_evidence"), adapter_context,
                                    where="collaboration/authorization/evidence")
        authorization = {
            "schema_version": "collaboration_authorization.v1",
            "authorization_id": input.get("authorization_id") or _stable_id("authz", operation_id),
            "project_id": document["project_id"],
            "request_id": request["request_id"],
            "mode": input.get("mode"),
            "actions": list(input.get("actions") or []),
            "scope": input.get("scope") or request.get("scope"),
            "decision_refs": list(input.get("decision_refs") or []),
            "delegated_topics": list(input.get("delegated_topics") or []),
            "constraints": dict(input.get("constraints") or {}),
            "max_external_calls": input.get("max_external_calls", 0),
            "max_candidate_count": input.get("max_candidate_count", 0),
            "budget_template": input.get("budget_template"),
            "budget_parent_ref": input.get("budget_parent_ref"),
            "budget_key": input.get("budget_key"),
            "adoption_policy": input.get("adoption_policy", "candidate_only"),
            "delivery_binding": input.get("delivery_binding", "none"),
            "evidence": evidence,
            "basis": list(input.get("basis") or []),
            "parent_authorization_ref": input.get("parent_authorization_ref"),
            "replaces": input.get("replaces"),
            "status": "active",
            "expires_at": input.get("expires_at"),
            "stop_conditions": list(input.get("stop_conditions") or []),
            "created_at": _now_iso(),
        }
        models.validate_authorization_semantics(authorization)
        _validate_parent_chain(store, region, authorization)
        digest = payload_digest(_ACTION_GRANT, {"input": input, "evidence": evidence})
        replay = replay_or_conflict(store, document, operation_id, _ACTION_GRANT, digest)
        if replay:
            return replay
        authorization_ref = store.put_json_object(authorization)
        updated_region = {**region, "authorizations": list(region.get("authorizations") or []) + [authorization_ref]}
        updated = {**document, "collaboration": updated_region}
        committed = commit_collaboration_change(store, document, operation_id=operation_id, action=_ACTION_GRANT,
                            digest=digest,
                            description=f"grant {authorization['authorization_id']} ({authorization['mode']})",
                            updated=updated)
        return {"status": "accepted", "authorization_ref": authorization_ref,
                "authorization_id": authorization["authorization_id"],
                "assurance": evidence["assurance"], "revision_id": committed}

    return locked(store)


def revoke_authorization(project, *, authorization_id: str, reason: str, base_revision: str,
                         operation_id: str, adapter_context=None) -> dict:
    """Revoke an authorization by writing a new version that replaces it; the
    original record stays in history (CONTRACT §3.3)."""
    store = Store(Path(project).expanduser())

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        if not (reason or "").strip():
            raise ModelError("collaboration/revoke/reason", "a revocation records its reason")
        refs = list(region.get("authorizations") or [])
        target_index = None
        target = None
        for index, ref in enumerate(refs):
            candidate = store.read_object_json(ref)
            if candidate.get("authorization_id") == authorization_id:
                target_index, target = index, candidate
                break
        if target is None:
            raise ModelError("collaboration/authorizations",
                             f"no authorization {authorization_id!r} in the current region")
        if target.get("status") == "revoked":
            return {"status": "already_revoked", "authorization_id": authorization_id,
                    "revision_id": document["revision_id"]}
        digest = payload_digest(_ACTION_REVOKE,
                                {"authorization_id": authorization_id, "reason": reason})
        replay = replay_or_conflict(store, document, operation_id, _ACTION_REVOKE, digest)
        if replay:
            return replay
        revoked = {**target, "status": "revoked", "replaces": refs[target_index]}
        models.validate_authorization_semantics(revoked)
        revoked_ref = store.put_json_object(revoked)
        updated_refs = list(refs)
        updated_refs[target_index] = revoked_ref
        updated_region = {**region, "authorizations": updated_refs}
        updated = {**document, "collaboration": updated_region}
        committed = commit_collaboration_change(store, document, operation_id=operation_id, action=_ACTION_REVOKE,
                            digest=digest,
                            description=f"revoke authorization {authorization_id}: {reason.strip()}",
                            updated=updated)
        return {"status": "accepted", "authorization_id": authorization_id,
                "revoked_ref": revoked_ref, "revision_id": committed}

    return locked(store)


def pause_request(project, *, reason: str, base_revision: str, operation_id: str,
                  adapter_context=None) -> dict:
    """Pause the current request; reads keep working, new production stops
    being eligible (enforcement in T04)."""
    return _set_pause(project, paused=True, reason=reason, base_revision=base_revision,
                      operation_id=operation_id, adapter_context=adapter_context)


def resume_request(project, *, instruction_evidence: dict | None = None, base_revision: str,
                   operation_id: str, adapter_context=None) -> dict:
    """Resume the paused request. It never widens scope: eligibility re-derives
    from the unchanged request (CONTRACT §7.1)."""
    return _set_pause(project, paused=False, reason=None, base_revision=base_revision,
                      operation_id=operation_id, adapter_context=adapter_context,
                      instruction_evidence=instruction_evidence)


def _set_pause(project, *, paused: bool, reason, base_revision: str, operation_id: str,
               adapter_context=None, instruction_evidence=None) -> dict:
    store = Store(Path(project).expanduser())
    action = _ACTION_PAUSE if paused else _ACTION_RESUME

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        request = region.get("request")
        if request is None or request.get("closed"):
            raise ModelError("collaboration/request", "no open request to pause or resume")
        if paused and not (reason or "").strip():
            raise ModelError("collaboration/request/pause_reason", "pausing records its reason")
        if bool(request.get("paused")) == paused:
            return {"status": "already_paused" if paused else "already_active",
                    "request_id": request["request_id"], "revision_id": document["revision_id"]}
        evidence = None
        if not paused and instruction_evidence is not None:
            evidence = resolve_evidence(instruction_evidence, adapter_context,
                                        where="collaboration/request/resume/evidence")
        digest = payload_digest(action, {"reason": reason, "evidence": evidence})
        replay = replay_or_conflict(store, document, operation_id, action, digest)
        if replay:
            return replay
        updated_request = {**request, "paused": paused,
                           "pause_reason": reason.strip() if paused else None}
        updated_region = {**region, "request": updated_request}
        updated = {**document, "collaboration": updated_region}
        committed = commit_collaboration_change(store, document, operation_id=operation_id, action=action,
                            digest=digest,
                            description="pause request: " + reason.strip() if paused else "resume request",
                            updated=updated)
        return {"status": "accepted", "request_id": request["request_id"],
                "revision_id": committed}

    return locked(store)


# ---------------------------------------------------------------------------
# Delegation checks


def _load_commands(store, region):
    authorizations = [store.read_object_json(ref) for ref in region.get("authorizations") or []]
    by_ref = {(ref.get("path"), ref.get("sha256")): obj
              for ref, obj in zip(region.get("authorizations") or [], authorizations)}
    return authorizations, by_ref


def _validate_delegation(store, region, delegation_ref, topic) -> None:
    _, by_ref = _load_commands(store, region)
    target = by_ref.get(((delegation_ref or {}).get("path"), (delegation_ref or {}).get("sha256")))
    if target is None:
        raise ModelError("decision/delegation_ref",
                         "a delegated decision must reference an authorization in the current region")
    if not (target.get("mode") == "delegate" and target.get("status") == "active"
            and topic in (target.get("delegated_topics") or [])):
        raise ModelError("decision/delegation_ref",
                         "the referenced delegation is not an active delegate covering this topic")


def _validate_parent_chain(store, region, authorization) -> None:
    parent_ref = authorization.get("parent_authorization_ref")
    if parent_ref is None:
        return
    _, by_ref = _load_commands(store, region)
    parent = by_ref.get((parent_ref.get("path"), parent_ref.get("sha256")))
    if parent is None or parent.get("mode") != "delegate":
        raise ModelError("authorization/parent_authorization_ref",
                         "a derived authorization must reference its delegate parent in the current region")
    parent_scope, child_scope = parent.get("scope") or {}, authorization.get("scope") or {}
    if child_scope.get("page_ids") and not set(child_scope["page_ids"]) <= set(parent_scope.get("page_ids") or []):
        raise ModelError("authorization/scope/page_ids",
                         "a sub-authorization cannot name pages beyond its parent delegation")
    parent_layers = set(parent_scope.get("layers") or [])
    child_layers = set(child_scope.get("layers") or [])
    if not child_layers <= parent_layers:
        raise ModelError("authorization/scope/layers",
                         "a sub-authorization cannot exceed the parent's layers")
    parent_topics = set(parent.get("delegated_topics") or [])
    if not set(authorization.get("delegated_topics") or []) <= parent_topics:
        raise ModelError("authorization/delegated_topics",
                         "a sub-authorization cannot delegate topics its parent does not cover")
    if (ASSURANCE_RANK[(authorization.get("evidence") or {}).get("assurance", "unverified")]
            > ASSURANCE_RANK[(parent.get("evidence") or {}).get("assurance", "unverified")]):
        raise ModelError("authorization/evidence/assurance",
                         "a sub-authorization cannot claim stronger assurance than its parent")
