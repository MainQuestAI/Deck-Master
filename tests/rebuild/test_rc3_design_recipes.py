"""Synthetic L1 tests for the pure recipe core; no image calls or visual verdicts."""
from copy import deepcopy
import base64

import pytest

from deck_master import design_recipe
from deck_master.models import ModelError, default_design_context
from deck_master.store import Store


def page(page_id):
    return {"schema_version": "deck_page_package.v2", "page_id": page_id,
            "customer_visible": {"title": "人工确认后提交", "body_blocks": [
                {"id": "exceptions", "type": "table",
                 "columns": [{"id": "owner", "label": "责任人"}, {"id": "action", "label": "动作"}],
                 "rows": [{"id": "human", "cells": [{"column_id": "owner", "display_text": "人工"},
                                                      {"column_id": "action", "display_text": "确认"}]},
                          {"id": "model", "cells": [{"column_id": "owner", "display_text": "模型"},
                                                      {"column_id": "action", "display_text": "草拟"}]}]}]},
            "visual_spec": {"intent": "保留责任人和动作归属", "reference_mode": "new_design"}}


@pytest.fixture
def context(tmp_path):
    store = Store(tmp_path / "synthetic-core")
    doc = {"project_id": "proj", "revision_id": "rev-test", "design_context": default_design_context(),
           "pages": [{"page_id": pid, "page": store.put_json_object(page(pid))} for pid in ("p1", "p2")],
           "style_recipes": [], "style_references": []}
    return store, doc


def input_value(doc, *, intent="initial_design", ids=None):
    ids = ["p1", "p2"] if ids is None else ids
    style = doc["design_context"]["styles"][0]
    return {"schema_version": "style_input.v3", "project_id": doc["project_id"],
            "base_revision": doc["revision_id"], "intent": intent, "target_page_ids": ids,
            "instruction": "固定正文，明确关系，只调整视觉表达。", "reference_refs": [],
            "recipe_draft": {"palette": {"background": "#FFFFFF", "text": "#132133", "accent": "#006688"},
                             "typography": deepcopy(style["typography"]),
                             "density": "完整保留两行异常表，每行不拆分归属。",
                             "composition": "主链置上方，异常表置下方。",
                             "spacing": "四周保留48px安全边距，表格单元格保留12px内距。",
                             "lines": "主链使用2px实线单向箭头。",
                             "icons": "只在人工确认节点使用单色人物图标。", "allowed_overrides": []},
            "page_profiles": [{"page_id": pid, "profile": "mechanism", "density": "四节点主链加两行异常表",
                               "diagram": "四节点定性机制", "task": "正确区分模型草拟与人工确认"} for pid in ids],
            "layout_rationale": "关系不随位置调整改变。",
            "sample_targets": [{"page_id": pid, "coverage_risks": ["箭头方向", "表格归属"]} for pid in ids],
            "uncovered_cases": ["多单位数据图尚未覆盖"], "tradeoffs": ["保留全部限定，增加表格宽度"]}


def recipe(store, doc, value=None):
    proposal = design_recipe.build_proposal(store, doc, value or input_value(doc))
    proposal_ref = store.put_json_object(proposal)
    return design_recipe.confirmed_recipe(proposal, proposal_ref, recipe_id="recipe-test"), proposal


def synthetic_artifact(store, *, role, page_id=None):
    # A fixed synthetic PNG solely for hashing/read tests, never a real tool observation.
    blob = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHoQAAAAASUVORK5CYII=")
    file = store.put_blob(blob, ext="png")
    return store.put_json_object({"schema_version": "deck_artifact.v1", "artifact_id": "synthetic-" + (page_id or "style"),
                                  "page_id": page_id, "role": role, "file": file, "media_type": "image/png",
                                  "created_at": "2026-10-14T00:00:00Z", "dependencies": [], "derived_from": [],
                                  "provenance": {"source_type": "unknown"}, "limitations": ["Synthetic L1 data"]})


def external_reference(store, doc):
    original = synthetic_artifact(store, role="asset")
    record = {"schema_version": "style-reference.v1", "project_id": doc["project_id"], "reference_id": "ref-test",
              "artifact_ref": original, "preview_ref": original, "width": 1, "height": 1,
              "created_at": "2026-10-14T00:00:00Z"}
    doc["style_references"].append(store.put_json_object(record))
    return {"kind": "external", "reference_id": "ref-test", "artifact_ref": original, "role": "reference"}


def test_initial_two_page_planning_needs_no_old_image_and_has_no_write_authority(context):
    store, doc = context
    value = input_value(doc)
    before_doc, before_input = deepcopy(doc), deepcopy(value)
    proposal = design_recipe.build_proposal(store, doc, value)
    assert [target["page_id"] for target in proposal["targets"]] == ["p1", "p2"]
    assert all(target["blueprint_ref"] is None for target in proposal["targets"])
    assert proposal["reference_refs"] == []
    assert [(item["identity"], item["projection"]) for item in proposal["basis"]] == [
        ("page:p1", "visual_input"), ("page:p2", "visual_input")]
    assert doc == before_doc and value == before_input and store.read_current() is None
    assert "tasks" not in doc and "calls" not in proposal


def test_sample_matrix_can_cover_a_subset_without_requesting_all_scope_pages(context):
    store, doc = context
    value = input_value(doc)
    value["sample_targets"] = value["sample_targets"][:1]
    assert design_recipe.build_proposal(store, doc, value)["sample_targets"] == value["sample_targets"]


def test_parameters_execute_and_planning_prose_cannot_override_or_change_page(context):
    store, doc = context
    value = input_value(doc)
    value["layout_rationale"] = "背景解释提及另一配色 #FF0000；不是执行配置。"
    value["page_profiles"][0]["density"] = "规划说明保留原值"
    fixed, proposal = recipe(store, doc, value)
    actual_page = store.read_object_json(doc["pages"][0]["page"])
    before_page, before_design = deepcopy(actual_page), deepcopy(doc["design_context"])
    resolved = design_recipe.compile_design(actual_page, doc["design_context"], fixed, "p1")
    assert resolved["styles"][0]["colors"] == value["recipe_draft"]["palette"]
    assert resolved["styles"][0]["typography"] == value["recipe_draft"]["typography"]
    assert value["recipe_draft"]["density"] in resolved["styles"][0]["layout_notes"]
    assert "#FF0000" not in resolved["styles"][0]["layout_notes"]
    assert resolved["recipe_parameters"]["density"] == value["recipe_draft"]["density"]
    assert fixed["input"] == value and proposal["page_profiles"] == value["page_profiles"]
    assert actual_page == before_page and doc["design_context"] == before_design
    resolved["recipe_parameters"]["palette"]["accent"] = "#000000"
    assert fixed["parameters"]["palette"]["accent"] == "#006688"


@pytest.mark.parametrize("mutation", ["missing", "palette", "typography", "font", "size", "nan", "rule", "content", "unknown", "duplicate_override", "unallowed", "ghost_rule"])
def test_incomplete_or_untyped_or_semantic_parameters_are_rejected(context, mutation):
    store, doc = context
    value = input_value(doc)
    draft = value["recipe_draft"]
    if mutation == "missing":
        del draft["density"]
    elif mutation == "palette":
        draft["palette"] = "use green"
    elif mutation == "typography":
        draft["typography"]["font_family"] = "unknown independent field"
    elif mutation == "font":
        draft["typography"]["body_font_id"] = "unregistered"
    elif mutation == "size":
        draft["typography"]["body_size_pt"] = True
    elif mutation == "nan":
        draft["typography"]["body_size_pt"] = float("nan")
    elif mutation == "rule":
        draft["density"] = {"rules": ["another rule shape"]}
    elif mutation == "content":
        draft["customer_visible"] = {"title": "模型直接提交"}
    elif mutation == "unknown":
        draft["allowed_overrides"] = ["nodes"]
    elif mutation == "duplicate_override":
        draft["allowed_overrides"] = ["spacing", "spacing"]
    elif mutation == "unallowed":
        draft["page_rules"] = {"p1": {"spacing": "24px"}}
    else:
        draft["allowed_overrides"] = ["spacing"]
        draft["page_rules"] = {"ghost": {"spacing": "24px"}}
    with pytest.raises(ModelError):
        design_recipe.build_proposal(store, doc, value)


@pytest.mark.parametrize("mutation", ["ghost_target", "duplicate", "wrong_page_ref", "ghost_profile", "empty_risk", "extra_field", "old_revision"])
def test_target_and_coverage_inputs_are_real_and_explicit(context, mutation):
    store, doc = context
    value = input_value(doc)
    if mutation == "ghost_target":
        value["target_page_ids"] = ["ghost"]
    elif mutation == "duplicate":
        value["target_page_ids"] = ["p1", "p1"]
    elif mutation == "wrong_page_ref":
        doc["pages"][0]["page"] = doc["pages"][1]["page"]
    elif mutation == "ghost_profile":
        value["page_profiles"][0]["page_id"] = "ghost"
    elif mutation == "empty_risk":
        value["sample_targets"][0]["coverage_risks"] = []
    elif mutation == "extra_field":
        value["authority"] = "authorized"
    else:
        value["base_revision"] = "rev-old"
    with pytest.raises(ModelError):
        design_recipe.build_proposal(store, doc, value)


def test_restyle_requires_real_target_original_and_owned_fixed_reference(context):
    store, doc = context
    value = input_value(doc, intent="restyle", ids=["p1"])
    with pytest.raises(ModelError, match="fixed real style reference"):
        design_recipe.build_proposal(store, doc, value)
    reference = external_reference(store, doc)
    value["reference_refs"] = [reference]
    with pytest.raises(ModelError, match="actual current original image"):
        design_recipe.build_proposal(store, doc, value)
    doc["pages"][0]["blueprint"] = synthetic_artifact(store, role="blueprint", page_id="p1")
    fixed, proposal = recipe(store, doc, value)
    assert proposal["targets"][0]["blueprint_ref"] == doc["pages"][0]["blueprint"]
    assert design_recipe.recipe_references(fixed) == [reference]
    changed = deepcopy(fixed)
    changed["reference_refs"][0]["reference_id"] = "unowned"
    with pytest.raises(ModelError, match="immutable input"):
        design_recipe.recipe_references(changed)


@pytest.mark.parametrize("mutation", ["bare", "target_role", "duplicate", "mutable_uri"])
def test_style_references_cannot_be_unfixed_or_misrepresented(context, mutation):
    store, doc = context
    value = input_value(doc)
    reference = external_reference(store, doc)
    if mutation == "bare":
        value["reference_refs"] = [reference["artifact_ref"]]
    elif mutation == "target_role":
        value["reference_refs"] = [{**reference, "role": "edit_target"}]
    elif mutation == "duplicate":
        value["reference_refs"] = [reference, reference]
    else:
        value["reference_refs"] = [{**reference, "artifact_ref": {"path": "https://example.test/style.png", "sha256": "a" * 64}}]
    with pytest.raises(ModelError):
        design_recipe.build_proposal(store, doc, value)


def test_allowed_page_rules_are_executable_and_show_dimension_diff(context):
    store, doc = context
    value = input_value(doc)
    value["recipe_draft"]["allowed_overrides"] = ["spacing"]
    value["recipe_draft"]["page_rules"] = {"p1": {"spacing": "64px外边距，16px表格内距。"}}
    fixed, _ = recipe(store, doc, value)
    actual_page = store.read_object_json(doc["pages"][0]["page"])
    resolved = design_recipe.compile_design(actual_page, doc["design_context"], fixed, "p1")
    assert resolved["recipe_parameters"]["spacing"] == "64px外边距，16px表格内距。"
    assert resolved["recipe_overrides"] == [{"field": "spacing", "before": value["recipe_draft"]["spacing"],
                                             "after": "64px外边距，16px表格内距。", "source": "recipe.page_rules"}]
    assert design_recipe.effective_parameters(fixed, "p2")["spacing"] == value["recipe_draft"]["spacing"]
    with pytest.raises(ModelError, match="outside"):
        design_recipe.effective_parameters(fixed, "ghost")


def test_page_font_override_requires_recipe_permission_and_cannot_conflict(context):
    store, doc = context
    value = input_value(doc)
    actual_page = store.read_object_json(doc["pages"][0]["page"])
    actual_page["visual_spec"]["design_overrides"] = {"body_font_id": "heading"}
    fixed, _ = recipe(store, doc, value)
    with pytest.raises(ModelError, match="not allowed"):
        design_recipe.compile_design(actual_page, doc["design_context"], fixed, "p1")
    value["recipe_draft"]["allowed_overrides"] = ["typography"]
    fixed, _ = recipe(store, doc, value)
    resolved = design_recipe.compile_design(actual_page, doc["design_context"], fixed, "p1")
    assert resolved["styles"][0]["typography"]["body_font_id"] == "heading"
    assert resolved["recipe_overrides"][0]["field"] == "typography.body_font_id"
    value["recipe_draft"]["page_rules"] = {"p1": {"typography": deepcopy(value["recipe_draft"]["typography"])}}
    fixed, _ = recipe(store, doc, value)
    with pytest.raises(ModelError, match="conflict"):
        design_recipe.compile_design(actual_page, doc["design_context"], fixed, "p1")


def test_confirmation_retains_fixed_parent_and_does_not_mutate_it(context):
    store, doc = context
    parent, _ = recipe(store, doc)
    parent_ref = store.put_json_object(parent)
    proposal = design_recipe.build_proposal(store, doc, input_value(doc))
    proposal["input"]["parent_recipe_id"] = parent["recipe_id"]
    proposal["parent_recipe_ref"] = parent_ref
    proposal_ref = store.put_json_object(proposal)
    before = deepcopy(parent)
    child = design_recipe.confirmed_recipe(proposal, proposal_ref, recipe_id="recipe-next", parent_ref=parent_ref, parent=parent)
    assert child["version"] == 2 and child["parent_recipe_ref"] == parent_ref and child["proposal_ref"] == proposal_ref
    assert parent == before and child["scope"] == {"page_ids": ["p1", "p2"], "layers": ["design"]}
    with pytest.raises(ModelError, match="immutable parent"):
        design_recipe.confirmed_recipe(proposal, proposal_ref, recipe_id="recipe-bad")
    child["parameters"]["density"] = "another mutable execution value"
    with pytest.raises(ModelError, match="immutable input"):
        design_recipe.effective_parameters(child, "p1")


def test_confirmation_rejects_content_mismatching_fixed_ref(context):
    store, doc = context
    proposal = design_recipe.build_proposal(store, doc, input_value(doc))
    fixed_ref = store.put_json_object(proposal)
    proposal["instruction"] = "changed after freezing"
    with pytest.raises(ModelError, match="immutable Ref"):
        design_recipe.confirmed_recipe(proposal, fixed_ref, recipe_id="recipe-bad")


def test_feasibility_can_discuss_genuinely_planned_pages_without_fabricating_page_refs(context):
    store, doc = context
    doc["pages"] = []
    role = {"page_id": "planned", "role": "解释机制", "audience_question": "谁确认", "intended_takeaway": "人工确认",
            "narrative_node_ids": [], "source_links": [], "required_qualifications": [], "content_profile": "mechanism",
            "density_rationale": "保留定性主链", "timing_seconds": None, "transition_to_next": None}
    plan = {"schema_version": "content_plan.v2", "plan_id": "plan", "version": 1, "project_id": doc["project_id"],
            "task_id": None, "origin": "host_composed", "basis": {"revision_id": "rev-test", "input_digest": "a" * 64},
            "previous_ref": None, "mode": "planned", "narrative_ref": None, "imported_manuscript": None,
            "input": {"schema_version": "content_plan_input.v2", "chapters": [{"chapter_id": "c", "title": "机制", "page_ids": ["planned"]}],
                      "page_order": ["planned"], "page_roles": [role], "page_budget": {"exact": None, "target": 1, "max": None},
                      "time_budget": {"total_seconds": None, "speaking_seconds": None, "interaction_seconds": None, "constraint": "unspecified"},
                      "speech_policy": {"mode": "none", "source": "default", "output": "none"}, "issues": [], "tradeoff_issue_ids": []},
            "page_links": []}
    doc["content_plan"] = store.put_json_object(plan)
    value = input_value(doc, intent="feasibility", ids=["planned"])
    proposal = design_recipe.build_proposal(store, doc, value)
    assert proposal["targets"] == [] and proposal["sample_targets"][0]["page_id"] == "planned"
    assert proposal["basis"][0]["identity"] == "content_plan"
    assert doc["pages"] == [] and store.read_current() is None
    value["target_page_ids"] = ["ghost"]
    with pytest.raises(ModelError, match="absent"):
        design_recipe.build_proposal(store, doc, value)


def test_fidelity_page_note_change_does_not_change_visual_basis(context):
    store, doc = context
    first = design_recipe.build_proposal(store, doc, input_value(doc))
    actual_page = store.read_object_json(doc["pages"][0]["page"])
    actual_page["speaker_notes"] = "新的口播说明"
    doc["pages"][0]["page"] = store.put_json_object(actual_page)
    after = design_recipe.build_proposal(store, doc, input_value(doc))
    assert first["basis"][0]["sha256"] == after["basis"][0]["sha256"]
    assert first["basis"][0]["ref"] != after["basis"][0]["ref"]


def test_feasibility_without_pages_uses_actual_narrative_but_cannot_produce(context):
    store, doc = context
    doc["pages"] = []
    narrative = {"schema_version": "narrative.v1", "narrative_id": "nar", "version": 1,
                 "project_id": doc["project_id"], "origin": "host_composed", "maturity": "framing",
                 "input_basis": [], "communication_job": {"mode": "explain", "audience_fact_key": "task.audience",
                     "audience_question": "如何表达机制", "desired_outcome": "判断可行性", "observable_success": "看懂限制",
                     "use_mode": "live", "primary_use": "live"}, "central_node_id": None,
                 "nodes": [], "edges": [], "issues": [], "alternatives": [], "previous_ref": None}
    doc["narrative"] = store.put_json_object(narrative)
    value = input_value(doc, intent="feasibility", ids=[])
    fixed, proposal = recipe(store, doc, value)
    assert proposal["targets"] == [] and proposal["basis"] == [
        {"kind": "artifact", "identity": "narrative", "projection": "content", "ref": doc["narrative"], "sha256": doc["narrative"]["sha256"]}]
    assert store.read_current() is None and doc["pages"] == []
    with pytest.raises(ModelError, match="feasibility"):
        design_recipe.compile_design(page("p1"), doc["design_context"], fixed, "p1")
    del doc["narrative"]
    with pytest.raises(ModelError, match="actual Page, Narrative or Plan"):
        design_recipe.build_proposal(store, doc, value)
