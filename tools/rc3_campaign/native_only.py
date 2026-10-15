#!/usr/bin/env python3
"""Record fixed-Cyber-five native text. No Deck Master SDK, installation or gate.

Root transcribes actual native tool observations; a hash is not platform trust.
Every supplied original is frozen before observation parsing. Blind copies are
exact bytes, including all wrapping and recognizable native-format differences.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('_rc3_campaign_common', Path(__file__).with_name('controller.py'))
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)
CampaignError, Journal = _common.CampaignError, _common.Journal
digest, encoded, read = _common.digest, _common.encoded, _common.read
reference, check_ref, save, write_once = _common.reference, _common.check_ref, _common.save, _common.write_once
fresh, safe_name, OBSERVER_KIND = _common.fresh, _common.safe_name, _common.OBSERVER_KIND

VERSION = 'rc3-native-only-registration.v1'
COMMIT = '980e5576565f0673c67ee41b01d20ed66cb8417c'
BUDGET = {'initial_writer': 5, 'feedback': 1, 'repair_cycles': 1, 'repair_writer': 3}
ROLES = {'initial_writer', 'feedback', 'repair_writer', 'verification', 'post_comparison_writer', 'extra_writer', 'extra_review'}
WRITERS = {'initial_writer', 'repair_writer', 'post_comparison_writer', 'extra_writer'}
METHODS = {
    'references/source-analysis.md': (3647, '4501ee35ed24ec31e0f68d1527ae741cbe6fd47f77fbe75e25f7bf2cfe959cfb'),
    'references/storyline.md': (3977, '06df580e70ca770288421a8e8f35d237bb602d6df844ac710d31876196e42a51'),
    'references/visual-system.md': (26883, '5eedd3691ad181550ff5e6ffc45b8ae22ac924d0855242a3847aa78911d54c20'),
    'references/ppt-production.md': (51232, 'b4f9b9ae43519791b930a68aced3cb34cfc65b5c21ad5b165f7d68c2ca8e3e5a'),
    'references/quality-assurance.md': (35628, 'a26afa95716661d22ceb14aa6da92d999beb9364bfce9c5f99bcc84a97f74763'),
    'LICENSE': (1078, '7c97ba85605e44b15549678bf66e536bcce1783c22c942bad854561493ea5556'),
}


def validate(config):
    engineering = config.get('status') == 'ENGINEERING_ONLY_NOT_ADMITTED'
    if config.get('format') != VERSION or config.get('status') not in {'ADMITTED', 'ENGINEERING_ONLY_NOT_ADMITTED'}:
        raise CampaignError('freeze a separate native-only registration')
    if config.get('recorder_sha256') != digest(Path(__file__).read_bytes()) or config.get('common_utils_sha256') != digest(Path(_common.__file__).read_bytes()):
        raise CampaignError('recorder/common utility bytes changed; re-review and freeze a new registration')
    if config.get('budget') != BUDGET or config.get('arm') != 'E1-C':
        raise CampaignError('fixed native E1-C uses the same preregistered v3 budget')
    if any(key in config for key in ('installations', 'project', 'task_id', 'sdk_gate')):
        raise CampaignError('native C has no Deck Master installation, project, Task or gate')
    for key in ('protocol', 'input_identities', 'exposure_registry', 'admission_review'):
        check_ref(config[key])
    protocol = read(config['protocol']['path'])
    shared = protocol.get('shared_conditions', {})
    if (not protocol.get('format', '').endswith('.v3') or shared.get('initial_substantive_stages_cap') != 5
            or shared.get('independent_content_feedback_cap') != 1 or shared.get('autonomous_substantive_repair_cap') != 1
            or shared.get('necessary_repair_layer_cap') != 3):
        raise CampaignError('pin the same actual v3 common content protocol and budgets')
    cyber = read(config['input_identities']['path'])['cyberppt']
    rows = cyber['five_complete_references_and_MIT']
    if cyber['fixed_commit'] != COMMIT or cyber['references_total_bytes'] != 121367 or len(rows) != 6:
        raise CampaignError('fixed Cyber five-method identity differs')
    if {r['relative_path']: (r['bytes'], r['sha256']) for r in rows} != METHODS:
        raise CampaignError('use the five full pinned files and original MIT bytes, never excerpts')
    for row in rows:
        check_ref(row)
    exposure = read(config['exposure_registry']['path'])
    if exposure.get('status') != 'FROZEN' or not exposure.get('excluded_identities'):
        raise CampaignError('freeze preparer/answer/author exclusions before any native Writer')
    if engineering and set(config['cases']) != {'GENTRY'}:
        raise CampaignError('synthetic engineering can expose only neutral GENTRY')
    for case, spec in config['cases'].items():
        if case not in {'Q1', 'Q2', 'GENTRY'}:
            raise CampaignError('this fixed E1-C recorder supports the registered Q1/Q2 comparison only')
        for ref in [spec['brief'], *spec['materials'], *config['role_instructions'].values()]:
            check_ref(ref)
        for event in spec.get('events', {}).values():
            check_ref(event['message'])
    if set(config.get('observable_configuration', {})) != {'model', 'seed', 'price', 'tokens', 'invocation_parameters'}:
        raise CampaignError('record actual observable configuration, using null for unknown fields')
    return config


def freeze(config_path, root):
    config = validate(read(config_path))
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    save(root / 'registration.json', config)
    save(root / 'registration-origin.json', reference(config_path))
    Journal(root).append('native_registration_frozen', {'assurance': 'local_byte_integrity_only', 'model_execution': 'NOT_RUN'})
    return {'campaign': str(root), 'status': config['status']}


def init(campaign, root, case, repetition):
    config = validate(read(Path(campaign) / 'registration.json'))
    if case not in config['cases'] or repetition not in (1, 2) or (case == 'GENTRY' and repetition != 1):
        raise CampaignError('case/repetition was not registered')
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    state = {'campaign': str(Path(campaign).resolve()), 'registration_sha256': digest(encoded(config)),
             'arm': 'E1-C', 'case': case, 'repetition': repetition, 'budget': config['budget']}
    save(root / 'run.json', state)
    Journal(root).append('native_workflow_initialized', state)
    return state


def load(root):
    journal = Journal(root); state = read(journal.root / 'run.json')
    config = validate(read(Path(state['campaign']) / 'registration.json'))
    if digest(encoded(config)) != state['registration_sha256']:
        raise CampaignError('native registration changed after initialization')
    journal.events()
    return journal, state, config


def events(journal, kind):
    return [e['data'] for e in journal.events() if e['kind'] == kind]


def copy_ref(ref, target):
    check_ref(ref)
    return write_once(target, Path(ref['path']).read_bytes())


def snapshot_ref(journal, name):
    return read(journal.root / 'snapshots' / (safe_name(name) + '.json'))


def role_policy(journal, role):
    if role not in ROLES:
        raise CampaignError('unregistered native role')
    if role == 'initial_writer' and events(journal, 'feedback_delivered'):
        raise CampaignError('post-feedback work cannot be relabeled initial writing')
    if role in {'initial_writer', 'repair_writer'} and events(journal, 'verification_started'):
        raise CampaignError('read-only closure feedback cannot initiate another comparison repair')
    if role == 'feedback':
        snapshot_ref(journal, 'original_complete')
        if events(journal, 'feedback_delivered'):
            raise CampaignError('only one substantive feedback is delivered')
    if role == 'repair_writer' and not events(journal, 'repair_begun'):
        raise CampaignError('single real feedback and necessary-layer record are required')
    if role == 'verification':
        snapshot_ref(journal, 'repaired_complete')
    if role.startswith('extra_') and not events(journal, 'extra_work_begun'):
        raise CampaignError('declare extra work separately before preparing it')
    if role == 'post_comparison_writer':
        if read(journal.root / 'run.json')['case'] != 'Q2':
            raise CampaignError('the preregistered later five-minute change belongs only to Q2')
        snapshot_ref(journal, 'equal_budget_evaluated')
        if not any(e['event_id'] == 'Q2-change-5min' for e in events(journal, 'scripted_event')):
            raise CampaignError('Q2 later change requires the frozen comparison timepoint and actual event')


def prepare(journal, state, config, stage, role):
    stage = safe_name(stage); role_policy(journal, role)
    target = journal.root / 'stages' / stage; target.mkdir(parents=True, exist_ok=False)
    copied = []
    case = config['cases'][state['case']]
    for index, ref in enumerate([case['brief'], *case['materials']]):
        copied.append(copy_ref(ref, target / 'inputs' / f'{index:03d}-{Path(ref["path"]).name}'))
    copy_ref(config['role_instructions'][role], target / 'role-instruction.txt')
    cyber = read(config['input_identities']['path'])['cyberppt']
    methods = []
    for row in cyber['five_complete_references_and_MIT']:
        actual = copy_ref(row, target / 'methods' / row['relative_path'])
        methods.append({**actual, 'relative_path': row['relative_path']})
    # Only released events and permitted local work enter the packet. No answer bank.
    for index, event in enumerate(events(journal, 'scripted_event')):
        copy_ref(event['message'], target / 'released-events' / f'{index:03d}.txt')
    permitted = WRITERS if role in {'feedback', 'verification', 'extra_review'} else WRITERS - {'extra_writer', 'post_comparison_writer'}
    for result in events(journal, 'native_observed'):
        if result['role'] in permitted:
            copy_ref(result['raw'], target / 'prior-author-originals' / f'{result["ordinal"]:04d}')
    if role in {'repair_writer', 'verification'}:
        copy_ref(events(journal, 'feedback_delivered')[0]['raw'], target / 'single-feedback.txt')
        save(target / 'repair-scope.json', events(journal, 'repair_begun')[0])
    if role == 'verification':
        copy_ref(snapshot_ref(journal, 'repaired_complete')['diff'], target / 'repair.diff')
        save(target / 'closure-basis.json', {'original': snapshot_ref(journal, 'original_complete')['raw'],
             'repaired': snapshot_ref(journal, 'repaired_complete')['raw'],
             'single_feedback': events(journal, 'feedback_delivered')[0]['raw'],
             'repair_diff': snapshot_ref(journal, 'repaired_complete')['diff']})
    inventory = {str(p.relative_to(target)): reference(p) for p in sorted(target.rglob('*')) if p.is_file()}
    packet = {'stage': stage, 'role': role, 'case': state['case'], 'arm': 'E1-C', 'files': inventory,
              'method_bundle_sha256': digest(encoded([[m['relative_path'], m['sha256']] for m in methods])),
              'method_files': methods, 'format': 'native-text-no-dm-schema',
              'unknown_configuration': config['observable_configuration'],
              'boundaries': ['No other arms, private oracles, answer banks, old FINALs or delegation.',
                             'Read the full five pinned methods. Return original native text.',
                             'Verification is read-only and is never delivered to Writer.'],
              'human': 'NOT_RUN_USER_DEFERRED'}
    packet_ref = save(target / 'packet.json', packet)
    journal.append('stage_prepared', {'stage': stage, 'role': role, 'packet': packet_ref})
    return packet_ref


def observation(record, config):
    synthetic = config['status'] == 'ENGINEERING_ONLY_NOT_ADMITTED'
    expected = 'SYNTHETIC_ENGINEERING_ONLY' if synthetic else 'ROOT_ACTUAL_NATIVE'
    if record.get('evidence_kind') != expected or record.get('observation_kind') != OBSERVER_KIND or record.get('assurance') != 'host_attested':
        raise CampaignError('only Root actual native observations are allowed; engineering fixtures cannot be admitted')
    fresh(record['observed_at_utc'])


def begin(journal, config, stage, path):
    packet_ref = reference(journal.root / 'stages' / safe_name(stage) / 'packet.json')
    packet = read(packet_ref['path']); role_policy(journal, packet['role'])
    for ref in packet['files'].values():
        check_ref(ref)
    record = read(path); observation(record, config)
    if record.get('packet_sha256') != packet_ref['sha256']:
        raise CampaignError('Root invocation must bind the exact native-only packet')
    spawn = record['spawn']; executor = spawn['canonical_task_name']
    previous = events(journal, 'native_begun'); same = [e for e in previous if e['executor'] == executor]
    excluded = set(read(config['exposure_registry']['path'])['excluded_identities'])
    if not executor.startswith('/root/') or spawn.get('returned_task_name') != executor or executor in excluded or set(spawn.get('inherited_identities', [])) & excluded:
        raise CampaignError('executor identity is excluded or disagrees with actual returned identity')
    role = packet['role']
    if spawn.get('tool') == 'collaboration.spawn_agent':
        if spawn.get('fork_turns') != 'none' or same:
            raise CampaignError('fresh native execution requires actual fork_turns=none')
    elif spawn.get('tool') == 'collaboration.followup_task':
        allowed = (WRITERS if role in {'post_comparison_writer', 'extra_writer'} else
                   {'feedback', 'verification', 'extra_review'} if role == 'extra_review' else
                   {role} | ({'initial_writer'} if role == 'repair_writer' else {'feedback'} if role == 'verification' else set()))
        if not same or any(e['role'] not in allowed for e in same):
            raise CampaignError('followup cannot inherit another workflow responsibility')
    else:
        raise CampaignError('record actual spawn/followup, never an invented model invocation')
    if role not in WRITERS and any(e['executor'] == executor and e['role'] in WRITERS for e in previous):
        raise CampaignError('an author cannot review its own manuscript')
    if role in WRITERS and any(e['executor'] == executor and e['role'] not in WRITERS for e in previous):
        raise CampaignError('reviewer cannot become comparison Writer')
    used = sum(e['role'] == role for e in previous); cap = BUDGET.get(role)
    ordinal = len(previous) + 1
    data = {'ordinal': ordinal, 'stage': stage, 'role': role, 'executor': executor,
            'packet': packet_ref, 'within_budget': cap is None or used < cap,
            'role_ordinal': used + 1, 'cap': cap, 'actual_cost': None,
            'evidence_kind': record['evidence_kind'], 'invocation': reference(path)}
    copy_ref(data['invocation'], journal.root / 'executions' / f'{ordinal:04d}' / 'root-invocation.json')
    journal.append('native_begun', data)
    if role == 'verification':
        journal.append('verification_started', {'ordinal': ordinal})
    return data


def execution(journal, ordinal):
    found = [e for e in events(journal, 'native_begun') if e['ordinal'] == ordinal]
    if len(found) != 1:
        raise CampaignError('no unique recorded actual native execution')
    return found[0], journal.root / 'executions' / f'{ordinal:04d}'


def method_read(journal, ordinal, executor):
    invocation, target = execution(journal, ordinal)
    if executor != invocation['executor']:
        raise CampaignError('method read must match Root observed executor')
    check_ref(invocation['packet']); packet = read(invocation['packet']['path'])
    for ref in packet['files'].values():
        check_ref(ref)
    rows = []
    for ref in packet['method_files']:
        check_ref(ref)
        rows.append({**ref, 'content': Path(ref['path']).read_bytes().decode('utf-8')})
    result = {'executor': executor, 'ordinal': ordinal, 'packet': invocation['packet'], 'files': rows,
              'method_bundle_sha256': packet['method_bundle_sha256'],
              'scope': 'Full bytes returned; actual native read/application separately Root observed.'}
    ref = save(target / 'method-read.json', result)
    journal.append('method_bytes_returned', {'ordinal': ordinal, 'record': ref})
    return result


def observe(journal, config, ordinal, result_path, result_sha, observation_path, observation_sha):
    invocation, target = execution(journal, ordinal)
    # No result parser or view exists before these exclusive immutable raw writes.
    raw = write_once(target / 'raw-native-output', Path(result_path).read_bytes())
    obs = write_once(target / 'raw-root-completion.json', Path(observation_path).read_bytes())
    journal.append('native_output_frozen', {'ordinal': ordinal, 'raw': raw, 'observation': obs})
    try:
        if raw['sha256'] != result_sha or obs['sha256'] != observation_sha:
            raise CampaignError('observed original hash differs')
        record = read(obs['path']); observation(record, config); completed = record['completion']
        check_ref(invocation['packet'])
        for ref in read(invocation['packet']['path'])['files'].values():
            check_ref(ref)
        method = reference(target / 'method-read.json')
        if (record.get('packet_sha256') != invocation['packet']['sha256'] or record.get('method_read_record_sha256') != method['sha256']
                or record.get('model_output_bytes_sha256') != raw['sha256'] or record.get('all_method_bytes_read') is not True
                or completed.get('sender') != invocation['executor'] or completed.get('message_type') != 'FINAL_ANSWER'
                or completed.get('status_observation_tool') != 'collaboration.list_agents'
                or completed.get('observed_status') != 'completed' or invocation['executor'] not in completed.get('observed_completed_agents', [])
                or not completed.get('raw_final_message') or completed['raw_final_message'].encode('utf-8') != Path(raw['path']).read_bytes()):
            raise CampaignError('full native FINAL/completed/output/packet/method-read binding disagrees')
        kind = record.get('native_output_kind')
        if kind not in {'question', 'partial_manuscript', 'complete_manuscript', 'review'}:
            raise CampaignError('Root must preserve the actual native output kind')
        data = {**invocation, 'raw': raw, 'observation': obs, 'native_output_kind': kind,
                'assurance': 'synthetic_engineering_only' if config['status'] != 'ADMITTED' else 'host_attested'}
        save(target / 'observed.json', data)
    except Exception as exc:
        journal.append('native_observation_refused', {'ordinal': ordinal, 'error': str(exc)})
        raise
    journal.append('native_observed', data)
    return data


def observed(journal, ordinal):
    invocation, target = execution(journal, ordinal); data = read(target / 'observed.json')
    for ref in (data['raw'], data['observation'], invocation['packet']):
        check_ref(ref)
    if not invocation['within_budget']:
        raise CampaignError('over-budget raw is preserved, but excluded from comparison snapshots/feedback')
    return data


def snapshot(journal, name, ordinal):
    if name not in {'original_complete', 'repaired_complete', 'equal_budget_evaluated', 'owner_later', 'extra_work'}:
        raise CampaignError('unregistered native timepoint')
    data = observed(journal, ordinal)
    if data['native_output_kind'] != 'complete_manuscript' or data['role'] not in WRITERS:
        raise CampaignError('snapshot requires an actual complete native author manuscript')
    if name == 'original_complete' and (data['role'] != 'initial_writer' or events(journal, 'feedback_delivered')):
        raise CampaignError('freeze the original before substantive feedback')
    if name == 'repaired_complete' and (not events(journal, 'repair_begun') or data['role'] != 'repair_writer'):
        raise CampaignError('repaired timepoint requires the actual single repair')
    if name in {'repaired_complete', 'equal_budget_evaluated'} and events(journal, 'repair_begun'):
        if data['role'] != 'repair_writer':
            raise CampaignError('comparison repair must retain its actual repaired manuscript')
    if name == 'equal_budget_evaluated':
        if not events(journal, 'feedback_delivered') or any(e['role'].startswith('extra_') or e['role'] == 'post_comparison_writer' or not e['within_budget'] for e in events(journal, 'native_begun')):
            raise CampaignError('comparison evaluation needs the single feedback and no extra/over-budget writing')
        if events(journal, 'repair_begun'):
            repaired = snapshot_ref(journal, 'repaired_complete')
            if repaired['raw']['sha256'] != data['raw']['sha256'] or not any(e['role'] == 'verification' and e['native_output_kind'] == 'review' for e in events(journal, 'native_observed')):
                raise CampaignError('separate independent read-only closure verification is missing')
    if name in {'original_complete', 'equal_budget_evaluated'} and data['role'] not in {'initial_writer', 'repair_writer'}:
        raise CampaignError('later work cannot replace comparison drafts')
    if name == 'extra_work' and data['role'] != 'extra_writer':
        raise CampaignError('extra snapshot must name an actual separately recorded extra author execution')
    if name == 'owner_later':
        snapshot_ref(journal, 'equal_budget_evaluated')
        if data['role'] not in {'post_comparison_writer', 'extra_writer'}:
            raise CampaignError('later Owner work is separate from comparison writing; no human acceptance is implied')
    raw = Path(data['raw']['path']).read_bytes()
    blind = write_once(journal.root / 'blind-exact-copies' / name, raw)
    record = {'timepoint': name, 'ordinal': ordinal, 'raw': data['raw'], 'blind_exact_copy': blind,
              'byte_offset_map': [{'original_start': 0, 'view_start': 0, 'length': len(raw)}],
              'removed_bytes': 0, 'format_family_identifiability': 'POSSIBLE_DISCLOSED; native wrapping retained',
              'professional_quality': 'NOT_ASSERTED'}
    if name == 'equal_budget_evaluated':
        record['single_feedback'] = events(journal, 'feedback_delivered')[0]
        record['readonly_verifications'] = [e for e in events(journal, 'native_observed') if e['role'] == 'verification']
    if name == 'repaired_complete':
        original = snapshot_ref(journal, 'original_complete')['raw']; check_ref(original)
        diff = b''.join(difflib.diff_bytes(difflib.unified_diff, Path(original['path']).read_bytes().splitlines(keepends=True), raw.splitlines(keepends=True), fromfile=b'original-native', tofile=b'repaired-native'))
        record['diff'] = write_once(journal.root / 'repair.diff', diff)
        record['original_raw'] = original
    ref = save(journal.root / 'snapshots' / (name + '.json'), record)
    journal.append('snapshot_frozen', {'name': name, 'snapshot': ref})
    return record


def feedback(journal, ordinal):
    data = observed(journal, ordinal); snapshot_ref(journal, 'original_complete')
    if data['role'] != 'feedback' or data['native_output_kind'] != 'review' or events(journal, 'feedback_delivered'):
        raise CampaignError('deliver one actual independent feedback only')
    journal.append('feedback_delivered', {'ordinal': ordinal, 'raw': data['raw'], 'executor': data['executor']})
    return {'status': 'single_native_feedback_frozen', 'raw': data['raw']}


def repair(journal, config, path):
    feedbacks = events(journal, 'feedback_delivered'); record = read(path); observation(record, config)
    layers = record.get('necessary_layers', [])
    if len(feedbacks) != 1 or events(journal, 'repair_begun') or events(journal, 'verification_started'):
        raise CampaignError('one feedback permits at most one autonomous repair cycle')
    if not layers or len(set(layers)) != len(layers) or len(layers) > 3 or set(layers) - {'argument', 'page_copy', 'speech'}:
        raise CampaignError('declare only the one-to-three actual necessary content layers')
    raw = Path(feedbacks[0]['raw']['path']).read_bytes()
    locators = record.get('finding_byte_locators', [])
    if record.get('actual_defect_identified') is not True or not locators:
        raise CampaignError('Root must identify actual feedback findings, not manufacture repair work')
    for locator in locators:
        start, end = locator['start'], locator['end']
        if not 0 <= start < end <= len(raw) or digest(raw[start:end]) != locator['sha256']:
            raise CampaignError('repair necessity must quote exact byte-addressed single-feedback findings')
    journal.append('repair_begun', {'necessary_layers': layers, 'finding_byte_locators': locators,
                   'feedback_raw': feedbacks[0]['raw'], 'necessity': reference(path), 'repair_cycle': 1})
    return {'status': 'single_native_repair_begun', 'necessary_layers': layers}


def scripted_event(journal, state, config, event_id, path):
    event_id = safe_name(event_id); event = config['cases'][state['case']]['events'][event_id]
    trigger = read(path); observation(trigger, config)
    if event.get('planned_dispatch') is not True or trigger.get('event_id') != event_id or trigger.get('actual_trigger_satisfied') is not True or not trigger.get('actual_trigger_explanation'):
        raise CampaignError('only the exact preregistered event after its actual Root-observed trigger')
    if not trigger.get('source_observations'):
        raise CampaignError('actual trigger source observations are required')
    for ref in trigger['source_observations']:
        check_ref(ref)
    local_hashes = {r[key]['sha256'] for r in events(journal, 'native_observed') for key in ('raw', 'observation')}
    local_hashes.update(e['snapshot']['sha256'] for e in events(journal, 'snapshot_frozen'))
    if not any(ref['sha256'] in local_hashes for ref in trigger['source_observations']):
        raise CampaignError('trigger must bind this workflow actual native output/completion or frozen snapshot')
    for name in event.get('required_snapshots', []):
        snapshot_ref(journal, name)
    if any(e['event_id'] == event_id for e in events(journal, 'scripted_event')):
        raise CampaignError('event already released; no silent replacement or second answer')
    message = copy_ref(event['message'], journal.root / 'released-events' / (event_id + '.txt'))
    journal.append('scripted_event', {'event_id': event_id, 'trigger': reference(path), 'message': message})
    return {'status': 'exact_native_event_released', 'message': message}


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze-campaign'); p.add_argument('--registration', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('init')
    for key in ('campaign', 'out', 'case'):
        p.add_argument('--' + key, required=True)
    p.add_argument('--repetition', type=int, default=1)
    for command in ('prepare', 'begin-native', 'read-methods', 'observe', 'snapshot', 'deliver-feedback', 'repair-begin', 'scripted-event', 'declare-extra', 'status'):
        p = sub.add_parser(command); p.add_argument('--run', required=True)
        if command in {'prepare', 'begin-native'}:
            p.add_argument('--stage', required=True)
        if command in {'read-methods', 'observe', 'snapshot', 'deliver-feedback'}:
            p.add_argument('--ordinal', type=int, required=True)
        if command == 'prepare':
            p.add_argument('--role', choices=sorted(ROLES), required=True)
        if command == 'read-methods':
            p.add_argument('--executor', required=True)
        if command == 'begin-native':
            p.add_argument('--invocation', required=True)
        if command == 'observe':
            for key in ('result', 'result-sha256', 'observation', 'observation-sha256'):
                p.add_argument('--' + key, required=True)
        if command == 'snapshot':
            p.add_argument('--name', required=True)
        if command == 'repair-begin':
            p.add_argument('--necessity', required=True)
        if command == 'scripted-event':
            p.add_argument('--event-id', required=True); p.add_argument('--trigger', required=True)
        if command == 'declare-extra':
            p.add_argument('--evidence', required=True)
    args = parser.parse_args()
    if args.command == 'freeze-campaign':
        result = freeze(args.registration, args.out)
    elif args.command == 'init':
        result = init(args.campaign, args.out, args.case, args.repetition)
    else:
        journal, state, config = load(args.run)
        with journal.locked():
            if args.command == 'prepare': result = prepare(journal, state, config, args.stage, args.role)
            elif args.command == 'begin-native': result = begin(journal, config, args.stage, args.invocation)
            elif args.command == 'read-methods': result = method_read(journal, args.ordinal, args.executor)
            elif args.command == 'observe': result = observe(journal, config, args.ordinal, args.result, args.result_sha256, args.observation, args.observation_sha256)
            elif args.command == 'snapshot': result = snapshot(journal, args.name, args.ordinal)
            elif args.command == 'deliver-feedback': result = feedback(journal, args.ordinal)
            elif args.command == 'repair-begin': result = repair(journal, config, args.necessity)
            elif args.command == 'scripted-event': result = scripted_event(journal, state, config, args.event_id, args.trigger)
            elif args.command == 'declare-extra': result = journal.append('extra_work_begun', {'evidence': reference(args.evidence), 'comparison_budget': 'EXCLUDED'})
            else: result = {'state': state, 'events': journal.events(), 'professional_quality': 'NOT_ASSERTED'}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
