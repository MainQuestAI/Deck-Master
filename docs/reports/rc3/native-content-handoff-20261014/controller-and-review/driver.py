#!/usr/bin/env python3
"""Actual native-Q controller harness. No model calls, canned outputs or fallback.

All semantic fields come from native model bytes or frozen synthetic Owner
messages. Only SDK metadata, exact object links and role instructions are
wrapped here. Run exclusively with the admitted isolated Python and -I.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
QROOT = Path('/workspace/work/rc3-planning/rc3-development-plan-20261014/docs/reports/content-collaboration-v1.2/fixtures')
OBSERVER_KIND = 'root_controller_transcription_of_actual_native_tool_response'
PROVIDER_ID = 'rc3-native-root-controller'
CHANNEL = 'independent_review_receipts'
MAX_AGE = timedelta(minutes=45)
STAGES = ('01-framing', '02-argument', '03-page-copy', '04-speech',
          '05-independent-review', 'repair-argument', 'repair-page-copy', 'repair-speech')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def immutable_bytes(path, raw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('xb') as stream:
        stream.write(raw)


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    result = (datetime.strptime(value, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
              if value.endswith(' UTC') else datetime.fromisoformat(value.replace('Z', '+00:00')))
    if result.tzinfo is None:
        raise ValueError('actual observation must include timezone')
    age = datetime.now(timezone.utc) - result
    if age < timedelta(seconds=-10) or age > MAX_AGE:
        raise ValueError('Root native observation is stale/future')
    return result


def bootstrap_record(path):
    raw = Path(path).read_bytes()
    record = json.loads(raw)
    if (record.get('observation_kind') != OBSERVER_KIND or record.get('assurance') != 'host_attested'
            or record.get('tool') != 'collaboration.list_agents'
            or '/root' not in record.get('observed_running_agents', [])):
        raise ValueError('Root must supply its actual live native channel observation')
    timestamp(record['observed_at_utc'])
    return raw


class NativeControllerProvider:
    """Trusted bootstrap adapter for Root's actual native observations only.

    No platform signature or malicious-coequal-Host protection is claimed.
    Project/output JSON never selects provider trust. Real manuscript authors
    are obtained from accepted native tasks, not synthetic fixture executors.
    """
    provider_id = PROVIDER_ID
    adapter_version = 'rc3-native-root-controller.actual-content.v1'
    authentication = 'protected_transport'
    channels = (CHANNEL,)

    def __init__(self, bootstrap_path, *, observed_raw=None, claims=None):
        self.bootstrap_path = Path(bootstrap_path)
        self.bootstrap_raw = bootstrap_record(bootstrap_path)
        self.observed_raw, self.claims = observed_raw, claims

    def health(self):
        try:
            return bootstrap_record(self.bootstrap_path) == self.bootstrap_raw
        except (OSError, KeyError, ValueError):
            return False

    def fetch(self, event_id):
        if self.claims is None or self.observed_raw is None or event_id != self.claims['event_id']:
            raise ValueError('no actual Root-observed completion registered')
        return self.observed_raw

    def verify(self, raw):
        if self.claims is None or self.observed_raw is None or raw != self.observed_raw:
            raise ValueError('not the exact actual Root-observed native completion')
        return dict(self.claims)


def protocol():
    return read(HERE / 'protocol.json')


def installation(arm):
    configs = read(HERE / 'installations.json')
    record = configs.get(arm)
    if arm == 'B_run':
        record = read(HERE / 'B-registration.json')
    if record is None:
        raise ValueError('B installation not yet fixed by Root')
    return record


def identity(arm):
    import deck_master
    from deck_master import capabilities
    if not sys.flags.isolated:
        raise ValueError('mandatory -I: do not borrow activity checkout through PYTHONPATH')
    expected = installation(arm)
    manifest = read(expected['manifest'])
    actual = capabilities.installation_identity()
    installed = actual.get('install') or {}
    if (manifest['source_sha'] != expected['source_sha']
            or manifest['wheel_sha256'] != expected['wheel_sha256']
            or installed.get('source_sha') != expected['source_sha']
            or installed.get('wheel_sha256') != expected['wheel_sha256']
            or Path(deck_master.__file__).resolve() != Path(manifest['module_path']).resolve()
            or Path(sys.executable).absolute() != Path(expected['python']).absolute()):
        raise ValueError('source/wheel/module/interpreter differs from fixed arm')
    return actual


def load_run(args):
    run = Path(args.run_dir).resolve()
    state = read(run / 'run-manifest.json')
    identity(state['arm'])
    if sha((HERE / 'protocol.json').read_bytes()) != state['protocol_sha256']:
        raise ValueError('protocol changed after init')
    if sha((HERE / 'driver.py').read_bytes()) != state['harness_sha256']:
        raise ValueError('harness changed after init; preserve run and register a new fixed run')
    from deck_master.store import Store
    return run, state, Store(state['project'])


def lookup(store, task_id):
    return next(store.read_object_json(r) for r in store.load_document()['tasks']
                if store.read_object_json(r)['task_id'] == task_id)


def scope(layers, *, purpose='working', pages=None, manifest=None, membership=False):
    return {'subject': 'deck', 'page_ids': list(pages or []), 'page_manifest_ref': manifest,
            'external_artifact_ref': None, 'layers': list(layers),
            'allow_page_membership_change': membership,
            'allow_page_order_change': False, 'purpose': purpose}


def evidence(store, text):
    ref = store.put_blob(text.encode('utf-8'), ext='txt')
    return {'kind': 'host_attested_instruction',
            'source_ref': ref, 'source_locator': 'full frozen synthetic controller message',
            'actor_id': 'synthetic-scripted-owner-not-human', 'transport_receipt_ref': None,
            'presentation_ref': None}


def start(store, message, *, op, content_intent='content_full'):
    from deck_master import collaboration
    document = store.load_document()
    current = (document.get('collaboration') or {}).get('request')
    data = {'intent': 'content_only', 'content_intent': content_intent,
            'scope': scope(['narrative', 'plan', 'page_copy', 'speech', 'review'], membership=True),
            'instruction_evidence': evidence(store, message)}
    if current and not current.get('closed'):
        data['replace_request_id'] = current['request_id']
    return collaboration.start_request(store.project_root, input=data,
            base_revision=document['revision_id'], operation_id=op)


def stage_dir(run, stage):
    return run / 'stages' / stage


def packet(run, state, store, task, stage):
    from deck_master import content_production, method_resources, service
    target = stage_dir(run, stage)
    target.mkdir(parents=True, exist_ok=False)
    document = store.load_document()
    methods = method_resources.read_task_methods(store.project_root, task['task_id'])
    save(target / 'task.json', task)
    save(target / 'work-order.json', service.task_summary(store, document, task))
    save(target / 'prepared-method-bytes.json', methods)
    if stage.startswith('repair-'):
        immutable_bytes(target / 'single-actual-review-feedback.json', (stage_dir(run, '05-independent-review') / 'observed-raw-model-output.json').read_bytes())
        save(target / 'repair-scope.json', {'instruction': protocol()['repair_controller_instruction'],
            'necessary_layers': read(run / 'repair-begin.json')['necessary_layers'],
            'budget': state['budget'], 'feedback_rounds': 1, 'repair_round': 1,
            'read_rule': 'read single-actual-review-feedback.json in full; no other feedback or new facts'})
    save(target / 'current-artifacts.json', {
        'project_id': document['project_id'], 'task_facts': document['task'],
        'narrative': {'ref': document.get('narrative'), 'object': store.read_object_json(document['narrative'])} if document.get('narrative') else None,
        'plan': {'ref': document.get('content_plan'), 'object': store.read_object_json(document['content_plan'])} if document.get('content_plan') else None,
        'pages': [{'ref': e['page'], 'object': store.read_object_json(e['page'])} for e in document['pages']],
        'prior_actual_proposals': [{'task_id': t['task_id'], 'refs': t.get('result_refs') or [],
            'objects': [store.read_object_json(r) for r in t.get('result_refs') or []]}
            for t in [store.read_object_json(r) for r in document['tasks']]
            if t['kind'] == 'compose' and t['status'] == 'completed']})
    module_root = Path(identity(state['arm'])['module_path']).parent
    schemas = target / 'schemas'
    schemas.mkdir()
    for name in ('compose-result.v2', 'narrative.v1', 'content-plan-input.v2',
                 'content-plan.v2', 'page.v2', 'review.v2'):
        shutil.copyfile(module_root / 'resources/contracts' / (name + '.schema.json'), schemas / (name + '.schema.json'))
    if task['kind'] == 'compose':
        save(target / 'envelope-metadata.json', {'schema_version': 'compose_result.v2', 'kind': 'compose',
            'variant': content_production.expected_variant(task), 'task_id': task['task_id'],
            'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
            'eligibility_digest': task['collaboration_binding']['eligibility_digest'], 'usage_events': []})
    instructions = f'''Actual content task using uploaded synthetic sources. Not human or professional acceptance.
Read work-order.json, task.json, current-artifacts.json and the exact source_reading in the work order.
Do not read original prototypes, anchors, fixture outputs, full answer-bearing EXAMPLES, other arms or future controller messages.
Use only this arm's installed methods; preserve explicit unknowns. Method examples are public regressions, not hidden test material.
Before writing, run the following with your actual native canonical execution identity, then read the entire returned methods/work order:
{sys.executable} -B -I {HERE / 'driver.py'} claim-read --run-dir {run} --stage {stage} --executor YOUR_ACTUAL_NATIVE_CANONICAL_TASK
Claim-read saves method-read-record.json in this stage. It is not a model result.
Submit only this Task's variant and scope. All substantive text/mapping/budget content must be yours, never filled by the controller.
Write a complete formal envelope to {target / 'model-output.json'} using exact metadata from envelope-metadata.json.
Use actual project/source/Page refs. A planned Plan in the argument result may use narrative_ref=null; SDK binds the submitted Narrative.
Zero image/candidate/external research calls. No SVG/PPT/production in this content subtask.
Never change project content directly, invent a completion or an assurance upgrade. Root alone observes completion and consumes output.
Final native message must include your actual canonical identity, raw output path/SHA-256, method-read record path/SHA-256,
and observable native model configuration (unknown where unavailable). Read complete actual methods before content, not their hashes alone.
'''
    immutable_bytes(target / 'instructions.txt', instructions.encode())
    save(target / 'dispatch.json', {'stage': stage, 'task_id': task['task_id'],
        'project_id': document['project_id'], 'method_release': methods['current_method_release'],
        'status': 'prepared_not_model_executed', 'prepared_at': now(),
        'prepared_method_bytes_limitation': 'bytes returned by SDK; not proof of actual native read/application'})
    return {'stage': stage, 'task_id': task['task_id'], 'writer_input': str(target)}


def init(args):
    from deck_master import collaboration_migration, content_production, service
    from deck_master.store import Store
    actual = identity(args.arm)
    run = Path(args.run_dir).resolve()
    if run.exists():
        raise ValueError('choose a fresh immutable run directory')
    frozen = protocol()
    source_list = []
    for name, expected in frozen['sources'][args.case].items():
        raw = (QROOT / args.case.lower() / name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('original source bytes changed: ' + name)
        source_list.append((name, raw, expected))
    run.mkdir(parents=True)
    inputs = run / 'original-sources'
    inputs.mkdir()
    for name, raw, _ in source_list:
        immutable_bytes(inputs / name, raw)
    project = run / ('actual-' + args.case.lower())
    initial = frozen['script_messages'][args.case]['initial']
    kwargs = {} if args.case == 'Q1' else {'audience': '售后运营与 IT 负责人', 'scenario': '10 分钟立项讨论，是否开展 4 周小范围试点', 'presentation_mode': 'live', 'page_limit': 8}
    created = service.create(project, brief=initial, sources=[inputs / name for name, _, _ in source_list], project_format='workbench.v3', **kwargs)
    store = Store(project)
    migration = collaboration_migration.describe(project)
    migrated = collaboration_migration.apply(project, base_revision=migration['revision_id'], plan_digest=migration['plan_digest'], operation_id='actual-migration')
    requested = start(store, initial, op='actual-initial-request', content_intent='plan_only')
    state = {'protocol_sha256': sha((HERE / 'protocol.json').read_bytes()), 'harness_sha256': sha((HERE / 'driver.py').read_bytes()), 'case': args.case,
        'arm': args.arm, 'project': str(project), 'project_id': store.load_document()['project_id'],
        'installation_identity': actual, 'installation_admission': installation(args.arm),
        'sources': [{'name': n, 'sha256': h, 'kind': frozen['input_kind']} for n, _, h in source_list],
        'started_at': now(), 'model_execution': 'NOT_RUN', 'synthetic_output_used': False,
        'budget': frozen['budgets'][args.case], 'seen_example': True,
        'human_acceptance': 'NOT_RUN; user explicitly deferred', 'original_twelve_host_session': False}
    save(run / 'run-manifest.json', state)
    save(run / 'init-transactions.json', {'create': created, 'migration_describe': migration, 'migration_apply': migrated, 'start_request': requested})
    task = content_production.open_phase_task(store, store.load_document(), operation_id='actual-framing', phase='framing')
    print(json.dumps(packet(run, state, store, task, '01-framing'), ensure_ascii=False))


def claim_read(args):
    from deck_master import method_resources, service
    run, state, store = load_run(args)
    prepared = read(stage_dir(run, args.stage) / 'dispatch.json')
    if not args.executor.startswith('/root/'):
        raise ValueError('use actual native canonical Root child identity')
    task = lookup(store, prepared['task_id'])
    claim = service.task_start(store.project_root, task_id=task['task_id'], execution_ref=args.executor,
        supported_protocols=[task['protocol_version']] if task.get('protocol_version') else None,
        capabilities=task.get('required_capabilities'))
    methods = method_resources.read_task_methods(store.project_root, task['task_id'])
    if methods['status'] != 'current' or methods['current_method_release'] != prepared['method_release']:
        raise ValueError('dispatched installed method basis changed')
    save(stage_dir(run, args.stage) / 'claim.json', claim)
    save(stage_dir(run, args.stage) / 'method-read-record.json', methods)
    print(json.dumps(methods, ensure_ascii=False, indent=2))


def check_completion(run, state, store, stage, args):
    target = stage_dir(run, stage)
    dispatch = read(target / 'dispatch.json')
    result_raw = Path(args.result).read_bytes()
    if sha(result_raw) != args.result_sha256:
        raise ValueError('Root observed different raw model output')
    observed_raw = Path(args.controller_observation).read_bytes()
    if sha(observed_raw) != args.observation_sha256:
        raise ValueError('Root observation bytes changed')
    observation = json.loads(observed_raw)
    spawn, completed = observation['spawn'], observation['completion']
    executor = spawn['canonical_task_name']
    if (observation.get('observation_kind') != OBSERVER_KIND or observation.get('assurance') != 'host_attested'
            or spawn['tool'] != 'collaboration.spawn_agent' or not executor.startswith('/root/')
            or spawn.get('returned_task_name') != executor
            or completed['sender'] != executor or completed['message_type'] != 'FINAL_ANSWER'
            or completed['status_observation_tool'] != 'collaboration.list_agents'
            or completed['observed_status'] != 'completed' or executor not in completed['observed_completed_agents']
            or not completed['raw_final_message'] or observation['project_id'] != state['project_id']
            or observation['task_id'] != dispatch['task_id'] or observation['model_output_bytes_sha256'] != sha(result_raw)
            or observation['method_release'] != dispatch['method_release']):
        raise ValueError('actual canonical spawn/completion/task/output/method identities must agree')
    timestamp(observation['observed_at_utc'])
    method = observation['method_read_record']
    method_path = Path(method['path']).resolve()
    if not method_path.is_relative_to(target):
        raise ValueError('method read must be actual stage record')
    method_raw = method_path.read_bytes()
    method_read = json.loads(method_raw)
    if (sha(method_raw) != method['sha256'] or method_read['task_id'] != dispatch['task_id']
            or method_read['project_id'] != state['project_id'] or method_read['status'] != 'current'
            or method_read['current_method_release'] != dispatch['method_release']
            or method_read['work_order'].get('execution_ref') != executor):
        raise ValueError('actual method response after native claim is required')
    task = lookup(store, dispatch['task_id'])
    if task['status'] != 'running' or task.get('execution_ref') != executor:
        raise ValueError('native execution must claim before completion; accept does not fabricate claims')
    immutable_bytes(target / 'observed-raw-model-output.json', result_raw)
    immutable_bytes(target / 'observed-root-completion.json', observed_raw)
    return task, json.loads(result_raw), observation, observed_raw


def accept(args):
    from deck_master import service
    run, state, store = load_run(args)
    task, envelope, observation, _ = check_completion(run, state, store, args.stage, args)
    if task['kind'] != 'compose':
        raise ValueError('review uses review-accept with a scoped trusted provider')
    if envelope.get('usage_events'):
        raise ValueError('content experiment external-call budget is zero')
    try:
        outcome = service.accept_result(store.project_root, task_id=task['task_id'], operation_id=task['operation_id'], produced_against=task['produced_against'], result_payload=envelope)
    except Exception as exc:
        save(stage_dir(run, args.stage) / 'acceptance-refused.json', {'actual_native_writer': observation['spawn']['canonical_task_name'], 'raw_output_sha256': args.result_sha256, 'error_type': type(exc).__name__, 'error': str(exc), 'semantic_fallback': False, 'observed_at': now()})
        raise
    save(stage_dir(run, args.stage) / 'accepted.json', {'accepted_at': now(), 'actual_native_writer': observation['spawn']['canonical_task_name'], 'raw_output_sha256': args.result_sha256, 'assurance': 'host_attested', 'result': outcome})
    if args.stage == '04-speech':
        snapshot(run, store, 'raw-first-complete-draft')
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


def owner_reply(args):
    from deck_master import service
    run, state, store = load_run(args)
    read(stage_dir(run, '01-framing') / 'accepted.json')
    if state['case'] == 'Q1' and not args.legitimate_question_observed:
        raise ValueError('Root must observe actual legitimate framing question before supplying frozen answer')
    if state['case'] == 'Q1' and not args.cancel_unstarted_input_revision:
        raise ValueError('this SDK always opens empty-project input_revision on facts update; Root must first authorize formal cancellation of the unexecuted task')
    message = protocol()['script_messages'][state['case']].get('after_legitimate_framing_question')
    if message is None:
        message = protocol()['script_messages']['Q2']['initial']
    save(run / 'owner-fact-message.json', {'message': message, 'kind': 'frozen synthetic controller reply, not human', 'actual_question_observed_by_root': args.legitimate_question_observed, 'Q2_fact_change': False if state['case'] == 'Q2' else None})
    if state['case'] == 'Q1':
        patch = {'reason': 'fixed synthetic Owner clarified audience, use and budget', 'task_patch': {'brief': message, 'audience': '新接单员', 'scenario': '8分钟、6页现场培训；逐字稿；先主线、最密一页样稿，确认后全套', 'presentation_mode': 'live', 'page_limit': 6}}
        updated = service.inputs_update(store.project_root, patch=patch, base_revision=store.current_revision_id(), operation_id='actual-owner-facts')
        save(run / 'owner-facts-inputs-update.json', updated)
        active = [store.read_object_json(r) for r in store.load_document()['tasks']]
        active = [t for t in active if t['status'] in ('awaiting_host', 'running', 'queued') and t.get('intent') == 'input_revision']
        if active and not args.cancel_unstarted_input_revision:
            raise ValueError('SDK opened empty-project input_revision; no model launch. Root must explicitly authorize documented cancellation.')
        cancellations = []
        for task in active:
            if task['status'] != 'awaiting_host' or task.get('execution_ref'):
                raise ValueError('cannot cancel an actual executed reconciliation as a mechanical step')
            cancellations.append(service.task_cancel(store.project_root, task_id=task['task_id'], reason='empty-project facts recorded; no content to reconcile; formal argument task will consume facts'))
        save(run / 'unused-input-revision-cancellations.json', cancellations)
    requested = start(store, message, op='actual-clarified-request', content_intent='plan_only')
    save(run / 'owner-clarified-request.json', requested)
    print(json.dumps({'status': 'fixed_owner_facts_recorded', 'next': 'dispatch --phase argument'}, ensure_ascii=False))


def dispatch(args):
    from deck_master import content_production
    run, state, store = load_run(args)
    phase = args.phase
    stage = {'argument': '02-argument', 'page_copy': '03-page-copy', 'speech': '04-speech'}[phase]
    prerequisite = {'argument': run / 'owner-clarified-request.json', 'page_copy': run / 'adopted-argument.json', 'speech': stage_dir(run, '03-page-copy') / 'accepted.json'}[phase]
    read(prerequisite)
    task = content_production.open_phase_task(store, store.load_document(), operation_id='actual-' + phase.replace('_', '-'), phase=phase)
    print(json.dumps(packet(run, state, store, task, stage), ensure_ascii=False))


def adopt(args):
    from deck_master import collaboration, content_production
    run, state, store = load_run(args)
    repair = args.command == 'repair-adopt'
    adopted_path = 'repair-adopted-argument.json' if repair else 'adopted-argument.json'
    accepted = read(stage_dir(run, 'repair-argument' if repair else '02-argument') / 'accepted.json')['result']
    narrative_ref, plan_ref = accepted['narrative_ref'], accepted.get('plan_ref')
    if plan_ref is None:
        raise ValueError('actual argument omitted planned Plan; retain failure, do not fabricate page roles')
    message = protocol()['repair_controller_instruction'] if repair else protocol()['script_messages'][state['case']]['after_actual_argument_proposal']
    if not repair:
        requested = start(store, message, op='actual-content-prerequisite-request')
        save(run / 'accepted-direction-message.json', {'message': message, 'kind': 'fixed synthetic controller choice of actual current proposal, not human', 'request': requested})
    subjects = [{'artifact_kind': 'narrative', 'artifact_ref': narrative_ref, 'projection': 'direction'}, {'artifact_kind': 'content_plan', 'artifact_ref': plan_ref, 'projection': 'page_roles'}, {'artifact_kind': 'content_plan', 'artifact_ref': plan_ref, 'projection': 'page_order'}]
    chosen_scope = scope(['narrative', 'plan', 'page_copy', 'speech', 'review'], membership=True)
    decision_input = {'topic': 'direction', 'subject_refs': subjects, 'scope': chosen_scope, 'value': {'message': message}, 'disposition': 'accepted', 'authority_mode': 'delegated' if repair else 'direct_user', 'instruction_evidence': evidence(store, message)}
    if repair:
        decision_input['delegation_ref'] = read(run / 'repair-begin.json')['delegation']['authorization_ref']
    prefix = 'repair' if repair else 'actual'
    decision = collaboration.record_decision(store.project_root, input=decision_input, base_revision=store.current_revision_id(), operation_id=prefix + '-direction-decision')
    adopted = []
    for ref, layers in ((narrative_ref, ['narrative']), (plan_ref, ['plan'])):
        adopted.append(content_production.adopt_proposal(store.project_root, input={'proposal_ref': ref, 'decision_ref': decision['decision_ref'], 'write_scope': scope(layers)}, base_revision=store.current_revision_id(), operation_id=prefix + '-adopt-' + layers[0]))
    save(run / adopted_path, {'decision': decision, 'adoptions': adopted, 'visual_authorization_issued': False})
    print(json.dumps({'status': 'actual_argument_and_plan_adopted', 'next': 'dispatch --phase page_copy'}, ensure_ascii=False))


def snapshot(run, store, name):
    document = store.load_document()
    content = {'document': document, 'narrative': store.read_object_json(document['narrative']) if document.get('narrative') else None,
        'plan': store.read_object_json(document['content_plan']) if document.get('content_plan') else None,
        'pages': [{'ref': e['page'], 'object': store.read_object_json(e['page'])} for e in document['pages']],
        'tasks': [store.read_object_json(r) for r in document['tasks']],
        'kind': 'actual accepted native model manuscript; original raw outputs remain per-stage', 'human_owner_review': 'NOT_RUN'}
    save(run / (name + '.json'), content)
    return content


def observed_authors(run):
    return {read(path)['actual_native_writer'] for path in (run / 'stages').glob('*/accepted.json')}


def review_prepare(args):
    from deck_master import capabilities, content_review, review_evidence
    run, state, store = load_run(args)
    # Freeze the complete first manuscript before dispatching reviewer feedback.
    frozen = run / 'raw-first-complete-draft.json'
    if not frozen.exists():
        raise ValueError('complete native manuscript has not yet been frozen')
    if (run / 'review-prepare.json').exists():
        raise ValueError('fixed feedback budget permits only one review preparation')
    provider = NativeControllerProvider(args.bootstrap_observation)
    registry = review_evidence.ProviderRegistry()
    registry.register(provider)
    runtime = review_evidence.ProviderRuntime(registry)
    with runtime.bound():
        channel = registry.channel_context()
        actual_capabilities = capabilities.describe(channel)
        prepared = content_review.dispatch_preproduction_review(store.project_root, adapter_context=channel)
    if prepared['status'] != 'review_dispatched':
        raise ValueError('actual independent channel did not dispatch: ' + prepared['status'])
    task = prepared['task']
    detail = packet(run, state, store, task, '05-independent-review')
    target = stage_dir(run, '05-independent-review')
    document = store.load_document()
    subjects = [document['narrative'], document['content_plan'], *[e['page'] for e in document['pages']]]
    authors = content_review.author_execution_refs(store, document, subjects)
    if not authors or not authors <= observed_authors(run):
        raise ValueError('every manuscript author must map to real observed native Writer execution')
    dependencies = [{'kind': 'content', 'identity': 'narrative', 'sha256': document['narrative']['sha256']},
                    {'kind': 'content', 'identity': 'content_plan', 'sha256': document['content_plan']['sha256']}]
    dependencies += [{'kind': 'content', 'identity': 'page:' + e['page_id'], 'sha256': e['page']['sha256']} for e in document['pages']]
    dependencies += [{'kind': 'source', 'identity': s['source_id'], 'sha256': s['extract']['sha256']} for s in document['sources']]
    save(target / 'review-packet.json', store.read_object_json(prepared['review_draft_ref']))
    save(target / 'review-envelope-metadata.json', {'kind': 'review', 'files': [], 'pages': [], 'page_order': [], 'artifact_specs': [], 'usage_events': [], 'notes': 'actual independent native content review; synthetic business input, not human acceptance'})
    save(target / 'review-binding-shape.json', {'units': prepared['units'], 'subjects': subjects, 'dependencies': dependencies, 'packet_ref': prepared['review_draft_ref'], 'formal_current_ref_author_execution_refs': sorted(authors), 'author_execution_refs': sorted(observed_authors(run)), 'reviewer_type': 'independent_host', 'assurance': 'host_attested', 'execution_ref_rule': 'use actual canonical identity different from every initial manuscript author, including Page copy authors whose Ref changed during speech', 'evidence_ref_rule': 'actual packet read may cite packet_ref; Root supplies separate actual native execution proof', 'status_rule': 'judge all units honestly; do not target a pass'})
    immutable_bytes(target / 'reviewer-instructions.txt', f'''Actual independent content review, not human/professional acceptance.
Read the entire review-packet.json, review-binding-shape.json, schemas/review.v2.schema.json and actual installed methods.
Use a native identity different from every author listed in review-binding-shape.json.
Run {sys.executable} -B -I {HERE / 'driver.py'} claim-read --run-dir {run} --stage 05-independent-review --executor YOUR_ACTUAL_NATIVE_CANONICAL_TASK
Read the entire returned installed methods. Submit review-envelope-metadata.json fields plus one substantive review per required unit.
Bind exact actual subjects/dependencies; locate findings at page/atom/node with specific source and explain necessary repair.
Preserve uncertainty and useful sparse pages. Never write manuscript semantics or fabricate native/human receipt claims.
Write your actual review envelope to {target / 'model-output.json'} exclusively.
Your final native message must state canonical identity, output/raw SHA256 and actual method read path/SHA256.
'''.encode())
    save(run / 'review-prepare.json', {'packet_ref': prepared['review_draft_ref'], 'task_id': task['task_id'], 'formal_current_ref_author_execution_refs': sorted(authors), 'author_execution_refs': sorted(observed_authors(run)), 'bootstrap_observation': str(Path(args.bootstrap_observation).resolve()), 'bootstrap_sha256': sha(provider.bootstrap_raw), 'capabilities': actual_capabilities, 'manuscript_provenance': 'actual observed native Writer output on original uploaded synthetic Q facts', 'human_acceptance': 'NOT_RUN'})
    print(json.dumps(detail, ensure_ascii=False))


def review_accept(args):
    from copy import deepcopy
    from deck_master import capabilities, content_review, review_evidence, service
    run, state, store = load_run(args)
    prepared = read(run / 'review-prepare.json')
    task, envelope, observation, raw_observation = check_completion(run, state, store, '05-independent-review', args)
    executor = observation['spawn']['canonical_task_name']
    binding = review_evidence.review_binding(store, store.load_document(), task, envelope)
    if not set(binding['author_execution_refs']) <= observed_authors(run) or executor in observed_authors(run):
        raise ValueError('reviewer must be independent of every actual manuscript author')
    issued = datetime.now(timezone.utc)
    claims = {**binding, 'provider_id': PROVIDER_ID, 'event_id': 'root-transcription-' + sha(raw_observation)[:32],
        'channel': CHANNEL, 'issued_at': issued.isoformat(), 'expires_at': (issued + timedelta(minutes=30)).isoformat(),
        'executor_ref': executor, 'reviewer_id': executor, 'assurance': 'host_attested',
        'observation_kind': OBSERVER_KIND, 'model_output_bytes_sha256': args.result_sha256,
        'controller_observation_sha256': args.observation_sha256,
        'author_provenance_kind': prepared['manuscript_provenance'],
        'all_native_writer_execution_refs': sorted(observed_authors(run)),
        'evidence_scope': 'actual synthetic-Q native independent content review; not human/professional or blind evaluation'}
    provider = NativeControllerProvider(args.bootstrap_observation or prepared['bootstrap_observation'], observed_raw=raw_observation, claims=claims)
    registry = review_evidence.ProviderRegistry(); registry.register(provider)
    runtime = review_evidence.ProviderRuntime(registry)
    before = store.load_document()
    protected = {k: deepcopy(before.get(k)) for k in ('narrative', 'content_plan', 'pages', 'files', 'design_context', 'outputs')}
    negatives = {}
    with runtime.bound():
        caps = capabilities.describe(registry.channel_context())
        if not caps[CHANNEL] or caps['verified_user_events'] or caps['human_review_receipts']:
            raise ValueError('fixed adapter must expose independent native channel only')
        rev = store.current_revision_id()
        try:
            service.accept_result(store.project_root, task_id=task['task_id'], operation_id=task['operation_id'], produced_against=task['produced_against'], result_payload=envelope, adapter_context={CHANNEL: [{'verified': True}]})
        except review_evidence.EvidenceRejected as exc:
            negatives['ordinary_json_context'] = {'refused': True, 'reason': str(exc)}
        else:
            raise AssertionError('ordinary output JSON must not select provider trust')
        if store.current_revision_id() != rev:
            raise AssertionError('forged-context refusal changed revision')
        changed = deepcopy(envelope); changed['notes'] = str(changed.get('notes', '')) + ' [negative replay control]'
        selector = {'provider_id': PROVIDER_ID, 'event_id': claims['event_id']}
        try:
            registry.review_context(store, store.load_document(), task, changed, selector)
        except review_evidence.EvidenceRejected as exc:
            negatives['changed_result_replay'] = {'refused': True, 'reason': str(exc)}
        else:
            raise AssertionError('receipt must bind exact original model result')
        context = registry.review_context(store, store.load_document(), task, envelope, selector)
        outcome = service.accept_result(store.project_root, task_id=task['task_id'], operation_id=task['operation_id'], produced_against=task['produced_against'], result_payload=envelope, adapter_context=context)
    after = store.load_document()
    if {k: after.get(k) for k in protected} != protected:
        raise AssertionError('review-only acceptance changed manuscript or production')
    proofs = [store.read_object_json(r) for r in lookup(store, task['task_id']).get('result_refs', [])]
    proofs = [p for p in proofs if p.get('schema_version') == 'authenticated_review_receipt.v1']
    if len(proofs) != 1 or store.read_object_bytes(proofs[0]['raw_event_ref']) != raw_observation:
        raise AssertionError('actual native observation bytes were not retained as immutable proof')
    save(run / 'review-finish.json', {'actual_native_reviewer': executor, 'raw_output_sha256': args.result_sha256, 'root_observation_sha256': args.observation_sha256, 'binding': binding, 'proof': proofs[0], 'negative_controls': negatives, 'acceptance': outcome, 'capabilities': caps, 'preproduction_status': content_review.preproduction_status(store, after), 'human_acceptance': 'NOT_RUN; user deferred', 'professional_predicate': 'not asserted'})
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


def repair_begin(args):
    from deck_master import collaboration
    run, state, store = load_run(args)
    read(run / 'review-finish.json')
    feedback_path = stage_dir(run, '05-independent-review') / 'observed-raw-model-output.json'
    feedback = read(feedback_path)
    if not any(r.get('findings') or r.get('status') != 'pass' for r in feedback['reviews']):
        raise ValueError('no actual defect; do not manufacture a repair round')
    layers = [p for p in ('argument', 'page_copy', 'speech') if p in args.necessary_layers]
    if 'argument' in layers and 'page_copy' not in layers:
        raise ValueError('changed Narrative requires real Page remapping; include page_copy')
    if len(layers) > protocol()['max_necessary_repair_stages'] or len(layers) != len(args.necessary_layers):
        raise ValueError('repair budget/order/duplicate layers invalid')
    necessity_raw = Path(args.necessity_record).read_bytes()
    necessity = json.loads(necessity_raw)
    if necessity.get('necessary_layers') != layers or not necessity.get('actual_review_finding_refs'):
        raise ValueError('Root must retain necessary-layer selection referencing actual feedback findings')
    if (run / 'repair-begin.json').exists():
        raise ValueError('one repair round only')
    message = protocol()['repair_controller_instruction']
    requested = start(store, message, op='repair-single-round-request')
    delegate_scope = scope(['narrative', 'plan', 'page_copy', 'speech', 'review'], membership=True)
    delegation = collaboration.grant(store.project_root, input={'mode': 'delegate',
        'actions': ['dispatch.compose', 'task.start', 'task.accept', 'proposal.adopt'],
        'scope': delegate_scope, 'delegated_topics': ['direction', 'manuscript', 'speech'],
        'constraints': {'experiment_repair_round': 1, 'necessary_layers': layers,
            'future_pages': {'selector': 'adopted_plan_for_this_request', 'max_pages': state['budget']['max_pages'], 'max_pages_basis': 'provided'}},
        'max_external_calls': 0, 'max_candidate_count': 0, 'adoption_policy': 'within_scope',
        'instruction_evidence': evidence(store, message)},
        base_revision=store.current_revision_id(), operation_id='repair-single-round-delegation')
    immutable_bytes(run / 'repair-necessity-record.json', necessity_raw)
    save(run / 'repair-begin.json', {'necessary_layers': layers, 'actual_feedback_sha256': sha(feedback_path.read_bytes()),
        'necessity_record_sha256': sha(necessity_raw), 'request': requested, 'delegation': delegation,
        'initial_draft_preserved': True, 'new_facts': False, 'new_feedback': False, 'images': 0,
        'authority': 'synthetic experiment autonomous repair delegation; not human Owner approval'})
    print(json.dumps({'status': 'single_repair_round_begun', 'necessary_layers': layers}, ensure_ascii=False))


def repair_dispatch(args):
    from deck_master import content_production
    run, state, store = load_run(args)
    selected = read(run / 'repair-begin.json')['necessary_layers']
    if args.phase not in selected:
        raise ValueError('layer was not selected as necessary; no empty extra model stage')
    for earlier in selected[:selected.index(args.phase)]:
        read(stage_dir(run, 'repair-' + earlier.replace('_', '-')) / 'accepted.json')
    if args.phase != 'argument' and 'argument' in selected:
        read(run / 'repair-adopted-argument.json')
    task = content_production.open_phase_task(store, store.load_document(), operation_id='repair-' + args.phase.replace('_', '-'), phase=args.phase)
    print(json.dumps(packet(run, state, store, task, 'repair-' + args.phase.replace('_', '-')), ensure_ascii=False))


def finish_content(args):
    from deck_master import content_review
    run, state, store = load_run(args)
    read(run / 'review-finish.json')
    repairs = run / 'repair-begin.json'
    if repairs.exists():
        selected = read(repairs)['necessary_layers']
        for phase in selected:
            read(stage_dir(run, 'repair-' + phase.replace('_', '-')) / 'accepted.json')
        snapshot(run, store, 'repaired-current')
    elif any(r.get('status') != 'pass' or r.get('findings') for r in read(stage_dir(run, '05-independent-review') / 'observed-raw-model-output.json')['reviews']):
        raise ValueError('actual review has defects; no repaired current draft yet')
    snapshot(run, store, 'first-complete-draft-for-owner')
    save(run / 'content-finish.json', {'scope': 'E1 actual content subtask only', 'initial_raw_draft': str(run / 'raw-first-complete-draft.json'),
        'first_for_owner_draft': str(run / 'first-complete-draft-for-owner.json'),
        'single_repair_round': repairs.exists(), 'initial_failure_preserved': True,
        'current_preproduction_status': content_review.preproduction_status(store, store.load_document()),
        'review_after_repair': 'NOT_RUN; E1 no repeated feedback; subsequent blind assessment reports repaired draft separately' if repairs.exists() else 'same actual independent review',
        'human_owner_acceptance': 'NOT_RUN; explicitly deferred', 'professional_predicate': 'not asserted',
        'model_generation_quality': 'independent blind assessment pending; no aggregate PASS manufactured',
        'original_twelve_host_session': False})
    print(json.dumps({'status': 'actual_content_artifacts_frozen_for_independent_assessment', 'human_acceptance': 'NOT_RUN'}, ensure_ascii=False))


def status(args):
    from deck_master import content_production, service
    run, state, store = load_run(args)
    print(json.dumps({'installation_identity': identity(state['arm']), 'inputs': service.inputs_show(store.project_root), 'phase': content_production.content_phase_status(store, store.load_document()), 'tasks': [store.read_object_json(r) for r in store.load_document()['tasks']]}, ensure_ascii=False, indent=2))


def configure_b(args):
    if (HERE / 'B-registration.json').exists():
        raise ValueError('B is already frozen; use a new protocol/run for changed methods')
    manifest = read(args.manifest)
    if manifest['source_sha'] != args.expected_source or manifest['wheel_sha256'] != args.expected_wheel:
        raise ValueError('B candidate differs from Root fixed source/wheel')
    save(HERE / 'B-registration.json', {'source_sha': args.expected_source, 'source_tree': manifest['source_tree'], 'wheel_sha256': args.expected_wheel, 'manifest': str(Path(args.manifest).resolve()), 'python': str(Path(args.python).absolute()), 'A_to_B_diff_manifest': str(Path(args.diff_manifest).resolve()), 'A_to_B_diff_sha256': sha(Path(args.diff_manifest).read_bytes()), 'registered_at': now()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('init'); p.add_argument('--arm', choices=['A_run', 'B_run'], required=True); p.add_argument('--case', choices=['Q1', 'Q2'], required=True); p.add_argument('--run-dir', required=True); p.set_defaults(func=init)
    for name, function in [('status', status), ('owner-reply', owner_reply), ('adopt', adopt), ('dispatch', dispatch), ('claim-read', claim_read), ('accept', accept), ('review-prepare', review_prepare), ('review-accept', review_accept), ('repair-begin', repair_begin), ('repair-dispatch', repair_dispatch), ('repair-adopt', adopt), ('finish-content', finish_content)]:
        p = commands.add_parser(name); p.add_argument('--run-dir', required=True); p.set_defaults(func=function)
        if name in ('claim-read', 'accept'): p.add_argument('--stage', choices=STAGES, required=True)
        if name == 'claim-read': p.add_argument('--executor', required=True)
        if name == 'dispatch': p.add_argument('--phase', choices=['argument', 'page_copy', 'speech'], required=True)
        if name == 'repair-dispatch': p.add_argument('--phase', choices=['argument', 'page_copy', 'speech'], required=True)
        if name == 'repair-begin':
            p.add_argument('--necessary-layers', nargs='+', choices=['argument', 'page_copy', 'speech'], required=True)
            p.add_argument('--necessity-record', required=True)
        if name == 'owner-reply': p.add_argument('--legitimate-question-observed', action='store_true'); p.add_argument('--cancel-unstarted-input-revision', action='store_true')
        if name in ('accept', 'review-accept'):
            for key in ('result', 'result-sha256', 'controller-observation', 'observation-sha256'): p.add_argument('--' + key, required=True)
        if name in ('review-prepare', 'review-accept'): p.add_argument('--bootstrap-observation', required=name == 'review-prepare')
    p = commands.add_parser('configure-b'); p.set_defaults(func=configure_b)
    for key in ('manifest', 'python', 'expected-source', 'expected-wheel', 'diff-manifest'): p.add_argument('--' + key, required=True)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
