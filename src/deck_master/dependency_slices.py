"""Registered dependency slices and semantic invalidation (content
collaboration v1.2 CONTRACTS §7, AC-C03).

A DependencySlice pins one registered semantic projection with its canonical
digest. Decisions and authorizations carry `basis: [DependencySlice]`; whether
they still apply is *computed* against the current document, never stored as a
second truth. Only registered (kind, projection) pairs exist — callers cannot
invent slices — and the same rule set serves both record writers (via
make_dependency_slice) and the eligibility resolver T04 builds on top.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import ModelError, canonical_json_bytes, sha256_bytes, parse_authorization_expiry
from .collaboration_scope import delegation_gaps

TASK_FACT_IDENTITIES = ("audience", "brief", "scenario", "presentation_mode", "page_limit", "existing_decisions")
_MAX_PARENT_DEPTH = 8

# Central minimum-basis registry (CONTRACTS §7, TASKS T02 item 4): the service
# completes these when a decision/authorization is recorded, so callers cannot
# omit a registered dependency. T04's eligibility resolver consumes the same
# registry for read paths.
REQUIRED_BASIS: dict[tuple[str, str], tuple[tuple[str, str, str], ...]] = {
    ("decision", "direction"): (("task_fact", "audience", "value"),
                                 ("task_fact", "brief", "value"),
                                 ("task_fact", "scenario", "value"),
                                 ("task_fact", "existing_decisions", "value")),
    ("decision", "manuscript"): (("task_fact", "brief", "value"),
                                  ("task_fact", "page_limit", "value")),
    ("decision", "speech"): (("task_fact", "presentation_mode", "value"),),
    ("decision", "tradeoff"): (("task_fact", "page_limit", "value"),),
    ("authorization", "execute"): (("policy", "document", "value"),),
    ("authorization", "delegate"): (("policy", "document", "value"),),
    # Task dispatch basis per content phase (CONTRACTS §7): the facts a phase
    # actually reads. Narrative/Plan pointer slices are appended when they exist
    # (collaboration_binding.binding_basis), never required into absence.
    ("task", "framing"): (("task_fact", "brief", "value"),
                           ("task_fact", "audience", "value"),
                           ("task_fact", "scenario", "value"),
                           ("task_fact", "existing_decisions", "value")),
    ("task", "argument"): (("task_fact", "brief", "value"),
                            ("task_fact", "audience", "value"),
                            ("task_fact", "scenario", "value"),
                            ("task_fact", "existing_decisions", "value")),
    ("task", "page_copy"): (("task_fact", "brief", "value"),
                             ("task_fact", "page_limit", "value")),
    ("task", "speech"): (("task_fact", "presentation_mode", "value"),),
}


def required_basis(family: str, key: str) -> tuple[tuple[str, str, str], ...]:
    return REQUIRED_BASIS.get((family, key), ())


def merge_required_basis(store, document, *, family: str, key: str, provided) -> list[dict]:
    """Provided slices plus every registered minimum for (family, key)."""
    merged = list(provided or [])
    present = {(dep.get("kind"), dep.get("identity"), dep.get("projection")) for dep in merged}
    for kind, identity, projection in required_basis(family, key):
        if (kind, identity, projection) not in present:
            merged.append(make_dependency_slice(store, document, kind=kind, identity=identity,
                                                projection=projection))
    return merged


def _canonical(value) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _find_page(document, page_id):
    for entry in document.get("pages") or []:
        if entry.get("page_id") == page_id:
            return entry
    return None


def _region_records(store, region, family):
    records = []
    for ref in region.get(family) or []:
        try:
            records.append((ref, store.read_object_json(ref)))
        except Exception:  # noqa: BLE001 - unreadable records are simply absent
            continue
    return records


def _select_head(records, id_field, identity):
    """Last matching record not replaced by a complete (path, sha256) pair."""
    if identity is None:
        return None
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


def _head_for_identity(store, document, family, id_field, identity):
    if identity is None:
        return None
    return _select_head(_region_records(store, document.get('collaboration') or {}, family), id_field, identity)




def _semantic_refs(value):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            return {"sha256": value["sha256"]}
        return {key: _semantic_refs(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_semantic_refs(item) for item in value]
    return value


def _record_projection(store, record, fields, sets):
    value = {key: record.get(key) for key in fields}
    scope = dict(value.get("scope") or {})
    for key in ("page_ids", "layers"):
        scope[key] = sorted(scope.get(key) or [])
    if scope.get("page_manifest_ref"):
        plan = store.read_object_json(scope["page_manifest_ref"])
        scope["page_manifest_ref"] = {"page_order": (plan.get("input") or {}).get("page_order")}
    value["scope"] = scope
    value = _semantic_refs(value)
    for key in sets:
        value[key] = sorted(value.get(key) or [], key=canonical_json_bytes)
    return value


def _decision_projection(store, record) -> dict:
    return _record_projection(store, record, (
        "topic", "disposition", "value", "status", "scope", "authority_mode",
        "evidence", "subject_refs", "request_id"), ("subject_refs",))


def _authorization_projection(store, record) -> dict:
    return _record_projection(store, record, (
        "mode", "actions", "scope", "delegated_topics", "constraints",
        "max_external_calls", "max_candidate_count", "budget_template", "budget_key",
        "adoption_policy", "delivery_binding", "status", "expires_at", "stop_conditions",
        "evidence", "request_id"), ("actions", "delegated_topics", "stop_conditions"))


def build_slice(store, document, *, kind, identity, projection, _seen=frozenset(), now=None):
    """Current value of one registered slice, or None when the target is absent
    or the (kind, projection) pair is not registered."""
    if kind == "artifact" and projection == "page_semantics" and identity.startswith("page:"):
        entry = _find_page(document, identity.split(":", 1)[1])
        if not entry:
            return None
        from .design_requirements import page_semantic_projection
        return {"ref": entry["page"], "sha256": _canonical(page_semantic_projection(store.read_object_json(entry["page"])))}
    if kind == "artifact" and projection in ("plan_page", "plan_progression"):
        ref = document.get("content_plan")
        if ref is None:
            return None
        from .design_requirements import plan_page_projection, plan_global_projection
        plan = store.read_object_json(ref)
        if projection == "plan_progression" and identity == "content_plan":
            return {"ref": ref, "sha256": _canonical(plan_global_projection(plan))}
        if projection == "plan_page" and identity.startswith("plan:"):
            pid = identity.split(":", 1)[1]
            if pid not in (plan.get("input") or {}).get("page_order", []):
                return None
            return {"ref": ref, "sha256": _canonical(plan_page_projection(plan, pid))}
        return None
    if kind == "artifact" and projection == "visual_input" and identity.startswith("page:"):
        entry = _find_page(document, identity.split(":", 1)[1])
        if not entry or not entry.get("page"):
            return None
        from .visual_dependencies import page_visual_digest
        return {"ref": entry["page"], "sha256": page_visual_digest(store.read_object_json(entry["page"]))}
    if kind == "artifact" and projection == "visual_role" and identity.startswith("plan:"):
        from .visual_dependencies import plan_visual_projection
        value = plan_visual_projection(store, document, [identity.split(":", 1)[1]])
        return None if value is None else {"ref": document["content_plan"], "sha256": _canonical(value)}
    if kind == "task_fact" and projection == "value" and identity in TASK_FACT_IDENTITIES:
        value = (document.get("task") or {}).get(identity)
        return {"ref": None, "sha256": _canonical({"task_fact": identity, "value": value})}
    if kind == "policy" and projection == "value" and identity == "document":
        return {"ref": None, "sha256": _canonical({"policy": document.get("policy") or {}})}
    if kind == "artifact" and projection == "content":
        if identity == "pptx":
            ref = (document.get("outputs") or {}).get("pptx")
            if not ref:
                return None
            try:
                return {"ref": ref, "sha256": store.read_object_json(ref)["file"]["sha256"]}
            except Exception:  # noqa: BLE001
                return None
        if identity in ("narrative", "content_plan"):
            # Current pointer slices: absent means absent, never satisfied.
            ref = document.get(identity)
            if not ref:
                return None
            return {"ref": ref, "sha256": ref["sha256"]}
        if identity.startswith("page:"):
            entry = _find_page(document, identity.split(":", 1)[1])
            if not entry or not entry.get("page"):
                return None
            return {"ref": entry["page"], "sha256": entry["page"]["sha256"]}
        return None
    if kind == "source" and projection == "extract":
        for entry in document.get("sources") or []:
            if entry.get("source_id") != identity:
                continue
            extract = entry.get("extract")
            if extract:
                return {"ref": extract, "sha256": extract["sha256"]}
            if entry.get("original_sha256"):
                return {"ref": None, "sha256": entry["original_sha256"]}
            return None
        return None
    if kind == "decision" and projection == "effective":
        head = _head_for_identity(store, document, "decisions", "decision_id", identity)
        if head is None:
            return None
        ref, record = head
        state = decision_effectiveness(store, document, ref, _seen=_seen, now=now)
        return {"ref": None, "sha256": _canonical({"decision": _decision_projection(store, record), "state": state}),
                "effective": state["effective"]}
    if kind == "authorization" and projection == "effective":
        head = _head_for_identity(store, document, "authorizations", "authorization_id", identity)
        if head is None:
            return None
        ref, record = head
        state = authorization_effectiveness(store, document, ref, _seen=_seen, now=now)
        return {"ref": None, "sha256": _canonical({"authorization": _authorization_projection(store, record), "state": state}),
                "effective": state["effective"]}
    return None


def make_dependency_slice(store, document, *, kind, identity, projection) -> dict:
    """Service-side constructor for the required basis of a task/decision —
    callers cannot omit registered dependencies (CONTRACTS §7)."""
    built = build_slice(store, document, kind=kind, identity=identity, projection=projection)
    if built is None:
        raise ModelError(f"slice:{kind}:{identity}",
                         "slice target is absent or the projection is not registered")
    if built.get("effective") is False:
        raise ModelError(f"slice:{kind}:{identity}", "cannot bind an ineffective dependency")
    return {"kind": kind, "identity": identity, "projection": projection,
            "ref": built["ref"], "sha256": built["sha256"]}


def slice_key(dep: dict) -> str:
    return f"{dep.get('kind')}:{dep.get('identity')}:{dep.get('projection')}"


def assess_basis(store, document, basis, *, _seen=frozenset(), now=None) -> dict:
    """Compare a recorded basis against the current document. Unknown slices
    are unverifiable and therefore not satisfied — never silently current."""
    matched, stale, unregistered = [], [], []
    for dep in basis or []:
        key = slice_key(dep)
        current = build_slice(store, document, kind=dep.get("kind"),
                              identity=dep.get("identity"), projection=dep.get("projection"),
                              _seen=_seen, now=now)
        if current is None:
            unregistered.append({"key": key, "reason": "unregistered_or_absent"})
        elif current.get("effective") is False:
            stale.append({"key": key, "expected": dep.get("sha256"), "current": current["sha256"],
                          "reason": "dependency_ineffective"})
        elif current["sha256"] != dep.get("sha256"):
            stale.append({"key": key, "expected": dep.get("sha256"), "current": current["sha256"]})
        else:
            matched.append(key)
    return {"matched": sorted(matched), "stale": sorted(stale, key=canonical_json_bytes),
            "unregistered": sorted(unregistered, key=canonical_json_bytes),
            "current": not stale and not unregistered}


def _resolve_current(store, document, family, id_field, ref):
    """Resolve a record reference to the version the current control still
    references, by identity (CONTRACTS §3.3): writing a new version (revoke,
    withdrawal) replaces the region's ref, so an old ref must be evaluated
    through the current version — a revoked identity never stays effective
    through a stale pointer. Returns (current_ref, record) or (None, record)
    when the identity is not referenced by the current region at all."""
    try:
        record = store.read_object_json(ref)
    except Exception as exc:  # noqa: BLE001
        raise ModelError("(slice)", f"unreadable record {ref.get('path')!r}") from exc
    identity = record.get(id_field)
    head = _head_for_identity(store, document, family, id_field, identity)
    if head is None:
        return None, record
    return head


def _request_state(document, record) -> list[str]:
    """Whether a record still belongs to the live work request.

    A replaced request renders its records ineffective by default; the only
    exception is the explicitly named background set — a new request lists the
    old request ids it allows to keep running, and nothing else can borrow the
    old scope (CONTRACTS §2: 新请求默认只推进自己)."""
    reasons: list[str] = []
    request = (document.get("collaboration") or {}).get("request")
    if request is None or request.get("closed"):
        reasons.append("request_closed")
    elif record.get("request_id") != request.get("request_id"):
        if record.get("request_id") in (request.get("background_request_ids") or []):
            return reasons
        reasons.append("request_superseded")
    return reasons


def _cycle_state():
    return {"effective": False, "reasons": ["dependency_cycle"],
            "basis": {"matched": [], "stale": [], "unregistered": [], "current": False}}


def accepted_decision(store, document, ref, *, _seen=frozenset(), now=None):
    """A reusable rejection is a valid fact, but cannot back execution."""
    _, record = _resolve_current(store, document, "decisions", "decision_id", ref)
    return (record.get("disposition") == "accepted"
            and record.get("authority_mode") in ("direct_user", "delegated")
            and decision_effectiveness(store, document, ref, _seen=_seen, now=now)["effective"])


def decision_effectiveness(store, document, decision_ref, *, _seen=frozenset(), now=None) -> dict:
    """Whether a decision still applies to the current project. Pausing a
    request does not invalidate decisions (it stops production); closing or
    replacing the request, withdrawal, supersession or a stale basis does."""
    current_ref, record = _resolve_current(store, document, "decisions", "decision_id", decision_ref)
    key = ("decision", record.get("decision_id"))
    if key in _seen or len(_seen) > 32:
        return _cycle_state()
    _seen = _seen | {key}
    reasons: list[str] = []
    if current_ref is None:
        reasons.append("not_in_current_control")
    if record.get("status") != "active":
        reasons.append(f"decision_{record.get('status')}")
    reasons.extend(_request_state(document, record))
    if record.get("authority_mode") == "delegated":
        # CONTRACTS §3.1: a delegated decision must trace to a still-effective
        # authorization that covers it.
        if not record.get("delegation_ref"):
            reasons.append("delegation_missing")
        else:
            delegation = authorization_effectiveness(store, document, record["delegation_ref"], _seen=_seen, now=now)
            if not delegation["effective"]:
                reasons.append("delegation_ineffective")
            _, parent = _resolve_current(store, document, "authorizations", "authorization_id", record["delegation_ref"])
            if delegation_gaps(store, parent, record, decision=True):
                reasons.append("delegation_scope_exceeded")
    basis = assess_basis(store, document, record.get("basis") or [], _seen=_seen, now=now)
    if basis["stale"]:
        reasons.append("basis_stale")
    if basis["unregistered"]:
        reasons.append("basis_unverifiable")
    return {"effective": not reasons, "reasons": reasons, "basis": basis}


def authorization_effectiveness(store, document, authorization_ref, *, now=None, _depth=0, _seen=frozenset()) -> dict:
    """Whether an authorization can still back a new action: active status, a
    current non-paused request, unexpired, a current basis and an effective
    parent chain."""
    current_ref, record = _resolve_current(store, document, "authorizations",
                                           "authorization_id", authorization_ref)
    key = ("authorization", record.get("authorization_id"))
    if key in _seen or len(_seen) > 32:
        return _cycle_state()
    _seen = _seen | {key}
    reasons: list[str] = []
    if current_ref is None:
        reasons.append("not_in_current_control")
    status = record.get("status")
    if status in ("revoked", "superseded", "invalidated"):
        reasons.append(f"authorization_{status}")
    elif status == "paused":
        reasons.append("authorization_paused")
    if _depth > _MAX_PARENT_DEPTH:
        reasons.append("parent_chain_too_deep")
    else:
        reasons.extend(_request_state(document, record))
        request = (document.get("collaboration") or {}).get("request")
        if request is not None and not request.get("closed") and request.get("paused"):
            reasons.append("request_paused")
    expires = record.get("expires_at")
    if expires is not None:
        current_time = now or datetime.now(timezone.utc)
        try:
            parsed = parse_authorization_expiry(expires)
            if current_time >= parsed:
                reasons.append("authorization_expired")
        except ModelError:
            reasons.append("authorization_expiry_invalid")
    basis = assess_basis(store, document, record.get("basis") or [], _seen=_seen, now=now)
    if basis["stale"]:
        reasons.append("basis_stale")
    if basis["unregistered"]:
        reasons.append("basis_unverifiable")
    parent_ref = record.get("parent_authorization_ref")
    if parent_ref and _depth <= _MAX_PARENT_DEPTH:
        parent_current, parent_record = _resolve_current(store, document, "authorizations",
                                             "authorization_id", parent_ref)
        if parent_current is None:
            reasons.append("parent_ineffective")
        else:
            parent = authorization_effectiveness(store, document, parent_ref, now=now, _depth=_depth + 1, _seen=_seen)
            if not parent["effective"]:
                reasons.append("parent_ineffective")
                if any(reason in ("authorization_revoked", "ancestor_authorization_revoked")
                       for reason in parent["reasons"]):
                    reasons.append("ancestor_authorization_revoked")
            if delegation_gaps(store, parent_record, record):
                reasons.append("parent_scope_exceeded")
    for decision_ref in record.get("decision_refs") or []:
        if not accepted_decision(store, document, decision_ref, _seen=_seen, now=now):
            reasons.append("decision_ineffective")
    return {"effective": not reasons, "reasons": sorted(set(reasons)), "basis": basis}
