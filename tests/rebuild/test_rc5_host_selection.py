"""RC5 actual Host command inputs freeze bounded selections before dispatch."""
import copy
import json

import pytest

from deck_master import cli, collaboration_api, method_resources as methods, service
from deck_master.models import ModelError
from deck_master.store import Store


def _create(tmp_path, **kwargs):
    source = tmp_path / 'source.txt'
    source.write_text('Synthetic operating diagnosis: revenue 100, costs 85. No causal conclusion is established.')
    project = tmp_path / 'project'
    result = service.create(project, brief='Explain the operating evidence and open questions', sources=[source], **kwargs)
    return project, result


def _task(project, result):
    store = Store(project)
    tid = result['pending_tasks'][0]['task_id']
    return next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                if store.read_object_json(ref)['task_id'] == tid)


def test_create_freezes_selection_after_final_phase_and_dependencies(tmp_path):
    project, result = _create(tmp_path, selected_resource_ids=['case-e04-walkthrough'])
    task = _task(project, result)
    ids = [row['id'] for row in task['method_manifest']]
    assert ids[-3:] == ['example-e04-input', 'example-e04-after', 'case-e04-walkthrough']
    assert 'method-selection' in ids
    assert task['collaboration_binding']['phase'] == 'framing'
    assert 'selected_resource_ids' not in task
    assert methods.resolve_task_methods(task)['basis_status'] == 'current'


@pytest.mark.parametrize('selection', [['does-not-exist'], ['installation'], 'content-m01'])
def test_create_invalid_selection_does_not_publish_project(tmp_path, selection):
    with pytest.raises(ModelError):
        _create(tmp_path, selected_resource_ids=selection)
    assert not (tmp_path / 'project' / '.deckmaster').exists()


def test_pending_task_selection_rejected_without_rewriting_history(tmp_path):
    project, result = _create(tmp_path)
    original = copy.deepcopy(Store(project).load_document())
    task = _task(project, result)
    with pytest.raises(service.ServiceError, match='frozen'):
        service.continue_project(project, selected_resource_ids=['content-m01'])
    assert Store(project).load_document() == original
    assert _task(project, result) == task


def test_continue_api_forwards_selection_to_new_dispatch(tmp_path):
    project, result = _create(tmp_path)
    service.task_cancel(project, task_id=result['pending_tasks'][0]['task_id'], reason='synthetic formal retirement')
    response, http, _ = collaboration_api.invoke(project, 'continue', {'selected_resource_ids': ['content-m01']})
    assert http < 400, response
    task = Store(project).read_object_json(Store(project).load_document()['tasks'][-1])
    assert 'content-m01' in [r['id'] for r in task['method_manifest']]
    assert 'selected_resource_ids' not in task


@pytest.mark.parametrize('mode', [None, 'full', 'manifest', 'delta'])
def test_methods_cli_selected_bytes_follow_existing_transport(mode, capsys):
    args = ['methods', '--kind', 'compose', '--phase', 'argument', '--read',
            '--selected-resource-id', 'case-e04-walkthrough']
    if mode:
        args += ['--read-protocol', 'work_context.v2', '--body-mode', mode]
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert [m['id'] for m in result['methods']][-3:] == ['example-e04-input', 'example-e04-after', 'case-e04-walkthrough']
    if mode:
        assert all(b['kind'] == 'method' for b in result['bodies'].values())
        assert result['context_ready'] == (mode != 'manifest')
    else:
        assert 'content' in result['methods'][-1]


def test_cli_rejects_supplementing_stored_task(tmp_path, capsys):
    project, result = _create(tmp_path)
    assert cli.main(['methods', '--project', str(project), '--task-id', result['pending_tasks'][0]['task_id'],
                     '--selected-resource-id', 'content-m01']) != 0
    assert 'frozen Task' in capsys.readouterr().err


def test_scope_and_new_defaults_do_not_change_old_selector():
    assert 'method-selection' not in methods.rc3_method_ids_for('compose', phase='framing')
    assert 'method-selection' in methods.method_ids_for('compose', phase='framing')
    assert 'page-writing' in methods.method_ids_for('compose', phase='page_copy')
    assert 'method-selection' not in methods.method_ids_for('compose', phase='speech')
    assert 'writing-profiles' in methods.method_ids_for('compose', phase='speech')
    assert 'method-review' not in methods.method_ids_for('review', intent='page_visual')
    assert 'method-review' in methods.method_ids_for('review', intent='preproduction')
    with pytest.raises(ModelError, match='outside'):
        methods.method_resources('compose', phase='speech', selected_resource_ids=['content-m04'])
    with pytest.raises(ModelError, match='outside'):
        methods.method_resources('review', intent='page_visual', selected_resource_ids=['content-m04'])
    assert any(m['id'] == 'content-m04' for m in methods.method_resources('review', intent='preproduction', selected_resource_ids=['content-m04']))
    read = methods.read_skill_methods('deck-content', selected_resource_ids=['content-m04'])
    assert 'content-m04' in [m['id'] for m in read['methods']]


def test_inputs_update_binds_selection_and_replay_identity(tmp_path):
    from deck_master.errors import InputRevisionConflict
    project, _ = _create(tmp_path)
    base = Store(project).current_revision_id()
    patch = {'task_patch': {'audience': 'Operations managers'}, 'reason': 'Bound audience change'}
    kwargs = dict(patch=patch, base_revision=base, operation_id='selection-update')
    result = service.inputs_update(project, selected_resource_ids=['content-m04'], **kwargs)
    task = Store(project).read_object_json(Store(project).load_document()['tasks'][-1])
    assert 'content-m04' in [m['id'] for m in task['method_manifest']]
    replay = service.inputs_update(project, selected_resource_ids=['content-m04'], **kwargs)
    assert replay['replayed']
    with pytest.raises(InputRevisionConflict):
        service.inputs_update(project, selected_resource_ids=['content-m01'], **kwargs)


def test_continue_invalid_selection_has_no_recovery_side_effects(tmp_path):
    project, _ = _create(tmp_path)
    before = Store(project).load_document()
    with pytest.raises(service.ServiceError, match='registered'):
        service.continue_project(project, selected_resource_ids=['NOT_REGISTERED'])
    assert Store(project).load_document() == before


def test_independent_review_stage_maps_to_review_phase_and_scope():
    result = methods.read_skill_methods('deck-review', review_stage='preproduction',
                                       selected_resource_ids=['content-m04'])
    assert 'content-m04' in [m['id'] for m in result['methods']]
    with pytest.raises(ModelError, match='outside'):
        methods.read_skill_methods('deck-review', review_stage='page_visual',
                                   selected_resource_ids=['content-m04'])


def test_speech_only_revision_scope_rejects_analysis_selection():
    task = {'kind': 'compose', 'intent': 'input_revision',
            'collaboration_binding': {'phase': 'input_revision', 'write_scope': {'layers': ['speech']}}}
    with pytest.raises(ModelError, match='outside'):
        methods.freeze_task_methods(task, selected_resource_ids=['content-m04'])


def test_invalid_input_selection_persists_no_source_or_task_objects(tmp_path):
    project, _ = _create(tmp_path)
    source = tmp_path / 'added.txt'
    source.write_text('New evidence must not be persisted for an invalid selection.')
    def files():
        return {p.relative_to(project): p.read_bytes() for p in project.rglob('*') if p.is_file()}
    before = files()
    with pytest.raises(ModelError):
        service.inputs_update(project,
            patch={'source_changes': {'add': [{'path': str(source)}]}, 'reason': 'new material'},
            base_revision=Store(project).current_revision_id(), operation_id='invalid-selection',
            selected_resource_ids=['NOT_REGISTERED'])
    assert files() == before
