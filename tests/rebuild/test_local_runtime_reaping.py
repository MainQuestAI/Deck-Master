"""A live launcher reaps only its own exited detached service children."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux /proc zombie regression')

WORKER = r'''
import json, os, subprocess, sys, time
from pathlib import Path
from deck_master import local_runtime
path = Path(sys.argv[1])
desc = local_runtime.descriptor(registry=path)
state = local_runtime.ensure(desc)
pid = state['pid']
assert local_runtime.healthy(state, desc)
assert local_runtime.ensure(desc)['reused']
if sys.argv[2] == 'external':
    code = "from pathlib import Path; from deck_master import local_runtime as r; import sys; assert r.stop(r.descriptor(registry=Path(sys.argv[1])))['status']=='stopped'"
    subprocess.run([sys.executable, '-c', code, str(path)], check=True)
else:
    assert local_runtime.stop(desc)['status'] == 'stopped'
deadline = time.monotonic() + 3
stat = Path('/proc') / str(pid) / 'stat'
while stat.exists() and time.monotonic() < deadline:
    time.sleep(.01)
remaining = stat.read_text() if stat.exists() else None
# Only reap the probe's exact child if the assertion is about to fail.
if remaining:
    os.waitpid(pid, 0)
print(json.dumps({'remaining': remaining, 'pid': pid}))
'''


@pytest.mark.parametrize('stopper', ['owner', 'external'])
def test_live_owner_reaps_stopped_service_without_another_launch(tmp_path, stopper):
    import deck_master
    origin = str(Path(deck_master.__file__).resolve().parent.parent)
    run = subprocess.run([sys.executable, '-c', WORKER, str(tmp_path/'registry.json'), stopper],
                         env={**os.environ, 'PYTHONPATH': origin}, capture_output=True, text=True,
                         timeout=20, check=True)
    result = json.loads(run.stdout)
    assert result['remaining'] is None, result


def test_reaper_start_failure_reaps_only_new_child(tmp_path, monkeypatch):
    import threading
    from deck_master import local_runtime as runtime

    existing = runtime.descriptor(registry=tmp_path / 'existing.json')
    created = runtime.descriptor(registry=tmp_path / 'created.json')
    state = runtime.ensure(existing)
    children = []
    popen = subprocess.Popen
    start = threading.Thread.start

    def capture(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    def fail_reaper(thread):
        if thread.name == 'deck-master-service-reap':
            raise RuntimeError('injected thread start failure')
        return start(thread)

    monkeypatch.setattr(subprocess, 'Popen', capture)
    monkeypatch.setattr(threading.Thread, 'start', fail_reaper)
    try:
        assert runtime.ensure(existing)['reused']
        assert not children
        with pytest.raises(RuntimeError, match='injected thread start failure'):
            runtime.ensure(created)
        assert len(children) == 1
        child = children[0]
        assert child.returncode is not None
        assert not Path(f'/proc/{child.pid}').exists()
        with pytest.raises(ChildProcessError):
            os.waitpid(child.pid, os.WNOHANG)
        assert runtime.read_state(created) is None
        assert runtime.healthy(state, existing)
    finally:
        # Also keeps the failure probe safe when run against the old code.
        for child in children:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=3)
        runtime.stop(existing)


def test_reaper_does_not_hold_parent_exit_or_stop_detached_child(tmp_path):
    # An isolated parent exits while its wait target stays blocked. A fake child
    # avoids deliberately orphaning a real service in hosts without PID 1 reaping.
    code = r'''
import sys, threading
from pathlib import Path
from unittest.mock import patch
from deck_master import local_runtime as r
desc = r.descriptor(registry=Path(sys.argv[1]))
state = {'instance_id': 'probe', 'port': 12345}
entered = threading.Event()
class Child:
    def wait(self):
        entered.set()
        threading.Event().wait()
    def terminate(self):
        raise AssertionError('must not stop detached child')
    kill = terminate
with patch.object(r.secrets, 'token_hex', return_value='probe'), \
     patch.object(r, 'read_state', side_effect=[None, state]), \
     patch.object(r, 'healthy', side_effect=[False, True]), \
     patch.object(r.subprocess, 'Popen', return_value=Child()):
    assert not r.ensure(desc)['reused']
    assert entered.wait(2)
print('parent exits without stopping child')
'''
    import deck_master
    origin = str(Path(deck_master.__file__).resolve().parent.parent)
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'registry.json')],
                            env={**os.environ, 'PYTHONPATH': origin},
                            capture_output=True, text=True, timeout=5, check=True)
    assert result.stdout.strip() == 'parent exits without stopping child'
