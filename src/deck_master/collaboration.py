"""Collaboration control objects: the single write path for the work request,
decisions and authorizations (content collaboration v1.2 CONTRACTS §2–§4).

Assurance is computed here from the transport adapter context; client
payloads can never set it, and a verified user event must be bound to the
exact write payload it approved. These functions own record correctness, the
writer boundary, CAS and operation replay. Scope/budget enforcement across
every production entry point is T04's card; record correctness is not.

Write order per CONTRACTS §6.1: an identical operation id replays its
original receipt *before* any base-revision check, so a natural retry after
a timeout succeeds instead of failing on CAS.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import dependency_slices, models, tasks as tasks_mod
from .collaboration_scope import delegation_gaps
from .editing import operation_revision
from .models import ModelError, bump_revision, canonical_json_bytes, sha256_bytes
from .store import ConflictError, Store, StoreError

WRITE_CHANGE_KIND = "collaboration_update"
ACTION_REQUEST_START = "collaboration.start_request"
ACTION_DECISION_RECORD = "collaboration.record_decision"
ACTION_GRANT = "collaboration.grant"
ACTION_REVOKE = "collaboration.revoke"
ACTION_PAUSE = "collaboration.pause_request"
ACTION_RESUME = "collaboration.resume_request"
ACTION_ADOPT_PROPOSAL = "collaboration.adopt_proposal"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_id(prefix: str, operation_id: str) -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, operation_id).hex[:12]}"


def payload_digest(action: str, payload: dict) -> str:
    """Canonical digest of a collaboration write payload. The same digest is
    both the replay-conflict fingerprint and the action binding a verified
    user event must carry to prove the user approved *this* write."""
    return sha256_bytes(canonical_json_bytes({"action": action, "payload": payload}))


def write_digest(action: str, write_input: dict) -> str:
    return payload_digest(action, {"input": write_input})


# ---------------------------------------------------------------------------
# Evidence: assurance comes from the adapter context, never from the client


def _verified_event(evidence: dict, adapter_context, action_binding, *, project_id=None, request_id=None) -> dict | None:
    """Match a declared user_event against the adapter's verified events.

    A match requires BOTH the adapter's action binding (the exact write payload
    the user confirmed — this is what stops replaying one verified event onto
    a different decision or grant) and a declared transport receipt whose Ref
    matches the event's receipt. A bare source match never upgrades. Receipt
    verification itself (issuer signature, actor binding, nonce, expiry) is
    T07's trusted transport; this is the record-side contract.
    """
    if not adapter_context or not action_binding or project_id is None:
        return None
    from .review_evidence import context_payload
    events = context_payload(adapter_context).get("verified_user_events") or []
    receipt = evidence.get("transport_receipt_ref") or {}
    if not receipt.get("path"):
        return None
    for event in events:
        if (not isinstance(event, dict) or event.get("action_binding") != action_binding
                or event.get("project_id") != project_id or event.get("request_id") != request_id
                or event.get("source_ref") != evidence.get("source_ref")
                or event.get("presentation_ref") != evidence.get("presentation_ref")):
            continue
        event_receipt = event.get("receipt_ref") or {}
        if (event_receipt.get("path"), event_receipt.get("sha256")) == (
                receipt.get("path"), receipt.get("sha256")):
            return event
    return None


def resolve_evidence(declared: dict, adapter_context=None, *, where: str = "evidence",
                     action_binding: str | None = None, project_id=None, request_id=None, store=None) -> dict:
    """Compute the recorded Evidence (CONTRACTS §4).

    A declared ``user_event`` is only verified_user when a matching trusted
    adapter event exists *for this exact write payload*; otherwise it is
    honestly downgraded to a traceable host-attested instruction. Any
    client-supplied ``assurance`` is rejected outright.
    """
    if not isinstance(declared, dict):
        raise ModelError(where, "evidence must be an object")
    if "assurance" in declared:
        raise ModelError(f"{where}/assurance",
                         "assurance is computed by the runtime adapter context and is never client-settable")
    if "text" in declared:
        if (store is None or set(declared) - {"kind", "text", "source_locator"}
                or declared.get("kind") != "host_attested_instruction"
                or not isinstance(declared.get("text"), str) or not declared["text"].strip()):
            raise ModelError(where, "raw instructions contain only kind=host_attested_instruction, nonempty text and source_locator")
        declared = {"kind": "host_attested_instruction",
                    "source_ref": store.put_blob(declared["text"].encode("utf-8"), ext="txt"),
                    "source_locator": declared.get("source_locator")}
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
        event = _verified_event(evidence, adapter_context, action_binding, project_id=project_id, request_id=request_id)
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
    if not models.collaboration_required(document):
        raise ModelError(
            "collaboration",
            "migration_required: this project predates the collaboration writer; "
            "run collaboration migration apply before any collaboration write",
        )
    region = document.get("collaboration")
    if region is None:
        raise ModelError("collaboration", "collaboration region missing at the collaboration.v1 writer boundary")
    return region


def _require_stored_refs(store, refs, where: str) -> None:
    """Every Ref that enters a formal record must exist in the Store
    (CONTRACTS §11: only real immutable objects may be referenced)."""
    for index, ref in enumerate(refs):
        if ref is None:
            continue
        try:
            store.read_object_bytes(ref)
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"{where}[{index}]",
                             f"referenced object is not in the store: {ref!r}") from exc


def _require_stored_evidence_refs(store, evidence: dict, where: str) -> None:
    slots = [evidence.get("source_ref"), evidence.get("transport_receipt_ref"),
             evidence.get("presentation_ref")]
    _require_stored_refs(store, [ref for ref in slots if ref], where)


def _require_scope_refs(store, scope, where):
    scope = scope or {}
    _require_stored_refs(store, [scope.get("page_manifest_ref"),
                                scope.get("external_artifact_ref")], where)
    if scope.get("page_manifest_ref"):
        manifest = store.read_object_json(scope["page_manifest_ref"])
        models.validate_content_plan_semantics(manifest)
        if manifest.get("schema_version") != "content_plan.v2":
            raise ModelError(where, "page_manifest_ref must reference content_plan.v2")


def replay_or_conflict(store, document, operation_id, action, payload_digest_value):
    """CONTRACTS §6.1 order: an already-committed operation replays its receipt
    first; a different payload under the same operation id conflicts. Callers
    invoke this before the base-revision check."""
    prior = operation_revision(store, document, operation_id)
    if prior is None:
        return None
    change = prior.get("change") or {}
    if change.get("kind") == WRITE_CHANGE_KIND and change.get("payload_digest") == payload_digest_value:
        receipt = store.operation_receipt(operation_id)
        response = receipt["response"] if receipt else _legacy_response(store, prior, action)
        return {**response, "status": "already_applied",
                "current_revision_id": document["revision_id"],
                "applied_revision_id": prior["revision_id"]}
    raise ConflictError("operation_id", "different payload already applied")


def _legacy_response(store, prior, action):
    """Recover pre-receipt T02 responses from their committed snapshot only."""
    response = {"status": "accepted", "revision_id": prior["revision_id"]}
    region = prior.get("collaboration") or {}
    request = region.get("request") or {}
    if action in (ACTION_REQUEST_START, ACTION_PAUSE, ACTION_RESUME):
        response["request_id"] = request.get("request_id")
        if action == ACTION_REQUEST_START:
            response.update(effective_scope=request.get("scope"),
                            assurance=(request.get("instruction_evidence") or {}).get("assurance"))
        return response
    parent = store.load_document(prior["parent_revision_id"])
    if action == "collaboration.migration":
        from .collaboration_migration import migration_plan, migration_response
        plan = migration_plan(store, parent)
        return {**response, **migration_response(plan, plan["tasks_to_supersede"])}
    family = "decisions" if action == ACTION_DECISION_RECORD else "authorizations"
    old = (parent.get("collaboration") or {}).get(family) or []
    for ref in region.get(family) or []:
        if ref in old:
            continue
        record = store.read_object_json(ref)
        if action == ACTION_REVOKE and record.get("status") == "revoked":
            return {**response, "revoked_ref": ref, "authorization_id": record["authorization_id"]}
        if record.get("status") == "active":
            prefix = "decision" if family == "decisions" else "authorization"
            return {**response, prefix + "_ref": ref, prefix + "_id": record[prefix + "_id"],
                    "assurance": record["evidence"]["assurance"]}
    raise StoreError("operation_receipt", "cannot recover the original collaboration response")


def commit_collaboration_change(store, document, *, operation_id, action, digest,
                                description, updated, response) -> dict:
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
    response = {"status": "accepted", **response, "revision_id": bumped["revision_id"]}
    store._commit_locked(base_revision=document["revision_id"], document=bumped,
                         operation_id=operation_id, blobs=[], operation_receipt={
                             "format": "operation_receipt.v1", "request_digest": digest,
                             "response": response})
    return response


def _region_records(store, region, family):
    records = []
    for ref in region.get(family) or []:
        try:
            records.append((ref, store.read_object_json(ref)))
        except Exception:  # noqa: BLE001 - unreadable refs cannot participate
            continue
    return records


def _head_for_identity(store, region, family, id_field, identity):
    """The version of ``identity`` the current region still references: the
    chain head that no other version replaces (CONTRACTS §3.3). Falls back to
    the last matching entry for records without a replaces chain."""
    if identity is None:
        return None
    records = _region_records(store, region, family)
    replaced_pairs = set()
    for _, record in records:
        pair = record.get("replaces")
        if isinstance(pair, dict) and pair.get("path"):
            replaced_pairs.add((pair.get("path"), pair.get("sha256")))
    heads = [(ref, record) for ref, record in records
             if record.get(id_field) == identity
             and (ref.get("path"), ref.get("sha256")) not in replaced_pairs]
    if heads:
        return heads[-1]
    return None


def _identity_of(store, ref):
    try:
        record = store.read_object_json(ref)
    except Exception:  # noqa: BLE001
        return None
    for field in ("authorization_id", "decision_id"):
        if field in record:
            return record[field]
    return None


def _index_of_ref(refs, ref) -> int:
    pair = (ref.get("path"), ref.get("sha256"))
    for index, candidate in enumerate(refs):
        if (candidate.get("path"), candidate.get("sha256")) == pair:
            return index
    return -1


def _request_source_key(request: dict) -> str:
    evidence = request.get("instruction_evidence") or {}
    locator = evidence.get("source_locator")
    source = evidence.get("source_ref") or {}
    variant = request.get("variant") or {}
    return sha256_bytes(canonical_json_bytes({
        "locator": locator,
        "source_sha256": source.get("sha256"),
        "intent": request.get("intent"),
        "content_intent": request.get("content_intent"),
        "scope": request.get("scope"),
        "variant_id": variant.get("variant_id"),
        "variant_group_id": variant.get("group_id"),
    }))


def _matching_request_source(store, document, candidate):
    """Read committed ancestry, not a disposable replay/source cache.

    A match identifies the original request; its latest committed state and the
    current control remain separate. Replaying a superseded source never
    reopens that request, restores its grants or creates a new credit identity.
    """
    from .snapshots import committed_snapshots
    histories = [document]
    if store.current_revision_id() is not None:
        histories.extend(committed_snapshots(store))
    requests = [(snapshot, (snapshot.get('collaboration') or {}).get('request')) for snapshot in histories]
    source_key = _request_source_key(candidate)
    match = next(((snapshot, request) for snapshot, request in requests
        if request and _request_source_key(request) == source_key), None)
    if match is None:
        return None
    _, original = match
    latest_snapshot, latest = next((snapshot, request) for snapshot, request in requests
        if request and request['request_id'] == original['request_id'])
    current = (document.get('collaboration') or {}).get('request')
    current_id = (current or {}).get('request_id')
    state = ('closed' if latest.get('closed') else 'superseded' if latest['request_id'] != current_id
        else 'paused' if latest.get('paused') else 'open')
    return {'status': 'already_started', 'request_id': latest['request_id'],
        'request_source_key': source_key, 'request_state': state,
        'request': copy.deepcopy(latest), 'effective_scope': copy.deepcopy(latest['scope']),
        'request_revision_id': latest_snapshot['revision_id'],
        'current_request_id': current_id, 'current_request': copy.deepcopy(current),
        'revision_id': document['revision_id'], 'creates_request': False, 'refreshes_credit': False}


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
    result["request_source_key"] = _request_source_key(region["request"]) if region.get("request") else None
    result["decisions"] = [record for _, record in _region_records(store, region, "decisions")]
    result["authorizations"] = [record for _, record in _region_records(store, region, "authorizations")]
    result["effective_decisions"] = [{"ref": ref, "record": record,
        **dependency_slices.decision_effectiveness(store, document, ref)}
        for ref, record in _region_records(store, region, "decisions")]
    result["effective_authorizations"] = [{"ref": ref, "record": record,
        **dependency_slices.authorization_effectiveness(store, document, ref)}
        for ref, record in _region_records(store, region, "authorizations")]
    from . import eligibility
    result["blocking_cards"] = []
    for action in ("dispatch.compose", "dispatch.blueprint", "export.delivery"):
        decision = eligibility.evaluate(store, document, document, action)
        if not decision["allowed"]:
            result["blocking_cards"].append({"action": action, "decision": decision})
    return result


def _stage_request(store, document, input, *, operation_id, digest, adapter_context=None):
    """Validate and stage the common request change for one owning transaction."""
    region = _require_region(store, document)
    transition = input.get("variant_transition") or {}
    if transition.get("kind") == "edit_variant" and input.get("variant") is None:
        from .snapshots import load_snapshot
        source = transition.get("source") or {}
        selected = load_snapshot(store, source.get("revision_id"))
        variant = ((selected.get("collaboration") or {}).get("request") or {}).get("variant")
        if not variant:
            raise ModelError("variant_transition/source", "the selected committed source has no variant")
        input = {**input, "variant": copy.deepcopy(variant)}
    declared = input.get("instruction_evidence")
    evidence = resolve_evidence(declared, adapter_context, store=store,
                                where="collaboration/request/instruction_evidence",
                                action_binding=digest, project_id=document["project_id"],
                                request_id=(region.get("request") or {}).get("request_id"))
    _require_stored_evidence_refs(store, evidence, "collaboration/request/instruction_evidence")
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
    _require_scope_refs(store, candidate["scope"], "collaboration/request/scope")
    if input.get("request_source_key") is not None and input["request_source_key"] != _request_source_key(candidate):
        raise ModelError("collaboration/request/request_source_key", "does not match the Runtime-computed source key")
    same_source = _matching_request_source(store, document, candidate)
    if same_source:
        return None, same_source
    if current is not None and not current.get("closed"):
        if replace_request_id != current.get("request_id"):
            raise ModelError(
                "collaboration/request",
                "an open request must be explicitly replaced: pass replace_request_id "
                "naming the current request",
            )
    elif replace_request_id is not None and (current is None or current.get("request_id") != replace_request_id):
        raise ModelError("collaboration/request/replace_request_id",
                         "replace_request_id must name the current open request")
    if input.get("variant") is not None:
        from .variant_requests import validate_variant_request
        posture = validate_variant_request(store, document, input,
                                 replace_request_id=replace_request_id)
        if posture["already_fixed"] and not input.get("variant_transition"):
            raise ModelError("variant_transition", "variant_source_required: select a fixed revision and versioned export for the sequential transition")
        if current is not None and not current.get("closed"):
            from .variant_requests import shared_narrative_check
            group = (input["variant"] or {}).get("group_id")
            check = shared_narrative_check(store, document, group)
            if not check["ok"]:
                raise ModelError("collaboration/request/variant/narrative_ref", check["reason"])
    updated_region = {**region, "request": candidate}
    updated = {**document, "collaboration": updated_region}
    response = {"request_id": candidate["request_id"], "request_source_key": _request_source_key(candidate),
                "effective_scope": candidate["scope"],
                "assurance": evidence["assurance"]}
    if current is not None and current.get("request_id") != candidate["request_id"]:
        # Replace (CONTRACTS §12): the old request's unfinished scope stops
        # by default — its authorizations are reported as no longer
        # executable and its open tasks as affected. Only the explicitly
        # listed background ids keep running.
        background = set(candidate.get("background_request_ids") or [])
        paused = [record.get("authorization_id")
                  for _, record in _region_records(store, region, "authorizations")
                  if record.get("request_id") == current.get("request_id")
                  and record.get("request_id") not in background]
        response["prior_request_disposition"] = {
            "request_id": current.get("request_id"),
            "disposition": "superseded",
            "background_request_ids": sorted(background),
        }
        response["paused_authorizations"] = sorted(paused)
        affected = []
        unbound = []
        for ref in document.get("tasks") or []:
            try:
                task = store.read_object_json(ref)
            except Exception:  # noqa: BLE001 - unreadable tasks cannot be affected
                continue
            if task.get("status") not in ("awaiting_host", "running", "queued"):
                continue
            task_request = (task.get("collaboration_binding") or {}).get("request_id")
            if task_request is None:
                # A still-active task without a binding cannot be attributed
                # to the request it belongs to, so it is reported as affected
                # too — it can no longer be accepted as production, only
                # settled. The report never pretends it was covered before.
                affected.append(task.get("task_id"))
                unbound.append({"task_id": task.get("task_id"),
                                "status": task.get("status"),
                                "reason": "no_collaboration_binding",
                                "handling": "only settled call facts remain; "
                                            "re-dispatch through the collaboration-aware path"})
                continue
            if task_request == current.get("request_id") and task_request not in background:
                affected.append(task.get("task_id"))
        response["affected_tasks"] = sorted(affected)
        affected_ids = set(affected)
        retired = []
        for ref in document.get('tasks') or []:
            try:
                task = store.read_object_json(ref)
            except (StoreError, OSError, ValueError, TypeError):
                retired.append(ref)
                continue
            retired.append(store.put_json_object({**task, 'status': 'superseded', 'updated_at': _now_iso()})
                if task.get('task_id') in affected_ids else ref)
        updated['tasks'] = retired
        if unbound:
            response["unbound_tasks"] = unbound
    if input.get("variant_transition") is not None:
        from .variant_requests import apply_transition
        updated, transition = apply_transition(store, document, updated, input)
        response["variant_transition"] = transition
    models.validate_collaboration_region(updated["collaboration"])
    return updated, response


def start_request(project, *, input: dict, base_revision: str, operation_id: str,
                  adapter_context=None) -> dict:
    store = Store(Path(project).expanduser())
    digest = write_digest(ACTION_REQUEST_START, input)
    @tasks_mod._project_transaction
    def locked(store):
        document = store.load_document()
        replay = replay_or_conflict(store, document, operation_id, ACTION_REQUEST_START, digest)
        if replay:
            return replay
        from . import eligibility
        eligibility.guard(store, document, "request.start")
        if document["revision_id"] != base_revision:
            raise ConflictError("base_revision", "base revision is not current; reload and retry")
        updated, response = _stage_request(store, document, input, operation_id=operation_id,
            digest=digest, adapter_context=adapter_context)
        if updated is None:
            updated = document
        return commit_collaboration_change(store, document, operation_id=operation_id,
            action=ACTION_REQUEST_START, digest=digest, description="start work request",
            updated=updated, response=response)
    return locked(store)


def prepare_decision(store, document, *, input, operation_id, evidence):
    """Validate a proposed decision without storage, locks, or authority issuance."""
    from . import eligibility
    eligibility.guard(store, document, "decision.record")
    region = _require_region(store, document)
    request = region.get("request")
    if request is None or request.get("closed"):
        raise ModelError("collaboration/request", "a decision requires the current open work request")
    topic = input.get("topic")
    delegation_ref = input.get("delegation_ref")
    authority_mode = input.get("authority_mode")
    _require_stored_evidence_refs(store, evidence, "collaboration/decision/evidence")
    basis = dependency_slices.merge_required_basis(
        store, document, family="decision", key=topic,
        provided=input.get("basis") or [])
    subject_refs = list(input.get("subject_refs") or [])
    # Each entry is a ProposalRef {artifact_kind, artifact_ref, projection};
    # the stored object to check is its artifact_ref.
    _require_stored_refs(store, [proposal.get("artifact_ref") for proposal in subject_refs],
                         "collaboration/decision/subject_refs")
    decision_id = input.get("decision_id") or _stable_id("dec", operation_id)
    existing = [(ref, record) for ref, record in _region_records(store, region, "decisions")
                if record.get("decision_id") == decision_id]
    replaces_ref = input.get("replaces")
    replaced_index = -1
    replaced_record = None
    if replaces_ref is None:
        if existing:
            raise ModelError("decision/replaces",
                             "this decision identity already exists in the current region; "
                             "pass replaces to write a new version")
    else:
        refs = list(region.get("decisions") or [])
        replaced_index = _index_of_ref(refs, replaces_ref)
        replaced_record = next((record for ref, record in existing
                                if (ref.get("path"), ref.get("sha256")) ==
                                (replaces_ref.get("path"), replaces_ref.get("sha256"))), None)
        if replaced_index < 0 or replaced_record is None:
            raise ModelError("decision/replaces",
                             "replaces must name a version of this decision identity "
                             "in the current region")
    decision = {
        "schema_version": "collaboration_decision.v1",
        "decision_id": decision_id,
        "project_id": document["project_id"],
        "request_id": request["request_id"],
        "topic": topic,
        "subject_refs": subject_refs,
        "scope": input.get("scope") or request.get("scope"),
        "value": input.get("value"),
        "disposition": input.get("disposition"),
        "authority_mode": authority_mode,
        "evidence": evidence,
        "delegation_ref": delegation_ref,
        "basis": basis,
        "status": "active",
        "replaces": replaces_ref,
        "invalidated_by": None,
        "created_at": _now_iso(),
    }
    models.validate_decision_semantics(decision)
    _require_scope_refs(store, decision["scope"], "collaboration/decision/scope")
    if authority_mode == "delegated":
        _validate_delegation(store, document, region, delegation_ref, decision)
    return region, decision, replaced_index, replaced_record


def record_decision(project, *, input: dict, base_revision: str, operation_id: str,
                    adapter_context=None) -> dict:
    """Record a decision as an immutable object referenced by the region
    (CONTRACT §3.1). Client assurance upgrades are rejected by resolve_evidence;
    the service completes the registered minimum basis so callers cannot omit
    a registered dependency (TASKS T02 item 4)."""
    store = Store(Path(project).expanduser())
    digest = write_digest(ACTION_DECISION_RECORD, input)

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        from . import eligibility
        eligibility.guard(store, document, "decision.record")
        replay = replay_or_conflict(store, document, operation_id, ACTION_DECISION_RECORD, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        if region.get("request") is None or region["request"].get("closed"):
            raise ModelError("collaboration/request", "a decision requires the current open work request")
        evidence = resolve_evidence(input.get("instruction_evidence"), adapter_context, store=store,
            where="collaboration/decision/evidence", action_binding=digest,
            project_id=document["project_id"], request_id=(region.get("request") or {}).get("request_id"))
        region, decision, replaced_index, replaced_record = prepare_decision(
            store, document, input=input, operation_id=operation_id, evidence=evidence)
        decision_id, topic = decision["decision_id"], decision["topic"]
        evidence = decision["evidence"]
        decision_ref = store.put_json_object(decision)
        updated_refs = list(region.get("decisions") or [])
        if replaced_record is not None:
            retirement = {**replaced_record, "status": "superseded",
                          "invalidated_by": operation_id}
            models.validate_decision_semantics(retirement)
            updated_refs[replaced_index] = store.put_json_object(retirement)
        updated_refs.append(decision_ref)
        updated_region = {**region, "decisions": updated_refs}
        updated = {**document, "collaboration": updated_region}
        from .content_review import apply_requirement_decision
        updated = apply_requirement_decision(store, updated, decision, decision_ref, previous_document=document)
        return commit_collaboration_change(store, document, operation_id=operation_id,
                                                action=ACTION_DECISION_RECORD, digest=digest,
                                                description=f"record decision {decision_id} ({topic})",
                                                updated=updated, response={"decision_ref": decision_ref,
                                                    "decision_id": decision_id, "assurance": evidence["assurance"]})

    return locked(store)


def grant(project, *, input: dict, base_revision: str, operation_id: str,
          adapter_context=None) -> dict:
    """Record an execute/delegate authorization (CONTRACT §3.2). Sub-grants
    cannot exceed their parent delegation's scope, topics, evidence level or
    effectiveness; a new version of the same identity replaces the old one."""
    store = Store(Path(project).expanduser())
    digest = write_digest(ACTION_GRANT, input)

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        from . import eligibility
        eligibility.guard(store, document, "authorization.grant")
        replay = replay_or_conflict(store, document, operation_id, ACTION_GRANT, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        request = region.get("request")
        if request is None or request.get("closed"):
            raise ModelError("collaboration/request", "a grant requires the current open work request")
        evidence = resolve_evidence(input.get("instruction_evidence"), adapter_context, store=store,
                                    where="collaboration/authorization/evidence",
                                    action_binding=digest, project_id=document["project_id"],
                                    request_id=(region.get("request") or {}).get("request_id"))
        _require_stored_evidence_refs(store, evidence, "collaboration/authorization/evidence")
        basis = dependency_slices.merge_required_basis(
            store, document, family="authorization", key=input.get("mode"),
            provided=input.get("basis") or [])
        authorization_id = input.get("authorization_id") or _stable_id("authz", operation_id)
        replaces_ref = input.get("replaces")
        refs = list(region.get("authorizations") or [])
        replaced_index = -1
        if replaces_ref is None:
            if _head_for_identity(store, region, "authorizations", "authorization_id",
                                  authorization_id) is not None:
                raise ModelError("authorization/replaces",
                                 "this authorization identity already exists in the current region; "
                                 "pass replaces to write a new version")
        else:
            replaced_index = _index_of_ref(refs, replaces_ref)
            if replaced_index < 0:
                raise ModelError("authorization/replaces",
                                 "replaces must name a version of this authorization in the current region")
            replaced_record = store.read_object_json(replaces_ref)
            if replaced_record.get("authorization_id") != authorization_id:
                raise ModelError("authorization/replaces",
                                 "replaces must name a version of the same authorization identity")
        authorization = {
            "schema_version": "collaboration_authorization.v1",
            "authorization_id": authorization_id,
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
            "basis": basis,
            "parent_authorization_ref": input.get("parent_authorization_ref"),
            "replaces": replaces_ref,
            "status": "active",
            "expires_at": input.get("expires_at"),
            "stop_conditions": list(input.get("stop_conditions") or []),
            "created_at": _now_iso(),
        }
        from .collaboration_budget import prepare_grant
        computed_budget = prepare_grant(store, document, authorization, input)
        if authorization.get('parent_authorization_ref') and not authorization.get('budget_parent_ref'):
            authorization['budget_parent_ref'] = authorization['parent_authorization_ref']
        numeric_parent_ref = authorization.get('budget_parent_ref')
        if numeric_parent_ref:
            numeric_parent = eligibility.current_authorization_record(store, document, numeric_parent_ref)
            if (numeric_parent.get('schema_version') != 'collaboration_authorization.v1'
                    or numeric_parent.get('project_id') != document['project_id']
                    or numeric_parent.get('request_id') != request['request_id']):
                raise ModelError('authorization/budget_parent_ref', 'the numeric parent must belong to this project and request')
            # This is a numeric ledger link, not an authority inheritance.
            # Withdrawn roots retain their cap/consumption; fresh explicit
            # authority may share that budget without reviving the old grant.
            if not computed_budget or not eligibility._planning_only_zero_authority(store, numeric_parent, document=document):
                if authorization['max_external_calls'] > numeric_parent['max_external_calls']:
                    raise ModelError('authorization/max_external_calls', 'a child cannot increase its numeric parent ceiling')
        authority_parent_ref = authorization.get('parent_authorization_ref')
        if authority_parent_ref:
            authority_parent = eligibility.current_authorization_record(store, document, authority_parent_ref)
            if (authority_parent['max_external_calls'] and numeric_parent_ref
                    and eligibility._chain_root_identity(store, document, authority_parent)
                    != eligibility._chain_root_identity(store, document, store.read_object_json(numeric_parent_ref))):
                raise ModelError('authorization/budget_parent_ref', 'a child must share its numeric authority parent root')
            if not computed_budget or not eligibility._planning_only_zero_authority(store, authority_parent, document=document):
                if authorization['max_external_calls'] > authority_parent['max_external_calls']:
                    raise ModelError('authorization/max_external_calls', 'a child cannot increase its parent ceiling')
            if authorization['max_candidate_count'] > authority_parent['max_candidate_count']:
                raise ModelError('authorization/max_candidate_count', 'a child cannot increase its parent candidate ceiling')
        if replaces_ref:
            for quantity in ('max_external_calls', 'max_candidate_count'):
                old_root = eligibility._chain_root_identity(store, document, replaced_record, quantity=quantity)
                new_root = eligibility._chain_root_identity(store, document, authorization, quantity=quantity)
                if old_root != new_root:
                    raise ModelError('authorization/budget_parent_ref', 'a replacement cannot move historical consumption to another numeric root')
        if authorization['delivery_binding'] == 'exact_artifact':
            from .delivery_eligibility import selected_output
            selected = selected_output(store, document, notes_policy=(input.get('constraints') or {}).get('delivery_notes_policy'))
            if not selected.get('file_sha256'):
                raise ModelError('authorization/delivery_binding', 'exact_artifact requires the actual current output')
            authorization['constraints']['fixed_delivery'] = {
                'artifact_ref': document['outputs']['pptx'], 'subject_ref': selected['subject_ref'],
                'file_sha256': selected['file_sha256'], 'notes_policy': selected['notes_policy'],
                'source_request_id': request['request_id']}
            for kind, identity, projection in [('task_fact', 'brief', 'value'), ('task_fact', 'audience', 'value'),
                    ('artifact', 'pptx', 'content')]:
                dep = dependency_slices.make_dependency_slice(store, document, kind=kind, identity=identity, projection=projection)
                if dep not in authorization['basis']:
                    authorization['basis'].append(dep)
        elif 'fixed_delivery' in authorization['constraints']:
            raise ModelError('authorization/constraints/fixed_delivery', 'fixed file bindings are computed by the Runtime')
        models.validate_authorization_semantics(authorization)
        _require_scope_refs(store, authorization["scope"], "collaboration/authorization/scope")
        _require_stored_refs(store, authorization["decision_refs"], "collaboration/authorization/decision_refs")
        for ref in authorization["decision_refs"]:
            decision = store.read_object_json(ref)
            if (decision.get("schema_version") != "collaboration_decision.v1"
                    or decision.get("project_id") != document["project_id"]
                    or not dependency_slices.accepted_decision(store, document, ref)):
                raise ModelError("authorization/decision_refs", "decision must have accepted authority in the current project")
            dep = dependency_slices.make_dependency_slice(store, document, kind="decision",
                identity=decision["decision_id"], projection="effective")
            if not any(dependency_slices.slice_key(item) == dependency_slices.slice_key(dep) for item in basis):
                basis.append(dep)
        _require_stored_refs(store, [authorization.get("budget_parent_ref")],
                             "collaboration/authorization/budget_parent_ref")
        _validate_parent_chain(store, document, region, authorization)
        authorization_ref = store.put_json_object(authorization)
        updated_refs = list(refs)
        if replaced_index >= 0:
            updated_refs[replaced_index] = authorization_ref
        else:
            updated_refs.append(authorization_ref)
        updated_region = {**region, "authorizations": updated_refs}
        updated = {**document, "collaboration": updated_region}
        return commit_collaboration_change(store, document, operation_id=operation_id,
                                                action=ACTION_GRANT, digest=digest,
                                                description=f"grant {authorization_id} "
                                                            f"({authorization['mode']})",
                                                updated=updated, response={"authorization_ref": authorization_ref,
                                                    "authorization_id": authorization_id,
                                                    "assurance": evidence["assurance"],
                                                    **({"budget": computed_budget} if computed_budget else {})})

    return locked(store)


def revoke_authorization(project, *, authorization_id: str, reason: str, base_revision: str,
                         operation_id: str, adapter_context=None,
                         instruction_evidence: dict | None = None) -> dict:
    """Revoke an authorization by writing a new version that replaces the
    current one; the original record stays in history (CONTRACT §3.3)."""
    store = Store(Path(project).expanduser())
    digest = write_digest(ACTION_REVOKE, {"authorization_id": authorization_id,
                                          "reason": reason,
                                          "instruction_evidence": instruction_evidence})

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        from . import eligibility
        eligibility.guard(store, document, "authorization.revoke")
        replay = replay_or_conflict(store, document, operation_id, ACTION_REVOKE, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        if not (reason or "").strip():
            raise ModelError("collaboration/revoke/reason", "a revocation records its reason")
        if instruction_evidence is not None:
            evidence = resolve_evidence(instruction_evidence, adapter_context, store=store,
                                        where="collaboration/revoke/evidence",
                                        action_binding=digest, project_id=document["project_id"],
                                    request_id=(region.get("request") or {}).get("request_id"))
            _require_stored_evidence_refs(store, evidence, "collaboration/revoke/evidence")
        head = _head_for_identity(store, region, "authorizations", "authorization_id", authorization_id)
        if head is None:
            raise ModelError("collaboration/authorizations",
                             f"no authorization {authorization_id!r} in the current region")
        head_ref, target = head
        if target.get("status") == "revoked":
            return commit_collaboration_change(store, document, operation_id=operation_id,
                action=ACTION_REVOKE, digest=digest, description="record already revoked request",
                updated=document, response={"status": "already_revoked", "authorization_id": authorization_id})
        revoked = {**target, "status": "revoked", "replaces": head_ref}
        models.validate_authorization_semantics(revoked)
        revoked_ref = store.put_json_object(revoked)
        refs = list(region.get("authorizations") or [])
        refs[_index_of_ref(refs, head_ref)] = revoked_ref
        updated_region = {**region, "authorizations": refs}
        updated = {**document, "collaboration": updated_region}
        return commit_collaboration_change(store, document, operation_id=operation_id,
                                                action=ACTION_REVOKE, digest=digest,
                                                description=f"revoke authorization "
                                                            f"{authorization_id}: {reason.strip()}",
                                                updated=updated, response={"authorization_id": authorization_id,
                                                    "revoked_ref": revoked_ref})

    return locked(store)


def pause_request(project, *, reason: str, base_revision: str, operation_id: str,
                  adapter_context=None, instruction_evidence: dict | None = None, request_id=None) -> dict:
    """Pause the current request; reads keep working, new production stops
    being eligible (enforcement in T04)."""
    return _set_pause(project, paused=True, reason=reason, base_revision=base_revision,
                      operation_id=operation_id, adapter_context=adapter_context,
                      instruction_evidence=instruction_evidence, request_id=request_id)


def resume_request(project, *, instruction_evidence: dict, base_revision: str,
                   operation_id: str, adapter_context=None, request_id=None) -> dict:
    """Resume the paused request. It never widens scope: eligibility re-derives
    from the unchanged request (CONTRACT §7.1). A resume requires its explicit
    instruction evidence — "继续" is a user action we must be able to trace."""
    if instruction_evidence is None:
        raise ModelError("collaboration/request/resume/evidence",
                         "a resume requires instruction evidence")
    return _set_pause(project, paused=False, reason=None, base_revision=base_revision,
                      operation_id=operation_id, adapter_context=adapter_context,
                      instruction_evidence=instruction_evidence, request_id=request_id)


def _set_pause(project, *, paused: bool, reason, base_revision: str, operation_id: str,
               adapter_context=None, instruction_evidence=None, request_id=None) -> dict:
    store = Store(Path(project).expanduser())
    action = ACTION_PAUSE if paused else ACTION_RESUME
    digest = write_digest(action, {"reason": reason, "instruction_evidence": instruction_evidence, "request_id": request_id})

    @tasks_mod._project_transaction
    def locked(store: Store):
        document = store.load_document()
        from . import eligibility
        eligibility.guard(store, document,
                          "request.pause" if paused else "request.resume")
        replay = replay_or_conflict(store, document, operation_id, action, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = _require_region(store, document)
        request = region.get("request")
        if request is None or request.get("closed"):
            raise ModelError("collaboration/request", "no open request to pause or resume")
        if request_id is not None and request_id != request["request_id"]:
            raise ConflictError("request_id", "the current request changed")
        if paused and not (reason or "").strip():
            raise ModelError("collaboration/request/pause_reason", "pausing records its reason")
        if bool(request.get("paused")) == paused:
            return commit_collaboration_change(store, document, operation_id=operation_id,
                action=action, digest=digest, description="record unchanged pause state",
                updated=document, response={"status": "already_paused" if paused else "already_active",
                                            "request_id": request["request_id"]})
        if instruction_evidence is not None:
            evidence = resolve_evidence(
                instruction_evidence, adapter_context, store=store,
                where=f"collaboration/request/{'pause' if paused else 'resume'}/evidence",
                action_binding=digest, project_id=document["project_id"],
                                    request_id=(region.get("request") or {}).get("request_id"))
            _require_stored_evidence_refs(
                store, evidence,
                f"collaboration/request/{'pause' if paused else 'resume'}/evidence")
        updated_request = {**request, "paused": paused,
                           "pause_reason": reason.strip() if paused else None}
        updated_region = {**region, "request": updated_request}
        updated = {**document, "collaboration": updated_region}
        return commit_collaboration_change(
            store, document, operation_id=operation_id, action=action, digest=digest,
            description="pause request: " + reason.strip() if paused else "resume request",
            updated=updated, response={"request_id": request["request_id"]})

    return locked(store)


# ---------------------------------------------------------------------------
# Delegation checks


def _validate_delegation(store, document, region, delegation_ref, decision) -> None:
    """A delegated decision must trace to a still-effective delegate covering
    the topic and bound to the same current request (CONTRACTS §3.1)."""
    if delegation_ref is None:
        raise ModelError("decision/delegation_ref",
                         "a delegated decision must reference an authorization in the current region")
    head = _head_for_identity(store, region, "authorizations", "authorization_id",
                              _identity_of(store, delegation_ref))
    if head is None:
        raise ModelError("decision/delegation_ref",
                         "a delegated decision must reference an authorization in the current region")
    _, target = head
    request = region.get("request") or {}
    if target.get("request_id") != request.get("request_id"):
        raise ModelError("decision/delegation_ref",
                         "the delegation belongs to a superseded request")
    state = dependency_slices.authorization_effectiveness(store, document, delegation_ref)
    if not state["effective"]:
        raise ModelError("decision/delegation_ref",
                         f"the referenced delegation is not effective: {state['reasons']}")
    gaps = delegation_gaps(store, target, decision, decision=True)
    if gaps:
        raise ModelError("decision/delegation_ref",
                         f"the referenced delegation is not an active delegate covering this topic and scope: {gaps}")


def _validate_parent_chain(store, document, region, authorization) -> None:
    """A derived authorization needs an effective delegate parent and cannot
    exceed its scope, topics or evidence level (CONTRACTS §3.2, §7.1)."""
    parent_ref = authorization.get("parent_authorization_ref")
    if parent_ref is None:
        return
    head = _head_for_identity(store, region, "authorizations", "authorization_id",
                              _identity_of(store, parent_ref))
    if head is None:
        raise ModelError("authorization/parent_authorization_ref",
                         "a derived authorization must reference its delegate parent in the current region")
    _, parent = head
    parent_state = dependency_slices.authorization_effectiveness(store, document, parent_ref)
    if not parent_state["effective"]:
        raise ModelError("authorization/parent_authorization_ref",
                         f"parent delegation is not effective: {parent_state['reasons']}")
    gaps = delegation_gaps(store, parent, authorization)
    if gaps:
        if "scope/page_ids" in gaps:
            raise ModelError("authorization/scope/page_ids", "a sub-authorization cannot name pages beyond its parent delegation")
        if "scope/layers" in gaps:
            raise ModelError("authorization/scope/layers", "a sub-authorization cannot exceed the parent's layers")
        if "delegated_topics" in gaps:
            raise ModelError("authorization/delegated_topics", "a sub-authorization cannot delegate topics its parent does not cover")
        if "evidence/assurance" in gaps:
            raise ModelError("authorization/evidence/assurance", "a sub-authorization cannot claim stronger assurance than its parent")
        raise ModelError("authorization/parent_authorization_ref",
                         f"a sub-authorization cannot exceed its parent: {gaps}")
