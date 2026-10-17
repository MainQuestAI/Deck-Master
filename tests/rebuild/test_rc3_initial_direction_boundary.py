"""S06 public, neutral L1 engineering flows; no actual user/native quality claim."""
from copy import deepcopy
import uuid

import pytest

from deck_master import collaboration, content_production, models, service
from deck_master.store import Store
from deck_master.tasks import EnvelopeError
from rc3_fixtures import evidence_for, source_snapshot
from test_compose_v2_phases import (_argument_narrative, _framing_narrative, _plan_input,
                                  _scope, _source_link, _submit)


def identifier():
    return str(uuid.uuid4())


def claim(project, task):
    service.task_start(project, task_id=task["task_id"], execution_ref="ENGINEERING_ONLY_S06",
                       supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
    return task


def next_task(project, phase):
    result = service.continue_project(project)
    task = next(t for t in result["pending_tasks"] if t.get("collaboration_binding", {}).get("phase") == phase)
    return claim(project, task)


def public_start(tmp_path, *, presentation_mode="live"):
    source = tmp_path / "source.txt"
    source.write_text("ENGINEERING_ONLY neutral source: distinguish a circle and square.\n")
    project = tmp_path / "project"
    service.create(project, brief="ENGINEERING_ONLY neutral direction boundary", sources=[source],
        audience="ENGINEERING_ONLY fixture audience", presentation_mode=presentation_mode,
        request_input={"intent": "content_only", "content_intent": "content_full", "scope": _scope()})
    store = Store(project)
    task = next_task(project, "framing")
    result = _submit(project, task, {"narrative": _framing_narrative(store.load_document()["project_id"])}, "framing")
    assert result["adopted"] is False and store.load_document().get("narrative") is None
    return project, store, result["proposal_refs"][0]


def source_revision(project, store, tmp_path):
    supplement = tmp_path / ("supplement-" + identifier() + ".txt")
    supplement.write_text("ENGINEERING_ONLY additional neutral source; no direction decision.\n")
    service.inputs_update(project, patch={"reason": "ENGINEERING_ONLY source-only update without direction decision",
        "source_changes": {"add": [{"path": str(supplement)}]}},
        base_revision=store.current_revision_id(), operation_id=identifier())
    task = next(store.read_object_json(ref) for ref in reversed(store.load_document()["tasks"])
                if store.read_object_json(ref).get("intent") == "input_revision"
                and store.read_object_json(ref)["status"] == "awaiting_host")
    return claim(project, task)


def revision_payload(store, task, *, maturity="argument"):
    doc = store.load_document()
    narrative = (_argument_narrative if maturity == "argument" else _framing_narrative)(doc["project_id"])
    if doc.get("narrative"):
        current = store.read_object_json(doc["narrative"])
        narrative.update(version=current["version"] + 1, previous_ref=doc["narrative"])
    return {"changed_layers": ["narrative"], "proposals": [{"layer": "narrative", "ref": store.put_json_object(narrative)}],
        "diff": {"input_digest": task["input_digest"], "summary": "ENGINEERING_ONLY substantively reconcile the neutral audience framing.",
                 "changed_page_ids": []}}


@pytest.mark.parametrize("current", ["absent", "framing"])
@pytest.mark.parametrize("presentation_mode", ["live", "read_alone"])
@pytest.mark.parametrize("with_plan", [False, True])
def test_input_revision_cannot_adopt_initial_argument_atomically(tmp_path, current, presentation_mode, with_plan):
    project, store, original_proposal = public_start(tmp_path, presentation_mode=presentation_mode)
    task = source_revision(project, store, tmp_path)
    if current == "framing":
        _submit(project, task, revision_payload(store, task, maturity="framing"), "input_revision")
        task = source_revision(project, store, tmp_path)
    doc = store.load_document()
    assert doc["collaboration"]["decisions"] == doc["collaboration"]["authorizations"] == []
    assert task["collaboration_binding"]["adoption_policy"] == "within_scope"
    payload = revision_payload(store, task)
    if with_plan:
        plan = _plan_input(doc, ["p1"], source_links=[_source_link(store, doc)])
        payload["changed_layers"].append("plan")
        payload["proposals"].append({"layer": "plan", "ref": store.put_json_object(plan)})
    before = source_snapshot(project)
    with pytest.raises(EnvelopeError, match="initial argument.*direction"):
        _submit(project, task, payload, "input_revision")
    assert source_snapshot(project) == before and store.load_document() == doc
    assert store.read_object_json(original_proposal)["maturity"] == "framing"
    assert store.read_object_json(payload["proposals"][0]["ref"])["maturity"] == "argument"
    continued = service.continue_project(project)
    assert all(t.get("intent") == "input_revision" or t.get("collaboration_binding", {}).get("phase") != "page_copy"
               for t in continued["pending_tasks"])


def ordinary_argument_after_reconciliation(project, store):
    # The input revision's framing is current, but the normal workflow still
    # requires a current framing Task and an ordinary argument proposal.
    task = next_task(project, "framing")
    _submit(project, task, {"narrative": _framing_narrative(store.load_document()["project_id"])}, "framing")
    task = next_task(project, "argument")
    current = store.load_document().get("narrative")
    result = _submit(project, task, {"narrative": _argument_narrative(store.load_document()["project_id"])}, "narrative")
    assert result["adopted"] is False and store.load_document().get("narrative") == current
    assert content_production.content_phase_status(store, store.load_document())["action"] == "await_decision"
    return result["proposal_refs"][0]


def direction(project, store, proposal, *, scope=None):
    return collaboration.record_decision(project, input={"topic": "direction", "disposition": "accepted",
        "authority_mode": "direct_user", "value": {"selected": "ENGINEERING_ONLY neutral L1 direction fixture"},
        "scope": scope or _scope(layers=["narrative"]),
        "instruction_evidence": evidence_for(project, text="ENGINEERING_ONLY explicit synthetic decision; not human evidence.",
                                             locator="ENGINEERING_ONLY:S06"),
        "subject_refs": [{"artifact_kind": "narrative", "artifact_ref": proposal, "projection": "direction"}]},
        base_revision=store.current_revision_id(), operation_id=identifier())


def adopt(project, store, proposal, decision, **over):
    return content_production.adopt_proposal(project, input={"proposal_ref": proposal,
        "decision_ref": decision["decision_ref"], "write_scope": _scope(layers=["narrative"])},
        base_revision=over.get("base_revision", store.current_revision_id()), operation_id=over.get("operation_id", identifier()))


def reconciled_framing(tmp_path):
    project, store, original = public_start(tmp_path)
    task = source_revision(project, store, tmp_path)
    rejected = revision_payload(store, task)
    before = source_snapshot(project)
    with pytest.raises(EnvelopeError, match="initial argument.*direction"):
        _submit(project, task, rejected, "input_revision")
    assert source_snapshot(project) == before
    payload = revision_payload(store, task, maturity="framing")
    result = _submit(project, task, payload, "input_revision")
    assert result["adopted"] is True and store.load_document()["narrative"] == payload["proposals"][0]["ref"]
    return project, store, task, result


def test_framing_then_ordinary_proposal_decision_adopt_remains_current_and_replayable(tmp_path):
    project, store, task, result = reconciled_framing(tmp_path)
    proposal = ordinary_argument_after_reconciliation(project, store)
    decision = direction(project, store, proposal)
    opid = identifier()
    base = store.current_revision_id()
    adopted = adopt(project, store, proposal, decision, base_revision=base, operation_id=opid)
    assert store.load_document()["narrative"] == proposal
    assert content_production.content_phase_status(store, store.load_document())["phase"] == "page_copy"
    assert adopt(project, store, proposal, decision, base_revision=base, operation_id=opid)["revision_id"] == adopted["revision_id"]
    # An already-adopted argument can still reconcile a source change atomically.
    task = source_revision(project, store, tmp_path)
    payload = revision_payload(store, task)
    out = _submit(project, task, payload, "input_revision")
    assert out["adopted"] is True and store.load_document()["narrative"] == payload["proposals"][0]["ref"]
    assert _submit(project, task, payload, "input_revision")["status"] == "already_applied"


def test_empty_layers_is_atomic_and_same_revision_task_can_reconcile_framing(tmp_path):
    project, store, _ = public_start(tmp_path)
    task = source_revision(project, store, tmp_path)
    empty = {"changed_layers": [], "proposals": [], "diff": {"input_digest": task["input_digest"],
             "summary": "ENGINEERING_ONLY empty diff is not reconciliation", "changed_page_ids": []}}
    before = source_snapshot(project)
    with pytest.raises(EnvelopeError, match="non-empty"):
        _submit(project, task, empty, "input_revision")
    assert source_snapshot(project) == before
    assert _submit(project, task, revision_payload(store, task, maturity="framing"), "input_revision")["adopted"] is True


@pytest.mark.parametrize("fault", ["wrong-proposal", "insufficient-scope", "stale-base", "other-request"])
def test_ordinary_adoption_keeps_exact_proposal_scope_request_and_cas_guards(tmp_path, fault):
    project, store, _, _ = reconciled_framing(tmp_path)
    proposal = ordinary_argument_after_reconciliation(project, store)
    before_decision = store.current_revision_id()
    decision = direction(project, store, proposal, scope=_scope(layers=["plan"]) if fault == "insufficient-scope" else None)
    if fault == "wrong-proposal":
        other = deepcopy(store.read_object_json(proposal))
        other["nodes"][0]["statement"] += " ENGINEERING_ONLY changed alternative"
        proposal = store.put_json_object(other)
    if fault == "other-request":
        request_id = store.load_document()["collaboration"]["request"]["request_id"]
        collaboration.start_request(project, input={"intent": "content_only", "content_intent": "plan_only",
            "scope": _scope(layers=["plan"]), "replace_request_id": request_id,
            "instruction_evidence": evidence_for(project, text="ENGINEERING_ONLY replacement plan-only request", locator="ENGINEERING_ONLY:S06:replace")},
            base_revision=store.current_revision_id(), operation_id=identifier())
    before = source_snapshot(project)
    with pytest.raises((models.ModelError, RuntimeError)):
        adopt(project, store, proposal, decision, **({"base_revision": before_decision} if fault == "stale-base" else {}))
    assert source_snapshot(project) == before
