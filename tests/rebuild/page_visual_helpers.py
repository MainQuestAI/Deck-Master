"""Synthetic Host results for workflow tests; no human review claim."""
from __future__ import annotations

from deck_master import service
from rc3_fixtures import claim_fixture_task


def make_page_reviews(task):
    requirement = task['page_visual_requirements'][0]
    reviews = []
    for kind in requirement['review_kinds']:
        reviews.append({
            'schema_version': 'deck_review.v2',
            'review_id': f"{task['task_id']}-{kind}",
            'kind': kind,
            'review_stage': 'page_visual',
            'status': 'pass',
            'subjects': requirement['subject_refs'],
            'dependencies': requirement['dependencies'],
            'reviewer': {'type': 'host_self', 'id': 'synthetic-test-host',
                         'execution_ref': 'synthetic-l1-page-review', 'independence_confirmed': False,
                         'evidence_ref': None, 'identity_receipt': None, 'assurance': 'host_attested'},
            'observations': ['L1 synthetic protocol fixture inspected the bound original and SVG preview; no human/model quality claim.'],
            'findings': [],
            'created_at': '2026-09-25T00:00:00Z',
            'replaces': None,
        })
    return reviews


def pass_page_review(project, task):
    claim_fixture_task(project, task, execution_ref='synthetic-l1-page-review')
    return service.accept_result(project, task_id=task['task_id'],
                                 operation_id=task['operation_id'],
                                 produced_against=task['produced_against'],
                                 result_payload={'kind': 'review', 'reviews': make_page_reviews(task)})
