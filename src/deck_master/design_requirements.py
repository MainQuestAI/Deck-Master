"""Read-only content requirements for visual production (CONTRACTS §11.4.1).

Page supplies copy and relationships; Plan supplies the actual page role and
density rationale. A recipe never rewrites either. The three projections here
are fixed service projections for the dependency registry, not caller JSONPath.
Historical Ref shells are retained in ``content_basis`` for tracing; canonical
consumption digests exclude revision/audit fields and unrelated page density.
"""
from __future__ import annotations

import copy

from . import content, models
from .models import ModelError, canonical_json_bytes, sha256_bytes
from .store import StoreError

PAGE_ROLE_FIELDS = ("role", "audience_question", "intended_takeaway", "transition_to_next")


def _digest(value) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def page_semantic_projection(page: dict) -> dict:
    """All visible ownership/value/unit and node/edge semantics, no layout.

    Body order and table row/column/cell identities remain intact. Geometry is
    expressed by legal ``layout_hint`` changes; nodes do not admit x/y fields.
    Speaker notes, style refs, design overrides and layout hints are excluded.
    """
    models.validate_page_semantics(page)
    content.validate_page_references(page)
    visual = page["visual_spec"]
    edges = visual.get("edges") or []
    edge_ids = [edge["edge_id"] for edge in edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise ModelError("page/visual_spec/edges", "duplicate edge_id")
    return copy.deepcopy({
        "page_id": page["page_id"],
        "customer_visible": page["customer_visible"],
        "visual_spec": {"intent": visual["intent"],
                        "nodes": visual.get("nodes") or [], "edges": edges},
    })


def plan_page_projection(plan: dict | None, page_id: str) -> dict:
    """Only this page's actual requirements; unavailable fidelity fields null."""
    if plan is not None:
        models.validate_content_plan_semantics(plan)
    role = None
    if plan and plan.get("schema_version") == "content_plan.v2":
        matches = [item for item in plan["input"]["page_roles"] if item["page_id"] == page_id]
        if len(matches) > 1:
            raise ModelError("design_requirements/plan/input/page_roles", "duplicate page role")
        role = matches[0] if matches else None
    return copy.deepcopy({
        "page_id": page_id,
        "page_role": {key: role.get(key) for key in PAGE_ROLE_FIELDS} if role else None,
        "content_profile": role.get("content_profile") if role else None,
        "density_rationale": role.get("density_rationale") if role else None,
        "required_qualifications": role.get("required_qualifications", []) if role else [],
    })


def plan_global_projection(plan: dict | None) -> dict | None:
    """Global argument/progression, purpose and budgets, excluding page density.

    Imports retain their real source/confirmation boundary, without creating a
    Narrative. Legacy plans retain their actual summary and goals as a distinct
    fidelity projection; their audit shell and Page hash links are not consumed.
    """
    if plan is None:
        return None
    models.validate_content_plan_semantics(plan)
    data = plan["input"]
    if plan.get("schema_version") != "content_plan.v2":
        return copy.deepcopy({"schema_version": plan["schema_version"],
                              "input_summary": data["input_summary"],
                              "chapters": data["chapters"], "goals": data["goals"],
                              "unresolved_facts": data["unresolved_facts"]})
    by_page = {role["page_id"]: role for role in data["page_roles"]}
    speech_policy = copy.deepcopy(data["speech_policy"])
    if speech_policy["mode"] == "none" and speech_policy["output"] == "none":
        # The origin of an absent speech product is audit evidence, not a
        # visual requirement. Keep the original complete policy in its Plan
        # Ref; active speech/file policy fields retain their dependency.
        speech_policy.pop("source", None)
    return copy.deepcopy({
        "mode": plan["mode"], "narrative_ref": plan["narrative_ref"],
        "imported_manuscript": plan["imported_manuscript"],
        "page_order": data["page_order"], "chapters": data["chapters"],
        "page_budget": data["page_budget"], "time_budget": data["time_budget"],
        "speech_policy": speech_policy,
        "progression": [{"page_id": page_id, **{key: (by_page.get(page_id) or {}).get(key)
                          for key in PAGE_ROLE_FIELDS}} for page_id in data["page_order"]],
    })


def _read(store, ref, where: str, *, json_object=True):
    models.validate_ref(ref, where=where)
    try:
        value = store.read_object_json(ref) if json_object else store.read_object_bytes(ref)
    except (StoreError, OSError, ValueError) as exc:
        raise ModelError(where, f"unreadable immutable object: {exc}") from exc
    if json_object and not isinstance(value, dict):
        raise ModelError(where, "expected a JSON object")
    return value


def _validate_links(store, document, plan, page_id: str) -> None:
    entries = document.get("pages") or []
    actual = {entry["page_id"]: entry["page"] for entry in entries}
    links = plan["page_links"]
    linked = [link["page_id"] for link in links]
    where = "design_requirements/plan/page_links"
    if len(linked) != len(set(linked)):
        raise ModelError(where, "duplicate Page links")
    if set(linked) != set(actual):
        raise ModelError(where, "Plan must link every current Page in the selected snapshot")
    for link in links:
        if link["page_ref"] != actual[link["page_id"]]:
            legacy = plan["schema_version"] == "content_plan.v1" and document.get("collaboration") is None
            if legacy and link["page_id"] != page_id:
                continue  # historical legacy links of unconsumed Pages are audit, not this Page's copy
            old_page = _read(store, link["page_ref"], where) if legacy else None
            new_page = _read(store, actual[link["page_id"]], where) if legacy else None
            equivalent = bool(legacy and old_page["customer_visible"] == new_page["customer_visible"]
                and all(old_page["visual_spec"].get(key) == new_page["visual_spec"].get(key) for key in ("nodes", "edges")))
            if not equivalent:
                raise ModelError(f"{where}/{link['page_id']}/page_ref",
                                 "Plan Page link does not match the selected snapshot")
        if plan["schema_version"] == "content_plan.v2" and link["plan_role_page_id"] != link["page_id"]:
            raise ModelError(f"{where}/{link['page_id']}/plan_role_page_id",
                             "Page link must name that Page's actual role")
    if plan["schema_version"] == "content_plan.v2":
        if plan["input"]["page_order"] != [entry["page_id"] for entry in entries]:
            raise ModelError("design_requirements/plan/input/page_order",
                             "Plan order differs from the selected snapshot")
        if page_id not in plan["input"]["page_order"]:
            raise ModelError(where, "requested Page has no current Plan role")


def _validate_mapping(store, document, plan, page: dict) -> None:
    """Validate existing content bindings without interpreting source claims."""
    from .content_plan import validate_source_links

    narrative_ref = plan["narrative_ref"]
    if narrative_ref != document.get("narrative"):
        raise ModelError("design_requirements/plan/narrative_ref",
                         "Plan Narrative is not current in the selected snapshot")
    narrative = None
    if narrative_ref is not None:
        narrative = _read(store, narrative_ref, "design_requirements/plan/narrative_ref")
        models.validate_narrative_semantics(narrative)
        if narrative["project_id"] != document["project_id"]:
            raise ModelError("design_requirements/plan/narrative_ref", "Narrative belongs to another project")
    if plan["mode"] == "bound" and narrative is None:
        raise ModelError("design_requirements/plan/narrative_ref",
                         "a bound argument Plan requires its current Narrative")
    if plan["mode"] == "imported_mapping":
        imported = plan["imported_manuscript"]
        _read(store, imported["source_ref"], "design_requirements/plan/imported_manuscript/source_ref",
              json_object=False)
        evidence = imported["claimed_confirmation_evidence"]
        for field in ("source_ref", "transport_receipt_ref", "presentation_ref"):
            if evidence.get(field) is not None:
                _read(store, evidence[field],
                      "design_requirements/plan/imported_manuscript/claimed_confirmation_evidence/" + field,
                      json_object=False)
    mapping = page.get("content_mapping")
    if mapping is None:
        if plan["mode"] == "bound" and document.get("collaboration") is not None:
            raise ModelError("design_requirements/page/content_mapping",
                             "a new bound argument Page requires its actual content mapping")
    elif mapping["narrative_ref"] != narrative_ref or mapping["plan_role_page_id"] != page["page_id"]:
        raise ModelError("design_requirements/page/content_mapping",
                         "Page mapping conflicts with the current Plan/Narrative")
    known_nodes = {node["node_id"] for node in narrative["nodes"]} if narrative else set()
    cache: dict = {}
    role = next((role for role in plan["input"]["page_roles"] if role["page_id"] == page["page_id"]), None)
    if role is None and plan["mode"] == "bound":
        raise ModelError("design_requirements/plan/input/page_roles/" + page["page_id"],
                         "a bound argument Page requires its actual Plan role")
    records = [(role, "design_requirements/plan/input/page_roles/" + page["page_id"])] if role else []
    records.extend((link, f"design_requirements/page/content_mapping/visible_links/{index}")
                   for index, link in enumerate((mapping or {}).get("visible_links") or []))
    for record, where in records:
        unknown = set(record["narrative_node_ids"]) - known_nodes
        if unknown:
            raise ModelError(where + "/narrative_node_ids", f"unknown current Narrative nodes: {sorted(unknown)}")
        try:
            validate_source_links(store, document, record["source_links"], where + "/source_links", cache)
        except (ModelError, StoreError, OSError) as exc:
            raise ModelError(where + "/source_links", str(exc)) from exc


def _decision_slices(store, document, page_id, refs) -> list[dict]:
    from . import dependency_slices

    consumed = []
    seen = set()
    for index, ref in enumerate(refs):
        where = f"design_requirements/decision_refs/{index}"
        decision = _read(store, ref, where)
        models.validate_decision_semantics(decision)
        pair = (ref["path"], ref["sha256"])
        if pair in seen:
            raise ModelError(where, "duplicate design decision")
        seen.add(pair)
        if decision["project_id"] != document["project_id"] or ref not in (document.get("collaboration") or {}).get("decisions", []):
            raise ModelError(where, "decision is not in the selected project snapshot")
        head = dependency_slices._head_for_identity(
            store, document, "decisions", "decision_id", decision["decision_id"])
        if head is None or head[0] != ref:
            raise ModelError(where, "decision is not the current version in the selected snapshot")
        if decision["topic"] not in ("style", "tradeoff") or page_id not in decision["scope"]["page_ids"]:
            raise ModelError(where, "decision does not apply to this Page's design")
        if not dependency_slices.accepted_decision(store, document, ref):
            raise ModelError(where, "design decision is no longer accepted and effective")
        sliced = dependency_slices.build_slice(store, document, kind="decision",
                                               identity=decision["decision_id"], projection="effective")
        consumed.append({"decision_ref": copy.deepcopy(ref), "sha256": sliced["sha256"]})
    return consumed


def resolve_content_requirements(store, document, page_ref, *, recipe_ref=None,
                                 decision_refs=(), recipe_parameters=None) -> dict:
    """Resolve from one selected snapshot, without writes or authority grants.

    ``recipe_parameters`` must be the Owner's effective recipe compilation; it
    is consumed in basis only and cannot override any business requirement.
    The caller registers these fixed digest projections in dependency_slices.
    """
    page = _read(store, page_ref, "design_requirements/page_ref")
    semantics = page_semantic_projection(page)
    page_id = page["page_id"]
    matches = [entry for entry in document.get("pages") or [] if entry["page_id"] == page_id]
    if len(matches) != 1 or matches[0]["page"] != page_ref:
        raise ModelError("design_requirements/page_ref", "Page is not current in the selected snapshot")
    plan_ref = document.get("content_plan")
    plan = _read(store, plan_ref, "design_requirements/plan_ref") if plan_ref else None
    mode = "fidelity"
    if plan is None:
        if document.get("collaboration") is not None:
            raise ModelError("design_requirements/plan_ref",
                             "a collaboration project requires its bound Plan or real imported mapping")
    else:
        models.validate_content_plan_semantics(plan)
        if plan["project_id"] != document["project_id"]:
            raise ModelError("design_requirements/plan_ref", "Plan belongs to another project")
        if plan["schema_version"] != "content_plan.v2" and document.get("collaboration") is not None:
            raise ModelError("design_requirements/plan_ref", "new collaboration production requires Plan v2")
        _validate_links(store, document, plan, page_id)
        if plan["schema_version"] == "content_plan.v2":
            if plan["mode"] == "planned":
                raise ModelError("design_requirements/plan/mode", "planned-only content cannot produce an actual Page")
            _validate_mapping(store, document, plan, page)
            mode = "fidelity" if plan["mode"] == "imported_mapping" else "planned"
    if recipe_parameters is not None and not isinstance(recipe_parameters, dict):
        raise ModelError("design_requirements/recipe_parameters", "compiled recipe parameters must be an object")
    if recipe_parameters is not None:
        try:
            canonical_json_bytes(recipe_parameters)
        except (TypeError, ValueError) as exc:
            raise ModelError("design_requirements/recipe_parameters", "compiled parameters must be canonical JSON") from exc
    if recipe_ref is not None:
        recipe = _read(store, recipe_ref, "design_requirements/recipe_ref")
        models.validate_schema("style_recipe", recipe)
        if recipe.get("project_id") != document["project_id"] or recipe_ref not in document.get("style_recipes", []):
            raise ModelError("design_requirements/recipe_ref", "recipe is not in the selected project snapshot")
        recipe_pages = ((recipe.get("scope") or {}).get("page_ids")
                        if recipe.get("schema_version") == "style_recipe.v3"
                        else (recipe.get("input") or {}).get("target_page_ids"))
        if page_id not in (recipe_pages or []):
            raise ModelError("design_requirements/recipe_ref", "recipe does not apply to the requested Page")
        if recipe_parameters is None:
            raise ModelError("design_requirements/recipe_parameters", "effective recipe compilation is required")
    elif recipe_parameters is not None:
        raise ModelError("design_requirements/recipe_ref", "compiled recipe parameters require their actual recipe Ref")
    if not isinstance(decision_refs, (list, tuple)):
        raise ModelError("design_requirements/decision_refs", "applicable decision Refs must be a list or tuple")
    decisions = list(decision_refs)
    selected = plan_page_projection(plan, page_id)
    visual = page["visual_spec"]
    requirements = {"schema_version": "content_requirements.v1", "mode": mode, **selected,
                    "text_visibility": "customer_visible_only.v1",
                    "structure_refs": {"atom_ids": sorted(content.atom_ids(page)),
                                       "node_ids": [node["node_id"] for node in visual.get("nodes") or []],
                                       "edge_ids": [edge["edge_id"] for edge in visual.get("edges") or []]},
                    "visual_intent": visual["intent"], "layout_hint": visual.get("layout_hint")}
    basis = {"schema_version": "content_basis.v1", "page_ref": copy.deepcopy(page_ref),
             "plan_ref": copy.deepcopy(plan_ref), "recipe_ref": copy.deepcopy(recipe_ref),
             "decision_refs": copy.deepcopy(decisions),
             "consumed": {"page_semantics_sha256": _digest(semantics),
                          "plan_page_sha256": _digest(selected) if plan is not None else None,
                          "plan_global_sha256": _digest(plan_global_projection(plan)) if plan else None,
                          "recipe_parameters_sha256": _digest(recipe_parameters) if recipe_ref else None,
                          "decision_slices": _decision_slices(store, document, page_id, decisions)}}
    return {"content_requirements": requirements, "content_basis": basis}
