"""Verify shipped polling under overlapping focus, hidden, failure and bfcache."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_polling_lifecycle_never_overlaps_or_applies_stale_generation():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to exercise the shipped polling module')
    script = Path(__file__).resolve().parents[2] / 'examples/workbench/w10_poll_lifecycle.mjs'
    result = subprocess.run([node, str(script)], capture_output=True, text=True, check=True, timeout=20)
    assert json.loads(result.stdout)['passed']
