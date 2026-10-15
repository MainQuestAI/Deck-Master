"""Synthetic recorder engineering, never unseen input/native/SDK evidence."""
import importlib.util
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'tools/rc3_campaign/unseen_native_only.py'
SPEC = importlib.util.spec_from_file_location('rc3_unseen_native_unit', SCRIPT)
u = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u)


def stored(tmp, name, value):
    return u.save(tmp / name, value)


def observation(**extra):
    return {'evidence_kind': 'SYNTHETIC_ENGINEERING_ONLY', 'observation_kind': u.c.OBSERVER_KIND,
            'assurance': 'host_attested', 'observed_at_utc': u.c.now(), **extra}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    # Portable tiny neutral six-file seam. No production fallback or real U source read.
    rows = []
    expected = {}
    for i, label in enumerate(u.METHODS):
        raw = f'SYNTHETIC_ENGINEERING_ONLY method {i}\n'.encode()
        ref = u.write_once(tmp_path / 'methods' / label, raw)
        rows.append({**ref, 'relative_path': label})
        expected[label] = (len(raw), u.digest(raw))
    monkeypatch.setattr(u, 'METHODS', expected)
    cyber = {'fixed_commit': u.COMMIT, 'files': rows}
    method_ref = stored(tmp_path, 'method-identity.json', cyber)
    common = stored(tmp_path, 'technical.json', {'fixture': 'SYNTHETIC_ENGINEERING_ONLY'})
    brief = u.write_once(tmp_path / 'brief.txt', b'Neutral library routing, not real U content.\n')
    material = u.write_once(tmp_path / 'material.txt', b'An unknown route stays unknown.\n')
    exposure = stored(tmp_path, 'exposure.json', {'status': 'FROZEN', 'excluded_identities': ['/root/preparer']})
    config = {'format': u.FORMAT, 'status': 'ENGINEERING_ONLY_NOT_ADMITTED', 'campaign_id': 'neutral-unseen',
              'recorder_sha256': u.digest(SCRIPT.read_bytes()), 'common_utils_sha256': u.COMMON_SHA,
              'arm': 'E1-C', 'budget': deepcopy(u.BUDGET), 'protocol': common, 'admission_review': common,
              'exposure_registry': exposure, 'cases': {case: {'brief': brief, 'materials': [material]} for case in u.CASES},
              'role_instructions': {role: u.write_once(tmp_path / f'{role}.txt', f'Neutral {role}; no private material.\n'.encode())
                                    for role in u.ROLES}, 'cyberppt': cyber,
              'barrier_methods': {slot: method_ref for slot in u.SLOTS},
              'observable_configuration': dict.fromkeys(['model', 'seed', 'tokens', 'price', 'invocation_parameters'])}
    registration = stored(tmp_path, 'registration.json', config)
    u.freeze(registration['path'], tmp_path / 'campaign')
    state = u.init(tmp_path / 'campaign', tmp_path / 'run', u.CASES[0])
    return tmp_path, u.Journal(tmp_path / 'run'), state, config


def invoke(setup, stage, role='initial_writer', *, executor=None, tool='collaboration.spawn_agent', **changes):
    tmp, journal, state, config = setup
    packet = u.prepare(journal, state, config, stage, role)
    ordinal = len(u.events(journal, 'native_begun')) + 1
    executor = executor or f'/root/neutral_{state["case"]}_{ordinal}'
    spawn = {'tool': tool, 'canonical_task_name': executor, 'returned_task_name': executor,
             'fork_turns': 'none', 'inherited_identities': [], 'lineage_known': True,
             'native_turn_id': f'{state["case"]}-turn{ordinal}', **changes}
    ref = stored(tmp, f'{state["case"]}-invoke{ordinal}.json', observation(packet_sha256=packet['sha256'], spawn=spawn))
    event = u.begin(journal, state, config, stage, ref['path'])
    if event['eligible']:
        u.method_read(journal, event['ordinal'], executor)
    return event


def finish(setup, event, raw=b'```native\nNeutral complete text.\n```\n', kind='complete_manuscript', **changes):
    tmp, journal, state, config = setup
    ordinal = event['ordinal']
    result = u.write_once(tmp / f'{state["case"]}-raw-{ordinal}', raw)
    method = u.reference(journal.root / 'executions' / f'{ordinal:04d}' / 'method-read.json')
    completion = {'sender': event['executor'], 'message_type': 'FINAL_ANSWER',
                  'status_observation_tool': 'collaboration.list_agents', 'observed_status': 'completed',
                  'observed_completed_agents': [event['executor']], 'raw_final_message': raw.decode()}
    record = observation(packet_sha256=event['packet']['sha256'], method_read_record_sha256=method['sha256'],
                         all_method_bytes_read=True, model_output_bytes_sha256=result['sha256'],
                         native_output_kind=kind, completion=completion)
    record.update(changes)
    obs = stored(tmp, f'{state["case"]}-complete-{ordinal}.json', record)
    return u.observe(journal, config, ordinal, result['path'], result['sha256'], obs['path'], obs['sha256'])


def complete_original(setup):
    e = invoke(setup, 'first')
    finish(setup, e)
    u.snapshot(setup[1], 'original_complete', e['ordinal'])
    return e


def necessity(setup, feedback, *, actual=True):
    tmp, _, _, _ = setup
    raw = Path(feedback['raw']['path']).read_bytes()
    return stored(tmp, 'necessity.json', observation(necessary_layers=['page_copy'], actual_defect_identified=actual,
                  finding_byte_locators=[{'start': 0, 'end': len(raw), 'sha256': u.digest(raw)}]))


def test_standalone_import_never_loads_SDK_or_old_native_validate():
    code = ('import importlib.util,sys; s=importlib.util.spec_from_file_location("n",sys.argv[1]); '
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
            'assert not any(k=="deck_master" or k.startswith("deck_master.") for k in sys.modules); '
            'assert not any("native_only.py" in str(getattr(v,"__file__","")) and v is not m for v in sys.modules.values())')
    subprocess.run([sys.executable, '-I', '-B', '-c', code, str(SCRIPT)], check=True)


@pytest.mark.parametrize('change', ['case_alias', 'SDK_field', 'truncated_method', 'budget', 'missing_role'])
def test_registration_rejects_scope_alias_sdk_methods_and_budget(setup, change):
    config = deepcopy(setup[3])
    if change == 'case_alias': config['cases']['Q1'] = config['cases'].pop(u.CASES[0])
    if change == 'SDK_field': config['task_id'] = 'not-a-C-task'
    if change == 'truncated_method': config['cyberppt']['files'].pop()
    if change == 'budget': config['budget']['verification'] = 2
    if change == 'missing_role': config['role_instructions'].pop('verification')
    with pytest.raises(u.CampaignError): u.validate(config)


def test_no_run_reset_and_packet_contains_only_own_public_inputs(setup):
    tmp, journal, state, config = setup
    with pytest.raises(u.CampaignError, match='unique C run'): u.init(tmp/'campaign', tmp/'alias', u.CASES[0])
    packet = u.read(u.prepare(journal, state, config, 'clean', 'initial_writer')['path'])
    assert all(p.startswith(('inputs/', 'methods/')) or p == 'role-instruction.txt' for p in packet['files'])
    assert len(packet['method_files']) == 6
    raw = u.readable(tmp/'brief.txt')
    assert raw.read_bytes() == Path(config['cases'][u.CASES[0]]['brief']['path']).read_bytes()


def test_exact_raw_first_refusal_retained_and_cannot_overwrite(setup):
    tmp, journal, _, config = setup
    e = invoke(setup, 'one')
    raw = b'prefix\n```\ncomplete\n```\n'
    bad = {'sender': e['executor'], 'raw_final_message': raw.decode().rstrip('\n')}
    with pytest.raises(u.CampaignError, match='FINAL bytes'): finish(setup, e, raw, completion=bad)
    dest = journal.root/'executions/0001'
    assert (dest/'raw-native-output').read_bytes() == raw
    assert u.events(journal, 'native_observation_refused')
    with pytest.raises(FileExistsError):
        u.observe(journal, config, 1, tmp/f'{u.CASES[0]}-raw-1', u.digest(raw), tmp/f'{u.CASES[0]}-complete-1.json', 'wrong')
    assert len(u.events(journal, 'native_begun')) == 1


def test_earliest_complete_no_second_initial_and_no_repair_equal_bytes(setup):
    tmp, journal, _, config = setup
    e = complete_original(setup)
    with pytest.raises(u.CampaignError, match='ends initial'): u.prepare(journal, setup[2], config, 'later', 'initial_writer')
    f = invoke(setup, 'feedback', 'feedback')
    review = finish(setup, f, b'No defect identified.\n', 'review')
    u.feedback(journal, f['ordinal'])
    with pytest.raises(u.CampaignError, match='one public'): u.prepare(journal, setup[2], config, 'second', 'feedback')
    bad = necessity(setup, review, actual=False)
    with pytest.raises(u.CampaignError, match='no defect'): u.repair(journal, config, bad['path'])
    evaluated = u.snapshot(journal, 'equal_budget_evaluated', e['ordinal'])
    original = u.snapshot_ref(journal, 'original_complete')
    assert evaluated['raw'] == original['raw']
    assert Path(evaluated['blind_exact_copy']['path']).read_bytes() == Path(original['raw']['path']).read_bytes()


def test_one_repair_readonly_closure_never_becomes_second_feedback(setup):
    _, journal, state, config = setup
    complete_original(setup)
    f = invoke(setup, 'feedback', 'feedback')
    review = finish(setup, f, b'Actual neutral defect: replace the placeholder.\n', 'review')
    u.feedback(journal, f['ordinal'])
    necessary = necessity(setup, review)
    u.repair(journal, config, necessary['path'])
    r = invoke(setup, 'repair', 'repair_writer')
    finish(setup, r, b'Neutral repaired full text.\n')
    u.snapshot(journal, 'repaired_complete', r['ordinal'])
    with pytest.raises(u.CampaignError, match='complete repair ends'): u.prepare(journal, state, config, 'preferred-repair', 'repair_writer')
    v = invoke(setup, 'closure', 'verification')
    finish(setup, v, b'Readonly closure, no Writer dispatch.\n', 'review')
    with pytest.raises(u.CampaignError, match='one actual'): u.feedback(journal, v['ordinal'])
    with pytest.raises(u.CampaignError, match='second'): u.repair(journal, config, necessary['path'])
    with pytest.raises(u.CampaignError, match='readonly'): u.prepare(journal, state, config, 'repair-again', 'repair_writer')
    assert u.snapshot(journal, 'equal_budget_evaluated', r['ordinal'])['raw']['sha256']
    packet = u.read(v['packet']['path'])
    assert 'repair.diff' in packet['files']
    assert all('closure' not in name for name in packet['files'])
    with pytest.raises(u.CampaignError, match='budget exhausted'): u.prepare(journal, state, config, 'closure2', 'verification')


def test_actual_sixth_turn_counts_overrun_and_unknown_not_complete(setup):
    tmp, journal, state, config = setup
    # Packets can be prepared before Root reports actual turns; actual sixth still charged.
    packets = [u.prepare(journal, state, config, f's{i}', 'initial_writer') for i in range(6)]
    for i, packet in enumerate(packets):
        record = stored(tmp, f'inv{i}.json', observation(packet_sha256=packet['sha256'], spawn={
            'native_turn_id': f'actual-{i}', 'tool': 'collaboration.spawn_agent', 'canonical_task_name': f'/root/over{i}',
            'returned_task_name': f'/root/over{i}', 'fork_turns': 'none', 'inherited_identities': [], 'lineage_known': True}))
        e = u.begin(journal, state, config, f's{i}', record['path'])
        u.method_read(journal, e['ordinal'], e['executor'])
        if i == 0:
            finish(setup, e, b'Unknown partial original.\n', 'unknown')
    assert len(u.events(journal, 'native_begun')) == 6 and e['within_budget'] is False
    finish(setup, e)
    with pytest.raises(u.CampaignError, match='over-budget'): u.snapshot(journal, 'original_complete', 6)
    with pytest.raises(u.CampaignError, match='already charged'): u.begin(journal, state, config, 's5', record['path'])
    assert u.first_complete(journal)['ordinal'] == 6  # cannot pick a later preferred draft


def test_excluded_unknown_lineage_and_cross_case_followup_still_preserve_cost(setup):
    tmp, journal, _, config = setup
    e = invoke(setup, 'bad', lineage_known=False)
    assert not e['eligible'] and len(u.events(journal, 'native_begun')) == 1
    second_state = u.init(tmp/'campaign', tmp/'run2', u.CASES[1])
    other = (tmp, u.Journal(tmp/'run2'), second_state, config)
    reused = invoke(other, 'cross', executor=e['executor'], tool='collaboration.followup_task')
    assert not reused['eligible'] and 'cross case' in reused['exclusion_reason']


def bind_proof(setup, case, arm, *, fail_timepoint=False):
    tmp, journal, state, config = setup
    slot = f'{case}-{arm}'
    tag = ('bad-' if fail_timepoint else '') + slot
    if arm == 'C':
        snap_ref = u.reference(journal.root/'snapshots/original_complete.json')
        snap = u.read(snap_ref['path']); e, dest = u.execution(journal, snap['ordinal'])
        completion = snap['observation']; method = u.reference(dest/'method-read.json'); invocation = e['invocation']
        authors = [e['executor']]
    else:
        raw = u.write_once(tmp/f'{tag}-raw', b'SYNTHETIC original envelope, SDK status independent.\n')
        executor = f'/root/{slot}-author'
        invocation = stored(tmp, f'{tag}-invoke.json', observation(spawn={'canonical_task_name':executor,'returned_task_name':executor}))
        method = stored(tmp, f'{tag}-read.json', {'executor': executor, 'fixture': 'full neutral method bytes read'})
        completion = stored(tmp, f'{tag}-completion.json', observation(model_output_bytes_sha256=raw['sha256'],
            all_method_bytes_read=True, method_read_record_sha256=method['sha256'], completion={
              'sender':executor,'message_type':'FINAL_ANSWER','status_observation_tool':'collaboration.list_agents',
              'observed_status':'completed','observed_completed_agents':[executor],'raw_final_message':'full original'}))
        manifest = stored(tmp, f'{tag}-complete-manifest.json', {'format':'rc3-native-complete-draft-manifest.v1',
            'complete_native_manuscript_observed':True,'assurance':'host_attested','raw_stage_ordinals':[1],
            'completeness_source_observation':completion})
        snap_ref = stored(tmp, f'{tag}-snapshot.json', {'format':'rc3-campaign-original-native-snapshot.v1',
            'timepoint':'qualified_for_owner' if fail_timepoint else 'original_complete','native_complete_manifest':manifest,
            'native_originals':[{'ordinal':1,'raw':raw,'observation':completion}]})
        authors=[executor]
    stage_receipts = [] if arm == 'C' else [{'ordinal':1, 'invocation':invocation, 'method_read':method, 'completion':completion}]
    lineage = stored(tmp, f'{tag}-lineage.json', observation(slot=slot, earliest_complete_snapshot_sha256=snap_ref['sha256'],
        earlier_complete_snapshot_refs=[],lineage_known=True,author_identities=authors,
        invocation=invocation,method_read=method,completion=completion,stage_receipts=stage_receipts))
    return stored(tmp, f'{tag}-proof.json', observation(slot=slot,input_identity=u.input_identity(config,case),
        method_identity=config['barrier_methods'][slot],original_snapshot=snap_ref,lineage_read_execution=lineage))


def test_six_slot_barrier_exact_native_not_sdk_or_second_draft(setup):
    tmp, journal, state, config = setup
    cj = u.Journal(state['campaign'])
    # A qualified SDK snapshot does not count as an original, even with real raw attached.
    bad = bind_proof(setup, u.CASES[0], 'A', fail_timepoint=True)
    with pytest.raises(u.CampaignError, match='not original'): u.bind_original(cj, config, u.SLOTS[0], bad['path'])
    assert len(u.barrier(cj)['missing']) == 6
    for case in u.CASES:
        active = setup
        if case != state['case']:
            new_state = u.init(tmp/'campaign', tmp/'second-case', case)
            active = (tmp,u.Journal(tmp/'second-case'),new_state,config)
        complete_original(active)
        for arm in ('A','B','C'):
            proof = bind_proof(active, case, arm)
            u.bind_original(cj,config,f'{case}-{arm}',proof['path'])
    assert u.barrier(cj)['ready'] and not u.barrier(cj)['missing']
    root = stored(tmp, 'private-open.json', observation())
    actor='/root/fresh_barrier_auditor'
    audit_raw=u.write_once(tmp/'audit-raw',b'Neutral independent audit, not quality grading.\n')
    audit_invocation=stored(tmp,'audit-invocation.json',observation(spawn={'tool':'collaboration.spawn_agent',
        'fork_turns':'none','canonical_task_name':actor,'returned_task_name':actor,'inherited_identities':[]}))
    audit_completion=stored(tmp,'audit-completion.json',observation(completion={'sender':actor,
        'message_type':'FINAL_ANSWER','observed_status':'completed','status_observation_tool':'collaboration.list_agents',
        'observed_completed_agents':[actor],'raw_final_message':Path(audit_raw['path']).read_text()}))
    audit = stored(tmp, 'independent-audit.json', observation(barrier_slots=list(u.SLOTS),all_originals_checked=True,
        independent_nonauthor=True,reviewer=actor,native_invocation=audit_invocation,native_completion=audit_completion,audit_raw=audit_raw,
        original_proof_sha256s=[e['proof']['sha256'] for e in u.events(cj,'original_bound')]))
    assert u.open_private(cj,config,root['path'],audit['path'])['oracle'].startswith('NOT_RECEIVED')


def test_actual_private_evaluation_before_barrier_permanently_contaminated(setup):
    tmp, _, state, config = setup
    cj=u.Journal(state['campaign'])
    root=stored(tmp,'early-private-observation.json',observation(private_evaluation_already_occurred=True))
    with pytest.raises(u.CampaignError,match='six originals'): u.open_private(cj,config,root['path'],tmp/'never-opened-audit')
    assert u.barrier(cj)['contaminated'] and not u.barrier(cj)['ready']
    folder=tmp/'private';folder.mkdir();(folder/'oracle.json').write_text('DO NOT READ')
    with pytest.raises(u.CampaignError,match='never opens'): u.read(folder/'oracle.json')


def test_barrier_rechecks_transitive_sidecars_and_rejects_wrong_input(setup):
    tmp, _, state, config = setup
    cj=u.Journal(state['campaign'])
    proof=bind_proof(setup,u.CASES[0],'A')
    wrong=u.read(proof['path']);wrong['input_identity']='wrong-input'
    ref=stored(tmp,'wrong-input-proof.json',wrong)
    with pytest.raises(u.CampaignError,match='input/method'): u.bind_original(cj,config,u.SLOTS[0],ref['path'])
    u.bind_original(cj,config,u.SLOTS[0],proof['path'])
    bound=u.events(cj,'original_bound')[0]
    lineage=u.read(bound['lineage']['path'])
    # Deliberate tamper of only this test's neutral receipt must invalidate later inspection.
    Path(lineage['method_read']['path']).write_text('changed test-only receipt')
    with pytest.raises(u.CampaignError,match='pinned bytes changed'): u.barrier(cj)


def test_unknown_global_native_charge_blocks_reset_after_interrupted_local_append(setup):
    tmp,journal,state,config=setup
    packet=u.prepare(journal,state,config,'pending','initial_writer')
    cj=u.Journal(state['campaign'])
    cj.append('native_begun',{'run_root':state['run_root'],'native_turn_id':'durable-unknown'})
    ref=stored(tmp,'after-crash.json',observation(packet_sha256=packet['sha256'],spawn={
        'native_turn_id':'new-turn','canonical_task_name':'/root/new'}))
    with pytest.raises(u.CampaignError,match='cross-journal'): u.begin(journal,state,config,'pending',ref['path'])
    assert len(u.events(cj,'native_begun'))==1
