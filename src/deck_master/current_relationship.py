"""Snapshot-scoped current relationship for UI readers, never production permission.

A historical failure remains failed. A stale candidate remains undecided. This
projection only determines whether either belongs in the current action queue.
Unknown calls are handled separately and must never disappear with old work.
"""
from .snapshots import READ_FAILURES
from .models import canonical_json_bytes


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

    def read_object_bytes(self, ref):
        self.ctx.object_stat(ref)
        return self.ctx.store.read_object_bytes(ref)

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
        self.basis_cache = {}
        self.kept_ids = None
        self.task_positions = {task_id: i for i, task_id in enumerate(tasks)}
        refs = [ref for entry in self.document.get('pages', []) for ref in
                (entry.get(slot) for slot in ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview'))]
        refs += list(self.document.get('outputs', {}).values()) + self.document.get('reviews', [])
        refs.append(self.document.get('content_plan'))
        self.adopted_refs = {ref['sha256'] for ref in refs if isinstance(ref, dict)}

    def _successor(self, task):
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

    def _completed_content(self, task, request_status):
        """Compare the adopted result, not the inputs that adoption replaced."""
        from .models import compute_input_digest
        # Receipt resolution proves the complete canonical operation ancestry,
        # including ancestors older than adoption. Endpoint/object signatures
        # do not capture that proof, so never reuse it across summary requests.
        # The relationship and snapshot caches remain scoped to this one read.
        self.ctx.cacheable = False
        receipt = self.store.operation_receipt(task['operation_id'])
        if not receipt:
            return relation('unknown', 'adoption_receipt_missing')
        response = receipt.get('response') or {}
        adopted = self.ctx.read_snapshot(response['revision_id'])
        completed = next((self.ctx.read(ref) for ref in adopted.get('tasks', [])
                          if self.ctx.read(ref).get('task_id') == task['task_id']), None)
        if (not completed or completed.get('status') != 'completed'
                or completed.get('operation_id') != task['operation_id']
                or completed.get('result_refs') != task.get('result_refs')
                or (adopted.get('change') or {}).get('operation_id') != task['operation_id']):
            return relation('unknown', 'adoption_identity_unverified')
        if response.get('adopted') is False:
            # Proposal-only content has not replaced its dispatch inputs.
            from .tasks import task_inputs_current
            return relation(request_status if task_inputs_current(
                self.store, self.document, task, read_snapshot=self.ctx.read_snapshot)
                else 'historical', 'content_proposal_basis')

        def slots(document):
            values = {('page', entry['page_id']): entry['page']
                      for entry in document.get('pages', [])}
            values.update({(name, ''): document[name] for name in ('narrative', 'content_plan')
                           if document.get(name)})
            return values

        before, now = slots(adopted), slots(self.document)
        results = task.get('result_refs') or []
        locations = [key for key, ref in before.items() if ref in results]
        if not results or any(ref not in before.values() for ref in results):
            return relation('unknown', 'adopted_result_location_missing')
        if any(now.get(key) != before[key] for key in locations):
            return relation('historical', 'adopted_content_replaced')
        # The whole content context includes membership/order and the adopted
        # narrative/plan. Unrelated rendering and display metadata do not.
        if (compute_input_digest(adopted) != compute_input_digest(self.document)
                or adopted.get('design_context') != self.document.get('design_context')
                or before != now
                or [p['page_id'] for p in adopted.get('pages', [])] !=
                   [p['page_id'] for p in self.document.get('pages', [])]
                or (adopted.get('collaboration') or {}).get('request') !=
                   (self.document.get('collaboration') or {}).get('request')):
            return relation('historical', 'adopted_content_context_changed')
        return relation(request_status, 'adopted_content_current')

    def task(self, task):
        key = task['task_id']
        if key in self.task_cache:
            return self.task_cache[key]
        result = request_relationship(self.document, task)
        if any(call.get('state') == 'unknown' for call in task.get('call_allowances', [])):
            # An unresolved external call stays visible even after its request
            # or task was retired. History never proves the call was not sent.
            result = relation('unknown', 'unknown_call_unresolved')
        elif task['status'] in ('superseded', 'cancelled'):
            result = relation('historical', 'task_' + task['status'])
        elif result['status'] in ('current', 'background'):
            successor = self._successor(task) if task['status'] == 'failed' else None
            if task['status'] == 'awaiting_host' and task.get('stage_request'):
                from .candidates import inputs_current
                try:
                    if not inputs_current(self.store, self.document, task,
                                          read_snapshot=self.ctx.read_snapshot):
                        result = relation(result['status'], 'dependency_basis_changed')
                except READ_FAILURES:
                    self.ctx.read_failed = True
                    result = relation('unknown', 'dependencies_unverifiable')
            elif successor:
                result = relation('historical', 'adopted_successor', successor_task_id=successor)
            elif task['status'] == 'completed' and task.get('candidate_refs'):
                statuses = []
                for ref in task['candidate_refs']:
                    try: statuses.append(self.candidate(self.ctx.overview_metadata(ref))['status'])
                    except READ_FAILURES: statuses.append('unknown')
                if not any(status in ('current','background') for status in statuses):
                    result = relation('unknown' if 'unknown' in statuses else 'historical', 'candidate_basis_not_current')
            elif task['status'] == 'completed' and task.get('kind') == 'compose':
                try:
                    result = self._completed_content(task, result['status'])
                except READ_FAILURES:
                    self.ctx.read_failed = True
                    result = relation('unknown', 'adoption_basis_unreadable')
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
                    # Several returned candidates can consume the exact same
                    # task/Page/Plan inputs. Revalidate that basis once within
                    # this immutable read, not once per output identity. Keep
                    # every field consumed by basis_state(adopted=False), and
                    # never share this cache across snapshots or requests.
                    basis_key = canonical_json_bytes({field: candidate.get(field) for field in (
                        'task_id', 'result_kind', 'page_id', 'stage', 'generation_basis',
                        'content_basis', 'target_ref')})
                    if basis_key not in self.basis_cache:
                        self.basis_cache[basis_key] = basis_state(
                            self.store, self.document, candidate, task, read_snapshot=self.ctx.read_snapshot)
                    state = self.basis_cache[basis_key]
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
