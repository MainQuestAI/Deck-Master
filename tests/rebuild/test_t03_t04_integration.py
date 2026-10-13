"""T03 x T04 joint gate: the seams the two cards share.

The two cards were developed and reviewed independently; this file pins the
cross-card contracts the joint gate must keep:

1. One binding digest, one implementation — the dispatch side writes it and
   the gate recomputes it (a slice-order drift between the two historical
   implementations was the joint gate's first find).
2. Every production dispatch in an enforced project carries a binding, so the
   gate's unconditional backstop has nothing to refuse (the change flow).
3. A phased compose.v2 task's binding recomputes as valid at the gate, and its
   result is accepted end-to-end with the gate active.
"""
import uuid

import pytest

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _grant, _page, _project, _scope, _start)
from test_compose_v2_phases import _deck_with_pages, _page as _phase_page  # noqa: E402

from deck_master import changes, collaboration_binding, content_production, eligibility, service
from deck_master.store import Store


def test_one_binding_digest_shared_by_dispatch_and_gate():
    """The gate recomputes the exact bytes the dispatcher wrote.

    Slice-key order (policy < task_fact) deliberately differs from digest
    order here ("zz" sorts after "aa"): sorting the digest values instead of
    the slice keys produced a different digest, and the joint gate caught it.
    """
    scope = {"subject": "pages", "page_ids": ["p2", "p1"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["svg", "page_copy"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "working"}
    basis = [{"kind": "policy", "identity": "document", "projection": "value",
              "ref": None, "sha256": "zz"},
             {"kind": "task_fact", "identity": "audience", "projection": "value",
              "ref": None, "sha256": "aa"}]
    dispatch_side = collaboration_binding.eligibility_digest(
        phase="page_copy", write_scope=scope, basis=basis)
    gate_side = eligibility.binding_eligibility_digest("page_copy", scope, basis)
    assert dispatch_side == gate_side
    # Order of the basis list never changes the digest.
    assert eligibility.binding_eligibility_digest(
        "page_copy", scope, list(reversed(basis))) == gate_side


def test_change_dispatch_on_an_enforced_project_is_bound_and_accepted(tmp_path):
    """The edit flow (AC-R03) stays usable in a managed project: commit
    dispatches a bound task, and the result is adopted under the same gate."""
    project, store = _project(tmp_path)
    _start(project, store, intent="edit",
           scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    _grant(project, store, actions=("change.commit",), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    value = {"schema_version": "change_intent.v1", "project_id": document["project_id"],
             "base_revision": document["revision_id"], "intent": "clarify",
             "instruction": "Clarify the selected page.", "annotation_refs": [],
             "max_calls": 0,
             "targets": [{"page_id": "p1", "page_ref": entry["page"], "layer": "content",
                          "artifact_ref": entry["page"]}]}
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan["plan_id"],
                            base_revision=value["base_revision"],
                            operation_id=str(uuid.uuid4()))
    task_id = result["operation_result"]["task_ids"][0]
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref)["task_id"] == task_id)
    binding = task["collaboration_binding"]
    assert binding["phase"] == "production"
    assert binding["write_scope"]["page_ids"] == ["p1"]
    assert eligibility.task_binding_state(store, store.load_document(), task)["status"] == "valid"
    # The host claims the task with the declared protocol, then answers; the
    # gate recomputes the same judgement and adopts.
    service.task_start(store.project_root, task_id=task_id, execution_ref="joint-host",
                       supported_protocols=["changes.v1", "generation.v1"],
                       capabilities=["change_plan", "generation_request_freeze",
                                     "attempt_binding", "native_tool_observation"])
    page = store.read_object_json(entry["page"])
    page["customer_visible"]["title"] = "Clear title"
    service.accept_result(store.project_root, task_id=task_id, operation_id=task["operation_id"],
                          produced_against=task["produced_against"],
                          result_payload={"kind": "repair", "pages": [page]})
    updated = next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")
    assert store.read_object_json(updated["page"])["customer_visible"]["title"] == "Clear title"


def test_change_commit_without_authorization_is_refused_before_dispatch(tmp_path):
    """The same boundary refuses the edit dispatch when no grant covers it."""
    project, store = _project(tmp_path)
    _start(project, store, intent="edit",
           scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    value = {"schema_version": "change_intent.v1", "project_id": document["project_id"],
             "base_revision": document["revision_id"], "intent": "clarify",
             "instruction": "Clarify the selected page.", "annotation_refs": [],
             "max_calls": 0,
             "targets": [{"page_id": "p1", "page_ref": entry["page"], "layer": "content",
                          "artifact_ref": entry["page"]}]}
    plan = changes.plan(store.project_root, input=value)
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        changes.commit(store.project_root, plan_id=plan["plan_id"],
                       base_revision=value["base_revision"],
                       operation_id=str(uuid.uuid4()))
    assert "authority_insufficient" in excinfo.value.payload()["error"]["reason_codes"]
    tasks = [store.read_object_json(ref) for ref in store.load_document()["tasks"]]
    assert not [t for t in tasks if t.get("kind") in ("repair", "reconstruct", "blueprint")]


def test_phased_result_is_accepted_under_the_gate(tmp_path):
    """End-to-end seam: a phased compose.v2 task written by T03 carries a
    binding whose digest the T04 gate recomputes as valid at acceptance."""
    project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    task = content_production.open_phase_task(
        store, store.load_document(), operation_id="joint-speech", phase="speech",
        page_ids=["p1"])
    assert eligibility.task_binding_state(store, store.load_document(), task)["status"] == "valid"
    notes = "先讲记录未知。"
    payload = {"updates": [{"page_id": "p1",
                            "page_ref": store.load_document()["pages"][0]["page"],
                            "speaker_notes": notes,
                            "speech_segments": [
                                {"segment_id": "s1", "start_codepoint": 0,
                                 "end_codepoint": len(notes), "narrative_node_ids": ["n1"],
                                 "kind": "cue", "estimated_seconds": 5}]}]}
    envelope = {"schema_version": "compose_result.v2", "kind": "compose", "variant": "speech",
                "task_id": task["task_id"], "operation_id": task["operation_id"],
                "produced_against": task["produced_against"],
                "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                "payload": payload, "usage_events": []}
    out = service.accept_result(project, task_id=task["task_id"],
                                operation_id=task["operation_id"],
                                produced_against=task["produced_against"],
                                result_payload=envelope)
    assert out["status"] == "accepted"
    page = store.read_object_json(store.load_document()["pages"][0]["page"])
    assert page["speaker_notes"] == notes
