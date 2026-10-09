"""Pressure fixture contracts; synthetic metadata is never production proof."""
import importlib.util
from pathlib import Path

from deck_master import editing, tasks
from deck_master.store import Store


def module(name):
    path = Path(__file__).resolve().parents[2] / 'examples' / 'workbench' / (name+'.py')
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_usability_pressure_fixture_keeps_counts_and_pages_adds_readable_history(tmp_path):
    factory = module('w01_pressure')
    pressure = module('w10_pressure')
    project = tmp_path / 'project'
    manifest = factory.create_fixture(project, page_count=24)
    store = Store(project)
    before = store.load_document()
    prepared = pressure.prepare_usability_fixture(project, history_count=25)
    after = store.load_document()
    assert prepared['synthetic'] and prepared['model_calls'] == 0 and not prepared['native_host_evidence']
    assert len(after['candidates']) == manifest['candidate_count'] == 120
    assert [row['page'] for row in after['pages']] == [row['page'] for row in before['pages']]
    for old, new in zip(before['pages'], after['pages']):
        if old['blueprint']:
            assert store.read_object_json(old['blueprint'])['file'] == store.read_object_json(new['blueprint'])['file']
        else:
            assert new['blueprint'] is None
    analysis = tasks._lookup_task(after, prepared['analysis_task_id'], store)
    assert analysis['status'] == 'completed' and analysis['call_allowances'] == []
    spec = store.read_object_json(analysis['result_refs'][0])
    assert len(spec['references']) == 1 and 'Synthetic' in spec['limitations'][0]
    first = editing.history(project, limit=20)
    assert len(first['revisions']) == 20 and first['pagination']['next_cursor']
    second = editing.history(project, revision=first['current'], limit=20, cursor=first['pagination']['next_cursor'])
    assert first['current'] == second['current'] and second['revisions']
    assert not set(row['revision_id'] for row in first['revisions']) & set(row['revision_id'] for row in second['revisions'])
