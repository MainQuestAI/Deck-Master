"""Real prompt completeness, per-page dependencies and semantic counterexamples."""

from copy import deepcopy

import pytest

from deck_master import dependency_slices, design_requirements, models, production


def _context(created_store):
    store = created_store
    doc = store.load_document()
    page = {
        "schema_version": "deck_page_package.v2",
        "page_id": "p1",
        "customer_visible": {"title": "人工核对后提交", "body_blocks": []},
        "speaker_notes": "口播不能混入 prompt",
        "visual_spec": {
            "intent": "交接",
            "reference_mode": "new_design",
            "layout_hint": "先核对再提交",
            "nodes": [{"node_id": "n-a", "label_ref": "atom:p1:title"}, {"node_id": "n-b"}],
            "edges": [{"edge_id": "e-a", "from": "n-a", "to": "n-b", "direction": "forward"}],
        },
        "internal_only": {"production_notes": "内部编号必须不进正文"},
    }
    pref = store.put_json_object(page)
    doc["pages"] = [{"page_id": "p1", "page": pref}]
    roles = [
        {
            "page_id": i,
            "role": "解释交接",
            "audience_question": "谁核对后提交？",
            "intended_takeaway": "人工保留提交职责",
            "transition_to_next": None,
            "content_profile": "mechanism",
            "density_rationale": "四分支完整责任与异常，不概括",
            "required_qualifications": ["接口只读，人工核对后提交"],
            "narrative_node_ids": ["n-a"],
        }
        for i in ["p1", "p2"]
    ]
    plan = {
        "schema_version": "content_plan.v2",
        "mode": "bound",
        "input": {"page_roles": roles},
        "page_links": [{"page_id": "p1", "page_ref": pref}],
    }
    doc["content_plan"] = store.put_json_object(plan)
    return store, doc, page, plan


def test_complete_density_fields_enter_actual_prompt_and_frozen_design_context(created_store):
    store, doc, page, _ = _context(created_store)
    design = design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])
    prepared = production.project_prompt(page, design, [])
    req = prepared["projection"]["content_requirements"]
    assert req["density_rationale"] == "四分支完整责任与异常，不概括"
    assert req["required_qualifications"] == ["接口只读，人工核对后提交"]
    assert req["page_role"]["audience_question"] == "谁核对后提交？"
    assert req["structure_refs"]["edge_ids"] == ["e-a"]
    assert "四分支完整责任与异常，不概括" in prepared["prompt"]
    assert "口播不能混入 prompt" not in prepared["prompt"]
    assert "内部编号必须不进正文" not in prepared["prompt"]
    assert ".deckmaster/objects/" not in prepared["prompt"]


def test_other_plan_page_or_notes_change_does_not_change_consumed_page_slice(created_store):
    store, doc, page, plan = _context(created_store)
    before = design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])["content_basis"]
    plan["input"]["page_roles"][1]["density_rationale"] = "另一页改稿"
    doc["content_plan"] = store.put_json_object(plan)
    after = design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])["content_basis"]
    assert before["plan_ref"] != after["plan_ref"]
    assert before["consumed_sha256"] == after["consumed_sha256"]
    old = dependency_slices.make_dependency_slice(store, doc, kind="artifact", identity="page:p1", projection="visual_input")
    page["speaker_notes"] = "仅备注变更"
    doc["pages"][0]["page"] = store.put_json_object(page)
    new = dependency_slices.make_dependency_slice(store, doc, kind="artifact", identity="page:p1", projection="visual_input")
    assert old["sha256"] == new["sha256"]


def test_new_blueprint_freshness_uses_consumed_role_and_visual_input(created_store):
    store, doc, page, plan = _context(created_store)
    resolved = design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])
    task = {"scope_pages": ["p1"], "preparation": {"content_basis": resolved["content_basis"], "resolved_design_context": resolved}}
    assert design_requirements.task_basis_current(store, doc, task)
    plan["input"]["page_roles"][1]["role"] = "只改另一页"
    doc["content_plan"] = store.put_json_object(plan)
    assert design_requirements.task_basis_current(store, doc, task)
    page["speaker_notes"] = "仅补口播限定"
    doc["pages"][0]["page"] = store.put_json_object(page)
    plan["page_links"][0]["page_ref"] = doc["pages"][0]["page"]
    doc["content_plan"] = store.put_json_object(plan)
    assert design_requirements.task_basis_current(store, doc, task)
    plan["input"]["page_roles"][0]["required_qualifications"] = ["核对职责改变"]
    doc["content_plan"] = store.put_json_object(plan)
    assert not design_requirements.task_basis_current(store, doc, task)


def test_arrow_direction_and_cell_ownership_are_semantic_but_layout_is_not(created_store):
    _, _, page, _ = _context(created_store)
    before = design_requirements.semantic_digest(page)
    moved = deepcopy(page)
    moved["visual_spec"]["nodes"][0]["x"] = 500
    moved["visual_spec"]["layout_hint"] = "上下排列"
    assert design_requirements.semantic_digest(moved) == before
    reversed_page = deepcopy(page)
    reversed_page["visual_spec"]["edges"][0]["from"], reversed_page["visual_spec"]["edges"][0]["to"] = "n-b", "n-a"
    assert design_requirements.semantic_digest(reversed_page) != before
    table = deepcopy(page)
    table["customer_visible"]["body_blocks"] = [
        {"block_id": "table", "type": "table", "columns": ["甲", "乙"], "rows": [["人工核对", "模型草稿"]]}
    ]
    swapped = deepcopy(table)
    swapped["customer_visible"]["body_blocks"][0]["rows"][0].reverse()
    assert design_requirements.semantic_digest(swapped) != design_requirements.semantic_digest(table)


def test_stale_plan_binding_is_rejected_and_fidelity_does_not_invent_a_plan(created_store):
    store, doc, page, plan = _context(created_store)
    plan["page_links"][0]["page_ref"] = store.put_json_object({"other": "revision"})
    doc["content_plan"] = store.put_json_object(plan)
    with pytest.raises(models.ModelError, match="Page/Plan basis changed"):
        design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])
    doc["content_plan"] = None
    req = design_requirements.resolve(store, doc, doc["pages"][0], doc["design_context"])["content_requirements"]
    assert req["mode"] == "fidelity"
    assert req["page_role"] is None and req["density_rationale"] is None
    assert req["structure_refs"]["edge_ids"] == ["e-a"]
