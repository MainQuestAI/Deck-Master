"""A04 browser-verification fixture: mixed-layer gallery on a real service.

create_gallery_sample provides 24 pages with real mixed layer facts (missing
blueprints p03/p14, stale p11/p21, SVG on even pages, PPT previews on a
subset). One real trial task on p01 adds a frozen generation request and an
unknown call (verify_execution projection). No model calls; synthetic only.
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from deck_master import changes, generation, service, tasks
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a04-'))
    project = root / 'a04-project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    intent = {"schema_version": "change_intent.v1", "project_id": doc["project_id"],
              "base_revision": doc["revision_id"], "intent": "repair", "instruction": "A04 frozen request verification.",
              "annotation_refs": [], "max_calls": 1, "mode": "trial",
              "targets": [{"page_id": "p01", "page_ref": entry["page"], "layer": "original_image",
                           "artifact_ref": entry["blueprint"]}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan["plan_id"], base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
    task_id = result["operation_result"]["task_ids"][0]
    service.task_start(project, task_id=task_id, execution_ref="synthetic-a04",
                       supported_protocols=["changes.v1", "generation.v1"],
                       capabilities=["change_plan", "generation_request_freeze", "attempt_binding", "native_tool_observation", "candidate_result"])
    doc = store.load_document()
    task = tasks._lookup_task(doc, task_id, store)
    frozen = generation.freeze(project, task_id=task_id,
                               input=generation.prepared_input(store, doc, task),
                               base_revision=store.current_revision_id(), operation_id="a04-freeze")
    attempt = tasks.call_begin(store, task_id=task_id, allowance_id=task["call_allowances"][0]["allowance_id"],
                               execution_ref="synthetic-a04", request_id=frozen["request_id"])
    tasks.call_settle(store, task_id=task_id, allowance_id=attempt["allowance_id"],
                      attempt_id=attempt["attempt_id"], outcome="unknown", report_bytes=None)
    server = WorkbenchServer(project)
    url = server.start()
    print(json.dumps({'url': url, 'project': str(project)}), flush=True)
    try:
        sys.stdin.read()
    finally:
        server.stop()


if __name__ == '__main__':
    main()
