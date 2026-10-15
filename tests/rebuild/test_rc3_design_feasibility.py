"""F5 zero-call design planning through public APIs; synthetic L1 content only.

Initial snapshots contain schema-valid immutable content, never fake images or
approval records. Requests and grants use the formal collaboration services.
"""
import copy
import uuid

import pytest

from deck_master import changes, collaboration, design_recipe, eligibility, models, service, styles
from deck_master.operations import OperationError
from deck_master.store import Store
from test_rc3_design_recipes import input_value, page
from test_rc3_design_requirements import _narrative
from test_rc3_notes_visual_inputs import _seed_imported_plan


def scope(page_ids, *, layers=None, manifest=None):
    return {"subject": "pages", "page_ids": list(page_ids), "page_manifest_ref": manifest,
            "external_artifact_ref": None, "layers": ["design"] if layers is None else layers,
            "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "exploratory"}


def evidence(store):
    return {"kind": "host_attested_instruction", "source_ref": store.put_json_object({
                "synthetic_l1": "Design feasibility only; no generated sample or production permission."}),
            "source_locator": "synthetic:design-feasibility", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def initial(tmp_path, kind):
    """A content-state fixture, with no Task/Review/Authorization bootstrap."""
    project = tmp_path / "design-only"
    store = Store(project)
    store.ensure_layout()
    doc = models.new_document(project_id="proj", task={"brief": "Synthetic mechanism layout feasibility"})
    doc["compatibility"] = {"project_format": "workbench.v3", "minimum_writer": "rc3.v1"}
    doc["collaboration"] = {"schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "independent_model_or_human",
                            "requirement_origin": "default_new_argument", "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": []}
    if kind == "page":
        doc["pages"] = [{"page_id": pid, "page": store.put_json_object(page(pid)), "blueprint": None,
                         "svg": None, "svg_preview": None, "ppt_preview": None} for pid in ("p1", "p2")]
    elif kind == "narrative":
        narrative = _narrative()
        models.validate_schema("narrative", narrative)
        doc["narrative"] = store.put_json_object(narrative)
    elif kind == "plan":
        roles = [{"page_id": pid, "role": "解释实际确认机制", "audience_question": "谁确认后提交？",
                  "intended_takeaway": "人工承担确认责任。", "narrative_node_ids": [], "source_links": [],
                  "required_qualifications": [], "content_profile": "mechanism", "density_rationale": "四节点主链，不制造数量判断。",
                  "timing_seconds": None, "transition_to_next": None} for pid in ("p1", "p2")]
        plan = {"schema_version": "content_plan.v2", "plan_id": "planned-layout", "version": 1, "project_id": doc["project_id"],
                "task_id": None, "origin": "host_composed", "basis": {"revision_id": doc["revision_id"], "input_digest": models.compute_input_digest(doc)},
                "previous_ref": None, "mode": "planned", "narrative_ref": None, "imported_manuscript": None,
                "input": {"schema_version": "content_plan_input.v2", "chapters": [], "page_order": ["p1", "p2"], "page_roles": roles,
                          "page_budget": {"exact": None, "target": 2, "max": None},
                          "time_budget": {"total_seconds": None, "speaking_seconds": None, "interaction_seconds": None, "constraint": "unspecified"},
                          "speech_policy": {"mode": "none", "source": "default", "output": "none"}, "issues": [], "tradeoff_issue_ids": []},
                "page_links": []}
        models.validate_schema("content_plan", plan)
        doc["content_plan"] = store.put_json_object(plan)
    else:
        raise AssertionError("unknown test content kind")
    models.validate_document_semantics(doc)
    store.commit_change(base_revision=None, document=doc, operation_id=doc["change"]["operation_id"])
    return project, store


def authorized(tmp_path, kind="page", *, actions=("design.feasibility", "design.propose"), request_scope=None,
               grant_scope=None, request_manifest_ids=None):
    project, store = initial(tmp_path, kind)
    doc = store.load_document()
    selected = [] if kind == "narrative" else ["p1", "p2"]
    current_scope = request_scope or scope(selected, manifest=doc.get("content_plan"))
    if request_scope is None and kind != "page":
        current_scope["subject"] = "deck"
    if request_manifest_ids is not None:
        manifest = store.read_object_json(doc["content_plan"])
        manifest["plan_id"] = "restricted-planning-manifest"
        manifest["input"]["page_order"] = list(request_manifest_ids)
        manifest["input"]["page_roles"] = [role for role in manifest["input"]["page_roles"] if role["page_id"] in request_manifest_ids]
        manifest["input"]["page_budget"]["target"] = len(request_manifest_ids)
        models.validate_content_plan_semantics(manifest)
        current_scope = scope([], manifest=store.put_json_object(manifest))
    collaboration.start_request(project, input={"intent": "design_trial", "content_intent": None,
        "instruction_evidence": evidence(store), "scope": current_scope, "replace_request_id": None},
        base_revision=store.current_revision_id(), operation_id="feasibility-start")
    grant = collaboration.grant(project, input={"mode": "execute", "actions": list(actions),
        "scope": grant_scope or current_scope, "decision_refs": [], "delegated_topics": [],
        "max_external_calls": 0, "max_candidate_count": 0, "adoption_policy": "candidate_only",
        "instruction_evidence": evidence(store)}, base_revision=store.current_revision_id(), operation_id="feasibility-grant")
    return project, store, grant


def value(store, kind="page", *, intent="feasibility", ids=None):
    return input_value(store.load_document(), intent=intent, ids=([] if kind == "narrative" else ["p1"]) if ids is None else ids)


def assert_no_production(store, before):
    after = store.load_document()
    assert after["pages"] == before["pages"]
    assert after.get("narrative") == before.get("narrative")
    assert after.get("content_plan") == before.get("content_plan")
    assert after["tasks"] == before["tasks"] == []
    assert after["outputs"] == before["outputs"]
    assert not after.get("candidates") and not after.get("candidate_adoptions")
    assert all(entry.get("blueprint") is None for entry in after["pages"])


@pytest.mark.parametrize("kind", ["page", "plan", "narrative"])
@pytest.mark.parametrize("actions", [("design.feasibility", "design.propose"), ("design.feasibility",), ("design.propose",)])
def test_public_feasibility_accepts_zero_call_design_scope_with_real_content(tmp_path, kind, actions):
    project, store, grant = authorized(tmp_path, kind, actions=actions)
    before = store.load_document()
    pointer = store.read_current()
    source_bytes = {key: store.read_object_bytes(before[key]) for key in ("narrative", "content_plan") if before.get(key)}
    proposed = styles.propose(project, input=value(store, kind))
    assert proposed["status"] == "suggestion" and proposed["model_calls"] == 0
    models.validate_schema("style_proposal", proposed["proposal"])
    assert proposed["proposal"]["intent"] == "feasibility"
    assert proposed["proposal"]["reference_refs"] == []
    assert proposed["proposal"]["basis"]
    assert len(proposed["proposal"]["targets"]) == (1 if kind == "page" else 0)
    assert store.read_current() == pointer and store.load_document() == before
    authorization = store.read_object_json(grant["authorization_ref"])
    assert authorization["actions"] == list(actions)
    assert authorization["max_external_calls"] == authorization["max_candidate_count"] == 0
    assert before["collaboration"]["request"]["intent"] == "design_trial"
    assert before["collaboration"]["request"]["content_intent"] is None
    assert before["collaboration"]["request"]["scope"]["layers"] == ["design"]
    assert_no_production(store, before)
    assert all(store.read_object_bytes(before[key]) == raw for key, raw in source_bytes.items())


@pytest.mark.parametrize("weakness", ["request_page", "grant_page", "request_layer", "grant_layer"])
def test_planning_does_not_widen_weak_page_or_layer_scope(tmp_path, weakness):
    request_scope = scope(["p1", "p2"])
    grant_scope = copy.deepcopy(request_scope)
    if weakness == "request_page":
        request_scope["page_ids"] = ["p2"]
        grant_scope["page_ids"] = ["p2"]
    elif weakness == "grant_page":
        grant_scope["page_ids"] = ["p2"]
    elif weakness == "request_layer":
        request_scope["layers"] = ["page_copy"]
        grant_scope["layers"] = ["page_copy"]
    else:
        grant_scope["layers"] = ["page_copy"]
    project, store, _ = authorized(tmp_path, request_scope=request_scope, grant_scope=grant_scope)
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store))
    assert any(code in failure.value.decision["reason_codes"] for code in ("scope_exceeded", "decision_needed"))
    assert store.read_current() == pointer
    assert_no_production(store, before)


@pytest.mark.parametrize("action", ["style.trial", "change.commit", "dispatch.blueprint", "asset.import"])
def test_other_actions_do_not_authorize_design_planning(tmp_path, action):
    project, store, _ = authorized(tmp_path, actions=(action,))
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store))
    assert "authority_insufficient" in failure.value.decision["reason_codes"]
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_feasibility_recipe_refuses_public_sample_plan_and_pure_production_compile(tmp_path):
    project, store, _ = authorized(tmp_path)
    proposed = styles.propose(project, input=value(store))
    confirmed = styles.confirm(project, proposal_id=proposed["proposal_id"], base_revision=store.current_revision_id(),
                               operation_id=str(uuid.uuid4()))["operation_result"]
    assert confirmed["model_calls"] == 0
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(OperationError, match="feasibility"):
        styles.plan(project, input={"recipe_id": confirmed["recipe_id"], "page_ids": ["p1"], "max_calls": 1})
    actual_page = store.read_object_json(before["pages"][0]["page"])
    recipe = store.read_object_json(confirmed["recipe_ref"])
    with pytest.raises(models.ModelError, match="feasibility"):
        design_recipe.compile_design(actual_page, before["design_context"], recipe, "p1")
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_zero_call_planning_authorization_cannot_dispatch_initial_sample_or_blueprint(tmp_path):
    project, store, _ = authorized(tmp_path, actions=("design.propose",))
    _seed_imported_plan(store)
    proposed = styles.propose(project, input=value(store, intent="initial_design"))
    confirmed = styles.confirm(project, proposal_id=proposed["proposal_id"], base_revision=store.current_revision_id(),
                               operation_id=str(uuid.uuid4()))["operation_result"]
    plan = styles.plan(project, input={"recipe_id": confirmed["recipe_id"], "page_ids": ["p1"], "max_calls": 1})
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        changes.commit(project, plan_id=plan["plan_id"], base_revision=before["revision_id"], operation_id=str(uuid.uuid4()))
    assert "scope_exceeded" in failure.value.decision["reason_codes"]
    with pytest.raises(eligibility.EligibilityBlocked):
        service.open_blueprint_task(store, before, before["pages"][0])
    assert store.read_current() == pointer
    assert_no_production(store, before)


@pytest.mark.parametrize("kind", ["plan", "narrative"])
def test_no_page_feasibility_cannot_invent_a_target_for_initial_image_design(tmp_path, kind):
    project, store, _ = authorized(tmp_path, kind)
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises((OperationError, models.ModelError, eligibility.EligibilityBlocked)):
        styles.propose(project, input=value(store, kind, intent="initial_design", ids=["p1"]))
    assert store.read_current() == pointer
    assert_no_production(store, before)


@pytest.mark.parametrize("kind", ["plan", "narrative"])
def test_empty_pages_scope_does_not_become_deck_planning_permission(tmp_path, kind):
    project, store, _ = authorized(tmp_path, kind, request_scope=scope([]))
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store, kind))
    assert "scope_exceeded" in failure.value.decision["reason_codes"]
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_no_page_planned_target_remains_inside_fixed_design_scope(tmp_path):
    restricted = {**scope(["p1"]), "subject": "deck"}
    project, store, _ = authorized(tmp_path, "plan", request_scope=restricted)
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store, "plan", ids=["p2"]))
    assert "scope_exceeded" in failure.value.decision["reason_codes"]
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_actual_planning_manifest_p1_cannot_authorize_proposal_for_planned_p2(tmp_path):
    project, store, _ = authorized(tmp_path, "plan", request_manifest_ids=["p1"])
    before, pointer = store.load_document(), store.read_current()
    manifest_ref = before["collaboration"]["request"]["scope"]["page_manifest_ref"]
    assert store.read_object_json(manifest_ref)["input"]["page_order"] == ["p1"]
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store, "plan", ids=["p2"]))
    assert "scope_exceeded" in failure.value.decision["reason_codes"]
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_global_plan_feasibility_uses_explicit_deck_design_scope_without_page_targets(tmp_path):
    project, store, _ = authorized(tmp_path, "plan", request_scope={**scope([]), "subject": "deck"})
    before, pointer = store.load_document(), store.read_current()
    proposed = styles.propose(project, input=value(store, "plan", ids=[]))
    assert proposed["model_calls"] == 0
    assert proposed["proposal"]["targets"] == proposed["proposal"]["page_profiles"] == proposed["proposal"]["sample_targets"] == []
    assert proposed["proposal"]["basis"][0]["ref"] == before["content_plan"]
    assert store.read_current() == pointer
    assert_no_production(store, before)


def test_feasibility_action_alone_does_not_authorize_a_production_style_proposal(tmp_path):
    project, store, _ = authorized(tmp_path, actions=("design.feasibility",))
    before, pointer = store.load_document(), store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        styles.propose(project, input=value(store, intent="initial_design"))
    assert "authority_insufficient" in failure.value.decision["reason_codes"]
    assert store.read_current() == pointer
    assert_no_production(store, before)
