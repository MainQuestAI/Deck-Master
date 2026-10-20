"""Synthetic integration fixtures; these are not the unavailable RC5 seeds."""
import copy
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import zipfile

import pytest

from deck_master import content_production, method_resources as methods, resource_catalog as catalog
from deck_master import collaboration_binding, install, models, tasks
from deck_master.work_context import ResourceCollector
from test_compose_v2_phases import _project, _request

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fixture_catalog(tmp_path, monkeypatch):
    root = tmp_path / 'methods'
    shutil.copytree(ROOT / 'skills/deck-master', root)
    data = json.loads((root / catalog.CATALOG_PATH).read_bytes())
    for mid, kind, deps, phases in [
        ('fixture-data', 'data', [], []),
        ('fixture-example', 'example', ['fixture-data'], []),
        ('fixture-script', 'script', [], []),
        ('fixture-argument', 'instruction', ['fixture-example'], ['argument']),
    ]:
        path = f'assets/{mid}.txt'
        (root / 'assets').mkdir(exist_ok=True)
        (root / path).write_text(f'SYNTHETIC_ENGINEERING {mid}; never execute or treat as customer evidence.\n')
        data['resources'].append(dict(id=mid, relative_path=path, kind=kind,
            owner='deck-content', consumers=['deck-content'], dependencies=deps,
            task_kinds=['compose'], phases=phases, review_units=[], readable=True))
    (root / catalog.CATALOG_PATH).write_text(json.dumps(data))
    monkeypatch.setattr(methods, 'resolve_root', lambda: root)
    resources = catalog.load_catalog(root)
    monkeypatch.setattr(methods, 'RELATIVE_PATHS',
                        {mid: row['relative_path'] for mid, row in resources.items() if row['readable']})
    return root, data


def test_original_inventory_preserved_and_shared_by_build():
    resources = catalog.load_catalog(ROOT / 'skills/deck-master')
    assert len(resources) == 14  # Existing only; no seed-import claim.
    assert len(methods.RELATIVE_PATHS) == 13
    hook = runpy.run_path(str(ROOT / 'tools/build_hook.py'))
    assert hook['canonical_mapping'](ROOT) == catalog.canonical_mapping(resources)


@pytest.mark.parametrize('defect', ['duplicate-id', 'duplicate-path', 'escape', 'absolute',
                                   'backslash', 'cycle', 'unknown-dependency', 'missing-legacy'])
def test_catalog_rejects_invalid_graph_and_paths(fixture_catalog, defect):
    _, data = fixture_catalog
    row = data['resources'][-1]
    if defect == 'duplicate-id':
        row['id'] = data['resources'][0]['id']
    elif defect == 'duplicate-path':
        row['relative_path'] = data['resources'][0]['relative_path']
    elif defect == 'escape':
        row['relative_path'] = 'assets/../outside'
    elif defect == 'absolute':
        row['relative_path'] = '/outside'
    elif defect == 'backslash':
        row['relative_path'] = 'assets\\outside'
    elif defect == 'cycle':
        row['dependencies'] = [row['id']]
    elif defect == 'missing-legacy':
        data['resources'].pop(0)
    else:
        row['dependencies'] = ['missing-id']
    with pytest.raises(ValueError):
        catalog.validate_catalog(data)


def test_selection_dependency_order_and_scope(fixture_catalog):
    _, data = fixture_catalog
    resources = catalog.validate_catalog(data)
    assert catalog.select(resources, ['fixture-argument', 'fixture-data', 'fixture-argument'],
                          role='deck-content', kind='compose', phase='argument') == (
                              'fixture-data', 'fixture-example', 'fixture-argument')
    for options in [dict(role='deck-design', kind='compose', phase='argument'),
                    dict(role='deck-content', kind='compose', phase='speech'),
                    dict(role='deck-content', kind='review', phase='argument')]:
        with pytest.raises(ValueError, match='outside'):
            catalog.select(resources, ['fixture-argument'], **options)
    with pytest.raises(ValueError, match='unknown'):
        catalog.select(resources, ['missing'], role='deck-content')


def test_final_bound_phase_builder_preserves_explicit_selection(tmp_path, fixture_catalog):
    project, store = _project(tmp_path)
    _request(project, store)
    task = content_production.build_phase_task(store, store.load_document(),
        operation_id='rc5-final-freeze', phase='argument',
        selected_resource_ids=['fixture-argument', 'fixture-data'])
    ids = [r['id'] for r in task['method_manifest']]
    assert ids[-3:] == ['fixture-data', 'fixture-example', 'fixture-argument']
    assert 'selected_resource_ids' not in task
    assert task['collaboration_binding']['phase'] == 'argument'
    models.validate_task_semantics(task)


def test_refreeze_recomputes_defaults_without_inferring_selection(fixture_catalog):
    task = dict(kind='compose', collaboration_binding={'phase': 'framing'})
    methods.freeze_task_methods(task, selected_resource_ids=['fixture-example'])
    assert 'source-reading' in [r['id'] for r in task['method_manifest']]
    task['collaboration_binding']['phase'] = 'speech'
    methods.freeze_task_methods(task, selected_resource_ids=['fixture-example'])
    ids = [r['id'] for r in task['method_manifest']]
    assert 'source-reading' not in ids
    assert ids[-2:] == ['fixture-data', 'fixture-example']
    # Omitting selection really means none; a temporary manifest is not input.
    methods.freeze_task_methods(task)
    assert 'fixture-example' not in [r['id'] for r in task['method_manifest']]


def test_generic_task_final_stamp_retains_dispatch_selection(tmp_path, fixture_catalog):
    project, store = _project(tmp_path)
    _request(project, store)
    document = store.load_document()
    task = tasks.new_task(task_id='generic', operation_id='generic', kind='compose',
        scope_pages=[], instruction='synthetic selection', inputs=[], dependencies=[],
        dispatch_revision=document['revision_id'], produced_against=models.content_identity(document),
        selected_resource_ids=['fixture-example'])
    collaboration_binding.stamp_task(store, document, task, phase='speech',
                                     selected_resource_ids=['fixture-example'])
    ids = [row['id'] for row in task['method_manifest']]
    assert ids[-2:] == ['fixture-data', 'fixture-example']
    assert 'source-reading' not in ids
    assert 'selected_resource_ids' not in task


def test_frozen_basis_retains_original_hash_and_never_appends_defaults(fixture_catalog):
    root, _ = fixture_catalog
    task = dict(kind='compose', collaboration_binding={'phase': 'argument'})
    methods.freeze_task_methods(task, selected_resource_ids=['fixture-argument'])
    original = copy.deepcopy(task)
    (root / 'assets/fixture-example.txt').write_text('changed')
    result = methods.resolve_task_methods(task)
    assert result['basis_status'] == 'basis_changed'
    assert result['method_manifest'] == original['method_manifest']
    assert task == original


@pytest.mark.parametrize('mode', ['full', 'delta', 'manifest'])
def test_semantic_resources_keep_method_transport_and_cold_cache(fixture_catalog, mode):
    entries = methods.method_resources('compose',
        selected_resource_ids=['fixture-example', 'fixture-script'])
    collector = ResourceCollector(body_mode=mode)
    items = collector.methods(entries)
    result = collector.envelope({'entry_methods': items})
    assert all(body['kind'] == 'method' for body in result['bodies'].values())
    if mode == 'manifest':
        assert result['context_ready'] is False
        assert all('content' not in body for body in result['bodies'].values())
    else:
        assert all('content' in body for body in result['bodies'].values())
    assert any(i['id'] == 'fixture-script' for i in items)


def test_independent_entry_uses_same_selection_reader(fixture_catalog):
    result = methods.read_skill_methods('deck-content', selected_resource_ids=['fixture-example'])
    assert [r['id'] for r in result['methods']][-2:] == ['fixture-data', 'fixture-example']
    result = methods.read_skill_methods('deck-content', selected_resource_ids=['fixture-example'],
        read_protocol='work_context.v2')
    assert [r['id'] for r in result['entry_methods']][-2:] == ['fixture-data', 'fixture-example']
    with pytest.raises(ValueError, match='frozen Task'):
        methods.read_skill_methods('deck-content', project='unused', task_id='frozen',
                                   selected_resource_ids=['fixture-example'])


def test_runtime_refuses_symlinked_selected_bytes(fixture_catalog, tmp_path):
    root, _ = fixture_catalog
    path = root / 'assets/fixture-data.txt'
    path.unlink()
    target = tmp_path / 'outside.txt'
    target.write_text('outside')
    path.symlink_to(target)
    with pytest.raises(Exception, match='symlink'):
        methods.method_resources('compose', selected_resource_ids=['fixture-example'])


def test_warm_delta_requires_actual_context_and_refetch_is_full(fixture_catalog):
    entries = methods.method_resources('compose', selected_resource_ids=['fixture-example'])
    identity = {'session_id': 'actual-session', 'context_generation': 'generation-1'}
    offer = {**identity, 'resources': [{'kind': 'method', 'sha256': r['sha256']} for r in entries]}
    for mode, observed, expected in [
        ('delta', identity, 'omitted_by_cache_offer'),
        ('delta', {**identity, 'context_generation': 'generation-2'}, 'returned'),
        ('delta', None, 'returned'),
        ('full', identity, 'returned'),
    ]:
        collector = ResourceCollector(body_mode=mode, cache_offer=offer, observed_context=observed)
        collector.methods(entries)
        assert {body['state'] for body in collector.bodies.values()} == {expected}


def test_new_resource_commit_advances_feature_floor_not_read(tmp_path, fixture_catalog):
    project, store = _project(tmp_path)
    _request(project, store)
    before = store.load_document()['compatibility']
    methods.read_skill_methods('deck-content', selected_resource_ids=['fixture-example'])
    assert store.load_document()['compatibility'] == before
    content_production.open_phase_task(store, store.load_document(),
        operation_id='rc5-commit', phase='argument', selected_resource_ids=['fixture-argument'])
    assert store.load_document()['compatibility']['minimum_writer'] == 'method-catalog.v1'


def test_build_refuses_unknown_files_and_directory_symlinks(tmp_path):
    root = tmp_path / 'repo'
    shutil.copytree(ROOT / 'skills', root / 'skills')
    (root / 'src/deck_master').mkdir(parents=True)
    shutil.copyfile(ROOT / 'src/deck_master/resource_catalog.py', root / 'src/deck_master/resource_catalog.py')
    hook = runpy.run_path(str(ROOT / 'tools/build_hook.py'))
    unknown = root / 'skills/deck-master/unregistered.txt'
    unknown.write_text('unregistered')
    with pytest.raises(RuntimeError, match='unknown'):
        hook['canonical_mapping'](root)
    unknown.unlink()
    (root / 'skills/deck-master/assets').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError, match='symlink'):
        hook['canonical_mapping'](root)


def test_wheel_installer_uses_same_catalog_and_checks_unknown_members():
    hook = runpy.run_path(str(ROOT / 'tools/build_hook.py'))
    inventory = hook['resource_inventory'](ROOT)
    def archive(extra=False):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            for target, row in inventory['files'].items():
                z.writestr(target, (ROOT / row['canonical_source']).read_bytes())
            z.writestr(hook['INVENTORY_PATH'], json.dumps(inventory))
            if extra:
                z.writestr('deck_master/resources/skill/assets/unregistered.txt', 'unknown')
        output.seek(0)
        return zipfile.ZipFile(output)
    with archive() as z:
        installed, _ = install._wheel_skills(z)
        assert installed == inventory
    with archive(True) as z, pytest.raises(ValueError, match='unknown'):
        install._wheel_skills(z)


def test_installer_verifies_registered_synthetic_nested_assets(fixture_catalog):
    root, _ = fixture_catalog
    resources = catalog.load_catalog(root)
    hook = runpy.run_path(str(ROOT / 'tools/build_hook.py'))
    payloads = {}
    for target, source in catalog.canonical_mapping(resources).items():
        path = (root / source.removeprefix('skills/deck-master/')
                if source.startswith('skills/deck-master/') else ROOT / source)
        payloads[target] = (source, path.read_bytes())
    inventory = {
        'schema_version': 'method_resource_inventory.v1',
        'public_skills': list(catalog.PUBLIC_SKILLS),
        'shared_method_source': 'skills/deck-master',
        'generated_exceptions': hook['GENERATED_EXCEPTIONS'],
        'files': {target: {'canonical_source': source, 'sha256': hashlib.sha256(raw).hexdigest()}
                  for target, (source, raw) in payloads.items()},
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for target, (_, raw) in payloads.items():
            z.writestr(target, raw)
        z.writestr(hook['INVENTORY_PATH'], json.dumps(inventory))
    output.seek(0)
    with zipfile.ZipFile(output) as z:
        _, extracted = install._wheel_skills(z)
        assert extracted['deck-master/assets/fixture-script.txt'] == (
            root / 'assets/fixture-script.txt').read_bytes()
