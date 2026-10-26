"""Failure lookup work must not grow as failed tasks times all tasks."""
from types import SimpleNamespace

import pytest

from deck_master.current_relationship import CurrentRelationships, request_relationship


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


# Exact pre-index predicate from b688c300; test oracle, never a production path.
def _reference_successor(self, task):
    position = self.task_positions.get(task['task_id'], -1)
    scope = set(task.get('scope_pages', []))
    pages = {entry['page_id']: entry for entry in self.document.get('pages', [])}
    if not scope <= pages.keys():
        return None
    for task_id, successor in self.tasks.items():
        if self.task_positions[task_id] <= position or successor['status'] != 'completed':
            continue
        if (successor.get('collaboration_binding') or {}).get('request_id') != (task.get('collaboration_binding') or {}).get('request_id'):
            continue
        if successor.get('review_stage') != task.get('review_stage'):
            continue
        if (successor['kind'] != task['kind']
                or set(successor.get('scope_pages', [])) != scope
                or successor.get('instruction') != task.get('instruction')
                or successor.get('created_at', '') < task.get('created_at', '')):
            continue
        if request_relationship(self.document, successor)['status'] not in ('current', 'background'):
            continue
        # A later label or a result for only part of the failed scope is
        # insufficient. Every affected page must have an adopted result
        # from this matching task; candidate returns do not satisfy this.
        results = successor.get('result_refs', [])
        if (any(ref.get('sha256') in self.adopted_refs for ref in results)
                and all(any(pages[page_id].get(slot) in results for slot in
                            ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview'))
                        for page_id in scope)):
            return task_id
    return None



def test_successor_index_matches_original_mixed_order_and_adoption():
    first = {'path': 'objects/page-one.json', 'sha256': 'one'}
    second = {'path': 'objects/page-two.json', 'sha256': 'two'}
    document = {'pages': [{'page_id': 'p1', 'page': first},
                          {'page_id': 'p2', 'page': second}],
                'collaboration': {'request': {'request_id': 'current',
                                              'background_request_ids': ['background']}}}
    base = {'status': 'completed', 'kind': 'compose', 'scope_pages': ['p1', 'p2'],
            'instruction': 'same', 'created_at': '20', 'review_stage': 'final',
            'collaboration_binding': {'request_id': 'current'},
            'result_refs': [first, second]}
    entries = [
        ('earlier', {}),
        ('failed', {'status': 'failed', 'result_refs': []}),
        ('cancelled', {'status': 'cancelled'}),
        ('old-time', {'created_at': '10'}),
        ('similar', {'instruction': 'same '}),
        ('wrong-kind', {'kind': 'repair'}),
        ('wrong-stage', {'review_stage': 'preproduction'}),
        ('wrong-scope', {'scope_pages': ['p1']}),
        ('other-request', {'collaboration_binding': {'request_id': 'other'}}),
        ('unadopted', {'result_refs': [{'path': 'objects/other.json', 'sha256': 'other'}]}),
        ('partial', {'result_refs': [first]}),
        ('winner', {'scope_pages': ['p2', 'p1', 'p1']}),
        ('late-failure', {'status': 'failed'}),
        ('background-failure', {'status': 'failed', 'collaboration_binding': {'request_id': 'background'}}),
        ('background-winner', {'collaboration_binding': {'request_id': 'background'}}),
        ('historical-failure', {'status': 'failed', 'collaboration_binding': {'request_id': 'other'}}),
        ('historical-completed', {'collaboration_binding': {'request_id': 'other'}}),
        ('missing-page-failure', {'status': 'failed', 'scope_pages': ['missing']}),
        ('missing-page-completed', {'scope_pages': ['missing']}),
    ]
    tasks = {key: {**base, **changes, 'task_id': key} for key, changes in entries}
    relationships = CurrentRelationships(SimpleNamespace(document=document, store=None), tasks)
    expected = {'failed': 'winner', 'late-failure': None,
                'background-failure': 'background-winner', 'historical-failure': None,
                'missing-page-failure': None}
    for key, successor in expected.items():
        assert _reference_successor(relationships, tasks[key]) == successor
        assert relationships._successor(tasks[key]) == successor


@pytest.mark.parametrize('count', [100, 500, 1000])
def test_successor_candidate_and_adoption_work_scales_by_matching_key(count):
    counts = {'index_visits': 0, 'candidate_visits': 0, 'adoption_predicates': 0}

    class Tasks(dict):
        def items(self):
            for pair in super().items():
                counts['index_visits'] += 1
                yield pair

    class Task(dict):
        def get(self, key, default=None):
            if key == 'result_refs':
                counts['adoption_predicates'] += 1
            return super().get(key, default)

    class Candidates(list):
        def __getitem__(self, index):
            counts['candidate_visits'] += 1
            return super().__getitem__(index)

    first = {'path': 'objects/one.json', 'sha256': 'one'}
    second = {'path': 'objects/two.json', 'sha256': 'two'}
    document = {'pages': [{'page_id': 'p1', 'page': first}, {'page_id': 'p2', 'page': second}]}
    tasks = Tasks()
    for index in range(count):
        base = {'kind': 'compose', 'scope_pages': ['p1', 'p2'], 'instruction': str(index),
                'created_at': '20', 'result_refs': [first, second]}
        for suffix, changes in [('failed', {'status': 'failed'}),
                                ('old', {'status': 'completed', 'created_at': '10'}),
                                ('partial', {'status': 'completed', 'result_refs': [first]}),
                                ('full', {'status': 'completed'})]:
            key = f'{index}-{suffix}'
            tasks[key] = Task(base, **changes, task_id=key)
    relationships = CurrentRelationships(SimpleNamespace(document=document, store=None), tasks)
    assert counts['index_visits'] == 4 * count
    for key, (positions, candidates) in list(relationships.successors.items()):
        relationships.successors[key] = positions, Candidates(candidates)
    for index in range(count):
        assert relationships._successor(tasks[f'{index}-failed']) == f'{index}-full'
    assert counts == {'index_visits': 4 * count, 'candidate_visits': 3 * count,
                      'adoption_predicates': 2 * count}
