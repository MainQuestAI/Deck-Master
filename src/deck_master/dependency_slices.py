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

from .models import ModelError, canonical_json_bytes, sha256_bytes

TASK_FACT_IDENTITIES = ("audience", "brief", "scenario", "presentation_mode", "page_limit")
_MAX_PARENT_DEPTH = 8


def _canonical(value) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _find_page(document, page_id):
    for entry in document.get("pages") or []:
        if entry.get("page_id") == page_id:
            return entry
    return None


def _load_region_object(store, document, family, id_field, identity):
    region = document.get("collaboration") or {}
    for ref in region.get(family) or []:
        try:
            record = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unreadable records are simply absent
            continue
        if record.get(id_field) == identity:
            return record
    return None


def _decision_projection(record) -> dict:
    scope = record.get("scope") or {}
    return {"topic": record.get("topic"), "disposition": record.get("disposition"),
            "value": record.get("value"), "status": record.get("status"),
            "subject": scope.get("subject"),
            "page_ids": sorted(scope.get("page_ids") or []),
            "layers": sorted(scope.get("layers") or [])}


def _authorization_projection(record) -> dict:
    scope = record.get("scope") or {}
    return {"mode": record.get("mode"), "actions": sorted(record.get("actions") or []),
            "subject": scope.get("subject"),
            "page_ids": sorted(scope.get("page_ids") or []),
            "layers": sorted(scope.get("layers") or []),
            "delegated_topics": sorted(record.get("delegated_topics") or []),
            "max_external_calls": record.get("max_external_calls"),
            "max_candidate_count": record.get("max_candidate_count"),
            "adoption_policy": record.get("adoption_policy"),
            "delivery_binding": record.get("delivery_binding"),
            "status": record.get("status")}


def build_slice(store, document, *, kind, identity, projection):
    """Current value of one registered slice, or None when the target is absent
    or the (kind, projection) pair is not registered."""
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
        record = _load_region_object(store, document, "decisions", "decision_id", identity)
        if record is None:
            return None
        return {"ref": None, "sha256": _canonical({"decision": _decision_projection(record)})}
    if kind == "authorization" and projection == "effective":
        record = _load_region_object(store, document, "authorizations", "authorization_id", identity)
        if record is None:
            return None
        return {"ref": None, "sha256": _canonical({"authorization": _authorization_projection(record)})}
    return None


def make_dependency_slice(store, document, *, kind, identity, projection) -> dict:
    """Service-side constructor for the required basis of a task/decision —
    callers cannot omit registered dependencies (CONTRACTS §7)."""
    built = build_slice(store, document, kind=kind, identity=identity, projection=projection)
    if built is None:
        raise ModelError(f"slice:{kind}:{identity}",
                         "slice target is absent or the projection is not registered")
    return {"kind": kind, "identity": identity, "projection": projection, **built}


def slice_key(dep: dict) -> str:
    return f"{dep.get('kind')}:{dep.get('identity')}:{dep.get('projection')}"


def assess_basis(store, document, basis) -> dict:
    """Compare a recorded basis against the current document. Unknown slices
    are unverifiable and therefore not satisfied — never silently current."""
    matched, stale, unregistered = [], [], []
    for dep in basis or []:
        key = slice_key(dep)
        current = build_slice(store, document, kind=dep.get("kind"),
                              identity=dep.get("identity"), projection=dep.get("projection"))
        if current is None:
            unregistered.append({"key": key, "reason": "unregistered_or_absent"})
        elif current["sha256"] != dep.get("sha256"):
            stale.append({"key": key, "expected": dep.get("sha256"), "current": current["sha256"]})
        else:
            matched.append(key)
    return {"matched": matched, "stale": stale, "unregistered": unregistered,
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
    region = document.get("collaboration") or {}
    for candidate_ref in region.get(family) or []:
        try:
            candidate = store.read_object_json(candidate_ref)
        except Exception:  # noqa: BLE001
            continue
        if candidate.get(id_field) == identity:
            return candidate_ref, candidate
    return None, record


def _request_state(document, record) -> list[str]:
    reasons: list[str] = []
    request = (document.get("collaboration") or {}).get("request")
    if request is None or request.get("closed"):
        reasons.append("request_closed")
    elif record.get("request_id") != request.get("request_id"):
        reasons.append("request_superseded")
    return reasons


def decision_effectiveness(store, document, decision_ref) -> dict:
    """Whether a decision still applies to the current project. Pausing a
    request does not invalidate decisions (it stops production); closing or
    replacing the request, withdrawal, supersession or a stale basis does."""
    current_ref, record = _resolve_current(store, document, "decisions", "decision_id", decision_ref)
    reasons: list[str] = []
    if current_ref is None:
        reasons.append("not_in_current_control")
    if record.get("status") != "active":
        reasons.append(f"decision_{record.get('status')}")
    reasons.extend(_request_state(document, record))
    basis = assess_basis(store, document, record.get("basis") or [])
    if basis["stale"]:
        reasons.append("basis_stale")
    if basis["unregistered"]:
        reasons.append("basis_unverifiable")
    return {"effective": not reasons, "reasons": reasons, "basis": basis}


def authorization_effectiveness(store, document, authorization_ref, *, now=None, _depth=0) -> dict:
    """Whether an authorization can still back a new action: active status, a
    current non-paused request, unexpired, a current basis and an effective
    parent chain."""
    current_ref, record = _resolve_current(store, document, "authorizations",
                                           "authorization_id", authorization_ref)
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
    if expires:
        current_time = now or datetime.now(timezone.utc)
        try:
            parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None and current_time > parsed:
            reasons.append("authorization_expired")
    basis = assess_basis(store, document, record.get("basis") or [])
    if basis["stale"]:
        reasons.append("basis_stale")
    if basis["unregistered"]:
        reasons.append("basis_unverifiable")
    parent_ref = record.get("parent_authorization_ref")
    if parent_ref and _depth <= _MAX_PARENT_DEPTH:
        parent_current, _ = _resolve_current(store, document, "authorizations",
                                             "authorization_id", parent_ref)
        if parent_current is None:
            reasons.append("parent_ineffective")
        else:
            parent = authorization_effectiveness(store, document, parent_ref, now=now, _depth=_depth + 1)
            if not parent["effective"]:
                reasons.append("parent_ineffective")
    return {"effective": not reasons, "reasons": reasons, "basis": basis}
