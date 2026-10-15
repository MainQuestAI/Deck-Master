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


def _manuscript_plan_input(document, pages, outline):
    order = [entry["page_id"] for entry in pages]
    hard_limit = document['task'].get('page_limit')
    if hard_limit is not None and len(order) > hard_limit:
        raise models.ModelError('draft/page_order',
            f'actual manuscript exceeds the provided hard maximum page_limit={hard_limit}')
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
    if outline is None:
        plan_input['page_roles'] = [{'page_id': pid, 'role': 'Imported page; rhetorical role unverified',
            'audience_question': 'Not recorded in the imported manuscript',
            'intended_takeaway': 'Not recorded in the imported manuscript',
            'narrative_node_ids': [], 'source_links': [], 'required_qualifications': [],
            'content_profile': 'mixed', 'density_rationale': 'Imported content retained; density has not been assessed',
            'timing_seconds': None, 'transition_to_next': None} for pid in order]
    return plan_input, unresolved


def imported_plan(store, document, pages, source_ref, evidence, *, preserve_mainline=True, outline=None):
    plan_input, unresolved = _manuscript_plan_input(document, pages, outline)
    return build_v2_plan(store, document, {"task_id": None, "intent": "import_draft",
        "dispatch_revision": document["revision_id"], "input_digest": models.compute_input_digest(document)},
        plan_input, pages, narrative_ref=None, mode="imported_mapping", require_role_mapping=False,
        imported_manuscript={"source_ref": source_ref,
            "claimed_confirmation_evidence": evidence, "preserve_mainline": preserve_mainline,
            "unresolved_mapping_items": unresolved})


def _manuscript_pages(payload):
    """Pure normalization, shared by admission and the actual stored write."""
    checked = [copy.deepcopy(content.check_page(page)) for page in payload["pages"]]
    ids = [page["page_id"] for page in checked]
    order = payload.get("page_order") or ids
    if len(ids) != len(set(ids)) or len(order) != len(ids) or set(order) != set(ids):
        raise models.ModelError("draft/page_order", "must name every unique Page exactly once")
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
        by_id[page['page_id']] = page
    return [by_id[pid] for pid in order]


def _manuscript_write_set(store, doc, payload, *, preserve_mainline):
    """The complete replacement effect, before even immutable staging writes.

    import_draft is a complete manuscript, not an implicit patch: omissions are
    removals and its explicit order is the resulting order. Identical retained
    Pages keep their original refs and visual slots.
    """
    after = {page['page_id']: page for page in _manuscript_pages(payload)}
    before = {entry['page_id']: store.read_object_json(entry['page']) for entry in doc['pages']}
    old_order, new_order = list(before), list(after)
    changed = {pid for pid in set(before) | set(after) if before.get(pid) != after.get(pid)}
    layers = {'plan'}
    for pid in changed:
        old, new = before.get(pid) or {}, after.get(pid) or {}
        if (old.get('speaker_notes', ''), (old.get('content_mapping') or {}).get('speech_segments', [])) != (
                new.get('speaker_notes', ''), (new.get('content_mapping') or {}).get('speech_segments', [])):
            layers.add('speech')
        copy_views = []
        for page in (old, new):
            view = copy.deepcopy(page)
            view.pop('speaker_notes', None)
            if view.get('content_mapping'):
                view['content_mapping'].pop('speech_segments', None)
            copy_views.append(view)
        if copy_views[0] != copy_views[1]:
            layers.add('page_copy')
    targets = set(changed)
    plan_input, _ = _manuscript_plan_input(doc, list(after.values()), payload.get('content_plan'))
    previous = store.read_object_json(doc['content_plan']) if doc.get('content_plan') else None
    old_input = (previous or {}).get('input') or {}
    if old_input.get('schema_version') == 'content_plan_input.v2':
        old_roles = {role['page_id']: role for role in old_input['page_roles']}
        new_roles = {role['page_id']: role for role in plan_input['page_roles']}
        targets.update(pid for pid in set(old_roles) | set(new_roles) if old_roles.get(pid) != new_roles.get(pid))
        global_fields = set(old_input) | set(plan_input)
        global_fields -= {'page_order', 'page_roles', 'chapters'}
        if (any(old_input.get(key) != plan_input.get(key) for key in global_fields)
                or old_input.get('chapters') != plan_input.get('chapters')):
            targets.update(set(before) | set(after))
    elif previous:
        targets.update(set(before) | set(after))
    if doc.get('narrative'):
        layers.add('narrative')
        targets.update(set(before) | set(after))
    if any(doc['outputs'].values()):
        layers.add('output')
        targets.update(set(before) | set(after))
    invalidated = []
    for entry in doc['pages']:
        if entry['page_id'] not in changed:
            continue
        for slot, layer in (('blueprint', 'blueprint'), ('svg', 'svg'), ('svg_preview', 'svg'), ('ppt_preview', 'output')):
            if entry.get(slot):
                layers.add(layer)
                invalidated.append(entry[slot])
    profile = (doc.get('collaboration') or {}).get('quality_profile')
    if preserve_mainline and profile != collaboration_region(imported=True)['quality_profile']:
        layers.add('review')
        targets.update(set(before) | set(after))
    if (doc.get('content_basis') or {}).get('input_digest') not in (None, models.compute_input_digest(doc)):
        targets.update(set(before) | set(after))
    retained = set(before) & set(after)
    return {'page_ids': sorted(targets), 'layers': sorted(layers),
        'allow_page_membership_change': set(before) != set(after),
        'allow_page_order_change': [pid for pid in old_order if pid in retained] != [pid for pid in new_order if pid in retained],
        'added_page_ids': sorted(set(after) - set(before)), 'removed_page_ids': sorted(set(before) - set(after)),
        'page_order': new_order, 'changed_page_ids': sorted(changed),
        'invalidated_refs': invalidated, 'invalidated_outputs': [ref for ref in doc['outputs'].values() if ref]}


def prepare_manuscript(store, doc, payload, *, evidence=None, preserve_mainline=True, adapter_context=None, digest=None):
    """Normalize fixed input bytes; the owning transaction alone publishes them."""
    checked = _manuscript_pages(payload)
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
    previous_entries = {entry['page_id']: entry for entry in doc['pages']}
    pages = []
    for page in checked:
        ref = store.put_json_object(page)
        old = previous_entries.get(page['page_id'])
        pages.append(copy.deepcopy(old) if old and old['page'] == ref else {
            'page_id': page['page_id'], 'page': ref, 'blueprint': None,
            'svg': None, 'svg_preview': None, 'ppt_preview': None})
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
    _manuscript_pages(payload)
    digest = collaboration.payload_digest("manuscript.import", {"draft": payload,
        "instruction_evidence": evidence, "preserve_mainline": preserve_mainline})
    with store._locked():
        doc = store.load_document()
        replay = collaboration.replay_or_conflict(store, doc, operation_id, "manuscript.import", digest)
        if replay:
            return replay
        if base_revision != doc["revision_id"]:
            raise ConflictError("base_revision", "manuscript import requires the current base")
        write_set = _manuscript_write_set(store, doc, payload, preserve_mainline=preserve_mainline)
        eligibility.guard(store, doc, 'import_draft', context={'targets': write_set,
            'manuscript_import': {'input_digest': models.compute_input_digest(doc),
                'covered_page_ids': write_set['page_ids'],
                'source_sha256': models.sha256_bytes(models.canonical_json_bytes(payload))}})
        updated, normalized = prepare_manuscript(store, doc, payload, evidence=evidence,
            preserve_mainline=preserve_mainline, adapter_context=adapter_context, digest=digest)
        source_ref, plan_ref = normalized["source_ref"], normalized["plan_ref"]
        pages = updated["pages"]
        # Pending work belongs to the replaced draft, never to the imported one.
        affected = set(write_set['page_ids'])
        updated["tasks"] = [store.put_json_object({**task, "status": "superseded"})
            if task["status"] in ("running", "awaiting_host", "queued")
                and (task['kind'] == 'compose' or not task['scope_pages'] or affected.intersection(task['scope_pages'])) else ref
            for ref in doc["tasks"] for task in [store.read_object_json(ref)]]
        models.require_writer(updated, "rc3-entry.v1")
        return collaboration.commit_collaboration_change(store, doc, operation_id=operation_id,
            action="manuscript.import", digest=digest, description="Import fixed manuscript with source mapping",
            updated=updated, response={"page_refs": [entry["page"] for entry in pages],
                "plan_ref": plan_ref, "source_ref": source_ref, "result_refs": [plan_ref],
                "narrative_ref": None, "creates_confirmation": False,
                "authorizes_production": False, "assurance": normalized["assurance"], 'write_set': write_set})
