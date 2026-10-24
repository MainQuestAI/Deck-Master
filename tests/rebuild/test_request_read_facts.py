"""RP-26 explicit synthetic immutable records, no Host/model calls."""

import copy
from unittest.mock import patch
import pytest
from test_candidate_decisions import store as store_fixture, candidate
from deck_master import candidates, changes, workbench, ui_journal, collaboration
from deck_master.models import bump_revision
from deck_master.store import Store
from deck_master.operations import OperationError


def scaled(root, n):
    store = store_fixture.__wrapped__(root)
    cid, task = candidate(store)
    doc = store.load_document()
    original = candidates._records(store, doc)[cid][0]
    original_task = next(store.read_object_json(r) for r in doc["tasks"] if store.read_object_json(r)["task_id"] == original["task_id"])
    original_change = store.read_object_json(doc["changes"][0])
    doc["tasks"] = []
    doc["candidates"] = []
    doc["changes"] = []
    for i in range(n):
        c = copy.deepcopy(original)
        t = copy.deepcopy(original_task)
        g = copy.deepcopy(original_change)
        c["candidate_id"] = f"candidate-scale-{i}"
        c["task_id"] = t["task_id"] = f"task-scale-{i}"
        r = store.put_json_object(c)
        t["candidate_refs"] = [r]
        t["result_refs"] = [c["result_ref"], r]
        # Explicitly invalid icon recipe exercises read-time verification refusal.
        t["stage_request"]["icon_recipe_ref"] = doc["pages"][0]["blueprint"]
        doc["tasks"].append(store.put_json_object(t))
        doc["candidates"].append(r)
        g["change_id"] = f"change-scale-{i}"
        g["task_ids"] = [t["task_id"]]
        doc["changes"].append(store.put_json_object(g))
    updated = bump_revision(
        doc, {"operation_id": "scale", "kind": "task_update", "description": "Synthetic read scaling, not Host evidence", "read_set": []}
    )
    store.commit_change(base_revision=doc["revision_id"], document=updated, operation_id="scale")
    return store


def test_candidate_collection_shared_and_new_request_revalidates(tmp_path, monkeypatch):
    store = scaled(tmp_path, 4)
    revision = store.current_revision_id()
    original = candidates._records
    calls = []

    def records(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(candidates, "_records", records)
    result = candidates.listing(store.project_root, revision=revision)
    assert len(calls) == 1
    assert [r["candidate"]["candidate_id"] for r in result["candidates"]] == [f"candidate-scale-{i}" for i in range(4)]
    assert all(not r["selection_allowed"] for r in result["candidates"])
    # A later public plan independently revalidates the collection. Read-time
    # preview sharing never becomes adoption eligibility.
    document = store.load_document()
    with pytest.raises(OperationError):
        candidates.plan(
            store.project_root,
            input={
                "schema_version": "candidate_selection.v1",
                "project_id": document["project_id"],
                "base_revision": revision,
                "candidate_ids": ["candidate-scale-0"],
            },
        )
    assert len(calls) == 3
    ref = document["tasks"][0]
    (store.project_root / ref["path"]).write_text("{}")
    with pytest.raises(OperationError):
        candidates.listing(store.project_root, revision=revision)
    assert len(calls) == 4


def test_change_list_matches_handoff_without_constructing_it(tmp_path, monkeypatch):
    store = scaled(tmp_path, 4)
    expected = [changes.handoff(store.project_root, change_id=f"change-scale-{i}") for i in range(4)]

    def forbidden(*args, **kwargs):
        raise AssertionError("list constructed a handoff")

    monkeypatch.setattr(changes, "handoff", forbidden)
    rows = changes.list_changes(store.project_root)["changes"]
    assert [r["change_id"] for r in rows] == [f"change-scale-{i}" for i in range(4)]
    for row, expected_state in zip(rows, expected, strict=True):
        assert {k: row[k] for k in ("status", "completed_count", "total_count", "needs_verification")} == {
            k: expected_state[k] for k in ("status", "completed_count", "total_count", "needs_verification")
        }
    plan_ref = store.read_object_json(store.load_document()["changes"][0])["plan_ref"]
    (store.project_root / plan_ref["path"]).write_text("{}")
    with pytest.raises(OperationError):
        changes.list_changes(store.project_root)


def test_lineage_one_task_lookup_and_fixed_snapshot(tmp_path, monkeypatch):
    store = scaled(tmp_path, 4)
    document = store.load_document()
    refs = {r["sha256"] for r in document["tasks"]}
    old_read = workbench._ReadContext.read
    reads = []

    def read(ctx, ref):
        if ref["sha256"] in refs:
            reads.append(ref["sha256"])
        return old_read(ctx, ref)

    monkeypatch.setattr(workbench._ReadContext, "read", read)
    result = workbench.page_lineage(store.project_root, "p01", revision=document["revision_id"])
    assert len(reads) == 4
    assert [t["task_id"] for t in result["tasks"]] == [f"task-scale-{i}" for i in range(4)]
    changed = bump_revision(
        copy.deepcopy(document),
        {"operation_id": "next", "kind": "task_update", "description": "Synthetic no-task current revision", "read_set": []},
    )
    changed["tasks"] = []
    store.commit_change(base_revision=document["revision_id"], document=changed, operation_id="next")
    assert workbench.page_lineage(store.project_root, "p01", revision=document["revision_id"]) == result
    assert workbench.page_lineage(store.project_root, "p01")["tasks"] == []


def test_project_info_passes_one_exact_snapshot_to_projections(tmp_path, monkeypatch):
    store = scaled(tmp_path, 4)
    seen = []
    original = collaboration.describe_snapshot

    def describe(reader, document, **kwargs):
        seen.append((reader, document))
        return original(reader, document, **kwargs)

    monkeypatch.setattr(collaboration, "describe_snapshot", describe)
    value = ui_journal.project_info(store.project_root)
    assert len(seen) == 1
    assert seen[0][0].document is seen[0][1]
    assert value["revision_id"] == value["collaboration"]["revision_id"] == value["migration"]["revision_id"]
    assert len([k for k in seen[0][0].objects if k[1] in {r["sha256"] for r in seen[0][1]["tasks"]}]) == 4


@pytest.mark.parametrize(
    "status,unknown", [("awaiting_host", False), ("running", False), ("failed", False), ("cancelled", False), ("completed", True)]
)
def test_change_aggregation_preserves_status_and_unknown(tmp_path, status, unknown):
    store = scaled(tmp_path, 1)
    document = store.load_document()
    task = store.read_object_json(document["tasks"][0])
    task["status"] = status
    if status == "running":
        task["execution_ref"] = "synthetic-running"
    if unknown:
        task["call_allowances"] = [
            {
                "allowance_id": "synthetic-unknown",
                "state": "unknown",
                "execution_ref": "synthetic-running",
                "invocation_ref": None,
                "evidence": [],
                "evidence_level": "host_reported",
            }
        ]
    document["tasks"] = [store.put_json_object(task)]
    updated = bump_revision(
        document,
        {"operation_id": "state", "kind": "task_update", "description": "Synthetic task state, not execution evidence", "read_set": []},
    )
    store.commit_change(base_revision=document["revision_id"], document=updated, operation_id="state")
    handoff = changes.handoff(store.project_root, change_id="change-scale-0")
    row = changes.list_changes(store.project_root)["changes"][0]
    assert row["status"] == handoff["status"] == ("unknown" if unknown else status)
    assert row["needs_verification"] == handoff["needs_verification"]


@pytest.mark.parametrize("damage", ["foreign_project", "missing"])
def test_summary_freshness_does_not_reuse_partial_ancestry_proof(tmp_path, damage):
    import json

    store = scaled(tmp_path, 1)
    before = workbench.workbench_summary(store.project_root)
    doc = store.load_document()
    ancestor_id = doc["parent_revision_id"]
    task = store.read_object_json(doc["tasks"][0])
    assert ancestor_id not in (doc["revision_id"], task["dispatch_revision"])
    path = store.revisions_dir / (ancestor_id + ".json")
    saved = path.read_bytes()
    if damage == "missing":
        path.unlink()
    else:
        ancestor = json.loads(saved)
        ancestor["project_id"] = "foreign-synthetic-project"
        path.write_text(json.dumps(ancestor))
    warm = workbench.workbench_summary(store.project_root)
    with workbench._summary_cache_lock:
        workbench._summary_cache.clear()
    cold = workbench.workbench_summary(store.project_root)
    assert warm == cold
    before_action = next(a for a in before["next_actions"]["actions"] if a["kind"] == "compare_candidates")
    after_action = next(a for a in warm["next_actions"]["actions"] if a["kind"] == "compare_candidates")
    assert before_action["state"] == "derived"
    assert after_action["state"] == "unknown"
    assert warm["pages"][0]["attention"]["items"][0]["state"] == "unknown"
    assert warm != before
    path.write_bytes(saved)
    assert workbench.workbench_summary(store.project_root) == before
