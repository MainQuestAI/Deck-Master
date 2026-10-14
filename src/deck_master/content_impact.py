"""Fact-source change impact analysis (content collaboration v1.2 TASKS T03 item 6).

After a material update, the affected claims and pages come first: the
revision task must carry the concrete list before anyone rewrites copy. This
module derives that list from the stored Narrative source links, the page
content mappings and the plan page roles — no second truth is written, and
unresolved issues / review findings keep their existing channels.
"""
from __future__ import annotations

from .models import canonical_json_bytes, sha256_bytes


def _source_index(document) -> dict[str, dict]:
    index = {}
    for source in document.get("sources") or []:
        extract = source.get("extract") or {}
        index[source.get("source_id")] = {
            "original_sha256": source.get("original_sha256"),
            "extract_sha256": extract.get("sha256"),
            "usage_note": source.get("usage_note") or "",
        }
    return index


def _changed_sources(before, after) -> dict:
    old, new = _source_index(before), _source_index(after)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(source_id for source_id in set(old) & set(new)
                     if old[source_id] != new[source_id])
    return {"added": added, "removed": removed, "changed": changed,
            "before": {key: old[key] for key in sorted(old)},
            "after": {key: new[key] for key in sorted(new)}}


def _affected_narrative_nodes(store, document, source_ids) -> tuple[list[str], list[dict]]:
    nodes: list[str] = []
    links: list[dict] = []
    if not document.get("narrative"):
        return nodes, links
    try:
        narrative = store.read_object_json(document["narrative"])
    except Exception:  # noqa: BLE001 - an unreadable narrative cannot be mapped
        return nodes, links
    for node in narrative.get("nodes") or []:
        for link in node.get("source_links") or []:
            if link.get("source_id") in source_ids:
                nodes.append(node["node_id"])
                links.append({"node_id": node["node_id"], "source_id": link.get("source_id"),
                              "locator": link.get("locator")})
                break
    return sorted(set(nodes)), links


def _page_source_links(page) -> list[dict]:
    mapping = page.get("content_mapping") or {}
    found = []
    for link in mapping.get("visible_links") or []:
        for source_link in link.get("source_links") or []:
            found.append({"atom": link.get("element_ref"),
                          "source_id": source_link.get("source_id"),
                          "locator": source_link.get("locator")})
    return found


def _affected_pages(store, document, plan, source_ids) -> tuple[list[str], list[dict]]:
    affected: list[str] = []
    detail: list[dict] = []
    for entry in document.get("pages") or []:
        page = store.read_object_json(entry["page"])
        linked = [link for link in _page_source_links(page)
                  if link["source_id"] in source_ids]
        if linked:
            affected.append(entry["page_id"])
            detail.append({"page_id": entry["page_id"], "atoms": linked})
            continue
        if plan:
            role = next((item for item in (plan.get("input") or {}).get("page_roles") or []
                         if item.get("page_id") == entry["page_id"]), None)
            plan_links = [link for link in (role or {}).get("source_links") or []
                          if link.get("source_id") in source_ids]
            if plan_links:
                affected.append(entry["page_id"])
                detail.append({"page_id": entry["page_id"], "atoms": [],
                               "plan_role_links": plan_links})
    return sorted(set(affected)), detail


def _unresolved_items(store, document, node_ids) -> list[dict]:
    items = []
    if not document.get("narrative"):
        return items
    try:
        narrative = store.read_object_json(document["narrative"])
    except Exception:  # noqa: BLE001
        return items
    for issue in narrative.get("issues") or []:
        if issue.get("resolution") != "open":
            continue
        if set(issue.get("affected_node_ids") or []) & set(node_ids):
            items.append({"issue_id": issue.get("issue_id"), "question": issue.get("question"),
                          "impact": issue.get("impact")})
    return items


def _open_findings(store, document, page_ids, source_ids) -> list[dict]:
    from .review import open_findings, pending_judgments
    found = []
    for ref in document.get("reviews") or []:
        try:
            review = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        deps = {f"{dep['kind']}:{dep['identity']}" for dep in review.get("dependencies") or []}
        touches = any(f"source:{source_id}" in deps for source_id in source_ids)
        for finding in open_findings(review) + pending_judgments(review):
            if touches or finding.get("page_id") in page_ids:
                found.append({"review_id": review.get("review_id"), "kind": review.get("kind"),
                              "finding_id": finding.get("finding_id"),
                              "page_id": finding.get("page_id"),
                              "impact": finding.get("impact"),
                              "message": finding.get("message")})
    return found


def analyze_input_change(store, before, after) -> dict:
    """Affected claims and pages after a task-fact or material change.

    ``before``/``after`` are committed Document snapshots. The result is a
    projection: it names objects and reasons, and it never writes or repairs
    anything by itself.
    """
    changes = _changed_sources(before, after)
    touched = set(changes["changed"]) | set(changes["removed"])
    plan = None
    if after.get("content_plan"):
        try:
            plan = store.read_object_json(after["content_plan"])
        except Exception:  # noqa: BLE001
            plan = None
    node_ids, node_links = _affected_narrative_nodes(store, after, touched)
    page_ids, page_detail = _affected_pages(store, after, plan, touched)
    task_fields = sorted(
        key for key in set(before.get("task") or {}) | set(after.get("task") or {})
        if (before.get("task") or {}).get(key) != (after.get("task") or {}).get(key))
    impact = {
        "schema_version": "content_impact.v1",
        "changed_task_fields": task_fields,
        "changed_sources": {"added": changes["added"], "removed": changes["removed"],
                            "changed": changes["changed"]},
        "affected_claims": node_ids,
        "claim_links": node_links,
        "affected_pages": page_ids,
        "page_links": page_detail,
        "unaffected_pages": sorted({entry["page_id"] for entry in after.get("pages") or []}
                                   - set(page_ids)),
        "unresolved_items": _unresolved_items(store, after, node_ids),
        "open_findings": _open_findings(store, after, set(page_ids), touched),
        "estimated": False,
        "note": ("impact only; rewrite the affected copy through the input_revision task and "
                 "report what changed, what stayed valid and which unresolved items remain"),
    }
    impact["has_impact"] = bool(impact["changed_task_fields"] or changes["added"]
                                or changes["removed"] or changes["changed"])
    impact["impact_digest"] = sha256_bytes(canonical_json_bytes({
        "task": impact["changed_task_fields"],
        "sources": impact["changed_sources"],
        "claims": impact["affected_claims"],
        "pages": impact["affected_pages"],
    }))
    return impact


def impact_summary_text(impact: dict) -> str:
    """One line a task instruction can carry without inventing anything."""
    if not impact.get("has_impact"):
        return "本次没有材料或任务事实变化"
    parts = []
    if impact["changed_sources"]["added"]:
        parts.append(f"新增来源 {len(impact['changed_sources']['added'])}")
    if impact["changed_sources"]["removed"]:
        parts.append(f"移除来源 {len(impact['changed_sources']['removed'])}")
    if impact["changed_sources"]["changed"]:
        parts.append(f"来源版本变化 {len(impact['changed_sources']['changed'])}")
    if impact["changed_task_fields"]:
        parts.append("任务事实变化：" + ", ".join(impact["changed_task_fields"]))
    if impact["affected_claims"]:
        parts.append("受影响 claim：" + ", ".join(impact["affected_claims"]))
    if impact["affected_pages"]:
        parts.append("受影响页面：" + ", ".join(impact["affected_pages"]))
    else:
        parts.append("没有页面直接引用变化的来源")
    return "；".join(parts)
