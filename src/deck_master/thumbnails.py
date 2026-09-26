"""Bounded local raster derivatives. Original objects and Documents never change.

The cache becomes active when the gallery requests it. Once active, newly
stored raster Artifacts are queued opportunistically; old images are queued
on access. An interrupted warm job is regenerated from immutable bytes on the
next request, without a Host call or a persisted job scheduler.
"""
from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
import heapq
import logging
import os
from pathlib import Path
from queue import Empty, Full, PriorityQueue
import stat
import threading
import time
import warnings

from .local_state import LocalStateError, local_lock, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_ref, validate_schema
from .store import Store, StoreError, _atomic_write_bytes
from .ui_journal import context

VARIANT = 'thumb-480-png-v1'
WORKERS = 2
MAX_QUEUED = 64
MAX_STATUS = 256
MAX_PIXELS = 32_000_000
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_THUMB_BYTES = 2_000_000
RASTER_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}


class ThumbnailError(LocalStateError):
    error_code = 'thumbnail_unavailable'


def _directory(store):
    return safe_path(store.deck_root, 'workbench', 'thumbnails')


def activate(project):
    store, _doc, _identity = context(project)
    directory = _directory(store)
    directory.mkdir(parents=True, exist_ok=True)


def _key(identity, ref, variant=VARIANT):
    return sha256_bytes(canonical_json_bytes({'project_identity': identity, 'hash': ref['sha256'], 'variant': variant}))


def _signature(store, ref):
    validate_ref(ref, where='thumbnail/source')
    path = store._resolve_object_path(ref['path'])
    info = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE_BYTES:
        raise ThumbnailError('source', 'source is not a supported regular raster object')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _paths(store, key):
    if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise ThumbnailError('cache_key', 'invalid thumbnail identity')
    directory = _directory(store)
    return (safe_path(directory, key + '.json'), safe_path(directory, key + '.png'), safe_path(directory, key + '.lock'))


def _cached(store, identity, key, *, ref=None):
    metadata, image, _lock = _paths(store, key)
    record = read_json(metadata)
    if record is None:
        return None
    validate_schema('thumbnail', record)
    required = {'schema_version', 'cache_key', 'project_identity', 'source_ref', 'source_signature', 'variant', 'width', 'height', 'bytes', 'sha256'}
    if (set(record) != required or record['schema_version'] != 'thumbnail.v1' or record['project_identity'] != identity
            or record['variant'] != VARIANT or record['cache_key'] != key or _key(identity, record['source_ref']) != key
            or ref is not None and record['source_ref'] != ref):
        raise ThumbnailError('cache', 'thumbnail identity or project ownership mismatch')
    if record['source_signature'] != _signature(store, record['source_ref']):
        return None  # Changed source must pass its original hash again in the worker.
    descriptor = os.open(image, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ThumbnailError('cache', 'thumbnail must be a regular file')
        data = stream.read(MAX_THUMB_BYTES + 1)
    if len(data) > MAX_THUMB_BYTES or len(data) != record['bytes'] or sha256_bytes(data) != record['sha256']:
        raise ThumbnailError('cache', 'thumbnail byte hash mismatch')
    return record, data


def _generate(project, ref, identity, key):
    from PIL import Image, ImageOps
    store = Store(project)
    metadata, output, lock = _paths(store, key)
    with local_lock(lock):
        try:
            hit = _cached(store, identity, key, ref=ref)
        except (LocalStateError, OSError, ValueError):
            hit = None  # Explicit retry repairs derivatives only, never originals.
        if hit is not None:
            return hit[0]
        before = _signature(store, ref)
        raw = store.read_object_bytes(ref)
        if before != _signature(store, ref):
            raise ThumbnailError('source', 'source changed during checksum validation')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                if original.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ThumbnailError('source', 'only PNG, JPEG and WebP raster derivatives are supported')
                if original.width * original.height > MAX_PIXELS:
                    raise ThumbnailError('source', 'image exceeds the supported derivative pixel limit')
                # EXIF orientation is visual content; embedded metadata is not copied.
                image = ImageOps.exif_transpose(original).convert('RGBA')
                image.thumbnail((480, 480), Image.Resampling.LANCZOS)
                encoded = BytesIO(); image.save(encoded, format='PNG')
                data = encoded.getvalue(); width, height = image.size
        if len(data) > MAX_THUMB_BYTES:
            raise ThumbnailError('cache', 'derived image exceeds the cache size limit')
        record = {'schema_version': 'thumbnail.v1', 'cache_key': key, 'project_identity': identity,
                  'source_ref': ref, 'source_signature': before, 'variant': VARIANT,
                  'width': width, 'height': height, 'bytes': len(data), 'sha256': sha256_bytes(data)}
        # Publish only after bytes are durable. No half-generated derivative is ready.
        _atomic_write_bytes(output, data)
        write_json(metadata, record)
        return record


class ThumbnailQueue:
    """Two daemon workers, bounded pending/status memory, no source byte retention."""
    def __init__(self):
        self.queue = PriorityQueue(maxsize=MAX_QUEUED)
        self.lock = threading.Lock()
        self.jobs = OrderedDict()
        self.threads = []
        self.counter = 0
        self.running = 0
        self.peak_running = 0
        self.peak_queued = 0
        self.completed = 0
        self.failed = 0
        self.stopping = threading.Event()

    def submit(self, project, ref, identity, *, priority=0):
        key = _key(identity, ref)
        job_id = (str(project), key)
        with self.lock:
            previous = self.jobs.get(job_id)
            if previous and previous['status'] in ('queued', 'running'):
                if priority == 0 and previous['status'] == 'queued':
                    with self.queue.mutex:
                        for index, item in enumerate(self.queue.queue):
                            if item[2] == job_id and item[0] > priority:
                                self.queue.queue[index] = (priority, *item[1:])
                                heapq.heapify(self.queue.queue)
                                break
                return {**previous, 'cache_key': key}
            if self.queue.full():
                return {'status': 'busy', 'cache_key': key, 'retry_after_ms': 150}
            self.counter += 1
            record = {'status': 'queued', 'cache_key': key}
            self.jobs[job_id] = record
            self.jobs.move_to_end(job_id)
            self._trim()
            try:
                self.queue.put_nowait((priority, self.counter, job_id, ref, identity))
            except Full:
                self.jobs.pop(job_id, None)
                return {'status': 'busy', 'cache_key': key, 'retry_after_ms': 150}
            self.peak_queued = max(self.peak_queued, self.queue.qsize())
            if not self.threads:
                for _ in range(WORKERS):
                    thread = threading.Thread(target=self._work, daemon=True, name='deck-thumbnail')
                    self.threads.append(thread); thread.start()
            return {**record, 'retry_after_ms': 75}

    def _trim(self):
        while len(self.jobs) > MAX_STATUS:
            victim = next((key for key, value in self.jobs.items() if value['status'] not in ('queued', 'running')), None)
            if victim is None: break
            del self.jobs[victim]

    def _work(self):
        while not self.stopping.is_set():
            try:
                _priority, _count, job_id, ref, identity = self.queue.get(timeout=.1)
            except Empty:
                continue
            with self.lock:
                self.running += 1
                self.peak_running = max(self.peak_running, self.running)
                self.jobs[job_id] = {'status': 'running', 'cache_key': job_id[1]}
            try:
                _generate(job_id[0], ref, identity, job_id[1])
                result = {'status': 'ready', 'cache_key': job_id[1]}
            except Exception as error:
                # Keep a concrete, bounded diagnostic instead of failing adoption.
                reason = error.detail if isinstance(error, (ThumbnailError, StoreError)) else 'source or derivative cache could not be read or written'
                result = {'status': 'failed', 'cache_key': job_id[1], 'error': {'code': 'thumbnail_unavailable', 'message': reason}}
            finally:
                with self.lock:
                    self.running -= 1
                    self.jobs[job_id] = result
                    self.jobs.move_to_end(job_id)
                    self.completed += result['status'] == 'ready'
                    self.failed += result['status'] == 'failed'
                    self._trim()
                self.queue.task_done()

    def status(self, project, key):
        with self.lock:
            value = self.jobs.get((str(project), key))
            return dict(value) if value else None

    def metrics(self):
        with self.lock:
            return {'workers_limit': WORKERS, 'queued_limit': MAX_QUEUED, 'status_limit': MAX_STATUS,
                    'running': self.running, 'queued': self.queue.qsize(), 'retained_statuses': len(self.jobs),
                    'peak_running': self.peak_running, 'peak_queued': self.peak_queued,
                    'completed': self.completed, 'failed': self.failed}

    def close(self):
        try:
            self.drain()
        finally:
            self.stopping.set()
            for thread in self.threads: thread.join(timeout=1)

    def drain(self, timeout=10):
        until = time.monotonic() + timeout
        while self.queue.unfinished_tasks:
            if time.monotonic() >= until: raise TimeoutError('thumbnail queue did not drain')
            time.sleep(.01)


QUEUE = ThumbnailQueue()


def request(project, *, ref, variant=VARIANT, retry=False):
    if variant != VARIANT:
        raise ThumbnailError('variant', 'unsupported thumbnail variant')
    store, _doc, identity = context(project)
    _signature(store, ref)  # Reject foreign/missing/path-invalid sources before queueing.
    key = _key(identity, ref, variant)
    if Path(ref['path']).suffix not in RASTER_EXTENSIONS:
        return {'status': 'unsupported', 'cache_key': key, 'variant': variant, 'reason': 'use a recorded raster preview for this layer'}
    _directory(store).mkdir(parents=True, exist_ok=True)
    try:
        cached = _cached(store, identity, key, ref=ref)
    except (LocalStateError, OSError, ValueError):
        if not retry:
            return {'status': 'failed', 'cache_key': key, 'error': {'code': 'thumbnail_unavailable', 'message': 'derivative cache is unreadable; retry can rebuild it from the verified original'}}
        cached = None
    if cached:
        record = {k: v for k, v in cached[0].items() if k != 'source_signature'}
        return {'status': 'ready', 'cache': 'hit', **record, 'url': '/api/thumbnail-file?cache_key=' + key}
    previous = QUEUE.status(store.project_root, key)
    if previous and previous['status'] == 'failed' and not retry:
        return previous
    return {**QUEUE.submit(store.project_root, ref, identity), 'cache': 'miss', 'variant': variant}


def file_bytes(project, key):
    store, _doc, identity = context(project)
    hit = _cached(store, identity, key)
    if hit is None:
        raise ThumbnailError('cache_key', 'thumbnail is not ready or its source changed')
    return hit[1], 'image/png'


def warm_artifact(store, artifact):
    """Best-effort only after gallery activation; never affects artifact adoption."""
    ref = artifact.get('file')
    if not ref or Path(ref['path']).suffix not in RASTER_EXTENSIONS:
        return {'status': 'unsupported'}
    try:
        if not _directory(store).is_dir(): return {'status': 'inactive'}
        _store, _doc, identity = context(store.project_root)
        return QUEUE.submit(store.project_root, ref, identity, priority=10)
    except Exception as error:
        logging.getLogger(__name__).warning('thumbnail warm deferred (%s); original adoption is unaffected', type(error).__name__)
        # Reading this cache later returns the concrete path/ownership diagnostic.
        # A derivative-cache failure cannot roll back already stored original bytes.
        return {'status': 'deferred', 'reason': 'thumbnail cache not available; request on access'}
