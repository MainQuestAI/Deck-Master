"""Narrow PERF-200 experiment: formal synthetic tasks, one fixture, two readers.

Not run by its author. Build only in a NEW scratch root. The fixture uses explicit
L1 synthetic permissions and local SVG result bytes: no customer data, model,
renderer, external call, adoption, or professional approval is involved.

Example orchestration (run sequentially, outside heavy test batches):
  python measure_runs_legal.py build --repo /workspace/Deck-Master --root NEW_ROOT
  python measure_runs_legal.py read --repo BASELINE_REPO --manifest NEW_ROOT/manifest.json --out baseline.json
  python measure_runs_legal.py read --repo CANDIDATE_REPO --manifest NEW_ROOT/manifest.json --out candidate.json
  python measure_runs_legal.py compare --baseline baseline.json --candidate candidate.json --out comparison.json

Use the same Python executable/environment for both read commands. Three warm
samples are observations, not p95. Probes run separately and their timing is not
reported as an uninstrumented measurement. No copied heavy-scope fixture is made.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime as RealDateTime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from unittest.mock import patch


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def tree_identity(root):
    """Once per run boundary, never in the timed/probed query."""
    rows = []
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root).as_posix()
        if file.is_symlink():
            rows.append([relative, 'symlink', os.readlink(file)])
        elif file.is_file():
            raw = file.read_bytes()
            rows.append([relative, len(raw), hashlib.sha256(raw).hexdigest()])
    return {'digest': digest(rows), 'files': len(rows), 'bytes': sum(row[1] for row in rows if isinstance(row[1], int))}


def source_identity(repo):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
    # Source identity is calculated once, before measurements. Exclude ignored
    # generated output through git's own tracked/untracked file selection.
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=repo).split(b'\0')
    rows = []
    for raw_path in sorted(set(paths) - {b''}):
        name = os.fsdecode(raw_path)
        file = repo/name
        if file.is_symlink():
            rows.append([name, 'symlink', os.readlink(file)])
        elif file.is_file():
            rows.append([name, hashlib.sha256(file.read_bytes()).hexdigest()])
        else:
            rows.append([name, 'missing'])
    import deck_master
    origin = Path(deck_master.__file__).resolve()
    assert origin.is_relative_to(repo/'src'), origin
    return {'source_sha': git('rev-parse', 'HEAD'), 'source_tree_sha': git('rev-parse', 'HEAD^{tree}'),
            'dirty_fingerprint': digest(rows), 'git_status': git('status', '--porcelain'),
            'loaded_module_origin': str(origin), 'python': sys.version, 'executable': sys.executable,
            'platform': platform.platform(), 'operation_cache_env': os.environ.get('DECK_MASTER_OPERATION_CACHE', '1')}


def import_repo(repo, include_fixtures=False):
    repo = repo.resolve()
    if include_fixtures:
        sys.path.insert(0, str(repo/'tests/rebuild'))
    sys.path.insert(0, str(repo/'src'))
    return repo


def build(args):
    repo = import_repo(args.repo, include_fixtures=True)
    from test_run_desk import store as fixture
    from test_candidates import dispatch, start, accept
    from rc3_fixtures import authorize_scope, evidence_for
    from deck_master.models import validate_task_semantics, validate_document_semantics
    if args.root.exists():
        raise ValueError('Fixture root must not already exist; no overwrite or reuse-by-rebuild')
    args.root.mkdir(parents=True)
    source = source_identity(repo)
    built = []
    latest = []
    for total in (25, 200):
        location = args.root/str(total)
        location.mkdir()
        store = fixture.__wrapped__(location)
        original = store.load_document()
        initial_count = len(original['tasks'])
        assert initial_count < total-3, (initial_count, total)
        scope = dict(original['collaboration']['request']['scope'])
        scope.update(page_ids=['p01', 'p02'], layers=['blueprint', 'svg'])
        authorization = authorize_scope(store.project_root,
            actions=['change.commit', 'candidate.adopt', 'dispatch.blueprint', 'allowance.allocate', 'call.begin'],
            scope=scope, max_external_calls=0, max_candidate_count=total,
            adoption_policy='within_scope', evidence=evidence_for(store.project_root,
                text=f'L1 SYNTHETIC PERF-200: at most {total} local SVG trials on p01/p02 for read-only pagination measurement; zero external calls; no model or customer input; no adoption requested.',
                locator=f'L1:performance-v12:runs:{total}:bounded-grant'))
        created = []
        for index in range(total-initial_count):
            task = dispatch(store, page='p01' if index % 2 == 0 else 'p02', mode='trial', layer='svg')
            created.append(task)
        # Exercise a running task and two formally returned candidates. Returned
        # SVG is explicitly synthetic (test_candidates.envelope provenance).
        start(store, created[-3])
        candidate_ids = []
        for task in created[-2:]:
            start(store, task)
            outcome = accept(store, task)
            candidate_ids.extend(outcome['candidate_ids'])
        doc = store.load_document()
        validate_document_semantics(doc)
        task_values = [store.read_object_json(ref) for ref in doc['tasks']]
        for task in task_values:
            validate_task_semantics(task)
            for key in ('created_at', 'updated_at', 'execution_started_at'):
                if task.get(key):
                    latest.append(RealDateTime.fromisoformat(task[key].replace('Z', '+00:00')))
        assert len(task_values) == total
        assert len(candidate_ids) == 2
        assert all(len(task['scope_pages']) == 1 for task in task_values if task['task_id'] in {item['task_id'] for item in created})
        assert all(not task.get('generation_attempts') for task in task_values)
        built.append({'task_count': total, 'project': str(store.project_root.resolve()),
            'page_count': len(doc['pages']), 'initial_task_count': initial_count,
            'formally_dispatched_trial_count': len(created), 'returned_candidate_ids': candidate_ids,
            'task_states': dict(Counter(task['status'] for task in task_values)),
            'task_kinds': dict(Counter(task['kind'] for task in task_values)),
            'task_scope_lengths': dict(Counter(len(task['scope_pages']) for task in task_values)),
            'current_pointer': store.read_current(), 'document_digest': digest(doc),
            'fixture_identity': tree_identity(store.project_root),
            'authorization_response_digest': digest(authorization)})
    frozen = max(latest)+timedelta(seconds=1)
    manifest = {'scenario': 'S05_PERF_200_legal_formal_trials', 'source': source,
        'evidence_level': 'L1_SYNTHETIC', 'customer_data': False, 'model_invocations': 0,
        'external_calls': 0, 'professional_evidence': 'not_evaluated',
        'fixture_construction': 'Existing run_desk fixture plus explicit bounded synthetic grant, formal change dispatch, claim, and local synthetic SVG acceptance; no direct Task cloning or bypassed validation.',
        'setup_excluded_from_read_timing': True, 'clock_utc': frozen.isoformat(), 'fixtures': built,
        'copied_heavy_scope': {'status': 'not_measured', 'reason': 'Separate workload; not substituted for these legal single-page formal tasks.'}}
    save(args.root/'manifest.json', manifest)


def query_probe(query, modules):
    """Specific counters for this experiment; no changes to business results."""
    run_desk, relationships, candidates, workbench, operations, snapshots, Store = modules
    counts = Counter()
    def wrap(obj, name, counter, extra=None):
        original = getattr(obj, name)
        def counted(*args, **kwargs):
            counts[counter] += 1
            if extra:
                extra(args, kwargs)
            return original(*args, **kwargs)
        stack.enter_context(patch.object(obj, name, counted))
    def task_miss(args, kwargs):
        owner, task = args[:2]
        counts['relationship_task_cache_misses'] += int(task['task_id'] not in owner.task_cache)
    def candidate_miss(args, kwargs):
        owner, candidate = args[:2]
        counts['relationship_candidate_cache_misses'] += int(candidate.get('candidate_id') not in owner.candidate_cache)
    def snapshot_miss(args, kwargs):
        owner, revision = args[:2]
        counts['context_snapshot_cache_misses'] += int(revision not in owner.snapshots)
    def operation_miss(args, kwargs):
        owner, revision = args[:2]
        counts['operation_snapshot_cache_misses'] += int(revision not in owner.documents)
    with ExitStack() as stack:
        wrap(run_desk, 'task_row', 'full_row_assemblies')
        wrap(relationships.CurrentRelationships, '__init__', 'relationship_contexts')
        wrap(relationships.CurrentRelationships, 'task', 'relationship_task_calls', task_miss)
        wrap(relationships.CurrentRelationships, 'candidate', 'relationship_candidate_calls', candidate_miss)
        wrap(relationships.CurrentRelationships, 'pending_candidates', 'pending_candidate_calls')
        wrap(candidates, 'basis_state', 'candidate_basis_evaluations')
        wrap(candidates, 'inputs_current', 'candidate_inputs_current_evaluations')
        wrap(workbench._ReadContext, 'read_snapshot', 'context_snapshot_calls', snapshot_miss)
        wrap(operations.OperationReader, '__init__', 'operation_readers')
        wrap(operations.OperationReader, 'snapshot', 'operation_snapshot_calls', operation_miss)
        wrap(snapshots, 'snapshot_evidence', 'snapshot_full_evidence_reads')
        wrap(snapshots, 'snapshot_signature', 'snapshot_signature_calls')
        wrap(Store, 'load_document', 'store_document_loads')
        wrap(Store, 'read_object_json', 'store_json_reads')
        original_read = Store.read_object_bytes
        def counted_bytes(*args, **kwargs):
            raw = original_read(*args, **kwargs)
            counts['store_object_byte_reads'] += 1
            counts['store_object_bytes_returned'] += len(raw)
            return raw
        stack.enter_context(patch.object(Store, 'read_object_bytes', counted_bytes))
        result = query()
    # These labels are business work counts. Bytes through workbench._cached_json
    # are not all routed through Store, so do not call this total physical I/O.
    keys = ['full_row_assemblies','relationship_contexts','relationship_task_calls','relationship_task_cache_misses',
        'relationship_candidate_calls','relationship_candidate_cache_misses','pending_candidate_calls',
        'candidate_basis_evaluations','candidate_inputs_current_evaluations','context_snapshot_calls','context_snapshot_cache_misses',
        'operation_readers','operation_snapshot_calls','operation_snapshot_cache_misses','snapshot_full_evidence_reads',
        'snapshot_signature_calls','store_document_loads','store_json_reads','store_object_byte_reads','store_object_bytes_returned']
    return {name: counts[name] for name in keys}, result


def read(args):
    repo = import_repo(args.repo)
    from deck_master import run_desk, current_relationship, candidates, workbench, operations, snapshots
    from deck_master.store import Store
    manifest = json.loads(args.manifest.read_text())
    source = source_identity(repo)
    fixed = RealDateTime.fromisoformat(manifest['clock_utc'])
    class FixedReadDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz is not None else fixed.replace(tzinfo=None)
        @classmethod
        def utcnow(cls):
            return fixed.astimezone(timezone.utc).replace(tzinfo=None)
    rows, errors = [], []
    responses_dir = args.out.parent/(args.out.stem+'-responses')
    if args.out.exists() or responses_dir.exists():
        raise ValueError('Output must be new; do not overwrite earlier evidence')
    report = {'scenario': manifest['scenario'], 'source': source,
        'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'clock_utc': manifest['clock_utc'],
        'clock_scope': ['run_desk.datetime: listing and task-row live timeout judgment', 'workbench.datetime: same captured read clock for context module'],
        'clock_policy': 'Same explicit instant in both readers, after fixture task updates. datetime parsing and timeout predicates unchanged; perf_counter/process_time stay real. These listing paths have no other wall-clock source.',
        'samples_per_condition': 3, 'p95': None, 'timing_scope': 'one in-process run_desk.listing call; warm process, no probe; no HTTP/browser/setup',
        'instrumentation_timing_included': False, 'copied_heavy_scope': manifest['copied_heavy_scope'],
        'rows': rows, 'errors': errors, 'fixture_checks': []}
    with ExitStack() as clock:
        clock.enter_context(patch.object(run_desk, 'datetime', FixedReadDateTime))
        clock.enter_context(patch.object(workbench, 'datetime', FixedReadDateTime))
        for fixture in manifest['fixtures']:
            project = Path(fixture['project'])
            before = tree_identity(project)
            store = Store(project)
            before_pointer = store.read_current()
            assert before == fixture['fixture_identity'], 'Fixture bytes differ before measurement'
            assert before_pointer == fixture['current_pointer'], 'Fixture current differs before measurement'
            for attention in (False, True):
                for limit in (1, 30, 100):
                    condition = f"tasks-{fixture['task_count']}-attention-{int(attention)}-limit-{limit}"
                    query = lambda: run_desk.listing(project, limit=limit, attention=attention)
                    query()  # Warmup is explicit and not a timing sample.
                    samples = []
                    reference = None
                    for index in range(3):
                        cpu = time.process_time()
                        wall = time.perf_counter()
                        value = query()
                        elapsed_wall = time.perf_counter()-wall
                        elapsed_cpu = time.process_time()-cpu
                        samples.append({'sample': index, 'wall_seconds': elapsed_wall,
                            'service_cpu_seconds': elapsed_cpu, 'functional_result_digest': digest(value)})
                        if reference is None:
                            reference = value
                        elif value != reference:
                            path = responses_dir/(condition+f'-changed-sample-{index}.json')
                            save(path, value)
                            errors.append({'condition': condition, 'error': 'uninstrumented_response_changed', 'sample': index, 'response': str(path)})
                    counts, probed = query_probe(query, (run_desk, current_relationship, candidates, workbench, operations, snapshots, Store))
                    if probed != reference:
                        path = responses_dir/(condition+'-probe-difference.json')
                        save(path, probed)
                        errors.append({'condition': condition, 'error': 'probe_changed_response', 'response': str(path)})
                    path = responses_dir/(condition+'.json')
                    save(path, reference)
                    rows.append({'condition': condition, 'fixture_digest': before['digest'], 'task_count': fixture['task_count'],
                        'attention': attention, 'limit': limit, 'samples': samples, 'counts': counts,
                        'functional_result_digest': digest(reference), 'full_response': str(path.resolve()),
                        'pagination': reference['pagination'], 'status_counts': reference['counts']})
            after = tree_identity(project)
            after_pointer = store.read_current()
            report['fixture_checks'].append({'task_count': fixture['task_count'], 'before': before, 'after': after,
                'pointer_before': before_pointer, 'pointer_after': after_pointer,
                'unchanged': before == after and before_pointer == after_pointer})
            if before != after or before_pointer != after_pointer:
                errors.append({'task_count': fixture['task_count'], 'error': 'fixture_changed_during_read'})
    report['status'] = 'observed' if not errors else 'failed'
    save(args.out, report)
    return int(bool(errors))


def differences(a, b, path='$'):
    if type(a) is not type(b):
        return [{'path': path, 'baseline': a, 'candidate': b}]
    if isinstance(a, dict):
        result = []
        for key in sorted(set(a)|set(b)):
            if key not in a or key not in b:
                result.append({'path': path+'.'+key, 'baseline_present': key in a, 'candidate_present': key in b})
            else:
                result.extend(differences(a[key], b[key], path+'.'+key))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': path, 'baseline_length': len(a), 'candidate_length': len(b)}]
        return [item for i, (first, second) in enumerate(zip(a, b)) for item in differences(first, second, f'{path}[{i}]')]
    return [] if a == b else [{'path': path, 'baseline': a, 'candidate': b}]


def compare(args):
    before = json.loads(args.baseline.read_text())
    after = json.loads(args.candidate.read_text())
    assert before['manifest_sha256'] == after['manifest_sha256'], 'Different fixture manifests'
    assert before['clock_utc'] == after['clock_utc'], 'Different read clocks'
    assert before['source']['executable'] == after['source']['executable'], 'Use the same Python environment'
    left = {row['condition']: row for row in before['rows']}
    right = {row['condition']: row for row in after['rows']}
    assert left.keys() == right.keys(), 'Different condition sets'
    rows, mismatches = [], []
    for key, first in left.items():
        second = right[key]
        a = json.loads(Path(first['full_response']).read_text())
        b = json.loads(Path(second['full_response']).read_text())
        delta = differences(a,b)
        if delta:
            mismatches.append({'condition': key, 'differences': delta})
        rows.append({'condition': key, 'full_response_equal': a == b,
            'baseline_digest': digest(a), 'candidate_digest': digest(b),
            'baseline_counts': first['counts'], 'candidate_counts': second['counts'],
            'baseline_samples': first['samples'], 'candidate_samples': second['samples']})
    passed = not mismatches and not before['errors'] and not after['errors']
    save(args.out, {'status': 'equivalent_observations' if passed else 'response_or_run_failure',
        'note': 'Full unfiltered response equality; no fields normalized or omitted. Three samples are not p95.',
        'baseline_source': before['source'], 'candidate_source': after['source'],
        'clock_utc': before['clock_utc'], 'manifest_sha256': before['manifest_sha256'],
        'rows': rows, 'mismatches': mismatches, 'baseline_errors': before['errors'], 'candidate_errors': after['errors']})
    return int(not passed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build'); p.add_argument('--repo', type=Path, required=True); p.add_argument('--root', type=Path, required=True)
    p = sub.add_parser('read'); p.add_argument('--repo', type=Path, required=True); p.add_argument('--manifest', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('compare'); p.add_argument('--baseline', type=Path, required=True); p.add_argument('--candidate', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    return {'build': build, 'read': read, 'compare': compare}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
