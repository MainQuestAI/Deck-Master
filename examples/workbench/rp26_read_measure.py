"""RP-26 N/2N/4N immutable synthetic record diagnosis.

PYTHONPATH=src:tests/rebuild python examples/workbench/rp26_read_measure.py OUT
Uses test factory explicitly. No models, production artifacts or HOME writes.
"""

import json, time, sys, collections
from pathlib import Path
from unittest.mock import patch
from test_request_read_facts import scaled
from deck_master import candidates, changes, workbench, ui_journal
from deck_master.store import Store

out = Path(sys.argv[1])
out.mkdir()
results = []
for n in [4, 8, 16]:
    root = out / str(n)
    root.mkdir()
    store = scaled(root, n)
    updated = store.load_document()
    for label, fn in [
        ("project", lambda: ui_journal.project_info(root / "decision-project")),
        ("candidates", lambda: candidates.listing(store.project_root)),
        ("changes", lambda: changes.list_changes(store.project_root)),
        ("lineage", lambda: workbench.page_lineage(store.project_root, "p01")),
    ]:
        counts = collections.Counter()
        oldinit = Store.__init__
        oldread = Store.read_object_json
        oldrecords = candidates._records
        oldhandoff = changes.handoff
        oldctx = workbench._ReadContext.read

        def init(self, *a, **kw):
            counts["Store"] += 1
            oldinit(self, *a, **kw)

        def read(self, *a, **kw):
            counts["object_json_reads"] += 1
            return oldread(self, *a, **kw)

        def records(*a, **kw):
            counts["candidate_sets"] += 1
            return oldrecords(*a, **kw)

        def handoff(*a, **kw):
            counts["handoffs"] += 1
            return oldhandoff(*a, **kw)

        task_refs = {r["sha256"] for r in updated["tasks"]}

        def ctx(self, ref):
            if ref["sha256"] in task_refs:
                counts["task_context_lookups"] += 1
            return oldctx(self, ref)

        with (
            patch.object(Store, "__init__", init),
            patch.object(Store, "read_object_json", read),
            patch.object(candidates, "_records", records),
            patch.object(changes, "handoff", handoff),
            patch.object(workbench._ReadContext, "read", ctx),
        ):
            t = time.perf_counter()
            cpu = time.process_time()
            result = fn()
            row = {"n": n, "path": label, "wall": time.perf_counter() - t, "cpu": time.process_time() - cpu, **counts}
        results.append(row)
        print(row, flush=True)
(out / "measure.json").write_text(json.dumps(results, indent=2))
