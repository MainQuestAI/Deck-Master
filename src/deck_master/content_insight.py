"""Version-bound reading projections. No dispatch, object writes or writer upgrades."""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from pathlib import Path

from . import models, content_production, collaboration, dependency_slices
from .errors import TypedServiceError
from .snapshots import load_snapshot, READ_FAILURES
from .store import Store


class InsightError(TypedServiceError):
    error_code = 'insight_invalid_query'

    def __init__(self, field, message, *, code='insight_invalid_query', http_status=400):
        super().__init__(field, message)
        self.error_code, self.http_status = code, http_status


def fail(message, *, code='insight_invalid_query', status=400):
    raise InsightError('insight', message, code=code, http_status=status)


def issue(ref, field='object', page_id=None):
    return {'code': 'insight_locator_unavailable', 'field': field,
            'message': '这版记录暂不可读；保留固定引用，核实原记录。', 'ref': ref, 'page_id': page_id}


def envelope(doc, name, data, issues=(), status=None):
    return {'schema_version': 'ui_' + name + '.v1', 'project_id': doc['project_id'],
            'revision_id': doc['revision_id'], 'status': status or ('partial' if issues else 'ready'),
            'issues': list(issues), 'data': data}


def snapshot(project, revision):
    store = Store(Path(project))
    return store, load_snapshot(store, revision)


def read(store, ref, schema=None, project_id=None):
    models.validate_ref(ref, where="insight/ref")
    value = store.read_object_json(ref)
    if schema:
        models.validate_schema(schema, value)
    if project_id and value.get('project_id') not in (None, project_id):
        raise ValueError('foreign object')
    return value


def records(store, doc, family):
    values, errors = [], []
    refs = (doc.get('collaboration') or {}).get(family, []) if family == 'decisions' else doc.get(family, [])
    for ref in refs:
        try:
            value = read(store, ref, {'tasks': 'task', 'reviews': 'review', 'decisions': 'collaboration_decision'}[family])
            if value.get('project_id') not in (None, doc['project_id']):
                raise ValueError('foreign object')
            values.append((ref, value))
        except READ_FAILURES:
            errors.append(issue(ref, family))
    return values, errors


def objects(store, doc):
    """Only formal pointers/results/decision subjects; never a disk scan or arbitrary Task input."""
    refs, errors = {}, []
    for name in ('narrative', 'content_plan'):
        if doc.get(name):
            refs[doc[name]['sha256']] = (doc[name], None, name)
    request = (doc.get('collaboration') or {}).get('request') or {}
    tasks, gaps = records(store, doc, 'tasks'); errors.extend(gaps)
    for _, task in tasks:
        binding = task.get('collaboration_binding') or {}
        if task.get('status') != 'completed' or task.get('kind') != 'compose' or task.get('protocol_version') != 'compose.v2':
            continue
        if binding and binding.get('request_id') is None:
            continue
        for ref in task.get('result_refs') or []:
            refs.setdefault(ref['sha256'], (ref, task, 'proposal' if binding.get('request_id') == request.get('request_id') and task.get('produced_against') == models.content_identity(doc) else 'historical'))
    decisions, gaps = records(store, doc, 'decisions'); errors.extend(gaps)
    for _, decision in decisions:
        for subject in decision.get('subject_refs') or []:
            ref = subject.get('artifact_ref')
            if ref and subject.get('artifact_kind') in ('narrative', 'content_plan'):
                refs.setdefault(ref['sha256'], (ref, None, 'historical'))
    return list(refs.values()), errors


def known_object_kind(doc, ref, task=None):
    if ref == doc.get('narrative'):
        return 'narrative'
    if ref == doc.get('content_plan'):
        return 'plan'
    # compose.v2 framing/argument acceptance fixes the result order: Narrative, optional Plan.
    if task and (task.get('collaboration_binding') or {}).get('phase') in ('framing', 'argument'):
        results = task.get('result_refs') or []
        if ref in results:
            return 'narrative' if results.index(ref) == 0 else 'plan' if results.index(ref) == 1 else 'object'
    return 'object'


def argument_objects(store, doc):
    entries, issues = objects(store, doc)
    result = []
    for ref, task, relation in entries:
        try:
            obj = read(store, ref, project_id=doc['project_id'])
            if obj.get('schema_version') not in models.NARRATIVE_VERSIONS:
                continue
            models.validate_narrative_semantics(obj)
            if obj['project_id'] != doc['project_id']:
                raise ValueError('foreign narrative')
            job = obj.get('communication_job') or {}
            central = next((n for n in obj.get('nodes', []) if n.get('node_id') == obj.get('central_node_id')), {})
            item = {'ref': ref, 'readable': True, 'narrative_id': obj['narrative_id'], 'maturity': obj['maturity'],
                    'relation': 'current' if ref == doc.get('narrative') else relation if relation in ('proposal', 'historical') else 'historical',
                    'request_id': (task or {}).get('collaboration_binding', {}).get('request_id'),
                    'producer_task_id': (task or {}).get('task_id'),
                    'communication_question': job.get('audience_question'),
                    'central_statement': central.get('statement')}
            result.append((item, obj))
        except READ_FAILURES:
            gap = issue(ref, known_object_kind(doc, ref, task)); issues.append(gap)
            if relation == 'narrative':
                result.append(({'ref': ref, 'readable': False, 'issues': [gap]}, None))
    return result, issues


def arguments(project, *, revision=None, limit=30, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        fail('invalid pagination')
    store, doc = snapshot(project, revision)
    rows, gaps = argument_objects(store, doc)
    return envelope(doc, 'arguments', {'items': [r[0] for r in rows[offset:offset+limit]],
        'pagination': {'limit': limit, 'offset': offset, 'next_offset': offset+limit if offset+limit < len(rows) else None}}, gaps)


def adoption(store, doc, ref, item):
    control = store.load_document()
    request = (control.get('collaboration') or {}).get('request') or {}
    scope = copy.deepcopy(request.get('scope') or {})
    scope['layers'] = ['narrative']
    scope['allow_page_membership_change'] = False
    scope['allow_page_order_change'] = False
    subject = {'artifact_kind': 'narrative', 'artifact_ref': ref, 'projection': 'direction'}
    result = {'readable_in_revision': doc['revision_id'], 'assessed_control_revision': control['revision_id'],
              'can_record_direction_decision': False, 'can_adopt': False, 'needs_decision': True,
              'decision_reason_codes': [], 'adoption_reason_codes': [], 'write_scope': scope,
              'existing_decision_ref': None, 'subject_ref': subject, 'basis': [], 'invalidated_refs': []}
    blocked = ('historical_revision' if doc['revision_id'] != control['revision_id'] or item.get('relation') == 'historical'
               else 'argument_required' if item.get('maturity') != 'argument'
               else 'fixed_content_intent' if request.get('content_intent') in ('write_only', 'speech_only') else None)
    if blocked:
        result['decision_reason_codes'] = result['adoption_reason_codes'] = [blocked]
        return result
    try:
        if (control.get('collaboration') or {}).get('authority_policy') == 'verified_user':
            fail('This UI channel cannot record verified-user decisions', code='authority_channel_unavailable')
        result['basis'] = dependency_slices.merge_required_basis(store, control, family='decision', key='direction', provided=[])
        # This is only admission for the existing Host-attested UI channel. The
        # actual instruction is supplied by the user and revalidated on write.
        payload = {'topic': 'direction', 'authority_mode': 'direct_user', 'subject_refs': [subject],
                   'scope': scope, 'basis': result['basis'], 'value': {'selected': ref['sha256']}, 'disposition': 'accepted',
                   'instruction_evidence': {'kind': 'host_attested_instruction', 'text': '预检方向决定准入；未记录决定',
                                            'source_locator': 'studio:direction:admission'}}
        source = request.get('instruction_evidence') or {}
        evidence = collaboration.resolve_evidence({'kind': 'host_attested_instruction',
            'source_ref': source.get('source_ref'), 'source_locator': source.get('source_locator')})
        collaboration.prepare_decision(store, control, input=payload,
            operation_id='ui-direction-preflight', evidence=evidence)
        result['can_record_direction_decision'] = True
    except READ_FAILURES as exc:
        result['decision_reason_codes'] = [getattr(exc, 'error_code', 'decision_not_allowed')]
    choices, _ = records(store, control, 'decisions')
    for decision_ref, decision in choices:
        if not any(s.get('artifact_ref') == ref for s in decision.get('subject_refs', [])):
            continue
        try:
            _, invalidated, _ = content_production.check_proposal_adoption(store, control,
                input={'proposal_ref': ref, 'decision_ref': decision_ref, 'write_scope': scope})
            result.update(can_adopt=True, needs_decision=False, existing_decision_ref=decision_ref, invalidated_refs=invalidated)
            break
        except READ_FAILURES as exc:
            result['adoption_reason_codes'].append(getattr(exc, 'error_code', 'decision_not_effective'))
    if result['can_adopt']:
        result['adoption_reason_codes'] = []
    elif not result['adoption_reason_codes']:
        result['adoption_reason_codes'] = ['direction_decision_required']
    return result


def argument(project, sha256, *, revision=None):
    if not re.fullmatch('[a-f0-9]{64}', sha256):
        fail('invalid Narrative reference')
    store, doc = snapshot(project, revision)
    rows, gaps = argument_objects(store, doc)
    found = next(((item, obj) for item, obj in rows if item['ref']['sha256'] == sha256), None)
    if found is None:
        fail('Narrative is not reachable', code='insight_object_not_reachable', status=404)
    item, obj = found
    if obj is None:
        return envelope(doc, 'argument', None, item['issues'], 'unreadable')
    plans, related = [], []
    plan_errors = []
    for ref, task, _ in objects(store, doc)[0]:
        kind = known_object_kind(doc, ref, task)
        if kind == 'narrative':
            continue
        try:
            plan = read(store, ref, project_id=doc['project_id'])
            if plan.get('schema_version') != 'content_plan.v2' or plan.get('narrative_ref') != item['ref']:
                continue
            kind = 'plan'
            models.validate_content_plan_semantics(plan)
            links = {l['page_id']: l['page_ref'] for l in plan['page_links']}
            plans.append({'ref': ref, 'readable': True, 'data': {'narrative_ref': item['ref'], 'mode': plan['mode'],
                'planned_roles': [{'role': role, 'page_ref': links.get(role['page_id']),
                                   'basis_status': 'planned' if plan['mode'] == 'planned' else 'current'}
                                  for role in plan['input']['page_roles']], 'plan': plan}})
        except READ_FAILURES:
            gap = issue(ref, kind); gaps.append(gap)
            if kind == 'plan':
                plan_errors.append(gap)
    for entry in doc['pages']:
        try:
            page = read(store, entry['page'], 'page')
            mapping = page.get('content_mapping') or {}
            if mapping.get('narrative_ref') == item['ref']:
                related.append({'page_id': entry['page_id'], 'page_ref': entry['page'],
                                'node_ids': list(dict.fromkeys(n for l in mapping.get('visible_links', []) for n in l['narrative_node_ids']))})
        except READ_FAILURES:
            gaps.append(issue(entry['page'], 'page', entry['page_id']))
    decisions = []
    for ref, d in records(store, doc, 'decisions')[0]:
        if any(s.get('artifact_ref') == item['ref'] for s in d.get('subject_refs', [])):
            try:
                state = dependency_slices.decision_effectiveness(store, doc, ref)
                decisions.append({'ref': ref, 'effective': state['effective'], 'disposition': d['disposition'],
                                  'reason_codes': state.get('reasons', [])})
            except READ_FAILURES:
                gaps.append(issue(ref, 'decision'))
    return envelope(doc, 'argument', {'item': item, 'narrative': obj, 'related_pages': related, 'plans': plans,
        'plan_status': 'partial' if plans and plan_errors else 'recorded' if plans else 'unreadable' if plan_errors else 'absent', 'decisions': decisions, 'adoption': adoption(store, doc, item['ref'], item)}, gaps)


def page_object(store, doc, page_id):
    entry = next((p for p in doc['pages'] if p['page_id'] == page_id), None)
    if not entry:
        fail('Page not in selected snapshot', code='insight_object_not_reachable', status=404)
    return entry, read(store, entry['page'], 'page')


def evidence(project, page_id, *, revision=None, element_ref=None):
    from .content import visible_atoms
    store, doc = snapshot(project, revision)
    try:
        entry, page = page_object(store, doc, page_id)
    except InsightError:
        raise
    except READ_FAILURES:
        entry = next(p for p in doc['pages'] if p['page_id'] == page_id)
        return envelope(doc, 'page_evidence', None, [issue(entry['page'], 'page', page_id)], 'unreadable')
    mapping = page.get('content_mapping') or {}
    ref = mapping.get('narrative_ref'); narrative = {}; gaps = []
    if ref:
        try:
            narrative = read(store, ref, 'narrative', doc['project_id'])
        except READ_FAILURES:
            gaps.append(issue(ref, 'narrative', page_id))
    atoms = visible_atoms(page)
    if element_ref and element_ref not in {a['atom_id'] for a in atoms}:
        fail('Text atom is unavailable in this Page', code='insight_locator_unavailable', status=404)
    nodes = {n['node_id']: n for n in narrative.get('nodes', [])}; elements = []
    checked_sources = {}
    def links(values, local_gaps):
        from .content_ops import source
        unique = {}
        for link in values:
            key = models.canonical_json_bytes(link); unique[key] = link
            if key in checked_sources:
                if checked_sources[key] is not None:
                    local_gaps.append(checked_sources[key])
                continue
            checked_sources[key] = None
            try:
                current = source(project, source_id=link['source_id'], revision=doc['revision_id'],
                    locator=link['locator'], extract_sha256=(link['source_version'].get('extract') or {}).get('sha256'))
                if current['source_version'] != link['source_version'] or current['location'] != 'exact':
                    raise ValueError('source locator differs')
            except READ_FAILURES:
                gap = issue(link['source_version'].get('extract'), 'source', page_id)
                checked_sources[key] = gap
                local_gaps.append(gap)
        return list(unique.values())
    narrative_gaps = list(gaps)
    for atom in atoms:
        if element_ref and atom['atom_id'] != element_ref:
            continue
        link = next((l for l in mapping.get('visible_links', []) if l['element_ref'] == atom['atom_id']), None)
        local_gaps = list(narrative_gaps) if link else []
        selected = [nodes[n] for n in (link or {}).get('narrative_node_ids', []) if n in nodes]
        if link and any(n not in nodes for n in link['narrative_node_ids']):
            local_gaps.append(issue(ref, 'narrative_node', page_id))
        qualification_ids = list(dict.fromkeys([q for n in selected for q in n.get('qualification_node_ids', [])] +
            [e['from_node_id'] for e in narrative.get('edges', []) if e['relation'] == 'qualifies' and e['to_node_id'] in {n['node_id'] for n in selected}]))
        direct_links = links((link or {}).get('source_links', []), local_gaps)
        node_links = links([s for n in selected for s in n.get('source_links', [])], local_gaps)
        for gap in local_gaps:
            if gap not in gaps:
                gaps.append(gap)
        elements.append({'element_ref': atom['atom_id'], 'text': atom['text'],
            'mapping_status': 'unreadable' if local_gaps and link else 'recorded' if link else 'not_recorded',
            'nodes': selected, 'edges': [e for e in narrative.get('edges', []) if any(n['node_id'] in e.values() for n in selected)],
            'qualifications': [nodes[q] for q in qualification_ids if q in nodes],
            'direct_source_links': direct_links,
            'node_source_links': node_links})
    return envelope(doc, 'page_evidence', {'page_id': page_id, 'page_ref': entry['page'], 'narrative_ref': ref,
        'alignment': 'not_recorded' if not ref else 'current' if ref == doc.get('narrative') else 'bound_to_older_narrative',
        'elements': elements}, gaps)


def review_reading(project, review_id, *, revision=None, review_sha256=None):
    from .content import visible_atoms
    store, doc = snapshot(project, revision)
    rows, gaps = records(store, doc, 'reviews')
    matches = [(r, v) for r, v in rows if v.get('review_id') == review_id and (not review_sha256 or r['sha256'] == review_sha256)]
    if not matches:
        bad = next((g for g in gaps if (g['ref'] or {}).get('sha256') == review_sha256), None)
        if bad:
            return envelope(doc, 'review_reading', None, [bad], 'unreadable')
        fail('Review is not reachable', code='insight_object_not_reachable', status=404)
    if len(matches) != 1:
        fail('Select an exact Review reference')
    ref, value = matches[0]; targets = []
    for index, finding in enumerate(value.get('findings', [])):
        pid = finding.get('page_id'); entry = next((p for p in doc['pages'] if p['page_id'] == pid), None)
        exact = False
        if entry:
            try:
                atoms = {a['atom_id'] for a in visible_atoms(read(store, entry['page'], 'page'))}
                exact = bool(finding['element_refs']) and set(finding['element_refs']) <= atoms and entry['page'] in value['subjects']
            except READ_FAILURES:
                gaps.append(issue(entry['page'], 'page', pid))
        layer = ({'source': 'source', 'design': 'design'}.get(finding['kind'])
            if finding['kind'] != 'content' else
            {'page_copy': 'content', 'content': 'content', 'speech': 'speech',
             'blueprint_content': 'design', 'blueprint_fidelity': 'design'}.get(value['kind']))
        request = (doc.get('collaboration') or {}).get('request') or {}
        scope = request.get('scope') or {}
        from .eligibility import scope_page_ids
        try:
            scope_pages = scope_page_ids(store, scope) or []
        except READ_FAILURES:
            scope_pages = []
        allowed = bool(entry and layer and not request.get('closed') and not request.get('paused')
            and request.get('intent') != 'review_only'
            and doc['revision_id'] == store.current_revision_id()
            and pid in scope_pages
            and {'content': 'page_copy', 'speech': 'speech', 'design': 'blueprint'}.get(layer) in scope.get('layers', []))
        # The UI prepares a draft only; existing plan/commit owns live admission.
        targets.append({'finding_id': finding['finding_id'], 'source_index': index, 'page_id': pid,
                        'page_ref': entry['page'] if entry else None, 'element_refs': finding['element_refs'],
                        'locator_status': 'exact' if exact else 'page_only' if entry else 'unavailable',
                        'repair_layer': layer, 'repair_allowed': allowed, 'reason_codes': ['prepare_only_recheck_scope'] if allowed else ['outside_request_scope_or_read_only']})
    return envelope(doc, 'review_reading', {'review_ref': ref, 'review': {'ref': ref, 'readable': True, 'data': value}, 'targets': targets}, gaps)


def requirements(project, page_id, *, revision=None):
    from .design_requirements import resolve_content_requirements
    store, doc = snapshot(project, revision)
    try:
        entry, _ = page_object(store, doc, page_id)
    except InsightError:
        raise
    except READ_FAILURES:
        entry = next(p for p in doc['pages'] if p['page_id'] == page_id)
        return envelope(doc, 'content_requirements', None, [issue(entry['page'], 'page', page_id)], 'unreadable')
    from .production import stored_blueprint_request
    tasks, gaps = records(store, doc, 'tasks')
    frozen_matches = []
    for task_ref, task in tasks:
        if task['kind'] != 'blueprint' or task.get('scope_pages') != [page_id]:
            continue
        try:
            prepared, _ = stored_blueprint_request(store, task)
            frozen = (prepared or {}).get('resolved_design_context') or {}
            if frozen.get('content_basis', {}).get('page_ref') == entry['page']:
                frozen_matches.append((task, frozen))
        except READ_FAILURES:
            gaps.append(issue(task_ref, 'requirements_task', page_id))
    if len(frozen_matches) == 1:
        task, frozen = frozen_matches[0]
        return envelope(doc, 'content_requirements', {'page_id': page_id, 'page_ref': entry['page'],
            'origin': 'frozen_task', 'producer_task_id': task['task_id'],
            'content_requirements': frozen['content_requirements'], 'content_basis': frozen['content_basis']}, gaps)
    if len(frozen_matches) > 1:
        gaps.append({'code': 'insight_requirements_multiple_tasks', 'field': 'requirements_task',
            'message': '同页有多份冻结任务要求；以下只展示快照推导值，不任意代选任务。',
            'ref': entry['page'], 'page_id': page_id})
    try:
        data = resolve_content_requirements(store, doc, entry['page'])
        return envelope(doc, 'content_requirements', {'page_id': page_id, 'page_ref': entry['page'],
            'origin': 'derived_from_snapshot', 'producer_task_id': None, **data}, gaps)
    except READ_FAILURES:
        return envelope(doc, 'content_requirements', None, gaps + [issue(entry['page'], 'requirements', page_id)], 'unreadable')


def task_methods(project, task_id, *, revision=None, availability=None):
    from . import method_resources as mr
    from .resource_catalog import safe_file
    store, doc = snapshot(project, revision)
    rows, gaps = records(store, doc, 'tasks')
    found = next(((r, t) for r, t in rows if t['task_id'] == task_id), None)
    if not found:
        fail('Task not in selected snapshot', code='insight_object_not_reachable', status=404)
    ref, task = found; manifest = task.get('method_manifest'); resources = []; problems = []
    if availability not in (None, 'current'):
        fail('unknown availability')
    for item in manifest or []:
        resources.append({**{k: item[k] for k in ('id', 'relative_path', 'sha256')},
                          'display_name': None, 'semantic_kind': None, 'metadata_status': 'unavailable'})
        if availability:
            actual = None
            try:
                if mr.RELATIVE_PATHS.get(item['id']) != item['relative_path']:
                    raise ValueError('unregistered resource')
                actual = models.sha256_bytes(safe_file(mr.resolve_root(), item['relative_path']).read_bytes())
            except (OSError, ValueError):
                pass
            if actual != item['sha256']:
                problems.append({'id': item['id'], 'reason': 'missing' if actual is None else 'hash_mismatch',
                                 'expected_sha256': item['sha256'], 'actual_sha256': actual})
    data = {'task_id': task_id, 'task_ref': ref, 'dispatch_revision': task.get('dispatch_revision'),
            'frozen_status': 'recorded' if manifest is not None else 'not_recorded', 'frozen_release': task.get('method_release'),
            'resources': resources, 'availability': None}
    if availability:
        data['availability'] = {'checked_at': datetime.now(timezone.utc).isoformat(),
            'observed_release_id': mr.method_release([])['release_id'],
            'status': 'unavailable' if manifest is None else 'basis_changed' if problems else 'current', 'issues': problems}
    return envelope(doc, 'task_methods', data, gaps)
