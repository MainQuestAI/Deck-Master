"""Request-scoped, read-only work_context.v2 transport.

The adapter may pass an observed context identity. Payload cache offers alone
never establish that identity, nor do returned bytes prove model application.
"""
from __future__ import annotations

import copy
import contextvars
import functools
import json
from pathlib import Path

from .errors import TypedServiceError
from .models import sha256_bytes
from .store import StoreError

PROTOCOL = 'work_context.v2'
MODES = ('full', 'delta', 'manifest')
_active = contextvars.ContextVar('work_context_request', default=None)


class ReadProtocolError(TypedServiceError):
    error_code = 'read_protocol_unsupported'

    def payload(self):
        return {'error': {'code': self.error_code, 'field': self.path, 'message': self.detail,
                          'supported_read_protocols': [PROTOCOL],
                          'next_action': 'request a declared read protocol, or omit it for legacy v1'}}


def validate_options(read_protocol=None, body_mode=None, cache_offer=None):
    if read_protocol not in (None, PROTOCOL):
        raise ReadProtocolError('read_protocol', f'unsupported read protocol; supported: {PROTOCOL} (legacy: omit read_protocol)')
    if body_mode is not None and (read_protocol is None or body_mode not in MODES):
        raise TypedServiceError('body_mode', f'{PROTOCOL} supports full, delta, manifest')
    if cache_offer is not None:
        if read_protocol != PROTOCOL or not isinstance(cache_offer, dict):
            raise TypedServiceError('cache_offer', 'an explicit v2 cache offer must be an object')
        if set(cache_offer) - {'session_id', 'context_generation', 'resources'}:
            raise TypedServiceError('cache_offer', 'only exact context and resource identities are accepted')
        if not isinstance(cache_offer.get('resources'), list):
            raise TypedServiceError('cache_offer.resources', 'expected exact resource identities')
        for resource in cache_offer['resources']:
            if (not isinstance(resource, dict) or set(resource) != {'kind', 'sha256'} or
                    resource['kind'] not in ('method', 'source_extract', 'page') or
                    not isinstance(resource['sha256'], str) or len(resource['sha256']) != 64 or
                    any(c not in '0123456789abcdef' for c in resource['sha256'])):
                raise TypedServiceError('cache_offer.resources', 'expected kind and lowercase SHA256')
        for key in ('session_id', 'context_generation'):
            if key not in cache_offer or not isinstance(cache_offer[key], str) or not cache_offer[key]:
                raise TypedServiceError(f'cache_offer.{key}', 'expected a nonempty observed context identity')
    return body_mode or 'full'


class RequestStore:
    """Small immutable reader proxy; the actual JSON decoder is inside the count."""
    def __init__(self, store, collector):
        self._store, self._collector = store, collector
    def __getattr__(self, key):
        return getattr(self._store, key)
    def _key(self, ref):
        return (str(self.project_root.resolve()), ref['path'], ref['sha256'])
    def load_document(self, revision_id=None):
        revision_id = revision_id or self._store.current_revision_id()
        key = (str(self.project_root.resolve()), revision_id)
        if key in self._collector.snapshot_errors:
            raise self._collector.snapshot_errors[key]
        if key not in self._collector.snapshots:
            try:
                self._collector.snapshots[key] = self._store.load_document(revision_id)
            except (StoreError, OSError, ValueError) as exc:
                self._collector.snapshot_errors[key] = exc
                raise
        return copy.deepcopy(self._collector.snapshots[key])
    def read_object_bytes(self, ref):
        key = self._key(ref)
        if key in self._collector.read_errors:
            raise self._collector.read_errors[key]
        if key not in self._collector.object_bytes:
            try:
                self._collector.object_bytes[key] = self._store.read_object_bytes(ref)
            except (StoreError, OSError) as exc:
                self._collector.read_errors[key] = exc
                raise
        return self._collector.object_bytes[key]
    def read_object_json(self, ref):
        key = self._key(ref)
        if key in self._collector.decode_errors:
            raise self._collector.decode_errors[key]
        if key not in self._collector.objects:
            raw = self.read_object_bytes(ref)
            try:
                self._collector.objects[key] = json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeError) as exc:
                error = StoreError(ref['path'], f'object is not valid JSON: {exc}')
                self._collector.decode_errors[key] = error
                raise error from exc
        return copy.deepcopy(self._collector.objects[key])


class ResourceCollector:
    def __init__(self, *, body_mode='full', cache_offer=None, observed_context=None):
        self.body_mode = body_mode
        self.object_bytes, self.objects, self.method_bytes = {}, {}, {}
        self.read_errors, self.decode_errors, self.method_errors, self.snapshot_errors = {}, {}, {}, {}
        self.documents, self.snapshots, self.bodies, self.gaps = {}, {}, {}, []
        self.ready = body_mode != 'manifest'
        self.offered = set()
        if (body_mode == 'delta' and observed_context and cache_offer and
                all(observed_context.get(k) == cache_offer.get(k) for k in ('session_id', 'context_generation'))):
            self.offered = {(r['kind'], r['sha256']) for r in cache_offer['resources']}
    def store(self, store):
        return store if isinstance(store, RequestStore) else RequestStore(store, self)
    def read_method(self, path):
        key = str(Path(path).resolve())
        if key in self.method_errors:
            raise self.method_errors[key]
        if key not in self.method_bytes:
            try:
                self.method_bytes[key] = Path(path).read_bytes()
            except OSError as exc:
                self.method_errors[key] = exc
                raise
        return self.method_bytes[key]
    def add(self, kind, raw, *, retrieval, encoding='utf-8'):
        digest = sha256_bytes(raw)
        ref = f'{kind}:sha256:{digest}'
        if ref not in self.bodies:
            state = ('manifest_only' if self.body_mode == 'manifest' else
                     'omitted_by_cache_offer' if (kind, digest) in self.offered else 'returned')
            body = {'kind': kind, 'sha256': digest, 'byte_length': len(raw), 'encoding': encoding,
                    'state': state, 'retrieval': [retrieval]}
            if state == 'returned':
                body['content'] = raw.decode('utf-8')
            self.bodies[ref] = body
        elif retrieval not in self.bodies[ref]['retrieval']:
            self.bodies[ref]['retrieval'].append(retrieval)
        return ref
    def unavailable(self, kind, identity, retrieval, reason):
        self.ready = False
        ref = f'{kind}:unavailable:{len(self.gaps)}'
        gap = {'kind': kind, 'identity': identity, 'state': 'unavailable', 'reason': str(reason), 'retrieval': [retrieval]}
        self.gaps.append(gap)
        self.bodies[ref] = gap
        return ref
    def methods(self, entries, *, task_id=None):
        result = []
        for entry in entries:
            item = {k: v for k, v in entry.items() if k != 'content'}
            retrieval = {'reader': 'methods', 'task_id': task_id, 'relative_path': entry['relative_path'], 'body_mode': 'full'}
            try:
                raw = self.read_method(entry['path'])
                item['body_ref'] = self.add('method', raw, retrieval=retrieval)
                if sha256_bytes(raw) != entry['sha256']:
                    self.ready = False
            except (OSError, UnicodeError) as exc:
                item['body_ref'] = self.unavailable('method', entry['relative_path'], retrieval, exc)
            result.append(item)
        return result
    def project(self, store, document, summary):
        order = copy.deepcopy(summary)
        order['method_resources'] = self.methods(order.get('method_resources', []), task_id=order['task_id'])
        if order.get('method_basis_status') != 'current':
            self.ready = False
        source_reading = order.pop('source_reading', [])
        projected = []
        readings = {s['source_id']: s for s in source_reading}
        for source in order.get('sources', []):
            entry = {'source_id': source['source_id']}
            ref = source.get('extract')
            retrieval = {'reader': 'content source', 'source_id': source['source_id'],
                         'revision': order.get('dispatch_revision'), 'extract': ref}
            try:
                if not ref or not ref['path'].endswith('.json'):
                    raise StoreError('source.extract', 'no JSON extract for required source')
                raw = store.read_object_bytes(ref)
                extract = store.read_object_json(ref)  # actual decoder is shared and counted
                if not isinstance(extract, dict) or not isinstance(extract.get('text'), str) or not isinstance(extract.get('original_uri'), str):
                    raise StoreError(ref['path'], 'source extract is missing its original identity or full text')
                if extract.get('status') == 'needs_tool':
                    raise StoreError(ref['path'], extract.get('detail') or 'source extraction requires a tool')
                original = extract.get('original_file')
                if original is not None and (not isinstance(original, dict) or not isinstance(original.get('path'), str) or not isinstance(original.get('sha256'), str)):
                    raise StoreError(ref['path'], 'source extract original file identity is invalid')
                entry['body_ref'] = self.add('source_extract', raw, retrieval=retrieval, encoding='json-utf-8')
                reading = readings.get(source['source_id'], {})
                entry.update({k: reading[k] for k in ('extract_path', 'original_path') if k in reading})
            except (StoreError, OSError, ValueError, UnicodeError) as exc:
                entry['body_ref'] = self.unavailable('source_extract', source['source_id'], retrieval, exc)
            projected.append(entry)
        order['source_reading'] = projected
        # Page bodies (including notes and constraints) supplement immutable entries.
        order['page_reading'] = []
        for entry in order.get('page_entries', []):
            ref = entry['page']
            retrieval = {'reader': 'immutable object', 'ref': ref}
            try:
                raw = store.read_object_bytes(ref)
                store.read_object_json(ref)
                body_ref = self.add('page', raw, retrieval=retrieval, encoding='json-utf-8')
            except (StoreError, OSError, ValueError) as exc:
                body_ref = self.unavailable('page', entry['page_id'], retrieval, exc)
            order['page_reading'].append({'page_id': entry['page_id'], 'page_ref': ref, 'body_ref': body_ref})
        return order
    def envelope(self, payload):
        return {**payload, 'schema_version': PROTOCOL, 'body_mode': self.body_mode,
                'bodies': self.bodies, 'context_ready': self.ready,
                'resource_gaps': self.gaps, 'host_application': 'not_recorded',
                'evidence_boundary': 'Returned or cached bytes do not establish reading, application, authorization or independent review'}


def active_collector():
    return _active.get()


def response_projection(function):
    """Validate negotiation before entering create/continue (and any side effect)."""
    @functools.wraps(function)
    def wrapped(*args, read_protocol=None, body_mode=None, cache_offer=None, observed_context=None, **kwargs):
        mode = validate_options(read_protocol, body_mode, cache_offer)
        if read_protocol is None:
            return function(*args, **kwargs)
        collector = ResourceCollector(body_mode=mode, cache_offer=cache_offer, observed_context=observed_context)
        token = _active.set(collector)
        try:
            return collector.envelope(function(*args, **kwargs))
        finally:
            _active.reset(token)
    return wrapped
