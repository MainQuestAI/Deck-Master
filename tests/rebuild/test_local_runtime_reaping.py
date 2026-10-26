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
