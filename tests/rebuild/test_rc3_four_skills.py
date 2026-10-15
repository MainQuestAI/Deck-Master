"""L1 responsibility/method dispatch checks, not evidence of Host application."""
from pathlib import Path

import pytest

from deck_master import method_resources, service
from deck_master.models import sha256_bytes
from deck_master.store import Store
from rc3_fixtures import read_request_completion, source_snapshot


PROMPTS = {
    'deck-master': 'Continue the complete deck within the existing request',
    'deck-content': '只写完整逐页稿，不制作PPT',
    'deck-design': '只设计一页样页方案，不执行图像调用',
    'deck-review': '只读审查现有文件，不修复',
}


@pytest.mark.parametrize('skill', method_resources.PUBLIC_SKILLS)
@pytest.mark.parametrize('mode', method_resources.ENTRY_MODES)
def test_sixteen_entry_paths_read_one_canonical_method_set_without_writes(tmp_path, skill, mode):
    project = tmp_path / 'project'
    service.create(project, brief='explicit synthetic scope; no production grant')
    before = source_snapshot(project)
    result = method_resources.read_skill_methods(
        skill, entry_mode=mode, project=project,
        text=PROMPTS[skill] if mode == 'natural' else None)
    assert result['skill'] == skill and result['entry_mode'] == mode
    assert result['consumption'] == 'runtime_returned_bytes'
    assert result['host_application'] == 'not_recorded'
    assert result['context']['completion'] == read_request_completion(project)
    root = method_resources.resolve_root()
    for item in result['methods']:
        path = Path(item['path'])
        assert path.is_relative_to(root)
        assert path.read_bytes() == item['content'].encode('utf-8')
        assert sha256_bytes(path.read_bytes()) == item['sha256']
    # Repeated pure method reads never dispatch, claim or create revisions.
    after_continue = source_snapshot(project)
    method_resources.read_skill_methods(skill, entry_mode=mode, project=project,
                                       text=PROMPTS[skill] if mode == 'natural' else None)
    assert source_snapshot(project) == after_continue
    assert before == after_continue


@pytest.mark.parametrize(('text', 'intent'), [
    ('只做内容策划', 'plan_only'), ('按确认大纲写完整逐页稿', 'write_only'),
    ('只给六页写逐字讲稿', 'speech_only'), ('提供完整内容包', 'content_full'),
])
def test_content_intents_route_without_becoming_authority(text, intent):
    route = method_resources.route_request(text)
    assert route['skill'] == 'deck-content' and route['content_intent'] == intent
    assert route['authority'] == 'routing_suggestion_only'


def test_real_framing_workorder_and_responsibility_mismatch(tmp_path):
    project = tmp_path / 'project'
    response = service.create(project, brief='planning only, synthetic input')
    store = Store(project)
    task = store.read_object_json(store.load_document()['tasks'][0])
    result = method_resources.read_skill_methods('deck-content', project=project, task_id=task['task_id'])
    assert result['dispatch']['work_order']['protocol_version'] == 'compose.v2'
    assert result['dispatch']['work_order']['method_release'] == result['dispatch']['current_method_release']
    assert result['context']['completion'] == response['completion']
    with pytest.raises(ValueError, match='does not execute compose'):
        method_resources.read_skill_methods('deck-review', project=project, task_id=task['task_id'])
    with pytest.raises(ValueError, match='routes to deck-review'):
        method_resources.read_skill_methods('deck-content', entry_mode='natural', text='只读审查文件')
    with pytest.raises(ValueError, match='existing project'):
        method_resources.read_skill_methods('deck-design', entry_mode='recovery')


def test_task_reader_consumes_actual_workorder_list_instead_of_recomputing_count(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    service.create(project, brief='synthetic manifest-list regression')
    store = Store(project)
    task = store.read_object_json(store.load_document()['tasks'][0])
    summary = service.task_summary

    def explicit_smaller_manifest(*args, **kwargs):
        order = summary(*args, **kwargs)
        order['method_resources'] = order['method_resources'][:2]
        return order

    monkeypatch.setattr(service, 'task_summary', explicit_smaller_manifest)
    result = method_resources.read_skill_methods('deck-content', project=project, task_id=task['task_id'])
    assert [item['id'] for item in result['methods']] == ['source-reading', 'content-methods']
    assert [item['id'] for item in result['entry_methods']] == ['collaboration-routing']
    assert method_resources.read_task_methods(project, task['task_id'])['methods'] == result['methods']


def test_public_skills_declare_real_responsibility_and_only_one_reference_tree():
    root = Path(__file__).resolve().parents[2] / 'skills'
    for name in method_resources.PUBLIC_SKILLS:
        text = (root / name / 'SKILL.md').read_text()
        for required in ('Use when', 'Do not use when', '允许产物', '退出条件', '下一责任'):
            assert required in text
        if name != 'deck-master':
            assert not (root / name / 'references').exists()
    assert 'speech_only' in (root / 'deck-content/SKILL.md').read_text()
    assert '不制作也不自动修复' in (root / 'deck-review/SKILL.md').read_text()
