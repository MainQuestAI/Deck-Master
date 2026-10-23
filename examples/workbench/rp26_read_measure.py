"""RP-26 repeated synthetic reads; never invokes models/renderers or changes HOME.

PYTHONPATH=src:tests/rebuild python examples/workbench/rp26_read_measure.py OUT \
    --workload-root SHARED --source-revision SHA
Cold clears named process caches before EVERY sample; it is not disk/process cold.
Warm clears those caches once, primes the exact call once, then measures repeats.
Reuse one immutable fixture tree across source versions. Results are compared in
full within each path/size; compare result hashes across matched source runs too.
"""

import argparse
import collections
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import patch
import deck_master
from deck_master import candidates, changes, workbench, ui_journal, snapshots
from deck_master import store as store_module
from deck_master.store import Store
from test_request_read_facts import scaled


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def files_digest(root):
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts})


def clear_caches():
    cleared = []
    for module, name in [(snapshots, '_cached_header'), (workbench, '_cached_json'),
                         (workbench, '_cached_overview_metadata'), (store_module, '_verified_small_json_bytes')]:
        fn = getattr(module, name, None)
        if fn is not None:
            fn.cache_clear()
            cleared.append(module.__name__ + '.' + name)
    workbench._summary_cache.clear()
    cleared.append('deck_master.workbench._summary_cache')
    return cleared


def measured(fn, updated):
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
        row = {"wall": time.perf_counter() - t, "cpu": time.process_time() - cpu, **counts}
    return row, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--workload-root', type=Path, required=True)
    parser.add_argument('--source-revision', required=True, help='Explicit archive/checkout revision; source bytes also hashed')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('at least three repeats are required')
    args.out.mkdir(parents=True, exist_ok=True)
    args.workload_root.mkdir(parents=True, exist_ok=True)
    results = []
    for n in [4, 8, 16]:
        root = args.workload_root / str(n)
        if not root.exists():
            root.mkdir()
            scaled(root, n)
        store = Store(root / 'decision-project')
        updated = store.load_document()
        input_digest = files_digest(root)
        for label, fn in [
            ('project', lambda: ui_journal.project_info(store.project_root)),
            ('candidates', lambda: candidates.listing(store.project_root, revision=updated['revision_id'])),
            ('changes', lambda: changes.list_changes(store.project_root)),
            ('lineage', lambda: workbench.page_lineage(store.project_root, 'p01', revision=updated['revision_id'])),
        ]:
            expected = None
            for mode in ['cold', 'warm']:
                caches = clear_caches()
                if mode == 'warm':
                    assert fn() == expected, (n, label, 'warmup changed facts')
                for repeat in range(args.repeats):
                    if mode == 'cold':
                        clear_caches()
                    row, result = measured(fn, updated)
                    if expected is None:
                        expected = result
                    assert result == expected, (n, label, mode, repeat, 'facts/refusals changed')
                    row.update(n=n, path=label, mode=mode, repeat=repeat,
                               input_digest=input_digest, revision_id=updated['revision_id'],
                               result_sha256=digest(result), cleared_caches=caches)
                    results.append(row)
            (args.out / f'{n}-{label}-result.json').write_text(json.dumps(expected, ensure_ascii=False, indent=2)+'\n')
            print(n, label, 'cold/warm facts equal', flush=True)
        assert files_digest(root) == input_digest, (n, 'benchmark mutated workload')
    metadata = {'source_revision': args.source_revision,
                'source_tree_sha256': files_digest(Path(deck_master.__file__).parent),
                'cold': 'named process caches cleared before each sample; OS/disk and Python imports remain warm',
                'warm': 'same caches cleared once; one untimed identical call before repeated samples',
                'repeats': args.repeats, 'rows': results}
    (args.out / 'measure.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    print(len(results), 'samples; immutable inputs and full results unchanged')


if __name__ == '__main__':
    main()
