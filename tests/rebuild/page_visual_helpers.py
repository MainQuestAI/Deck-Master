"""Synthetic Host results for workflow tests; no human review claim."""
from __future__ import annotations

from deck_master import service


def make_page_reviews(task):
    requirement = task['page_visual_requirements'][0]
    reviews = []
    for kind in requirement['review_kinds']:
        reviews.append({
            'schema_version': 'deck_review.v1',
            'review_id': f"{task['task_id']}-{kind}",
            'kind': kind,
            'review_stage': 'page_visual',
            'status': 'pass',
            'subjects': requirement['subject_refs'],
            'dependencies': requirement['dependencies'],
            'reviewer': {'type': 'host_self', 'id': 'synthetic-test-host',
                         'execution_ref': None, 'independence_confirmed': False},
            'observations': ['Synthetic test inspected the current original and SVG preview.'],
            'findings': [],
            'created_at': '2026-09-25T00:00:00Z',
            'replaces': None,
        })
    return reviews


def pass_page_review(project, task):
    return service.accept_result(project, task_id=task['task_id'],
                                 operation_id=task['operation_id'],
                                 produced_against=task['produced_against'],
                                 result_payload={'kind': 'review', 'reviews': make_page_reviews(task)})
