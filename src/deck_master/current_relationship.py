"""Snapshot-scoped current relationship for UI readers, never production permission.

A historical failure remains failed. A stale candidate remains undecided. This
projection only determines whether either belongs in the current action queue.
Unknown calls are handled separately and must never disappear with old work.
"""
from .snapshots import READ_FAILURES


def relation(status, reason, **facts):
    return {'status': status, 'reason': reason, **facts}


def request_relationship(document, task):
    request = (document.get('collaboration') or {}).get('request')
    binding = task.get('collaboration_binding') or {}
    if not request:
        return relation('current', 'legacy_dependency_check')
    if not binding.get('request_id'):
        return relation('unknown', 'request_binding_missing')
    if binding['request_id'] == request['request_id']:
        return relation('current', 'current_request')
    if binding['request_id'] in (request.get('background_request_ids') or []):
        return relation('background', 'explicit_background_request')
    return relation('historical', 'request_replaced')


def candidate_relationship(document, task, state):
    if task is None:
        return relation('unknown', 'candidate_task_unreadable')
    request = request_relationship(document, task)
    if request['status'] not in ('current', 'background'):
        return request
    basis = state.get('generation_basis') or state.get('content_basis') or {}
    if basis.get('status') != 'current':
        return relation('historical', 'candidate_basis_changed', changed_fields=basis.get('changed_fields', []))
    return relation(request['status'], 'candidate_basis_current')


class _ReaderStore:
    """Reuse validated immutable objects inside one read without changing Store."""
    def __init__(self, ctx):
        self.ctx = ctx

    def read_object_json(self, ref):
        return self.ctx.read(ref)

    def load_document(self, revision=None):
        return self.ctx.read_snapshot(revision or self.ctx.document['revision_id'])

    def __getattr__(self, name):
        return getattr(self.ctx.store, name)


class CurrentRelationships:
    def __init__(self, ctx, tasks):
        self.ctx, self.document = ctx, ctx.document
        self.store = _ReaderStore(ctx)
        self.tasks = tasks
        self.task_cache, self.candidate_cache = {}, {}
        self.kept_ids = None
        self.task_positions = {task_id: i for i, task_id in enumerate(tasks)}
        refs = [ref for entry in self.document.get('pages', []) for ref in
                (entry.get(slot) for slot in ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview'))]
        refs += list(self.document.get('outputs', {}).values()) + self.document.get('reviews', [])
        refs.append(self.document.get('content_plan'))
        self.adopted_refs = {ref['sha256'] for ref in refs if isinstance(ref, dict)}

    def _successor(self, task):
        position = self.task_positions.get(task['task_id'], -1)
        for task_id, successor in self.tasks.items():
            if self.task_positions[task_id] <= position or successor['status'] != 'completed':
                continue
            if (successor.get('collaboration_binding') or {}).get('request_id') != (task.get('collaboration_binding') or {}).get('request_id'):
                continue
            if successor.get('review_stage') != task.get('review_stage'):
                continue
            if successor['kind'] != task['kind'] or set(successor.get('scope_pages', [])) != set(task.get('scope_pages', [])):
                continue
            if request_relationship(self.document, successor)['status'] not in ('current', 'background'):
                continue
            # A later label alone is insufficient: its real result must be an
            # adopted current object. Candidate returns do not satisfy this.
            if any(ref.get('sha256') in self.adopted_refs for ref in successor.get('result_refs', [])):
                return task_id
        return None

    def task(self, task):
        key = task['task_id']
        if key in self.task_cache:
            return self.task_cache[key]
        result = request_relationship(self.document, task)
        if task['status'] in ('superseded', 'cancelled'):
            result = relation('historical', 'task_' + task['status'])
        elif result['status'] in ('current', 'background'):
            successor = self._successor(task) if task['status'] == 'failed' else None
            if successor:
                result = relation('historical', 'adopted_successor', successor_task_id=successor)
            elif task['status'] == 'completed' and task.get('candidate_refs'):
                statuses = []
                for ref in task['candidate_refs']:
                    try: statuses.append(self.candidate(self.ctx.overview_metadata(ref))['status'])
                    except READ_FAILURES: statuses.append('unknown')
                if not any(status in ('current','background') for status in statuses):
                    result = relation('unknown' if 'unknown' in statuses else 'historical', 'candidate_basis_not_current')
            else:
                from .tasks import task_inputs_current
                try:
                    if not task_inputs_current(self.store, self.document, task, read_snapshot=self.ctx.read_snapshot):
                        result = relation('historical', 'task_inputs_changed')
                except READ_FAILURES:
                    self.ctx.read_failed = True
                    result = relation('unknown', 'task_basis_unreadable')
        self.task_cache[key] = result
        return result

    def candidate(self, candidate):
        key = candidate.get('candidate_id')
        if not isinstance(key,str) or not 1<=len(key)<=128:
            return relation('unknown','target_identity_mismatch')
        if key not in self.candidate_cache:
            task = self.tasks.get(candidate.get('task_id'))
            request = request_relationship(self.document, task) if task else relation('unknown', 'candidate_task_unreadable')
            if request['status'] not in ('current', 'background'):
                result = request
            else:
                from .candidates import basis_state
                try:
                    state = basis_state(self.store, self.document, candidate, task, read_snapshot=self.ctx.read_snapshot)
                    result = candidate_relationship(self.document, task, state)
                except READ_FAILURES:
                    self.ctx.read_failed = True
                    result = relation('unknown', 'candidate_basis_unreadable')
            self.candidate_cache[key] = result
        return self.candidate_cache[key]

    def pending_candidates(self, task, adopted):
        refs = []
        if self.kept_ids is None:
            self.kept_ids = {}
            for ref in self.document.get('candidate_decisions', []):
                try:
                    decision = self.ctx.read(ref)
                    self.kept_ids[decision['candidate_id']] = decision['decision'] == 'keep_current'
                except READ_FAILURES:
                    self.kept_ids = {}
                    break
        for ref in task.get('candidate_refs', []):
            if ref['sha256'] in adopted:
                continue
            try:
                candidate = self.ctx.overview_metadata(ref)
                if self.kept_ids.get(candidate['candidate_id']):
                    continue
                if self.candidate(candidate)['status'] != 'historical':
                    refs.append(ref)
            except READ_FAILURES:
                refs.append(ref)
        return refs
