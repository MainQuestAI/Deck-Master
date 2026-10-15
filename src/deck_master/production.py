"""Codex-hosted blueprint production requests.

The package prepares an exact, inspectable prompt projection.  It does not
call a provider or read API credentials: the Codex host executes its built-in
image tool and returns the resulting file through the normal task envelope.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .models import ModelError, canonical_json_bytes, sha256_bytes


def stored_blueprint_request(store, task):
    """Return the unique actual immutable preparation and its Task.inputs Ref.

    The request is never regenerated from current Pages or cached on the Task.
    Legacy tasks may have no request; generation.v1 tasks may not.
    """
    from .store import StoreError
    found = []
    for ref in task.get("inputs") or []:
        try:
            value = store.read_object_json(ref)
        except (StoreError, OSError, ValueError, TypeError) as exc:
            raise ModelError("task/inputs", "unreadable immutable task input") from exc
        if not isinstance(value, dict) or value.get("schema_version") != "deck_blueprint_request.v1":
            continue
        projection = value.get("projection")
        if (value.get("page_id") not in (task.get("scope_pages") or [])
                or task.get("scope_pages") != [value.get("page_id")]
                or not isinstance(value.get("prompt"), str) or not value["prompt"]
                or not isinstance(value.get("projection"), dict)
                or value["projection"].get("page_id") != value["page_id"]
                or value.get("prompt_sha256") != sha256_bytes(value["prompt"].encode("utf-8"))
                or value.get("projection_sha256") != sha256_bytes(canonical_json_bytes(value["projection"]))):
            raise ModelError("task/inputs", "invalid blueprint preparation identity or hashes")
        if (value.get("host") != "codex_imagegen"
                or not isinstance(value.get("requires"), list)
                or not all(isinstance(item, str) for item in value["requires"])
                or not {"image_generation", "image_inspection", "local_file_access"} <= set(value["requires"])
                or not all(isinstance(projection.get(key), dict) for key in ("canvas", "style", "customer_visible", "visual_spec"))
                or not all(isinstance(projection.get(key), list) for key in ("fonts", "permitted_assets"))
                or not isinstance(projection.get("language"), str)
                or not projection["customer_visible"].get("title")):
            raise ModelError("task/inputs", "incomplete stored blueprint preparation")
        resolved = value.get("resolved_design_context")
        if resolved is not None:
            from .models import validate_schema
            validate_schema("content_requirements", resolved.get("content_requirements"))
            validate_schema("content_basis", resolved.get("content_basis"))
            page_ref = resolved["content_basis"]["page_ref"]
            if page_ref not in task.get("inputs", []):
                raise ModelError("task/inputs", "requirements Page is outside actual immutable task inputs")
            page = store.read_object_json(page_ref)
            actual = project_prompt(page, resolved, resolved.get("assets") or [])
            if projection != actual["projection"] or not value["prompt"].endswith(actual["prompt"]):
                raise ModelError("task/inputs", "requirements/design projection differs from its actual prompt")
        found.append((value, ref))
    if len(found) > 1 and any(item[0] != found[0][0] for item in found[1:]):
        raise ModelError("task/inputs", "conflicting immutable blueprint preparations")
    if not found:
        if task.get("protocol_version") == "generation.v1":
            raise ModelError("task/inputs", "stored blueprint preparation is missing")
        return None, None
    return found[0]


def _visible_block(block: dict[str, Any]) -> dict[str, Any]:
    """Keep the complete customer-visible block, including nested items/cells."""
    return json.loads(json.dumps(block, ensure_ascii=False))


def _style_for(page: dict[str, Any], design_context: dict[str, Any]) -> dict[str, Any]:
    visual = page.get("visual_spec") or {}
    style_id = visual.get("style_ref") or design_context.get("default_style_id")
    styles = design_context.get("styles") or []
    style = next((item for item in styles if item.get("style_id") == style_id), None)
    if style is None:
        raise ModelError("visual_spec/style_ref", f"unknown style {style_id!r}")
    return style


def resolve_design(page, design, permitted_assets):
    effective = deepcopy(design)
    style = deepcopy(_style_for(page, design))
    overrides = (page.get("visual_spec") or {}).get("design_overrides") or {}
    project_ids = set(design.get("allowed_asset_ids") or [])
    page_ids = set(overrides.get("allowed_asset_ids", project_ids))
    if not page_ids <= project_ids:
        raise ModelError("visual_spec/design_overrides/allowed_asset_ids", "page asset permissions exceed project")
    asset_map = {a["asset_id"]: a for a in permitted_assets}
    for aid in project_ids:
        if aid not in asset_map or asset_map[aid].get("external_use") != "allowed":
            raise ModelError("design_context/allowed_asset_ids", f"asset {aid!r} is missing or not allowed for external use")
    fonts = {f["font_id"]: f for f in design.get("fonts") or []}
    for slot in ("body_font_id", "heading_font_id"):
        fid = overrides.get(slot, style["typography"].get(slot))
        if fid not in fonts:
            raise ModelError(f"visual_spec/design_overrides/{slot}", f"unknown font {fid!r}")
        style["typography"][slot] = fid
    effective["language"] = overrides.get("language", design["language"])
    effective["styles"] = [style]
    effective["default_style_id"] = style["style_id"]
    effective["allowed_asset_ids"] = sorted(page_ids)
    effective["assets"] = [a for a in permitted_assets if a["asset_id"] in page_ids]
    return effective, style


def resolve_generation_design(store, document, page_entry, *, recipe_ref=None):
    """Resolve the exact current Page/Plan/recipe consumption before prompting."""
    from .design_requirements import resolve_content_requirements
    page = store.read_object_json(page_entry["page"])
    design = document["design_context"]
    if recipe_ref is not None:
        recipe = store.read_object_json(recipe_ref)
    else:
        recipe = None
    if recipe and recipe.get("schema_version") == "style_recipe.v3":
        from .design_recipe import compile_design
        resolved = compile_design(page, design, recipe, page_entry["page_id"])
    else:
        resolved, _ = resolve_design(page, design, design.get("assets") or [])
        if recipe:
            # Old executable recipes retain their actual selected rule contract.
            if recipe.get("schema_version") == "style_recipe.v2":
                from .styles import effective_spec
                resolved["recipe_parameters"] = effective_spec(recipe)
            else:
                resolved["recipe_parameters"] = deepcopy(recipe["dimensions"])
    # Only used fonts and their explicitly registered fallback closure enter
    # this consumer; changing an unused registered face cannot stale it.
    fonts = {font["font_id"]: font for font in resolved.get("fonts") or []}
    typography = resolved["styles"][0]["typography"]
    used = {typography["body_font_id"], typography["heading_font_id"]}
    pending = list(used)
    while pending:
        font = fonts[pending.pop()]
        for fallback in font.get("fallback_font_ids") or []:
            if fallback not in fonts:
                raise ModelError("fonts/fallback_font_ids", "fallback is not registered")
            if fallback not in used:
                used.add(fallback); pending.append(fallback)
    resolved["fonts"] = [font for font in resolved.get("fonts") or [] if font["font_id"] in used]
    from .dependency_slices import accepted_decision
    decisions = []
    for ref in (document.get("collaboration") or {}).get("decisions", []):
        decision = store.read_object_json(ref)
        if (decision.get("topic") in ("style", "tradeoff")
                and page_entry["page_id"] in decision.get("scope", {}).get("page_ids", [])
                and accepted_decision(store, document, ref)):
            decisions.append(ref)
    resolved.update(resolve_content_requirements(
        store, document, page_entry["page"], recipe_ref=recipe_ref,
        decision_refs=decisions, recipe_parameters=resolved.get("recipe_parameters")))
    return resolved


def consumed_design(resolved):
    """Audit Refs stay recorded; freshness compares the actual consumed values."""
    result = {key: value for key, value in resolved.items() if key != "content_basis"}
    if resolved.get("content_basis"):
        result["consumed_basis"] = resolved["content_basis"]["consumed"]
    return result


def style_font_fingerprint(design, style, asset_sha):
    """Font-reality slice of a style fingerprint (P1-06).

    ``asset_sha`` maps a design asset_id to its stored artifact content sha
    (or None). Resolved font files hash by content, so swapping bytes under
    the same font_id always changes the fingerprint; unresolvable fonts are
    conservatively recorded by their declared identity.
    """
    fonts_by_id = {f.get("font_id"): f for f in (design or {}).get("fonts") or []}
    typography = (style or {}).get("typography") or {}
    entries = []
    for slot in ("body_font_id", "heading_font_id"):
        font_id = typography.get(slot)
        font = fonts_by_id.get(font_id) or {}
        sha = asset_sha(font.get("asset_id")) if font.get("asset_id") else None
        if sha:
            entries.append((slot, "asset", sha))
        else:
            entries.append((slot, "decl", font_id, font.get("family"), font.get("face"),
                            font.get("weight")))
    return repr(sorted(entries))


def project_prompt(
    page: dict[str, Any],
    resolved_design_context: dict[str, Any],
    permitted_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project one Page and its resolved design into the actual ImageGen input.

    ``projection`` is stored beside the prompt so tests and later review can
    prove which source fields entered the submitted request.  Speaker notes
    and ``internal_only`` are deliberately excluded from the visible design.
    """
    visible = page.get("customer_visible") or {}
    visual = page.get("visual_spec") or {}
    resolved_design_context, style = resolve_design(page, resolved_design_context, permitted_assets)
    assets = resolved_design_context["assets"]
    projection = {
        "page_id": page.get("page_id"),
        "language": resolved_design_context.get("language") or "zh-CN",
        "canvas": resolved_design_context.get("canvas") or {},
        "style": style,
        "fonts": resolved_design_context.get("fonts") or [],
        "permitted_assets": assets,
        "customer_visible": {
            "title": visible.get("title") or "",
            "subtitle": visible.get("subtitle") or "",
            "body_blocks": [_visible_block(block) for block in visible.get("body_blocks") or []],
            "labels": visible.get("labels") or [],
            "footnotes": visible.get("footnotes") or [],
            "callouts": visible.get("callouts") or [],
        },
        "visual_spec": {
            "intent": visual.get("intent") or "",
            "layout_hint": visual.get("layout_hint") or "",
            "reference_mode": visual.get("reference_mode") or "new_design",
            "nodes": visual.get("nodes") or [],
            "edges": visual.get("edges") or [],
            "style_ref": visual.get("style_ref") or resolved_design_context.get("default_style_id"),
        },
    }
    for key in ("content_requirements", "recipe_parameters", "recipe_overrides"):
        if key in resolved_design_context:
            projection[key] = deepcopy(resolved_design_context[key])
    payload = json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True)
    prompt = (
        "Use case: productivity-visual\n"
        "Asset type: editable-presentation blueprint reference, one complete slide\n"
        f"Canvas: {projection['canvas']['width_px']}x{projection['canvas']['height_px']} px; "
        f"physical size {projection['canvas']['slide_width_in']}x{projection['canvas']['slide_height_in']} in; contain fit\n"
        "Primary request: Create a polished business slide blueprint from the exact structured input below. "
        "Preserve every visible fact, number, unit, label, footnote, node and directed relationship.\n"
        "Style/medium: precise enterprise presentation design; clear hierarchy; production-ready reference image\n"
        "Composition/framing: use the supplied canvas, layout intent and node relationships; keep all content inside safe margins\n"
        "Text: render the supplied customer-visible text verbatim and legibly\n"
        "Constraints: do not add claims or invent numeric values, dates, customer data, or outcomes. "
        "If a chart needs data absent from the input, use an unlabeled schematic marked 示意数据, "
        "without plausible-looking values. Do not omit modules; connect arrows to their actual nodes; "
        "use only permitted assets; no watermark; no internal notes\n"
        "Structured input:\n" + payload
    )
    result = {
        "schema_version": "deck_blueprint_request.v1",
        "page_id": page.get("page_id"),
        "prompt": prompt,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "projection": projection,
        "projection_sha256": sha256_bytes(canonical_json_bytes(projection)),
        "host": "codex_imagegen",
        "requires": ["image_generation", "image_inspection", "local_file_access"],
    }
    if "content_requirements" in resolved_design_context:
        result["resolved_design_context"] = deepcopy(resolved_design_context)
    return result
