"""Frozen inputs and immutable attempt observations on the existing Task ledger."""
from __future__ import annotations

import copy
import json
import time
import uuid

from . import tasks
from .errors import TypedServiceError
from .models import bump_revision, canonical_json_bytes, sha256_bytes, validate_schema, validate_task_semantics
from .observations import collect_codex_image
from .snapshots import load_snapshot
from .store import ConflictError, Store, _validate_operation_id

PROTOCOL = "generation.v1"
CAPABILITIES = ["generation_request_freeze", "attempt_binding", "native_tool_observation", "content_requirements_v1"]


class GenerationError(TypedServiceError):
    def __init__(self, code, field, message, *, conflict=False):
        super().__init__(field, message)
        self.error_code = code
        self.exit_code = 5 if conflict else 2


def _error(code, field, message, *, conflict=False):
    return GenerationError(code, field, message, conflict=conflict)


def is_new(task):
    return task.get("protocol_version") == PROTOCOL


def protocol_fields(document, *, store=None):
    if store is not None and not store.workbench_protocol_required(document):
        return {}
    if document.get("compatibility", {}).get("project_format") != "workbench.v3":
        return {}
    return {"protocol_version": PROTOCOL, "required_capabilities": CAPABILITIES.copy(),
            "generation_requests": [], "generation_attempts": []}


def check_host(task, declaration=None):
    if not task.get("protocol_version"):
        return
    declaration = declaration if declaration is not None else task.get("host_protocol") or {}
    protocol = task.get("protocol_version")
    if (protocol not in (PROTOCOL, "compose.v1", "compose.v2", "changes.v1")
            or not isinstance(declaration, dict)
            or not all(isinstance(declaration.get(k), list) and all(isinstance(v, str) for v in declaration[k])
                       for k in ("supported_protocols", "capabilities"))
            or protocol not in declaration["supported_protocols"]
            or not set(task.get("required_capabilities") or []) <= set(declaration["capabilities"])):
        raise _error("host_protocol_unsupported", "host_protocol", f"this task requires {protocol} and its declared capabilities")


def prepared_input(store, document, task):
    """A proposal, never an assertion that these inputs were sent to a tool."""
    if not is_new(task):
        return None
    from .production import resolve_design, stored_blueprint_request
    from .models import ModelError
    try:
        prepared, _ = stored_blueprint_request(store, task)
    except ModelError as exc:
        raise _error("generation_request_invalid", "task/inputs", exc.detail) from exc
    dispatched = load_snapshot(store, task["dispatch_revision"])
    entry = next(p for p in dispatched["pages"] if p["page_id"] == prepared["page_id"])
    page = store.read_object_json(entry["page"])
    design = copy.deepcopy(prepared.get("resolved_design_context"))
    if design is None:
        design, _ = resolve_design(page, dispatched["design_context"], dispatched["design_context"].get("assets") or [])
    result = {"schema_version": "generation_input.v1", "prompt": prepared["prompt"],
            "page": {"page_id": entry["page_id"], "page_ref": entry["page"]}, "design_context": design,
            "template_ref": None, "references": copy.deepcopy(task.get("stage_request", {}).get("references", [])),
            "parameters": {"transparent_background": False} if design.get("content_requirements") else {}, "constraints": {},
            "basis": {"project_id": document["project_id"], "revision_id": dispatched["revision_id"],
                      "produced_against": task["produced_against"]}}
    if "asset_inputs" in design:
        for image in design["asset_inputs"]["images"]:
            attachment = {"file": copy.deepcopy(image["file"]), "role": "reference"}
            if attachment not in result["references"]:
                result["references"].append(attachment)
    recipe_ref = task.get("stage_request", {}).get("style_recipe_ref")
    if recipe_ref:
        result["style_recipe_ref"] = copy.deepcopy(recipe_ref)
        result["constraints"] = {"preserve_target_content": True, "style_recipe_ref": copy.deepcopy(recipe_ref)}
        recipe = store.read_object_json(recipe_ref)
        if recipe['schema_version'] == 'style_recipe.v3':
            result['constraints']['recipe_parameters'] = copy.deepcopy(design['recipe_parameters'])
        if recipe['schema_version'] == 'style_recipe.v2':
            result['constraints']['visual_style_ref'] = recipe['input']['visual_style_ref']
            from .styles import effective_spec
            result['constraints']['visual_style_spec'] = effective_spec(recipe)
    return result


def _read_owned(store, task, field, object_id):
    key, kind = ("request_id", "generation_request") if field == "generation_requests" else ("attempt_id", "generation_attempt")
    for ref in task.get(field) or []:
        obj = store.read_object_json(ref)
        validate_schema(kind, obj)
        if kind == "generation_request" and obj["input_hash"] != sha256_bytes(canonical_json_bytes(obj["input"])):
            raise _error("generation_request_invalid", "input_hash", "stored input does not match its frozen hash")
        if obj.get(key) == object_id:
            if obj["task_id"] != task["task_id"]:
                raise _error("generation_binding_conflict", key, "object belongs to another task", conflict=True)
            return obj, ref
    raise _error("generation_object_not_found", key, "object is not referenced by this task")


def show(project_dir, *, request_id=None, attempt_id=None, revision=None):
    store = Store(project_dir)
    document = load_snapshot(store, revision)
    if bool(request_id) == bool(attempt_id):
        raise _error("generation_request_invalid", "id", "select one request or attempt")
    field = "generation_requests" if request_id else "generation_attempts"
    for task_ref in document["tasks"]:
        task = store.read_object_json(task_ref)
        try:
            obj, ref = _read_owned(store, task, field, request_id or attempt_id)
        except GenerationError as exc:
            if exc.error_code == "generation_object_not_found":
                continue
            raise
        if obj["project_id"] != document["project_id"]:
            raise _error("generation_binding_conflict", "project_id", "object belongs to another project", conflict=True)
        result = {"project_id": document["project_id"], "revision_id": document["revision_id"], "ref": ref,
                  "request" if request_id else "attempt": obj}
        if attempt_id:
            result["call"] = copy.deepcopy(next(c for c in task["call_allowances"] if c["allowance_id"] == obj["allowance_id"]))
            result["observations"] = [store.read_object_json(r) for r in obj["observations"]]
        return result
    raise _error("generation_object_not_found", "id", "object is not in this committed snapshot")


def _validate_input(store, document, task, value):
    validate_schema("generation_input", value)
    canonical_json_bytes(value)  # reject non-finite values rather than normalizing
    expected = prepared_input(store, document, task)
    for key in ("page", "design_context", "template_ref", "basis"):
        if value[key] != expected[key]:
            raise _error("generation_binding_conflict", "input/" + key, "input does not match the dispatched task basis", conflict=True)
    if value.get("style_recipe_ref") != expected.get("style_recipe_ref") or (expected.get("style_recipe_ref") and value["constraints"] != expected["constraints"]):
        raise _error("generation_binding_conflict", "input/style_recipe_ref", "preserve the dispatched recipe and content constraints", conflict=True)
    allowed = set()
    if task.get('stage_request') or expected["design_context"].get("content_requirements"):
        for key in ('prompt', 'references'):
            if value[key] != expected[key]:
                raise _error('generation_binding_conflict', 'input/' + key, 'input differs from the committed stage request', conflict=True)
        allowed.update(ref['file']['sha256'] for ref in expected['references'])
    for asset in value["design_context"].get("assets") or []:
        if asset.get("external_use") == "allowed" and asset.get("artifact"):
            allowed.add(store.read_object_json(asset["artifact"])["file"]["sha256"])
    for entry in document["pages"]:
        if entry.get("blueprint"):
            allowed.add(store.read_object_json(entry["blueprint"])["file"]["sha256"])
    for reference in value["references"]:
        store.read_object_bytes(reference["file"])
        if reference["file"]["sha256"] not in allowed:
            raise _error("generation_request_invalid", "input/references", "reference is not a permitted asset or stored original image")
    def no_credentials(value):
        if isinstance(value, dict):
            if any(k.lower() in {"api_key", "authorization", "password", "secret", "access_token"} for k in value):
                raise _error("generation_request_invalid", "input/parameters", "credentials are not request parameters")
            for v in value.values():
                no_credentials(v)
        elif isinstance(value, list):
            for v in value:
                no_credentials(v)
    no_credentials(value["parameters"])


def freeze(project_dir, *, task_id, input, base_revision, operation_id):
    from .legacy import looks_like_legacy_run
    store = Store(project_dir)
    if looks_like_legacy_run(store.project_root):
        raise _error("legacy_run_format", "project", "old runs cannot be initialized or migrated in place")
    load_snapshot(store)  # reject missing/invalid projects before the lock creates a layout
    return _freeze(store, task_id=task_id, input=input, base_revision=base_revision, operation_id=operation_id)


@tasks._project_transaction
def _freeze(store, *, task_id, input, base_revision, operation_id):
    _validate_operation_id(operation_id)
    digest = sha256_bytes(canonical_json_bytes({"action": "requests.freeze", "task_id": task_id,
                                              "input": input, "base_revision": base_revision}))
    previous = store.operation_receipt(operation_id)
    if previous:
        if previous["request_digest"] != digest:
            raise _error("operation_payload_conflict", "operation_id", "this operation is already bound to other input", conflict=True)
        return {**previous["response"], "status": "already_applied"}
    document = store.load_document()
    task = tasks._lookup_task(document, task_id, store)
    if not is_new(task):
        raise _error("host_protocol_unsupported", "task/protocol_version", "request freezing requires an explicit workbench.v3 project")
    check_host(task)
    if task["status"] != "running" or not tasks.task_inputs_current(store, document, task):
        raise _error("generation_binding_conflict", "task", "claim a current active task before freezing", conflict=True)
    if document["revision_id"] != base_revision:
        raise ConflictError("base_revision", "project changed before freezing")
    _validate_input(store, document, task, input)
    request = {"schema_version": "generation_request.v1", "request_id": "req-" + uuid.uuid4().hex,
               "task_id": task_id, "project_id": document["project_id"], "operation_id": operation_id,
               "input": copy.deepcopy(input), "input_hash": sha256_bytes(canonical_json_bytes(input)), "created_at_ms": time.time_ns() // 1000000}
    validate_schema("generation_request", request)
    ref = store.put_json_object(request)
    updated = {**task, "generation_requests": [*(task.get("generation_requests") or []), ref]}
    validate_task_semantics(updated)
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "task_update", "description": "generation input frozen", "read_set": []})
    bumped = tasks._replace_task_ref(bumped, task, store.put_json_object(updated), store)
    response = {"status": "frozen", "revision_id": bumped["revision_id"], "request_id": request["request_id"],
                "request_ref": ref, "input_hash": request["input_hash"], "input": request["input"], "observer": "core_frozen"}
    store._commit_locked(base_revision=base_revision, document=bumped, blobs=[], operation_id=operation_id,
                         operation_receipt={"format": "operation_receipt.v1", "request_digest": digest, "response": response})
    return response


def begin_attempt(store, document, task, allowance_id, execution_ref, request_id, *, replay_only=False):
    check_host(task)
    if not request_id:
        raise _error("generation_request_required", "request_id", "freeze and bind a request before calling the tool")
    request, request_ref = _read_owned(store, task, "generation_requests", request_id)
    if request["project_id"] != document["project_id"] or not tasks.task_inputs_current(store, document, task):
        raise _error("generation_binding_conflict", "request_id", "request basis is no longer current", conflict=True)
    for ref in task.get("generation_attempts") or []:
        old = store.read_object_json(ref)
        validate_schema("generation_attempt", old)
        if old["project_id"] != document["project_id"] or old["task_id"] != task["task_id"]:
            raise _error("generation_binding_conflict", "attempt_id", "attempt belongs to another project or task", conflict=True)
        if old["allowance_id"] == allowance_id:
            if old["request_ref"] != request_ref or old["execution_ref"] != execution_ref:
                raise _error("generation_binding_conflict", "request_id", "this allowance already began a different attempt", conflict=True)
            return task, old, ref
    if replay_only:
        raise _error("generation_binding_conflict", "attempt_id", "in-flight allowance has no committed attempt", conflict=True)
    attempt = {"schema_version": "generation_attempt.v1", "attempt_id": "attempt-" + uuid.uuid4().hex,
               "task_id": task["task_id"], "project_id": document["project_id"], "request_ref": request_ref,
               "allowance_id": allowance_id, "execution_ref": execution_ref, "started_at_ms": time.time_ns() // 1000000,
               "previous_ref": None, "observations": [], "output_refs": []}
    from .native_image_evidence import execution_installation_identity
    attempt["execution_identity"] = execution_installation_identity()
    validate_schema("generation_attempt", attempt)
    ref = store.put_json_object(attempt)
    return {**task, "generation_attempts": [*(task.get("generation_attempts") or []), ref]}, attempt, ref


def settle_attempt(store, document, task, target, *, attempt_id, outcome, report_bytes, invocation_ref,
                   adapter_context=None):
    if not attempt_id:
        raise _error("generation_attempt_required", "attempt_id", "settlement must name its begun attempt")
    attempt, prior_ref = _read_owned(store, task, "generation_attempts", attempt_id)
    if attempt["allowance_id"] != target["allowance_id"] or attempt["execution_ref"] != target["execution_ref"]:
        raise _error("generation_binding_conflict", "attempt_id", "attempt does not own this call allowance", conflict=True)
    # Empty Host input is not evidence. Wrapping it in non-empty observation
    # metadata must not turn an unknown call into consumed/released, nor prove
    # a newly supplied invocation identity. Exact known-state replay remains
    # available without inventing a new report.
    try:
        report = json.loads(report_bytes) if report_bytes else {}
    except (ValueError, UnicodeError, TypeError) as exc:
        raise _error('generation_request_invalid', 'report', 'observation report must be a JSON object') from exc
    if not isinstance(report, dict):
        raise _error("generation_request_invalid", "report", "observation report must be a JSON object")
    if not report and ((outcome == 'consumed' and target['state'] != 'consumed')
            or (target['state'] == 'unknown' and outcome != 'unknown')
            or (invocation_ref and not target.get('invocation_ref'))):
        raise tasks.EnvelopeError('(settle)/report', 'changing this call fact requires its actual report')
    if not report:
        # No submitted observation means no new immutable evidence. In
        # particular a known receipt can be read/replayed without an adapter
        # and without manufacturing a different empty Host report.
        settled = tasks._settle_target(store, document, task['task_id'], target['allowance_id'],
            target, outcome, None, 'json', invocation_ref)
        return task, settled, prior_ref
    output_ref = None
    if report.get("source") == "native_host_image.v1":
        from .native_image_evidence import (NativeObservationRejected, consume_image_context,
                                            unusable_receipt_ref)
        selector = {key: report.get(key) for key in ("provider_id", "event_id")}
        try:
            if set(report) != {"source", "provider_id", "event_id"}:
                raise NativeObservationRejected("report", "native selectors cannot carry self-reported claims")
            if outcome != "consumed":
                raise NativeObservationRejected("outcome", "a successful native completion is a consumed call")
            # A terminal replay reads an already authenticated call fact. It
            # confers no new output or execution/adoption permission, and does
            # not require a live proof after that call's target was adopted.
            metadata = next((observed for ref in attempt["observations"]
                if (observed := store.read_object_json(ref)).get("observer") == "tool_observed"
                and observed.get("source", {}).get("source") == "native_host_image.v1"
                and all(observed["source"].get(key) == value for key, value in selector.items())), None
                ) if target["state"] == "consumed" else None
            if metadata is None:
                metadata, output = consume_image_context(adapter_context, store, document, task, attempt, selector)
                output_ref = store.put_blob(output, ext="png")
            if invocation_ref and invocation_ref != metadata["invocation_ref"]:
                raise NativeObservationRejected("invocation_ref", "native invocation differs from the supplied identity")
            invocation_ref = metadata["invocation_ref"]
        except Exception as exc:  # proof admission never rolls back an already sent call
            # Proof rejection must not roll back an already sent call's facts.
            # The report stays Host-attested and cannot satisfy image adoption.
            metadata = {"schema_version": "tool_observation.v1", "observer": "host_reported", "collector": None,
                        "submitted": None, "coverage": {}, "output": None, "invocation_ref": invocation_ref,
                        "reported": {"selector": report, "native_observation_rejected": {
                            "code": getattr(exc, "error_code", "native_image_observation_rejected"),
                            "field": getattr(exc, "path", "adapter_context"),
                            "message": getattr(exc, "detail", "native observation provider validation failed")},
                            "unusable_receipt_ref": unusable_receipt_ref(adapter_context)}}
    elif report.get("source") == "codex_session.v1":
        if outcome != "consumed":
            raise _error("generation_binding_conflict", "outcome", "a completed native output is a consumed call", conflict=True)
        if attempt["execution_ref"] != f"codex:{report.get('thread_id')}:{report.get('turn_id')}":
            raise _error("generation_binding_conflict", "execution_ref", "native event does not belong to the claimed execution", conflict=True)
        observed = collect_codex_image(report, minimum_started_at_ms=attempt["started_at_ms"], reference_store=store)
        metadata = observed.metadata
        if invocation_ref and invocation_ref != metadata["invocation_ref"]:
            raise _error("generation_binding_conflict", "invocation_ref", "native invocation differs from the supplied identity", conflict=True)
        invocation_ref = metadata["invocation_ref"]
        output_ref = store.put_blob(observed.output_bytes, ext="png")
    else:
        # Even a JSON field saying provider_receipt/tool_observed remains a
        # Host statement. Only the collector branch can confer native coverage.
        metadata = {"schema_version": "tool_observation.v1", "observer": "host_reported", "collector": None,
                    "submitted": report.get("submitted"), "reported": report, "invocation_ref": invocation_ref,
                    "coverage": {}, "output": None}
    validate_schema("tool_observation", metadata)
    canonical_report = canonical_json_bytes(metadata)
    settlement_report = canonical_report
    if (metadata['observer'] == 'host_reported' and target['state'] == 'consumed'
            and invocation_ref and not target.get('invocation_ref')):
        # A missing invocation can be enriched using the same original report.
        # The optional metadata field changes, but the observed report does not;
        # retain both immutable observations and all previous call evidence.
        content = {key: value for key, value in metadata.items() if key != 'invocation_ref'}
        for ref in attempt['observations']:
            prior = store.read_object_json(ref)
            if (prior.get('observer') == 'host_reported' and not prior.get('invocation_ref')
                    and {key: value for key, value in prior.items() if key != 'invocation_ref'} == content):
                settlement_report = store.read_object_bytes(ref)
                break
    # A later native receipt may enrich a Host-only consumed fact without
    # changing consumption. Preserve the earlier report and its attempt version.
    settlement_target = target
    if metadata["observer"] == "tool_observed" and target["state"] == "consumed":
        prior_native = [store.read_object_json(r) for r in attempt["observations"]
                        if store.read_object_json(r).get("observer") == "tool_observed"]
        if not prior_native:
            settlement_target = {**target, "evidence": []}
    settled = tasks._settle_target(store, document, task["task_id"], target["allowance_id"], settlement_target, outcome,
                                   settlement_report, "json", invocation_ref)
    settled["evidence"] = list(target.get("evidence") or []) + [r for r in settled["evidence"] if r not in (target.get("evidence") or [])]
    settled["evidence_level"] = metadata["observer"]
    obs_ref = store.put_blob(canonical_report, ext="json")
    if obs_ref not in settled['evidence']:
        settled['evidence'].append(obs_ref)
    if obs_ref in attempt["observations"]:
        return task, settled, prior_ref
    updated_attempt = {**attempt, "previous_ref": prior_ref, "observations": [*attempt["observations"], obs_ref],
                       "output_refs": [*attempt["output_refs"], *([output_ref] if output_ref and output_ref not in attempt["output_refs"] else [])]}
    validate_schema("generation_attempt", updated_attempt)
    new_ref = store.put_json_object(updated_attempt)
    updated = {**task, "generation_attempts": [new_ref if ref == prior_ref else ref for ref in task["generation_attempts"]]}
    return updated, settled, new_ref


def comparison(request, observation):
    """Report only fields actually exposed by this observation's collector."""
    expected = request["input"]
    submitted = observation.get("submitted") or {}
    differences, unknown = [], []
    if observation.get("observer") != "tool_observed":
        return {"status": "unverified", "differences": [], "unknown": ["prompt", "references", "parameters", "output"]}
    if submitted.get("prompt") != expected["prompt"]:
        differences.append("prompt")
    for key, value in expected["parameters"].items():
        if key not in (submitted.get("parameters") or {}):
            unknown.append("parameters." + key)
        elif submitted["parameters"][key] != value:
            differences.append("parameters." + key)
    for key in (submitted.get("parameters") or {}).keys() - expected["parameters"].keys():
        differences.append("parameters." + key)
    if submitted.get("references") is None:
        unknown.append("references")
    elif submitted["references"] != expected["references"]:
        differences.append("references")
    return {"status": "mismatch" if differences else "partial" if unknown else "match",
            "differences": differences, "unknown": unknown}


def adoption_binding(store, document, task, envelope, staged):
    if not is_new(task):
        if envelope.get("generation_result"):
            raise _error("host_protocol_unsupported", "generation_result", "old tasks cannot claim a new generation binding")
        return None
    check_host(task)
    binding = envelope.get("generation_result")
    if not isinstance(binding, dict) or set(binding) != {"request_id", "attempt_id"}:
        raise _error("generation_attempt_required", "generation_result", "result must bind one request and attempt")
    attempt, attempt_ref = _read_owned(store, task, "generation_attempts", binding["attempt_id"])
    request, request_ref = _read_owned(store, task, "generation_requests", binding["request_id"])
    if attempt["request_ref"] != request_ref:
        raise _error("generation_binding_conflict", "generation_result", "request and attempt do not correspond", conflict=True)
    allowance = next(c for c in task["call_allowances"] if c["allowance_id"] == attempt["allowance_id"])
    if allowance["state"] != "consumed":
        raise _error("generation_evidence_incomplete", "call_allowance", "settle the actual call before adopting its output")
    specs = envelope.get("artifact_specs") or []
    if len(specs) != 1 or specs[0].get("role") != "blueprint":
        raise _error("generation_request_invalid", "artifact_specs", "one generation attempt returns one original image")
    output_hash = sha256_bytes(staged[specs[0]["file_id"]]["bytes"])
    observations = [store.read_object_json(ref) for ref in attempt["observations"]]
    observed = next((o for o in observations if o.get("observer") == "tool_observed"
                     and (o.get("output") or {}).get("sha256") == output_hash), None)
    if not observed:
        raise _error("generation_evidence_incomplete", "observation", "a native observation must bind this exact output; call facts are retained")
    compared = comparison(request, observed)
    if compared["differences"]:
        raise _error("generation_input_mismatch", "submitted", "observed tool input differs from the frozen input; facts are retained", conflict=True)
    required_unknown = [key for key in compared["unknown"] if key != "references" or request["input"]["references"]]
    if required_unknown:
        raise _error("generation_evidence_incomplete", "submitted", "native record does not cover required attachments or parameters; facts are retained")
    return {"request_ref": request_ref, "attempt_ref": attempt_ref, "request": request, "observation": observed, "comparison": compared}


def bind_artifact(store, artifact, binding):
    if binding is None:
        return artifact
    observation = binding["observation"]
    existing_prompt = artifact["provenance"].get("submitted_prompt")
    if existing_prompt and store.read_object_bytes(existing_prompt) != observation["submitted"]["prompt"].encode("utf-8"):
        raise _error("generation_input_mismatch", "artifact/submitted_prompt", "supplied prompt differs from the native observation", conflict=True)
    artifact["provenance"].update(generation_request=binding["request_ref"], generation_attempt=binding["attempt_ref"],
                                  invocation_ref=observation["invocation_ref"], generated_from_page=binding["request"]["input"]["page"]["page_ref"],
                                  submitted_prompt=store.put_blob(observation["submitted"]["prompt"].encode("utf-8"), ext="txt"))
    return artifact
