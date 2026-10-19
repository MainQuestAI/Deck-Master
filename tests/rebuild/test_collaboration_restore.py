"""T02 slice 6: restore preserves the current collaboration control region,
call facts, stop policy and minimum writer while restoring content and the
narrative it governed (MIGRATION §4, AC-C02/C04)."""
import hashlib
import uuid

from rc3_fixtures import historical_snapshot, submit_host_fixture

from deck_master import collaboration, collaboration_migration, content_production, restoration
from deck_master.models import bump_revision
from deck_master.store import Store


def _page(pid: str, text: str) -> dict:
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": f"标题{pid}", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": text}]},
            "visual_spec": {"intent": "synthetic", "reference_mode": "new_design"}}


def _scope() -> dict:
    return {"subject": "pages", "page_ids": ["p1", "p2"], "page_manifest_ref": None,
            "external_artifact_ref": None,
            "layers": ["narrative", "plan", "page_copy", "speech"],
            "allow_page_membership_change": False, "allow_page_order_change": False,
            "purpose": "exploratory"}


def _declared(store) -> dict:
    return {"kind": "host_attested_instruction",
            "source_ref": store.put_json_object({"fixture": "source"}),
            "source_locator": "chat:msg-1", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _narrative_object(project_id) -> dict:
    return {
        "schema_version": "narrative.v1", "narrative_id": "nar-1", "version": 1,
        "project_id": project_id, "origin": "host_composed", "maturity": "argument",
        "input_basis": [],
        "communication_job": {"mode": "train", "audience_fact_key": "task.audience",
                              "audience_question": "如何记录未知", "desired_outcome": "能填写",
                              "observable_success": "答对", "use_mode": "live",
                              "primary_use": "live"},
        "central_node_id": "n1",
        "nodes": [{"node_id": "n1", "role": "claim", "statement": "可接手 = 已知未知下一步",
                   "authority": "instruction",
                   "source_links": [],
                   "qualification_node_ids": [], "unresolved_issue_ids": []}],
        "edges": [], "issues": [], "alternatives": [], "previous_ref": None,
    }


def _build(tmp_path):
    project = historical_snapshot(tmp_path,
        scenario="Fixed pre-migration restore facts: old content, call settlement and narrative",
        pages=[_page("p1", "原始句。"), _page("p2", "第二页。")])["project"]
    store = Store(project)
    revisions = {"content": store.load_document()["revision_id"]}
    # Legacy facts: a completed task with a consumed call and a stop policy.
    document = store.load_document()
    task = {"schema_version": "deck_task.v1", "task_id": "t-consumed", "operation_id": "op-1",
            "kind": "compose", "status": "completed", "scope_pages": ["p1"], "instruction": "x",
            "inputs": [document["pages"][0]["page"]], "dependencies": [],
            "dispatch_revision": document["revision_id"],
            "produced_against": hashlib.sha256(b"x").hexdigest(), "result_refs": [], "error": None,
            "execution_ref": None, "created_at": "2026-10-12T08:00:00Z",
            "updated_at": "2026-10-12T08:00:00Z", "cost_class": "host_reasoning", "usage": {},
            "call_allowances": [{"allowance_id": "a1", "state": "consumed",
                                 "cost_class": "host_reasoning", "slot": 1}]}
    task_ref = store.put_json_object(task)
    bumped = bump_revision(document, {"operation_id": "facts", "kind": "task_update",
                                      "description": "facts", "read_set": []})
    bumped["tasks"] = [task_ref]
    bumped["policy"] = {**bumped["policy"], "user_stop": True}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="facts")
    # Migrate through the actual service before any current-control write.
    described = collaboration_migration.describe(project)
    collaboration_migration.apply(project, base_revision=store.current_revision_id(),
        plan_digest=described["plan_digest"], operation_id="op-migrate")
    collaboration.start_request(project, input={"intent": "full_deck",
                                                "content_intent": None,
                                                "instruction_evidence": _declared(store),
                                                "scope": _scope()},
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-start")
    grant = collaboration.grant(project, input={"mode": "delegate", "actions": ["task.start"],
                                                "scope": _scope(), "delegated_topics": ["direction"],
                                                "max_external_calls": 0,
                                                "instruction_evidence": _declared(store)},
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-grant")
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="范围撤回",
                                       base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    # Establish the second target through an actual capability-aware L1 Host
    # proposal, a subject-bound direction decision and the canonical adoption.
    task = content_production.open_phase_task(store, store.load_document(),
        operation_id="L1-narrative-result", phase="argument", page_ids=["p1", "p2"],
        instruction="L1 synthetic Narrative for the explicit restore preservation test")
    accepted = submit_host_fixture(project, task_id=task["task_id"],
        execution_ref="L1-synthetic-restore-author",
        host_declaration={"supported_protocols": [task["protocol_version"]],
                          "capabilities": task["required_capabilities"]},
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
            "variant": "narrative", "task_id": task["task_id"],
            "operation_id": task["operation_id"], "produced_against": task["produced_against"],
            "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
            "payload": {"narrative": _narrative_object(store.load_document()["project_id"])},
            "usage_events": []})
    narrative_ref = accepted["narrative_ref"]
    decision = collaboration.record_decision(project, input={"topic": "direction",
        "disposition": "accepted", "authority_mode": "direct_user", "value": "Use this synthetic direction",
        "scope": {**_scope(), "layers": ["narrative", "plan"]},
        "instruction_evidence": _declared(store), "subject_refs": [{"artifact_kind": "narrative",
            "artifact_ref": narrative_ref, "projection": "direction"}]},
        base_revision=store.current_revision_id(), operation_id="op-restore-direction")
    content_production.adopt_proposal(project, input={"proposal_ref": narrative_ref,
        "decision_ref": decision["decision_ref"], "write_scope": {**_scope(), "layers": ["narrative"]}},
        base_revision=store.current_revision_id(), operation_id="op-restore-adopt")
    revisions["narrative"] = store.current_revision_id()
    # The scoped public edit precedes the pause. Restore may then recover old
    # facts while leaving the current paused request and revoked grant intact.
    from deck_master.editing import edit_page
    store = Store(project)
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    edit_page(project, page=_page("p1", "改过的句子。"), base_revision=document["revision_id"],
              page_hash=entry["page"]["sha256"], operation_id="op-edit")
    collaboration.pause_request(project, reason="等确认",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    return project, Store(project), revisions


def _restore_to(project, store, revision):
    plan = restoration.plan(project, revision_id=revision,
                            base_revision=store.load_document()["revision_id"])
    return restoration.commit(project, plan_id=plan["plan_id"],
                              base_revision=store.load_document()["revision_id"],
                              operation_id=str(uuid.uuid4()))


def test_restore_to_pre_migration_snapshot_preserves_current_control(tmp_path):
    project, store, revisions = _build(tmp_path)
    control = store.load_document()
    outcome = _restore_to(project, store, revisions["content"])
    assert outcome["committed_revision_id"]
    after = store.load_document()
    # Content is restored…
    p1 = next(e for e in after["pages"] if e["page_id"] == "p1")
    restored = store.read_object_json(p1["page"])
    assert restored["customer_visible"]["body_blocks"][0]["text"] == "原始句。"
    # …while every control fact stays exactly as it was.
    assert after["collaboration"] == control["collaboration"]
    assert after["collaboration"]["request"]["paused"] is True
    assert after["collaboration"]["request"]["request_id"] == \
        control["collaboration"]["request"]["request_id"]
    assert after["policy"]["user_stop"] is True
    assert after["compatibility"]["minimum_writer"] == control["compatibility"]["minimum_writer"] == "rc4-content.v1"
    task = store.read_object_json(after["tasks"][0])
    assert task["status"] == "completed"
    assert task["call_allowances"][0]["state"] == "consumed"
    # The pre-narrative snapshot restores without a narrative pointer.
    assert after.get("narrative") is None


def test_restore_keeps_the_narrative_of_the_target_snapshot(tmp_path):
    project, store, revisions = _build(tmp_path)
    _restore_to(project, store, revisions["narrative"])
    after = store.load_document()
    assert after.get("narrative") is not None
    narrative = store.read_object_json(after["narrative"])
    assert narrative["narrative_id"] == "nar-1"
    # Control facts are still the current ones, not the snapshot's.
    assert after["collaboration"]["request"]["paused"] is True
