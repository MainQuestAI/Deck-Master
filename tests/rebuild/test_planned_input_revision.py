"""RC3-S02: actual input revisions can deliver planning without ghost Pages.

Synthetic payloads exercise public create/update/claim/accept, not native quality.
"""
from copy import deepcopy

import pytest

from deck_master import collaboration, content_plan, content_production, eligibility, models, service
from deck_master.store import Store
from deck_master.tasks import EnvelopeError, TaskConflict

from test_compose_v2_phases import (_accept_argument, _adopt_direction, _argument_narrative,
                                  _instruction, _page, _plan_input, _scope, _source_link)


def dispatched_revision(tmp_path, *, layers=None):
    source = tmp_path / "source.txt"
    source.write_text("SYNTHETIC engineering input: record unknown fields explicitly.\nNo measured benefit is provided.\n")
    project = tmp_path / "p"
    service.create(project, brief="Synthetic planning-only input revision", sources=[source],
                   audience="Synthetic initial audience", presentation_mode="live", page_limit=8)
    store = Store(project)
    # S06: a planned input revision updates an adopted argument; it cannot
    # establish the initial direction merely through within_scope.
    _, argument = _accept_argument(project, store)
    _adopt_direction(project, store, argument["proposal_refs"][0])
    if layers:
        request = store.load_document()["collaboration"]["request"]
        collaboration.start_request(project, input={"intent": request["intent"], "content_intent": request["content_intent"],
            "scope": _scope(layers=layers), "replace_request_id": request["request_id"],
            "instruction_evidence": _instruction(store, "s02-explicit-narrow-request")},
            base_revision=store.current_revision_id(), operation_id="s02-narrow-request")
    service.inputs_update(project, patch={"reason": "Explicit synthetic audience clarification",
        "task_patch": {"audience": "Synthetic clarified audience"}},
        base_revision=store.current_revision_id(), operation_id="s02-input-update")
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref).get("intent") == "input_revision"
                and store.read_object_json(ref)["status"] == "awaiting_host")
    service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-s02-engineering-writer",
        supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
    return project, store, task


def planned_payload(store, task, *, whole_plan=True):
    doc = store.load_document()
    narrative = _argument_narrative(doc["project_id"])
    nref = store.put_json_object(narrative)
    order = ["p" + str(i) for i in range(1, 7)]
    plan = _plan_input(doc, order, source_links=[_source_link(store, doc, "L1")])
    if whole_plan:
        plan = {"schema_version": "content_plan.v2", "plan_id": "s02-plan", "version": 1,
            "project_id": doc["project_id"], "task_id": task["task_id"], "origin": "host_composed",
            "basis": {"revision_id": doc["revision_id"], "input_digest": task["input_digest"]},
            "previous_ref": None, "mode": "planned", "narrative_ref": nref,
            "imported_manuscript": None, "input": plan, "page_links": []}
    pref = store.put_json_object(plan)
    return {"changed_layers": ["narrative", "plan"],
        "proposals": [{"layer": "narrative", "ref": nref}, {"layer": "plan", "ref": pref}],
        "diff": {"input_digest": task["input_digest"], "summary": "Reconcile clarified audience in argument and proposed six-page plan; no Page text requested.",
            "changed_page_ids": [], "removed_page_ids": [], "page_order": []}}


def submit(project, task, payload):
    return service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload={"schema_version": "compose_result.v2",
            "kind": "compose", "variant": "input_revision", "task_id": task["task_id"],
            "operation_id": task["operation_id"], "produced_against": task["produced_against"],
            "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
            "payload": payload, "usage_events": []})


@pytest.mark.parametrize("whole_plan", [True, False])
def test_planned_revision_retains_six_proposed_pages_without_creating_any(tmp_path, whole_plan):
    project, store, task = dispatched_revision(tmp_path)
    payload = planned_payload(store, task, whole_plan=whole_plan)
    before = store.load_document()
    result = submit(project, task, payload)
    doc = store.load_document()
    assert result["status"] == "accepted"
    assert doc["pages"] == [] and doc["outputs"] == before["outputs"]
    pref = next(ref for ref in result["result_refs"] if store.read_object_json(ref).get("schema_version") == "content_plan.v2")
    plan = store.read_object_json(pref)
    assert plan["mode"] == "planned" and plan["page_links"] == []
    assert plan["input"]["page_order"] == ["p" + str(i) for i in range(1, 7)]
    assert plan["narrative_ref"] == payload["proposals"][0]["ref"]
    assert doc["narrative"] == plan["narrative_ref"]
    assert doc["content_basis"]["resolved_by_task_id"] == task["task_id"]
    assert models.input_alignment(doc) == "no_content"
    projected = content_plan.projection(store, doc)
    assert projected["mode"] == "planned" and projected["applicability"] == "current"
    assert all(role["page_ref"] is None and role["basis_status"] == "planned" for role in projected["goals"])
    assert content_production.content_phase_status(store, doc)["phase"] == "page_copy"


def fingerprint(project):
    return {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}


@pytest.mark.parametrize("fault,match", [
    ("qualification-label", "qualifications must name actual qualification nodes"),
    ("qualification-claim-id", "qualifications must name actual qualification nodes"),
    ("source-version", "source identity or version"),
    ("source-locator", "locator does not exist"),
    ("unknown-node", "nodes outside"),
    ("duplicate-proposed-page", "duplicate page ids"),
    ("foreign-narrative", "another Narrative"),
    ("foreign-project", "another project"),
    ("planned-links", "planned Plan has no bound"),
    ("bound-without-pages", "without actual Pages"),
    ("ghost-diff-pages", "complete resulting set"),
    ("wrong-input-digest", "dispatched input revision"),
])
def test_planning_still_rejects_bad_semantics_and_identity_before_any_write(tmp_path, fault, match):
    project, store, task = dispatched_revision(tmp_path)
    payload = planned_payload(store, task)
    plan = store.read_object_json(payload["proposals"][1]["ref"])
    if fault == "qualification-label": plan["input"]["page_roles"][0]["required_qualifications"] = ["Preserve the unknown boundary"]
    if fault == "qualification-claim-id": plan["input"]["page_roles"][0]["required_qualifications"] = ["n1"]
    if fault == "source-version": plan["input"]["page_roles"][0]["source_links"][0]["source_version"]["original_sha256"] = "a" * 64
    if fault == "source-locator": plan["input"]["page_roles"][0]["source_links"][0]["locator"] = "L999"
    if fault == "unknown-node": plan["input"]["page_roles"][0]["narrative_node_ids"] = ["not-in-this-argument"]
    if fault == "duplicate-proposed-page": plan["input"]["page_order"].append("p1")
    if fault == "foreign-narrative": plan["narrative_ref"] = store.put_json_object({"synthetic": "other Narrative identity"})
    if fault == "foreign-project": plan["project_id"] = "another-project"
    if fault == "planned-links": plan["page_links"] = [{"page_id": "p1", "page_ref": payload["proposals"][0]["ref"], "plan_role_page_id": "p1"}]
    if fault == "bound-without-pages":
        plan["mode"] = "bound"
        plan["page_links"] = [{"page_id": pid, "page_ref": payload["proposals"][0]["ref"], "plan_role_page_id": pid} for pid in plan["input"]["page_order"]]
    if fault == "ghost-diff-pages": payload["diff"]["page_order"] = list(plan["input"]["page_order"])
    if fault == "wrong-input-digest": payload["diff"]["input_digest"] = "a" * 64
    payload["proposals"][1]["ref"] = store.put_json_object(plan)
    before = fingerprint(project)
    with pytest.raises((EnvelopeError, models.ModelError, TaskConflict), match=match): submit(project, task, payload)
    assert fingerprint(project) == before


def produced_pages(tmp_path):
    project, store, task = dispatched_revision(tmp_path)
    submit(project, task, planned_payload(store, task))
    service.continue_project(project)
    task = next(store.read_object_json(ref) for ref in reversed(store.load_document()["tasks"])
                if store.read_object_json(ref)["status"] == "awaiting_host"
                and (store.read_object_json(ref).get("collaboration_binding") or {}).get("phase") == "page_copy")
    service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-s02-page-author",
        supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
    doc = store.load_document(); order = ["p" + str(i) for i in range(1, 7)]
    plan = store.read_object_json(doc["content_plan"])
    pages = [_page(store, doc, pid) for pid in order]
    result = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload={"schema_version": "compose_result.v2", "kind": "compose",
            "variant": "page_copy", "task_id": task["task_id"], "operation_id": task["operation_id"],
            "produced_against": task["produced_against"], "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
            "payload": {"pages": pages, "page_order": order, "plan_input": plan["input"]}, "usage_events": []})
    assert result["status"] == "accepted"
    return project, store, plan


def existing_revision(project, store, *, operation_id="s02-update-existing", audience="Synthetic final clarified audience"):
    service.inputs_update(project, patch={"reason": "Explicit subsequent synthetic audience clarification",
        "task_patch": {"audience": audience}},
        base_revision=store.current_revision_id(), operation_id=operation_id)
    task = next(store.read_object_json(ref) for ref in reversed(store.load_document()["tasks"])
                if store.read_object_json(ref).get("intent") == "input_revision" and store.read_object_json(ref)["status"] == "awaiting_host")
    service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-s02-existing-author",
        supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
    return task


def test_planned_then_actual_copy_binds_every_real_ref_and_stays_unreviewed(tmp_path):
    from deck_master import content_review
    project, store, planned = produced_pages(tmp_path)
    doc = store.load_document(); bound = store.read_object_json(doc["content_plan"])
    assert planned["mode"] == "planned" and planned["page_links"] == []
    assert bound["mode"] == "bound" and bound["narrative_ref"] == planned["narrative_ref"] == doc["narrative"]
    assert bound["previous_ref"] == store.load_document(doc["parent_revision_id"])["content_plan"]
    assert bound["input"]["page_order"] == [row["page_id"] for row in doc["pages"]]
    assert [{"page_id": l["page_id"], "page": l["page_ref"]} for l in bound["page_links"]] == [{"page_id": r["page_id"], "page": r["page"]} for r in doc["pages"]]
    assert content_review.preproduction_status(store, doc)["status"] != "pass"
    assert not doc["outputs"]["pptx"]


@pytest.mark.parametrize("fault", [None, "order", "wrong-page-ref", "wrong-role-ref"])
def test_existing_pages_keep_complete_bound_order_and_actual_refs(tmp_path, fault):
    project, store, _ = produced_pages(tmp_path)
    task = existing_revision(project, store)
    doc = store.load_document(); plan = store.read_object_json(doc["content_plan"])
    old_pages = deepcopy(doc["pages"])
    if fault == "order":
        plan["input"]["page_order"].reverse()
    if fault == "wrong-page-ref": plan["page_links"][0]["page_ref"] = doc["pages"][1]["page"]
    if fault == "wrong-role-ref": plan["page_links"][0]["plan_role_page_id"] = "p2"
    payload = {"changed_layers": ["plan"], "proposals": [{"layer": "plan", "ref": store.put_json_object(plan)}],
        "diff": {"input_digest": task["input_digest"], "summary": "Reconcile actual current plan only; keep all six Page refs unchanged.", "changed_page_ids": []}}
    before = fingerprint(project)
    if fault:
        with pytest.raises(EnvelopeError, match="order must match|actual resulting Pages"): submit(project, task, payload)
        assert fingerprint(project) == before
    else:
        submit(project, task, payload)
        doc = store.load_document(); new_plan = store.read_object_json(doc["content_plan"])
        assert doc["pages"] == old_pages and new_plan["mode"] == "bound"
        assert new_plan["page_links"] == plan["page_links"]


def test_planning_does_not_expand_actual_layer_scope(tmp_path):
    project, store, task = dispatched_revision(tmp_path, layers=["narrative"])
    payload = planned_payload(store, task)
    before = fingerprint(project)
    with pytest.raises(eligibility.EligibilityBlocked, match="outside the current request scope"): submit(project, task, payload)
    assert fingerprint(project) == before


def test_stale_actual_revision_cannot_accept_a_valid_planned_result(tmp_path):
    project, store, task = dispatched_revision(tmp_path)
    payload = planned_payload(store, task)
    service.inputs_update(project, patch={"reason": "New real clarification supersedes old input basis", "task_patch": {"audience": "Another synthetic audience"}},
        base_revision=store.current_revision_id(), operation_id="s02-newer-update")
    before = store.load_document()
    with pytest.raises(TaskConflict): submit(project, task, payload)
    after = store.load_document()
    # Existing Runtime may commit late-Task/receipt bookkeeping. CAS protects
    # actual content/input/control, not an assertion that no bookkeeping exists.
    protected = ("task", "sources", "content_basis", "narrative", "content_plan", "pages", "outputs", "design_context", "collaboration")
    assert {key: after.get(key) for key in protected} == {key: before.get(key) for key in protected}


def test_removing_every_actual_page_does_not_silently_reclassify_old_bound_plan(tmp_path):
    project, store, _ = produced_pages(tmp_path)
    task = existing_revision(project, store)
    ids = [row["page_id"] for row in store.load_document()["pages"]]
    payload = {"changed_layers": ["page_copy"], "proposals": [], "diff": {"input_digest": task["input_digest"],
        "summary": "Explicit all-page removal without supplying a replacement Plan", "changed_page_ids": ids, "removed_page_ids": ids, "page_order": []}}
    before = fingerprint(project)
    with pytest.raises(EnvelopeError, match="Plan and resulting page order must match"): submit(project, task, payload)
    assert fingerprint(project) == before


def planning_with_existing_pages(tmp_path, *, one_page=True):
    from deck_master import collaboration
    project, store, _ = produced_pages(tmp_path)
    if one_page:
        task = existing_revision(project, store)
        doc = store.load_document()
        removed = [p["page_id"] for p in doc["pages"] if p["page_id"] != "p5"]
        payload = {"changed_layers": ["page_copy", "plan"],
            "proposals": [{"layer": "plan", "ref": store.put_json_object(_plan_input(doc, ["p5"], source_links=[_source_link(store, doc, "L1")]))}],
            "diff": {"input_digest": task["input_digest"], "summary": "Explicit synthetic membership change retains one actual representative Page.", "changed_page_ids": removed, "removed_page_ids": removed, "page_order": ["p5"]}}
        submit(project, task, payload)
    doc = store.load_document()
    evidence = {"kind": "host_attested_instruction", "source_ref": store.put_blob(b"SYNTHETIC planning only; preserve actual Pages, propose future plan.", ext="txt"),
        "source_locator": "synthetic:s02-planning", "actor_id": None, "transport_receipt_ref": None, "presentation_ref": None}
    collaboration.start_request(project, input={"intent": "content_only", "content_intent": "plan_only", "scope": _scope(layers=["narrative", "plan"], allow_page_membership_change=False),
        "instruction_evidence": evidence, "replace_request_id": doc["collaboration"]["request"]["request_id"]},
        base_revision=doc["revision_id"], operation_id="s02-plan-existing-request")
    task = existing_revision(project, store, operation_id="s02-plan-existing-input", audience="Distinct synthetic future planning audience")
    return project, store, task


@pytest.mark.parametrize("one_page,new_narrative", [(True, False), (False, False), (True, True)])
def test_explicit_planned_order_preserves_current_real_pages_and_blocks_production(tmp_path, one_page, new_narrative):
    from deck_master import content_review
    from deck_master.design_requirements import resolve_content_requirements
    project, store, task = planning_with_existing_pages(tmp_path, one_page=one_page)
    doc = store.load_document(); before_pages = deepcopy(doc["pages"])
    payload = planned_payload(store, task)
    if new_narrative:
        narrative = store.read_object_json(payload["proposals"][0]["ref"])
        narrative["version"] += 1
        nref = store.put_json_object(narrative)
        payload["proposals"][0]["ref"] = nref
        plan = store.read_object_json(payload["proposals"][1]["ref"])
        plan["narrative_ref"] = nref
        payload["proposals"][1]["ref"] = store.put_json_object(plan)
    else:
        payload["changed_layers"] = ["plan"]
        payload["proposals"] = [payload["proposals"][1]]
    result = submit(project, task, payload)
    after = store.load_document(); plan = store.read_object_json(after["content_plan"])
    assert result["status"] == "accepted" and after["pages"] == before_pages
    assert plan["mode"] == "planned" and plan["page_links"] == [] and len(plan["input"]["page_order"]) == 6
    assert content_plan.projection(store, after)["applicability"] == "basis_changed"
    assert all(row["page_ref"] is None for row in content_plan.projection(store, after)["page_roles"])
    assert content_production.content_phase_status(store, after)["action"] == "complete"  # real plan_only response
    assert content_review.preproduction_status(store, after)["status"] != "pass"
    page_ref = after["pages"][0]["page"]
    page = store.read_object_json(page_ref)
    with pytest.raises(models.ModelError, match="link every current Page|planned|bound"):
        resolve_content_requirements(store, after, page_ref)
    assert page["content_mapping"]["narrative_ref"] == doc["narrative"]  # historical Page mapping is not rewritten
    if new_narrative: assert after["narrative"] != doc["narrative"]
    # The plan_only request is truly closed. Open a real new request before a
    # later Narrative-only revision; never change closed-request enforcement.
    from deck_master import collaboration
    current = store.load_document()
    evidence = {"kind": "host_attested_instruction", "source_ref": store.put_blob(b"SYNTHETIC new follow-up planning request; preserve existing Page evidence.", ext="txt"),
        "source_locator": "synthetic:s02-followup", "actor_id": None, "transport_receipt_ref": None, "presentation_ref": None}
    collaboration.start_request(project, input={"intent": "content_only", "content_intent": "plan_only", "scope": _scope(layers=["narrative", "plan"], allow_page_membership_change=False),
        "instruction_evidence": evidence, "replace_request_id": current["collaboration"]["request"]["request_id"]},
        base_revision=current["revision_id"], operation_id="s02-followup-plan-request")
    # Inherit planned semantics and preserve sample refs, not fake bound links.
    task = existing_revision(project, store, operation_id="s02-plan-narrative-followup", audience="Another distinct planning clarification")
    narrative = store.read_object_json(store.load_document()["narrative"]); narrative["version"] += 1
    nref = store.put_json_object(narrative)
    submit(project, task, {"changed_layers": ["narrative"], "proposals": [{"layer": "narrative", "ref": nref}],
        "diff": {"input_digest": task["input_digest"], "summary": "Future Narrative revision only, existing sample stays historical.", "changed_page_ids": []}})
    after = store.load_document(); retained = store.read_object_json(after["content_plan"])
    assert retained["mode"] == "planned" and retained["page_links"] == [] and after["pages"] == before_pages
    assert retained["narrative_ref"] == nref and content_plan.projection(store, after)["applicability"] == "basis_changed"


@pytest.mark.parametrize("fault,match", [("page-write", "outside"), ("diff-order", "resulting set"),
    ("bound", "order must match"), ("qualification", "actual qualification nodes"),
    ("source", "source identity or version"), ("narrative", "another Narrative")])
def test_planned_with_sample_does_not_relax_scope_bound_or_plan_semantics(tmp_path, fault, match):
    project, store, task = planning_with_existing_pages(tmp_path)
    payload = planned_payload(store, task)
    payload["changed_layers"] = ["plan"]; payload["proposals"] = [payload["proposals"][1]]
    plan = store.read_object_json(payload["proposals"][0]["ref"])
    if fault == "page-write":
        payload["changed_layers"].append("page_copy")
        payload["proposals"].append({"layer": "page_copy", "ref": store.load_document()["pages"][0]["page"]})
        payload["diff"]["changed_page_ids"] = ["p5"]
    if fault == "diff-order": payload["diff"]["page_order"] = plan["input"]["page_order"]
    if fault == "bound":
        plan["mode"] = "bound"
        plan["page_links"] = [{"page_id": pid, "page_ref": store.load_document()["pages"][0]["page"], "plan_role_page_id": pid} for pid in plan["input"]["page_order"]]
    if fault == "qualification": plan["input"]["page_roles"][0]["required_qualifications"] = ["n1"]
    if fault == "source": plan["input"]["page_roles"][0]["source_links"][0]["source_version"]["original_sha256"] = "a" * 64
    if fault == "narrative": plan["narrative_ref"] = store.put_json_object({"other": "Narrative"})
    payload["proposals"][0]["ref"] = store.put_json_object(plan)
    before = fingerprint(project)
    with pytest.raises((EnvelopeError, models.ModelError, eligibility.EligibilityBlocked), match=match): submit(project, task, payload)
    assert fingerprint(project) == before
