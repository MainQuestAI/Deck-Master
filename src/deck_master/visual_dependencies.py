"""Read-only visual consumption projections, shared by tasks and history.

Historical objects stay immutable.  Equivalence applies only to visual work;
it never makes a historical Page current for speech or file-level review.
"""
from __future__ import annotations

from .models import canonical_json_bytes, compute_input_digest, content_identity, sha256_bytes, validate_schema
from .store import StoreError


def page_visual_digest(page):
    validate_schema("page", page)
    return sha256_bytes(canonical_json_bytes({
        "page_id": page["page_id"], "customer_visible": page["customer_visible"],
        "visual_spec": page["visual_spec"],
    }))


def page_visual_equivalent(store, before_ref, after_ref, page_id):
    """Fail closed unless both real, valid stored Pages have the requested ID."""
    try:
        before, after = store.read_object_json(before_ref), store.read_object_json(after_ref)
        return (before["page_id"] == after["page_id"] == page_id
                and page_visual_digest(before) == page_visual_digest(after))
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        return False


def plan_visual_projection(store, document, page_ids):
    """Global manuscript structure and the roles actually consumed by pages.

    Page links and revision/audit shells do not enter visual production.  A
    legacy plan with no registered roles remains conservatively whole-plan.
    """
    ref = document.get("content_plan")
    if ref is None:
        return None
    plan = store.read_object_json(ref)
    validate_schema("content_plan", plan)
    if plan.get("schema_version") != "content_plan.v2":
        return {"legacy_plan": ref}
    from .design_requirements import plan_global_projection, plan_page_projection
    if not set(page_ids) <= set(plan["input"]["page_order"]):
        raise ValueError("consumed Page is outside Plan")
    return {"global": plan_global_projection(plan),
            "page_roles": [plan_page_projection(plan, pid) for pid in sorted(page_ids)]}


def is_visual_task(task):
    return (task.get("kind") in ("blueprint", "reconstruct")
            or (task.get("kind") in ("review", "repair")
                and task.get("review_stage", "final") == "page_visual")
            or (task.get("stage_request", {}).get("stage") in ("blueprint", "svg")
                and task.get("kind") != "compose"))


def visual_task_inputs_current(store, document, task):
    """Actual dispatched visual inputs; no task.preparation/cache inference."""
    from .production import (consumed_design, resolve_page_design,
                             resolve_page_rendering_design, stored_blueprint_request)
    from .snapshots import load_snapshot
    try:
        if not is_visual_task(task) or not task.get("scope_pages"):
            return False
        if task.get("kind") == "blueprint":
            prepared, _ = stored_blueprint_request(store, task)
        else:
            prepared = None
        target = task.get("stage_request", {}).get("target_reference_ref")
        if target is not None and any(entry.get("blueprint") != target for entry in document["pages"] if entry["page_id"] in task["scope_pages"]):
            return False
        if task.get("kind") != "blueprint":
            for entry in document["pages"]:
                if entry["page_id"] in task["scope_pages"]:
                    # Validate the actual adopted lineage even on the identity
                    # fast path; an already-stale image cannot seed new work.
                    resolve_page_design(store, document, entry, require_current=True)
        if content_identity(document) == task.get("produced_against"):
            return True
        dispatched = load_snapshot(store, task["dispatch_revision"])
        if compute_input_digest(dispatched) != compute_input_digest(document):
            return False
        ids = task["scope_pages"]
        if plan_visual_projection(store, dispatched, ids) != plan_visual_projection(store, document, ids):
            return False
        before = {entry["page_id"]: entry for entry in dispatched["pages"]}
        after = {entry["page_id"]: entry for entry in document["pages"]}
        for page_id in ids:
            old, current = before[page_id], after[page_id]
            if not page_visual_equivalent(store, old["page"], current["page"], page_id):
                return False
            if prepared and prepared.get("resolved_design_context"):
                from .production import resolve_generation_design
                recipe_ref = task.get("stage_request", {}).get("style_recipe_ref")
                if consumed_design(prepared["resolved_design_context"]) != consumed_design(
                        resolve_generation_design(store, document, current, recipe_ref=recipe_ref)):
                    return False
            elif consumed_design(resolve_page_rendering_design(store, dispatched, old)) != consumed_design(
                    resolve_page_rendering_design(store, document, current)):
                return False
            slots = ("blueprint", "svg", "svg_preview") if task.get("review_stage") == "page_visual" else (("blueprint", "svg") if task.get("kind") in ("reconstruct", "repair", "review") else ())
            if task.get("stage_request", {}).get("mode") == "trial":
                slots = ("blueprint",) if task.get("kind") == "reconstruct" else ()
            if any(old.get(slot) != current.get(slot) for slot in slots):
                return False
            target = task.get("stage_request", {}).get("target_reference_ref")
            if target is not None and current.get("blueprint") != target:
                return False
        return True
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        return False


def assess_visual_task_basis(store, document, task, basis):
    """Assess immutable legacy visual bindings without rewriting their basis.

    Only an actual dispatched Page/Plan pointer may use the consumed visual
    projection. Authorizations, decisions and every other dependency retain
    their ordinary exact resolver.
    """
    from . import dependency_slices
    from .snapshots import load_snapshot
    state = dependency_slices.assess_basis(store, document, basis)
    if not is_visual_task(task) or not state["stale"]:
        return state
    try:
        dispatched = load_snapshot(store, task["dispatch_revision"])
        ids = task.get("scope_pages") or []
        old_pages = {entry["page_id"]: entry for entry in dispatched["pages"]}
        new_pages = {entry["page_id"]: entry for entry in document["pages"]}
        allowed = set()
        for dep in basis:
            if dep.get("kind") != "artifact" or dep.get("projection") != "content":
                continue
            identity = dep.get("identity")
            if identity == "content_plan" and ids:
                old_ref = dispatched.get("content_plan")
                equivalent = (old_ref is not None
                              and plan_visual_projection(store, dispatched, ids)
                              == plan_visual_projection(store, document, ids))
            elif identity.startswith("page:") and identity.split(":", 1)[1] in ids:
                page_id = identity.split(":", 1)[1]
                old_ref = old_pages[page_id]["page"]
                equivalent = page_visual_equivalent(store, old_ref, new_pages[page_id]["page"], page_id)
            else:
                continue
            if equivalent and dep.get("ref") == old_ref and dep.get("sha256") == old_ref["sha256"]:
                allowed.add(dependency_slices.slice_key(dep))
        state = {**state, "stale": [item for item in state["stale"] if item["key"] not in allowed],
                 "matched": sorted(set(state["matched"]) | allowed)}
        state["current"] = not state["stale"] and not state["unregistered"]
        return state
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        return state
