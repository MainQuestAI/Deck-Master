"""Shared RC3 project/request and imported manuscript initialization."""
from __future__ import annotations

import copy
import uuid

from . import collaboration, content, models
from .content_plan import build_v2_plan
from .store import ConflictError


def collaboration_region(*, imported=False):
    return {"schema_version": "collaboration.v1", "authority_policy": "traceable",
            "quality_profile": {"content_review_requirement": "fidelity_only" if imported else "independent_model_or_human",
                "requirement_origin": "confirmed_manuscript" if imported else "default_new_argument",
                "override_decision_ref": None}, "request": None, "decisions": [], "authorizations": []}


def instruction(store, value, *, locator):
    ref = store.put_blob(models.canonical_json_bytes(value), ext="json")
    return {"kind": "host_attested_instruction", "source_ref": ref,
            "source_locator": locator, "actor_id": None, "transport_receipt_ref": None,
            "presentation_ref": None}


def request_defaults(store, document, *, supplied=None, page_ids=(), imported=False):
    source = instruction(store, {"task": document["task"], "sources": document["sources"],
        "request_input": supplied, "imported_manuscript": imported}, locator="create:actual-input")
    value = copy.deepcopy(supplied or {})
    value.setdefault("intent", "full_deck")
    value.setdefault("content_intent", None)
    value.setdefault("instruction_evidence", source)
    value.setdefault("scope", {"subject": "deck", "page_ids": list(page_ids),
        "page_manifest_ref": None, "external_artifact_ref": None,
        "layers": ["narrative", "plan", "page_copy", "speech", "design", "blueprint", "svg", "review", "output"],
        "allow_page_membership_change": True, "allow_page_order_change": True, "purpose": "working"})
    return value


def imported_plan(store, document, pages, source_ref, evidence, *, preserve_mainline=True, outline=None):
    order = [entry["page_id"] for entry in pages]
    plan_input = {"schema_version": "content_plan_input.v2", "chapters": [],
        "page_order": order, "page_roles": [],
        "page_budget": {"exact": None, "target": None, "max": document["task"].get("page_limit")},
        "time_budget": {"total_seconds": None, "speaking_seconds": None,
                        "interaction_seconds": None, "constraint": "unspecified"},
        "speech_policy": {"mode": "none", "source": "default", "output": "none"},
        "issues": [], "tradeoff_issue_ids": []}
    unresolved = ["Original narrative relationships and source claims were not independently verified; original bytes remain in source_ref"]
    if outline is not None:
        models.validate_schema('content_plan_input', outline)
        if outline['schema_version'] == 'content_plan_input.v2':
            if outline['page_order'] != order:
                raise models.ModelError('draft/content_plan/page_order', 'the imported Plan must match the actual manuscript order')
            plan_input = copy.deepcopy(outline)
            for role in plan_input['page_roles']:
                role['narrative_node_ids'] = []
                role['required_qualifications'] = []
                role['source_links'] = []
        else:
            goals = {goal['page_id']: goal for goal in outline['goals']}
            if set(goals) != set(order) or len(goals) != len(outline['goals']):
                raise models.ModelError('draft/content_plan/goals', 'goals must cover the actual imported Pages exactly once')
            goal_ids = {goal['goal_id']: goal['page_id'] for goal in outline['goals']}
            plan_input['chapters'] = [{'chapter_id': chapter['chapter_id'], 'title': chapter['title'],
                'page_ids': [goal_ids[identity] for identity in chapter['goal_ids']]} for chapter in outline['chapters']]
            plan_input['page_roles'] = [{'page_id': pid, 'role': goals[pid]['purpose'],
                'audience_question': 'Not recorded in the imported outline',
                'intended_takeaway': goals[pid]['purpose'], 'narrative_node_ids': [], 'source_links': [],
                'required_qualifications': [], 'content_profile': 'mixed',
                'density_rationale': 'Imported purpose retained; density has not been independently assessed',
                'timing_seconds': None, 'transition_to_next': None} for pid in order]
            unresolved.extend(outline.get('unresolved_facts') or [])
            unresolved.extend(f"{pid}: {item}" for pid in order for item in goals[pid].get('unresolved_facts', []))
    return build_v2_plan(store, document, {"task_id": None, "intent": "import_draft",
        "dispatch_revision": document["revision_id"], "input_digest": models.compute_input_digest(document)},
        plan_input, pages, narrative_ref=None, mode="imported_mapping", require_role_mapping=False,
        imported_manuscript={"source_ref": source_ref,
            "claimed_confirmation_evidence": evidence, "preserve_mainline": preserve_mainline,
            "unresolved_mapping_items": unresolved})


def prepare_manuscript(store, doc, payload, *, evidence=None, preserve_mainline=True, adapter_context=None, digest=None):
    """Normalize fixed input bytes; the owning transaction alone publishes them.

    New-project initialization uses this before any public current pointer exists.
    Existing-project import still requires its normal CAS/scope gate first.
    """
    checked = [copy.deepcopy(content.check_page(page)) for page in payload["pages"]]
    ids = [page["page_id"] for page in checked]
    order = payload.get("page_order") or ids
    if len(ids) != len(set(ids)) or len(order) != len(ids) or set(order) != set(ids):
        raise models.ModelError("draft/page_order", "must name every unique Page exactly once")
    digest = digest or collaboration.payload_digest("manuscript.import", {"draft": payload,
        "instruction_evidence": evidence, "preserve_mainline": preserve_mainline})
    source_ref = store.put_blob(models.canonical_json_bytes(payload), ext="json")
    declared = evidence or {"kind": "approved_document", "source_ref": source_ref,
        "source_locator": "import:actual-manuscript", "actor_id": None,
        "transport_receipt_ref": None, "presentation_ref": None}
    resolved = collaboration.resolve_evidence(declared, adapter_context, store=store,
        where="draft/instruction_evidence", action_binding=digest,
        project_id=doc["project_id"], request_id=((doc.get("collaboration") or {}).get("request") or {}).get("request_id"))
    collaboration._require_stored_evidence_refs(store, resolved, "draft/evidence")
    by_id = {}
    for page in checked:
        notes = page.get("speaker_notes") or ""
        old_mapping = page.get('content_mapping') or {}
        segments = copy.deepcopy(old_mapping.get('speech_segments') or [])
        for segment in segments:
            segment['narrative_node_ids'] = []
        page["content_mapping"] = {"narrative_ref": None, "plan_role_page_id": page["page_id"],
            "visible_links": [{"element_ref": atom, "narrative_node_ids": [], "source_links": []}
                              for atom in sorted(content.atom_ids(page))],
            "speech_segments": segments or ([{"segment_id": "imported-notes", "start_codepoint": 0,
                "end_codepoint": len(notes), "narrative_node_ids": [], "kind": "cue",
                "estimated_seconds": None}] if notes else [])}
        content.check_page(page)
        by_id[page["page_id"]] = {"page_id": page["page_id"], "page": store.put_json_object(page),
            "blueprint": None, "svg": None, "svg_preview": None, "ppt_preview": None}
    pages = [by_id[pid] for pid in order]
    plan_ref = imported_plan(store, doc, pages, source_ref, resolved,
                             preserve_mainline=preserve_mainline, outline=payload.get('content_plan'))
    region = copy.deepcopy(doc["collaboration"])
    if preserve_mainline:
        region["quality_profile"] = collaboration_region(imported=True)["quality_profile"]
    updated = {**doc, "pages": pages, "content_plan": plan_ref, "narrative": None,
        "collaboration": region, "outputs": dict.fromkeys(doc["outputs"]),
        "content_basis": {"input_digest": models.compute_input_digest(doc),
                          "input_revision_id": None, "resolved_by_task_id": None}}
    return updated, {"source_ref": source_ref, "plan_ref": plan_ref, "assurance": resolved["assurance"]}


def adopt_manuscript(store, payload, *, base_revision, operation_id, evidence=None,
                     preserve_mainline=True, adapter_context=None):
    """One source-bound Page/Plan/current swap; no old compose Task is opened."""
    from . import eligibility
    checked = [copy.deepcopy(content.check_page(page)) for page in payload["pages"]]
    ids = [page["page_id"] for page in checked]
    order = payload.get("page_order") or ids
    if len(ids) != len(set(ids)) or len(order) != len(ids) or set(order) != set(ids):
        raise models.ModelError("draft/page_order", "must name every unique Page exactly once")
    digest = collaboration.payload_digest("manuscript.import", {"draft": payload,
        "instruction_evidence": evidence, "preserve_mainline": preserve_mainline})
    with store._locked():
        doc = store.load_document()
        replay = collaboration.replay_or_conflict(store, doc, operation_id, "manuscript.import", digest)
        if replay:
            return replay
        if base_revision != doc["revision_id"]:
            raise ConflictError("base_revision", "manuscript import requires the current base")
        eligibility.guard(store, doc, "import_draft", context={"targets": {
            "page_ids": ids, "layers": ["page_copy", "plan"]}})
        updated, normalized = prepare_manuscript(store, doc, payload, evidence=evidence,
            preserve_mainline=preserve_mainline, adapter_context=adapter_context, digest=digest)
        source_ref, plan_ref = normalized["source_ref"], normalized["plan_ref"]
        pages = updated["pages"]
        # Pending work belongs to the replaced draft, never to the imported one.
        updated["tasks"] = [store.put_json_object({**task, "status": "superseded"})
            if task["status"] in ("running", "awaiting_host", "queued") else ref
            for ref in doc["tasks"] for task in [store.read_object_json(ref)]]
        models.require_writer(updated, "rc3-entry.v1")
        return collaboration.commit_collaboration_change(store, doc, operation_id=operation_id,
            action="manuscript.import", digest=digest, description="Import fixed manuscript with source mapping",
            updated=updated, response={"page_refs": [entry["page"] for entry in pages],
                "plan_ref": plan_ref, "source_ref": source_ref, "result_refs": [plan_ref],
                "narrative_ref": None, "creates_confirmation": False,
                "authorizes_production": False, "assurance": normalized["assurance"]})
