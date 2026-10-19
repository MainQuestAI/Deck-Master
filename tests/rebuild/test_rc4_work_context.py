"""SYNTHETIC_ENGINEERING: N4A transport equivalence and measured reader limits."""
import copy
from collections import Counter
import json
from pathlib import Path

import pytest

from deck_master import capabilities, cli, method_resources as methods, service
from deck_master.models import sha256_bytes
from deck_master.store import Store
from deck_master.work_context import PROTOCOL, ReadProtocolError, ResourceCollector, TypedServiceError


def _project(tmp_path):
    source = tmp_path / 'material.txt'
    source.write_bytes('Complete source first line.\r\n限定与完整尾段。\r\n'.encode())
    other = tmp_path / 'unreferenced.txt'
    other.write_text('Another required source, even before any Page cites it.')
    project = tmp_path / 'project'
    service.create(project, brief='SYNTHETIC_ENGINEERING complete context', sources=[source, other])
    store = Store(project)
    document = store.load_document()
    task = store.read_object_json(document['tasks'][0])
    return project, store, document, task


def _snapshot(project):
    return {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}


def _hydrate(order, bodies):
    value = copy.deepcopy(order)
    for entry in value.get('method_resources', []):
        entry.pop('body_ref')
    readings = []
    for entry in value.get('source_reading', []):
        body = bodies[entry['body_ref']]
        readings.append({'source_id': entry['source_id'], **json.loads(body['content']),
                         **{k: entry[k] for k in ('extract_path', 'original_path') if k in entry}})
    value['source_reading'] = readings
    value.pop('page_reading', None)
    return value


def test_default_v1_full_semantics_source_inventory_and_no_writes(tmp_path):
    project, store, document, task = _project(tmp_path)
    before = _snapshot(project)
    v1 = service.task_summary(store, document, task)
    v2 = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    assert _hydrate(v2['tasks'][0], v2['bodies']) == v1
    assert v2['context_ready'] and len(v2['tasks'][0]['sources']) == 2
    assert _snapshot(project) == before
    assert 'schema_version' not in v1
    for body in v2['bodies'].values():
        assert sha256_bytes(body['content'].encode()) == body['sha256']
    assert any(p['protocol'] == PROTOCOL for p in capabilities.describe()['read_protocols'])


@pytest.mark.parametrize('options', [dict(read_protocol='work_context.v99'),
    dict(read_protocol=PROTOCOL, body_mode='short'), dict(body_mode='full'),
    dict(read_protocol=PROTOCOL, cache_offer={'passed_review': True})])
def test_negotiation_precedes_all_create_continue_side_effects(tmp_path, options):
    project = tmp_path / 'absent' / 'project'
    with pytest.raises((ReadProtocolError, TypedServiceError)):
        service.create(project, brief='invalid negotiation', **options)
    assert not project.parent.exists()
    project, _, _, _ = _project(tmp_path)
    before = _snapshot(project)
    with pytest.raises((ReadProtocolError, TypedServiceError)):
        service.continue_project(project, **options)
    assert _snapshot(project) == before


def test_shared_tasks_actual_json_and_method_byte_counts(tmp_path, monkeypatch):
    project, store, document, task = _project(tmp_path)
    second = {**task, 'task_id': 'second-reader', 'operation_id': 'second-reader'}
    second_ref = store.put_json_object(second)
    # Includes an identical Task ref twice: it too is decoded only once.
    document['tasks'] += [second_ref, document['tasks'][0]]
    byte_reads, decodes, method_reads = Counter(), Counter(), Counter()
    counted_json = {ref['sha256'] for ref in document['tasks']} | {s['extract']['sha256'] for s in document['sources']}
    original_bytes, original_loads, path_bytes = Store.read_object_bytes, json.loads, Path.read_bytes
    def read_bytes(self, ref):
        byte_reads[ref['path']] += 1
        return original_bytes(self, ref)
    def loads(raw, *args, **kwargs):
        result = original_loads(raw, *args, **kwargs)
        digest = sha256_bytes(raw.encode() if isinstance(raw, str) else raw)
        if digest in counted_json:
            decodes[digest] += 1
        return result
    root = methods.resolve_root()
    def method_bytes(path):
        if path.is_relative_to(root):
            method_reads[str(path)] += 1
        return path_bytes(path)
    monkeypatch.setattr(Store, 'read_object_bytes', read_bytes)
    monkeypatch.setattr(json, 'loads', loads)
    monkeypatch.setattr(Path, 'read_bytes', method_bytes)
    response = service._pending_host_tasks(document, store, read_protocol=PROTOCOL)
    assert len(response['tasks']) == 3 and response['context_ready']
    assert max(byte_reads.values()) == 1
    assert max(method_reads.values()) == 1
    assert set(decodes) == counted_json and max(decodes.values()) == 1
    serialized = json.dumps(response, ensure_ascii=False)
    for body in response['bodies'].values():
        assert serialized.count(json.dumps(body['content'], ensure_ascii=False)) == 1
    assert len([b for b in response['bodies'].values() if b['kind'] == 'source_extract']) == 2
    assert {e['source_id'] for e in response['tasks'][0]['source_reading']} == {s['source_id'] for s in document['sources']}


def test_delta_exact_observed_context_cold_recovery_manifest_and_change(tmp_path):
    project, store, document, task = _project(tmp_path)
    full = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    context = {'session_id': 'observed-host-session', 'context_generation': 'generation-2'}
    offer = {**context, 'resources': [{'kind': b['kind'], 'sha256': b['sha256']} for b in full['bodies'].values()]}
    for observed in (None, {**context, 'session_id': 'new-session'}, {**context, 'context_generation': 'after-compaction'}):
        cold = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode='delta',
                                    cache_offer=offer, observed_context=observed)
        assert all(b['state'] == 'returned' for b in cold['bodies'].values())
    delta = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode='delta',
                                cache_offer=offer, observed_context=context)
    assert all(b['state'] == 'omitted_by_cache_offer' and 'content' not in b for b in delta['bodies'].values())
    assert delta['tasks'] == full['tasks'] and delta['context_ready']
    hydrated = {key: {**body, 'content': full['bodies'][key]['content']} for key, body in delta['bodies'].items()}
    assert _hydrate(delta['tasks'][0], hydrated) == _hydrate(full['tasks'][0], full['bodies'])
    manifest = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode='manifest')
    assert not manifest['context_ready'] and all(b['state'] == 'manifest_only' for b in manifest['bodies'].values())
    collector = ResourceCollector(body_mode='delta', cache_offer=offer, observed_context=context)
    changed = collector.add('source_extract', b'new bytes', retrieval={'source_id': 'same-source'})
    assert collector.bodies[changed]['state'] == 'returned'
    assert delta['host_application'] == 'not_recorded'
    assert service.task_summary(store, document, task, read_protocol=PROTOCOL)['bodies'] == full['bodies']


@pytest.mark.parametrize('mode', ['full', 'delta', 'manifest'])
def test_manifest_legacy_drift_missing_exact_n3_basis_and_partial_sources(tmp_path, monkeypatch, mode):
    _, store, document, task = _project(tmp_path)
    expected = methods.resolve_task_methods(task)
    result = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode=mode)
    order = result['tasks'][0]
    assert [{k: e[k] for k in ('id', 'relative_path', 'sha256')} for e in order['method_resources']] == expected['method_manifest']
    legacy = copy.deepcopy(task); legacy.pop('method_manifest', None)
    old = service.task_summary(store, document, legacy, read_protocol=PROTOCOL, body_mode=mode)
    assert old['tasks'][0]['method_manifest'] == methods.resolve_task_methods(legacy)['method_manifest']
    replacement = tmp_path / 'installed-methods'
    for item in expected['methods']:
        target = replacement / item['relative_path']; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(item['path']).read_bytes())
    first = replacement / expected['methods'][0]['relative_path']
    first.write_bytes(first.read_bytes() + b'\nchanged bytes\n')
    monkeypatch.setattr(methods, 'resolve_root', lambda: replacement)
    drift = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode=mode)
    assert drift['tasks'][0]['method_basis_status'] == 'basis_changed' and not drift['context_ready']
    assert drift['tasks'][0]['method_manifest'] == task['method_manifest']
    assert drift['tasks'][0]['current_method_release'] != task['method_release']
    first.unlink()
    missing = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode=mode)
    assert any(b['state'] == 'unavailable' for b in missing['bodies'].values())
    assert missing['tasks'][0]['current_method_release'] is None
    assert not missing['context_ready'] and missing['tasks'][0]['sources'] == document['sources']
    ref = document['sources'][0]['extract']; (store.project_root / ref['path']).write_bytes(b'corrupt')
    partial = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode=mode)
    assert any(b['kind'] == 'source_extract' and b['state'] == 'unavailable' for b in partial['bodies'].values())
    assert any(b['kind'] == 'source_extract' and b['state'] != 'unavailable' for b in partial['bodies'].values())
    assert len(partial['tasks'][0]['source_reading']) == 2 and not partial['context_ready']


@pytest.mark.parametrize('skill', methods.PUBLIC_SKILLS)
def test_four_roles_recovery_readonly_no_task_and_exact_task_contract(tmp_path, skill):
    project, store, document, task = _project(tmp_path)
    before = _snapshot(project)
    for entry in methods.ENTRY_MODES:
        text = f'{skill}: explicit synthetic request' if entry == 'natural' else None
        # Non-content roles get their own read-only entry, never implicit dispatch.
        actual_task = task['task_id'] if skill in ('deck-master', 'deck-content') else None
        old = methods.read_skill_methods(skill, entry_mode=entry, project=project, task_id=actual_task, text=text)
        new = methods.read_skill_methods(skill, entry_mode=entry, project=project, task_id=actual_task, text=text, read_protocol=PROTOCOL)
        assert new['context'] == old['context']
        assert new['host_application'] == old['host_application'] == 'not_recorded'
        if actual_task:
            assert _hydrate(new['tasks'][0], new['bodies']) == old['dispatch']['work_order']
        else:
            assert [e['id'] for e in new['entry_methods']] == [e['id'] for e in old['methods']]
    assert _snapshot(project) == before


def test_cli_negotiation_methods_and_file_offer(tmp_path, capsys):
    project, store, _, task = _project(tmp_path)
    before = _snapshot(project)
    assert cli.main(['continue', '--project', str(project), '--read-protocol', 'future']) == 2
    assert json.loads(capsys.readouterr().err)['error']['code'] == 'read_protocol_unsupported'
    assert _snapshot(project) == before
    offer = tmp_path / 'offer.json'; offer.write_text(json.dumps({'session_id': 'host', 'context_generation': '1', 'resources': []}))
    assert cli.main(['methods', '--project', str(project), '--task-id', task['task_id'], '--read-protocol', PROTOCOL,
                     '--body-mode', 'delta', '--cache-offer', str(offer)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema_version'] == PROTOCOL and result['context_ready']
    assert all(b['state'] == 'returned' for b in result['bodies'].values())


@pytest.mark.parametrize('kind,stage', [('reconstruct', None), ('review', 'page_visual'), ('review', 'final')])
def test_visual_orders_keep_complete_pages_originals_notes_design_and_result_policy(tmp_path, kind, stage):
    from test_rc3_adopted_design_handoff import _adopted, _open, _visual_inputs
    project, store, _, sent, _ = _adopted(tmp_path)
    if kind == 'review':
        _visual_inputs(store, sent)
    task = _open(store, kind=kind, review_stage=stage)
    document = store.load_document()
    before = _snapshot(project)
    v1 = service.task_summary(store, document, task)
    v2 = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    order = v2['tasks'][0]
    assert _hydrate(order, v2['bodies']) == v1
    assert order['reference_images'] == v1['reference_images']
    from PIL import Image
    import io
    with Image.open(io.BytesIO(sent[2].png)) as image:
        assert order['reference_images'][0]['dimensions'] == list(image.size)
    original_ref = order['reference_images'][0]['file']
    assert sha256_bytes(store.read_object_bytes(original_ref)) == original_ref['sha256']
    for page in order['page_reading']:
        actual = json.loads(v2['bodies'][page['body_ref']]['content'])
        expected = store.read_object_json(page['page_ref'])
        assert actual == expected and 'speaker_notes' in actual and 'content_mapping' in actual
    assert order['page_design_contexts'] == v1['page_design_contexts']
    assert order['produced_against'] == task['produced_against']
    assert order['required_capabilities'] == v1['required_capabilities']
    assert order.get('review_plan') == v1.get('review_plan')
    skill = 'deck-design' if kind == 'reconstruct' else 'deck-review'
    for entry in methods.ENTRY_MODES:
        args = dict(entry_mode=entry, project=project, task_id=task['task_id'],
                    text=f'{skill}: synthetic fixed Task' if entry == 'natural' else None)
        old = methods.read_skill_methods(skill, **args)
        new = methods.read_skill_methods(skill, read_protocol=PROTOCOL, **args)
        assert _hydrate(new['tasks'][0], new['bodies']) == old['dispatch']['work_order']
        assert new['context'] == old['context']
    observed = {'session_id': 'observed-visual-host', 'context_generation': '1'}
    offer = {**observed, 'resources': [{'kind': b['kind'], 'sha256': b['sha256']} for b in v2['bodies'].values()]}
    delta = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode='delta',
                                 cache_offer=offer, observed_context=observed)
    assert delta['tasks'] == v2['tasks'] and delta['context_ready']
    assert _snapshot(project) == before


def test_v2_schema_serialization_is_registered_and_valid(tmp_path):
    import jsonschema
    from deck_master.models import SCHEMA_FILES
    _, store, document, task = _project(tmp_path)
    assert SCHEMA_FILES[PROTOCOL] == 'work-context.v2.schema.json'
    root = Path(__file__).resolve().parents[2]
    schema_path = root / 'src/deck_master/resources/contracts/work-context.v2.schema.json'
    mirror = root / 'docs/specs/deck-master-next-iteration-20261019/contracts/work-context.v2.schema.json'
    assert schema_path.read_bytes() == mirror.read_bytes()
    schema = json.loads(schema_path.read_bytes())
    for mode in ('full', 'delta', 'manifest'):
        response = service.task_summary(store, document, task, read_protocol=PROTOCOL, body_mode=mode)
        jsonschema.validate(json.loads(json.dumps(response)), schema)


def test_corrupt_original_image_keeps_readable_manuscript_and_exact_refs(tmp_path):
    from test_rc3_adopted_design_handoff import _adopted, _open
    project, store, _, _, _ = _adopted(tmp_path)
    task = _open(store)
    document = store.load_document()
    full = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    original = full['tasks'][0]['reference_images'][0]
    (store.project_root / original['file']['path']).write_bytes(b'corrupt original image')
    partial = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    assert not partial['context_ready']
    assert partial['tasks'][0]['reference_images'][0]['file'] == original['file']
    assert partial['tasks'][0]['reference_images'][0]['artifact'] == original['artifact']
    assert partial['tasks'][0]['page_reading']
    assert any(g['kind'] == 'original_image' for g in partial['resource_gaps'])


def test_public_create_continue_v2_preserve_business_response_and_persistent_protocol(tmp_path):
    project = tmp_path / 'negotiated-project'
    created = service.create(project, brief='SYNTHETIC_ENGINEERING negotiated create', read_protocol=PROTOCOL)
    assert created['schema_version'] == PROTOCOL and created['context_ready']
    assert created['pending_tasks'] and created['bodies']
    store = Store(project)
    task = store.read_object_json(store.load_document()['tasks'][0])
    assert task.get('protocol_version') != PROTOCOL
    assert PROTOCOL not in task.get('required_capabilities', [])
    before = _snapshot(project)
    legacy = service.continue_project(project)
    full = service.continue_project(project, read_protocol=PROTOCOL)
    assert {key: full[key] for key in legacy if key != 'pending_tasks'} == {key: value for key, value in legacy.items() if key != 'pending_tasks'}
    assert [_hydrate(order, full['bodies']) for order in full['pending_tasks']] == legacy['pending_tasks']
    assert _snapshot(project) == before


def test_corrupt_page_keeps_task_and_other_immutable_facts(tmp_path):
    from test_rc3_adopted_design_handoff import _adopted, _open
    _, store, _, _, _ = _adopted(tmp_path)
    task = _open(store)
    document = store.load_document()
    ref = document['pages'][0]['page']
    (store.project_root / ref['path']).write_bytes(b'corrupt page bytes')
    response = service.task_summary(store, document, task, read_protocol=PROTOCOL)
    order = response['tasks'][0]
    assert not response['context_ready'] and order['task_id'] == task['task_id']
    assert order['produced_against'] == task['produced_against']
    assert order['sources'] == document['sources'] and order['page_entries'][0]['page'] == ref
    assert order['reference_images'][0]['dimensions'] and order['reference_images'][0]['file']
    assert any(b['kind'] == 'page' and b['state'] == 'unavailable' for b in response['bodies'].values())
    assert any(b['kind'] == 'method' and b['state'] == 'returned' for b in response['bodies'].values())
