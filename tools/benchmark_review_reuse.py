"""RP-27 synthetic diagnostics. PYTHONPATH needs src and tests/rebuild.

Reuse --workload-root for both sources. Cold clears process header cache only;
no renderer/model calls or disk-cache flush. Three observations per condition.
"""

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from deck_master import editing, exports, review, snapshots, stages, delivery_eligibility
from deck_master.models import bump_revision
from deck_master.store import Store
from review_reuse_helpers import assembled_inputs
from test_export import _passing_deck
from test_review import make_document, make_review, finding, ref, current_artifacts, PAGE_REF, PPTX_REF


def closure_input(n):
    records = []
    for i in range(n):
        owner = make_review(
            "content",
            seed=str(i),
            subjects=[ref("old-page"), ref("old-ppt")],
            findings=[finding("shared")],
            dependencies=[{"kind": "content", "identity": "page:p1", "sha256": ref("old-page")["sha256"]}],
        )
        owner["ref"] = ref("owner-" + str(i))
        records.append(owner)
        previous = owner
        for j in range(n):
            current = j == n - 1 and i % 2 == 0
            record = make_review(
                "content",
                seed=str(i),
                replaces=previous["ref"],
                subjects=[PAGE_REF, PPTX_REF] if current else [ref("intermediate-page"), ref("intermediate-ppt")],
                findings=[finding("shared", resolution="fixed" if current else "open", evidence=[ref("evidence")])],
                dependencies=None
                if current
                else [{"kind": "content", "identity": "page:p1", "sha256": ref("intermediate-page")["sha256"]}],
            )
            record["ref"] = ref(f"owner-{i}-history-{j}")
            records.append(record)
            previous = record
    return records


def measured(fn, cold):
    if cold:
        snapshots._cached_header.cache_clear()
    counts = {"graphs": 0, "page_checks": 0, "closure_checks": 0, "replacement_indexes": 0, "object_reads": 0}

    def wrap(name, original):
        def counted(*args, **kwargs):
            counts[name] += 1
            return original(*args, **kwargs)

        return counted

    with ExitStack() as stack:
        for obj, attr, name in [
            (editing, "_current_artifact_digests", "graphs"),
            (review, "evaluate_page_visual", "page_checks"),
            (review, "finding_closed", "closure_checks"),
            (Store, "read_object_json", "object_reads"),
        ]:
            stack.enter_context(patch.object(obj, attr, wrap(name, getattr(obj, attr))))
        if hasattr(review, "replacement_index"):
            stack.enter_context(patch.object(review, "replacement_index", wrap("replacement_indexes", review.replacement_index)))
        cpu = time.process_time()
        wall = time.perf_counter()
        result = fn()
        counts.update(cpu_ms=round((time.process_time() - cpu) * 1000, 3), wall_ms=round((time.perf_counter() - wall) * 1000, 3))
    if not hasattr(review, "replacement_index"):
        counts["replacement_indexes"] = counts["closure_checks"]
    return counts, result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workload-root", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.workload_root.mkdir(parents=True, exist_ok=True)
rows = []
for n in (4, 8, 16):
    project = args.workload_root / str(n)
    if not project.exists():
        assembled_inputs(project, n)
    store = Store(project)
    doc = store.load_document()
    records = closure_input(n)
    workloads = {
        "assembly": lambda: stages.require_assembly_ready(store, doc),
        "multiowner_history": lambda: review.evaluate_current(make_document(), records, current_artifacts()),
    }
    for name, fn in workloads.items():
        for mode in ("cold", "warm"):
            if mode == "warm":
                fn()
            for rep in range(3):
                counts, result = measured(fn, mode == "cold")
                rows.append({"N": n, "workload": name, "mode": mode, "repeat": rep, **counts, "result": result})
root = args.workload_root / "delivery"
root.mkdir(exist_ok=True)
projects = sorted(root.glob("rc3-*"))
if not projects:
    _, store = _passing_deck(root, notes="Synthetic fixed speaker notes")
    doc = store.load_document()
    doc = bump_revision(doc, {"operation_id": "strict", "kind": "policy_update", "description": "Synthetic strict policy", "read_set": []})
    doc["policy"]["professional_review_required_for_delivery"] = True
    store.commit_change(base_revision=doc["parent_revision_id"], document=doc, operation_id="strict")
store = Store(next(root.glob("rc3-*")))
doc = store.load_document()
for notes in ("pptx_notes", "pure_reading"):
    selected = delivery_eligibility.selected_output(store, doc, notes_policy=notes)
    for mode in ("cold", "warm"):
        fn = lambda: exports._facts(store, doc, control=doc, selected_output=selected)
        if mode == "warm":
            fn()
        for rep in range(3):
            counts, result = measured(fn, mode == "cold")
            rows.append({"N": 1, "workload": "strict_delivery_" + notes, "mode": mode, "repeat": rep, **counts, "result": result})
args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
print(len(rows), "samples")
