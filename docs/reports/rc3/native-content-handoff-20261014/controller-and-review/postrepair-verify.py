#!/usr/bin/env python3
"""Supplemental native content verification using a separately admitted SDK.

Root is the trusted transport controller. This tool never generates model
content, fabricates a completion, edits an old result or changes frozen E1.
Use the admitted Python with -B -I. Every write is explicit and uses public
SDK APIs; all additional evidence lives under run/verification/.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import runpy
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER_SHA = 'f70a5d63a0da54e941e0e754af62988a37de87e58bad1ff651e9a7fc37947c23'
PROTOCOL_SHA = '4fa26f301f817bb274586e8a18359d5ea598b670b28cf785bb46d785e3e14f67'
OBSERVER_KIND = 'root_controller_transcription_of_actual_native_tool_response'
PROVIDER_ID = 'rc3-native-supplemental-controller'
CHANNEL = 'independent_review_receipts'
PURPOSES = ('postrepair', 'final-content-verification', 'post-failure-verification')
PROTECTED = ('narrative', 'content_plan', 'pages', 'files', 'design_context',
             'outputs', 'sources', 'task', 'content_basis', 'policy')
CLASSIFICATION = 'supplemental_protocol_repair_not_original_frozen_E1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate JSON key: ' + key)
            value[key] = item
        return value
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=constant)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def raw_save(path, raw):
    with Path(path).open('xb') as stream:
        stream.write(raw)


def now():
    return datetime.now(timezone.utc).isoformat()


def frozen_helpers():
    if sha((HERE / 'driver.py').read_bytes()) != DRIVER_SHA:
        raise ValueError('original frozen driver changed')
    if sha((HERE / 'protocol.json').read_bytes()) != PROTOCOL_SHA:
        raise ValueError('original frozen protocol changed')
    return runpy.run_path(str(HERE / 'driver.py'), run_name='frozen_helpers_only')


def admitted(args):
    """Independent admission: never call the frozen installation identity."""
    import deck_master
    from deck_master import capabilities
    from deck_master.store import Store
    helpers = frozen_helpers()
    run = Path(args.run_dir).resolve()
    state = read(run / 'run-manifest.json')
    if state['protocol_sha256'] != PROTOCOL_SHA or state['harness_sha256'] != DRIVER_SHA:
        raise ValueError('run is not bound to the original frozen experiment')
    if not sys.flags.isolated:
        raise ValueError('mandatory isolated Python -I')
    manifest_path = Path(args.installation_manifest).resolve()
    manifest = read(manifest_path)
    actual = capabilities.installation_identity()
    installed = actual.get('install') or {}
    if (manifest['source_sha'] != args.expected_source
            or manifest['wheel_sha256'] != args.expected_wheel
            or installed.get('source_sha') != args.expected_source
            or installed.get('wheel_sha256') != args.expected_wheel
            or Path(deck_master.__file__).resolve() != Path(manifest['module_path']).resolve()
            or Path(sys.executable).absolute() != Path(args.expected_python).absolute()
            or not Path(deck_master.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())):
        raise ValueError('SDK/module/source/wheel differs from explicit new admission')
    transition_path = Path(args.transition_record).resolve()
    transition_raw = transition_path.read_bytes()
    if sha(transition_raw) != args.transition_sha256:
        raise ValueError('transition record changed')
    transition = read(transition_path)
    old = state['installation_admission']
    if (transition.get('classification') != CLASSIFICATION
            or transition.get('old_installation') != {k: old[k] for k in ('source_sha', 'wheel_sha256')}
            or transition.get('new_installation') != {
                'source_sha': args.expected_source, 'wheel_sha256': args.expected_wheel}):
        raise ValueError('transition must bind actual original and supplemental installations')
    difference = transition['difference_record']
    if sha(Path(difference['path']).read_bytes()) != difference['sha256']:
        raise ValueError('old/new source difference record changed')
    old_root = Path(state['installation_identity']['method_root']).resolve()
    new_root = Path(deck_master.__file__).resolve().parent / 'resources' / 'skill'
    old_files = {p.relative_to(old_root).as_posix(): sha(p.read_bytes())
                 for p in old_root.rglob('*') if p.is_file()}
    new_files = {p.relative_to(new_root).as_posix(): sha(p.read_bytes())
                 for p in new_root.rglob('*') if p.is_file()}
    method_changes = [{'relative_path': name, 'old_sha256': old_files.get(name),
                       'new_sha256': new_files.get(name)}
                      for name in sorted(old_files.keys() | new_files.keys())
                      if old_files.get(name) != new_files.get(name)]
    if method_changes and transition.get('permitted_method_change') is not True:
        raise ValueError('methods changed despite method-preservation admission')
    record = {'classification': CLASSIFICATION, 'installation': actual,
              'manifest_path': str(manifest_path), 'manifest_sha256': sha(manifest_path.read_bytes()),
              'expected_python': str(Path(args.expected_python).absolute()),
              'transition_path': str(transition_path), 'transition_sha256': args.transition_sha256,
              'source_difference': difference, 'method_changes': method_changes,
              'not_original_frozen_E1': True, 'frozen_driver_sha256': DRIVER_SHA,
              'frozen_protocol_sha256': PROTOCOL_SHA, 'adapter_sha256': sha(Path(__file__).read_bytes())}
    return helpers, run, state, Store(state['project']), record


def originals(run):
    files = [HERE / 'driver.py', HERE / 'protocol.json', run / 'run-manifest.json']
    files += [p for p in run.glob('*.json') if p.is_file()]
    for stage in (run / 'stages').iterdir():
        if stage.is_dir():
            files += [p for p in stage.rglob('*') if p.is_file()]
    return {str(p.resolve()): sha(p.read_bytes()) for p in files}


def original_check(record):
    if any(sha(Path(p).read_bytes()) != digest for p, digest in record.items()):
        raise AssertionError('original experiment evidence changed')


def protected(document):
    return {k: copy.deepcopy(document.get(k)) for k in PROTECTED}


def stage_for(args, run):
    return run / 'verification' / args.purpose


def actual_authors(helpers, run, store):
    """Every completed compose execution, including superseded Page authors."""
    stages = {p.parent.resolve(): p for p in (run / 'stages').glob('*/accepted.json')}
    supplement = run / 'verification' / 'post-failure-consumption'
    if supplement.exists():
        for p in supplement.glob('*/accepted.json'):
            stages[Path(read(p)['original_stage_path']).resolve()] = p
    tasks = [store.read_object_json(r) for r in store.load_document()['tasks']]
    completed = {t['task_id']: t for t in tasks
                 if t['kind'] == 'compose' and t['status'] == 'completed'}
    records = []
    covered = set()
    for stage, accepted_path in sorted(stages.items(), key=lambda pair: str(pair[0])):
        dispatch = read(stage / 'dispatch.json')
        task = completed.get(dispatch['task_id'])
        if task is None:
            raise ValueError('accepted author stage is not a completed actual compose Task')
        accepted = read(accepted_path)
        executor = accepted['actual_native_writer']
        digest = accepted['raw_output_sha256']
        if (task.get('execution_ref') != executor or not executor.startswith('/root/')
                or accepted.get('result', {}).get('status') != 'accepted'
                or not task.get('result_refs')):
            raise ValueError('formal task and accepted native author do not agree')
        method_path = stage / 'method-read-record.json'
        method = read(method_path)
        if (method.get('task_id') != task['task_id']
                or method['work_order'].get('execution_ref') != executor
                or method['work_order'].get('execution_started_at') != task.get('execution_started_at')):
            raise ValueError('native author lacks its actual original claim/method record')
        candidates = list(stage.glob('*.json'))
        candidates += list(stage.glob('mechanical-correction-attempt-*/*.json'))
        if accepted_path.parent != stage:
            candidates += list(accepted_path.parent.glob('*.json'))
        raw_matches = [p for p in candidates if sha(p.read_bytes()) == digest]
        observers = []
        for p in candidates:
            obj = read(p)
            if (isinstance(obj, dict) and obj.get('observation_kind') == OBSERVER_KIND
                    and obj.get('assurance') == 'host_attested'
                    and obj.get('model_output_bytes_sha256') == digest
                    and obj.get('task_id') == task['task_id']
                    and obj.get('project_id') == store.load_document()['project_id']
                    and obj.get('spawn', {}).get('canonical_task_name') == executor
                    and obj.get('completion', {}).get('sender') == executor
                    and obj.get('completion', {}).get('message_type') == 'FINAL_ANSWER'
                    and digest in obj.get('completion', {}).get('raw_final_message', '')
                    and obj.get('method_read_record', {}).get('sha256') == sha(method_path.read_bytes())):
                observers.append(p)
        checked_observers = []
        for p in observers:
            obj = read(p)
            spawn = obj['spawn']
            if (spawn.get('tool') != 'collaboration.spawn_agent'
                    or spawn.get('returned_task_name') != executor or spawn.get('fork_turns') != 'none'
                    or obj.get('method_release') != dispatch['method_release']
                    or obj.get('method_release') != method.get('current_method_release')
                    or Path(obj['method_read_record']['path']).resolve() != method_path.resolve()):
                continue
            try:
                completion_status(obj['completion'], executor)
            except ValueError:
                continue
            checked_observers.append(p)
        observers = checked_observers
        if not raw_matches or not observers:
            raise ValueError('accepted writer lacks retained actual raw output/native FINAL binding')
        records.append({'task_id': task['task_id'], 'execution_ref': executor,
                        'accepted_record': str(accepted_path),
                        'accepted_record_sha256': sha(accepted_path.read_bytes()),
                        'raw_output_sha256': digest, 'raw_output_paths': [str(p) for p in raw_matches],
                        'native_observation_paths': [str(p) for p in observers],
                        'method_read_sha256': sha(method_path.read_bytes())})
        covered.add(task['task_id'])
    if covered != set(completed) or not records:
        raise ValueError('every completed substantive author must have actual native provenance')
    return records


def independent(executor, provenance, prior_reviewers=()):
    if not isinstance(executor, str) or not executor.startswith('/root/'):
        raise ValueError('use the actual native canonical execution identity')
    if executor in {r['execution_ref'] for r in provenance}:
        raise ValueError('every actual manuscript author is forbidden as independent verifier')
    if executor in prior_reviewers:
        raise ValueError('verification requires a fresh execution, distinct from prior reviewers')


def providers(helpers, bootstrap, *, observation=None, claims=None):
    from deck_master import review_evidence
    base = helpers['NativeControllerProvider']
    class SupplementalProvider(base):
        provider_id = PROVIDER_ID
        adapter_version = 'rc3-native-supplemental-controller.v1'
    provider = SupplementalProvider(bootstrap, observed_raw=observation, claims=claims)
    registry = review_evidence.ProviderRegistry()
    registry.register(provider)
    return provider, registry, review_evidence.ProviderRuntime(registry)


def current_repair_complete(helpers, run, store, purpose):
    if not (run / 'raw-first-complete-draft.json').is_file() or not (run / 'review-finish.json').is_file():
        raise ValueError('original complete draft and actual initial independent review are required')
    first = read(run / 'review-finish.json')
    task = helpers['lookup'](store, first['binding']['task_id'])
    original_review = run / 'stages' / '05-independent-review'
    proof_objects = [store.read_object_json(ref) for ref in task.get('result_refs', [])]
    receipts = [obj for obj in proof_objects
                if obj.get('schema_version') == 'authenticated_review_receipt.v1']
    if (task['kind'] != 'review' or task['status'] != 'completed'
            or task.get('execution_ref') != first['actual_native_reviewer']
            or first.get('acceptance', {}).get('status') != 'accepted'
            or sha((original_review / 'observed-raw-model-output.json').read_bytes()) != first['raw_output_sha256']
            or sha((original_review / 'observed-root-completion.json').read_bytes()) != first['root_observation_sha256']
            or len(receipts) != 1 or receipts[0] != first['proof']
            or store.read_object_bytes(receipts[0]['raw_event_ref']) !=
            (original_review / 'observed-root-completion.json').read_bytes()):
        raise ValueError('initial review must be an actual formally accepted authenticated native result')
    repair_path = run / 'repair-begin.json'
    if purpose == 'postrepair' and not repair_path.exists():
        raise ValueError('postrepair purpose requires an actual repair round')
    if repair_path.exists():
        for phase in read(repair_path)['necessary_layers']:
            path = run / 'stages' / ('repair-' + phase.replace('_', '-'))
            task = helpers['lookup'](store, read(path / 'dispatch.json')['task_id'])
            if task['status'] != 'completed':
                raise ValueError('necessary repair phase not formally accepted: ' + phase)
    for ref in store.load_document()['tasks']:
        task = store.read_object_json(ref)
        if task['kind'] == 'compose' and task['status'] in ('awaiting_host', 'running'):
            raise ValueError('an actual author task is still pending; do not freeze an incomplete repair')


def prepare(args):
    from deck_master import capabilities, content_review, method_resources, service
    helpers, run, state, store, admission = admitted(args)
    current_repair_complete(helpers, run, store, args.purpose)
    target = stage_for(args, run)
    if target.exists():
        raise ValueError('verification directory already exists; never overwrite a prior attempt')
    provenance = actual_authors(helpers, run, store)
    prior = []
    for ref in store.load_document()['reviews']:
        obj = store.read_object_json(ref)
        if obj.get('review_stage') == 'preproduction':
            prior.append({'ref': ref, 'object': obj})
    prior_reviewers = sorted({p['object']['reviewer']['execution_ref'] for p in prior
                             if p['object']['reviewer'].get('execution_ref')})
    evidence_path = Path(args.scope_evidence_manifest).resolve()
    if sha(evidence_path.read_bytes()) != args.scope_evidence_sha256:
        raise ValueError('scope evidence manifest changed')
    evidence_records = read(evidence_path)
    allowed_roles = {'original_spec', 'actual_root_observation', 'independent_scope_audit',
                     'actual_user_acceptance_deferral'}
    for item in evidence_records:
        if item.get('role') not in allowed_roles or sha(Path(item['path']).read_bytes()) != item['sha256']:
            raise ValueError('scope evidence must bind actual unchanged evidence and its explicit role')
    invariant = originals(run)
    before = store.load_document()
    before_protected = protected(before)
    target.mkdir(parents=True, exist_ok=False)
    provider, registry, runtime = providers(helpers, args.bootstrap_observation)
    save(target / 'admission.json', admission)
    with runtime.bound():
        caps = capabilities.describe(registry.channel_context())
        if not caps[CHANNEL] or caps['verified_user_events'] or caps['human_review_receipts']:
            raise ValueError('only the real independent native channel may be exposed')
        prepared = content_review.dispatch_preproduction_review(
            store.project_root, adapter_context=registry.channel_context(),
            instruction='Supplemental ' + args.purpose + ': independently verify the complete current '
                        'manuscript and explicitly resolve or retain any prior finding. This is no '
                        'second Writer feedback round, no human test, and no instruction to pass.')
    if prepared['status'] != 'review_dispatched':
        raise ValueError('genuine native channel did not dispatch a review')
    if prepared['requirement'] != 'independent_model_or_human':
        raise ValueError('this supplemental verifier never downgrades the independent review policy')
    task = prepared['task']
    after = store.load_document()
    if protected(after) != before_protected:
        raise AssertionError('review dispatch changed manuscript or production')
    first_task = read(run / 'review-finish.json')['binding']['task_id']
    if task['task_id'] == first_task or task.get('execution_ref'):
        raise AssertionError('verification must receive a new unclaimed formal Task')
    document = store.load_document()
    subjects = [document['narrative'], document['content_plan'], *[e['page'] for e in document['pages']]]
    direct = content_review.author_execution_refs(store, document, subjects)
    all_authors = {r['execution_ref'] for r in provenance}
    if not direct or not direct <= all_authors:
        raise ValueError('formal current Ref authors must all have authentic native provenance')
    dependencies = [{'kind': 'content', 'identity': 'narrative', 'sha256': document['narrative']['sha256']},
                    {'kind': 'content', 'identity': 'content_plan', 'sha256': document['content_plan']['sha256']}]
    dependencies += [{'kind': 'content', 'identity': 'page:' + e['page_id'], 'sha256': e['page']['sha256']}
                     for e in document['pages']]
    dependencies += [{'kind': 'source', 'identity': s['source_id'], 'sha256': s['extract']['sha256']}
                     for s in document['sources']]
    methods = method_resources.read_task_methods(store.project_root, task['task_id'])
    save(target / 'task.json', task)
    save(target / 'work-order.json', service.task_summary(store, document, task))
    save(target / 'prepared-method-bytes.json', methods)
    save(target / 'review-packet.json', store.read_object_json(prepared['review_draft_ref']))
    save(target / 'current-manuscript.json', {'document': document,
        'narrative': store.read_object_json(document['narrative']),
        'plan': store.read_object_json(document['content_plan']),
        'pages': [{'ref': e['page'], 'object': store.read_object_json(e['page'])} for e in document['pages']]})
    save(target / 'prior-review-records.json', prior)
    save(target / 'review-binding-shape.json', {'units': prepared['units'], 'subjects': subjects,
        'dependencies': dependencies, 'packet_ref': prepared['review_draft_ref'],
        'all_actual_author_execution_refs': sorted(all_authors),
        'forbidden_prior_reviewer_execution_refs': prior_reviewers,
        'prior_by_kind': {unit: [{'ref': p['ref'], 'review_id': p['object']['review_id'],
                                'finding_ids': [f['finding_id'] for f in p['object'].get('findings', [])]}
                               for p in prior if p['object']['kind'] == unit]
                          for unit in prepared['units']},
        'replacement_rule': 'Reviewer chooses whether a genuine same logical review replacement is '
                            'warranted. Use exact prior Ref, review_id/kind/stage/shared finding_id/page; '
                            'derive observations/resolution/evidence yourself. Otherwise use a new '
                            'review_id and replaces=null. No controller-supplied closure or target pass.'})
    save(target / 'review-envelope-metadata.json', {'kind': 'review', 'files': [], 'pages': [],
        'page_order': [], 'artifact_specs': [], 'usage_events': [],
        'notes': 'actual supplemental independent content verification, not human acceptance or original frozen E1'})
    evidence_dir = target / 'scope-evidence'
    evidence_dir.mkdir()
    copied_evidence = []
    for i, item in enumerate(evidence_records):
        path = evidence_dir / (str(i).zfill(2) + '-' + Path(item['path']).name)
        raw_save(path, Path(item['path']).read_bytes())
        copied_evidence.append({**item, 'copied_path': str(path)})
    save(target / 'scope-evidence-manifest.json', copied_evidence)
    schemas = target / 'schemas'
    schemas.mkdir()
    module_root = Path(admission['installation']['module_path']).parent
    shutil.copyfile(module_root / 'resources/contracts/review.v2.schema.json', schemas / 'review.v2.schema.json')
    for name in ('shared-public-review-envelope-shape.txt', 'shared-review-severity-rubric.txt'):
        raw_save(target / name, (HERE / name).read_bytes())
    raw_save(target / 'reviewer-instructions.txt', f'''Fresh independent {args.purpose}.
Read the complete review-packet.json, current-manuscript.json, prior-review-records.json,
review-binding-shape.json, scope-evidence-manifest.json and all its full copied evidence,
schema and shared shape/severity instructions. Prior evidence is context, never a target verdict.
Use your actual fresh canonical Native identity, different from every author and prior reviewer.
Run {sys.executable} -B -I {Path(__file__).resolve()} claim-read {common_command(args)} --executor YOUR_ACTUAL_CANONICAL_TASK
Read the entire returned methods/work order. Judge each required unit honestly against actual
current sources, complete visible manuscript, notes and mappings. Separate AC-M03 estimated
feasibility from AC-U03 real timed delivery; no actual human rehearsal/Owner approval is supplied
unless the source evidence really demonstrates it. Preserve human/use tests as NOT_RUN.
Choose to retain or explicitly close prior findings yourself, with exact current evidence.
For a genuine replacement, follow actual same review_id/kind/stage/finding/page requirements;
never fabricate changed Page or accepted_variance rationale. New units may use new IDs/null replaces.
Write only your actual envelope to {target / 'model-output.json'} exclusively. No manuscript,
authority or production edits, no external calls, no feedback to Writer, no next repair.
Final message must identify actual canonical identity, raw output SHA and method-read path/SHA.
'''.encode())
    manifest = {'purpose': args.purpose, 'classification': CLASSIFICATION,
        'task_id': task['task_id'], 'project_id': state['project_id'],
        'packet_ref': prepared['review_draft_ref'], 'method_release': task['method_release'],
        'current_manuscript': before_protected, 'author_provenance': provenance,
        'prior_reviewers': prior_reviewers, 'original_evidence': invariant,
        'admission_sha256': sha((target / 'admission.json').read_bytes()),
        'bootstrap_path': str(Path(args.bootstrap_observation).resolve()),
        'bootstrap_sha256': sha(provider.bootstrap_raw), 'prepared_at': now(),
        'writer_feedback': False, 'extra_repair_round': False, 'human_acceptance': 'NOT_RUN'}
    manifest['fixed_inputs'] = {str(p.relative_to(target)): sha(p.read_bytes())
                                for p in target.rglob('*') if p.is_file()}
    save(target / 'prepare.json', manifest)
    original_check(invariant)
    print(json.dumps({'status': 'supplemental_review_prepared', 'task_id': task['task_id'],
                      'target': str(target), 'not_original_frozen_E1': True}, ensure_ascii=False))


def common_command(args):
    # Display only; paths are shell quoted so the reviewer can use the exact command.
    import shlex
    values = {'run-dir': args.run_dir, 'purpose': args.purpose,
              'installation-manifest': args.installation_manifest, 'expected-source': args.expected_source,
              'expected-wheel': args.expected_wheel, 'expected-python': args.expected_python,
              'transition-record': args.transition_record,
              'transition-sha256': args.transition_sha256}
    return ' '.join('--' + key + ' ' + shlex.quote(str(value)) for key, value in values.items())


def loaded_verification(args):
    helpers, run, state, store, admission = admitted(args)
    target = stage_for(args, run)
    prepared = read(target / 'prepare.json')
    original_check(prepared['original_evidence'])
    for name, digest in prepared['fixed_inputs'].items():
        if sha((target / name).read_bytes()) != digest:
            raise ValueError('fixed verification input changed: ' + name)
    if (protected(store.load_document()) != prepared['current_manuscript']
            or sha((target / 'admission.json').read_bytes()) != prepared['admission_sha256']
            or read(target / 'admission.json') != admission):
        raise ValueError('current manuscript or explicitly admitted verifier changed')
    return helpers, run, state, store, admission, target, prepared


def claim_read(args):
    from deck_master import method_resources, service
    helpers, _run, _, store, _, target, prepared = loaded_verification(args)
    independent(args.executor, prepared['author_provenance'], prepared['prior_reviewers'])
    if (target / 'claim.json').exists() or (target / 'method-read-record.json').exists():
        raise ValueError('verification was already claimed; never rewrite the original claim')
    task = helpers['lookup'](store, prepared['task_id'])
    if task['status'] != 'awaiting_host' or task.get('execution_ref'):
        raise ValueError('fresh verification Task must be unclaimed')
    claimed = service.task_start(store.project_root, task_id=task['task_id'], execution_ref=args.executor,
        supported_protocols=[task['protocol_version']] if task.get('protocol_version') else None,
        capabilities=task.get('required_capabilities'))
    methods = method_resources.read_task_methods(store.project_root, task['task_id'])
    if methods['status'] != 'current' or methods['current_method_release'] != prepared['method_release']:
        raise ValueError('actual verifier method basis is stale')
    save(target / 'claim.json', claimed)
    save(target / 'method-read-record.json', methods)
    original_check(prepared['original_evidence'])
    print(json.dumps(methods, ensure_ascii=False, indent=2))


def completion_status(completion, executor):
    if completion.get('observed_status') == 'completed':
        if (completion.get('status_observation_tool') != 'collaboration.list_agents'
                or executor not in completion.get('observed_completed_agents', [])):
            raise ValueError('claimed completed status lacks actual roster observation')
    else:
        raise ValueError('actual completed/list_agents observation is required; unknown is not acceptance evidence')


def native_completion(args, target, task, project_id, method_release, *, historical=False):
    result_path = Path(args.result).resolve()
    if result_path.parent != target.resolve():
        raise ValueError('actual Native output must be in this separately prepared verification directory')
    result_raw = result_path.read_bytes()
    observation_raw = Path(args.controller_observation).read_bytes()
    if sha(result_raw) != args.result_sha256 or sha(observation_raw) != args.observation_sha256:
        raise ValueError('actual result/Root observation bytes changed')
    observation = read(args.controller_observation)
    spawn, completion = observation['spawn'], observation['completion']
    executor = spawn['canonical_task_name']
    if (observation.get('observation_kind') != OBSERVER_KIND or observation.get('assurance') != 'host_attested'
            or spawn.get('tool') != 'collaboration.spawn_agent' or spawn.get('fork_turns') != 'none'
            or spawn.get('returned_task_name') != executor
            or completion.get('sender') != executor or completion.get('message_type') != 'FINAL_ANSWER'
            or args.result_sha256 not in completion.get('raw_final_message', '')
            or observation.get('project_id') != project_id or observation.get('task_id') != task['task_id']
            or observation.get('model_output_bytes_sha256') != args.result_sha256
            or observation.get('method_release') != method_release
            or task['status'] != 'running' or task.get('execution_ref') != executor):
        raise ValueError('actual Native spawn/FINAL/Task/result/method identities must agree')
    completion_status(completion, executor)
    if historical:
        value = observation['observed_at_utc']
        observed_at = (datetime.strptime(value, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
                       if value.endswith(' UTC') else datetime.fromisoformat(value.replace('Z', '+00:00')))
        if observed_at.tzinfo is None or observed_at > datetime.now(timezone.utc) + timedelta(seconds=10):
            raise ValueError('historical Native observation has an invalid/future timestamp')
    else:
        frozen_helpers()['timestamp'](observation['observed_at_utc'])
    method_path = target / 'method-read-record.json'
    method = read(method_path)
    claimed_task = method['work_order']
    if (observation.get('method_read_record', {}).get('sha256') != sha(method_path.read_bytes())
            or Path(observation['method_read_record']['path']).resolve() != method_path.resolve()
            or method.get('task_id') != task['task_id'] or method.get('project_id') != project_id
            or method.get('status') != 'current' or method.get('current_method_release') != method_release
            or claimed_task.get('execution_ref') != executor
            or claimed_task.get('execution_started_at') != task.get('execution_started_at')):
        raise ValueError('actual original Native claim/read record does not match')
    return read(result_path), result_raw, observation, observation_raw, executor


def accept(args):
    from deck_master import capabilities, content_review, review_evidence, service
    helpers, run, state, store, _, target, prepared = loaded_verification(args)
    if (target / 'finish.json').exists():
        raise ValueError('verification already finished; never overwrite')
    task = helpers['lookup'](store, prepared['task_id'])
    envelope, raw, _observation, raw_observation, executor = native_completion(
        args, target, task, state['project_id'], prepared['method_release'])
    independent(executor, prepared['author_provenance'], prepared['prior_reviewers'])
    if (set(envelope) != {'kind', 'files', 'pages', 'page_order', 'artifact_specs', 'reviews', 'usage_events', 'notes'}
            or envelope.get('kind') != 'review'
            or any(envelope.get(key) for key in ('files', 'pages', 'page_order', 'artifact_specs', 'usage_events'))):
        raise ValueError('verification only writes actual Review records, with zero external calls')
    for review in envelope.get('reviews', []):
        r = review.get('reviewer') or {}
        if (r.get('type') != 'independent_host' or r.get('execution_ref') != executor
                or r.get('independence_confirmed') is not True or r.get('assurance') != 'host_attested'):
            raise ValueError('every actual unit must use the true independent Native reviewer')
    provenance = actual_authors(helpers, run, store)
    if provenance != prepared['author_provenance']:
        raise ValueError('actual author provenance changed after fixed packet')
    binding = review_evidence.review_binding(store, store.load_document(), task, envelope)
    if not set(binding['author_execution_refs']) <= {p['execution_ref'] for p in provenance}:
        raise ValueError('formal authors lack actual native provenance')
    issued = datetime.now(timezone.utc)
    claims = {**binding, 'provider_id': PROVIDER_ID,
        'event_id': 'supplemental-' + sha(raw_observation)[:32], 'channel': CHANNEL,
        'issued_at': issued.isoformat(), 'expires_at': (issued + timedelta(minutes=30)).isoformat(),
        'executor_ref': executor, 'reviewer_id': executor, 'assurance': 'host_attested',
        'all_native_writer_execution_refs': sorted({p['execution_ref'] for p in provenance}),
        'observation_kind': OBSERVER_KIND, 'model_output_bytes_sha256': args.result_sha256,
        'controller_observation_sha256': args.observation_sha256,
        'evidence_scope': CLASSIFICATION, 'writer_feedback': False, 'human_acceptance': False}
    _, registry, runtime = providers(helpers, args.bootstrap_observation,
                                   observation=raw_observation, claims=claims)
    before = store.load_document()
    before_protected = protected(before)
    raw_save(target / 'observed-raw-model-output.json', raw)
    raw_save(target / 'observed-root-completion.json', raw_observation)
    negatives = {}
    for author in sorted({p['execution_ref'] for p in provenance}):
        try:
            independent(author, provenance, prepared['prior_reviewers'])
        except ValueError as exc:
            negatives.setdefault('every_actual_author', {})[author] = {'refused': True, 'reason': str(exc)}
        else:
            raise AssertionError('an actual author passed the independent controller guard')
    with runtime.bound():
        caps = capabilities.describe(registry.channel_context())
        if not caps[CHANNEL] or caps['verified_user_events'] or caps['human_review_receipts']:
            raise ValueError('supplemental adapter exposes independent Native receipts only')
        revision = store.current_revision_id()
        try:
            service.accept_result(store.project_root, task_id=task['task_id'], operation_id=task['operation_id'],
                produced_against=task['produced_against'], result_payload=envelope,
                adapter_context={CHANNEL: [{'verified': True}]})
        except review_evidence.EvidenceRejected as exc:
            negatives['ordinary_json_context'] = {'refused': True, 'reason': str(exc)}
        else:
            raise AssertionError('ordinary JSON context was trusted')
        if store.current_revision_id() != revision:
            raise AssertionError('negative-control refusal changed current Store')
        selector = {'provider_id': PROVIDER_ID, 'event_id': claims['event_id']}
        changed = copy.deepcopy(envelope)
        changed['notes'] += ' [negative replay control]'
        foreign_task = {**task, 'task_id': task['task_id'] + '-foreign'}
        for name, test_task, test_result in [('changed_result_replay', task, changed),
                                              ('foreign_task_replay', foreign_task, envelope)]:
            try:
                registry.review_context(store, store.load_document(), test_task, test_result, selector)
            except review_evidence.EvidenceRejected as exc:
                negatives[name] = {'refused': True, 'reason': str(exc)}
            else:
                raise AssertionError('modified result/task reused the true native receipt')
        context = registry.review_context(store, store.load_document(), task, envelope, selector)
        try:
            outcome = service.accept_result(store.project_root, task_id=task['task_id'],
                operation_id=task['operation_id'], produced_against=task['produced_against'],
                result_payload=envelope, adapter_context=context)
        except Exception as exc:
            save(target / 'acceptance-refused.json', {'error_type': type(exc).__name__, 'error': str(exc),
                'result_sha256': args.result_sha256, 'observation_sha256': args.observation_sha256,
                'negative_controls': negatives, 'not_original_frozen_E1': True, 'observed_at': now()})
            raise
    after = store.load_document()
    if protected(after) != before_protected:
        raise AssertionError('independent verification changed manuscript or production')
    results = [store.read_object_json(r) for r in helpers['lookup'](store, task['task_id'])['result_refs']]
    proofs = [p for p in results if p.get('schema_version') == 'authenticated_review_receipt.v1']
    if len(proofs) != 1 or store.read_object_bytes(proofs[0]['raw_event_ref']) != raw_observation:
        raise AssertionError('actual original Native event was not persisted')
    original_check(prepared['original_evidence'])
    finish = {'purpose': args.purpose, 'classification': CLASSIFICATION, 'not_original_frozen_E1': True,
        'actual_native_reviewer': executor, 'raw_output_sha256': args.result_sha256,
        'root_observation_sha256': args.observation_sha256, 'binding': binding, 'proof': proofs[0],
        'negative_controls': negatives, 'acceptance': outcome, 'capabilities': caps,
        'preproduction_status': content_review.preproduction_status(store, after),
        'writer_feedback': False, 'extra_repair_round': False, 'human_acceptance': 'NOT_RUN',
        'professional_predicate': 'not asserted', 'finished_at': now()}
    save(target / 'finish.json', finish)
    print(json.dumps({'status': outcome['status'], 'current_gate': finish['preproduction_status'],
                      'target': str(target), 'not_original_frozen_E1': True}, ensure_ascii=False))


def accept_existing_speech(args):
    """Same original result/Task consumed by a genuinely new admitted SDK."""
    from deck_master import method_resources, service
    helpers, run, state, store, admission = admitted(args)
    original = run / 'stages' / args.original_stage
    if args.original_stage not in ('04-speech', 'repair-speech'):
        raise ValueError('supplemental existing-result consumption only admits actual speech')
    if (original / 'accepted.json').exists():
        raise ValueError('original installed SDK already accepted this stage')
    if not (original / 'acceptance-refused.json').exists():
        raise ValueError('retain the original installed SDK refusal before supplemental consumption')
    dispatch = read(original / 'dispatch.json')
    task = helpers['lookup'](store, dispatch['task_id'])
    if task['kind'] != 'compose' or (task.get('collaboration_binding') or {}).get('phase') != 'speech':
        raise ValueError('original formal task is not speech')
    envelope, raw, _observation, raw_observation, executor = native_completion(
        args, original, task, state['project_id'], dispatch['method_release'], historical=True)
    refusal = read(original / 'acceptance-refused.json')
    if (refusal.get('raw_output_sha256') != args.result_sha256
            or refusal.get('actual_native_writer') != executor
            or refusal.get('semantic_fallback') is not False):
        raise ValueError('retained original SDK refusal must bind this exact real author/output')
    if envelope.get('usage_events') or envelope.get('variant') != 'speech':
        raise ValueError('same original speech output only; zero external calls')
    methods = method_resources.read_task_methods(store.project_root, task['task_id'])
    original_method = read(original / 'method-read-record.json')
    if (methods['status'] != 'current' or methods['methods'] != original_method['methods']):
        # Paths and release IDs legitimately differ, but full text/hash/id must not.
        old_bytes = [(m['id'], m['relative_path'], m['sha256'], m['content']) for m in original_method['methods']]
        new_bytes = [(m['id'], m['relative_path'], m['sha256'], m['content']) for m in methods['methods']]
        if methods['status'] != 'current' or old_bytes != new_bytes:
            raise ValueError('new SDK method basis differs; do not rebind old task or author')
    target = run / 'verification' / 'post-failure-consumption' / args.original_stage
    target.mkdir(parents=True, exist_ok=False)
    invariant = originals(run)
    raw_save(target / 'observed-raw-model-output.json', raw)
    raw_save(target / 'observed-root-completion.json', raw_observation)
    save(target / 'admission.json', admission)
    save(target / 'current-method-read.json', methods)
    before = store.load_document()
    try:
        outcome = service.accept_result(store.project_root, task_id=task['task_id'],
            operation_id=task['operation_id'], produced_against=task['produced_against'], result_payload=envelope)
    except Exception as exc:
        save(target / 'acceptance-refused.json', {'error_type': type(exc).__name__, 'error': str(exc),
            'raw_output_sha256': args.result_sha256, 'classification': CLASSIFICATION,
            'original_refusal_preserved': True, 'observed_at': now()})
        raise
    after = store.load_document()
    if ([e['page_id'] for e in before['pages']] != [e['page_id'] for e in after['pages']]
            or {e['page_id']: store.read_object_json(e['page'])['customer_visible'] for e in before['pages']}
            != {e['page_id']: store.read_object_json(e['page'])['customer_visible'] for e in after['pages']}
            or any(before.get(k) != after.get(k) for k in ('narrative', 'design_context', 'files'))):
        raise AssertionError('supplemental speech changed protected visible semantics')
    save(target / 'accepted.json', {'result': outcome, 'actual_native_writer': executor,
        'raw_output_sha256': args.result_sha256, 'root_observation_sha256': args.observation_sha256,
        'original_stage_path': str(original), 'original_refusal_preserved': True,
        'classification': CLASSIFICATION, 'not_original_frozen_E1': True,
        'new_native_output': False, 'new_claim': False,
        'dispatch_method_release': task['method_release'],
        'current_method_release': methods['current_method_release'],
        'method_basis_status': methods['status'],
        'historical_immutable_native_completion_reused_for_exact_result': True,
        'accepted_at': now()})
    original_check(invariant)
    print(json.dumps({'status': outcome['status'], 'target': str(target),
                      'not_original_frozen_E1': True}, ensure_ascii=False))


def freeze_owner(args):
    from deck_master import content_review, review
    from deck_master.editing import _current_artifact_digests
    _helpers, run, _, store, _, target, prepared = loaded_verification(args)
    finish = read(target / 'finish.json')
    envelope = read(target / 'observed-raw-model-output.json')
    required = set(read(target / 'review-binding-shape.json')['units'])
    records = envelope['reviews']
    if ({r['kind'] for r in records} != required or any(r['status'] != 'pass' for r in records)
            or any(review.open_findings(r) or review.pending_judgments(r) for r in records)):
        raise ValueError('actual current verification is not all-units pass without unresolved blockers')
    document = store.load_document()
    gate = content_review.preproduction_status(store, document)
    if finish['acceptance']['status'] != 'accepted' or gate['status'] != 'pass':
        raise ValueError('actual SDK current preproduction gate is not pass; do not bypass old findings')
    # A stale old owner must not disappear from the delivery account merely
    # because a changed manuscript made its review inapplicable. Require the
    # SDK's genuine explicit replacement closure for every old open blocker.
    prior_records = read(target / 'prior-review-records.json')
    all_reviews = [{**store.read_object_json(ref), 'ref': ref} for ref in document['reviews']]
    relevant_subjects = [ref for item in all_reviews for ref in item.get('subjects', [])]
    context = _current_artifact_digests(store, document, relevant_subjects)
    closure_checks = []
    for prior in prior_records:
        owner = {**prior['object'], 'ref': prior['ref']}
        for finding in review.open_findings(owner) + review.pending_judgments(owner):
            if not review.finding_closed(all_reviews, owner, finding, context):
                raise ValueError('prior blocker lacks genuine explicit current replacement closure: '
                                 + owner['review_id'] + '/' + finding['finding_id'])
            closure_checks.append({'prior_review_ref': prior['ref'], 'review_id': owner['review_id'],
                                   'finding_id': finding['finding_id'], 'page_id': finding.get('page_id'),
                                   'closed_by_actual_sdk_central_semantics': True})
    deferred = [{'review_id': r['review_id'], 'kind': r['kind'], 'finding': f,
                 'disposition': 'not executed; retained as a nonblocking suggestion'}
                for r in records for f in r.get('findings', [])
                if f.get('impact') == 'advisory' and f.get('resolution') == 'open']
    repaired = (run / 'repair-begin.json').exists()
    prior_advisories = [{'review_ref': p['ref'], 'review_id': p['object']['review_id'],
                         'kind': p['object']['kind'], 'finding': f,
                         'disposition': ('historical suggestion retained; execution not inferred'
                                         if repaired else
                                         'not executed; this verification preserves the original content refs')}
                        for p in prior_records
                        for f in p['object'].get('findings', [])
                        if f.get('impact') == 'advisory' and f.get('resolution') == 'open']
    save(target / 'owner-draft.json', {'document': document,
        'narrative': store.read_object_json(document['narrative']),
        'plan': store.read_object_json(document['content_plan']),
        'pages': [{'ref': e['page'], 'object': store.read_object_json(e['page'])} for e in document['pages']],
        'classification': CLASSIFICATION, 'actual_current_content_gate': gate,
        'original_initial_draft': str(run / 'raw-first-complete-draft.json'),
        'original_initial_review': str(run / 'review-finish.json'),
        'actual_repair_round': repaired, 'extra_repair_round': False,
        'nonblocking_suggestions_not_executed': deferred,
        'original_nonblocking_suggestions': prior_advisories,
        'prior_blocker_closure_checks': closure_checks,
        'human_owner_acceptance': 'NOT_RUN; user explicitly deferred',
        'real_rehearsal_and_desktop_use': 'NOT_RUN unless separately evidenced; this snapshot creates no such proof',
        'not_original_frozen_E1': True, 'frozen_at': now()})
    original_check(prepared['original_evidence'])
    print(json.dumps({'status': 'actual_current_draft_frozen_for_owner',
                      'path': str(target / 'owner-draft.json'), 'human_acceptance': 'NOT_RUN'}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name, func in [('prepare', prepare), ('claim-read', claim_read), ('accept', accept),
                       ('accept-existing-speech', accept_existing_speech), ('freeze-owner', freeze_owner)]:
        command = commands.add_parser(name)
        command.set_defaults(func=func)
        for flag in ('run-dir', 'installation-manifest', 'expected-source', 'expected-wheel', 'expected-python',
                     'transition-record', 'transition-sha256'):
            command.add_argument('--' + flag, required=True)
        if name != 'accept-existing-speech':
            command.add_argument('--purpose', choices=PURPOSES, required=True)
        if name == 'prepare':
            command.add_argument('--bootstrap-observation', required=True)
            command.add_argument('--scope-evidence-manifest', required=True)
            command.add_argument('--scope-evidence-sha256', required=True)
        if name == 'claim-read':
            command.add_argument('--executor', required=True)
        if name in ('accept', 'accept-existing-speech'):
            for flag in ('result', 'result-sha256', 'controller-observation', 'observation-sha256'):
                command.add_argument('--' + flag, required=True)
        if name == 'accept':
            command.add_argument('--bootstrap-observation', required=True)
        if name == 'accept-existing-speech':
            command.add_argument('--original-stage', choices=('04-speech', 'repair-speech'), required=True)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
