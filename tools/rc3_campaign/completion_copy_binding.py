#!/usr/bin/env python3
"""Narrow public original binding for an admitted byte-identical completion copy.

The old recorder, proof, snapshot and manifest are never rewritten. No SDK,
native/model/image operation, oracle IO or private-opening entry is provided.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

RECORDER_SHA = 'c6e64132703e1b1eed77abdb2e3c52c4794435c7db091a82a5b59c0f4c032af3'
COMMON_SHA = 'd0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261'
SOURCE = Path(__file__).with_name('unseen_native_only.py')
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != RECORDER_SHA:
    raise RuntimeError('exact frozen unseen recorder required')
_spec = importlib.util.spec_from_file_location('s04_frozen_unseen', SOURCE)
u = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(u)
c = u.c
Error = u.CampaignError
FORMAT = 'rc3-completion-copy-admission.v1'
ACTION = 'bind_original_same_bytes_completion_copy_only'


def require(value, message):
    if not value:
        raise Error(message)


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute canonical public path required')
    require(not any('oracle' in part.lower() or part.lower() == 'private' for part in path.parts),
            'private/oracle path is never read')
    require(path.resolve(strict=True) == path, 'path aliases or symlinks refused')
    return path


def reference(path):
    return u.reference(canonical(path))


def check_ref(ref):
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256', 'bytes'}, 'exact file Ref required')
    path = canonical(ref['path'])
    require(type(ref['bytes']) is int and ref['bytes'] >= 0, 'actual byte length required')
    require(stat.S_ISREG(path.stat().st_mode) and path.stat().st_size == ref['bytes'], 'actual regular file/byte length differs')
    return u.check_ref(ref)


def checked(ref):
    check_ref(ref)
    return public_json(ref['path'])


def preflight_refs(value):
    """Guard nested file Ref paths before a frozen reader can follow them.

    Extra fields on old registration/method rows belong to their old schema;
    this preflight only applies our path/regular-file boundary, not a new one.
    It never opens a referenced body or treats opaque path strings as reads.
    """
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            path = canonical(value['path'])
            require(stat.S_ISREG(path.stat().st_mode), 'actual regular file required')
        for item in value.values():
            preflight_refs(item)
    elif isinstance(value, list):
        for item in value:
            preflight_refs(item)


def public_json(path):
    """Guard before opening, then guard all nested Refs before delegation."""
    path = canonical(path)
    require(stat.S_ISREG(path.stat().st_mode), 'actual regular file required')
    value = json.loads(path.read_bytes())
    preflight_refs(value)
    return value


def public_campaign(root):
    """Retain old validation on the same preflighted registration object.

    The frozen validator follows exposure and C method JSON. Preflight those
    nested objects too, before calling it, without changing the old helpers.
    Journal metadata can contain invocation Refs used by old uniqueness checks.
    """
    journal = u.Journal(canonical(root))
    config = public_json(journal.root / 'registration.json')
    checked(config['exposure_registry'])
    for case in u.CASES:
        checked(config['barrier_methods'][case + '-C'])
    paths = sorted((journal.root / 'journal').glob('*.json'))
    for path in paths:
        canonical(path)
    for path in paths:
        public_json(path)
    return journal, u.validate(config)


def copy_context(campaign, slot, proof_ref):
    """Read-only actual pair discovery, not authorization or a new first draft."""
    root = canonical(campaign)
    cj, config = public_campaign(root)
    require(slot in u.SLOTS and slot.rsplit('-', 1)[1] in {'A', 'B'}, 'A/B completion-copy bridge only; C keeps original route')
    proof = checked(proof_ref)
    require(proof.get('slot') == slot, 'exact original slot proof required')
    snap = checked(proof['original_snapshot'])
    manifest = checked(snap['native_complete_manifest'])
    original = manifest['completeness_source_observation']
    check_ref(original)
    matches = [item for item in snap['native_originals']
               if item['observation']['sha256'] == original['sha256'] and item['observation']['bytes'] == original['bytes']]
    require(len(matches) == 1, 'one exact complete-stage frozen copy required, not a preferred stage')
    item = matches[0]
    frozen = item['observation']
    check_ref(frozen)
    require(original['path'] != frozen['path'], 'equal Ref needs no completion-copy bridge')
    require(Path(original['path']).read_bytes() == Path(frozen['path']).read_bytes(), 'completion copies differ in actual bytes')
    lineage = checked(proof['lineage_read_execution'])
    receipts = lineage.get('stage_receipts', [])
    receipt = next((r for r in receipts if r['ordinal'] == item['ordinal']), None)
    require(receipt and receipt['completion'] == frozen, 'complete-stage receipt must bind its unchanged frozen copy')
    comp = checked(frozen)
    invocation = checked(receipt['invocation'])
    method = checked(receipt['method_read'])
    task_id, project_id = comp.get('task_id'), comp.get('project_id')
    require(isinstance(task_id, str) and task_id and isinstance(project_id, str) and project_id
            and invocation.get('task_id') == method.get('task_id') == task_id
            and invocation.get('project_id') == method.get('project_id') == project_id,
            'same actual Task/project invocation, method read and completion required')
    pair = {'ordinal': item['ordinal'], 'task_id': task_id, 'project_id': project_id,
            'invocation': receipt['invocation'], 'method_read': receipt['method_read'],
            'original_completion': original, 'frozen_completion': frozen,
            'sha256': original['sha256'], 'bytes': original['bytes']}
    return cj, config, proof, snap, manifest, pair


def admitted_context(campaign, slot, proof_ref, admission_ref):
    admission = checked(admission_ref)
    cj, config, proof, snap, manifest, pair = copy_context(campaign, slot, proof_ref)
    require(admission.get('format') == FORMAT and admission.get('action') == ACTION,
            'exact narrow completion-copy amendment required')
    require(admission.get('status') == config['status'], 'engineering cannot authorize an admitted campaign')
    if config['status'] == 'ADMITTED':
        require(admission.get('observer_id') == '/root' and admission.get('assurance') == 'host_attested'
                and admission.get('evidence_kind') == 'ROOT_ACTUAL_PROSPECTIVE_COMPLETION_COPY_AMENDMENT',
                'actual prospective Root scope amendment required')
    else:
        require(admission.get('observer_id') == '/engineering/rc3-s04'
                and admission.get('assurance') == 'synthetic_engineering'
                and admission.get('evidence_kind') == 'SYNTHETIC_ENGINEERING_ONLY',
                'engineering authorization is explicit, never fake Root/native admission')
    expected = {'tool': reference(Path(__file__).resolve()), 'recorder': reference(SOURCE),
                'common': reference(u._path), 'campaign': str(cj.root), 'slot': slot,
                'registration': reference(cj.root / 'registration.json'), 'proof': proof_ref,
                'original_snapshot': proof['original_snapshot'], 'native_complete_manifest': snap['native_complete_manifest'],
                'lineage': proof['lineage_read_execution'], 'copy_pair': pair}
    require(expected['common']['sha256'] == COMMON_SHA, 'frozen common helper changed')
    require(all(admission.get(k) == v for k, v in expected.items()), 'amendment scope/dependency/pair differs')
    return cj, config, proof, snap, manifest, pair


def equivalent(left, right, pair):
    """Only this pinned complete-stage pair; no global digest-only equality."""
    if left == right:
        return True
    return ((left == pair['original_completion'] and right == pair['frozen_completion'])
            or (right == pair['original_completion'] and left == pair['frozen_completion']))


def original_record(cj, config, slot, proof_ref, proof, snap, manifest, pair):
    """The frozen A/B bind checks, with only two exact pair comparisons bridged.

    C's complete-prefix/earliest-original path stays in the original recorder.
    No old function is patched, recompiled, replaced or called with fake data.
    """
    require(not u.events(cj, 'private_evaluation_opened'), 'private evaluation already opened')
    require(not any(e['slot'] == slot for e in u.events(cj, 'original_bound')), 'original slot cannot be replaced')
    require(set(proof) == {'slot', 'input_identity', 'method_identity', 'original_snapshot', 'lineage_read_execution',
                          'evidence_kind', 'observation_kind', 'assurance', 'observed_at_utc'}, 'exact original proof fields, no oracle/schema payload')
    u.observation(proof, config)
    case, _ = slot.rsplit('-', 1)
    require(proof['input_identity'] == u.input_identity(config, case)
            and proof['method_identity'] == config['barrier_methods'][slot], 'case/input/method identity mismatch')
    check_ref(proof['method_identity'])
    validated = [proof['method_identity'], proof['original_snapshot'], proof['lineage_read_execution'], snap['native_complete_manifest']]
    require(snap.get('timepoint') == 'original_complete', 'SDK accepted/qualified/later snapshot is not original native')
    require(snap.get('format') == 'rc3-campaign-original-native-snapshot.v1', 'actual A/B original-native snapshot required')
    require(manifest.get('format') == 'rc3-native-complete-draft-manifest.v1'
            and manifest.get('complete_native_manuscript_observed') is True
            and manifest.get('assurance') == 'host_attested', 'A/B complete raw manifest required, not gate status')
    originals = snap['native_originals']
    require(originals and manifest['raw_stage_ordinals'] == [r['ordinal'] for r in originals], 'exact all native raw stages required')
    raw_refs, authors = [], set()
    for item in originals:
        check_ref(item['raw'])
        completion = checked(item['observation'])
        expected_kind = 'ROOT_ACTUAL_NATIVE' if config['status'] == 'ADMITTED' else 'SYNTHETIC_ENGINEERING_ONLY'
        require(completion.get('evidence_kind') == expected_kind and completion.get('observation_kind') == c.OBSERVER_KIND
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
            raise Error('A/B full native FINAL carrier must be UTF-8') from exc
        authors.add(final['sender']); raw_refs.append(item['raw']); validated.append(item['observation'])
    expected_completion = manifest['completeness_source_observation']
    check_ref(expected_completion)
    require(any(equivalent(expected_completion, r['observation'], pair) for r in originals), 'complete declaration must be a frozen completion')
    validated.append(expected_completion)
    lineage = checked(proof['lineage_read_execution'])
    u.observation(lineage, config)
    require(lineage.get('slot') == slot and lineage.get('earliest_complete_snapshot_sha256') == proof['original_snapshot']['sha256']
            and lineage.get('earlier_complete_snapshot_refs') == [] and lineage.get('lineage_known') is True,
            'first-complete chronology and actual known execution lineage required')
    for key in ('invocation', 'method_read', 'completion'):
        require(lineage.get(key), 'full invocation/read/completion sidecars required')
        check_ref(lineage[key]); validated.append(lineage[key])
    require(set(lineage.get('author_identities', [])) == authors and lineage['completion'] == expected_completion,
            'exact author lineage and completeness sidecar required')
    completion = checked(expected_completion)
    require(completion.get('method_read_record_sha256') == lineage['method_read']['sha256'], 'actual complete method-read sidecar differs')
    receipts = lineage.get('stage_receipts', [])
    require([r['ordinal'] for r in receipts] == manifest['raw_stage_ordinals'], 'all selected A/B native stage execution/read receipts required')
    invocations = []
    for receipt, original in zip(receipts, originals):
        require(receipt['completion'] == original['observation'], 'stage receipt differs from actual original completion')
        for key in ('invocation', 'method_read', 'completion'):
            check_ref(receipt[key]); validated.append(receipt[key])
        comp = checked(receipt['completion'])
        inv = checked(receipt['invocation']); spawn = inv['spawn']; method = checked(receipt['method_read'])
        expected_kind = 'ROOT_ACTUAL_NATIVE' if config['status'] == 'ADMITTED' else 'SYNTHETIC_ENGINEERING_ONLY'
        require(inv.get('evidence_kind') == expected_kind and inv.get('observation_kind') == c.OBSERVER_KIND
                and inv.get('assurance') == 'host_attested' and spawn.get('lineage_known') is True
                and spawn.get('tool') in {'collaboration.spawn_agent', 'collaboration.followup_task'},
                'actual known invocation lineage/evidence class required')
        if spawn['tool'] == 'collaboration.spawn_agent':
            require(spawn.get('fork_turns') == 'none' and spawn.get('inherited_identities') == [],
                    'fresh spawn must exclude inherited identities')
        require(comp.get('method_read_record_sha256') == receipt['method_read']['sha256']
                and spawn.get('canonical_task_name') == comp['completion']['sender']
                and spawn.get('returned_task_name') == comp['completion']['sender'], 'A/B stage execution/read binding differs')
        require(comp.get('task_id') and inv.get('task_id') == method.get('task_id') == comp['task_id']
                and comp.get('project_id') and inv.get('project_id') == method.get('project_id') == comp['project_id'],
                'actual stage Task/project identity differs')
        invocations.append(receipt['invocation'])
    require(any(r['invocation'] == lineage['invocation'] and r['method_read'] == lineage['method_read']
                and equivalent(r['completion'], lineage['completion'], pair) for r in receipts), 'summary sidecars must be actual completeness stage')
    require(not authors & set(checked(config['exposure_registry'])['excluded_identities']), 'excluded author in original proof')
    previous = {u.invocation_identity(r) for e in u.events(cj, 'original_bound') for r in e['invocations']}
    identities = [u.invocation_identity(r) for r in invocations]
    require(len(set(identities)) == len(identities) and not previous & set(identities),
            'same actual invocation cannot fill another slot/stage')
    return {'slot': slot, 'proof': proof_ref, 'snapshot': proof['original_snapshot'], 'raw_originals': raw_refs,
            'lineage': proof['lineage_read_execution'], 'validated_refs': validated, 'author_identities': sorted(authors),
            'invocations': invocations, 'invocation_identities': [{'executor': executor, 'native_turn_id': turn} for executor, turn in identities]}


def execute(campaign, slot, proof_path, proof_sha256, *, admission_path=None, admission_sha256=None, bind=False):
    proof_ref = reference(proof_path)
    require(proof_ref['sha256'] == proof_sha256, 'original proof bytes differ')
    cj, _ = public_campaign(campaign)
    with cj.locked():
        if bind:
            require(admission_path and admission_sha256, 'binding needs an exact prospective Root amendment')
            admission_ref = reference(admission_path)
            require(admission_ref['sha256'] == admission_sha256, 'admission bytes differ')
            _, config, proof, snap, manifest, pair = admitted_context(campaign, slot, proof_ref, admission_ref)
        else:
            _, config, proof, snap, manifest, pair = copy_context(campaign, slot, proof_ref)
            admission_ref = None
        dependencies = [reference(Path(__file__).resolve()), reference(SOURCE), reference(u._path), reference(cj.root / 'registration.json')]
        if admission_ref:
            dependencies.append(admission_ref)
        record = original_record(cj, config, slot, proof_ref, proof, snap, manifest, pair)
        record['validated_refs'] += dependencies
        # Recheck immutable dependencies and the actual two files under the
        # original campaign lock immediately before the sole binding append.
        for ref in [record['proof'], *record['validated_refs'], *record['raw_originals']]:
            check_ref(ref)
        require(Path(pair['original_completion']['path']).read_bytes() == Path(pair['frozen_completion']['path']).read_bytes(),
                'completion copies changed before binding')
        require(public_campaign(cj.root)[1] == config, 'registration changed while validating')
        if not bind:
            return {'status': 'DIAGNOSIS_ONLY_NO_ADMISSION_NO_BINDING', 'slot': slot, 'copy_pair': pair,
                    'all_original_binding_checks_passed': True, 'ledger_event_appended': False,
                    'private_evaluation_opened': False, 'oracle_IO': False}
        # Rebind the exact prospective amendment as well as the parsed config:
        # semantically equal JSON with different bytes is still identity drift.
        rebound = admitted_context(campaign, slot, proof_ref, admission_ref)
        require(rebound[1:] == (config, proof, snap, manifest, pair), 'admitted binding changed before append')
        record.update(completion_copy_amendment=admission_ref, completion_copy_pair=pair,
                      binding_tool=dependencies[0], unchanged_frozen_recorder=dependencies[1],
                      original_frozen_refs_preserved=True, private_release=False)
        cj.append('original_bound', record)
        return {'status': 'ORIGINAL_BOUND_NO_PRIVATE_RELEASE', 'binding': record, 'oracle_IO': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('diagnose-copy', 'bind-original-slot'))
    for name in ('campaign', 'slot', 'proof', 'proof-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--admission'); parser.add_argument('--admission-sha256')
    args = parser.parse_args()
    result = execute(args.campaign, args.slot, args.proof, args.proof_sha256,
                     admission_path=args.admission, admission_sha256=args.admission_sha256,
                     bind=args.command == 'bind-original-slot')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
