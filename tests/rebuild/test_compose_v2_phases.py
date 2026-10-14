"""T03 slice 1: compose.v2 phased dispatch and acceptance (CONTRACTS §5, §11.5).

Every variant writes only what its row of the §11.5 table allows, commits in one
pointer swap, and refuses the whole result otherwise. The legacy compose.v1 path
stays exactly as it was.
"""
import hashlib
import json

import pytest

from deck_master import collaboration, content_production, models, service
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import Store
from deck_master.tasks import EnvelopeError, TaskConflict


def _stored(store, seed: str) -> dict:
    return store.put_json_object({"fixture": seed})


def _instruction(store, seed="instruction") -> dict:
    return {"kind": "host_attested_instruction", "source_ref": _stored(store, seed),
            "source_locator": f"chat:{seed}", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _scope(**over) -> dict:
    scope = {"subject": "deck", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["narrative", "plan", "page_copy", "speech"],
             "allow_page_membership_change": True, "allow_page_order_change": False,
             "purpose": "working"}
    scope.update(over)
    return scope


def _project(tmp_path, *, material=True, presentation_mode=None):
    project = tmp_path / "proj"
    sources = []
    if material:
        path = tmp_path / "S1-material.txt"
        path.write_text("第一行：版本未知时先记录未知。\n第二行：紧急程度与版本可得性是两个维度。\n"
                        "第三行：不得从缺字段率推出节省比例。\n", encoding="utf-8")
        sources = [path]
    service.create(project, brief="培训材料", title="记录训练", sources=sources,
                   project_format="workbench.v3", audience="新接单员工",
                   presentation_mode=presentation_mode)
    store = Store(project)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "bootstrap-collaboration",
                                      "kind": "collaboration_update",
                                      "description": "bootstrap region", "read_set": []})
    bumped["collaboration"] = {
        "schema_version": "collaboration.v1",
        "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "independent_model_or_human",
                            "requirement_origin": "default_new_argument",
                            "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": [],
    }
    require_writer(bumped, "collaboration.v1")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="bootstrap-collaboration")
    return project, Store(project)


def _request(project, store, *, intent="content_only", content_intent="content_full", **scope_over):
    return collaboration.start_request(
        project, input={"intent": intent, "content_intent": content_intent,
                        "instruction_evidence": _instruction(store),
                        "scope": _scope(**scope_over), "replace_request_id": None},
        base_revision=store.load_document()["revision_id"], operation_id="op-request-1")


def _source_link(store, document, locator="L1", source_id=None):
    source = (document.get("sources") or [{}])[0]
    return {"source_id": source_id or source.get("source_id"),
            "source_version": {"original_sha256": source.get("original_sha256"),
                               "extract": source.get("extract")},
            "locator": locator}


def _framing_narrative(project_id, **over) -> dict:
    narrative = {
        "schema_version": "narrative.v1", "narrative_id": "nar-1", "version": 1,
        "project_id": project_id, "origin": "host_composed", "maturity": "framing",
        "input_basis": [], "communication_job": {
            "mode": "train", "audience_fact_key": "task.audience",
            "audience_question": "新接单员工如何记录未知版本",
            "desired_outcome": "能独立填写可交接的记录",
            "observable_success": "在普通/紧急与新情境题上给出正确下一动作",
            "use_mode": "live", "primary_use": "live"},
        "central_node_id": None, "nodes": [], "edges": [], "issues": [],
        "alternatives": [], "previous_ref": None,
    }
    narrative.update(over)
    return narrative


def _argument_narrative(project_id, **over) -> dict:
    nodes = [
        {"node_id": "n1", "role": "claim", "statement": "版本未知时记录未知，再按紧急程度决定流转",
         "authority": "instruction", "source_links": [], "qualification_node_ids": [],
         "unresolved_issue_ids": []},
        {"node_id": "n2", "role": "evidence", "statement": "SOP 把紧急程度与版本可得性列为两个维度",
         "authority": "instruction", "source_links": [], "qualification_node_ids": [],
         "unresolved_issue_ids": []},
        {"node_id": "q1", "role": "qualification",
         "statement": "缺字段率不等于可节省比例，本材料没有收益测量",
         "authority": "instruction", "source_links": [], "qualification_node_ids": [],
         "unresolved_issue_ids": []},
    ]
    narrative = _framing_narrative(project_id)
    narrative.update({
        "maturity": "argument", "central_node_id": "n1", "nodes": nodes,
        "edges": [{"from_node_id": "n2", "to_node_id": "n1", "relation": "supports"},
                  {"from_node_id": "q1", "to_node_id": "n1", "relation": "qualifies"}]})
    narrative.update(over)
    return narrative


def _page(store, document, page_id, *, title="记录未知版本", text="先记录未知，再按紧急程度流转。",
          notes="这一页讲清楚两个独立判断。", nodes=("n1",), notes_kind="cue") -> dict:
    mapping = {
        "narrative_ref": document.get("narrative"),
        "plan_role_page_id": page_id,
        "visible_links": [
            {"element_ref": f"atom:{page_id}:title", "narrative_node_ids": list(nodes),
             "source_links": []},
            {"element_ref": f"atom:{page_id}:block:b1:text", "narrative_node_ids": list(nodes),
             "source_links": [_source_link(store, document, "L1")]},
        ],
        "speech_segments": [],
    }
    if notes:
        mapping["speech_segments"] = [
            {"segment_id": "s1", "start_codepoint": 0, "end_codepoint": len(notes),
             "narrative_node_ids": list(nodes), "kind": notes_kind, "estimated_seconds": 20}]
    return {
        "schema_version": "deck_page_package.v2", "page_id": page_id,
        "customer_visible": {"title": title, "body_blocks": [{"id": "b1", "type": "paragraph",
                                                             "text": text}]},
        "speaker_notes": notes,
        "visual_spec": {"intent": "培训页", "reference_mode": "new_design"},
        "content_mapping": mapping,
    }


def _plan_input(document, page_ids, *, source_links=None, **over) -> dict:
    roles = []
    for page_id in page_ids:
        roles.append({
            "page_id": page_id, "role": "记录未知值", "audience_question": "这一页解决什么",
            "intended_takeaway": "能记录未知并说明下一动作",
            "narrative_node_ids": ["n1"], "source_links": source_links or [],
            "required_qualifications": ["q1"], "content_profile": "evidence",
            "density_rationale": "规则加一个限定", "timing_seconds": 75,
            "transition_to_next": None})
    data = {
        "schema_version": "content_plan_input.v2",
        "chapters": [{"chapter_id": "c1", "title": "记录与流转", "page_ids": list(page_ids)}],
        "page_order": list(page_ids),
        "page_roles": roles,
        "page_budget": {"exact": None, "target": 6, "max": 8},
        "time_budget": {"total_seconds": 480, "speaking_seconds": 380,
                        "interaction_seconds": 100, "constraint": "hard"},
        "speech_policy": {"mode": "cues", "source": "provided", "output": "pptx_notes"},
        "issues": [], "tradeoff_issue_ids": [],
    }
    data.update(over)
    return data


def _submit(project, task, payload, variant, **over):
    envelope = {"schema_version": "compose_result.v2", "kind": "compose", "variant": variant,
                "task_id": task["task_id"], "operation_id": task["operation_id"],
                "produced_against": task["produced_against"],
                "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                "payload": payload, "usage_events": []}
    envelope.update(over)
    return service.accept_result(project, task_id=task["task_id"],
                                 operation_id=task["operation_id"],
                                 produced_against=task["produced_against"],
                                 result_payload=envelope)


def _dispatch(store, *, phase, **over):
    import uuid
    return content_production.open_phase_task(
        store, store.load_document(), operation_id=f"phase-{phase}-{uuid.uuid4().hex[:6]}",
        phase=phase, **over)


def _accept_argument(project, store):
    task = _dispatch(store, phase="argument")
    document = store.load_document()
    out = _submit(project, task, {"narrative": _argument_narrative(document["project_id"])}, "narrative")
    return task, out


def _adopt_direction(project, store, proposal_ref):
    """Record a covering direction decision and adopt the proposal Ref."""
    decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user",
                        "value": {"selected": "记录未知 + 紧急程度两维度"},
                        "scope": _scope(layers=["narrative", "plan"]),
                        "instruction_evidence": _instruction(store, "direction"),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": proposal_ref,
                                          "projection": "direction"}]},
        base_revision=store.load_document()["revision_id"],
        operation_id=f"op-direction-{proposal_ref['sha256'][:6]}")
    return content_production.adopt_proposal(
        project, input={"proposal_ref": proposal_ref, "decision_ref": decision["decision_ref"],
                        "write_scope": _scope(layers=["narrative"])},
        base_revision=store.load_document()["revision_id"],
        operation_id=f"op-adopt-{proposal_ref['sha256'][:6]}")


# ---------------------------------------------------------------------------
# Dispatch shape


def test_phase_dispatch_carries_compose_v2_and_binding(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="framing")
    assert task["protocol_version"] == "compose.v2"
    assert set(task["required_capabilities"]) == {"compose.v2", "collaboration.v1"}
    binding = task["collaboration_binding"]
    assert binding["phase"] == "framing" and binding["executor_type"] == "host"
    assert binding["adoption_policy"] == "proposal_only"
    assert binding["request_id"] == (store.load_document()["collaboration"]["request"]["request_id"])
    assert binding["write_scope"]["layers"] == ["narrative"]
    assert binding["eligibility_basis"], "registered task basis must be completed by the service"
    # Method resources follow the phase, not just the task kind.
    summary = service.task_summary(store, store.load_document(), task)
    assert [m["id"] for m in summary["method_resources"]] == \
        ["source-reading", "content-methods", "content-examples"]


def test_every_task_in_a_collaboration_project_is_gated(tmp_path):
    """A dispatch with no binding is refused by models.require_task_binding."""
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    task = content_production.build_phase_task(store, document, operation_id="x", phase="framing")
    stripped = {k: v for k, v in task.items() if k != "collaboration_binding"}
    with pytest.raises(ModelError, match="collaboration binding"):
        models.require_task_binding(document, stripped)
    # A binding that names a different request is refused too.
    forged = {**task, "collaboration_binding": {**task["collaboration_binding"],
                                                "request_id": "req-other"}}
    with pytest.raises(ModelError, match="current work request"):
        models.require_task_binding(document, forged)


def test_phase_dispatch_requires_an_open_request(tmp_path):
    project, store = _project(tmp_path)
    # F06: the phase write point consumes the unified gate first, so the
    # refusal is the typed decision instead of the builder's ModelError.
    from deck_master import eligibility
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        _dispatch(store, phase="framing")
    assert "decision_needed" in excinfo.value.decision["reason_codes"]


def test_legacy_project_keeps_compose_v1(tmp_path):
    """The phased protocol never applies below the collaboration.v1 writer."""
    project = tmp_path / "legacy"
    service.create(project, brief="legacy", sources=[], project_format="workbench.v3")
    store = Store(project)
    task = service.open_compose_task(store, store.load_document(), operation_id="legacy-compose")
    assert task.get("protocol_version") == "compose.v1"
    assert "collaboration_binding" not in task
    phases = content_production.content_phase_status(store, store.load_document())
    assert phases["action"] == "inactive"


# ---------------------------------------------------------------------------
# framing


def test_framing_stores_a_proposal_without_touching_current_semantics(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="framing")
    document = store.load_document()
    out = _submit(project, task, {"narrative": _framing_narrative(document["project_id"])}, "framing")
    assert out["status"] == "accepted" and out["next_action"] == "argument_phase"
    document = store.load_document()
    assert document.get("narrative") is None
    assert document.get("pages") == []
    stored = store.read_object_json(out["result_refs"][0])
    assert stored["maturity"] == "framing"
    # The completed task carries the proposal and no user decision was invented.
    assert document["collaboration"]["decisions"] == []


def test_framing_refuses_pages_and_an_argument_narrative(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="framing")
    document = store.load_document()
    with pytest.raises(EnvelopeError, match="frames a framing Narrative|framing Narrative"):
        _submit(project, task, {"narrative": _argument_narrative(document["project_id"])}, "framing")
    hidden = {"schema_version": "compose_result.v2", "kind": "compose", "variant": "framing",
              "task_id": task["task_id"], "operation_id": task["operation_id"],
              "produced_against": task["produced_against"],
              "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
              "payload": {"narrative": _framing_narrative(document["project_id"])},
              "usage_events": [], "pages": [{"page_id": "p9"}]}
    with pytest.raises(EnvelopeError, match="Additional properties|legacy slots are not a channel"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=hidden)
    assert store.load_document().get("pages") == []


# ---------------------------------------------------------------------------
# narrative


def test_narrative_proposal_with_optional_planned_plan(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="argument")
    document = store.load_document()
    narrative = _argument_narrative(document["project_id"])
    plan = {
        "schema_version": "content_plan.v2", "plan_id": "plan-1", "version": 1,
        "project_id": document["project_id"], "task_id": None, "origin": "host_composed",
        "basis": {"revision_id": document["revision_id"],
                  "input_digest": models.compute_input_digest(document)},
        "previous_ref": None, "mode": "planned", "narrative_ref": None,
        "imported_manuscript": None,
        "input": _plan_input(document, ["p1"], source_links=[_source_link(store, document, "L2")]),
        "page_links": [],
    }
    out = _submit(project, task, {"narrative": narrative, "plan": plan}, "narrative")
    assert out["status"] == "accepted"
    assert out["operation_result"]["adopted"] is False
    assert len(out["result_refs"]) == 2
    # page_links stay empty on a planned plan: no ghost pages.
    planned = store.read_object_json(out["result_refs"][1])
    assert planned["page_links"] == [] and planned["narrative_ref"] == out["result_refs"][0]
    assert store.load_document().get("content_plan") is None


def test_narrative_rejects_a_framing_body_and_a_mismatched_plan(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="argument")
    document = store.load_document()
    with pytest.raises(EnvelopeError, match="argument Narrative"):
        _submit(project, task, {"narrative": _framing_narrative(document["project_id"])}, "narrative")
    narrative = _argument_narrative(document["project_id"])
    other = store.put_json_object({**_argument_narrative(document["project_id"]),
                                   "narrative_id": "nar-2"})
    plan = {"schema_version": "content_plan.v2", "plan_id": "plan-1", "version": 1,
            "project_id": document["project_id"], "task_id": None, "origin": "host_composed",
            "basis": {"revision_id": document["revision_id"],
                      "input_digest": models.compute_input_digest(document)},
            "previous_ref": None, "mode": "planned", "narrative_ref": other,
            "imported_manuscript": None,
            "input": _plan_input(document, ["p1"]), "page_links": []}
    with pytest.raises(EnvelopeError, match="only bind the Narrative submitted"):
        _submit(project, task, {"narrative": narrative, "plan": plan}, "narrative")


# ---------------------------------------------------------------------------
# page_copy


def test_page_copy_adopts_pages_and_a_bound_plan_atomically(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    _adopt_direction(project, store, out["result_refs"][0])
    assert store.load_document()["narrative"] is not None
    task = _dispatch(store, phase="page_copy")
    document = store.load_document()
    pages = [_page(store, document, "p1"), _page(store, document, "p2")]
    payload = {"pages": pages, "page_order": ["p1", "p2"],
               "plan_input": _plan_input(document, ["p1", "p2"],
                                         source_links=[_source_link(store, document, "L1")])}
    result = _submit(project, task, payload, "page_copy")
    assert result["status"] == "accepted"
    assert result["operation_result"]["adopted"] is True
    document = store.load_document()
    assert [entry["page_id"] for entry in document["pages"]] == ["p1", "p2"]
    plan_ref = document["content_plan"]
    plan = store.read_object_json(plan_ref)
    assert plan["schema_version"] == "content_plan.v2" and plan["mode"] == "bound"
    assert [link["page_id"] for link in plan["page_links"]] == ["p1", "p2"]
    assert all(link["page_ref"] == document["pages"][index]["page"]
               for index, link in enumerate(plan["page_links"]))
    assert document["outputs"] == {"pptx": None, "trace": None, "render_report": None}
    assert document["content_basis"]["input_digest"] == task["input_digest"]


def test_page_copy_refusals(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    _adopt_direction(project, store, out["result_refs"][0])
    task = _dispatch(store, phase="page_copy")
    document = store.load_document()
    good = {"pages": [_page(store, document, "p1")], "page_order": ["p1"],
            "plan_input": _plan_input(document, ["p1"])}
    # An empty page array never stands in for a plan.
    with pytest.raises(EnvelopeError, match="empty list cannot stand in"):
        _submit(project, task, {**good, "pages": [], "page_order": []}, "page_copy")
    # page_order must match the delivered pages exactly.
    with pytest.raises(EnvelopeError, match="exactly the delivered pages"):
        _submit(project, task, {**good, "page_order": ["p2"]}, "page_copy")
    # A page outside the plan's roles is refused before anything is written.
    with pytest.raises(EnvelopeError, match="plan role|exactly one role"):
        _submit(project, task, {"pages": [_page(store, document, "p9")], "page_order": ["p9"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    # A page cannot switch semantics: its mapping must name the adopted Narrative.
    other = store.put_json_object({**_argument_narrative(document["project_id"]),
                                   "narrative_id": "nar-other"})
    tampered = _page(store, document, "p1")
    tampered["content_mapping"] = {**tampered["content_mapping"], "narrative_ref": other}
    with pytest.raises(EnvelopeError, match="adopted current Narrative"):
        _submit(project, task, {"pages": [tampered], "page_order": ["p1"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    # A missing mapping is refused: atom coverage is not optional at this phase.
    incomplete = _page(store, document, "p1")
    incomplete.pop("content_mapping")
    with pytest.raises(EnvelopeError, match="content_mapping is required"):
        _submit(project, task, {"pages": [incomplete], "page_order": ["p1"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    # A mapping that points at a narrative node that does not exist is refused.
    ghost = _page(store, document, "p1", nodes=("n9",))
    with pytest.raises(EnvelopeError, match="narrative nodes not present"):
        _submit(project, task, {"pages": [ghost], "page_order": ["p1"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    # A source locator that is not in the stored extract is refused.
    bad_link = _page(store, document, "p1")
    bad_link["content_mapping"]["visible_links"][1]["source_links"] = [
        _source_link(store, document, "L99")]
    with pytest.raises(ModelError, match="locator"):
        _submit(project, task, {"pages": [bad_link], "page_order": ["p1"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    assert store.load_document().get("pages") == []


def test_page_copy_needs_an_adopted_narrative(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase="page_copy", adoption_policy="within_scope")
    document = store.load_document()
    with pytest.raises(ModelError, match="decision_needed"):
        _submit(project, task, {"pages": [_page(store, document, "p1")], "page_order": ["p1"],
                                "plan_input": _plan_input(document, ["p1"])}, "page_copy")


def test_page_copy_keeps_membership_change_behind_the_scope(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    _adopt_direction(project, store, out["result_refs"][0])
    task = _dispatch(store, phase="page_copy")
    document = store.load_document()
    _submit(project, task, {"pages": [_page(store, document, "p1")], "page_order": ["p1"],
                            "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    # A second revision that drops and adds pages needs an explicit scope.
    narrow = _dispatch(store, phase="page_copy", adoption_policy="within_scope",
                       page_ids=["p1"])
    document = store.load_document()
    new_task = content_production.build_phase_task(
        store, document, operation_id="phase-page_copy-2", phase="page_copy",
        adoption_policy="within_scope")
    assert "page_ids" in (new_task["collaboration_binding"]["write_scope"] or {})
    # The acceptance gate consumes the same scope judgement first, so the
    # out-of-scope page is refused as a typed eligibility decision (the
    # variant's own write-scope check would refuse it one step later).
    from deck_master import eligibility
    with pytest.raises(eligibility.EligibilityBlocked, match="outside the current request scope"):
        _submit(project, narrow, {"pages": [_page(store, document, "p2")], "page_order": ["p2"],
                                  "plan_input": _plan_input(document, ["p2"])}, "page_copy")


# ---------------------------------------------------------------------------
# speech


def _deck_with_pages(tmp_path, *, notes="这一页讲清楚两个独立判断。", kind="cue"):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    _adopt_direction(project, store, out["result_refs"][0])
    task = _dispatch(store, phase="page_copy")
    document = store.load_document()
    _submit(project, task, {"pages": [_page(store, document, "p1", notes=notes, notes_kind=kind)],
                            "page_order": ["p1"],
                            "plan_input": _plan_input(document, ["p1"])}, "page_copy")
    return project, store


def test_speech_writes_notes_mapping_and_rebinds_page_links(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    entry = document["pages"][0]
    body_before = store.read_object_json(entry["page"])["customer_visible"]
    plan_before = document["content_plan"]
    task = content_production.open_phase_task(
        store, store.load_document(), operation_id="phase-speech", phase="speech",
        page_ids=["p1"])
    content_production._stamp_speech_kind(store, task, "cue")
    notes = "先讲记录未知，再讲紧急程度。"
    payload = {"updates": [{"page_id": "p1",
                            "page_ref": store.load_document()["pages"][0]["page"],
                            "speaker_notes": notes,
                            "speech_segments": [
                                {"segment_id": "s1", "start_codepoint": 0,
                                 "end_codepoint": 6, "narrative_node_ids": ["n1"],
                                 "kind": "cue", "estimated_seconds": 5},
                                {"segment_id": "s2", "start_codepoint": 6,
                                 "end_codepoint": len(notes), "narrative_node_ids": ["q1"],
                                 "kind": "cue", "estimated_seconds": 6}]}]}
    out = _submit(project, task, payload, "speech")
    assert out["status"] == "accepted"
    document = store.load_document()
    page = store.read_object_json(document["pages"][0]["page"])
    assert page["speaker_notes"] == notes
    assert page["customer_visible"] == body_before
    assert len(page["content_mapping"]["speech_segments"]) == 2
    assert document["outputs"] == {"pptx": None, "trace": None, "render_report": None}
    assert document["content_plan"] != plan_before
    plan = store.read_object_json(document["content_plan"])
    assert plan["version"] == 2 and plan["previous_ref"] == plan_before
    assert plan["page_links"][0]["page_ref"] == document["pages"][0]["page"]
    assert out["invalidated_outputs"] == ["pptx", "render_report", "trace"]


def test_speech_refuses_body_edits_and_the_wrong_kind(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    entry = document["pages"][0]
    task = content_production.open_phase_task(
        store, store.load_document(), operation_id="phase-speech", phase="speech", page_ids=["p1"])
    content_production._stamp_speech_kind(store, task, "cue")
    current = store.load_document()["pages"][0]
    base = {"page_id": "p1", "page_ref": current["page"], "speaker_notes": "改写后的口播。",
            "speech_segments": [{"segment_id": "s1", "start_codepoint": 0,
                                 "end_codepoint": len("改写后的口播。"),
                                 "narrative_node_ids": ["n1"], "kind": "cue",
                                 "estimated_seconds": 4}]}
    with pytest.raises(EnvelopeError, match="refusing"):
        _submit(project, task, {"updates": [{**base, "customer_visible": {"title": "偷改"}}]},
                "speech")
    stale_ref = store.put_json_object({"fixture": "some other page object"})
    with pytest.raises(EnvelopeError, match="fixed Page Ref"):
        _submit(project, task, {"updates": [{**base, "page_ref": stale_ref}]}, "speech")
    with pytest.raises(EnvelopeError, match="dispatched for 'cue'"):
        _submit(project, task, {"updates": [{**base, "speech_segments": [
            {**base["speech_segments"][0], "kind": "verbatim"}]}]}, "speech")
    with pytest.raises(EnvelopeError, match="estimated"):
        _submit(project, task, {"updates": [{**base, "speech_segments": [
            {**base["speech_segments"][0], "estimated_seconds": None}]}]}, "speech")
    # Notes that are not covered by the segments are refused by the page validator.
    with pytest.raises(EnvelopeError):
        _submit(project, task, {"updates": [{**base, "speaker_notes": "更长的一段口播，需要完整覆盖。"}]},
                "speech")
    document = store.load_document()
    assert store.read_object_json(document["pages"][0]["page"])["customer_visible"]["title"] \
        == "记录未知版本"


def test_speech_scope_requires_the_speech_layer(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = _dispatch(store, phase="page_copy")
    current = store.load_document()["pages"][0]
    payload = {"updates": [{"page_id": "p1", "page_ref": current["page"],
                            "speaker_notes": "笔记", "speech_segments": []}]}
    with pytest.raises(EnvelopeError, match="variant"):
        _submit(project, task, payload, "speech")


# ---------------------------------------------------------------------------
# input_revision


def test_input_revision_reuses_the_single_swap_path(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    store.put_json_object({"fixture": "new input"})
    document = store.load_document()
    # Recompute the dispatched digest after an input change.
    service.inputs_update  # noqa: B018 - the real path is exercised in test_inputs.py
    task = content_production.build_phase_task(
        store, document, operation_id="rev-1", intent="input_revision",
        input_revision_id="op-update-1")
    document = store.load_document()
    updated = _page(store, document, "p1", text="先记录未知；紧急程度决定流转，版本未知不等于紧急。")
    # A real input change is required for the digest to move; here the page copy
    # itself is the proposal under a matching input digest.
    task["input_digest"] = models.compute_input_digest(document)
    task_ref = store.put_json_object(task)
    bumped = models.bump_revision(document, {"operation_id": "dispatch-rev-1",
                                             "kind": "task_update",
                                             "description": "revision task", "read_set": []})
    bumped["tasks"] = list(document["tasks"]) + [task_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="dispatch-rev-1")
    task = tasks_lookup(store, task["task_id"])
    payload = {"changed_layers": ["page_copy"],
               "proposals": [{"layer": "page_copy", "ref": store.put_json_object(updated)}],
               "diff": {"input_digest": task["input_digest"], "summary": "补充紧急程度的适用条件",
                        "changed_page_ids": ["p1"]}}
    out = _submit(project, task, payload, "input_revision")
    assert out["status"] == "accepted"
    document = store.load_document()
    assert "紧急程度决定流转" in store.read_object_json(document["pages"][0]["page"])[
        "customer_visible"]["body_blocks"][0]["text"]
    assert document["content_basis"]["resolved_by_task_id"] == task["task_id"]


def tasks_lookup(store, task_id):
    for ref in store.load_document().get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("task_id") == task_id:
            return task
    raise AssertionError("task not found")


def test_input_revision_refusals(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    task = content_production.build_phase_task(store, document, operation_id="rev-2",
                                               intent="input_revision")
    task_ref = store.put_json_object(task)
    bumped = models.bump_revision(document, {"operation_id": "dispatch-rev-2",
                                             "kind": "task_update",
                                             "description": "revision task", "read_set": []})
    bumped["tasks"] = list(document["tasks"]) + [task_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="dispatch-rev-2")
    task = tasks_lookup(store, task["task_id"])
    page = _page(store, store.load_document(), "p1")
    proposal = store.put_json_object(page)
    with pytest.raises(EnvelopeError, match="unknown layers"):
        _submit(project, task, {"changed_layers": ["everything"],
                                "proposals": [{"layer": "everything", "ref": proposal}],
                                "diff": {"input_digest": task["input_digest"], "summary": "x",
                                         "changed_page_ids": []}}, "input_revision")
    with pytest.raises(EnvelopeError, match="without any substantive proposal"):
        _submit(project, task, {"changed_layers": ["page_copy"], "proposals": [],
                                "diff": {"input_digest": task["input_digest"], "summary": "x",
                                         "changed_page_ids": []}}, "input_revision")
    with pytest.raises(TaskConflict, match="dispatched input revision"):
        _submit(project, task, {"changed_layers": ["page_copy"],
                                "proposals": [{"layer": "page_copy", "ref": proposal}],
                                "diff": {"input_digest": "0" * 64, "summary": "x",
                                         "changed_page_ids": []}}, "input_revision")
    # The page is outside the request scope, so the acceptance gate refuses it
    # as a typed eligibility decision before the variant's own write-scope check.
    from deck_master import eligibility
    with pytest.raises(eligibility.EligibilityBlocked, match="outside the current request scope"):
        _submit(project, task, {"changed_layers": ["page_copy"],
                                "proposals": [{"layer": "page_copy", "ref": proposal}],
                                "diff": {"input_digest": task["input_digest"], "summary": "x",
                                         "changed_page_ids": ["p9"]}}, "input_revision")
    # Empty prose is not a diff.
    with pytest.raises(EnvelopeError, match="concrete change summary"):
        _submit(project, task, {"changed_layers": ["page_copy"],
                                "proposals": [{"layer": "page_copy", "ref": proposal}],
                                "diff": {"input_digest": task["input_digest"], "summary": "  ",
                                         "changed_page_ids": []}}, "input_revision")


# ---------------------------------------------------------------------------
# adopt_proposal


def test_adopt_proposal_promotes_a_narrative_inside_a_covering_decision(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    proposal_ref = out["result_refs"][0]
    document = store.load_document()
    decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user",
                        "value": {"selected": "两维度记录"},
                        "scope": _scope(layers=["narrative", "plan"]),
                        "instruction_evidence": _instruction(store, "direction"),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": proposal_ref,
                                          "projection": "direction"}]},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction")
    decision_ref = decision["decision_ref"]
    adoption = content_production.adopt_proposal(
        project, input={"proposal_ref": proposal_ref, "decision_ref": decision_ref,
                        "write_scope": _scope(layers=["narrative"])},
        base_revision=store.load_document()["revision_id"], operation_id="op-adopt-1")
    assert adoption["status"] == "accepted"
    assert adoption["adopted_refs"] == [proposal_ref]
    assert adoption["creates_confirmation"] is False
    assert adoption["authorizes_production"] is False
    document = store.load_document()
    assert document["narrative"] == proposal_ref
    assert [record["decision_id"] for _, record in
            [(None, store.read_object_json(r)) for r in document["collaboration"]["decisions"]]] \
        == [store.read_object_json(decision_ref)["decision_id"]]
    # Replaying the same operation returns the original receipt.
    replay = content_production.adopt_proposal(
        project, input={"proposal_ref": proposal_ref, "decision_ref": decision_ref,
                        "write_scope": _scope(layers=["narrative"])},
        base_revision=store.load_document()["revision_id"], operation_id="op-adopt-1")
    assert replay["status"] == "already_applied"


def test_adopt_proposal_refusals(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _, out = _accept_argument(project, store)
    proposal_ref = out["result_refs"][0]
    # No decision at all.
    with pytest.raises(ModelError, match="current collaboration region"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": _stored(store, "ghost"),
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-x")
    rejected = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "rejected",
                        "authority_mode": "direct_user", "value": {"selected": None},
                        "scope": _scope(layers=["narrative"]),
                        "instruction_evidence": _instruction(store, "rejected")},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction-rejected")
    with pytest.raises(ModelError, match="authority_insufficient"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": rejected["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-y")
    # A host-proposed decision is not a user decision.
    proposed = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "host_proposal", "value": {"selected": "host 自选"},
                        "scope": _scope(layers=["narrative"]),
                        "instruction_evidence": _instruction(store, "host-proposal")},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction-host")
    with pytest.raises(ModelError, match="authority_insufficient"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": proposed["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-z")
    # A valid decision but a wider write scope than the decision covers.
    decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "两维度"},
                        "scope": _scope(layers=["narrative"]),
                        "instruction_evidence": _instruction(store, "direction-2")},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction-2")
    with pytest.raises(ModelError, match="scope_exceeded"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref, "decision_ref": decision["decision_ref"],
                            "write_scope": _scope(layers=["narrative", "page_copy"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-w")
    # A decision that names subject refs must name this proposal.
    subject_decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "另一份提案"},
                        "scope": _scope(layers=["narrative"]),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": _stored(store, "other-proposal"),
                                          "projection": "direction"}],
                        "instruction_evidence": _instruction(store, "direction-3")},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction-3")
    with pytest.raises(ModelError, match="does not name this proposal"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": subject_decision["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-v")
    # Page candidates adopt through the existing candidate semantics, not here:
    # the decision names the page proposal, so the refusal is about its kind.
    page_ref = store.put_json_object(_page(store, store.load_document(), "p1"))
    page_decision = collaboration.record_decision(
        project, input={"topic": "manuscript", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "这一页"},
                        "scope": _scope(layers=["page_copy"]),
                        "subject_refs": [{"artifact_kind": "page", "artifact_ref": page_ref,
                                          "projection": "page_roles"}],
                        "instruction_evidence": _instruction(store, "page-decision")},
        base_revision=store.load_document()["revision_id"], operation_id="op-page-decision")
    with pytest.raises(ModelError, match="candidate adoption semantics"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": page_ref,
                            "decision_ref": page_decision["decision_ref"],
                            "write_scope": _scope(layers=["page_copy"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-u")
    # A decision with empty subject_refs names no artifact and adopts nothing.
    empty_subjects = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "泛指方向"},
                        "scope": _scope(layers=["narrative"]),
                        "subject_refs": [],
                        "instruction_evidence": _instruction(store, "empty-subjects")},
        base_revision=store.load_document()["revision_id"], operation_id="op-empty-subjects")
    with pytest.raises(ModelError, match="names no proposal"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": empty_subjects["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-t")
    # A decision that names the proposal under the wrong registered projection
    # (a palette decision cannot promote an argument) is refused too.
    wrong_projection = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "配色"},
                        "scope": _scope(layers=["narrative"]),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": proposal_ref,
                                          "projection": "style.palette"}],
                        "instruction_evidence": _instruction(store, "wrong-projection")},
        base_revision=store.load_document()["revision_id"], operation_id="op-wrong-projection")
    with pytest.raises(ModelError, match="needs one of"):
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": wrong_projection["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt-s")
    assert store.load_document().get("narrative") is None


# ---------------------------------------------------------------------------
# Digest contract


def test_eligibility_digest_is_stable_and_scope_sensitive():
    from deck_master import collaboration_binding
    basis = [{"kind": "task_fact", "identity": "brief", "projection": "value", "sha256": "b" * 64},
             {"kind": "task_fact", "identity": "audience", "projection": "value", "sha256": "a" * 64}]
    scope = {"subject": "deck", "page_ids": ["p2", "p1"], "layers": ["speech", "narrative"],
             "page_manifest_ref": None, "external_artifact_ref": None,
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "working"}
    first = collaboration_binding.eligibility_digest(phase="speech", write_scope=scope, basis=basis)
    reordered = collaboration_binding.eligibility_digest(
        phase="speech", write_scope={**scope, "page_ids": ["p1", "p2"],
                                     "layers": ["narrative", "speech"]},
        basis=list(reversed(basis)))
    assert first == reordered
    changed = collaboration_binding.eligibility_digest(
        phase="speech", write_scope={**scope, "page_ids": ["p1"]}, basis=basis)
    assert changed != first
    assert len(first) == 64 and all(c in "0123456789abcdef" for c in first)
