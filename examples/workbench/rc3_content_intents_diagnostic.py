"""Actual Host-authored content-intent diagnostics; no fixture content.

This helper performs public Runtime calls and saves exact raw workorders and
responses. The model supplies authored payload JSON separately after reading
its actual methods. It never creates Narrative/Page completion by editing a
Document, minting reviewer evidence or importing test helpers.
"""
from pathlib import Path
import argparse
import hashlib
import json
import traceback
import uuid

from deck_master import __version__, collaboration, content_production, eligibility, method_resources, service, tasks
from deck_master.store import Store


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def scope(pages, layers, *, membership=False, purpose='working'):
    return {'subject': 'deck', 'page_ids': list(pages), 'page_manifest_ref': None,
            'external_artifact_ref': None, 'layers': list(layers),
            'allow_page_membership_change': membership, 'allow_page_order_change': False, 'purpose': purpose}


def evidence(store, text, locator):
    return {'kind': 'host_attested_instruction', 'source_ref': store.put_blob(text.encode(), ext='txt'),
            'source_locator': locator, 'actor_id': None, 'transport_receipt_ref': None, 'presentation_ref': None}


def current_task(store):
    doc = store.load_document()
    return next((store.read_object_json(ref) for ref in reversed(doc['tasks'])
                 if store.read_object_json(ref)['status'] in ('awaiting_host', 'running')), None)


def runtime_provenance():
    return {'package_version': __version__, 'modules': {
        module.__name__: {'path': str(Path(module.__file__).resolve()),
                          'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
        for module in (service, collaboration, content_production, eligibility, method_resources, tasks)}}


def capture(project, out):
    store = Store(project); doc = store.load_document(); task = current_task(store)
    result = {'module_path': str(Path(service.__file__).resolve()), 'revision_id': doc['revision_id'],
              'runtime_provenance': runtime_provenance(),
              'compatibility': doc['compatibility'], 'request': doc['collaboration']['request'],
              'completion': content_production.completion_status(store, doc), 'task': task}
    if task:
        result['methods'] = method_resources.read_skill_methods('deck-content', project=project, task_id=task['task_id'])
    save(out, result)
    return result


def start(root, intent, source, instruction, *, manuscript=None, pages=('p1', 'p2')):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    project = root / intent
    allowed = ['narrative', 'plan'] if intent == 'plan_only' else (
        ['speech', 'plan'] if intent == 'speech_only' else ['narrative', 'plan', 'page_copy', 'speech'])
    if manuscript:
        allowed = sorted(set(allowed + ['page_copy']))  # initial actual imported manuscript only
    bounded = scope(pages, allowed, membership=True)
    request = {'intent': 'content_only', 'content_intent': intent, 'scope': bounded}
    result = service.create(project, brief=instruction, sources=[source], audience='新入组研究生与预约员',
                            presentation_mode='live' if intent == 'speech_only' else 'read_alone',
                            draft=manuscript, request_input=request)
    save(root / (intent + '-create.json'), result)
    store = Store(project)
    declared = evidence(store, instruction, 'codex-collaboration-agent:/root/rc3_04_owner/skills_install/owner-delegated-diagnostic')
    grant = collaboration.grant(project, input={'mode': 'delegate', 'actions': ['dispatch.compose', 'proposal.adopt'],
        'scope': bounded, 'delegated_topics': ['direction', 'manuscript', 'speech'],
        'constraints': {'diagnostic': 'Only this synthetic material, two named pages and no visual production'},
        'max_external_calls': 0, 'max_candidate_count': 0, 'adoption_policy': 'within_scope',
        'instruction_evidence': declared}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    save(root / (intent + '-delegation.json'), grant)
    if manuscript:
        save(root / (intent + '-continue-initial.json'), service.continue_project(project))
    return capture(project, root / (intent + '-workorder-initial.json'))


def submit(project, payload_path, execution_ref, out):
    store = Store(project); task = current_task(store)
    if task is None:
        raise RuntimeError('No actual pending content task; do not fabricate a workorder')
    payload = json.loads(Path(payload_path).read_text())
    phase = task['collaboration_binding']['phase']
    variant = content_production.PHASE_VARIANT[phase]
    order = service.task_summary(store, store.load_document(), task)
    methods = method_resources.read_task_methods(project, task['task_id'])
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': variant,
                'task_id': task['task_id'], 'operation_id': task['operation_id'],
                'produced_against': task['produced_against'],
                'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
                'payload': payload, 'usage_events': []}
    save(str(out) + '.envelope.json', envelope)
    try:
        service.task_start(project, task_id=task['task_id'], execution_ref=execution_ref,
                           supported_protocols=[task['protocol_version']], capabilities=task['required_capabilities'])
        result = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                        produced_against=task['produced_against'], result_payload=envelope)
    except Exception as exc:
        save(out, {'status': 'actual_runtime_failure', 'workorder': order, 'method_read': methods,
                   'execution_ref': execution_ref, 'authored_payload': str(Path(payload_path).resolve()),
                   'authored_payload_sha256': hashlib.sha256(Path(payload_path).read_bytes()).hexdigest(),
                   'error': str(exc), 'traceback': traceback.format_exc()})
        raise
    response = {'workorder': order, 'method_read': methods, 'authored_payload': str(Path(payload_path).resolve()),
                'runtime_provenance': runtime_provenance(),
                'authored_payload_sha256': hashlib.sha256(Path(payload_path).read_bytes()).hexdigest(),
                'execution_ref': execution_ref, 'result': result,
                'completion': content_production.completion_status(store, store.load_document())}
    save(out, response)
    return response


def adopt(project, ref, delegation, out):
    store = Store(project); doc = store.load_document(); obj = store.read_object_json(ref)
    family = 'narrative' if obj['schema_version'] == 'narrative.v1' else 'plan'
    projection = 'direction' if family == 'narrative' else 'page_roles'
    current_scope = doc['collaboration']['request']['scope']
    exact_scope = {**current_scope, 'layers': [family]}
    instruction = evidence(store, 'Owner委派的合成诊断范围内，Host实际审阅并选择这一具体提案；非人类或客户接受。',
                           'codex-collaboration-agent:/root/rc3_04_owner/skills_install/actual-proposal-selection')
    decision = collaboration.record_decision(project, input={'topic': 'direction', 'disposition': 'accepted',
        'authority_mode': 'delegated', 'delegation_ref': delegation, 'scope': exact_scope,
        'value': {'selected_ref': ref, 'rationale': 'Preserves the original synthetic rule boundaries, explicit responsibilities and exceptions'},
        'instruction_evidence': instruction, 'subject_refs': [{'artifact_kind': obj['schema_version'].split('.')[0],
            'artifact_ref': ref, 'projection': projection}]}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    result = content_production.adopt_proposal(project, input={'proposal_ref': ref, 'decision_ref': decision['decision_ref'],
        'write_scope': exact_scope}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    save(out, {'decision': decision, 'adoption': result})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['capture', 'submit', 'continue'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--payload')
    parser.add_argument('--execution-ref', default='codex-collaboration-agent:/root/rc3_04_owner/skills_install')
    args = parser.parse_args()
    if args.action == 'capture':
        result = capture(args.project, args.out)
    elif args.action == 'submit':
        result = submit(args.project, args.payload, args.execution_ref, args.out)
    else:
        result = service.continue_project(args.project); save(args.out, result)
    print(json.dumps({'status': result.get('status') or (result.get('result') or {}).get('status'),
                      'completion': result.get('completion'), 'out': args.out}, ensure_ascii=False))
