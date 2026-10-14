"""T03 slice 2: collaboration binding construction, the fixed eligibility digest
and the dispatch gate (CONTRACTS §5, §6.3, §7).

The binding is built by the Runtime: a Host never submits one, cannot omit a
registered dependency, and cannot skip a required decision by claiming there is
none. Projects below the collaboration.v1 writer keep their exact old dispatch.
"""
import hashlib

import pytest

from deck_master import collaboration, collaboration_binding, content_production, models, service
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import Store


def _stored(store, seed: str) -> dict:
    return store.put_json_object({"fixture": seed})


def _instruction(store, seed="instruction") -> dict:
    return {"kind": "host_attested_instruction", "source_ref": _stored(store, seed),
            "source_locator": f"chat:{seed}", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _scope(**over) -> dict:
    scope = {"subject": "deck", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["narrative", "plan"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "working"}
    scope.update(over)
    return scope


def _project(tmp_path, *, material=True, presentation_mode=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "proj"
    sources = []
    if material:
        path = tmp_path / "S1-material.txt"
        path.write_text("第一行：版本未知时先记录未知。\n第二行：紧急程度与可得性是两个维度。\n",
                        encoding="utf-8")
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


def _request(project, store, *, layers=("narrative", "plan", "page_copy", "speech"),
             intent="content_only", content_intent="content_full"):
    return collaboration.start_request(
        project, input={"intent": intent, "content_intent": content_intent,
                        "instruction_evidence": _instruction(store),
                        "scope": _scope(layers=list(layers)), "replace_request_id": None},
        base_revision=store.load_document()["revision_id"], operation_id="op-request")


def _decision(project, store, *, topic="direction", disposition="accepted",
              authority_mode="direct_user", layers=("narrative",), operation_id="op-decision",
              scope=None, **over):
    return collaboration.record_decision(
        project, input={"topic": topic, "disposition": disposition,
                        "authority_mode": authority_mode, "value": over.pop("value", {"ok": True}),
                        "scope": scope or _scope(layers=list(layers)),
                        "instruction_evidence": _instruction(store, operation_id), **over},
        base_revision=store.load_document()["revision_id"], operation_id=operation_id)


def _grant(project, store, *, mode="execute", actions=("compose",), topics=(),
           max_external_calls=0, scope=None, operation_id="op-grant", **over):
    return collaboration.grant(
        project, input={"mode": mode, "actions": list(actions), "delegated_topics": list(topics),
                        "max_external_calls": max_external_calls, "max_candidate_count": 0,
                        "scope": scope or _scope(layers=["narrative", "plan", "page_copy"]),
                        "instruction_evidence": _instruction(store, operation_id), **over},
        base_revision=store.load_document()["revision_id"], operation_id=operation_id)


# ---------------------------------------------------------------------------
# Construction


def test_build_binding_names_the_current_request_and_completes_the_basis(tmp_path):
    project, store = _project(tmp_path)
    started = _request(project, store)
    document = store.load_document()
    binding = collaboration_binding.build_binding(
        store, document, phase="argument", executor_type="host",
        write_scope=content_production.write_scope_for(store, document, "argument"),
        adoption_policy="proposal_only")
    assert binding["request_id"] == started["request_id"]
    keys = [dependency_slices_key(item) for item in binding["eligibility_basis"]]
    # Registered minimum for the phase is completed by the service.
    assert "task_fact:brief:value" in keys and "task_fact:audience:value" in keys
    # A caller-supplied slice is kept, not replaced.
    extra = {"kind": "source", "identity": document["sources"][0]["source_id"],
             "projection": "extract",
             "ref": document["sources"][0]["extract"],
             "sha256": document["sources"][0]["extract"]["sha256"]}
    binding = collaboration_binding.build_binding(
        store, document, phase="argument", executor_type="host",
        write_scope=content_production.write_scope_for(store, document, "argument"),
        adoption_policy="proposal_only", basis=[extra])
    assert any(item["identity"] == extra["identity"] for item in binding["eligibility_basis"])


def test_build_binding_refuses_without_an_open_request(tmp_path):
    project, store = _project(tmp_path)
    with pytest.raises(ModelError, match="current open work request"):
        collaboration_binding.build_binding(
            store, store.load_document(), phase="framing", executor_type="host",
            write_scope=_scope(), adoption_policy="proposal_only")


def test_build_binding_rejects_unregistered_phase_executor_and_policy(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    with pytest.raises(ModelError, match="unregistered phase"):
        collaboration_binding.build_binding(store, document, phase="nope",
                                            executor_type="host", write_scope=_scope(),
                                            adoption_policy="proposal_only")
    with pytest.raises(ModelError, match="executor_type"):
        collaboration_binding.build_binding(store, document, phase="framing",
                                            executor_type="robot", write_scope=_scope(),
                                            adoption_policy="proposal_only")
    with pytest.raises(ModelError, match="adoption_policy"):
        collaboration_binding.build_binding(store, document, phase="framing",
                                            executor_type="host", write_scope=_scope(),
                                            adoption_policy="sometimes")


def dependency_slices_key(dep):
    from deck_master.dependency_slices import slice_key
    return slice_key(dep)


def test_basis_never_manufactures_an_absent_pointer_slice(tmp_path):
    """An absent Narrative pointer is a real state, not a missing registration."""
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    binding = collaboration_binding.build_binding(
        store, document, phase="page_copy", executor_type="host",
        write_scope=_scope(layers=["page_copy", "plan"]), adoption_policy="within_scope")
    assert not [item for item in binding["eligibility_basis"]
                if item["kind"] == "artifact" and item["identity"] == "narrative"]


# ---------------------------------------------------------------------------
# Digest formula


def test_eligibility_digest_matches_the_fixed_formula(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    scope = _scope(page_ids=["p2", "p1"], layers=["plan", "narrative"])
    binding = collaboration_binding.build_binding(
        store, document, phase="argument", executor_type="host", write_scope=scope,
        adoption_policy="proposal_only")
    ordered = sorted(binding["eligibility_basis"],
                     key=lambda item: dependency_slices_key(item))
    payload = {"phase": "argument",
               "write_scope": {"subject": "deck", "page_ids": ["p1", "p2"],
                               "page_manifest_ref": None, "external_artifact_ref": None,
                               "layers": ["narrative", "plan"],
                               "allow_page_membership_change": False,
                               "allow_page_order_change": False,
                               "purpose": "working"},
               "basis": [item["sha256"] for item in ordered]}
    assert binding["eligibility_digest"] == hashlib.sha256(
        models.canonical_json_bytes(payload)).hexdigest()


def test_binding_errors_report_every_problem(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    task = content_production.build_phase_task(store, document, operation_id="b-1", phase="framing")
    assert collaboration_binding.binding_errors(document, task) == []
    tampered = {**task, "collaboration_binding": {
        **task["collaboration_binding"],
        "request_id": "req-other", "eligibility_digest": "0" * 64,
        "phase": "not-a-phase"}}
    problems = collaboration_binding.binding_errors(document, tampered)
    assert any("phase" in problem for problem in problems)
    assert any("eligibility_digest" in problem for problem in problems)
    assert any("current work request" in problem for problem in problems)
    assert collaboration_binding.binding_errors(document, {}) == \
        ["task/collaboration_binding: missing"]


def test_require_binding_rejects_bound_refs_outside_the_region(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    task = content_production.build_phase_task(store, document, operation_id="b-2", phase="framing")
    ghost = _stored(store, "ghost-decision")
    drifted = {**task, "collaboration_binding": {
        **task["collaboration_binding"], "decision_refs": [ghost]}}
    with pytest.raises(ModelError, match="collaboration region"):
        collaboration_binding.require_binding(document, drifted)


def test_scope_containment_helper_is_the_shared_rule(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    parent = _scope(page_ids=["p1"], layers=["narrative", "plan"])
    child = _scope(page_ids=["p1"], layers=["narrative"])
    assert collaboration_binding.containment_gaps(store, parent, child) == []
    wider = _scope(page_ids=["p1", "p2"], layers=["narrative"])
    assert "page_ids" in collaboration_binding.containment_gaps(store, parent, wider)


# ---------------------------------------------------------------------------
# Requirement derivation (Runtime side; T04 owns entry enforcement)


def test_phase_requirements_are_derived_not_submitted(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    framing = collaboration_binding.derive_requirements(store, document, phase="framing")
    assert framing["required_decision_topics"] == [] and framing["allowed"] is True
    argument = collaboration_binding.derive_requirements(store, document, phase="argument")
    assert argument["required_decision_topics"] == ["direction"]
    assert "decision_needed:direction" in argument["gaps"] and argument["allowed"] is False


def test_direction_decision_and_delegation_satisfy_the_requirement(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    _decision(project, store, topic="direction", layers=["narrative", "plan"])
    document = store.load_document()
    state = collaboration_binding.derive_requirements(store, document, phase="argument")
    assert state["allowed"] is True and state["satisfied_decisions"]
    # A covering delegate alone also satisfies it (no repeated confirmation).
    project2, store2 = _project(tmp_path / "second")
    _request(project2, store2)
    _grant(project2, store2, mode="delegate", topics=["direction"], actions=["content.compose"],
           operation_id="op-delegate")
    state2 = collaboration_binding.derive_requirements(store2, store2.load_document(),
                                                      phase="argument")
    assert state2["allowed"] is True and state2["covering_delegations"]


def test_speech_verbatim_needs_an_explicit_request_but_cues_do_not(tmp_path):
    project, store = _project(tmp_path, presentation_mode=None)
    _request(project, store)
    document = store.load_document()
    assert collaboration_binding.derive_requirements(
        store, document, phase="speech", speech_mode="cues")["required_decision_topics"] == []
    verbatim = collaboration_binding.derive_requirements(store, document, phase="speech",
                                                         speech_mode="verbatim")
    assert verbatim["required_decision_topics"] == ["speech"]
    assert "decision_needed:speech" in verbatim["gaps"]
    _decision(project, store, topic="speech", layers=["speech"], operation_id="op-speech")
    assert collaboration_binding.derive_requirements(
        store, store.load_document(), phase="speech", speech_mode="verbatim")["allowed"] is True


def test_production_and_delivery_need_an_effective_execution_grant(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    production = collaboration_binding.derive_requirements(store, store.load_document(),
                                                           phase="production")
    assert production["requires_external_calls"] is True
    assert "authorization_needed" in production["gaps"]
    _grant(project, store, mode="execute", actions=["blueprint.generate"],
           max_external_calls=2, operation_id="op-execute")
    # The grant alone is not enough: production also needs the direction decision.
    mid = collaboration_binding.derive_requirements(store, store.load_document(),
                                                    phase="production")
    assert mid["authorization_ref"] and mid["gaps"] == ["decision_needed:direction"]
    _decision(project, store, topic="direction", layers=["narrative", "plan"],
              operation_id="op-direction-production")
    state = collaboration_binding.derive_requirements(store, store.load_document(),
                                                      phase="production")
    assert state["allowed"] is True and state["authorization_ref"]
    # A zero-credit execute grant cannot cover external production.
    project2, store2 = _project(tmp_path / "third")
    _request(project2, store2)
    _grant(project2, store2, mode="execute", actions=["blueprint.generate"],
           max_external_calls=0, operation_id="op-execute-zero")
    assert "authorization_needed" in collaboration_binding.derive_requirements(
        store2, store2.load_document(), phase="production")["gaps"]


# ---------------------------------------------------------------------------
# Dispatch gate


def test_gate_stamps_every_dispatch_in_a_collaboration_project(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    compose = content_production.open_phase_task(store, store.load_document(),
                                                 operation_id="gate-1", phase="framing")
    binding = compose["collaboration_binding"]
    assert binding["phase"] == "framing" and binding["eligibility_digest"]
    assert collaboration_binding.binding_errors(store.load_document(), compose) == []


def test_dispatch_without_a_request_is_refused(tmp_path):
    """The gate closes the door the moment a project is at collaboration.v1."""
    project, store = _project(tmp_path)
    with pytest.raises(ModelError):
        content_production.open_phase_task(store, store.load_document(),
                                           operation_id="gate-2", phase="framing")
    with pytest.raises(ModelError):
        service.open_compose_task(store, store.load_document(), operation_id="gate-3")


def test_host_and_blueprint_dispatch_receive_their_phase_binding(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store, intent="edit")
    document = store.load_document()
    # A review dispatch on an existing page gets a review-phase binding.
    page = {"schema_version": "deck_page_package.v2", "page_id": "p1",
            "customer_visible": {"title": "标题", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": "正文"}]},
            "visual_spec": {"intent": "培训", "reference_mode": "new_design"}}
    page_ref = store.put_json_object(page)
    bumped = bump_revision(document, {"operation_id": "add-page", "kind": "content_update",
                                      "description": "fixture page", "read_set": []})
    bumped["pages"] = [{"page_id": "p1", "page": page_ref, "blueprint": None, "svg": None,
                        "svg_preview": None, "ppt_preview": None}]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="add-page")
    task = service.open_host_task(store, kind="review", page_ids=["p1"], instruction="审阅这一页")
    binding = task["collaboration_binding"]
    assert binding["phase"] == "review" and binding["write_scope"]["layers"] == ["review"]
    assert binding["write_scope"]["page_ids"] == ["p1"]
    task = service.open_host_task(store, kind="repair", page_ids=["p1"], instruction="修复这一页")
    assert task["collaboration_binding"]["phase"] == "production"


def test_gate_is_inert_below_the_collaboration_writer(tmp_path):
    project = tmp_path / "legacy"
    service.create(project, brief="legacy", sources=[], project_format="workbench.v3")
    store = Store(project)
    document = store.load_document()
    task = service.open_compose_task(store, document, operation_id="legacy-1")
    assert "collaboration_binding" not in task
    assert collaboration_binding.stamp_task(
        store, document, {"task_id": "t"}, phase="framing") == {"task_id": "t"}
