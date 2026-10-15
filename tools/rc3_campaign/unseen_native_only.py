#!/usr/bin/env python3
"""Standalone unseen C native recorder. No SDK, content authoring or oracle IO.

Root observations are host_attested, not platform signatures. Engineering
fixtures never become actual native evidence. Original FINAL bytes are immutable;
metadata, completeness declarations and semantic judgments remain separate.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

COMMON_SHA = 'd0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261'
_path = Path(__file__).with_name('controller.py')
if hashlib.sha256(_path.read_bytes()).hexdigest() != COMMON_SHA:
    raise ValueError('unseen recorder requires exact d0 mechanical utilities')
_spec = importlib.util.spec_from_file_location('_unseen_mechanical_common', _path)
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)
CampaignError, Journal = c.CampaignError, c.Journal
digest, encoded = c.digest, c.encoded
save, write_once, safe_name = c.save, c.write_once, c.safe_name

FORMAT = 'rc3-unseen-native-registration.v1'
CASES = ('U-LIVE-01', 'U-READ-01')
SLOTS = tuple(f'{case}-{arm}' for case in CASES for arm in ('A', 'B', 'C'))
BUDGET = {'initial_writer': 5, 'feedback': 1, 'repair_cycles': 1, 'repair_writer': 3, 'verification': 1}
ROLES = {'initial_writer', 'feedback', 'repair_writer', 'verification', 'extra_writer', 'extra_review'}
WRITERS = {'initial_writer', 'repair_writer', 'extra_writer'}
COMMIT = '980e5576565f0673c67ee41b01d20ed66cb8417c'
METHODS = {
    'references/source-analysis.md': (3647, '4501ee35ed24ec31e0f68d1527ae741cbe6fd47f77fbe75e25f7bf2cfe959cfb'),
    'references/storyline.md': (3977, '06df580e70ca770288421a8e8f35d237bb602d6df844ac710d31876196e42a51'),
    'references/visual-system.md': (26883, '5eedd3691ad181550ff5e6ffc45b8ae22ac924d0855242a3847aa78911d54c20'),
    'references/ppt-production.md': (51232, 'b4f9b9ae43519791b930a68aced3cb34cfc65b5c21ad5b165f7d68c2ca8e3e5a'),
    'references/quality-assurance.md': (35628, 'a26afa95716661d22ceb14aa6da92d999beb9364bfce9c5f99bcc84a97f74763'),
    'LICENSE': (1078, '7c97ba85605e44b15549678bf66e536bcce1783c22c942bad854561493ea5556'),
}


def require(condition, message):
    if not condition:
        raise CampaignError(message)


def readable(path):
    path = Path(path).resolve(strict=True)
    require(not any(p.lower() in {'private', 'oracle', 'oracle.json', 'private-oracle.json'} for p in path.parts),
            'recorder never opens private/oracle paths')
    return path


def read(path):
    return c.read(readable(path))


def reference(path):
    return c.reference(readable(path))


def check_ref(ref):
    readable(ref['path'])
    return c.check_ref(ref)


def checked(ref):
    check_ref(ref)
    return read(ref['path'])


def invocation_identity(ref):
    spawn = checked(ref).get('spawn', {})
    executor, turn = spawn.get('canonical_task_name'), spawn.get('native_turn_id')
    require(isinstance(executor, str) and executor.startswith('/root/')
            and spawn.get('returned_task_name') == executor and isinstance(turn, str) and turn.strip(),
            'observable executor/native_turn_id required; unknown identity cannot gain original credit')
    return executor, turn


def events(journal, kind):
    return [e['data'] for e in journal.events() if e['kind'] == kind]


def input_identity(config, case):
    spec = config['cases'][case]
    return digest(encoded([[r['sha256'], r['bytes']] for r in [spec['brief'], *spec['materials']]]))


def validate(config):
    allowed = {'format', 'status', 'campaign_id', 'recorder_sha256', 'common_utils_sha256', 'arm', 'budget',
               'protocol', 'admission_review', 'exposure_registry', 'cases', 'role_instructions', 'cyberppt',
               'barrier_methods', 'observable_configuration'}
    require(set(config) == allowed, 'exact native-only registration fields; no oracle/SDK/project/schema fields')
    require(config['format'] == FORMAT and config['status'] in {'ADMITTED', 'ENGINEERING_ONLY_NOT_ADMITTED'},
            'separate admitted or synthetic-engineering registration required')
    safe_name(config['campaign_id'])
    require(config['recorder_sha256'] == digest(Path(__file__).read_bytes())
            and config['common_utils_sha256'] == COMMON_SHA, 'pin exact new recorder and mechanical helper bytes')
    require(config['arm'] == 'E1-C' and config['budget'] == BUDGET, 'fixed unseen C5/1/1/3/verification1')
    for key in ('protocol', 'admission_review'):
        check_ref(config[key])
    exposure = checked(config['exposure_registry'])
    require(exposure.get('status') == 'FROZEN' and exposure.get('excluded_identities'), 'actual exposure exclusions required')
    require(set(config['cases']) == set(CASES), 'exact two unseen cases, never Q1 aliases')
    for spec in config['cases'].values():
        require(set(spec) == {'brief', 'materials'} and spec['materials'], 'only fixed legal brief/material allowlist')
        for ref in [spec['brief'], *spec['materials']]:
            check_ref(ref)
    require(set(config['role_instructions']) == ROLES, 'each role needs its own exact nonnull instruction')
    for ref in config['role_instructions'].values():
        require(check_ref(ref)['bytes'] > 0, 'empty role instruction')
    cyber = config['cyberppt']
    require(set(cyber) == {'fixed_commit', 'files'} and cyber['fixed_commit'] == COMMIT, 'fixed Cyber reference commit')
    rows = cyber['files']
    require(len(rows) == 6 and {r['relative_path']: (r['bytes'], r['sha256']) for r in rows} == METHODS,
            'five complete Cyber files and original MIT, not excerpts/DM methods')
    for row in rows:
        check_ref(row)
    require(set(config['barrier_methods']) == set(SLOTS), 'register exact six case/arm method identities')
    for ref in config['barrier_methods'].values():
        check_ref(ref)
    for case in CASES:
        require(checked(config['barrier_methods'][case + '-C']) == cyber, 'C method identity must be its exact full Cyber bundle')
    require(set(config['observable_configuration']) == {'model', 'seed', 'tokens', 'price', 'invocation_parameters'},
            'observable configuration explicit; unknown values null')
    return config


def freeze(path, root):
    config = validate(read(path))
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    save(root / 'registration.json', config)
    save(root / 'registration-origin.json', reference(path))
    Journal(root).append('registration_frozen', {'assurance': 'local_integrity_only', 'native': 'NOT_RUN'})
    return {'campaign': str(root), 'status': config['status']}


def campaign(root):
    journal = Journal(root)
    return journal, validate(read(journal.root / 'registration.json'))


def init(root, out, case):
    cj, config = campaign(root)
    require(case in CASES, 'exact unseen case only')
    with cj.locked():
        require(not any(e['case'] == case for e in events(cj, 'run_initialized')), 'case already has its unique C run; no reset')
        target = Path(out).resolve()
        target.mkdir(parents=True, exist_ok=False)
        state = {'campaign': str(cj.root), 'run_root': str(target), 'case': case, 'arm': 'E1-C',
                 'registration_sha256': digest(encoded(config))}
        save(target / 'run.json', state)
        cj.append('run_initialized', state)
        Journal(target).append('run_initialized', state)
    return state


def load(root):
    journal = Journal(root)
    state = read(journal.root / 'run.json')
    cj, config = campaign(state['campaign'])
    require(state['run_root'] == str(journal.root) and state['case'] in CASES
            and state['registration_sha256'] == digest(encoded(config)), 'run copied or registration changed')
    require(state in events(cj, 'run_initialized'), 'unregistered run alias')
    journal.events()
    return journal, state, config


def observation(record, config):
    expected = 'ROOT_ACTUAL_NATIVE' if config['status'] == 'ADMITTED' else 'SYNTHETIC_ENGINEERING_ONLY'
    require(record.get('evidence_kind') == expected and record.get('observation_kind') == c.OBSERVER_KIND
            and record.get('assurance') == 'host_attested', 'Root host_attested observation, no synthetic upgrade')
    c.fresh(record['observed_at_utc'])


def snapshot_ref(journal, name):
    return read(journal.root / 'snapshots' / (safe_name(name) + '.json'))


def first_complete(journal):
    return next((e for e in events(journal, 'native_observed')
                 if e['role'] == 'initial_writer' and e['native_output_kind'] == 'complete_manuscript'), None)


def role_policy(journal, role):
    require(role in ROLES, 'unregistered native role')
    if role == 'initial_writer':
        require(first_complete(journal) is None and not events(journal, 'feedback_delivered'), 'first complete ends initial writing')
    if role in {'initial_writer', 'repair_writer'}:
        require(not events(journal, 'verification_started'), 'readonly closure cannot start a second Writer repair')
    if role == 'feedback':
        snapshot_ref(journal, 'original_complete')
        require(not events(journal, 'feedback_delivered'), 'only one public feedback')
    if role == 'repair_writer':
        require(events(journal, 'repair_begun'), 'one real necessary repair required')
        require(not any(e['role'] == 'repair_writer' and e['native_output_kind'] == 'complete_manuscript'
                        for e in events(journal, 'native_observed')), 'complete repair ends the single repair; no preferred later draft')
    if role == 'verification':
        snapshot_ref(journal, 'repaired_complete')
    if role.startswith('extra_'):
        require(events(journal, 'extra_work_declared'), 'extra work separately declared, never new allowance')


def copy_ref(ref, dest):
    check_ref(ref)
    return write_once(dest, Path(ref['path']).read_bytes())


def prepare(journal, state, config, stage, role):
    stage = safe_name(stage)
    role_policy(journal, role)
    cap = BUDGET.get(role)
    require(cap is None or sum(e['role'] == role for e in events(journal, 'native_begun')) < cap, 'role budget exhausted')
    target = journal.root / 'stages' / stage
    target.mkdir(parents=True, exist_ok=False)
    spec = config['cases'][state['case']]
    for i, ref in enumerate([spec['brief'], *spec['materials']]):
        copy_ref(ref, target / 'inputs' / f'{i:03d}')
    copy_ref(config['role_instructions'][role], target / 'role-instruction.txt')
    methods = []
    for ref in config['cyberppt']['files']:
        methods.append({**copy_ref(ref, target / 'methods' / ref['relative_path']), 'relative_path': ref['relative_path']})
    # Only own authors and the one delivered public feedback. Never closure/private/other arm.
    for e in events(journal, 'native_observed'):
        if e['role'] in {'initial_writer', 'repair_writer'}:
            copy_ref(e['raw'], target / 'prior-author-originals' / str(e['ordinal']))
    if role in {'repair_writer', 'verification'}:
        copy_ref(events(journal, 'feedback_delivered')[0]['raw'], target / 'single-feedback.txt')
        save(target / 'repair-scope.json', events(journal, 'repair_begun')[0])
    if role == 'verification':
        copy_ref(snapshot_ref(journal, 'repaired_complete')['diff'], target / 'repair.diff')
    packet = {'case': state['case'], 'arm': 'E1-C', 'stage': stage, 'role': role,
              'input_identity': input_identity(config, state['case']),
              'method_identity': config['barrier_methods'][state['case'] + '-C'],
              'method_files': methods, 'method_bundle_sha256': digest(encoded([[r['relative_path'], r['sha256']] for r in methods])),
              'files': {str(f.relative_to(target)): reference(f) for f in sorted(target.rglob('*')) if f.is_file()},
              'format': 'exact-native-text-no-DM-schema', 'observable_configuration': config['observable_configuration'],
              'verification': 'readonly, never delivered to Writer', 'human': 'NOT_RUN_USER_DEFERRED'}
    ref = save(target / 'packet.json', packet)
    journal.append('stage_prepared', {'stage': stage, 'role': role, 'packet': ref})
    return ref


def begin(journal, state, config, stage, path):
    packet_ref = reference(journal.root / 'stages' / safe_name(stage) / 'packet.json')
    packet = checked(packet_ref)
    record = read(path)
    observation(record, config)
    spawn = record['spawn']
    turn = spawn['native_turn_id']
    require(isinstance(turn, str) and turn and record.get('packet_sha256') == packet_ref['sha256'], 'exact actual turn/packet required')
    cj = Journal(state['campaign'])
    with cj.locked():
        previous = events(cj, 'native_begun')
        require(not any(e['native_turn_id'] == turn for e in previous), 'actual native turn already charged; no replay')
        local = events(journal, 'native_begun')
        require(local == [e for e in previous if e['run_root'] == state['run_root']],
                'incomplete cross-journal recording; preserve unknown charge, no automatic resend/reset')
        role, executor = packet['role'], spawn['canonical_task_name']
        same = [e for e in previous if e['executor'] == executor]
        count = sum(e['role'] == role for e in local)
        cap = BUDGET.get(role)
        data = {'ordinal': len(local) + 1, 'stage': stage, 'role': role, 'executor': executor,
                'native_turn_id': turn, 'run_root': state['run_root'], 'case': state['case'],
                'role_ordinal': count + 1, 'cap': cap, 'within_budget': cap is not None and count < cap,
                'packet': packet_ref, 'invocation': reference(path), 'actual_cost': None, 'eligible': True}
        try:
            role_policy(journal, role)
            for ref in packet['files'].values():
                check_ref(ref)
            excluded = checked(config['exposure_registry'])['excluded_identities']
            require(spawn.get('lineage_known') is True and isinstance(spawn.get('inherited_identities'), list)
                    and executor.startswith('/root/') and spawn.get('returned_task_name') == executor
                    and executor not in excluded and not set(spawn['inherited_identities']) & set(excluded), 'excluded/unknown executor lineage')
            if spawn.get('tool') == 'collaboration.spawn_agent':
                require(spawn.get('fork_turns') == 'none' and not same and not spawn['inherited_identities'], 'fresh fork none required')
            elif spawn.get('tool') == 'collaboration.followup_task':
                allowed = {'initial_writer', 'repair_writer'} if role in {'initial_writer', 'repair_writer'} else {'feedback', 'verification'}
                require(same and all(e['run_root'] == state['run_root'] and e['role'] in allowed for e in same),
                        'followup cannot cross case/author/reviewer responsibilities')
            else:
                raise CampaignError('actual spawn/followup observation required')
        except (CampaignError, KeyError, TypeError) as exc:
            data['eligible'] = False
            data['exclusion_reason'] = str(exc)
        copy_ref(data['invocation'], journal.root / 'executions' / f"{data['ordinal']:04d}" / 'root-invocation.json')
        cj.append('native_begun', data)
        journal.append('native_begun', data)
        if role == 'verification':
            journal.append('verification_started', {'ordinal': data['ordinal']})
    # Even actual excluded/over-budget turns remain charged and can collect raw.
    return data


def execution(journal, ordinal):
    rows = [e for e in events(journal, 'native_begun') if e['ordinal'] == ordinal]
    require(len(rows) == 1, 'unique actual recorded invocation required')
    return rows[0], journal.root / 'executions' / f'{ordinal:04d}'


def method_read(journal, ordinal, executor):
    invocation, dest = execution(journal, ordinal)
    require(invocation['eligible'] and executor == invocation['executor'], 'method read matches actual eligible executor')
    packet = checked(invocation['packet'])
    rows = []
    for ref in packet['method_files']:
        check_ref(ref)
        rows.append({**ref, 'content': Path(ref['path']).read_bytes().decode('utf-8')})
    result = {'executor': executor, 'ordinal': ordinal, 'packet': invocation['packet'], 'files': rows,
              'method_bundle_sha256': packet['method_bundle_sha256'],
              'scope': 'Full bytes returned; actual native read/application separately Root observed.'}
    ref = save(dest / 'method-read.json', result)
    journal.append('method_bytes_returned', {'ordinal': ordinal, 'record': ref})
    return result


def observe(journal, config, ordinal, result_path, result_sha, observation_path, observation_sha):
    invocation, dest = execution(journal, ordinal)
    raw = write_once(dest / 'raw-native-output', readable(result_path).read_bytes())
    obs = write_once(dest / 'raw-root-completion.json', readable(observation_path).read_bytes())
    journal.append('native_output_frozen', {'ordinal': ordinal, 'raw': raw, 'observation': obs})
    try:
        require(raw['sha256'] == result_sha and obs['sha256'] == observation_sha, 'original supplied hashes differ')
        record = checked(obs)
        observation(record, config)
        require(invocation['eligible'], 'actual excluded invocation retained, not accepted as comparison evidence')
        method = reference(dest / 'method-read.json')
        completed = record['completion']
        kind = record['native_output_kind']
        require(kind in {'question', 'partial_manuscript', 'complete_manuscript', 'review', 'refusal', 'unknown'}, 'actual output kind required')
        require(record.get('packet_sha256') == invocation['packet']['sha256']
                and record.get('method_read_record_sha256') == method['sha256']
                and record.get('model_output_bytes_sha256') == raw['sha256']
                and record.get('all_method_bytes_read') is True
                and completed.get('sender') == invocation['executor'], 'exact output/method read/packet/executor binding')
        final = completed.get('raw_final_message')
        require(final is None and kind == 'unknown' or isinstance(final, str) and final.encode('utf-8') == Path(raw['path']).read_bytes(),
                'entire original FINAL bytes must match, including prefix/fences/terminalLF')
        if kind != 'unknown':
            require(raw['bytes'] > 0, 'complete FINAL cannot be empty')
            require(completed.get('message_type') == 'FINAL_ANSWER'
                    and completed.get('status_observation_tool') == 'collaboration.list_agents'
                    and completed.get('observed_status') == 'completed'
                    and invocation['executor'] in completed.get('observed_completed_agents', []), 'actual FINAL/completed required')
        packet = checked(invocation['packet'])
        for ref in packet['files'].values():
            check_ref(ref)
        data = {**invocation, 'raw': raw, 'observation': obs, 'native_output_kind': kind,
                'evidence_kind': record['evidence_kind'],
                'assurance': 'host_attested' if config['status'] == 'ADMITTED' else 'synthetic_engineering_only',
                'semantic_completeness': 'Root declaration, not recorder judgment'}
        save(dest / 'observed.json', data)
    except Exception as exc:
        journal.append('native_observation_refused', {'ordinal': ordinal, 'error': str(exc)})
        raise
    journal.append('native_observed', data)
    return data


def observed(journal, ordinal):
    invocation, dest = execution(journal, ordinal)
    data = read(dest / 'observed.json')
    require(invocation['within_budget'] and invocation['eligible'], 'over-budget/excluded raw cannot enter equal-budget views')
    for ref in (data['raw'], data['observation'], invocation['packet']):
        check_ref(ref)
    return data


def snapshot(journal, name, ordinal):
    require(name in {'original_complete', 'repaired_complete', 'equal_budget_evaluated'}, 'registered native timepoint only')
    data = observed(journal, ordinal)
    require(data['native_output_kind'] == 'complete_manuscript', 'actual complete manuscript declaration required')
    if name == 'original_complete':
        require(data['role'] == 'initial_writer' and first_complete(journal)['ordinal'] == ordinal
                and not events(journal, 'feedback_delivered'), 'original is earliest observed complete, not a preferred later draft')
    if name == 'repaired_complete':
        require(data['role'] == 'repair_writer' and events(journal, 'repair_begun'), 'actual single repair required')
        first = next(e for e in events(journal, 'native_observed')
                     if e['role'] == 'repair_writer' and e['native_output_kind'] == 'complete_manuscript')
        require(first['ordinal'] == ordinal, 'repaired complete is the first actual full repair, not a preferred later draft')
    if name == 'equal_budget_evaluated':
        require(events(journal, 'feedback_delivered') and not any(not e['within_budget'] or not e['eligible']
                for e in events(journal, 'native_begun')), 'single feedback and no extra/overrun comparison')
        if events(journal, 'repair_begun'):
            repaired = snapshot_ref(journal, 'repaired_complete')
            require(repaired['ordinal'] == ordinal and any(e['role'] == 'verification' and e['native_output_kind'] == 'review'
                    and e['within_budget'] for e in events(journal, 'native_observed')), 'actual readonly postrepair closure required')
        else:
            require(snapshot_ref(journal, 'original_complete')['ordinal'] == ordinal, 'no-repair view must retain identical original invocation')
    raw = Path(data['raw']['path']).read_bytes()
    record = {'format': 'rc3-unseen-native-snapshot.v1', 'timepoint': name, 'ordinal': ordinal,
              'case': data['case'], 'arm': 'C', 'raw': data['raw'], 'observation': data['observation'],
              'blind_exact_copy': write_once(journal.root / 'blind-exact-copies' / name, raw),
              'byte_offset_map': [{'original_start': 0, 'view_start': 0, 'length': len(raw)}],
              'removed_bytes': 0, 'format_identifiability': 'POSSIBLE_DISCLOSED_NATIVE_WRAPPING_RETAINED',
              'professional_quality': 'NOT_ASSERTED'}
    if name == 'repaired_complete':
        original = snapshot_ref(journal, 'original_complete')['raw']
        check_ref(original)
        delta = b''.join(difflib.diff_bytes(difflib.unified_diff, Path(original['path']).read_bytes().splitlines(keepends=True),
                        raw.splitlines(keepends=True), fromfile=b'original', tofile=b'repaired'))
        record['diff'] = write_once(journal.root / 'repair.diff', delta)
    ref = save(journal.root / 'snapshots' / (name + '.json'), record)
    journal.append('snapshot_frozen', {'name': name, 'snapshot': ref})
    return record


def feedback(journal, ordinal):
    data = observed(journal, ordinal)
    snapshot_ref(journal, 'original_complete')
    require(data['role'] == 'feedback' and data['native_output_kind'] == 'review'
            and not events(journal, 'feedback_delivered'), 'one actual independent public feedback only')
    journal.append('feedback_delivered', {'ordinal': ordinal, 'raw': data['raw'], 'executor': data['executor']})
    return data['raw']


def repair(journal, config, path):
    record = read(path)
    observation(record, config)
    rows = events(journal, 'feedback_delivered')
    require(len(rows) == 1 and not events(journal, 'repair_begun') and not events(journal, 'verification_started'),
            'one necessary repair, never a second feedback/closure-driven loop')
    layers = record.get('necessary_layers', [])
    require(0 < len(layers) <= 3 and len(set(layers)) == len(layers)
            and set(layers) <= {'argument', 'page_copy', 'speech'}, 'one-to-three actual necessary content layers')
    locators = record.get('finding_byte_locators', [])
    raw = Path(rows[0]['raw']['path']).read_bytes()
    require(record.get('actual_defect_identified') is True and locators, 'no defect means no manufactured repair')
    for item in locators:
        a, b = item['start'], item['end']
        require(type(a) is int and type(b) is int and 0 <= a < b <= len(raw)
                and digest(raw[a:b]) == item['sha256'], 'exact single-feedback finding byte locators required')
    data = {'necessary_layers': layers, 'finding_byte_locators': locators, 'feedback_raw': rows[0]['raw'],
            'necessity': reference(path), 'repair_cycle': 1}
    journal.append('repair_begun', data)
    return data


def bind_original(cj, config, slot, proof_path):
    require(slot in SLOTS, 'exact six initial slots only')
    require(not events(cj, 'private_evaluation_opened'), 'private evaluation already opened')
    require(not any(e['slot'] == slot for e in events(cj, 'original_bound')), 'original slot cannot be replaced')
    proof = read(proof_path)
    require(set(proof) == {'slot', 'input_identity', 'method_identity', 'original_snapshot', 'lineage_read_execution',
                          'evidence_kind', 'observation_kind', 'assurance', 'observed_at_utc'}, 'exact original proof fields, no oracle/schema payload')
    observation(proof, config)
    case, arm = slot.rsplit('-', 1)
    require(proof.get('slot') == slot and proof.get('input_identity') == input_identity(config, case)
            and proof.get('method_identity') == config['barrier_methods'][slot], 'case/input/method identity mismatch')
    check_ref(proof['method_identity'])
    validated = [proof['method_identity'], proof['original_snapshot'], proof['lineage_read_execution']]
    snap = checked(proof['original_snapshot'])
    require(snap.get('timepoint') == 'original_complete', 'SDK accepted/qualified/later snapshot is not original native')
    if arm == 'C':
        run = next(e for e in events(cj, 'run_initialized') if e['case'] == case)
        journal, _, _ = load(run['run_root'])
        require(proof['original_snapshot'] == reference(journal.root / 'snapshots/original_complete.json')
                and snap['ordinal'] == first_complete(journal)['ordinal'], 'C proof must bind this exact earliest local original')
        raw_refs = [snap['raw']]
        invocation, dest = execution(journal, snap['ordinal'])
        prefix = [e for e in events(journal, 'native_begun') if e['ordinal'] <= snap['ordinal']]
        require(all(e['eligible'] and e['within_budget'] and e['role'] == 'initial_writer' for e in prefix),
                'original C prefix has unknown/excluded/extra execution; preserve it, no transfer barrier credit')
        authors = {e['executor'] for e in prefix}
        expected_completion = snap['observation']
        expected_invocation = invocation['invocation']
        expected_method = reference(dest / 'method-read.json')
        receipt_invocations = [expected_invocation]
    else:
        require(snap.get('format') == 'rc3-campaign-original-native-snapshot.v1', 'actual A/B original-native snapshot required')
        manifest = checked(snap['native_complete_manifest'])
        validated.append(snap['native_complete_manifest'])
        require(manifest.get('format') == 'rc3-native-complete-draft-manifest.v1'
                and manifest.get('complete_native_manuscript_observed') is True
                and manifest.get('assurance') == 'host_attested', 'A/B complete raw manifest required, not gate status')
        originals = snap['native_originals']
        require(originals and manifest['raw_stage_ordinals'] == [r['ordinal'] for r in originals], 'exact all native raw stages required')
        raw_refs = []
        authors = set()
        for item in originals:
            check_ref(item['raw'])
            completion = checked(item['observation'])
            expected_kind = 'ROOT_ACTUAL_NATIVE' if config['status'] == 'ADMITTED' else 'SYNTHETIC_ENGINEERING_ONLY'
            require(completion.get('evidence_kind') == expected_kind
                    and completion.get('observation_kind') == c.OBSERVER_KIND
                    and completion.get('assurance') == 'host_attested', 'A/B synthetic evidence cannot upgrade to actual native')
            require(completion.get('model_output_bytes_sha256') == item['raw']['sha256']
                    and completion.get('all_method_bytes_read') is True, 'A/B exact raw/completion/method-read binding')
            final = completion['completion']
            require(final.get('sender', '').startswith('/root/') and final.get('message_type') == 'FINAL_ANSWER'
                    and final.get('observed_status') == 'completed'
                    and final.get('status_observation_tool') == 'collaboration.list_agents'
                    and final['sender'] in final.get('observed_completed_agents', []), 'A/B actual completed FINAL required')
            text = final.get('raw_final_message')
            require(isinstance(text, str) and text.strip(), 'A/B nonempty full native FINAL carrier required')
            try:
                text.encode('utf-8')
            except UnicodeEncodeError as exc:
                raise CampaignError('A/B full native FINAL carrier must be UTF-8') from exc
            authors.add(final['sender'])
            raw_refs.append(item['raw'])
            validated.append(item['observation'])
        check_ref(manifest['completeness_source_observation'])
        require(manifest['completeness_source_observation'] in [r['observation'] for r in originals], 'complete declaration must be a frozen completion')
        expected_completion = manifest['completeness_source_observation']
        expected_invocation = None
        expected_method = None
    # Root supplies actual chronology/lineage sidecars, not a quality selection.
    lineage = checked(proof['lineage_read_execution'])
    observation(lineage, config)
    require(lineage.get('slot') == slot and lineage.get('earliest_complete_snapshot_sha256') == proof['original_snapshot']['sha256']
            and lineage.get('earlier_complete_snapshot_refs') == [] and lineage.get('lineage_known') is True,
            'first-complete chronology and actual known execution lineage required')
    for key in ('invocation', 'method_read', 'completion'):
        require(lineage.get(key), 'full invocation/read/completion sidecars required')
        check_ref(lineage[key])
        validated.append(lineage[key])
    require(set(lineage.get('author_identities', [])) == authors
            and lineage['completion'] == expected_completion, 'exact author lineage and completeness sidecar required')
    completion = checked(expected_completion)
    require(completion.get('method_read_record_sha256') == lineage['method_read']['sha256'], 'actual complete method-read sidecar differs')
    if arm == 'C':
        require(lineage['invocation'] == expected_invocation and lineage['method_read'] == expected_method,
                'C invocation/method sidecars must be this actual execution')
    else:
        receipts = lineage.get('stage_receipts', [])
        require([r['ordinal'] for r in receipts] == manifest['raw_stage_ordinals'], 'all selected A/B native stage execution/read receipts required')
        receipt_invocations = []
        for receipt, original in zip(receipts, originals):
            require(receipt['completion'] == original['observation'], 'stage receipt differs from actual original completion')
            for key in ('invocation', 'method_read', 'completion'):
                check_ref(receipt[key])
                validated.append(receipt[key])
            comp = checked(receipt['completion'])
            spawn = checked(receipt['invocation'])['spawn']
            require(comp.get('method_read_record_sha256') == receipt['method_read']['sha256']
                    and spawn.get('canonical_task_name') == comp['completion']['sender']
                    and spawn.get('returned_task_name') == comp['completion']['sender'], 'A/B stage execution/read binding differs')
            receipt_invocations.append(receipt['invocation'])
        require(any(r['invocation'] == lineage['invocation'] and r['method_read'] == lineage['method_read']
                    and r['completion'] == lineage['completion'] for r in receipts), 'summary sidecars must be actual completeness stage')
    require(not authors & set(checked(config['exposure_registry'])['excluded_identities']), 'excluded author in original proof')
    previous_invocations = {invocation_identity(r) for e in events(cj, 'original_bound') for r in e['invocations']}
    identities = [invocation_identity(r) for r in receipt_invocations]
    require(not previous_invocations & set(identities), 'same actual invocation cannot fill another slot')
    record = {'slot': slot, 'proof': reference(proof_path), 'snapshot': proof['original_snapshot'],
              'raw_originals': raw_refs, 'lineage': proof['lineage_read_execution'],
              'validated_refs': validated, 'author_identities': sorted(authors), 'invocations': receipt_invocations,
              'invocation_identities': [{'executor': executor, 'native_turn_id': turn} for executor, turn in identities]}
    cj.append('original_bound', record)
    return record


def barrier(cj):
    bound = events(cj, 'original_bound')
    for row in bound:
        for ref in [row['proof'], *row['validated_refs'], *row['raw_originals']]:
            check_ref(ref)
    present = {r['slot'] for r in bound}
    contaminated = bool(events(cj, 'premature_private_evaluation'))
    return {'slots': list(SLOTS), 'missing': sorted(set(SLOTS) - present),
            'ready': present == set(SLOTS) and not contaminated, 'contaminated': contaminated,
            'oracle_read_by_recorder': False}


def open_private(cj, config, observation_path, audit_path):
    # Record an attempted early release permanently; later bindings cannot wash it.
    root = read(observation_path)
    observation(root, config)
    if root.get('private_evaluation_before_initial_barrier') is True:
        cj.append('premature_private_evaluation', {'observation': reference(observation_path), 'reported_afterward': True})
    status = barrier(cj)
    if not status['ready']:
        kind = 'premature_private_evaluation' if root.get('private_evaluation_already_occurred') is True else 'private_open_refused'
        cj.append(kind, {'observation': reference(observation_path), 'barrier': status})
        raise CampaignError('all six originals required; actual premature evaluation remains contaminated')
    audit = read(audit_path)
    observation(audit, config)
    excluded = checked(config['exposure_registry'])['excluded_identities']
    authors = {a for row in events(cj, 'original_bound') for a in row['author_identities']}
    require(audit.get('barrier_slots') == list(SLOTS) and audit.get('all_originals_checked') is True
            and audit.get('independent_nonauthor') is True and audit.get('reviewer', '').startswith('/root/')
            and audit.get('reviewer') not in excluded and audit.get('reviewer') not in authors
            and audit.get('reviewer') not in {e['executor'] for e in events(cj, 'native_begun')}
            and audit.get('original_proof_sha256s') == [e['proof']['sha256'] for e in events(cj, 'original_bound')],
            'actual independent barrier audit bound to exact six proofs required')
    invocation = checked(audit['native_invocation'])
    completion = checked(audit['native_completion'])
    for sidecar in (invocation, completion):
        require(sidecar.get('evidence_kind') == audit['evidence_kind']
                and sidecar.get('observation_kind') == c.OBSERVER_KIND and sidecar.get('assurance') == 'host_attested',
                'audit native evidence class cannot be upgraded from synthetic')
    check_ref(audit['audit_raw'])
    spawn, final = invocation['spawn'], completion['completion']
    require(spawn.get('tool') == 'collaboration.spawn_agent' and spawn.get('fork_turns') == 'none'
            and spawn.get('canonical_task_name') == audit['reviewer'] and spawn.get('returned_task_name') == audit['reviewer']
            and spawn.get('inherited_identities') == [] and final.get('sender') == audit['reviewer']
            and final.get('message_type') == 'FINAL_ANSWER' and final.get('observed_status') == 'completed'
            and final.get('status_observation_tool') == 'collaboration.list_agents'
            and audit['reviewer'] in final.get('observed_completed_agents', [])
            and isinstance(final.get('raw_final_message'), str)
            and final['raw_final_message'].encode('utf-8') == Path(audit['audit_raw']['path']).read_bytes(),
            'actual fresh independent audit invocation/fullFINAL/completion required, not reviewer boolean')
    require(not events(cj, 'private_evaluation_opened'), 'private barrier already opened')
    data = {'Root_observation': reference(observation_path), 'independent_audit': reference(audit_path),
            'audit_evidence': {k: audit[k] for k in ('native_invocation', 'native_completion', 'audit_raw')}, 'barrier': status,
            'external_native_audit': {'count': 1, 'actual_cost': None,
                                      'attribution': 'actual external barrier audit; not a C Writer/feedback budget refresh'},
            'assurance': 'host_attested', 'oracle': 'NOT_RECEIVED_OR_READ; Root separately dispatches eligible judges'}
    cj.append('private_evaluation_opened', data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('freeze-campaign'); p.add_argument('--registration', required=True); p.add_argument('--out', required=True)
    p = sub.add_parser('init'); p.add_argument('--campaign', required=True); p.add_argument('--out', required=True)
    p.add_argument('--case', choices=CASES, required=True)
    for command in ('bind-original-slot', 'inspect-initial-barrier', 'open-private-evaluation'):
        p = sub.add_parser(command); p.add_argument('--campaign', required=True)
        if command == 'bind-original-slot':
            p.add_argument('--slot', choices=SLOTS, required=True); p.add_argument('--proof', required=True)
        if command == 'open-private-evaluation':
            p.add_argument('--Root-observation', dest='root_observation', required=True); p.add_argument('--independent-audit', required=True)
    for command in ('prepare', 'begin-native', 'read-methods', 'observe', 'snapshot', 'deliver-feedback', 'repair-begin', 'declare-extra', 'status'):
        p = sub.add_parser(command); p.add_argument('--run', required=True)
        if command in {'prepare', 'begin-native'}: p.add_argument('--stage', required=True)
        if command == 'prepare': p.add_argument('--role', choices=sorted(ROLES), required=True)
        if command == 'begin-native': p.add_argument('--invocation', required=True)
        if command in {'read-methods', 'observe', 'snapshot', 'deliver-feedback'}: p.add_argument('--ordinal', type=int, required=True)
        if command == 'read-methods': p.add_argument('--executor', required=True)
        if command == 'observe':
            for key in ('result', 'result-sha256', 'observation', 'observation-sha256'): p.add_argument('--' + key, required=True)
        if command == 'snapshot': p.add_argument('--name', required=True)
        if command in {'repair-begin', 'declare-extra'}: p.add_argument('--evidence', required=True)
    args = parser.parse_args()
    if args.command == 'freeze-campaign':
        result = freeze(args.registration, args.out)
    elif args.command == 'init':
        result = init(args.campaign, args.out, args.case)
    elif args.command in {'bind-original-slot', 'inspect-initial-barrier', 'open-private-evaluation'}:
        cj, config = campaign(args.campaign)
        with cj.locked():
            if args.command == 'bind-original-slot': result = bind_original(cj, config, args.slot, args.proof)
            elif args.command == 'open-private-evaluation': result = open_private(cj, config, args.root_observation, args.independent_audit)
            else: result = barrier(cj)
    else:
        journal, state, config = load(args.run)
        with journal.locked():
            if args.command == 'prepare': result = prepare(journal, state, config, args.stage, args.role)
            elif args.command == 'begin-native': result = begin(journal, state, config, args.stage, args.invocation)
            elif args.command == 'read-methods': result = method_read(journal, args.ordinal, args.executor)
            elif args.command == 'observe': result = observe(journal, config, args.ordinal, args.result, args.result_sha256,
                                                          args.observation, args.observation_sha256)
            elif args.command == 'snapshot': result = snapshot(journal, args.name, args.ordinal)
            elif args.command == 'deliver-feedback': result = feedback(journal, args.ordinal)
            elif args.command == 'repair-begin': result = repair(journal, config, args.evidence)
            elif args.command == 'declare-extra':
                observation(read(args.evidence), config)
                result = journal.append('extra_work_declared', {'evidence': reference(args.evidence), 'comparison_credit': False})
            else: result = {'state': state, 'events': journal.events(), 'quality': 'NOT_ASSERTED'}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
