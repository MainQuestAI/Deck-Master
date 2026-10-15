"""Phased content production: compose.v2 dispatch and result acceptance
(content collaboration v1.2 CONTRACTS §5, §6.3, §11.5, §11.7).

compose.v1 stays byte-for-byte the historical protocol: it is only read and
replayed. Every new phased production task is dispatched with
``protocol_version=compose.v2`` and a ``collaboration_binding``, and its result
carries the compose_result.v2 variant envelope.

The variant table is implemented literally: framing never writes Pages, images,
SVG, PPTX or a user Decision; narrative stores proposal Refs only; page_copy
validates every Page, lets the Runtime generate all page_links, and commits
Pages + Plan in one pointer swap; speech writes only notes plus the mapping's
speech segment and rebinds page_links; input_revision declares its changed-layer
mask, refuses out-of-scope differences and never half-writes.

``adoption_policy=proposal_only`` keeps results in ``Task.result_refs``; the
current pointers move only through :func:`adopt_proposal`, which requires an
effective accepted Decision covering the exact write scope.
"""
from __future__ import annotations

import copy
import uuid
from pathlib import Path

from . import dependency_slices, models, tasks as tasks_mod
from .collaboration_scope import scope_gaps
from .content import atom_ids, check_page
from .models import ModelError, bump_revision, collaboration_required
from .store import Store, StoreError

FRAMING = "framing"
ARGUMENT = "argument"
PAGE_COPY = "page_copy"
SPEECH = "speech"
DESIGN = "design"
PRODUCTION = "production"
REVIEW = "review"
DELIVERY = "delivery"

INPUT_REVISION = "input_revision"

# phase -> result variant for compose.v2 (CONTRACTS §11.5). A compose task can
# only submit the variant its phase expects; intent=input_revision selects the
# revision variant regardless of phase.
PHASE_VARIANT = {FRAMING: "framing", ARGUMENT: "narrative",
                 PAGE_COPY: "page_copy", SPEECH: "speech"}
REGISTERED_PHASES = (FRAMING, ARGUMENT, PAGE_COPY, SPEECH, DESIGN, PRODUCTION, REVIEW, DELIVERY)

# Default write scope / adoption policy per phase. A dispatcher may narrow the
# scope, never widen it beyond the registered layers of its phase.
PHASE_SPEC = {
    FRAMING: {"layers": ["narrative"], "purpose": "exploratory",
              "adoption_policy": "proposal_only", "allow_page_membership_change": False},
    ARGUMENT: {"layers": ["narrative", "plan"], "purpose": "working",
               "adoption_policy": "proposal_only", "allow_page_membership_change": False},
    PAGE_COPY: {"layers": ["page_copy", "plan"], "purpose": "working",
                "adoption_policy": "within_scope", "allow_page_membership_change": True},
    SPEECH: {"layers": ["speech"], "purpose": "working",
             "adoption_policy": "within_scope", "allow_page_membership_change": False},
    # Non-content phases: dispatch shapes for design feasibility, local/external
    # production, review records and delivery. Entry-level enforcement for these
    # paths is T04's card; the binding records the exact scope here.
    DESIGN: {"layers": ["design"], "purpose": "exploratory",
             "adoption_policy": "proposal_only", "allow_page_membership_change": False},
    PRODUCTION: {"layers": ["blueprint", "svg", "output"], "purpose": "working",
                 "adoption_policy": "within_scope", "allow_page_membership_change": False},
    REVIEW: {"layers": ["review"], "purpose": "review",
             "adoption_policy": "within_scope", "allow_page_membership_change": False},
    DELIVERY: {"layers": ["output"], "purpose": "delivery",
               "adoption_policy": "within_scope", "allow_page_membership_change": False},
}

# Registered changed-layer names for the input_revision mask.
CHANGED_LAYERS = ("narrative", "plan", "page_copy", "speech")

# Old-envelope slots are never a hidden channel for compose.v2 results.
_FORBIDDEN_V2_SLOTS = ("files", "pages", "page_order", "artifact_specs", "reviews",
                       "content_update", "content_plan", "notes", "generation_result",
                       "style_analysis")

_CAPABILITIES = ["compose.v2", "collaboration.v1", "rc3-entry.v1"]

# Registered adoption projections per proposal schema (models.REGISTERED_PROJECTIONS):
# a decision may only promote the slice it actually names.
_ADOPTION_PROJECTIONS = {
    "narrative.v1": ("direction",),
    "content_plan.v2": ("page_roles", "page_order"),
}


def expected_variant(task: dict) -> str | None:
    """The only compose.v2 variant this task may submit; None for v1 tasks."""
    if task.get("protocol_version") != "compose.v2":
        return None
    if task.get("intent") == "input_revision":
        return INPUT_REVISION
    phase = (task.get("collaboration_binding") or {}).get("phase")
    return PHASE_VARIANT.get(phase)


def parse_compose_v2(raw: dict) -> dict:
    """Schema plus variant-table envelope checks (no variant payload parsing)."""
    models.validate_compose_result_semantics(raw)
    hidden = sorted(slot for slot in _FORBIDDEN_V2_SLOTS if raw.get(slot))
    if hidden:
        raise tasks_mod.EnvelopeError(
            "(result)", f"compose.v2 results submit payload only; legacy slots are not a channel: {hidden}")
    return raw


# ---------------------------------------------------------------------------
# Dispatch


def write_scope_for(store, document: dict, phase: str, *, page_ids=None) -> dict:
    """The phase's default write scope. A scope never widens silently: pages are
    named explicitly, and a deck-level phase binds the current Plan manifest."""
    spec = PHASE_SPEC[phase]
    pages = sorted(page_ids if page_ids is not None
                   else [entry["page_id"] for entry in document.get("pages") or []])
    manifest = None
    plan_ref = document.get("content_plan")
    if plan_ref and phase in (SPEECH, PRODUCTION, DELIVERY):
        try:
            plan = store.read_object_json(plan_ref)
        except Exception:  # noqa: BLE001 - an unreadable plan is simply not a manifest
            plan = None
        if plan and plan.get("schema_version") == "content_plan.v2":
            manifest = plan_ref
    return {
        "subject": "deck",
        "page_ids": pages,
        "page_manifest_ref": manifest,
        "external_artifact_ref": None,
        "layers": list(spec["layers"]),
        "allow_page_membership_change": spec["allow_page_membership_change"],
        "allow_page_order_change": False,
        "purpose": spec["purpose"],
    }


def _phase_instruction(document, phase: str, variant: str, store) -> str:
    if variant == INPUT_REVISION:
        return (
            "输入已更新：读取新的来源与 diff，只提交真正受影响的层。payload 必须给出 changed_layers、"
            "每个变化层的实质 proposal Ref 与 diff（input_digest、summary、changed_page_ids）；"
            "范围外差异会被拒绝，不允许半写成功。"
        )
    if phase == FRAMING:
        return (
            "按材料读出用途、权威与冲突，建立受众变化目标与具体缺口：提交 maturity=framing 的 Narrative "
            "作为提案（payload.narrative）。不得提交完整 Page、图像、SVG 或任何用户决定。"
        )
    if phase == ARGUMENT:
        return (
            "写 argument Narrative：中心节点、连通论证/讲解结构、证据与限定、未决项；可选附 planned "
            "content_plan.v2（payload.plan）。这是提案：不改当前指针，不进入完整页稿或外部生成。"
        )
    if phase == PAGE_COPY:
        return (
            "按已采用的 Narrative 写完整逐页稿：payload.pages 为完整 Page v2（含 content_mapping，"
            "覆盖每个可见 atom 与真实来源 locator），payload.page_order 为完整页序，payload.plan_input "
            "为 content_plan_input.v2。Runtime 会校验全部 Page 后生成全部 page_links 并一次提交。"
        )
    if phase == SPEECH:
        return (
            "只写口播：payload.updates 对固定 Page Ref 提交 speaker_notes 与 speech_segments"
            "（覆盖全部口播文本、标注 estimated_seconds 与 narrative 节点）。不得改上屏正文、页序或视觉配置。"
        )
    return "按 phase 写出本阶段内容产物。"


def open_phase_task(store, document, *, operation_id: str, intent: str = "initial",
                    input_revision_id: str | None = None, phase: str | None = None,
                    adoption_policy: str | None = None, page_ids=None,
                    instruction: str | None = None) -> dict:
    """Dispatch one compose.v2 phase task carrying its collaboration binding.

    This is the real write point for phased content tasks, so it consumes the
    unified gate (CONTRACTS §6.2): `continue`'s phase progression, the guarded
    compose wrapper and every other path that lands here are judged at
    dispatch — a paused or closed request gains no task through a side door
    (external review F06).
    """
    from . import eligibility
    requested_layers = list(PHASE_SPEC[phase or FRAMING]["layers"])
    if intent == "input_revision":
        request_scope = ((document.get("collaboration") or {}).get("request") or {}).get("scope") or {}
        requested_layers = [layer for layer in CHANGED_LAYERS if layer in request_scope.get("layers", [])]
    eligibility.guard(store, document, "dispatch.compose",
                      context={"targets": {"page_ids": sorted(page_ids or []), "layers": requested_layers}})
    task = build_phase_task(store, document, operation_id=operation_id, intent=intent,
                            input_revision_id=input_revision_id, phase=phase,
                            adoption_policy=adoption_policy, page_ids=page_ids,
                            instruction=instruction)
    task_ref = store.put_json_object(task)
    bumped = bump_revision(document, {
        "operation_id": f"dispatch-{uuid.uuid4().hex[:12]}", "kind": "task_update",
        "description": f"compose.v2 {expected_variant(task)} task opened for Host", "read_set": []})
    bumped["tasks"] = list(document.get("tasks") or []) + [task_ref]
    store._commit_locked(
        blobs=[], base_revision=document["revision_id"], document=bumped,
        operation_id=bumped["change"]["operation_id"])
    return task


def build_phase_task(store, document, *, operation_id: str, intent: str = "initial",
                     input_revision_id: str | None = None, phase: str | None = None,
                     adoption_policy: str | None = None, page_ids=None,
                     instruction: str | None = None) -> dict:
    """Build (without committing) one compose.v2 phase task.

    Callers that already own a project transaction — ``inputs_update`` records
    the input revision and its reconciliation task in one commit — use this and
    commit the task themselves; nothing here writes project state.
    """
    from . import collaboration_binding
    if not store.workbench_protocol_required(document):
        raise ModelError("(task)/protocol_version",
                         "compose.v2 requires an explicit workbench.v3 project")
    if intent == "input_revision":
        phase = phase or PAGE_COPY
        variant = INPUT_REVISION
    else:
        phase = phase or FRAMING
        variant = PHASE_VARIANT.get(phase)
        if variant is None:
            raise ModelError("(task)/phase",
                             f"phase {phase!r} has no compose.v2 variant; "
                             f"use one of {sorted(PHASE_VARIANT)}")
    if phase not in REGISTERED_PHASES:
        raise ModelError("(task)/phase", f"unregistered phase {phase!r}")
    spec = PHASE_SPEC.get(phase, {"layers": ["narrative"], "purpose": "exploratory",
                                  "adoption_policy": "proposal_only",
                                  "allow_page_membership_change": False})
    write_scope = write_scope_for(store, document, phase, page_ids=page_ids)
    if intent == "input_revision":
        requested = ((document.get("collaboration") or {}).get("request") or {}).get("scope") or {}
        write_scope["layers"] = [layer for layer in CHANGED_LAYERS if layer in requested.get("layers", [])]
        write_scope["allow_page_membership_change"] = bool(requested.get("allow_page_membership_change"))
        write_scope["allow_page_order_change"] = bool(requested.get("allow_page_order_change"))
    if page_ids is not None and phase == PAGE_COPY:
        # Naming exact pages narrows the scope: that dispatch cannot add pages.
        write_scope = {**write_scope, "allow_page_membership_change": False}
    policy = adoption_policy or spec["adoption_policy"]
    from .method_resources import method_release, method_resources
    methods = method_resources("compose", intent=intent, phase=phase)
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12],
        operation_id=operation_id,
        kind="compose",
        intent=intent,
        input_digest=models.compute_input_digest(document),
        input_revision_id=input_revision_id,
        method_release=method_release(methods) if methods else None,
        scope_pages=sorted(write_scope["page_ids"]),
        instruction=instruction or _phase_instruction(document, phase, variant, store),
        inputs=[],
        dependencies=[{"kind": "content",
                       "identity": f"document-revision:{document['revision_id']}",
                       "sha256": models.content_identity(document)}],
        dispatch_revision=document["revision_id"],
        produced_against=models.content_identity(document),
    )
    task["protocol_version"] = "compose.v2"
    task["required_capabilities"] = list(_CAPABILITIES)
    topics = collaboration_binding.phase_decision_topics(phase)
    binding = collaboration_binding.build_binding(
        store, document, phase=phase, executor_type="host", write_scope=write_scope,
        adoption_policy=policy,
        decision_refs=collaboration_binding.decision_refs_for(store, document, topics))
    task["collaboration_binding"] = binding
    collaboration_binding.require_binding(document, task)
    models.validate_task_semantics(task)
    return task


# ---------------------------------------------------------------------------
# Phase progression and speech policy


def speech_policy(document, *, plan_input=None, explicit_mode=None, explicit_source=None,
                  primary_use=None, job=None) -> dict:
    """The effective speech policy for this production step (CONTRACTS §1.7, §10.1).

    ``presentation_mode`` with source ``default`` is a technical compatibility
    value, never a user request: it may recommend cues but never requires them.
    ``verbatim`` exists only when explicitly requested or already delegated;
    ``read_alone`` defaults to none. ``mixed`` needs a primary use from an
    explicit instruction or an effective delegation — without one this returns
    the read-primary plus cues recommendation and a decision requirement.
    """
    task = document.get("task") or {}
    mode = task.get("presentation_mode") or "live"
    source = task.get("presentation_mode_source") or "default"
    plan_policy = None
    if isinstance(plan_input, dict) and isinstance(plan_input.get("speech_policy"), dict):
        plan_policy = plan_input["speech_policy"]
    if explicit_mode is not None:
        resolved = explicit_mode
        if explicit_source is None:
            explicit_source = "provided"
        return _policy_result(resolved, explicit_source, plan_policy, job, primary_use,
                              requires_decision=False, reason="explicit instruction")
    if plan_policy and plan_policy.get("mode"):
        resolved = plan_policy["mode"]
        if resolved == "verbatim" and plan_policy.get("source") == "default":
            resolved = "cues"
        return _policy_result(resolved, plan_policy.get("source") or "provided", plan_policy, job,
                              primary_use, requires_decision=False, reason="plan speech policy")
    if mode == "read_alone":
        return _policy_result("none", source, plan_policy, job, primary_use,
                              requires_decision=False,
                              reason="read_alone defaults to no new speech")
    if mode == "mixed":
        resolved_primary = primary_use or job_primary_use(job)
        if resolved_primary == "read_alone":
            return _policy_result("none", "provided", plan_policy, job, "read_alone",
                                  requires_decision=False, reason="mixed with read primary use")
        if resolved_primary == "live":
            return _policy_result("cues", "provided", plan_policy, job, "live",
                                  requires_decision=False, reason="mixed with live primary use")
        return {
            "mode": "cues", "output": "pptx_notes", "source": "default",
            "primary_use": None, "required": False, "requires_decision": True,
            "recommendation": {"primary_use": "read_alone", "speech_mode": "cues"},
            "reason": "mixed needs a primary use from an explicit instruction or an effective "
                      "delegation; recommending read-primary with cues instead of choosing",
        }
    if mode == "live":
        required = source == "provided"
        result = _policy_result("cues", source, plan_policy, job, primary_use,
                                requires_decision=False,
                                reason="live defaults to cues" if required
                                else "live is a default compatibility value, not a user request")
        result["required"] = required
        return result
    return _policy_result("none", source, plan_policy, job, primary_use, requires_decision=False,
                          reason=f"unknown presentation mode {mode!r} produces no speech")


def job_primary_use(job) -> str | None:
    return (job or {}).get("primary_use")


def _policy_result(mode, source, plan_policy, job, primary_use, *, requires_decision, reason) -> dict:
    output = (plan_policy or {}).get("output")
    if output is None:
        output = "none" if mode == "none" else "pptx_notes"
    return {
        "mode": mode, "output": output, "source": source,
        "primary_use": primary_use if primary_use is not None else job_primary_use(job),
        "required": mode != "none", "requires_decision": requires_decision,
        "reason": reason,
    }


def _proposals_for_phase(store, document, variant: str) -> dict | None:
    """The current proposal set of one completed compose.v2 phase, if any.

    ``produced_against`` must still equal the current content identity: a
    proposal from superseded inputs is history, not a decision input.
    """
    identity = models.content_identity(document)
    for ref in reversed(list(document.get("tasks") or [])):
        try:
            task = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if (task.get("protocol_version") == "compose.v2" and task.get("status") == "completed"
                and expected_variant(task) == variant and task.get("produced_against") == identity
                and (task.get('collaboration_binding') or {}).get('request_id') ==
                    ((document.get('collaboration') or {}).get('request') or {}).get('request_id')
                and task.get("result_refs")):
            return {"task_id": task["task_id"], "refs": list(task["result_refs"])}
    return None


def _phased_content_active(store, document) -> bool:
    """The phased pipeline runs for fresh production, or once it has been entered.

    A migrated project that already has Pages is never dragged into a new
    Narrative cycle by `continue`; its legacy path stays exactly as it was.
    """
    if not collaboration_required(document):
        return False
    if not document.get("pages"):
        return True
    if document.get('content_plan'):
        plan = store.read_object_json(document['content_plan'])
        if plan.get('schema_version') == 'content_plan.v2' and plan.get('mode') == 'imported_mapping':
            return True
    for ref in document.get("tasks") or []:
        try:
            task = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if task.get("protocol_version") == "compose.v2":
            return True
    return False


def _full_content_phase_status(store, document, *, explicit_speech_mode: str | None = None) -> dict:
    """Which content phase comes next and why (read-only; CONTRACTS §5, §6.3).

    ``explicit_speech_mode`` lets a caller pass an explicit user request (or a
    delegated decision) into the same effective-policy function that acceptance
    uses. This plans content production only: entry-level eligibility
    enforcement for every write path is T04's card; nothing here grants
    production scope.
    """
    if not _phased_content_active(store, document):
        return {"action": "inactive", "phase": None, "reason": "legacy or non-content project"}
    initial_plan = (store.read_object_json(document['content_plan'])
                    if document.get('content_plan') else None)
    if initial_plan and initial_plan.get('mode') == 'imported_mapping':
        models.validate_content_plan_semantics(initial_plan)
        entries = document.get('pages') or []
        if (initial_plan.get('project_id') != document['project_id'] or
                initial_plan['input']['page_order'] != [entry['page_id'] for entry in entries] or
                {link['page_id']: link['page_ref'] for link in initial_plan['page_links']} !=
                {entry['page_id']: entry['page'] for entry in entries}):
            return {'action': 'blocked', 'phase': None, 'reason': 'imported manuscript mapping is stale'}
        kind = effective_speech_kind(store, document, explicit_mode=explicit_speech_mode)
        missing = [entry['page_id'] for entry in entries
                   if not (store.read_object_json(entry['page']).get('speaker_notes') or '').strip()]
        if kind and missing:
            return {'action': 'dispatch', 'phase': SPEECH, 'page_ids': sorted(missing),
                    'speech_kind': kind, 'speech_mode': 'verbatim' if kind == 'verbatim' else 'cues',
                    'reason': 'current imported manuscript needs only its requested speaking notes'}
        return {'action': 'complete', 'phase': None, 'reason': 'imported manuscript retained without new argument'}
    narrative_ref = document.get("narrative")
    narrative = None
    if narrative_ref:
        try:
            narrative = store.read_object_json(narrative_ref)
        except Exception:  # noqa: BLE001
            narrative = None
    if narrative is None or narrative.get("maturity") == "framing":
        proposals = _proposals_for_phase(store, document, "narrative")
        if proposals is not None:
            return {"action": "await_decision", "phase": ARGUMENT, "topic": "direction",
                    "proposal_refs": proposals["refs"], "task_id": proposals["task_id"],
                    "reason": "an argument Narrative proposal exists; adopting it needs an "
                              "accepted direction decision or an effective delegation"}
        if _proposals_for_phase(store, document, "framing") is None:
            return {"action": "dispatch", "phase": FRAMING,
                    "reason": "no framing or argument Narrative exists yet"}
        return {"action": "dispatch", "phase": ARGUMENT,
                "reason": "a framing proposal exists; the argument Narrative is the next phase"}
    plan_ref = document.get("content_plan")
    plan = None
    if plan_ref:
        try:
            plan = store.read_object_json(plan_ref)
        except Exception:  # noqa: BLE001
            plan = None
    bound = bool(plan and plan.get("schema_version") == "content_plan.v2"
                 and plan.get("mode") == "bound" and plan.get("page_links")
                 and (plan.get("narrative_ref") or None) == narrative_ref)
    if not bound:
        proposals = _proposals_for_phase(store, document, "page_copy")
        if proposals is not None:
            return {"action": "await_decision", "phase": PAGE_COPY, "topic": "direction",
                    "proposal_refs": proposals["refs"], "task_id": proposals["task_id"],
                    "reason": "a page-copy proposal exists; adopting it needs a covering decision"}
        return {"action": "dispatch", "phase": PAGE_COPY,
                "reason": "the adopted argument Narrative has no bound page plan yet"}
    kind = effective_speech_kind(store, document, explicit_mode=explicit_speech_mode)
    if kind is not None:
        missing = [entry["page_id"] for entry in document.get("pages") or []
                   if not (store.read_object_json(entry["page"]).get("speaker_notes") or "").strip()]
        if missing:
            return {"action": "dispatch", "phase": SPEECH, "page_ids": sorted(missing),
                    "speech_mode": "verbatim" if kind == "verbatim" else "cues",
                    "speech_kind": kind,
                    "reason": speech_policy(document, plan_input=(plan or {}).get("input"),
                                            explicit_mode=explicit_speech_mode)["reason"]}
    return {"action": "complete", "phase": None, "reason": "content phases are current"}


def content_phase_status(store, document, *, explicit_speech_mode=None):
    """Stop at the current request's actual content responsibility."""
    request = (document.get("collaboration") or {}).get("request") or {}
    intent = request.get("content_intent") if request.get("intent") == "content_only" else None
    if intent == "plan_only":
        proposals = _proposals_for_phase(store, document, "narrative")
        refs = (proposals or {}).get("refs", [])
        planned = any(store.read_object_json(ref).get("schema_version") == "content_plan.v2" for ref in refs)
        if planned or (document.get("narrative") and document.get("content_plan")):
            return {"action": "complete", "phase": None, "proposal_refs": refs,
                    "reason": "requested planning artifacts are available; no page production requested"}
    if intent in ("write_only", "speech_only"):
        entries = document.get("pages") or []
        wanted = set(request.get("scope", {}).get("page_ids") or [])
        selected = [entry for entry in entries if entry["page_id"] in wanted]
        if intent == "speech_only":
            if not selected:
                return {"action": "blocked", "phase": None, "reason": "speech_only requires fixed current Pages"}
            complete = False
            selected_refs = {entry["page"]["sha256"] for entry in selected}
            for ref in document.get("tasks") or []:
                task = store.read_object_json(ref)
                if (task.get("status") == "completed" and expected_variant(task) == "speech"
                        and (task.get("collaboration_binding") or {}).get("request_id") == request.get("request_id")
                        and selected_refs <= {r["sha256"] for r in task.get("result_refs", [])}):
                    complete = True
            if complete:
                return {"action": "complete", "phase": None, "reason": "requested speaking notes and mappings are current"}
            kind = effective_speech_kind(store, document, explicit_mode=explicit_speech_mode) or "cue"
            return {"action": "dispatch", "phase": SPEECH, "page_ids": [e["page_id"] for e in selected],
                    "speech_kind": kind, "reason": "write only the requested speaking notes"}
        if entries and document.get("content_plan"):
            return {"action": "complete", "phase": None, "reason": "requested visible manuscript is available"}
        if not document.get("narrative"):
            return {"action": "blocked", "phase": None, "reason": "write_only needs adopted direction or an imported manuscript"}
        return {"action": "dispatch", "phase": PAGE_COPY, "reason": "write the agreed visible manuscript only"}
    return _full_content_phase_status(store, document, explicit_speech_mode=explicit_speech_mode)


def completion_status(store, document):
    """Pure request-scoped completion; unreadable facts remain explicit gaps."""
    request = (document.get("collaboration") or {}).get("request") or {}
    missing = []
    try:
        phase = content_phase_status(store, document) if request.get("intent") in ("full_deck", "content_only") else {}
    except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
        phase = {"action": "blocked", "reason": f"content facts require recovery: {type(exc).__name__}"}
    action = phase.get("action")
    state = "completed" if action == "complete" and request.get("intent") == "content_only" else (
        "awaiting_decision" if action in ("await_decision", "blocked") else "in_progress")
    for ref in document.get("tasks") or []:
        try:
            task = store.read_object_json(ref)
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            missing.append({"code": "unreadable_task", "ref": ref, "next_action": "recover_task_facts"})
            state = "needs_recovery"
            continue
        if (task.get("status") in ("running", "awaiting_host", "queued")
                and (task.get("collaboration_binding") or {}).get("request_id") == request.get("request_id")
                and state != "needs_recovery"):
            state = "in_progress"
    if models.input_alignment(document) == 'needs_reconciliation':
        state = 'awaiting_decision'
        missing.append({'code': 'input_reconciliation_pending', 'next_action': 'reconcile_current_inputs'})
    refs = ([document["narrative"]] if document.get("narrative") else [])
    refs += ([document["content_plan"]] if document.get("content_plan") else [])
    ids = set((request.get("scope") or {}).get("page_ids") or [])
    refs += [entry["page"] for entry in document.get("pages") or [] if entry["page_id"] in ids]
    refs += phase.get("proposal_refs") or []
    if state == "awaiting_decision":
        missing.append({"code": "content_requirement", "detail": phase.get("reason")})
    return {"state": state, "request_id": request.get("request_id"), "intent": request.get("intent"),
        "content_intent": request.get("content_intent"), "artifact_revision_id": document["revision_id"],
        "effective_scope": request.get("scope"), "outputs": refs,
        "checks": [{"kind": "requested_content", "status": "pass" if state == "completed" else "not_evaluated",
                    "basis": phase.get("reason")}],
        "missing": missing, "responsible_role": "content" if state != "completed" else "caller",
        "next_action": "return_requested_content" if state == "completed" else phase.get("reason")}


def next_phase_task(store, document, *, explicit_speech_mode: str | None = None):
    """Dispatch the next content phase task, or None when none is due."""
    status = content_phase_status(store, document, explicit_speech_mode=explicit_speech_mode)
    if status.get("action") != "dispatch":
        return None
    phase = status["phase"]
    if phase == SPEECH:
        kind = status.get("speech_kind") or ("verbatim" if status.get("speech_mode") == "verbatim"
                                            else "cue")
        pages = sorted(status.get("page_ids") or [])
        task = open_phase_task(store, document, operation_id=f"compose-{uuid.uuid4().hex[:12]}",
                               phase=SPEECH, page_ids=pages,
                               instruction=_speech_instruction(kind, pages))
        _stamp_speech_kind(store, task, kind)
        return task
    return open_phase_task(store, document, operation_id=f"compose-{uuid.uuid4().hex[:12]}",
                           phase=phase)


def _speech_instruction(kind: str, page_ids) -> str:
    segment_policy = (
        "逐字稿的实际口播标 verbatim；停顿、练习等非口播指令保留 cue，不能改标签冒充口播。"
        "每个更新页必须包含实际逐字口播；完整性与估时仍须内容审阅。"
        if kind == "verbatim" else "提示稿的各段标 cue，不扩张为逐字稿。"
    )
    return (
        f"只写口播（{kind}）：对 {sorted(page_ids)} 的固定 Page Ref 提交 speaker_notes 与 speech_segments。"
        "各段连续覆盖全部备注文本、标注 kind 与 estimated_seconds（估计值，不得写成实测）。"
        f"{segment_policy}"
        "不得改上屏正文、页序或视觉配置。"
    )


def _stamp_speech_kind(store, task, kind) -> None:
    """Record the requested speech kind on the task so acceptance can enforce it."""
    stage_request = {"mode": "auto", "stage": "content", "references": [],
                     "speech_kind": kind}
    document = store.load_document()
    latest = tasks_mod._lookup_task(document, task["task_id"], store)
    updated = {**latest, "stage_request": stage_request}
    models.validate_task_semantics(updated)
    ref = store.put_json_object(updated)
    bumped = bump_revision(document, {
        "operation_id": f"speech-kind-{uuid.uuid4().hex[:12]}", "kind": "task_update",
        "description": f"speech phase requested {kind}", "read_set": []})
    tasks_mod._replace_task_in_document(bumped, task, ref, store)
    store._commit_locked(blobs=[], base_revision=document["revision_id"], document=bumped,
                         operation_id=bumped["change"]["operation_id"])
    task["stage_request"] = dict(updated["stage_request"])


# ---------------------------------------------------------------------------
# Acceptance


def accept_compose_v2(store, *, document: dict, task: dict, envelope: dict,
                      produced_against: str, result_digest: str, staged: dict) -> dict:
    """Route one compose.v2 result to its variant acceptor (all-or-nothing)."""
    parse_compose_v2(envelope)
    if envelope.get("task_id") != task.get("task_id"):
        raise tasks_mod.EnvelopeError("(result)/task_id", "result must name the dispatched task")
    if envelope.get("operation_id") != task.get("operation_id"):
        raise tasks_mod.TaskConflict("(result)/operation_id",
                                     "operation_id does not match the dispatched task operation")
    variant = expected_variant(task)
    if variant is None:
        raise tasks_mod.EnvelopeError("(result)/variant",
                                      "this task was not dispatched with a compose.v2 phase")
    if envelope.get("variant") != variant:
        raise tasks_mod.EnvelopeError(
            "(result)/variant",
            f"task phase expects variant {variant!r}; got {envelope.get('variant')!r}")
    binding = task.get("collaboration_binding") or {}
    if envelope.get("eligibility_digest") != binding.get("eligibility_digest"):
        raise tasks_mod.EnvelopeError(
            "(result)/eligibility_digest",
            "the result is not bound to this task's dispatch basis")
    acceptors = {"framing": _accept_framing, "narrative": _accept_narrative,
                 "page_copy": _accept_page_copy, "speech": _accept_speech,
                 "input_revision": _accept_input_revision}
    return acceptors[variant](store, document=document, task=task, envelope=envelope,
                              payload=envelope.get("payload") or {},
                              produced_against=produced_against, result_digest=result_digest,
                              staged=staged)


def _complete_task(store, new_document, task, result_refs):
    """Complete the task with its proposal/result refs (the binding already
    records the adoption policy; no second flag is invented)."""
    updated_task = {**task, "status": "completed", "updated_at": tasks_mod._utc_now_iso(),
                    "result_refs": list(result_refs)}
    models.validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    tasks_mod._replace_task_in_document(new_document, task, task_ref, store)
    close_completed_content_request(store, new_document)


def close_completed_content_request(store, document):
    """Finish only this declared content request in its actual adoption swap."""
    region = document.get('collaboration') or {}
    request = region.get('request') or {}
    if (request.get('intent') == 'content_only' and not request.get('closed')
            and completion_status(store, document)['state'] == 'completed'):
        document['collaboration'] = {**region, 'request': {**request, 'closed': True, 'closed_reason': 'completed'}}
    return document


def _payload_object(payload, key, where):
    value = payload.get(key)
    if not isinstance(value, dict):
        raise tasks_mod.EnvelopeError(f"(result)/payload/{where}",
                                      f"{where} must be a stored-shaped object")
    return value


def _scope_pages(task, binding):
    scope = (binding or {}).get("write_scope") or {}
    return set(scope.get("page_ids") or []), set(task.get("scope_pages") or [])


def _require_pages_in_scope(page_ids, task, binding, where):
    scoped, task_scoped = _scope_pages(task, binding)
    if scoped:
        outside = sorted(set(page_ids) - scoped)
        if outside:
            raise tasks_mod.EnvelopeError(where, f"pages outside the bound write scope: {outside}")
    if task_scoped:
        outside = sorted(set(page_ids) - task_scoped)
        if outside:
            raise tasks_mod.EnvelopeError(where, f"pages outside the task scope: {outside}")


def _narrative_project_check(narrative, document):
    if narrative.get("project_id") != document["project_id"]:
        raise tasks_mod.EnvelopeError("(result)/payload/narrative/project_id",
                                      "narrative belongs to another project")


# --- framing


def _accept_framing(store, *, document, task, envelope, payload, produced_against,
                    result_digest, staged):
    narrative = _payload_object(payload, "narrative", "narrative")
    if narrative.get("maturity") != "framing":
        raise tasks_mod.EnvelopeError(
            "(result)/payload/narrative/maturity",
            "the framing variant carries a framing Narrative; an argument narrative is a separate phase")
    models.validate_narrative_semantics(narrative)
    _narrative_project_check(narrative, document)
    narrative_ref = store.put_json_object(narrative)
    binding = task.get("collaboration_binding") or {}
    updated = bump_revision(document, {
        "operation_id": task["operation_id"], "kind": "task_update",
        "description": f"framing proposal {narrative['narrative_id']}", "read_set": []})
    # The current semantic pointer never moves here: framing is a proposal.
    _complete_task(store, updated, task, [narrative_ref])
    response = {
        "status": "accepted", "revision_id": updated["revision_id"],
        "variant": "framing", "adopted": False,
        "narrative_ref": narrative_ref, "proposal_refs": [narrative_ref],
        "effective_scope": binding.get("write_scope"),
        "result_refs": [narrative_ref],
        "next_action": "argument_phase",
        "note": "framing proposal stored; the current Narrative pointer moves only through an adopted decision",
    }
    return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
                                      task=task, envelope=envelope, produced_against=produced_against,
                                      result_digest=result_digest, response=response)


# --- narrative


def _accept_narrative(store, *, document, task, envelope, payload, produced_against,
                      result_digest, staged):
    narrative = _payload_object(payload, "narrative", "narrative")
    if narrative.get("maturity") != "argument":
        raise tasks_mod.EnvelopeError(
            "(result)/payload/narrative/maturity",
            "the narrative variant carries an argument Narrative with a central node and connected structure")
    models.validate_narrative_semantics(narrative)
    _narrative_project_check(narrative, document)
    narrative_ref = store.put_json_object(narrative)
    result_refs = [narrative_ref]
    plan_ref = None
    if payload.get("plan") is not None:
        plan = _payload_object(payload, "plan", "plan")
        models.validate_content_plan_semantics(plan)
        if plan.get("schema_version") != "content_plan.v2" or plan.get("mode") != "planned":
            raise tasks_mod.EnvelopeError(
                "(result)/payload/plan/mode",
                "the narrative variant may attach a planned content_plan.v2; bound plans arrive with page_copy")
        if plan.get("project_id") != document["project_id"]:
            raise tasks_mod.EnvelopeError("(result)/payload/plan/project_id",
                                          "plan belongs to another project")
        if plan.get("narrative_ref") not in (None, narrative_ref):
            raise tasks_mod.EnvelopeError(
                "(result)/payload/plan/narrative_ref",
                "a planned plan may only bind the Narrative submitted in this same result")
        if plan.get("page_links"):
            raise tasks_mod.EnvelopeError("(result)/payload/plan/page_links",
                                          "a planned plan has no bound page_links")
        # The Host cannot know the Ref of an object it is submitting, so the
        # Runtime fills this structural link with the stored Narrative Ref.
        plan = {**plan, "narrative_ref": narrative_ref}
        plan_ref = store.put_json_object(plan)
        result_refs.append(plan_ref)
    binding = task.get("collaboration_binding") or {}
    updated = bump_revision(document, {
        "operation_id": task["operation_id"], "kind": "task_update",
        "description": f"narrative proposal {narrative['narrative_id']}", "read_set": []})
    _complete_task(store, updated, task, result_refs)
    response = {
        "status": "accepted", "revision_id": updated["revision_id"],
        "variant": "narrative", "adopted": False,
        "narrative_ref": narrative_ref, "plan_ref": plan_ref, "proposal_refs": result_refs,
        "effective_scope": binding.get("write_scope"),
        "result_refs": result_refs,
        "next_action": "adopt_or_request_direction",
        "note": "proposal stored; adoption needs an effective accepted direction decision",
    }
    return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
                                      task=task, envelope=envelope, produced_against=produced_against,
                                      result_digest=result_digest, response=response)


# --- page_copy


def _require_mapping_links_current(mapping, known_nodes, where) -> None:
    """Every visible mapping link must still resolve in the bound Narrative.

    The same predicate page_copy applies to a new page: a mapping bound to the
    current Narrative may not keep atom links pointing at nodes that no longer
    exist in it (CONTRACTS §11.3 mapping discipline).
    """
    for index, link in enumerate(mapping.get("visible_links") or []):
        unknown = sorted(set(link.get("narrative_node_ids") or []) - known_nodes)
        if unknown:
            raise tasks_mod.EnvelopeError(
                f"{where}/content_mapping/visible_links[{index}]",
                f"the visible mapping references narrative nodes that are not in the current "
                f"Narrative: {unknown}; re-run the page_copy phase for this page")


def _check_mapping_against(
        store, document, narrative, narrative_ref, plan_input, page, *, require_role_mapping=True,
):
    """Page content_mapping must point at the adopted Narrative and real atoms.

    CONTRACTS §11.3: every visible atom gets exactly one mapping entry (checked
    by the page validator) and the attached source locators must exist in the
    stored source version.
    """
    from .content_plan import ContentPlanError, validate_source_links
    mapping = page.get("content_mapping")
    if mapping is None:
        raise tasks_mod.EnvelopeError(
            f"(result)/payload/pages/{page['page_id']}/content_mapping",
            "a page_copy result maps every atom to the adopted Narrative; "
            "content_mapping is required at this phase")
    expected = atom_ids(page)
    if mapping.get("narrative_ref") != narrative_ref:
        raise tasks_mod.EnvelopeError(
            f"(result)/payload/pages/{page['page_id']}/content_mapping/narrative_ref",
            "page mapping must reference the adopted current Narrative; a page cannot switch semantics")
    known_nodes = {node["node_id"] for node in (narrative or {}).get("nodes") or []}
    roles = {role["page_id"]: role for role in plan_input.get("page_roles") or []}
    if mapping.get("plan_role_page_id") != page["page_id"] or (require_role_mapping and page["page_id"] not in roles):
        raise tasks_mod.EnvelopeError(
            f"(result)/payload/pages/{page['page_id']}/content_mapping/plan_role_page_id",
            "the mapping must name this page's plan role")
    cache: dict = {}
    for index, link in enumerate(mapping.get("visible_links") or []):
        if link.get("element_ref") not in expected:
            raise tasks_mod.EnvelopeError(
                f"(result)/payload/pages/{page['page_id']}/content_mapping/visible_links[{index}]",
                f"unknown visible atom {link.get('element_ref')!r}")
        unknown = sorted(set(link.get("narrative_node_ids") or []) - known_nodes)
        if unknown:
            raise tasks_mod.EnvelopeError(
                f"(result)/payload/pages/{page['page_id']}/content_mapping/visible_links[{index}]",
                f"narrative nodes not present in the adopted Narrative: {unknown}")
        try:
            validate_source_links(
                store, document, link.get("source_links"),
                f"page/{page['page_id']}/content_mapping/visible_links[{index}]/source_links",
                cache)
        except (ModelError, StoreError, ContentPlanError) as exc:
            raise tasks_mod.EnvelopeError(
                f"(result)/payload/pages/{page['page_id']}/content_mapping/visible_links[{index}]",
                str(exc)) from exc
    segments = mapping.get("speech_segments") or []
    notes = page.get("speaker_notes") or ""
    if notes and not segments:
        raise tasks_mod.EnvelopeError(
            f"(result)/payload/pages/{page['page_id']}/content_mapping/speech_segments",
            "non-empty speaker notes must be covered by speech segments at this phase")
    for index, segment in enumerate(segments):
        unknown = sorted(set(segment.get("narrative_node_ids") or []) - known_nodes)
        if unknown:
            raise tasks_mod.EnvelopeError(
                f"(result)/payload/pages/{page['page_id']}/content_mapping/speech_segments[{index}]",
                f"narrative nodes not present in the adopted Narrative: {unknown}")


def _accept_page_copy(store, *, document, task, envelope, payload, produced_against,
                      result_digest, staged):
    from .content_plan import attach, build_v2_plan
    pages_raw = payload.get("pages")
    page_order = payload.get("page_order")
    plan_input = _payload_object(payload, "plan_input", "plan_input")
    if not isinstance(pages_raw, list) or not pages_raw:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/pages",
            "page_copy delivers the complete page array; an empty list cannot stand in for a plan")
    if (not isinstance(page_order, list) or not page_order
            or len(set(page_order)) != len(page_order)):
        raise tasks_mod.EnvelopeError("(result)/payload/page_order",
                                      "page_copy requires the complete unique result page order")
    pages = []
    for index, page in enumerate(pages_raw):
        if not isinstance(page, dict):
            raise tasks_mod.EnvelopeError(f"(result)/payload/pages[{index}]", "page must be an object")
        try:
            pages.append(check_page(page))
        except ModelError as exc:
            raise tasks_mod.EnvelopeError(f"(result)/payload/pages[{index}]", str(exc)) from exc
    page_ids = [page["page_id"] for page in pages]
    if len(set(page_ids)) != len(page_ids):
        raise tasks_mod.EnvelopeError("(result)/payload/pages", "duplicate page_id in result")
    if sorted(page_order) != sorted(page_ids):
        raise tasks_mod.EnvelopeError(
            "(result)/payload/page_order",
            "page_order must list exactly the delivered pages")
    binding = task.get("collaboration_binding") or {}
    _require_pages_in_scope(page_ids, task, binding, "(result)/payload/pages")

    narrative_ref = document.get("narrative")
    if narrative_ref is None:
        raise ModelError(
            "(result)/payload/pages",
            "decision_needed: page_copy binds the adopted current Narrative Ref; "
            "adopt the narrative proposal before writing the copy")
    narrative = store.read_object_json(narrative_ref)
    if narrative.get("maturity") != "argument":
        raise ModelError("(result)/payload/pages",
                         "the current Narrative is not an argument Narrative yet")
    for page in pages:
        _check_mapping_against(store, document, narrative, narrative_ref, plan_input, page)

    old_ids = [entry["page_id"] for entry in document.get("pages") or []]
    old_order = list(old_ids)
    scope = binding.get("write_scope") or {}
    # Existing pages must be inside the bound scope; brand-new page ids are a
    # membership change, never a scope escape (CONTRACTS §2.1/§3.4).
    existing = set(old_ids)
    _require_pages_in_scope(sorted(set(page_ids) & existing), task, binding,
                            "(result)/payload/pages")
    added = sorted(set(page_ids) - existing)
    if added and scope.get("allow_page_membership_change") is not True:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/pages",
            f"adding pages needs a scope that allows membership change: {added}")
    # The same membership rule guards the other direction: the result's
    # page_order rebuilds the manuscript, so omitting a current page is a
    # deletion of that page — one a scoped partial write is never authorized
    # to express by silence (external review F03).
    removed = sorted(existing - set(page_ids))
    if removed and scope.get("allow_page_membership_change") is not True:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/pages",
            f"omitting current pages is an undeclared deletion, not a partial write: {removed}; "
            "page_copy delivers the complete page set, and removing pages needs a scope "
            "that allows membership change")
    if old_order and scope.get("allow_page_order_change") is not True and old_order != list(page_order) \
            and set(old_order) == set(page_order):
        raise tasks_mod.EnvelopeError(
            "(result)/payload/page_order",
            "reordering existing pages needs a scope that allows page order change")
    violation = models.page_limit_violation({**document, "pages": page_order})
    if violation:
        raise tasks_mod.EnvelopeError("(result)/payload/page_order", violation)

    page_refs = {page["page_id"]: store.put_json_object(page) for page in pages}
    ordered_refs = [{"page_id": page_id, "page": page_refs[page_id]} for page_id in page_order]

    proposal_only = binding.get("adoption_policy") in ("proposal_only", "candidate_only")
    from .candidates import is_trial, record_result
    if is_trial(task):
        updated_task = {**task, "status": "completed", "updated_at": tasks_mod._utc_now_iso()}
        return record_result(store, document=document, task=task, updated_task=updated_task,
                             artifacts=[], artifact_refs=[], generation_binding=None,
                             envelope=envelope, produced_against=produced_against,
                             result_digest=result_digest, page_refs=page_refs)
    try:
        plan_ref = build_v2_plan(store, document, task, plan_input, ordered_refs,
                                 narrative_ref=narrative_ref, mode="bound")
    except (ModelError, StoreError) as exc:
        raise tasks_mod.EnvelopeError("(result)/payload/plan_input", str(exc)) from exc
    if proposal_only:
        updated = bump_revision(document, {
            "operation_id": task["operation_id"], "kind": "task_update",
            "description": "page_copy proposals stored", "read_set": []})
        result_refs = list(page_refs.values()) + [plan_ref]
        _complete_task(store, updated, task, result_refs)
        response = {
            "status": "accepted", "revision_id": updated["revision_id"],
            "variant": "page_copy", "adopted": False,
            "page_refs": page_refs, "plan_ref": plan_ref, "proposal_refs": result_refs,
            "result_refs": result_refs, "next_action": "adopt_or_request_direction",
            "note": "proposal_only keeps the current Document pages, plan and narrative unchanged",
        }
        return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
                                          task=task, envelope=envelope,
                                          produced_against=produced_against,
                                          result_digest=result_digest, response=response)

    updated = bump_revision(document, {
        "operation_id": task["operation_id"], "kind": "content_update",
        "description": envelope.get("notes") or "page copy adopted", "read_set": []})
    models.require_writer(updated, "rc3.v1")
    updated["pages"] = [
        {"page_id": page_id, "page": page_refs[page_id], "blueprint": None,
         "svg": None, "svg_preview": None, "ppt_preview": None}
        for page_id in page_order]
    updated["outputs"] = dict.fromkeys(updated["outputs"])
    if task.get("input_digest"):
        updated["content_basis"] = {
            "input_digest": task["input_digest"],
            "input_revision_id": task.get("input_revision_id"),
            "resolved_by_task_id": task["task_id"],
        }
    attach(updated, plan_ref)
    result_refs = list(page_refs.values()) + [plan_ref]
    _complete_task(store, updated, task, result_refs)
    updated["change"] = {
        "operation_id": task["operation_id"], "kind": "content_update",
        "description": envelope.get("notes") or "page copy adopted",
        "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}",
                      "sha256": produced_against}],
    }
    response = {
        "status": "accepted", "revision_id": updated["revision_id"],
        "variant": "page_copy", "adopted": True,
        "page_refs": page_refs, "plan_ref": plan_ref,
        "result_refs": result_refs,
        "page_count": len(page_order),
        "work_complete": tasks_mod.derive_work_complete(updated, store),
        "next_action": "speech_or_production",
    }
    return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
                                      task=task, envelope=envelope, produced_against=produced_against,
                                      result_digest=result_digest, response=response)


# --- speech


_SPEECH_FORBIDDEN_UPDATE_FIELDS = ("customer_visible", "visual_spec", "internal_only",
                                   "citations", "page_id")


def _accept_speech(store, *, document, task, envelope, payload, produced_against,
                   result_digest, staged):
    from .content_plan import attach, refresh_v2_plan_links
    updates = payload.get("updates")
    if not isinstance(updates, list) or not updates:
        raise tasks_mod.EnvelopeError("(result)/payload/updates",
                                      "speech delivers at least one page note update")
    binding = task.get("collaboration_binding") or {}
    scope = binding.get("write_scope") or {}
    if "speech" not in (scope.get("layers") or []):
        raise tasks_mod.EnvelopeError(
            "(result)/payload/updates",
            "this task's write scope does not include the speech layer")
    entries = {entry["page_id"]: entry for entry in document.get("pages") or []}
    narrative_ref = document.get("narrative")
    narrative = store.read_object_json(narrative_ref) if narrative_ref else None
    known_nodes = {node["node_id"] for node in (narrative or {}).get("nodes") or []}
    requested_kind = _requested_speech_kind(store, document, task)
    new_pages: dict[str, dict] = {}
    new_page_refs: dict[str, dict] = {}
    for index, update in enumerate(updates):
        where = f"(result)/payload/updates[{index}]"
        if not isinstance(update, dict):
            raise tasks_mod.EnvelopeError(where, "update must be an object")
        unknown_fields = sorted(set(update) - {
            "page_id", "page_ref", "speaker_notes", "speech_segments"})
        if unknown_fields:
            raise tasks_mod.EnvelopeError(where, f"refusing unknown speech update fields: {unknown_fields}")
        page_id = update.get("page_id")
        if page_id in new_pages:
            raise tasks_mod.EnvelopeError(f"{where}/page_id", "duplicate speech update identity")
        entry = entries.get(page_id)
        if entry is None:
            raise tasks_mod.EnvelopeError(f"{where}/page_id", "page not present in the current deck")
        _require_pages_in_scope([page_id], task, binding, f"{where}/page_id")
        forbidden = sorted(key for key in _SPEECH_FORBIDDEN_UPDATE_FIELDS
                           if key != "page_id" and update.get(key) is not None)
        if forbidden:
            raise tasks_mod.EnvelopeError(
                where, f"speech writes speaker_notes and its mapping segment only; refusing {forbidden}")
        page_ref = update.get("page_ref")
        if not isinstance(page_ref, dict) or (page_ref.get("path"), page_ref.get("sha256")) != \
                (entry["page"]["path"], entry["page"]["sha256"]):
            raise tasks_mod.EnvelopeError(
                f"{where}/page_ref",
                "speech updates a fixed Page Ref; re-read the current page and resubmit")
        notes = update.get("speaker_notes")
        if not isinstance(notes, str) or not notes.strip():
            raise tasks_mod.EnvelopeError(f"{where}/speaker_notes", "notes must be a non-empty string")
        current = store.read_object_json(entry["page"])
        mapping = copy.deepcopy(current.get("content_mapping"))
        segments = update.get("speech_segments")
        if mapping is None:
            plan = (store.read_object_json(document['content_plan'])
                    if document.get('content_plan') else {})
            if (plan.get('mode') != 'imported_mapping' or narrative_ref is not None or
                    plan.get('narrative_ref') is not None):
                raise tasks_mod.EnvelopeError(
                    f"{where}/speaker_notes",
                    "this Page has no content_mapping; a new argument needs page_copy mapping before speech")
            # A source-bound imported manuscript can honestly have unknown
            # argument links. Do not invent a Narrative to add notes. Preserve
            # every real visible atom and reuse only the stored page-role sources.
            models.validate_content_plan_semantics(plan)
            role = next((role for role in plan['input']['page_roles']
                         if role['page_id'] == page_id), None)
            link = next((link for link in plan.get('page_links') or [] if link['page_id'] == page_id), None)
            if link is None or link['page_ref'] != entry['page']:
                raise tasks_mod.EnvelopeError(where, 'imported Page has no exact current Plan link')
            mapping = {'narrative_ref': None, 'plan_role_page_id': page_id,
                       'visible_links': [{'element_ref': atom, 'narrative_node_ids': [],
                                         'source_links': copy.deepcopy((role or {}).get('source_links') or [])}
                                        for atom in sorted(atom_ids(current))],
                       'speech_segments': []}
        if mapping.get("narrative_ref") != narrative_ref:
            # The page's visible copy is mapped to a different argument than the
            # current one. A silent rebind would leave every visible_links entry
            # dangling, so the fix is the copy phase, not a speech rewrite.
            raise tasks_mod.EnvelopeError(
                f"{where}/speaker_notes",
                "this Page's content_mapping binds another Narrative than the current one "
                "(its visible copy was written for a superseded argument); re-run the page_copy "
                "phase to re-map the visible atoms against the current Narrative, then write speech")
        _require_mapping_links_current(mapping, known_nodes, where)
        if not isinstance(segments, list) or not segments:
            raise tasks_mod.EnvelopeError(
                f"{where}/speech_segments",
                "the mapping's speech range must cover the new notes")
        for seg_index, segment in enumerate(segments):
            seg_where = f"{where}/speech_segments[{seg_index}]"
            allowed_kinds = ("cue", "verbatim") if requested_kind == "verbatim" else ("cue",)
            if segment.get("kind") not in allowed_kinds:
                raise tasks_mod.EnvelopeError(
                    f"{seg_where}/kind",
                    f"this task was dispatched for {requested_kind!r} speech; "
                    f"got {segment.get('kind')!r}")
            unknown = sorted(set(segment.get("narrative_node_ids") or []) - known_nodes)
            if unknown:
                raise tasks_mod.EnvelopeError(seg_where,
                                              f"narrative nodes not in the current Narrative: {unknown}")
            if segment.get("estimated_seconds") is None:
                raise tasks_mod.EnvelopeError(
                    f"{seg_where}/estimated_seconds",
                    "speech estimates are required per segment and stay labelled estimated")
        mapping["speech_segments"] = copy.deepcopy(segments)
        updated_page = {**current, "speaker_notes": notes}
        updated_page["content_mapping"] = mapping
        try:
            updated_page = check_page(updated_page)
        except ModelError as exc:
            raise tasks_mod.EnvelopeError(where, str(exc)) from exc
        # CONTRACTS §11.3 defines kind per segment. A complete verbatim script
        # can contain honestly labelled non-spoken cues; an all-cue page cannot
        # satisfy an explicit verbatim request. This structural floor does not
        # prove the spoken content is complete or its estimated timing feasible.
        if requested_kind == "verbatim" and not any(
            segment["kind"] == "verbatim" and
            notes[segment["start_codepoint"]:segment["end_codepoint"]].strip()
            for segment in segments
        ):
            raise tasks_mod.EnvelopeError(
                f"{where}/speech_segments",
                "this task was dispatched for 'verbatim' speech; each updated page must "
                "contain spoken verbatim content, not only cues")
        # The visible body and the visual configuration are byte-identical:
        # a speech result cannot smuggle a copy or design change.
        assert updated_page["customer_visible"] == current["customer_visible"]
        assert updated_page.get("visual_spec") == current.get("visual_spec")
        new_pages[page_id] = updated_page
        new_page_refs[page_id] = store.put_json_object(updated_page)

    updated = bump_revision(document, {
        "operation_id": task["operation_id"], "kind": "content_update",
        "description": envelope.get("notes") or "speech notes adopted", "read_set": []})
    models.require_writer(updated, "rc3.v1")
    refreshed_entries = []
    for entry in updated.get("pages") or []:
        page_id = entry["page_id"]
        if page_id not in new_page_refs:
            refreshed_entries.append(entry)
            continue
        refreshed_entries.append({**entry, "page": new_page_refs[page_id],
                                  "ppt_preview": None})
    updated["pages"] = refreshed_entries
    updated["outputs"] = dict.fromkeys(updated["outputs"])
    plan_ref = None
    plan_note = None
    plan_source_ref = document.get("content_plan")
    if plan_source_ref:
        plan = store.read_object_json(plan_source_ref)
        if (plan.get("schema_version") == "content_plan.v2" and
                plan.get("mode") in ("bound", "imported_mapping")):
            plan_ref = refresh_v2_plan_links(
                store, document, task, plan,
                [{"page_id": e["page_id"], "page": e["page"]} for e in refreshed_entries],
                previous_ref=plan_source_ref)
            attach(updated, plan_ref)
        elif plan.get("schema_version") == "content_plan.v2":
            plan_note = "planned plan has no page_links to rebind yet"
        else:
            plan_note = "current plan is content_plan.v1; speech keeps it unchanged"
    result_refs = list(new_page_refs.values()) + ([plan_ref] if plan_ref else [])
    _complete_task(store, updated, task, result_refs)
    updated["change"] = {
        "operation_id": task["operation_id"], "kind": "content_update",
        "description": envelope.get("notes") or "speech notes adopted",
        "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}",
                      "sha256": produced_against}],
    }
    stale_reviews = stale_speech_reviews(store, updated)
    response = {
        "status": "accepted", "revision_id": updated["revision_id"],
        "variant": "speech", "adopted": True,
        "page_refs": new_page_refs,
        "plan_ref": plan_ref,
        "plan_note": plan_note,
        "result_refs": result_refs,
        "invalidated_outputs": sorted(updated["outputs"]),
        "invalidated_reviews": stale_reviews,
        "next_action": "speech_review_or_production",
    }
    return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
                                      task=task, envelope=envelope, produced_against=produced_against,
                                      result_digest=result_digest, response=response)


def effective_speech_kind(store, document, *, explicit_mode: str | None = None) -> str | None:
    """The one effective speech kind: 'cue', 'verbatim' or None for no new speech.

    CONTRACTS §1.7/§10.1: dispatch and acceptance must read the *same* effective
    policy — a plan that only claims verbatim by default is downgraded to cues,
    so the task is dispatched for cues and cue segments are what acceptance
    requires. `none` means this project produces no new speech at all.
    """
    plan_input = None
    plan_ref = document.get("content_plan")
    if plan_ref:
        try:
            plan_input = store.read_object_json(plan_ref).get("input") or {}
        except Exception:  # noqa: BLE001 - an unreadable plan cannot select a kind
            plan_input = None
    mode = speech_policy(document, plan_input=plan_input, explicit_mode=explicit_mode)["mode"]
    if mode == "none":
        request = (document.get("collaboration") or {}).get("request") or {}
        if request.get("intent") == "content_only" and request.get("content_intent") == "speech_only":
            return "cue"
        return None
    return "verbatim" if mode == "verbatim" else "cue"


def _requested_speech_kind(store, document, task) -> str:
    """The kind this speech task may write, from the effective policy.

    The dispatched kind is recorded on the task at dispatch time (derived from
    the same policy); if the plan changed since dispatch the task is stale and
    never reaches this check. An effective `none` policy refuses new speech
    instead of quietly producing a verbatim/cue script the request never asked
    for.
    """
    effective = effective_speech_kind(store, document)
    if effective is None:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/updates",
            "this project's effective speech policy produces no new speech; writing notes would "
            "expand the requested scope — record an explicit speech request first")
    recorded = (task.get("stage_request") or {}).get("speech_kind")
    # The dispatched kind was derived from the same effective policy (including
    # an explicit instruction); a plan change since dispatch makes the task
    # stale before this point, so the recorded contract is the right one.
    return recorded if recorded in ("cue", "verbatim") else effective


def stale_speech_reviews(store, document) -> list[dict]:
    """Speech reviews whose Page dependency no longer matches the current hash."""
    stale = []
    for ref in document.get("reviews") or []:
        try:
            review = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if review.get("kind") != "speech" or review.get("review_stage") not in (None, "preproduction"):
            continue
        for dep in review.get("dependencies") or []:
            if dep.get("kind") != "content" or not str(dep.get("identity", "")).startswith("page:"):
                continue
            page_id = dep["identity"].split(":", 1)[1]
            entry = next((e for e in document.get("pages") or [] if e["page_id"] == page_id), None)
            if entry is None or entry["page"]["sha256"] != dep.get("sha256"):
                stale.append({"review_id": review.get("review_id"), "review_ref": ref,
                              "reason": "speech dependency changed"})
                break
    return stale


# --- input_revision


def _accept_input_revision(store, *, document, task, envelope, payload, produced_against,
                           result_digest, staged):
    changed_layers = payload.get("changed_layers")
    if (not isinstance(changed_layers, list) or not changed_layers
            or not all(isinstance(layer, str) and layer for layer in changed_layers)):
        raise tasks_mod.EnvelopeError("(result)/payload/changed_layers",
                                      "input_revision declares its non-empty changed-layer mask")
    unknown = sorted(set(changed_layers) - set(CHANGED_LAYERS))
    if unknown:
        raise tasks_mod.EnvelopeError("(result)/payload/changed_layers",
                                      f"unknown layers: {unknown}")
    binding = task.get("collaboration_binding") or {}
    scope_layers = set((binding.get("write_scope") or {}).get("layers") or [])
    outside = sorted(set(changed_layers) - scope_layers)
    if outside:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/changed_layers",
            f"layers outside the bound write scope: {outside}")
    proposals = payload.get("proposals") or []
    if not isinstance(proposals, list):
        raise tasks_mod.EnvelopeError("(result)/payload/proposals", "proposals must be an array")
    diff = payload.get("diff")
    if not isinstance(diff, dict):
        raise tasks_mod.EnvelopeError("(result)/payload/diff",
                                      "input_revision reports the diff it reconciled")
    expected_digest = task.get("input_digest") or models.compute_input_digest(document)
    if diff.get("input_digest") != expected_digest:
        raise tasks_mod.TaskConflict(
            "(result)/payload/diff/input_digest",
            "the diff does not describe the dispatched input revision; read the new inputs and resubmit")
    summary = diff.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise tasks_mod.EnvelopeError("(result)/payload/diff/summary",
                                      "a diff needs a concrete change summary")
    changed_page_ids = diff.get("changed_page_ids") or []
    if not isinstance(changed_page_ids, list) or not all(isinstance(pid, str) and pid
                                                         for pid in changed_page_ids):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/changed_page_ids",
                                      "must be an array of page ids")
    old_ids = {entry['page_id'] for entry in document.get('pages') or []}
    _require_pages_in_scope([pid for pid in changed_page_ids if pid in old_ids], task, binding,
                            "(result)/payload/diff/changed_page_ids")
    if set(changed_page_ids) - old_ids and not (binding.get('write_scope') or {}).get('allow_page_membership_change'):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/changed_page_ids", "new page membership is outside the task scope")
    proposal_by_layer: dict[str, list[dict]] = {layer: [] for layer in changed_layers}
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict) or not proposal.get("layer") or not proposal.get("ref"):
            raise tasks_mod.EnvelopeError(f"(result)/payload/proposals[{index}]",
                                          "a proposal names its layer and a stored Ref")
        layer = proposal["layer"]
        if layer not in proposal_by_layer:
            raise tasks_mod.EnvelopeError(f"(result)/payload/proposals[{index}]/layer",
                                          "a proposal must belong to a changed layer")
        try:
            store.read_object_bytes(proposal["ref"])
        except Exception as exc:  # noqa: BLE001
            raise tasks_mod.EnvelopeError(f"(result)/payload/proposals[{index}]/ref",
                                          f"referenced object is not in the store: {exc}") from exc
        proposal_by_layer[layer].append(proposal)
    removals = diff.get('removed_page_ids')
    removes_copy = isinstance(removals, list) and bool(removals) and all(isinstance(pid, str) and pid for pid in removals)
    silent = sorted(layer for layer, items in proposal_by_layer.items()
        if not items and not (layer == 'page_copy' and removes_copy))
    if silent:
        raise tasks_mod.EnvelopeError(
            "(result)/payload/proposals",
            f"a changed layer without any substantive proposal cannot be claimed: {silent}")

    # Parse every declared layer before constructing a single committed write set.
    single = {}
    for layer in ("narrative", "plan"):
        items = proposal_by_layer.get(layer) or []
        if len(items) > 1:
            raise tasks_mod.EnvelopeError("(result)/payload/proposals", f"{layer} has exactly one proposal; no last-wins")
        if items:
            single[layer] = store.read_object_json(items[0]["ref"])
    narrative_ref = document.get("narrative")
    narrative = store.read_object_json(narrative_ref) if narrative_ref else None
    if "narrative" in single:
        narrative = single["narrative"]
        models.validate_narrative_semantics(narrative)
        _narrative_project_check(narrative, document)
        from .content_plan import ContentPlanError, validate_source_links
        for node in narrative.get('nodes') or []:
            try:
                validate_source_links(store, document, node.get('source_links'),
                    '(result)/payload/proposals/narrative/nodes/' + node['node_id'] + '/source_links')
            except ContentPlanError as exc:
                raise tasks_mod.EnvelopeError('(result)/payload/proposals/narrative', str(exc)) from exc
        narrative_ref = proposal_by_layer["narrative"][0]["ref"]
        from .variant_requests import require_fixed_narrative
        require_fixed_narrative(store, document, narrative_ref)
    known_nodes = {node["node_id"] for node in (narrative or {}).get("nodes", [])}
    entries = {entry["page_id"]: entry for entry in document.get("pages") or []}
    pages = {pid: copy.deepcopy(store.read_object_json(entry["page"])) for pid, entry in entries.items()}
    changed_pages = set()
    for layer in ("page_copy", "speech"):
        seen_pages = set()
        for proposal in proposal_by_layer.get(layer) or []:
            page = store.read_object_json(proposal["ref"])
            if page.get("schema_version") != "deck_page_package.v2":
                raise tasks_mod.EnvelopeError("(result)/payload/proposals", f"{layer} carries complete Page v2 proposals")
            check_page(page)
            if page.get("content_mapping") is None:
                raise tasks_mod.EnvelopeError("(result)/payload/proposals", "each declared Page layer carries its complete mapping")
            pid = page["page_id"]
            if pid in seen_pages:
                raise tasks_mod.EnvelopeError("(result)/payload/proposals", f"duplicate {layer} page {pid}")
            seen_pages.add(pid)
            if pid in entries or not (binding.get('write_scope') or {}).get('allow_page_membership_change'):
                _require_pages_in_scope([pid], task, binding, "(result)/payload/proposals/page_id")
            if layer == "speech":
                if pid not in entries:
                    raise tasks_mod.EnvelopeError("(result)/payload/proposals", "speech cannot add a Page")
                original = store.read_object_json(entries[pid]["page"])
                before = copy.deepcopy(original); after = copy.deepcopy(page)
                for value in (before, after):
                    value.pop("speaker_notes", None)
                    if value.get("content_mapping"):
                        value["content_mapping"].pop("speech_segments", None)
                if before != after:
                    raise tasks_mod.EnvelopeError("(result)/payload/proposals", "speech changes only notes and speech segments")
                segments = (page.get('content_mapping') or {}).get('speech_segments') or []
                expected_kind = effective_speech_kind(store, document) or 'cue'
                if (not segments or any(segment.get('estimated_seconds') is None for segment in segments)
                        or any(segment.get('kind') not in (('cue', 'verbatim') if expected_kind == 'verbatim' else ('cue',)) for segment in segments)
                        or expected_kind == 'verbatim' and not any(segment.get('kind') == 'verbatim' for segment in segments)):
                    raise tasks_mod.EnvelopeError('(result)/payload/proposals/speech', 'speech requires the requested kind, complete mapping and honest per-segment estimates')
                target = copy.deepcopy(pages[pid])
                target["speaker_notes"] = page.get("speaker_notes", "")
                target.setdefault("content_mapping", copy.deepcopy(page.get("content_mapping") or {}))["speech_segments"] = copy.deepcopy((page.get("content_mapping") or {}).get("speech_segments", []))
                pages[pid] = target
            else:
                if "speech" not in changed_layers and pid in entries:
                    original = store.read_object_json(entries[pid]["page"])
                    if page.get("speaker_notes", "") != original.get("speaker_notes", ""):
                        raise tasks_mod.EnvelopeError("(result)/payload/proposals", "page_copy cannot silently change speech")
                pages[pid] = copy.deepcopy(page)
            changed_pages.add(pid)
    removed = diff.get("removed_page_ids") or []
    if not isinstance(removed, list) or any(not isinstance(pid, str) or not pid for pid in removed) or len(removed) != len(set(removed)):
        raise tasks_mod.EnvelopeError('(result)/payload/diff/removed_page_ids', 'removed pages are unique non-empty page identities')
    if removed and "page_copy" not in changed_layers:
        raise tasks_mod.EnvelopeError("(result)/payload/diff", "only page_copy may remove pages")
    if set(removed) - set(entries):
        raise tasks_mod.EnvelopeError("(result)/payload/diff", "cannot remove absent pages")
    _require_pages_in_scope(removed, task, binding, "(result)/payload/diff/removed_page_ids")
    for pid in removed:
        pages.pop(pid, None)
    old_order = list(entries)
    order = diff.get("page_order") or [pid for pid in old_order if pid in pages] + [pid for pid in pages if pid not in entries]
    if len(order) != len(set(order)) or set(order) != set(pages):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/page_order", "page order covers the complete resulting set exactly once")
    scope = binding.get("write_scope") or {}
    if set(order) != set(old_order) and not scope.get("allow_page_membership_change"):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/page_order", "page membership is outside this task's scope")
    if set(order) == set(old_order) and order != old_order and not scope.get("allow_page_order_change"):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/page_order", "page order is outside this task's scope")
    old_plan = store.read_object_json(document["content_plan"]) if document.get("content_plan") else None
    plan_input = single.get("plan") or (copy.deepcopy(old_plan["input"]) if old_plan else None)
    if plan_input is not None and plan_input.get("schema_version") == "content_plan.v2":
        models.validate_content_plan_semantics(plan_input)
        if plan_input["project_id"] != document["project_id"]:
            raise tasks_mod.EnvelopeError("(result)/payload/proposals", "Plan belongs to another project")
        plan_input = plan_input["input"]
    if plan_input is not None:
        models.validate_schema("content_plan_input", plan_input)
        if plan_input["page_order"] != order:
            raise tasks_mod.EnvelopeError("(result)/payload/proposals", "Plan and resulting page order must match")
        for role in plan_input["page_roles"]:
            if set(role.get("narrative_node_ids", [])) - known_nodes:
                raise tasks_mod.EnvelopeError("(result)/payload/proposals", "Plan references nodes outside the new Narrative")
    elif pages:
        raise tasks_mod.EnvelopeError("(result)/payload/proposals", "reconciled Pages need their complete Plan mapping")
    imported_mapping = bool(old_plan and old_plan.get('mode') == 'imported_mapping' and narrative_ref is None)
    if plan_input is not None:
        from .content_plan import ContentPlanError, validate_plan_input_v2
        try:
            validate_plan_input_v2(store, document, plan_input,
                mode='imported_mapping' if imported_mapping else 'planned',
                imported_manuscript=old_plan.get('imported_manuscript') if imported_mapping else None,
                narrative_ref=narrative_ref)
        except ContentPlanError as exc:
            raise tasks_mod.EnvelopeError('(result)/payload/proposals/plan', str(exc)) from exc
    for page in pages.values():
        mapping = page.get("content_mapping")
        if mapping is None:
            raise tasks_mod.EnvelopeError("(result)/payload/proposals", "Page mapping is missing")
        if "narrative" in changed_layers:
            mapping["narrative_ref"] = narrative_ref
        if mapping.get("narrative_ref") != narrative_ref:
            raise tasks_mod.EnvelopeError("(result)/payload/proposals", "Page mapping binds another Narrative")
        check_page(page)
        _check_mapping_against(store, document, narrative, narrative_ref, plan_input, page,
            require_role_mapping=not imported_mapping)
    virtual_update = {'input_digest': expected_digest, 'upsert_pages': [pages[pid] for pid in sorted(changed_pages)],
        'remove_page_ids': list(removed), 'page_order': order, 'impact_summary': summary.strip()}
    violation = tasks_mod.page_limit_violation({**document, 'pages': [{'page_id': pid} for pid in order]})
    if violation:
        raise tasks_mod.EnvelopeError('(result)/payload/diff/page_order', violation)
    if not changed_pages and not removed:
        virtual_update['unchanged_reason'] = summary.strip()
    if set(changed_page_ids) != changed_pages | set(removed):
        raise tasks_mod.EnvelopeError("(result)/payload/diff/changed_page_ids", "diff must identify exactly the substantive Page proposals and removals")
    if task.get('content_operation_ref'):
        if set(changed_layers) - {'page_copy', 'plan'}:
            raise tasks_mod.EnvelopeError('(result)/payload/changed_layers', 'the editorial operation does not authorize Narrative or speech changes')
        from .content_ops import validate_host_result
        validate_host_result(store, document, task, virtual_update, plan_input)
    from .candidates import is_trial, record_result
    if is_trial(task):
        converted = {'kind': 'compose', 'content_update': virtual_update, 'content_plan': plan_input}
        return record_result(store, document=document, task=task,
            updated_task={**task, 'status': 'completed', 'updated_at': tasks_mod._utc_now_iso()},
            artifacts=[], artifact_refs=[], generation_binding=None, envelope=converted,
            receipt_envelope=envelope, content_update=virtual_update,
            produced_against=produced_against, result_digest=result_digest)
    new_pages = []
    for pid in order:
        page = pages[pid]
        ref = store.put_json_object(page)
        previous = entries.get(pid)
        entry = {"page_id": pid, "page": ref, "blueprint": None, "svg": None,
                 "svg_preview": None, "ppt_preview": None}
        if previous:
            entry.update(previous); entry["page"] = ref
            from .visual_dependencies import page_visual_digest
            if page_visual_digest(page) != page_visual_digest(store.read_object_json(previous["page"])):
                entry.update(svg=None, svg_preview=None, ppt_preview=None)
        new_pages.append(entry)
    updated = bump_revision(document, {"operation_id": task["operation_id"], "kind": "content_update",
        "description": summary.strip(), "read_set": []})
    updated["pages"] = new_pages
    updated["narrative"] = narrative_ref
    updated["content_basis"] = {"input_digest": expected_digest, "input_revision_id": task.get("input_revision_id"),
                                "resolved_by_task_id": task["task_id"]}
    result_refs = [entry["page"] for entry in new_pages if entries.get(entry["page_id"], {}).get("page") != entry["page"]]
    if "narrative" in changed_layers:
        result_refs.append(narrative_ref)
    if plan_input is not None:
        from .content_plan import build_v2_plan
        mode = "imported_mapping" if old_plan and old_plan.get("mode") == "imported_mapping" and narrative_ref is None else ("bound" if new_pages else "planned")
        plan_ref = build_v2_plan(store, document, task, plan_input, new_pages, narrative_ref=narrative_ref,
            mode=mode, imported_manuscript=old_plan.get("imported_manuscript") if mode == "imported_mapping" else None,
            require_role_mapping=mode != "imported_mapping")
        updated["content_plan"] = plan_ref; result_refs.append(plan_ref)
    if binding.get("adoption_policy") in ("proposal_only", "candidate_only"):
        proposed = [*result_refs]
        pending = bump_revision(document, {"operation_id": task["operation_id"], "kind": "task_update",
            "description": "input revision proposals retained without adopting content or clearing reconciliation", "read_set": []})
        _complete_task(store, pending, task, proposed)
        return tasks_mod._commit_adoption(store, document=pending, base_revision=document["revision_id"],
            task=task, envelope=envelope, produced_against=produced_against, result_digest=result_digest,
            response={"status": "accepted", "revision_id": pending["revision_id"], "variant": "input_revision",
                "adopted": False, "changed_layers": changed_layers, "proposal_refs": proposed,
                'impact_summary': summary.strip(), 'new_page_hashes': {},
                "result_refs": proposed, "next_action": "adopt_with_covering_decision"})
    actual_plan_change = plan_input != (old_plan or {}).get('input')
    if (any(entry['page'] != entries.get(entry['page_id'], {}).get('page') for entry in new_pages)
            or order != list(entries) or narrative_ref != document.get('narrative') or actual_plan_change):
        updated["outputs"] = dict.fromkeys(document["outputs"])
    if task.get('content_operation_ref'):
        from .content_ops import bind_derivation
        bind_derivation(store, document, updated, task, {entry['page_id']: entry['page'] for entry in new_pages if entry['page_id'] in changed_pages})
    _complete_task(store, updated, task, result_refs)
    models.validate_document_semantics(updated)
    return tasks_mod._commit_adoption(store, document=updated, base_revision=document["revision_id"],
        task=task, envelope=envelope, produced_against=produced_against, result_digest=result_digest,
        response={"status": "accepted", "revision_id": updated["revision_id"], "variant": "input_revision",
            "adopted": True, "changed_layers": changed_layers, "narrative_ref": narrative_ref,
            'impact_summary': summary.strip(),
            'new_page_hashes': {entry['page_id']: entry['page']['sha256'] for entry in new_pages if entry['page_id'] in changed_pages},
            "plan_ref": updated.get("content_plan"), "page_refs": [entry["page"] for entry in new_pages],
            "result_refs": result_refs, "invalidated_outputs": [ref for key, ref in document['outputs'].items()
                if ref and updated['outputs'].get(key) != ref],
            "effective_scope": scope, "next_action": "continue_within_request"})


# ---------------------------------------------------------------------------
# Proposal adoption (CONTRACTS §11.5, §12)


def adopt_proposal(project, *, input: dict, base_revision: str, operation_id: str,
                   adapter_context=None) -> dict:
    """Promote a proposal Ref to the current pointer inside a covering Decision.

    The Decision must be effective, accepted and direct-user or delegated, and
    its scope must cover the requested write scope. Adoption writes an exact
    pointer set with CAS and a receipt: it creates no new confirmation and
    grants no production authority (CONTRACTS §11.5).
    """
    from . import collaboration
    from .tasks import _project_transaction

    store = Store(Path(project).expanduser())
    action = collaboration.ACTION_ADOPT_PROPOSAL
    digest = collaboration.write_digest(action, input)

    @_project_transaction
    def locked(store: Store):
        document = store.load_document()
        replay = collaboration.replay_or_conflict(store, document, operation_id, action, digest)
        if replay:
            return replay
        if document["revision_id"] != base_revision:
            raise StoreError("base_revision", "base revision is not current; reload and retry")
        region = collaboration._require_region(store, document)
        proposal_ref = input.get("proposal_ref")
        decision_ref = input.get("decision_ref")
        write_scope = input.get("write_scope")
        if not isinstance(proposal_ref, dict) or not isinstance(decision_ref, dict):
            raise ModelError("collaboration/adopt_proposal",
                             "proposal_ref and decision_ref are required Refs")
        head = collaboration._head_for_identity(store, region, "decisions", "decision_id",
                                               collaboration._identity_of(store, decision_ref))
        if head is None:
            raise ModelError("collaboration/adopt_proposal/decision_ref",
                             "the decision must be referenced by the current collaboration region")
        _, decision = head
        if (decision.get("disposition") != "accepted"
                or decision.get("authority_mode") not in ("direct_user", "delegated")):
            raise ModelError("collaboration/adopt_proposal/decision_ref",
                             "authority_insufficient: adoption needs an accepted decision "
                             "recorded as direct_user or delegated")
        state = dependency_slices.decision_effectiveness(store, document, head[0])
        if not state["effective"]:
            raise ModelError("collaboration/adopt_proposal/decision_ref",
                             f"the decision is not effective: {state['reasons']}")
        if not isinstance(write_scope, dict):
            raise ModelError("collaboration/adopt_proposal/write_scope",
                             "adoption names its exact write scope")
        from . import eligibility
        eligibility.guard(store, document, "proposal.adopt", context={"scope": write_scope})
        gaps = scope_gaps(store, decision.get("scope") or {}, write_scope)
        if gaps:
            raise ModelError("collaboration/adopt_proposal/write_scope",
                             f"scope_exceeded: the decision does not cover {gaps}")
        try:
            proposal = store.read_object_json(proposal_ref)
        except Exception as exc:  # noqa: BLE001
            raise ModelError("collaboration/adopt_proposal/proposal_ref",
                             f"proposal is not stored: {exc}") from exc
        schema = proposal.get("schema_version")
        # A decision adopts only the proposals it names: an accepted direction
        # with no subject refs approves no specific artifact, so it must not be
        # usable to promote any proposal of the topic (CONTRACTS §3.1: a
        # decision is about ProposalRefs, and a projection is a registered
        # slice of the named artifact).
        subjects = decision.get("subject_refs") or []
        if not subjects:
            raise ModelError(
                "collaboration/adopt_proposal/decision_ref",
                "the decision names no proposal (empty subject_refs), so it covers no specific "
                "artifact; record a decision that names this proposal Ref with a registered "
                "projection before adopting it")
        allowed = _ADOPTION_PROJECTIONS.get(schema, ())
        matches = [item for item in subjects
                   if (item.get("artifact_ref") or {}).get("sha256") == proposal_ref.get("sha256")]
        if not matches:
            raise ModelError("collaboration/adopt_proposal/proposal_ref",
                             "the decision does not name this proposal among its subject refs")
        if allowed and not any(item.get("projection") in allowed for item in matches):
            raise ModelError(
                "collaboration/adopt_proposal/proposal_ref",
                f"the decision names this proposal with projection "
                f"{sorted({item.get('projection') for item in matches})}; adopting a {schema} "
                f"needs one of {list(allowed)}")
        if schema not in ("narrative.v1", "content_plan.v2"):
            raise ModelError(
                "collaboration/adopt_proposal/proposal_ref",
                "only Narrative and ContentPlan proposals adopt through this action; "
                "Page candidates reuse the existing candidate adoption semantics")
        topic = decision.get("topic")
        allowed_topics = {"narrative.v1": ("direction",),
                          "content_plan.v2": ("manuscript", "direction", "tradeoff")}[schema]
        if topic not in allowed_topics:
            raise ModelError("collaboration/adopt_proposal/decision_ref",
                             f"a {schema} proposal is adopted by a {allowed_topics} decision, not {topic!r}")
        invalidated = []
        updated = dict(document)
        if schema == "narrative.v1":
            if proposal.get("project_id") != document["project_id"]:
                raise ModelError("collaboration/adopt_proposal/proposal_ref",
                                 "a proposal of another project cannot become this project's truth")
            if proposal.get("maturity") != "argument":
                raise ModelError("collaboration/adopt_proposal/proposal_ref",
                                 "a framing proposal sets no direction; adopt an argument Narrative")
            if document.get("narrative") and document["narrative"] != proposal_ref:
                invalidated.append({"ref": document["narrative"], "reason": "narrative_replaced"})
            from .variant_requests import require_fixed_narrative
            require_fixed_narrative(store, document, proposal_ref)
            updated["narrative"] = proposal_ref
            current_plan_ref = document.get("content_plan")
            if current_plan_ref:
                current_plan = store.read_object_json(current_plan_ref)
                if (current_plan.get("schema_version") == "content_plan.v2"
                        and current_plan.get("narrative_ref") not in (None, proposal_ref)):
                    invalidated.append({"ref": current_plan_ref, "reason": "plan_bound_to_previous_narrative"})
        else:
            if proposal.get("project_id") != document["project_id"]:
                raise ModelError("collaboration/adopt_proposal/proposal_ref",
                                 "a proposal of another project cannot become this project's truth")
            if proposal.get("mode") not in ("planned", "bound"):
                raise ModelError("collaboration/adopt_proposal/proposal_ref",
                                 "imported_mapping is not adopted through a proposal promotion")
            narrative_ref = proposal.get("narrative_ref")
            if narrative_ref is not None and narrative_ref != document.get("narrative"):
                raise ModelError("collaboration/adopt_proposal/proposal_ref",
                                 "the plan binds a Narrative that is not the current pointer")
            if document.get("content_plan") and document["content_plan"] != proposal_ref:
                invalidated.append({"ref": document["content_plan"], "reason": "plan_replaced"})
            updated["content_plan"] = proposal_ref
            if (proposal.get('input') or {}).get('speech_policy', {}).get('output') in (
                    'pptx_notes', 'separate_script', 'both'):
                models.require_writer(updated, 'rc3.v1')
        models.validate_document_semantics(updated)
        return collaboration.commit_collaboration_change(
            store, document, operation_id=operation_id, action=action, digest=digest,
            description=f"adopt proposal {proposal_ref['sha256'][:8]}",
            updated=updated,
            response={"adopted_refs": [proposal_ref], "invalidated_refs": invalidated,
                      "adopted_kind": schema, "creates_confirmation": False,
                      "authorizes_production": False})

    return locked(store)
