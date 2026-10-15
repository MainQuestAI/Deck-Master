"""Real modern editorial workorders retain their raw and unknown instructions."""
import pytest

from deck_master import run_desk, tasks
from deck_master.samples import create_sample
from deck_master.store import Store
from test_content_ops import commit, prepare_editorial_project, value


@pytest.mark.parametrize('mode', ['auto', 'trial'])
def test_actual_editorial_v2_summary_preserves_user_reason_and_unknown_suffix(tmp_path, mode):
    project = tmp_path / 'editorial'
    create_sample(project, page_count=3, readonly=False)
    prepare_editorial_project(project, review=False)
    store = Store(project)
    authored = value(store, action='rewrite', ids=('p02',), mode=mode)
    authored['instruction'] = '保留用户讨论 API、Page v2 与 proposal Ref 的原话。\n只改所选正文。'
    dispatched = commit(project, store, authored)
    task = tasks._lookup_task(store.load_document(), dispatched['task_ids'][0], store)
    raw = task['instruction']
    assert task['protocol_version'] == 'compose.v2'
    row = run_desk.task_row(task)
    assert row['display_instruction'].startswith(authored['instruction'] + ' · 改写所选正文')
    assert 'changed_layers仅page_copy/plan' not in row['display_instruction']
    assert ('先返回候选' in row['display_instruction']) is (mode == 'trial')
    assert task['instruction'] == row['instruction'] == raw
    task['instruction'] += ' 用户另加的完整说明必须原样展示。'
    assert run_desk.task_row(task)['display_instruction'] == task['instruction']
