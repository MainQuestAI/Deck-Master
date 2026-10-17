"""Content preproduction review (content collaboration v1.2 CONTRACTS §6.3, §11.6).

A newly argued full deck needs a content review before real visual production.
This module owns the dispatch packet, the reviewer requirements and the
consumption/query view:

* the review packet carries the materials, the task facts and the **complete**
  candidate manuscript (full Narrative, full Plan, every Page's visible copy and
  speaker notes) — a reviewer never receives only the author's summary;
* ``independent_model_or_human`` needs an actual independent execution receipt
  (a different executor from the author) or a human with identity evidence.
  Without that capability the service returns ``needs_reviewer`` with the
  reviewable draft instead of quietly falling back to self-review;
* ``host_self`` is only accepted when an explicit, still-effective downgrade
  decision for this request exists; ``fidelity_only`` requires a confirmed
  manuscript mapping whose mainline is not being changed.

Cross-entry enforcement of the gate belongs to T04; this module provides
:func:`qualify_for_production` as the record-level decision to consume.
"""
from __future__ import annotations

from pathlib import Path

from . import models
from .editing import _current_artifact_digests
from .models import ModelError, canonical_json_bytes, sha256_bytes
from .store import Store

STAGE = "preproduction"

# CONTRACTS §11.6: the required units of a newly argued full deck, plus speech
# when the request has a speech output.
BASE_UNITS = ("argument", "page_copy", "progression")
SPEECH_UNIT = "speech"
FIDELITY_UNITS = ("page_copy", "progression")
ALLOWED_KINDS = BASE_UNITS + (SPEECH_UNIT,)

REQUIREMENTS = ("independent_model_or_human", "host_self", "fidelity_only")
CAPABILITY_KEYS = ("verified_user_events", "independent_review_receipts", "human_review_receipts")


def reviewer_capabilities(adapter_context=None) -> dict:
    """Read-only capability description; unknown or absent means False.

    A capability is only true for a registered authenticated provider's live
    channel. A completed receipt is separately required for result acceptance;
    advertising a healthy channel does not fabricate a future completion.
    """
    from .review_evidence import reviewer_capabilities as available
    return available(adapter_context)


def quality_profile(document) -> dict:
    region = document.get("collaboration") or {}
    return region.get("quality_profile") or {}


def _is_confirmed_manuscript_mapping(store, document) -> bool:
    plan_ref = document.get("content_plan")
    if not plan_ref:
        return False
    try:
        plan = store.read_object_json(plan_ref)
    except Exception:  # noqa: BLE001 - an unreadable plan is not a mapping
        return False
    return (plan.get("schema_version") == "content_plan.v2"
            and plan.get("mode") == "imported_mapping"
            and bool(plan.get("imported_manuscript")))


def _downgrade_decision_effective(store, document, override_ref) -> bool:
    """The explicit host_self downgrade must be a real, still-effective decision."""
    if not override_ref:
        return False
    try:
        record = store.read_object_json(override_ref)
    except Exception:  # noqa: BLE001
        return False
    if (record.get("schema_version") != "collaboration_decision.v1"
            or record.get("topic") != "policy"
            or record.get("disposition") != "accepted"
            or record.get("authority_mode") not in ("direct_user", "delegated")):
        return False
    value = record.get("value")
    if (not isinstance(value, dict) or value.get("content_review_requirement") != "host_self"
            or not isinstance(value.get("reason"), str) or not value["reason"].strip()
            or not _quality_decision_source_allowed(store, document, record)
            or not _quality_scope_covered(store, document, record)):
        return False
    from . import dependency_slices
    current_ref, _ = dependency_slices._resolve_current(store, document, "decisions", "decision_id", override_ref)
    if current_ref != override_ref:
        return False
    return dependency_slices.decision_effectiveness(store, document, override_ref)["effective"]


def _quality_decision_source_allowed(store, document, decision):
    """A stored claimed authority is not an authenticated/traceable instruction."""
    allowed = ("verified_user",) if (document.get("collaboration") or {}).get("authority_policy") == "verified_user" else ("host_attested", "verified_user")
    if (decision.get("evidence") or {}).get("assurance") not in allowed:
        return False
    if decision.get("authority_mode") == "direct_user":
        return True
    if decision.get("authority_mode") != "delegated":
        return False
    ref = decision.get("delegation_ref")
    seen = set()
    while ref:
        digest = ref.get("sha256")
        if digest in seen or len(seen) >= 8:
            return False
        seen.add(digest)
        try:
            grant = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unreadable authority cannot relax review
            return False
        if (grant.get("mode") != "delegate" or "policy" not in grant.get("delegated_topics", [])
                or (grant.get("evidence") or {}).get("assurance") not in allowed):
            return False
        ref = grant.get("parent_authorization_ref")
    return bool(seen)


def _quality_scope_covered(store, document, decision):
    from .eligibility import _covers, _page_coverage_from_binding, scope_page_ids
    request = (document.get("collaboration") or {}).get("request") or {}
    pages = [entry["page_id"] for entry in document.get("pages") or []]
    targets = {"subject": "pages", "page_ids": pages, "layers": ["review"]}
    return bool(pages) and decision.get("request_id") == request.get("request_id") and not request.get("closed") \
        and set(scope_page_ids(store, decision.get("scope")) or []) == set(pages) \
        and _covers(store, decision.get("scope"), targets) \
        and (_covers(store, request.get("scope"), targets)
             or _page_coverage_from_binding(store, request, targets, None, document))


def apply_requirement_decision(store, document, decision, decision_ref):
    """Atomically bind an explicit policy choice through the normal decision API.

    Defaults, proposals and unrelated policy records never select self-review.
    This changes neither production grants nor the human professional policy.
    """
    value = decision.get("value")
    if (decision.get("topic") != "policy" or decision.get("disposition") != "accepted"
            or not isinstance(value, dict) or "content_review_requirement" not in value):
        return document
    requirement = value["content_review_requirement"]
    if requirement not in ("host_self", "independent_model_or_human"):
        raise ModelError("decision/value/content_review_requirement", "choose independent_model_or_human or explicit host_self")
    if (not isinstance(value.get("reason"), str) or not value["reason"].strip()
            or not _quality_decision_source_allowed(store, document, decision)):
        raise ModelError("decision/value", "review policy requires an explicit user instruction or policy delegation and a nonempty reason")
    if requirement == "host_self" and not _quality_scope_covered(store, document, decision):
        raise ModelError("decision/scope", "self-review must explicitly cover every current manuscript page's review layer within this request")
    region = document["collaboration"]
    updated = {**document, "collaboration": {**region, "quality_profile": {
        "content_review_requirement": requirement, "requirement_origin": "explicit_decision",
        "override_decision_ref": decision_ref}}}
    if quality_profile(document).get("content_review_requirement") != requirement:
        refs = []
        for ref in document.get("tasks") or []:
            task = store.read_object_json(ref)
            if (task.get("kind") == "review" and task.get("review_stage") == STAGE
                    and task.get("status") in ("awaiting_host", "running", "queued")
                    and (task.get("collaboration_binding") or {}).get("request_id") == decision["request_id"]):
                task = {**task, "status": "superseded", "updated_at": decision["created_at"]}
                ref = store.put_json_object(task)
            refs.append(ref)
        updated["tasks"] = refs
    models.validate_collaboration_region(updated["collaboration"])
    return updated


def requirement_state(store, document) -> dict:
    """The effective preproduction requirement for this project.

    ``fidelity_only`` is only effective for a confirmed-manuscript mapping that
    does not change the mainline; otherwise the profile's declared requirement
    stands (and a host_self downgrade without its decision is ineffective).
    """
    profile = quality_profile(document)
    declared = profile.get("content_review_requirement") or "independent_model_or_human"
    origin = profile.get("requirement_origin")
    override_ref = profile.get("override_decision_ref")
    effective = declared
    reasons: list[str] = []
    if declared == "host_self" and not _downgrade_decision_effective(store, document, override_ref):
        effective = "independent_model_or_human"
        reasons.append("host_self_downgrade_decision_missing_or_ineffective")
    if declared == "fidelity_only" and not _is_confirmed_manuscript_mapping(store, document):
        effective = "independent_model_or_human"
        reasons.append("fidelity_only_requires_a_confirmed_manuscript_mapping")
    return {"declared": declared, "origin": origin, "override_decision_ref": override_ref,
            "effective": effective, "reasons": reasons}


def required_units(store, document) -> list[str]:
    """The review units this project's preproduction review must cover."""
    state = requirement_state(store, document)
    if state["effective"] == "fidelity_only":
        return list(FIDELITY_UNITS)
    units = list(BASE_UNITS)
    plan_ref = document.get("content_plan")
    speech_required = False
    if plan_ref:
        try:
            plan = store.read_object_json(plan_ref)
            policy = ((plan.get("input") or {}).get("speech_policy") or {})
            speech_required = policy.get("mode") in ("cues", "verbatim")
        except Exception:  # noqa: BLE001
            speech_required = False
    if speech_required:
        units.append(SPEECH_UNIT)
    return units


# ---------------------------------------------------------------------------
# The review packet (AC-M05)


def build_review_packet(store, document, *, page_ids=None, required=None,
                        requirement=None) -> dict:
    """Materials + task facts + the complete candidate manuscript.

    Nothing here is a summary of the author's conclusion: the packet embeds the
    full stored Narrative, the full Plan input and every reviewed Page's visible
    copy, speaker notes and mapping, plus each material's complete extract.
    """
    pages = []
    for entry in document.get("pages") or []:
        page_id = entry["page_id"]
        if page_ids is not None and page_id not in page_ids:
            continue
        page = store.read_object_json(entry["page"])
        pages.append({"page_id": page_id, "page_ref": entry["page"],
                      "customer_visible": page.get("customer_visible") or {},
                      "speaker_notes": page.get("speaker_notes") or "",
                      "content_mapping": page.get("content_mapping"),
                      "visual_spec": page.get("visual_spec") or {}})
    narrative = None
    if document.get("narrative"):
        narrative = store.read_object_json(document["narrative"])
    plan = None
    if document.get("content_plan"):
        plan = store.read_object_json(document["content_plan"])
    materials = []
    for source in document.get("sources") or []:
        extract = None
        if source.get("extract"):
            try:
                extract = store.read_object_json(source["extract"])
            except Exception:  # noqa: BLE001 - an unreadable extract stays labelled
                extract = None
        materials.append({"source_id": source.get("source_id"), "name": source.get("name"),
                          "format": source.get("format"),
                          "original_sha256": source.get("original_sha256"),
                          "usage_note": source.get("usage_note") or "",
                          "restriction": source.get("restriction") or "",
                          "extract_ref": source.get("extract"), "extract": extract})
    return {
        "schema_version": "content_review_packet.v1",
        "project_id": document["project_id"],
        "revision_id": document["revision_id"],
        "task": document.get("task") or {},
        "content_basis": document.get("content_basis"),
        "input_digest": models.compute_input_digest(document),
        "materials": materials,
        "narrative": narrative,
        "plan": plan,
        "manuscript": {"pages": pages, "page_order": [p["page_id"] for p in pages]},
        "required_units": list(required if required is not None else required_units(store, document)),
        "requirement": requirement,
        "instruction": (
            "Judge the task fit, the argument, the evidence boundaries, the page coverage, "
            "the progression and the use budgets against the materials and this complete "
            "candidate manuscript. Return one review record per required unit with subjects "
            "and dependencies binding exactly these objects; do not replace the manuscript "
            "with a summary of the author's conclusion."),
    }


def packet_digest(packet: dict) -> str:
    return sha256_bytes(canonical_json_bytes(packet))


# ---------------------------------------------------------------------------
# Independence


def _subjects_digest(subjects) -> str:
    ordered = sorted(((ref.get("path"), ref.get("sha256")) for ref in subjects or []),
                     key=lambda pair: (pair[0] or "", pair[1] or ""))
    return sha256_bytes(canonical_json_bytes(ordered))


def author_execution_refs(store, document, subjects) -> set[str]:
    """Authors of retained current content, including earlier Page-copy writers.

    Only adopted refs on the committed ancestry count. Retained visible atoms
    and notes keep their author across a notes-only or partial copy update;
    replacing all their content ends that lineage. Proposal refs never became
    current, so cannot invent authorship. Missing lineage is an explicit gap.
    """
    from .content import visible_atoms
    from .store import StoreError

    def key(ref):
        return (ref.get("path"), ref.get("sha256"))

    def tokens(obj):
        schema = obj.get("schema_version")
        if schema == "deck_page_package.v2":
            values = {("visible", atom["atom_id"], atom["text"]) for atom in visible_atoms(obj)
                      if str(atom.get("text") or "").strip()}
            values.update(("notes", line.strip()) for line in (obj.get("speaker_notes") or "").splitlines() if line.strip())
            if not values:
                values.add(("visual", canonical_json_bytes(obj.get("visual_spec") or {}).decode()))
            return values
        if schema == "narrative.v1":
            return {("node", node["node_id"], canonical_json_bytes(node).decode()) for node in obj.get("nodes", [])}
        if schema in ("content_plan.v1", "content_plan.v2"):
            return {("plan_input", canonical_json_bytes(obj.get("input") or {}).decode())}
        return set()

    wanted = {key(ref) for ref in subjects or []}
    retained = {}
    for ref in subjects or []:
        try:
            obj = store.read_object_json(ref)
        except (ValueError, UnicodeError):
            continue  # a final binary subject has no editorial ancestry
        except (StoreError, OSError) as exc:
            raise ModelError("content_review/author_lineage", "reviewed content is unreadable") from exc
        if obj.get("schema_version") == "deck_page_package.v2":
            retained[("page", obj["page_id"])] = tokens(obj)
        elif obj.get("schema_version") == "narrative.v1":
            retained[("narrative", None)] = tokens(obj)
        elif obj.get("schema_version") in ("content_plan.v1", "content_plan.v2"):
            retained[("content_plan", None)] = tokens(obj)
    adopted = set(wanted)
    revision = document.get("revision_id")
    seen = set()
    task_refs = {}
    while revision:
        if revision in seen:
            raise ModelError("content_review/author_lineage", "cyclic committed ancestry")
        seen.add(revision)
        try:
            snap = document if revision == document["revision_id"] else store.load_document(revision)
            task_refs.update({key(ref): ref for ref in snap.get("tasks") or []})
            pointers = {("page", entry["page_id"]): entry["page"] for entry in snap.get("pages") or []}
            pointers.update({(role, None): snap[role] for role in ("narrative", "content_plan") if snap.get(role)})
            for identity in list(retained):
                ref = pointers.get(identity)
                if not ref:
                    del retained[identity]
                    continue
                retained[identity].intersection_update(tokens(store.read_object_json(ref)))
                if retained[identity]:
                    adopted.add(key(ref))
                else:
                    del retained[identity]
        except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
            raise ModelError("content_review/author_lineage", "committed author lineage requires recovery") from exc
        revision = snap.get("parent_revision_id")
        if not retained:
            break
    found = set()
    for ref in task_refs.values():
        try:
            task = store.read_object_json(ref)
        except (StoreError, OSError, ValueError, TypeError) as exc:
            raise ModelError("content_review/author_lineage", "Task author facts require recovery") from exc
        if {key(item) for item in task.get("result_refs") or []} & adopted:
            found.add(task.get("execution_ref") or task["task_id"])
    return found


def _independent_receipt(adapter_context, review, subjects, forbidden_executors):
    """A trusted independent execution receipt for exactly these subjects."""
    from .review_evidence import context_payload
    context = context_payload(adapter_context)
    receipts = context.get("independent_review_receipts") or []
    reviewer = review.get("reviewer") or {}
    execution_ref = reviewer.get("execution_ref")
    digest = _subjects_digest(subjects)
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("subjects_sha256") != digest:
            continue
        if execution_ref and receipt.get("executor_ref") != execution_ref:
            continue
        if not receipt.get("executor_ref") or receipt.get("executor_ref") in forbidden_executors:
            continue
        if not receipt.get("receipt_ref"):
            continue
        return receipt
    return None


def _human_receipt(adapter_context, review, subjects):
    from .review_evidence import context_payload
    context = context_payload(adapter_context)
    receipts = context.get("human_review_receipts") or []
    digest = _subjects_digest(subjects)
    identity = (review.get("reviewer") or {}).get("identity_receipt")
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("subjects_sha256") != digest or not receipt.get("receipt_ref"):
            continue
        if identity and (receipt.get("event_id") != identity.get("event_id")
                         or receipt.get("reviewer_id") != identity.get("reviewer_id")):
            continue
        return receipt
    return None


# ---------------------------------------------------------------------------
# Dispatch


def _review_pages(store, document, page_ids=None) -> list[str]:
    ids = [entry["page_id"] for entry in document.get("pages") or []]
    if page_ids is not None:
        outside = sorted(set(page_ids) - set(ids))
        if outside:
            raise ModelError("content_review/page_ids", f"pages not in the current deck: {outside}")
        return list(page_ids)
    return ids


def dispatch_preproduction_review(project, *, page_ids=None, adapter_context=None,
                                  instruction=None) -> dict:
    """Open the preproduction review task, or return an honest needs_reviewer.

    ``needs_reviewer`` carries the reviewable draft (the packet) so the caller
    can still hand the user a manuscript; it never downgrades the requirement
    on its own.
    """
    from . import service

    store = Store(Path(project).expanduser())
    document = store.load_document()
    if not models.collaboration_required(document):
        raise ModelError("content_review",
                         "migration_required: preproduction review needs the collaboration.v1 writer")
    state = requirement_state(store, document)
    pages = _review_pages(store, document, page_ids)
    if not pages:
        raise ModelError("content_review/pages", "there is no manuscript to review yet")
    units = required_units(store, document)
    packet = build_review_packet(store, document, page_ids=pages, required=units,
                                 requirement=state["effective"])
    packet_ref = store.put_json_object(packet)
    capabilities = reviewer_capabilities(adapter_context)
    if (state["effective"] == "independent_model_or_human"
            and not (capabilities["independent_review_receipts"]
                     or capabilities["human_review_receipts"])):
        return {
            "status": "needs_reviewer", "stage": STAGE, "requirement": state["effective"],
            "requirement_state": state,
            "review_draft_ref": packet_ref, "review_draft": packet,
            "units": units,
            "reason": "no independent reviewer capability is available; a self-declared "
                      "reviewer name or a random execution_ref is not independence",
            "next_action": "provide_reviewer_or_record_downgrade_decision",
        }
    executor_type = "external_reviewer" if state["effective"] == "independent_model_or_human" else "host"
    task = service.open_host_task(
        store, kind="review", page_ids=pages, review_stage=STAGE,
        instruction=instruction or (
            "内容前置审查：读取 packet（材料 + 任务事实 + 完整候选稿），按 required units "
            f"({', '.join(units)}) 各自提交一条 review 记录。"
            "subjects/dependencies 必须绑定当前 Narrative、ContentPlan 与本次全部 Page 及来源；"
            "发现必须定位到具体节点/页面/atom 与依据。"),
        extra_inputs=[packet_ref], executor_type=executor_type,
        phase="review")
    return {"status": "review_dispatched", "stage": STAGE, "requirement": state["effective"],
            "requirement_state": state, "review_draft_ref": packet_ref,
            "units": units, "task": task, "executor_type": executor_type,
            "next_action": "submit_preproduction_review"}


# ---------------------------------------------------------------------------
# Acceptance (called from the review result path)


def _require_unit_coverage(store, document, reviews) -> None:
    units = set(required_units(store, document))
    submitted = {review.get("kind") for review in reviews}
    unknown = sorted(submitted - set(ALLOWED_KINDS))
    if unknown:
        raise _envelope_error("review/kind",
                              f"preproduction reviews cover {list(ALLOWED_KINDS)}; got {unknown}")
    missing = sorted(units - submitted)
    if missing:
        raise _envelope_error("review/kind",
                              f"preproduction review is incomplete; missing units: {missing}")


def _envelope_error(where, message):
    from .tasks import EnvelopeError
    return EnvelopeError(f"review/{where}", message)


def _require_subject_binding(store, document, review, page_ids) -> None:
    cited = {(ref.get("path"), ref.get("sha256")) for ref in review.get("subjects") or []}
    required: set[tuple] = set()
    for pointer in (document.get("narrative"), document.get("content_plan")):
        if pointer:
            required.add((pointer["path"], pointer["sha256"]))
    entries = {entry["page_id"]: entry for entry in document.get("pages") or []}
    for page_id in page_ids:
        entry = entries.get(page_id)
        if entry:
            required.add((entry["page"]["path"], entry["page"]["sha256"]))
    missing = sorted(pair for pair in required if pair not in cited)
    if missing:
        raise _envelope_error(
            "subjects",
            "a preproduction review must cite the current Narrative, ContentPlan and every "
            f"reviewed Page; missing {[pair[1][:8] for pair in missing]}")
    digests = _current_artifact_digests(store, document)
    deps = {f"{dep['kind']}:{dep['identity']}": dep.get("sha256")
            for dep in review.get("dependencies") or []}
    expected = {}
    if document.get("narrative"):
        expected["content:narrative"] = document["narrative"]["sha256"]
    if document.get("content_plan"):
        expected["content:content_plan"] = document["content_plan"]["sha256"]
    for page_id in page_ids:
        key = f"content:page:{page_id}"
        if key in digests:
            expected[key] = digests[key]
    for source in document.get("sources") or []:
        extract = source.get("extract")
        if extract:
            expected[f"source:{source.get('source_id')}"] = extract["sha256"]
    wrong = sorted(key for key, value in expected.items() if deps.get(key) != value)
    if wrong:
        raise _envelope_error(
            "dependencies",
            f"preproduction review dependencies must bind the current objects: {wrong}")


def _reviewer_type(review) -> str:
    return (review.get("reviewer") or {}).get("type")


def validate_preproduction_result(store, document, task, envelope, *, adapter_context=None) -> dict:
    """Record-level preproduction gate for a submitted review result.

    Returns the accepted posture (requirement, reviewers, grants) so the caller
    can report it; raises EnvelopeError for a submission that pretends to be an
    independence it does not have.
    """
    reviews = envelope.get("reviews") or []
    if not reviews:
        raise _envelope_error("review", "a preproduction task returns review records")
    for review in reviews:
        if review.get("review_stage") != STAGE:
            raise _envelope_error("review_stage", "preproduction results carry review_stage=preproduction")
    state = requirement_state(store, document)
    _require_unit_coverage(store, document, reviews)
    page_ids = list(task.get("scope_pages") or [])
    capabilities = reviewer_capabilities(adapter_context)
    accepted_reviewers = []
    if state["effective"] == "independent_model_or_human" and adapter_context is not None:
        from .review_evidence import validate_review_context
        validate_review_context(adapter_context, store, document, task, envelope)
    for index, review in enumerate(reviews):
        reviewer_type = _reviewer_type(review)
        subjects = review.get("subjects") or []
        _require_subject_binding(store, document, review, page_ids)
        if state["effective"] == "independent_model_or_human":
            if reviewer_type in ("human_internal", "human_external"):
                receipt = _human_receipt(adapter_context, review, subjects)
                if receipt is None:
                    raise _envelope_error(
                        "reviewer",
                        f"reviews[{index}]: a human preproduction review needs a verifiable "
                        "identity/execution receipt; a claimed reviewer id is not evidence")
                accepted_reviewers.append({"type": reviewer_type, "receipt": receipt})
                continue
            if reviewer_type != "independent_host" or not capabilities["independent_review_receipts"]:
                raise _envelope_error(
                    "reviewer",
                    f"reviews[{index}]: needs_reviewer: this project requires an independent "
                    "model or human review; a self-declared reviewer name or a random "
                    "execution_ref does not satisfy it")
            if not (review.get("reviewer") or {}).get("independence_confirmed"):
                raise _envelope_error("reviewer/independence_confirmed",
                                      f"reviews[{index}]: an independent review confirms its independence")
            forbidden = author_execution_refs(store, document, subjects)
            receipt = _independent_receipt(adapter_context, review, subjects, forbidden)
            if receipt is None:
                raise _envelope_error(
                    "reviewer/execution_ref",
                    f"reviews[{index}]: no trusted independent execution receipt matches these "
                    "subjects; the author cannot be recorded as an independent reviewer")
            accepted_reviewers.append({"type": reviewer_type, "receipt": receipt})
            continue
        if state["effective"] == "host_self":
            if reviewer_type not in ("host_self", "tool", "independent_host",
                                     "human_internal", "human_external"):
                raise _envelope_error("reviewer", f"reviews[{index}]: unknown reviewer type")
            accepted_reviewers.append({"type": reviewer_type, "receipt": None})
            continue
        # fidelity_only: an independent claim is not required, but the review
        # must stay a fidelity check on the confirmed manuscript.
        if reviewer_type in ("human_internal", "human_external", "independent_host", "host_self", "tool"):
            accepted_reviewers.append({"type": reviewer_type, "receipt": None})
            continue
        raise _envelope_error("reviewer", f"reviews[{index}]: unknown reviewer type {reviewer_type!r}")
    return {"stage": STAGE, "requirement": state["effective"], "requirement_state": state,
            "units": sorted({review.get("kind") for review in reviews}),
            "reviewers": accepted_reviewers,
            "needs_reviewer": False}


# ---------------------------------------------------------------------------
# Consumption and query


def _preproduction_reviews(store, document) -> list[dict]:
    """Immutable preproduction history, including stale finding owners."""
    records = []
    for ref in document.get("reviews") or []:
        try:
            review = store.read_object_json(ref)
        except Exception:  # noqa: BLE001
            continue
        if review.get("review_stage") != STAGE:
            continue
        records.append({"review_ref": ref, "review": review})
    return records


def _unit_dependency_equivalent(store, document, review, key, digest):
    """Interpret real immutable subjects through this unit's editorial inputs.

    This never changes a review or promotes its assurance. Visual bytes and
    speech retain their own checks; design-only layout does not change copy.
    """
    import copy
    from .design_requirements import page_semantic_projection, plan_global_projection
    from .models import canonical_json_bytes, sha256_bytes
    from .store import StoreError
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    old_ref = {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}
    try:
        before = store.read_object_json(old_ref)
        if key == 'content:content_plan' and document.get('content_plan'):
            after = store.read_object_json(document['content_plan'])
            if before.get('schema_version') != after.get('schema_version'):
                return False
            if before.get('schema_version') != 'content_plan.v2':
                return False
            ids = {dep['identity'].split(':', 1)[1] for dep in review.get('dependencies', [])
                   if dep.get('kind') == 'content' and dep.get('identity', '').startswith('page:')}
            def projected(plan):
                roles = copy.deepcopy([item for item in plan['input']['page_roles'] if item['page_id'] in ids])
                for role in roles:
                    role.pop('content_profile', None); role.pop('density_rationale', None)
                    if review.get('kind') != 'speech': role.pop('timing_seconds', None)
                return {'global': plan_global_projection(plan), 'roles': roles,
                        'issues': plan['input']['issues'], 'tradeoff_issue_ids': plan['input']['tradeoff_issue_ids']}
            return projected(before) == projected(after)
        if key.startswith('content:page:'):
            pid = key.split(':', 2)[2]
            entry = next(item for item in document['pages'] if item['page_id'] == pid)
            after = store.read_object_json(entry['page'])
            def projected(page):
                mapping = copy.deepcopy(page.get('content_mapping'))
                if mapping is not None and review.get('kind') != 'speech': mapping.pop('speech_segments', None)
                result = {'page': page_semantic_projection(page), 'content_mapping': mapping}
                if review.get('kind') == 'speech': result['speaker_notes'] = page.get('speaker_notes')
                return result
            return before.get('page_id') == pid and projected(before) == projected(after)
    except (StoreError, OSError, ValueError, KeyError, TypeError, StopIteration):
        return False
    return False


def _applicable_reviews(store, document, page_ids, *, records=None) -> list[dict]:
    """Preproduction reviews that can satisfy a current manuscript unit."""
    digests = _current_artifact_digests(store, document)
    applicable = []
    if records is None:
        records = _preproduction_reviews(store, document)
    for item in records:
        review = item["review"]
        notes_aliases = (digests.get('_preproduction_notes_aliases') or {}) if review.get('kind') != 'speech' else {}
        deps = {f"{dep['kind']}:{dep['identity']}": dep.get("sha256")
                for dep in review.get("dependencies") or []}
        stale = [key for key, value in deps.items()
                 if key in digests and digests[key] != value and value not in notes_aliases.get(key, set())
                 and not _unit_dependency_equivalent(store, document, review, key, value)]
        if document.get("narrative") and deps.get("content:narrative") != document["narrative"]["sha256"]:
            stale.append("content:narrative")
        if (document.get("content_plan") and
                deps.get("content:content_plan") != document["content_plan"]["sha256"] and
                deps.get("content:content_plan") not in notes_aliases.get('content:content_plan', set()) and
                not _unit_dependency_equivalent(store, document, review, 'content:content_plan', deps.get('content:content_plan'))):
            stale.append("content:content_plan")
        if page_ids and not set(page_ids) <= {str(dep.get("identity", "")).split(":", 1)[-1]
                                             for dep in review.get("dependencies") or []
                                             if dep.get("kind") == "content"}:
            stale.append("content:page")
        if stale:
            continue
        applicable.append(item)
    return applicable


def preproduction_status(store, document, *, adapter_context=None, page_ids=None) -> dict:
    """Whether the current manuscript has an applicable preproduction review."""
    state = requirement_state(store, document)
    units = required_units(store, document)
    if not document.get("pages"):
        return {"stage": STAGE, "status": "no_manuscript", "requirement": state["effective"],
                "requirement_state": state, "units": units, "satisfied_units": [],
                "missing_units": units, "review_refs": [], "blocking_findings": [],
                "next_action": "write_manuscript"}
    ids = [entry["page_id"] for entry in document.get("pages") or []]
    if page_ids is None:
        page_ids = ids
    history = _preproduction_reviews(store, document)
    applicable = _applicable_reviews(store, document, page_ids, records=history)
    satisfied = sorted({item["review"].get("kind") for item in applicable
                        if item["review"].get("status") == "pass"})
    missing = sorted(set(units) - set(satisfied))
    blocking = []
    from .review import finding_closed, open_findings, pending_judgments
    records = [{**item["review"], "ref": item["review_ref"]} for item in history]
    artifacts = _current_artifact_digests(store, document)
    scoped_pages = set(page_ids) & set(ids)
    for item in history:
        if item["review"].get("kind") not in units:
            continue
        owner = {**item["review"], "ref": item["review_ref"]}
        for finding in open_findings(item["review"]) + pending_judgments(item["review"]):
            # Freshness determines whether a pass can satisfy a unit; it does
            # not erase an unresolved defect on a current page. Retired pages,
            # out-of-scope pages and no-longer-required units do not block this
            # query. Deck-level findings remain relevant to a non-empty scope.
            if finding.get("page_id") is None:
                if not scoped_pages:
                    continue
            elif finding.get("page_id") not in scoped_pages:
                continue
            # Consume the same explicit, current replacement semantics as the
            # receiver and final/page review. A separate pass never closes an
            # older finding; its immutable record remains available as evidence.
            if finding_closed(records, owner, finding, artifacts):
                continue
            blocking.append({"review_id": item["review"].get("review_id"),
                             "kind": item["review"].get("kind"),
                             "finding_id": finding.get("finding_id") or finding.get("id"),
                             "impact": finding.get("impact"),
                             "message": finding.get("message") or finding.get("detail")})
    if missing:
        status = "missing"
    elif blocking:
        status = "blocked"
    else:
        status = "pass"
    next_action = {"pass": "proceed_to_visual_production",
                   "missing": "dispatch_preproduction_review",
                   "blocked": "resolve_blocking_findings",
                   "no_manuscript": "write_manuscript"}[status]
    return {"stage": STAGE, "status": status, "requirement": state["effective"],
            "requirement_state": state, "units": units, "satisfied_units": satisfied,
            "missing_units": missing, "review_refs": [item["review_ref"] for item in applicable],
            "blocking_findings": blocking, "next_action": next_action}


def qualify_for_production(store, document, *, adapter_context=None, page_ids=None) -> dict:
    """The record-level answer for 'may this manuscript enter real production'.

    T04 consumes this from every entry point; the gate here is derived from the
    stored review records and the current controls, never stored twice.
    """
    status = preproduction_status(store, document, adapter_context=adapter_context,
                                  page_ids=page_ids)
    gaps: list[str] = []
    needs_reviewer = False
    if status["status"] == "missing" and status["requirement"] == "independent_model_or_human":
        capabilities = reviewer_capabilities(adapter_context)
        if not (capabilities["independent_review_receipts"] or capabilities["human_review_receipts"]):
            needs_reviewer = True
            gaps.append("needs_reviewer")
    if status["status"] == "blocked":
        gaps.append("open_blocking_findings")
    return {"allowed": status["status"] == "pass",
            "stage": STAGE,
            "requirement": status["requirement"],
            "needs_reviewer": needs_reviewer,
            "reason_codes": gaps,
            "status": status["status"],
            "missing_units": status["missing_units"],
            "blocking_findings": status["blocking_findings"],
            "next_action": status["next_action"],
            "professional_review_required_for_delivery":
                bool((document.get("policy") or {}).get("professional_review_required_for_delivery")),
            "note": "A host_self downgrade of the content review never relaxes the human "
                    "professional-review policy for delivery."}
