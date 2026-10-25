"""Compatibility views over the shared, snapshot-scoped current relationship.

The projection is read-only; currentness never authorizes production writes.
"""
from .current_relationship import CurrentRelationships


def legacy_relation(value):
    """Keep the original action display fields while sharing relationship facts."""
    result = {'state': 'current' if value['status'] == 'background' else value['status'],
              'reason': value['reason']}
    if value.get('successor_task_id'):
        result['successor_id'] = value['successor_task_id']
    return result


class Projection:
    def __init__(self, ctx, tasks):
        self.ctx, self.tasks = ctx, tasks
        self.relationships = CurrentRelationships(ctx, tasks)

    def task(self, task):
        return legacy_relation(self.relationships.task(task))

    def candidate(self, candidate):
        value = self.relationships.candidate(candidate)
        if value['status'] == 'historical':
            return 'stale'
        return 'current' if value['status'] in ('current', 'background') else 'unknown'
