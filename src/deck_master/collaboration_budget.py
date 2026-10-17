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


def _reusable_blueprint(document, page_id, store=None) -> bool:
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
    if not (entry.get("blueprint") and entry.get("page")):
        return False
    if store is not None:
        from .production import resolve_page_design
        from .visual_dependencies import page_visual_equivalent
        try:
            artifact = store.read_object_json(entry["blueprint"])
            origin = (artifact.get("provenance") or {}).get("generated_from_page")
            if not origin or not page_visual_equivalent(store, origin, entry["page"], page_id):
                return False
            store.read_object_bytes(artifact["file"])
            resolve_page_design(store, document, entry, require_current=True)
        except (ModelError, KeyError, OSError, ValueError):
            return False
    return True


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
    if len(pages) != len(set(pages)):
        raise ModelError("budget/page_order", "the fixed page set must be unique")
    reusable = [page_id for page_id in pages if _reusable_blueprint(document, page_id, store)]
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
        if page_id not in affected:
            affected.append(page_id)
        if authorized_pages is not None and page_id not in authorized_pages:
            gaps.append({"page_id": page_id, "reason": "page_outside_authorized_scope"})
            continue
        if layer == "blueprint":
            if authorized_layers and "blueprint" not in authorized_layers:
                gaps.append({"page_id": page_id, "reason": "layer_outside_authorized_scope"})
                continue
            if page_id not in must_redraw:
                must_redraw.append(page_id)
            if page_id in reuse:
                reuse.remove(page_id)
        elif page_id not in must_redraw and page_id not in reuse:
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


def _fixed_plan(store, document, plan_ref=None):
    ref = document.get("content_plan")
    if not ref or (plan_ref is not None and plan_ref != ref):
        raise ModelError("budget/plan_ref", "use the actual current adopted Plan")
    plan = store.read_object_json(ref)
    pages = list((plan.get("input") or {}).get("page_order") or [])
    if not pages:
        pages = [item["page_id"] for item in plan.get("page_links") or []]
    current = [item["page_id"] for item in document.get("pages") or []]
    if not pages or len(pages) != len(set(pages)) or pages != current:
        raise ModelError("budget/plan_ref", "the adopted Plan needs a fixed, unique current page order")
    return ref, pages


def describe_document(store, document, *, budget_template, scope=None, plan_ref=None,
                      change_plan_id=None, parent_authorization_ref=None):
    """Read-only calculation against real current Plan/ChangePlan bytes."""
    request = (document.get("collaboration") or {}).get("request") or {}
    if not request or request.get("closed"):
        raise ModelError("budget/request", "a budget needs the current open request")
    expected = {TEMPLATE_INITIAL: "full_deck", TEMPLATE_EDIT: "edit"}.get(budget_template)
    if expected is None or request.get("intent") != expected:
        raise ModelError("budget/template", "this template does not cover the current request intent")
    scope = dict(scope or request["scope"])
    parent = store.read_object_json(parent_authorization_ref) if parent_authorization_ref else None
    fixed_ref, order = _fixed_plan(store, document, plan_ref)
    selected = eligibility.scope_page_ids(store, scope)
    if selected is None:
        selected = order
    elif not selected:
        raise ModelError("budget/scope", "an explicit empty page set is not 'all pages'")
    if not set(selected) <= set(order):
        raise ModelError("budget/scope", "selected pages must be in the current adopted Plan")
    concrete_scope = {**scope, "page_ids": list(selected),
                      "page_manifest_ref": fixed_ref if list(selected) == order else None}
    request_pages = eligibility.scope_page_ids(store, request["scope"])
    if ((request_pages is not None and not set(selected) <= set(request_pages))
            or not set(scope.get("layers") or []) <= set(request["scope"].get("layers") or [])):
        raise ModelError("budget/scope", "the budget cannot exceed the current request scope")
    if parent:
        from .collaboration_scope import delegation_gaps
        gaps = delegation_gaps(store, parent, {"scope": concrete_scope, "actions": [],
            "delegated_topics": [], "evidence": parent["evidence"]})
        if gaps:
            raise ModelError("budget/scope", f"outside the parent delegation: {gaps}")
        future = (parent.get("constraints") or {}).get("future_pages") or {}
        if eligibility.scope_page_ids(store, parent.get("scope") or {}) is None and (
                not isinstance(future.get("max_pages"), int)
                or isinstance(future.get("max_pages"), bool)):
            raise ModelError("budget/scope", "future pages need an effective finite page budget")
    if budget_template == TEMPLATE_INITIAL:
        if "blueprint" not in scope.get("layers", []):
            raise ModelError("budget/scope", "first-image production requires the blueprint layer")
        plan = initial_per_page_plan(store, document, request_id=request["request_id"],
                                     page_order=selected, scope=concrete_scope)
        # Derived pages retain their origin; renaming/splitting a spent page
        # cannot create a new first-image credit under this request.
        sources = {}
        for ref in document.get("page_derivations") or []:
            derivation = store.read_object_json(ref)
            for item in derivation.get("result_pages") or []:
                sources[item["page_id"]] = [page["page_id"] for page in derivation["source_pages"]]
        for credit in plan["credits"]:
            pending, seen = list(sources.get(credit["page_id"], [])), set()
            while pending:
                origin = pending.pop()
                if origin in seen:
                    continue
                seen.add(origin); pending.extend(sources.get(origin, []))
                if eligibility.credit_state(store, document,
                        f"{request['request_id']}:initial:{origin}")["used"]:
                    raise ModelError("budget/credit", "derived pages cannot refresh a consumed first-image credit")
    else:
        if not change_plan_id:
            raise ModelError("budget/change_plan_id", "use the immutable ID returned by changes plan")
        from .changes import _read_plan, _plan
        change, change_ref = _read_plan(store, change_plan_id)
        if change["base_revision"] != document["revision_id"] or _plan(store, document, change["input"]) != change:
            raise ModelError("budget/change_plan_id", "the ChangePlan changed; preview it against current control")
        plan = edit_rebuild_plan(store, document, request_id=request["request_id"],
                                 change_plan=change, scope=concrete_scope)
        plan["change_plan_ref"] = change_ref
        plan["change_payload_digest"] = change["payload_digest"]
        plan["max_candidate_count"] = len(plan["affected_page_ids"]) if change["input"].get("mode") == "trial" else 0
        if plan["scope_gaps"]:
            plan["blocked"] = True
    plan.update(scope=concrete_scope, plan_ref=fixed_ref,
                artifact_revision_id=document["revision_id"], control_revision_id=document["revision_id"])
    plan["credit_problems"] = credit_problems(store, document, plan)
    return plan


def describe(project, **kwargs):
    from pathlib import Path
    from .store import Store
    store = Store(Path(project).expanduser())
    return describe_document(store, store.load_document(), **kwargs)


def prepare_grant(store, document, authorization, input):
    """Materialize the template inside the existing grant CAS transaction."""
    if "fixed_budget" in authorization["constraints"]:
        raise ModelError("authorization/constraints/fixed_budget", "budget bindings are computed by the Runtime")
    template = authorization.get("budget_template")
    if not template:
        return None
    if "scope" in input and not input["scope"]:
        raise ModelError("budget/scope", "an explicitly empty scope cannot default to the whole request")
    if authorization["mode"] != "execute":
        raise ModelError("authorization/budget_template", "a template materializes an execute grant")
    plan = describe_document(store, document, budget_template=template, scope=authorization["scope"],
        plan_ref=input.get("plan_ref"), change_plan_id=input.get("change_plan_id"),
        parent_authorization_ref=authorization.get("parent_authorization_ref"))
    if plan.get("blocked") or plan["credit_problems"]:
        raise ModelError("budget/credit", f"budget_exhausted: credits already consumed or outside scope: {plan}")
    authorization["scope"] = plan["scope"]
    ceiling = plan["max_external_calls"]
    if "max_external_calls" in input:
        explicit = input["max_external_calls"]
        if not isinstance(explicit, int) or isinstance(explicit, bool) or explicit < 0:
            raise ModelError("authorization/max_external_calls", "must be a nonnegative integer")
        ceiling = min(ceiling, explicit)
    parent_ref = authorization.get("parent_authorization_ref")
    if parent_ref:
        parent = store.read_object_json(parent_ref)
        if parent["max_external_calls"]:
            ceiling = min(ceiling, parent["max_external_calls"])
        authorization["budget_parent_ref"] = parent_ref
    # Repeated grants share the first numeric root, even with new IDs/Plans.
    for ref, other in eligibility._authorization_heads(store, document):
        if other.get("request_id") == authorization["request_id"] and other.get("budget_template") == template \
                and (other.get("constraints") or {}).get("fixed_budget"):
            authorization["budget_parent_ref"] = ref
            ceiling = min(ceiling, other["max_external_calls"])
            break
    authorization["max_external_calls"] = ceiling
    plan["computed_upper_bound"] = plan["max_external_calls"]
    plan["max_external_calls"] = ceiling
    plan["explicit_limit_conflict"] = ceiling < plan["computed_upper_bound"]
    authorization["budget_key"] = plan["credits"][0]["budget_key"] if len(plan["credits"]) == 1 else None
    authorization["constraints"]["fixed_budget"] = plan
    return plan


def materialize_execution(project, *, parent_authorization_ref=None, plan_ref=None,
                          page_order=None, budget_template=None, change_plan_id=None,
                          actions=None, operation_id, base_revision, adapter_context=None,
                          instruction_evidence=None, request_id=None):
    """Compatibility SDK wrapper; the grant transaction owns all computation."""
    from pathlib import Path
    from . import collaboration
    from .store import Store
    store = Store(Path(project).expanduser())
    doc = store.load_document(); request = (doc.get("collaboration") or {}).get("request") or {}
    if request_id is not None and request_id != request.get("request_id"):
        raise ModelError("budget/request", "materialization must name the current request")
    parent = store.read_object_json(parent_authorization_ref) if parent_authorization_ref else {}
    scope = dict(parent.get("scope") or request.get("scope") or {})
    if page_order:
        if scope.get("page_manifest_ref") and list(page_order) != eligibility.scope_page_ids(store, scope):
            raise ModelError("budget/scope", "explicit page_order cannot be expanded by a whole-deck parent manifest; use an explicitly narrower parent")
        scope["page_ids"] = list(page_order)
    elif page_order is not None:
        raise ModelError("budget/scope", "an explicit empty page_order is not 'all pages'")
    if not budget_template and not scope.get("page_ids"):
        raise ModelError("budget/scope", "an empty set is not 'all pages'")
    allowed = eligibility.scope_page_ids(store, parent.get("scope") or {}) if parent else None
    if allowed is not None and not set(scope.get("page_ids") or []) <= set(allowed):
        raise ModelError("budget/scope", "pages are outside the parent delegation")
    payload = {"mode": "execute", "scope": scope,
        "actions": list(actions or parent.get("actions") or []),
        "decision_refs": parent.get("decision_refs") or [], "budget_template": budget_template,
        "plan_ref": plan_ref, "change_plan_id": change_plan_id,
        "parent_authorization_ref": parent_authorization_ref,
        "adoption_policy": parent.get("adoption_policy", "candidate_only"),
        "delivery_binding": parent.get("delivery_binding", "none"),
        "max_candidate_count": parent.get("max_candidate_count", 0),
        "instruction_evidence": instruction_evidence}
    if not budget_template:
        payload["max_external_calls"] = len(scope["page_ids"])
    return collaboration.grant(project, input=payload, base_revision=base_revision,
        operation_id=operation_id, adapter_context=adapter_context)
