#!/usr/bin/env python3
"""Run only after root's installed/heavy batch ends; never runs concurrently.

One fresh final-factory seed -> byte-identical independent clones -> original
W01 detached-service 100-warm-read/250ms gate, baseline then candidate.
No script thresholds, timings, background transitions, or assertions modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASELINE_SHA = 'b688c300dbb612bea9af8cf63a1743fb8136ae2c'
FACTORY_SHA = '072c88e47ec30bc440f2470bdf03975575175947'


def inventory(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--baseline-src', type=Path, required=True)
    parser.add_argument('--candidate-src', type=Path, required=True)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--repository', type=Path, default=Path('/workspace/Deck-Master'))
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)  # No overwrite/reuse of old evidence.
    factory = out / 'w01_pressure-final-factory.py'
    factory.write_bytes(subprocess.check_output(['git', '-C', str(args.repository), 'show',
        FACTORY_SHA + ':examples/workbench/w01_pressure.py']))
    identities = {'factory_sha': FACTORY_SHA,
        'factory_file_sha256': hashlib.sha256(factory.read_bytes()).hexdigest(),
        'runtime': {}, 'python': str(args.python.resolve()), 'runs': {}}
    environments = {}
    for name, source, sha in [('baseline', args.baseline_src, BASELINE_SHA),
                              ('candidate', args.candidate_src, args.candidate_sha)]:
        env = dict(os.environ, PYTHONPATH=str(source.resolve()))
        env.pop('DECK_MASTER_OPERATION_CACHE', None)  # Original default mode.
        env.pop('DECK_MASTER_SUMMARY_CACHE', None)
        environments[name] = env
        info = json.loads(subprocess.check_output([str(args.python), '-c',
            'import json,sys,deck_master.workbench as w,deck_master.service as s;'
            'print(json.dumps({"python":sys.version,"workbench":w.__file__,"service":s.__file__}))'],
            env=env, cwd=out, text=True))
        # Fail if PYTHONPATH selected an unintended installed/editable source.
        assert Path(info['workbench']).resolve().is_relative_to(source.resolve()), info
        assert Path(info['service']).resolve().is_relative_to(source.resolve()), info
        identities['runtime'][name] = {'source_sha': sha, 'source_directory': str(source.resolve()), **info}

    def run(name, args_list, env):
        with (out / (name + '.log')).open('w') as log:
            return subprocess.run([str(args.python), str(factory), *args_list],
                env=env, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode

    seed = out / 'seed'
    code = run('fixture-build', ['--out', str(seed), '--fixture-only'], environments['candidate'])
    assert code == 0, f'fixture build failed: {out / "fixture-build.log"}'
    manifest = json.loads((seed / 'manifest.json').read_text())
    assert (manifest['page_count'], manifest['candidate_count'], manifest['attempt_count']) == (300, 1500, 4500)
    assert len(manifest['background_task_ids']) == 150
    assert manifest['background_dispatch']['count'] == 150
    current = json.loads((seed / 'project/.deckmaster/current.json').read_text())
    document = json.loads((seed / 'project/.deckmaster/revisions' / (current['revision_id'] + '.json')).read_text())
    assert len(document['tasks']) == 1650
    assert 'design' in document['collaboration']['request']['scope']['layers']
    seed_files = inventory(seed)
    clones = {}
    for name in ('baseline', 'candidate'):
        clone = out / (name + '-fixture')
        shutil.copytree(seed, clone)
        assert inventory(clone) == seed_files
        clones[name] = clone
    (out / 'initial-file-hashes.json').write_text(json.dumps(seed_files, indent=2) + '\n')
    identities['fixture'] = {'seed': str(seed), 'page_count': 300, 'task_count': 1650,
        'candidate_count': 1500, 'attempt_count': 4500, 'history_versions':
        len(list((seed / 'project/.deckmaster/revisions').glob('*.json'))),
        'request_scope': document['collaboration']['request']['scope'],
        'clones_have_identical_initial_bytes': True,
        'manifest_sha256': hashlib.sha256((seed / 'manifest.json').read_bytes()).hexdigest()}
    (out / 'identities.json').write_text(json.dumps(identities, indent=2) + '\n')
    # These are intentionally sequential; W01 owns/reclaims its service.
    for name, sha in [('baseline', BASELINE_SHA), ('candidate', args.candidate_sha)]:
        result_dir = out / (name + '-result')
        code = run(name, ['--existing', str(clones[name]), '--out', str(result_dir),
            '--source-commit', sha, '--server-mode', 'detached'], environments[name])
        row = {'returncode': code, 'result_directory': str(result_dir)}
        measurements = result_dir / 'measurements.json'
        if measurements.exists():
            data = json.loads(measurements.read_text())
            row.update(p95_ms=data['p95_ms'], passed=data['passed'],
                threshold_ms=data['threshold_ms'], samples=len(data['samples']),
                sample_revision_count=len({sample['revision_id'] for sample in data['samples']}),
                service=data['service'])
            assert row['samples'] == 100 and row['threshold_ms'] == 250
        background = result_dir / 'background.json'
        if background.exists():
            row['background'] = json.loads(background.read_text())
        identities['runs'][name] = row
        (out / 'identities.json').write_text(json.dumps(identities, indent=2) + '\n')
        # On failure stop rather than starting a second measurement while the
        # previous service's cleanup outcome might be uncertain.
        if code:
            raise SystemExit(f'{name} failed; inspect {out / (name + ".log")} and cleanup before continuing')
    print(json.dumps(identities, indent=2))


if __name__ == '__main__':
    main()
