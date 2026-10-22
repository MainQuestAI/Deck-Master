"""Read-only change planning and atomic, bounded Host dispatch."""
from __future__ import annotations

import copy
import json
import re
import shlex
import uuid

from . import operations, tasks
from .annotation_service import validate as validate_annotation
from .local_state import project_path
from .method_resources import method_release, method_resources
from .models import (bump_revision, canonical_json_bytes, content_identity, sha256_bytes,
                     validate_schema, validate_task_semantics)
from .snapshots import READ_FAILURES, load_snapshot
from .store import Store
from .ui_journal import _base_refs

SLOTS = {'content': 'page', 'original_image': 'blueprint', 'prepared_prompt': 'blueprint',
         'submitted_prompt': 'blueprint', 'svg': 'svg', 'ppt': 'svg'}


def fail(field, message, *, conflict=False):
    raise operations.OperationError('conflict' if conflict else 'change_invalid', field, message,
                                    exit_code=5 if conflict else 2)


def _reference_files(store, document, references, *, original=False):
    files = []
    for reference in references:
        if reference.get('kind') == 'external':
            from .visual_styles import owned
            record, _ = owned(store, document, reference['reference_id'])
            if record['artifact_ref'] != reference['artifact_ref'] or reference['role'] != 'reference':
                fail('references', 'external reference bytes differ from the imported version')
            artifact = store.read_object_json(record['artifact_ref'] if original else record['preview_ref'])
            store.read_object_bytes(artifact['file'])
            files.append({'file': artifact['file'], 'role': 'reference'})
            continue
        snapshot = load_snapshot(store, reference['revision_id'])
        entry = next((e for e in snapshot['pages'] if e['page_id'] == reference['page_id']), None)
        if snapshot['project_id'] != document['project_id'] or not entry or entry.get('blueprint') != reference['artifact_ref']:
            fail('references', 'reference must name the original image in its fixed committed page version')
        artifact = store.read_object_json(reference['artifact_ref']); validate_schema('artifact', artifact)
        if artifact['role'] != 'blueprint' or artifact['page_id'] != reference['page_id']:
            fail('references', 'reference is not the selected original image')
        store.read_object_bytes(artifact['file'])
        files.append({'file': artifact['file'], 'role': reference['role']})
    return files


def _plan(store, document, value):
    validate_schema('change_intent', value)
    if not store.workbench_protocol_required(document):
        fail('project', 'changes require an explicit workbench.v3 project')
    if value['project_id'] != document['project_id']:
        fail('project_id', 'change belongs to another project')
    if value['base_revision'] != document['revision_id']:
        fail('base_revision', 'project changed; create a new plan', conflict=True)
    if not value['instruction'].strip() or not value['intent'].strip():
        fail('instruction', 'provide a concrete change instruction')
    if value.get('icon_recipe_ref'):
        from .icons import validate_change as validate_icon_change
        validate_icon_change(store, document, value)
    entries = {entry['page_id']: entry for entry in document['pages']}
    extended = any(key in value for key in ('mode', 'references')) or any('stage' in t for t in value['targets'])
    mode = value.get('mode', 'auto')
    if value.get('style_recipe_ref'):
        from .styles import validate_change
        validate_change(store, document, value)
    elif value.get('style_adopted_candidate_id'):
        fail('style_adopted_candidate_id', 'style expansion requires its fixed recipe')
    _reference_files(store, document, value.get('references', []))
    seen = set(); actions = []
    for target in value['targets']:
        pid = target['page_id']; layer = target['layer']; entry = entries.get(pid)
        if not entry or entry['page'] != target['page_ref']:
            fail('targets/page_ref', 'target page changed or is not in the project', conflict=True)
        # One action per page: content/image/SVG are sequential dependencies,
        # not independent simultaneous jobs on the same page.
        if pid in seen:
            fail('targets', 'one action per page per plan; plan dependent layers after the first result')
        seen.add(pid)
        refs = _base_refs(store, document, {'scope': 'page', 'page_id': pid, 'layer': layer})
        if (refs and target['artifact_ref'] not in refs) or (not refs and target['artifact_ref'] is not None):
            fail('targets/artifact_ref', 'target reference differs from the selected layer', conflict=True)
        slot = SLOTS[layer]
        stage = target.get('stage', {'page': 'repair', 'blueprint': 'blueprint', 'svg': 'reconstruct'}[slot])
        if stage not in ({'repair'} if slot == 'page' else {'blueprint'} if slot == 'blueprint' else {'reconstruct', 'repair'}):
            fail('targets/stage', 'stage does not match the selected layer')
        if mode == 'trial' and slot == 'page' and value['intent'].strip() == 'content':
            # B03: a single-page content trial returns one immutable Page
            # candidate; current content moves only through explicit adoption.
            pass
        elif mode == 'trial' and slot == 'page':
            fail('mode', 'content trials require intent "content"; other layers support original-image and SVG candidates')
        if extended and slot == 'svg':
            if not entry.get('blueprint'):
                fail('targets/stage', 'SVG reconstruction requires a current original image')
            store.read_object_bytes(store.read_object_json(entry['blueprint'])['file'])
        if value.get('references') and slot != 'blueprint':
            fail('references', 'fixed image references are for original-image generation')
        downstream = (['svg', 'svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability']
                      if slot in ('page', 'blueprint') else ['svg_preview', 'ppt_preview', 'deck_outputs', 'quality_applicability'])
        actions.append({'action_id': 'action-' + str(len(actions) + 1), 'page_id': pid,
                        'page_ref': entry['page'], 'layer': layer, 'target_ref': entry.get(slot),
                        'kind': stage,
                        'write_slots': [slot], 'max_calls': int(slot == 'blueprint'), 'downstream': downstream})
        if extended:
            actions[-1].update(mode=mode, stage=stage)
    for ref in value['annotation_refs']:
        if ref not in document.get('annotations', []):
            fail('annotation_refs', 'opinion is not saved in the selected project version')
        note = store.read_object_json(ref); validate_annotation(store, document, note)
        if note['scope'] in ('page', 'artifact') and note['page_id'] not in seen:
            fail('annotation_refs', 'opinion names a page outside the explicit targets')
        if note['scope'] in ('page', 'artifact') and note['page_ref'] != entries[note['page_id']]['page']:
            fail('annotation_refs', 'opinion refers to older page content; explicitly create a new opinion', conflict=True)
        if note['scope'] == 'artifact' and note['artifact_ref'] not in _base_refs(
                store, document, {'scope': 'page', 'page_id': note['page_id'], 'layer': note['layer']}):
            fail('annotation_refs', 'opinion location belongs to an older artifact; do not migrate it silently', conflict=True)
        if note['scope'] == 'chapter' and note['content_plan_ref'] != document.get('content_plan'):
            fail('annotation_refs', 'chapter opinion belongs to an older content plan', conflict=True)
    required_calls = sum(action['max_calls'] for action in actions)
    if required_calls > value['max_calls']:
        fail('max_calls', 'selected original-image actions exceed the approved call upper bound')
    if document['policy']['user_stop']:
        fail('policy/user_stop', 'project is stopped; resolve the stop before dispatch')
    return {'schema_version': 'change_plan.v1', 'project_id': document['project_id'],
            'base_revision': document['revision_id'], 'input': copy.deepcopy(value),
            'payload_digest': sha256_bytes(canonical_json_bytes(value)), 'actions': actions,
            'max_calls': required_calls, 'content_identity': content_identity(document),
            'effects': 'Trial results are immutable candidates; current artifacts change only through explicit candidate adoption.' if mode == 'trial' else 'Commit creates Host tasks only. Adoption writes the listed slots and invalidates listed downstream outputs. PPT requests repair the selected page SVG before normal deck compilation.'}


@operations.public
def plan(project, *, input):
    store = Store(project_path(project)); document = load_snapshot(store)
    record = _plan(store, document, input); validate_schema('change_plan', record)
    # Immutable derived preview only: no Document, tasks, allowance or model call.
    ref = store.put_json_object(record)
    return {'status': 'planned', 'plan_id': 'plan-' + ref['sha256'], 'plan_ref': ref, 'plan': record}


def _plan_layers(record) -> list[str]:
    """The layers a change plan writes, in scope-vocabulary terms."""
    layers: list[str] = []
    for action in record['actions']:
        layer = {'page': 'page_copy', 'blueprint': 'blueprint', 'svg': 'svg'}[action['write_slots'][0]]
        if layer not in layers:
            layers.append(layer)
    return layers


def _read_plan(store, plan_id):
    if not isinstance(plan_id, str) or not re.fullmatch(r'plan-[a-f0-9]{64}', plan_id):
        fail('plan_id', 'use the immutable plan ID returned by changes plan')
    digest = plan_id[5:]
    ref = {'path': f'.deckmaster/objects/{digest[:2]}/{digest}.json', 'sha256': digest}
    record = store.read_object_json(ref); validate_schema('change_plan', record)
    return record, ref


@operations.public
def commit(project, *, plan_id, base_revision, operation_id):
    operations.validate_id(operation_id, new=True)
    store = Store(project_path(project)); record, plan_ref = _read_plan(store, plan_id)
    with store._locked():
        document = store.load_document()
        digest = operations.request_digest(document, 'changes.commit', base_revision,
                                            {'plan_id': plan_id, 'plan': record})
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if document['revision_id'] != base_revision or record['base_revision'] != base_revision:
            fail('base_revision', 'project changed; preview a new plan', conflict=True)
        if _plan(store, document, record['input']) != record:
            fail('plan_id', 'plan payload or target basis changed; preview again', conflict=True)
        # CONTRACTS §6.2 row 4: committing a change plan dispatches real work,
        # so the plan's own write targets must be inside the request scope and
        # covered by an authorization before any task or allowance is created.
        from . import eligibility
        external_call_page_ids = [action['page_id'] for action in record['actions'] if action['max_calls'] > 0]
        eligibility.guard(store, document, "change.commit", context={
            "external_call_page_ids": external_call_page_ids,
            "count": record['max_calls'],
            "candidate_count": sum(action.get('mode') == 'trial' for action in record['actions']),
            "targets": {"page_ids": [action['page_id'] for action in record['actions']],
                        "layers": _plan_layers(record)}})
        authorization_ref = eligibility.covering_authorization_ref(store, document, 'change.commit',
            {'page_ids': [action['page_id'] for action in record['actions']], 'layers': _plan_layers(record)},
            count=record['max_calls'], external_call_page_ids=external_call_page_ids,
            candidate_count=sum(action.get('mode') == 'trial' for action in record['actions']))
        active = [store.read_object_json(ref) for ref in document['tasks']]
        for action in record['actions']:
            if action.get('mode') == 'trial':
                continue
            if any(task.get('stage_request', {}).get('mode') != 'trial' and task['status'] in ('queued', 'awaiting_host', 'running')
                   and action['page_id'] in task.get('scope_pages', []) and task['kind'] != 'review' for task in active):
                fail('tasks', 'target has active work; verify or cancel it before a new handoff', conflict=True)
        change_id = 'change-' + uuid.uuid4().hex
        task_ids = ['task-' + uuid.uuid4().hex for _ in record['actions']]
        change = {'schema_version': 'change_set.v1', 'change_id': change_id,
                  'project_id': document['project_id'], 'base_revision': base_revision,
                  'payload_digest': record['payload_digest'], 'plan_ref': plan_ref,
                  'task_ids': task_ids, 'actions': record['actions']}
        validate_schema('change_set', change); change_ref = store.put_json_object(change)
        updated = bump_revision(copy.deepcopy(document), {'operation_id': operation_id, 'kind': 'task_update',
                                  'description': 'Explicit change plan dispatched', 'read_set': []})
        if any('mode' in a for a in record['actions']):
            from .models import require_writer
            require_writer(updated, 'candidates.v1')
        updated['changes'] = [*document.get('changes', []), change_ref]
        for task_id, action in zip(task_ids, record['actions']):
            task = _new_task(store, updated, document, record, change_ref, task_id, action,
                             authorization_ref=authorization_ref)
            updated['tasks'].append(store.put_json_object(task))
        if any(action['kind'] == 'blueprint' for action in record['actions']):
            from .models import require_writer
            require_writer(updated, 'rc3.v1')
        result = {'status': 'awaiting_host', 'revision_id': updated['revision_id'], 'change_id': change_id,
                  'change_ref': change_ref, 'task_ids': task_ids, 'max_calls': record['max_calls']}
        return operations.commit_locked(store, document=updated, base_revision=base_revision,
                                        operation_id=operation_id, kind='changes.commit', digest=digest, result=result)


def _new_task(store, ledger, basis, plan, change_ref, task_id, action, *, authorization_ref=None):
    entry = next(e for e in basis['pages'] if e['page_id'] == action['page_id'])
    inputs = [ref for key, ref in entry.items() if key != 'page_id' and ref] + [change_ref]
    protocol = {'protocol_version': 'changes.v1', 'required_capabilities': ['change_plan']}
    if action['kind'] == 'blueprint':
        from .generation import protocol_fields
        from .production import project_prompt, resolve_generation_design
        from .service import _resolve_permitted_asset_files
        recipe_ref = plan['input'].get('style_recipe_ref')
        recipe = store.read_object_json(recipe_ref) if recipe_ref else None
        # Historical v1/v2 style execution keeps its original contract.
        compiled_ref = recipe_ref
        design = resolve_generation_design(store, basis, entry, recipe_ref=compiled_ref)
        request = project_prompt(store.read_object_json(entry['page']), design, design.get('assets') or [])
        if plan['input'].get('style_recipe_ref'):
            from .styles import apply_request
            apply_request(store, basis, plan['input'], request, action['page_id'])
        else:
            request['prompt'] = plan['input']['instruction'] + '\n\n' + request['prompt']
            request['prompt_sha256'] = sha256_bytes(request['prompt'].encode('utf-8'))
        request['permitted_asset_files'] = _resolve_permitted_asset_files(store, request['projection']['permitted_assets'])
        inputs.append(store.put_json_object(request))
        protocol = protocol_fields(basis, store=store)
        protocol['required_capabilities'].append('change_plan')
    elif action['kind'] in ('reconstruct', 'repair') and action['write_slots'] == ['svg']:
        from .production import design_handoff_protocol_fields
        handoff = design_handoff_protocol_fields(store, basis, [entry])
        if handoff:
            protocol['required_capabilities'].extend(handoff['required_capabilities'])
            from .models import require_writer
            require_writer(ledger, 'rc3.v1')
    task = tasks.new_task(task_id=task_id, operation_id=str(uuid.uuid4()), kind=action['kind'],
                          scope_pages=[action['page_id']], instruction=plan['input']['instruction'], inputs=inputs,
                          dependencies=[{'kind': 'content', 'identity': 'page:' + action['page_id'], 'sha256': action['page_ref']['sha256']}],
                          dispatch_revision=basis['revision_id'], produced_against=content_identity(basis),
                          cost_class='external_generation' if action['max_calls'] else 'host_reasoning',
                          method_release=method_release(method_resources(action['kind'])))
    # A collaboration.v1 project dispatches an accountable task: the change
    # action materialises into a phase binding before any allowance is
    # reserved, so the same judgement covers the dispatch and its call slots
    # (T03 binding writer; T04 refuses unbound production unconditionally).
    # Older projects keep their exact old dispatch (stamp_task is a no-op).
    from . import collaboration_binding
    content_trial = action.get('mode') == 'trial' and action['write_slots'] == ['page']
    write_scope = None
    if content_trial:
        from .content_production import write_scope_for
        write_scope = write_scope_for(store, basis, 'page_copy', page_ids=[action['page_id']])
        write_scope.update(layers=['page_copy'], allow_page_membership_change=False)
    collaboration_binding.stamp_task(
        store, basis, task, phase="page_copy" if content_trial else "production", executor_type="host",
        write_scope=write_scope,
        page_ids=[action["page_id"]],
        adoption_policy="candidate_only" if action.get("mode") == "trial" else "within_scope",
        authorization_ref=authorization_ref,
        candidate_count=int(action.get('mode') == 'trial'), external_call_count=action['max_calls'],
        action="change.commit",
        action_targets={"page_ids": [action["page_id"]], "layers": _plan_layers({"actions": [action]})})
    # Reserve on the prospective complete Document so the whole batch observes
    # its own earlier reservations. No intermediate pointer is published.
    if action['max_calls']:
        task, _ = tasks.reserve_allowances(store, ledger, task, action['max_calls'])
    task.update(protocol, change_binding={'change_ref': change_ref, 'action_id': action['action_id']})
    if 'mode' in action:
        stage = 'content' if action['write_slots'] == ['page'] and action['mode'] == 'trial' else action['stage']
        v3 = bool(plan['input'].get('style_recipe_ref') and store.read_object_json(plan['input']['style_recipe_ref'])['schema_version'] == 'style_recipe.v3')
        task['stage_request'] = {'mode': action['mode'], 'stage': stage,
                                 'references': _reference_files(store, basis, plan['input'].get('references', []), original=v3)}
        if plan['input'].get('style_recipe_ref'):
            task['stage_request']['style_recipe_ref'] = plan['input']['style_recipe_ref']
            task['inputs'].append(plan['input']['style_recipe_ref'])
            task['required_capabilities'].append('style_recipe')
            selected_recipe = store.read_object_json(plan['input']['style_recipe_ref'])
            if selected_recipe['schema_version'] == 'style_recipe.v3':
                task['required_capabilities'].append('style_recipe_v3')
            if selected_recipe['schema_version'] == 'style_recipe.v2' or (selected_recipe['schema_version'] == 'style_recipe.v3' and selected_recipe['intent'] == 'restyle'):
                task['required_capabilities'].append('visual_reference')
                # The target image anchors all explicitly preserved dimensions.
                original = store.read_object_json(entry['blueprint'])
                task['stage_request']['references'].insert(0, {'file': original['file'], 'role': 'reference'})
                task['stage_request']['target_reference_ref'] = entry['blueprint']
        if plan['input'].get('icon_recipe_ref'):
            task['stage_request']['icon_recipe_ref'] = plan['input']['icon_recipe_ref']
            task['inputs'].append(plan['input']['icon_recipe_ref'])
            task['required_capabilities'].append('icon_repair')
        if action['mode'] == 'trial':
            task['required_capabilities'].append('candidate_result')
            if stage == 'content':
                # B03: a content trial Host must declare the content capability;
                # old Hosts are refused before they can claim the task.
                from .candidates import CONTENT_CAPABILITY
                task['required_capabilities'].append(CONTENT_CAPABILITY)
    if content_trial:
        from .method_resources import freeze_task_methods
        freeze_task_methods(task)
    validate_task_semantics(task)
    return task


def action_for_task(store, document, task):
    binding = task.get('change_binding')
    if not binding:
        return None
    if binding['change_ref'] not in document.get('changes', []):
        fail('change_binding', 'task change is not committed in this project', conflict=True)
    change = store.read_object_json(binding['change_ref']); validate_schema('change_set', change)
    if change['project_id'] != document['project_id'] or task['task_id'] not in change['task_ids']:
        fail('change_binding', 'task belongs to a different change', conflict=True)
    index = change['task_ids'].index(task['task_id']); action = change['actions'][index]
    if action['action_id'] != binding['action_id'] or task['scope_pages'] != [action['page_id']]:
        fail('change_binding', 'task action identity differs from the committed plan', conflict=True)
    return action


def validate_result(store, document, task, envelope):
    action = action_for_task(store, document, task)
    if not action:
        return
    from .generation import check_host
    check_host(task)
    if task['status'] != 'running' or not task.get('execution_ref'):
        fail('task/status', 'Host must claim the task through task start before adoption', conflict=True)
    if not envelope.get('pages') and not envelope.get('artifact_specs'):
        fail('result', 'the planned action requires a result in its explicit write slot')
    entry = next((e for e in document['pages'] if e['page_id'] == action['page_id']), None)
    slot = action['write_slots'][0]
    page_current = bool(entry and entry['page'] == action['page_ref'])
    if entry and not page_current and slot in ('blueprint', 'svg'):
        from .visual_dependencies import page_visual_equivalent
        page_current = (page_visual_equivalent(store, action['page_ref'], entry['page'], action['page_id'])
                        and tasks.task_inputs_current(store, document, task))
    if not page_current or (action.get('mode') != 'trial' and entry.get(slot) != action['target_ref']):
        fail('adoption_target', 'planned target slot changed; late result cannot overwrite it', conflict=True)
    if envelope.get('page_order') or envelope.get('content_update') or envelope.get('content_plan') or envelope.get('reviews'):
        fail('result', 'result exceeds the explicitly planned write scope')
    if envelope.get('pages') and slot != 'page':
        fail('result/pages', 'this plan does not authorize page content writes')
    if any(spec.get('role') != slot for spec in envelope.get('artifact_specs', [])):
        fail('result/artifact_specs', 'artifact role exceeds the planned write slot')


@operations.public
def handoff(project, *, change_id):
    store = Store(project_path(project)); document = load_snapshot(store)
    change = next((store.read_object_json(ref) for ref in document.get('changes', [])
                   if store.read_object_json(ref).get('change_id') == change_id), None)
    if not change:
        raise operations.OperationError('change_not_found', 'change_id', 'change is not in this project', http_status=404)
    validate_schema('change_set', change)
    selected = [tasks._lookup_task(document, task_id, store) for task_id in change['task_ids']]
    rows = [{'task_id': t['task_id'], 'status': t['status'], 'execution_ref': t.get('execution_ref'),
             'operation_id': t['operation_id'], 'protocol_version': t.get('protocol_version'),
             'required_capabilities': t.get('required_capabilities', []),
             'request_ids': [store.read_object_json(ref)['request_id'] for ref in t.get('generation_requests', [])]}
            for t in selected]
    from .run_desk import task_row
    for row, task in zip(rows, selected, strict=True):
        projected = task_row(task)
        row.update({key: projected[key] for key in ('scope_pages', 'execution_started_at', 'execution_time_source',
                    'result_refs', 'candidate_refs', 'call_counts', 'needs_verification')})
        row['attempt_ids'] = [store.read_object_json(ref)['attempt_id'] for ref in task.get('generation_attempts', [])]
    plan_record = store.read_object_json(change['plan_ref']); validate_schema('change_plan', plan_record)
    block = {'schema_version': 'deck-master-handoff.v1', 'project_id': document['project_id'],
             'change_id': change_id, 'base_revision': change['base_revision'], 'tasks': rows,
             'plan_ref': change['plan_ref'], 'plan': plan_record,
             'read_command': shlex.join(['deck-master', 'changes', 'handoff', '--project', str(store.project_root), '--change-id', change_id])}
    validate_schema('change_handoff', block)
    state = _status(selected)
    return {**state,
            'recovery': 'Verify the existing execution or confirm cancellation before a new handoff. Never retry a call automatically.',
            'handoff': block,
            'summary': f'{len(rows)} explicit page tasks; copy is not execution. Read the committed plan before starting.',
            'text': 'Read this local change using the official CLI. Copying does not start work.\n' +
                    block['read_command'] + '\n\n```deck-master-handoff.v1\n' +
                    json.dumps(block, ensure_ascii=False, indent=2).replace('`', '\\u0060') + '\n```'}


def _status(selected):
    """Aggregate task state without constructing a handoff or command text."""
    from .run_desk import task_row
    completed = sum(t['status'] == 'completed' for t in selected)
    state = ('completed' if completed == len(selected) else 'partial' if completed else
             'running' if any(t['status'] == 'running' and t.get('execution_ref') for t in selected) else
             'cancelled' if all(t['status'] == 'cancelled' for t in selected) else
             'failed' if any(t['status'] in ('failed', 'superseded') for t in selected) else 'awaiting_host')
    needs_verification = any(task_row(task)['needs_verification'] for task in selected)
    unknown = any(c['state'] == 'unknown' for t in selected for c in t.get('call_allowances', []))
    if unknown:
        state = 'unknown'
    return {'status': state, 'needs_verification': needs_verification or unknown,
            'completed_count': completed, 'total_count': len(selected)}


@operations.public
def list_changes(project):
    store = Store(project_path(project)); document = load_snapshot(store)
    from .read_facts import ReadFacts
    store = ReadFacts(store, document)
    task_map, first_error = {}, None
    for ref in document.get('tasks', []) if document.get('changes') else []:
        try:
            task = store.read_object_json(ref)
            task_map.setdefault(task['task_id'], (task, first_error))
        except READ_FAILURES as exc:
            if first_error is None:
                first_error = exc
    records = []
    for ref in document.get('changes', []):
        change = store.read_object_json(ref); validate_schema('change_set', change)
        selected = []
        for task_id in change['task_ids']:
            if task_id not in task_map:
                if first_error is not None:
                    raise first_error
                raise tasks.EnvelopeError(f'(task {task_id})', 'task not found in current Document')
            task, preceding_error = task_map[task_id]
            if preceding_error is not None:
                raise preceding_error
            validate_task_semantics(task)
            selected.append(task)
        # Preserve malformed frozen-plan/call-record refusal without building
        # the complete handoff schema, command, or text for each group.
        validate_schema('change_plan', store.read_object_json(change['plan_ref']))
        for task in selected:
            for item in task.get('generation_requests', []):
                store.read_object_json(item)['request_id']
            for item in task.get('generation_attempts', []):
                store.read_object_json(item)['attempt_id']
        state = _status(selected)
        records.append({'change_id': change['change_id'], 'ref': ref, 'status': state['status'],
                        'completed_count': state['completed_count'], 'total_count': state['total_count'],
                        'needs_verification': state['needs_verification']})
    return {'project_id': document['project_id'], 'revision_id': document['revision_id'], 'changes': records}
