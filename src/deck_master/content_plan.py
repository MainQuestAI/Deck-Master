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


def protocol_fields(document, intent, *, store=None):
    if store is not None and not store.workbench_protocol_required(document):
        return {}
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
    if value is not None and value.get("schema_version") == "content_plan_input.v2":
        previous = store.read_object_json(document["content_plan"]) if document.get("content_plan") else {}
        mode = "imported_mapping" if previous.get("mode") == "imported_mapping" and not document.get("narrative") else "bound"
        return build_v2_plan(store, document, task, value, pages, narrative_ref=document.get("narrative"),
            mode=mode, imported_manuscript=previous.get("imported_manuscript") if mode == "imported_mapping" else None,
            require_role_mapping=mode != "imported_mapping")
    required = task.get("protocol_version") == PROTOCOL
    if required:
        from .generation import check_host
        check_host(task)
    if value is None:
        if required:
            _fail("input", "compose.v1 requires a content_plan with explicit unresolved facts")
        return None
    if task.get("kind") != "compose" or not store.workbench_protocol_required(document):
        _fail("input", "only compose in an explicit workbench.v3 project can adopt a plan")
    previous_ref, previous = validate_input(store, document, value, pages)
    goals = value["goals"]
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


def validate_input(store, document, value, pages):
    """Validate editorial structure independently from how the edit was made."""
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
    return previous_ref, previous


def attach(document, ref):
    if ref:
        document["content_plan"] = ref
        from .models import require_writer
        require_writer(document, "content-plan.v1")


# ---------------------------------------------------------------------------
# content_plan.v2 (content collaboration v1.2 CONTRACTS §11.2): the phased
# production path plans against a Narrative, then binds the real Page hashes.
# Validation is shared with the record schema so a plan can never carry a
# page_order the committed Document does not have.


def source_locators(store, document, source_id: str) -> set[str]:
    """Every locator the stored extract of one source version offers."""
    for source in document.get("sources") or []:
        if source.get("source_id") != source_id:
            continue
        extract_ref = source.get("extract")
        if not extract_ref:
            return set()
        extract = store.read_object_json(extract_ref)
        return {item["locator"] for field in ("locators", "tables", "image_pages")
                for item in extract.get(field, []) if "locator" in item}
    return set()


def validate_source_links(store, document, links, where: str, _cache: dict | None = None) -> None:
    """Every structured SourceLink must name a dispatched source version and a
    locator that exists in it. Locators prove locatability, not support (the
    semantic judgement stays with content review, CONTRACTS §11.1)."""
    known = {source["source_id"]: source for source in document.get("sources") or []}
    cache = {} if _cache is None else _cache
    for index, link in enumerate(links or []):
        source = known.get(link.get("source_id"))
        if source is None or link.get("source_version") != source_version(source):
            _fail(f"{where}[{index}]/source_version",
                  "source identity or version is not in the dispatched inputs")
        locators = cache.setdefault(link["source_id"], source_locators(store, document, link["source_id"]))
        if link.get("locator") not in locators:
            _fail(f"{where}[{index}]/locator", "locator does not exist in this stored source version")


def validate_plan_input_v2(store, document, value: dict, *, mode="planned", imported_manuscript=None) -> None:
    """Structural input validation before any Page/Plan object is written."""
    from .models import validate_content_plan_semantics
    shell = {
        "schema_version": "content_plan.v2", "plan_id": "probe", "version": 1,
        "project_id": document["project_id"], "task_id": None, "origin": "host_composed",
        "basis": {"revision_id": document["revision_id"],
                  "input_digest": compute_input_digest(document)}, "previous_ref": None,
        "mode": mode, "narrative_ref": None, "imported_manuscript": imported_manuscript,
        "input": value, "page_links": [],
    }
    validate_content_plan_semantics(shell, require_page_links=False)
    cache: dict = {}
    for role in value.get("page_roles") or []:
        validate_source_links(store, document, role.get("source_links"),
                              f"content_plan/input/page_roles/{role.get('page_id')}/source_links", cache)


def build_v2_plan(store, document, task, plan_input: dict, page_refs: list[dict], *,
                  narrative_ref, mode: str = "bound", imported_manuscript=None,
                  require_role_mapping: bool = True) -> dict:
    """Store one content_plan.v2 for the same adoption swap.

    ``page_refs`` is the resulting [{page_id, page}] after the swap, so a bound
    plan links every real Page hash exactly once — ghost pages and partial links
    are impossible by construction.
    """
    validate_plan_input_v2(store, document, plan_input,
                           mode="imported_mapping" if mode == "imported_mapping" else "planned",
                           imported_manuscript=imported_manuscript)
    previous_ref = document.get("content_plan")
    previous = None
    if previous_ref:
        try:
            previous = store.read_object_json(previous_ref)
        except Exception:  # noqa: BLE001 - an unreadable old plan is replaced, not trusted
            previous = None
    plan_id = previous["plan_id"] if previous and previous.get("plan_id") else "plan-" + uuid.uuid4().hex
    version = (previous.get("version") or 0) + 1 if previous else 1
    if mode == "planned":
        page_links: list[dict] = []
    else:
        by_page = {entry["page_id"]: entry["page"] for entry in page_refs}
        roles_by_page = {role["page_id"]: role for role in plan_input.get("page_roles") or []}
        missing = sorted(set(plan_input.get("page_order") or []) - set(by_page))
        if missing:
            _fail("input/page_order", f"bound pages have no committed Page object: {missing}")
        page_links = [
            {"page_id": page_id,
             "page_ref": by_page[page_id],
             "plan_role_page_id": page_id if require_role_mapping else page_id}
            for page_id in plan_input.get("page_order") or []
        ]
        unknown = sorted(set(by_page) - set(roles_by_page))
        if unknown and mode != "imported_mapping":
            _fail("input/page_roles", f"every bound page needs exactly one role; missing: {unknown}")
    record = {
        "schema_version": "content_plan.v2",
        "plan_id": plan_id,
        "version": version,
        "project_id": document["project_id"],
        "task_id": task.get("task_id"),
        "origin": "user_imported" if task.get("intent") == "import_draft" else "host_composed",
        "basis": {"revision_id": task.get("dispatch_revision"),
                  "input_digest": task.get("input_digest")
                  or compute_input_digest(document)},
        "previous_ref": previous_ref,
        "mode": mode,
        "narrative_ref": narrative_ref,
        "imported_manuscript": imported_manuscript,
        "input": copy.deepcopy(plan_input),
        "page_links": page_links,
    }
    from .models import validate_content_plan_semantics
    validate_content_plan_semantics(record)
    return store.put_json_object(record)


def refresh_v2_plan_links(store, document, task, plan: dict, page_refs: list[dict], *,
                          previous_ref=None) -> dict:
    """A new Plan version whose only difference is the current page_links.

    CONTRACTS §11.5: a speech update writes notes/mapping for fixed Page Refs and
    rebinds page_links, so the plan's mapping stays current without touching
    page_order, roles or budgets.
    """
    if (plan.get("schema_version") != "content_plan.v2" or
            plan.get("mode") not in ("bound", "imported_mapping")):
        _fail("page_links", "only bound or imported_mapping content_plan.v2 carries page_links to rebind")
    from .models import validate_content_plan_semantics
    validate_content_plan_semantics(plan)
    if plan.get("project_id") != document.get("project_id"):
        _fail("project_id", "plan belongs to another project")
    before_entries = document.get("pages") or []
    before = {entry["page_id"]: entry["page"] for entry in before_entries}
    after_ids = [entry["page_id"] for entry in page_refs]
    _unique(after_ids, "page_links")
    by_page = {entry["page_id"]: entry["page"] for entry in page_refs}
    order = plan["input"]["page_order"]
    if (len(before) != len(before_entries) or list(before) != order or after_ids != order):
        _fail("page_links", "notes refresh preserves the complete current page membership and order")
    links = plan.get("page_links") or []
    if any(link["page_ref"] != before.get(link["page_id"]) for link in links):
        _fail("page_links", "the existing mapping is stale; refresh cannot repair an unrelated old link")
    for page_id, ref in by_page.items():
        page = store.read_object_json(ref)
        validate_schema("page", page)
        if page.get("page_id") != page_id:
            _fail("page_links", "page Ref belongs to another stable page identity")
    refreshed = {
        **copy.deepcopy(plan),
        "version": plan["version"] + 1,
        "previous_ref": previous_ref,
        "task_id": task.get("task_id"),
        "page_links": [{"page_id": link["page_id"],
                        "page_ref": by_page[link["page_id"]],
                        "plan_role_page_id": link["plan_role_page_id"]}
                       for link in plan["page_links"]],
    }
    validate_content_plan_semantics(refreshed)
    return store.put_json_object(refreshed)


def projection(store, document, *, reader=None, page_id=None, summary=False, schema_validated=False):
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
        # Snapshot read contexts already validate this immutable object against
        # its schema after checking the bytes/signature. Other readers retain
        # the full validation here.
        if not schema_validated:
            validate_schema("content_plan", plan)
        if plan["schema_version"] != "content_plan.v1":
            raise ValueError("not a content plan")
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


# ---------------------------------------------------------------------------
# Time budget (content collaboration v1.2 ACCEPTANCE AC-M03, SPEC §9)

TIMING_ITEMS = ("speaking", "pause", "exercise", "qa")


def timing_budget(store, document, *, items: dict | None = None) -> dict:
    """Per-page estimated time that must add up before any length claim.

    Items are separated (speaking / pause / exercise / qa) and every number is
    labelled an estimate: a measured speaking time only exists in Review
    evidence from an actual rehearsal (AC-M03 forbids writing an estimate as a
    measurement). ``items`` may carry explicit per-page numbers; otherwise the
    speaking item comes from the page's speech segment estimates (falling back
    to the plan role's whole-page estimate) and the interaction item stays at
    the plan level.
    """
    ref = document.get("content_plan")
    plan = store.read_object_json(ref) if ref else None
    if not plan or plan.get("schema_version") != "content_plan.v2":
        return {"status": "no_plan", "per_page": [], "totals": {}, "estimated": True,
                "note": "a time budget needs a content_plan.v2 with page roles and time_budget"}
    data = plan["input"]
    entries = {entry["page_id"]: entry for entry in document.get("pages") or []}
    overrides = items or {}
    per_page = []
    totals = {item: 0 for item in TIMING_ITEMS}
    unknown_items: set[str] = set()
    for role in data.get("page_roles") or []:
        page_id = role["page_id"]
        page = None
        if page_id in entries:
            page = store.read_object_json(entries[page_id]["page"])
        segments = ((page or {}).get("content_mapping") or {}).get("speech_segments") or []
        speaking = sum(segment.get("estimated_seconds") or 0 for segment in segments)
        page_items = {item: 0 for item in TIMING_ITEMS}
        page_items["speaking"] = speaking if segments else (role.get("timing_seconds") or 0)
        for item, value in (overrides.get(page_id) or {}).items():
            if item not in TIMING_ITEMS:
                unknown_items.add(item)
                continue
            page_items[item] = int(value)
        source = "speech_segments" if segments else (
            "plan_role_estimate" if role.get("timing_seconds") is not None else "absent")
        per_page.append({"page_id": page_id, "role": role.get("role"),
                         "items": page_items, "total": sum(page_items.values()),
                         "speaking_source": source,
                         "plan_role_estimate": role.get("timing_seconds")})
        for item in TIMING_ITEMS:
            totals[item] += page_items[item]
    budget = data.get("time_budget") or {}
    total_seconds = budget.get("total_seconds")
    interaction_seconds = budget.get("interaction_seconds") or 0
    interaction_total = totals["pause"] + totals["exercise"] + totals["qa"]
    if interaction_total == 0 and interaction_seconds:
        interaction_total = interaction_seconds
    estimated_total = totals["speaking"] + interaction_total
    within = None if total_seconds is None else estimated_total <= total_seconds
    return {
        "status": "over_budget" if within is False else "within_budget" if within else "unknown_total",
        "per_page": per_page,
        "totals": {**totals, "interaction": interaction_total, "estimated_total": estimated_total},
        "declared": {"total_seconds": total_seconds,
                     "speaking_seconds": budget.get("speaking_seconds"),
                     "interaction_seconds": budget.get("interaction_seconds"),
                     "constraint": budget.get("constraint"),
                     "page_count": len(data.get("page_order") or [])},
        "over_by": None if within is not False else estimated_total - total_seconds,
        "estimated": True,
        "measured": False,
        "unknown_items": sorted(unknown_items),
        "note": ("all numbers here are estimates; a measured time only exists in Review evidence "
                 "from an actual rehearsal, and page count alone never proves a duration"),
    }


def check_time_budget(store, document, *, items: dict | None = None) -> dict:
    """The content-side verdict for a declared hard/soft time budget."""
    budget = timing_budget(store, document, items=items)
    if budget["status"] == "no_plan":
        return {**budget, "allows": False, "next_action": "plan_pages_and_budget"}
    declared = budget["declared"]
    if declared["total_seconds"] is None or declared["constraint"] == "unspecified":
        return {**budget, "allows": True,
                "next_action": "declare_a_total_and_constraint_before_claiming_a_duration"}
    if budget["over_by"]:
        return {**budget, "allows": False, "next_action": "present_a_real_keep_drop_tradeoff"}
    return {**budget, "allows": True, "next_action": "proceed"}
