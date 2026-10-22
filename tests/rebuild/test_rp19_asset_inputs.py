"""Synthetic local image fixtures; no provider consumption or output-quality claim."""
import copy

import pytest
from PIL import Image

from deck_master import candidates, editing, generation, models, production, service, tasks
from deck_master.models import ModelError
from test_rc3_notes_visual_inputs import enf, _seed_imported_plan


def _image(tmp_path, name, color, format='PNG'):
    path = tmp_path / name
    Image.new('RGB', (16, 12), color).save(path, format=format)
    return path


def _flow(tmp_path, selected=('logo',), format='PNG'):
    project, store = enf._project(tmp_path)
    suffix = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[format]
    path = _image(tmp_path, 'logo.' + suffix, 'red', format)
    service.import_asset(project, asset_id='logo', kind='logo', file_path=path)
    other = _image(tmp_path, 'other.png', 'blue')
    service.import_asset(project, asset_id='other', kind='image', file_path=other)
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['visual_spec']['design_overrides'] = {'selected_asset_ids': list(selected)}
    editing.edit_page(project, page=page, base_revision=doc['revision_id'],
                      page_hash=doc['pages'][0]['page']['sha256'], operation_id='rp19-select')
    _seed_imported_plan(store)
    enf._start(project, store)
    enf._settle_preproduction(store, seed='rp19-synthetic')
    enf._grant(project, store, actions=('dispatch.blueprint', 'allowance.allocate', 'task.start'))
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc['pages'][0])
    return project, store, task, path


@pytest.mark.parametrize('format', ['PNG', 'JPEG', 'WEBP'])
def test_registered_selected_original_bytes_reach_exact_frozen_tool_references(tmp_path, format):
    project, store, task, source = _flow(tmp_path, format=format)
    prepared, _ = production.stored_blueprint_request(store, task)
    inputs = prepared['resolved_design_context']['asset_inputs']
    models.validate_schema('asset_inputs', inputs)
    assert len(inputs['images']) == 1
    image = inputs['images'][0]
    artifact = store.read_object_json(image['artifact_ref'])
    assert artifact['provenance']['source_type'] == 'user_supplied'
    assert store.read_object_bytes(image['file']) == source.read_bytes()
    assert artifact['file'] == image['file']
    assert image['asset_id'] == 'logo'
    assert [a['asset_id'] for a in prepared['projection']['permitted_assets']] == ['logo']
    proposed = generation.prepared_input(store, store.load_document(), task)
    assert proposed['references'] == [{'file': image['file'], 'role': 'reference'}]
    service.task_start(project, task_id=task['task_id'], execution_ref='rp19-synthetic',
        supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    frozen = generation.freeze(project, task_id=task['task_id'], input=proposed,
        base_revision=store.current_revision_id(), operation_id='rp19-freeze')
    assert frozen['input'] == proposed
    assert store.load_document()['compatibility']['minimum_writer'] == 'asset-inputs.v1'
    assert store.read_object_json(store.load_document()['tasks'][0]).get('generation_attempts', []) == []


def test_no_selection_does_not_treat_permission_as_consumption(tmp_path):
    _, store, task, _ = _flow(tmp_path, selected=())
    prepared, _ = production.stored_blueprint_request(store, task)
    assert prepared['projection']['permitted_assets'] == []
    assert generation.prepared_input(store, store.load_document(), task)['references'] == []
    assert prepared['projection']['asset_inputs']['images'] == []


@pytest.mark.parametrize('asset_id,expected', [('logo', False), ('other', True)])
def test_replaced_bytes_stale_only_consuming_page_and_preserve_old_original(tmp_path, asset_id, expected):
    project, store, task, _ = _flow(tmp_path)
    prepared, ref = production.stored_blueprint_request(store, task)
    original = prepared['projection']['asset_inputs']['images'][0]
    old_bytes = store.read_object_bytes(original['file'])
    old_basis = candidates.generation_basis(store, store.load_document(), 'p1', 'blueprint', task=task)
    replacement = _image(tmp_path, 'replacement.png', 'green')
    service.import_asset(project, asset_id=asset_id, kind='logo' if asset_id == 'logo' else 'image', file_path=replacement)
    assert tasks.task_inputs_current(store, store.load_document(), task) is expected
    current_basis = candidates.generation_basis(store, store.load_document(), 'p1', 'blueprint', task=task)
    assert (current_basis == old_basis) is expected
    if expected:
        assert tasks._lookup_task(store.load_document(), task["task_id"], store)["status"] == "awaiting_host"
    assert store.read_object_bytes(original['file']) == old_bytes
    assert production.stored_blueprint_request(store, task) == (prepared, ref)


def test_revoked_permission_blocks_old_task_and_new_freeze(tmp_path):
    project, store, task, source = _flow(tmp_path)
    service.import_asset(project, asset_id='logo', kind='logo', file_path=source, external_use='restricted')
    assert not tasks.task_inputs_current(store, store.load_document(), task)
    with pytest.raises(tasks.TaskConflict, match="superseded"):
        service.task_start(project, task_id=task['task_id'], execution_ref='rp19-revoked',
            supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])


def test_selected_ids_cannot_expand_page_permissions_or_name_duplicates(tmp_path):
    _, store, task, _ = _flow(tmp_path)
    request, _ = production.stored_blueprint_request(store, task)
    design = request['resolved_design_context']
    page = store.read_object_json(design['content_basis']['page_ref'])
    for ids in (['missing'], ['logo', 'logo']):
        page['visual_spec']['design_overrides']['selected_asset_ids'] = ids
        with pytest.raises(ModelError, match='unique and permitted'):
            production.resolve_asset_inputs(store, page, design)


def test_asset_contract_is_strict(tmp_path):
    _, store, task, _ = _flow(tmp_path)
    request, _ = production.stored_blueprint_request(store, task)
    value = request['projection']['asset_inputs']
    for mutate in (lambda v: v.update(extra=True), lambda v: v.update(schema_version='asset_inputs.v2'),
                   lambda v: v['images'][0].update(media_type='image/svg+xml')):
        bad = copy.deepcopy(value)
        mutate(bad)
        with pytest.raises(ModelError):
            models.validate_schema('asset_inputs', bad)


@pytest.mark.parametrize('kind,ext,data', [('logo', 'svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
    ('font', 'ttf', b'synthetic-font-not-a-real-face'), ('image', 'png', b'not an image')])
def test_unsupported_or_invalid_attachment_is_explicitly_refused(tmp_path, kind, ext, data):
    from deck_master.content import normalize_design_assets
    from deck_master.store import Store
    store = Store(tmp_path / 'isolated')
    source = tmp_path / ('original.' + ext)
    source.write_bytes(data)
    design = normalize_design_assets(store, {'assets': [{'asset_id': 'asset', 'kind': kind,
        'external_use': 'allowed', 'file': str(source)}], 'allowed_asset_ids': ['asset']}, base_dir=tmp_path)
    page = {'visual_spec': {'design_overrides': {'selected_asset_ids': ['asset']}}}
    with pytest.raises(ModelError):
        production.resolve_asset_inputs(store, page, design)


def test_selected_attachment_cannot_be_omitted_at_freeze(tmp_path):
    project, store, task, _ = _flow(tmp_path)
    proposed = generation.prepared_input(store, store.load_document(), task)
    service.task_start(project, task_id=task['task_id'], execution_ref='rp19-synthetic',
        supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    proposed['references'] = []
    before = store.read_current()
    with pytest.raises(generation.GenerationError, match='input differs from the committed stage request'):
        generation.freeze(project, task_id=task['task_id'], input=proposed,
            base_revision=store.current_revision_id(), operation_id='rp19-omit')
    assert store.read_current() == before


def test_legacy_preparation_does_not_acquire_new_asset_selection(tmp_path):
    from test_rc3_notes_visual_inputs import _blueprint_with_imported_plan
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    doc = store.load_document()
    _, original_ref = production.stored_blueprint_request(store, task)
    resolved = production.resolve_generation_design(store, doc, doc['pages'][0], asset_inputs=False)
    page = store.read_object_json(doc['pages'][0]['page'])
    old = production.project_prompt(page, resolved, [])
    ref = store.put_json_object(old)
    historical_task = copy.deepcopy(task)
    historical_task['inputs'] = [ref if value == original_ref else value for value in task['inputs']]
    before = store.read_object_bytes(ref)
    assert production.stored_blueprint_request(store, historical_task) == (old, ref)
    assert tasks.task_inputs_current(store, doc, historical_task)
    assert store.read_object_bytes(ref) == before
    assert 'asset_inputs' not in old['projection']


def test_registration_timestamp_alone_does_not_stale_consumption(tmp_path):
    _, store, task, _ = _flow(tmp_path)
    doc = copy.deepcopy(store.load_document())
    asset = next(a for a in doc['design_context']['assets'] if a['asset_id'] == 'logo')
    original = store.read_object_json(asset['artifact'])
    changed = {**original, 'created_at': '2030-01-01T00:00:00Z'}
    asset['artifact'] = store.put_json_object(changed)
    assert tasks.task_inputs_current(store, doc, task)
    changed['provenance'] = {'source_type': 'unknown'}
    asset['artifact'] = store.put_json_object(changed)
    assert not tasks.task_inputs_current(store, doc, task)


@pytest.mark.parametrize('format', ['PNG', 'JPEG'])
def test_registered_original_embeds_byte_exactly_in_local_native_pptx(tmp_path, format):
    import zipfile
    from deck_master.compiler import SvgInput, CompileOptions, compile_deck
    from deck_master.pipeline import page_asset_paths
    _, store, task, source = _flow(tmp_path, format=format)
    doc = store.load_document()
    prepared = generation.prepared_input(store, doc, task)
    work = tmp_path / 'local-native-output'
    work.mkdir()
    mapping = page_asset_paths(store, doc, doc['pages'][0], work)
    svg = work / 'synthetic.svg'
    svg.write_text('<svg viewBox="0 0 100 100"><image href="logo" x="0" y="0" width="100" height="75"/></svg>')
    result = compile_deck([SvgInput('p1', svg)], CompileOptions(assets={'p1': mapping}), work / 'compiled')
    with zipfile.ZipFile(result.pptx_path) as deck:
        media = [name for name in deck.namelist() if name.startswith('ppt/media/')]
        assert len(media) == 1
        assert deck.read(media[0]) == store.read_object_bytes(prepared['references'][0]['file']) == source.read_bytes()
    # This is a local native compiler result, not an ImageGen output or adoption.
    assert store.read_object_json(store.load_document()['tasks'][0]).get('generation_attempts', []) == []


def test_record_permission_cannot_be_bypassed_by_allowlist_alone(tmp_path):
    _, store, task, _ = _flow(tmp_path)
    prepared, _ = production.stored_blueprint_request(store, task)
    design = copy.deepcopy(prepared['resolved_design_context'])
    next(a for a in design['assets'] if a['asset_id'] == 'logo')['external_use'] = 'restricted'
    page = store.read_object_json(design['content_basis']['page_ref'])
    with pytest.raises(ModelError, match='not permitted for external use'):
        production.resolve_asset_inputs(store, page, design)
