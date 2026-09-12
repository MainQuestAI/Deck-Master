"""SC-1 B4: solution model (deck_solution_model.v1).

A reviewable solution design — problems, capabilities, components,
relations, phases, alternatives, assumptions (spec 05 §5.1). It is a
domain object between the claim graph and the narrative: it never
copies source material, manages approvals, or replaces page content.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "deck_solution_model.v1"
COMPONENT_STATUSES = {"existing", "proposed", "replacing"}
RELATION_KINDS = {"supports", "triggers", "feeds", "contains"}
FACT_KINDS = {"customer_fact", "externally_verified", "analysis_judgment", "design_suggestion", "working_assumption", "derived_calculation"}

_MODEL_SECTIONS = ("problems", "capabilities", "components", "relations", "phases", "alternatives", "assumptions")


def empty_solution_model(run_id: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "problems": [],
        "capabilities": [],
        "components": [],
        "relations": [],
        "phases": [],
        "alternatives": [],
        "assumptions": [],
    }


def validate_solution_model(model: dict[str, Any]) -> list[str]:
    """Structural + content rules from spec 05 §5.1. Fail-closed."""

    if 'model_id' in model or 'based_on' in model:
        return validate_formal_solution_model(model)
    errors: list[str] = []
    if str(model.get("schema_version") or "") != SCHEMA_VERSION:
        errors.append(f"schema_version must be '{SCHEMA_VERSION}'")
        return errors

    problem_ids = {str(item.get("problem_id") or "") for item in model.get("problems", []) if isinstance(item, dict)}
    component_ids = {str(item.get("component_id") or "") for item in model.get("components", []) if isinstance(item, dict)}
    capability_ids = {str(item.get("capability_id") or "") for item in model.get("capabilities", []) if isinstance(item, dict)}

    if not model.get("problems"):
        errors.append("solution model requires at least one problem")
    if not model.get("capabilities"):
        errors.append("solution model requires at least one capability")

    for index, capability in enumerate(model.get("capabilities", [])):
        if not isinstance(capability, dict):
            continue
        cid = str(capability.get("capability_id") or f"capability[{index}]")
        mechanism = str(capability.get("mechanism") or "").strip()
        if not mechanism:
            errors.append(f"capability {cid} lacks a concrete mechanism")
        related = [str(item) for item in (capability.get("problem_ids") or [])]
        if not any(item in problem_ids for item in related):
            errors.append(f"capability {cid} is not tied to any known problem")
        if not capability.get("checkable_result"):
            errors.append(f"capability {cid} lacks a checkable result")
        generic_tokens = ("智能化", "赋能", "提效")
        if mechanism and all(token in mechanism for token in generic_tokens[:1]) and len(mechanism) < 12:
            errors.append(f"capability {cid} mechanism is a generic slogan, not a mechanism")

    for component in model.get("components", []):
        if not isinstance(component, dict):
            continue
        comp_id = str(component.get("component_id") or "")
        status = str(component.get("status") or "").strip().lower()
        if status not in COMPONENT_STATUSES:
            errors.append(f"component {comp_id} status must be one of {sorted(COMPONENT_STATUSES)}")

    for relation in model.get("relations", []):
        if not isinstance(relation, dict):
            continue
        kind = str(relation.get("kind") or "").strip().lower()
        if kind not in RELATION_KINDS:
            errors.append(f"relation kind must be one of {sorted(RELATION_KINDS)}")
        target = str(relation.get("target") or "")
        source = str(relation.get("source") or "")
        if source and source not in component_ids and source not in capability_ids:
            errors.append(f"relation source '{source}' is not a known component/capability")
        if target and target not in component_ids and target not in capability_ids and target not in problem_ids:
            errors.append(f"relation target '{target}' is not a known component/capability/problem")

    for assumption in model.get("assumptions", []):
        if not isinstance(assumption, dict):
            continue
        aid = str(assumption.get("assumption_id") or "")
        if not str(assumption.get("recheck_trigger") or "").strip():
            errors.append(f"assumption {aid} lacks a recheck trigger")
        if not [str(item) for item in (assumption.get("affects") or [])]:
            errors.append(f"assumption {aid} lacks affected objects")

    alternatives = [item for item in model.get("alternatives", []) if isinstance(item, dict)]
    if alternatives:
        recommended = [item for item in alternatives if item.get("recommended")]
        if len(recommended) != 1:
            errors.append("exactly one alternative must be marked recommended when alternatives are provided")
        for alt in alternatives:
            if not str(alt.get("why_rejected") or "").strip() and not alt.get("recommended"):
                errors.append(f"alternative {alt.get('alternative_id','')} lacks a why_rejected rationale")
    return errors


def validate_formal_solution_model(model: dict[str, Any]) -> list[str]:
    """Validate the public contract and references without certifying evidence truth."""
    import json
    from jsonschema import Draft202012Validator
    from native_pptx.contracts import SCHEMA_DIR
    schema = json.loads((SCHEMA_DIR / 'solution-model.v1.schema.json').read_text())
    errors = [f"{'.'.join(map(str, e.path))}: {e.message}" for e in Draft202012Validator(schema).iter_errors(model)]
    if errors:
        return errors
    sections = ('problems', 'capabilities', 'components', 'relations', 'implementation_phases', 'alternatives', 'assumptions')
    index = {s: {i['id']: i for i in model[s]} for s in sections}
    all_ids = set()
    for section in sections:
        for item in model[section]:
            if item['id'] in all_ids:
                errors.append(f"duplicate model object {item['id']}")
            all_ids.add(item['id'])
    object_ids = set(index['problems']) | set(index['capabilities']) | set(index['components'])
    for item in model['capabilities']:
        for ref in item['problem_refs']:
            if ref not in index['problems']:
                errors.append(f"capability {item['id']} references missing problem {ref}")
    for item in model['relations']:
        for key in ('from_id', 'to_id'):
            if item[key] not in object_ids:
                errors.append(f"relation {item['id']} references missing object {item[key]}")
        if item['status'] == 'existing' and not item['evidence_refs']:
            errors.append(f"existing relation {item['id']} requires evidence")
    for item in model['implementation_phases']:
        for ref in item['component_refs']:
            if ref not in index['components']:
                errors.append(f"phase {item['id']} references missing component {ref}")
        for ref in item['depends_on']:
            if ref not in index['implementation_phases'] or ref == item['id']:
                errors.append(f"phase {item['id']} has invalid dependency {ref}")
    if model['recommended_alternative_id'] not in index['alternatives']:
        errors.append('recommended alternative does not exist')
    if len(model['alternatives']) == 1 and not model['single_viable_reason'].strip():
        errors.append('single alternative requires a single_viable_reason')
    for item in model['assumptions']:
        for ref in item['affected_refs']:
            if ref not in all_ids:
                errors.append(f"assumption {item['id']} references missing object {ref}")
    return errors


def build_solution_model(run_dir, design: dict[str, Any], *, source_refs: list[str]) -> dict[str, Any]:
    """Bind Agent-authored design to actual public source bytes; never invent a design."""
    import copy
    import hashlib
    import json
    from pathlib import Path
    root = Path(run_dir).resolve()
    request = json.loads((root / 'request.json').read_text())
    refs = []
    for ref in source_refs:
        relative = Path(ref)
        path = root / relative
        if relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError(f'invalid or missing source: {ref}')
        refs.append({'ref': relative.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if not refs:
        raise ValueError('at least one actual source is required')
    payload = copy.deepcopy(design)
    payload.update(schema_version=SCHEMA_VERSION, run_id=root.name, run_mode=request.get('origin_run_mode', request.get('run_mode', 'production')),
                   based_on={'input_fingerprint': hashlib.sha256(json.dumps(refs, sort_keys=True).encode()).hexdigest(), 'input_refs': refs})
    errors = validate_formal_solution_model(payload)
    if errors:
        raise ValueError('solution model invalid: ' + '; '.join(errors))
    return payload
