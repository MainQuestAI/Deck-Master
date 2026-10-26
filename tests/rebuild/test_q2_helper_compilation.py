"""Reuse code compilation, never pinned validation or mutable helper modules."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'tools/rc3_campaign'


def load(base):
    for name in ('q2_later_300.py', 'supplementary_recorder.py', 'controller.py'):
        shutil.copyfile(SOURCE / name, base / name)
    spec = importlib.util.spec_from_file_location('q2_compilation_probe', base / 'q2_later_300.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compilation_reuse_keeps_fresh_modules_and_original_pins(tmp_path):
    p = load(tmp_path)
    first, first_c = p.helpers()
    first.PROFILES.clear()
    first_c.PUBLIC_OPERATIONS.clear()
    second, second_c = p.helpers()
    assert first is not second and first_c is not second_c
    assert second.PROFILES and second_c.PUBLIC_OPERATIONS
    assert p._scoped_code.cache_info().misses == 1
    assert p._scoped_code.cache_info().hits == 1
    assert hashlib.sha256((tmp_path/'controller.py').read_bytes()).hexdigest() == p.COMMON_SHA
    assert hashlib.sha256((tmp_path/'supplementary_recorder.py').read_bytes()).hexdigest() == p.SCOPED_SHA


@pytest.mark.parametrize('name', ['controller.py', 'supplementary_recorder.py'])
def test_warm_compilation_does_not_hide_same_size_same_mtime_tamper(tmp_path, name):
    p = load(tmp_path)
    p.helpers()
    path = tmp_path / name
    original = path.read_bytes()
    before = path.stat()
    path.write_bytes(original.replace(b'#!/usr/bin/env python3', b'#!/usr/bin/env python2', 1))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    with pytest.raises(p.Error, match='frozen helpers differ'):
        p.helpers()
    path.write_bytes(original)
    p.helpers()
    assert p._scoped_code.cache_info().misses == 1
