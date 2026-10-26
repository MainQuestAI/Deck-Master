"""Failure lookup work must not grow as failed tasks times all tasks."""
from types import SimpleNamespace

import pytest

from deck_master.current_relationship import CurrentRelationships


@pytest.mark.parametrize('count', [100, 500, 1000])
def test_failed_tasks_do_not_rescan_task_collection(count):
    class Tasks(dict):
        visits = 0

        def items(self):
            for pair in super().items():
                self.visits += 1
                yield pair

    tasks = Tasks({str(i): {'task_id': str(i), 'status': 'failed', 'kind': 'compose',
                           'scope_pages': [], 'instruction': str(i)} for i in range(count)})
    relationships = CurrentRelationships(SimpleNamespace(document={}, store=None), tasks)
    assert tasks.visits == count
    for task in tasks.values():
        assert relationships._successor(task) is None
    assert tasks.visits == count
