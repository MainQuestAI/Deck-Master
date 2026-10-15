"""Explicit synthetic RC3 test inputs; never a product gate bypass.

Historical fixtures initialize old data, public fixtures call current services.
No autouse monkeypatch and no implicit authorization is provided.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import uuid

from deck_master import collaboration, service
from deck_master.content import check_page
from deck_master.models import new_document, require_writer
from deck_master.store import Store


def _handle(project, response=None, *, scenario):
    store = Store(project)
    doc = store.load_document()
    return {"project": Path(project), "revision_id": doc["revision_id"],
            "request_id": ((doc.get("collaboration") or {}).get("request") or {}).get("request_id"),
            "refs": {"pages": [p["page"] for p in doc["pages"]], "plan": doc.get("content_plan")},
            "response": response, "scenario_manifest": {"scenario": scenario,
                "evidence_level": "L1_SYNTHETIC", "human_or_native_evidence": False}}


def historical_snapshot(tmp_path, *, scenario, pages=(), minimum_writer=None, task=None):
    project = Path(tmp_path) / ("historical-" + uuid.uuid4().hex[:8])
    store = Store(project)
    store.ensure_layout()
    doc = new_document(project_id=project.name, task=task or {"brief": scenario},
                       operation_id="historical-fixture")
    for page in pages:
        page = check_page(page)
        doc["pages"].append({"page_id": page["page_id"], "page": store.put_json_object(page),
                             "blueprint": None, "svg": None, "svg_preview": None, "ppt_preview": None})
    if minimum_writer is not None:
        require_writer(doc, minimum_writer)
    store.init_project(doc, operation_id="historical-fixture")
    return _handle(project, scenario=scenario)


def public_project(tmp_path, *, create_input, request_input=None, manuscript=None):
    project = Path(tmp_path) / ("rc3-" + uuid.uuid4().hex[:8])
    values = dict(create_input)
    if request_input is not None:
        values["request_input"] = request_input
    if manuscript is not None:
        values["draft"] = manuscript
    response = service.create(project, **values)
    return _handle(project, response, scenario="public current RC3 service")


def evidence_for(project, *, text, locator):
    store = Store(project)
    ref = store.put_blob(text.encode("utf-8"), ext="txt")
    return {"kind": "host_attested_instruction", "source_ref": ref,
            "source_locator": locator, "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def authorize_scope(project, *, actions, scope, max_external_calls,
                    max_candidate_count, adoption_policy, evidence):
    store = Store(project)
    return collaboration.grant(project, input={"mode": "execute", "actions": list(actions),
        "scope": scope, "max_external_calls": max_external_calls,
        "max_candidate_count": max_candidate_count, "adoption_policy": adoption_policy,
        "instruction_evidence": evidence}, base_revision=store.load_document()["revision_id"],
        operation_id=str(uuid.uuid4()))


def submit_host_fixture(project, *, task_id, result_payload, execution_ref, host_declaration):
    store = Store(project)
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref)["task_id"] == task_id)
    service.task_start(project, task_id=task_id, execution_ref=execution_ref,
        supported_protocols=host_declaration["supported_protocols"],
        capabilities=host_declaration["capabilities"])
    return service.accept_result(project, task_id=task_id, operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=result_payload)


def read_request_completion(project):
    from deck_master.content_production import completion_status
    store = Store(project)
    return completion_status(store, store.load_document())


def source_snapshot(root):
    root = Path(root)
    rows = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows[relative] = {"link": str(path.readlink())}
        elif path.is_file():
            rows[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def call_facts(project):
    store = Store(project)
    doc = store.load_document()
    return {"revision_id": doc["revision_id"], "tasks": [
        {"task_id": task["task_id"], "status": task["status"],
         "allowances": task.get("call_allowances", []),
         "attempts": task.get("generation_attempts", [])}
        for ref in doc["tasks"] for task in [store.read_object_json(ref)]]}


def claim_fixture_task(project, task, *, execution_ref="synthetic-l1-host"):
    """An explicit L1 Host claim using this actual public workorder contract."""
    service.task_start(project, task_id=task["task_id"], execution_ref=execution_ref,
        supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
        capabilities=task.get("required_capabilities", []))
    return task


def settle_fidelity_review(project, *, page_ids, execution_ref, scenario):
    """Explicit L1 manuscript check via actual dispatch/claim/adoption.

    This helper never changes the quality profile. Its host_self evidence is
    usable only when the actual request already calls for fidelity_only.
    """
    from deck_master import content_review
    store = Store(project)
    dispatched = content_review.dispatch_preproduction_review(project, page_ids=list(page_ids),
        instruction='L1 synthetic fidelity protocol fixture: ' + scenario)
    assert dispatched['status'] == 'review_dispatched', dispatched
    assert dispatched['requirement'] == 'fidelity_only', dispatched
    task = dispatched['task']
    doc = store.load_document()
    pages = [entry for entry in doc['pages'] if entry['page_id'] in page_ids]
    subjects = [ref for ref in (doc.get('narrative'), doc.get('content_plan')) if ref]
    subjects += [entry['page'] for entry in pages]
    deps = [{'kind': 'content', 'identity': key, 'sha256': ref['sha256']}
            for key, ref in (('narrative', doc.get('narrative')), ('content_plan', doc.get('content_plan'))) if ref]
    deps += [{'kind': 'content', 'identity': 'page:' + entry['page_id'], 'sha256': entry['page']['sha256']} for entry in pages]
    deps += [{'kind': 'source', 'identity': source['source_id'], 'sha256': source['extract']['sha256']}
             for source in doc.get('sources') or [] if source.get('extract')]
    evidence = store.put_json_object({'evidence_level': 'L1_SYNTHETIC', 'scenario': scenario,
        'subjects': subjects, 'human_or_native_evidence': False,
        'observation': 'Explicit synthetic protocol fixture inspected exactly the named manuscript objects.'})
    reviews = [{'schema_version': 'deck_review.v2', 'review_id': 'l1-fidelity-' + uuid.uuid4().hex,
        'kind': kind, 'review_stage': 'preproduction', 'status': 'pass',
        'subjects': subjects, 'dependencies': deps,
        'reviewer': {'type': 'host_self', 'id': 'L1-synthetic-fidelity-host', 'execution_ref': execution_ref,
            'independence_confirmed': False, 'identity_receipt': None, 'evidence_ref': evidence, 'assurance': 'host_attested'},
        'observations': ['L1 synthetic fidelity check: ' + scenario], 'findings': [],
        'created_at': '2026-10-15T00:00:00Z', 'replaces': None} for kind in dispatched['units']]
    response = submit_host_fixture(project, task_id=task['task_id'], execution_ref=execution_ref,
        host_declaration={'supported_protocols': [task['protocol_version']], 'capabilities': task['required_capabilities']},
        result_payload={'kind': 'review', 'files': [], 'pages': [], 'page_order': [], 'artifact_specs': [],
            'reviews': reviews, 'usage_events': [], 'notes': 'Explicit L1 synthetic fidelity, no independent/human/native claim.'})
    assert response['status'] == 'accepted', response
    current = store.load_document()
    completed = next(store.read_object_json(ref) for ref in current['tasks']
        if store.read_object_json(ref)['task_id'] == task['task_id'])
    return {'task': task, 'response': response, 'review_refs': completed['result_refs'], 'evidence_level': 'L1_SYNTHETIC'}


def claimed_phase_task(store, document, **kwargs):
    from deck_master import content_production
    task = content_production.open_phase_task(store, document, **kwargs)
    return claim_fixture_task(store.project_root, task)


def accept_synthetic_blueprint(project, *, task, result_payload, execution_ref, scenario, adopt=True):
    """Actual generation lifecycle with a registered, explicitly L1 provider.

    Original caller-authored PNG/artifact specs are retained. This is protocol
    evidence only; the synthetic provider never establishes real tool/fee facts.
    The returned synthetic_execution records the exact enriched envelope for
    terminal replay rather than opening another call on a helper retry.
    adopt=False leaves the actual first adoption to a separate installed CLI
    process; it still records the same explicitly synthetic call facts.
    """
    from copy import deepcopy
    import time
    from deck_master import generation, tasks
    from deck_master.models import canonical_json_bytes, sha256_bytes
    from deck_master.native_image_evidence import (NativeImageCompletion, NativeImageRegistry,
        NativeImageRuntime, image_binding)
    store = Store(project)
    current = tasks._lookup_task(store.load_document(), task['task_id'], store)
    assert current['kind'] == 'blueprint' and generation.is_new(current)
    if current['status'] == 'awaiting_host':
        claim_fixture_task(project, current, execution_ref=execution_ref)
    else:
        assert current['status'] == 'running' and current['execution_ref'] == execution_ref
    prepared = generation.prepared_input(store, store.load_document(), current)
    prepared['parameters'] = {'transparent_background': False}
    frozen = generation.freeze(project, task_id=task['task_id'], input=prepared,
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    current = tasks._lookup_task(store.load_document(), task['task_id'], store)
    if not current['call_allowances']:
        tasks.allocate_call_allowances(store, task_id=task['task_id'], count=1)
        current = tasks._lookup_task(store.load_document(), task['task_id'], store)
    allowance = next(item for item in current['call_allowances'] if item['state'] == 'reserved')
    attempt = tasks.call_begin(store, task_id=task['task_id'], allowance_id=allowance['allowance_id'],
        execution_ref=execution_ref, request_id=frozen['request_id'])
    binding, _, begun, _ = image_binding(store, store.load_document(), task['task_id'], attempt['attempt_id'])
    spec = next(item for item in result_payload['artifact_specs'] if item['role'] == 'blueprint')
    file = next(item for item in result_payload['files'] if item['file_id'] == spec['file_id'])
    raw = (store.staging_dir / task['operation_id'] / file['path']).read_bytes()
    now = time.time_ns() // 1_000_000
    arguments = {'prompt': prepared['prompt'], 'transparent_background': False}
    if prepared['references']:
        arguments['referenced_image_paths'] = [str(store.project_root / ref['file']['path']) for ref in prepared['references']]
    claims = {'provider_id': 'synthetic-l1-shared-fixture', 'event_id': uuid.uuid4().hex,
        'binding': binding, 'tool_name': 'image_gen__imagegen', 'status': 'completed',
        'issued_at_ms': now, 'expires_at_ms': now + 60000,
        'started_at_ms': begun['started_at_ms'], 'completed_at_ms': now,
        'arguments': arguments, 'output_sha256': sha256_bytes(raw), 'invocation_ref': None}

    class SyntheticProvider:
        provider_id = claims['provider_id']
        adapter_version = 'synthetic-l1-shared.v1'
        authentication = 'protected_transport'

        def health(self):
            return True

        def fetch(self, event_id):
            assert event_id == claims['event_id']
            return canonical_json_bytes(claims)

        def verify(self, event):
            assert event == canonical_json_bytes(claims)
            return NativeImageCompletion(deepcopy(claims), raw)

    registry = NativeImageRegistry()
    registry.register(SyntheticProvider())
    selector = {'provider_id': claims['provider_id'], 'event_id': claims['event_id']}
    with NativeImageRuntime(registry).bound():
        context = registry.image_context(store, store.load_document(), task_id=task['task_id'],
            attempt_id=attempt['attempt_id'], selector=selector)
        settlement = tasks.call_settle(store, task_id=task['task_id'], allowance_id=allowance['allowance_id'],
            attempt_id=attempt['attempt_id'], outcome='consumed',
            report_bytes=canonical_json_bytes({'source': 'native_host_image.v1', **selector}), adapter_context=context)
    payload = deepcopy(result_payload)
    payload['generation_result'] = {'request_id': frozen['request_id'], 'attempt_id': attempt['attempt_id']}
    execution = {'scenario': scenario, 'evidence_level': 'L1_SYNTHETIC',
        'frozen': frozen, 'attempt': attempt, 'settlement': settlement, 'result_payload': payload}
    if not adopt:
        return {'status': 'prepared_for_cli_adoption', 'result_payload': payload,
            'synthetic_execution': execution}
    response = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
        produced_against=task['produced_against'], result_payload=payload)
    return {**response, 'synthetic_execution': execution}
