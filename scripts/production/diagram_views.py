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


def validate_diagram_view(view: dict[str, Any], *, solution_model: dict[str, Any]) -> list[str]:
    """Semantic consistency: no nodes/edges outside the model; aggregations
    must list their members; existing/proposed attributes come from the model."""

    ids = _model_index(solution_model)
    problems: list[str] = []
    node_ids: set[str] = set()
    for node in view.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        node_ids.add(node_id)
        ref = str(node.get("model_ref") or "")
        members = node.get("aggregates") or []
        if ref and ref not in ids["component"] and ref not in ids["capability"] and ref not in ids["problem"]:
            problems.append(f"node {node_id} references model object '{ref}' which does not exist in the solution model")
        if members:
            missing = [str(m) for m in members if str(m) not in ids["component"] and str(m) not in ids["capability"]]
            if missing:
                problems.append(f"node {node_id} aggregates unknown model objects: {missing}")
        if not ref and not members:
            problems.append(f"node {node_id} has neither a model_ref nor an aggregation; drawing cannot create new components")
        status = str(node.get("status") or "").strip().lower()
        if status and status not in {"existing", "proposed", "replacing", "aggregate"}:
            problems.append(f"node {node_id} has invalid status '{status}'")
    for edge in view.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        edge_id = str(edge.get("edge_id") or "")
        source = str(edge.get("source_node") or "")
        target = str(edge.get("target_node") or "")
        if source not in node_ids:
            problems.append(f"edge {edge_id} source node '{source}' is not in the view")
        if target not in node_ids:
            problems.append(f"edge {edge_id} target node '{target}' is not in the view")
        if str(edge.get("relation_ref") or "") not in ids["relation"] and not edge.get("derived_flow"):
            problems.append(
                f"edge {edge_id} references no model relation and is not marked derived_flow; "
                "arrows cannot invent model relationships"
            )
    return problems


def impact_of_component_change(solution_model_before: dict[str, Any], solution_model_after: dict[str, Any], views: list[dict[str, Any]]) -> dict[str, Any]:
    """SC-1 §6.5: component changes invalidate dependent views and pages."""

    def _component_set(model: dict[str, Any]) -> set[str]:
        return {
            str(item.get("component_id") or "")
            for item in model.get("components", []) or []
            if isinstance(item, dict)
        }

    def _node_refs(view: dict[str, Any]) -> set[str]:
        refs: set[str] = set()
        for node in view.get("nodes", []) or []:
            if not isinstance(node, dict):
                continue
            if node.get("model_ref"):
                refs.add(str(node["model_ref"]))
            refs.update(str(m) for m in (node.get("aggregates") or []))
        return refs

    removed = _component_set(solution_model_before) - _component_set(solution_model_after)
    added = _component_set(solution_model_after) - _component_set(solution_model_before)
    affected_views: dict[str, list[str]] = {}
    for view in views:
        refs = _node_refs(view)
        touched = sorted((refs & removed) | (refs & added))
        if touched:
            affected_views[str(view.get("view_id") or "")] = touched
    return {
        "removed_components": sorted(removed),
        "added_components": sorted(added),
        "affected_views": affected_views,
        "affected_page_ids": sorted({str(view.get("target_page_id") or "") for view in views if str(view.get("view_id") or "") in affected_views} - {""}),
    }
