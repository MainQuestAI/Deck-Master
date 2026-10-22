"""Read-only current-action projection; recorded statuses are never rewritten."""
import json

from .snapshots import READ_FAILURES, snapshot_signature


class Projection:
    def __init__(self, ctx, tasks):
        self.ctx, self.tasks = ctx, tasks
        self.bases = {}
        self.relations = {}
        self.current_request = ((ctx.document.get('collaboration') or {}).get('request') or {}).get('request_id')

    def task(self, task):
        if task['task_id'] not in self.relations:
            self.relations[task['task_id']] = self._task(task)
        return self.relations[task['task_id']]

    def _task(self, task):
        bound = (task.get('collaboration_binding') or {}).get('request_id')
        if any(call.get('state') == 'unknown' for call in task.get('call_allowances', [])):
            return {'state': 'unknown', 'reason': 'unknown_call_unresolved'}
        if bound and self.current_request and bound != self.current_request:
            return {'state': 'historical', 'reason': 'previous_request'}
        if task['status'] == 'superseded':
            return {'state': 'historical', 'reason': 'explicitly_superseded'}
        if task['status'] == 'awaiting_host' and task.get('stage_request'):
            from .candidates import inputs_current
            try:
                self._revision(task)
                if not inputs_current(self, self.ctx.document, task):
                    return {'state': 'current', 'reason': 'dependency_basis_changed'}
            except READ_FAILURES:
                self.ctx.read_failed = True
                return {'state': 'unknown', 'reason': 'dependencies_unverifiable'}
        # A later attempt alone is not a successor. Require the same recorded
        # request, kind, instruction and scope, and its output in current slots.
        if bound and bound == self.current_request and task['status'] == 'failed':
            current = [e.get(k) for e in self.ctx.document['pages'] for k in
                       ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview')]
            current += list((self.ctx.document.get('outputs') or {}).values())
            for other in self.tasks.values():
                if (other['status'] == 'completed' and
                    (other.get('collaboration_binding') or {}).get('request_id') == bound and
                    all(other.get(k) == task.get(k) for k in ('kind', 'scope_pages', 'instruction')) and
                    other.get('created_at', '') >= task.get('created_at', '') and
                    set(task.get('scope_pages', [])) <= set(self.ctx.pages) and
                    any(ref in current for ref in other.get('result_refs', [])) and
                    all(any(entry.get(slot) in other.get('result_refs', []) for slot in
                            ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview'))
                        for entry in self.ctx.document['pages'] if entry['page_id'] in task.get('scope_pages', []))):
                    return {'state': 'historical', 'reason': 'adopted_successor', 'successor_id': other['task_id']}
        return {'state': 'current' if bound and bound == self.current_request else 'unknown',
                'reason': 'current_request' if bound and bound == self.current_request else 'request_binding_missing'}

    def candidate(self, candidate):
        from .candidates import _state
        task = self.tasks.get(candidate.get('task_id'))
        if task is None:
            return 'unknown'
        relation = self.task(task)
        if relation['state'] == 'historical':
            return 'stale'
        # Memoize equivalent bases only within this response, never eligibility.
        key = json.dumps([task['task_id'], candidate.get('page_id'), candidate.get('stage'),
            candidate.get('result_kind'), candidate.get('generation_basis'), candidate.get('content_basis')], sort_keys=True)
        if key not in self.bases:
            try:
                self._revision(task)
                # Decisions/adoptions are handled by the callers before this
                # undecided-only freshness query, avoiding a quadratic scan.
                doc = dict(self.ctx.document, candidate_decisions=[], candidate_adoptions=[])
                value = _state(self, doc, candidate, task)
                status = (value.get('content_basis') or value.get('generation_basis'))['status']
                self.bases[key] = 'stale' if status == 'changed' else 'current'
            except READ_FAILURES:
                self.ctx.read_failed = True
                self.bases[key] = 'unknown'
        return self.bases[key]

    def _revision(self, task):
        revision = task.get('dispatch_revision')
        if revision:
            signature = snapshot_signature(self.ctx.store, revision)
            self.ctx.revision_signatures[revision] = signature
            if signature is None:
                self.ctx.read_failed = True

    def read_object_json(self, ref):
        return self.ctx.read(ref)

    def read_object_bytes(self, ref):
        self.ctx.object_stat(ref)
        return self.ctx.store.read_object_bytes(ref)

    def __getattr__(self, name):
        return getattr(self.ctx.store, name)
