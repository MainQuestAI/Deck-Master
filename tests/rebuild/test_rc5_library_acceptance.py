"""Actual catalog acceptance, distinct from synthetic transport fixtures."""
import copy
import hashlib
from pathlib import Path
import runpy
import shutil

import pytest

from deck_master import method_resources as methods, resource_catalog as catalog
from deck_master.work_context import ResourceCollector

ROOT = Path(__file__).resolve().parents[2]
SELECTED = ['content-m04', 'case-e04-walkthrough']


def test_actual_m04_e04_dependency_bytes_are_small_and_frozen():
    task = {'kind': 'compose', 'collaboration_binding': {'phase': 'argument'}}
    methods.freeze_task_methods(task, selected_resource_ids=SELECTED)
    manifest = task['method_manifest']
    ids = [row['id'] for row in manifest]
    assert set(SELECTED + ['example-e04-input', 'example-e04-after']) <= set(ids)
    assert 'example-e04-before' not in ids
    assert not any(mid.startswith('example-e01') for mid in ids)
    assert len(ids) < len(catalog.load_catalog(methods.resolve_root()))
    for row in manifest:
        assert hashlib.sha256((methods.resolve_root() / row['relative_path']).read_bytes()).hexdigest() == row['sha256']
    assert 'selected_resource_ids' not in task


def test_actual_example_remains_method_bytes_and_new_session_refetches():
    entries = methods.method_resources('compose', phase='argument', selected_resource_ids=SELECTED)
    identity = {'session_id': 'old-session', 'context_generation': 'g1'}
    offer = {**identity, 'resources': [{'kind': 'method', 'sha256': row['sha256']} for row in entries]}
    collector = ResourceCollector(body_mode='delta', cache_offer=offer,
        observed_context={**identity, 'session_id': 'new-session'})
    collector.methods(entries)
    assert all(row['kind'] == 'method' and row['state'] == 'returned' and row['content']
               for row in collector.bodies.values())


def test_legacy_manifest_hash_drift_is_not_resigned(monkeypatch, tmp_path):
    root = tmp_path / 'library'
    shutil.copytree(methods.resolve_root(), root)
    monkeypatch.setattr(methods, 'resolve_root', lambda: root)
    path = 'references/content-methods.md'
    task = {'kind': 'compose', 'method_manifest': [
        {'id': 'content-methods', 'relative_path': path,
         'sha256': hashlib.sha256(b'old immutable RC4 bytes').hexdigest()}]}
    task['method_release'] = {'release_id': '1.0.0rc4', 'methods_sha256': methods.methods_sha256(task['method_manifest'])}
    before = copy.deepcopy(task)
    result = methods.resolve_task_methods(task)
    assert result['basis_status'] == 'basis_changed'
    assert task == before and result['method_manifest'] == before['method_manifest']


@pytest.mark.parametrize('defect', ['unknown', 'missing', 'symlink', 'broken-link', 'unlabelled-example'])
def test_library_checker_reports_real_defects(tmp_path, defect):
    root = tmp_path / 'repo'
    for name in ('skills',):
        shutil.copytree(ROOT / name, root / name)
    (root / 'tools').mkdir()
    (root / 'src/deck_master').mkdir(parents=True)
    shutil.copyfile(ROOT / 'tools/build_hook.py', root / 'tools/build_hook.py')
    shutil.copyfile(ROOT / 'src/deck_master/resource_catalog.py', root / 'src/deck_master/resource_catalog.py')
    path = root / 'skills/deck-master/assets/content/examples/E04-saas-retention/input.md'
    if defect == 'unknown':
        (root / 'skills/unregistered.txt').write_text('unknown')
    elif defect == 'missing':
        path.unlink()
    elif defect == 'symlink':
        path.unlink()
        path.symlink_to(ROOT / 'README.md')
    elif defect == 'broken-link':
        with path.open('a') as f:
            f.write('\n[missing](unregistered.md)\n')
    else:
        path.write_text('# Input\nOrdinary prose without classification.\n')
    checker = runpy.run_path(str(ROOT / 'tools/check_content_method_library.py'))['check_library']
    if defect in ('unknown', 'missing', 'symlink'):
        with pytest.raises((ValueError, RuntimeError), match='unknown|missing|symlink'):
            checker(root)
    else:
        result = checker(root)
        assert result['status'] == 'FAIL' and result['errors']


@pytest.mark.parametrize('operator,expected', [
    ('add', '30'), ('subtract', '-10'), ('multiply', '200'),
    ('divide', '0.5'), ('percent_change', '100'), ('share_pct', '50')])
def test_explicit_finite_arithmetic_and_mismatch(operator, expected):
    helper = runpy.run_path(str(ROOT / 'skills/deck-master/scripts/check_case_numbers.py'))
    document = {'schema_version': 'case-arithmetic.v1', 'values': {'a': '10', 'b': '20'},
        'checks': [{'id': 'arithmetic', 'operator': operator, 'operands': ['a', 'b'], 'expected': expected}]}
    assert helper['evaluate'](document)['all_passed'] is True
    document['checks'][0]['expected'] = '999'
    assert helper['evaluate'](document)['all_passed'] is False


@pytest.mark.parametrize('defect,message', [
    ('zero', 'zero denominator'), ('operator', 'operator'), ('nan', 'finite'),
    ('expression', 'invalid decimal'), ('missing', 'missing'), ('boolean', 'not bool')])
def test_arithmetic_refuses_invalid_inputs_without_execution(defect, message):
    helper = runpy.run_path(str(ROOT / 'skills/deck-master/scripts/check_case_numbers.py'))
    document = {'schema_version': 'case-arithmetic.v1', 'values': {'a': '10', 'b': '2'},
        'checks': [{'id': 'arithmetic', 'operator': 'divide', 'operands': ['a', 'b'], 'expected': '5'}]}
    if defect == 'operator':
        document['checks'][0]['operator'] = '__import__'
    elif defect == 'missing':
        del document['values']['b']
    else:
        document['values']['b'] = {'zero': '0', 'nan': 'NaN', 'expression': "__import__('os').getcwd()", 'boolean': True}[defect]
    with pytest.raises(ValueError, match=message):
        helper['evaluate'](document)


@pytest.mark.parametrize('raw,code', [
    ('{"values": {}, "values": {}}', 'duplicate JSON key'),
    (' ' * 1_000_001, 'input exceeds')])
def test_arithmetic_cli_bounded_json(tmp_path, raw, code):
    import json
    import subprocess
    import sys
    path = tmp_path / 'input.json'
    path.write_text(raw)
    output = subprocess.run([sys.executable, str(ROOT / 'skills/deck-master/scripts/check_case_numbers.py'), str(path)],
        capture_output=True, text=True, check=False)
    assert output.returncode == 2
    assert code in json.loads(output.stdout)['error']
    assert path.read_text() == raw
