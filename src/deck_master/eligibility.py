"""Unified eligibility resolver (content collaboration v1.2 CONTRACTS §6–§7).

``evaluate`` is a **pure interpreter**: it reads the Store plus an artifact
snapshot and a control snapshot, and never creates a task, writes a receipt,
reserves an allowance or moves the current pointer. Every entry point listed in
CONTRACTS §6.2 asks the same function for the same facts through ``guard``, so
"each boundary consumes one eligibility judgement" is a code fact, not a
convention.

Snapshots
    ``control_snapshot`` is the current project head for every formal action;
    ``artifact_snapshot`` may be a user-selected historical revision (CONTRACTS
    §7/§8: historical delivery reads the selected artifact with the *current*
    control, so an old relaxed policy or an old human label can never override
    a current withdrawal).

Enforcement boundary (T04 development increment)
    Projects at the ``collaboration.v1`` writer boundary (or carrying a
    ``collaboration`` region) get full enforcement: ``guard`` raises for a
    blocked action. Projects below that writer keep today's behaviour — the
    resolver still *computes* ``migration_required`` for them and dedicated
    tests lock that decision, but the gate does not fire until the deployment
    step that turns on the new writer for real projects (MIGRATION §5.3: while
    enforcement is not complete, new-writer production is not enabled for real
    projects). ``decision["enforcement"]`` states which mode was applied.

Reason codes
    CONTRACTS §6 requires at least ``request_paused``, ``scope_exceeded``,
    ``decision_needed``, ``authority_insufficient``,
    ``authority_channel_unavailable``, ``basis_stale``,
    ``authorization_revoked``, ``budget_exhausted``,
    ``input_reconciliation_pending``, ``professional_review_required``,
    ``migration_required``; ``needs_reviewer`` is an independent addition that
    never replaces ``professional_review_required`` (the preproduction content
    review and the human professional sign-off are two policy dimensions).
    This module registers a small set of extra codes the contract implies but
    does not name — ``request_closed``, ``binding_invalid``, ``binding_stale``,
    ``budget_unknown``, ``persistence_none``, ``legacy_writer`` — each listed
    with its meaning in ``REASON_MEANINGS``.

Task bindings
    ``binding_eligibility_digest`` is the single formula shared with T03's
    compose.v2 dispatch: sha256 over the canonical JSON of ``{"phase",
    "write_scope", "basis"}`` where ``basis`` is the list of slice sha256
    values sorted by slice key. A task carrying a ``collaboration_binding`` is
    checked for structure (``models.require_task_binding``) and timeliness
    (recomputed digest). A task without a binding is judged by protocol: old
    protocols may settle already-started calls but cannot open new production.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import dependency_slices, models, operations
from .models import ModelError, canonical_json_bytes, sha256_bytes
from .store import Store, StoreError

SCHEMA_VERSION = "eligibility.v1"

# ---------------------------------------------------------------------------
# Registered reason codes


REASON_ORDER = (
    # request / control state
    "migration_required",
    "request_closed",
    "request_paused",
    "persistence_none",
    "input_reconciliation_pending",
    # scope and decisions
    "scope_exceeded",
    "decision_needed",
    "basis_stale",
    # authority
    "authorization_revoked",
    "authority_insufficient",
    "authority_channel_unavailable",
    "binding_invalid",
    "binding_stale",
    # quality
    "needs_reviewer",
    "preproduction_blocked",
    "professional_review_required",
    # money
    "budget_unknown",
    "budget_exhausted",
    "user_stop",
)

REASON_MEANINGS = {
    "migration_required": "the project predates the collaboration writer; the action is refused until its explicit migration apply",
    "request_closed": "the current work request is closed (completed/rejected/withdrawn/superseded); start a new request",
    "request_paused": "the current request is paused; reads, display, cancel and settlement stay available",
    "persistence_none": "a strict read-only request can never write project state; the report belongs outside the project",
    "input_reconciliation_pending": "inputs changed and the content still awaits reconciliation against the new inputs",
    "scope_exceeded": "the target pages/layers/purpose are outside the authorized scope; an empty page set is never 'all pages'",
    "decision_needed": "a required business decision (or delegate covering its topic) is missing or ineffective",
    "basis_stale": "the controlling decision/authorization basis no longer matches the current document",
    "authorization_revoked": "the authorization that could cover this action is revoked (or its parent chain is)",
    "authority_insufficient": "no effective execute/delegate authorization covers this action and scope",
    "authority_channel_unavailable": "the verified_user policy needs a trusted user-event channel that is not available; no silent downgrade",
    "binding_invalid": "the task's collaboration binding does not name the current request/records",
    "binding_stale": "the task's recomputed eligibility digest differs from its recorded binding digest",
    "needs_reviewer": "the required independent preproduction content review has no acceptable reviewer; a review draft can still be returned",
    "preproduction_blocked": "the preproduction content review does not pass on the current manuscript (units missing, open findings, or no manuscript yet); a review draft can still be returned",
    "professional_review_required": "delivery policy requires a verified human professional review that the selected artifact does not have",
    "budget_unknown": "an unsettled external call exists project-wide; resolve it before new calls",
    "budget_exhausted": "the authorization's bounded call ceiling has no remaining credit for a new call",
    "user_stop": "the project stop policy (policy.user_stop) forbids external calls until it is lifted",
}

# Extra (non-contract-named) codes this resolver registers, kept explicit so
# the entry inventory test can assert the set never grows silently.
EXTRA_REASON_CODES = ("request_closed", "binding_invalid", "binding_stale",
                      "budget_unknown", "persistence_none", "user_stop",
                      "preproduction_blocked")


# ---------------------------------------------------------------------------
# Action catalog (CONTRACTS §6.2 row per action)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    group: str                  # creation | execution | adoption | change | local | delivery | history
    subject: str                # project | deck | pages | external_artifact
    layers: tuple[str, ...]
    decision_topics: tuple[str, ...]
    authority: str              # none | execute | delegate | either
    production: bool            # dispatches or continues content/visual production
    writes: bool                # mutates project state when it proceeds
    external_calls: bool        # consumes bounded external image calls
    role: str                   # responsible role when the action proceeds
    card: str | None = None     # decision-card projection when a decision is missing
    delivery: bool = False      # consumes the unified professional delivery policy


def _spec(name, group, subject, layers=(), topics=(), authority="none", *,
          production=False, writes=True, external=False, role="runtime",
          card=None, delivery=False) -> ActionSpec:
    return ActionSpec(name=name, group=group, subject=subject, layers=tuple(layers),
                      decision_topics=tuple(topics), authority=authority,
                      production=production, writes=writes, external_calls=external,
                      role=role, card=card, delivery=delivery)


ACTIONS: dict[str, ActionSpec] = {spec.name: spec for spec in (
    # -- creation and routing (CONTRACTS §6.2 row 1)
    _spec("create", "creation", "project", role="user"),
    _spec("import_draft", "creation", "deck", layers=("page_copy",), authority="none",
          production=True, role="host", card="visible_copy"),
    _spec("continue_project", "creation", "deck", role="runtime"),
    _spec("dispatch.compose", "creation", "deck", layers=("narrative", "plan", "page_copy"),
          production=True, role="host"),
    _spec("dispatch.host_task", "creation", "pages", production=True, role="host"),
    _spec("dispatch.blueprint", "creation", "pages", layers=("blueprint",),
          authority="either", production=True, external=True, role="host"),
    # -- execution and fees (row 2)
    _spec("task.start", "execution", "pages", production=True, role="host"),
    _spec("allowance.allocate", "execution", "pages", authority="execute",
          production=True, external=True, role="runtime"),
    _spec("allowance.repair", "execution", "pages", authority="execute",
          production=True, external=True, role="runtime"),
    _spec("call.begin", "execution", "pages", authority="either",
          production=True, external=True, role="host"),
    _spec("generation.dispatch", "execution", "pages", authority="execute",
          production=True, external=True, role="runtime"),
    # -- adoption (row 3)
    _spec("task.accept", "adoption", "pages", writes=True, role="runtime"),
    _spec("proposal.adopt", "adoption", "deck", writes=True, role="runtime"),
    _spec("call.settle", "execution", "pages", writes=True, role="host"),
    _spec("material.upload", "adoption", "external_artifact", writes=True, role="user"),
    _spec("content.inputs_update", "adoption", "deck", layers=("narrative",),
          production=False, writes=True, role="user", card="direction"),
    _spec("page.edit", "adoption", "pages", layers=("page_copy",), production=True,
          writes=True, role="host"),
    _spec("asset.import", "adoption", "deck", layers=("design",), writes=True, role="user"),
    _spec("design.update", "adoption", "deck", layers=("design",), writes=True, role="user"),
    _spec("review.record", "adoption", "deck", layers=("review",), writes=True, role="reviewer"),
    _spec("annotation.save", "adoption", "deck", layers=("review",), writes=True, role="reviewer"),
    _spec("review.strict", "adoption", "external_artifact", layers=("review",),
          writes=False, role="reviewer"),
    # -- change / candidates / content operations (row 4)
    _spec("change.plan", "change", "pages", writes=False, role="runtime"),
    _spec("change.commit", "change", "pages", authority="either", production=True,
          role="user", card="direction"),
    _spec("candidate.select", "change", "pages", writes=True, role="user"),
    _spec("candidate.adopt", "change", "pages", authority="execute", writes=True,
          production=False, role="user", card="style.palette"),
    _spec("style.propose", "change", "pages", layers=("design",), authority="either",
          production=True, role="user", card="style.density"),
    _spec("design.propose", "change", "pages", layers=("design",), authority="either",
          production=False, role="user", card="style.density"),
    _spec("design.feasibility", "change", "pages", layers=("design",), authority="either",
          production=False, role="user", card="style.density"),
    _spec("style.trial", "change", "pages", authority="either", production=True,
          external=True, role="user", card="style.density"),
    _spec("style.expand", "change", "pages", authority="either", production=True,
          external=True, role="user", card="style.density"),
    _spec("content.operation", "change", "deck", layers=("page_copy",), authority="either",
          topics=("direction",), production=True, writes=True, role="user",
          card="direction"),
    _spec("stage.assemble", "change", "deck", layers=("output",), production=True,
          writes=True, role="runtime"),
    # -- local production (row 5): no external fee, still bounded by the request
    _spec("compile.svg", "local", "pages", layers=("svg",), production=True, writes=True,
          role="runtime"),
    _spec("render.preview", "local", "pages", layers=("svg",), production=True, writes=True,
          role="runtime"),
    _spec("compile.ppt", "local", "deck", layers=("output",), production=True,
          writes=True, role="runtime"),
    _spec("compile.repair", "local", "pages", production=True, writes=True, role="runtime"),
    # -- delivery (row 6)
    _spec("export.review", "delivery", "deck", writes=True, role="runtime"),
    _spec("export.engineering", "delivery", "deck", writes=True, role="runtime"),
    _spec("export.delivery", "delivery", "deck", layers=("output",), authority="either",
          topics=("delivery_acceptance",), writes=True, role="user",
          card="delivery_acceptance", delivery=True),
    _spec("handoff.delivery", "delivery", "deck", layers=("output",), authority="either",
          topics=("delivery_acceptance",), writes=True, role="user",
          card="delivery_acceptance", delivery=True),
    _spec("readiness.final", "delivery", "deck", layers=("output",), writes=False,
          role="runtime", delivery=True),
    _spec("studio.deliver", "delivery", "deck", layers=("output",), authority="either",
          topics=("delivery_acceptance",), writes=True, role="user",
          card="delivery_acceptance", delivery=True),
    _spec("delivery.historical", "delivery", "deck", layers=("output",), authority="either",
          topics=("delivery_acceptance",), writes=True, role="user",
          card="delivery_acceptance", delivery=True),
    # -- control plane (T02 write paths; correctness lives in collaboration.py,
    # T04 consumes the same judgement for reporting and migration gating)
    _spec("request.start", "control", "project", writes=True, production=False, role="user"),
    _spec("request.pause", "control", "project", writes=True, production=False, role="user"),
    _spec("request.resume", "control", "project", writes=True, production=False, role="user"),
    _spec("decision.record", "control", "project", writes=True, production=False, role="user"),
    _spec("authorization.grant", "control", "project", writes=True, production=False, role="user"),
    _spec("authorization.revoke", "control", "project", writes=True, production=False, role="user"),
    _spec("migration.describe", "control", "project", writes=False, role="operator"),
    _spec("migration.apply", "control", "project", writes=True, production=False, role="operator"),
    _spec("review.import", "control", "deck", layers=("review",), writes=True, role="reviewer"),
    # -- history and policy (row 7)
    _spec("restore", "history", "deck", writes=True, role="user"),
    _spec("task.cancel", "history", "pages", writes=True, role="user"),
    _spec("policy.update", "history", "deck", topics=("policy",), writes=True, role="user",
          card="policy"),
    _spec("authority.update", "history", "deck", writes=True, role="user"),
)}

# Actions that need a preproduction content review before real page production
# (CONTRACTS §1.9, §6.3: 新论证 full_deck 默认需要独立内容前审).
PREPRODUCTION_GATED_ACTIONS = ("dispatch.blueprint", "style.trial", "style.expand",
                               "change.commit", "compile.ppt", "stage.assemble")

# Every delivery entry consumes the same authorization vocabulary: a grant
# naming any delivery entry covers the others (they are the same delivery
# fact reached through different frontends, CONTRACTS §6.2/§8).
DELIVERY_ENTRY_ACTIONS = ("export.delivery", "handoff.delivery", "studio.deliver",
                          "delivery.historical")

# Routing/analysis actions that stay available with no request and under a
# paused request: reading, displaying, cancelling and settling are explicitly
# allowed while paused (CONTRACTS §7.1), and `continue` reports the decision
# card instead of raising (CONTRACTS §5).
# Control-plane writes are checked structurally by the T02 collaboration write
# path itself (writer boundary, open request, delegation chains, CAS/receipts);
# T04 consumes the same judgement for reporting/route projection but does not
# re-refuse them — a decision or grant must be recordable even while paused.
CONTROL_PLANE_ACTIONS = ("request.start", "request.pause", "request.resume",
                         "decision.record", "authorization.grant",
                         "authorization.revoke", "migration.describe", "migration.apply",
                         )

# Fact channels: recording that a call settled/released, that a task was
# cancelled, or staging a material upload never creates production. CONTRACTS
# §7.1 keeps settlement and cancellation available while paused or withdrawn,
# so these actions cannot be refused — their decision is informational only.
FACT_ACTIONS = ("call.settle", "task.cancel", "material.upload")

# Actions whose answer is reported rather than enforced on the caller's behalf
# (read routing, stop/settlement facts, control-plane writes).
# `restore` is a reporting decision, not a veto: it recovers content/visual
# facts and keeps the current control (request, withdrawals, pauses, budget,
# writer), so a current stop must not block the recovery itself. The decision it
# returns is still the same one the other entries consume.
#
# T07 note: a strict read-only review (persistence=none) must never reach a
# project write through this path — `review.strict` is the read-only action and
# the persistence_none reason keeps refusing any state-writing action when the
# caller declares persistence=none (see test_persistence_none_forbids_project_writes).
ROUTING_ACTIONS = ("create", "continue_project", "change.plan", "export.review",
                   "export.engineering", "readiness.final", "review.strict",
                   "task.cancel", "call.settle", "material.upload",
                   *CONTROL_PLANE_ACTIONS)

# Per-intent production ceiling (CONTRACTS §5 table). A new request only
# advances what its own intent/content_intent covers; an action outside that
# boundary is a scope violation, not a missing decision.
_INTENT_BLOCKED_ACTIONS = {
    "review_only": ("dispatch.compose", "import_draft", "dispatch.blueprint", "style.trial",
                    "style.expand", "change.commit", "compile.ppt", "stage.assemble",
                    "page.edit", "content.operation"),
    "design_trial": ("dispatch.compose", "import_draft", "compile.ppt", "stage.assemble",
                     "page.edit"),
    "edit": ("dispatch.compose", "stage.assemble"),
}
_CONTENT_INTENT_BLOCKED_ACTIONS = {
    "plan_only": ("dispatch.blueprint", "style.trial", "style.expand", "compile.ppt",
                  "stage.assemble", "page.edit", "import_draft"),
    "speech_only": ("dispatch.blueprint", "style.trial", "style.expand", "page.edit",
                    "import_draft", "dispatch.compose"),
}


def action_spec(action: str) -> ActionSpec:
    spec = ACTIONS.get(action)
    if spec is None:
        raise ModelError("eligibility/action", f"unregistered action {action!r}")
    return spec


def registered_actions() -> tuple[str, ...]:
    return tuple(sorted(ACTIONS))


# ---------------------------------------------------------------------------
# Scope helpers


def scope_page_ids(store: Store, scope: dict | None) -> list[str] | None:
    """The page set a scope actually authorizes.

    A fixed ``page_manifest_ref`` (content_plan.v2) names the members and the
    order; otherwise the explicit ``page_ids``. ``None`` means the deck's page
    set is not fixed yet (a planner scope) — it never means "all pages"
    (CONTRACTS §2.1, §3.4: 空集恒指没有页面).
    """
    scope = scope or {}
    manifest_ref = scope.get("page_manifest_ref")
    if manifest_ref:
        plan = store.read_object_json(manifest_ref)
        return list((plan.get("input") or {}).get("page_order") or [])
    if scope.get("subject") == "deck" and not (scope.get("page_ids") or []):
        return None
    return list(scope.get("page_ids") or [])


def target_page_ids(store: Store, targets: dict | None) -> list[str] | None:
    """The page set a target names: explicit ids or its own manifest."""
    targets = targets or {}
    if targets.get("page_manifest_ref"):
        return scope_page_ids(store, targets)
    if targets.get("page_ids") is not None:
        return list(targets.get("page_ids") or [])
    return None


def normalize_scope(scope: dict | None) -> dict:
    """Deterministic scope JSON: unordered id/layer sets are sorted, order
    carriers (page_manifest_ref/page_order) keep their order (CONTRACTS §7)."""
    scope = dict(scope or {})
    for key in ("page_ids", "layers"):
        scope[key] = sorted(scope.get(key) or [])
    return scope


def binding_eligibility_digest(phase: str, write_scope: dict | None, basis) -> str:
    """The T03/T04 shared binding digest — one implementation, no drift.

    The dispatch-side builder (``collaboration_binding.eligibility_digest``)
    owns the canonical formula; gates recompute through this wrapper so a
    stamped binding and its re-check can never disagree about slice ordering
    or scope canonicalisation (the joint gate caught exactly that drift).
    """
    from .collaboration_binding import eligibility_digest as _canonical
    return _canonical(phase=phase, write_scope=write_scope or {}, basis=basis)


def eligibility_digest(action: str, scope: dict | None, basis) -> str:
    """Action-level digest: action, scope and the required slices (CONTRACTS §7:
    a canonical hash, not an authorization token)."""
    digests = sorted((dep.get("sha256") or "") for dep in (basis or []))
    return sha256_bytes(canonical_json_bytes({
        "action": action,
        "scope": normalize_scope(scope),
        "basis": digests,
    }))


# ---------------------------------------------------------------------------
# Region / record helpers


def _region(document: dict) -> dict | None:
    return document.get("collaboration")


def _request(document: dict) -> dict | None:
    return (_region(document) or {}).get("request")


def _records(store: Store, region: dict, family: str) -> list[tuple[dict, dict]]:
    records = []
    for ref in region.get(family) or []:
        try:
            records.append((ref, store.read_object_json(ref)))
        except Exception:  # noqa: BLE001 - unreadable records cannot participate
            continue
    return records


def _head(records: list[tuple[dict, dict]], id_field: str, identity: str | None):
    if identity is None:
        return None
    replaced = set()
    for _, record in records:
        pair = record.get("replaces")
        if isinstance(pair, dict) and pair.get("path"):
            replaced.add((pair.get("path"), pair.get("sha256")))
    heads = [(ref, record) for ref, record in records
             if record.get(id_field) == identity
             and (ref.get("path"), ref.get("sha256")) not in replaced]
    return heads[-1] if heads else None


def _authorization_heads(store: Store, document: dict) -> list[tuple[dict, dict]]:
    region = _region(document) or {}
    records = _records(store, region, "authorizations")
    replaced = set()
    for _, record in records:
        pair = record.get("replaces")
        if isinstance(pair, dict) and pair.get("path"):
            replaced.add((pair.get("path"), pair.get("sha256")))
    return [(ref, record) for ref, record in records
            if (ref.get("path"), ref.get("sha256")) not in replaced]


def _same_ref(left, right) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return (left.get("path"), left.get("sha256")) == (right.get("path"), right.get("sha256"))


def _chain_root_identity(store: Store, document: dict, record: dict, *, quantity="max_external_calls") -> str | None:
    """The numeric budget root of an authorization: itself, or the top of its
    ``budget_parent_ref`` chain (CONTRACTS §3.4: 子授权共享父预算根)."""
    seen = set()
    current = record
    for _ in range(8):
        identity = current.get("authorization_id")
        parent_ref = current.get("budget_parent_ref")
        if not parent_ref:
            return identity
        if identity in seen:
            return identity
        seen.add(identity)
        try:
            parent = store.read_object_json(parent_ref)
        except Exception:  # noqa: BLE001
            return identity
        if not isinstance(parent, dict) or not parent.get("authorization_id"):
            return identity
        # A zero-call future-page authority cannot execute, but its computed
        # template child is the finite numeric root (§3.4.5).
        if not parent.get(quantity) and (
                (quantity == "max_external_calls" and (current.get("constraints") or {}).get("fixed_budget"))
                or (quantity == "max_candidate_count" and not current.get("parent_authorization_ref"))):
            return identity
        current = parent
    return current.get("authorization_id")


def _budget_chain_ids(store: Store, document: dict, authorization_ref: dict, *, quantity="max_external_calls") -> set[str]:
    ids = set()
    root = _chain_root_identity(store, document, store.read_object_json(authorization_ref), quantity=quantity)
    for _, record in _authorization_heads(store, document):
        if _chain_root_identity(store, document, record, quantity=quantity) == root:
            ids.add(record.get("authorization_id"))
    return ids


# ---------------------------------------------------------------------------
# Ledger accounting (CONTRACTS §3.2–§3.4; the existing allowance ledger is the
# only fee truth — no second cost ledger)


HELD_STATES = ("reserved", "in_flight", "consumed", "unknown")


def binding_of(task: dict) -> dict:
    binding = task.get("collaboration_binding")
    return binding if isinstance(binding, dict) else {}


def task_authorization_id(store: Store, task: dict) -> str | None:
    ref = binding_of(task).get("authorization_ref")
    if not ref:
        return None
    try:
        return store.read_object_json(ref).get("authorization_id")
    except Exception:  # noqa: BLE001
        return None


def allowance_usage(store: Store, document: dict) -> dict:
    """Project ledger totals plus per-budget-key usage for bounded credits."""
    totals = {state: 0 for state in HELD_STATES}
    by_key: dict[str, dict] = {}
    for ref in document.get("tasks") or []:
        try:
            task = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        key = binding_of(task).get("budget_key")
        for entry in task.get("call_allowances") or []:
            state = entry.get("state")
            if state not in totals:
                continue
            totals[state] += 1
            if key:
                slot = by_key.setdefault(key, {name: 0 for name in HELD_STATES})
                slot[state] += 1
    return {"totals": totals, "by_budget_key": by_key}


def credit_state(store: Store, document: dict, budget_key: str, ceiling: int = 1) -> dict:
    usage = allowance_usage(store, document)["by_budget_key"].get(budget_key)
    used = sum((usage or {}).get(state, 0) for state in HELD_STATES)
    return {"budget_key": budget_key, "ceiling": ceiling, "used": used,
            "remaining": max(0, ceiling - used),
            "state": "available" if used < ceiling else "exhausted"}


def authorization_budget(store: Store, document: dict, authorization_ref: dict, *, _quantity="max_external_calls") -> dict:
    """Derived budget state of one authorization and its shared budget root.

    The chain ceiling is the numeric ceiling of the authorization that holds
    one; per-request credits are bounded by ``budget_key`` reuse instead of a
    second ledger. ``state`` is available/exhausted (never a revocation).
    """
    record = store.read_object_json(authorization_ref)
    chain_ids = _budget_chain_ids(store, document, authorization_ref, quantity=_quantity)
    records = {item["authorization_id"]: item for _, item in _authorization_heads(store, document)}
    root_id = _chain_root_identity(store, document, record, quantity=_quantity)
    root = records.get(root_id, record)
    usage = {}
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        identity = task_authorization_id(store, task)
        if identity in chain_ids:
            if _quantity == "max_candidate_count":
                count = (max(1, len(task.get("candidate_refs") or []))
                         if task.get("stage_request", {}).get("mode") == "trial"
                         and (task.get("candidate_refs") or task["status"] in ("queued", "awaiting_host", "running")) else 0)
            else:
                count = sum(entry.get("state") in HELD_STATES for entry in task.get("call_allowances") or [])
            usage[identity] = usage.get(identity, 0) + count
    used = sum(usage.values())
    ceiling = int(root.get(_quantity) or 0)
    remaining = max(0, ceiling - used)
    # Each explicit narrower child also limits its own subtree. A sibling's
    # usage consumes the root, never the other sibling's individual allowance.
    current, seen = record, set()
    while current.get("authorization_id") not in seen:
        identity = current.get("authorization_id"); seen.add(identity)
        descendants = set()
        for candidate in records.values():
            cursor, visited = candidate, set()
            while cursor.get("authorization_id") not in visited:
                candidate_id = cursor.get("authorization_id"); visited.add(candidate_id)
                if candidate_id == identity:
                    descendants.add(candidate["authorization_id"]); break
                parent_ref = cursor.get("budget_parent_ref")
                if not parent_ref:
                    break
                cursor = store.read_object_json(parent_ref)
        local_used = sum(usage.get(item, 0) for item in descendants)
        local_ceiling = int(current.get(_quantity) or 0)
        remaining = min(remaining, max(0, local_ceiling - local_used))
        if identity == root_id or not current.get("budget_parent_ref"):
            break
        current = store.read_object_json(current["budget_parent_ref"])
    unknown = _quantity == "max_external_calls" and any(entry.get("state") == "unknown"
                  for ref in document.get("tasks") or []
                  for entry in (store.read_object_json(ref).get("call_allowances") or []))
    return {
        "authorization_id": record.get("authorization_id"),
        "budget_parent_ref": record.get("budget_parent_ref"),
        "budget_key": record.get("budget_key"),
        "budget_template": record.get("budget_template"),
        "ceiling": ceiling,
        "used": used,
        "remaining": remaining,
        "state": "unknown" if unknown else ("available" if remaining else "exhausted"),
        "chain_ids": sorted(chain_ids),
    }


def candidate_budget(store: Store, document: dict, authorization_ref: dict) -> dict:
    """Existing trial Tasks reserve slots; their immutable candidates retain use.

    Call slots and candidate slots are distinct quantities on the same authority
    chain. Cancellation before producing a candidate releases its slot; adopting
    or restoring content never removes the recorded candidate or spends again.
    """
    return authorization_budget(store, document, authorization_ref, _quantity="max_candidate_count")


# ---------------------------------------------------------------------------
# Task binding state


def task_binding_state(store: Store, document: dict, task: dict) -> dict:
    """Structure and timeliness of one task's collaboration binding.

    ``absent`` is legitimate only for protocols older than collaboration.v1;
    the caller decides per action whether settlement or new production applies
    (CONTRACTS §5, MIGRATION §2.2).
    """
    binding = binding_of(task)
    if not binding:
        declared = ("collaboration.v1" in (task.get("required_capabilities") or [])
                    or str(task.get("protocol_version") or "").endswith(".v2"))
        return {"status": "absent", "reasons": ["binding_missing"],
                "new_protocol": declared,
                "digest": None, "expected_digest": None}
    try:
        models.require_task_binding(document, task)
    except ModelError as exc:
        # A task bound to an old request the current request explicitly lists as
        # background permission keeps its binding (CONTRACTS §2/§12: only an
        # explicit background list lets old work continue).
        request = _request(document) or {}
        if binding.get("request_id") and \
                binding["request_id"] in (request.get("background_request_ids") or []):
            return {"status": "valid", "reasons": [], "new_protocol": True,
                    "digest": binding.get("eligibility_digest"), "expected_digest": None,
                    "background_request_id": binding["request_id"]}
        # A binding whose authorization was replaced by a *withdrawal* is not a
        # foreign binding: report the withdrawal (CONTRACTS §3.3), so the user
        # sees "the withdrawal stands" rather than a structural complaint.
        auth_ref = binding.get("authorization_ref")
        if isinstance(auth_ref, dict) and auth_ref.get("path"):
            try:
                record = store.read_object_json(auth_ref)
            except Exception:  # noqa: BLE001
                record = None
            if isinstance(record, dict) and record.get("authorization_id"):
                head = _head(_records(store, _region(document) or {}, "authorizations"),
                             "authorization_id", record["authorization_id"])
                if head is None or head[1].get("status") in ("revoked", "superseded", "invalidated"):
                    return {"status": "withdrawn", "reasons": [exc.detail], "new_protocol": True,
                            "digest": binding.get("eligibility_digest"), "expected_digest": None,
                            "authorization_id": record["authorization_id"]}
        return {"status": "invalid", "reasons": [exc.detail], "new_protocol": True,
                "digest": binding.get("eligibility_digest"), "expected_digest": None}
    digest = binding.get("eligibility_digest")
    basis = binding.get("eligibility_basis")
    phase = binding.get("phase")
    write_scope = binding.get("write_scope")
    expected = None
    if digest and phase and isinstance(basis, list):
        expected = binding_eligibility_digest(phase, write_scope, basis)
        if expected != digest:
            return {"status": "stale", "reasons": ["eligibility_digest_mismatch"],
                    "new_protocol": True, "digest": digest, "expected_digest": expected}
    # Registered slices must still match the current document.
    if isinstance(basis, list) and basis:
        from .visual_dependencies import assess_visual_task_basis
        state = assess_visual_task_basis(store, document, task, basis)
        if not state["current"]:
            return {"status": "stale", "reasons": sorted(
                [item["key"] for item in state["stale"]] +
                [item["key"] for item in state["unregistered"]]),
                "new_protocol": True, "digest": digest, "expected_digest": expected,
                "basis": state}
    return {"status": "valid", "reasons": [], "new_protocol": True,
            "digest": digest, "expected_digest": expected}


# ---------------------------------------------------------------------------
# Authority / decision resolution


def _decision_topic_covered(store: Store, document: dict, topic: str, targets: dict) -> dict:
    """An accepted, effective decision for the topic, or an effective delegate
    covering it (CONTRACTS §3.1: host_proposal/system_default/imported_unknown
    can never satisfy a required decision).

    Returns ``stale`` when the only accepted decision for the topic is
    ineffective *because its registered basis moved* — the actionable gap is
    then "re-record against current facts", not "record a decision".
    """
    region = _region(document) or {}
    decisions = _records(store, region, "decisions")
    accepted = []
    for ref, record in decisions:
        if record.get("topic") != topic:
            continue
        if record.get("disposition") != "accepted" or record.get("authority_mode") not in (
                "direct_user", "delegated"):
            continue
        accepted.append((ref, record))
    for ref, record in accepted:
        if not _covers(store, record.get("scope"), targets):
            continue
        state = dependency_slices.decision_effectiveness(store, document, ref)
        if state["effective"]:
            return {"satisfied": True, "via": "decision", "ref": ref,
                    "assurance": (record.get("evidence") or {}).get("assurance"),
                    "reasons": []}
    for ref, record in _authorization_heads(store, document):
        if record.get("mode") != "delegate":
            continue
        if topic not in (record.get("delegated_topics") or []):
            continue
        state = dependency_slices.authorization_effectiveness(store, document, ref)
        if state["effective"] and _covers(store, record.get("scope"), targets):
            return {"satisfied": True, "via": "delegate", "ref": ref,
                    "assurance": (record.get("evidence") or {}).get("assurance"),
                    "reasons": []}
    stale_reasons = set()
    for ref, record in accepted:
        state = dependency_slices.decision_effectiveness(store, document, ref)
        stale_reasons.update(state["reasons"])
    return {"satisfied": False, "via": None, "ref": None,
            "stale": bool(stale_reasons & {"basis_stale", "basis_unverifiable"}),
            "reasons": sorted(stale_reasons) or ["missing"]}


def _delivery_decision_state(store: Store, document: dict, targets: dict) -> dict:
    """Delivery acceptance is a business decision: an accepted delivery_acceptance
    decision, or an effective authorization that already binds the delivery
    process/artifact (``delivery_binding`` ≠ none, CONTRACTS §3.2 — such a
    delegation means "deliver once these requirements are met", not "click
    approve again")."""
    state = _decision_topic_covered(store, document, "delivery_acceptance", targets)
    if state["satisfied"]:
        return state
    for ref, record in _authorization_heads(store, document):
        if (record.get("delivery_binding") or "none") == "none":
            continue
        if dependency_slices.authorization_effectiveness(store, document, ref)["effective"] \
                and _covers(store, record.get("scope"), targets):
            return {"satisfied": True, "via": "delivery_authorization", "ref": ref,
                    "assurance": (record.get("evidence") or {}).get("assurance"),
                    "reasons": []}
    return state


def _covers(store: Store, scope: dict | None, targets: dict | None) -> bool:
    """Whether ``scope`` covers the target pages/layers (an empty page set is
    never all pages; an unfixed planner scope only covers planner targets)."""
    scope = scope or {}
    targets = targets or {}
    wanted_pages = target_page_ids(store, targets)
    if wanted_pages:
        allowed = scope_page_ids(store, scope)
        if allowed is None or not set(wanted_pages) <= set(allowed):
            return False
    for flag in ("allow_page_membership_change", "allow_page_order_change"):
        if targets.get(flag) and not scope.get(flag):
            return False
    wanted_layers = set(targets.get("layers") or [])
    if wanted_layers and not wanted_layers <= set(scope.get("layers") or []):
        return False
    if targets.get("subject") and scope.get("subject") != "deck" \
            and targets["subject"] != scope.get("subject"):
        return False
    return True


def _page_coverage_from_binding(store: Store, request: dict, wanted: dict, task,
                                control: dict | None = None) -> bool:
    """Whether a deck request's planner scope already covers the page target.

    A deck request carries no fixed page set until a plan exists
    (``page_ids=[]`` with no manifest never means "all pages", CONTRACTS §2.1).
    The adopted plan is the frozen projection of that page manifest (§2.1), so
    a target wholly inside the current plan's page set is covered by the
    request's own production intent — including at dispatch time, before the
    task exists. A bound task materialises the same set (§3.4), and the
    plan-creating phase (``page_copy``) fixes the set with its own accepted
    result under the §11.5 atomic swap. Layers must still sit inside the
    request scope, and anything outside the frozen set stays refused.
    """
    scope = request.get("scope") or {}
    if scope_page_ids(store, scope) is not None:
        return False  # a fixed request page set is authoritative on its own
    wanted_layers = set(wanted.get("layers") or [])
    if not wanted_layers <= set(scope.get("layers") or []):
        return False
    wanted_pages = target_page_ids(store, wanted)
    if not wanted_pages:
        return False
    plan_ref = (control or {}).get("content_plan")
    if plan_ref:
        try:
            plan = store.read_object_json(plan_ref)
        except StoreError:
            plan = None
        if isinstance(plan, dict):
            order = [link.get("page_id") for link in (plan.get("page_links") or [])
                     if isinstance(link, dict)]
            if not order:
                order = list((plan.get("input") or {}).get("page_order") or [])
            if order and set(wanted_pages) <= set(order):
                return True
    binding = (task or {}).get("collaboration_binding") or {}
    if not binding or binding.get("request_id") != request.get("request_id"):
        return False
    bound_pages = scope_page_ids(store, binding.get("write_scope"))
    if bound_pages is None:
        # The plan-creating phase writes the page set its own result fixes;
        # every page still validates inside the variant acceptance (§11.5).
        return binding.get("phase") == "page_copy"
    return set(wanted_pages) <= set(bound_pages)


def _effective_targets(spec: ActionSpec, targets: dict) -> dict:
    """The concrete target the action must be covered for: the caller's explicit
    targets, plus the action's own declared layers when the caller names none
    (a local compile still needs the request to include the output layer —
    CONTRACTS §6.2 '无外部费用也不代表可越过请求范围').

    The subject axis is never derived: it is a caller statement about the
    object boundary (deck vs pages), not an action property.
    """
    wanted = dict(targets or {})
    if not wanted.get("layers") and spec.layers:
        wanted["layers"] = list(spec.layers)
    return wanted


# Executing one authorized production action necessarily allocates and begins
# its own bounded call slots, so the task's bound authorization also covers
# these slots (CONTRACTS §1.6/§3.2: each external generation needs a bounded
# authorization *and* the existing allowance — from one authority chain).
SLOT_ACTIONS = ("call.begin", "generation.dispatch", "allowance.allocate", "allowance.repair")


def _slot_covered_by_binding(spec: ActionSpec, bound_ref, ref, actions) -> bool:
    """The task's bound authorization also covers its bounded calling slots.

    Limited to actions that really spend a bounded external call
    (``external_calls``); a binding never silently widens authority over any
    other action family.
    """
    return (bound_ref is not None and _same_ref(ref, bound_ref)
            and spec.name in SLOT_ACTIONS and spec.external_calls)


def _fixed_delivery_state(store, artifact, control, selected, ref, record):
    """A fixed old file may retain delivery permission, never production scope."""
    fixed = (record.get('constraints') or {}).get('fixed_delivery') or {}
    request = _request(artifact) or {}
    if (record.get('delivery_binding') != 'exact_artifact' or not fixed
            or fixed.get('source_request_id') != request.get('request_id')
            or record.get('request_id') != request.get('request_id')
            or fixed.get('artifact_ref') != (artifact.get('outputs') or {}).get('pptx')
            or fixed.get('subject_ref') != (selected or {}).get('subject_ref')
            or fixed.get('file_sha256') != (selected or {}).get('file_sha256')
            or fixed.get('notes_policy') != (selected or {}).get('notes_policy')
            or models.compute_input_digest(artifact) != models.compute_input_digest(control)
            or artifact.get('narrative') != control.get('narrative')):
        return None
    # Only this read judgement uses the source request. Current auth heads,
    # withdrawals, source rights, user/task facts and policy remain authoritative.
    view = {**artifact, 'task': control['task'], 'sources': control['sources'],
        'policy': control['policy'], 'narrative': control.get('narrative'),
        'collaboration': {**control['collaboration'], 'request': {**request, 'closed': False, 'paused': False}}}
    state = dependency_slices.authorization_effectiveness(store, view, ref)
    return {**state, 'fixed_file_only': True}


def _authority_candidates(store: Store, document: dict, spec: ActionSpec,
                          targets: dict, task: dict | None = None, *, artifact=None, selected_output=None) -> list[dict]:
    candidates = []
    # Only pure proposal permissions share these names. They never cover a
    # trial, dispatch, change commit, allowance, or candidate adoption.
    planning_names = {
        "design.feasibility": ("design.feasibility", "design.propose", "style.propose"),
        "design.propose": ("design.propose", "style.propose"),
        "style.propose": ("style.propose", "design.propose"),
    }
    accepted_names = DELIVERY_ENTRY_ACTIONS if spec.delivery else planning_names.get(spec.name, (spec.name,))
    bound_ref = binding_of(task).get("authorization_ref") if task is not None else None
    for ref, record in _authorization_heads(store, document):
        actions = record.get("actions") or []
        slot_covered = _slot_covered_by_binding(spec, bound_ref, ref, actions)
        if not (any(name in actions for name in accepted_names)
                or _family_match(spec.name, actions)
                or slot_covered):
            continue
        if slot_covered and spec.name not in actions \
                and not any(name in actions for name in accepted_names):
            # A bound slot is a *call* slot; the same authorization must still
            # name a production action so a call cannot ride on an authorization
            # that only exists to be shared.
            if not any(record_name in actions for record_name in
                       ("dispatch.blueprint", "dispatch.compose", "style.trial",
                        "style.expand", "change.commit", "content.operation",
                        "page.edit", "dispatch.host_task")):
                continue
        state = dependency_slices.authorization_effectiveness(store, document, ref)
        if spec.delivery and artifact is not None:
            fixed_state = _fixed_delivery_state(store, artifact, document, selected_output, ref, record)
            if fixed_state is not None:
                state = fixed_state
        candidates.append({
            "ref": ref, "record": record, "effective": state["effective"],
            "reasons": state["reasons"], "assurance": (record.get("evidence") or {}).get("assurance"),
            "covers": _covers(store, record.get("scope"), targets),
            "mode": record.get("mode"), "fixed_file_only": state.get('fixed_file_only', False),
        })
    return candidates


def _rank_authority_candidates(store, document, candidates, spec, *, task=None,
                               count=None, candidate_count=0):
    """Use the same actual budget choice at the gate and Task binding.

    A zero-call planning parent cannot hide its usable execute child. Existing
    Tasks retain their own numeric authority instead of borrowing another grant.
    """
    bound = binding_of(task or {}).get('authorization_ref')
    if bound and spec.external_calls:
        identity = store.read_object_json(bound)['authorization_id']
        candidates = [item for item in candidates if item['record']['authorization_id'] == identity]
    calls = count if isinstance(count, int) and not isinstance(count, bool) else int(spec.external_calls)
    slots = candidate_count if isinstance(candidate_count, int) and not isinstance(candidate_count, bool) else 0

    def priority(item):
        usable = item['effective'] and item['covers'] and (item['mode'] == 'execute' or spec.authority in ('delegate', 'either'))
        assurance_missing = (document.get('collaboration', {}).get('authority_policy') == 'verified_user'
                             and item['assurance'] != 'verified_user')
        fundable = usable
        if usable and calls > 0:
            budget = authorization_budget(store, document, item['ref'])
            fundable = budget['state'] != 'unknown' and budget['remaining'] >= calls
        if usable and slots > 0:
            fundable = fundable and candidate_budget(store, document, item['ref'])['remaining'] >= slots
        return (not usable, assurance_missing, not fundable, item['mode'] != 'execute')

    return sorted(candidates, key=priority)


def covering_authorization_ref(store: Store, document: dict, action: str,
                                targets: dict | None, *, count=None, candidate_count=0) -> dict | None:
    """The effective authorization covering one action's execution.

    The precise Ref a dispatched task carries as its binding's
    ``authorization_ref``: the effective, covering, funded candidate the gate
    itself would choose for this action and target (CONTRACTS §3.2, §6.1.4),
    so revocation and budget attribution follow the grant the work actually
    runs under. Pure; ``None`` when no authorization names the action or covers
    the target — an action that needs no authority stays unbound (F01).
    """
    try:
        spec = action_spec(action)
    except (ModelError, KeyError):
        return None
    candidates = _authority_candidates(store, document, spec, targets or {}, None)
    candidates = _rank_authority_candidates(store, document, candidates, spec,
                                           count=count, candidate_count=candidate_count)
    for candidate in candidates:
        if not candidate["effective"] or not candidate["covers"]:
            continue
        if candidate["mode"] == "execute" or spec.authority in ("delegate", "either"):
            return candidate["ref"]
    return None


def _family_match(action: str, actions) -> bool:
    """A grant may name a family, e.g. ``exports.delivery`` for ``export.delivery``
    or ``changes.commit`` for ``change.commit`` — the same verb namespace with a
    plural segment. The fallback requires both segments to agree, so
    ``style.trial`` never covers ``style.expand``."""
    head, _, leaf = action.partition(".")
    for entry in actions:
        if entry == action:
            return True
        entry_head, _, entry_leaf = str(entry).partition(".")
        if entry_head.rstrip("s") == head.rstrip("s") and entry_leaf == leaf:
            return True
    return False


_INTENT_STOPS = {
    "review_only": ("review_only may record review records but never produce, repair or "
                    "adopt pages (CONTRACTS §5)"),
    "design_trial": ("design_trial stops at bounded sample-page candidates; it never "
                     "produces the full deck (CONTRACTS §5)"),
    "edit": ("an edit request never rebuilds the mainline or the whole deck "
             "(CONTRACTS §5)"),
}


def _intent_allows(spec: ActionSpec, request: dict | None, targets=None) -> str | None:
    """Whether the request's own intent/content_intent reaches this action."""
    if request is None:
        return None
    intent = request.get("intent")
    content_intent = request.get("content_intent")
    if spec.name in _INTENT_BLOCKED_ACTIONS.get(intent, ()):
        return _INTENT_STOPS.get(intent, f"request intent {intent!r} does not reach {spec.name!r}")
    speech_edit = spec.name == "page.edit" and (targets or {}).get("layers") == ["speech"]
    if spec.name in _CONTENT_INTENT_BLOCKED_ACTIONS.get(content_intent, ()) and not speech_edit and not (spec.name == "dispatch.compose" and (targets or {}).get("layers") == ["speech"]):
        return (f"content_intent {content_intent!r} does not reach {spec.name!r}; "
                "the request must say it wants that production")
    return None


def _reconciles_current_inputs(control: dict, task: dict | None, spec: ActionSpec, context=None) -> bool:
    """Whether this action claims the compose.v2 input_revision task that
    answers for the pending reconciliation (external review F05).

    The exemption is exact, never a general waiver: the claimed task must be
    the phased input_revision dispatch, its stamped input digest must equal
    the current inputs, and its binding must name the current request.
    Production that still depends on the old content stays blocked.
    """
    if spec.name == 'import_draft':
        manuscript = (context or {}).get('manuscript_import') or {}
        return (manuscript.get('input_digest') == models.compute_input_digest(control)
            and set(manuscript.get('covered_page_ids') or []) >= {entry['page_id'] for entry in control['pages']}
            and bool(manuscript.get('source_sha256')))
    if spec.name not in ('task.start', 'dispatch.compose') or task is None:
        return False
    if task.get("intent") != "input_revision" \
            or task.get("protocol_version") != "compose.v2":
        return False
    if task.get("input_digest") != models.compute_input_digest(control):
        return False
    request = _request(control)
    binding = binding_of(task)
    if request is None or not binding:
        return False
    return binding.get("request_id") == request.get("request_id")


# ---------------------------------------------------------------------------
# Preproduction content review (AC-R06)


def preproduction_state(store: Store, document: dict) -> dict:
    """The one preproduction content-review verdict, consumed from T03.

    T03's ``content_review`` owns the units, the currency, the reviewer
    identity, the effective failures and the downgrade semantics (CONTRACTS
    §6.3, §11.6); this resolver no longer keeps a second, weaker judgement.
    ``satisfied`` is true only when every required unit is covered by an
    applicable passing review on the current manuscript. An existing delegate
    covering the review topics is reused to arrange that review (AC-R06) — it
    never substitutes the review's result, so it cannot satisfy this state.
    """
    from . import content_review
    try:
        status = content_review.preproduction_status(store, document)
        qualified = content_review.qualify_for_production(store, document)
    except ModelError as exc:
        # Only the strict adopted-generation lineage reader reports this
        # path. A damaged Task must not erase read-only recovery, but asset
        # I/O and current design/permission errors keep their own contracts.
        # Never turn those semantic failures into missing review evidence.
        if exc.path != 'blueprint/provenance/generation_request':
            raise
        # Keep the production resolver strict without repairing or skipping
        # any immutable object or treating the missing proof as a pass.
        state = content_review.requirement_state(store, document)
        units = content_review.required_units(store, document)
        return {'requirement': state['effective'], 'declared_requirement': state['declared'],
            'requirement_origin': state['origin'], 'requirement_reasons': list(state['reasons']),
            'required': bool(document.get('pages')), 'satisfied': False, 'status': 'unreadable',
            'units': list(units), 'satisfied_units': [], 'missing_units': list(units),
            'blocking_findings': [], 'review_refs': [], 'needs_reviewer': False, 'via': None,
            'reasons': [*state['reasons'], 'stored applicability evidence is unreadable; preserve and inspect the original records']}
    state = status["requirement_state"]
    return {"requirement": state["effective"],
            "declared_requirement": state["declared"],
            "requirement_origin": state["origin"],
            "requirement_reasons": list(state["reasons"]),
            "required": status["status"] != "no_manuscript",
            "satisfied": status["status"] == "pass",
            "status": status["status"],
            "units": list(status["units"]),
            "satisfied_units": list(status["satisfied_units"]),
            "missing_units": list(status["missing_units"]),
            "blocking_findings": list(status["blocking_findings"]),
            "review_refs": list(status["review_refs"]),
            "needs_reviewer": bool(qualified["needs_reviewer"]),
            "via": "review" if status["status"] == "pass" else None,
            "reasons": list(state["reasons"])}


# ---------------------------------------------------------------------------
# Delivery policy (one interpretation: delivery_eligibility)


def delivery_control_state(store: Store, artifact_snapshot: dict, control_snapshot: dict, *, selected_output=None) -> dict:
    """The unified delivery judgement for an artifact snapshot read under the
    current control (CONTRACTS §8): the selected artifact supplies pages/output/
    reviews, the current head supplies policy and collaboration control."""
    from . import delivery_eligibility
    merged = {**artifact_snapshot, "policy": control_snapshot.get("policy") or {},
              "reviews": control_snapshot.get("reviews") or []}
    professional = delivery_eligibility.professional_policy(store, merged, selected_output=selected_output)
    return {"professional": professional,
            "output_pptx": (artifact_snapshot.get("outputs") or {}).get("pptx"),
            "artifact_revision_id": artifact_snapshot.get("revision_id"),
            "control_revision_id": control_snapshot.get("revision_id")}


# ---------------------------------------------------------------------------
# The resolver


def evaluate(store: Store, artifact_snapshot: dict | None, control_snapshot: dict | None,
             action: str, context: dict | None = None) -> dict:
    """Pure eligibility judgement for one action (CONTRACTS §6).

    No side effects: nothing is dispatched, written, reserved or advanced.
    ``context`` accepts ``targets`` (page_ids/layers/subject/purpose),
    ``task`` (a dispatched task dict, for binding and budget checks),
    ``persistence`` ("project" | "none") and ``basis`` (extra DependencySlice
    values the caller wants checked).
    """
    spec = action_spec(action)
    control = control_snapshot if control_snapshot is not None else artifact_snapshot
    artifact = artifact_snapshot if artifact_snapshot is not None else control
    context = dict(context or {})
    if control is None:
        raise ModelError("eligibility/control_snapshot", "a control snapshot is required")
    region = _region(control)
    enforced = region is not None and models.writer_at_least(control, "collaboration.v1")
    request = _request(control)
    targets = dict(context.get("targets") or {})
    task = context.get("task")
    reasons: list[dict] = []
    fixed_candidates = (_authority_candidates(store, control, spec, targets, task,
        artifact=artifact, selected_output=context.get('selected_output')) if spec.delivery else [])
    fixed_delivery = any(c['effective'] and c['covers'] and c.get('fixed_file_only') for c in fixed_candidates)

    def block(code, detail, **extra):
        reasons.append({"code": code, "detail": detail, **extra})

    # -- writer boundary ---------------------------------------------------
    legacy_allowed = action in ("create", "continue_project", "migration.describe", "migration.apply",
                                "review.strict", "export.review", "export.engineering",
                                "task.cancel", "call.settle", "readiness.final")
    if not enforced and not legacy_allowed and (spec.production or spec.delivery or spec.writes):
        block("migration_required",
              "this project predates the collaboration writer boundary; "
              "run collaboration migration apply before this action",
              writing=spec.writes)
    if not enforced and context.get("persistence") == "none" and spec.writes:
        block("persistence_none",
              "a strict read-only request never writes to the source project")

    # -- request state -----------------------------------------------------
    if enforced and action not in ROUTING_ACTIONS and action != "restore" and not fixed_delivery:
        if request is None:
            block("decision_needed",
                  "no current work request; start one that names the intended intent, "
                  "scope and evidence before production",
                  missing="work_request")
        else:
            if request.get("closed"):
                block("request_closed",
                      f"the current request is closed ({request.get('closed_reason')}); "
                      "start a new request for new work")
            if request.get("paused") and (spec.production or spec.writes):
                block("request_paused",
                      request.get("pause_reason") or "the current request is paused")
            stop = _intent_allows(spec, request, targets)
            if stop:
                block("scope_exceeded", stop,
                      request_intent=request.get("intent"),
                      content_intent=request.get("content_intent"))

    # -- scope coverage ----------------------------------------------------
    if enforced and request is not None and request.get("scope") and not fixed_delivery:
        wanted = dict(targets or {}) if action in ROUTING_ACTIONS \
            else _effective_targets(spec, targets)
        if (wanted.get("layers") or target_page_ids(store, wanted)) \
                and not _covers(store, request.get("scope"), wanted) \
                and not _page_coverage_from_binding(store, request, wanted, task, control):
            allowed_pages = scope_page_ids(store, request.get("scope"))
            block("scope_exceeded",
                  "the target is outside the current request scope",
                  authorized_pages=allowed_pages,
                  authorized_layers=sorted(request["scope"].get("layers") or []),
                  target_pages=target_page_ids(store, wanted),
                  target_layers=sorted(wanted.get("layers") or []))

    # -- required decisions ------------------------------------------------
    missing_topics = []
    stale_topics = []
    for topic in spec.decision_topics:
        if not enforced:
            continue
        if spec.delivery and not spec.writes:
            # A read-only delivery readiness report *reports* the decision gap;
            # it must not refuse to answer because of it (AC-P02: the same
            # policy result and gaps are returned, not raised).
            continue
        state = ({"satisfied": True, "via": "fixed_file_delivery_authorization"} if fixed_delivery else _delivery_decision_state(store, control, targets)
                 if topic == "delivery_acceptance"
                 else _decision_topic_covered(store, control, topic, targets))
        if not state["satisfied"]:
            missing_topics.append(topic)
            if state.get("stale"):
                stale_topics.append(topic)
    if missing_topics:
        if stale_topics:
            block("basis_stale",
                  "the accepted decisions for these topics no longer match the current "
                  "facts: " + ", ".join(stale_topics),
                  topics=stale_topics, missing="decision")
        else:
            block("decision_needed",
                  "required business decisions are missing or ineffective: "
                  + ", ".join(missing_topics),
                  missing="decision", topics=missing_topics,
                  card={"kind": "decision_card", "topics": missing_topics,
                        "projection": spec.card,
                        "subject_refs": context.get("subject_refs") or [],
                        "scope": (request or {}).get("scope")})

    # -- task binding ------------------------------------------------------
    binding_state = None
    if task is not None and (enforced or region is not None):
        binding_state = task_binding_state(store, control, task)
        if binding_state["status"] == "withdrawn":
            block("authorization_revoked",
                  "the authorization this task bound was withdrawn; the withdrawal stands "
                  "and only settled call facts remain",
                  authorization_id=binding_state.get("authorization_id"))
        elif binding_state["status"] == "invalid":
            block("binding_invalid",
                  "the task's collaboration binding is not valid in the current region",
                  reasons=binding_state["reasons"])
        elif binding_state["status"] == "stale":
            block("binding_stale",
                  "the task binding's digest/basis no longer matches the current document",
                  reasons=binding_state["reasons"])
        elif binding_state["status"] == "absent":
            # A task without a collaboration binding cannot establish *whose*
            # authority it holds, so in a managed project it may never produce
            # or adopt: production/dispatch and every state-writing adoption are
            # refused unconditionally (all task protocols, not just the ones
            # that will write a binding), while already-started call facts may
            # still settle. This is the independent backstop the card requires
            # until every dispatch path stamps a binding (T03).
            #
            # A record-only acceptance — an observation task's result that
            # carries review records and no page/artifact/content write — records
            # what was reviewed about artifacts that already exist, so it stays a
            # fact channel like settlement. Anything that would write production
            # state, and any production task, is refused (the caller computes
            # record_only from the envelope *and* the task kind). Note the
            # asymmetry this leaves today: a style_analyze result carries a
            # `style_analysis` envelope, which is not classified as record-only,
            # so its acceptance stays refused in managed projects until the
            # design flow (T05) gives that envelope its own fact-channel judgement.
            record_only = (spec.name == "task.accept" and context.get("record_only"))
            if (spec.production or spec.group == "adoption") and not record_only:
                block("decision_needed",
                      "this task carries no collaboration binding, so the authority behind it "
                      "cannot be established; only already-started call facts may settle — "
                      "dispatch and adopt through the collaboration-aware path (a bound task)",
                      missing="task_binding")

    # -- authority ---------------------------------------------------------
    authority_assurance = None
    if enforced:
        request_evidence = (request or {}).get("instruction_evidence") or {}
        authority_assurance = request_evidence.get("assurance")
        candidates = []
        if spec.authority in ("execute", "either", "delegate"):
            candidates = fixed_candidates if spec.delivery else _authority_candidates(store, control, spec, targets, task)
            candidates = _rank_authority_candidates(store, control, candidates, spec, task=task,
                count=context.get('count'), candidate_count=context.get('candidate_count', 0))
            usable = [c for c in candidates if c["effective"]
                      and (c["mode"] == "execute" or spec.authority in ("delegate", "either"))]
            covering = [c for c in usable if c["covers"]]
            if not usable:
                revoked = [c for c in candidates
                           if any("revoked" in reason for reason in c["reasons"])]
                if revoked:
                    block("authorization_revoked",
                          "every authorization naming this action is revoked "
                          "(or its parent chain is)",
                          authorization_ids=[c["record"].get("authorization_id") for c in revoked],
                          reasons=sorted({reason for c in candidates for reason in c["reasons"]}))
                else:
                    ineffective = [c for c in candidates if not c["effective"]]
                    if ineffective:
                        stale = [c for c in ineffective if "basis_stale" in c["reasons"]]
                        if stale:
                            block("basis_stale",
                                  "the covering authorization's registered basis changed",
                                  authorization_ids=[c["record"].get("authorization_id") for c in stale])
                        else:
                            block("authority_insufficient",
                                  "the covering authorization is not effective",
                                  reasons=sorted({reason for c in ineffective for reason in c["reasons"]}),
                                  authorization_ids=[c["record"].get("authorization_id") for c in ineffective])
                    else:
                        block("authority_insufficient",
                              f"no authorization names {spec.name!r} within the request scope",
                              action=spec.name)
            elif not covering:
                block("scope_exceeded",
                      f"the authorization naming {spec.name!r} does not cover the target "
                      "pages/layers",
                      authorization_ids=[c["record"].get("authorization_id") for c in usable],
                      target_pages=target_page_ids(store, targets),
                      target_layers=sorted((targets or {}).get("layers") or []))
            else:
                chosen = covering[0]
                authority_assurance = _weakest(
                    authority_assurance, (chosen["record"].get("evidence") or {}).get("assurance"))
        # verified_user policy: no silent downgrade when the channel is absent.
        if region.get("authority_policy") == "verified_user":
            controllers = [c for c in candidates]
            controlling = [c for c in controllers if c["effective"] and c["covers"]]
            if controlling and all(c["assurance"] != "verified_user" for c in controlling):
                block("authority_channel_unavailable",
                      "authority_policy=verified_user needs a verified user event for this "
                      "action; the current records are only host-attested",
                      authorization_ids=[c["record"].get("authorization_id") for c in controlling])
            if request is not None and request_evidence.get("assurance") != "verified_user" \
                    and spec.group in ("execution", "change", "delivery"):
                block("authority_channel_unavailable",
                      "authority_policy=verified_user requires verified user evidence for this "
                      "request; no trusted user-event channel is registered",
                      missing="verified_user_channel")

        # -- budget --------------------------------------------------------
        if spec.external_calls:
            budget = None
            if candidates:
                chosen = next((c for c in candidates if c["effective"] and c["covers"]), candidates[0])
                budget = authorization_budget(store, control, chosen["ref"])
            elif task is not None:
                budget_key = binding_of(task).get("budget_key")
                if budget_key:
                    budget = credit_state(store, control, budget_key, 1)
            credit_budgets = []
            if task is not None:
                key = binding_of(task).get("budget_key")
                auth_ref = binding_of(task).get("authorization_ref")
                fixed = ((store.read_object_json(auth_ref).get("constraints") or {}).get("fixed_budget") or {}) if auth_ref else {}
                if fixed:
                    expected = {item["budget_key"] for item in fixed.get("credits") or []
                                if item["page_id"] in task.get("scope_pages", [])}
                    if len(task.get("scope_pages") or []) != 1 or expected != {key}:
                        block("binding_invalid", "a template-funded image task must bind its exact single-page credit")
                if key:
                    credit_budgets.append(credit_state(store, control, key))
            elif candidates:
                fixed = (chosen["record"].get("constraints") or {}).get("fixed_budget") or {}
                for credit in fixed.get("credits") or []:
                    if credit["page_id"] in (target_page_ids(store, targets or {}) or []):
                        credit_budgets.append(credit_state(store, control, credit["budget_key"]))
            # CONTRACTS §3.3: begin validates its own already-reserved slot; it
            # never needs a second remaining credit for the same slot.
            slot_held = False
            if spec.name in ("call.begin", "generation.dispatch") and task is not None:
                allowance_id = context.get("allowance_id")
                slot_held = any(
                    entry.get("allowance_id") == allowance_id
                    and entry.get("state") in ("reserved", "in_flight")
                    for entry in task.get("call_allowances") or [])
            if not slot_held:
                for credit in credit_budgets:
                    requested = context.get("count", 1) if task is not None else 1
                    if credit["state"] == "exhausted" or (isinstance(requested, int) and requested > credit["remaining"]):
                        block("budget_exhausted", "this page credit is already held or consumed; a repeated grant never refreshes it", budget=credit)
            if budget is not None and not slot_held:
                requested = context.get("count")
                batch_over = (isinstance(requested, int) and not isinstance(requested, bool)
                              and requested > budget["remaining"])
                if budget["state"] == "unknown":
                    block("budget_unknown",
                          "an unsettled external call exists; resolve it before new calls",
                          budget={k: v for k, v in budget.items() if k != "chain_ids"})
                elif batch_over:
                    block("budget_exhausted",
                          f"the request asks for {requested} external calls but only "
                          f"{budget['remaining']} remain on the bound authorization chain; a "
                          "batch request answers to the same ceiling, not just to availability",
                          budget={k: v for k, v in budget.items() if k != "chain_ids"},
                          requested=requested)
                elif budget["state"] == "exhausted":
                    block("budget_exhausted",
                          "no remaining credit for a new external call; an exhausted budget "
                          "only stops new calls (settlement and adoption stay available)",
                          budget={k: v for k, v in budget.items() if k != "chain_ids"})

        # Candidate quotas constrain new trial slots, not acceptance or adoption
        # of a result that already owns its slot. The service derives the count
        # from the actual immutable plan, never from a client quota assertion.
        count = context.get("candidate_count", 0)
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            authority = next((item for item in candidates if item["effective"] and item["covers"]), None)
            if authority:
                candidate_limit = candidate_budget(store, control, authority["ref"])
                if count > candidate_limit["remaining"]:
                    block("budget_exhausted", "the bounded candidate quota has no room for these new trial slots",
                          candidate_budget=candidate_limit, requested=count)

    # -- project stop policy (a separate stop fact: policy.user_stop) -------
    if enforced and spec.external_calls and (control.get("policy") or {}).get("user_stop"):
        block("user_stop",
              "the project stop policy forbids external calls; it is a separate fact from a "
              "request pause and stays until it is explicitly lifted")

    # -- input reconciliation ---------------------------------------------
    if enforced and spec.production and models.input_alignment(control) == "needs_reconciliation":
        if not _reconciles_current_inputs(control, task, spec, context):
            block("input_reconciliation_pending",
                  "inputs changed; reconcile the content against the new inputs first")

    # -- preproduction content review (one T03 verdict for every entry) ----
    preproduction = None
    if enforced and spec.name in PREPRODUCTION_GATED_ACTIONS:
        preproduction = preproduction_state(store, control)
        if not preproduction["satisfied"]:
            code = "needs_reviewer" if preproduction["needs_reviewer"] \
                else "preproduction_blocked"
            detail = {"needs_reviewer": "the required preproduction content review has no "
                                        "acceptable reviewer; a review draft can still be "
                                        "returned, and 'continue' does not waive it",
                      "preproduction_blocked": "the preproduction content review does not "
                                               "pass on the current manuscript; a review "
                                               "draft can still be returned"}[code]
            block(code, detail,
                  requirement=preproduction["requirement"],
                  review_status=preproduction["status"],
                  missing_units=preproduction["missing_units"],
                  open_findings=len(preproduction["blocking_findings"]))

    # -- professional delivery policy (never replaced by the review above) --
    delivery = None
    if spec.delivery:
        if enforced and request is not None and spec.writes:
            request_scope = request.get("scope") or {}
            delivers = request_scope.get("purpose") == "delivery" \
                or request_scope.get("subject") == "deck"
            if not delivers and not any(
                    c["effective"] and c["covers"]
                    and (c["record"].get("delivery_binding") or "none") != "none"
                    for c in candidates):
                block("decision_needed",
                      "delivery needs the request scope purpose=delivery (or a deck-scoped "
                      "request, or an effective delivery authorization)",
                      missing="decision", topics=["delivery_acceptance"],
                      card={"kind": "delivery_card", "projection": spec.card,
                            "topics": ["delivery_acceptance"]})
        if (models.compute_input_digest(artifact) != models.compute_input_digest(control)
                or artifact.get('narrative') != control.get('narrative')):
            block('basis_stale', 'selected output no longer matches current audience/source/argument facts')
        delivery = delivery_control_state(store, artifact or control, control, selected_output=context.get("selected_output"))
        professional = delivery["professional"]
        if professional["required"] and not professional["satisfied"]:
            block("professional_review_required",
                  "delivery requires a verified human professional review of the selected artifact",
                  gap_reasons=professional["gap_reasons"])
        if context.get("expected_output_ref") and delivery["output_pptx"] \
                and context["expected_output_ref"] != delivery["output_pptx"]:
            block("scope_exceeded",
                  "the selected artifact's current output is not the requested output")

    # -- strict read-only --------------------------------------------------
    if context.get("persistence") == "none" and spec.writes:
        block("persistence_none",
              "persistence=none forbids any write to the source project; "
              "a report may only be persisted outside the project")

    # -- assemble ----------------------------------------------------------
    basis = list(context.get("basis") or [])
    if request is not None:
        request_scope = request.get("scope")
    else:
        request_scope = None
    effective_scope = context.get("scope") or request_scope or {"subject": spec.subject,
                                                                "page_ids": [],
                                                                "layers": list(spec.layers)}
    required_artifacts = _required_artifacts(store, control, artifact, spec, targets)
    if spec.name in FACT_ACTIONS:
        # A fact channel records what already happened; nothing here can refuse
        # it (the surrounding state stays visible in the other decision fields).
        reasons = [reason for reason in reasons if reason["code"] == "persistence_none"]
    reasons.sort(key=lambda item: REASON_ORDER.index(item["code"])
                 if item["code"] in REASON_ORDER else len(REASON_ORDER))
    codes = []
    for item in reasons:
        if item["code"] not in codes:
            codes.append(item["code"])
    allowed = not codes
    primary = reasons[0] if reasons else None
    return {
        "schema_version": SCHEMA_VERSION,
        "allowed": allowed,
        "action": spec.name,
        "enforcement": "active",
        "scope": normalize_scope(effective_scope),
        "required_artifact_refs": required_artifacts,
        "required_decision_topics": list(spec.decision_topics),
        "missing_decision_topics": missing_topics,
        "reason_codes": codes,
        "reasons": reasons,
        "responsible_role": spec.role if allowed else _role_for(primary),
        "next_action": None if allowed else _next_action(primary, spec, targets),
        "decision_card_ref_or_projection": None if allowed else _card_for(primary, spec, context),
        "dependency_slices": basis,
        "eligibility_digest": eligibility_digest(spec.name, effective_scope, basis),
        "authority_assurance": authority_assurance,
        "request_id": (request or {}).get("request_id"),
        "artifact_revision_id": (artifact or {}).get("revision_id"),
        "control_revision_id": control.get("revision_id"),
        "facts_only": spec.name in FACT_ACTIONS,
        "binding": binding_state,
        "preproduction": preproduction,
        "delivery": delivery,
        "targets": {"page_ids": target_page_ids(store, targets),
                    "layers": sorted(targets.get("layers") or []),
                    "subject": targets.get("subject")},
    }


def _weakest(*assurances) -> str | None:
    from .collaboration_scope import ASSURANCE_RANK
    values = [a for a in assurances if a]
    if not values:
        return None
    return min(values, key=lambda value: ASSURANCE_RANK.get(value, -1))


def _role_for(primary: dict | None) -> str:
    if primary is None:
        return "runtime"
    return {
        "decision_needed": "user",
        "request_closed": "user",
        "request_paused": "user",
        "scope_exceeded": "user",
        "authorization_revoked": "user",
        "authority_insufficient": "user",
        "authority_channel_unavailable": "user",
        "basis_stale": "user",
        "budget_exhausted": "user",
        "user_stop": "user",
        "budget_unknown": "host",
        "needs_reviewer": "reviewer",
        "professional_review_required": "user",
        "input_reconciliation_pending": "host",
        "migration_required": "operator",
        "binding_invalid": "runtime",
        "binding_stale": "runtime",
        "persistence_none": "runtime",
    }.get(primary["code"], "user")


def _next_action(primary: dict | None, spec: ActionSpec, targets: dict) -> str | None:
    if primary is None:
        return None
    pages = sorted(targets.get("page_ids") or [])
    where = f" for pages {pages}" if pages else ""
    code = primary["code"]
    if code == "decision_needed":
        topics = primary.get("topics")
        if topics:
            return (f"record an accepted decision (or an effective delegate) for "
                    f"{', '.join(topics)}{where}, then retry {spec.name}")
        if primary.get("missing") == "task_binding":
            return ("re-dispatch this work as a bound task through the collaboration-aware path; "
                    "the already-started calls may still settle, but this task cannot "
                    f"{spec.name}{where}")
        return f"start the work request that authorizes {spec.name}{where}, then retry"
    if code == "scope_exceeded":
        return (f"narrow the action to the authorized pages/layers, or get an explicit "
                f"scope/grant covering {sorted(targets.get('page_ids') or []) or 'the target'}")
    if code == "request_paused":
        return "resume the request explicitly (resume never widens scope) or cancel it"
    if code == "request_closed":
        return "start a new work request for the new work"
    if code == "authority_insufficient":
        return f"grant an execute authorization naming {spec.name!r} within the request scope{where}"
    if code == "authorization_revoked":
        return "the withdrawal stands; a new authorization requires a new explicit user instruction"
    if code == "authority_channel_unavailable":
        return ("provide a trusted user-event channel for verified_user, or record an explicit "
                "policy change; the runtime never downgrades this automatically")
    if code == "basis_stale":
        return "re-record the decision/authorization against the current facts, or keep the narrower scope"
    if code == "user_stop":
        return ("lift the project stop policy explicitly (or record why it should stay) before "
                "any external call; the request itself may still be resumed")
    if code == "budget_exhausted":
        return ("the exhausted budget only blocks new calls; settle/accept the last legal result, "
                "or obtain an explicit increase")
    if code == "budget_unknown":
        return "settle the unknown call first (verify success or failure; never auto-retry)"
    if code == "needs_reviewer":
        return ("dispatch the independent preproduction review (or an explicit host_self downgrade "
                "decision) — the manuscript/review draft stays available meanwhile")
    if code == "preproduction_blocked":
        if primary.get("review_status") == "no_manuscript":
            return ("write the candidate manuscript first; the preproduction review answers "
                    "for real pages, not for an empty deck")
        if primary.get("review_status") == "blocked":
            return ("resolve the open preproduction review findings on the current manuscript "
                    "before production; a review draft stays available meanwhile")
        return (f"complete the missing preproduction review units "
                f"{primary.get('missing_units') or []} on the current manuscript; a review "
                "draft stays available meanwhile")
    if code == "professional_review_required":
        return ("arrange a verified human professional review of the exact selected PPTX; "
                "an independent model or host self-review never satisfies it")
    if code == "input_reconciliation_pending":
        return "read the new inputs and reconcile the affected pages before production"
    if code == "migration_required":
        return ("run collaboration migration describe/apply, then start the request that covers "
                "this action")
    if code == "binding_invalid":
        return "re-dispatch the task under the current request; only settled call facts remain"
    if code == "binding_stale":
        return "re-dispatch the task with a recomputed binding; do not accept this result"
    if code == "persistence_none":
        return "write the report outside the project; import it later as an explicit separate operation"
    return None


def _card_for(primary: dict | None, spec: ActionSpec, context: dict) -> dict | None:
    """The projection the caller shows the responsible role. A blocking answer
    always carries the concrete gap; it is never a bare "please confirm"
    (CONTRACTS §6)."""
    if primary is None:
        return None
    code = primary["code"]
    if code == "decision_needed":
        return primary.get("card") or {"kind": "decision_card",
                                       "topics": list(spec.decision_topics),
                                       "projection": spec.card,
                                       "subject_refs": context.get("subject_refs") or []}
    if code in ("authority_insufficient", "authorization_revoked",
                "authority_channel_unavailable"):
        return {"kind": "authorization_card", "action": spec.name,
                "required_actions": [spec.name], "projection": spec.card,
                "reason": code, "detail": primary.get("detail")}
    if code == "scope_exceeded":
        return {"kind": "scope_card", "action": spec.name,
                "authorized_pages": primary.get("authorized_pages"),
                "target_pages": primary.get("target_pages"),
                "authorized_layers": primary.get("authorized_layers"),
                "target_layers": primary.get("target_layers"),
                "projection": spec.card}
    if code == "needs_reviewer":
        return {"kind": "review_card", "action": spec.name,
                "requirement": primary.get("requirement"),
                "review_draft_still_available": True}
    if code in ("budget_exhausted", "budget_unknown"):
        return {"kind": "budget_card", "action": spec.name, "budget": primary.get("budget")}
    if code == "professional_review_required":
        return {"kind": "professional_review_card", "action": spec.name,
                "gap_reasons": primary.get("gap_reasons")}
    if code == "request_paused":
        return {"kind": "stop_card", "action": spec.name, "state": "paused"}
    if code == "user_stop":
        return {"kind": "stop_card", "action": spec.name, "state": "user_stop"}
    return None


def _required_artifacts(store: Store, control: dict, artifact: dict, spec: ActionSpec,
                        targets: dict) -> list[dict]:
    refs: list[dict] = []
    if spec.delivery:
        pptx = (artifact.get("outputs") or {}).get("pptx")
        if pptx:
            refs.append(pptx)
    wanted = target_page_ids(store, targets) or []
    for entry in control.get("pages") or []:
        if wanted and entry.get("page_id") not in wanted:
            continue
        if entry.get("page"):
            refs.append(entry["page"])
    return refs


# ---------------------------------------------------------------------------
# Enforcement adapter


class EligibilityBlocked(operations.OperationError):
    """A recoverable admission gap (CONTRACTS §12: CLI exit 4, HTTP 409).

    ``error_code`` is the primary reason code so callers and tests assert on the
    same vocabulary the resolver reports; the response carries the concrete
    artifact/decision/scope gap, the responsible role and the next action.
    """

    def __init__(self, decision: dict) -> None:
        primary = (decision.get("reasons") or [{}])[0]
        self.decision = decision
        code = decision["reason_codes"][0] if decision["reason_codes"] else "eligibility_blocked"
        message = primary.get("detail") or "action is not eligible"
        super().__init__(code, f"eligibility/{decision['action']}", message,
                         exit_code=4, http_status=409, operation_state="blocked")

    def payload(self) -> dict:
        base = super().payload()
        base["error"].update({
            "action": self.decision["action"],
            "enforcement": self.decision["enforcement"],
            "reason_codes": self.decision["reason_codes"],
            "reasons": self.decision["reasons"],
            "responsible_role": self.decision.get("responsible_role"),
            "next_action": self.decision.get("next_action") or base["error"]["next_action"],
            "decision_card": self.decision.get("decision_card_ref_or_projection"),
            "required_artifact_refs": self.decision.get("required_artifact_refs"),
        })
        return base


def guard(store: Store, document: dict, action: str, *, context: dict | None = None) -> dict:
    """Consume one active decision; historical readers/fact settlement remain legal.

    Every new business write, including legacy-project production, is refused
    when ineligible. Routing returns the same named gap without dispatching.
    Restore recovers facts under scope while preserving current stop/control.
    """
    decision = evaluate(store, document, document, action, context)
    if not decision["allowed"] and (
            "migration_required" in decision["reason_codes"]
            or "persistence_none" in decision["reason_codes"]
            or decision["action"] not in ROUTING_ACTIONS):
        raise EligibilityBlocked(decision)
    return decision


def describe(project, action: str, *, targets: dict | None = None, revision: str | None = None,
             context: dict | None = None) -> dict:
    """Read-only eligibility entry (CONTRACTS §9/§12): ``artifact_revision`` may
    be a historical revision while control stays the current head. Creates no
    task, receipt or allowance."""
    from pathlib import Path
    store = Store(Path(project).expanduser())
    control = store.load_document()
    artifact = store.load_document(revision) if revision else control
    payload = dict(context or {})
    if targets is not None:
        payload["targets"] = targets
    decision = evaluate(store, artifact, control, action, payload)
    decision["selected_revision_id"] = artifact.get("revision_id")
    return decision
