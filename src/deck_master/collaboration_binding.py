"""Collaboration binding construction for newly dispatched tasks
(content collaboration v1.2 CONTRACTS §5, §6.3, §7).

Every task dispatched into a ``collaboration.v1`` project carries a
``collaboration_binding``: which work request it belongs to, which production
phase it executes, who executes it, the exact write scope, the adoption policy,
and the eligibility basis with a canonical digest. The Runtime derives the
binding — a Host never submits one, and a Host cannot skip a required decision
by claiming there is none.

Digest formula (fixed, shared with T04's eligibility resolver):

    eligibility_digest = sha256_bytes(canonical_json_bytes({
        "phase": <phase>,
        "write_scope": <canonical scope JSON>,
        "basis": [<slice sha256> for slices ordered by dependency_slices.slice_key],
    }))

The canonical scope sorts every set-valued field (``page_ids``, ``layers``, …)
and serializes Ref/object fields through the shared canonical encoding
(``models.canonical_json_bytes``: sorted keys, UTF-8, NaN forbidden), so two
bindings with the same meaning hash identically while display names, time
stamps and task claim state never enter the digest.
"""
from __future__ import annotations

from . import dependency_slices, models
from .collaboration_scope import delegation_gaps, scope_gaps
from .models import ModelError, canonical_json_bytes, sha256_bytes

PHASES = ("framing", "argument", "page_copy", "speech", "design", "production",
          "review", "delivery")
EXECUTOR_TYPES = ("runtime", "host", "external_reviewer")
ADOPTION_POLICIES = ("proposal_only", "candidate_only", "within_scope")

# Required decision topics per phase (CONTRACTS §5 table + §6.3 exit conditions).
# The Runtime derives these; a task cannot declare them away. Deep-water entry
# enforcement for every write path is T04's card — this derivation is the
# content-phase subset that dispatch actually needs.
PHASE_DECISION_TOPICS = {
    "framing": (),
    "argument": ("direction",),
    "page_copy": ("direction",),
    "speech": ("speech",),
    "design": ("direction",),
    "production": ("direction",),
    "review": (),
    "delivery": ("delivery_acceptance",),
}
EXTERNAL_PHASES = ("production",)
_AUTHORIZED_PHASES = ("production", "delivery")

_SCOPE_KEYS = ("subject", "page_ids", "page_manifest_ref", "external_artifact_ref",
               "layers", "allow_page_membership_change", "allow_page_order_change", "purpose")
_SET_FIELDS = ("page_ids", "layers")


def canonical_scope(scope: dict | None) -> dict:
    """A canonical rendering of one Scope for hashing and comparison.

    Set-valued fields are sorted; Ref/object fields are kept as plain objects so
    the outer canonical encoding serializes them deterministically.
    """
    scope = scope or {}
    rendered = {}
    for key in _SCOPE_KEYS:
        value = scope.get(key)
        if key in _SET_FIELDS:
            rendered[key] = sorted(value or [])
        elif key in ("page_manifest_ref", "external_artifact_ref"):
            rendered[key] = None if value is None else {
                "path": value.get("path"), "sha256": value.get("sha256")}
        else:
            rendered[key] = value
    return rendered


def eligibility_digest(*, phase: str, write_scope: dict, basis) -> str:
    """The fixed digest formula documented in this module's docstring."""
    ordered = sorted(basis or [], key=dependency_slices.slice_key)
    payload = {"phase": phase,
               "write_scope": canonical_scope(write_scope),
               "basis": [item.get("sha256") for item in ordered]}
    return sha256_bytes(canonical_json_bytes(payload))


def binding_basis(store, document, *, phase: str, provided=None, page_ids=None) -> list[dict]:
    """Registered minimum slices for the phase, plus the current pointers.

    ``merge_required_basis`` completes the registered minimum so a caller can
    never omit a required dependency; the Narrative/Plan slices are added only
    when those pointers exist, because an absent pointer is a real state, not a
    missing registration.
    """
    basis = dependency_slices.merge_required_basis(
        store, document, family="task", key=phase, provided=list(provided or []))
    for identity in ("narrative", "content_plan"):
        if identity == "content_plan" and phase in ("design", "production") and page_ids:
            for page_id in page_ids:
                basis.append(dependency_slices.make_dependency_slice(
                    store, document, kind="artifact", identity=f"page:{page_id}", projection="visual_input"))
                if document.get("content_plan"):
                    basis.append(dependency_slices.make_dependency_slice(
                        store, document, kind="artifact", identity=f"plan:{page_id}", projection="visual_role"))
            continue
        probe = dependency_slices.build_slice(store, document, kind="artifact",
                                              identity=identity, projection="content")
        if probe is None:
            continue
        key = f"artifact:{identity}:content"
        if not any(dependency_slices.slice_key(item) == key for item in basis):
            basis.append({"kind": "artifact", "identity": identity, "projection": "content",
                          "ref": probe["ref"], "sha256": probe["sha256"]})
    return basis


def build_binding(store, document, *, phase: str, executor_type: str, write_scope: dict,
                  adoption_policy: str, request: dict | None = None,
                  authorization_ref: dict | None = None, decision_refs=(),
                  basis=None) -> dict:
    """Build the full binding dict for one dispatched task.

    ``request_id`` always comes from the *current* request; the binding cannot
    name a superseded request. Registered minimum slices are completed here so a
    dispatcher cannot omit a dependency.
    """
    if phase not in PHASES:
        raise ModelError("task/collaboration_binding/phase", f"unregistered phase {phase!r}")
    if executor_type not in EXECUTOR_TYPES:
        raise ModelError("task/collaboration_binding/executor_type",
                         f"executor_type must be one of {EXECUTOR_TYPES}")
    if adoption_policy not in ADOPTION_POLICIES:
        raise ModelError("task/collaboration_binding/adoption_policy",
                         f"adoption_policy must be one of {ADOPTION_POLICIES}")
    region = document.get("collaboration") or {}
    current = request if request is not None else region.get("request")
    if current is None or current.get("closed"):
        raise ModelError("task/collaboration_binding/request_id",
                         "a collaboration.v1 task needs the current open work request")
    scope = canonical_scope(write_scope)
    resolved_basis = binding_basis(store, document, phase=phase, provided=basis,
                                   page_ids=scope.get("page_ids"))
    binding = {
        "request_id": current["request_id"],
        "phase": phase,
        "executor_type": executor_type,
        "authorization_ref": authorization_ref,
        "decision_refs": list(decision_refs or []),
        "write_scope": scope,
        "adoption_policy": adoption_policy,
        "eligibility_basis": resolved_basis,
        "eligibility_digest": eligibility_digest(phase=phase, write_scope=scope,
                                                 basis=resolved_basis),
    }
    return binding


def binding_errors(document, task) -> list[str]:
    """Non-raising binding check: every structural problem, in report order."""
    problems: list[str] = []
    binding = task.get("collaboration_binding")
    if not binding:
        return ["task/collaboration_binding: missing"]
    if binding.get("phase") not in PHASES:
        problems.append(f"task/collaboration_binding/phase: unregistered {binding.get('phase')!r}")
    if binding.get("executor_type") not in EXECUTOR_TYPES:
        problems.append("task/collaboration_binding/executor_type: unregistered")
    if binding.get("adoption_policy") not in ADOPTION_POLICIES:
        problems.append("task/collaboration_binding/adoption_policy: unregistered")
    scope = binding.get("write_scope")
    if not isinstance(scope, dict):
        problems.append("task/collaboration_binding/write_scope: must be an object")
    else:
        if len(set(scope.get("page_ids") or [])) != len(scope.get("page_ids") or []):
            problems.append("task/collaboration_binding/write_scope/page_ids: duplicates")
        if len(set(scope.get("layers") or [])) != len(scope.get("layers") or []):
            problems.append("task/collaboration_binding/write_scope/layers: duplicates")
        expected = eligibility_digest(phase=binding.get("phase"), write_scope=scope,
                                      basis=binding.get("eligibility_basis") or [])
        if binding.get("eligibility_digest") != expected:
            problems.append("task/collaboration_binding/eligibility_digest: does not match the basis")
    try:
        models.require_task_binding(document, task)
    except ModelError as exc:
        problems.append(f"{exc.path}: {exc.detail}")
    return problems


def require_binding(document, task) -> None:
    """Gate helper: the binding must be complete and current for this Document."""
    problems = binding_errors(document, task)
    if problems:
        raise ModelError("task/collaboration_binding", "; ".join(problems))


def phase_decision_topics(phase: str, *, speech_mode: str | None = None) -> tuple[str, ...]:
    """Decision topics a phase requires; speech only needs one for verbatim."""
    if phase not in PHASES:
        raise ModelError("task/collaboration_binding/phase", f"unregistered phase {phase!r}")
    if phase == "speech" and speech_mode != "verbatim":
        return ()
    return PHASE_DECISION_TOPICS.get(phase, ())


def decision_refs_for(store, document, topics) -> list[dict]:
    """Refs of accepted, still-effective decisions covering any of ``topics``."""
    region = document.get("collaboration") or {}
    refs = []
    for ref in region.get("decisions") or []:
        try:
            record = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unreadable records cannot satisfy anything
            continue
        if (record.get("topic") in topics and record.get("disposition") == "accepted"
                and dependency_slices.accepted_decision(store, document, ref)):
            refs.append(ref)
    return refs


def _effective_delegates(store, document, topics) -> list[dict]:
    """Effective delegate authorizations whose topics cover this phase."""
    region = document.get("collaboration") or {}
    found = []
    for ref in region.get("authorizations") or []:
        try:
            record = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if record.get("mode") != "delegate" or record.get("status") != "active":
            continue
        if topics and not set(topics) <= set(record.get("delegated_topics") or []):
            continue
        state = dependency_slices.authorization_effectiveness(store, document, ref)
        if state["effective"]:
            found.append(ref)
    return found


def derive_requirements(store, document, *, phase: str, speech_mode: str | None = None,
                        write_scope: dict | None = None) -> dict:
    """What this phase needs before it may proceed (CONTRACTS §5, §6.3).

    Runtime-side derivation: a Host cannot bypass a required decision by
    submitting ``none``. Returns the required topics, whether an execution
    authorization is needed, and the concrete gaps found against the current
    control state. This is the content-phase subset; T04 owns the unified
    eligibility resolver that every entry point consumes.
    """
    if phase not in PHASES:
        raise ModelError("eligibility/phase", f"unregistered phase {phase!r}")
    topics = list(PHASE_DECISION_TOPICS.get(phase, ()))
    if phase == "speech" and speech_mode != "verbatim":
        # CONTRACTS §1.7/§10.1: only verbatim needs an explicit request or an
        # already-effective delegation; cues are the live default.
        topics = []
    required_decisions = list(topics)
    satisfied_decisions = decision_refs_for(store, document, topics)
    delegate_refs = _effective_delegates(store, document, topics)
    gaps: list[str] = []
    for topic in required_decisions:
        if satisfied_decisions:
            break
        if delegate_refs:
            break
        gaps.append(f"decision_needed:{topic}")
    requires_authorization = phase in _AUTHORIZED_PHASES or phase in EXTERNAL_PHASES
    authorization_ref = None
    if requires_authorization:
        candidates = [ref for ref in _effective_executes(store, document, phase)]
        if candidates:
            authorization_ref = candidates[0]
        else:
            gaps.append("authorization_needed")
    reason_codes = []
    for gap in gaps:
        reason_codes.append("decision_needed" if gap.startswith("decision_needed")
                            else "authority_insufficient")
    return {
        "phase": phase,
        "required_decision_topics": required_decisions,
        "requires_authorization": requires_authorization,
        "requires_external_calls": phase in EXTERNAL_PHASES,
        "satisfied_decisions": satisfied_decisions,
        "covering_delegations": delegate_refs,
        "authorization_ref": authorization_ref,
        "gaps": gaps,
        "reason_codes": sorted(set(reason_codes)),
        "allowed": not gaps,
        "scope_containment": None if not write_scope else (
            "within_parent" if not scope_gaps(store, write_scope, write_scope) else "unknown"),
    }


def _effective_executes(store, document, phase: str) -> list[dict]:
    region = document.get("collaboration") or {}
    found = []
    for ref in region.get("authorizations") or []:
        try:
            record = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if record.get("mode") != "execute" or record.get("status") != "active":
            continue
        if phase in EXTERNAL_PHASES and not (record.get("max_external_calls") or 0) > 0:
            continue
        state = dependency_slices.authorization_effectiveness(store, document, ref)
        if state["effective"]:
            found.append(ref)
    return found


def containment_gaps(store, parent, child) -> list[str]:
    """Expose the shared scope-containment rule for binding-time checks."""
    return scope_gaps(store, parent, child)


def delegation_containment(store, parent, child) -> list[str]:
    """Expose the shared delegation-containment rule (topics, budget, evidence)."""
    return delegation_gaps(store, parent, child)


def stamp_task(store, document, task: dict, *, phase: str, executor_type: str = "host",
               write_scope: dict | None = None, adoption_policy: str = "within_scope",
               authorization_ref: dict | None = None, decision_refs=(),
               page_ids=None, action: str | None = None,
               action_targets: dict | None = None) -> dict:
    """Attach the binding to a task about to be dispatched.

    ``action`` names the service action this task executes under. When the
    caller does not pass an explicit ``authorization_ref``, the covering
    effective authorization for that action (and ``action_targets``, or the
    built write scope) is resolved and bound, so revocation and budget
    attribution follow the grant the work actually runs under (F01). An action
    no authorization names stays unbound — a checked grant at dispatch time
    never fabricates authority into the task.

    Projects below the collaboration.v1 writer keep their exact old behavior:
    no binding, no gate, byte-identical dispatch.
    """
    if not models.collaboration_required(document):
        return task
    if task.get("collaboration_binding"):
        require_binding(document, task)
        return task
    from .content_production import write_scope_for
    scope = write_scope or write_scope_for(store, document, phase, page_ids=page_ids)
    if authorization_ref is None and action:
        from . import eligibility
        targets = action_targets or {"page_ids": scope.get("page_ids") or [],
                                     "layers": scope.get("layers") or []}
        authorization_ref = eligibility.covering_authorization_ref(store, document, action,
                                                                    targets)
    binding = build_binding(store, document, phase=phase, executor_type=executor_type,
                            write_scope=scope, adoption_policy=adoption_policy,
                            authorization_ref=authorization_ref, decision_refs=decision_refs)
    task["collaboration_binding"] = binding
    task.setdefault("protocol_version", "changes.v1")
    task["required_capabilities"] = list(dict.fromkeys([*task.get("required_capabilities", []), "collaboration.v1", "rc3-entry.v1"]))
    require_binding(document, task)
    return task
