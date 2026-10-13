"""Bounded production budgets and delegation materialization (CONTRACTS §3.2–§3.5).

Two budget templates replace "ask the user for a call count" with a *computed,
displayed* bound:

* ``initial_per_page`` — an explicit "do the whole deck" instruction with no
  numeric limit gets one first-image call for every agreed page that has no
  reusable blueprint (TASKS §3.4.3/§3.4.6). Sample-page trials keep their own
  separate budget and never expand into the deck budget.
* ``edit_rebuild_per_page`` — an explicit edit that asks for usable artwork gets
  at most one rebuild call per page that must actually be redrawn; pages that
  only need SVG/notes/recompile get zero (TASKS §3.5). Pages outside the
  authorized page_ids/layers are reported as scope gaps, never rebuilt
  "because a dependency changed".

Credits are keyed ``<request_id>:initial:<page_id>`` /
``<request_id>:rebuild:<page_id>`` and are spent through the existing allowance
ledger: a new operation id, a restart or a repeated grant never refreshes an
already-consumed credit. Nothing here writes; :func:`materialize_execution`
performs the single write by delegating to ``collaboration.grant`` so CAS,
receipts and the parent-chain validation are reused rather than re-implemented.
"""
from __future__ import annotations

from . import eligibility
from .models import ModelError

TEMPLATE_INITIAL = "initial_per_page"
TEMPLATE_EDIT = "edit_rebuild_per_page"


def _authorized_page_ids(store, scope) -> list[str] | None:
    return eligibility.scope_page_ids(store, scope)


def _reusable_blueprint(document, page_id) -> bool:
    """Whether the page already has an original image the runtime may reuse.

    A page counts as reusable when it carries a blueprint and the current copy
    still matches the committed page entry it was built for; a page whose copy
    moved (or that never had one) needs a first image call. The looser
    template/coverage reuse rules belong to the design card (T05); this is the
    bounded first-pass accounting the contract fixes.
    """
    entry = next((e for e in document.get("pages") or [] if e.get("page_id") == page_id), None)
    if not entry:
        return False
    return bool(entry.get("blueprint") and entry.get("page"))


def initial_per_page_plan(store, document, *, request_id: str,
                          page_order=None, page_ids=None, scope=None) -> dict:
    """The bounded first-image budget for an agreed deck (CONTRACTS §3.4.3)."""
    scope = scope or {}
    pages = list(page_order or [])
    if not pages:
        pages = list(page_ids if page_ids is not None else (_authorized_page_ids(store, scope) or []))
    if not pages:
        raise ModelError("budget/initial_per_page",
                         "no fixed page set: an unfixed deck scope cannot materialize a numeric budget")
    reusable = [page_id for page_id in pages if _reusable_blueprint(document, page_id)]
    first_time = [page_id for page_id in pages if page_id not in reusable]
    credits = [{"page_id": page_id, "budget_key": f"{request_id}:initial:{page_id}", "calls": 1}
               for page_id in first_time]
    return {
        "budget_template": TEMPLATE_INITIAL,
        "request_id": request_id,
        "pages_selected": len(pages),
        "pages_reused": len(reusable),
        "pages_requiring_first_image": first_time,
        "reused_page_ids": reusable,
        "first_generation_upper_bound": len(first_time),
        "retry_budget": 0,
        "credits": credits,
        "max_external_calls": len(first_time),
        "display": (f"选定 {len(pages)} 页，复用 {len(reusable)} 页，首次生成最多 "
                    f"{len(first_time)} 次；已授权样页单独列出；额外重试为 0"),
    }


def edit_rebuild_plan(store, document, *, request_id: str, change_plan: dict,
                      scope=None) -> dict:
    """The bounded rebuild budget for an explicit edit (CONTRACTS §3.5)."""
    scope = scope or {}
    authorized_pages = _authorized_page_ids(store, scope)
    authorized_layers = set(scope.get("layers") or [])
    affected, must_redraw, reuse, gaps = [], [], [], []
    for action in change_plan.get("actions") or []:
        page_id = action.get("page_id")
        layer = (action.get("write_slots") or [None])[0]
        if page_id in affected:
            continue
        affected.append(page_id)
        if authorized_pages is not None and page_id not in authorized_pages:
            gaps.append({"page_id": page_id, "reason": "page_outside_authorized_scope"})
            continue
        if layer == "blueprint" or (layer == "page" and not _reusable_blueprint(document, page_id)):
            if authorized_layers and "blueprint" not in authorized_layers:
                gaps.append({"page_id": page_id, "reason": "layer_outside_authorized_scope"})
                continue
            must_redraw.append(page_id)
        else:
            reuse.append(page_id)
    credits = [{"page_id": page_id, "budget_key": f"{request_id}:rebuild:{page_id}", "calls": 1}
               for page_id in must_redraw]
    return {
        "budget_template": TEMPLATE_EDIT,
        "request_id": request_id,
        "affected_page_ids": affected,
        "must_redraw_page_ids": must_redraw,
        "reused_page_ids": reuse,
        "scope_gaps": gaps,
        "first_rebuild_upper_bound": len(must_redraw),
        "retry_budget": 0,
        "credits": credits,
        "max_external_calls": len(must_redraw),
        "display": (f"受影响 {len(affected)} 页；必须重画 {len(must_redraw)} 页；复用 "
                    f"{len(reuse)} 页；首次重建上限 {len(must_redraw)}；重试 0"
                    + (f"；范围外缺口 {len(gaps)} 页（不自动重做）" if gaps else "")),
    }


def budget_plan(store, document, *, template: str, request_id: str, **kwargs) -> dict:
    if template == TEMPLATE_INITIAL:
        return initial_per_page_plan(store, document, request_id=request_id, **kwargs)
    if template == TEMPLATE_EDIT:
        return edit_rebuild_plan(store, document, request_id=request_id, **kwargs)
    raise ModelError("budget/template", f"unknown budget template {template!r}")


def credit_problems(store, document, plan: dict) -> list[dict]:
    """Credits that are already consumed and therefore never refresh.

    A consumed credit is not re-created by a new operation id, a restart or a
    repeated grant (CONTRACTS §3.4.4/§3.5, TASKS T04 item 4).
    """
    problems = []
    for credit in plan.get("credits") or []:
        state = eligibility.credit_state(store, document, credit["budget_key"], credit["calls"])
        if state["used"]:
            problems.append({"page_id": credit["page_id"], "budget_key": credit["budget_key"],
                             "used": state["used"], "reason": "credit_already_consumed"})
    return problems


def materialize_execution(project, *, parent_authorization_ref=None, plan_ref=None,
                          page_order=None, budget_template: str | None = None,
                          actions=None, operation_id: str, base_revision: str,
                          adapter_context=None, instruction_evidence: dict | None = None,
                          request_id: str | None = None) -> dict:
    """Turn a delegate/future-page authority into one concrete execute grant.

    The materialized grant names real ``page_ids`` (never an empty set meaning
    "all pages"), shares the parent's numeric budget root instead of copying
    its ceiling, carries one bounded credit per page and is written through the
    normal ``collaboration.grant`` path (CAS + receipt + parent-chain checks).
    A credit that is already consumed is refused unless the user gives a new
    explicit increase.
    """
    from pathlib import Path
    from . import collaboration
    from .store import Store
    store = Store(Path(project).expanduser())
    document = store.load_document()
    region = document.get("collaboration") or {}
    request = region.get("request") or {}
    request_id = request_id or request.get("request_id")
    if not request_id:
        raise ModelError("budget/request", "materializing an execution grant needs the current work request")
    parent = None
    if parent_authorization_ref is not None:
        parent = store.read_object_json(parent_authorization_ref)

    plan = None
    scope = dict((request.get("scope") or {}))
    if budget_template:
        plan = budget_plan(store, document, template=budget_template, request_id=request_id,
                           page_order=page_order,
                           scope=(parent or {}).get("scope") or scope)
        problems = credit_problems(store, document, plan)
        if problems:
            raise ModelError(
                "budget/credit",
                "these credits are already consumed and a repeated grant or a new operation id "
                f"never refreshes them: {problems}; a new explicit increase is required")
        page_ids = plan["must_redraw_page_ids"] if budget_template == TEMPLATE_EDIT \
            else plan["pages_requiring_first_image"]
    else:
        page_ids = list(page_order or [])
        if not page_ids:
            raise ModelError("budget/scope",
                             "materialized execute grants need concrete page ids; an empty set is not 'all pages'")

    if parent is not None:
        allowed = eligibility.scope_page_ids(store, parent.get("scope") or {})
        if allowed is not None and not set(page_ids) <= set(allowed):
            raise ModelError("budget/scope",
                             f"pages {sorted(set(page_ids) - set(allowed))} are outside the parent delegation")
    grant_scope = {**(parent.get("scope") if parent else scope), "page_ids": page_ids}
    grant_scope["page_manifest_ref"] = (parent or {}).get("scope", {}).get("page_manifest_ref") \
        if parent else grant_scope.get("page_manifest_ref")
    if plan and budget_template == TEMPLATE_EDIT and not plan["must_redraw_page_ids"]:
        # A zero-rebuild edit is still a valid (zero-call) execution grant.
        pass
    input_payload = {
        "mode": "execute",
        "actions": list(actions or (parent or {}).get("actions") or []),
        "scope": grant_scope,
        "decision_refs": list((parent or {}).get("decision_refs") or []),
        "max_external_calls": len(page_ids),
        "max_candidate_count": (parent or {}).get("max_candidate_count", 0),
        "budget_template": budget_template,
        "budget_parent_ref": (parent or {}).get("budget_parent_ref") or parent_authorization_ref,
        "budget_key": (plan["credits"][0]["budget_key"] if plan and plan["credits"] else None),
        "parent_authorization_ref": parent_authorization_ref,
        "adoption_policy": (parent or {}).get("adoption_policy", "candidate_only"),
        "delivery_binding": (parent or {}).get("delivery_binding", "none"),
        "instruction_evidence": instruction_evidence,
    }
    return collaboration.grant(project, input=input_payload, base_revision=base_revision,
                               operation_id=operation_id, adapter_context=adapter_context)
