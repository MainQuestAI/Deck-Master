"""Versioned editorial structure. Page objects remain the only body-copy truth."""
from __future__ import annotations

import copy
import uuid

from .errors import TypedServiceError
from .models import compute_input_digest, validate_schema
from .snapshots import READ_FAILURES, load_snapshot
from .store import Store

PROTOCOL = "compose.v1"
CAPABILITIES = ["content_plan", "versioned_source_links"]


class ContentPlanError(TypedServiceError):
    error_code = "content_plan_invalid"


def protocol_fields(document, intent):
    if document.get("compatibility", {}).get("project_format") != "workbench.v3" or intent == "import_draft":
        return {}
    return {"protocol_version": PROTOCOL, "required_capabilities": CAPABILITIES.copy()}


def source_version(source):
    return {"original_sha256": source.get("original_sha256"), "extract": source.get("extract")}


def _fail(field, message):
    raise ContentPlanError("content_plan/" + field, message)


def _unique(values, field):
    if len(values) != len(set(values)):
        _fail(field, "identities must be unique")


def bind_result(store, document, task, value, pages):
    """Validate a complete structure and store it before the same adoption swap.

    Resolving a locator proves a reference exists, not that the cited claim is
    true. No missing plan, source, goal or source version is manufactured.
    """
    required = task.get("protocol_version") == PROTOCOL
    if required:
        from .generation import check_host
        check_host(task)
    if value is None:
        if required:
            _fail("input", "compose.v1 requires a content_plan with explicit unresolved facts")
        return None
    if task.get("kind") != "compose" or document.get("compatibility", {}).get("project_format") != "workbench.v3":
        _fail("input", "only compose in an explicit workbench.v3 project can adopt a plan")
    validate_schema("content_plan_input", value)
    goals, chapters = value["goals"], value["chapters"]
    _unique([g["goal_id"] for g in goals], "goals")
    _unique([g["page_id"] for g in goals], "goals/page_id")
    _unique([c["chapter_id"] for c in chapters], "chapters")
    chapter_goals = [gid for chapter in chapters for gid in chapter["goal_ids"]]
    _unique(chapter_goals, "chapters/goal_ids")
    if set(chapter_goals) != {g["goal_id"] for g in goals}:
        _fail("chapters/goal_ids", "every goal must belong to exactly one chapter")
    if {g["page_id"] for g in goals} != {p["page_id"] for p in pages}:
        _fail("goals/page_id", "goals must cover every resulting Page exactly once")
    sources = {s["source_id"]: s for s in document["sources"]}
    locators = {}
    for goal in goals:
        if not goal["source_links"] and not goal["unresolved_facts"]:
            _fail("goals/source_links", "a goal without source evidence must state its missing basis")
        for link in goal["source_links"]:
            source = sources.get(link["source_id"])
            if source is None or link["source_version"] != source_version(source):
                _fail("goals/source_links/source_version", "source identity or version is not in the dispatched inputs")
            if source["source_id"] not in locators:
                extract = store.read_object_json(source["extract"])
                locators[source["source_id"]] = {item["locator"] for field in ("locators", "tables", "image_pages")
                                                  for item in extract.get(field, []) if "locator" in item}
            if link["locator"] not in locators[source["source_id"]]:
                _fail("goals/source_links/locator", "locator does not exist in this stored source version")
    previous_ref = document.get("content_plan")
    previous = store.read_object_json(previous_ref) if previous_ref else None
    if previous:
        validate_schema("content_plan", previous)
        if previous["project_id"] != document["project_id"]:
            _fail("project_id", "previous plan belongs to another project")
        old_goals = {g["page_id"]: g["goal_id"] for g in previous["input"]["goals"]}
        if any(g["page_id"] in old_goals and old_goals[g["page_id"]] != g["goal_id"] for g in goals):
            _fail("goals/goal_id", "preserve the goal identity of retained pages")
    goals_by_page = {g["page_id"]: g for g in goals}
    record = {"schema_version": "content_plan.v1", "plan_id": previous["plan_id"] if previous else "plan-" + uuid.uuid4().hex,
              "version": previous["version"] + 1 if previous else 1, "project_id": document["project_id"],
              "task_id": task["task_id"], "origin": "user_imported" if task.get("intent") == "import_draft" else "host_composed",
              "basis": {"revision_id": task["dispatch_revision"], "input_digest": task["input_digest"],
                        "produced_against": task["produced_against"]}, "previous_ref": previous_ref,
              "input": copy.deepcopy(value),
              "page_links": [{"goal_id": goals_by_page[p["page_id"]]["goal_id"], "page_id": p["page_id"], "page_ref": p["page"]} for p in pages]}
    validate_schema("content_plan", record)
    return store.put_json_object(record)


def attach(document, ref):
    if ref:
        document["content_plan"] = ref
        document["compatibility"] = {"project_format": "workbench.v3", "minimum_writer": "content-plan.v1"}


def projection(store, document, *, reader=None, page_id=None, summary=False):
    """A fixed snapshot projection; absent plans yield a labeled, unwritten TOC."""
    read = reader or store.read_object_json
    ref = document.get("content_plan")
    pages = {p["page_id"]: p for p in document["pages"]}
    if ref is None:
        result = {"status": "derived", "relation": "derived", "ref": None,
                  "basis": "Page titles at this snapshot; no historical content plan", "chapters": []}
        if not summary:
            goals = []
            for entry in pages.values():
                if page_id is not None and entry["page_id"] != page_id:
                    continue
                try:
                    page = read(entry["page"])
                    validate_schema("page", page)
                    if page["page_id"] != entry["page_id"]:
                        raise ValueError("foreign page")
                    title = page["customer_visible"]["title"]
                except READ_FAILURES:
                    title = None
                goals.append({"goal_id": None, "page_id": entry["page_id"], "page_ref": entry["page"],
                              "title": title, "purpose": None, "source_links": [], "basis_status": "unknown"})
            result["goals"] = goals
        return result
    try:
        plan = read(ref)
        validate_schema("content_plan", plan)
        if plan["project_id"] != document["project_id"]:
            raise ValueError("foreign content plan")
        linked = {p["page_id"]: p for p in plan["page_links"]}
        changed = plan["basis"]["input_digest"] != compute_input_digest(document) or list(linked) != list(pages)
        changed |= any(pages.get(pid, {}).get("page") != link["page_ref"] for pid, link in linked.items())
        result = {"status": "recorded", "relation": "known", "ref": ref, "plan_id": plan["plan_id"],
                  "version": plan["version"], "origin": plan["origin"],
                  "applicability": "basis_changed" if changed else "current",
                  "chapter_count": len(plan["input"]["chapters"]), "goal_count": len(plan["input"]["goals"])}
        if summary:
            return result
        goals = [copy.deepcopy(g) for g in plan["input"]["goals"] if page_id is None or g["page_id"] == page_id]
        sources = {s["source_id"]: s for s in document["sources"]}
        for goal in goals:
            link = linked[goal["page_id"]]
            goal["page_ref"] = link["page_ref"]
            goal["basis_status"] = "current" if pages.get(goal["page_id"], {}).get("page") == link["page_ref"] else "basis_changed"
            for source_link in goal["source_links"]:
                source = sources.get(source_link["source_id"])
                source_link["relation"] = "missing" if source is None else "current" if source_version(source) == source_link["source_version"] else "version_changed"
                source_link["verification"] = "stored locator checked at adoption; claim not independently verified"
        goal_ids = {g["goal_id"] for g in goals}
        result.update(input_summary=plan["input"]["input_summary"], goals=goals,
                      chapters=[copy.deepcopy(c) for c in plan["input"]["chapters"] if set(c["goal_ids"]) & goal_ids],
                      unresolved_facts=copy.deepcopy(plan["input"]["unresolved_facts"]),
                      previous_ref=plan["previous_ref"], basis=copy.deepcopy(plan["basis"]))
        return result
    except READ_FAILURES:
        return {"status": "unreadable", "relation": "unknown", "ref": ref,
                "error": {"code": "content_plan_unreadable", "message": "stored content plan is missing, invalid or damaged"}}


def show(project_dir, *, revision=None):
    store = Store(project_dir)
    document = load_snapshot(store, revision)
    return {"project_id": document["project_id"], "revision_id": document["revision_id"],
            "content_plan": projection(store, document)}
