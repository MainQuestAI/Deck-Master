"""Sequential live/read variant sub-requests (content collaboration v1.2
CONTRACTS §11.7, ACCEPTANCE AC-M02).

Two optimised versions of the same argument are two **sequential, bounded
sub-requests** inside one project — never a general branch workflow. Both share
the fixed Narrative Ref and the source facts, each has its own Plan/Page/output
and scope, Document.current stays single, and each version is addressed through
its own immutable revision and versioned export.

The original instruction must declare ``variant_ids`` in an effective
authorization; the group id is derived by the Runtime from that authorization
(so relabelling cannot produce a third version), and a variant id already
produced in the group cannot be produced again.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import dependency_slices
from .models import ModelError, canonical_json_bytes, sha256_bytes

VARIANT_FIELDS = ("group_id", "variant_id", "label", "requested_variant_ids")
MAX_VARIANTS = 2
_VARIANT_ID = re.compile(r"^[a-z][a-z0-9_-]*$")


def variant_group_id(authorization_ref, declared_ids) -> str:
    """The group id the Runtime derives from the declaring authorization.

    A caller-supplied group label cannot open a fresh group for the same
    declared variant set, so "two versions" cannot silently become three.
    """
    return "vg-" + sha256_bytes(canonical_json_bytes(
        {"authorization": [authorization_ref.get("path"), authorization_ref.get("sha256")],
         "variant_ids": sorted(declared_ids)}))[:16]


def declaring_authorization(store, document):
    """The effective authorization whose constraints declare variant_ids."""
    region = document.get("collaboration") or {}
    found = []
    for ref in region.get("authorizations") or []:
        try:
            record = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unreadable records declare nothing
            continue
        if record.get("status") != "active":
            continue
        declared = (record.get("constraints") or {}).get("variant_ids")
        if not isinstance(declared, list) or not declared:
            continue
        if not dependency_slices.authorization_effectiveness(store, document, ref)["effective"]:
            continue
        found.append((ref, record, sorted(set(declared))))
    if not found:
        return None
    # The narrowest effective declaration is the one the user actually gave.
    found.sort(key=lambda item: (len(item[2]), item[0].get("sha256") or ""))
    return found[0]


def _export_records(store) -> list[dict]:
    records = []
    root = store.project_root / ".deckmaster" / "workbench" / "exports"
    if not root.is_dir():
        return records
    for record_path in sorted(root.glob("*/export-record.json")):
        try:
            record = json.loads(record_path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        records.append(record)
    return records


# How far back the committed-revision walk looks for variant sub-requests.
# A variant group is short-lived (two sequential requests); the bound keeps the
# check cheap and is reported so a caller never mistakes the bound for "all
# history".
VARIANT_HISTORY_LIMIT = 256


def _history_variant_ids(store, document, group_id) -> tuple[set[str], bool]:
    """Variant ids recorded by committed revisions, oldest-to-newest bounded walk.

    The Store's immutable revisions are the durable fact: a sub-request exists
    as a committed `collaboration.request.variant`, so deleting export output
    (a user-visible directory) cannot erase the fact that a version was already
    produced. Returns (ids, truncated) where truncated means the walk hit its
    bound before reaching the project start.
    """
    used: set[str] = set()
    revision = document.get("revision_id")
    visited = 0
    truncated = False
    while revision:
        if visited >= VARIANT_HISTORY_LIMIT:
            truncated = True
            break
        try:
            snapshot = store.load_document(revision)
        except Exception:  # noqa: BLE001 - an unreadable ancestor ends the walk
            break
        variant = ((snapshot.get("collaboration") or {}).get("request") or {}).get("variant") or {}
        if variant.get("group_id") == group_id and variant.get("variant_id"):
            used.add(variant["variant_id"])
        revision = snapshot.get("parent_revision_id")
        visited += 1
    return used, truncated


def used_variant_ids(store, document, group_id) -> list[str]:
    """Variant ids this group has already fixed.

    Two independent sources, so removing one cannot re-open a finished version:
    the committed revision history (Store fact) and the frozen export records
    (which also cover versions whose branch is no longer in the current
    ancestry, e.g. after a restore).
    """
    used, _ = _history_variant_ids(store, document, group_id)
    for record in _export_records(store):
        variant = (record.get("manifest") or {}).get("variant") or {}
        if variant.get("group_id") == group_id and variant.get("variant_id"):
            used.add(variant["variant_id"])
    request = (document.get("collaboration") or {}).get("request") or {}
    variant = request.get("variant") or {}
    if variant.get("group_id") == group_id and variant.get("variant_id"):
        used.add(variant["variant_id"])
    return sorted(used)


def current_request_variant(document) -> dict | None:
    return ((document.get("collaboration") or {}).get("request") or {}).get("variant")


def validate_variant_request(store, document, candidate: dict, *, replace_request_id=None) -> dict:
    """Check one variant sub-request against the declared authority and history.

    Returns the accepted posture (group id, declared ids, already-used ids) and
    raises ModelError with a specific reason otherwise.
    """
    variant = candidate.get("variant")
    if not isinstance(variant, dict):
        raise ModelError("collaboration/request/variant", "a variant request names its group and variant")
    unknown = sorted(set(variant) - set(VARIANT_FIELDS))
    if unknown:
        raise ModelError("collaboration/request/variant", f"unknown variant fields: {unknown}")
    missing = [field for field in VARIANT_FIELDS if not variant.get(field)]
    if missing:
        raise ModelError("collaboration/request/variant", f"missing variant fields: {missing}")
    requested = variant["requested_variant_ids"]
    if (not isinstance(requested, list) or not requested
            or not all(isinstance(item, str) and item for item in requested)
            or len(set(requested)) != len(requested)):
        raise ModelError("collaboration/request/variant/requested_variant_ids",
                         "must be a non-empty list of distinct variant ids")
    if len(requested) > MAX_VARIANTS:
        raise ModelError("collaboration/request/variant/requested_variant_ids",
                         f"this contract supports at most {MAX_VARIANTS} optimised versions")
    for variant_id in requested:
        if not _VARIANT_ID.match(variant_id):
            raise ModelError("collaboration/request/variant/requested_variant_ids",
                             f"variant id {variant_id!r} must match {_VARIANT_ID.pattern}")
    if variant["variant_id"] not in requested:
        raise ModelError("collaboration/request/variant/variant_id",
                         "this sub-request must name a variant id the original instruction requested")
    current_request = (document.get("collaboration") or {}).get("request") or {}
    carried = current_request.get("variant") or {}
    if carried and variant["group_id"] == carried.get("group_id"):
        # The second (sequential) version carries the declaration the first one
        # recorded: the same group, the same requested ids, the other variant.
        declared_ids = sorted(set(carried.get("requested_variant_ids") or []))
        group_id = carried["group_id"]
        authorization_ref, record = None, None
        declaration_source = "carried_by_current_variant"
    else:
        declaration = declaring_authorization(store, document)
        if declaration is None:
            raise ModelError(
                "collaboration/request/variant",
                "decision_needed: two optimised versions need the original instruction to declare "
                "variant_ids in an effective authorization")
        authorization_ref, record, declared_ids = declaration
        group_id = variant_group_id(authorization_ref, declared_ids)
        declaration_source = "effective_authorization"
        if variant["group_id"] != group_id:
            raise ModelError(
                "collaboration/request/variant/group_id",
                "the group id is derived by the Runtime from the declaring authorization; "
                "relabelling cannot open a second group for the same variants")
    outside = sorted(set(requested) - set(declared_ids))
    if outside:
        raise ModelError("collaboration/request/variant/requested_variant_ids",
                         f"scope_exceeded: the instruction does not declare {outside}")
    if not declared_ids:
        raise ModelError("collaboration/request/variant/requested_variant_ids",
                         "the carried declaration has no variant ids to work from")
    used = used_variant_ids(store, document, group_id)
    history_used, truncated = _history_variant_ids(store, document, group_id)
    if variant["variant_id"] in used:
        raise ModelError("collaboration/request/variant/variant_id",
                         f"this variant was already fixed in this group: {variant['variant_id']!r}; "
                         "edit that version through its own revision instead of producing it twice")
    current = (document.get("collaboration") or {}).get("request")
    open_current = current is not None and not current.get("closed")
    if used or open_current:
        if not open_current or replace_request_id != current.get("request_id"):
            raise ModelError(
                "collaboration/request/replace_request_id",
                "a variant sub-request is sequential: pass replace_request_id naming the "
                "current open request (it stays a single current pointer)")
        if used:
            prior = current.get("variant") or {}
            if prior.get("group_id") != group_id:
                raise ModelError("collaboration/request/variant/group_id",
                                 "the current open request belongs to another variant group")
            if prior.get("variant_id") == variant["variant_id"]:
                raise ModelError("collaboration/request/variant/variant_id",
                                 "the replacement must be the other declared variant")
    elif replace_request_id not in (None, ""):
        raise ModelError("collaboration/request/replace_request_id",
                         "the first version starts a request; there is nothing to replace yet")
    return {"group_id": group_id, "variant_id": variant["variant_id"], "label": variant["label"],
            "requested_variant_ids": sorted(requested), "declared_variant_ids": declared_ids,
            "authorization_ref": authorization_ref, "already_fixed": used,
            "declaration_source": declaration_source,
            "fixed_from_history": sorted(history_used), "history_truncated": truncated,
            "authorization_id": (record or {}).get("authorization_id")}


def shared_narrative_check(store, document, group_id: str) -> dict:
    """Both versions must reuse one fixed Narrative Ref (CONTRACTS §11.7.3).

    The first export of a variant records the Narrative it was built on; a
    second sub-request in the same group may not adopt a different one.
    """
    narrative_ref = document.get("narrative")
    recorded = None
    for record in _export_records(store):
        variant = (record.get("manifest") or {}).get("variant") or {}
        if variant.get("group_id") != group_id:
            continue
        recorded = variant.get("narrative_ref") or recorded
    if recorded is None:
        return {"ok": True, "narrative_ref": narrative_ref, "reason": "no earlier variant export"}
    if narrative_ref != recorded:
        return {"ok": False, "narrative_ref": narrative_ref, "recorded_narrative_ref": recorded,
                "reason": "the second version must reuse the same Narrative Ref; adopting a new "
                          "one is a new argument, not a second optimisation"}
    return {"ok": True, "narrative_ref": narrative_ref, "reason": "reuses the fixed Narrative Ref"}


def digest_of(value) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
