"""Trusted SDK transport for actual Host-observed native image completions.

The provider is configured by a controller at service bootstrap. Public JSON
selects an event, never its trust. This is Host attestation of an actual native
call, not a platform signature or protection against a coequal malicious Host.
The genuine Desktop collector remains a separate, unchanged source version.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
import io
import re
import time
import weakref

from PIL import Image

from .errors import TypedServiceError
from .models import canonical_json_bytes, sha256_bytes, validate_schema

SOURCE = "native_host_image.v1"
COLLECTOR = "native-host-image.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
MAX_EVENT_BYTES = 64 * 1024 * 1024
_CONTEXTS = weakref.WeakKeyDictionary()


class NativeObservationRejected(TypedServiceError):
    error_code = "native_image_observation_rejected"


def _reject(field, message):
    return NativeObservationRejected(field, message)


@dataclass(frozen=True)
class NativeImageCompletion:
    """An authenticated provider result, not a public request payload."""
    claims: dict
    output_bytes: bytes


class NativeImageContext:
    """Only a registered Runtime can mint a completed observation context."""
    __slots__ = ("__weakref__",)


def control_digest(document, *, store, task):
    """Current control and actual target slots, separate from historical input."""
    region = document.get("collaboration") or {}
    control = {"request": region.get("request"), "authority_policy": region.get("authority_policy")}
    from .dependency_slices import _head_for_identity
    from .visual_dependencies import page_visual_digest
    binding = task.get("collaboration_binding") or {}
    authorization_ref = binding.get("authorization_ref")
    if authorization_ref is not None:
        record = store.read_object_json(authorization_ref)
        control["authorization_head"] = _head_for_identity(
            store, document, "authorizations", "authorization_id", record["authorization_id"])
    ids = set(task.get("scope_pages") or [])
    return sha256_bytes(canonical_json_bytes({
        "policy": document.get("policy"), "collaboration": control,
        "pages": [{"page_id": entry["page_id"],
                   "visual_sha256": page_visual_digest(store.read_object_json(entry["page"])),
                   "blueprint": entry.get("blueprint")} for entry in document["pages"] if entry["page_id"] in ids],
    }))


def execution_installation_identity():
    """Observe this actual SDK/install, including the executing runtime bytes."""
    from pathlib import Path
    from .capabilities import installation_identity
    from .method_resources import method_release, method_resources
    value = installation_identity()
    root = Path(__file__).parent
    value["runtime_sha256"] = {name: sha256_bytes((root / name).read_bytes()) for name in (
        "generation.py", "observations.py", "native_image_evidence.py", "production.py", "tasks.py")}
    value["blueprint_method_release"] = method_release(method_resources("blueprint"))
    return value


def image_binding(store, document, task_id, attempt_id):
    from . import generation, tasks
    task = tasks._lookup_task(document, task_id, store)
    if not generation.is_new(task) or task.get("kind") != "blueprint":
        raise _reject("task", "native observations require a generation.v1 blueprint Task")
    if not tasks.task_inputs_current(store, document, task):
        raise _reject("visual_inputs", "the Task's registered visual Page/Plan/design inputs changed")
    attempt, attempt_ref = generation._read_owned(store, task, "generation_attempts", attempt_id)
    # Observation appends version the Attempt. The genuine call identity is
    # its immutable begun version, so an exact settlement replay is stable.
    begun_ref, begun = attempt_ref, attempt
    seen = set()
    while begun.get("previous_ref") is not None:
        pair = (begun_ref["path"], begun_ref["sha256"])
        if pair in seen or len(seen) >= 4096:
            raise _reject("attempt_ref", "invalid Attempt observation ancestry")
        seen.add(pair)
        begun_ref = begun["previous_ref"]
        begun = store.read_object_json(begun_ref)
        validate_schema("generation_attempt", begun)
        fixed = ("attempt_id", "task_id", "project_id", "request_ref", "allowance_id",
                 "execution_ref", "started_at_ms", "execution_identity")
        if any(begun.get(key) != attempt.get(key) for key in fixed):
            raise _reject("attempt_ref", "Attempt ancestry changed the actual begun call identity")
    request_ref = attempt["request_ref"]
    request = store.read_object_json(request_ref)
    validate_schema("generation_request", request)
    if (request_ref not in task.get("generation_requests", [])
            or request["task_id"] != task_id or request["project_id"] != document["project_id"]
            or request["input_hash"] != sha256_bytes(canonical_json_bytes(request["input"]))):
        raise _reject("request", "the Attempt must bind its exact owned frozen Request")
    allowance = next((entry for entry in task["call_allowances"]
                      if entry["allowance_id"] == attempt["allowance_id"]), None)
    if (allowance is None or allowance.get("execution_ref") != attempt["execution_ref"]
            or allowance["state"] not in ("in_flight", "consumed", "unknown")):
        raise _reject("allowance", "a real begun call allowance is required")
    binding = {"project_id": document["project_id"],
               "request_id": (task.get("collaboration_binding") or {}).get("request_id"),
               "task_id": task_id, "generation_request_ref": request_ref,
               "generation_request_id": request["request_id"], "input_hash": request["input_hash"],
               "attempt_ref": begun_ref, "attempt_id": attempt_id,
               "allowance_id": attempt["allowance_id"], "execution_ref": attempt["execution_ref"],
               "prompt": request["input"]["prompt"],
               "references": request["input"]["references"],
               "parameters": request["input"]["parameters"],
               "control_sha256": control_digest(document, store=store, task=task),
               "execution_identity": attempt.get("execution_identity"),
               "settlement_reader_identity": execution_installation_identity()}
    if not isinstance(binding["execution_identity"], dict):
        raise _reject("execution_identity", "this old Attempt has no recorded actual execution/install identity")
    return binding, task, attempt, request


class NativeImageRegistry:
    """Trusted controller bootstrap; no provider modules come from JSON/env."""
    def __init__(self):
        self._providers = {}
        self._seen = {}
        self._sealed = False

    def register(self, provider):
        identity = getattr(provider, "provider_id", None)
        if (self._sealed or not isinstance(identity, str) or not _ID.fullmatch(identity)
                or identity in self._providers or not getattr(provider, "adapter_version", None)
                or getattr(provider, "authentication", None) != "protected_transport"
                or any(not callable(getattr(provider, name, None)) for name in ("health", "fetch", "verify"))):
            raise _reject("provider", "configure one actual controller provider at trusted bootstrap")
        self._providers[identity] = provider

    def image_context(self, store, document, *, task_id, attempt_id, selector):
        if not self._sealed or _REGISTRY.get() is not self:
            raise _reject("provider", "issue native image contexts inside the configured sealed Runtime")
        if (not isinstance(selector, dict) or set(selector) != {"provider_id", "event_id"}
                or any(not isinstance(selector.get(key), str) or not _ID.fullmatch(selector[key])
                       for key in ("provider_id", "event_id"))):
            raise _reject("selector", "use registered provider_id and actual controller event_id")
        provider = self._providers.get(selector["provider_id"])
        if provider is None or provider.health() is not True:
            raise _reject("provider", "the actual native image controller is unavailable")
        expected, _, attempt, request = image_binding(store, document, task_id, attempt_id)
        try:
            raw = provider.fetch(selector["event_id"])
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_EVENT_BYTES:
                raise ValueError("invalid event bytes")
            verified = provider.verify(raw)
        except Exception as exc:  # noqa: BLE001 - no public-data fallback
            raise _reject("transport", "the controller did not authenticate this observed native event") from exc
        if not isinstance(verified, NativeImageCompletion):
            raise _reject("transport", "the provider must return an authenticated native completion")
        claims = deepcopy(verified.claims)
        if (not isinstance(claims, dict) or claims.get("provider_id") != provider.provider_id
                or claims.get("event_id") != selector["event_id"] or claims.get("binding") != expected
                or claims.get("tool_name") != "image_gen__imagegen"
                or claims.get("status") != "completed"):
            raise _reject("binding", "native completion must bind the exact Task/Request/Attempt and current control")
        now = time.time_ns() // 1_000_000
        issued, expires = claims.get("issued_at_ms"), claims.get("expires_at_ms")
        started, completed = claims.get("started_at_ms"), claims.get("completed_at_ms")
        if (any(not isinstance(value, int) or isinstance(value, bool)
                for value in (issued, expires, started, completed))
                or not issued <= now < expires or not attempt["started_at_ms"] <= started <= completed <= now):
            raise _reject("time", "use actual controller observation times and a currently valid receipt")
        arguments = claims.get("arguments")
        if (not isinstance(arguments, dict)
                or set(arguments) not in ({"prompt", "transparent_background"},
                                         {"prompt", "transparent_background", "referenced_image_paths"})
                or not isinstance(arguments.get("prompt"), str)
                or not isinstance(arguments.get("transparent_background"), bool)):
            raise _reject("arguments", "the actual native literal call exposes only supported image arguments")
        from .observations import _fixed_object_references
        paths = arguments.get("referenced_image_paths")
        if paths is None:
            references = []
        elif (isinstance(paths, list) and 1 <= len(paths) <= 16
              and all(isinstance(path, str) for path in paths)):
            references = _fixed_object_references(store, paths, started)
        else:
            references = None
        if references is None:
            raise _reject("references", "actual attachments must be unchanged same-project immutable image blobs")
        output = verified.output_bytes
        if not isinstance(output, bytes) or not 0 < len(output) <= MAX_EVENT_BYTES:
            raise _reject("output", "a native completion must return its original PNG bytes")
        try:
            with Image.open(io.BytesIO(output)) as original:
                if original.format != "PNG":
                    raise ValueError("not PNG")
                dimensions = list(original.size)
                original.verify()
        except (OSError, ValueError) as exc:
            raise _reject("output", "native output is not a valid original PNG") from exc
        output_sha = sha256_bytes(output)
        if claims.get("output_sha256") != output_sha:
            raise _reject("output", "controller completion and original PNG bytes differ")
        invocation = claims.get("invocation_ref")
        if invocation is not None and (not isinstance(invocation, str) or not invocation):
            raise _reject("invocation_ref", "unknown platform invocation stays null")
        # The controller event locator is explicitly not an invented platform ID.
        ledger_invocation = invocation or f"native-host:{provider.provider_id}:{selector['event_id']}"
        metadata = {"schema_version": "tool_observation.v1", "observer": "tool_observed",
                    "collector": COLLECTOR, "invocation_ref": ledger_invocation,
                    "source": {"source": SOURCE, **selector, "adapter_version": provider.adapter_version,
                               "authentication": "protected_transport", "assurance": "host_attested",
                               "raw_event_sha256": sha256_bytes(raw), "platform_invocation_ref": invocation,
                               "fee": "not_reported", "model": "unknown", "seed": "unknown"},
                    "started_at_ms": started, "completed_at_ms": completed,
                    "submitted": {"prompt": arguments["prompt"], "references": references,
                                  "parameters": {"transparent_background": arguments["transparent_background"]},
                                  "model": None, "seed": None},
                    "coverage": {"prompt": "controller observed actual native arguments",
                                 "references": "ordered literal object paths; immutable bytes and pre-call timestamps verified",
                                 "parameters": {"transparent_background": "controller observed actual native arguments"},
                                 "output": "controller observed original native PNG", "model": "unknown", "seed": "unknown"},
                    "output": {"sha256": output_sha, "media_type": "image/png", "dimensions": dimensions},
                    "trust_scope": "host_attested actual native controller observation; not platform signed; coequal malicious Host excluded"}
        from .generation import comparison
        compared = comparison(request, metadata)
        if compared["status"] != "match":
            raise _reject("submitted", "actual native input does not fully match the frozen prompt, attachments and parameters")
        event_key = (provider.provider_id, selector["event_id"])
        digest = sha256_bytes(canonical_json_bytes({"claims": claims, "raw_sha256": sha256_bytes(raw)}))
        if event_key in self._seen and self._seen[event_key] != digest:
            raise _reject("event_id", "an observed event cannot be rebound or replayed with changed bytes")
        self._seen[event_key] = digest
        raw_ref = store.put_blob(raw, ext="json")
        proof = {"schema_version": "native_image_receipt.v1", "provider_id": provider.provider_id,
                 "adapter_version": provider.adapter_version, "assurance": "host_attested",
                 "authentication": "protected_transport", "raw_event_ref": raw_ref, "claims": claims}
        validate_schema("native_image_receipt", proof)
        metadata["source"]["receipt_ref"] = store.put_json_object(proof)
        validate_schema("tool_observation", metadata)
        context = NativeImageContext()
        _CONTEXTS[context] = (self, expected, metadata, output, expires)
        return context


DEFAULT_REGISTRY = NativeImageRegistry()
DEFAULT_REGISTRY._sealed = True
_REGISTRY = ContextVar("deck_master_native_image_registry", default=DEFAULT_REGISTRY)


class NativeImageRuntime:
    def __init__(self, registry):
        if not isinstance(registry, NativeImageRegistry):
            raise _reject("provider", "configure a native image registry at trusted bootstrap")
        registry._sealed = True
        self.registry = registry

    @contextmanager
    def bound(self):
        token = _REGISTRY.set(self.registry)
        try:
            yield self
        finally:
            _REGISTRY.reset(token)


def consume_image_context(context, store, document, task, attempt, selector):
    if not isinstance(context, NativeImageContext) or context not in _CONTEXTS:
        raise _reject("adapter_context", "ordinary JSON/self-labels cannot mint a native image observation")
    registry, expected, metadata, output, expires = _CONTEXTS[context]
    if registry is not _REGISTRY.get() or time.time_ns() // 1_000_000 >= expires:
        raise _reject("adapter_context", "native image context is foreign or expired")
    provider = registry._providers.get(selector.get("provider_id"))
    if (provider is None or provider.health() is not True
            or any(metadata["source"].get(key) != selector.get(key) for key in ("provider_id", "event_id"))):
        raise _reject("selector", "context belongs to a different actual native completion")
    current, _, _, _ = image_binding(store, document, task["task_id"], attempt["attempt_id"])
    if current != expected:
        raise _reject("binding", "Task/Request/Attempt/target or current control changed after observation")
    return deepcopy(metadata), output


def unusable_receipt_ref(context):
    """Retain an actually issued proof as history even when adoption is refused."""
    if isinstance(context, NativeImageContext) and context in _CONTEXTS:
        return deepcopy(_CONTEXTS[context][2]["source"].get("receipt_ref"))
    return None
