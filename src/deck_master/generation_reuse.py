"""Explicit zero-call adoption of a settled, same-project native original.

This is not execution transfer: both calls retain their own states and identity.
Only committed native observations are sources, never a caller's receipt JSON.
"""
from copy import deepcopy

from . import eligibility, generation, tasks
from .models import canonical_json_bytes, sha256_bytes, validate_schema


def reject(field, message):
    raise generation._error('generation_reuse_invalid', field, message, conflict=True)


def owned(store, document, task, request_id, attempt_id):
    request, request_ref = generation._read_owned(store, task, 'generation_requests', request_id)
    attempt, attempt_ref = generation._read_owned(store, task, 'generation_attempts', attempt_id)
    validate_schema('generation_request', request); validate_schema('generation_attempt', attempt)
    if (request['task_id'] != task['task_id'] or attempt['task_id'] != task['task_id']
            or request['project_id'] != document['project_id'] or attempt['project_id'] != document['project_id']
            or attempt['request_ref'] != request_ref
            or request['input_hash'] != sha256_bytes(canonical_json_bytes(request['input']))):
        reject('request', 'request and attempt must retain their actual project and Task ownership')
    call = next((c for c in task['call_allowances'] if c['allowance_id'] == attempt['allowance_id']), None)
    if not call or call['state'] != 'consumed' or call.get('execution_ref') != attempt['execution_ref']:
        reject('allowance', 'reuse requires both original, independently consumed calls')
    return request, request_ref, attempt, attempt_ref, call


def original(store, document, source, request, request_ref, attempt, attempt_ref, file):
    """Validate the persisted source chain without reissuing/refreshing a receipt."""
    from .native_image_evidence import COLLECTOR, SOURCE
    if file not in attempt['output_refs']:
        reject('output', 'source Attempt does not own this original output')
    store.read_object_bytes(file)
    begun, begun_ref = attempt, attempt_ref
    seen = set()
    while begun.get('previous_ref'):
        if begun_ref['sha256'] in seen or len(seen) >= 4096:
            reject('attempt', 'invalid original Attempt ancestry')
        seen.add(begun_ref['sha256'])
        begun_ref = begun['previous_ref']; begun = store.read_object_json(begun_ref)
        validate_schema('generation_attempt', begun)
        if any(begun.get(k) != attempt.get(k) for k in ('attempt_id','task_id','project_id',
                'request_ref','allowance_id','execution_ref','started_at_ms','execution_identity')):
            reject('attempt', 'original Attempt identity changed')
    call = next(c for c in source['call_allowances'] if c['allowance_id'] == attempt['allowance_id'])
    for observation_ref in attempt['observations']:
        observation = store.read_object_json(observation_ref)
        validate_schema('tool_observation', observation)
        metadata = observation.get('source') or {}
        if (observation.get('observer') != 'tool_observed' or observation.get('collector') != COLLECTOR
                or metadata.get('source') != SOURCE or (observation.get('output') or {}).get('sha256') != file['sha256']):
            continue
        receipt_ref = metadata.get('receipt_ref')
        if not receipt_ref:
            continue
        receipt = store.read_object_json(receipt_ref); validate_schema('native_image_receipt', receipt)
        claims = receipt['claims']; binding = claims.get('binding') or {}
        raw = store.read_object_bytes(receipt['raw_event_ref'])
        expected = {'project_id': document['project_id'], 'task_id': source['task_id'],
            'generation_request_ref': request_ref, 'generation_request_id': request['request_id'],
            'input_hash': request['input_hash'], 'attempt_ref': begun_ref, 'attempt_id': attempt['attempt_id'],
            'allowance_id': attempt['allowance_id'], 'execution_ref': attempt['execution_ref'],
            'execution_identity': attempt.get('execution_identity'), 'prompt': request['input']['prompt'],
            'references': request['input']['references'], 'parameters': request['input']['parameters']}
        if (any(binding.get(k) != v for k,v in expected.items())
                or claims.get('status') != 'completed' or claims.get('tool_name') != 'image_gen__imagegen'
                or claims.get('output_sha256') != file['sha256']
                or claims.get('provider_id') != receipt['provider_id']
                or receipt['provider_id'] != metadata.get('provider_id')
                or claims.get('event_id') != metadata.get('event_id')
                or sha256_bytes(raw) != metadata.get('raw_event_sha256')
                or call.get('invocation_ref') != observation['invocation_ref']):
            reject('receipt', 'persisted native evidence no longer matches its actual source ledger')
        compared = generation.comparison(request, observation)
        if compared['status'] != 'match':
            reject('observation', 'source native arguments must completely match the frozen request')
        return observation, observation_ref, receipt_ref
    reject('observation', 'only an already committed original native controller observation may be reused')


def budget_current(store, document, task):
    """A zero-call reuse may exhaust, but never exceed, a current ancestor cap."""
    ref = eligibility.binding_of(task).get('authorization_ref')
    if not ref:
        reject('authorization', 'reuse requires an explicitly bound original authorization')
    records = {r['authorization_id']: r for _,r in eligibility._authorization_heads(store, document)}
    record = store.read_object_json(ref)
    lineages = {key: eligibility._current_authorization_lineage(store, records, value)
                for key,value in records.items()}
    usage = {}
    for task_ref in document['tasks']:
        item = store.read_object_json(task_ref)
        identity = eligibility.task_authorization_id(store, item)
        usage[identity] = usage.get(identity,0) + sum(c['state'] in eligibility.HELD_STATES for c in item['call_allowances'])
    for identity in eligibility._current_authorization_lineage(store, records, record):
        ancestor = records.get(identity)
        if ancestor is None:
            reject('authorization', 'original authorization ancestry is missing')
        if eligibility._planning_only_zero_authority(store, ancestor, document=document):
            continue
        used = sum(usage.get(child,0) for child,lineage in lineages.items() if identity in lineage)
        if used > ancestor['max_external_calls']:
            reject('budget', 'actual held/consumed calls exceed the current authorization ceiling')


def adoption_binding(store, document, task, envelope, staged):
    binding = envelope['generation_result']
    selector = binding.get('reuse_from')
    if (set(binding) != {'request_id','attempt_id','reuse_from'} or not isinstance(selector,dict)
            or set(selector) != {'task_id','request_id','attempt_id'}):
        reject('reuse_from', 'name one registered source Task, Request and Attempt')
    if 'settled_image_reuse_v1' not in (task.get('host_protocol') or {}).get('capabilities',[]):
        reject('host_protocol', 'the original execution must explicitly declare settled_image_reuse_v1 before reuse')
    source = tasks._lookup_task(document, selector['task_id'], store)
    if (source['task_id'] == task['task_id'] or source['kind'] != 'blueprint'
            or not generation.is_new(source) or source['status'] in ('cancelled','superseded')
            or task['kind'] != 'blueprint' or task['status'] != 'running'
            or len(task['scope_pages']) != 1 or task['scope_pages'] != source['scope_pages']
            or any(t.get('stage_request',{}).get('mode') == 'trial' for t in (task,source))):
        reject('task', 'v1 reuse requires distinct non-trial source and destination blueprint Tasks')
    for ref in document['tasks']:
        if any(c['state'] in ('unknown','in_flight') for c in store.read_object_json(ref)['call_allowances']):
            reject('allowance', 'resolve every project-wide unknown or in-flight call before reuse')
    targets = {'page_ids':task['scope_pages'],'layers':['blueprint']}
    if tasks.task_method_contract_changed(task):
        reject('methods', 'destination must retain the current execution contract')
    for item in (source,task):
        if not tasks.task_inputs_current(store,document,item):
            reject('inputs', 'both Tasks must still consume their actual current inputs and methods')
        eligibility.guard(store,document,'task.accept',context={'task':item,'targets':targets})
        budget_current(store,document,item)
    a = owned(store,document,task,binding['request_id'],binding['attempt_id'])
    b = owned(store,document,source,selector['request_id'],selector['attempt_id'])
    if a[2]['execution_ref'] == b[2]['execution_ref']:
        reject('execution_ref','source and destination must retain different actual executions')
    for item,values in ((task,a),(source,b)):
        generation._validate_input(store,document,item,values[0]['input'])
    left,right = deepcopy(a[0]['input']),deepcopy(b[0]['input'])
    left.pop('basis');right.pop('basis')
    if left != right:
        reject('input','all frozen generation inputs except independently validated basis must match')
    specs = envelope.get('artifact_specs') or []
    if len(specs)!=1 or specs[0].get('role')!='blueprint':
        reject('artifact_specs','reuse adopts exactly one original blueprint')
    output_hash = sha256_bytes(staged[specs[0]['file_id']]['bytes'])
    file = next((ref for ref in b[2]['output_refs'] if ref['sha256']==output_hash),None)
    if file is None:
        reject('output','submitted bytes differ from the source original')
    observation, observation_ref, receipt_ref = original(store,document,source,b[0],b[1],b[2],b[3],file)
    if generation.comparison(a[0],observation)['status']!='match':
        reject('input','source native input is not a full match for destination intent')
    eligibility.guard(store, document, 'generation.reuse', context={'task':task,'targets':targets})
    authority = eligibility.covering_authorization_ref(store, document, 'generation.reuse', targets)
    if authority is None or eligibility.binding_of(task).get('adoption_policy') != 'within_scope':
        reject('authorization', 'explicit current reuse authorization and within-scope adoption are required')
    association = {'schema_version':'generation_reuse.v1','project_id':document['project_id'],
        'operation_id':task['operation_id'],'destination_task_id':task['task_id'],'source_task_id':source['task_id'],
        'destination_request_ref':a[1],'destination_attempt_ref':a[3],'source_request_ref':b[1],
        'source_attempt_ref':b[3],'source_observation_ref':observation_ref,'source_receipt_ref':receipt_ref,
        'file':file,'authorization_ref':authority}
    validate_schema('generation_reuse',association)
    return {'request_ref':b[1],'attempt_ref':b[3],'request':b[0],'observation':observation,
            'comparison':generation.comparison(b[0],observation),'reuse':association}


def artifact_owner(store, document, artifact, artifact_ref):
    """Historical read validates immutable association; it never renews authority."""
    provenance=artifact['provenance']; ref=provenance.get('generation_reuse')
    if not ref:
        return None
    value=store.read_object_json(ref);validate_schema('generation_reuse',value)
    destination=tasks._lookup_task(document,value['destination_task_id'],store)
    source=tasks._lookup_task(document,value['source_task_id'],store)
    if (value['project_id']!=document['project_id'] or destination['status']!='completed'
            or destination['operation_id']!=value['operation_id'] or artifact_ref not in destination['result_refs']
            or value['source_task_id']==value['destination_task_id']
            or value['source_request_ref']!=provenance.get('generation_request')
            or value['source_attempt_ref']!=provenance.get('generation_attempt') or value['file']!=artifact['file']):
        reject('association','artifact is not the committed destination result of this original source')
    a_request=store.read_object_json(value['destination_request_ref'])
    a_attempt=store.read_object_json(value['destination_attempt_ref'])
    b_request=store.read_object_json(value['source_request_ref'])
    b_attempt=store.read_object_json(value['source_attempt_ref'])
    a=owned(store,document,destination,a_request['request_id'],a_attempt['attempt_id'])
    b=owned(store,document,source,b_request['request_id'],b_attempt['attempt_id'])
    # V1 deliberately refuses later Attempt enrichment instead of silently
    # substituting a different evidence version for the accepted association.
    if (a[1]!=value['destination_request_ref'] or b[1]!=value['source_request_ref']
            or a[3]!=value['destination_attempt_ref'] or b[3]!=value['source_attempt_ref']
            or a_attempt['execution_ref']==b_attempt['execution_ref']):
        reject('association','association changed its owned Request or accepted Attempt version')
    left,right=deepcopy(a_request['input']),deepcopy(b_request['input'])
    left.pop('basis');right.pop('basis')
    if left!=right:
        reject('association','source and destination frozen inputs differ')
    observation,obs_ref,receipt_ref=original(store,document,source,b_request,value['source_request_ref'],b_attempt,value['source_attempt_ref'],artifact['file'])
    if obs_ref!=value['source_observation_ref'] or receipt_ref!=value['source_receipt_ref']:
        reject('association','association changed its original native evidence')
    return destination
