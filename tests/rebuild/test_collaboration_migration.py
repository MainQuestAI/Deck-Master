"""T02 slice 5: migration describe/apply (MIGRATION §3, AC-C04) — read-only
describe with a plan digest, single-transaction apply that preserves every
immutable fact, idempotent replays, legacy tasks retired to settle-only and
no fabricated history approvals."""
import hashlib

import pytest

from rc3_fixtures import historical_snapshot

from deck_master import collaboration, collaboration_migration, service, tasks as tasks_mod
from deck_master.models import ModelError, bump_revision
from deck_master.store import ConflictError, Store


def _page(pid: str) -> dict:
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": f"标题{pid}", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": "正文。"}]},
            "visual_spec": {"intent": "synthetic", "reference_mode": "new_design"}}


def _legacy_project(tmp_path):
    """A pre-collaboration project: no writer metadata, one runnable task with
    an unknown call, legacy decision strings, a default presentation mode."""
    fixture = historical_snapshot(tmp_path, scenario="pre-collaboration fixed original with unknown call",
        pages=[_page("p1"), _page("p2")], task={"brief": "legacy deck"})
    project = fixture["project"]
    store = Store(project)
    document = store.load_document()
    task = tasks_mod.new_task(
        task_id="legacy-task-1", operation_id="legacy-op-1", kind="compose",
        scope_pages=["p1"], instruction="legacy", inputs=[document["pages"][0]["page"]],
        dependencies=[], dispatch_revision=document["revision_id"],
        produced_against=hashlib.sha256(b"legacy").hexdigest())
    # This fixture represents a pre-RC4 Task, not a new producer invocation.
    task.pop("method_manifest", None)
    task.pop("content_validation_policy", None)
    from deck_master import method_resources
    historical_methods = method_resources._read_ids(method_resources.rc3_method_ids_for(task["kind"]))
    task["method_release"] = method_resources.method_release(historical_methods)
    task["call_allowances"] = [{"allowance_id": "a1", "state": "unknown",
                                "cost_class": "host_reasoning", "slot": 1}]
    task_ref = store.put_json_object(task)
    bumped = bump_revision(document, {"operation_id": "legacy-setup", "kind": "task_update",
                                      "description": "legacy facts", "read_set": []})
    bumped["tasks"] = [task_ref]
    bumped["task"]["existing_decisions"] = ["默认按现场讲解准备", "沿用旧模板"]
    bumped["task"]["presentation_mode_source"] = "default"
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="legacy-setup")
    return project, Store(project)


def test_describe_is_read_only_and_lists_pending_reconciliation(tmp_path):
    project, store = _legacy_project(tmp_path)
    before_revision = store.load_document()["revision_id"]
    current_before = (store.deck_root / "current.json").read_bytes()
    description = collaboration_migration.describe(project)
    assert description["plan"]["needs_migration"] is True
    plan = description["plan"]
    assert plan["minimum_writer"] is None and plan["target_minimum_writer"] == "rc3-entry.v1"
    assert plan["counts"] == {"pages": 2, "sources": 0, "reviews": 0, "tasks": 1, "runnable_tasks": 1}
    assert plan["tasks_to_supersede"] == ["legacy-task-1"]
    assert plan["unknown_calls"] == 1
    assert [item["disposition"] for item in plan["pending_decisions"]] == [
        "imported_unknown", "imported_unknown", "default_not_a_user_choice"]
    assert store.load_document()["revision_id"] == before_revision
    assert (store.deck_root / "current.json").read_bytes() == current_before


def test_apply_preserves_facts_and_retires_legacy_tasks(tmp_path):
    project, store = _legacy_project(tmp_path)
    before = store.load_document()
    page_refs = [entry["page"] for entry in before["pages"]]
    description = collaboration_migration.describe(project)
    outcome = collaboration_migration.apply(
        project, base_revision=before["revision_id"],
        plan_digest=description["plan_digest"], operation_id="op-migrate")
    assert outcome["status"] == "accepted"
    assert outcome["superseded_tasks"] == ["legacy-task-1"]
    assert outcome["unknown_calls"] == 1
    after = store.load_document()
    assert after["compatibility"]["minimum_writer"] == "rc3-entry.v1"
    assert after["collaboration"]["request"] is None
    assert after["collaboration"]["decisions"] == []
    # Immutable facts survive byte-for-byte.
    assert [entry["page"] for entry in after["pages"]] == page_refs
    assert after["task"]["existing_decisions"] == before["task"]["existing_decisions"]
    assert after["task"]["presentation_mode_source"] == "default"
    retired = store.read_object_json(after["tasks"][0])
    assert retired["status"] == "superseded"
    assert retired["call_allowances"][0]["state"] == "unknown"
    assert retired["error"]["code"] == "migration_superseded"
    # After migration the ordinary collaboration writes work.
    outcome = collaboration.start_request(
        project, input={"intent": "content_only", "content_intent": "write_only",
                        "instruction_evidence": {"kind": "host_attested_instruction",
                                                 "source_ref": {"path": page_refs[0]["path"],
                                                                "sha256": page_refs[0]["sha256"]},
                                                 "source_locator": "chat:msg-1", "actor_id": None,
                                                 "transport_receipt_ref": None, "presentation_ref": None},
                        "scope": {"subject": "pages", "page_ids": [], "page_manifest_ref": None,
                                  "external_artifact_ref": None, "layers": ["narrative"],
                                  "allow_page_membership_change": False,
                                  "allow_page_order_change": False, "purpose": "exploratory"}},
        base_revision=after["revision_id"], operation_id="op-start-after-migration")
    assert outcome["status"] == "accepted"


def test_apply_is_idempotent_and_digest_guarded(tmp_path):
    project, store = _legacy_project(tmp_path)
    description = collaboration_migration.describe(project)
    first = collaboration_migration.apply(
        project, base_revision=store.load_document()["revision_id"],
        plan_digest=description["plan_digest"], operation_id="op-migrate")
    assert first["status"] == "accepted"
    revision_after = store.load_document()["revision_id"]
    # Same operation id replays the original receipt without writing.
    replay = collaboration_migration.apply(
        project, base_revision=revision_after,
        plan_digest=description["plan_digest"], operation_id="op-migrate")
    assert replay["status"] == "already_applied"
    assert replay["applied_revision_id"] == first["revision_id"]
    # An already-migrated project is a no-op, not a second migration.
    again = collaboration_migration.apply(
        project, base_revision=revision_after,
        plan_digest=description["plan_digest"], operation_id="op-migrate-2")
    assert again["status"] == "already_migrated"
    assert store.load_document()["revision_id"] == revision_after


def test_apply_rejects_a_stale_plan_digest(tmp_path):
    project, store = _legacy_project(tmp_path)
    description = collaboration_migration.describe(project)
    # Project moves after describe (e.g. another session committed).
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "unrelated-commit", "kind": "task_update",
                                      "description": "unrelated", "read_set": []})
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="unrelated-commit")
    with pytest.raises(ConflictError, match="plan_digest"):
        collaboration_migration.apply(
            project, base_revision=store.load_document()["revision_id"],
            plan_digest=description["plan_digest"], operation_id="op-migrate")
