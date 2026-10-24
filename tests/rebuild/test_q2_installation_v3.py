"""Old/new verifier differential checks against fresh filesystem observations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType

import pytest

BASE = Path(__file__).resolve().parents[2] / 'tools/rc3_campaign'


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OLD, NEW = load('controller'), load('controller_v3')


def ref(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    root = tmp_path / 'package'
    root.mkdir()
    (root / '__init__.py').write_text('# neutral\n')
    (root / 'nested').mkdir()
    (root / 'nested/data.txt').write_text('neutral\n')
    wheel = tmp_path / 'original.whl'
    wheel.write_bytes(b'neutral wheel')
    manifest = tmp_path / 'manifest.json'
    record = {'source_sha': 'a'*40, 'source_tree': 'b'*40,
              'wheel_sha256': ref(wheel)['sha256'], 'installed_module_path': str(root / '__init__.py')}
    manifest.write_text(json.dumps(record))
    spec = {**{k: record[k] for k in ('source_sha', 'source_tree', 'wheel_sha256')},
            'python': sys.executable, 'module_file': str(root / '__init__.py'),
            'manifest': ref(manifest), 'wheel': ref(wheel), 'adapter_profile': 'A0-public-legacy',
            'package_files': [{'relative_path': str(p.relative_to(root)), 'sha256': ref(p)['sha256']}
                              for p in root.rglob('*') if p.is_file()]}
    # A synthetic admitted module, not a replacement for the real SDK carrier.
    for name in list(sys.modules):
        if name == 'deck_master' or name.startswith('deck_master.'):
            monkeypatch.delitem(sys.modules, name)
    module = ModuleType('deck_master')
    module.__file__ = str(root / '__init__.py')
    monkeypatch.setitem(sys.modules, 'deck_master', module)
    return {'installations': {'A0': spec}}, root


def outcomes(config):
    values = []
    for module in (OLD, NEW):
        try:
            values.append(('ok', module.installation(config, 'A0', enforce_isolation=False)))
        except Exception as exc:
            values.append((type(exc).__name__, str(exc)))
    assert values[0] == values[1]
    return values[0]


def test_success_and_repeated_fresh_observation(admitted):
    config, root = admitted
    assert outcomes(config)[0] == 'ok'
    path = root / 'nested/data.txt'
    stat = path.stat()
    path.write_text('changed\n')
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size
    assert outcomes(config)[0] == 'CampaignError'
    path.write_text('neutral\n')
    assert outcomes(config)[0] == 'ok'


@pytest.mark.parametrize('fault', ['add', 'remove', 'duplicate', 'parent', 'absolute', 'leaf_link',
                                   'parent_escape', 'sibling_prefix', 'manifest_bytes', 'manifest_identity',
                                   'interpreter', 'module', 'wheel', 'borrowed_module'])
def test_same_failure_categories(admitted, tmp_path, monkeypatch, fault):
    config, root = admitted
    spec = config['installations']['A0']
    assert outcomes(config)[0] == 'ok'
    if fault == 'add': (root / 'extra').write_text('extra')
    elif fault == 'remove': (root / 'nested/data.txt').unlink()
    elif fault == 'duplicate': spec['package_files'].append(dict(spec['package_files'][0]))
    elif fault == 'parent': spec['package_files'][0]['relative_path'] = '../outside'
    elif fault == 'absolute': spec['package_files'][0]['relative_path'] = str(root / '__init__.py')
    elif fault == 'leaf_link':
        p = root / 'nested/data.txt'; p.unlink(); p.symlink_to(root / '__init__.py')
    elif fault in ('parent_escape', 'sibling_prefix'):
        p = root / 'nested'; (p / 'data.txt').unlink(); p.rmdir()
        outside = tmp_path / ('package-sibling' if fault == 'sibling_prefix' else 'outside')
        outside.mkdir(); (outside / 'data.txt').write_text('neutral\n'); p.symlink_to(outside, target_is_directory=True)
    elif fault.startswith('manifest'):
        p = Path(spec['manifest']['path']); data = json.loads(p.read_text()); data['source_tree'] = 'c'*40
        p.write_text(json.dumps(data))
        if fault == 'manifest_identity': spec['manifest'] = ref(p)
    elif fault == 'interpreter': spec['python'] = str(tmp_path / 'other-python')
    elif fault == 'module': spec['module_file'] = str(root / 'nested/data.txt')
    elif fault == 'wheel': Path(spec['wheel']['path']).write_bytes(b'changed wheel')
    elif fault == 'borrowed_module':
        module = ModuleType('deck_master.borrowed'); module.__file__ = str(tmp_path / 'foreign.py')
        monkeypatch.setitem(sys.modules, module.__name__, module)
    assert outcomes(config)[0] != 'ok'


@pytest.mark.parametrize('key', ['source_sha', 'source_tree', 'wheel_sha256'])
def test_b_identity_is_observed_again_between_calls(admitted, monkeypatch, key):
    config, root = admitted
    spec = config['installations']['A0']
    spec.pop('adapter_profile')
    identity = {k: spec[k] for k in ('source_sha', 'source_tree', 'wheel_sha256')}
    capabilities = ModuleType('deck_master.capabilities')
    capabilities.__file__ = str(root / '__init__.py')
    calls = []

    def current_identity():
        calls.append(1)
        return {'install': dict(identity)}

    capabilities.installation_identity = current_identity
    monkeypatch.setattr(sys.modules['deck_master'], 'capabilities', capabilities, raising=False)
    assert outcomes(config)[0] == 'ok'
    identity[key] = 'different-now'
    assert outcomes(config)[0] == 'CampaignError'
    assert len(calls) == 4  # Both versions observe identity again, no success cache.


def test_inside_parent_alias_and_ignored_bytecode_match_old_behavior(admitted):
    config, root = admitted
    spec = config['installations']['A0']
    (root / 'alias').symlink_to(root / 'nested', target_is_directory=True)
    for item in spec['package_files']:
        if item['relative_path'] == 'nested/data.txt': item['relative_path'] = 'alias/data.txt'
    # A parent alias stays inside root, but rglob does not follow directory
    # symlinks: the frozen inventory still must match and both reject aliases.
    assert outcomes(config)[0] == 'CampaignError'
    (root / 'alias').unlink()
    for item in spec['package_files']:
        if item['relative_path'] == 'alias/data.txt': item['relative_path'] = 'nested/data.txt'
    (root / '__pycache__').mkdir()
    (root / '__pycache__/ignored.pyc').write_bytes(b'ignored')
    assert outcomes(config)[0] == 'ok'


@pytest.mark.parametrize('old_binding', ['format', 'common', 'scoped', 'tool'])
def test_v2_rejects_old_control_bindings_without_migration(tmp_path, old_binding):
    import subprocess
    tool = BASE / 'q2_later_300_v3.py'
    new = load('q2_later_300_v3')
    review = tmp_path / 'review.txt'; review.write_text('synthetic review reference')
    scope = {'tool': ref(tool), 'common': ref(BASE/'controller_v3.py'),
             'scoped': ref(BASE/'supplementary_recorder_v3.py'),
             'ledger_root': str(tmp_path/'ledger'), 'origins': {}, 'six_cuts': {},
             'protocol': ref(review), 'resource_selection': ref(review)}
    record = {'format': new.FORMAT, 'status': new.ENGINEERING,
              'observer_id': '/engineering/rc3-s09', 'assurance': 'synthetic_engineering',
              'observed_at_utc': 'synthetic', 'implementation_review': ref(review), 'scope': scope}
    if old_binding == 'format': record['format'] = 'rc3-q2-later-300-control.v1'
    else:
        old_name = {'common': 'controller.py', 'scoped': 'supplementary_recorder.py', 'tool': 'q2_later_300.py'}[old_binding]
        scope[old_binding] = ref(BASE/old_name)
    control = tmp_path/'control.json'; control.write_text(json.dumps(record)); before = control.read_bytes()
    result = subprocess.run([sys.executable, '-I', '-B', str(tool), 'initialize', '--engineering',
                             '--flow', 'r04', '--control', str(control), '--control-sha256', ref(control)['sha256']],
                            capture_output=True, timeout=10)
    assert result.returncode == 2
    error = json.loads(result.stderr)['error']
    assert error == ('prospective Root control required' if old_binding == 'format' else 'reviewed tool/helper bytes changed')
    assert control.read_bytes() == before


def test_v2_compilation_still_creates_fresh_helper_and_controller():
    tool = load('q2_later_300_v3')
    first, common = tool.helpers()
    first.PROFILES.clear(); common.PUBLIC_OPERATIONS.clear()
    second, second_common = tool.helpers()
    assert first is not second and common is not second_common
    assert second.PROFILES and second_common.PUBLIC_OPERATIONS
    assert tool._scoped_code.cache_info().misses == 1
    assert tool._scoped_code.cache_info().hits == 1


def test_every_package_file_is_read_on_every_validation(admitted, monkeypatch):
    config, root = admitted
    original = Path.read_bytes
    reads = []

    def observed(path):
        if path.is_relative_to(root): reads.append(str(path))
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', observed)
    expected = sorted(str(root/item['relative_path']) for item in config['installations']['A0']['package_files'])
    for module in (OLD, NEW):
        for _ in range(2):
            reads.clear()
            module.installation(config, 'A0', enforce_isolation=False)
            assert sorted(reads) == expected


def test_valid_module_path_alias_and_normalization(admitted, tmp_path, monkeypatch):
    config, root = admitted
    alias = tmp_path/'package-link'; alias.symlink_to(root, target_is_directory=True)
    config['installations']['A0']['module_file'] = str(alias/'__init__.py')
    extra = ModuleType('deck_master.extra')
    extra.__file__ = str(root/'nested/../__init__.py')
    monkeypatch.setitem(sys.modules, extra.__name__, extra)
    assert outcomes(config)[0] == 'ok'


def test_change_at_file_read_is_detected_by_both(admitted, monkeypatch):
    config, root = admitted
    target = root/'nested/data.txt'
    original = Path.read_bytes
    errors = []
    for module in (OLD, NEW):
        target.write_text('neutral\n')
        with monkeypatch.context() as patch:
            def changed_at_read(path):
                if path == target: target.write_text('changed\n')
                return original(path)
            patch.setattr(Path, 'read_bytes', changed_at_read)
            with pytest.raises(module.CampaignError) as error:
                module.installation(config, 'A0', enforce_isolation=False)
            errors.append(str(error.value))
    assert errors[0] == errors[1] == 'installed bytes changed: nested/data.txt'
