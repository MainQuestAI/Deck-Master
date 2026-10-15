"""R1/F2 native-channel reuse: explicit synthetic L1 SDK diagnostics only.

The sealed SyntheticController supplies artificial PNGs and controller events,
not actual native-tool evidence. Manuscript qualification uses an honestly
labelled host_self fidelity review through dispatch/claim/accept. No independent
reviewer, image model, design-quality verdict or real user approval is invented.
"""
import copy
import uuid

import pytest

from deck_master import (candidates, collaboration, content_plan, content_review, eligibility,
                         generation, models, service, tasks)
from deck_master.models import canonical_json_bytes
from deck_master.native_image_evidence import NativeImageRuntime, NativeObservationRejected
from test_rc3_design_recipes import input_value, synthetic_artifact
from test_rc3_design_requirements import _page as relational_page
from test_rc3_design_workflows import confirmed, dispatch
from test_rc3_notes_visual_inputs import _seed_imported_plan, enf
from test_rc3_restyle_workflows import adopted_initial, begin, accept, edit, import_reference


def _fidelity_review(path, store):
    """Submit real stored dependencies; no fabricated independent receipt."""
    outcome = content_review.dispatch_preproduction_review(path)
    assert outcome["requirement"] == "fidelity_only" and outcome["status"] == "review_dispatched"
    task = outcome["task"]
    service.task_start(path, task_id=task["task_id"], execution_ref="synthetic-fidelity-self-review",
                       capabilities=task.get("required_capabilities"))
    document = store.load_document()
    subjects = [document["content_plan"], *[entry["page"] for entry in document["pages"]]]
    deps = [{"kind": "content", "identity": "content_plan", "sha256": document["content_plan"]["sha256"]}]
    deps.extend({"kind": "content", "identity": "page:" + entry["page_id"],
                 "sha256": entry["page"]["sha256"]} for entry in document["pages"])
    evidence_ref = store.put_json_object({"synthetic": "L1 host_self fidelity protocol check only"})
    reviews = [{"schema_version": "deck_review.v2", "review_id": "f2-fidelity-" + kind,
        "kind": kind, "review_stage": "preproduction", "status": "pass", "subjects": subjects,
        "dependencies": deps, "reviewer": {"type": "host_self", "id": "synthetic-fidelity-self-review",
            "execution_ref": "synthetic-fidelity-self-review", "independence_confirmed": False,
            "identity_receipt": None, "evidence_ref": evidence_ref, "assurance": "host_attested"},
        "observations": ["Synthetic fidelity qualification for native-channel reuse diagnostics."],
        "findings": [], "created_at": "2026-10-15T00:00:00Z", "replaces": None}
        for kind in content_review.required_units(store, document)]
    for review in reviews:
        models.validate_review_semantics(review)
    result = service.accept_result(path, **{key: task[key] for key in (
        "task_id", "operation_id", "produced_against")}, result_payload={"kind": "review",
        "pages": [], "page_order": [], "artifact_specs": [], "reviews": reviews, "usage_events": [],
        "notes": "Explicit synthetic host_self fidelity fixture; no independent/native model receipt."})
    assert result["status"] == "accepted"
    assert content_review.qualify_for_production(store, store.load_document())["allowed"]


def _project(tmp_path):
    path, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(path, store)
    grant = enf._grant(path, store, actions=("style.propose", "design.update", "asset.import", "page.edit",
        "change.commit", "dispatch.host_task", "task.start", "task.cancel", "call.begin", "result.accept",
        "candidate.adopt", "allowance.allocate"), max_external_calls=2, max_candidate_count=2)
    # Author the complete relation fixture before qualification or freezing.
    edit(path, store, "p1", lambda page: page.update(relational_page("p1")))
    _fidelity_review(path, store)
    return path, store, grant


def _begun(tmp_path, *, intent="initial_design"):
    path, store, grant = _project(tmp_path)
    value = input_value(store.load_document(), intent=intent, ids=["p1"])
    if intent == "restyle":
        adopted_initial(path, store)
        reference, _, _ = import_reference(path, store)
        value = input_value(store.load_document(), intent="restyle", ids=["p1"])
        value["reference_refs"] = [reference]
    recipe = confirmed(path, store, **value)
    task = dispatch(path, store, recipe, ["p1"])[0]
    assert task["collaboration_binding"]["adoption_policy"] == "candidate_only"
    sent = begin(path, store, task)
    assert sent[2].provider_id == "synthetic-l1-controller"
    assert bool(task["stage_request"].get("target_reference_ref")) is (intent == "restyle")
    return path, store, grant, task, sent


def _issue(store, task, sent):
    _, attempt, controller, registry = sent
    return registry.image_context(store, store.load_document(), task_id=task["task_id"],
        attempt_id=attempt["attempt_id"], selector={"provider_id": controller.provider_id,
                                                   "event_id": task["task_id"]})


def _settle(store, task, sent, context, *, outcome="consumed"):
    _, attempt, controller, _ = sent
    report = {"source": "native_host_image.v1", "provider_id": controller.provider_id,
              "event_id": task["task_id"]}
    return tasks.call_settle(store, task_id=task["task_id"], allowance_id=attempt["allowance_id"],
        attempt_id=attempt["attempt_id"], outcome=outcome, report_bytes=canonical_json_bytes(report),
        adapter_context=context)


def _authorization_ref(task):
    return task["collaboration_binding"]["authorization_ref"]


def _assert_call_facts(store, task, sent, before_budget, *, outcome):
    current = store.load_document()
    actual = tasks._lookup_task(current, task["task_id"], store)
    shown = generation.show(store.project_root, attempt_id=sent[1]["attempt_id"])
    assert shown["call"]["state"] == outcome
    assert len(actual["call_allowances"]) == len(actual["generation_attempts"]) == 1
    assert actual["call_allowances"][0]["allowance_id"] == sent[1]["allowance_id"]
    assert actual["usage"] == {"source": "not_reported", "external_calls": None}
    budget = eligibility.authorization_budget(store, current, _authorization_ref(task))
    assert {key: budget[key] for key in ("ceiling", "used", "remaining")} == {
        key: before_budget[key] for key in ("ceiling", "used", "remaining")}
    assert budget["state"] == ("unknown" if outcome == "unknown" else
                               ("available" if budget["remaining"] else "exhausted"))
    ledger = eligibility.allowance_usage(store, current)["totals"]
    assert ledger["in_flight"] == 0 and ledger["reserved"] == 0
    assert ledger[outcome] >= 1 and sum(ledger.values()) == before_budget["used"]
    return shown


def _successful_reuse(tmp_path, change, phase, *, intent="initial_design"):
    path, store, _, task, sent = _begun(tmp_path, intent=intent)
    frozen, attempt, controller, registry = sent
    frozen_bytes = store.read_object_bytes(frozen["request_ref"])
    original = copy.deepcopy(store.load_document())
    budget = eligibility.authorization_budget(store, original, _authorization_ref(task))
    def mutate():
        if change == "notes":
            edit(path, store, "p1", lambda page: page.update(speaker_notes="仅新增讲述：人工确认后提交；正文与关系不变。"))
        elif change == "p2_design":
            edit(path, store, "p2", lambda page: page["visual_spec"].update(layout_hint="仅P2上下排列"))
        else:
            edit(path, store, "p2", lambda page: page["customer_visible"].update(title="仅P2正文改变"))
    with NativeImageRuntime(registry).bound():
        if phase == "before_context":
            mutate()
        context = _issue(store, task, sent)
        if phase == "after_context":
            mutate()
        after_edit = copy.deepcopy(store.load_document())
        assert tasks.task_inputs_current(store, after_edit, tasks._lookup_task(after_edit, task["task_id"], store))
        result = _settle(store, task, sent, context)
    assert result["native_observation_status"] == "accepted"
    shown = _assert_call_facts(store, task, sent, budget, outcome="consumed")
    observation = shown["observations"][-1]
    assert observation["observer"] == "tool_observed" and observation["collector"] == "native-host-image.v1"
    assert observation["source"]["fee"] == "not_reported"
    assert observation["submitted"]["prompt"] == frozen["input"]["prompt"]
    assert observation["submitted"]["references"] == frozen["input"]["references"]
    assert store.read_object_bytes(shown["attempt"]["output_refs"][0]) == controller.png
    receipt = store.read_object_json(observation["source"]["receipt_ref"])
    assert receipt["claims"]["binding"] == controller.claims["binding"]
    assert receipt["claims"]["binding"]["generation_request_ref"] == frozen["request_ref"]
    accepted = accept(path, store, task, sent)
    assert accepted["status"] == "candidate_ready" and accepted["current_artifacts_changed"] is False
    current = store.load_document()
    assert current["pages"] == after_edit["pages"], "candidate reception must preserve current Page/notes/other-page edits"
    assert current.get("candidate_adoptions") == original.get("candidate_adoptions")
    assert len(candidates.listing(path)["candidates"]) == len(candidates.listing(path,
        revision=original["revision_id"])["candidates"]) + 1
    candidate = candidates.show(path, candidate_id=accepted["candidate_ids"][0])["candidate"]
    artifact = store.read_object_json(candidate["result_ref"])
    assert artifact["provenance"]["generated_from_page"] == frozen["input"]["page"]["page_ref"]
    assert store.read_object_bytes(frozen["request_ref"]) == frozen_bytes
    assert generation.show(path, request_id=frozen["request_id"])["request"]["input"] == frozen["input"]
    _assert_call_facts(store, task, sent, budget, outcome="consumed")


@pytest.mark.parametrize("intent", ["initial_design", "restyle"])
@pytest.mark.parametrize("phase", ["before_context", "after_context"])
def test_notes_only_edit_keeps_sealed_native_completion_and_candidate(tmp_path, intent, phase):
    _successful_reuse(tmp_path, "notes", phase, intent=intent)


@pytest.mark.parametrize("change", ["p2_design", "p2_body"])
@pytest.mark.parametrize("phase", ["before_context", "after_context"])
def test_unrelated_page_edit_keeps_p1_native_completion_and_candidate(tmp_path, change, phase):
    _successful_reuse(tmp_path, change, phase)


def _semantic_or_control_change(path, store, grant, change):
    if change == "body":
        edit(path, store, "p1", lambda page: page["customer_visible"].update(title="P1业务正文改变"))
    elif change == "arrow":
        def reverse(page):
            edge = page["visual_spec"]["edges"][0]
            edge["from"], edge["to"] = edge["to"], edge["from"]
        edit(path, store, "p1", reverse)
    elif change in ("pause", "revoke"):
        doc = store.load_document()
        if change == "pause":
            collaboration.pause_request(path, reason="Synthetic explicit pause after begin",
                base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
        else:
            collaboration.revoke_authorization(path, authorization_id=grant["authorization_id"],
                reason="Synthetic explicit revoke after begin", base_revision=doc["revision_id"],
                operation_id=str(uuid.uuid4()))
    else:
        doc = store.load_document()
        updated = copy.deepcopy(doc)
        if change == "role":
            plan = store.read_object_json(doc["content_plan"])
            value = copy.deepcopy(plan["input"])
            value["page_roles"][0]["intended_takeaway"] = "P1业务职责和结论改变"
            updated["content_plan"] = content_plan.build_v2_plan(
                store, doc, {"task_id": None, "dispatch_revision": doc["revision_id"]}, value,
                doc["pages"], narrative_ref=None, mode="imported_mapping",
                imported_manuscript=plan["imported_manuscript"])
        else:
            updated["pages"][0]["blueprint"] = synthetic_artifact(store, role="blueprint", page_id="p1")
            assert updated["pages"][0]["blueprint"] != doc["pages"][0]["blueprint"]
        operation_id = str(uuid.uuid4())
        updated = models.bump_revision(updated, {"operation_id": operation_id, "kind": "content_update",
            "description": "Explicit synthetic concurrent " + change + " replacement", "read_set": []})
        store.commit_change(base_revision=doc["revision_id"], document=updated, operation_id=operation_id)


@pytest.mark.parametrize("change", ["body", "role", "arrow", "target", "pause", "revoke"])
@pytest.mark.parametrize("phase", ["before_context", "after_context"])
@pytest.mark.parametrize("outcome", ["consumed", "unknown"])
def test_changed_selected_semantics_or_control_rejects_late_result_without_erasing_call(tmp_path, change, phase, outcome):
    path, store, grant, task, sent = _begun(tmp_path, intent="restyle" if change == "target" else "initial_design")
    frozen, attempt, _, registry = sent
    frozen_bytes = store.read_object_bytes(frozen["request_ref"])
    begun = store.load_document()
    original_candidate_refs = copy.deepcopy(begun.get("candidates", []))
    original_candidate_bytes = {ref["path"]: store.read_object_bytes(ref) for ref in original_candidate_refs}
    budget = eligibility.authorization_budget(store, begun, _authorization_ref(task))
    with NativeImageRuntime(registry).bound():
        context = _issue(store, task, sent) if phase == "after_context" else None
        _semantic_or_control_change(path, store, grant, change)
        if phase == "before_context":
            with pytest.raises(NativeObservationRejected):
                _issue(store, task, sent)
        settled = _settle(store, task, sent, context, outcome=outcome)
    assert settled["native_observation_status"] == "rejected"
    shown = _assert_call_facts(store, task, sent, budget, outcome=outcome)
    observation = shown["observations"][-1]
    assert observation["observer"] == "host_reported"
    assert observation["reported"]["native_observation_rejected"]
    assert not shown["attempt"]["output_refs"]
    proof_ref = observation["reported"]["unusable_receipt_ref"]
    if phase == "after_context":
        assert store.read_object_json(proof_ref)["claims"]["binding"]["generation_request_ref"] == frozen["request_ref"]
    else:
        assert proof_ref is None
    before_reject = store.read_current()
    current = copy.deepcopy(store.load_document())
    current_task = tasks._lookup_task(current, task["task_id"], store)
    with pytest.raises((eligibility.EligibilityBlocked, tasks.TaskConflict, generation.GenerationError)):
        accept(path, store, task, sent)
    if current_task["status"] not in ("superseded", "cancelled"):
        assert store.read_current() == before_reject
    # A terminal task may append its first late-settlement receipt. That fact
    # cannot adopt output, change controls or create another call/candidate.
    assert store.load_document()["pages"] == current["pages"]
    assert store.load_document()["outputs"] == current["outputs"]
    assert store.load_document()["collaboration"] == current["collaboration"]
    assert store.load_document().get("candidates", []) == original_candidate_refs
    assert store.load_document().get("candidate_adoptions") == current.get("candidate_adoptions")
    assert original_candidate_bytes == {ref["path"]: store.read_object_bytes(ref) for ref in original_candidate_refs}
    settled_pointer = store.read_current()
    with pytest.raises((eligibility.EligibilityBlocked, tasks.TaskConflict, generation.GenerationError)):
        accept(path, store, task, sent)
    assert store.read_current() == settled_pointer, "same late payload must not duplicate settlement facts"
    assert store.read_object_bytes(frozen["request_ref"]) == frozen_bytes
    _assert_call_facts(store, task, sent, budget, outcome=outcome)
