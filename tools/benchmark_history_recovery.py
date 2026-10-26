"""RP-29 synthetic fixed-workload diagnostics; no external/model calls.

Run the same script against baseline and candidate via PYTHONPATH, reusing one
--workload-root. Cold means cleared in-process ancestry/operation caches, not an
OS disk-cache flush. Each N/cold-or-warm workload has three timed observations.
"""

import argparse
import json, os, time, uuid
from pathlib import Path
from unittest.mock import patch
from deck_master import editing, operations, operation_coverage, personal_recovery, snapshots, ui_journal, view
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workload-root", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
ROOT = args.workload_root
ROOT.mkdir(parents=True, exist_ok=True)


def setup(n):
    project = ROOT / str(n)
    info = ROOT / (str(n) + ".json")
    if info.exists():
        return project, json.loads(info.read_text())
    create_sample(project, page_count=2, readonly=False)
    store = Store(project)
    revisions = []
    for i in range(n):
        doc = store.load_document()
        op = str(uuid.uuid4())
        new = bump_revision(
            doc, {"operation_id": op, "kind": "task_update", "description": "Synthetic history " + str(i) + " x" * 100, "read_set": []}
        )
        with store._locked():
            operations.commit_locked(
                store,
                document=new,
                base_revision=doc["revision_id"],
                operation_id=op,
                kind="benchmark.local",
                digest=operations.request_digest(doc, "benchmark.local", doc["revision_id"], {}),
                result={"revision_id": new["revision_id"], "fixture": i},
            )
        revisions.append(new["revision_id"])
    doc = store.load_document()
    identity = ui_journal.context(project)[2]
    for i in range(n):
        draft = {
            "schema_version": "ui_draft.v1",
            "draft_id": "fixture-" + str(i),
            "project_id": doc["project_id"],
            "project_identity": identity,
            "target": {"scope": "page", "page_id": "p01", "layer": "content"},
            "base_revision": revisions[0],
            "base_ref": doc["pages"][0]["page"],
            "content": {"text": "Synthetic backup " + str(i)},
            "pending": None,
        }
        ui_journal.save(project, draft=draft)
        input = {"project_id": doc["project_id"], "scope": "current_project", "draft_ids": "all", "reading_preferences": False}
        p = ui_journal.plan_clear(project, input=input)
        ui_journal.commit_clear(
            project, operation_id=str(uuid.uuid4()), input=input, plan_id=p["plan_id"], manifest_digest=p["manifest_digest"]
        )
    data = {"head": doc["revision_id"], "start": revisions[0], "operation_id": op}
    info.write_text(json.dumps(data))
    return project, data


def sample(fn, cold):
    if cold:
        snapshots._cached_header.cache_clear()
        operation_coverage.clear()
    count = {"revision_reads": 0, "header_checks": 0, "clear_log_reads": 0, "index_writes": 0, "fsync": 0}
    rb, rt = Path.read_bytes, Path.read_text
    header = snapshots._header
    log = ui_journal._read_clear_log
    atomic = operations._atomic_write_bytes
    fsync = os.fsync

    def read(fn, self, *a, **k):
        if self.parent.name == "revisions":
            count["revision_reads"] += 1
        return fn(self, *a, **k)

    def h(*a, **k):
        count["header_checks"] += 1
        return header(*a, **k)

    def l(*a, **k):
        count["clear_log_reads"] += 1
        return log(*a, **k)

    def w(*a, **k):
        count["index_writes"] += 1
        return atomic(*a, **k)

    def f(*a, **k):
        count["fsync"] += 1
        return fsync(*a, **k)

    with (
        patch.object(Path, "read_bytes", lambda self, *a, **k: read(rb, self, *a, **k)),
        patch.object(Path, "read_text", lambda self, *a, **k: read(rt, self, *a, **k)),
        patch.object(snapshots, "_header", h),
        patch.object(ui_journal, "_read_clear_log", l),
        patch.object(operations, "_atomic_write_bytes", w),
        patch.object(os, "fsync", f),
    ):
        cpu = time.process_time()
        wall = time.perf_counter()
        result = fn()
        count.update(cpu_ms=round((time.process_time() - cpu) * 1000, 3), wall_ms=round((time.perf_counter() - wall) * 1000, 3))
    return count


rows = []
for n in (8, 16, 32):
    project, info = setup(n)
    store = Store(project)
    doc = store.load_document()
    workloads = {
        "input_reason": lambda: view._latest_input_update_reason(store, doc),
        "history_page": lambda: editing.history(
            project, revision=info["head"], cursor=info["head"] + ":" + info["start"], limit=2, related_only=False
        ),
        "backup_list": lambda: personal_recovery.listing(project),
        "operation_query": lambda: [operations.show(project, operation_id=info["operation_id"]) for _ in range(n)],
    }
    for name, fn in workloads.items():
        for mode in ("cold", "warm"):
            if mode == "warm":
                fn()
            for rep in range(3):
                rows.append({"N": n, "workload": name, "mode": mode, "repeat": rep, **sample(fn, mode == "cold")})
args.out.write_text(json.dumps(rows, indent=2) + "\n")
print(str(args.out), len(rows), "samples")
