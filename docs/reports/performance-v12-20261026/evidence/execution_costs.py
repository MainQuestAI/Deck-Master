#!/usr/bin/env python3
"""Isolated synthetic #202/#203/#205 probes, executable unchanged on both trees.

Use PYTHONPATH=<tree>/src:<tree>/tests/rebuild python execution_costs.py
  --case all --out <new-directory> --label <actual-source-identity>
No renderer, external call, browser, or production permission is simulated.
Timing and work counters run separately. Fixture setup is outside timing.
"""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
from unittest.mock import patch

from deck_master import candidate_preview as preview, exports
from deck_master.local_state import write_json
from deck_master.models import bump_revision, new_document, require_writer, validate_task_semantics
from deck_master.store import Store
from deck_master.tasks import new_task


def clock(call):
    wall, cpu = time.perf_counter(), time.process_time()
    result = call()
    return result, {'wall_ms': (time.perf_counter() - wall) * 1000,
                    'cpu_ms': (time.process_time() - cpu) * 1000}


def empty_store(root, writer=None):
    store = Store(root)
    doc = new_document(project_id='synthetic-cost-probe', task={'title': 'Synthetic cost probe'})
    if writer:
        require_writer(doc, writer)
    store.init_project(doc, operation_id=doc['change']['operation_id'])
    return store, doc


def preview_costs(root):
    # Same fixed-context boundary as test_candidate_preview_recovery.context;
    # this measures cache bytes only, not fonts/context or renderer correctness.
    from test_candidate_preview_recovery import cached_report, state_path
    store, _ = empty_store(root / 'project')
    identity = {'candidate_ref': {'sha256': 'candidate'}}
    context = (store, {}, {}, {}, {}, {}, b'', {}, {}, identity, 'a' * 64)
    report = cached_report(context)
    folder = state_path(context).parent
    raw = b'x' * (8 * 1024 * 1024)
    digest = hashlib.sha256(raw).hexdigest()
    for name in preview._FILES:
        (folder / name).write_bytes(raw)
        report['files'][name] = {'sha256': digest, 'bytes': len(raw)}
    del raw
    write_json(folder / 'report.json', report)
    write_json(state_path(context), {'status': 'ready', 'cache_key': context[-1], 'check_id': report['check_id']})
    actions = {
        'ordinary_cached': lambda: preview._cached(store, context[-1], identity),
        'target_download': lambda: preview.file_bytes(store.project_root, cache_key=context[-1], name='candidate.png'),
        'freeze': lambda: preview.freeze_check(store, 'candidate'),
    }
    result = {}
    with patch.object(preview, '_context', lambda *a, **kw: context):
        for name, action in actions.items():
            # The fixed context is a common fixture boundary, not a work probe.
            value, timing = clock(action)
            if name == 'ordinary_cached':
                assert value == report
            elif name == 'target_download':
                assert len(value[0]) == 8 * 1024 * 1024 and hashlib.sha256(value[0]).hexdigest() == digest
            else:
                frozen = store.read_object_json(value)
                assert set(frozen['files']) == set(preview._FILES)
                for item in frozen['files'].values():
                    assert hashlib.sha256(store.read_object_bytes(item['file'])).hexdigest() == digest
            del value
            reads = Counter()
            original = Path.read_bytes
            def counted(path):
                data = original(path)
                if path.parent == folder and path.name in preview._FILES:
                    reads[path.name] += 1
                    reads['physical_bytes'] += len(data)
                return data
            with patch.object(Path, 'read_bytes', counted):
                action()
            gc.collect()
            tracemalloc.start()
            try:
                action()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            result[name] = {'unprobed_timing': timing, 'separate_counts': dict(reads),
                            'separate_tracemalloc_peak_bytes': peak}
    return {'boundary': '4 x 8 MiB fixed context; no font/tool identity or renderer measurement', 'results': result}


def writer_case(root, size, writer, counts):
    store, doc = empty_store(root, writer)
    task = new_task(task_id='synthetic-check', operation_id='synthetic-task', kind='check',
        scope_pages=[], instruction='x' * size, inputs=[], dependencies=[],
        dispatch_revision=doc['revision_id'], produced_against='0' * 64)
    if writer is None:
        task.pop('method_manifest', None)
        task.pop('method_release', None)
        validate_task_semantics(task)
    ref = store.put_json_object(task)
    updated = bump_revision(doc, {'operation_id': 'synthetic-classify', 'kind': 'task_update',
        'description': 'Synthetic classification measurement', 'read_set': []})
    updated['tasks'] = [ref]
    reads = Counter()
    original = store.read_object_bytes
    def counted(value):
        data = original(value)
        if value == ref:
            reads['task_reads'] += 1
            reads['task_bytes'] += len(data)
        return data
    # Directly time the existing commit body under its real lock: lock wait is
    # excluded; validation, CAS, writes and fsync remain included. Counts use a
    # different fresh project and are never advertised as unprobed timing.
    with patch.object(store, 'read_object_bytes', counted) if counts else patch.object(store, 'read_object_bytes', original):
        with store._locked():
            _, timing = clock(lambda: store._commit_locked(base_revision=doc['revision_id'],
                document=updated, operation_id='synthetic-classify', blobs=[]))
    actual = store.load_document()
    return {'timing' if not counts else 'ignored_instrumented_timing': timing,
            'counts': dict(reads), 'minimum_writer': actual.get('compatibility', {}).get('minimum_writer')}


def writer_costs(root):
    rows = []
    for size in (20 * 1024, 100 * 1024):
        for writer in (None, 'asset-inputs.v1'):
            label = f'{size}-{writer or "legacy"}'
            timing = [writer_case(root / f'{label}-time-{n}', size, writer, False) for n in range(3)]
            counts = writer_case(root / f'{label}-counts', size, writer, True)
            assert all(row['minimum_writer'] == counts['minimum_writer'] for row in timing)
            rows.append({'instruction_bytes': size, 'initial_writer': writer,
                'unprobed_locked_commit_samples': [row['timing'] for row in timing],
                'median_cpu_ms': statistics.median(row['timing']['cpu_ms'] for row in timing),
                'separate_counts': counts['counts'], 'minimum_writer': counts['minimum_writer']})
    return {'boundary': 'whole _commit_locked body, not classification-only CPU; lock acquisition/setup excluded', 'results': rows}


def export_costs(root):
    from test_versioned_exports import project
    rows = []
    for count in (14, 44, 104):
        case = root / str(count)
        case.mkdir(parents=True)
        project_root, _ = project(case)
        original_write = exports._write_public
        # Retain real review export generation/manifest/zip validation. Add
        # declared synthetic text files only during fixture generation, to
        # isolate file-count scaling independently of page/rendering cost.
        def write_public(store, doc, target, report):
            originals = original_write(store, doc, target, report)
            current = sum(p.is_file() for p in target.rglob('*'))
            assert current <= count - 2
            for n in range(count - 2 - current):
                (target / f'synthetic-{n:03}.txt').write_text(f'Synthetic immutable copy fixture {n}\n')
            return originals
        with patch.object(exports, '_write_public', write_public):
            record = exports.create(project_root, purpose='review')
        assert len(record['files']) == count
        def copy_to(name):
            return exports.create(project_root, purpose='review', export_id=record['export_id'], output_dir=case / name)
        timings = [clock(lambda n=n: copy_to(f'timing-{n}'))[1] for n in range(3)]
        counters = Counter()
        original_record, loads = exports._record, json.loads
        class Entries(list):
            def __iter__(self):
                for item in super().__iter__():
                    counters['manifest_entry_visits'] += 1
                    yield item
        def counted_loads(*args, **kwargs):
            value = loads(*args, **kwargs)
            if isinstance(value, dict) and 'manifest' in value and value.get('export_id') == record['export_id']:
                value['manifest']['files'] = Entries(value['manifest']['files'])
            return value
        def counted_record(*args, **kwargs):
            counters['record_validations'] += 1
            return original_record(*args, **kwargs)
        with patch.object(exports, '_record', counted_record), patch.object(json, 'loads', counted_loads):
            copy_to('counts')
        for name, expected in record['files'].items():
            data = (case / 'counts' / name).read_bytes()
            assert len(data) == expected['size'] and hashlib.sha256(data).hexdigest() == expected['sha256']
        rows.append({'files_including_manifest_archive': count, 'manifest_files': len(record['manifest']['files']),
            'unprobed_timing_samples': timings, 'separate_counts': dict(counters)})
    return {'boundary': 'existing review export reuse+copy; synthetic filler text; entry visits include validation/serialization', 'results': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('all', '202', '203', '205'), default='all')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    result = {'label': args.label, 'python': sys.version, 'platform': platform.platform(),
        'module_files': {name: module.__file__ for name, module in [('candidate_preview', preview), ('exports', exports)]},
        'synthetic': True, 'results': {}}
    for number, function in [('202', preview_costs), ('203', writer_costs), ('205', export_costs)]:
        if args.case in ('all', number):
            result['results'][number] = function(args.out / number)
            (args.out / 'measurements.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
