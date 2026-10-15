"""Pure v3 design planning and compilation over immutable project inputs.

This module reads fixed objects but never writes, claims a task, authorizes a
call or adopts a candidate.  The public service owns those boundaries.  Planning
prose is evidence; only the typed recipe parameters execute.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re

from .models import ModelError, canonical_json_bytes, sha256_bytes, validate_ref, validate_schema


DIMENSIONS = ("palette", "typography", "density", "composition", "spacing", "lines", "icons")
RULE_DIMENSIONS = DIMENSIONS[2:]
TYPOGRAPHY_FIELDS = ("body_font_id", "heading_font_id", "body_size_pt", "heading_size_pt", "auxiliary_size_pt")
PLANNING_FIELDS = ("page_profiles", "layout_rationale", "sample_targets", "uncovered_cases", "tradeoffs")
INPUT_FIELDS = {"schema_version", "project_id", "base_revision", "intent", "target_page_ids",
                "instruction", "reference_refs", "recipe_draft", *PLANNING_FIELDS, "parent_recipe_id"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _error(path, message):
    raise ModelError(path, message)


def _text(value, path):
    if not isinstance(value, str) or not value.strip():
        _error(path, "provide a nonempty concrete string")


def _strings(value, path, *, unique=False):
    if not isinstance(value, list):
        _error(path, "must be an array of strings")
    for index, item in enumerate(value):
        _text(item, f"{path}/{index}")
    if unique and len(set(value)) != len(value):
        _error(path, "duplicate values are not allowed")


def _parameter(key, value, path):
    if key == "palette":
        if not isinstance(value, dict) or not value:
            _error(path, "palette must contain explicit color tokens")
        for token, color in value.items():
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", token):
                _error(path, "invalid color token")
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                _error(f"{path}/{token}", "use a six-digit hex color")
    elif key == "typography":
        if not isinstance(value, dict) or set(value) != set(TYPOGRAPHY_FIELDS):
            _error(path, "use the five explicit Document style.typography fields")
        for slot in TYPOGRAPHY_FIELDS[:2]:
            if not isinstance(value[slot], str) or not IDENTIFIER.fullmatch(value[slot]):
                _error(f"{path}/{slot}", "use a registered font identifier")
        for slot in TYPOGRAPHY_FIELDS[2:]:
            number = value[slot]
            if (isinstance(number, bool) or not isinstance(number, (int, float))
                    or not math.isfinite(number) or number <= 0):
                _error(f"{path}/{slot}", "use a finite positive point size")
    elif key in RULE_DIMENSIONS:
        _text(value, path)
    else:
        _error(path, "unknown visual dimension")


def validate_parameters(parameters, page_ids, *, path="recipe_draft"):
    """Validate executable parameters; page rules are complete typed replacements."""
    if not isinstance(parameters, dict):
        _error(path, "must be an explicit typed recipe object")
    required = {*DIMENSIONS, "allowed_overrides"}
    if not required <= set(parameters) or set(parameters) - required - {"page_rules"}:
        _error(path, "use all seven visual dimensions, allowed_overrides and optional page_rules")
    for key in DIMENSIONS:
        _parameter(key, parameters[key], f"{path}/{key}")
    allowed = parameters["allowed_overrides"]
    _strings(allowed, f"{path}/allowed_overrides", unique=True)
    if set(allowed) - set(DIMENSIONS):
        _error(f"{path}/allowed_overrides", "only visual dimensions may be overridden")
    page_rules = parameters.get("page_rules", {})
    if not isinstance(page_rules, dict):
        _error(f"{path}/page_rules", "must map target page IDs to visual parameters")
    if set(page_rules) - set(page_ids):
        _error(f"{path}/page_rules", "page rules must name explicitly selected targets")
    for page_id, rules in page_rules.items():
        if not isinstance(rules, dict) or not rules or set(rules) - set(allowed):
            _error(f"{path}/page_rules/{page_id}", "every page rule must be explicitly allowed by the recipe")
        for key, value in rules.items():
            _parameter(key, value, f"{path}/page_rules/{page_id}/{key}")


def _references(value):
    refs = value.get("reference_refs")
    if not isinstance(refs, list) or len(refs) > 16:
        _error("reference_refs", "use an ordered array of at most 16 fixed references")
    seen = set()
    for index, reference in enumerate(refs):
        path = f"reference_refs/{index}"
        if not isinstance(reference, dict) or reference.get("role") != "reference":
            _error(path, "each style reference must have role=reference")
        external = reference.get("kind") == "external"
        keys = {"kind", "reference_id", "artifact_ref", "role"} if external else {"page_id", "revision_id", "artifact_ref", "role"}
        if set(reference) != keys:
            _error(path, "use a fixed project-page or imported external reference description")
        for key in keys - {"artifact_ref"}:
            _text(reference[key], f"{path}/{key}")
        validate_ref(reference["artifact_ref"], where=f"{path}/artifact_ref")
        identity = (reference["artifact_ref"]["path"], reference["artifact_ref"]["sha256"])
        if identity in seen:
            _error(path, "duplicate reference image")
        seen.add(identity)
    return deepcopy(refs)


def _planning(value, known_page_ids):
    _text(value.get("layout_rationale"), "layout_rationale")
    for key in ("uncovered_cases", "tradeoffs"):
        _strings(value.get(key), key)
    profiles = value.get("page_profiles")
    if not isinstance(profiles, list):
        _error("page_profiles", "must be an array of page profiles")
    seen = set()
    for index, profile in enumerate(profiles):
        path = f"page_profiles/{index}"
        if not isinstance(profile, dict) or set(profile) != {"page_id", "profile", "density", "diagram", "task"}:
            _error(path, "use page_id, profile, density, diagram and task")
        for key in ("page_id", "profile", "density", "task"):
            _text(profile[key], f"{path}/{key}")
        if profile["diagram"] is not None:
            _text(profile["diagram"], f"{path}/diagram")
        if profile["page_id"] not in known_page_ids or profile["page_id"] in seen:
            _error(f"{path}/page_id", "profile must name one unique real or planned page")
        seen.add(profile["page_id"])
    samples = value.get("sample_targets")
    if not isinstance(samples, list):
        _error("sample_targets", "must be an array of coverage choices")
    seen = set()
    for index, sample in enumerate(samples):
        path = f"sample_targets/{index}"
        if not isinstance(sample, dict) or set(sample) != {"page_id", "coverage_risks"}:
            _error(path, "use page_id and coverage_risks")
        _text(sample["page_id"], f"{path}/page_id")
        _strings(sample["coverage_risks"], f"{path}/coverage_risks", unique=True)
        if not sample["coverage_risks"]:
            _error(f"{path}/coverage_risks", "state the risk each representative page covers")
        if sample["page_id"] not in value["target_page_ids"] or sample["page_id"] in seen:
            _error(f"{path}/page_id", "sample must name one unique selected target")
        seen.add(sample["page_id"])
    if value["intent"] != "feasibility":
        if not samples:
            _error("sample_targets", "select representative targets and state their covered risks")
        if not set(value["target_page_ids"]) <= {profile["page_id"] for profile in profiles}:
            _error("page_profiles", "profile each selected representative target explicitly")


def _parent(store, document, recipe_id):
    if recipe_id is None:
        return None, None
    _text(recipe_id, "parent_recipe_id")
    for ref in document.get("style_recipes", []):
        record = store.read_object_json(ref)
        if record.get("recipe_id") == recipe_id:
            validate_schema("style_recipe", record)
            if record.get("project_id") != document["project_id"]:
                _error("parent_recipe_id", "parent recipe belongs to another project")
            return record, ref
    _error("parent_recipe_id", "parent recipe must exist in this selected committed project")


def _diff(before, after, *, source=None):
    rows = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            row = {"field": key, "before": deepcopy(before.get(key)), "after": deepcopy(after.get(key))}
            if source is not None:
                row["source"] = source
            rows.append(row)
    return rows


def build_proposal(store, document, value):
    """Build a zero-call proposal from current Pages, fixed references and a recipe draft."""
    if not isinstance(value, dict) or set(value) - INPUT_FIELDS:
        _error("input", "unknown style_input.v3 field")
    if value.get("schema_version") != "style_input.v3":
        _error("schema_version", "use style_input.v3")
    if value.get("project_id") != document["project_id"]:
        _error("project_id", "input belongs to another project")
    if value.get("base_revision") != document["revision_id"]:
        _error("base_revision", "project changed; propose against the selected current snapshot")
    if value.get("intent") not in {"initial_design", "restyle", "feasibility"}:
        _error("intent", "use initial_design, restyle or feasibility")
    _text(value.get("instruction"), "instruction")
    ids = value.get("target_page_ids")
    _strings(ids, "target_page_ids", unique=True)
    if value["intent"] != "feasibility" and not ids:
        _error("target_page_ids", "select actual representative Pages")
    references = _references(value)
    if value["intent"] == "restyle" and not references:
        _error("reference_refs", "restyle requires a fixed real style reference")
    if any(reference.get("page_id") in ids for reference in references):
        _error("reference_refs", "a selected target cannot also be its independent style reference")
    if references:
        from .changes import _reference_files
        _reference_files(store, document, references)
    entries = {entry["page_id"]: entry for entry in document.get("pages", [])}
    if len(entries) != len(document.get("pages", [])):
        _error("target_page_ids", "duplicate Document page identity")
    plan = store.read_object_json(document["content_plan"]) if document.get("content_plan") else None
    if plan is not None:
        validate_schema("content_plan", plan)
        if plan.get("project_id") != document["project_id"]:
            _error("content_plan", "Plan belongs to another project")
    if value["intent"] == "feasibility" and document.get("narrative"):
        narrative = store.read_object_json(document["narrative"])
        validate_schema("narrative", narrative)
        if narrative.get("project_id") != document["project_id"]:
            _error("narrative", "Narrative belongs to another project")
    planned_ids = set((plan.get("input") or {}).get("page_order", [])) if plan else set()
    known_ids = set(entries) | (planned_ids if value["intent"] == "feasibility" else set())
    if set(ids) - known_ids:
        _error("target_page_ids", "target is absent from the selected project Page/Plan snapshot")
    if value["intent"] == "feasibility" and not ids and not (document.get("narrative") or plan):
        _error("basis", "feasibility requires actual Page, Narrative or Plan inputs")
    _planning(value, known_ids)
    validate_parameters(value.get("recipe_draft"), ids)
    font_ids = {font["font_id"] for font in document.get("design_context", {}).get("fonts", [])}
    draft = value["recipe_draft"]
    typographies = [("recipe_draft/typography", draft["typography"])]
    typographies.extend((f"recipe_draft/page_rules/{pid}/typography", rules["typography"])
                        for pid, rules in draft.get("page_rules", {}).items() if "typography" in rules)
    for path, typography in typographies:
        for slot in TYPOGRAPHY_FIELDS[:2]:
            if typography[slot] not in font_ids:
                _error(f"{path}/{slot}", "font is not registered in this project snapshot")
    from .dependency_slices import make_dependency_slice
    targets, basis = [], []
    for page_id in ids:
        entry = entries.get(page_id)
        if entry is None:  # Feasibility may discuss genuinely planned, unmaterialized pages.
            continue
        page = store.read_object_json(entry["page"])
        validate_schema("page", page)
        if page["page_id"] != page_id:
            _error("targets/page_ref", "Page ref does not contain the selected stable page identity")
        blueprint = entry.get("blueprint")
        if value["intent"] == "restyle" and blueprint is None:
            _error("targets/blueprint_ref", "restyle requires the target's actual current original image")
        if blueprint is not None:
            artifact = store.read_object_json(blueprint)
            validate_schema("artifact", artifact)
            if artifact.get("role") != "blueprint" or artifact.get("page_id") != page_id:
                _error("targets/blueprint_ref", "target must bind its actual blueprint artifact")
            store.read_object_bytes(artifact["file"])
        targets.append({"page_id": page_id, "page_ref": deepcopy(entry["page"]),
                        "blueprint_ref": deepcopy(blueprint), "content": deepcopy(page["customer_visible"])})
        basis.append(make_dependency_slice(store, document, kind="artifact", identity=f"page:{page_id}", projection="visual_input"))
        if plan and plan.get("schema_version") == "content_plan.v2":
            basis.append(make_dependency_slice(store, document, kind="artifact", identity=f"plan:{page_id}", projection="visual_role"))
    if value["intent"] == "feasibility" and not targets:
        for identity in ("narrative", "content_plan"):
            if document.get(identity):
                basis.append(make_dependency_slice(store, document, kind="artifact", identity=identity, projection="content"))
    parent, parent_ref = _parent(store, document, value.get("parent_recipe_id"))
    before = deepcopy(parent.get("parameters", {})) if parent else {}
    parameters = deepcopy(value["recipe_draft"])
    diff = [{**row, "field": "parameters." + row["field"]} for row in _diff(before, parameters)]
    prior_input = parent.get("input", {}) if parent else {}
    diff.extend(_diff({key: prior_input.get(key) for key in ("intent", "target_page_ids", "instruction", "reference_refs", *PLANNING_FIELDS)},
                      {key: value.get(key) for key in ("intent", "target_page_ids", "instruction", "reference_refs", *PLANNING_FIELDS)}))
    return {"schema_version": "style_proposal.v3", "project_id": document["project_id"],
            "base_revision": document["revision_id"], "input": deepcopy(value), "intent": value["intent"],
            "basis": basis, "targets": targets, "reference_refs": references,
            "recipe_draft": parameters, "parent_recipe_ref": deepcopy(parent_ref),
            **{key: deepcopy(value[key]) for key in PLANNING_FIELDS},
            "dimensions": {key: deepcopy(parameters[key]) for key in DIMENSIONS},
            "preserve_dimensions": {}, "conflicts": [], "diff": diff,
            "preserve_target_content": True, "suggestion_state": "none"}


def confirmed_recipe(proposal, proposal_ref, *, recipe_id, parent_ref=None, parent=None):
    """Freeze an already-reviewed proposal; confirmation conveys no execution authority."""
    if proposal.get("schema_version") != "style_proposal.v3":
        _error("proposal", "use the immutable v3 design proposal")
    validate_ref(proposal_ref, where="proposal_ref")
    if sha256_bytes(canonical_json_bytes(proposal)) != proposal_ref["sha256"]:
        _error("proposal_ref", "proposal content differs from its immutable Ref")
    _text(recipe_id, "recipe_id")
    if bool(parent is not None) != bool(parent_ref is not None):
        _error("parent_recipe_ref", "parent recipe and its fixed Ref must be supplied together")
    if proposal.get("parent_recipe_ref") != parent_ref:
        _error("parent_recipe_ref", "parent differs from the proposal's immutable parent")
    if parent is not None:
        validate_ref(parent_ref, where="parent_recipe_ref")
        if sha256_bytes(canonical_json_bytes(parent)) != parent_ref["sha256"]:
            _error("parent_recipe_ref", "parent content differs from its immutable Ref")
        if (parent.get("project_id") != proposal["project_id"]
                or parent.get("recipe_id") != proposal["input"].get("parent_recipe_id")):
            _error("parent_recipe_ref", "parent identity differs from the proposal")
    elif proposal["input"].get("parent_recipe_id"):
        _error("parent_recipe_ref", "the proposal requires its actual parent")
    if proposal.get("conflicts"):
        _error("conflicts", "resolve the proposal's explicit conflicts before confirmation")
    if proposal.get("recipe_draft") != proposal["input"].get("recipe_draft"):
        _error("recipe_draft", "executable parameters differ from the immutable input")
    parameters = deepcopy(proposal["recipe_draft"])
    ids = proposal["input"]["target_page_ids"]
    validate_parameters(parameters, ids)
    recipe = deepcopy(proposal)
    recipe.update({"schema_version": "style_recipe.v3", "recipe_id": recipe_id,
                   "version": parent["version"] + 1 if parent else 1,
                   "proposal_ref": deepcopy(proposal_ref), "parent_recipe_ref": deepcopy(parent_ref),
                   "scope": {"page_ids": deepcopy(ids), "layers": ["design"]}, "parameters": parameters})
    return recipe


def effective_parameters(recipe, page_id):
    """The single executable recipe source, including only expressly permitted page rules."""
    if recipe.get("schema_version") != "style_recipe.v3":
        _error("recipe", "use style_recipe.v3")
    ids = (recipe.get("scope") or {}).get("page_ids", [])
    if ids != (recipe.get("input") or {}).get("target_page_ids"):
        _error("scope/page_ids", "recipe scope conflicts with its immutable input")
    if page_id not in ids:
        _error("page_id", "page is outside this recipe's explicit scope")
    parameters = recipe.get("parameters")
    validate_parameters(parameters, ids, path="parameters")
    if parameters != recipe.get("recipe_draft") or parameters != (recipe.get("input") or {}).get("recipe_draft"):
        _error("parameters", "recipe parameters conflict with their immutable input")
    effective = {key: deepcopy(parameters[key]) for key in DIMENSIONS}
    effective.update(deepcopy(parameters.get("page_rules", {}).get(page_id, {})))
    return effective


def compile_design(page, design, recipe, page_id):
    """Return a resolved design without mutating Page facts, relations or persisted design."""
    validate_schema("page", page)
    if page.get("page_id") != page_id:
        _error("page_id", "actual Page identity differs from the selected target")
    if recipe.get("intent") == "feasibility":
        _error("intent", "a feasibility recipe cannot compile a production page")
    parameters = effective_parameters(recipe, page_id)
    base = {key: recipe["parameters"][key] for key in DIMENSIONS}
    overrides = _diff(base, parameters, source="recipe.page_rules")
    visual = page.get("visual_spec") or {}
    page_overrides = visual.get("design_overrides") or {}
    # Language and asset scope retain existing resolver semantics. Font rules
    # are allowed differences only when the immutable recipe explicitly says so.
    for slot in TYPOGRAPHY_FIELDS[:2]:
        font_id = page_overrides.get(slot)
        if font_id is None or font_id == parameters["typography"][slot]:
            continue
        if "typography" not in recipe["parameters"]["allowed_overrides"]:
            _error(f"visual_spec/design_overrides/{slot}", "font override is not allowed by this recipe")
        rule = recipe["parameters"].get("page_rules", {}).get(page_id, {}).get("typography")
        if rule is not None and rule[slot] != font_id:
            _error(f"visual_spec/design_overrides/{slot}", "Page and recipe page rule conflict in the same dimension")
        before = parameters["typography"][slot]
        parameters["typography"][slot] = font_id
        overrides.append({"field": "typography." + slot, "before": before, "after": font_id,
                          "source": "Page.visual_spec.design_overrides"})
    effective = deepcopy(design)
    style_id = visual.get("style_ref") or design.get("default_style_id")
    style = next((deepcopy(item) for item in design.get("styles", []) if item.get("style_id") == style_id), None)
    if style is None:
        _error("visual_spec/style_ref", "select an actual registered project style")
    style["colors"] = deepcopy(parameters["palette"])
    style["typography"] = deepcopy(parameters["typography"])
    style["layout_notes"] = "\n".join(key + ": " + parameters[key] for key in RULE_DIMENSIONS)
    effective["styles"] = [style]
    effective["default_style_id"] = style_id
    from .production import resolve_design
    effective, _ = resolve_design(page, effective, design.get("assets") or [])
    effective["recipe_parameters"] = parameters
    effective["recipe_overrides"] = overrides
    return effective


def recipe_references(recipe):
    """Return fixed ordered style-reference descriptions, never a fabricated target image."""
    references = _references(recipe)
    if references != (recipe.get("input") or {}).get("reference_refs"):
        _error("reference_refs", "references differ from this recipe's immutable input")
    return references
