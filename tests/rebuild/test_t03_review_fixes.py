"""T03 independent-review fixes: the regressions behind P2-1, P2-2, P3-1, P3-2,
P3-3 and P3-4 from the review that returned REQUEST-CHANGES.

Each test drives the real service entry points and locks the *refusal* (plus the
one acceptance that must keep working) so the defect cannot silently return.
"""
import json

import pytest

from deck_master import collaboration, content_production, content_review, exports, models, service
from deck_master import variant_requests
from deck_master.models import ModelError, bump_revision
from deck_master.store import Store
from deck_master.tasks import EnvelopeError

from rc3_fixtures import claim_fixture_task, evidence_for, historical_snapshot, source_snapshot

from test_content_preproduction_review import (
    _argument_narrative, _deck, _instruction, _page, _plan_input, _project, _scope,
    _source_link, _stored)
from test_variant_requests import _grant_variants, _produce_variant, _start_variant


def _submit(project, task, payload, variant):
    claim_fixture_task(project, task)
    return service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": variant, "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": payload, "usage_events": []})


def _adopt_new_narrative(project, store):
    """Swap in a different argument (new node ids) through the real adopt path."""
    document = store.load_document()
    narrative = _argument_narrative(document["project_id"])
    narrative["narrative_id"] = "nar-swapped"
    for node in narrative["nodes"]:
        node["node_id"] = node["node_id"] + "-v2"
    narrative["central_node_id"] = "n1-v2"
    narrative["edges"] = [{"from_node_id": "q1-v2", "to_node_id": "n1-v2",
                           "relation": "qualifies"}]
    narrative_ref = store.put_json_object(narrative)
    decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "换论证"},
                        "scope": _scope(layers=["narrative", "plan", "page_copy"]),
                        "instruction_evidence": _instruction(store, "swap"),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": narrative_ref,
                                          "projection": "direction"}]},
        base_revision=store.load_document()["revision_id"], operation_id="op-swap-direction")
    content_production.adopt_proposal(
        project, input={"proposal_ref": narrative_ref, "decision_ref": decision["decision_ref"],
                        "write_scope": _scope(layers=["narrative"])},
        base_revision=store.load_document()["revision_id"], operation_id="op-swap-adopt")
    return Store(project)


# ---------------------------------------------------------------------------
# P2-1: speech must not silently rebind a superseded page mapping


def test_speech_cannot_silently_rebind_a_superseded_mapping(tmp_path):
    project, store = _deck(tmp_path)
    store = _adopt_new_narrative(project, store)
    document = store.load_document()
    page_ref_before = document["pages"][0]["page"]
    page_before = store.read_object_json(page_ref_before)
    assert page_before["content_mapping"]["narrative_ref"] != document["narrative"]
    task = content_production.open_phase_task(store, document, operation_id="sp-rebind",
                                              phase="speech")
    document = store.load_document()
    entry = document["pages"][0]
    notes = "换过论证之后的口播。"
    update = {"page_id": "p1", "page_ref": entry["page"], "speaker_notes": notes,
              "speech_segments": [{"segment_id": "s1", "start_codepoint": 0,
                                   "end_codepoint": len(notes),
                                   "narrative_node_ids": ["n1-v2"], "kind": "cue",
                                   "estimated_seconds": 8}]}
    with pytest.raises(EnvelopeError, match="re-run the page_copy"):
        _submit(project, task, {"updates": [update]}, "speech")
    # Nothing moved: the page (and its dangling mapping) is exactly as it was.
    document = store.load_document()
    assert document["pages"][0]["page"] == page_ref_before
    assert store.read_object_json(document["pages"][0]["page"]) == page_before
    # The same state cannot be smuggled through a verbatim request either.
    task2 = content_production.open_phase_task(store, document,
                                               operation_id="sp-rebind-2", phase="speech")
    verbatim = {**update, "speech_segments": [
        {**update["speech_segments"][0], "kind": "verbatim"}]}
    with pytest.raises(EnvelopeError, match="re-run the page_copy"):
        _submit(project, task2, {"updates": [verbatim]}, "speech")
    assert store.load_document()["pages"][0]["page"] == page_ref_before


# ---------------------------------------------------------------------------
# P2-2: one effective policy for dispatch and acceptance


def _deck_with_default_verbatim_plan(tmp_path, *, policy_mode="verbatim", policy_source="default"):
    project, store = _deck(tmp_path)
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="pc-policy",
                                              phase="page_copy")
    page = _page(store, document, "p1", notes="")
    plan_input = {**_plan_input(document, ["p1"], [_source_link(store, document, "L1")]),
                  "speech_policy": {"mode": policy_mode, "source": policy_source,
                                    "output": "pptx_notes"}}
    _submit(project, task, {"pages": [page], "page_order": ["p1"], "plan_input": plan_input},
            "page_copy")
    return project, Store(project)


def test_default_verbatim_plan_dispatches_and_accepts_cues(tmp_path):
    project, store = _deck_with_default_verbatim_plan(tmp_path)
    document = store.load_document()
    status = content_production.content_phase_status(store, document)
    assert status["phase"] == "speech" and status["speech_kind"] == "cue"
    task = content_production.next_phase_task(store, document)
    assert task["stage_request"]["speech_kind"] == "cue"
    document = store.load_document()
    entry = document["pages"][0]
    notes = "默认来源的逐字政策降级为提示口播。"
    update = {"page_id": "p1", "page_ref": entry["page"], "speaker_notes": notes,
              "speech_segments": [{"segment_id": "s1", "start_codepoint": 0,
                                   "end_codepoint": len(notes),
                                   "narrative_node_ids": ["n1"], "kind": "cue",
                                   "estimated_seconds": 9}]}
    out = _submit(project, task, {"updates": [update]}, "speech")
    assert out["status"] == "accepted"
    store = Store(project)
    document = store.load_document()
    page = store.read_object_json(document["pages"][0]["page"])
    assert page["speaker_notes"] == notes
    # The phase is satisfied: no second speech task appears for the same notes.
    assert content_production.content_phase_status(store, document)["action"] == "complete"
    assert content_production.content_phase_status(
        store, document, explicit_speech_mode="verbatim")["action"] == "complete"


def test_explicit_verbatim_still_requires_verbatim_segments(tmp_path):
    project, store = _deck_with_default_verbatim_plan(tmp_path, policy_mode="cues",
                                                      policy_source="default")
    document = store.load_document()
    status = content_production.content_phase_status(store, document,
                                                     explicit_speech_mode="verbatim")
    assert status["speech_kind"] == "verbatim"
    task = content_production.next_phase_task(store, document, explicit_speech_mode="verbatim")
    assert task["stage_request"]["speech_kind"] == "verbatim"
    document = store.load_document()
    entry = document["pages"][0]
    notes = "明确要求的逐字稿。"
    cue = {"page_id": "p1", "page_ref": entry["page"], "speaker_notes": notes,
           "speech_segments": [{"segment_id": "s1", "start_codepoint": 0,
                                "end_codepoint": len(notes),
                                "narrative_node_ids": ["n1"], "kind": "cue",
                                "estimated_seconds": 9}]}
    with pytest.raises(EnvelopeError, match="dispatched for 'verbatim'"):
        _submit(project, task, {"updates": [cue]}, "speech")
    verbatim = {**cue, "speech_segments": [{**cue["speech_segments"][0], "kind": "verbatim"}]}
    assert _submit(project, task, {"updates": [verbatim]}, "speech")["status"] == "accepted"


def test_a_none_policy_refuses_new_speech(tmp_path):
    """An effective `none` policy refuses notes instead of quietly producing speech."""
    project, store = _deck_with_default_verbatim_plan(tmp_path, policy_mode="none",
                                                      policy_source="default")
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="sp-none",
                                              phase="speech")
    document = store.load_document()
    entry = document["pages"][0]
    notes = "未请求的口播。"
    update = {"page_id": "p1", "page_ref": entry["page"], "speaker_notes": notes,
              "speech_segments": [{"segment_id": "s1", "start_codepoint": 0,
                                   "end_codepoint": len(notes),
                                   "narrative_node_ids": ["n1"], "kind": "cue",
                                   "estimated_seconds": 9}]}
    with pytest.raises(EnvelopeError, match="produces no new speech"):
        _submit(project, task, {"updates": [update]}, "speech")


# ---------------------------------------------------------------------------
# P3-1: no speech write onto a page without a mapping


def test_speech_on_a_mapping_less_page_is_refused(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    legacy = {key: value for key, value in store.read_object_json(document["pages"][0]["page"]).items()
              if key != "content_mapping"}
    legacy["speaker_notes"] = ""
    legacy_ref = store.put_json_object(legacy)
    bumped = bump_revision(document, {"operation_id": "probe-legacy-copy",
                                      "kind": "content_update",
                                      "description": "fixture: strip the mapping", "read_set": []})
    bumped["pages"] = [{**entry, "page": legacy_ref} if entry["page_id"] == "p1" else entry
                       for entry in document["pages"]]
    store._commit_locked(blobs=[], base_revision=document["revision_id"], document=bumped,
                         operation_id="probe-legacy-copy")
    store = Store(project)
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="sp-legacy",
                                              phase="speech")
    document = store.load_document()
    entry = document["pages"][0]
    update = {"page_id": "p1", "page_ref": entry["page"],
              "speaker_notes": "无映射页的口播。", "speech_segments": []}
    with pytest.raises(EnvelopeError, match="no content_mapping"):
        _submit(project, task, {"updates": [update]}, "speech")
    # The existing (empty) notes of that page stay untouched.
    assert store.read_object_json(Store(project).load_document()["pages"][0]["page"])["speaker_notes"] == ""


# ---------------------------------------------------------------------------
# P3-2: a decision with empty subject_refs adopts nothing


def test_empty_subject_refs_decision_adopts_no_proposal(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="nar-prop",
                                              phase="argument")
    document = store.load_document()
    narrative = _argument_narrative(document["project_id"])
    narrative["narrative_id"] = "nar-proposal"
    out = _submit(project, task, {"narrative": narrative}, "narrative")
    proposal_ref = out["narrative_ref"]
    narrative_before = store.load_document()["narrative"]
    broad = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "泛指"},
                        "scope": _scope(layers=["narrative", "plan", "page_copy"]),
                        "instruction_evidence": _instruction(store, "broad"),
                        "subject_refs": []},
        base_revision=store.load_document()["revision_id"], operation_id="op-broad")
    with pytest.raises(ModelError, match="names no proposal"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": broad["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-broad")
    assert store.load_document()["narrative"] == narrative_before
    # Naming the proposal under an unrelated projection is refused as well.
    palette = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "配色"},
                        "scope": _scope(layers=["narrative"]),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": proposal_ref,
                                          "projection": "style.palette"}],
                        "instruction_evidence": _instruction(store, "palette")},
        base_revision=store.load_document()["revision_id"], operation_id="op-palette")
    with pytest.raises(ModelError, match="needs one of"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": palette["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-palette")
    assert store.load_document()["narrative"] == narrative_before


# ---------------------------------------------------------------------------
# P3-3: import_draft never dispatches an unbound legacy task


def _draft_payload():
    return {"pages": [{"schema_version": "deck_page_package.v2", "page_id": "d1",
                       "customer_visible": {"title": "导入稿", "body_blocks": [
                           {"id": "b1", "type": "paragraph", "text": "已确认的正文。"}]},
                       "speaker_notes": "",
                       "visual_spec": {"intent": "阅读", "reference_mode": "new_design"}}],
            "page_order": ["d1"]}


def test_import_draft_on_a_collaboration_project_checks_actual_scope(tmp_path):
    from deck_master import eligibility
    project, store = _deck(tmp_path)
    before = store.load_document()
    tree = source_snapshot(project)
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        service.import_draft(project, draft_payload=_draft_payload(),
            base_revision=before["revision_id"], operation_id="out-of-scope-import")
    assert "scope_exceeded" in blocked.value.decision["reason_codes"]
    assert store.load_document() == before and source_snapshot(project) == tree

    # A current complete manuscript can change a selected Page while retaining
    # the unselected Page. This is a public CAS import, not an unbound Task.
    project = tmp_path / "current-fixed-manuscript"
    page1 = _draft_payload()["pages"][0]
    page1["page_id"] = "p1"
    page2 = {**page1, "page_id": "p2"}
    service.create(project, brief="L1 preserve fixed manuscript", draft={"pages": [page1, page2]})
    store = Store(project)
    document = store.load_document()
    scope = {**document["collaboration"]["request"]["scope"], "subject": "pages",
        "page_ids": ["p1"], "layers": ["page_copy", "plan"],
        "allow_page_membership_change": False, "allow_page_order_change": False}
    collaboration.start_request(project, input={"intent": "edit", "scope": scope,
        "replace_request_id": document["collaboration"]["request"]["request_id"],
        "instruction_evidence": evidence_for(project, text="L1 change only p1 copy; retain p2 and manuscript order.",
            locator="synthetic-l1:t03-fixed-import")}, base_revision=document["revision_id"],
        operation_id="fixed-import-request")
    before = store.load_document()
    pages = [store.read_object_json(entry["page"]) for entry in before["pages"]]
    pages[0]["customer_visible"]["title"] += "（修订）"
    result = service.import_draft(project, draft_payload={"pages": pages},
        base_revision=before["revision_id"], operation_id="in-scope-import")
    after = store.load_document()
    assert result["status"] == "accepted" and result["write_set"]["page_ids"] == ["p1"]
    assert after["pages"][1] == before["pages"][1]
    assert after["tasks"] == before["tasks"] and after["collaboration"] == before["collaboration"]


def test_existing_historical_import_requires_explicit_migration(tmp_path):
    from deck_master import eligibility
    fixture = historical_snapshot(tmp_path, scenario="L1 pre-collaboration import reader")
    project = fixture["project"]
    store = Store(project)
    before, tree = store.load_document(), source_snapshot(project)
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        service.import_draft(project, draft_payload=_draft_payload(),
            base_revision=before["revision_id"], operation_id="historical-import")
    assert "migration_required" in blocked.value.decision["reason_codes"]
    assert store.load_document() == before and source_snapshot(project) == tree
    # New standalone manuscript import still uses the actual canonical create
    # path and publishes no legacy compose Task.
    fresh = tmp_path / "new-manuscript"
    service.import_draft(fresh, draft_payload=_draft_payload())
    current = Store(fresh).load_document()
    assert [entry["page_id"] for entry in current["pages"]] == ["d1"]
    assert current["tasks"] == [] and current["compatibility"]["minimum_writer"] == "rc3-entry.v1"


# ---------------------------------------------------------------------------
# P3-4: produced variants are remembered by the Store, not by deletable files


def test_produced_variant_cannot_be_reproduced_after_export_files_vanish(tmp_path):
    project, store = _deck(tmp_path)
    _grant_variants(project, store)
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    _start_variant(project, store, variant_id="live", replace_request_id=current)
    _produce_variant(project, store, text="现场版正文。")
    store = Store(project)
    export_one = exports.create(project, purpose="review")
    store = Store(project)
    group_id = export_one["manifest"]["variant"]["group_id"]
    # A user (or a cleanup) removes the export records entirely.
    exports_root = store.project_root / ".deckmaster" / "workbench" / "exports"
    removed = 0
    for record in exports_root.glob("*/export-record.json"):
        record.unlink()
        removed += 1
    assert removed >= 1
    document = Store(project).load_document()
    assert variant_requests.used_variant_ids(Store(project), document, group_id) == ["live"]
    # The Store's committed revision history still remembers the produced version.
    current = document["collaboration"]["request"]["request_id"]
    retried = _start_variant(project, Store(project), variant_id="live", replace_request_id=current,
                            operation_id="op-live-retry-after-delete")
    after_retry = Store(project).load_document()
    assert retried["status"] == "already_started"
    assert retried["creates_request"] is False and retried["refreshes_credit"] is False
    for key in ("collaboration", "pages", "tasks", "outputs"):
        assert after_retry[key] == document[key]
    with pytest.raises(ModelError, match="already fixed in this group"):
        _start_variant(project, Store(project), variant_id="live", replace_request_id=current,
                       operation_id="op-live-again-after-delete", instruction_seed="new-repeat-fixed-live")
    # A different version still needs its actual versioned source export.
    from deck_master.store import ConflictError
    with pytest.raises(ConflictError, match="variant_source_unavailable"):
        _start_variant(project, Store(project), variant_id="read", replace_request_id=current,
            operation_id="op-read-missing-source", source={"revision_id": export_one["revision_id"]})
    fixed = exports.create(project, purpose="review", revision=export_one["revision_id"])
    second = _start_variant(project, Store(project), variant_id="read",
                            replace_request_id=current, operation_id="op-read-after-delete",
                            source={"revision_id": fixed["revision_id"], "export_id": fixed["export_id"]})
    assert second["status"] == "accepted"
    fixed, truncated = variant_requests._history_variant_ids(
        Store(project), Store(project).load_document(), group_id)
    assert truncated is False and fixed == {"live", "read"}
