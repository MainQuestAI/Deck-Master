"""S04 synthetic mechanical checks; no model, SDK, oracle or native evidence.

The existing recorder fixture's tiny Cyber hashes are explicitly a pytest-only
portability seam. Frozen production helpers and constants are never changed.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'tools/rc3_campaign/completion_copy_binding.py'
spec = importlib.util.spec_from_file_location('s04_copy_unit', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
u, c = m.u, m.c
oldspec = importlib.util.spec_from_file_location('s04_old_neutral_fixtures', Path(__file__).with_name('test_rc3_unseen_native_only.py'))
old = importlib.util.module_from_spec(oldspec); oldspec.loader.exec_module(old)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    result = old.setup.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(u, 'METHODS', old.u.METHODS)
    return result


def obs(**values):
    return {'evidence_kind': 'SYNTHETIC_ENGINEERING_ONLY', 'observation_kind': c.OBSERVER_KIND,
            'assurance': 'host_attested', 'observed_at_utc': c.now(), **values}


def fixture(setup, *, slot='U-LIVE-01-A', change=None, actor=None, turn=None):
    tmp, _, state, config = setup
    dest = tmp / slot; dest.mkdir()
    def save(name, value): return c.save(dest / name, value)
    author = actor or '/root/synthetic-' + slot
    task, project = 'synthetic-task-' + slot, 'synthetic-project-' + slot
    spawn = {'tool': 'collaboration.spawn_agent', 'canonical_task_name': author, 'returned_task_name': author,
        'native_turn_id': turn or 'synthetic-turn-' + slot, 'lineage_known': True,
        'fork_turns': 'none', 'inherited_identities': []}
    if change == 'unknown-lineage': spawn['lineage_known'] = False
    if change == 'unknown-turn': spawn.pop('native_turn_id')
    if change == 'wrong-actor': spawn['returned_task_name'] = '/root/other-actor'
    if change == 'inherited': spawn['inherited_identities'] = ['/root/preparer']
    inv = obs(spawn=spawn, task_id=task, project_id=project)
    if change == 'wrong-evidence': inv['evidence_kind'] = 'ROOT_ACTUAL_NATIVE'
    invocation = save('invocation.json', inv)
    method = save('method-read.json', {'task_id': 'wrong-task' if change == 'wrong-task' else task, 'project_id': project,
        'SYNTHETIC_FULL_READ_FIXTURE_NOT_ACTUAL_NATIVE': True})
    raw = c.write_once(dest / 'raw-envelope', b'Synthetic native formal envelope, not a model output.\n')
    final = {'sender': author, 'message_type': 'FINAL_ANSWER', 'observed_status': 'completed',
        'status_observation_tool': 'collaboration.list_agents', 'observed_completed_agents': [author],
        'raw_final_message': 'Synthetic full FINAL carrier, distinct from the formal envelope.\n'}
    if change == 'not-completed': final['observed_status'] = 'running'
    if change == 'non-root': final['sender'] = 'non-root-author'
    if change == 'empty-FINAL': final['raw_final_message'] = ' \n\t'
    value = obs(task_id=task, project_id=project, method_read_record_sha256=method['sha256'],
        model_output_bytes_sha256=raw['sha256'], all_method_bytes_read=change != 'method-not-read', completion=final)
    original = save('Root-original-completion.json', value)
    frozen = c.write_once(dest / 'frozen-completion-copy.json', Path(original['path']).read_bytes())
    originals = [{'ordinal': 1, 'raw': raw, 'observation': frozen}]
    manifest = save('manifest.json', {'format': 'rc3-native-complete-draft-manifest.v1',
        'complete_native_manuscript_observed': True, 'assurance': 'host_attested',
        'raw_stage_ordinals': [1], 'completeness_source_observation': original})
    snap = save('earliest-original.json', {'format': 'rc3-campaign-original-native-snapshot.v1',
        'timepoint': 'first_sdk_complete' if change == 'later-snapshot' else 'original_complete',
        'native_complete_manifest': manifest, 'native_originals': originals})
    receipt = {'ordinal': 1, 'invocation': invocation, 'method_read': method, 'completion': frozen}
    lineage = obs(slot=slot, earliest_complete_snapshot_sha256=snap['sha256'], lineage_known=change != 'unknown-proof-lineage',
        earlier_complete_snapshot_refs=[snap] if change == 'earlier-complete' else [], author_identities=[author],
        invocation=invocation, method_read=method, completion=original,
        stage_receipts=[] if change == 'missing-receipt' else [receipt])
    lineage_ref = save('lineage.json', lineage)
    case = slot.rsplit('-', 1)[0]
    proof = save('proof.json', obs(slot=slot, input_identity=u.input_identity(config, case),
        method_identity=config['barrier_methods'][slot], original_snapshot=snap, lineage_read_execution=lineage_ref))
    # Construct amendment from the actual immutable fixture refs, not from
    # potentially invalid helper output, so every negative reaches validation.
    pair = {'ordinal': 1, 'task_id': task, 'project_id': project, 'invocation': invocation, 'method_read': method,
        'original_completion': original, 'frozen_completion': frozen, 'sha256': original['sha256'], 'bytes': original['bytes']}
    amendment = {'format': m.FORMAT, 'action': m.ACTION, 'status': config['status'], 'observer_id': '/engineering/rc3-s04',
        'assurance': 'synthetic_engineering', 'evidence_kind': 'SYNTHETIC_ENGINEERING_ONLY',
        'tool': m.reference(SCRIPT), 'recorder': m.reference(m.SOURCE), 'common': m.reference(u._path),
        'campaign': state['campaign'], 'slot': slot, 'registration': m.reference(Path(state['campaign'])/'registration.json'),
        'proof': proof, 'original_snapshot': snap, 'native_complete_manifest': manifest, 'lineage': lineage_ref, 'copy_pair': pair}
    admission = save('amendment.json', amendment)
    return {'campaign': state['campaign'], 'slot': slot, 'proof': proof, 'admission': admission, 'pair': pair, 'original': original,
            'frozen': frozen, 'manifest': manifest, 'snapshot': snap, 'lineage': lineage_ref, 'directory': dest}


def execute(f, *, bind=True, admission=None):
    a = admission or f['admission']
    return m.execute(f['campaign'], f['slot'], f['proof']['path'], f['proof']['sha256'],
        admission_path=a['path'], admission_sha256=a['sha256'], bind=bind)


def test_old_exact_Ref_failure_then_diagnose_then_explicit_binding(setup):
    f = fixture(setup)
    cj, config = u.campaign(f['campaign'])
    originals = {k: Path(f[k]['path']).read_bytes() for k in ('proof','manifest','snapshot','lineage','original','frozen')}
    with pytest.raises(m.Error, match='complete declaration'):
        u.bind_original(cj, config, f['slot'], f['proof']['path'])
    assert execute(f, bind=False)['status'] == 'DIAGNOSIS_ONLY_NO_ADMISSION_NO_BINDING'
    assert not u.events(cj, 'original_bound')
    result = execute(f)
    assert result['status'] == 'ORIGINAL_BOUND_NO_PRIVATE_RELEASE'
    assert [e['slot'] for e in u.events(cj, 'original_bound')] == [f['slot']]
    assert not u.barrier(cj)['ready'] and not u.events(cj, 'private_evaluation_opened')
    assert all(Path(f[k]['path']).read_bytes() == v for k,v in originals.items())
    with pytest.raises(m.Error, match='cannot be replaced'): execute(f)


@pytest.mark.parametrize('change', ['unknown-lineage','unknown-proof-lineage','unknown-turn','wrong-actor','inherited','wrong-evidence',
    'wrong-task','not-completed','non-root','empty-FINAL','method-not-read','later-snapshot','earlier-complete','missing-receipt'])
def test_original_checks_cannot_be_bypassed_by_same_bytes(setup, change):
    f = fixture(setup, change=change)
    with pytest.raises(m.Error): execute(f)
    cj, _ = u.campaign(f['campaign'])
    assert not u.events(cj, 'original_bound') and not u.barrier(cj)['ready']


@pytest.mark.parametrize('fault', ['wrong-tool','wrong-slot','wrong-status','fake-root','wrong-pair','digest','size','changed-byte','unadmitted-alias'])
def test_exact_authorization_and_copy_bytes_required(setup, fault):
    f = fixture(setup)
    value = c.read(f['admission']['path'])
    if fault == 'wrong-tool': value['tool'] = m.reference(m.SOURCE)
    if fault == 'wrong-slot': value['slot'] = 'U-READ-01-A'
    if fault == 'wrong-status': value['status'] = 'ADMITTED'
    if fault == 'fake-root': value['observer_id'] = '/root'
    if fault == 'wrong-pair': value['copy_pair']['ordinal'] = 2
    if fault == 'digest': value['copy_pair']['sha256'] = '0' * 64
    if fault == 'size': value['copy_pair']['bytes'] += 1
    if fault == 'changed-byte': Path(f['frozen']['path']).write_bytes(b'changed bytes')
    if fault == 'unadmitted-alias':
        third = c.write_once(f['directory']/'third-same-body.json', Path(f['original']['path']).read_bytes())
        value['copy_pair']['original_completion'] = third
    a = c.save(f['directory']/'wrong-amendment.json', value)
    with pytest.raises((m.Error, ValueError)): execute(f, admission=a)
    assert not u.events(u.campaign(f['campaign'])[0], 'original_bound')


def test_same_actual_turn_cannot_fill_a_second_slot(setup):
    first = fixture(setup, actor='/root/shared-engineering-actor', turn='same-actual-turn')
    execute(first)
    second = fixture(setup, slot='U-READ-01-B', actor='/root/shared-engineering-actor', turn='same-actual-turn')
    with pytest.raises(m.Error, match='same actual invocation'): execute(second)


def test_old_barrier_rechecks_new_admission_and_original_copy(setup):
    f = fixture(setup); execute(f)
    Path(f['original']['path']).write_bytes(b'tampered after binding')
    with pytest.raises((m.Error, ValueError)): u.barrier(u.campaign(f['campaign'])[0])


def test_six_slot_barrier_keeps_C_original_route_and_private_closed(setup):
    tmp, _, state, config = setup
    cj, _ = u.campaign(state['campaign'])
    for case in u.CASES:
        for arm in ('A', 'B'):
            execute(fixture(setup, slot=f'{case}-{arm}'))
        active = setup
        if case != state['case']:
            next_state = old.u.init(state['campaign'], tmp/'second-C', case)
            active = (tmp, old.u.Journal(tmp/'second-C'), next_state, config)
        old.complete_original(active)
        proof = old.bind_proof(active, case, 'C')
        u.bind_original(cj, config, f'{case}-C', proof['path'])
    assert u.barrier(cj)['ready'] and len(u.events(cj, 'original_bound')) == 6
    assert not u.events(cj, 'private_evaluation_opened')


@pytest.mark.parametrize('target', ['admission','original','registration'])
def test_revalidation_immediately_before_append_rejects_drift(setup, monkeypatch, target):
    f = fixture(setup)
    real = m.original_record
    def changed(*args):
        record = real(*args)
        path = Path(f['campaign'])/'registration.json' if target == 'registration' else Path(f[target]['path'])
        path.write_bytes(path.read_bytes() + b' ')
        return record
    monkeypatch.setattr(m, 'original_record', changed)  # explicit test scheduling seam, not production source rewrite
    with pytest.raises((m.Error, ValueError)): execute(f)
    assert not u.events(c.Journal(f['campaign']), 'original_bound')


def test_private_path_refused_before_body_read_and_symlink_refused(setup):
    f = fixture(setup)
    private = f['directory']/'private'; private.mkdir()
    target = private/'unread-body'; target.write_text('SYNTHETIC SECRET SENTINEL MUST NOT BE OPENED')
    with pytest.raises(m.Error, match='never read'): m.reference(target)
    alias = f['directory']/'alias.json'; alias.symlink_to(f['original']['path'])
    with pytest.raises(m.Error, match='aliases'): m.reference(alias)


def test_no_SDK_import_or_private_open_entrypoint():
    code = ('import importlib.util,sys; s=importlib.util.spec_from_file_location("n",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
            'assert not any(k=="deck_master" or k.startswith("deck_master.") for k in sys.modules)')
    subprocess.run([sys.executable,'-I','-B','-c',code,str(SCRIPT)],check=True)
    result = subprocess.run([sys.executable,'-I','-B',str(SCRIPT),'--help'],capture_output=True,text=True,check=True)
    assert 'open-private' not in result.stdout


def guarded_sentinel(f):
    """The permanent external audit hook blocks even an attempted body open."""
    path = f['directory'] / 'synthetic-oracle-path-guard' / 'never-read-sentinel'
    path.parent.mkdir()
    body = b'SYNTHETIC PUBLIC TEST SENTINEL. NEVER READ OR HASH THIS FILE.\n'
    with path.open('xb') as stream:
        stream.write(body)
    ref = {'path': str(path), 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
    attempts = []
    def audit(event, args):
        if event == 'open' and str(args[0]) == str(path):
            attempts.append(event)
            raise AssertionError('external audit blocked forbidden OPEN before sentinel body IO')
    sys.addaudithook(audit)  # Deliberately never removed; no sentinel is read/hashed later.
    return ref, attempts


def change_registration_ref(f, ref, location):
    path = Path(f['campaign']) / 'registration.json'
    config = json.loads(path.read_bytes())
    if location == 'source': config['cases']['U-LIVE-01']['materials'][0] = ref
    elif location == 'role': config['role_instructions']['initial_writer'] = ref
    elif location == 'method': config['barrier_methods']['U-LIVE-01-A'] = ref
    elif location == 'exposure-nested':
        value = json.loads(Path(config['exposure_registry']['path']).read_bytes())
        value['nested'] = {'refs': [ref]}
        config['exposure_registry'] = c.save(f['directory'] / 'exposure-with-nested-ref.json', value)
    elif location == 'method-nested':
        value = deepcopy(config['cyberppt'])
        value['nested'] = {'refs': [ref]}
        config['barrier_methods']['U-LIVE-01-C'] = c.save(f['directory'] / 'method-with-nested-ref.json', value)
    else: config['protocol'] = ref
    path.write_bytes(c.encoded(config))


@pytest.mark.parametrize('bind', [False, True])
@pytest.mark.parametrize('location', ['protocol', 'source', 'role', 'method', 'exposure-nested', 'method-nested', 'alias'])
def test_registration_transitive_paths_rejected_before_any_open(setup, bind, location):
    f = fixture(setup)
    ref, attempts = guarded_sentinel(f)
    if location == 'alias':
        alias = f['directory'] / 'public-looking-alias.json'
        alias.symlink_to(ref['path'])
        ref = {**ref, 'path': str(alias)}
    change_registration_ref(f, ref, location)
    with pytest.raises(m.Error, match='never read|aliases'):
        execute(f, bind=bind)
    assert attempts == []
    assert not u.events(c.Journal(f['campaign']), 'original_bound')


def test_direct_copy_context_preflights_registration_before_old_reader(setup):
    f = fixture(setup)
    ref, attempts = guarded_sentinel(f)
    change_registration_ref(f, ref, 'protocol')
    with pytest.raises(m.Error, match='never read'):
        m.copy_context(f['campaign'], f['slot'], f['proof'])
    assert attempts == []


@pytest.mark.parametrize('bind', [False, True])
def test_final_locked_reload_preflights_changed_ref_before_old_validator(setup, monkeypatch, bind):
    f = fixture(setup)
    ref, attempts = guarded_sentinel(f)
    real = m.public_campaign
    calls = []
    def at_reload(root):
        calls.append(str(root))
        if len(calls) == 3:
            # Scheduling seam only: bootstrap and copy_context already passed,
            # then an external registration changes just before locked reload.
            change_registration_ref(f, ref, 'protocol')
        return real(root)
    monkeypatch.setattr(m, 'public_campaign', at_reload)
    with pytest.raises(m.Error, match='never read'):
        execute(f, bind=bind)
    assert len(calls) == 3 and attempts == []
    assert not u.events(c.Journal(f['campaign']), 'original_bound')


def test_old_journal_invocation_ref_is_preflighted_before_uniqueness_reader(setup):
    f = fixture(setup)
    ref, attempts = guarded_sentinel(f)
    c.Journal(f['campaign']).append('original_bound', {'slot': 'U-READ-01-A', 'invocations': [ref]})
    with pytest.raises(m.Error, match='never read'):
        execute(f, bind=False)
    assert attempts == []
    assert len(u.events(c.Journal(f['campaign']), 'original_bound')) == 1
