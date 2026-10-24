"""Synthetic L1 provider only. Never packaged or a real identity claim.

Tests explicitly issue fixture completions before invoking production acceptance.
No monkeypatch of gates, runtime context minting or default registry is used.
"""
from datetime import datetime, timedelta, timezone
import json
import weakref

from deck_master import content_review, review_evidence, service
from deck_master.models import canonical_json_bytes, sha256_bytes
from deck_master.store import Store

_FIXTURES = weakref.WeakKeyDictionary()


class SyntheticProvider:
    provider_id = "synthetic-l1"
    adapter_version = "synthetic-l1.v1"
    authentication = "protected_transport"  # test doubles authenticate fixture bytes, no real transport claimed
    channels = ("independent_review_receipts", "verified_user_events", "human_review_receipts")

    def __init__(self):
        self.events = {}
        self.ready = True

    def health(self):
        return self.ready

    def fetch(self, event_id):
        return self.events[event_id]

    def verify(self, raw):
        if raw not in self.events.values():
            raise ValueError("not a synthetic fixture completion")
        return json.loads(raw)

    def issue(self, event_id, claims, channel):
        now = datetime.now(timezone.utc)
        complete = {"provider_id": self.provider_id, "event_id": event_id, "channel": channel,
                    "issued_at": (now - timedelta(seconds=1)).isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(), **claims}
        self.events[event_id] = canonical_json_bytes(complete)
        return {"provider_id": self.provider_id, "event_id": event_id}


def synthetic_context(receipts=None):
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    ctx = registry.channel_context()
    _FIXTURES[ctx] = (registry, provider, receipts or {})
    return ctx


def receipt_context(channel_context, store, task, envelope):
    registry, provider, options = _FIXTURES[channel_context]
    document = store.load_document()
    binding = review_evidence.review_binding(store, document, task, envelope)
    overrides = (options.get("independent_review_receipts") or [{}])[0]
    claims = {**binding, "executor_ref": "exec-independent", **{key: value for key, value in overrides.items()
                                                                if key not in ("receipt_ref",)}}
    selector = provider.issue("synthetic-" + binding["result_sha256"], claims, "independent_review_receipts")
    return registry.review_context(store, document, task, envelope, selector)


def accept_with_synthetic_provider(project, **kwargs):
    ctx = kwargs.get("adapter_context")
    if isinstance(ctx, review_evidence.TrustedContext) and ctx in _FIXTURES:
        store = Store(project)
        task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                    if store.read_object_json(ref)["task_id"] == kwargs["task_id"])
        registry = _FIXTURES[ctx][0]
        kwargs["adapter_context"] = receipt_context(ctx, store, task, kwargs["result_payload"])
        with review_evidence.ProviderRuntime(registry).bound():
            return service.accept_result(project, **kwargs)
    return service.accept_result(project, **kwargs)


def synthetic_runtime_call(function, *args, **kwargs):
    ctx = kwargs.get("adapter_context")
    if ctx is not None and ctx in _FIXTURES:
        with review_evidence.ProviderRuntime(_FIXTURES[ctx][0]).bound():
            return function(*args, **kwargs)
    return function(*args, **kwargs)


def dispatch_with_synthetic_provider(*args, **kwargs):
    result = synthetic_runtime_call(content_review.dispatch_preproduction_review, *args, **kwargs)
    if result.get("task"):
        from rc3_fixtures import claim_fixture_task
        claim_fixture_task(args[0], result["task"], execution_ref="exec-independent")
    return result


def synthetic_user_context(store, document, *, action_binding, declared, actor_id="u-1"):
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    expected = {"project_id": document["project_id"], "request_id":
                ((document.get("collaboration") or {}).get("request") or {}).get("request_id"),
                "action_binding": action_binding, "source_ref": declared["source_ref"],
                "presentation_ref": declared.get("presentation_ref"), "receipt_ref": declared["transport_receipt_ref"],
                "transport_record_sha256": sha256_bytes(store.read_object_bytes(declared["transport_receipt_ref"])),
                "actor_id": actor_id}
    selector = provider.issue("synthetic-user", expected, "verified_user_events")
    authenticated = provider.verify(provider.events[selector["event_id"]])
    transport = store.read_object_bytes(declared["transport_receipt_ref"])
    provider.events[selector["event_id"]] = transport
    # Synthetic protected-transport double: the controller authenticates this
    # precise original record and supplies its observed metadata separately.
    provider.verify = lambda raw: authenticated if raw == transport else (_ for _ in ()).throw(ValueError("different original"))
    ctx = registry.user_event_context(store, document, action_binding=action_binding,
                                      source_ref=declared["source_ref"], presentation_ref=declared.get("presentation_ref"),
                                      receipt_ref=declared["transport_receipt_ref"], selector=selector)
    _FIXTURES[ctx] = (registry, provider, {})
    return ctx


def accept_original_expression_fixture(project, *, page_id, candidate_id=None):
    """L1 receipt/graph protocol fixture, never actual independent pixel evidence."""
    from deck_master import original_review
    from rc3_fixtures import claim_fixture_task
    context = synthetic_context()
    outcome = synthetic_runtime_call(original_review.dispatch, project, page_id=page_id,
        candidate_id=candidate_id, adapter_context=context)
    task, fixed = outcome['task'], outcome['packet']
    claim_fixture_task(project, task, execution_ref='exec-independent')
    spec = fixed['page']['visual_spec']
    row = {'schema_version': 'deck_review.v2', 'review_id': task['task_id'] + '-expression',
        'kind': 'visual_expression', 'review_stage': 'original_image', 'status': 'pass',
        'subjects': fixed['subjects'], 'dependencies': fixed['dependencies'],
        'reviewer': {'type': 'independent_host', 'id': 'synthetic-independent', 'execution_ref': 'exec-independent',
            'independence_confirmed': True, 'evidence_ref': None, 'identity_receipt': None, 'assurance': 'host_attested'},
        'expression_checks': {'graph': 'pass', 'hierarchy': 'pass', 'reading_path': 'pass',
            'observed_nodes': [node['node_id'] for node in spec.get('nodes') or []],
            'observed_edges': [{key: edge[key] for key in ('edge_id', 'from', 'to', 'direction')} for edge in spec.get('edges') or []]},
        'observations': ['Synthetic protocol fixture; no independent model/pixel inspection occurred.'],
        'findings': [], 'created_at': '2026-10-22T00:00:00Z', 'replaces': None}
    return accept_with_synthetic_provider(project, **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
        result_payload={'kind': 'review', 'pages': [], 'page_order': [], 'artifact_specs': [], 'reviews': [row],
            'usage_events': [], 'notes': 'Synthetic original expression protocol only'}, adapter_context=context)
