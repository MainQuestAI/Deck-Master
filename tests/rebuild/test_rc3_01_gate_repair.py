"""RC3-01-S01: formal acceptance regressions for two actual E1 gate defects.

The provider and source/manuscript are explicit synthetic L1 fixtures. These
tests prove protocol behavior, never independent real model or human acceptance.
"""
from copy import deepcopy

import pytest

from deck_master import content_production, content_review, editing, review as review_module
from deck_master.store import Store
from deck_master.tasks import EnvelopeError

from synthetic_review_provider import accept_with_synthetic_provider
from test_content_preproduction_review import (
    _deck, _dispatch_and_reviews, _independent_adapter, _plan_input, _source_link, _stored,
)
from test_t03_review_fixes import _deck_with_default_verbatim_plan, _submit


def _mixed_speech(store):
    parts = [("先独立判断紧急程度，再判断版本可得性。\n", "verbatim", 12),
             ("[暂停讲述，学员独立作答 60 秒。]\n", "cue", 60),
             ("现在解释你的流转选择和下一责任人。", "verbatim", 8)]
    notes, segments = "", []
    for index, (text, kind, seconds) in enumerate(parts):
        start = len(notes)
        notes += text
        segments.append({"segment_id": f"s{index}", "start_codepoint": start,
                         "end_codepoint": len(notes), "narrative_node_ids": ["n1"],
                         "kind": kind, "estimated_seconds": seconds})
    return {"page_id": "p1", "page_ref": store.load_document()["pages"][0]["page"],
            "speaker_notes": notes, "speech_segments": segments}


def _verbatim_task(store):
    return content_production.next_phase_task(
        store, store.load_document(), explicit_speech_mode="verbatim")


def test_verbatim_accepts_honest_interaction_cue_without_relabelling_or_copy_changes(tmp_path):
    project, store = _deck_with_default_verbatim_plan(
        tmp_path, policy_mode="cues", policy_source="default")
    old_document = store.load_document()
    old_page = store.read_object_json(old_document["pages"][0]["page"])
    task = _verbatim_task(store)
    update = _mixed_speech(store)
    assert _submit(project, task, {"updates": [update]}, "speech")["status"] == "accepted"
    document = store.load_document()
    page = store.read_object_json(document["pages"][0]["page"])
    assert page["speaker_notes"] == update["speaker_notes"]
    assert page["content_mapping"]["speech_segments"] == update["speech_segments"]
    assert [s["kind"] for s in page["content_mapping"]["speech_segments"]] == [
        "verbatim", "cue", "verbatim"]
    assert sum(s["estimated_seconds"] for s in update["speech_segments"]
               if s["kind"] == "verbatim") == 20
    assert sum(s["estimated_seconds"] for s in update["speech_segments"]
               if s["kind"] == "cue") == 60
    assert page["customer_visible"] == old_page["customer_visible"]
    assert page["visual_spec"] == old_page["visual_spec"]
    assert store.read_object_json(old_document["pages"][0]["page"]) == old_page
    plan = store.read_object_json(document["content_plan"])
    assert plan["page_links"][0]["page_ref"] == document["pages"][0]["page"]


@pytest.mark.parametrize("defect", ["all_cues", "whitespace_verbatim", "bad_kind", "range_gap",
                                   "unknown_node", "missing_estimate", "body_write"])
def test_mixed_verbatim_still_refuses_invalid_or_out_of_scope_results_atomically(tmp_path, defect):
    project, store = _deck_with_default_verbatim_plan(
        tmp_path, policy_mode="cues", policy_source="default")
    task = _verbatim_task(store)
    update = _mixed_speech(store)
    if defect == "all_cues":
        for segment in update["speech_segments"]:
            segment["kind"] = "cue"
    elif defect == "whitespace_verbatim":
        update["speaker_notes"] = " \n[暂停作答。]"
        update["speech_segments"] = [
            {**update["speech_segments"][0], "start_codepoint": 0, "end_codepoint": 2},
            {**update["speech_segments"][1], "start_codepoint": 2,
             "end_codepoint": len(update["speaker_notes"])}]
    elif defect == "bad_kind":
        update["speech_segments"][1]["kind"] = "interaction"
    elif defect == "range_gap":
        update["speech_segments"][1]["start_codepoint"] += 1
    elif defect == "unknown_node":
        update["speech_segments"][1]["narrative_node_ids"] = ["invented"]
    elif defect == "missing_estimate":
        update["speech_segments"][1]["estimated_seconds"] = None
    elif defect == "body_write":
        update["customer_visible"] = {"title": "偷偷改正文"}
    before = store.load_document()
    with pytest.raises(EnvelopeError):
        _submit(project, task, {"updates": [update]}, "speech")
    after = store.load_document()
    assert after["pages"] == before["pages"]
    assert after["content_plan"] == before["content_plan"]
    assert after["reviews"] == before["reviews"]


def test_cues_request_does_not_expand_to_mixed_verbatim(tmp_path):
    project, store = _deck_with_default_verbatim_plan(
        tmp_path, policy_mode="cues", policy_source="provided")
    task = content_production.next_phase_task(store, store.load_document())
    before = store.load_document()["pages"]
    with pytest.raises(EnvelopeError, match="dispatched for 'cue'"):
        _submit(project, task, {"updates": [_mixed_speech(store)]}, "speech")
    assert store.load_document()["pages"] == before


def _finding(store, finding_id, *, impact="needs_judgment", resolution="open"):
    return {"finding_id": finding_id, "kind": "content", "impact": impact,
            "resolution": resolution, "page_id": "p1", "element_refs": ["atom:p1:title"],
            "message": "培训页的版本限定需核对", "expected": "限定保留且核对依据",
            "actual": "待审", "evidence": [_stored(store, f"evidence-{finding_id}")]}


def _publish(project, store, mutate=None, *, authenticated=True):
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    if mutate:
        mutate(reviews)
    return accept_with_synthetic_provider(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"kind": "review", "pages": [], "page_order": [],
                        "artifact_specs": [], "reviews": reviews, "usage_events": [],
                        "notes": "synthetic L1 preproduction recheck"},
        adapter_context=adapter if authenticated else None)


def _initial_judgment(project, store, *, impact="needs_judgment", count=1, kind="page_copy"):
    def mutate(reviews):
        target = next(r for r in reviews if r["kind"] == kind)
        target["status"] = "fail" if impact == "must_fix" else "needs_review"
        target["findings"] = [_finding(store, f"f{i}", impact=impact) for i in range(count)]
    _publish(project, store, mutate)
    document = store.load_document()
    ref = next(ref for ref in document["reviews"]
               if store.read_object_json(ref)["kind"] == kind)
    assert content_review.preproduction_status(store, document)["status"] != "pass"
    return ref, store.read_object_json(ref)


def _variance(store, old_ref, old_review, *, count=None):
    def mutate(reviews):
        target = next(r for r in reviews if r["kind"] == "page_copy")
        target["replaces"] = old_ref
        target["review_id"] = old_review["review_id"]
        target["findings"] = [{**deepcopy(f), "resolution": "accepted_variance",
                               "resolution_reason": "实际核对当前稿：合理不确定性已明确，实测另验。"}
                              for f in old_review["findings"][:count]]
    return mutate


def test_explicit_evidenced_variance_closes_only_its_original_finding(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, count=2)
    _publish(project, store, _variance(store, old_ref, old_review, count=1))
    status = content_review.preproduction_status(store, store.load_document())
    assert status["status"] == "blocked"
    assert [f["finding_id"] for f in status["blocking_findings"]] == ["f1"]
    _publish(project, store, _variance(store, old_ref, old_review))
    status = content_review.preproduction_status(store, store.load_document())
    assert status["status"] == "pass" and not status["blocking_findings"]
    assert old_ref in store.load_document()["reviews"]
    assert store.read_object_json(old_ref) == old_review


@pytest.mark.parametrize("impact", ["needs_judgment", "must_fix"])
def test_new_pass_without_replaces_cannot_erase_an_open_finding(tmp_path, impact):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact=impact)
    assert _publish(project, store)["status"] == "accepted"
    status = content_review.preproduction_status(store, store.load_document())
    assert status["status"] == "blocked"
    assert status["blocking_findings"][0]["finding_id"] == "f0"
    assert store.read_object_json(old_ref) == old_review


@pytest.mark.parametrize("defect", ["review_id", "kind", "stage", "page", "finding_id",
                                   "reason", "evidence", "observations", "dependency", "subject",
                                   "unauthenticated", "must_fix_variance"])
def test_replacement_does_not_bypass_logical_review_basis_evidence_or_identity(tmp_path, defect):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(
        project, store, impact="must_fix" if defect == "must_fix_variance" else "needs_judgment")
    variance = _variance(store, old_ref, old_review)

    def mutate(reviews):
        variance(reviews)
        target = next(r for r in reviews if r["kind"] == "page_copy")
        if defect == "review_id":
            target["review_id"] = "unrelated"
        elif defect == "kind":
            target["kind"] = "argument"
        elif defect == "stage":
            target["review_stage"] = "final"
        elif defect == "page":
            target["findings"][0]["page_id"] = "p2"
        elif defect == "finding_id":
            target["findings"][0]["finding_id"] = "unrelated"
        elif defect in ("reason", "evidence"):
            target["findings"][0]["resolution_reason" if defect == "reason" else "evidence"] = (
                "" if defect == "reason" else [])
        elif defect == "observations":
            target["observations"] = []
        elif defect == "dependency":
            target["dependencies"][0]["sha256"] = "0" * 64
        elif defect == "subject":
            target["subjects"] = []
    before = store.load_document()
    with pytest.raises(EnvelopeError):
        _publish(project, store, mutate, authenticated=defect != "unauthenticated")
    after = store.load_document()
    assert after["reviews"] == before["reviews"]
    assert after["pages"] == before["pages"]
    assert content_review.preproduction_status(store, after)["status"] != "pass"


def test_fixed_preproduction_recheck_accepts_changed_manuscript_without_pptx(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact="must_fix")
    document = store.load_document()
    old_page = store.read_object_json(document["pages"][0]["page"])
    changed = deepcopy(old_page)
    changed["customer_visible"]["body_blocks"][0]["text"] = (
        "版本未知时记录未知，紧急程度另作判断；缺字段率不等于收益。")
    # The same formal page-copy API used by Content performs the repair.
    task = content_production.open_phase_task(store, document, operation_id="fix-copy",
                                              phase="page_copy")
    plan_input = store.read_object_json(document["content_plan"])["input"]
    pages = [changed, store.read_object_json(document["pages"][1]["page"])]
    _submit(project, task, {"pages": pages, "page_order": plan_input["page_order"],
                            "plan_input": plan_input}, "page_copy")
    assert store.load_document()["outputs"].get("pptx") is None

    def fixed(reviews):
        target = next(r for r in reviews if r["kind"] == "page_copy")
        target["replaces"] = old_ref
        target["review_id"] = old_review["review_id"]
        target["findings"] = [{**old_review["findings"][0], "resolution": "fixed",
                               "evidence": [_stored(store, "actual-current-copy-recheck")]}]
    assert _publish(project, store, fixed)["status"] == "accepted"
    assert content_review.preproduction_status(store, store.load_document())["status"] == "pass"
    assert store.read_object_json(old_ref) == old_review


def test_fixed_without_actual_manuscript_change_is_refused(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact="must_fix")

    def fixed(reviews):
        target = next(r for r in reviews if r["kind"] == "page_copy")
        target["replaces"] = old_ref
        target["review_id"] = old_review["review_id"]
        target["findings"] = [{**old_review["findings"][0], "resolution": "fixed"}]
    with pytest.raises(EnvelopeError, match="not closed"):
        _publish(project, store, fixed)
    assert content_review.preproduction_status(store, store.load_document())["status"] != "pass"


def _revise_page(project, store, page_id, *, layer="copy"):
    document = store.load_document()
    if layer == "notes":
        task = content_production.open_phase_task(
            store, document, operation_id="change-notes", phase="speech", page_ids=[page_id])
        entry = next(e for e in document["pages"] if e["page_id"] == page_id)
        notes = "讲述未知版本的记录方式，紧急程度另作判断。"
        update = {"page_id": page_id, "page_ref": entry["page"], "speaker_notes": notes,
                  "speech_segments": [{"segment_id": "revised-cue", "start_codepoint": 0,
                                       "end_codepoint": len(notes), "narrative_node_ids": ["n1"],
                                       "kind": "cue", "estimated_seconds": 20}]}
        _submit(project, task, {"updates": [update]}, "speech")
        return
    pages = [store.read_object_json(e["page"]) for e in document["pages"]]
    page = next(p for p in pages if p["page_id"] == page_id)
    page["customer_visible"]["body_blocks"][0]["text"] += " 缺字段率不能推得收益。"
    task = content_production.open_phase_task(
        store, document, operation_id=f"change-copy-{page_id}", phase="page_copy")
    plan_input = store.read_object_json(document["content_plan"])["input"]
    _submit(project, task, {"pages": pages, "page_order": plan_input["page_order"],
                            "plan_input": plan_input}, "page_copy")


@pytest.mark.parametrize("impact", ["must_fix", "needs_judgment"])
@pytest.mark.parametrize("page_id,layer", [("p1", "copy"), ("p2", "copy"),
                                           ("p1", "notes"), ("p2", "notes")])
def test_manuscript_changes_and_new_pass_cannot_erase_an_unclosed_current_finding(
        tmp_path, impact, page_id, layer):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact=impact)
    _revise_page(project, store, page_id, layer=layer)
    # This fresh review is accepted, but it declares no replaces or closure.
    assert _publish(project, store)["status"] == "accepted"
    status = content_review.preproduction_status(store, store.load_document())
    assert status["status"] == "blocked" and status["missing_units"] == []
    assert [f["finding_id"] for f in status["blocking_findings"]] == ["f0"]
    assert store.read_object_json(old_ref) == old_review


def test_historical_finding_closes_through_explicit_current_replacement_chain(tmp_path):
    project, store = _deck(tmp_path)
    original_ref, original = _initial_judgment(project, store, impact="must_fix")
    _revise_page(project, store, "p2")

    def still_open(reviews):
        target = next(r for r in reviews if r["kind"] == "page_copy")
        target["status"] = "fail"
        target["replaces"] = original_ref
        target["review_id"] = original["review_id"]
        target["findings"] = deepcopy(original["findings"])
    _publish(project, store, still_open)
    intermediate_ref = next(ref for ref in reversed(store.load_document()["reviews"])
                            if store.read_object_json(ref)["kind"] == "page_copy")
    intermediate = store.read_object_json(intermediate_ref)
    _revise_page(project, store, "p1")

    def fixed(reviews):
        target = next(r for r in reviews if r["kind"] == "page_copy")
        target["replaces"] = intermediate_ref
        target["review_id"] = original["review_id"]
        target["findings"] = [{**original["findings"][0], "resolution": "fixed",
                               "evidence": [_stored(store, "same-page-current-recheck")]}]
    assert _publish(project, store, fixed)["status"] == "accepted"
    status = content_review.preproduction_status(store, store.load_document())
    assert status["status"] == "pass" and status["blocking_findings"] == []
    assert store.read_object_json(original_ref) == original
    assert store.read_object_json(intermediate_ref) == intermediate


def test_historical_finding_blocks_its_page_but_not_an_unrelated_query_scope(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact="must_fix")
    _revise_page(project, store, "p2")
    _publish(project, store)
    document = store.load_document()
    assert content_review.preproduction_status(store, document, page_ids=["p2"])["status"] == "pass"
    assert content_review.preproduction_status(store, document, page_ids=["p1"])["status"] == "blocked"
    assert content_review.preproduction_status(store, document)["status"] == "blocked"
    assert store.read_object_json(old_ref) == old_review


def test_retired_page_finding_does_not_block_the_current_manuscript(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact="must_fix")
    document = store.load_document()
    page = store.read_object_json(document["pages"][1]["page"])
    task = content_production.open_phase_task(
        store, document, operation_id="retire-p1", phase="page_copy")
    plan_input = _plan_input(document, ["p2"], [_source_link(store, document)])
    _submit(project, task, {"pages": [page], "page_order": ["p2"], "plan_input": plan_input},
            "page_copy")
    assert _publish(project, store)["status"] == "accepted"
    document = store.load_document()
    assert [e["page_id"] for e in document["pages"]] == ["p2"]
    assert content_review.preproduction_status(store, document)["status"] == "pass"
    assert store.read_object_json(old_ref) == old_review


def test_no_longer_required_speech_unit_does_not_block_a_none_policy(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _initial_judgment(project, store, impact="must_fix", kind="speech")
    document = store.load_document()
    task = content_production.open_phase_task(
        store, document, operation_id="no-new-speech", phase="page_copy")
    pages = [store.read_object_json(e["page"]) for e in document["pages"]]
    plan_input = deepcopy(store.read_object_json(document["content_plan"])["input"])
    plan_input["speech_policy"] = {"mode": "none", "source": "provided", "output": "none"}
    _submit(project, task, {"pages": pages, "page_order": plan_input["page_order"],
                            "plan_input": plan_input}, "page_copy")
    _publish(project, store)
    status = content_review.preproduction_status(store, store.load_document())
    assert "speech" not in status["units"]
    assert status["status"] == "pass" and status["blocking_findings"] == []
    assert store.read_object_json(old_ref) == old_review


def _null_initial(project, store, *, impact="needs_judgment", kind="argument"):
    def mutate(reviews):
        target = next(r for r in reviews if r["kind"] == kind)
        target["status"] = "fail" if impact == "must_fix" else "needs_review"
        target["findings"] = [{**_finding(store, "whole-draft", impact=impact),
                               "page_id": None, "element_refs": []}]
    _publish(project, store, mutate)
    old_ref = next(ref for ref in store.load_document()["reviews"]
                   if store.read_object_json(ref)["kind"] == kind)
    return old_ref, store.read_object_json(old_ref)


def _null_closure(old_ref, old_review, *, resolution="accepted_variance"):
    def mutate(reviews):
        target = next(r for r in reviews if r["kind"] == old_review["kind"])
        target["review_id"] = old_review["review_id"]
        target["replaces"] = old_ref
        target["findings"] = [{**deepcopy(old_review["findings"][0]), "resolution": resolution,
                               "resolution_reason": "已实际核对完整当前稿；保留未知，未冒称已实测。"}]
    return mutate


def test_deck_level_preproduction_judgment_has_a_full_manuscript_variance_exit(tmp_path):
    project, store = _deck(tmp_path)
    old_ref, old_review = _null_initial(project, store)
    _publish(project, store)
    assert content_review.preproduction_status(store, store.load_document())["status"] == "blocked"
    assert _publish(project, store, _null_closure(old_ref, old_review))["status"] == "accepted"
    assert content_review.preproduction_status(store, store.load_document())["status"] == "pass"
    assert store.read_object_json(old_ref) == old_review


@pytest.mark.parametrize("defect", ["evidence", "observations", "reason", "missing_page",
                                   "missing_plan", "stale_dependency", "must_fix_variance"])
def test_deck_level_variance_keeps_complete_binding_and_evidence_floors(tmp_path, defect):
    project, store = _deck(tmp_path)
    old_ref, old_review = _null_initial(
        project, store, impact="must_fix" if defect == "must_fix_variance" else "needs_judgment")
    closure = _null_closure(old_ref, old_review)

    def mutate(reviews):
        closure(reviews)
        target = next(r for r in reviews if r["kind"] == "argument")
        if defect == "evidence":
            target["findings"][0]["evidence"] = []
        elif defect == "observations":
            target["observations"] = []
        elif defect == "reason":
            target["findings"][0]["resolution_reason"] = ""
        elif defect in ("missing_page", "missing_plan"):
            document = store.load_document()
            omit = (document["pages"][1]["page"] if defect == "missing_page"
                    else document["content_plan"])
            target["subjects"] = [ref for ref in target["subjects"] if ref != omit]
        elif defect == "stale_dependency":
            target["dependencies"][0]["sha256"] = "0" * 64
    before = store.load_document()["reviews"]
    with pytest.raises(EnvelopeError):
        _publish(project, store, mutate)
    assert store.load_document()["reviews"] == before
    assert content_review.preproduction_status(store, store.load_document())["status"] != "pass"


@pytest.mark.parametrize("kind,layer", [("argument", "copy"), ("page_copy", "copy"),
                                       ("progression", "copy"), ("speech", "notes")])
def test_deck_level_fixed_requires_a_real_current_consumed_manuscript_change(tmp_path, kind, layer):
    project, store = _deck(tmp_path)
    old_ref, old_review = _null_initial(project, store, impact="must_fix", kind=kind)
    _revise_page(project, store, "p1", layer=layer)
    assert _publish(project, store, _null_closure(old_ref, old_review, resolution="fixed"))[
        "status"] == "accepted"
    assert content_review.preproduction_status(store, store.load_document())["status"] == "pass"
    assert store.read_object_json(old_ref) == old_review


@pytest.mark.parametrize("kind", ["argument", "page_copy", "progression"])
@pytest.mark.parametrize("change", ["unchanged", "notes", "plan_version", "layout", "production", "audit_link"])
def test_deck_level_content_fixed_cannot_use_notes_metadata_layout_or_labels(tmp_path, kind, change):
    project, store = _deck(tmp_path)
    old_ref, old_review = _null_initial(project, store, impact="must_fix", kind=kind)
    if change == "notes":
        _revise_page(project, store, "p1", layer="notes")
    elif change != "unchanged":
        document = store.load_document()
        pages = [store.read_object_json(e["page"]) for e in document["pages"]]
        if change == "layout":
            pages[0]["visual_spec"]["layout_hint"] = "改为上下排列；事实、归属和方向保持。"
        elif change == "production":
            pages[0]["internal_only"] = {"production_notes": "仅更新制作备注。"}
        elif change == "audit_link":
            pages[0]["content_mapping"]["visible_links"][1]["source_links"][0]["locator"] = "L2"
        task = content_production.open_phase_task(
            store, document, operation_id="metadata-copy", phase="page_copy")
        plan_input = store.read_object_json(document["content_plan"])["input"]
        _submit(project, task, {"pages": pages, "page_order": plan_input["page_order"],
                                "plan_input": plan_input}, "page_copy")
    with pytest.raises(EnvelopeError, match="not closed"):
        _publish(project, store, _null_closure(old_ref, old_review, resolution="fixed"))
    assert content_review.preproduction_status(store, store.load_document())["status"] != "pass"


@pytest.mark.parametrize("stage", ["final", "page_visual"])
def test_null_manuscript_closure_does_not_relax_other_review_stages(tmp_path, stage):
    project, store = _deck(tmp_path)
    old_ref, old_review = _null_initial(project, store)
    _publish(project, store, _null_closure(old_ref, old_review))
    new_ref = next(ref for ref in reversed(store.load_document()["reviews"])
                   if store.read_object_json(ref)["kind"] == "argument")
    original = {**old_review, "ref": old_ref, "review_stage": stage}
    replacement = {**store.read_object_json(new_ref), "ref": new_ref, "review_stage": stage}
    artifacts = editing._current_artifact_digests(store, store.load_document())
    assert not review_module.finding_closed(
        [original, replacement], original, original["findings"][0], artifacts)
