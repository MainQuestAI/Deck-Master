"""Synthetic neutral observations, real public SDK and original protected bridge.

No actual native/model/formal call. Ordinary CI invokes this explicit carrier
in a real -I -B child; installation/guard/provider are not patched.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

TOOL = Path(__file__).resolve().parents[2]/'tools/rc3_campaign/q2_later_300.py'
spec = importlib.util.spec_from_file_location('s09_cases', TOOL)
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def installation(base, c):
    import deck_master
    from deck_master import capabilities
    module = Path(deck_master.__file__).resolve(); identity = capabilities.installation_identity(); observed = identity.get('install') or {}
    manifest = c.save(base/'engineering-installation.json', {'status': p.ENGINEERING, 'module_path': str(module),
        **{k: observed.get(k) for k in ('source_sha', 'source_tree', 'wheel_sha256')}, 'actual_identity': identity})
    return {'python': sys.executable, 'module_file': str(module), 'manifest': manifest,
        **{k: observed.get(k) for k in ('source_sha', 'source_tree', 'wheel_sha256')},
        'package_files': [{'relative_path': str(f.relative_to(module.parent)), 'sha256': c.digest(f.read_bytes())}
            for f in sorted(module.parent.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc']}


def page(pid):
    return {'schema_version': 'deck_page_package.v2', 'page_id': pid,
        'customer_visible': {'title': 'Neutral '+pid, 'body_blocks': [{'id': 'b1', 'type': 'paragraph', 'text': 'Keep unknown explicit and the boundary read-only.'}]},
        'speaker_notes': 'Neutral complete cue for '+pid,
        'visual_spec': {'intent': 'Neutral original layout', 'reference_mode': 'new_design'}}


def scope(ids, layers=None):
    return {'subject': 'deck', 'page_ids': ids, 'page_manifest_ref': None, 'external_artifact_ref': None,
        'layers': layers or ['narrative', 'plan', 'page_copy', 'speech', 'review'],
        'allow_page_membership_change': True, 'allow_page_order_change': True, 'purpose': 'working'}


def fixture(base, tool=p, flow='r04'):
    from deck_master import collaboration, content_production, service
    base = Path(base).resolve(); base.mkdir(parents=True, exist_ok=True); s, c = tool.helpers()
    c.save(base/'identity.json', {'isolated': sys.flags.isolated, 'dont_write_bytecode': sys.dont_write_bytecode,
                                'python': sys.executable, 'SYNTHETIC_NOT_FORMAL': True})
    grammar = c.save(base/'grammar.json', {'SYNTHETIC_PUBLIC_TECHNICAL_ONLY': True})
    source = c.write_once(base/'source.txt', b'SYNTHETIC neutral facts: preserve key evidence; read-only; max eight pages.\n')
    message = c.write_once(base/'message.txt', tool.MESSAGE.encode())
    policy = c.save(base/'policy.json', {'status': 'FROZEN', 'excluded_identities': ['/root/engineering_preparer'],
        'opaque_private_index_ref': {'path': str(base/'private/never-open-index.json'), 'bytes': 1, 'sha256': '0'*64}})
    arm, repetition, _ = tool.RUNS[flow]; project = base/'project'; origin = base/'origin'; origin.mkdir()
    reg = {'status': tool.ENGINEERING, 'format': c.VERSION, 'controller_sha256': tool.COMMON_SHA,
        'installations': {arm: installation(base, c)}, 'grammar': grammar, 'protocol': grammar, 'exposure_registry': policy,
        'budget': {'initial_writer': 5, 'feedback': 1, 'repair_writer': 3, 'repair_cycles': 1},
        'cases': {'Q2': {'materials': [source], 'events': {tool.EVENT: {'message': message, 'planned_dispatch': True,
             'required_snapshots': ['original_complete', 'equal_budget_evaluated'], 'source': 'SYNTHETIC_NONHUMAN'}}}}}
    campaign = base/'original-campaign'; campaign.mkdir(); rr = c.save(campaign/'registration.json', reg)
    state = {'format': c.VERSION, 'campaign': str(campaign), 'registration_sha256': rr['sha256'], 'arm': arm,
        'case': 'Q2', 'repetition': repetition, 'project': str(project), 'budget': reg['budget'], 'materials': [source],
        'checkpoint': None, 'human': 'NOT_RUN_USER_DEFERRED'}
    run = c.save(origin/'run.json', state); journal = c.Journal(origin); journal.append('workflow_initialized', state)
    created = c.record_sdk(journal, 'service.create.fixture', {}, lambda: service.create(project,
        brief='Neutral 10 分钟; preserve key evidence, read-only boundary, max8.', sources=[source['path']],
        draft={'pages': [page('p1'), page('p2')]}, request_input={'intent': 'full_deck', 'content_intent': None,
        'scope': scope(['p1', 'p2']), 'instruction_evidence': {'kind': 'host_attested_instruction', 'text': 'SYNTHETIC initial neutral import only'}}))
    store = c.store_for(state); doc = store.load_document()
    old_task = c.record_sdk(journal, 'content_production.open_phase_task.fixture', {}, lambda: content_production.open_phase_task(
        store, doc, operation_id='fixture-old-input', intent='input_revision', page_ids=['p1', 'p2'], adoption_policy='within_scope'))
    old_executor = '/root/engineering_old_writer'
    c.record_sdk(journal, 'service.task_start.fixture', {'task_id': old_task['task_id']}, lambda: service.task_start(project,
        task_id=old_task['task_id'], execution_ref=old_executor, supported_protocols=[old_task['protocol_version']], capabilities=old_task['required_capabilities']))
    doc = store.load_document(); proposals = []
    for entry in doc['pages']:
        obj = store.read_object_json(entry['page']); obj['customer_visible']['title'] += ' owned'
        ref = c.record_sdk(journal, 'Store.put_json_object.fixture', {'page_id': entry['page_id']}, lambda obj=obj: store.put_json_object(obj))
        proposals.append({'layer': 'page_copy', 'ref': ref})
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'input_revision',
        'task_id': old_task['task_id'], 'operation_id': old_task['operation_id'], 'produced_against': old_task['produced_against'],
        'eligibility_digest': old_task['collaboration_binding']['eligibility_digest'], 'usage_events': [],
        'payload': {'changed_layers': ['page_copy'], 'proposals': proposals,
            'diff': {'input_digest': old_task['input_digest'], 'summary': 'SYNTHETIC old author metadata', 'changed_page_ids': ['p1', 'p2']}}}
    c.record_sdk(journal, 'service.accept_result.fixture', {'task_id': old_task['task_id']}, lambda: service.accept_result(project,
        task_id=old_task['task_id'], operation_id=old_task['operation_id'], produced_against=old_task['produced_against'], result_payload=envelope))
    doc = store.load_document()
    instruction = c.record_sdk(journal, 'Store.put_blob.fixture', {'text': 'SYNTHETIC prior review request', 'ext': 'txt'},
                               lambda: store.put_blob(b'SYNTHETIC prior review request', ext='txt'))
    c.record_sdk(journal, 'collaboration.start_request.fixture', {}, lambda: collaboration.start_request(project,
        input={'intent': 'review_only', 'content_intent': None, 'replace_request_id': doc['collaboration']['request']['request_id'],
            'scope': scope(['p1', 'p2'], ['review']), 'instruction_evidence': {'kind': 'host_attested_instruction', 'source_ref': instruction,
                'source_locator': 'SYNTHETIC_OLD_REVIEW', 'actor_id': None, 'transport_receipt_ref': None, 'presentation_ref': None}},
        base_revision=doc['revision_id'], operation_id=str(c.uuid.uuid4())))
    old_stage = origin/'stages/old'; old_stage.mkdir(parents=True)
    c.save(old_stage/'dispatch.json', {'task_id': old_task['task_id'], 'project_id': doc['project_id'], 'role': 'initial_writer'})
    obs = c.save(base/'old-invocation.json', {'SYNTHETIC_NOT_ACTUAL_NATIVE': True, 'observation_kind': c.OBSERVER_KIND,
        'assurance': 'host_attested', 'project_id': doc['project_id'], 'task_id': old_task['task_id'], 'spawn': {
            'canonical_task_name': old_executor, 'returned_task_name': old_executor, 'tool': 'collaboration.spawn_agent', 'fork_turns': 'none', 'inherited_identities': []}})
    journal.append('native_begun', {'stage': 'old', 'ordinal': 1, 'role': 'initial_writer', 'executor': old_executor,
        'observation': obs, 'within_budget': True})
    six = {}
    for name in tool.CUTS:
        kinds = ['original_complete', 'equal_budget_evaluated']+([] if name == 'cq2' else ['first_sdk_complete'])
        six[name] = {k: c.save(base/'six-cuts'/name/(k+'.json'), {'SYNTHETIC_FROZEN_CUT_ONLY': True, 'name': name, 'timepoint': k, 'quality': 'not_asserted'}) for k in kinds}
    for k in ('original_complete', 'first_sdk_complete', 'equal_budget_evaluated'):
        c.write_once(origin/'snapshots'/(k+'.json'), Path(six[flow][k]['path']).read_bytes())
        six[flow][k] = c.reference(origin/'snapshots'/(k+'.json'))
    doc = store.load_document(); row = {'run': run, 'frontier': tool.tip(c, journal), 'project_id': doc['project_id'],
        'revision_id': doc['revision_id'], 'request': doc['collaboration']['request']}
    control = c.save(base/'control.json', {'format': tool.FORMAT, 'status': tool.ENGINEERING, 'observer_id': '/engineering/rc3-s09',
        'assurance': 'synthetic_engineering', 'observed_at_utc': c.now(), 'implementation_review': grammar,
        'scope': {'tool': tool.reference(Path(tool.__file__).resolve()), 'common': tool.reference(Path(tool.__file__).with_name('controller.py')),
            'scoped': tool.reference(Path(tool.__file__).with_name('supplementary_recorder.py')), 'ledger_root': str(base/'later-ledger'),
            'origins': {name: deepcopy(row) for name in tool.RUNS}, 'six_cuts': six, 'protocol': grammar, 'resource_selection': grammar}})
    bootstrap = c.save(base/'bootstrap.json', {'SYNTHETIC_NOT_ACTUAL_CHANNEL': True, 'observation_kind': c.OBSERVER_KIND,
        'assurance': 'host_attested', 'observed_at_utc': c.now(), 'tool': 'collaboration.list_agents', 'observed_running_agents': ['/root']})
    return {'base': base, 'tool': tool, 's': s, 'c': c, 'control': control, 'flow': flow, 'origin': journal,
        'old_state': state, 'reg': reg, 'created': created, 'bootstrap': bootstrap, 'old_executor': old_executor}


def step(f, action, **payload):
    return f['tool'].advance(action, f['control']['path'], f['control']['sha256'], f['flow'], payload, True)


def initialize(f):
    f['state'] = f['tool'].initialize(f['control']['path'], f['control']['sha256'], f['flow'], True)
    return f


def released(f):
    initialize(f); c = f['c']; control = c.read(f['control']['path'])
    trigger = c.save(f['base']/'trigger.json', {'SYNTHETIC_NOT_ACTUAL_ROOT_TRIGGER': True, 'event_id': p.EVENT,
        'assurance': 'host_attested', 'actual_trigger_satisfied': True, 'actual_trigger_explanation': 'SYNTHETIC six frozen outcomes including missing are retained',
        'source_observations': [control['scope']['six_cuts']['r04']['equal_budget_evaluated']], 'six_cut_binding': control['scope']['six_cuts']})
    step(f, 'release', trigger=trigger['path']); f['instruction'] = step(f, 'materialize')
    return f


def inputs(f):
    released(f); f['new_request'] = step(f, 'request'); f['update'] = step(f, 'inputs')
    store = f['c'].store_for(f['state']); doc = store.load_document()
    f['task'] = next(store.read_object_json(ref) for ref in doc['tasks']
        if store.read_object_json(ref)['status'] == 'awaiting_host' and store.read_object_json(ref).get('intent') == 'input_revision')
    return f


def invocation(f, stage, executor='/root/engineering_later_writer', tool='collaboration.spawn_agent', **over):
    c = f['c']; d = c.read(Path(f['state']['root'])/'stages'/stage/'dispatch.json')
    return c.save(f['base']/(stage+'-invocation.json'), {'SYNTHETIC_NOT_ACTUAL_NATIVE': True, 'observation_kind': c.OBSERVER_KIND,
        'assurance': 'host_attested', 'observed_at_utc': c.now(), 'project_id': d['project_id'], 'task_id': d['task_id'],
        'spawn': {'tool': tool, 'canonical_task_name': executor, 'returned_task_name': executor, 'fork_turns': 'none',
            'inherited_identities': [], **over}})


def launch(f, stage='initial', executor='/root/engineering_later_writer', tool='collaboration.spawn_agent', **over):
    f['dispatch'] = step(f, 'prepare', stage=stage, task_id=f['task']['task_id'], role='initial_writer')
    obs = invocation(f, stage, executor, tool, **over)
    f['invocation'] = step(f, 'begin', stage=stage, observation=obs['path']); f['stage'] = stage
    f['methods'] = step(f, 'claim', stage=stage, ordinal=f['invocation']['ordinal'])
    return f


def freeze_result(f, envelope, stage=None, invocation_record=None, native_objects=()):
    c = f['c']; stage = stage or f['stage']; inv = invocation_record or f['invocation']
    dispatch = c.read(Path(f['state']['root'])/'stages'/stage/'dispatch.json')
    _, target = c.execution(c.Journal(f['state']['root']), stage, inv['ordinal'])
    raw = c.save(f['base']/(stage+'-native-original.json'), envelope)
    observation = c.save(f['base']/(stage+'-completion.json'), {'SYNTHETIC_NOT_ACTUAL_NATIVE_FINAL': True,
        'observation_kind': c.OBSERVER_KIND, 'assurance': 'host_attested', 'observed_at_utc': c.now(),
        'task_id': dispatch['task_id'], 'project_id': dispatch['project_id'], 'method_release': dispatch['method_release'],
        'model_output_bytes_sha256': raw['sha256'], 'all_method_bytes_read': True,
        'method_read_record_sha256': c.reference(target/'method-read-record.json')['sha256'],
        'native_object_files': list(native_objects), 'completion': {'sender': inv['executor'], 'message_type': 'FINAL_ANSWER',
            'status_observation_tool': 'collaboration.list_agents', 'observed_status': 'completed',
            'observed_completed_agents': [inv['executor']], 'raw_final_message': Path(raw['path']).read_text()}})
    step(f, 'observe', stage=stage, ordinal=inv['ordinal'], result=raw['path'], result_sha256=raw['sha256'],
         observation=observation['path'], observation_sha256=observation['sha256'])
    return raw, observation


def finish_initial(f):
    from deck_master.models import canonical_json_bytes
    c = f['c']; store = c.store_for(f['state']); doc = store.load_document(); task = f['task']
    obj = store.read_object_json(doc['pages'][0]['page']); obj['customer_visible']['title'] += ' 300s'
    digest = c.digest(canonical_json_bytes(obj)); ref = {'path': '.deckmaster/objects/'+digest[:2]+'/'+digest+'.json', 'sha256': digest}
    sidecar = c.save(Path(f['dispatch']['packet'])/'neutral-native-page.json', obj)
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'input_revision',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'], 'usage_events': [],
        'payload': {'changed_layers': ['page_copy'], 'proposals': [{'layer': 'page_copy', 'ref': ref}],
            'diff': {'input_digest': task['input_digest'], 'summary': 'SYNTHETIC new300s Page; p2/notes/evidence retained', 'changed_page_ids': ['p1']}}}
    raw, obs = freeze_result(f, envelope, native_objects=[{**sidecar, 'declared_ref': ref}])
    step(f, 'objects', stage=f['stage'], ordinal=f['invocation']['ordinal'])
    f['accepted'] = step(f, 'accept', stage=f['stage'], ordinal=f['invocation']['ordinal'])
    manifest = c.save(f['base']/'native-complete-manifest.json', {'format': 'rc3-native-complete-draft-manifest.v1',
        'SYNTHETIC_NOT_MODEL_COMPLETENESS': True, 'complete_native_manuscript_observed': True, 'assurance': 'host_attested',
        'raw_stage_ordinals': [f['invocation']['ordinal']], 'completeness_source_observation': obs, 'readonly_conversion': None})
    step(f, 'snapshot', name='original_complete', native_manifest=manifest['path'])
    step(f, 'snapshot', name='first_sdk_complete', native_manifest=None)
    return f


def review(f, role='feedback', fail=False, stage=None, executor='/root/engineering_reviewer'):
    c = f['c']; stage = stage or role
    step(f, 'review-request', role=role)
    dispatch = step(f, 'review-prepare', stage=stage, role=role, bootstrap=f['bootstrap']['path'])
    obs = invocation(f, stage, executor)
    inv = step(f, 'begin', stage=stage, observation=obs['path'])
    step(f, 'claim', stage=stage, ordinal=inv['ordinal'])
    store = c.store_for(f['state']); doc = store.load_document()
    subjects = [doc[k] for k in ('narrative', 'content_plan') if doc.get(k)]+[e['page'] for e in doc['pages']]
    deps = [{'kind': 'content', 'identity': k, 'sha256': doc[k]['sha256']} for k in ('narrative', 'content_plan') if doc.get(k)]
    deps += [{'kind': 'content', 'identity': 'page:'+e['page_id'], 'sha256': e['page']['sha256']} for e in doc['pages']]
    deps += [{'kind': 'source', 'identity': s['source_id'], 'sha256': s['extract']['sha256']} for s in doc['sources']]
    records = []
    for kind in ('page_copy', 'progression'):
        finding = [{'finding_id': 'neutral-f1', 'kind': 'content', 'impact': 'must_fix', 'resolution': 'open',
            'page_id': 'p1', 'element_refs': ['atom:p1:title'], 'message': 'SYNTHETIC neutral missing qualification',
            'expected': 'Neutral complete qualification', 'actual': 'SYNTHETIC shorter label', 'evidence': []}] if fail and kind == 'page_copy' else []
        records.append({'schema_version': 'deck_review.v2', 'review_id': stage+'-'+kind, 'kind': kind,
            'review_stage': 'preproduction', 'status': 'pass', 'subjects': deepcopy(subjects), 'dependencies': deepcopy(deps),
            'findings': finding, 'observations': ['SYNTHETIC full own manuscript and original source read; no professional judgment'],
            'created_at': c.now(), 'replaces': None, 'reviewer': {'type': 'independent_host', 'id': executor,
            'execution_ref': executor, 'independence_confirmed': True, 'identity_receipt': None, 'assurance': 'host_attested', 'evidence_ref': None}})
    envelope = {'kind': 'review', 'pages': [], 'page_order': [], 'artifact_specs': [], 'usage_events': [],
                'notes': 'SYNTHETIC only, no formal/model/human evidence', 'reviews': records}
    freeze_result(f, envelope, stage, inv)
    return {'stage': stage, 'ordinal': inv['ordinal'], 'dispatch': dispatch, 'invocation': inv, 'envelope': envelope}


def test_real_B_request_inputs_full_own_claim_and_single_physical_materialization(tmp_path):
    f = launch(inputs(fixture(tmp_path))); c = f['c']; state = f['state']; j = c.Journal(state['root'])
    doc = c.store_for(state).load_document(); control = c.read(f['control']['path'])
    assert doc['task']['brief'].count('5 分钟') == 1 and '10 分钟' not in doc['task']['brief']
    assert doc['collaboration']['request']['request_id'] != control['scope']['origins']['r04']['request']['request_id']
    assert doc['collaboration']['request']['instruction_evidence']['source_ref'] == f['instruction']['source_ref']
    assert f['task']['protocol_version'] == 'compose.v2' and f['task']['intent'] == 'input_revision'
    assert f['methods']['methods'] and all(m['content'] for m in f['methods']['methods'])
    assert c.read(Path(f['dispatch']['packet'])/'writer-boundary.json')['packet_contract'] == 'original-main-full-own-Q2'
    materialize = [e for e in f['origin'].events() if e['kind'] == 'sdk_intent' and e['data']['operation'] == 'Store.put_blob.exact_scripted_instruction']
    charges = f['s'].Resources(state).journal.events()
    assert len(materialize) == 1
    identity = {'project': state['project'], 'journal': str(f['origin'].root), 'operation_key': materialize[0]['data']['operation_key']}
    assert sum(e['kind'] == 'resource_charge' and e['data']['identity'] == identity for e in charges) == 1
    assert sum(e['kind'] == 'native_begun' for e in j.events()) == 1  # No copied old execution/cost.
    assert step(f, 'status')['resources'][0] == {'writer': 1, 'review': 0, 'sdk': 8, 'render': 0}


@pytest.mark.parametrize('action', ['release', 'request', 'inputs'])
def test_replays_refused_without_new_physical_sdk_or_cost(tmp_path, action):
    f = inputs(fixture(tmp_path)); before = step(f, 'status')['resources']; old_tip = f['tool'].tip(f['c'], f['origin'])
    args = {'trigger': str(f['base']/'trigger.json')} if action == 'release' else {}
    with pytest.raises((ValueError, FileExistsError)):
        step(f, action, **args)
    assert step(f, 'status')['resources'] == before and f['tool'].tip(f['c'], f['origin']) == old_tip


def test_confirmed_materialization_reuses_exact_ref_without_another_physical_call(tmp_path):
    f = released(fixture(tmp_path)); before = step(f, 'status'); frontier = f['tool'].tip(f['c'], f['origin'])
    assert step(f, 'materialize') == f['instruction']
    assert step(f, 'status')['resources'] == before['resources'] and f['tool'].tip(f['c'], f['origin']) == frontier


def test_actual_same_project_old_writer_followup_is_honest_and_costs_one_later_turn(tmp_path):
    f = inputs(fixture(tmp_path)); launch(f, executor=f['old_executor'], tool='collaboration.followup_task', origin_run=str(f['origin'].root))
    assert f['invocation']['origin_lineage'] and f['invocation']['actual_invocation_tool'] == 'collaboration.followup_task'
    assert step(f, 'status')['resources'][0]['writer'] == 1


@pytest.mark.parametrize('fault', ['old-fake-fresh', 'unknown-followup', 'wrong-origin-followup', 'preparer'])
def test_native_lineage_refusals_before_claim_or_extra_cost(tmp_path, fault):
    f = inputs(fixture(tmp_path)); step(f, 'prepare', stage='refusal', task_id=f['task']['task_id'], role='initial_writer')
    executor = f['old_executor'] if fault in {'old-fake-fresh', 'wrong-origin-followup'} else '/root/unknown'
    tool = 'collaboration.followup_task' if 'followup' in fault else 'collaboration.spawn_agent'
    if fault == 'preparer': executor = '/root/engineering_preparer'
    obs = invocation(f, 'refusal', executor, tool, origin_run=str(f['base']/'wrong-origin'))
    before = step(f, 'status')['resources']
    with pytest.raises(ValueError): step(f, 'begin', stage='refusal', observation=obs['path'])
    assert step(f, 'status')['resources'] == before


def test_actual_W4_is_preserved_charged_and_cannot_claim(tmp_path):
    f = inputs(fixture(tmp_path))
    for index in range(4):
        stage = 'attempt'+str(index); step(f, 'prepare', stage=stage, task_id=f['task']['task_id'], role='initial_writer')
        obs = invocation(f, stage, executor='/root/neutral_writer_'+str(index))
        inv = step(f, 'begin', stage=stage, observation=obs['path'])
    assert inv['within_budget'] is False and step(f, 'status')['resources'][0]['writer'] == 4
    before = step(f, 'status')['resources']
    with pytest.raises(ValueError, match='over-budget'): step(f, 'claim', stage=stage, ordinal=inv['ordinal'])
    with pytest.raises(ValueError, match='scope consumption blocked'): step(f, 'claim', stage='attempt0', ordinal=1)
    assert step(f, 'status')['resources'] == before


@pytest.mark.parametrize('journal_name', ['origin', 'later'])
def test_old_union_later_unknown_blocks_new_sdk_without_retry_or_refund(tmp_path, journal_name):
    f = inputs(fixture(tmp_path)); c = f['c']; journal = f['origin'] if journal_name == 'origin' else c.Journal(f['state']['root'])
    journal.append('sdk_intent', {'operation_key': 'synthetic-unknown', 'operation': 'fixture.transport.lost', 'arguments': {}})
    journal.append('sdk_error', {'operation_key': 'synthetic-unknown', 'error': 'SYNTHETIC unknown, never not_found'})
    before = step(f, 'status')['resources']
    with pytest.raises(ValueError): step(f, 'request')
    assert step(f, 'status')['resources'] == before


@pytest.mark.parametrize('key,value', [('operation', 'service.create'), ('adapter_context', {}), ('store', 'foreign'), ('scope', {'page_ids': []})])
def test_finite_actions_reject_any_operation_context_scope_or_store_override(tmp_path, key, value):
    with pytest.raises(ValueError, match='finite action'): p.advance('inputs', '/absent', '0'*64, 'r04', {key: value}, True)


@pytest.mark.parametrize('flow', ['raq2', 'cq2', 'r02', 'flow-04-alias'])
def test_other_flows_cannot_gain_a_later_pool(tmp_path, flow):
    with pytest.raises(ValueError, match='only original'): p.initialize('/absent', '0'*64, flow, True)


def test_SDK129_refused_before_public_call(tmp_path):
    from deck_master import service
    f = released(fixture(tmp_path))
    with p.session(f['control']['path'], f['control']['sha256'], f['flow'], True) as (_, c, j, _, _, _, state, _, _):
        for _ in range(127):
            c.record_sdk(j, 'service.inputs_show', {'project': state['project']}, lambda: service.inputs_show(state['project']))
    before = f['c'].store_for(f['state']).load_document()
    with pytest.raises(ValueError): step(f, 'request')
    assert f['c'].store_for(f['state']).load_document() == before


def test_actual_inputs_commit_lost_ack_is_charged_unknown_and_not_retried(tmp_path, monkeypatch):
    from deck_master import service
    f = released(fixture(tmp_path)); step(f, 'request'); original = service.inputs_update; actual = []
    def lost(*args, **kwargs):
        result = original(*args, **kwargs); actual.append(result); raise OSError('SYNTHETIC transport lost after real committed update')
    monkeypatch.setattr(service, 'inputs_update', lost)
    with pytest.raises(OSError, match='real committed'): step(f, 'inputs')
    monkeypatch.setattr(service, 'inputs_update', original)
    assert len(actual) == 1 and f['c'].store_for(f['state']).load_document()['revision_id'] == actual[0]['revision_id']
    before = step(f, 'status')['resources']; assert step(f, 'status')['later_pending']
    with pytest.raises(ValueError, match='unresolved'): step(f, 'inputs')
    assert step(f, 'status')['resources'] == before


def test_duplicate_initialize_and_pool_relocation_rejected(tmp_path):
    f = initialize(fixture(tmp_path))
    with pytest.raises(FileExistsError): initialize(f)
    control = f['c'].read(f['control']['path']); control['scope']['ledger_root'] = str(f['base']/'another-pool')
    changed = f['c'].save(f['base']/'different-control.json', control)
    with pytest.raises((ValueError, FileNotFoundError)):
        p.advance('status', changed['path'], changed['sha256'], f['flow'], {}, True)


def test_original_frozen_files_and_cuts_not_overwritten(tmp_path):
    f = inputs(fixture(tmp_path)); control = f['c'].read(f['control']['path'])
    for cuts in control['scope']['six_cuts'].values():
        for ref in cuts.values(): assert f['tool'].reference(ref['path']) == ref
    with pytest.raises(ValueError, match='distinct later300s'): step(f, 'snapshot', name='equal_budget_evaluated', native_manifest=None)


def test_no_private_nested_policy_target_is_read(tmp_path, monkeypatch):
    f = fixture(tmp_path); original = Path.read_bytes
    def guarded(path):
        assert 'never-open-index' not in str(path)
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    inputs(f)


def test_real_protected_review_uses_old_union_later_binding_and_frozen_original_counterexample(tmp_path):
    f = finish_initial(launch(inputs(fixture(tmp_path)))); record = review(f); c = f['c']
    j = c.Journal(f['state']['root']); before = step(f, 'status')['resources']
    # Genuine old d0 seam: old Page p2 is still authored by the original actor,
    # while d0 sees only the later writer in this journal. No SDK call occurs.
    with pytest.raises(ValueError, match='actual authors must be observed'):
        c.review_accept(j, f['state'], record['stage'], record['ordinal'], f['bootstrap']['path'])
    result = step(f, 'review-accept', stage=record['stage'], ordinal=record['ordinal'], bootstrap=f['bootstrap']['path'])
    assert f['old_executor'] in result['binding']['author_execution_refs']
    assert result['all_native_writer_execution_refs'] == sorted([f['old_executor'], f['invocation']['executor']])
    assert step(f, 'status')['resources'][0]['sdk'] == before[0]['sdk']+1
    step(f, 'feedback', stage=record['stage'], ordinal=record['ordinal'])
    with pytest.raises(ValueError): step(f, 'feedback', stage=record['stage'], ordinal=record['ordinal'])
    necessity = c.save(f['base']/'unnecessary-repair.json', {'necessary_layers': ['page_copy'], 'actual_review_finding_refs': ['invented']})
    with pytest.raises(ValueError, match='no actual defect'): step(f, 'repair', necessity=necessity['path'])


@pytest.mark.parametrize('inherited', [False, True])
def test_old_author_or_inherited_old_author_cannot_review_real_later_manuscript(tmp_path, inherited):
    f = finish_initial(launch(inputs(fixture(tmp_path)))); step(f, 'review-request', role='feedback')
    dispatch = step(f, 'review-prepare', stage='feedback', role='feedback', bootstrap=f['bootstrap']['path'])
    executor = '/root/new_reviewer' if inherited else f['old_executor']
    obs = invocation(f, 'feedback', executor, inherited_identities=[f['old_executor']] if inherited else [])
    before = step(f, 'status')['resources']
    with pytest.raises(ValueError, match='author cannot review'): step(f, 'begin', stage='feedback', observation=obs['path'])
    assert step(f, 'status')['resources'] == before and dispatch['task_id']


def test_actual_F2_preserved_and_cannot_claim(tmp_path):
    f = finish_initial(launch(inputs(fixture(tmp_path)))); step(f, 'review-request', role='feedback')
    for i in range(2):
        stage = 'feedback'+str(i); step(f, 'review-prepare', stage=stage, role='feedback', bootstrap=f['bootstrap']['path'])
        obs = invocation(f, stage, '/root/neutral_reviewer_'+str(i)); inv = step(f, 'begin', stage=stage, observation=obs['path'])
    assert inv['within_budget'] is False and step(f, 'status')['resources'][0]['review'] == 2
    with pytest.raises(ValueError, match='over-budget'): step(f, 'claim', stage=stage, ordinal=inv['ordinal'])


def repair_fixture(base, layer='page_copy'):
    f = finish_initial(launch(inputs(fixture(base)))); record = review(f, fail=True)
    step(f, 'review-accept', stage=record['stage'], ordinal=record['ordinal'], bootstrap=f['bootstrap']['path'])
    step(f, 'feedback', stage=record['stage'], ordinal=record['ordinal'])
    necessity = f['c'].save(f['base']/'necessary-repair.json', {'SYNTHETIC_NOT_NATIVE_JUDGMENT': True,
        'necessary_layers': [layer], 'actual_review_finding_refs': ['neutral-f1']})
    step(f, 'repair', necessity=necessity['path']); step(f, 'repair-request')
    f['repair_task'] = step(f, 'repair-task', layer=layer)
    return f


def test_actual_R4_preserved_shared_pool_and_cannot_claim(tmp_path):
    f = repair_fixture(tmp_path)
    for i in range(4):
        stage = 'repair'+str(i); step(f, 'prepare', stage=stage, role='repair_writer', task_id=f['repair_task']['task_id'])
        obs = invocation(f, stage, '/root/neutral_repair_writer_'+str(i)); inv = step(f, 'begin', stage=stage, observation=obs['path'])
    assert inv['within_budget'] is False and step(f, 'status')['resources'][0]['writer'] == 5
    with pytest.raises(ValueError, match='over-budget'): step(f, 'claim', stage=stage, ordinal=inv['ordinal'])
    assert step(f, 'status')['pool'] == 'q2-300:flow-04:1:B'


def test_verification_requires_repair_and_cannot_be_second_feedback(tmp_path):
    f = finish_initial(launch(inputs(fixture(tmp_path))))
    with pytest.raises(ValueError, match='necessary repair'):
        step(f, 'review-prepare', stage='verify', role='verification', bootstrap=f['bootstrap']['path'])


def finish_speech_repair(f):
    task = f['repair_task']; step(f, 'prepare', stage='repair', task_id=task['task_id'], role='repair_writer')
    obs = invocation(f, 'repair', '/root/neutral_speech_repair'); inv = step(f, 'begin', stage='repair', observation=obs['path'])
    step(f, 'claim', stage='repair', ordinal=inv['ordinal'])
    store = f['c'].store_for(f['state']); entry = store.load_document()['pages'][0]; notes = 'SYNTHETIC repaired complete neutral cue.'
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'speech', 'task_id': task['task_id'],
        'operation_id': task['operation_id'], 'produced_against': task['produced_against'], 'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'usage_events': [], 'payload': {'updates': [{'page_id': entry['page_id'], 'page_ref': entry['page'], 'speaker_notes': notes,
            'speech_segments': [{'segment_id': 'cue', 'start_codepoint': 0, 'end_codepoint': len(notes), 'narrative_node_ids': [], 'kind': 'cue', 'estimated_seconds': 5}]}]}}
    freeze_result(f, envelope, 'repair', inv); step(f, 'accept', stage='repair', ordinal=inv['ordinal'])
    return f


def test_actual_V2_preserved_readonly_not_second_feedback_or_repair(tmp_path):
    f = finish_speech_repair(repair_fixture(tmp_path, 'speech')); step(f, 'review-request', role='verification')
    for i in range(2):
        stage = 'verify'+str(i); step(f, 'review-prepare', stage=stage, role='verification', bootstrap=f['bootstrap']['path'])
        obs = invocation(f, stage, '/root/neutral_verifier_'+str(i)); inv = step(f, 'begin', stage=stage, observation=obs['path'])
    assert inv['within_budget'] is False and step(f, 'status')['resources'][0]['review'] == 3
    before = f['c'].store_for(f['state']).load_document()
    with pytest.raises(ValueError): step(f, 'claim', stage=stage, ordinal=inv['ordinal'])
    with pytest.raises(ValueError): step(f, 'feedback', stage=stage, ordinal=inv['ordinal'])
    with pytest.raises(ValueError): step(f, 'repair-task', layer='speech')
    assert f['c'].store_for(f['state']).load_document() == before


def test_completed_content_request_direct_review_dispatch_is_real_preserved_negative(tmp_path):
    from deck_master.eligibility import EligibilityBlocked
    f = finish_initial(launch(inputs(fixture(tmp_path))))
    doc = f['c'].store_for(f['state']).load_document(); assert doc['collaboration']['request']['closed'] is True
    before = step(f, 'status')['resources'][0]['sdk']
    with pytest.raises(EligibilityBlocked, match='current request is closed'):
        step(f, 'review-prepare', stage='closed-direct', role='feedback', bootstrap=f['bootstrap']['path'])
    status = step(f, 'status'); assert status['resources'][0]['sdk'] == before+1 and status['later_pending']


def test_lifecycle_requests_retain_same_project_original_released_52B_input(tmp_path):
    f = finish_speech_repair(repair_fixture(tmp_path, 'speech')); step(f, 'review-request', role='verification')
    doc = f['c'].store_for(f['state']).load_document(); request = doc['collaboration']['request']
    assert f['c'].store_for(f['state']).read_object_bytes(request['instruction_evidence']['source_ref']) == p.MESSAGE.encode()
    assert request['instruction_evidence']['source_ref'] == f['instruction']['source_ref']
    assert request['scope']['page_ids'] == [e['page_id'] for e in doc['pages']]
    assert request['scope']['page_manifest_ref'] == doc['content_plan'] and request['scope']['layers'] == ['review']
    assert step(f, 'status')['resources'][0]['review'] == 1  # Request changes never refill or fabricate roles.


def test_real_CAS_race_keeps_error_attempt_and_blocks_retry(tmp_path, monkeypatch):
    from deck_master import service
    f = released(fixture(tmp_path)); step(f, 'request'); original = service.inputs_show; c = f['c']; external = c.Journal(f['base']/'external-actor')
    def raced(project):
        observed = original(project)
        c.record_sdk(external, 'service.inputs_update.external_fixture_actor', {'project': str(project)},
            lambda: service.inputs_update(project, patch={'task_patch': {'title': 'SYNTHETIC competing actor'}, 'reason': 'SYNTHETIC CAS interleave'},
                base_revision=observed['revision_id'], operation_id='external-'+c.uuid.uuid4().hex))
        return observed
    monkeypatch.setattr(service, 'inputs_show', raced)
    with pytest.raises(Exception, match='revision'):
        step(f, 'inputs')
    monkeypatch.setattr(service, 'inputs_show', original)
    status = step(f, 'status'); assert status['later_pending'] and status['resources'][0]['sdk'] == 4
    assert len([e for e in external.events() if e['kind'] == 'sdk_intent']) == 1
    with pytest.raises(ValueError): step(f, 'inputs')


def test_interrupted_charge_projection_retains_unknown_without_executing_sdk(tmp_path, monkeypatch):
    f = released(fixture(tmp_path)); c = f['c']; before = c.store_for(f['state']).load_document()
    # Inject only the actual filesystem projection write boundary, after the
    # real charge and intent and before any public SDK call.
    write_original = Path.open
    def fail_file(path, mode='r', *args, **kwargs):
        if mode == 'xb' and path.parent.name == 'journal' and path.parent.parent.name == 'resource-ledger':
            current = [f['c'].read(x) for x in sorted(path.parent.glob('*.json'))]
            if current and current[-1]['kind'] == 'resource_charge' and current[-1]['data']['resource'] == 'sdk':
                raise OSError('SYNTHETIC durable projection I/O interruption')
        return write_original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_file)
    with pytest.raises(OSError, match='projection'): step(f, 'request')
    monkeypatch.setattr(Path, 'open', write_original)
    assert c.store_for(f['state']).load_document() == before
    assert step(f, 'status')['resources'][0]['sdk'] == 2
    with pytest.raises(ValueError): step(f, 'request')


def test_private_target_rejected_before_resolve_stat_or_frozen_reader(monkeypatch):
    def no_target_IO(*args, **kwargs):
        raise AssertionError('private target must not be resolved/read/stat-ed')
    monkeypatch.setattr(Path, 'resolve', no_target_IO)
    with pytest.raises(ValueError, match='ordinary public path'):
        p.canonical('/private/never-open.json')
    with pytest.raises(ValueError, match='ordinary public path'):
        p.advance('release', '/unused-control', '0'*64, 'r04', {'trigger': '/private/never-open.json'}, True)
