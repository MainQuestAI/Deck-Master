"""G06/G07: immutable preproduction dependencies follow editorial semantics.

All manuscripts, instructions and self-reviews are explicit isolated L1 test
data. Reviews use an SDK-recorded host_self downgrade, real dispatch/claim/
accept and stored Page/Plan dependencies. No independent/native reviewer,
image generation, visual-quality verdict or production authorization is faked.
"""
import copy
import uuid
import xml.etree.ElementTree as ET

import pytest

from deck_master import collaboration, content, content_plan, content_review, editing, models, service
from test_rc3_design_requirements import _evidence, _snapshot


SELF_EXECUTOR = "synthetic-self-review-diagnostic"


def _commit(store, before, updated, description):
    operation_id = str(uuid.uuid4())
    changed = models.bump_revision(updated, {"operation_id": operation_id, "kind": "content_update",
                                           "description": description, "read_set": []})
    store.commit_change(base_revision=before["revision_id"], document=changed, operation_id=operation_id)
    return store.load_document()


def _scope(document, layers):
    return {**copy.deepcopy(document["collaboration"]["request"]["scope"]), "layers": list(layers)}


def _reviewed(store, *, page_ids=("p1",)):
    document = store.load_document()
    outcome = content_review.dispatch_preproduction_review(store.project_root, page_ids=list(page_ids))
    assert outcome["status"] == "review_dispatched" and outcome["requirement"] == "host_self"
    task = outcome["task"]
    assert task["collaboration_binding"]["executor_type"] == "host"
    service.task_start(store.project_root, task_id=task["task_id"], execution_ref=SELF_EXECUTOR,
                       supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else None,
                       capabilities=task.get("required_capabilities"))
    subjects = [document["narrative"], document["content_plan"]]
    dependencies = [{"kind": "content", "identity": identity, "sha256": document[key]["sha256"]}
                    for key, identity in (("narrative", "narrative"), ("content_plan", "content_plan"))]
    for entry in document["pages"]:
        if entry["page_id"] in page_ids:
            subjects.append(entry["page"])
            dependencies.append({"kind": "content", "identity": "page:" + entry["page_id"],
                                 "sha256": entry["page"]["sha256"]})
    reviews = []
    for kind in content_review.required_units(store, document):
        evidence = store.put_json_object({"synthetic": "host_self protocol diagnostic, not native independence",
                                          "kind": kind})
        review = {"schema_version": "deck_review.v2", "review_id": "diagnostic-" + kind,
                  "kind": kind, "review_stage": "preproduction", "status": "pass",
                  "subjects": copy.deepcopy(subjects), "dependencies": copy.deepcopy(dependencies),
                  "reviewer": {"type": "host_self", "id": SELF_EXECUTOR, "execution_ref": SELF_EXECUTOR,
                               "independence_confirmed": False, "identity_receipt": None,
                               "evidence_ref": evidence, "assurance": "host_attested"},
                  "observations": ["Synthetic self-review for dependency freshness diagnostics only."],
                  "findings": [], "created_at": "2026-10-15T00:00:00Z", "replaces": None}
        models.validate_review_semantics(review)
        reviews.append(review)
    result = service.accept_result(store.project_root, task_id=task["task_id"],
                                   operation_id=task["operation_id"], produced_against=task["produced_against"],
                                   result_payload={"kind": "review", "pages": [], "page_order": [],
                                       "artifact_specs": [], "reviews": reviews, "usage_events": [],
                                       "notes": "Explicit synthetic host_self review; no independent/native receipt."})
    assert result["status"] == "accepted"
    current = store.load_document()
    assert content_review.qualify_for_production(store, current, page_ids=list(page_ids))["allowed"]
    assert content_review.qualify_for_production(store, current, page_ids=list(page_ids))[
        "professional_review_required_for_delivery"]
    return current


def _flow(tmp_path, *, speech=False, page_ids=("p1",)):
    store, document, plan = _snapshot(tmp_path)
    document["policy"]["professional_review_required_for_delivery"] = True
    request = document["collaboration"]["request"]
    request["intent"], request["content_intent"] = "content_only", "content_full"
    request["scope"]["layers"] = ["narrative", "plan", "page_copy", "speech", "review", "design", "svg"]
    if speech:
        for entry in document["pages"]:
            page = store.read_object_json(entry["page"])
            page["speaker_notes"] = "先由模型拟稿，再由人工确认。"
            page["content_mapping"]["speech_segments"] = [{
                "segment_id": "cue-1", "start_codepoint": 0, "end_codepoint": len(page["speaker_notes"]),
                "narrative_node_ids": ["n1"], "kind": "cue", "estimated_seconds": 20}]
            models.validate_page_semantics(page)
            entry["page"] = store.put_json_object(page)
        plan["input"]["speech_policy"] = {"mode": "cues", "source": "provided", "output": "pptx_notes"}
        plan["page_links"] = [{"page_id": entry["page_id"], "page_ref": entry["page"],
                               "plan_role_page_id": entry["page_id"]} for entry in document["pages"]]
        models.validate_content_plan_semantics(plan)
        document["content_plan"] = store.put_json_object(plan)
    store.init_project(document)
    instruction = _evidence(store)
    instruction.pop("assurance")
    recorded = collaboration.record_decision(store.project_root, input={
        "topic": "policy", "disposition": "accepted", "authority_mode": "direct_user",
        "value": {"content_review_requirement": "host_self", "reason": "Synthetic freshness diagnostic only"},
        "scope": _scope(document, ["review"]), "instruction_evidence": instruction},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert store.load_document()["collaboration"]["quality_profile"]["override_decision_ref"] == recorded["decision_ref"]
    assert content_review.requirement_state(store, store.load_document())["effective"] == "host_self"
    return store, _reviewed(store, page_ids=page_ids)


def _page_edit(store, mutate, *, page_id="p1"):
    before = store.load_document()
    entry = next(entry for entry in before["pages"] if entry["page_id"] == page_id)
    page = store.read_object_json(entry["page"])
    mutate(page)
    models.validate_page_semantics(page)
    content.validate_page_references(page)
    result = editing.edit_page(store.project_root, page=page, base_revision=before["revision_id"],
                               page_hash=entry["page"]["sha256"], operation_id=str(uuid.uuid4()))
    assert result["status"] == "edited"
    current = store.load_document()
    plan = store.read_object_json(current["content_plan"])
    assert {link["page_id"]: link["page_ref"] for link in plan["page_links"]} == {
        item["page_id"]: item["page"] for item in current["pages"]}
    return current


def _plan_edit(store, mutate, *, reverse_order=False):
    before = store.load_document()
    updated = copy.deepcopy(before)
    plan = store.read_object_json(before["content_plan"])
    value = copy.deepcopy(plan["input"])
    mutate(value)
    if reverse_order:
        updated["pages"].reverse()
        value["page_order"].reverse()
        value["chapters"][0]["page_ids"].reverse()
    updated["content_plan"] = content_plan.build_v2_plan(
        store, before, {"task_id": None, "dispatch_revision": before["revision_id"]}, value,
        updated["pages"], narrative_ref=before["narrative"], mode="bound")
    return _commit(store, before, updated, "Explicit synthetic Plan mutation through current Plan builder")


def _assert_gate(store, original, *, allowed, missing=()):
    current = store.load_document()
    before_files = {ref["path"]: store.read_object_bytes(ref) for ref in original["reviews"]}
    status = content_review.preproduction_status(store, current, page_ids=["p1"])
    gate = content_review.qualify_for_production(store, current, page_ids=["p1"])
    assert gate["allowed"] is allowed
    assert gate["status"] == ("pass" if allowed else "missing")
    assert status["missing_units"] == sorted(missing)
    assert current["reviews"] == original["reviews"]
    assert before_files == {ref["path"]: store.read_object_bytes(ref) for ref in original["reviews"]}
    assert store.load_document() == current, "freshness queries must remain read-only"
    for ref in original["reviews"]:
        review = store.read_object_json(ref)
        assert review["reviewer"]["type"] == "host_self"
        assert review["reviewer"]["independence_confirmed"] is False


@pytest.mark.parametrize("change", ["layout", "style", "design_override"])
def test_sdk_legal_page_design_changes_preserve_non_speech_preproduction(tmp_path, change):
    store, original = _flow(tmp_path)
    def mutate(page):
        if change == "layout":
            page["visual_spec"]["layout_hint"] = "相同责任、归属与边方向，改为上下排列"
        elif change == "style":
            page["visual_spec"]["style_ref"] = "default"
        else:
            page["visual_spec"]["design_overrides"] = {"language": "en-US"}
    _page_edit(store, mutate)
    assert store.load_document()["pages"][0]["page"] != original["pages"][0]["page"]
    _assert_gate(store, original, allowed=True)


@pytest.mark.parametrize("change", ["responsibility", "cell_ownership", "arrow", "label_owner", "mapping"])
def test_same_visible_text_with_changed_business_semantics_stales_preproduction(tmp_path, change):
    store, original = _flow(tmp_path)
    before = store.read_object_json(original["pages"][0]["page"])
    def mutate(page):
        nodes, edge = page["visual_spec"]["nodes"], page["visual_spec"]["edges"][0]
        if change == "responsibility":
            nodes[0]["responsibility_refs"], nodes[1]["responsibility_refs"] = (
                nodes[1]["responsibility_refs"], nodes[0]["responsibility_refs"])
        elif change == "cell_ownership":
            rows = page["customer_visible"]["body_blocks"][1]["rows"]
            rows[0]["cells"][1], rows[1]["cells"][1] = rows[1]["cells"][1], rows[0]["cells"][1]
        elif change == "arrow":
            edge["from"], edge["to"] = edge["to"], edge["from"]
        elif change == "label_owner":
            nodes[0]["label_ref"], nodes[1]["label_ref"] = nodes[1]["label_ref"], nodes[0]["label_ref"]
        else:
            page["content_mapping"]["visible_links"][0]["narrative_node_ids"] = []
    current = _page_edit(store, mutate)
    after = store.read_object_json(current["pages"][0]["page"])
    assert sorted(atom["text"] for atom in content.visible_atoms(before)) == sorted(
        atom["text"] for atom in content.visible_atoms(after))
    _assert_gate(store, original, allowed=False, missing=content_review.BASE_UNITS)


@pytest.mark.parametrize("change", ["role", "qualification", "other_page_progression", "time_budget", "order"])
def test_relevant_plan_role_or_global_progression_stales_review(tmp_path, change):
    store, original = _flow(tmp_path)
    def mutate(value):
        if change == "role":
            value["page_roles"][0]["role"] = "新页职责"
        elif change == "qualification":
            value["page_roles"][0]["required_qualifications"].append("q-new")
        elif change == "other_page_progression":
            value["page_roles"][1]["transition_to_next"] = "后续论证推进改变"
        elif change == "time_budget":
            value["time_budget"]["total_seconds"] = 90
    _plan_edit(store, mutate, reverse_order=change == "order")
    _assert_gate(store, original, allowed=False, missing=content_review.BASE_UNITS)


@pytest.mark.parametrize("change", ["density", "profile", "timing", "other_qualification", "audit_only"])
def test_unconsumed_plan_fields_do_not_stale_current_review(tmp_path, change):
    store, original = _flow(tmp_path)
    def mutate(value):
        if change == "density":
            value["page_roles"][1]["density_rationale"] = "另一页的新密度解释，正文未变"
        elif change == "profile":
            value["page_roles"][1]["content_profile"] = "data_dense"
        elif change == "timing":
            value["page_roles"][0]["timing_seconds"] = 99
        elif change == "other_qualification":
            value["page_roles"][1]["required_qualifications"].append("q-other")
    current = _plan_edit(store, mutate)
    assert current["content_plan"] != original["content_plan"]
    _assert_gate(store, original, allowed=True)


def test_svg_geometry_bytes_change_without_changing_editorial_gate(tmp_path):
    store, original = _flow(tmp_path)
    for offset in (0, 100):
        before = store.load_document()
        page_ref = before["pages"][0]["page"]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
               f'<g transform="translate(0 {offset})"><g data-node-id="model"><rect x="100" y="50" width="200" '
               'height="80"/><text x="120" y="90">模型</text></g><g data-node-id="human"><rect x="600" y="50" '
               'width="200" height="80"/><text x="620" y="90">人工</text></g><path data-edge-id="confirm" '
               'data-edge-from="model" data-edge-to="human" d="M 300 90 L 600 90"/></g></svg>').encode()
        ET.fromstring(svg)
        file_ref = store.put_blob(svg, ext="svg")
        artifact = {"schema_version": "deck_artifact.v1", "artifact_id": "diagnostic-svg-" + str(offset),
                    "page_id": "p1", "role": "svg", "file": file_ref, "media_type": "image/svg+xml",
                    "created_at": "2026-10-15T00:00:00Z", "dependencies": [
                        {"kind": "content", "identity": "page:p1", "sha256": page_ref["sha256"]}],
                    "derived_from": [page_ref], "provenance": {"source_type": "tool_generated",
                        "tool": "synthetic-geometry-diagnostic"}, "reference_regions": [],
                    "limitations": ["Diagnostic SVG; no completeness or visual-quality claim"], "editability": "unknown"}
        models.validate_artifact_semantics(artifact)
        updated = copy.deepcopy(before)
        updated["pages"][0]["svg"] = store.put_json_object(artifact)
        _commit(store, before, updated, "Only actual SVG geometry changed")
        _assert_gate(store, original, allowed=True)
    current = store.load_document()
    assert current["pages"][0]["page"] == original["pages"][0]["page"]
    assert current["content_plan"] == original["content_plan"]


def test_speech_notes_change_invalidates_only_speech_unit(tmp_path):
    store, original = _flow(tmp_path, speech=True)
    def mutate(page):
        page["speaker_notes"] = "新的讲述顺序，屏幕责任链不变。"
        page["content_mapping"]["speech_segments"][0]["end_codepoint"] = len(page["speaker_notes"])
    _page_edit(store, mutate)
    _assert_gate(store, original, allowed=False, missing=["speech"])


def test_speech_segment_edit_invalidates_only_speech_unit(tmp_path):
    store, original = _flow(tmp_path, speech=True)
    _page_edit(store, lambda page: page["content_mapping"]["speech_segments"][0].update(kind="verbatim"))
    _assert_gate(store, original, allowed=False, missing=["speech"])


def test_page_timing_change_invalidates_only_speech_unit(tmp_path):
    store, original = _flow(tmp_path, speech=True)
    _plan_edit(store, lambda value: value["page_roles"][0].update(timing_seconds=90))
    _assert_gate(store, original, allowed=False, missing=["speech"])


def test_other_page_timing_is_outside_scoped_speech_review(tmp_path):
    store, original = _flow(tmp_path, speech=True)
    _plan_edit(store, lambda value: value["page_roles"][1].update(timing_seconds=90))
    _assert_gate(store, original, allowed=True)
