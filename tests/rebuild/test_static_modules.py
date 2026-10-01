"""Shipped v2 modules must parse: one broken module takes down the whole UI.

A04 regression guard: the gallery/page-production-chain rework edits several ES
modules by hand; this keeps a syntax slip from reaching the browser layer.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'


def test_every_v2_module_and_entry_parses():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to parse the shipped ES modules')
    modules = sorted(V2.glob('*.js'))
    assert V2.joinpath('gallery.js') in modules and V2.joinpath('page-workbench.js') in modules
    for module in modules:
        result = subprocess.run([node, '--check', str(module)], capture_output=True, text=True)
        assert result.returncode == 0, f'{module.name}: {result.stderr}'
