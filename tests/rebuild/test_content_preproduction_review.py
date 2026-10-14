"""T03 slice 3: preproduction content review (CONTRACTS §6.3, §11.6, AC-M05).

The dispatched independent-model review envelope must contain the materials, the
task facts and the *complete* candidate manuscript; independence must be a real
receipt from a different executor, and a missing capability returns
needs_reviewer instead of a silent self-review.
"""
import pathlib

import pytest

from synthetic_review_provider import synthetic_context, accept_with_synthetic_provider, dispatch_with_synthetic_provider
from deck_master.review_evidence import EvidenceRejected

from deck_master import collaboration, content_production, content_review, models, service
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import Store
from deck_master.tasks import EnvelopeError


def _stored(store, seed: str) -> dict:
    return store.put_json_object({"fixture": seed})


def _instruction(store, seed="instruction") -> dict:
    return {"kind": "host_attested_instruction", "source_ref": _stored(store, seed),
            "source_locator": f"chat:{seed}", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _scope(**over) -> dict:
    # A full_deck request carries the layers its flow legitimately writes;
    # the preproduction review is required for new-argument work (§6.3), so
    # the review layer sits inside the request scope from the start.
    scope = {"subject": "deck", "page_ids": [], "page_manifest_ref": None,
             "external_artifact_ref": None,
             "layers": ["narrative", "plan", "page_copy", "speech", "review"],
             "allow_page_membership_change": True, "allow_page_order_change": False,
             "purpose": "working"}
    scope.update(over)
    return scope


def _source_link(store, document, locator="L1"):
    source = (document.get("sources") or [{}])[0]
    return {"source_id": source.get("source_id"),
            "source_version": {"original_sha256": source.get("original_sha256"),
                               "extract": source.get("extract")},
            "locator": locator}


def _project(tmp_path, *, quality=None, presentation_mode=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "S1-material.txt"
    path.write_text("第一行：版本未知时先记录未知。\n第二行：紧急程度与可得性是两个维度。\n"
                    "第三行：不得从缺字段率推出节省比例。\n", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="培训材料", title="记录训练", sources=[path],
                   project_format="workbench.v3", audience="新接单员工",
                   presentation_mode=presentation_mode)
    store = Store(project)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "bootstrap-collaboration",
                                      "kind": "collaboration_update",
                                      "description": "bootstrap region", "read_set": []})
    bumped["collaboration"] = {
        "schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": quality or {
            "content_review_requirement": "independent_model_or_human",
            "requirement_origin": "default_new_argument", "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": [],
    }
    require_writer(bumped, "collaboration.v1")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="bootstrap-collaboration")
    store = Store(project)
    collaboration.start_request(
        project, input={"intent": "full_deck", "content_intent": None,
                        "instruction_evidence": _instruction(store),
                        "scope": _scope(), "replace_request_id": None},
        base_revision=store.load_document()["revision_id"], operation_id="op-request")
    return project, Store(project)


def _argument_narrative(project_id) -> dict:
    return {
        "schema_version": "narrative.v1", "narrative_id": "nar-1", "version": 1,
        "project_id": project_id, "origin": "host_composed", "maturity": "argument",
        "input_basis": [], "communication_job": {
            "mode": "train", "audience_fact_key": "task.audience",
            "audience_question": "新接单员工如何记录未知版本",
            "desired_outcome": "能独立填写可交接的记录",
            "observable_success": "在新情境题上给出正确下一动作",
            "use_mode": "live", "primary_use": "live"},
        "central_node_id": "n1",
        "nodes": [
            {"node_id": "n1", "role": "claim", "statement": "版本未知时记录未知，再按紧急程度决定流转",
             "authority": "instruction", "source_links": [], "qualification_node_ids": ["q1"],
             "unresolved_issue_ids": []},
            {"node_id": "q1", "role": "qualification",
             "statement": "缺字段率不等于可节省比例",
             "authority": "instruction", "source_links": [], "qualification_node_ids": [],
             "unresolved_issue_ids": []}],
        "edges": [{"from_node_id": "q1", "to_node_id": "n1", "relation": "qualifies"}],
        "issues": [], "alternatives": [], "previous_ref": None,
    }


def _page(store, document, page_id="p1", *, notes="这一页讲清两个独立判断。") -> dict:
    mapping = {
        "narrative_ref": document.get("narrative"), "plan_role_page_id": page_id,
        "visible_links": [
            {"element_ref": f"atom:{page_id}:title", "narrative_node_ids": ["n1"],
             "source_links": []},
            {"element_ref": f"atom:{page_id}:block:b1:text", "narrative_node_ids": ["n1"],
             "source_links": [_source_link(store, document, "L1")]}],
        "speech_segments": ([{"segment_id": "s1", "start_codepoint": 0,
                              "end_codepoint": len(notes), "narrative_node_ids": ["n1"],
                              "kind": "cue", "estimated_seconds": 20}] if notes else []),
    }
    return {
        "schema_version": "deck_page_package.v2", "page_id": page_id,
        "customer_visible": {"title": "记录未知版本",
                             "body_blocks": [{"id": "b1", "type": "paragraph",
                                              "text": "先记录未知，再按紧急程度流转。"}]},
        "speaker_notes": notes,
        "visual_spec": {"intent": "培训页", "reference_mode": "new_design"},
        "content_mapping": mapping,
    }


def _plan_input(document, page_ids, links) -> dict:
    roles = [{"page_id": pid, "role": "记录未知值", "audience_question": "这一页解决什么",
              "intended_takeaway": "能记录未知并说明下一动作", "narrative_node_ids": ["n1"],
              "source_links": links, "required_qualifications": ["q1"],
              "content_profile": "evidence", "density_rationale": "规则加一个限定",
              "timing_seconds": 75, "transition_to_next": None} for pid in page_ids]
    return {"schema_version": "content_plan_input.v2",
            "chapters": [{"chapter_id": "c1", "title": "记录与流转", "page_ids": list(page_ids)}],
            "page_order": list(page_ids), "page_roles": roles,
            "page_budget": {"exact": None, "target": 6, "max": 8},
            "time_budget": {"total_seconds": 480, "speaking_seconds": 380,
                            "interaction_seconds": 100, "constraint": "hard"},
            "speech_policy": {"mode": "cues", "source": "provided", "output": "pptx_notes"},
            "issues": [], "tradeoff_issue_ids": []}


def _deck(tmp_path, *, quality=None, plan_mode="bound"):
    """A project with an adopted Narrative, bound Plan and two pages."""
    project, store = _project(tmp_path, quality=quality)
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="arg", phase="argument")
    accept_with_synthetic_provider(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": "narrative", "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": {"narrative": _argument_narrative(document["project_id"])},
                        "usage_events": []})
    document = store.load_document()
    proposal_ref = [ref for ref in store.read_object_json(
        document["tasks"][-1])["result_refs"]][0]
    decision = collaboration.record_decision(
        project, input={"topic": "direction", "disposition": "accepted",
                        "authority_mode": "direct_user", "value": {"selected": "两维度记录"},
                        "scope": _scope(layers=["narrative", "plan", "page_copy"]),
                        "instruction_evidence": _instruction(store, "direction"),
                        "subject_refs": [{"artifact_kind": "narrative",
                                          "artifact_ref": proposal_ref,
                                          "projection": "direction"}]},
        base_revision=store.load_document()["revision_id"], operation_id="op-direction")
    content_production.adopt_proposal(
        project, input={"proposal_ref": proposal_ref, "decision_ref": decision["decision_ref"],
                        "write_scope": _scope(layers=["narrative"])},
        base_revision=store.load_document()["revision_id"], operation_id="op-adopt")
    task = content_production.open_phase_task(store, store.load_document(),
                                              operation_id="pc", phase="page_copy")
    document = store.load_document()
    pages = [_page(store, document, "p1"), _page(store, document, "p2", notes="第二页口播。")]
    accept_with_synthetic_provider(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": "page_copy", "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": {"pages": pages, "page_order": ["p1", "p2"],
                                    "plan_input": _plan_input(
                                        document, ["p1", "p2"], [_source_link(store, document, "L1")])},
                        "usage_events": []})
    return project, Store(project)


def _review(store, document, kind, *, reviewer, status="pass", findings=(), deps=None,
            subjects=None) -> dict:
    reviewer = {"evidence_ref": _stored(store, f"reviewer-evidence-{kind}-{reviewer['type']}"),
                **reviewer}
    page_entries = document["pages"]
    subjects = subjects if subjects is not None else [
        document["narrative"], document["content_plan"]] + [e["page"] for e in page_entries]
    if deps is None:
        deps = [{"kind": "content", "identity": "narrative",
                 "sha256": document["narrative"]["sha256"]},
                {"kind": "content", "identity": "content_plan",
                 "sha256": document["content_plan"]["sha256"]}]
        deps += [{"kind": "content", "identity": f"page:{e['page_id']}",
                  "sha256": e["page"]["sha256"]} for e in page_entries]
        deps += [{"kind": "source", "identity": s["source_id"], "sha256": s["extract"]["sha256"]}
                 for s in document["sources"]]
    return {"schema_version": "deck_review.v2", "review_id": f"rev-{kind}",
            "kind": kind, "review_stage": "preproduction", "status": status,
            "subjects": subjects, "dependencies": deps, "reviewer": reviewer,
            "observations": [f"checked the {kind} unit against the materials"],
            "findings": list(findings), "created_at": "2026-10-12T00:00:00Z", "replaces": None}


def _independent_adapter(store, document, *, executor="exec-independent", subjects=None):
    from deck_master.content_review import _subjects_digest
    subjects = subjects if subjects is not None else [
        document["narrative"], document["content_plan"]] + [e["page"] for e in document["pages"]]
    receipt_ref = _stored(store, "independent-receipt")
    return synthetic_context({"independent_review_receipts": [
        {"receipt_ref": receipt_ref, "executor_ref": executor, "reviewer_id": "model-b",
         "subjects_sha256": _subjects_digest(subjects)}]})


def _submit_reviews(project, store, task, reviews):
    return accept_with_synthetic_provider(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"kind": "review", "pages": [], "page_order": [], "artifact_specs": [],
                        "reviews": reviews, "usage_events": [], "notes": "preproduction review"},
        adapter_context=None)


# ---------------------------------------------------------------------------
# Packet (AC-M05)


def test_review_packet_carries_materials_task_and_the_complete_manuscript(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    packet = content_review.build_review_packet(store, document)
    # Materials: the complete extract, not a name.
    assert packet["materials"][0]["extract"]["locators"][0]["text"].startswith("第一行")
    # Task facts.
    assert packet["task"]["audience"] == "新接单员工"
    assert packet["task"]["brief"] == "培训材料"
    # Complete candidate manuscript: every page's full visible copy and notes.
    pages = packet["manuscript"]["pages"]
    assert [p["page_id"] for p in pages] == ["p1", "p2"]
    for entry in pages:
        stored = store.read_object_json(entry["page_ref"])
        assert entry["customer_visible"] == stored["customer_visible"]
        assert entry["speaker_notes"] == stored["speaker_notes"]
        assert entry["content_mapping"] == stored["content_mapping"]
    # The full argument model and plan travel with it.
    assert [node["node_id"] for node in packet["narrative"]["nodes"]] == ["n1", "q1"]
    assert packet["plan"]["input"]["page_order"] == ["p1", "p2"]
    assert packet["plan"]["page_links"], "a bound plan keeps its real page links"


def test_dispatched_review_task_references_the_packet(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    outcome = dispatch_with_synthetic_provider(
        project, adapter_context=_independent_adapter(store, document))
    assert outcome["status"] == "review_dispatched"
    task = outcome["task"]
    assert task["review_stage"] == "preproduction"
    assert task["collaboration_binding"]["executor_type"] == "external_reviewer"
    assert outcome["review_draft_ref"] in task["inputs"]
    assert service.task_summary(store, store.load_document(), task)["review_stage"] == "preproduction"
    packet = store.read_object_json(outcome["review_draft_ref"])
    assert packet["manuscript"]["pages"][0]["speaker_notes"]
    assert set(packet["required_units"]) == {"argument", "page_copy", "progression", "speech"}
    assert packet["requirement"] == "independent_model_or_human"
    for unit in packet["required_units"]:
        assert unit in task["instruction"]


def test_missing_reviewer_capability_returns_needs_reviewer_with_the_draft(tmp_path):
    project, store = _deck(tmp_path)
    outcome = dispatch_with_synthetic_provider(project)
    assert outcome["status"] == "needs_reviewer"
    assert outcome["requirement"] == "independent_model_or_human"
    assert outcome["review_draft"]["manuscript"]["pages"]
    assert "independence" in outcome["reason"]
    # No task was created and no review record was faked.
    document = store.load_document()
    assert not [ref for ref in document["tasks"]
                if store.read_object_json(ref).get("review_stage") == "preproduction"]


# ---------------------------------------------------------------------------
# Acceptance


def _dispatch_and_reviews(store, document, adapter):
    outcome = dispatch_with_synthetic_provider(
        store.project_root, adapter_context=adapter)
    assert outcome["status"] == "review_dispatched"
    task = outcome["task"]
    kinds = ("argument", "page_copy", "progression", "speech")
    reviews = [_review(store, document, kind,
                       reviewer={"type": "independent_host", "id": "model-b",
                                 "execution_ref": "exec-independent",
                                 "independence_confirmed": True, "identity_receipt": None,
                                 "assurance": "host_attested"})
               for kind in kinds]
    return task, reviews


def test_independent_review_is_accepted_and_consumed(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    out = accept_with_synthetic_provider(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                produced_against=task["produced_against"],
                                result_payload={"kind": "review", "pages": [], "page_order": [],
                                                "artifact_specs": [], "reviews": reviews,
                                                "usage_events": [], "notes": "preproduction"},
                                adapter_context=adapter)
    assert out["status"] == "accepted"
    store = Store(project)
    document = store.load_document()
    status = content_review.preproduction_status(store, document)
    assert status["status"] == "pass" and not status["missing_units"]
    qualified = content_review.qualify_for_production(store, document, adapter_context=adapter)
    assert qualified["allowed"] is True and qualified["needs_reviewer"] is False


def test_self_declared_independence_is_refused(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    # A random execution_ref that no receipt matches is not independence.
    forged = [{**review, "reviewer": {**review["reviewer"], "id": "someone",
                                      "execution_ref": "random-123"}}
              for review in reviews]
    with pytest.raises(EvidenceRejected, match="actual authenticated executor"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": forged,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=adapter)
    # Without the capability at all, an independent claim cannot be accepted.
    with pytest.raises(EnvelopeError, match="does not satisfy it"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": reviews,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=None)


def test_the_author_cannot_be_the_independent_reviewer(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    # The page_copy task that wrote the manuscript is the author here.
    author_refs = content_review.author_execution_refs(
        store, document, [document["narrative"], document["content_plan"]] +
        [e["page"] for e in document["pages"]])
    assert author_refs, "the fixture must record the author's execution"
    author = sorted(author_refs)[0]
    from deck_master.content_review import _subjects_digest
    receipt_ref = _stored(store, "author-receipt")
    adapter = synthetic_context({"independent_review_receipts": [
        {"receipt_ref": receipt_ref, "executor_ref": author, "reviewer_id": "same-host",
         "subjects_sha256": _subjects_digest(
             [document["narrative"], document["content_plan"]] +
             [e["page"] for e in document["pages"]])}]})
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    same_author = [{**review, "reviewer": {**review["reviewer"], "id": "same-host",
                                           "execution_ref": author}}
                   for review in reviews]
    with pytest.raises(EvidenceRejected, match="author cannot be recorded as an independent"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": same_author,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=adapter)


def test_human_review_needs_a_verifiable_receipt(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    outcome = dispatch_with_synthetic_provider(
        project, adapter_context=_independent_adapter(store, document))
    task = outcome["task"]
    kinds = ("argument", "page_copy", "progression", "speech")
    subjects = [document["narrative"], document["content_plan"]] + \
        [e["page"] for e in document["pages"]]
    claimed = [_review(store, document, kind,
                       reviewer={"type": "human_internal", "id": "human",
                                 "execution_ref": None, "independence_confirmed": False,
                                 "assurance": "verified_user",
                                 "identity_receipt": {"adapter_id": "synthetic-adapter",
                                                      "event_id": f"evt-{kind}",
                                                      "issued_at": "2026-10-12T00:00:00Z",
                                                      "reviewer_id": "human-1",
                                                      "project_id": document["project_id"],
                                                      "subjects": subjects}})
               for kind in kinds]
    with pytest.raises(EnvelopeError, match="identity/execution receipt"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": claimed,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=None)


def test_incomplete_units_and_stale_subjects_are_refused(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    reviewer = {"type": "independent_host", "id": "model-b", "execution_ref": "exec-independent",
                "independence_confirmed": True, "identity_receipt": None,
                "assurance": "host_attested"}
    partial = [_review(store, document, "argument", reviewer=reviewer)]
    with pytest.raises(EnvelopeError, match="missing units"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": partial,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=adapter)
    wrong_deps = [_review(store, document, review["kind"], reviewer=reviewer,
                          deps=[{"kind": "content", "identity": "page:p1", "sha256": "0" * 64}])
                  for review in reviews]
    with pytest.raises(EnvelopeError, match="bind the current objects"):
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "review", "pages": [], "page_order": [],
                                              "artifact_specs": [], "reviews": wrong_deps,
                                              "usage_events": [], "notes": "x"},
                              adapter_context=adapter)


# ---------------------------------------------------------------------------
# Requirement variants


def test_host_self_needs_an_explicit_effective_downgrade_decision(tmp_path):
    quality = {"content_review_requirement": "host_self",
               "requirement_origin": "explicit_decision", "override_decision_ref": None}
    # The schema already refuses host_self without a bound decision.
    with pytest.raises(ModelError, match="override_decision_ref"):
        _project(tmp_path / "bare", quality=quality)
    # A decision bound in the profile makes it effective; an unrelated or
    # ineffective decision does not.
    project, store = _deck(tmp_path)
    document = store.load_document()
    decision = collaboration.record_decision(
        project, input={"topic": "policy", "disposition": "accepted",
                        "authority_mode": "direct_user",
                        "value": {"content_review_requirement": "host_self",
                                  "scope": "this request", "reason": "本次为合成演练"},
                        "scope": _scope(layers=["review"]),
                        "instruction_evidence": _instruction(store, "policy")},
        base_revision=store.load_document()["revision_id"], operation_id="op-policy")
    document = store.load_document()
    region = dict(document["collaboration"])
    region["quality_profile"] = {**region["quality_profile"], "content_review_requirement": "host_self",
                                 "requirement_origin": "explicit_decision",
                                 "override_decision_ref": decision["decision_ref"]}
    bumped = bump_revision(document, {"operation_id": "set-policy", "kind": "collaboration_update",
                                      "description": "record the downgrade", "read_set": []})
    bumped["collaboration"] = region
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="set-policy")
    store = Store(project)
    document = store.load_document()
    state = content_review.requirement_state(store, document)
    assert state["effective"] == "host_self" and not state["reasons"]
    # With host_self, the review is accepted without an independence receipt...
    outcome = dispatch_with_synthetic_provider(project)
    assert outcome["status"] == "review_dispatched"
    assert outcome["task"]["collaboration_binding"]["executor_type"] == "host"
    kinds = ("argument", "page_copy", "progression", "speech")
    reviews = [_review(store, document, kind,
                       reviewer={"type": "host_self", "id": "author-host",
                                 "execution_ref": None, "independence_confirmed": False,
                                 "identity_receipt": None, "assurance": "host_attested"})
               for kind in kinds]
    accept_with_synthetic_provider(project, task_id=outcome["task"]["task_id"],
                          operation_id=outcome["task"]["operation_id"],
                          produced_against=outcome["task"]["produced_against"],
                          result_payload={"kind": "review", "pages": [], "page_order": [],
                                          "artifact_specs": [], "reviews": reviews,
                                          "usage_events": [], "notes": "self review"},
                          adapter_context=None)
    store = Store(project)
    document = store.load_document()
    qualified = content_review.qualify_for_production(store, document)
    assert qualified["allowed"] is True
    # ...but the human professional-review policy for delivery is untouched.
    assert qualified["professional_review_required_for_delivery"] is False
    assert "never relaxes" in qualified["note"]


def test_fidelity_only_requires_a_confirmed_manuscript_mapping(tmp_path):
    quality = {"content_review_requirement": "fidelity_only",
               "requirement_origin": "confirmed_manuscript", "override_decision_ref": None}
    project, store = _deck(tmp_path, quality=quality)
    document = store.load_document()
    state = content_review.requirement_state(store, document)
    # A freshly argued bound plan is not a confirmed-manuscript mapping.
    assert state["effective"] == "independent_model_or_human"
    assert "fidelity_only_requires_a_confirmed_manuscript_mapping" in state["reasons"]
    assert content_review.required_units(store, document) == ["argument", "page_copy",
                                                             "progression", "speech"]


def test_blocking_findings_keep_production_blocked(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    task, reviews = _dispatch_and_reviews(store, document, adapter)
    reviewer = {"type": "independent_host", "id": "model-b", "execution_ref": "exec-independent",
                "independence_confirmed": True, "identity_receipt": None,
                "assurance": "host_attested"}
    kinds = ("argument", "page_copy", "progression", "speech")
    reviewed = []
    for kind in kinds:
        findings = []
        if kind == "argument":
            findings = [{"finding_id": "f1", "kind": "content", "impact": "must_fix",
                         "resolution": "open", "page_id": "p1", "element_refs": ["atom:p1:title"],
                         "message": "限定没有进入上屏正文", "expected": "上屏正文带限定",
                         "actual": "正文无该限定", "evidence": []}]
        reviewed.append(_review(store, document, kind, reviewer=reviewer, findings=findings))
    accept_with_synthetic_provider(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"],
                          result_payload={"kind": "review", "pages": [], "page_order": [],
                                          "artifact_specs": [], "reviews": reviewed,
                                          "usage_events": [], "notes": "x"},
                          adapter_context=adapter)
    store = Store(project)
    document = store.load_document()
    status = content_review.preproduction_status(store, document)
    assert status["status"] == "blocked"
    assert status["blocking_findings"][0]["message"] == "限定没有进入上屏正文"
    qualified = content_review.qualify_for_production(store, document, adapter_context=adapter)
    assert qualified["allowed"] is False and "open_blocking_findings" in qualified["reason_codes"]


def test_status_without_a_manuscript_is_explicit(tmp_path):
    project, store = _project(tmp_path)
    document = store.load_document()
    status = content_review.preproduction_status(store, document)
    assert status["status"] == "no_manuscript"
    assert status["next_action"] == "write_manuscript"
    qualified = content_review.qualify_for_production(store, document)
    assert qualified["allowed"] is False
