"""One scope-containment rule for collaboration writes and later rechecks."""
from __future__ import annotations

from .store import StoreError

ASSURANCE_RANK = {"unverified": 0, "host_attested": 1, "verified_user": 2}


def scope_gaps(store, parent, child) -> list[str]:
    """Return dimensions outside the parent; an empty page set is never '*'.

    A deck may be narrowed to named pages. Purpose has no implicit promotion
    or ordering in the contract. A manifest binds page order, not page_links,
    so replacing copy without changing the manifest does not widen scope.
    """
    gaps = []
    if child.get("subject") != parent.get("subject") and not (
            parent.get("subject") == "deck" and child.get("subject") == "pages"):
        gaps.append("subject")
    if not set(child.get("page_ids") or []) <= set(parent.get("page_ids") or []):
        gaps.append("page_ids")
    if not set(child.get("layers") or []) <= set(parent.get("layers") or []):
        gaps.append("layers")
    for field in ("allow_page_membership_change", "allow_page_order_change"):
        if child.get(field) and not parent.get(field):
            gaps.append(field)
    if child.get("purpose") != parent.get("purpose"):
        gaps.append("purpose")
    external = parent.get("external_artifact_ref")
    if external and child.get("external_artifact_ref") != external:
        gaps.append("external_artifact_ref")
    manifest = parent.get("page_manifest_ref")
    if manifest:
        try:
            old = store.read_object_json(manifest)
            new = store.read_object_json(child.get("page_manifest_ref"))
            if (old.get("schema_version") != "content_plan.v2"
                    or new.get("schema_version") != "content_plan.v2"
                    or old["input"]["page_order"] != new["input"]["page_order"]):
                gaps.append("page_manifest_ref")
        except (KeyError, TypeError, ValueError, OSError, StoreError):
            gaps.append("page_manifest_ref")
    return gaps


def _future_pages_gap(parent, child) -> str | None:
    """§3.4: a parent delegate may declare ``future_pages`` — the domain
    permission to fix a bounded page set later. The Runtime then materializes
    that selector into a child execute grant whose page_ids are the real Plan
    pages, so an empty parent page set is *not* a containment failure when the
    selector and its page bound allow exactly this child.

    Returns a gap name when the child exceeds the declared domain, else None.
    """
    future = ((parent.get("constraints") or {}).get("future_pages") or {})
    if not future:
        # Without a declared future-pages domain an empty parent page set stays
        # exactly that: no pages (an empty set is never "all pages").
        return "scope/page_ids"
    selector = future.get("selector")
    if selector != "adopted_plan_for_this_request":
        return "scope/page_ids"
    child_pages = list(child.get("scope", {}).get("page_ids") or [])
    maximum = future.get("max_pages")
    if maximum is not None and len(child_pages) > int(maximum):
        return "scope/page_ids"
    if future.get("max_pages") is None and future.get("max_pages_basis") == "pending":
        return "scope/page_ids"
    return None


def delegation_gaps(store, parent, child, *, decision=False) -> list[str]:
    """A replacement parent must still cover the original child's authority."""
    gaps = []
    if parent.get("mode") != "delegate":
        gaps.append("delegate_mode")
    parent_scope = parent.get("scope") or {}
    child_scope = child.get("scope") or {}
    for field in scope_gaps(store, parent_scope, child_scope):
        if field == "page_ids" and not (parent_scope.get("page_ids") or []):
            future_gap = _future_pages_gap(parent, child)
            if future_gap is None:
                continue
            gaps.append(future_gap)
            continue
        gaps.append("scope/" + field)
    topics = [child.get("topic")] if decision else child.get("delegated_topics") or []
    if not set(topics) <= set(parent.get("delegated_topics") or []):
        gaps.append("delegated_topics")
    if not decision:
        if not set(child.get("actions") or []) <= set(parent.get("actions") or []):
            gaps.append("actions")
        if child.get("adoption_policy") == "within_scope" and parent.get("adoption_policy") != "within_scope":
            gaps.append("adoption_policy")
        if child.get("delivery_binding", "none") not in ("none", parent.get("delivery_binding")):
            gaps.append("delivery_binding")
    if (ASSURANCE_RANK.get((child.get("evidence") or {}).get("assurance"), 0)
            > ASSURANCE_RANK.get((parent.get("evidence") or {}).get("assurance"), 0)):
        gaps.append("evidence/assurance")
    return gaps
