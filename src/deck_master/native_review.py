"""Normal installed native review: execute, observe, bind, and accept once.

No persistent issuer permission is installed. The private provider lives only
inside this owned execution; CLI/HTTP callers cannot submit receipt claims.
Committed standard Review/Task/receipt facts remain usable after it exits.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
from jsonschema import Draft202012Validator, ValidationError

from . import content_review, method_resources, models, review_evidence, service, tasks
from .native_review_transport import CodexReviewSession
from .store import Store, StoreError

PROVIDER_ID = "codex-native-review"


class _ObservedProvider:
    provider_id = PROVIDER_ID
    adapter_version = "codex-native-review.v1"
    authentication = "protected_transport"
    channels = ("independent_review_receipts",)

    def __init__(self, session):
        self.session = session
        self.raw = None
        self.claims = None

    def health(self):
        return self.session.ready

    def fetch(self, event_id):
        if not self.claims or event_id != self.claims["event_id"]:
            raise ValueError("no observed completion")
        return self.raw

    def verify(self, raw):
        if self.raw is None or raw != self.raw or not self.claims:
            raise ValueError("not this native completion")
        return deepcopy(self.claims)


def _judgment_schema(units):
    review = models.load_schema("review_v2")
    finding = deepcopy(review["properties"]["findings"]["items"])
    finding["required"] = list(finding["properties"])
    row = {"type": "object", "additionalProperties": False,
           "required": ["kind", "status", "observations", "findings", "replaces"],
           "properties": {"kind": {"enum": list(units)},
               **{key: deepcopy(review["properties"][key]) for key in
                  ("status", "observations", "replaces")},
               "findings": {"type": "array", "items": finding}}}
    result = {"type": "object", "additionalProperties": False, "required": ["reviews"],
              "properties": {"reviews": {"type": "array", "items": row}}}
    def explicit_types(value):
        if isinstance(value, dict):
            if "enum" in value and all(isinstance(item, str) for item in value["enum"]):
                value.setdefault("type", "string")
            for child in value.values():
                explicit_types(child)
        elif isinstance(value, list):
            for child in value:
                explicit_types(child)
    explicit_types(result)
    return result


def _packet(store, task):
    packets = []
    for ref in task["inputs"]:
        try:
            value = store.read_object_json(ref)
        except (ValueError, UnicodeError, StoreError):
            continue  # Other Task inputs may be original binary/text material.
        if isinstance(value, dict) and value.get("schema_version") == "content_review_packet.v1":
            packets.append(value)
    if len(packets) != 1:
        raise review_evidence.EvidenceRejected("native_review/packet", "one fixed complete review packet is required")
    return packets[0]


def _envelope(store, document, task, session, observation, units):
    try:
        judgments = json.loads(observation["raw_final_message"])
        Draft202012Validator(_judgment_schema(units)).validate(judgments)
    except (ValueError, ValidationError) as exc:
        raise review_evidence.EvidenceRejected("native_review/output", "native final output is not a valid complete review judgment") from exc
    rows = judgments["reviews"]
    owners = [(row['kind'], json.dumps(row['replaces'], sort_keys=True)) for row in rows]
    if ({row['kind'] for row in rows} != set(units) or len(owners) != len(set(owners))
            or any(sum(row['kind'] == unit for row in rows) > 1
                   and any(row['kind'] == unit and row['replaces'] is None for row in rows) for unit in units)):
        raise review_evidence.EvidenceRejected("native_review/units", "cover every required unit; repeated units must replace distinct actual owners")
    subjects = [document[key] for key in ("narrative", "content_plan") if document.get(key)]
    pages = [entry for entry in document["pages"] if entry["page_id"] in task["scope_pages"]]
    subjects += [entry["page"] for entry in pages]
    deps = [{"kind": "content", "identity": key, "sha256": document[key]["sha256"]}
            for key in ("narrative", "content_plan") if document.get(key)]
    deps += [{"kind": "content", "identity": "page:" + entry["page_id"], "sha256": entry["page"]["sha256"]} for entry in pages]
    deps += [{"kind": "source", "identity": source["source_id"], "sha256": source["extract"]["sha256"]}
             for source in document.get("sources") or [] if source.get("extract")]
    from .business_review import frozen_standard
    standard = frozen_standard(store, task)
    if standard is not None:
        deps.append(standard["dependency"])
    previous = {(ref["path"], ref["sha256"]): store.read_object_json(ref)
                for ref in document.get("reviews") or []}
    evidence_ref = store.put_json_object(observation)
    reviews = []
    for row in rows:
        review_id = task["task_id"] + "-" + row["kind"]
        if row["replaces"]:
            ref = row["replaces"]
            prior = previous.get((ref["path"], ref["sha256"]))
            if not prior or prior.get("kind") != row["kind"] or prior.get("review_stage") != "preproduction":
                raise review_evidence.EvidenceRejected("native_review/replaces", "replacement must name an actual prior review of the same unit")
            review_id = prior["review_id"]
        reviews.append({**row, "schema_version": "deck_review.v2", "review_stage": "preproduction",
                "review_id": review_id,
                **({"review_subject": "outline"} if task.get("review_subject") == "outline" else {}),
                "subjects": subjects, "dependencies": deps,
                "reviewer": {"type": "independent_host", "id": session.execution_ref,
                             "execution_ref": session.execution_ref, "independence_confirmed": True,
                             "identity_receipt": None, "assurance": "host_attested", "evidence_ref": evidence_ref},
                "created_at": datetime.now(timezone.utc).isoformat()})
    return {"kind": "review", "pages": [], "page_order": [], "artifact_specs": [],
            "reviews": reviews, "usage_events": [], "notes": "Actual native independent preproduction review"}


def _checkpoint(store, task, session, observation, *, envelope=None, context=None):
    """Commit owned observation/proof references before adopting any review.

    Only the owned native execution calls this writer. Recovery accepts only
    records referenced by its exact Task, never a caller's JSON/file/selector.
    """
    document = store.load_document()
    current = tasks._lookup_task(document, task['task_id'], store)
    if current['status'] != 'running' or current.get('execution_ref') != session.execution_ref:
        raise tasks.TaskConflict('native_review/checkpoint', 'native execution was cancelled, replaced or changed')
    record = {'schema_version': 'native_review_checkpoint.v1', 'project_id': document['project_id'],
        'task_id': current['task_id'], 'execution_ref': session.execution_ref,
        'operation_id': current['operation_id'], 'produced_against': current['produced_against'],
        'method_release': current.get('method_release'), 'observation_ref': store.put_json_object(observation),
        'envelope_ref': None, 'receipt_ref': None, 'state': 'observed'}
    if context is not None:
        payload = review_evidence.validate_review_context(context, store, document, current, envelope)
        receipts = payload.get('independent_review_receipts') or []
        if len(receipts) != 1 or receipts[0].get('provider_id') != PROVIDER_ID:
            raise review_evidence.EvidenceRejected('native_review/checkpoint', 'one owned native proof is required')
        record.update(envelope_ref=store.put_json_object(envelope), receipt_ref=receipts[0]['receipt_ref'], state='ready')
    models.validate_schema('native_review_checkpoint', record)
    ref = store.put_json_object(record)
    updated = {**current, 'result_refs': [*current.get('result_refs', []), ref], 'updated_at': service._utc_now_iso()}
    service._commit_task_update(store, document, current, updated, 'persist owned native review evidence before acceptance')
    return ref


def _checkpoints(store, task):
    return [value for ref in task.get('result_refs') or []
            if (value := store.read_object_json(ref)).get('schema_version') == 'native_review_checkpoint.v1']


def recovery_task_ids(store, document, *, subject=None):
    """Existing owned completions must be resolved before any new execution."""
    return [task['task_id'] for ref in document['tasks']
            if (task := store.read_object_json(ref)).get('review_stage') == 'preproduction'
            and task.get('review_subject') == subject and task['status'] == 'failed'
            and any(record.get('state') == 'ready' for record in _checkpoints(store, task))]


def _subject_status(store, document, subject):
    if subject == 'outline':
        from .outline_review import status
        return status(store, document)
    return content_review.preproduction_status(store, document)


class _RecoveredProvider:
    """Replay one already-authenticated, committed native proof, unchanged."""
    provider_id = PROVIDER_ID
    adapter_version = 'codex-native-review.v1'
    authentication = 'protected_transport'
    channels = ('independent_review_receipts',)

    def __init__(self, raw, claims):
        self.raw, self.claims = raw, claims

    def health(self):
        return True

    def fetch(self, event_id):
        if event_id != self.claims['event_id']:
            raise ValueError('not the recorded event')
        return self.raw

    def verify(self, raw):
        if raw != self.raw:
            raise ValueError('recorded bytes changed')
        return deepcopy(self.claims)


def recover(project, *, task_id):
    """Resume acceptance of a Task's committed proof, without a model call.

    Missing/expired proof remains blocked. This does not sign a loose JSON
    observation, renew a receipt or change the original executor/consumption.
    """
    store = Store(Path(project).expanduser())
    handle = os.open(store.deck_root / 'native-review.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise review_evidence.EvidenceRejected('native_review/lock', 'operation lock must be a regular file')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'running', 'task_id': task_id, 'next_action': 'read the active native operation; do not retry concurrently'}
        return _recover(store, task_id)
    finally:
        os.close(handle)


def _recover(store, task_id):
    document = store.load_document()
    task = tasks._lookup_task(document, task_id, store)
    if task.get('review_stage') != 'preproduction' or not (task.get('execution_ref') or '').startswith('codex-native:'):
        raise review_evidence.EvidenceRejected('native_review/task', 'recovery requires the original native preproduction Task')
    if task['status'] == 'completed':
        return {'status': 'already_applied', 'task_id': task_id, 'result_refs': task['result_refs'], 'model_called': False}
    if task['status'] not in ('failed', 'running'):
        raise tasks.TaskConflict('native_review/task', 'cancelled, superseded or unclaimed Task cannot adopt a recovered review')
    records = _checkpoints(store, task)
    ready = [record for record in records if record.get('state') == 'ready']
    if len(ready) != 1:
        return {'status': 'needs_evidence', 'task_id': task_id, 'model_called': False,
                'observation_refs': [record['observation_ref'] for record in records],
                'next_action': 'No unique committed authenticated completion is available. Inspect the original failure; never import or self-sign loose JSON.'}
    record = ready[0]
    models.validate_schema('native_review_checkpoint', record)
    for key, value in {'project_id': document['project_id'], 'task_id': task_id,
            'execution_ref': task['execution_ref'], 'operation_id': task['operation_id'],
            'produced_against': task['produced_against'], 'method_release': task.get('method_release')}.items():
        if record[key] != value:
            raise review_evidence.EvidenceRejected('native_review/' + key, 'checkpoint does not bind the original Task')
    if not tasks.task_inputs_current(store, document, task) or tasks.task_method_contract_changed(task):
        raise tasks.StaleInputContext('native_review/task', 'the original review basis is no longer current')
    observation = store.read_object_json(record['observation_ref'])
    envelope = store.read_object_json(record['envelope_ref'])
    proof = store.read_object_json(record['receipt_ref'])
    models.validate_schema('authenticated_review_receipt', proof)
    raw = store.read_object_bytes(proof['raw_event_ref'])
    claims = proof['claims']
    if (proof['provider_id'] != PROVIDER_ID or claims.get('provider_id') != PROVIDER_ID
            or proof['authentication'] != 'protected_transport'
            or raw != models.canonical_json_bytes(observation)
            or observation.get('status') != 'completed'
            or 'codex-native:' + str(observation.get('thread_id')) != task['execution_ref']
            or claims.get('observation_kind') != 'owned_native_process_completion'
            or claims.get('model_output_bytes_sha256') != models.sha256_bytes(observation['raw_final_message'].encode())
            or claims.get('method_release') != record['method_release']):
        raise review_evidence.EvidenceRejected('native_review/proof', 'recorded proof does not authenticate this exact observed completion')
    registry = review_evidence.ProviderRegistry()
    registry.register(_RecoveredProvider(raw, claims))
    with review_evidence.ProviderRuntime(registry).bound():
        # Normal receiver checks exact result/basis/executor/author binding and
        # original validity interval; no renewed or edited claims are created.
        context = registry.review_context(store, document, task, envelope,
            {'provider_id': PROVIDER_ID, 'event_id': claims['event_id']})
        if task['status'] == 'failed':
            resumed = {**task, 'status': 'running', 'error': None, 'updated_at': service._utc_now_iso()}
            service._commit_task_update(store, document, task, resumed, 'resume acceptance of recorded native completion')
        try:
            accepted = service.accept_result(store.project_root, task_id=task_id,
                operation_id=task['operation_id'], produced_against=task['produced_against'],
                result_payload=envelope, adapter_context=context)
            return {'status': 'recovered', 'task_id': task_id, 'execution_ref': task['execution_ref'],
                    'model_called': False, 'acceptance': accepted,
                    'preproduction': _subject_status(store, store.load_document(), task.get('review_subject'))}
        except Exception as exc:
            _failure(store, task, task['execution_ref'], exc)
            raise


def _failure(store, task, executor, exc):
    """Preserve failure and any owned checkpoint; recovery never reruns the model."""
    document = store.load_document()
    current = tasks._lookup_task(document, task["task_id"], store)
    if current["status"] == "running" and current.get("execution_ref") == executor:
        updated = {**current, "status": "failed", "updated_at": service._utc_now_iso(),
                   "error": {"code": "native_review_failed", "message": str(getattr(exc, "detail", type(exc).__name__))[:500],
                             "next_action": "inspect task result_refs; use review recover --task-id for a committed proof; missing proof must not be self-signed"}}
        service._commit_task_update(store, document, current, updated, "native independent review failed")


def run(project, *, task_id=None, force_units=None, subject=None, selected_resource_ids=None):
    """Run native review, optionally selecting current units for explicit re-review."""
    store = Store(Path(project).expanduser())
    # A derived operation lock prevents double-clicks/reconnects from issuing a
    # second native call. It grants no policy or receipt authority.
    handle = os.open(store.deck_root / "native-review.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise review_evidence.EvidenceRejected("native_review/lock", "operation lock must be a regular file")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "running", "next_action": "read current task status; do not launch another native review"}
        return _run(store, task_id=task_id, force_units=force_units, subject=subject,
                    selected_resource_ids=selected_resource_ids)
    finally:
        os.close(handle)


@contextmanager
def _session_with_startup_history(store, revision_id):
    session = CodexReviewSession()
    try:
        entered = session.__enter__()
    except Exception as exc:
        from . import native_review_startup
        try:
            native_review_startup.record(store, revision_id, getattr(session, 'startup_failure', {}))
        except (OSError, ValueError, TypeError):
            # Preserve the startup error; explicitly report unknown persistence.
            exc.startup_history_saved = False
        else:
            exc.startup_history_saved = True
        exc.error_details = {**native_review_startup.normalize(getattr(session, 'startup_failure', None)),
                             'startup_history_saved': exc.startup_history_saved,
                             'next_action': native_review_startup.NEXT_ACTION}
        raise
    try:
        yield entered
    except BaseException:
        import sys
        if not session.__exit__(*sys.exc_info()):
            raise
    else:
        session.__exit__(None, None, None)


def _run(store, *, task_id, force_units=None, subject=None, selected_resource_ids=None):
    document = store.load_document()
    if subject not in (None, 'outline'):
        raise review_evidence.EvidenceRejected('native_review/subject', 'unsupported review subject')
    if task_id and selected_resource_ids is not None:
        raise review_evidence.EvidenceRejected('selected_resource_ids', 'frozen Task methods cannot be supplemented; use formal reissue')
    from . import outline_review
    if task_id:
        selected = tasks._lookup_task(document, task_id, store)
        if subject is not None and selected.get('review_subject') != subject:
            raise review_evidence.EvidenceRejected('native_review/subject', 'subject differs from frozen task')
        subject = selected.get('review_subject')
    if subject == 'outline':
        outline_review.require_outline(store, document)
        forced = force_units or []
        if not set(forced) <= set(outline_review.UNITS) or len(forced) != len(set(forced)):
            raise review_evidence.EvidenceRejected('native_review/force_units', 'invalid outline units')
    else:
        forced = content_review.validate_force_units(store, document, force_units)
    if task_id and force_units is not None:
        raise review_evidence.EvidenceRejected("native_review/force_units", "select a frozen task_id or force_units, not both")
    gate = outline_review.status(store, document) if subject == 'outline' else content_review.preproduction_status(store, document)
    candidates = [task for ref in document["tasks"] if
                  (task := store.read_object_json(ref)).get("kind") == "review"
                  and task.get("review_stage") == "preproduction"
                  and task.get("review_subject") == subject
                  and task["status"] in ("awaiting_host", "running", "queued")]
    if forced:
        expected = set(gate["missing_units"]) | {row["kind"] for row in gate["blocking_findings"]} | set(forced)
        candidates = [task for task in candidates
                      if {row["kind"] for row in task.get("review_units", [])} == expected
                      and set(task.get("scope_pages", [])) == (set() if subject == "outline" else {page["page_id"] for page in document["pages"]})
                      and tasks.task_inputs_current(store, document, task)]
    if task_id:
        task = tasks._lookup_task(document, task_id, store)
        if task not in candidates:
            raise review_evidence.EvidenceRejected("native_review/task_id", "select a live preproduction review task")
    elif len(candidates) > 1:
        raise review_evidence.EvidenceRejected("native_review/task_id", "select one of the existing preproduction review tasks")
    else:
        task = candidates[0] if candidates else None
    if task and selected_resource_ids is not None:
        raise review_evidence.EvidenceRejected('selected_resource_ids', 'pending review methods are frozen; use formal reissue')
    if task and task["status"] == "running":
        return {"status": "running", "task_id": task["task_id"],
                "next_action": "inspect the existing execution; cancel it explicitly if interrupted before retrying"}
    recoverable = recovery_task_ids(store, document, subject=subject)
    if recoverable:
        if selected_resource_ids is not None:
            raise review_evidence.EvidenceRejected('selected_resource_ids', 'recover the original frozen review before selecting methods')
        return {'status': 'recovery_available', 'task_ids': recoverable,
                'next_action': 'Use review recover --project <project> --task-id <id>; do not repeat the native call.'}
    if gate["status"] == "pass" and not forced and not task_id and task is None:
        if selected_resource_ids is not None:
            raise review_evidence.EvidenceRejected('selected_resource_ids', 'select review units for a new review before choosing methods')
        return {"status": "already_reviewed", "preproduction": gate}
    if selected_resource_ids is not None:
        units = sorted(set(gate['missing_units']) | {row['kind'] for row in gate['blocking_findings']} | set(forced))
        method_resources.method_resources('review', intent='preproduction', phase='review', review_units=units,
            selected_resource_ids=selected_resource_ids,
            business_framing=models.writer_at_least(document, 'business-framing.v1'))
    with _session_with_startup_history(store, document["revision_id"]) as session:
        provider = _ObservedProvider(session)
        registry = review_evidence.ProviderRegistry()
        registry.register(provider)
        with review_evidence.ProviderRuntime(registry).bound():
            if task is None:
                dispatch = outline_review.dispatch if subject == 'outline' else content_review.dispatch_preproduction_review
                dispatched = dispatch(store.project_root,
                    adapter_context=registry.channel_context(), force_units=force_units,
                    selected_resource_ids=selected_resource_ids)
                if not dispatched.get("task"):
                    return dispatched
                task = dispatched["task"]
            document = store.load_document()
            if not tasks.task_inputs_current(store, document, task):
                raise tasks.StaleInputContext("native_review/task", "review inputs changed; run continue to retire and reissue the task")
            methods = method_resources.read_task_methods(store.project_root, task["task_id"])
            if methods["status"] != "current":
                raise tasks.StaleInputContext("native_review/methods", "frozen methods changed; run continue to retire and reissue the task")
            packet = _packet(store, task)
            units = packet["required_units"]
            subjects = [document[key] for key in ("narrative", "content_plan") if document.get(key)]
            subjects += [entry["page"] for entry in document["pages"] if entry["page_id"] in task["scope_pages"]]
            authors = content_review.author_execution_refs(store, document, subjects)
            if session.execution_ref in authors:
                raise review_evidence.EvidenceRejected("native_review/executor", "reviewer is an author of this manuscript")
            service.task_start(store.project_root, task_id=task["task_id"], execution_ref=session.execution_ref,
                supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
                capabilities=task.get("required_capabilities") or [])
            try:
                prior = [{"ref": ref, "review": value} for ref in document.get("reviews") or []
                         if (value := store.read_object_json(ref)).get("review_stage") == "preproduction"]
                if packet.get('review_scope') is not None:
                    owner_refs = {row['review_ref']['sha256'] for row in packet['review_scope']['owners']}
                    prior = [row for row in prior if row['ref']['sha256'] in owner_refs]
                subject_instruction = ("Independently review only the fixed Narrative and ContentPlan outline, argument and progression. "
                    "There are no page-copy or visual-production judgments; cite outline nodes and evidence. "
                    if subject == 'outline' else "Independently review the complete manuscript against the task, materials, and frozen methods below. ")
                prompt = (subject_instruction +
                          "Return a judgment for every required unit. Multiple judgments of one unit are allowed only to replace distinct "
                          "actual prior owners that you rechecked; do not merge or omit their finding identities. Do not edit the draft. Cite concrete pages/atoms "
                          "and evidence for findings. Re-check prior findings against the current manuscript; preserve finding IDs "
                          "and use replaces only when actually verifying the corresponding previous review. Never fabricate "
                          "human/professional approval or claim unobserved evidence. JSON input follows:\n" +
                          json.dumps({"packet": packet, "methods": methods["methods"], "prior_reviews": prior}, ensure_ascii=False))
                observation = session.review(prompt, _judgment_schema(units))
                if (observation.get("thread_id") != session.thread_id or observation.get("turn_id") != session.turn_id
                        or observation.get("status") != "completed"):
                    raise review_evidence.EvidenceRejected("native_review/completion", "completion does not match the owned native execution")
                _checkpoint(store, task, session, observation)
                # Bind to the dispatched manuscript, never silently rebase a
                # judgment onto content changed during the native call.
                envelope = _envelope(store, document, task, session, observation, units)
                binding = review_evidence.review_binding(store, document, task, envelope)
                issued = datetime.now(timezone.utc)
                provider.raw = models.canonical_json_bytes(observation)
                provider.claims = {**binding, "provider_id": PROVIDER_ID,
                    "event_id": "native-" + models.sha256_bytes(provider.raw)[:40],
                    "channel": "independent_review_receipts", "issued_at": issued.isoformat(),
                    "expires_at": (issued + timedelta(minutes=30)).isoformat(),
                    "executor_ref": session.execution_ref, "reviewer_id": session.execution_ref,
                    "assurance": "host_attested", "observation_kind": "owned_native_process_completion",
                    "model_output_bytes_sha256": models.sha256_bytes(observation["raw_final_message"].encode()),
                    "method_release": task.get("method_release"),
                    "evidence_scope": "native independent content review; not human or professional approval"}
                current = store.load_document()
                claimed = tasks._lookup_task(current, task["task_id"], store)
                context = registry.review_context(store, current, claimed, envelope,
                    {"provider_id": PROVIDER_ID, "event_id": provider.claims["event_id"]})
                _checkpoint(store, task, session, observation, envelope=envelope, context=context)
                accepted = service.accept_result(store.project_root, task_id=task["task_id"],
                    operation_id=task["operation_id"], produced_against=task["produced_against"],
                    result_payload=envelope, adapter_context=context)
                return {"status": "reviewed", "task_id": task["task_id"], "execution_ref": session.execution_ref,
                        "acceptance": accepted, "preproduction": _subject_status(store, store.load_document(), subject)}
            except Exception as exc:
                try:
                    _failure(store, task, session.execution_ref, exc)
                except Exception:
                    pass  # Never mask cancellation/CAS/failure evidence with a second error.
                raise
