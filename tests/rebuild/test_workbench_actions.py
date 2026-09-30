"""B01 actionable overview read-model tests; synthetic evidence, no Host calls.

Covers the summary candidates schema branches (none/pending/adopted/damaged/
unknown-task), the per-page prompt_summary (prepared/frozen/submitted with
not_recorded/unreadable isolation and no prompt bodies in the payload),
deterministic next_actions ordering with stable action_ids, pending-only
candidate counting, and the no-action reason. No style-deviation action is
projected without professional review evidence.
"""
import copy
import io
import json
import uuid
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from deck_master import service, tasks, ui_journal as journal, workbench
from deck_master.models import bump_revision, content_identity, require_writer, validate_schema
from deck_master.pipeline import artifact
from deck_master.samples import create_sample
from deck_master.store import Store

from test_generation_protocol import accept as accept_image, begin, flow, freeze, settle, start
from test_candidates import adopt, candidate as svg_candidate, plan

SUMMARY_SCHEMA = json.loads(
    (Path(workbench.__file__).parent / "resources/contracts/workbench-summary.v1.schema.json").read_text())


def validate(summary):
    Draft202012Validator.check_schema(SUMMARY_SCHEMA)
    Draft202012Validator(SUMMARY_SCHEMA).validate(summary)


def commit(store, doc, operation):
    current = store.load_document()
    updated = bump_revision({**doc, "revision_id": current["revision_id"]},
                            {"operation_id": operation, "kind": "task_update", "description": "test fixture", "read_set": []})
    store.commit_change(base_revision=current["revision_id"], document=updated, operation_id=operation)
    return updated


def png_file(tmp_path, color="#224466"):
    from PIL import Image
    target = tmp_path / ("synthetic-" + color.lstrip("#") + ".png")
    Image.new("RGB", (32, 18), color).save(target)
    return target


def synthetic_task(doc, task_id, status, *, result_refs=()):
    value = tasks.new_task(task_id=task_id, operation_id="op-" + task_id, kind="review",
                           scope_pages=["p1"], instruction="synthetic " + status, inputs=[], dependencies=[],
                           dispatch_revision=doc["revision_id"], produced_against=content_identity(doc),
                           status=status)
    value["result_refs"] = list(result_refs)
    return value


def synthetic_candidate(store, doc, *, task_id, page_id, result_ref, stage="svg", valid=True):
    value = {"schema_version": "candidate.v1", "candidate_id": "candidate-" + uuid.uuid4().hex[:8],
             "project_id": doc["project_id"], "task_id": task_id,
             "created_at": tasks._utc_now_iso(), "page_id": page_id, "stage": stage,
             "base_revision": doc["revision_id"],
             "generation_basis": {"page_ref": doc["pages"][0]["page"], "input_digest": "0" * 64,
                                  "design_digest": "0" * 64, "blueprint_ref": None},
             "request_ref": None, "attempt_ref": None,
             "target_ref": doc["pages"][0].get("svg"), "result_ref": result_ref, "status": "available"}
    if valid:
        # a page-less candidate is deliberately schema-invalid damage; the
        # summary must still isolate it instead of crashing the read
        validate_schema("candidate", value)
    return value


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "candidate-project"
    create_sample(path, page_count=2, readonly=False)
    return path


def kinds(summary):
    return [action["kind"] for action in summary["next_actions"]["actions"]]


def test_candidates_block_branches_pass_active_schema(project):
    store = Store(project)
    summary = workbench.workbench_summary(project)
    assert summary["candidates"] == {"status": "not_recorded"}
    validate(summary)

    cid = svg_candidate(store)
    summary = workbench.workbench_summary(project)
    assert summary["candidates"] == {"status": "recorded", "count": 1, "pending_count": 1,
                                     "adopted_count": 0, "unreadable_count": 0}
    compare = [a for a in summary["next_actions"]["actions"] if a["kind"] == "compare_candidates"]
    assert len(compare) == 1
    assert compare[0]["page_ids"] == ["p01"] and compare[0]["layer"] == "svg"
    assert compare[0]["enabled"] is True and compare[0]["state"] == "derived"
    assert compare[0]["source_refs"] and compare[0]["revision_id"] == summary["revision_id"]
    assert summary["pages"][0]["attention"]["status"] == "recorded"
    assert {i["kind"] for i in summary["pages"][0]["attention"]["items"]} == {"compare_candidates", "prepare_stage"}
    validate(summary)

    adopt(store, plan(store, [cid]))
    summary = workbench.workbench_summary(project)
    assert summary["candidates"]["count"] == 1 and summary["candidates"]["pending_count"] == 0
    assert summary["candidates"]["adopted_count"] == 1 and summary["candidates"]["unreadable_count"] == 0
    assert "compare_candidates" not in kinds(summary)
    assert summary["pages"][0]["attention"] == {"status": "not_recorded"}
    validate(summary)


def test_damaged_candidate_is_isolated_but_still_pending(project):
    store = Store(project)
    svg_candidate(store)
    ref = store.load_document()["candidates"][0]
    (project / ref["path"]).write_bytes(b"corrupted candidate object")
    summary = workbench.workbench_summary(project)
    block = summary["candidates"]
    assert block["status"] == "recorded" and block["count"] == 1
    assert block["pending_count"] == 1 and block["unreadable_count"] == 1
    compare = [a for a in summary["next_actions"]["actions"] if a["kind"] == "compare_candidates"][0]
    assert compare["enabled"] is False and compare["blocked_reason"] == "candidate_unreadable"
    assert compare["state"] == "unknown" and compare["page_ids"] == []
    # the damage stays local: pages and other actions still read
    assert summary["pages"][0]["title"] is not None
    assert "prepare_stage" in kinds(summary)
    validate(summary)


def test_candidate_with_unknown_task_stays_pending(project, tmp_path):
    store = Store(project)
    doc = copy.deepcopy(store.load_document())
    result_ref = artifact(store, png_file(tmp_path), "svg", page_id="p01",
                          dependencies=[{"kind": "content", "identity": "page:p01", "sha256": doc["pages"][0]["page"]["sha256"]}])
    with_page = synthetic_candidate(store, doc, task_id="no-such-task", page_id="p01", result_ref=result_ref)
    without_page = synthetic_candidate(store, doc, task_id="no-such-task-either", page_id=None,
                                       result_ref=result_ref, valid=False)
    doc["candidates"] = [store.put_json_object(with_page), store.put_json_object(without_page)]
    require_writer(doc, "candidates.v1")
    commit(store, doc, "unknown-task-candidates")
    summary = workbench.workbench_summary(project)
    assert summary["candidates"]["pending_count"] == 2 and summary["candidates"]["adopted_count"] == 0
    compares = [a for a in summary["next_actions"]["actions"] if a["kind"] == "compare_candidates"]
    # same kind/reason/layer groups into one deck action; the page-less fact
    # still contributes its source ref and the pending count
    assert len(compares) == 1
    assert compares[0]["page_ids"] == ["p01"]
    # both candidate refs plus their shared result ref
    assert len(compares[0]["source_refs"]) == 3
    validate(summary)


def test_prompt_summary_prepared_frozen_submitted_and_no_text_leak(flow):
    path, store, task, native = flow
    prepared_ref = next(r for r in task["inputs"]
                        if store.read_object_json(r).get("schema_version") == "deck_blueprint_request.v1")
    summary = workbench.workbench_summary(path)
    prompt = summary["pages"][0]["prompt_summary"]
    assert prompt["prepared"] == {"status": "recorded", "count": 1, "refs": [prepared_ref]}
    assert prompt["frozen"] == {"status": "not_recorded"}
    assert prompt["submitted"] == {"status": "not_recorded"}

    start(flow)
    frozen = freeze(flow)
    summary = workbench.workbench_summary(path)
    prompt = summary["pages"][0]["prompt_summary"]
    # freezing adds the immutable request; the prepared record is unchanged
    assert prompt["prepared"] == {"status": "recorded", "count": 1, "refs": [prepared_ref]}
    assert prompt["frozen"]["status"] == "recorded" and prompt["frozen"]["count"] == 1
    assert prompt["frozen"]["refs"][0]["sha256"] == frozen["request_ref"]["sha256"]
    assert prompt["submitted"] == {"status": "not_recorded"}

    attempt = begin(flow, frozen)
    report, raw = native()
    settle(flow, attempt, report)
    accept_image(flow, frozen, attempt, raw)
    # the real accept path records the Host-reported submitted prompt; the
    # summary reports the evidence without expanding any prompt body
    summary = workbench.workbench_summary(path)
    submitted = summary["pages"][0]["prompt_summary"]["submitted"]
    assert submitted["status"] == "recorded" and submitted["observer"] == "host_reported"
    assert submitted["basis"] == "artifact.provenance.submitted_prompt"
    submitted_text = store.read_object_bytes(submitted["ref"]).decode("utf-8")

    dumped = json.dumps(summary)
    assert submitted_text not in dumped
    assert store.read_object_json(frozen["request_ref"])["input"]["prompt"] not in dumped
    assert store.read_object_json(prepared_ref)["prompt"] not in dumped
    validate(summary)

    # a missing frozen record is never filled from the personal draft journal
    current = store.load_document()
    journal.save(path, draft={
        "schema_version": "ui_draft.v1", "project_id": current["project_id"],
        "project_identity": journal.project_info(path)["project_identity"], "draft_id": "prompt-draft",
        "target": {"scope": "page", "page_id": "p1", "layer": "content"},
        "base_revision": current["revision_id"],
        "base_ref": current["pages"][0]["page"],
        "content": {"text": frozen["input"]["prompt"]}, "pending": None})
    fresh = workbench.workbench_summary(path)
    assert fresh["pages"][0]["prompt_summary"]["frozen"]["status"] == "recorded"
    assert fresh["pages"][0]["prompt_summary"]["frozen"]["refs"][0]["sha256"] == frozen["request_ref"]["sha256"]


def test_unreadable_prompt_records_are_isolated_per_branch(project):
    store = Store(project)
    doc = store.load_document()
    service.open_blueprint_task(store, doc, doc["pages"][0])
    task_obj = store.read_object_json(store.load_document()["tasks"][-1])
    request_ref = next(r for r in task_obj["inputs"]
                       if store.read_object_json(r).get("schema_version") == "deck_blueprint_request.v1")
    summary = workbench.workbench_summary(project)
    prompt = summary["pages"][0]["prompt_summary"]
    assert prompt["prepared"]["status"] == "recorded" and prompt["prepared"]["count"] == 1
    assert prompt["prepared"]["refs"][0]["sha256"] == request_ref["sha256"]
    assert prompt["frozen"] == {"status": "not_recorded"}
    assert prompt["submitted"] == {"status": "not_recorded"}

    (project / request_ref["path"]).write_bytes(b"corrupted prepared request")
    summary = workbench.workbench_summary(project)
    prompt = summary["pages"][0]["prompt_summary"]
    assert prompt["prepared"]["status"] == "unreadable"
    assert prompt["prepared"]["unreadable_count"] == 1
    assert prompt["prepared"]["error"]["code"] == "object_unreadable"
    assert prompt["frozen"] == {"status": "not_recorded"}
    validate(summary)

    # an unreadable blueprint artifact hides whether a submitted prompt existed
    doc = copy.deepcopy(store.load_document())
    (project / doc["pages"][0]["blueprint"]["path"]).write_bytes(b"corrupted blueprint artifact")
    summary = workbench.workbench_summary(project)
    assert summary["pages"][0]["prompt_summary"]["submitted"]["status"] == "unreadable"
    validate(summary)


def test_next_actions_order_reasons_and_stable_ids(flow, tmp_path):
    path, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    begin(flow, frozen)
    doc = copy.deepcopy(store.load_document())
    entry = doc["pages"][0]
    # a blueprint bound to the current content: replacing the page below makes
    # it basis_changed while the missing svg stays a prepare fact
    dep = [{"kind": "content", "identity": "page:p1", "sha256": entry["page"]["sha256"]}]
    entry["blueprint"] = artifact(store, png_file(tmp_path), "blueprint", page_id="p1", dependencies=dep)
    stored = store.read_object_json(doc["tasks"][-1])
    stored["call_allowances"][0]["state"] = "unknown"
    doc["tasks"][-1] = store.put_json_object(stored)
    for status in ("failed", "superseded", "awaiting_host"):
        doc["tasks"] = [*doc["tasks"], store.put_json_object(synthetic_task(doc, "task-" + status, status))]
    doc["tasks"] = [*doc["tasks"], store.put_json_object(
        synthetic_task(doc, "task-completed", "completed", result_refs=[entry["page"]]))]
    page = store.read_object_json(entry["page"])
    page["customer_visible"]["title"] = "Edited outside the content basis"
    entry["page"] = store.put_json_object(page)
    # the input digest covers task facts and source semantics, so a brief
    # change without a content update is what flips input_alignment
    doc["task"]["brief"] = "Changed after the current content was built"
    candidate = synthetic_candidate(store, doc, task_id=task["task_id"], page_id="p1",
                                    result_ref=entry["blueprint"])
    doc["candidates"] = [store.put_json_object(candidate)]
    require_writer(doc, "candidates.v1")
    doc["reviews"] = [store.put_json_object({"schema_version": "deck_review.v1", "review_id": "rev-1",
                                             "kind": "page_visual", "status": "pass", "subjects": [],
                                             "dependencies": [], "reviewer": [], "observations": [],
                                             "findings": [], "created_at": tasks._utc_now_iso(), "replaces": None})]
    commit(store, doc, "mixed-action-facts")

    summary = workbench.workbench_summary(path)
    assert summary["input_alignment"] == "needs_reconciliation"
    # handoff sits right below recovery: an awaiting task is the primary
    # executable loop step and must not be buried behind rework or reading
    assert kinds(summary) == ["verify_execution", "handoff", "inspect_failure", "replan",
                              "compare_candidates", "reconcile_inputs", "prepare_stage",
                              "refresh_stage", "review_quality", "review_results"]
    by_kind = {action["kind"]: action for action in summary["next_actions"]["actions"]}
    assert by_kind["verify_execution"]["reason_code"] == "unknown_calls_recorded"
    assert by_kind["inspect_failure"]["reason_code"] == "task_failed"
    assert by_kind["replan"]["reason_code"] == "task_superseded"
    assert by_kind["compare_candidates"]["reason_code"] == "candidate_pending"
    assert by_kind["reconcile_inputs"]["reason_code"] == "content_needs_reconciliation"
    assert by_kind["prepare_stage"]["reason_code"] == "stage_missing" and by_kind["prepare_stage"]["layer"] == "svg"
    assert by_kind["refresh_stage"]["reason_code"] == "stage_basis_changed" and by_kind["refresh_stage"]["layer"] == "blueprint"
    assert by_kind["handoff"]["reason_code"] == "task_awaiting_host"
    assert by_kind["review_results"]["reason_code"] == "task_results_ready"
    assert by_kind["review_quality"]["reason_code"] == "quality_reviews_recorded"
    assert by_kind["review_quality"]["source_refs"] == summary["quality"]["review_refs"]
    for action in summary["next_actions"]["actions"]:
        assert action["enabled"] is True and action["state"] == "derived"
        assert action["revision_id"] == summary["revision_id"]
        # reconcile_inputs is a derived deck fact with no single object ref
        if action["kind"] != "reconcile_inputs":
            assert action["source_refs"]

    # attention stays page-scoped; deck-level facts never land on a page
    attention = {item["kind"] for item in summary["pages"][0]["attention"]["items"]}
    assert attention == {"verify_execution", "inspect_failure", "replan", "compare_candidates",
                         "prepare_stage", "refresh_stage", "handoff", "review_results"}
    assert all(item["page_ids"] == ["p1"] for item in summary["pages"][0]["attention"]["items"])

    # stable payload for the same current revision, and a fixed revision read
    # never consults the live clock
    assert workbench.workbench_summary(path) == summary
    fixed = store.current_revision_id()
    assert workbench.workbench_summary(path, revision=fixed) == workbench.workbench_summary(path, revision=fixed)
    validate(summary)


def test_snapshot_level_candidate_damage_is_isolated_not_fatal(project):
    store = Store(project)
    # snapshot-level damage: entries that are not valid object refs, plus a
    # foreign-path entry, must not crash the summary or echo foreign paths
    revision = store.current_revision_id()
    path = store.revisions_dir / f"{revision}.json"
    doc = json.loads(path.read_text("utf-8"))
    doc["candidates"] = ["not-a-ref", {"path": "etc/passwd", "sha256": "0" * 64}]
    doc["candidate_adoptions"] = ["oops"]
    path.write_text(json.dumps(doc), "utf-8")
    summary = workbench.workbench_summary(project)
    assert summary["candidates"] == {"status": "recorded", "count": 2, "pending_count": 2,
                                     "adopted_count": 0, "unreadable_count": 2}
    compare = [a for a in summary["next_actions"]["actions"] if a["kind"] == "compare_candidates"][0]
    assert compare["enabled"] is False and compare["blocked_reason"] == "candidate_unreadable"
    assert compare["state"] == "unknown" and compare["source_refs"] == []
    assert "etc/passwd" not in json.dumps(summary) and "not-a-ref" not in json.dumps(summary)
    # the damage stays local: pages and stage actions still read
    assert summary["pages"][0]["title"] is not None
    assert "prepare_stage" in kinds(summary)
    validate(summary)


def test_frozen_record_damage_is_attributed_unreadable(flow):
    path, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    (path / frozen["request_ref"]["path"]).write_bytes(b"corrupted request object")
    summary = workbench.workbench_summary(path)
    prompt = summary["pages"][0]["prompt_summary"]
    assert prompt["frozen"]["status"] == "unreadable" and prompt["frozen"]["unreadable_count"] == 1
    # the frozen damage does not leak into the other prompt branches
    assert prompt["prepared"]["status"] in ("recorded", "not_recorded")
    assert prompt["submitted"]["status"] in ("recorded", "not_recorded", "unreadable")
    validate(summary)


def test_stale_running_is_live_only_and_unclaimed_is_a_snapshot_fact(project):
    store = Store(project)
    doc = copy.deepcopy(store.load_document())
    stale = tasks.new_task(task_id="task-stale", operation_id="op-stale", kind="blueprint",
                           scope_pages=["p01"], instruction="synthetic stale run", inputs=[], dependencies=[],
                           dispatch_revision=doc["revision_id"], produced_against=content_identity(doc),
                           status="running")
    stale["execution_ref"] = "synthetic-execution"
    stale["execution_started_at"] = "2000-01-01T00:00:00+00:00"
    unclaimed = tasks.new_task(task_id="task-unclaimed", operation_id="op-unclaimed", kind="blueprint",
                               scope_pages=["p01"], instruction="synthetic unclaimed run", inputs=[], dependencies=[],
                               dispatch_revision=doc["revision_id"], produced_against=content_identity(doc),
                               status="running")
    doc["tasks"] = [*doc["tasks"], store.put_json_object(stale), store.put_json_object(unclaimed)]
    fixed = commit(store, doc, "stale-unclaimed-fixture")["revision_id"]

    current = workbench.workbench_summary(project)
    verify = [a for a in current["next_actions"]["actions"] if a["kind"] == "verify_execution"]
    assert {a["reason_code"] for a in verify} == {"running_task_stale", "running_task_unclaimed"}
    # the fixed read of the same revision is clock-free and byte-stable
    first = workbench.workbench_summary(project, revision=fixed)
    second = workbench.workbench_summary(project, revision=fixed)
    assert first == second
    assert [a["reason_code"] for a in first["next_actions"]["actions"]
            if a["kind"] == "verify_execution"] == ["running_task_unclaimed"]
    validate(current)
    validate(first)


def test_unreadable_task_record_is_an_isolated_inspect_failure(project):
    store = Store(project)
    doc = copy.deepcopy(store.load_document())
    doomed = synthetic_task(doc, "task-doomed", "failed")
    ref = store.put_json_object(doomed)
    doc["tasks"] = [*doc["tasks"], ref]
    commit(store, doc, "doomed-task")
    (project / ref["path"]).write_bytes(b"corrupted task object")
    summary = workbench.workbench_summary(project)
    assert summary["unreadable_tasks"] == 1
    inspect = [a for a in summary["next_actions"]["actions"] if a["kind"] == "inspect_failure"][0]
    assert inspect["reason_code"] == "task_unreadable" and inspect["state"] == "unknown"
    assert inspect["page_ids"] == [] and inspect["source_refs"] == [ref]
    validate(summary)


def test_no_style_deviation_action_without_professional_evidence(tmp_path):
    from deck_master.samples import create_gallery_sample
    path = tmp_path / "gallery"
    manifest = create_gallery_sample(path, page_count=24, readonly=False)
    summary = workbench.workbench_summary(path)
    assert manifest["style_deviation_pages"]
    dumped = json.dumps(summary).lower()
    for forbidden in ("style_deviation", "drift", "风格偏离"):
        assert forbidden not in dumped
    assert summary["quality"]["status"] == "detail_required"
    allowed = {"verify_execution", "inspect_failure", "replan", "compare_candidates", "reconcile_inputs",
               "prepare_stage", "refresh_stage", "handoff", "review_results", "review_quality"}
    assert set(kinds(summary)) <= allowed
    # the rewritten blueprints are facts, not style verdicts: the stale ppt
    # previews on p11/p21 lag their replaced blueprints, and p19 (whose svg was
    # never drawn) stays a plain missing-layer fact
    refresh = {a["layer"]: set(a["page_ids"]) for a in summary["next_actions"]["actions"]
               if a["kind"] == "refresh_stage"}
    assert refresh.get("ppt_preview", set()) == {"p11", "p21"}
    assert "svg" not in refresh
    prepare = {a["layer"]: set(a["page_ids"]) for a in summary["next_actions"]["actions"]
               if a["kind"] == "prepare_stage"}
    assert "p19" in prepare.get("svg", set())
    validate(summary)


def test_completed_project_reports_no_pending_actions_with_readable_location(tmp_path):
    path = tmp_path / "complete"
    create_sample(path, page_count=1, readonly=False)
    store = Store(path)
    doc = copy.deepcopy(store.load_document())
    entry = doc["pages"][0]
    dep = [{"kind": "content", "identity": "page:p01", "sha256": entry["page"]["sha256"]}]
    entry["blueprint"] = artifact(store, png_file(tmp_path), "blueprint", page_id="p01", dependencies=dep)
    svg_file = tmp_path / "synthetic.svg"
    svg_file.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    entry["svg"] = artifact(store, svg_file, "svg", page_id="p01",
                            dependencies=[{"kind": "blueprint", "identity": "page:p01", "sha256": entry["blueprint"]["sha256"]}],
                            derived_from=[entry["blueprint"]])
    # a completed compose task would still be a tier-6 reading action (same as
    # run_desk); this fixture removes tasks to reach the truly action-free state
    doc["tasks"] = []
    commit(store, doc, "complete-fixture")
    summary = workbench.workbench_summary(path)
    assert summary["next_actions"] == {"status": "not_recorded", "reason_code": "no_pending_actions",
                                       "readable": {"scope": "deck_pages", "page_ids": ["p01"]}}
    assert all(page["attention"] == {"status": "not_recorded"} for page in summary["pages"])
    validate(summary)


def test_http_serves_actions_and_health_advertises_capability(project):
    from deck_master.web import WorkbenchServer
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        import urllib.request
        with urllib.request.urlopen(url + "/api/health", timeout=5) as response:
            health = json.loads(response.read())
        assert workbench.ACTIONS_CAPABILITY == "workbench_actions.v1"
        assert "workbench_actions.v1" in health["ui_capabilities"]
        with urllib.request.urlopen(url + "/api/workbench", timeout=5) as response:
            summary = json.loads(response.read())
        assert summary == workbench.workbench_summary(project)
        validate(summary)
    finally:
        server.stop()
