"""Controlled subprocess probes; the real Q2 gate remains 180 seconds."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).with_name("q2_timeout_diagnostics.py")


def child_code(finish):
    return f'''
import importlib.util, time
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location("observer", {str(MODULE)!r})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class ControlledTimer:
    def __init__(self, delay, callback): self.cancelled = False
    def start(self): pass
    def cancel(self): self.cancelled = True
if {finish!r}: m.threading.Timer = ControlledTimer
d = m.Diagnostics(delay=0.05)
d.pytest_runtest_logstart("private-input-never-emitted", None)
{"d.pytest_runtest_logreport(SimpleNamespace(when='call', outcome='passed', duration=0.001)); d.pytest_runtest_logfinish(None, None); d.pytest_sessionfinish(None, 0); assert d.timer.cancelled" if finish else "time.sleep(10)"}
'''


def records(stderr):
    return [json.loads(line.split(" ", 1)[1]) for line in stderr.decode().splitlines()
            if line.startswith("Q2_DIAGNOSTIC ")]


def test_success_records_phases_cpu_and_cancels_snapshot():
    result = subprocess.run([sys.executable, "-I", "-B", "-c", child_code(True)],
                            capture_output=True, timeout=5)
    assert result.returncode == 0
    rows = records(result.stderr)
    assert [r['event'] for r in rows] == ['start', 'phase', 'finish', 'end']
    assert rows[1]['duration_s'] == 0.001 and rows[1]['outcome'] == 'passed'
    assert all(r['wall_s'] >= 0 and r['process_cpu_s'] >= 0 for r in rows)
    assert b'private-input' not in result.stderr


def test_controlled_timeout_keeps_exception_and_pre_deadline_evidence():
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        subprocess.run([sys.executable, "-I", "-B", "-c", child_code(False)],
                       capture_output=True, timeout=1)
    assert caught.value.timeout == 1
    stderr = caught.value.stderr
    rows = records(stderr)
    assert [r['event'] for r in rows] == ['start', 'pre_deadline']
    assert rows[-1]['active_case'] == 1 and rows[-1]['active_elapsed_s'] > 0
    assert b'Thread' in stderr and b'<module>' in stderr
    assert b'private-input' not in stderr
