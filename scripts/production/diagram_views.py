"""SC-1 B6: diagram views — typed, scoped derivations of the solution model.

``deck_diagram_view.v1`` objects never introduce business objects that the
solution model does not contain (spec 06 §6.2): every node carries a
``model_ref`` into the model's components/capabilities/problems, every edge a
``relation_ref`` into the model relations (or an explicit aggregation /
containment justification). View content validation is separate from
geometry: this module validates semantics; layout stays with the producer.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "deck_diagram_view.v1"
VIEW_TYPES = {"business_architecture", "application_architecture", "data_flow", "implementation_roadmap"}


def _model_sha256(solution_model: dict[str, Any]) -> str:
    blob = json.dumps(solution_model, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _model_index(solution_model: dict[str, Any]) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {"component": set(), "capability": set(), "problem": set(), "relation": set()}
    for section, key in (("components", "component"), ("capabilities", "capability"), ("problems", "problem")):
        for item in solution_model.get(section, []) or []:
            if isinstance(item, dict) and str(item.get(f"{key}_id") or "").strip():
                ids[key].add(str(item[f"{key}_id"]))
    for index, relation in enumerate(solution_model.get("relations", []) or []):
        if isinstance(relation, dict):
            ids["relation"].add(str(relation.get("relation_id") or f"relation_{index:02d}"))
    return ids


def build_diagram_view(
    *,
    view_id: str,
    view_type: str,
    solution_model: dict[str, Any],
    target_page_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    visible_to: str = "internal",
    layout: str = "layered",
    label_source: str = "solution_model",
) -> dict[str, Any]:
    if solution_model.get('model_id'):
        from planning.solution_model import validate_formal_solution_model
        from native_pptx.contracts import SCHEMA_DIR
        from jsonschema import Draft202012Validator
        errors = validate_formal_solution_model(solution_model)
        if errors:
            raise ValueError('formal solution model invalid: ' + '; '.join(errors))
        model_hash = _model_sha256(solution_model)
        result = dict(schema_version=SCHEMA_VERSION, run_id=solution_model['run_id'], run_mode=solution_model['run_mode'],
                      based_on={'input_fingerprint': model_hash, 'input_refs': [{'ref': 'solution_model.json', 'sha256': model_hash}]},
                      view_id=view_id, page_id=target_page_id, view_type=view_type,
                      model_ref='solution_model.json', model_sha256=model_hash,
                      title=view_id, scope_note='Derived view of the referenced solution model; no new customer facts.',
                      nodes=[dict(n) for n in nodes], edges=[dict(e) for e in edges],
                      layout={'strategy': layout, 'aspect_ratio': '16:9', 'editability_target': 'native_shapes'})
        schema = json.loads((SCHEMA_DIR / 'diagram-view.v1.schema.json').read_text())
        Draft202012Validator(schema).validate(result)
        errors = validate_diagram_view(result, solution_model=solution_model)
        if errors:
            raise ValueError('diagram view violates model consistency: ' + '; '.join(errors))
        return result
    if view_type not in VIEW_TYPES:
        raise ValueError(f"view_type must be one of {sorted(VIEW_TYPES)}")
    problems = validate_diagram_view(
        {
            "view_type": view_type,
            "nodes": nodes,
            "edges": edges,
        },
        solution_model=solution_model,
    )
    if problems:
        raise ValueError("diagram view violates model consistency: " + "; ".join(problems))
    return {
        "schema_version": SCHEMA_VERSION,
        "view_id": view_id,
        "view_type": view_type,
        "solution_model_sha256": _model_sha256(solution_model),
        "target_page_id": str(target_page_id),
        "visible_to": str(visible_to),
        "label_source": str(label_source),
        "layout": str(layout),
        "nodes": [dict(node) for node in nodes],
        "edges": [dict(edge) for edge in edges],
    }


def _objects(model):
    return {str(item.get('id') or item.get(key)): item
            for section, key in [('components','component_id'), ('capabilities','capability_id'), ('problems','problem_id')]
            for item in model.get(section, [])}


def _refs(node):
    return set(node.get('model_refs') or ([node['model_ref']] if node.get('model_ref') else [])) | set(node.get('aggregates') or [])


def validate_diagram_view(view: dict[str, Any], *, solution_model: dict[str, Any]) -> list[str]:
    """Validate topology and direction, not just existence of relation identifiers."""
    if 'model_sha256' in view:
        from jsonschema import Draft202012Validator
        from native_pptx.contracts import SCHEMA_DIR
        schema = json.loads((SCHEMA_DIR / 'diagram-view.v1.schema.json').read_text())
        structural = [e.message for e in Draft202012Validator(schema).iter_errors(view)]
        if structural:
            return structural
    objects = _objects(solution_model)
    problems = []
    nodes = {}
    for node in view.get('nodes', []):
        nid = str(node.get('id') or node.get('node_id') or '')
        if not nid or nid in nodes:
            problems.append(f'duplicate or empty node id {nid}')
        nodes[nid] = node
        refs = _refs(node)
        if not refs:
            problems.append(f'node {nid} has neither a model_ref nor an aggregation; drawing cannot create new components')
        for ref in refs:
            if ref not in objects:
                problems.append(f"node {nid} references model object '{ref}' which does not exist in the solution model")
        if len(refs) > 1 and not str(node.get('aggregation_reason') or '').strip():
            problems.append(f'node {nid} aggregation requires an explicit reason')
        status = node.get('status')
        if status and status not in {'existing','proposed','replacing','aggregate'}:
            problems.append(f'node {nid} has invalid status {status}')
        if status and status != 'aggregate' and any(objects[r].get('status') and objects[r]['status'] != status for r in refs if r in objects):
            problems.append(f'node {nid} status disagrees with model')
    relations = {str(r.get('id') or r.get('relation_id') or f'relation_{i:02d}'): r for i,r in enumerate(solution_model.get('relations', []))}
    edge_ids = set()
    for edge in view.get('edges', []):
        eid = str(edge.get('id') or edge.get('edge_id') or '')
        if not eid or eid in edge_ids:
            problems.append(f'duplicate or empty edge id {eid}')
        edge_ids.add(eid)
        source = str(edge.get('from_node_id') or edge.get('source_node') or '')
        target = str(edge.get('to_node_id') or edge.get('target_node') or '')
        if source not in nodes or target not in nodes:
            problems.append(f'edge {eid} endpoint is not in the view')
            continue
        relation = relations.get(str(edge.get('relation_ref') or ''))
        if not relation:
            problems.append(f'edge {eid} references no model relation; arrows cannot invent model relationships')
            continue
        origin = relation.get('from_id') or relation.get('source')
        destination = relation.get('to_id') or relation.get('target')
        if origin not in _refs(nodes[source]) or destination not in _refs(nodes[target]):
            problems.append(f'edge {eid} direction/endpoints disagree with relation {edge.get("relation_ref")}')
    if 'model_sha256' in view and view['model_sha256'] != _model_sha256(solution_model):
        problems.append('view model_sha256 is stale')
    return problems


def impact_of_component_change(solution_model_before: dict[str, Any], solution_model_after: dict[str, Any], views: list[dict[str, Any]], *, narrative_plan=None) -> dict[str, Any]:
    """Report affected references, including in-place updates and relation payload changes.

    This is an impact report, never an approval or an automatic rewrite of page text.
    """
    def components(model):
        return {str(i.get('id') or i.get('component_id')): i for i in model.get('components', [])}
    before, after = components(solution_model_before), components(solution_model_after)
    removed, added = set(before)-set(after), set(after)-set(before)
    changed = {key for key in set(before)&set(after) if before[key] != after[key]}
    touched = removed | added | changed
    ob, oa = _objects(solution_model_before), _objects(solution_model_after)
    changed_objects = {key for key in set(ob)|set(oa) if ob.get(key) != oa.get(key)}
    def relations(model):
        return {str(i.get('id') or i.get('relation_id')): i for i in model.get('relations', [])}
    rb, ra = relations(solution_model_before), relations(solution_model_after)
    changed_relations = {key for key in set(rb)|set(ra) if rb.get(key) != ra.get(key)}
    for key in changed_relations:
        for relation in [rb.get(key, {}), ra.get(key, {})]:
            changed_objects.update(str(relation[k]) for k in ('from_id','to_id','source','target') if relation.get(k))
    affected = {}
    pages = set()
    for view in views:
        refs = set().union(*[_refs(n) for n in view.get('nodes', [])])
        matches = refs & changed_objects
        if matches or any(e.get('relation_ref') in changed_relations for e in view.get('edges', [])):
            affected[view['view_id']] = sorted(matches)
            page = view.get('page_id') or view.get('target_page_id')
            if page: pages.add(str(page))
    for beat in (narrative_plan or {}).get('beats', []):
        refs = set(beat.get('required_components', [])) | set(beat.get('model_refs', []))
        if refs & changed_objects:
            page = beat.get('page_id') or beat.get('beat_id')
            if page: pages.add(str(page))
    phases = {str(p.get('id') or p.get('phase_id')) for m in [solution_model_before,solution_model_after]
              for p in m.get('implementation_phases', m.get('phases', []))
              if set(p.get('component_refs', p.get('component_ids', []))) & changed_objects}
    # Dependent phases also need revalidation even when their own components are unchanged.
    phase_list = solution_model_after.get('implementation_phases', solution_model_after.get('phases', []))
    while True:
        dependent = {str(p.get('id') or p.get('phase_id')) for p in phase_list if set(p.get('depends_on', [])) & phases}
        if dependent <= phases: break
        phases |= dependent
    return {'removed_components': sorted(removed), 'added_components': sorted(added),
            'changed_components': sorted(changed), 'changed_relations': sorted(changed_relations),
            'affected_views': affected, 'affected_page_ids': sorted(pages), 'affected_phase_ids': sorted(phases)}
