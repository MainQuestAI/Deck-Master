"""Real POSIX process death and concurrent commit durability, beyond exceptions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from workflow import actions

WORKER = r'''
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from workflow import actions
root, mode = Path(sys.argv[2]), sys.argv[3]
def ready():
    print('READY', flush=True)
if mode == 'recover':
    before = actions.read_current_revision(root)
    state = {k:v.decode() for k,v in actions.read_revision_state(root).items()}
    receipt = actions.action_applied(root, 'change')
    result = actions.recover_projections(root)
    print(json.dumps(dict(before=before,state=state,receipt=receipt,recovery=result)))
    raise SystemExit
config = json.loads(sys.argv[4])
envelope = config['envelope']
if mode in ('before_pointer', 'after_pointer'):
    real = actions._atomic_json
    def atomic(path,payload):
        is_pointer = path == actions.revision_pointer_path(root)
        if is_pointer and mode == 'before_pointer':
            ready(); signal.pause()
        real(path,payload)
        if is_pointer and mode == 'after_pointer':
            ready(); signal.pause()
    actions._atomic_json = atomic
elif mode == 'partial_projection':
    real = Path.replace
    def replace(self,target):
        if Path(target) == root/'b':
            ready(); signal.pause()
        return real(self,target)
    Path.replace = replace
elif mode == 'concurrent':
    ready()
    while not Path(config['gate']).exists(): time.sleep(.01)
try:
    receipt=actions.commit_action_result(root,envelope,current_input_fingerprint='approved-fp',targets={k:root/k for k in config['files']},expected_revision=config.get('expected_revision'))
    print(json.dumps(dict(status=receipt['status'],receipt=receipt)),flush=True)
except actions.ActionStaleError as exc:
    print(json.dumps(dict(status='stale',error=str(exc))),flush=True)
'''

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='SIGKILL and flock acceptance requires POSIX')


def envelope(action):
    return actions.create_action_envelope(action_id=action, task_id='process-acceptance', scope_pages=['P001'], input_fingerprint='approved-fp')


def staged(root, action, files):
    value = envelope(action)
    actions.stage_action_result(root, value, files)
    return dict(envelope=value, files=list(files))


def baseline(root):
    root.mkdir()
    approved = root/'approved-input.json'
    approved.write_text('{"approval":"approved","sha256":"locked-original"}')
    config = staged(root, 'baseline', {'a':'old-a', 'b':'old-b'})
    receipt = actions.commit_action_result(root,config['envelope'],current_input_fingerprint='approved-fp',targets={k:root/k for k in config['files']})
    return receipt['revision_id'], hashlib.sha256(approved.read_bytes()).hexdigest()


def start(root, mode, config=None):
    return subprocess.Popen([sys.executable,'-u','-c',WORKER,str(SCRIPTS),str(root),mode,json.dumps(config or {})],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def ready(process):
    assert select.select([process.stdout],[],[],15)[0], 'worker did not reach durable boundary'
    assert process.stdout.readline().strip() == 'READY'


def finish(process):
    stdout,stderr=process.communicate(timeout=20)
    assert process.returncode == 0, stderr
    return json.loads(stdout.strip())


def evidence(root, result):
    (root.parent/'evidence.json').write_text(json.dumps(result,indent=2))


@pytest.mark.parametrize('boundary',['before_pointer','after_pointer','partial_projection'])
def test_sigkill_then_fresh_process_recovers_complete_revision(tmp_path,boundary):
    root=tmp_path/'run'
    old_revision,approved_hash=baseline(root)
    config=staged(root,'change',{'a':'new-a','b':'new-b'})
    config['expected_revision']=old_revision
    process=start(root,boundary,config)
    try:
        ready(process)
        if boundary == 'partial_projection':
            assert (root/'a').read_text() == 'new-a'
            assert (root/'b').read_text() == 'old-b'
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode == -signal.SIGKILL
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=10)
    # New interpreter proves recovery does not rely on surviving Python state.
    result=finish(start(root,'recover'))
    committed=boundary != 'before_pointer'
    assert (result['before']['revision_id'] != old_revision) == committed
    assert bool(result['receipt']) == committed
    assert result['state']['a'] == ('new-a' if committed else 'old-a')
    assert result['state']['b'] == ('new-b' if committed else 'old-b')
    assert all((root/k).read_text()==v for k,v in result['state'].items())
    assert hashlib.sha256((root/'approved-input.json').read_bytes()).hexdigest()==approved_hash
    assert hashlib.sha256(result['state']['approved-input.json'].encode()).hexdigest()==approved_hash
    result.update(boundary=boundary,termination_signal='SIGKILL',returncode=process.returncode,approved_sha256=approved_hash)
    evidence(root,result)
    if committed:
        assert actions.action_applied(root,'change')['input_fingerprint']=='approved-fp'
        assert finish(start(root,'replay',config))['status']=='already_applied'
    else:
        assert finish(start(root,'retry',config))['status']=='applied'


@pytest.mark.parametrize('cas',[True,False])
def test_two_real_commit_processes_serialize_without_lost_snapshot(tmp_path,cas):
    root=tmp_path/'run'
    old_revision,approved_hash=baseline(root)
    gate=tmp_path/'go'
    configs=[staged(root,'writer-a',{'a':'new-a'}),staged(root,'writer-b',{'b':'new-b'})]
    for config in configs:
        config['gate']=str(gate)
        if cas: config['expected_revision']=old_revision
    processes=[start(root,'concurrent',config) for config in configs]
    try:
        for process in processes: ready(process)
        gate.write_text('go')
        results=[finish(process) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None: process.kill(); process.wait(timeout=10)
    assert sorted(r['status'] for r in results)==(['applied','stale'] if cas else ['applied','applied'])
    state=actions.read_revision_state(root)
    if cas:
        winner=next(r['receipt']['action_id'] for r in results if r['status']=='applied')
        assert (state['a'],state['b'])==((b'new-a',b'old-b') if winner=='writer-a' else (b'old-a',b'new-b'))
    else:
        assert (state['a'],state['b'])==(b'new-a',b'new-b')
        assert all(actions.action_applied(root,c['envelope']['action_id']) for c in configs)
    assert hashlib.sha256(state['approved-input.json']).hexdigest()==approved_hash
    restarted=finish(start(root,'recover'))
    assert all((root/k).read_text()==v for k,v in restarted['state'].items())
    evidence(root,dict(cas=cas,results=results,restarted=restarted,approved_sha256=approved_hash))
