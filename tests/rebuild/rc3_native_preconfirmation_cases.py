"""S13 isolated substantive cases; every native observation is SYNTHETIC.

Portable source fixtures use six tiny neutral methods without patching the
frozen helper or its production validator. prepare/begin/read/observe/event
functions are real. The separate engineering trace uses the six full pinned
public files and genuinely validates/freezes/initializes through old CLI.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[2]/'tools/rc3_campaign/native_preconfirmation.py'
spec = importlib.util.spec_from_file_location('s13_source_companion', SCRIPT)
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def _obs(n, **extra):
    return {'evidence_kind': 'SYNTHETIC_ENGINEERING_ONLY', 'observation_kind': n.OBSERVER_KIND,
            'assurance': 'host_attested', 'observed_at_utc': n._common.now(), **extra}


def _finish(n, base, journal, config, begun, raw, kind):
    ordinal = begun['ordinal']
    result = n.write_once(base/f'original-{ordinal}.txt', raw)
    method = n.reference(journal.root/f'executions/{ordinal:04d}/method-read.json')
    obs = n.save(base/f'completion-{ordinal}.json', _obs(n, packet_sha256=begun['packet']['sha256'],
        method_read_record_sha256=method['sha256'], model_output_bytes_sha256=result['sha256'],
        all_method_bytes_read=True, native_output_kind=kind, completion={
            'sender': begun['executor'], 'message_type': 'FINAL_ANSWER',
            'status_observation_tool': 'collaboration.list_agents', 'observed_status': 'completed',
            'observed_completed_agents': [begun['executor']], 'raw_final_message': raw.decode()}))
    return n.observe(journal, config, ordinal, result['path'], result['sha256'], obs['path'], obs['sha256'])


def build_fixture(base, tool, full_methods=None):
    base = Path(base).resolve(); base.mkdir(parents=True, exist_ok=True)
    n = tool._native(); campaign = base/'campaign'; run = base/'run'
    rows = []
    for index, relative in enumerate(n.METHODS):
        content = (full_methods[relative] if full_methods is not None
                   else f'SYNTHETIC_ENGINEERING_ONLY complete neutral method {index}.\n'.encode())
        rows.append({**n.write_once(base/'method-inputs'/relative, content), 'relative_path': relative})
    identity = n.save(base/'input-identities.json', {'cyberppt': {'fixed_commit': n.COMMIT,
        'references_total_bytes': 121367, 'five_complete_references_and_MIT': rows}})
    protocol = n.save(base/'protocol.json', {'format': 'synthetic-native-protocol.v3', 'shared_conditions': {
        'initial_substantive_stages_cap': 5, 'independent_content_feedback_cap': 1,
        'autonomous_substantive_repair_cap': 1, 'necessary_repair_layer_cap': 3}})
    exposure = n.save(base/'exposure.json', {'status': 'FROZEN', 'excluded_identities': ['/engineering/preparer']})
    technical = n.save(base/'technical-admission.json', {'status': 'ENGINEERING_ONLY_NOT_ADMITTED'})
    # Future campaign path is fixed before its registration is written.
    campaign.mkdir()
    direction = n.write_once(campaign/'synthetic-direction.txt', tool.ENGINEERING_REPLY)
    purpose = n.write_once(base/'purpose.txt', b'Neutral purpose already provided.\n')
    config = {'format': n.VERSION, 'status': 'ENGINEERING_ONLY_NOT_ADMITTED', 'arm': 'E1-C',
        'recorder_sha256': tool.NATIVE_SHA, 'common_utils_sha256': tool.COMMON_SHA,
        'budget': deepcopy(tool.BUDGET), 'protocol': protocol, 'input_identities': identity,
        'exposure_registry': exposure, 'admission_review': technical,
        'observable_configuration': dict.fromkeys(('model', 'seed', 'price', 'tokens', 'invocation_parameters')),
        'cases': {'GENTRY': {'brief': n.write_once(base/'brief.txt', b'Neutral library route task.\n'),
            'materials': [n.write_once(base/'material.txt', b'An unknown route stays unknown.\n')],
            'events': {'Q1-answer-purpose': {'planned_dispatch': True, 'message': purpose},
                       'Q1-answer-direction': {'planned_dispatch': True, 'message': direction}}}},
        'role_instructions': {role: n.write_once(base/(role+'.txt'), b'Neutral native role; no model is invoked.\n')
                              for role in n.ROLES}}
    n.save(campaign/'registration.json', config)
    state = {'campaign': str(campaign), 'registration_sha256': n.digest(n.encoded(config)),
             'arm': 'E1-C', 'case': 'GENTRY', 'repetition': 1, 'budget': deepcopy(tool.BUDGET)}
    if full_methods is not None:
        n.validate(config)  # exact original six-method validator, no monkeypatch
        n.init(campaign, run, 'GENTRY', 1)
    else:
        run.mkdir(); n.save(run/'run.json', state)
        n.Journal(run).append('native_workflow_initialized', state)
    journal = n.Journal(run)
    with journal.locked():
        pass
    for ordinal in (1, 2):
        packet = n.prepare(journal, state, config, f'n0{ordinal}', 'initial_writer')
        invocation = n.save(base/f'invocation-{ordinal}.json', _obs(n, packet_sha256=packet['sha256'], spawn={
            'tool': 'collaboration.spawn_agent' if ordinal == 1 else 'collaboration.followup_task',
            'canonical_task_name': tool.ENGINEERING_ACTOR, 'returned_task_name': tool.ENGINEERING_ACTOR,
            'fork_turns': 'none', 'inherited_identities': []}))
        begun = n.begin(journal, config, f'n0{ordinal}', invocation['path'])
        n.method_read(journal, ordinal, tool.ENGINEERING_ACTOR)
        observed = _finish(n, base, journal, config, begun,
            b'Neutral purpose question.\n' if ordinal == 1 else tool.ENGINEERING_RAW,
            'question' if ordinal == 1 else 'partial_manuscript')
        if ordinal == 1:
            trigger = n.save(base/'purpose-trigger.json', _obs(n, event_id='Q1-answer-purpose',
                actual_trigger_satisfied=True, actual_trigger_explanation='Synthetic neutral purpose question.',
                source_observations=[observed['raw']]))
            n.scripted_event(journal, state, config, 'Q1-answer-purpose', trigger['path'])
    return {'base': base, 'run': run, 'campaign': campaign, 'config': config, 'state': state, 'journal': journal, 'n': n}


def admission_for(fixture, tool):
    n = fixture['n']; _, scope, _, _ = tool._context(fixture['run'], True, n)
    value = {'format': tool.FORMAT, 'action': tool.ACTION, 'status': 'ENGINEERING_ONLY_NOT_ADMITTED',
        'observer_id': '/engineering/rc3-s13', 'evidence_kind': 'SYNTHETIC_ENGINEERING_ONLY',
        'observation_kind': n.OBSERVER_KIND, 'assurance': 'synthetic_engineering',
        'observed_at_utc': n._common.now(), 'scope': scope, 'actual_early_checkpoint_observed': True,
        'no_pending_native_invocation': True, 'independent_implementation_review_passed': True,
        'full_direction_trigger_satisfied': False}
    path = fixture['base']/('control-'+str(len(list(fixture['base'].glob('control-*.json'))))+'.json')
    return n.save(path, value)


def prefix(fixture):
    return [(fixture['run']/f'journal/{i:06d}.json').read_bytes() for i in range(1, 13)]


@pytest.fixture
def setup(tmp_path):
    f = build_fixture(tmp_path, p); f['admission'] = admission_for(f, p)
    (tmp_path/'identity.json').write_text(json.dumps({'isolated': sys.flags.isolated,
        'dont_write_bytecode': sys.dont_write_bytecode, 'native_helper': f['n'].__file__, 'synthetic_only': True}))
    return f


def release(f):
    return p.release(f['run'], f['admission']['path'], f['admission']['sha256'], engineering=True)


def replace_admission(f, value):
    ref = f['n'].save(f['base']/('altered-'+str(len(list(f['base'].glob('altered-*.json'))))+'.json'), value)
    f['admission'] = ref


def rewrite_chain(f, mutate):
    events = f['journal'].events(); mutate(events)
    previous = None
    for i, event in enumerate(events, 1):
        event['sequence'] = i; event['previous_sha256'] = previous
        raw = f['n'].encoded(event); (f['run']/f'journal/{i:06d}.json').write_bytes(raw)
        previous = f['n'].digest(raw)


def start_logged_process(base, label, argv):
    started = datetime.now(timezone.utc).isoformat()
    child = subprocess.Popen(argv, cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return child, {'argv': argv, 'cwd': str(base), 'start_UTC': started,
                   'stdout_path': str(base/(label+'.stdout.txt')),
                   'stderr_path': str(base/(label+'.stderr.txt')),
                   'command_path': str(base/(label+'.command.json'))}


def finish_logged_process(pending, timeout=15):
    child, record = pending
    stdout, stderr = b'', b''
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        record['execution_error'] = 'TimeoutExpired; killed after logging available output'
        raise
    finally:
        Path(record['stdout_path']).open('xb').write(stdout)
        Path(record['stderr_path']).open('xb').write(stderr)
        record.update(end_UTC=datetime.now(timezone.utc).isoformat(), exit=child.returncode)
        Path(record['command_path']).open('x').write(json.dumps(record, indent=2)+'\n')
    return (stdout, stderr), child.returncode


def test_exact_prefix_single_typed_event_and_frozen_prepare_compatibility(setup):
    f = setup; before = prefix(f); result = release(f); n = f['n']
    assert prefix(f) == before and len(f['journal'].events()) == 13
    event = f['journal'].events()[-1]
    assert event['kind'] == 'scripted_event' and event['data']['format'] == p.CONTROL
    assert event['data']['event_id'] == p.EVENT_ID
    assert Path(result['message']['path']).read_bytes() == p.ENGINEERING_REPLY[:15]
    assert result['message']['sha256'] == p.PREFIX_SHA
    assert result['initial_used'] == 2 and result['remaining_initial'] == 3
    assert [d['event_id'] for d in n.events(f['journal'], 'scripted_event')] == ['Q1-answer-purpose', p.EVENT_ID]
    packet = n.read(n.prepare(f['journal'], f['state'], f['config'], 'n03', 'initial_writer')['path'])
    assert Path(packet['files']['released-events/001.txt']['path']).read_bytes() == p.ENGINEERING_REPLY[:15]
    assert len(packet['method_files']) == 6 and 'prior-author-originals/0001' in packet['files'] and 'prior-author-originals/0002' in packet['files']
    assert not any('technical-control' in k or 'admission' in k for k in packet['files'])
    assert len(n.events(f['journal'], 'native_begun')) == 2  # prepare/release never charges a Writer


def test_replay_refuses_without_new_writer_cost_or_old_prefix_change(setup):
    f = setup; before = prefix(f); release(f)
    with pytest.raises(p.Error): release(f)
    assert prefix(f) == before and len(f['journal'].events()) == 13
    assert len(f['n'].events(f['journal'], 'native_begun')) == 2


def test_unrecorded_old_full_answer_copy_is_unknown_and_refuses(setup):
    f=setup; before=prefix(f)
    f['n'].write_once(f['run']/'released-events/Q1-answer-direction.txt',p.ENGINEERING_REPLY)
    with pytest.raises(p.Error,match='unrecorded answer'):release(f)
    assert prefix(f)==before and len(f['journal'].events())==12


@pytest.mark.parametrize('field,value', [
    ('status','ADMITTED'), ('observer_id','/root'), ('evidence_kind','ROOT_ACTUAL_PROSPECTIVE_NATIVE_CONTROL'),
    ('assurance','host_attested'), ('format','generic-control'), ('action','override'),
    ('actual_early_checkpoint_observed',False), ('no_pending_native_invocation',False),
    ('independent_implementation_review_passed',False), ('full_direction_trigger_satisfied',True)])
def test_wrong_admission_or_unobserved_checkpoint_refuses_atomically(setup, field, value):
    f = setup; a = f['n'].read(f['admission']['path']); a[field] = value; replace_admission(f,a)
    before = prefix(f)
    with pytest.raises(p.Error): release(f)
    assert prefix(f) == before and len(f['journal'].events()) == 12
    assert not (f['run']/'technical-controls').exists()


@pytest.mark.parametrize('field', ['message','choice','range','api','callback'])
def test_no_generic_override_even_inside_an_admission(setup, field):
    f = setup; a = f['n'].read(f['admission']['path']); a[field] = 'not an allowed seam'; replace_admission(f,a)
    with pytest.raises(p.Error, match='finite'): release(f)
    assert len(f['journal'].events()) == 12


@pytest.mark.parametrize('field', ['actor','case','python','history','raw','completion','packet','method_read','projection','tool','registration','source_reply'])
def test_wrong_exact_scope_refuses_before_writing(setup, field):
    f = setup; a = f['n'].read(f['admission']['path']); a['scope'][field] = {'wrong': True}; replace_admission(f,a)
    before = prefix(f)
    with pytest.raises(p.Error): release(f)
    assert prefix(f) == before and not (f['run']/'technical-controls').exists()


@pytest.mark.parametrize('kind', ['scripted_event','snapshot_frozen','feedback_delivered','repair_begun','verification_started','native_begun'])
def test_every_advanced_frontier_or_started_phase_refuses(setup, kind):
    f = setup; f['journal'].append(kind, {'event_id':'Q1-answer-direction','role':'initial_writer'})
    before = [path.read_bytes() for path in sorted((f['run']/'journal').glob('*.json'))]
    with pytest.raises(p.Error, match='frontier'): release(f)
    assert [path.read_bytes() for path in sorted((f['run']/'journal').glob('*.json'))] == before


@pytest.mark.parametrize('change', ['complete','budget','used','different_actor','ambiguous_recommendation','raw','method','packet_file','old_full_event'])
def test_changed_original_phase_question_budget_or_bytes_refuses(setup, change):
    f = setup
    if change == 'complete': rewrite_chain(f,lambda e:e[-1]['data'].update(native_output_kind='complete_manuscript'))
    elif change == 'used': rewrite_chain(f,lambda e:e[8]['data'].update(role_ordinal=5))
    elif change == 'different_actor': rewrite_chain(f,lambda e:e[-1]['data'].update(executor='/root/another'))
    elif change == 'old_full_event': rewrite_chain(f,lambda e:e[6]['data'].update(event_id='Q1-answer-direction'))
    elif change == 'budget':
        state = f['n'].read(f['run']/'run.json'); state['budget']['initial_writer']=6; (f['run']/'run.json').write_bytes(f['n'].encoded(state))
    elif change in ('raw','ambiguous_recommendation'):
        (f['run']/'executions/0002/raw-native-output').write_bytes(b'Recommend route B.\nConfirm A/B.\n')
    elif change == 'method': (f['run']/'executions/0002/method-read.json').write_text('{}')
    else: (f['run']/'stages/n02/released-events/000.txt').write_bytes(b'purpose erased')
    before = prefix(f)
    with pytest.raises((p.Error,KeyError)): release(f)
    assert prefix(f) == before and len(f['journal'].events()) == 12


def test_private_index_registration_refs_are_not_followed(setup, monkeypatch):
    f = setup; config = deepcopy(f['config'])
    config['exposure_registry'] = {'path':str(f['base']/'private/index.json'),'sha256':'0'*64}
    config['admission_review'] = config['exposure_registry']
    (f['campaign']/'registration.json').write_bytes(f['n'].encoded(config))
    state = deepcopy(f['state']);state['registration_sha256']=f['n'].digest(f['n'].encoded(config))
    (f['run']/'run.json').write_bytes(f['n'].encoded(state))
    rewrite_chain(f,lambda e:e[0].update(data=state)); f['admission']=admission_for(f,p)
    original = Path.read_bytes
    def observed(path):
        assert 'private' not in path.parts, 'private registry must never be opened'
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',observed)
    assert release(f)['status']=='prospective_native_prefix_released'


def test_admission_private_path_and_engineering_formal_target_refuse_before_body_io(setup, monkeypatch):
    def no_read(path): raise AssertionError('refused path body was opened')
    monkeypatch.setattr(Path,'read_bytes',no_read)
    with pytest.raises(p.Error): p.release(str(p.RUN),'/private/index.json','0'*64,engineering=True)
    with pytest.raises(p.Error): p.file_ref('/private/index.json')


@pytest.mark.parametrize('where', ['admission.json','message.txt','control.json','000013.json'])
def test_fault_before_each_publish_preserves_prefix_and_never_exposes_partial_event(setup, monkeypatch, where):
    f = setup; before = prefix(f); actual = p._publish
    def fail(path,raw):
        if path.name==where: raise OSError('actual injected write failure before '+where)
        return actual(path,raw)
    monkeypatch.setattr(p,'_publish',fail)
    with pytest.raises(OSError): release(f)
    assert prefix(f)==before and len(f['journal'].events())==12
    assert not (f['run']/'journal/000013.json').exists()
    packet=f['n'].read(f['n'].prepare(f['journal'],f['state'],f['config'],'n03','initial_writer')['path'])
    assert 'released-events/001.txt' not in packet['files']  # orphan bytes are not delivered


def test_actual_short_write_failure_cannot_publish_partial_journal(setup, monkeypatch):
    f=setup; before=prefix(f); actual=os.write; actual_open=os.open; count=0
    journal_fds=set()
    def track_open(path,*args,**kwargs):
        fd=actual_open(path,*args,**kwargs)
        target=Path(path)
        if target.parent==f['run']/'journal' and target.name.startswith('.pending-'):
            journal_fds.add(fd)
        return fd
    def fail(fd,raw):
        nonlocal count
        if fd in journal_fds:
            count+=1
            if count==1:return actual(fd,raw[:9])
            raise OSError('interrupted partial journal write')
        return actual(fd,raw)
    monkeypatch.setattr(os,'open',track_open)
    monkeypatch.setattr(os,'write',fail)
    with pytest.raises(OSError):release(f)
    assert count==2 and prefix(f)==before and len(f['journal'].events())==12
    assert not list((f['run']/'journal').glob('.pending-*'))


def test_lost_ack_after_complete_event_never_retries_or_references_incomplete_bytes(setup, monkeypatch):
    f=setup; before=prefix(f); actual=p._publish
    def lost(path,raw):
        result=actual(path,raw)
        if path.name=='000013.json':raise OSError('after valid append, acknowledgment lost')
        return result
    monkeypatch.setattr(p,'_publish',lost)
    with pytest.raises(OSError):release(f)
    assert prefix(f)==before and len(f['journal'].events())==13
    event=f['journal'].events()[-1]
    for key in ('trigger','message','control_admission'):assert p.file_ref(event['data'][key]['path'])==event['data'][key]
    with pytest.raises(p.Error):release(f)
    assert len(f['journal'].events())==13


def test_replaced_shared_lock_is_detected_before_append(setup, monkeypatch):
    f=setup; actual=p._publish; changed=False
    def replace(path,raw):
        nonlocal changed
        result=actual(path,raw)
        if not changed:
            changed=True; lock=f['run']/'.controller.lock';lock.unlink();lock.touch()
        return result
    monkeypatch.setattr(p,'_publish',replace)
    with pytest.raises(p.Error,match='lock replaced'):release(f)
    assert len(f['journal'].events())==12


def test_cooperating_writer_advances_while_release_waits_for_same_real_lock(setup, tmp_path):
    f=setup; ready=tmp_path/'ready'; before=prefix(f)
    code='''import importlib.util,sys
from pathlib import Path
from contextlib import contextmanager
spec=importlib.util.spec_from_file_location('companion',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
actual=m._locked
@contextmanager
def observe(root):
 Path(sys.argv[5]).write_text('waiting for real shared lock')
 with actual(root) as check:yield check
m._locked=observe
try:m.release(sys.argv[2],sys.argv[3],sys.argv[4],engineering=True)
except m.Error:sys.exit(2)
raise AssertionError('changed frontier accepted')
'''
    with f['journal'].locked():
        pending=start_logged_process(tmp_path,'process-waiting-release',[sys.executable,'-I','-B','-c',code,str(SCRIPT),str(f['run']),f['admission']['path'],f['admission']['sha256'],str(ready)])
        child=pending[0]
        deadline=time.monotonic()+10
        while not ready.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert ready.exists() and child.poll() is None
        f['journal'].append('feedback_delivered',{'synthetic_competing_writer':True})
    (stdout,stderr),exit_code=finish_logged_process(pending,timeout=10)
    assert exit_code==2,(stdout+stderr).decode()
    assert prefix(f)==before and len(f['journal'].events())==13
    assert not (f['run']/'technical-controls').exists()


def test_two_actual_processes_release_at_most_one_event(setup):
    f=setup; before=prefix(f); argv=[sys.executable,'-I','-B',str(SCRIPT),'--engineering-only','--run',str(f['run']),'--admission',f['admission']['path'],'--admission-sha256',f['admission']['sha256']]
    children=[start_logged_process(f['base'],'process-release-'+str(i),argv) for i in range(2)]
    results=[finish_logged_process(pending) for pending in children]
    assert sorted(exit for _,exit in results)==[0,2],results
    assert prefix(f)==before and len(f['journal'].events())==13


@pytest.mark.parametrize('offset',[-3600,60])
def test_stale_or_future_admission_refuses(setup,offset):
    f=setup;a=f['n'].read(f['admission']['path']);a['observed_at_utc']=(datetime.now(timezone.utc)+timedelta(seconds=offset)).isoformat();replace_admission(f,a)
    with pytest.raises(ValueError):release(f)
    assert len(f['journal'].events())==12


def test_duplicate_json_keys_and_wrong_digest_refuse(setup):
    f=setup;before=prefix(f)
    with pytest.raises(p.Error):p.release(f['run'],f['admission']['path'],'0'*64,engineering=True)
    path=f['base']/'duplicate.json';raw=Path(f['admission']['path']).read_bytes();path.write_bytes(raw.replace(b'{',b'{"format":"ambiguous",',1))
    with pytest.raises(p.Error,match='duplicate'):p.release(f['run'],str(path),p.file_ref(path)['sha256'],engineering=True)
    assert prefix(f)==before


def test_admission_parser_cannot_authorize_different_bytes_than_its_digest(setup, monkeypatch):
    f=setup; a=f['n'].read(f['admission']['path']);a['independent_implementation_review_passed']=False
    replace_admission(f,a); path=Path(f['admission']['path']); actual=Path.read_bytes; reads=0
    forged=deepcopy(a);forged['independent_implementation_review_passed']=True
    def transient(current):
        nonlocal reads
        if current==path:
            reads+=1
            if reads==2:return f['n'].encoded(forged)
        return actual(current)
    monkeypatch.setattr(Path,'read_bytes',transient)
    with pytest.raises(p.Error):release(f)
    assert len(f['journal'].events())==12
