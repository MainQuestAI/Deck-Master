#!/usr/bin/env python3
"""Explicit 300 x 5 x 3 read-pressure fixture; no model or native Host claim.

PYTHONPATH=src python examples/workbench/w01_pressure.py --out <new-directory>
This factory is for read/UX performance only, never a production fallback.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
from io import BytesIO
import json
import math
from pathlib import Path
import platform
import subprocess
import threading
import time
import urllib.request

from PIL import Image, ImageDraw

from deck_master import candidates, production, service, tasks, workbench
from deck_master.models import (bump_revision, canonical_json_bytes, content_identity,
                                sha256_bytes, validate_schema, validate_task_semantics)
from deck_master.pipeline import artifact
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

SEED = 20260930
FACTORY = 'w01-pressure.v1'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def create_fixture(project, *, page_count=300):
    gallery = create_gallery_sample(project, page_count=page_count, readonly=True)
    store = Store(project); base = store.load_document(); doc = copy.deepcopy(base)
    doc['compatibility']['minimum_writer'] = 'candidates.v1'
    doc['candidates'] = []; doc['tasks'] = []
    produced = content_identity(base); outcomes = Counter(); image_sizes = []
    manifest_rows = []; tick = 1790726400000

    def put(kind, obj):
        validate_schema(kind, obj)
        return store.put_json_object(obj)

    for index, entry in enumerate(base['pages']):
        pid = entry['page_id']; page = store.read_object_json(entry['page'])
        design, _ = production.resolve_design(page, base['design_context'], [])
        prepared = production.project_prompt(page, design, [])
        prepared_ref = store.put_json_object(prepared)
        basis = candidates.generation_basis(store, base, pid, 'blueprint')
        refs = ([{'file': store.read_object_json(entry['blueprint'])['file'], 'role': 'reference'}]
                if entry.get('blueprint') else [])
        for variant in range(5):
            key = f'{SEED}-{pid}-{variant}'
            tid, cid = 'task-' + key, 'candidate-' + key
            request_input = {'schema_version': 'generation_input.v1',
                'prompt': f'Explicit synthetic pressure variant {variant}; no tool invocation.\n' + prepared['prompt'],
                'page': {'page_id': pid, 'page_ref': entry['page']}, 'design_context': design,
                'template_ref': None, 'references': refs, 'parameters': {'transparent_background': False},
                'constraints': {'fixture': FACTORY}, 'basis': {'project_id': base['project_id'],
                'revision_id': base['revision_id'], 'produced_against': produced}}
            request = {'schema_version': 'generation_request.v1', 'request_id': 'request-' + key,
                'task_id': tid, 'project_id': base['project_id'], 'operation_id': 'freeze-' + key,
                'input_hash': sha256_bytes(canonical_json_bytes(request_input)), 'input': request_input,
                'created_at_ms': tick + index * 50 + variant * 5}
            request_ref = put('generation_request', request)
            canvas = Image.new('RGB', (960, 540), '#f8faf9'); draw = ImageDraw.Draw(canvas)
            draw.text((50, 40), f'SYNTHETIC READ FIXTURE / {pid} / VARIANT {variant}', fill='#172c23')
            for column in range(3):
                x = 50 + column * 290
                color = (40 + variant * 25, 100 + column * 35, 70 + (index % 13) * 8)
                draw.rectangle((x, 140, x + 260, 410), fill=color)
                draw.text((x + 20, 220), f'STEP {column + 1} / SEED {SEED}', fill='white')
            raw = BytesIO(); canvas.save(raw, format='PNG'); data = raw.getvalue()
            image_sizes.append(len(data)); file_ref = store.put_blob(data, ext='png')
            art_ref = artifact(store, store.project_root / file_ref['path'], 'blueprint', page_id=pid,
                dependencies=[{'kind': 'content', 'identity': 'page:' + pid, 'sha256': entry['page']['sha256']}])
            art = store.read_object_json(art_ref)
            art['limitations'] = ['Synthetic read-pressure image; not a Host or model result.']
            art_ref = put('artifact', art)
            attempt_refs, allowances = [], []
            # Every candidate has one final success and two separately identified
            # prior outcomes. Unknown remains unknown; no native collector label.
            for number, outcome in enumerate([('failure', 'cancelled', 'unknown')[variant % 3],
                                               ('failure', 'cancelled', 'unknown')[(variant + 1) % 3], 'success']):
                aid = f'attempt-{key}-{number}'; allowance_id = f'call-{number + 1}'
                observation = {'schema_version': 'tool_observation.v1', 'observer': 'host_reported',
                    'collector': None, 'submitted': None, 'coverage': {'prompt': 'unknown', 'references': 'unknown'},
                    'output': None, 'invocation_ref': None, 'trust_scope': 'synthetic read-pressure fixture only',
                    'reported': {'fixture': FACTORY, 'attempt_id': aid, 'outcome': outcome,
                                 'description': 'Constructed data shape; no external call or provider receipt.'}}
                obs_ref = put('tool_observation', observation)
                attempt = {'schema_version': 'generation_attempt.v1', 'attempt_id': aid, 'task_id': tid,
                    'project_id': base['project_id'], 'request_ref': request_ref, 'allowance_id': allowance_id,
                    'execution_ref': 'synthetic-pressure', 'started_at_ms': request['created_at_ms'] + number + 1,
                    'previous_ref': None, 'observations': [obs_ref],
                    'output_refs': [file_ref] if outcome == 'success' else []}
                attempt_refs.append(put('generation_attempt', attempt)); outcomes[outcome] += 1
                allowances.append({'allowance_id': allowance_id,
                    'state': {'failure': 'consumed', 'cancelled': 'released', 'unknown': 'unknown', 'success': 'consumed'}[outcome],
                    'execution_ref': 'synthetic-pressure', 'invocation_ref': None, 'evidence': [obs_ref],
                    'evidence_level': 'host_reported'})
            candidate = {'schema_version': 'candidate.v1', 'candidate_id': cid, 'project_id': base['project_id'],
                'task_id': tid, 'created_at': '2026-09-30T00:00:00Z', 'page_id': pid, 'stage': 'blueprint',
                'base_revision': base['revision_id'], 'generation_basis': basis, 'request_ref': request_ref,
                'attempt_ref': attempt_refs[-1], 'target_ref': entry.get('blueprint'),
                'result_ref': art_ref, 'status': 'available'}
            candidate_ref = put('candidate', candidate)
            task = tasks.new_task(task_id=tid, operation_id='trial-' + key, kind='blueprint', scope_pages=[pid],
                instruction=request_input['prompt'], inputs=[entry['page'], prepared_ref],
                dependencies=[{'kind': 'content', 'identity': 'page:' + pid, 'sha256': entry['page']['sha256']}],
                dispatch_revision=base['revision_id'], produced_against=produced, status='completed',
                cost_class='external_generation', call_allowances=allowances)
            task.update(protocol_version='generation.v1', required_capabilities=['freeze_request', 'candidate_result'],
                generation_requests=[request_ref], generation_attempts=attempt_refs, candidate_refs=[candidate_ref],
                stage_request={'mode': 'trial', 'stage': 'blueprint', 'references': refs},
                result_refs=[art_ref, candidate_ref])
            validate_task_semantics(task)
            doc['tasks'].append(store.put_json_object(task)); doc['candidates'].append(candidate_ref)
            manifest_rows.append({'page_id': pid, 'candidate_id': cid, 'candidate_ref': candidate_ref,
                                  'task_id': tid, 'attempt_refs': attempt_refs, 'file': file_ref})
        if (index + 1) % 25 == 0:
            print(json.dumps({'fixture_pages_written': index + 1}), flush=True)
    # Ordinary core start/cancel operations on these tasks supply background
    # writes, while all Candidate/Attempt content remains immutable.
    background_ids = []
    for index in range(150):
        tid = f'pressure-background-{index:03}'; background_ids.append(tid)
        task = tasks.new_task(task_id=tid, operation_id=tid, kind='reconstruct', scope_pages=[base['pages'][index % page_count]['page_id']],
            instruction='Synthetic background reasoning task; no model call.', inputs=[], dependencies=[],
            dispatch_revision=base['revision_id'], produced_against=produced)
        doc['tasks'].append(store.put_json_object(task))
    updated = bump_revision(doc, {'operation_id': 'pressure-fixture', 'kind': 'task_update',
        'description': 'Explicit synthetic read-pressure dataset; no native Host evidence', 'read_set': []})
    store.commit_change(base_revision=base['revision_id'], document=updated, operation_id='pressure-fixture')
    counts = Counter(); object_bytes = 0
    for path in (store.deck_root / 'objects').glob('*/*'):
        data = path.read_bytes(); assert sha256_bytes(data) == path.stem
        object_bytes += len(data)
        if path.suffix == '.json':
            obj = json.loads(data); counts[obj.get('schema_version', 'other_json')] += 1
        else:
            counts[path.suffix] += 1
    assert len({r['candidate_id'] for r in manifest_rows}) == page_count * 5
    assert counts['generation_attempt.v1'] == page_count * 15
    for pid in (base['pages'][0]['page_id'], base['pages'][-1]['page_id']):
        result = candidates.listing(project, page_id=pid)
        assert len(result['candidates']) == 5
        shown = candidates.show(project, candidate_id=result['candidates'][0]['candidate']['candidate_id'])
        assert shown['request']['input']['page']['page_id'] == pid
    return {'factory': FACTORY, 'synthetic': True, 'model_calls': 0, 'native_host_evidence': False,
        'purpose': 'read-only performance data; not an executable generation history or production fallback',
        'seed': SEED, 'page_count': page_count, 'candidate_count': page_count * 5, 'attempt_count': page_count * 15,
        'outcomes': dict(outcomes), 'project_id': base['project_id'], 'base_revision': base['revision_id'],
        'fixture_revision': updated['revision_id'], 'source_dimensions': [960, 540],
        'candidate_image_bytes': {'min': min(image_sizes), 'max': max(image_sizes), 'total': sum(image_sizes)},
        'object_count': sum(counts.values()), 'object_bytes': object_bytes, 'object_types': dict(counts),
        'gallery': gallery, 'candidates': manifest_rows, 'background_task_ids': background_ids}


def sample(project, out, manifest):
    store = Store(project); server = WorkbenchServer(project); stop = threading.Event()
    available = {t['task_id'] for ref in store.load_document()['tasks']
                 if (t := store.read_object_json(ref))['status'] == 'awaiting_host'}
    updates, errors = [], []

    def background():
        try:
            for tid in manifest['background_task_ids']:
                if stop.is_set():
                    break
                if tid not in available:
                    continue
                started = time.perf_counter()
                result = service.task_start(project, task_id=tid, execution_ref='synthetic-pressure-background')
                updates.append({'task_id': tid, 'action': 'start', 'result': {k: result[k] for k in ('status', 'revision_id')}, 'elapsed_ms': (time.perf_counter() - started) * 1000})
                if stop.wait(.25):
                    break
                started = time.perf_counter()
                result = service.task_cancel(project, task_id=tid, reason='Synthetic background pressure transition')
                updates.append({'task_id': tid, 'action': 'cancel', 'result': {k: result[k] for k in ('status', 'revision_id')}, 'elapsed_ms': (time.perf_counter() - started) * 1000})
                if stop.wait(.25):
                    break
        except Exception as exc:
            errors.append(repr(exc)); stop.set()

    def request(url):
        started = time.perf_counter()
        with urllib.request.urlopen(url + '/api/view/summary', timeout=120) as response:
            data = json.loads(response.read())
        elapsed = (time.perf_counter() - started) * 1000
        assert data['page_count'] == manifest['page_count']
        assert data['candidates']['count'] == manifest['candidate_count']
        assert data['attempts']['count'] == manifest['attempt_count']
        return elapsed, data

    thread = threading.Thread(target=background, daemon=True)
    try:
        url = server.start().rstrip('/')
        cold_ms, _ = request(url)
        thread.start()
        for _ in range(5):
            request(url)
        rows = []
        for index in range(100):
            elapsed, data = request(url)
            rows.append({'index': index, 'ms': elapsed, 'revision_id': data['revision_id'], 'updates_completed': len(updates)})
            if (index + 1) % 10 == 0:
                print(json.dumps({'samples': index + 1, 'last_ms': elapsed, 'background_updates': len(updates)}), flush=True)
        # A separate instrumented read verifies lazy detail access without adding
        # instrumentation overhead to the latency samples.
        seen = Counter(); original = workbench._ReadContext.read
        def tracked(ctx, ref):
            obj = original(ctx, ref); seen[obj.get('schema_version', 'other')] += 1
            return obj
        workbench._ReadContext.read = tracked
        try:
            workbench.workbench_summary(project)
        finally:
            workbench._ReadContext.read = original
        assert not any(seen[k] for k in ('candidate.v1', 'generation_attempt.v1', 'generation_request.v1', 'tool_observation.v1'))
        assert not errors, errors
        assert len({row['revision_id'] for row in rows}) > 1
        times = sorted(row['ms'] for row in rows)
        result = {'measurement': 'loopback client request start through JSON parse', 'warmup': 5, 'samples': rows,
            'cold_ms': cold_ms, 'p50_ms': times[49], 'p95_ms': times[math.ceil(len(times) * .95) - 1],
            'p99_ms': times[98], 'max_ms': times[-1], 'background': updates,
            'background_errors': errors, 'summary_object_reads': dict(seen),
            'object_cache': workbench._cached_json.cache_info()._asdict(),
            'environment': {'os': platform.platform(), 'python': platform.python_version(), 'machine': platform.machine(),
                'hardware': subprocess.check_output(['sysctl', '-n', 'hw.model'], text=True).strip() if platform.system() == 'Darwin' else platform.machine(),
                'memory_bytes': int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True)) if platform.system() == 'Darwin' else __import__('os').sysconf('SC_PAGE_SIZE') * __import__('os').sysconf('SC_PHYS_PAGES'),
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'browser': None, 'viewport': None}, 'threshold_ms': 250, 'passed': times[94] <= 250}
        write_json(out / 'measurements.json', result)
        print(json.dumps({'p95_ms': result['p95_ms'], 'passed': result['passed']}), flush=True)
    finally:
        stop.set()
        if thread.is_alive():
            thread.join(timeout=120)
        server.stop()
        write_json(out / 'background.json', {'updates': updates, 'errors': errors})
    assert not thread.is_alive(), 'background writer did not stop'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fixture-only', action='store_true')
    parser.add_argument('--existing', type=Path, help='existing explicit pressure fixture root')
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    if args.existing:
        manifest = json.loads((args.existing / 'manifest.json').read_text()); project = args.existing / 'project'
        assert manifest['factory'] == FACTORY and manifest['synthetic'] is True
    else:
        project = args.out / 'project'; manifest = create_fixture(project)
    write_json(args.out / 'manifest.json', manifest)
    if not args.fixture_only:
        sample(project, args.out, manifest)


if __name__ == '__main__':
    main()
