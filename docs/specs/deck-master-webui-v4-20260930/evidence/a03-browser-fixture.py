"""A03 browser-verification fixture: mixed-stage project on a real service.

Creates a 24-page editable synthetic sample, then mixes real action facts:
a pending SVG candidate, an awaiting-host task, a task with an unknown call
(verify_execution), and an un-reconciled brief change (reconcile_inputs).
No model calls; synthetic evidence only.
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from deck_master import changes, service, tasks
from deck_master.models import bump_revision, content_identity, require_writer
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def synthetic_task(doc, task_id, status, *, result_refs=()):
    value = tasks.new_task(task_id=task_id, operation_id="op-" + task_id, kind="review",
                           scope_pages=["p01"], instruction="A03 synthetic " + status, inputs=[], dependencies=[],
                           dispatch_revision=doc["revision_id"], produced_against=content_identity(doc),
                           status=status)
    value["result_refs"] = list(result_refs)
    return value


def synthetic_candidate(store, doc, *, task_id, page_id, result_ref, stage="svg"):
    value = {"schema_version": "candidate.v1", "candidate_id": "candidate-" + uuid.uuid4().hex[:8],
             "project_id": doc["project_id"], "task_id": task_id, "created_at": tasks._utc_now_iso(),
             "page_id": page_id, "stage": stage, "base_revision": doc["revision_id"],
             "generation_basis": {"page_ref": doc["pages"][0]["page"], "input_digest": "0" * 64,
                                  "design_digest": "0" * 64, "blueprint_ref": None},
             "request_ref": None, "attempt_ref": None,
             "target_ref": doc["pages"][0].get("svg"), "result_ref": result_ref, "status": "available"}
    return value


def commit(store, doc, operation):
    current = store.load_document()
    updated = bump_revision({**doc, "revision_id": current["revision_id"]},
                            {"operation_id": operation, "kind": "task_update", "description": "A03 fixture", "read_set": []})
    store.commit_change(base_revision=current["revision_id"], document=updated, operation_id=operation)
    return updated


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a03-'))
    project = root / 'a03-project'
    create_sample(project, page_count=24, readonly=False)
    store = Store(project)

    # 1) a real trial task with an unknown call -> verify_execution action
    doc = store.load_document()
    entry = next(e for e in doc["pages"] if e["page_id"] == "p01")
    intent = {"schema_version": "change_intent.v1", "project_id": doc["project_id"],
              "base_revision": doc["revision_id"], "intent": "repair", "instruction": "A03 verification spacing.",
              "annotation_refs": [], "max_calls": 1, "mode": "trial",
              "targets": [{"page_id": "p01", "page_ref": entry["page"], "layer": "original_image",
                           "artifact_ref": entry["blueprint"]}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan["plan_id"], base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
    task_id = result["operation_result"]["task_ids"][0]
    service.task_start(project, task_id=task_id, execution_ref="synthetic-a03",
                       supported_protocols=["changes.v1", "generation.v1"],
                       capabilities=["change_plan", "generation_request_freeze", "attempt_binding", "native_tool_observation", "candidate_result"])
    doc = store.load_document()
    task = tasks._lookup_task(doc, task_id, store)
    from deck_master import generation
    frozen = generation.freeze(project, task_id=task_id,
                               input=generation.prepared_input(store, doc, task),
                               base_revision=store.current_revision_id(), operation_id="a03-freeze")
    attempt = tasks.call_begin(store, task_id=task_id, allowance_id=task["call_allowances"][0]["allowance_id"],
                               execution_ref="synthetic-a03", request_id=frozen["request_id"])
    tasks.call_settle(store, task_id=task_id, allowance_id=attempt["allowance_id"],
                      attempt_id=attempt["attempt_id"], outcome="unknown", report_bytes=None)

    # 2) awaiting-host task + pending candidate + un-reconciled brief, one commit
    doc = store.load_document()
    staging = store.staging_dir / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "page.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><rect width="24" height="24"/></svg>')
    result_ref = store.put_json_object({"schema_version": "artifact.v1", "file": {"path": ".deckmaster/staging/x/page.svg", "sha256": "0" * 64}})
    candidate = synthetic_candidate(store, doc, task_id=task_id, page_id="p01", result_ref=result_ref)
    doc["candidates"] = [store.put_json_object(candidate)]
    require_writer(doc, "candidates.v1")
    doc["tasks"] = [*doc["tasks"], store.put_json_object(synthetic_task(doc, "task-a03-awaiting", "awaiting_host"))]
    doc["task"]["brief"] = "A03 修改后的用途：验证输入待协调投影"
    commit(store, doc, "a03-mixed-facts")

    server = WorkbenchServer(project)
    url = server.start()
    print(json.dumps({'url': url, 'project': str(project)}))
    try:
        sys.stdin.read()
    finally:
        server.stop()


if __name__ == '__main__':
    main()
