"""Initial design and feasibility use the existing immutable style ledger."""

from copy import deepcopy
import json

from . import changes
from .design_requirements import resolve
from .models import ModelError


def proposal(store, document, value):
    from .styles import fail

    intent = value["intent"]
    ids = value["target_page_ids"]
    if intent != "feasibility" and not ids:
        fail("target_page_ids", "initial design needs current representative Page references")
    refs = value["reference_refs"]
    if intent == "restyle" and not refs:
        fail("reference_refs", "restyle needs actual fixed image references")
    changes._reference_files(store, document, refs)
    params = value["recipe_draft"]
    fonts = {f["font_id"] for f in document["design_context"]["fonts"]}
    if any(params["typography"][k] not in fonts for k in ("body_font_id", "heading_font_id")):
        fail("recipe_draft/typography", "choose fonts registered in the project")
    targets, profiles = [], []
    for page_id in ids:
        entry = next((e for e in document["pages"] if e["page_id"] == page_id), None)
        if not entry:
            fail("target_page_ids", f"{page_id}: no current Page")
        if intent == "restyle" and not entry.get("blueprint"):
            fail("target_page_ids", f"{page_id}: restyle requires the actual current original image")
        context = resolve(store, document, entry, document["design_context"])
        req = context["content_requirements"]
        targets.append(
            {
                "page_id": page_id,
                "page_ref": entry["page"],
                "blueprint_ref": entry.get("blueprint"),
                "content": deepcopy(store.read_object_json(entry["page"])["customer_visible"]),
            }
        )
        profiles.append(
            {
                "page_id": page_id,
                "content_profile": req["content_profile"],
                "density_rationale": req["density_rationale"],
                "required_qualifications": req["required_qualifications"],
                "structure_refs": req["structure_refs"],
            }
        )
    return {
        "schema_version": "style_proposal.v3",
        "project_id": document["project_id"],
        "base_revision": document["revision_id"],
        "input": deepcopy(value),
        "intent": intent,
        "targets": targets,
        "reference_sources": {"references": deepcopy(refs)},
        "dimensions": {k: json.dumps(v, ensure_ascii=False, sort_keys=True) for k, v in params.items() if k != "allowed_page_overrides"},
        "preserve_dimensions": {},
        "conflicts": [],
        "diff": [{"field": "recipe_draft", "before": None, "after": deepcopy(params)}],
        "preserve_target_content": True,
        "suggestion_state": "none",
        "recipe_draft": deepcopy(params),
        "page_profiles": profiles,
        "layout_rationale": value.get("layout_rationale", value["instruction"]),
        "sample_targets": [{"page_id": p["page_id"], "profile": p["content_profile"]} for p in profiles],
        "uncovered_cases": deepcopy(value.get("uncovered_cases", [])),
        "tradeoffs": deepcopy(value.get("tradeoffs", [])),
    }


def project(store, document, recipe, entry, ref):
    """Project one immutable recipe to the current Page, without rewriting it."""
    page = store.read_object_json(entry["page"])
    design = deepcopy(document["design_context"])
    params = recipe["recipe_draft"]
    allowed = set(params.get("allowed_page_overrides", []))
    overrides = (page.get("visual_spec") or {}).get("design_overrides") or {}
    for key in ("body_font_id", "heading_font_id"):
        if key in overrides and key not in allowed and overrides[key] != params["typography"][key]:
            raise ModelError("design/recipe/page_override", f"{entry['page_id']}: {key} conflicts with recipe; decide explicitly")
    style_id = (page.get("visual_spec") or {}).get("style_ref") or design["default_style_id"]
    style = next(s for s in design["styles"] if s["style_id"] == style_id)
    style["colors"] = deepcopy(params["palette"])
    style["typography"] = deepcopy(params["typography"])
    style["layout_notes"] = params["composition"]
    # Density/spacing/icon/line values are the recipe's actual visual inputs,
    # not a second writable configuration or additional customer-visible copy.
    style["recipe_rules"] = {k: deepcopy(params[k]) for k in ("density", "spacing", "lines", "icons")}
    return resolve(store, document, entry, design, recipe_ref=ref)
