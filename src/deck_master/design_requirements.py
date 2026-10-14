"""Service-owned page-level content projection; Page and Plan stay authoritative."""

from __future__ import annotations

from copy import deepcopy

from .content import visible_atoms
from .models import ModelError, canonical_json_bytes, sha256_bytes, writer_at_least, validate_schema

ROLE_FIELDS = ("role", "audience_question", "intended_takeaway", "transition_to_next")
PLAN_FIELDS = (*ROLE_FIELDS, "content_profile", "density_rationale", "required_qualifications", "narrative_node_ids")
GEOMETRY = {"x", "y", "width", "height", "position", "bounds", "geometry", "rotation"}


def semantic_projection(page):
    """Relations and cell ownership matter even when the text multiset is equal.

    Pure node geometry is excluded; label ownership, edge direction and the
    ordered cell/row/column structure are retained. Layout remains a separate
    visual input, never a reason to rewrite business meaning.
    """
    visual = page.get("visual_spec") or {}
    return {
        "customer_visible": deepcopy(page.get("customer_visible") or {}),
        "nodes": [{k: deepcopy(v) for k, v in node.items() if k not in GEOMETRY} for node in visual.get("nodes") or []],
        "edges": [{k: deepcopy(v) for k, v in edge.items() if k not in GEOMETRY} for edge in visual.get("edges") or []],
        "visual_intent": visual.get("intent"),
    }


def semantic_digest(page):
    return sha256_bytes(canonical_json_bytes(semantic_projection(page)))


def page_role(store, document, page_id, *, check_binding=True):
    ref = document.get("content_plan")
    if not ref:
        return None
    plan = store.read_object_json(ref)
    if plan.get("schema_version") != "content_plan.v2":
        return None
    role = next((r for r in (plan.get("input") or {}).get("page_roles") or [] if r.get("page_id") == page_id), None)
    if not role:
        raise ModelError("design/content_plan/page_roles", f"{page_id}: no current page role")
    if plan.get("mode") != "bound":
        raise ModelError("design/content_plan", "production requires a bound plan, not a planned proposal")
    if check_binding:
        entry = next((e for e in document["pages"] if e["page_id"] == page_id), None)
        link = next((p for p in plan.get("page_links") or [] if p.get("page_id") == page_id), None)
        if not entry or not link or link.get("page_ref") != entry["page"]:
            raise ModelError("design/content_plan/page_links", f"{page_id}: Page/Plan basis changed; reconcile content")
    return {key: deepcopy(role.get(key)) for key in PLAN_FIELDS}


def resolve(store, document, entry, design, *, recipe_ref=None, decision_refs=()):
    page = store.read_object_json(entry["page"])
    role = page_role(store, document, entry["page_id"])
    if role is None and writer_at_least(document, "collaboration.v1"):
        request = (document.get("collaboration") or {}).get("request") or {}
        # Confirmed imported manuscripts may legitimately have no argument
        # plan. Newly argued production must not silently take that route.
        if request.get("content_intent") in ("content_full", "plan_only"):
            raise ModelError("design/content_plan", "new argument needs a current bound ContentPlan")
    from .production import resolve_design

    design, _ = resolve_design(page, design, design.get("assets") or [])
    visual = page.get("visual_spec") or {}
    requirements = {
        "schema_version": "content_requirements.v1",
        "mode": "planned" if role is not None else "fidelity",
        "page_id": entry["page_id"],
        "page_role": {k: role[k] for k in ROLE_FIELDS} if role else None,
        "content_profile": role["content_profile"] if role else None,
        "density_rationale": role["density_rationale"] if role else None,
        "required_qualifications": role["required_qualifications"] if role else None,
        "structure_refs": {
            "atom_ids": [a["atom_id"] for a in visible_atoms(page)],
            "node_ids": [n["node_id"] for n in visual.get("nodes") or []],
            "edge_ids": [e["edge_id"] for e in visual.get("edges") or []],
        },
        "visual_intent": visual.get("intent"),
        "layout_hint": visual.get("layout_hint"),
    }
    validate_schema("content_requirements", requirements)
    consumed = {
        "page_semantics": semantic_projection(page),
        "page_role": role,
        "layout_hint": visual.get("layout_hint"),
        "effective_design": deepcopy(design),
    }
    # Derived transport keys are not part of the visual parameters themselves.
    consumed["effective_design"].pop("content_requirements", None)
    consumed["effective_design"].pop("content_basis", None)
    basis = {
        "page_ref": deepcopy(entry["page"]),
        "plan_ref": deepcopy(document.get("content_plan")),
        "recipe_ref": deepcopy(recipe_ref),
        "decision_refs": deepcopy(list(decision_refs)),
        "page_semantics_sha256": semantic_digest(page),
        "page_role_sha256": sha256_bytes(canonical_json_bytes(role)),
        "consumed_sha256": sha256_bytes(canonical_json_bytes(consumed)),
    }
    return {**deepcopy(design), "content_requirements": requirements, "content_basis": basis}


def task_basis_current(store, document, task):
    """Compare what a new RC3 blueprint actually consumed, ignoring note shells.

    Legacy tasks have no such preparation and keep their historical predicate.
    Global input/design and authorization checks remain owned by their callers.
    """
    prep = task.get("preparation") or {}
    expected = prep.get("content_basis")
    if not expected:
        return None
    ids = task.get("scope_pages") or []
    if len(ids) != 1:
        return False
    entry = next((e for e in document["pages"] if e["page_id"] == ids[0]), None)
    if entry is None:
        return False
    try:
        current = resolve(
            store,
            document,
            entry,
            prep["resolved_design_context"],
            recipe_ref=expected.get("recipe_ref"),
            decision_refs=expected.get("decision_refs") or [],
        )
        if current["content_basis"]["consumed_sha256"] != expected["consumed_sha256"]:
            return False
        old = store.read_object_json(expected["page_ref"])
        page = store.read_object_json(entry["page"])
        return old.get("customer_visible") == page.get("customer_visible") and old.get("visual_spec") == page.get("visual_spec")
    except (ModelError, KeyError):
        return False
