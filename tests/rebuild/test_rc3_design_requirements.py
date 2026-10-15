"""RC3-03 resolver diagnostics: synthetic stored objects, no model/image calls.

The positive relation/layout cases are schema-valid Pages. Object insertion is
an isolated resolver fixture, never production evidence or an authorization.
"""
import copy

import pytest

from deck_master import content, models
from deck_master.design_requirements import (page_semantic_projection, plan_global_projection,
                                            plan_page_projection, resolve_content_requirements)
from deck_master.models import ModelError
from deck_master.store import Store


def _page(page_id):
    return {"schema_version": "deck_page_package.v2", "page_id": page_id,
            "customer_visible": {
                "title": "人工确认后提交", "subtitle": "保留单位与归属",
                "body_blocks": [
                    {"id": "rule", "type": "paragraph", "text": "模型拟稿，人工确认后提交。"},
                    {"id": "cost", "type": "table", "columns": [
                        {"id": "owner", "label": "主体"}, {"id": "amount", "label": "成本（万元）"}],
                     "rows": [
                         {"id": "human", "cells": [{"column_id": "owner", "display_text": "人工"},
                             {"column_id": "amount", "display_text": "12", "value": 12, "unit": "万元"}]},
                         {"id": "model", "cells": [{"column_id": "owner", "display_text": "模型"},
                             {"column_id": "amount", "display_text": "6", "value": 6, "unit": "万元"}]}]}],
                "labels": [{"id": "human", "text": "人工"}, {"id": "model", "text": "模型"}],
                "footnotes": [{"id": "scope", "text": "仅比较指定记录，不外推节约率。"}],
                "callouts": [{"id": "limit", "text": "人工承担最终确认责任。"}]},
            "speaker_notes": "",
            "visual_spec": {"intent": "表现实际责任与提交顺序", "layout_hint": "左右排列",
                "reference_mode": "new_design",
                "nodes": [{"node_id": "human", "label_ref": f"atom:{page_id}:label:human:text",
                           "status": "existing", "responsibility_refs": [f"atom:{page_id}:callout:limit:text"]},
                          {"node_id": "model", "label_ref": f"atom:{page_id}:label:model:text",
                           "status": "proposed", "responsibility_refs": [f"atom:{page_id}:block:rule:text"]}],
                "edges": [{"edge_id": "confirm", "from": "model", "to": "human",
                           "direction": "forward", "relationship": "人工核对后提交"}]}}


def _narrative():
    return {"schema_version": "narrative.v1", "narrative_id": "argument", "version": 1,
            "project_id": "proj", "origin": "host_composed", "maturity": "argument", "input_basis": [],
            "communication_job": {"mode": "train", "audience_fact_key": "task.audience",
                "audience_question": "谁确认", "desired_outcome": "保留真实责任",
                "observable_success": "能解释人工确认", "use_mode": "live", "primary_use": "live"},
            "central_node_id": "n1", "nodes": [{"node_id": "n1", "role": "claim",
                "statement": "人工承担确认责任", "authority": "instruction", "source_links": [],
                "qualification_node_ids": ["q1"], "unresolved_issue_ids": []}] + [
                {"node_id": identity, "role": "qualification", "statement": text,
                 "authority": "instruction", "source_links": [], "qualification_node_ids": [], "unresolved_issue_ids": []}
                for identity, text in (("q1", "仅比较指定记录，不外推节约率。"),
                                       ("q-new", "新的适用限制"), ("q-other", "另一页限定"))],
            "edges": [], "issues": [], "alternatives": [], "previous_ref": None}


def _scope(page_ids=("p1", "p2")):
    return {"subject": "pages", "page_ids": list(page_ids), "page_manifest_ref": None,
            "external_artifact_ref": None, "layers": ["design"],
            "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"}


def _evidence(store):
    return {"kind": "host_attested_instruction", "source_ref": store.put_json_object(
                {"synthetic": "explicit diagnostic instruction, never a real approval"}),
            "source_locator": "synthetic:instruction", "actor_id": None, "assurance": "host_attested",
            "transport_receipt_ref": None, "presentation_ref": None}


def _snapshot(tmp_path, *, imported=False, legacy=False):
    store = Store(tmp_path / "synthetic-resolver")
    store.ensure_layout()
    doc = models.new_document(project_id="proj", task={"brief": "Synthetic resolver diagnostic"})
    narrative_ref = None if imported or legacy else store.put_json_object(_narrative())
    if narrative_ref:
        doc["narrative"] = narrative_ref
    for page_id in ("p1", "p2"):
        page = _page(page_id)
        if not legacy:
            page["content_mapping"] = {"narrative_ref": narrative_ref, "plan_role_page_id": page_id,
                "visible_links": [{"element_ref": atom, "narrative_node_ids": [] if imported else ["n1"],
                                   "source_links": []} for atom in sorted(content.atom_ids(page))],
                "speech_segments": []}
        models.validate_page_semantics(page)
        content.validate_page_references(page)
        doc["pages"].append({"page_id": page_id, "page": store.put_json_object(page), "blueprint": None,
                             "svg": None, "svg_preview": None, "ppt_preview": None})
    if legacy:
        models.validate_document_semantics(doc)
        return store, doc, None
    evidence = _evidence(store)
    doc["collaboration"] = {"schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "independent_model_or_human",
                            "requirement_origin": "default_new_argument", "override_decision_ref": None},
        "request": {"request_id": "request-1", "intent": "design_trial", "content_intent": None,
            "instruction_evidence": evidence, "scope": _scope(), "paused": False, "pause_reason": None,
            "closed": False, "closed_reason": None, "background_request_ids": [], "variant": None},
        "decisions": [], "authorizations": []}
    models.require_writer(doc, "rc3.v1")
    roles = [{"page_id": pid, "role": "明确人工责任", "audience_question": "谁确认？原值",
              "intended_takeaway": "人工确认后才提交；不省略", "narrative_node_ids": [] if imported else ["n1"],
              "source_links": [], "required_qualifications": ["仅比较指定记录，不外推节约率。"] if imported else ["q1"],
              "content_profile": "mixed", "density_rationale": "必须同时保留两主体、成本单位及人工确认链；这是原文。",
              "timing_seconds": 45, "transition_to_next": "转入例外条件"} for pid in ("p1", "p2")]
    plan = {"schema_version": "content_plan.v2", "plan_id": "plan-1", "version": 1,
            "project_id": "proj", "task_id": None, "origin": "user_imported" if imported else "host_composed",
            "basis": {"revision_id": doc["revision_id"], "input_digest": models.compute_input_digest(doc)},
            "previous_ref": None, "mode": "imported_mapping" if imported else "bound",
            "narrative_ref": narrative_ref,
            "imported_manuscript": {"source_ref": evidence["source_ref"], "claimed_confirmation_evidence": evidence,
                "preserve_mainline": True, "unresolved_mapping_items": ["未推断论证关系"]} if imported else None,
            "input": {"schema_version": "content_plan_input.v2", "chapters": [
                {"chapter_id": "c1", "title": "责任与例外", "page_ids": ["p1", "p2"]}],
                "page_order": ["p1", "p2"], "page_roles": roles,
                "page_budget": {"exact": 2, "target": None, "max": 2},
                "time_budget": {"total_seconds": 120, "speaking_seconds": 90,
                                "interaction_seconds": 30, "constraint": "hard"},
                "speech_policy": {"mode": "none", "source": "default", "output": "none"},
                "issues": [], "tradeoff_issue_ids": []},
            "page_links": [{"page_id": entry["page_id"], "page_ref": entry["page"],
                            "plan_role_page_id": entry["page_id"]} for entry in doc["pages"]]}
    models.validate_content_plan_semantics(plan)
    doc["content_plan"] = store.put_json_object(plan)
    models.validate_document_semantics(doc)
    return store, doc, plan


def _resolve(store, doc, **kwargs):
    return resolve_content_requirements(store, doc, doc["pages"][0]["page"], **kwargs)


def _replace_plan(store, doc, plan):
    models.validate_content_plan_semantics(plan)
    doc["content_plan"] = store.put_json_object(plan)


def test_complete_raw_requirements_and_basis_are_readonly(tmp_path):
    store, doc, plan = _snapshot(tmp_path)
    original = copy.deepcopy(doc)
    files = {str(path): path.read_bytes() for path in store.deck_root.rglob("*") if path.is_file()}
    result = _resolve(store, doc)
    req, basis = result["content_requirements"], result["content_basis"]
    role = plan["input"]["page_roles"][0]
    assert req == {"schema_version": "content_requirements.v1", "mode": "planned", "page_id": "p1",
        "page_role": {key: role[key] for key in ("role", "audience_question", "intended_takeaway", "transition_to_next")},
        "content_profile": role["content_profile"], "density_rationale": role["density_rationale"],
        "required_qualifications": role["required_qualifications"], "visual_intent": "表现实际责任与提交顺序",
        "layout_hint": "左右排列", "structure_refs": {"atom_ids": sorted(content.atom_ids(_page("p1"))),
                                                        "node_ids": ["human", "model"], "edge_ids": ["confirm"]}}
    assert basis["page_ref"] == doc["pages"][0]["page"] and basis["plan_ref"] == doc["content_plan"]
    assert basis["recipe_ref"] is None and basis["decision_refs"] == []
    assert all(len(basis["consumed"][key]) == 64 for key in
               ("page_semantics_sha256", "plan_page_sha256", "plan_global_sha256"))
    req["required_qualifications"].append("cannot mutate Plan")
    assert doc == original and store.read_object_json(doc["content_plan"]) == plan
    assert files == {str(path): path.read_bytes() for path in store.deck_root.rglob("*") if path.is_file()}


def test_legacy_no_plan_fidelity_has_honest_null_fields(tmp_path):
    store, doc, _ = _snapshot(tmp_path, legacy=True)
    result = _resolve(store, doc)
    req = result["content_requirements"]
    assert req["mode"] == "fidelity" and req["page_role"] is None
    assert req["content_profile"] is None and req["density_rationale"] is None
    assert req["required_qualifications"] == []
    assert req["structure_refs"]["node_ids"] == ["human", "model"]
    assert result["content_basis"]["plan_ref"] is None
    assert plan_global_projection(None) is None


def test_imported_null_narrative_retains_actual_source_and_available_fields(tmp_path):
    store, doc, plan = _snapshot(tmp_path, imported=True)
    result = _resolve(store, doc)
    assert result["content_requirements"]["mode"] == "fidelity"
    assert result["content_requirements"]["density_rationale"] == plan["input"]["page_roles"][0]["density_rationale"]
    global_value = plan_global_projection(plan)
    assert global_value["narrative_ref"] is None
    assert global_value["imported_manuscript"] == plan["imported_manuscript"]
    assert "narrative" not in doc


def test_imported_real_mapping_without_roles_returns_honest_nulls(tmp_path):
    store, doc, plan = _snapshot(tmp_path, imported=True)
    plan["input"]["page_roles"] = []
    _replace_plan(store, doc, plan)
    models.validate_document_semantics(doc)
    result = _resolve(store, doc)
    req, basis = result["content_requirements"], result["content_basis"]
    assert req["mode"] == "fidelity"
    assert req["page_role"] is None and req["content_profile"] is None and req["density_rationale"] is None
    assert req["required_qualifications"] == []
    assert req["structure_refs"]["atom_ids"] == sorted(content.atom_ids(_page("p1")))
    assert req["visual_intent"] == _page("p1")["visual_spec"]["intent"]
    assert basis["page_ref"] == doc["pages"][0]["page"] and basis["plan_ref"] == doc["content_plan"]
    assert "narrative" not in doc and plan["narrative_ref"] is None
    global_value = plan_global_projection(plan)
    assert global_value["imported_manuscript"] == plan["imported_manuscript"]
    assert global_value["progression"] == [{"page_id": pid, "role": None, "audience_question": None,
        "intended_takeaway": None, "transition_to_next": None} for pid in ["p1", "p2"]]
    assert store.read_object_json(doc["pages"][0]["page"])["customer_visible"] == _page("p1")["customer_visible"]


def test_imported_partial_roles_preserves_only_actual_role_values(tmp_path):
    store, doc, plan = _snapshot(tmp_path, imported=True)
    second_role = copy.deepcopy(plan["input"]["page_roles"][1])
    plan["input"]["page_roles"] = [second_role]
    _replace_plan(store, doc, plan)
    unknown = _resolve(store, doc)["content_requirements"]
    known = resolve_content_requirements(store, doc, doc["pages"][1]["page"])["content_requirements"]
    assert unknown["page_role"] is None and unknown["content_profile"] is None
    assert unknown["required_qualifications"] == []
    assert known["mode"] == "fidelity" and known["density_rationale"] == second_role["density_rationale"]
    assert known["page_role"]["intended_takeaway"] == second_role["intended_takeaway"]
    assert known["required_qualifications"] == second_role["required_qualifications"]
    global_value = plan_global_projection(plan)
    assert global_value["progression"][0]["role"] is None
    assert global_value["progression"][1]["role"] == second_role["role"]
    assert [link["page_id"] for link in plan["page_links"]] == ["p1", "p2"]


@pytest.mark.parametrize("mode", ["bound", "planned"])
def test_only_imported_mapping_can_omit_page_roles(tmp_path, mode):
    store, doc, plan = _snapshot(tmp_path)
    plan["mode"] = mode
    plan["input"]["page_roles"] = []
    models.validate_schema("content_plan", plan)
    doc["content_plan"] = store.put_json_object(plan)
    with pytest.raises(ModelError, match="content_plan/input/page_roles"):
        _resolve(store, doc)


@pytest.mark.parametrize("field", ["layout_hint", "style_ref", "design_overrides", "notes", "internal"])
def test_legal_layout_style_and_notes_change_preserves_page_semantics(field):
    page = _page("p1")
    changed = copy.deepcopy(page)
    if field == "layout_hint":
        changed["visual_spec"]["layout_hint"] = "同节点、关系和归属，上下排列"
    elif field == "style_ref":
        changed["visual_spec"]["style_ref"] = "legal-style-id"
    elif field == "design_overrides":
        changed["visual_spec"]["design_overrides"] = {"language": "zh-CN"}
    elif field == "notes":
        changed["speaker_notes"] = "仅改变口播。"
    else:
        changed["internal_only"] = {"production_notes": "内部实现描述"}
    models.validate_page_semantics(changed)
    assert page_semantic_projection(changed) == page_semantic_projection(page)


@pytest.mark.parametrize("mutation", ["swap_cells", "unit", "value", "label_owner", "responsibility",
                                      "arrow", "direction", "relationship", "qualification"])
def test_schema_valid_semantic_changes_are_detected_with_same_texts(mutation):
    page = _page("p1")
    changed = copy.deepcopy(page)
    visual = changed["visual_spec"]
    table = changed["customer_visible"]["body_blocks"][1]
    if mutation == "swap_cells":
        table["rows"][0]["cells"][1], table["rows"][1]["cells"][1] = (
            table["rows"][1]["cells"][1], table["rows"][0]["cells"][1])
    elif mutation in ("unit", "value"):
        table["rows"][0]["cells"][1][mutation] = "元" if mutation == "unit" else 120
    elif mutation == "label_owner":
        visual["nodes"][0]["label_ref"], visual["nodes"][1]["label_ref"] = (
            visual["nodes"][1]["label_ref"], visual["nodes"][0]["label_ref"])
    elif mutation == "responsibility":
        visual["nodes"][0]["responsibility_refs"], visual["nodes"][1]["responsibility_refs"] = (
            visual["nodes"][1]["responsibility_refs"], visual["nodes"][0]["responsibility_refs"])
    elif mutation == "arrow":
        visual["edges"][0]["from"], visual["edges"][0]["to"] = "human", "model"
    elif mutation == "direction":
        visual["edges"][0]["direction"] = "both"
    elif mutation == "relationship":
        visual["edges"][0]["relationship"] = "模型直接提交"
    else:
        changed["customer_visible"]["footnotes"][0]["text"] = "可推广全部记录。"
    models.validate_page_semantics(changed)
    content.validate_page_references(changed)
    if mutation != "qualification":
        assert sorted(atom["text"] for atom in content.visible_atoms(changed)) == sorted(
            atom["text"] for atom in content.visible_atoms(page))
    assert page_semantic_projection(changed) != page_semantic_projection(page)


def test_illegal_node_coordinates_are_rejected():
    page = _page("p1")
    page["visual_spec"]["nodes"][0]["x"] = 100
    with pytest.raises(ModelError):
        page_semantic_projection(page)


def test_unrelated_density_timing_and_audit_do_not_change_consumed_slices(tmp_path):
    store, doc, plan = _snapshot(tmp_path)
    original = _resolve(store, doc)["content_basis"]["consumed"]
    changed = copy.deepcopy(plan)
    changed["version"] = 2
    changed["previous_ref"] = doc["content_plan"]
    changed["basis"]["revision_id"] = "audit-only-revision"
    changed["input"]["page_roles"][1]["density_rationale"] = "另一页实际密度改变"
    changed["input"]["page_roles"][1]["content_profile"] = "data_dense"
    changed["input"]["page_roles"][1]["timing_seconds"] = 20
    _replace_plan(store, doc, changed)
    result = _resolve(store, doc)["content_basis"]
    assert result["consumed"] == original
    assert result["plan_ref"] != changed["previous_ref"]


@pytest.mark.parametrize("mutation", ["page_density", "other_takeaway", "budget", "order", "chapter", "purpose"])
def test_actual_consumed_plan_fields_change_correct_slice(tmp_path, mutation):
    store, _, plan = _snapshot(tmp_path)
    changed = copy.deepcopy(plan)
    if mutation == "page_density":
        changed["input"]["page_roles"][0]["density_rationale"] += " 保留更多限定"
    elif mutation == "other_takeaway":
        changed["input"]["page_roles"][1]["intended_takeaway"] = "后续页面改变论证推进"
    elif mutation == "budget":
        changed["input"]["time_budget"]["total_seconds"] = 90
    elif mutation == "order":
        changed["input"]["page_order"].reverse()
    elif mutation == "chapter":
        changed["input"]["chapters"][0]["title"] = "新的推进章节"
    else:
        changed["input"]["speech_policy"] = {"mode": "cues", "source": "provided", "output": "pptx_notes"}
    models.validate_content_plan_semantics(changed)
    assert (plan_page_projection(plan, "p1") != plan_page_projection(changed, "p1")) == (mutation == "page_density")
    assert (plan_global_projection(plan) != plan_global_projection(changed)) == (mutation != "page_density")


@pytest.mark.parametrize("mutation", ["missing_plan", "foreign_plan", "old_link", "ghost_link", "role_link",
                                      "planned_only", "foreign_narrative", "wrong_page_mapping", "unknown_node"])
def test_schema_valid_snapshot_conflicts_refuse_fidelity_fallback(tmp_path, mutation):
    store, doc, plan = _snapshot(tmp_path)
    if mutation == "missing_plan":
        doc.pop("content_plan")
    elif mutation == "foreign_plan":
        plan["project_id"] = "another-project"
    elif mutation == "old_link":
        old_page = _page("p1")
        old_page["customer_visible"]["title"] = "历史 Page"
        plan["page_links"][0]["page_ref"] = store.put_json_object(old_page)
    elif mutation == "ghost_link":
        plan["page_links"][0]["page_id"] = "p3"
        plan["input"]["page_order"][0] = "p3"
        plan["input"]["page_roles"][0]["page_id"] = "p3"
        plan["input"]["chapters"][0]["page_ids"][0] = "p3"
    elif mutation == "role_link":
        plan["page_links"][0]["plan_role_page_id"] = "p2"
    elif mutation == "planned_only":
        plan["mode"] = "planned"
        plan["page_links"] = []
    elif mutation == "foreign_narrative":
        narrative = _narrative()
        narrative["version"] = 2
        plan["narrative_ref"] = store.put_json_object(narrative)
    elif mutation == "unknown_node":
        plan["input"]["page_roles"][0]["narrative_node_ids"] = ["missing-node"]
    else:
        page = store.read_object_json(doc["pages"][0]["page"])
        page["content_mapping"]["plan_role_page_id"] = "p2"
        doc["pages"][0]["page"] = store.put_json_object(page)
        plan["page_links"][0]["page_ref"] = doc["pages"][0]["page"]
    if mutation != "missing_plan":
        _replace_plan(store, doc, plan)
    with pytest.raises(ModelError):
        _resolve(store, doc)


@pytest.mark.parametrize("field", ["role", "content_profile", "density_rationale"])
def test_bound_missing_required_fields_is_contract_error_not_fidelity(tmp_path, field):
    store, doc, plan = _snapshot(tmp_path)
    del plan["input"]["page_roles"][0][field]
    doc["content_plan"] = store.put_json_object(plan)
    with pytest.raises(ModelError):
        _resolve(store, doc)


def test_imported_mapping_requires_real_source_and_evidence_objects(tmp_path):
    store, doc, plan = _snapshot(tmp_path, imported=True)
    source = plan["imported_manuscript"]["source_ref"]
    (store.project_root / source["path"]).unlink()
    with pytest.raises(ModelError, match="imported_manuscript/source_ref"):
        _resolve(store, doc)


def test_actual_page_ref_must_belong_to_selected_snapshot(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    historical = _page("p1")
    historical["customer_visible"]["title"] = "仅历史对象"
    ref = store.put_json_object(historical)
    with pytest.raises(ModelError, match="design_requirements/page_ref"):
        resolve_content_requirements(store, doc, ref)


def test_bound_null_narrative_cannot_enter_fidelity(tmp_path):
    store, doc, plan = _snapshot(tmp_path)
    doc.pop("narrative")
    plan["narrative_ref"] = None
    _replace_plan(store, doc, plan)
    with pytest.raises(ModelError, match="bound argument Plan requires"):
        _resolve(store, doc)


def test_bound_missing_page_mapping_cannot_enter_fidelity(tmp_path):
    store, doc, plan = _snapshot(tmp_path)
    page = store.read_object_json(doc["pages"][0]["page"])
    page.pop("content_mapping")
    models.validate_page_semantics(page)
    ref = store.put_json_object(page)
    doc["pages"][0]["page"] = ref
    plan["page_links"][0]["page_ref"] = ref
    _replace_plan(store, doc, plan)
    with pytest.raises(ModelError, match="content_mapping"):
        _resolve(store, doc)


def _recipe(store, doc):
    page_ref = doc["pages"][0]["page"]
    reference = store.put_json_object({"synthetic": "reference for resolver shape only"})
    recipe = {"schema_version": "style_recipe.v1", "project_id": "proj", "base_revision": doc["revision_id"],
        "input": {"schema_version": "style_input.v1", "project_id": "proj", "base_revision": doc["revision_id"],
            "reference": {"page_id": "p1", "revision_id": doc["revision_id"], "artifact_ref": reference,
                          "role": "reference"}, "target_page_ids": ["p1"], "instruction": "保留全部业务内容"},
        "targets": [{"page_id": "p1", "page_ref": page_ref, "blueprint_ref": None, "content": {}}],
        "reference_sources": {}, "dimensions": {"palette": "蓝色"}, "conflicts": [], "diff": [],
        "preserve_target_content": True, "suggestion_state": "confirmed", "recipe_id": "recipe-1", "version": 1,
        "parent_ref": None, "proposal_ref": reference}
    models.validate_schema("style_recipe", recipe)
    ref = store.put_json_object(recipe)
    doc["style_recipes"] = [ref]
    return ref


def test_compiled_recipe_only_enters_basis_and_cannot_override_content(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    ref = _recipe(store, doc)
    original = _resolve(store, doc)["content_requirements"]
    result = _resolve(store, doc, recipe_ref=ref,
                      recipe_parameters={"density": "sparse", "palette": {"accent": "blue"}})
    assert result["content_requirements"] == original
    assert result["content_basis"]["recipe_ref"] == ref
    assert len(result["content_basis"]["consumed"]["recipe_parameters_sha256"]) == 64
    with pytest.raises(ModelError, match="recipe_parameters"):
        _resolve(store, doc, recipe_ref=ref)
    with pytest.raises(ModelError, match="recipe_ref"):
        _resolve(store, doc, recipe_parameters={"density": "sparse"})


def test_recipe_for_another_page_cannot_enter_basis(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    ref = _recipe(store, doc)
    recipe = store.read_object_json(ref)
    recipe["input"]["target_page_ids"] = ["p2"]
    recipe["targets"] = [{"page_id": "p2", "page_ref": doc["pages"][1]["page"],
                          "blueprint_ref": None, "content": {}}]
    models.validate_schema("style_recipe", recipe)
    other_ref = store.put_json_object(recipe)
    doc["style_recipes"] = [other_ref]
    with pytest.raises(ModelError, match="recipe does not apply"):
        _resolve(store, doc, recipe_ref=other_ref, recipe_parameters={"density": "sparse"})


@pytest.mark.parametrize("parameters", [[], {"spacing": float("nan")}, {"spacing": object()}])
def test_noncanonical_compiled_parameters_raise_contract_path(tmp_path, parameters):
    store, doc, _ = _snapshot(tmp_path)
    ref = _recipe(store, doc)
    with pytest.raises(ModelError, match="design_requirements/recipe_parameters"):
        _resolve(store, doc, recipe_ref=ref, recipe_parameters=parameters)


def _decision(store, doc, **over):
    decision = {"schema_version": "collaboration_decision.v1", "decision_id": "style-1", "project_id": "proj",
        "request_id": "request-1", "topic": "style", "subject_refs": [], "scope": _scope(),
        "value": {"palette": "blue"}, "disposition": "accepted", "authority_mode": "direct_user",
        "evidence": _evidence(store), "delegation_ref": None, "basis": [], "status": "active",
        "replaces": None, "invalidated_by": None, "created_at": "2026-10-14T10:00:00Z"}
    decision.update(over)
    models.validate_decision_semantics(decision)
    ref = store.put_json_object(decision)
    doc["collaboration"]["decisions"] = [ref]
    return ref, decision


def test_design_decision_consumes_registered_effective_slice_without_audit(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    ref, decision = _decision(store, doc)
    first = _resolve(store, doc, decision_refs=[ref])["content_basis"]
    decision["created_at"] = "2026-10-14T11:00:00Z"
    newer = store.put_json_object(decision)
    doc["collaboration"]["decisions"] = [newer]
    second = _resolve(store, doc, decision_refs=[newer])["content_basis"]
    assert first["decision_refs"] != second["decision_refs"]
    assert first["consumed"]["decision_slices"][0]["sha256"] == second["consumed"]["decision_slices"][0]["sha256"]


def test_historical_decision_ref_cannot_masquerade_as_current_effective_ref(tmp_path):
    store, doc, _ = _snapshot(tmp_path)
    old_ref, decision = _decision(store, doc)
    decision["value"] = {"palette": "green"}
    decision["replaces"] = old_ref
    new_ref = store.put_json_object(decision)
    doc["collaboration"]["decisions"] = [old_ref, new_ref]
    with pytest.raises(ModelError, match="not the current version"):
        _resolve(store, doc, decision_refs=[old_ref])
    assert _resolve(store, doc, decision_refs=[new_ref])["content_basis"]["decision_refs"] == [new_ref]


@pytest.mark.parametrize("mutation", ["withdrawn", "rejected", "wrong_scope", "wrong_topic", "not_current", "superseded_request"])
def test_inapplicable_or_ineffective_design_decisions_rejected(tmp_path, mutation):
    store, doc, _ = _snapshot(tmp_path)
    extra = {"status": "withdrawn"} if mutation == "withdrawn" else {}
    if mutation == "rejected":
        extra["disposition"] = "rejected"
    elif mutation == "wrong_scope":
        extra["scope"] = _scope(["p2"])
    elif mutation == "wrong_topic":
        extra["topic"] = "manuscript"
    ref, _ = _decision(store, doc, **extra)
    if mutation == "not_current":
        doc["collaboration"]["decisions"] = []
    elif mutation == "superseded_request":
        doc["collaboration"]["request"]["request_id"] = "request-2"
    with pytest.raises(ModelError, match="decision_refs/0"):
        _resolve(store, doc, decision_refs=[ref])
