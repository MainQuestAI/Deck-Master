"""SDK bridge to registered, authenticated review-event providers.

No provider ships with the runtime. Registration is trusted service bootstrap,
not a CLI option or JSON input. A provider must authenticate its own transport
(or an external issuer's signature) before returning claims. A trusted Host
controller directly observing native subagent executions is a supported
protected-transport integration at host_attested assurance; no platform
cryptographic signature is required for ordinary independent-model review. A local file hash,
a key available to the author Host, or a caller's ``verified`` flag is not such
an authentication. This module checks exact runtime bindings after that step.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Protocol
import re
import weakref

from .errors import TypedServiceError
from .models import canonical_json_bytes, sha256_bytes, validate_schema

CAPABILITIES = ("verified_user_events", "independent_review_receipts", "human_review_receipts")
MAX_RECEIPT_BYTES = 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")
_CONTEXTS = weakref.WeakKeyDictionary()


class EvidenceRejected(TypedServiceError):
    error_code = "review_evidence_rejected"
    exit_code = 4


class ProviderUnavailable(TypedServiceError):
    error_code = "needs_reviewer"
    exit_code = 3


class ReceiptProvider(Protocol):
    """Implement in a trusted Host/controller integration separate from authors.

    ``verify`` must reject unauthenticated bytes and validate issuer/transport,
    actual execution identity (not the author's claimed ID), completion, and the
    event's evidence kind. Independent execution also requires real author
    provenance; renaming the same executor does not establish independence.
    ``health`` proves that this configured provider is currently reachable.
    """
    provider_id: str
    adapter_version: str
    authentication: str  # external_signature | protected_transport
    channels: tuple[str, ...]

    def health(self) -> bool: ...
    def fetch(self, event_id: str) -> bytes: ...
    def verify(self, raw: bytes) -> dict: ...


class TrustedContext:
    """Opaque service capability. Constructing/copying/JSON cannot mint one."""
    __slots__ = ("__weakref__",)


def _mint(registry, payload):
    value = TrustedContext()
    _CONTEXTS[value] = (registry, deepcopy(payload))
    return value


def context_payload(context=None) -> dict:
    if context is None:
        return {}
    if not isinstance(context, TrustedContext) or context not in _CONTEXTS:
        raise EvidenceRejected("adapter_context", "a registered provider must issue an opaque trusted context; JSON/dict is untrusted")
    registry, payload = _CONTEXTS[context]
    # Health is not a permanent grant. Receipts remain independently bound.
    result = deepcopy(payload)
    result["capabilities"] = registry.capabilities()
    return result


def reviewer_capabilities(context=None) -> dict:
    if context is None:
        return DEFAULT_REGISTRY.capabilities()
    payload = context_payload(context)
    return {key: bool((payload.get("capabilities") or {}).get(key)) for key in CAPABILITIES}


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result
    except (TypeError, AttributeError, ValueError) as exc:
        raise EvidenceRejected("receipt/time", "receipt times require timezone-aware ISO timestamps") from exc


def result_digest(envelope):
    from .tasks import parse_envelope
    return sha256_bytes(canonical_json_bytes(parse_envelope(envelope)))


def review_binding(store, document, task, envelope):
    from .content_review import _subjects_digest, author_execution_refs
    if task.get("kind") != "review" or task.get("review_stage") != "preproduction":
        raise EvidenceRejected("receipt/task", "this bridge only accepts preproduction review tasks")
    packets = []
    for ref in task.get("inputs") or []:
        try:
            obj = store.read_object_json(ref)
        except Exception:  # noqa: BLE001 - unrelated binary input
            continue
        if obj.get("schema_version") == "content_review_packet.v1":
            packets.append(ref)
    if len(packets) != 1:
        raise EvidenceRejected("receipt/packet", "review task requires exactly one fixed complete review packet")
    subjects = ([document["narrative"]] if document.get("narrative") else [])
    if document.get("content_plan"):
        subjects.append(document["content_plan"])
    subjects += [entry["page"] for entry in document["pages"] if entry["page_id"] in task["scope_pages"]]
    return {"project_id": document["project_id"],
            "request_id": (task.get("collaboration_binding") or {}).get("request_id"),
            "task_id": task["task_id"], "packet_sha256": packets[0]["sha256"],
            "subjects_sha256": _subjects_digest(subjects),
            "author_execution_refs": sorted(author_execution_refs(store, document, subjects)),
            "write_scope": {"layers": ["review"], "page_ids": list(task["scope_pages"])},
            "result_sha256": result_digest(envelope)}


class ProviderRegistry:
    """Trusted bootstrap registry; never load provider code from request data."""
    def __init__(self):
        self._providers = {}
        self._seen = {}

    def register(self, provider: ReceiptProvider):
        identity = provider.provider_id
        if (not isinstance(identity, str) or not _ID.fullmatch(identity)
                or identity in self._providers or not provider.adapter_version
                or provider.authentication not in ("external_signature", "protected_transport")
                or not isinstance(provider.channels, tuple) or not provider.channels
                or any(key not in CAPABILITIES for key in provider.channels)
                or any(not callable(getattr(provider, name, None)) for name in ("health", "fetch", "verify"))):
            raise EvidenceRejected("provider", "register one authenticated provider at trusted service startup")
        self._providers[identity] = provider

    def capabilities(self):
        ready = {key: False for key in CAPABILITIES}
        for provider in self._providers.values():
            try:
                available = provider.health() is True
            except Exception:  # noqa: BLE001 - an unavailable provider never upgrades
                available = False
            if available:
                for key in provider.channels:
                    ready[key] = True
        return ready

    def describe(self):
        values = []
        for provider in self._providers.values():
            try:
                ready = provider.health() is True
            except Exception:  # noqa: BLE001
                ready = False
            values.append({"provider_id": provider.provider_id, "adapter_version": provider.adapter_version,
                           "authentication": provider.authentication, "channels": list(provider.channels),
                           "status": "available" if ready else "unavailable"})
        return {"providers": values, "capabilities": self.capabilities()}

    def channel_context(self):
        """Advertise real live channels; this contains no completed receipts."""
        return _mint(self, {"adapter_version": ",".join(p.adapter_version for p in self._providers.values()) or None,
                           "verified_user_events": [], "independent_review_receipts": [], "human_review_receipts": []})

    def _resolve(self, selector, channel, expected):
        if (not isinstance(selector, dict) or set(selector) != {"provider_id", "event_id"}
                or not all(isinstance(selector.get(k), str) and _ID.fullmatch(selector[k])
                           for k in ("provider_id", "event_id"))):
            raise EvidenceRejected("receipt_selector", "provide only registered provider_id and event_id")
        provider = self._providers.get(selector["provider_id"])
        if provider is None:
            raise ProviderUnavailable("receipt_selector/provider_id", "no trusted receipt provider is installed")
        try:
            ready = provider.health() is True and channel in provider.channels
        except Exception:  # noqa: BLE001
            ready = False
        if not ready:
            raise ProviderUnavailable("provider", "the required authenticated provider channel is unavailable")
        try:
            raw = provider.fetch(selector["event_id"])
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RECEIPT_BYTES:
                raise ValueError("invalid receipt bytes")
            claims = provider.verify(raw)
        except Exception as exc:  # noqa: BLE001 - no unverified fallback
            raise EvidenceRejected("receipt/authentication", "provider could not authenticate the selected event") from exc
        if not isinstance(claims, dict):
            raise EvidenceRejected("receipt", "authenticated event claims must be an object")
        if (claims.get("provider_id") != provider.provider_id or claims.get("event_id") != selector["event_id"]
                or claims.get("channel") != channel):
            raise EvidenceRejected("receipt/identity", "authenticated issuer, event and channel must match the selector")
        for key, value in expected.items():
            if claims.get(key) != value:
                raise EvidenceRejected("receipt/" + key, "authenticated event does not bind this exact " + key)
        now = datetime.now(timezone.utc)
        issued, expires = _time(claims.get("issued_at")), _time(claims.get("expires_at"))
        if issued > now or not issued <= now < expires:
            raise EvidenceRejected("receipt/time", "receipt is expired or not yet valid")
        key = (provider.provider_id, selector["event_id"])
        digest = sha256_bytes(canonical_json_bytes({"claims": claims, "raw_sha256": sha256_bytes(raw)}))
        if key in self._seen and self._seen[key] != digest:
            raise EvidenceRejected("receipt/event_id", "one event cannot be replayed with changed claims or bytes")
        self._seen[key] = digest
        return provider, raw, deepcopy(claims)

    def review_context(self, store, document, task, envelope, selector):
        expected = review_binding(store, document, task, envelope)
        reviewers = [item.get("reviewer") or {} for item in envelope.get("reviews") or []]
        human = bool(reviewers) and all(item.get("type") in ("human_internal", "human_external") for item in reviewers)
        channel = "human_review_receipts" if human else "independent_review_receipts"
        provider, raw, claims = self._resolve(selector, channel, expected)
        executor = claims.get("executor_ref")
        if not human:
            if not executor or executor in expected["author_execution_refs"]:
                raise EvidenceRejected("receipt/executor_ref", "the author cannot be recorded as an independent reviewer")
            if task.get("execution_ref") and task["execution_ref"] != executor:
                raise EvidenceRejected("receipt/executor_ref", "receipt executor must match the claimed review task execution")
            if not reviewers or any(item.get("execution_ref") != executor for item in reviewers):
                raise EvidenceRejected("receipt/executor_ref", "review records must name the actual authenticated executor")
        else:
            if not claims.get("reviewer_id") or any(
                (item.get("identity_receipt") or {}).get("event_id") != claims["event_id"]
                or (item.get("identity_receipt") or {}).get("reviewer_id") != claims["reviewer_id"] for item in reviewers):
                raise EvidenceRejected("receipt/reviewer_id", "human identity events must bind every review record")
        raw_ref = store.put_blob(raw, ext="json")
        proof = {"schema_version": "authenticated_review_receipt.v1", "provider_id": provider.provider_id,
                 "adapter_version": provider.adapter_version, "authentication": provider.authentication,
                 "raw_event_ref": raw_ref, "claims": claims}
        validate_schema("authenticated_review_receipt", proof)
        receipt = {**claims, "receipt_ref": store.put_json_object(proof)}
        payload = {"adapter_version": provider.adapter_version, "review_binding": expected,
                   "verified_user_events": [], "independent_review_receipts": [], "human_review_receipts": []}
        payload[channel] = [receipt]
        return _mint(self, payload)

    def user_event_context(self, store, document, *, action_binding, source_ref, presentation_ref, receipt_ref, selector):
        expected = {"project_id": document["project_id"], "request_id":
                    ((document.get("collaboration") or {}).get("request") or {}).get("request_id"),
                    "action_binding": action_binding, "source_ref": source_ref, "presentation_ref": presentation_ref,
                    "receipt_ref": receipt_ref, "transport_record_sha256": sha256_bytes(store.read_object_bytes(receipt_ref))}
        provider, raw, claims = self._resolve(selector, "verified_user_events", expected)
        if not claims.get("actor_id"):
            raise EvidenceRejected("receipt/actor_id", "authenticated user event requires an actual actor")
        return _mint(self, {"adapter_version": provider.adapter_version,
                           "verified_user_events": [{**claims, "receipt_ref": receipt_ref}],
                           "independent_review_receipts": [], "human_review_receipts": [],
                           "authenticated_event_sha256": sha256_bytes(raw)})


# Empty by design. A real integration registers its authenticated provider at
# service bootstrap, never from an environment-variable module path or JSON.
DEFAULT_REGISTRY = ProviderRegistry()


def validate_review_context(context, store, document, task, envelope):
    payload = context_payload(context)
    expected = review_binding(store, document, task, envelope)
    if payload.get("review_binding") != expected:
        raise EvidenceRejected("adapter_context/review_binding", "a channel capability is not a completed receipt for this result")
    receipts = payload.get("independent_review_receipts") or payload.get("human_review_receipts") or []
    if not receipts or any(_time(r.get("expires_at")) <= datetime.now(timezone.utc) for r in receipts):
        raise EvidenceRejected("receipt/time", "completed authenticated receipt is absent or expired")
    for receipt in receipts:
        proof = store.read_object_json(receipt["receipt_ref"])
        validate_schema("authenticated_review_receipt", proof)
        if proof["claims"] != {key: value for key, value in receipt.items() if key != "receipt_ref"}:
            raise EvidenceRejected("receipt/proof", "stored authenticated proof differs from the issued context")
    return payload
