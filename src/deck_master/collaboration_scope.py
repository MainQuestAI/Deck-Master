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


def delegation_gaps(store, parent, child, *, decision=False) -> list[str]:
    """A replacement parent must still cover the original child's authority."""
    gaps = []
    if parent.get("mode") != "delegate":
        gaps.append("delegate_mode")
    gaps.extend("scope/" + field for field in scope_gaps(
        store, parent.get("scope") or {}, child.get("scope") or {}))
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
