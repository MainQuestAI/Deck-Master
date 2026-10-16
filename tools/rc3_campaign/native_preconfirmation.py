#!/usr/bin/env python3
"""One prospective native-C route prefix; no SDK, actor or message override.

Root attests the current observation/admission. Hashes bind local bytes, not
platform trust or comparison eligibility. The frozen native consumer is intact.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import uuid

NATIVE_SHA = 'd9f24668dee4a743ac18ce3ab6ec9fc5fa45ad329b5695523ec32932506a7d12'
COMMON_SHA = 'd0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261'
FORMAT = 'rc3-native-preconfirmation-admission.v1'
CONTROL = 'rc3-native-preconfirmation-control.v1'
ACTION = 'release_captured_native_recommendation_prefix_only'
EVENT_ID = 'RC3-S13-native-preconfirmation'
RUN = Path('/tmp/rc3-pv2/cq1')
CAMPAIGN = Path('/tmp/rc3-pv2/cc')
REPLY = Path('/workspace/work/rc3/r05/postfix-v2-execution-inputs/controller-only/messages/Q1-answer-direction.txt')
REPLY_SHA = '100be63b567e52e82742eb3a56c615824c28fc05738f1b68d8e2b0fe86e0dcd9'
PREFIX_SHA = '6fb2496f7d0bac0744c5a36d70a50e4365728225c186b72613867d3b0b7e538f'
ENGINEERING_REPLY = '主线按这个，SYNTHETIC_ONLY\n'.encode()
ENGINEERING_RAW = b'Recommend route A.\nConfirm A or B.\n'
ENGINEERING_ACTOR = '/root/engineering_s13_writer'
BUDGET = {'initial_writer': 5, 'feedback': 1, 'repair_cycles': 1, 'repair_writer': 3}
HISTORY = (
    '2d361766f8e21d29f00d469eeeec6f59528d514020c5771767c0e3ce6b2e2b28',
    'c71a625c047d1ea41e32102b53ea10e929eeb870275a95531c4609ab54fdc877',
    'bd253bfb26d5e492c7a3cf02f86000eac627cdcb9f0b8a3fafd2b28410f0901b',
    '26944e5640132f63067c005b34728ca2b4291cec9991a7f5de3aac200e2057bb',
    'd31584f1a1053b38deeed1e95b2caa2b60bf1dda99c9022da277bd5e788d84e0',
    '3bf763bebfb2cd9349dfa0d57b0283a24cd2bd15d17f5abbbdbc5f83ab06a26f',
    'db7b9268d8a0923a40666c0ac2a5c567e51a56feaa4831f396b44d0d4822ddda',
    '2bfc1200b01fa23040eff4924b5ee74c4b31925cbc570c3fe5b17949c1847514',
    'f91cad65015939318227bfc7920aa11714cc97358bdc8f53dc21ba3e748ad85d',
    '60532c56b4fd1c2d380760979e71dd8eeb87a67d73d3e60f620cdc94a2fdf6df',
    '3cbcb3c282ad82882ebdaab876715974919f0be3c7f723021fd9eadde963560c',
    '505cfda384ced0cb1177661eb7fe8e6a8582fde58b6f6f45d8af6e0af828d496',
)
KINDS = ('native_workflow_initialized', 'stage_prepared', 'native_begun', 'method_bytes_returned',
         'native_output_frozen', 'native_observed', 'scripted_event', 'stage_prepared',
         'native_begun', 'method_bytes_returned', 'native_output_frozen', 'native_observed')
FORMAL = {
    'registration': (16456, '238bad93fe1702231f8dd8443c334915bb23140b1f6cd82428dca7bb759ff02b'),
    'run_manifest': (291, '40d0ea6f04d548d0bc43d83c14dda8411f08960c6824520b85be2381dd75d770'),
    'raw': (6770, 'a61c2b7af489ce1f16194fb10055db8c722d0b3f4e3b45f997dba6ca3cd6aeda'),
    'completion': (7696, 'bbea02659fb2248e4ed4d6829cbf3a68f96d8aba2dd2230c7c852ba1ab232e30'),
    'packet': (5067, '4d870fd1d9bcb3657e47662494653df3295f86fe5de5727a9372cf5e03b480d0'),
    'method_read': (126534, '7612511c534c2810dff8faaeb3e540990a1932dd832f409a9a877de4694b6013'),
}
LIMIT = ('Prospective technical early-route intervention only. Original full direction/P5/full-six '
         'triggers remain unsatisfied; no DM adoption, writer call, cap renewal or retroactive comparison credit. '
         'Root must label every affected continuation/cut as post-intervention; eligibility is not granted here.')


class Error(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Error(reason)


def guard():
    require(sys.flags.isolated and sys.dont_write_bytecode and Path(sys.executable).is_absolute(),
            'use absolute Python -I -B')


def canonical(value):
    p = Path(value)
    require(not any('oracle' in part.lower() or part.lower() in {'private', 'authkey'} for part in p.parts),
            'private/oracle/key path is never opened')
    require(p.is_absolute() and '..' not in p.parts and p.resolve(strict=True) == p,
            'canonical absolute ordinary path required')
    return p


def file_ref(path):
    p = canonical(path)
    require(stat.S_ISREG(p.stat().st_mode) and p.stat().st_nlink == 1, 'single ordinary file required')
    raw = p.read_bytes()
    return {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _read(path, expected):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise Error('nonfinite JSON value: ' + value)
    raw = Path(path).read_bytes()
    require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
            'JSON bytes changed between Ref and parser')
    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=nonfinite)


def _native():
    base = Path(__file__).resolve().parent
    require(file_ref(base/'native_only.py')['sha256'] == NATIVE_SHA
            and file_ref(base/'controller.py')['sha256'] == COMMON_SHA, 'frozen helper bytes differ')
    spec = importlib.util.spec_from_file_location('rc3_s13_frozen_native', base/'native_only.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return native


def _context(root, engineering, n):
    """Only named public run artifacts; never native.load/validate's index IO."""
    root = canonical(root)
    require(root.is_dir(), 'existing native run required')
    if engineering:
        require(not root.is_relative_to(Path('/tmp/rc3-pv2')), 'engineering cannot open a formal run')
    else:
        require(root == RUN, 'only captured Q1 native C run supported')
    run_ref = file_ref(root/'run.json'); state = _read(run_ref['path'], run_ref)
    campaign = canonical(state['campaign'])
    if engineering:
        require(not campaign.is_relative_to(Path('/tmp/rc3-pv2')), 'engineering cannot open formal campaign')
    else:
        require(campaign == CAMPAIGN, 'original campaign required')
    reg_ref = file_ref(campaign/'registration.json'); config = _read(reg_ref['path'], reg_ref)
    status = 'ENGINEERING_ONLY_NOT_ADMITTED' if engineering else 'ADMITTED'
    case = 'GENTRY' if engineering else 'Q1'
    require(state.get('arm') == config.get('arm') == 'E1-C' and state.get('case') == case
            and state.get('repetition') == 1 and state.get('budget') == config.get('budget') == BUDGET,
            'native case/arm/repetition/original budget differs')
    require(type(state['repetition']) is int and all(type(v) is int for v in state['budget'].values())
            and all(type(v) is int for v in config['budget'].values()), 'integer original budgets required')
    require(config.get('format') == n.VERSION and config.get('status') == status
            and config.get('recorder_sha256') == NATIVE_SHA and config.get('common_utils_sha256') == COMMON_SHA
            and state.get('registration_sha256') == n.digest(n.encoded(config)) == reg_ref['sha256'],
            'original initialized registration differs')
    require(not any(k in config for k in ('project', 'installations', 'task_id', 'sdk_gate')),
            'native C does not use a DM installation/project/Task')
    paths = sorted((root/'journal').glob('*.json'))
    require([p.name for p in paths] == [f'{i:06d}.json' for i in range(1, 13)],
            'exact twelve-event frontier required; duplicate/later phase refuses')
    refs = [file_ref(p) for p in paths]
    journal = n.Journal(root); events = journal.events()
    require(len(events) == 12 and all(n.digest(n.encoded(e)) == r['sha256'] for e, r in zip(events, refs)),
            'journal data changed between Ref and parser')
    require(tuple(e['kind'] for e in events) == KINDS, 'original native phase differs')
    require(events[0]['data'] == state and events[6]['data'].get('event_id') == 'Q1-answer-purpose',
            'original initialization/purpose event required')
    require({p.name for p in (root/'released-events').iterdir()} == {'Q1-answer-purpose.txt'},
            'old full/other release or unrecorded answer exists')
    require(file_ref(root/'released-events/Q1-answer-purpose.txt') == events[6]['data']['message'],
            'original released purpose changed')
    for directory, names in (('stages', {'n01', 'n02'}), ('executions', {'0001', '0002'})):
        require({p.name for p in (root/directory).iterdir()} == names, 'unrecorded/later native work exists')
    require(not (root/'snapshots').exists() or not list((root/'snapshots').iterdir()),
            'complete/comparison/feedback phase already started')
    begun = [e['data'] for e in events if e['kind'] == 'native_begun']
    observed = [e['data'] for e in events if e['kind'] == 'native_observed']
    require(len(begun) == len(observed) == 2 and all(
        b['ordinal'] == b['role_ordinal'] == i and b['role'] == 'initial_writer'
        and b['within_budget'] is True and b['cap'] == 5 for i, b in enumerate(begun, 1)),
        'same original two initial calls/cap required, no renewal')
    require([o['native_output_kind'] for o in observed] == ['question', 'partial_manuscript'],
            'first complete/review is not early confirmation')
    actor = ENGINEERING_ACTOR if engineering else '/root/pv2_q1_c_writer_01'
    require(all(o['executor'] == b['executor'] == actor and all(o[k] == v for k, v in b.items())
                for o, b in zip(observed, begun)), 'actual same actor/invocation binding differs')
    artifacts = {'registration': reg_ref, 'run_manifest': run_ref,
                 'raw': file_ref(root/'executions/0002/raw-native-output'),
                 'completion': file_ref(root/'executions/0002/raw-root-completion.json'),
                 'packet': file_ref(root/'stages/n02/packet.json'),
                 'method_read': file_ref(root/'executions/0002/method-read.json')}
    if not engineering:
        require(all(refs[i]['sha256'] == sha for i, sha in enumerate(HISTORY)), 'captured twelve-event prefix differs')
        require(all((artifacts[k]['bytes'], artifacts[k]['sha256']) == value for k, value in FORMAL.items()),
                'captured public n02 artifact differs')
    else:
        require(Path(artifacts['raw']['path']).read_bytes() == ENGINEERING_RAW, 'fixed neutral recommendation/question required')
    data = observed[-1]; comp = _read(artifacts['completion']['path'], artifacts['completion'])
    packet = _read(artifacts['packet']['path'], artifacts['packet'])
    methods = _read(artifacts['method_read']['path'], artifacts['method_read']); raw = Path(artifacts['raw']['path']).read_bytes()
    require(data['raw'] == artifacts['raw'] and data['observation'] == artifacts['completion']
            and data['packet'] == artifacts['packet'] and events[9]['data']['record'] == artifacts['method_read'],
            'journal raw/completion/packet/method-read differs')
    completed = comp['completion']
    require(comp.get('evidence_kind') == ('SYNTHETIC_ENGINEERING_ONLY' if engineering else 'ROOT_ACTUAL_NATIVE')
            and comp.get('observation_kind') == n.OBSERVER_KIND and comp.get('assurance') == 'host_attested'
            and comp.get('packet_sha256') == artifacts['packet']['sha256']
            and comp.get('method_read_record_sha256') == artifacts['method_read']['sha256']
            and comp.get('model_output_bytes_sha256') == artifacts['raw']['sha256']
            and comp.get('all_method_bytes_read') is True and comp.get('native_output_kind') == 'partial_manuscript'
            and completed.get('sender') == actor and completed.get('message_type') == 'FINAL_ANSWER'
            and completed.get('status_observation_tool') == 'collaboration.list_agents'
            and completed.get('observed_status') == 'completed' and actor in completed.get('observed_completed_agents', [])
            and completed.get('raw_final_message', '').encode() == raw, 'actual completed native original binding differs')
    require(packet.get('format') == 'native-text-no-dm-schema' and packet.get('case') == case
            and packet.get('arm') == 'E1-C' and packet.get('role') == 'initial_writer'
            and packet.get('stage') == 'n02' and methods.get('packet') == artifacts['packet']
            and methods.get('executor') == actor and methods.get('ordinal') == 2,
            'native packet/method identity differs')
    for relative, r in packet['files'].items():
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
                'packet file must be relative to its exact stage')
        require(file_ref(root/'stages/n02'/relative) == r, 'copied packet file differs')
    rows = packet['method_files']
    require(len(rows) == 6 and {r['relative_path'] for r in rows} == set(n.METHODS), 'six complete method files required')
    for r in rows:
        require({k: v for k, v in r.items() if k != 'relative_path'} ==
                packet['files']['methods/' + r['relative_path']], 'method Ref is outside exact copied packet')
    require(methods.get('method_bundle_sha256') == packet.get('method_bundle_sha256') == n.digest(n.encoded(
        [[r['relative_path'], r['sha256']] for r in rows])), 'full method bundle differs')
    require(len(methods['files']) == 6 and all(
        {k: m[k] for k in r} == r and m['content'].encode() == Path(r['path']).read_bytes()
        and (engineering or (r['bytes'], r['sha256']) == n.METHODS[r['relative_path']])
        for r, m in zip(rows, methods['files'])), 'actual full method-read bytes differ')
    purpose = file_ref(root/'stages/n02/released-events/000.txt')
    require(purpose['sha256'] == events[6]['data']['message']['sha256'], 'purpose was already released and must remain delivered')
    source = campaign/'synthetic-direction.txt' if engineering else REPLY
    source_ref = file_ref(source); answer = source.read_bytes()
    require(len(answer) == source_ref['bytes'] and n.digest(answer) == source_ref['sha256'],
            'reply bytes changed between Ref and projection')
    require(answer == ENGINEERING_REPLY if engineering else (len(answer) == 38 and source_ref['sha256'] == REPLY_SHA),
            'only fixed source reply supported')
    require(config['cases'][case]['events']['Q1-answer-direction']['message'] == source_ref,
            'registered full reply source differs')
    require(n.digest(answer[:15]) == PREFIX_SHA and answer[15:18] == '，'.encode()
            and len(answer[:15].decode()) == 5, 'only exact complete five-character prefix is allowed')
    scope = {'run': str(root), 'campaign': str(campaign), 'case': case, 'arm': 'E1-C', 'repetition': 1,
             'tool': file_ref(Path(__file__).resolve()), 'native_helper': file_ref(Path(n.__file__)),
             'common': file_ref(Path(n._common.__file__)), 'python': sys.executable,
             'history': refs, **artifacts, 'actor': actor, 'recommended_route': 'A',
             'source_reply': source_ref, 'projection': {'start': 0, 'end_exclusive': 15, 'bytes': 15, 'sha256': PREFIX_SHA},
             'original_budget': BUDGET, 'initial_used': 2, 'remaining_initial': 3}
    return journal, scope, events[-1]['recorded_at'], answer[:15]


@contextmanager
def _locked(root):
    path = root/'.controller.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'ordinary shared journal lock required')
        fcntl.flock(fd, fcntl.LOCK_EX)
        def unchanged():
            current = path.lstat()
            require((current.st_dev, current.st_ino) == (st.st_dev, st.st_ino), 'shared journal lock replaced')
        unchanged()
        yield unchanged
        unchanged()
    finally:
        os.close(fd)


def _publish(path, raw):
    """Publish complete bytes exclusively; never expose partial journal JSON."""
    temp = path.with_name('.pending-' + uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            require(count > 0, 'short file write')
            offset += count
        os.fsync(fd)
        os.link(temp, path)  # complete, exclusive, no replacement of old facts
    finally:
        os.close(fd)
        temp.unlink()
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return file_ref(path)


def release(root, admission, admission_sha256, *, engineering=False):
    guard()
    # Refuse wrong target before helper or caller-supplied file body IO.
    require(not Path(root).is_relative_to(Path('/tmp/rc3-pv2')) if engineering else Path(root) == RUN,
            'wrong native run/profile')
    root = canonical(root); n = _native()
    original = file_ref(admission)
    require(original['sha256'] == admission_sha256, 'exact prospective admission digest required')
    a = _read(original['path'], original)
    expected_keys = {'format', 'action', 'status', 'observer_id', 'evidence_kind', 'observation_kind', 'assurance',
                     'observed_at_utc', 'scope', 'actual_early_checkpoint_observed', 'no_pending_native_invocation',
                     'independent_implementation_review_passed', 'full_direction_trigger_satisfied'}
    require(set(a) == expected_keys and a['format'] == FORMAT and a['action'] == ACTION,
            'exact finite CONTROL admission fields required; no message/choice/range overrides')
    require(a['status'] == ('ENGINEERING_ONLY_NOT_ADMITTED' if engineering else 'ADMITTED')
            and a['observer_id'] == ('/engineering/rc3-s13' if engineering else '/root')
            and a['evidence_kind'] == ('SYNTHETIC_ENGINEERING_ONLY' if engineering else 'ROOT_ACTUAL_PROSPECTIVE_NATIVE_CONTROL')
            and a['assurance'] == ('synthetic_engineering' if engineering else 'host_attested')
            and a['observation_kind'] == n.OBSERVER_KIND and a['actual_early_checkpoint_observed'] is True
            and a['no_pending_native_invocation'] is True and a['independent_implementation_review_passed'] is True
            and a['full_direction_trigger_satisfied'] is False, 'fresh Root CONTROL observation/admission required')
    def bind():
        n.fresh(a['observed_at_utc'])
        journal, scope, last_time, message = _context(root, engineering, n)
        require(a['scope'] == scope and file_ref(admission) == original, 'exact scope/frontier/admission changed')
        require(datetime.fromisoformat(a['observed_at_utc'].replace('Z', '+00:00')) >= datetime.fromisoformat(last_time),
                'prospective observation cannot predate captured frontier')
        return journal, scope, message
    bind()
    with _locked(root) as unchanged:
        journal, scope, message = bind()  # same lock as frozen controller, new current read
        target = root/'technical-controls'/EVENT_ID
        target.parent.mkdir(exist_ok=True)
        require(target.parent.resolve() == target.parent and not target.exists(), 'write-once intervention already exists')
        target.mkdir(mode=0o700)
        copied = _publish(target/'admission.json', Path(original['path']).read_bytes())
        require((copied['bytes'], copied['sha256']) == (original['bytes'], original['sha256']),
                'admission changed during its immutable copy')
        projected = _publish(target/'message.txt', message)
        control = _publish(target/'control.json', n.encoded({'format': CONTROL, 'event_id': EVENT_ID,
            'admission': copied, 'original_admission': original, 'scope': scope, 'message': projected,
            'comparison_interpretation': LIMIT, 'native_writer_calls_added': 0, 'budget_renewed': False}))
        rebound = bind()
        require(rebound[1:] == (scope, message), 'scope changed immediately before append')
        for r in (copied, projected, control):
            require(file_ref(r['path']) == r, 'unpublished/incomplete intervention artifact')
        unchanged()
        event = {'sequence': 13, 'previous_sha256': scope['history'][-1]['sha256'], 'recorded_at': n._common.now(),
                 'kind': 'scripted_event', 'data': {'format': CONTROL, 'event_id': EVENT_ID,
                    'trigger': control, 'message': projected, 'control_admission': copied,
                    'comparison_interpretation': LIMIT, 'original_full_direction_released': False}}
        event_ref = _publish(root/'journal/000013.json', n.encoded(event))
        unchanged()
        return {'status': 'prospective_native_prefix_released', 'event': event_ref, 'message': projected,
                'technical_control': control, 'initial_used': 2, 'initial_cap': 5, 'remaining_initial': 3,
                'comparison_interpretation': LIMIT, 'automatic_retry': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--admission', required=True)
    parser.add_argument('--admission-sha256', required=True)
    parser.add_argument('--engineering-only', action='store_true')
    args = parser.parse_args()
    try:
        result = release(args.run, args.admission, args.admission_sha256, engineering=args.engineering_only)
    except Exception as exc:
        print(json.dumps({'status': 'refused_or_unknown', 'error_type': type(exc).__name__, 'error': str(exc),
                          'automatic_retry': False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
