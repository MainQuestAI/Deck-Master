#!/usr/bin/env python3
"""Prospective original Q2 four-flow 300s adapter; no model or image calls.

Uses d0's full-own packet/native protocol and 442's q2-300 resource ledger.
Root observations remain Host attestations, not platform/human approval.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

COMMON_SHA = 'd0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261'
SCOPED_SHA = '44210a2965d2a8e44a6de954996b69c3d14fb886ed0e7e6d16ed212e062bb7c9'
REG_SHA = 'b0a38fb2721fcad675101d8f97b47b18707db81bcbafe753cceb1223140e45ba'
PROTOCOL_SHA = '26aedd6e47d6e10adc08781bb035572f8338dfb9c5ff1ded68ebf5659c3e5c5c'
CAPS_SHA = '8f82f1a36dcee89c086cad2e71c7296b1b9c03cc12882dcc5370d4286c895279'
RUNS = {'r03': ('A0', 1, 'bb2cd581126243a6b06eb36dd5fc4e6d0a4df23212f393ecc60659d3d6526af3'),
        'r04': ('B', 1, '1180ff13f1f9f9db266cc2541f4cc2d7b017ae0cf340df1012f5f8450712a288'),
        'r11': ('A0', 2, '82fd1fea4fdc9c28595a47c68e9ce20edfd9e6c2dc6377a282844e6c6ed5ac54'),
        'r12': ('B', 2, '86dfb67f36c59583eb7e755e3afda79243c9b1bfd0e42dd3c11ee6ce57bd5d97')}
EVENT = 'Q2-change-5min'
MESSAGE = '改为5分钟，但保留关键证据与只读边界'
MESSAGE_SHA = '8e434d9bbe51a57818413d6025a29797a0863c74b7fb345c456d34840dc12bb5'
LEDGER = Path('/tmp/rc3-pv2/q2-300-later')
FORMAT = 'rc3-q2-later-300-control.v1'
ENGINEERING = 'ENGINEERING_ONLY_NOT_ADMITTED'
LIMITS = {'writer': 6, 'review': 2, 'sdk': 128, 'render': 0}
ROLES = {'initial_writer': 3, 'repair_writer': 3, 'feedback': 1, 'verification': 1,
         'production': 0, 'production_review': 0}
CUTS = {'r03', 'r04', 'r11', 'r12', 'raq2', 'cq2'}


class Error(ValueError):
    pass


def require(value, message):
    if not value:
        raise Error(message)


def canonical(value, *, exists=True):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts
            and not any('oracle' in x.lower() or x.lower() in {'private', 'authkey'} for x in p.parts)
            and p.resolve(strict=exists) == p,
            'canonical ordinary public path required; no aliases/private targets')
    return p


def reference(path):
    p = canonical(path); raw = p.read_bytes()
    return {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def checked(ref):
    require(reference(ref['path']) == ref, 'exact public Ref bytes changed')
    return Path(ref['path']).read_bytes()


def read(path):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    def finite(value):
        raise Error('nonfinite JSON: '+value)
    return json.loads(canonical(path).read_bytes(), object_pairs_hook=pairs, parse_constant=finite)


def helpers():
    base = Path(__file__).resolve().parent
    require(reference(base/'controller.py')['sha256'] == COMMON_SHA
            and reference(base/'supplementary_recorder.py')['sha256'] == SCOPED_SHA, 'frozen helpers differ')
    spec = importlib.util.spec_from_file_location('rc3_s09_scoped', base/'supplementary_recorder.py')
    s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
    return s, s.c


def config(path, sha, flow, engineering):
    require(sys.flags.isolated and sys.dont_write_bytecode and Path(sys.executable).is_absolute(), 'use own absolute Python -I -B')
    require(flow in RUNS, 'only original r03/r04/r11/r12; no E1 later allocation')
    s, c = helpers(); ref = reference(path); require(ref['sha256'] == sha, 'exact Root control hash required')
    a = read(path)
    require(set(a) == {'format', 'status', 'observer_id', 'assurance', 'observed_at_utc', 'implementation_review', 'scope'}, 'finite Root control fields only')
    require(a['format'] == FORMAT and a['status'] == (ENGINEERING if engineering else 'ADMITTED')
            and a['observer_id'] == ('/engineering/rc3-s09' if engineering else '/root')
            and a['assurance'] == ('synthetic_engineering' if engineering else 'host_attested'), 'prospective Root control required')
    checked(a['implementation_review'])
    scope = a['scope']
    require(set(scope) == {'tool', 'common', 'scoped', 'ledger_root', 'origins', 'six_cuts', 'protocol', 'resource_selection'}, 'finite scope binding only')
    require(scope['tool'] == reference(Path(__file__).resolve()) and scope['common'] == reference(Path(__file__).with_name('controller.py'))
            and scope['scoped'] == reference(Path(__file__).with_name('supplementary_recorder.py')), 'reviewed tool/helper bytes changed')
    ledger = canonical(scope['ledger_root'], exists=False)
    require(not ledger.is_relative_to(Path('/tmp/rc3-pv2')) if engineering else ledger == LEDGER, 'one canonical original later ledger')
    require(set(scope['origins']) == set(RUNS) and set(scope['six_cuts']) == CUTS, 'four original continuations and six existing cut identities')
    for name, cuts in scope['six_cuts'].items():
        require(set(cuts) == ({'original_complete', 'equal_budget_evaluated'} if name == 'cq2' else
                              {'original_complete', 'equal_budget_evaluated', 'first_sdk_complete'}), 'preserve actual cut types; no new gate requirement')
        for kind, cut in cuts.items():
            if not engineering:
                require(Path(cut['path']) == Path('/tmp/rc3-pv2')/name/'snapshots'/(kind+'.json'), 'original cut path only')
            checked(cut)  # Body/quality and nested Refs remain opaque.
    for key, digest in (('protocol', PROTOCOL_SHA), ('resource_selection', CAPS_SHA)):
        checked(scope[key]); require(engineering or scope[key]['sha256'] == digest, 'original public protocol/resource selection required')
    row = scope['origins'][flow]
    require(set(row) == {'run', 'frontier', 'project_id', 'revision_id', 'request'}, 'finite original frontier/Request binding')
    state = read(row['run']['path']); checked(row['run'])
    origin = canonical(Path(row['run']['path']).parent)
    expected_arm, repetition, run_sha = RUNS[flow]
    require(state['arm'] == expected_arm and state['repetition'] == repetition and state['case'] == 'Q2', 'original arm/repetition/case required')
    if not engineering:
        require(origin == Path('/tmp/rc3-pv2')/flow and row['run']['sha256'] == run_sha
                and state['project'] == str(Path('/tmp/rc3-pv2')/('p'+flow[1:])), 'original run/project bytes only')
    else:
        require(not origin.is_relative_to(Path('/tmp/rc3-pv2')) and not canonical(state['project']).is_relative_to(Path('/tmp/rc3-pv2')), 'engineering cannot open formal run/project')
    campaign = canonical(state['campaign']); reg_ref = reference(campaign/'registration.json'); reg = read(reg_ref['path'])
    require(state['registration_sha256'] == reg_ref['sha256'] == c.digest(c.encoded(reg)), 'original registration drift')
    require(engineering or (campaign == Path('/tmp/rc3-pv2/cmain') and reg_ref['sha256'] == REG_SHA), 'only original main registration')
    # Do not call old load/validate: their recursive policy checks are outside this public adapter.
    policy = read(reg['exposure_registry']['path']); checked(reg['exposure_registry'])
    require(policy.get('status') == 'FROZEN' and policy.get('excluded_identities'), 'original public Host exclusion policy required')
    c.installation(reg, state['arm'])
    journal = c.Journal(origin); events = journal.events()
    require(events and events[0]['kind'] == 'workflow_initialized' and events[0]['data'] == state, 'original initialized identity changed')
    checked(row['frontier'])
    require(Path(row['frontier']['path']).parent == origin/'journal' and row['frontier'] in
            [reference(origin/'journal'/f"{e['sequence']:06d}.json") for e in events], 'original journal prefix binding required')
    require(reg['cases']['Q2']['events'][EVENT]['message']['sha256'] == MESSAGE_SHA
            and reg['cases']['Q2']['events'][EVENT]['planned_dispatch'] is True, 'original fixed event required')
    root = ledger/flow
    later = {'format': 'rc3-supplementary-run.v1', 'root': str(root), 'campaign': str(ledger), 'slot': flow,
             'registration_sha256': sha, 'profile': 'q2-300', 'case': 'Q2', 'checkpoint': 'Q2_300',
             'whole_run_id': 'flow-'+flow[1:], 'repetition': repetition, 'arm': state['arm'],
             'scope_slot': 'flow-'+flow[1:]+'-later-300s-input', 'project': state['project'], 'page_ids': [],
             'materials': state['materials'], 'budget': ROLES, 'native_limits': ROLES, 'limits': LIMITS,
             'grammar': reg['grammar'], 'origin': str(origin), 'control': ref, 'human': 'NOT_RUN_USER_DEFERRED'}
    return s, c, a, row, journal, state, reg, later


def tip(c, journal):
    events = journal.events()
    return reference(journal.root/'journal'/f"{events[-1]['sequence']:06d}.json") if events else None


def lineage(c, journal, project_id):
    authors = []
    for e in journal.events():
        if e['kind'] != 'native_begun' or e['data']['role'] not in c.WRITER_ROLES:
            continue
        d = e['data']; raw = checked(d['observation']); o = json.loads(raw); spawn = o['spawn']
        require(o['project_id'] == project_id and o['assurance'] == 'host_attested' and o['observation_kind'] == c.OBSERVER_KIND
                and spawn['canonical_task_name'] == spawn['returned_task_name'] == d['executor'], 'author invocation/provenance changed')
        dispatch = read(journal.root/'stages'/d['stage']/'dispatch.json')
        require(dispatch['project_id'] == project_id and dispatch['task_id'] == o['task_id'], 'author belongs to another project/Task')
        authors.append({'executor': d['executor'], 'role': d['role'], 'ordinal': d['ordinal'],
                        'journal_event': reference(journal.root/'journal'/f"{e['sequence']:06d}.json"), 'invocation': d['observation']})
    return authors


class Meter:
    """One physical SDK intent, one charge; journals retain complete real calls."""
    def __init__(self, c, s, journal, origin, state, resources):
        self.c, self.s, self.journal, self.origin, self.state, self.resources = c, s, journal, origin, state, resources
        self.root = journal.root

    def events(self):
        return self.journal.events()

    def unfinished(self):
        return {**{'origin:'+k: v for k, v in self.origin.unfinished().items()}, **self.journal.unfinished()}

    def append(self, kind, data):
        if kind == 'sdk_intent':
            identity = {'project': self.state['project'], 'journal': str(self.root), 'operation_key': data['operation_key']}
            require(not any(e['kind'] == 'resource_charge' and e['data']['identity'] == identity
                            for e in self.resources.journal.events()), 'SDK physical identity already charged; never resend')
            self.resources.charge('sdk', 1, identity)
            event = self.journal.append(kind, data)
            self.resources.journal.append('sdk_projection', {'pool': self.s.pool_key(self.state), 'identity': identity,
                'intent': reference(self.root/'journal'/f"{event['sequence']:06d}.json")})
            return event
        if kind == 'native_begun':
            charge = self.resources.charge('writer' if data['role'] in self.s.WRITERS else 'review', 1,
                {'run': str(self.root), 'ordinal': data['ordinal'], 'executor': data['executor'], 'observation': data['observation']}, actual=True)
            data['within_budget'] = data['within_budget'] and charge['within_budget']
        return self.journal.append(kind, data)


def initialize(control, sha, flow, engineering=False):
    s, c, a, row, origin, old, reg, state = config(control, sha, flow, engineering)
    c.fresh(a['observed_at_utc'])
    ledger = Path(state['campaign']); ledger.parent.mkdir(parents=True, exist_ok=True)
    with (ledger.parent/('.'+ledger.name+'.s09-init.lock')).open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        with origin.locked():
            require(tip(c, origin) == row['frontier'] and not origin.unfinished(), 'original frontier changed or unresolved before admission')
            require(not any(e['kind'] in {'scripted_event', 'scripted_instruction_materialized'} and e['data'].get('event_id') == EVENT
                            for e in origin.events()), 'prospective scope must precede original event release/materialization')
            doc = c.store_for(old).load_document()
            require((doc['project_id'], doc['revision_id'], (doc.get('collaboration') or {}).get('request')) ==
                    (row['project_id'], row['revision_id'], row['request']), 'original current revision/Request changed')
            authors = lineage(c, origin, row['project_id'])
            if not ledger.exists():
                ledger.mkdir(); c.write_once(ledger/'registration.json', Path(control).read_bytes())
                c.save(ledger/'ledger-origin.json', {'root': str(ledger), 'registration_sha256': sha})
            require(reference(ledger/'registration.json')['sha256'] == sha
                    and read(ledger/'ledger-origin.json') == {'root': str(ledger), 'registration_sha256': sha}, 'canonical pool already bound; no directory/config reset')
            root = Path(state['root']); root.mkdir(exist_ok=False)
            c.save(ledger/'runs'/(flow+'.json'), {'root': str(root), 'project': state['project']})
            c.save(root/'run.json', state); j = c.Journal(root); j.append('scoped_initialized', state)
            j.append('origin_author_lineage', {'authors': authors, 'frontier': row['frontier'], 'historical_costs_copied': False})
    return state


@contextmanager
def session(control, sha, flow, engineering=False, *, inspect_only=False):
    s, c, a, row, origin, old, reg, state = config(control, sha, flow, engineering)
    root = Path(state['root']); require(read(root/'run.json') == state, 'copied run/changed scope cannot refresh pool')
    require(reference(Path(state['campaign'])/'registration.json')['sha256'] == sha
            and read(Path(state['campaign'])/'runs'/(flow+'.json')) == {'root': str(root), 'project': state['project']}, 'canonical registered slot differs')
    j = c.Journal(root); resources = s.Resources(state)
    with origin.locked(), j.locked(), resources.locked():
        events = j.events(); require(events[0]['kind'] == 'scoped_initialized' and events[0]['data'] == state, 'later prefix identity changed')
        authors = lineage(c, origin, row['project_id'])
        require(events[1]['kind'] == 'origin_author_lineage' and events[1]['data']['authors'] == authors, 'origin author union changed')
        if not inspect_only:
            linked = [e['data']['frontier'] for e in events if e['kind'] == 'origin_linked']
            require(tip(c, origin) == (linked[-1] if linked else row['frontier']), 'origin frontier changed without confirmed later projection')
            require(not origin.unfinished() and not j.unfinished(), 'old union later SDK outcome unresolved; no retry/refund')
            charges = [e['data']['identity'] for e in resources.journal.events() if e['kind'] == 'resource_charge'
                       and e['data']['pool'] == s.pool_key(state) and e['data']['resource'] == 'sdk']
            projections = [e['data'] for e in resources.journal.events() if e['kind'] == 'sdk_projection' and e['data']['pool'] == s.pool_key(state)]
            require(len(charges) == len(projections) and all(sum(p['identity'] == identity for p in projections) == 1 for identity in charges), 'interrupted SDK charge/projection; unknown blocks writes')
            for p in projections:
                checked(p['intent'])
            frontiers = [e['data']['revision_id'] for e in events if e['kind'] == 'project_frontier']
            require(c.store_for(state).load_document()['revision_id'] == (frontiers[-1] if frontiers else row['revision_id']), 'current project changed outside later chain')
        yield s, c, Meter(c, s, j, origin, state, resources), origin, old, reg, state, row, resources


def event_instruction(c, origin):
    released = [e['data'] for e in origin.events() if e['kind'] == 'scripted_event' and e['data']['event_id'] == EVENT]
    require(len(released) == 1 and checked(released[0]['message']) == MESSAGE.encode(), 'actual original fixed 52B release required')
    return released[0]


def prepared(s, c, j, state, reg, stage, task_id, role):
    """Original main full-own files; public method/summary calls now explicit intents."""
    from deck_master import content_production, service
    c.safe_name(stage); store = c.store_for(state); doc = store.load_document(); task = c.task_for(store, task_id)
    s.role_task(j, state, task, role)
    target = j.root/'stages'/stage; target.mkdir(parents=True, exist_ok=False)
    methods = s.read_methods(j, state, task)
    order = c.record_sdk(j, 'service.task_summary', {'task_id': task_id, 'project': state['project']}, lambda: service.task_summary(store, doc, task))
    c.save(target/'task.json', task); c.save(target/'work-order.json', order)
    c.save(target/'prepared-method-bytes.json', methods); c.save(target/'current-artifacts.json', c.current_manuscript(store))
    c.write_once(target/'public-technical-grammar.json', checked(reg['grammar']))
    if task.get('protocol_version') == 'compose.v2':
        c.save(target/'envelope-metadata.json', {'schema_version': 'compose_result.v2', 'kind': 'compose',
            'variant': content_production.expected_variant(task), 'task_id': task_id, 'operation_id': task['operation_id'],
            'produced_against': task['produced_against'], 'eligibility_digest': task['collaboration_binding']['eligibility_digest'], 'usage_events': []})
    module_root = Path(reg['installations'][state['arm']]['module_file']).parent
    for p in (module_root/'resources/contracts').glob('*.schema.json'):
        c.write_once(target/'schemas'/p.name, p.read_bytes())
    if role == 'repair_writer':
        repair = next(e['data'] for e in j.events() if e['kind'] == 'repair_begun')
        c.write_once(target/'single-feedback.json', checked(repair['feedback_raw'])); c.save(target/'repair-scope.json', repair)
    if role == 'verification':
        c.save(target/'historical-review-and-repair-events.json', [e for e in j.events() if e['kind'] in
               {'feedback_delivered', 'repair_begun', 'result_accepted', 'snapshot_frozen'}])
    dispatch = {'stage': stage, 'role': role, 'task_id': task_id, 'project_id': doc['project_id'],
                'method_release': methods['current_method_release'], 'prepared_at': c.now(), 'status': 'prepared_not_executed'}
    c.save(target/'dispatch.json', dispatch)
    c.save(target/'writer-boundary.json', {'allowed_packet': str(target), 'material_refs': state['materials'],
        'packet_contract': 'original-main-full-own-Q2', 'must_claim_and_read_all_methods': True, 'raw_before_sdk': True,
        'external_image_calls': 0, 'verification_feedback_must_not_be_returned_to_writer': role == 'verification',
        'forbidden': ['private oracles', 'answer banks', 'other arm outputs', 'old native FINALs', 'delegation'],
        'human_acceptance': 'NOT_RUN_USER_DEFERRED'})
    j.append('stage_prepared', dispatch)
    return {'packet': str(target), **dispatch}


def begin(s, c, j, state, reg, row, stage, observation):
    target, dispatch = c.stage_info(j, stage); o = read(observation); spawn = o['spawn']; executor = spawn['canonical_task_name']
    require(o.get('observation_kind') == c.OBSERVER_KIND and o.get('assurance') == 'host_attested'
            and o.get('task_id') == dispatch['task_id'] and o.get('project_id') == row['project_id']
            and executor.startswith('/root/') and spawn.get('returned_task_name') == executor, 'actual own project/Task invocation required')
    c.fresh(o['observed_at_utc']); policy = read(reg['exposure_registry']['path']); excluded = set(policy['excluded_identities'])
    inherited = spawn.get('inherited_identities', []); require(executor not in excluded and not excluded.intersection(inherited), 'excluded preparer/private exposure')
    previous = [e['data'] for e in j.events() if e['kind'] == 'native_begun']
    historical = next(e['data']['authors'] for e in j.events() if e['kind'] == 'origin_author_lineage')
    authors = {e['executor'] for e in historical+previous if e['role'] in c.WRITER_ROLES}
    role = dispatch['role']; require(role in ROLES and ROLES[role], 'finite content/review roles only')
    require(role not in {'feedback', 'verification'} or not ({executor, *inherited} & authors), 'old union later author cannot review')
    same = [e for e in previous if e['executor'] == executor]
    old_same = [e for e in historical if e['executor'] == executor]
    if spawn.get('tool') == 'collaboration.spawn_agent':
        require(spawn.get('fork_turns') == 'none' and not same and not old_same, 'fresh actual fork-none cannot relabel historical actor')
    elif spawn.get('tool') == 'collaboration.followup_task':
        writer = role in {'initial_writer', 'repair_writer'} and (same or old_same) and all(e['role'] in c.WRITER_ROLES for e in same+old_same)
        reviewer = role in {'feedback', 'verification'} and same and all(e['role'] in {'feedback', 'verification'} for e in same)
        require(writer or reviewer, 'followup requires actual same-project writer lineage or same later reviewer')
        require(spawn.get('origin_run') == state['origin'] if old_same and not same else True, 'cross-scope followup must name this exact origin run')
    else:
        raise Error('actual spawn/followup only')
    used = sum(e['role'] == role for e in previous); ordinal = len(previous)+1
    require(not any(e['stage'] == stage for e in previous), 'one actual invocation per prepared stage')
    data = {'ordinal': ordinal, 'stage': stage, 'role': role, 'executor': executor, 'observation': reference(observation),
            'same_role_ordinal': used+1, 'cap': ROLES[role], 'within_budget': used < ROLES[role], 'actual_cost': 'unknown',
            'origin_lineage': old_same if old_same else [], 'actual_invocation_tool': spawn['tool']}
    c.write_once(target/'executions'/f'{ordinal:04d}'/'root-invocation.json', Path(observation).read_bytes())
    j.append('native_begun', data); c.save(target/'executions'/f'{ordinal:04d}'/'launch-ready.json', data)
    return data


def review_accept(c, j, state, stage, ordinal, bootstrap):
    """d0 protected provider/collector; only author set becomes genuine old union later."""
    require(importlib.util.find_spec('deck_master.review_evidence') is not None, 'BLOCKED_MISSING_OWN_CAPABILITY: original protected review')
    from deck_master import content_review, review_evidence, service
    invocation, target, envelope, proof = c.observed_result(j, stage, ordinal)
    require(invocation['role'] in {'feedback', 'verification'}, 'independent review role required')
    task = c.task_for(c.store_for(state), read(target.parent.parent/'dispatch.json')['task_id'])
    store = c.store_for(state); before = store.load_document()
    require(not envelope.get('pages') and not envelope.get('page_order') and not envelope.get('artifact_specs')
            and not envelope.get('usage_events'), 'read-only zero-call review envelope required')
    binding = review_evidence.review_binding(store, before, task, envelope)
    historical = next(e['data']['authors'] for e in j.events() if e['kind'] == 'origin_author_lineage')
    authors = {e['executor'] for e in historical} | {e['data']['executor'] for e in j.events() if e['kind'] == 'native_begun' and e['data']['role'] in c.WRITER_ROLES}
    require(invocation['executor'] not in authors and set(binding['author_execution_refs']) <= authors, 'protected binding requires all actual old union later authors')
    issued = datetime.now(timezone.utc); raw = checked(proof['observation'])
    claims = {**binding, 'provider_id': c.PROVIDER_ID, 'event_id': 'native-'+c.digest(raw)[:40], 'channel': c.CHANNEL,
        'issued_at': issued.isoformat(), 'expires_at': (issued+timedelta(minutes=30)).isoformat(),
        'executor_ref': invocation['executor'], 'reviewer_id': invocation['executor'], 'assurance': 'host_attested',
        'observation_kind': c.OBSERVER_KIND, 'model_output_bytes_sha256': proof['raw']['sha256'],
        'all_native_writer_execution_refs': sorted(authors),
        'evidence_scope': 'original Q2 own full manuscript, later300s; no human/professional evidence'}
    protected = {k: deepcopy(before.get(k)) for k in ('task', 'sources', 'narrative', 'content_plan', 'pages', 'files', 'design_context', 'outputs')}
    with c.native_runtime(bootstrap, raw, claims) as registry:
        context = registry.review_context(store, before, task, envelope, {'provider_id': c.PROVIDER_ID, 'event_id': claims['event_id']})
        args = {'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'], 'result_payload': envelope}
        outcome = c.record_sdk(j, 'service.accept_result.independent_review', args, lambda: service.accept_result(state['project'], **args, adapter_context=context))
    after = store.load_document(); require({k: after.get(k) for k in protected} == protected, 'read-only review changed protected manuscript')
    data = {'ordinal': ordinal, 'role': invocation['role'], 'task_id': task['task_id'], 'raw': proof['raw'],
            'executor': invocation['executor'], 'outcome': outcome, 'current_gate': content_review.preproduction_status(store, after), 'binding': binding,
            'all_native_writer_execution_refs': sorted(authors)}
    j.append('result_accepted', data)
    return data


def accepted_repair_layers(j):
    accepted = {e['data']['ordinal'] for e in j.events() if e['kind'] == 'result_accepted'}
    return {(read(j.root/'stages'/e['data']['stage']/'task.json').get('collaboration_binding') or {}).get('phase')
            for e in j.events() if e['kind'] == 'native_begun' and e['data']['role'] == 'repair_writer'
            and e['data']['ordinal'] in accepted}


FIELDS = {'release': {'trigger'}, 'materialize': set(), 'request': set(), 'inputs': set(), 'continue-content': set(),
          'review-request': {'role'}, 'repair-request': set(),
          'prepare': {'stage', 'task_id', 'role'}, 'review-prepare': {'stage', 'role', 'bootstrap'},
          'begin': {'stage', 'observation'}, 'claim': {'stage', 'ordinal'},
          'observe': {'stage', 'ordinal', 'result', 'result_sha256', 'observation', 'observation_sha256'},
          'objects': {'stage', 'ordinal'}, 'accept': {'stage', 'ordinal'},
          'review-accept': {'stage', 'ordinal', 'bootstrap'}, 'feedback': {'stage', 'ordinal'},
          'repair': {'necessity'}, 'repair-task': {'layer'}, 'snapshot': {'name', 'native_manifest'}, 'status': set()}


def advance(action, control, sha, flow, payload=None, engineering=False):
    require(action in FIELDS and isinstance(payload or {}, dict) and set(payload or {}) == FIELDS[action], 'finite action arguments only')
    p = payload or {}
    for key in ('trigger', 'bootstrap', 'observation', 'result', 'necessity', 'native_manifest'):
        if p.get(key) is not None:
            canonical(p[key])  # Never hand a private/alias target to frozen readers.
    with session(control, sha, flow, engineering, inspect_only=action == 'status') as (s, c, j, origin, old, reg, state, row, resources):
        if action == 'status':
            return {'pool': s.pool_key(state), 'resources': resources.totals(), 'old_pending': origin.unfinished(),
                    'later_pending': j.journal.unfinished(), 'origin_frontier': tip(c, origin), 'later_frontier': tip(c, j),
                    'human': 'NOT_RUN_USER_DEFERRED'}
        # Already performed native calls/originals must remain recordable even
        # after an overrun. No earlier result in that scope may then be consumed
        # as admitted same-budget work by choosing a different ordinal/role.
        if action not in {'begin', 'observe'}:
            s.budget_clean(j, state)
            require(not any(e['kind'] == 'native_begun' and not e['data']['within_budget'] for e in j.events()),
                    'actual role over-budget work retained; scope consumption blocked')
        if action == 'release':
            require(not any(e['kind'] == 'scripted_event' and e['data']['event_id'] == EVENT for e in origin.events()), 'event occurrence already released')
            trigger = read(p['trigger'])
            require(trigger.get('six_cut_binding') == read(control)['scope']['six_cuts'], 'Root trigger must bind the six actual original cut sets; no PASS requirement')
            result = c.scripted_event(origin, old, reg, EVENT, p['trigger'])
            event_instruction(c, origin); j.append('origin_linked', {'frontier': tip(c, origin), 'event_id': EVENT})
        elif action == 'materialize':
            event_instruction(c, origin)
            previous = [e['data'] for e in origin.events() if e['kind'] == 'scripted_instruction_materialized' and e['data']['event_id'] == EVENT]
            if previous:
                require(len(previous) == 1, 'ambiguous original materialization')
                result = previous[0]['instruction_evidence']
                require(c.store_for(old).read_object_bytes(result['source_ref']) == MESSAGE.encode(), 'confirmed original blob differs')
                confirmations = [e['data']['instruction_evidence'] for e in j.events() if e['kind'] == 'later_instruction']
                require(confirmations == [result], 'interrupted materialization confirmation; preserve unknown without retry')
                return result  # Same confirmed logical occurrence; no SDK/cost or new event.
            else:
                meter = Meter(c, s, origin, origin, state, resources)
                result = c.materialize_instruction(meter, old, EVENT)
                j.append('origin_linked', {'frontier': tip(c, origin), 'event_id': EVENT})
            require(not any(e['kind'] == 'later_instruction' for e in j.events()), 'logical materialization already confirmed in later scope')
            j.append('later_instruction', {'event_id': EVENT, 'instruction_evidence': result, 'origin_frontier': tip(c, origin)})
        else:
            instructions = [e['data']['instruction_evidence'] for e in j.events() if e['kind'] == 'later_instruction']
            require(len(instructions) == 1, 'confirmed same-project 52B materialization required')
            instruction = instructions[0]; require(c.store_for(state).read_object_bytes(instruction['source_ref']) == MESSAGE.encode(), 'same-project instruction bytes differ')
            if action in {'request', 'inputs'}:
                from deck_master import service
                store = c.store_for(state); doc = store.load_document()
                require(not any(e['kind'] == 'later_inputs_updated' for e in j.events()), 'inputs already updated; no second event/update')
                if action == 'request':
                    require(state['arm'] == 'B' and not any(e['kind'] == 'later_request_replaced' for e in j.events()), 'B current Request replacement once only')
                    from deck_master import collaboration
                    req = (doc.get('collaboration') or {}).get('request') or {}
                    require(req == row['request'] and req.get('intent') == 'review_only' and not req.get('closed') and not req.get('paused'), 'actual original open review_only Request required')
                    request_scope = {'subject': 'deck', 'page_ids': [x['page_id'] for x in doc['pages']], 'page_manifest_ref': None,
                        'external_artifact_ref': None, 'layers': ['narrative', 'plan', 'page_copy', 'speech', 'review'],
                        'allow_page_membership_change': True, 'allow_page_order_change': True, 'purpose': 'working'}
                    args = {'input': {'intent': 'content_only', 'content_intent': 'content_full', 'scope': request_scope,
                                      'replace_request_id': req['request_id'], 'instruction_evidence': instruction},
                            'base_revision': doc['revision_id'], 'operation_id': str(c.uuid.uuid4())}
                    result = c.record_sdk(j, 'collaboration.start_request', args, lambda: collaboration.start_request(state['project'], **args))
                    after = store.load_document(); require(after['revision_id'] == result['revision_id'], 'Request CAS advanced after result')
                    j.append('later_request_replaced', {'old_request': req, 'old_revision': doc['revision_id'], 'result': result,
                            'new_request': after['collaboration']['request'], 'new_revision': after['revision_id'], 'instruction': instruction})
                else:
                    if state['arm'] == 'B':
                        replace = [e['data'] for e in j.events() if e['kind'] == 'later_request_replaced']
                        require(len(replace) == 1 and doc['collaboration']['request'] == replace[0]['new_request'], 'actual new B content Request required before inputs')
                    else:
                        require(not doc.get('collaboration'), 'A0 retains its original legacy inputs/content route')
                    actual = c.record_sdk(j, 'service.inputs_show', {'project': state['project']}, lambda: service.inputs_show(state['project']))
                    require(actual['revision_id'] == doc['revision_id'], 'inputs query raced current revision')
                    brief = actual['task']['brief']; require(brief.count('10 分钟') == 1 and '5 分钟' not in brief, 'unique original 10 分钟 required; no semantic task rewrite')
                    patch = {'task_patch': {'brief': brief.replace('10 分钟', '5 分钟')}, 'reason': MESSAGE, 'mode': 'auto'}
                    args = {'patch': patch, 'base_revision': actual['revision_id'], 'operation_id': 's09-'+c.uuid.uuid4().hex}
                    result = c.record_sdk(j, 'service.inputs_update', args, lambda: service.inputs_update(state['project'], **args))
                    after = store.load_document(); require(after['revision_id'] == result['revision_id'], 'inputs CAS advanced after result')
                    require(after['task'] == {**doc['task'], 'brief': patch['task_patch']['brief']} and after['sources'] == doc['sources'], 'mechanical update changed facts/sources')
                    j.append('later_inputs_updated', {'actual_inputs': actual, 'patch': patch, 'result': result, 'pending_tasks': result.get('pending_tasks', [])})
            elif action in {'review-request', 'repair-request'}:
                from deck_master import collaboration
                require(state['arm'] == 'B', 'BLOCKED_MISSING_OWN_CAPABILITY: no modern Request bridge in A0')
                store = c.store_for(state); doc = store.load_document(); current = (doc.get('collaboration') or {}).get('request') or {}
                repair = [e['data'] for e in j.events() if e['kind'] == 'repair_begun']
                if action == 'review-request':
                    role = p['role']; require(role in {'feedback', 'verification'}, 'one feedback or readonly verification only')
                    if role == 'feedback':
                        require(not any(e['kind'] in {'feedback_delivered', 'repair_begun'} for e in j.events())
                                and all((j.root/'snapshots'/(n+'.json')).is_file() for n in ('original_complete', 'first_sdk_complete')), 'later original/accepted cuts before single feedback')
                    else:
                        require(len(repair) == 1 and set(repair[0]['necessary_layers']) <= accepted_repair_layers(j), 'verification needs actual accepted necessary repair layers')
                    previous = [e['data'] for e in j.events() if e['kind'] == 'later_review_request' and e['data']['role'] == role]
                    if previous:
                        require(len(previous) == 1 and previous[0]['request'] == current and not current.get('closed'), 'review Request already consumed/changed')
                        return previous[0]['result']
                    request_scope = {'subject': 'pages', 'page_ids': [e['page_id'] for e in doc['pages']],
                        'page_manifest_ref': doc.get('content_plan'), 'external_artifact_ref': None, 'layers': ['review'],
                        'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'review'}
                    request_input = {'intent': 'review_only', 'content_intent': None, 'scope': request_scope}
                else:
                    require(len(repair) == 1 and not any(e['kind'] == 'later_repair_request' for e in j.events())
                            and not any(e['kind'] == 'native_begun' and e['data']['role'] == 'verification' for e in j.events()), 'single necessary repair Request before verification')
                    layers = [x for x in ('narrative', 'plan', 'page_copy', 'speech') if
                              (x == 'narrative' and 'argument' in repair[0]['necessary_layers']) or
                              (x in {'plan', 'page_copy'} and 'page_copy' in repair[0]['necessary_layers']) or
                              (x == 'speech' and 'speech' in repair[0]['necessary_layers'])]
                    request_scope = {'subject': 'deck', 'page_ids': [e['page_id'] for e in doc['pages']],
                        'page_manifest_ref': None, 'external_artifact_ref': None, 'layers': layers+['review'],
                        'allow_page_membership_change': 'page_copy' in repair[0]['necessary_layers'],
                        'allow_page_order_change': False, 'purpose': 'working'}
                    request_input = {'intent': 'content_only', 'content_intent': 'speech_only' if layers == ['speech'] else 'content_full', 'scope': request_scope}
                args = {'input': {**request_input, 'replace_request_id': current.get('request_id'), 'instruction_evidence': instruction},
                        'base_revision': doc['revision_id'], 'operation_id': str(c.uuid.uuid4())}
                result = c.record_sdk(j, 'collaboration.start_request.'+action, args, lambda: collaboration.start_request(state['project'], **args))
                after = store.load_document(); require(after['revision_id'] == result['revision_id'], 'lifecycle Request CAS advanced after result')
                j.append('later_review_request' if action == 'review-request' else 'later_repair_request',
                         {'role': p.get('role'), 'old_request': current, 'old_revision': doc['revision_id'],
                          'request': after['collaboration']['request'], 'result': result, 'instruction': instruction})
            elif action == 'continue-content':
                from deck_master import service
                req = (c.store_for(state).load_document().get('collaboration') or {}).get('request') or {}
                require(state['arm'] == 'B' and req.get('intent') == 'content_only'
                        and not any(e['kind'] in {'feedback_delivered', 'repair_begun'} for e in j.events()), 'only B original content progression before feedback; no legacy production routing')
                result = c.record_sdk(j, 'service.continue_project.content_only', {'project': state['project']}, lambda: service.continue_project(state['project']))
            elif action == 'prepare':
                require(any(e['kind'] == 'later_inputs_updated' for e in j.events()), 'real input revision Task must exist first')
                result = prepared(s, c, j, state, reg, p['stage'], p['task_id'], p['role'])
            elif action == 'review-prepare':
                from deck_master import content_review
                require(p['role'] in {'feedback', 'verification'}, 'finite feedback/readonly verification')
                if p['role'] == 'feedback':
                    require(not any(e['kind'] == 'feedback_delivered' for e in j.events())
                            and all((j.root/'snapshots'/(n+'.json')).is_file() for n in ('original_complete', 'first_sdk_complete')), 'freeze later native and accepted complete cuts before single feedback')
                else:
                    require(any(e['kind'] == 'repair_begun' for e in j.events()), 'verification only after necessary repair')
                if reg['installations'][state['arm']].get('adapter_profile') == 'A0-public-legacy':
                    result = c.record_sdk(j, 'content_review.dispatch_preproduction_review.A0-original', {}, lambda: content_review.dispatch_preproduction_review(state['project']))
                else:
                    with c.native_runtime(p['bootstrap']) as registry:
                        result = c.record_sdk(j, 'content_review.dispatch_preproduction_review', {'bootstrap': reference(p['bootstrap'])},
                            lambda: content_review.dispatch_preproduction_review(state['project'], adapter_context=registry.channel_context()))
                j.append('review_dispatch', {'role': p['role'], 'actual_result': result})
                if result['status'] == 'review_dispatched':
                    outcome = result; result = prepared(s, c, j, state, reg, p['stage'], outcome['task']['task_id'], p['role'])
                    c.save(Path(result['packet'])/'review-packet.json', c.store_for(state).read_object_json(outcome['review_draft_ref']))
                    c.save(Path(result['packet'])/'review-dispatch.json', outcome)
            elif action == 'begin':
                result = begin(s, c, j, state, reg, row, p['stage'], p['observation'])
            elif action == 'claim':
                from deck_master import service
                inv, target = c.execution(j, p['stage'], p['ordinal']); require(inv['within_budget'], 'actual over-budget native retained; cannot consume')
                dispatch = read(target.parent.parent/'dispatch.json'); task = c.task_for(c.store_for(state), dispatch['task_id'])
                args = {'task_id': task['task_id'], 'execution_ref': inv['executor'], 'supported_protocols': [task['protocol_version']] if task.get('protocol_version') else None,
                        'capabilities': task.get('required_capabilities')}
                claim = c.record_sdk(j, 'service.task_start', args, lambda: service.task_start(state['project'], **args))
                result = s.read_methods(j, state, task)
                require(result['status'] == 'current' and result['current_method_release'] == dispatch['method_release'], 'own current method bytes changed')
                c.save(target/'claim.json', claim); r = c.save(target/'method-read-record.json', result)
                j.append('method_bytes_returned', {'ordinal': p['ordinal'], 'executor': inv['executor'], 'record': r, 'limitation': 'full bytes returned; actual native read separately observed'})
            elif action == 'observe':
                result = c.observe(j, state, **{k: p[k] for k in ('stage', 'ordinal')}, result_path=p['result'], result_sha256=p['result_sha256'], observation_path=p['observation'], observation_sha256=p['observation_sha256'])
            elif action in {'objects', 'accept', 'review-accept'}:
                inv, _, envelope, _ = c.observed_result(j, p['stage'], p['ordinal'])
                require(not any(envelope.get(k) for k in ('usage_events', 'files', 'artifact_specs', 'generation_result', 'style_analysis')),
                        'Q2 content-only image/render/production budget is zero')
                require(inv['role'] not in c.WRITER_ROLES or not envelope.get('reviews'), 'Writer cannot supply independent feedback/review')
                if action == 'objects': result = c.materialize_native_objects(j, state, p['stage'], p['ordinal'])
                elif action == 'review-accept': result = review_accept(c, j, state, p['stage'], p['ordinal'], p['bootstrap'])
                else: result = c.accept(j, state, p['stage'], p['ordinal'])
            elif action == 'feedback':
                c.observed_result_for_feedback(j, p['stage'], p['ordinal'])
                resources.once('content_feedback', 'one', p); result = c.deliver_feedback(j, p['stage'], p['ordinal'])
            elif action == 'repair':
                require(not any(e['kind'] == 'repair_begun' for e in j.events()), 'one necessary semantic repair cycle')
                result = c.repair_begin(j, p['necessity']); resources.once('content_repair_cycle', 'one', result)
            elif action == 'repair-task':
                from deck_master import content_production
                repair = [e['data'] for e in j.events() if e['kind'] == 'repair_begun']
                require(len(repair) == 1 and p['layer'] in repair[0]['necessary_layers']
                        and not any(e['kind'] == 'native_begun' and e['data']['role'] == 'verification' for e in j.events()), 'only declared necessary layers before readonly verification')
                require(not any(e['kind'] == 'repair_task_dispatched' and e['data']['layer'] == p['layer'] for e in j.events()), 'same necessary repair layer already dispatched')
                require(state['arm'] == 'B', 'BLOCKED_MISSING_OWN_CAPABILITY: no B phased repair bridge in A0')
                store = c.store_for(state); doc = store.load_document()
                # Own public phase API has initial/input_revision/import_draft;
                # repair is the metered native role, never an invented SDK intent.
                args = {'operation_id': 's09-repair-'+c.uuid.uuid4().hex, 'intent': 'initial', 'phase': p['layer'],
                        'page_ids': [e['page_id'] for e in doc['pages']]}
                result = c.record_sdk(j, 'content_production.open_phase_task.necessary_repair', args,
                                     lambda: content_production.open_phase_task(store, doc, **args))
                j.append('repair_task_dispatched', {'layer': p['layer'], 'task': result, 'necessity_record': repair[0]['necessity_record']})
            elif action == 'snapshot':
                require(p['name'] in {'original_complete', 'first_sdk_complete', 'owner_later'}, 'distinct later300s cuts only; no old equal/qualified/E1 replacement')
                require(p['name'] == 'original_complete' or p['native_manifest'] is None, 'native manifest belongs only to actual original complete')
                result = c.snapshot(j, state, p['name'], native_manifest=p['native_manifest'])
                j.append('later300s_cut', {'name': p['name'], 'snapshot': result, 'old_equal_qualified_unchanged': True})
            else:
                raise Error('unimplemented finite action')
        j.append('project_frontier', {'revision_id': c.store_for(state).load_document()['revision_id'], 'action': action})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['initialize', *FIELDS])
    parser.add_argument('--control', required=True); parser.add_argument('--control-sha256', required=True)
    parser.add_argument('--flow', choices=list(RUNS), required=True)
    parser.add_argument('--payload'); parser.add_argument('--engineering', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'initialize':
            require(args.payload is None, 'initialize has no caller operation/metadata overrides')
            result = initialize(args.control, args.control_sha256, args.flow, args.engineering)
        else:
            result = advance(args.action, args.control, args.control_sha256, args.flow, read(args.payload) if args.payload else {}, args.engineering)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        print(json.dumps({'status': 'refused', 'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
