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
            # The immutable policy/instruction prefix is historical evidence;
            # a newer prompt policy must not reinterpret an old Request.
            payload = json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True)
            if projection != actual["projection"] or not value["prompt"].endswith("Structured input:\n" + payload):
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
    layout_scope = style.pop("layout_page_ids", None)
    if "layout_notes" in overrides:
        style["layout_notes"] = overrides["layout_notes"]
    elif layout_scope is not None and page["page_id"] not in layout_scope:
        style["layout_notes"] = ""
    effective["language"] = overrides.get("language", design["language"])
    effective["styles"] = [style]
    effective["default_style_id"] = style["style_id"]
    effective["allowed_asset_ids"] = sorted(page_ids)
    effective["assets"] = [a for a in permitted_assets if a["asset_id"] in page_ids]
    return effective, style


def resolve_generation_design(store, document, page_entry, *, recipe_ref=None, design_policy=True):
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
    from .dependency_slices import accepted_decision, _head_for_identity
    decisions = []
    seen_decisions = set()
    for ref in (document.get("collaboration") or {}).get("decisions", []):
        decision = store.read_object_json(ref)
        identity = decision["decision_id"]
        if identity in seen_decisions:
            continue
        seen_decisions.add(identity)
        # Acceptance follows identity to its current version. Select that
        # same head before applying topic/scope filters or recording audit Refs.
        head = _head_for_identity(store, document, "decisions", "decision_id", identity)
        if head is None:
            continue
        ref, decision = head
        if (decision.get("topic") in ("style", "tradeoff")
                and page_entry["page_id"] in decision.get("scope", {}).get("page_ids", [])
                and accepted_decision(store, document, ref)):
            decisions.append(ref)
    if design_policy:
        visual = page.get("visual_spec") or {}
        explicit = visual.get("design_policy")
        if explicit:
            from .models import validate_page_semantics
            validate_page_semantics(page)
        # This default is created only at new preparation, never on frozen request reads.
        resolved["design_policy"] = deepcopy(explicit) if explicit else {
            "version": "design_policy.v1", "strategy": "model_designed",
            "purpose": visual.get("intent") or page["customer_visible"]["title"],
            "primary_object": page["customer_visible"]["title"],
            "free_layout": "Choose spatial composition while preserving all fixed copy, ownership and directed relationships.",
            "layout_instruction": visual.get("layout_hint") or "", "table_roles": []}
        if explicit:
            # A revised page layout replaces inherited layout instructions, including
            # executable recipe composition. Other recipe dimensions remain fixed.
            notes = visual.get("design_overrides", {}).get("layout_notes", explicit["layout_instruction"])
            resolved["styles"][0]["layout_notes"] = notes
            if "recipe_parameters" in resolved:
                resolved["recipe_parameters"]["composition"] = explicit["layout_instruction"]
                resolved["recipe_overrides"] = [item for item in resolved.get("recipe_overrides", [])
                                                 if item.get("field") != "composition"]
    resolved.update(resolve_content_requirements(
        store, document, page_entry["page"], recipe_ref=recipe_ref,
        decision_refs=decisions, recipe_parameters=resolved.get("recipe_parameters")))
    # Explicit policy is authoritative over a superseded Page hint and Plan projection.
    if design_policy:
        resolved["content_requirements"]["layout_hint"] = resolved["design_policy"]["layout_instruction"]
    return resolved


def consumed_design(resolved, *, store):
    """Audit Refs stay recorded; freshness compares the actual consumed values."""
    result = {key: value for key, value in resolved.items() if key != "content_basis"}
    if resolved.get("content_basis"):
        from .models import validate_decision_semantics
        basis = resolved["content_basis"]
        consumed = deepcopy(basis["consumed"])
        slices = consumed["decision_slices"]
        if basis["decision_refs"] != [item["decision_ref"] for item in slices]:
            raise ModelError("content_basis/decision_refs", "decision slices differ from their actual audit Refs")
        decisions = [store.read_object_json(item["decision_ref"]) for item in slices]
        if decisions:
            plan = store.read_object_json(basis["plan_ref"])
            for decision in decisions:
                validate_decision_semantics(decision)
                if (decision["project_id"] != plan["project_id"]
                        or decision["topic"] not in ("style", "tradeoff")
                        or resolved["content_requirements"]["page_id"] not in decision["scope"]["page_ids"]):
                    raise ModelError("content_basis/decision_refs", "decision is outside its actual project/Page design")
        # Immutable Ref versions remain in the original basis. The registered
        # effective slice supplies semantics; the actual Decision supplies its
        # identity so equal values from different decisions never collapse.
        consumed["decision_slices"] = sorted([
            {"decision_id": decision["decision_id"],
             "sha256": item["sha256"]}
            for item, decision in zip(slices, decisions)
        ], key=lambda item: item["decision_id"])
        result["consumed_basis"] = consumed
    return result


def adopted_blueprint_design(store, document, page_entry):
    """Read the adopted image's owned, immutable generation design, if modern.

    Closed observations are historical facts: reading their Request does not
    reauthenticate an old execution against this reader's installation. No
    latest recipe, caller label or current writer floor supplies a missing
    lineage. A genuinely older Request without requirements stays legacy.
    """
    from . import generation, tasks
    from .models import validate_artifact_semantics, validate_schema
    from .store import StoreError

    ref = page_entry.get("blueprint")
    if ref is None:
        return None
    where = "blueprint/provenance/generation_request"
    try:
        artifact = store.read_object_json(ref)
        validate_artifact_semantics(artifact)
        if artifact["role"] != "blueprint" or artifact["page_id"] != page_entry["page_id"]:
            raise ModelError(where, "adopted blueprint has a different page or role")
        provenance = artifact["provenance"]
        request_ref = provenance.get("generation_request")
        if request_ref is None:
            # A stripped modern provenance must not become a legacy fallback.
            for task_ref in document.get("tasks") or []:
                owner = store.read_object_json(task_ref)
                if (page_entry["page_id"] not in (owner.get("scope_pages") or [])
                        or "content_requirements_v1" not in (owner.get("required_capabilities") or [])):
                    continue
                for result_ref in owner.get("result_refs") or []:
                    result = store.read_object_json(result_ref)
                    if (result_ref == ref or (result.get("schema_version") == "deck_artifact.v1"
                            and result.get("role") == "blueprint" and result.get("page_id") == artifact["page_id"]
                            and result.get("file") == artifact["file"])):
                        raise ModelError(where, "modern blueprint is missing its owned generation Request")
            if provenance.get("generation_attempt") is not None:
                raise ModelError(where, "generation provenance has no Request")
            return None
        request = store.read_object_json(request_ref)
        validate_schema("generation_request", request)
        if (request["project_id"] != document["project_id"]
                or request["input_hash"] != sha256_bytes(canonical_json_bytes(request["input"]))):
            raise ModelError(where, "generation Request project or frozen hash differs")
        owner = tasks._lookup_task(document, request["task_id"], store)
        if (owner["kind"] != "blueprint" or owner["scope_pages"] != [page_entry["page_id"]]
                or request_ref not in (owner.get("generation_requests") or [])
                or ref not in (owner.get("result_refs") or [])):
            raise ModelError(where, "Request and adopted blueprint are not owned by their actual Task")
        attempt_ref = provenance.get("generation_attempt")
        if attempt_ref is None or attempt_ref not in (owner.get("generation_attempts") or []):
            raise ModelError(where, "generation Attempt is not owned by the actual Task")
        attempt = store.read_object_json(attempt_ref)
        validate_schema("generation_attempt", attempt)
        if (attempt["task_id"] != owner["task_id"] or attempt["project_id"] != document["project_id"]
                or attempt["request_ref"] != request_ref or artifact["file"] not in attempt["output_refs"]
                or provenance.get("generated_from_page") != request["input"]["page"]["page_ref"]):
            raise ModelError(where, "adopted image, Page and Attempt do not bind the same Request")
        prepared, _ = stored_blueprint_request(store, owner)
        resolved = (prepared or {}).get("resolved_design_context")
        frozen = request["input"]["design_context"]
        modern = ("content_requirements_v1" in (owner.get("required_capabilities") or [])
                  or resolved is not None or "content_requirements" in frozen or "content_basis" in frozen)
        if not modern:
            return None
        if (resolved is None or frozen != resolved
                or request["input"]["page"] != {"page_id": page_entry["page_id"],
                                                  "page_ref": resolved["content_basis"]["page_ref"]}):
            raise ModelError(where, "modern Request does not retain its full actual preparation")
        # The original formal preparation checks Page membership and prompt
        # projection; the frozen Request must retain those exact consumer inputs.
        expected = generation.prepared_input(store, document, owner)
        for key in ("page", "design_context", "prompt", "references", "basis", "template_ref"):
            if request["input"][key] != expected[key]:
                raise ModelError(where, "frozen Request differs from its owned preparation: " + key)
        recipe_ref = request["input"].get("style_recipe_ref")
        if (recipe_ref != expected.get("style_recipe_ref")
                or recipe_ref != resolved["content_basis"]["recipe_ref"]
                or request["input"]["constraints"] != expected["constraints"]):
            raise ModelError(where, "frozen recipe or constraints differ from the actual Task")
        return {"resolved_design_context": deepcopy(resolved), "recipe_ref": deepcopy(recipe_ref)}
    except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, ModelError):
            raise
        raise ModelError(where, "unreadable or invalid adopted generation lineage") from exc


def resolve_page_design(store, document, page_entry, *, require_current=False):
    """Full immutable adopted design for writers; legacy Pages keep old behavior."""
    bound = adopted_blueprint_design(store, document, page_entry)
    if bound is None:
        page = store.read_object_json(page_entry["page"])
        return resolve_design(page, document["design_context"],
                              document["design_context"].get("assets") or [])[0]
    resolved = bound["resolved_design_context"]
    if require_current and consumed_design(resolved, store=store) != consumed_design(
            resolve_generation_design(store, document, page_entry, recipe_ref=bound["recipe_ref"]), store=store):
        raise ModelError("blueprint/content_basis", "adopted blueprint's consumed Page/Plan/design inputs changed")
    return resolved


def resolve_page_rendering_design(store, document, page_entry):
    """Current rendering slice using the adopted image's exact recipe identity.

    This lets a dependency checker report a relevant current change, while a
    writer receives the original complete context only after freshness checks.
    """
    bound = adopted_blueprint_design(store, document, page_entry)
    if bound is not None:
        return resolve_generation_design(store, document, page_entry, recipe_ref=bound["recipe_ref"])
    return resolve_page_design(store, document, page_entry)


def design_handoff_protocol_fields(store, document, entries):
    """Existing envelope protocol, explicit capabilities for new consumers.

    This is not a change-plan binding: direct Host tasks need no fictitious
    change_plan capability. Historical tasks are never rewritten by this read.
    """
    capabilities = set()
    for entry in entries:
        bound = adopted_blueprint_design(store, document, entry)
        if bound is None:
            continue
        resolve_page_design(store, document, entry, require_current=True)
        capabilities.add("content_requirements_v1")
        if bound["recipe_ref"] is not None:
            capabilities.add("style_recipe")
            if store.read_object_json(bound["recipe_ref"])["schema_version"] == "style_recipe.v3":
                capabilities.add("style_recipe_v3")
    return {"protocol_version": "changes.v1", "required_capabilities": sorted(capabilities)} if capabilities else {}


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
    for key in ("content_requirements", "recipe_parameters", "recipe_overrides", "design_policy"):
        if key in resolved_design_context:
            projection[key] = deepcopy(resolved_design_context[key])
    policy = resolved_design_context.get("design_policy")
    policy_instruction = ""
    if policy:
        projection["visual_spec"]["layout_hint"] = policy["layout_instruction"]
        policy_instruction = (
            "Design policy (design_policy.v1): agreed_layout follows the explicit layout_instruction; "
            "model_designed chooses composition within free_layout, treating layout_instruction as guidance. "
            "Purpose and primary_object guide hierarchy, not extra visible copy. Preserve all fixed nodes, "
            "edges, direction, responsibility and ownership regardless of strategy. No minimum node count "
            "or nonempty layout hint proves quality. Tables are comparisons by default; preserve their cells, "
            "units, row/column ownership and comparisons. Only tables explicitly tagged content_inventory "
            "may be rearranged as non-table composition, retaining every cell and its ownership. "
            "Page layout notes replace project layout notes; only effective notes below apply.\n")
    requirements = resolved_design_context.get("content_requirements") or {}
    visibility_instruction = ""
    if "text_visibility" in requirements:
        from .models import validate_schema
        validate_schema("content_requirements", requirements)
        visibility_instruction = (
            "Text visibility (customer_visible_only.v1): customer_visible is the ONLY source of text to render. "
            "content_requirements is non-rendering design context: content_profile classifies composition; "
            "density_rationale explains density; page_role describes purpose; required_qualifications contains "
            "Narrative node IDs, never copy to print. Do not turn these fields, source locators, provenance or "
            "author verification into slide text. Preserve every business condition, attribution and qualification "
            "already authored in customer_visible, even when it contains words such as source or assumption. "
            "If a required business condition is missing from fixed copy, return the gap to the content stage; "
            "do not invent or silently remove copy.\n"
        )
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
        "If a quantitative judgment requires data absent from the input, return that gap to the content stage "
        "for the necessary evidence; preserve the fixed copy and qualifications. Do not substitute a decorative "
        "quantity chart or invent schematic data. Preserve qualitative mechanisms or teaching illustrations only "
        "when the fixed manuscript explicitly requests them and they create no quantitative impression. "
        "Do not omit modules; connect arrows to their actual nodes; "
        "use only permitted assets; no watermark; no internal notes\n"
        + visibility_instruction + policy_instruction + "Structured input:\n" + payload
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
