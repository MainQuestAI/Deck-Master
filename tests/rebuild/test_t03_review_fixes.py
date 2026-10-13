"""T03 independent-review fixes: the regressions behind P2-1, P2-2, P3-1, P3-2,
P3-3 and P3-4 from the review that returned REQUEST-CHANGES.

Each test drives the real service entry points and locks the *refusal* (plus the
one acceptance that must keep working) so the defect cannot silently return.
"""
import json

import pytest

from deck_master import collaboration, content_production, content_review, exports, models, service
from deck_master import variant_requests
from deck_master.errors import ImportRequiresPhasedPath
from deck_master.models import ModelError, bump_revision
from deck_master.store import Store
from deck_master.tasks import EnvelopeError

from test_content_preproduction_review import (
    _argument_narrative, _deck, _instruction, _page, _plan_input, _project, _scope,
    _source_link, _stored)
from test_variant_requests import _grant_variants, _produce_variant, _start_variant


def _submit(project, task, payload, variant):
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
    task2 = content_production.open_phase_task(store, content_production and document,
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
            "page_order": ["d1"], "notes": "import"}


def test_import_draft_on_a_collaboration_project_is_blocked_with_recovery(tmp_path):
    project, store = _deck(tmp_path)
    with pytest.raises(ImportRequiresPhasedPath) as excinfo:
        service.import_draft(project, draft_payload=_draft_payload())
    error = excinfo.value
    assert error.error_code == "import_requires_phased_path" and error.exit_code == 4
    assert "page_copy" in error.detail and "start_request" in error.detail or \
        "work request" in error.detail
    # No page, plan, output or unbound task was written.
    document = Store(project).load_document()
    assert [entry["page_id"] for entry in document["pages"]] == ["p1", "p2"]
    assert not [ref for ref in document["tasks"]
                if Store(project).read_object_json(ref).get("intent") == "import_draft"]


def test_import_draft_still_works_below_the_collaboration_writer(tmp_path):
    project = tmp_path / "legacy"
    service.create(project, brief="legacy import", sources=[], project_format="workbench.v3")
    out = service.import_draft(project, draft_payload=_draft_payload())
    assert out["status"] == "accepted"
    document = Store(project).load_document()
    assert [entry["page_id"] for entry in document["pages"]] == ["d1"]


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
    with pytest.raises(ModelError, match="already fixed in this group"):
        _start_variant(project, Store(project), variant_id="live", replace_request_id=current,
                       operation_id="op-live-again-after-delete")
    # And the second, still-unproduced version remains available.
    second = _start_variant(project, Store(project), variant_id="read",
                            replace_request_id=current, operation_id="op-read-after-delete")
    assert second["status"] == "accepted"
    fixed, truncated = variant_requests._history_variant_ids(
        Store(project), Store(project).load_document(), group_id)
    assert truncated is False and fixed == {"live", "read"}
