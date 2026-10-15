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
    transition = candidate.get("variant_transition") or {}
    editing = transition.get("kind") == "edit_variant" and candidate.get("intent") == "edit"
    if variant["variant_id"] in used and not editing:
        raise ModelError("collaboration/request/variant/variant_id",
                         f"this variant was already fixed in this group: {variant['variant_id']!r}; "
                         "edit that version through its own revision instead of producing it twice")
    current = (document.get("collaboration") or {}).get("request")
    open_current = current is not None and not current.get("closed")
    if open_current:
        if replace_request_id != current.get("request_id"):
            raise ModelError(
                "collaboration/request/replace_request_id",
                "a variant sub-request is sequential: pass replace_request_id naming the "
                "current open request (it stays a single current pointer)")
        if used:
            prior = current.get("variant") or {}
            if prior.get("group_id") != group_id:
                raise ModelError("collaboration/request/variant/group_id",
                                 "the current open request belongs to another variant group")
            if prior.get("variant_id") == variant["variant_id"] and not editing:
                raise ModelError("collaboration/request/variant/variant_id",
                                 "the replacement must be the other declared variant")
    elif replace_request_id not in (None, "") and (current is None or replace_request_id != current.get("request_id")):
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


def _fixed_narrative(store, document, group_id):
    values = []
    revision = document.get("revision_id")
    seen = set()
    while revision:
        if revision in seen:
            raise ModelError("variant/history", "cyclic committed history")
        seen.add(revision)
        snap = store.load_document(revision)
        request = (snap.get("collaboration") or {}).get("request") or {}
        if ((request.get("variant") or {}).get("group_id") == group_id
                and snap.get("narrative") and snap.get("pages") and snap.get("content_plan")):
            values.append(snap["narrative"])
        revision = snap.get("parent_revision_id")
    return values[-1] if values else None


def require_fixed_narrative(store, document, narrative_ref):
    variant = current_request_variant(document) or {}
    if not variant:
        return
    fixed = _fixed_narrative(store, document, variant["group_id"])
    if fixed is not None and narrative_ref != fixed:
        from .store import ConflictError
        raise ConflictError("variant/narrative_ref", "same-source variants must preserve their fixed shared Narrative")


def apply_transition(store, document, updated, input):
    """Select historical content under current control in the request transaction."""
    from .snapshots import load_snapshot
    from . import exports
    from .collaboration_scope import scope_gaps
    from .store import ConflictError
    transition = input["variant_transition"]
    if not isinstance(transition, dict) or set(transition) != {"kind", "source"}:
        raise ModelError("variant_transition", "name kind and fixed source")
    kind = transition["kind"]
    source = transition["source"]
    if kind not in ("next_variant", "edit_variant") or not isinstance(source, dict) or set(source) - {"revision_id", "export_id"}:
        raise ModelError("variant_transition", "unsupported transition/source fields")
    if kind == "edit_variant" and input.get("intent") != "edit":
        raise ModelError("variant_transition", "historical version edits require intent=edit")
    snap = load_snapshot(store, source.get("revision_id"))
    if not source.get("revision_id"):
        raise ModelError("variant_transition/source/revision_id", "an explicit committed source revision is required")
    source_variant = current_request_variant(snap) or {}
    target = input.get("variant") or {}
    if not source_variant or source_variant.get("group_id") != target.get("group_id"):
        raise ModelError("variant_transition/source", "source belongs to another variant group")
    if (kind == "edit_variant") != (source_variant.get("variant_id") == target.get("variant_id")):
        raise ModelError("variant_transition/source", "next selects the other version; edit selects this source version")
    records = [record for record in _export_records(store) if record.get("revision_id") == snap["revision_id"]]
    if source.get("export_id"):
        records = [record for record in records if record.get("export_id") == source["export_id"]]
    if not records or not snap.get("content_plan") or not snap.get("pages") or not snap.get("narrative"):
        raise ConflictError("variant_transition/source", "variant_source_unavailable: fix the complete source revision and versioned export first")
    record = exports.show(store.project_root, export_id=records[0]["export_id"])
    if record["manifest"].get("variant", {}).get("narrative_ref") != snap["narrative"]:
        raise ConflictError("variant_transition/source", "export and actual source Narrative differ")
    for name in record["files"]:
        exports.download(store.project_root, export_id=record["export_id"], filename=name)
    fixed = _fixed_narrative(store, document, target["group_id"])
    if fixed is not None and snap["narrative"] != fixed:
        raise ConflictError("variant_transition/source", "the source changed the fixed shared argument")
    if kind == "edit_variant":
        selected = {entry["page_id"] for entry in snap["pages"]}
        request_scope = input.get("scope") or {}
        if not set(request_scope.get("page_ids") or []) <= selected:
            raise ModelError("variant_transition/scope", "edit targets must belong to the selected version")
        for key in ("narrative", "content_plan", "pages", "outputs", "content_basis", "style_recipes"):
            if key in snap:
                updated[key] = snap[key]
        from .models import compute_input_digest
        if (snap.get("content_basis") or {}).get("input_digest") != compute_input_digest(document):
            # Content is selected, but current user/task facts remain authoritative.
            # The old basis is retained so normal reconciliation cannot be skipped.
            updated["content_basis"] = snap.get("content_basis") or {
                "input_digest": compute_input_digest(snap), "input_revision_id": None, "resolved_by_task_id": None}
    else:
        updated["narrative"] = snap["narrative"]
        updated["pages"] = []
        updated.pop("content_plan", None)
        updated["outputs"] = dict.fromkeys(document["outputs"])
        updated.pop("content_basis", None)
    # History/call facts and current control are never replaced by source state.
    retired = []
    refs = []
    current_request = (document.get("collaboration") or {}).get("request") or {}
    for ref in document.get("tasks", []):
        task = store.read_object_json(ref)
        if (task.get("status") in ("queued", "awaiting_host", "running")
                and (task.get("collaboration_binding") or {}).get("request_id") == current_request.get("request_id")):
            ref = store.put_json_object({**task, "status": "superseded"}); retired.append(task["task_id"])
        refs.append(ref)
    updated["tasks"] = refs
    return updated, {"kind": kind, "source_revision_id": snap["revision_id"],
        "source_export_id": record["export_id"], "source_manifest_sha256": sha256_bytes(canonical_json_bytes(record["manifest"])),
        "variant": target, "narrative_ref": snap["narrative"], "preserved_export_ids": [record["export_id"]],
        "affected_tasks": retired, "reused_refs": [snap["narrative"]], "detached_refs": []}
