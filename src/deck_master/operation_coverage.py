"""Disposable, bounded in-process ancestry metadata for the I01 resolver.

No receipt/result or disk hint is trusted here. Entries originate exclusively
from snapshots.snapshot_evidence and expire on any canonical signature change.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import os
from threading import RLock

from . import snapshots
from .models import validate_schema

MAX_PROJECTS = 8
MAX_REVISIONS = 4096


@dataclass(frozen=True, slots=True)
class Header:
    revision: str
    project_id: str
    parent: str | None
    operation_id: str | None
    signature: tuple | None
    sha256: str


@dataclass(frozen=True, slots=True)
class Coverage:
    root: tuple
    head: str
    project_id: str
    headers: dict[str, Header]
    operations: dict[str, str]
    complete: bool = True


_cache = OrderedDict()
_lock = RLock()
_pid = os.getpid()


def clear():
    """Drop all trust; the next query establishes canonical coverage again."""
    with _lock:
        _cache.clear()


def root_identity(store):
    # Actual directories distinguish copied/same-name projects and replacement.
    paths = (store.project_root, store.deck_root, store.revisions_dir)
    if any(path.is_symlink() for path in paths[1:]):
        raise ValueError('unsafe project root')
    identities = []
    for path in paths:
        info = path.stat()
        identities.append((str(path.resolve()), info.st_dev, info.st_ino))
    return tuple(identities)


def current_head(store):
    if store.deck_root.is_symlink() or (store.deck_root / 'current.json').is_symlink():
        raise ValueError('unsafe current pointer')
    head = store.current_revision_id()
    if not isinstance(head, str) or not snapshots.IDENTIFIER.fullmatch(head):
        raise ValueError('missing current pointer')
    return head


def get(root):
    global _pid
    with _lock:
        # forked children are cold processes, too.
        if _pid != os.getpid():
            _cache.clear()
            _pid = os.getpid()
        result = _cache.get(root)
        if result is not None:
            _cache.move_to_end(root)
        return result


def discard(root):
    with _lock:
        _cache.pop(root, None)


def publish(coverage):
    """Retain bounded metadata from successful complete canonical scans."""
    if MAX_REVISIONS <= 0 or any(h.signature is None for h in coverage.headers.values()):
        return
    if len(coverage.headers) > MAX_REVISIONS:
        # Retain bounded canonical headers, never a claim of complete ancestry.
        # A later scan still walks through the uncached tail before deciding.
        headers = {}
        revision = coverage.head
        while revision is not None and len(headers) < MAX_REVISIONS:
            header = coverage.headers[revision]
            headers[revision] = header
            revision = header.parent
        coverage = Coverage(coverage.root, coverage.head, coverage.project_id, headers,
            {h.operation_id: h.revision for h in headers.values() if h.operation_id is not None}, complete=False)
    with _lock:
        _cache[coverage.root] = coverage
        _cache.move_to_end(coverage.root)
        while (len(_cache) > MAX_PROJECTS
               or sum(len(c.headers) for c in _cache.values()) > MAX_REVISIONS):
            _cache.popitem(last=False)  # Evict whole entries; partial metadata proves no absence.


def valid(store, coverage):
    return all(header.signature is not None
               and snapshots.snapshot_signature(store, revision) == header.signature
               for revision, header in coverage.headers.items())


def scan(store, *, root, control, operation_id, head_revision=None, cached=None):
    """Collect ancestry metadata, never decide operation truth or decode receipts.

    The returned Document was read from canonical bytes during this scan, or is
    reread once at a verified cached location. All snapshots through the root
    are covered, including non-operation revisions and the control prefix for
    an explicit historical head.
    """
    if cached is not None and control in cached.headers and control != cached.head:
        cached = None
    complete = cached is not None and cached.complete
    hints = cached.headers if cached is not None else {}
    headers = dict(cached.headers) if complete else {}
    ops = dict(cached.operations) if complete else {}
    new_documents = {}
    duplicate = False
    revision = control
    visited = set()
    project_id = cached.project_id if complete else None
    while revision not in headers:
        if revision in visited:
            raise ValueError('ancestry cycle')
        visited.add(revision)
        doc = None
        header = hints.get(revision)
        if header is None:
            doc, signature, digest = snapshots.snapshot_evidence(store, revision)
            validate_schema('document', doc)
            change = doc.get('change') or {}
            if not isinstance(change, dict):
                raise ValueError('invalid change')
            op = change.get('operation_id')
            if op is not None and not isinstance(op, str):
                raise ValueError('invalid operation ID')
            identity = project_id if doc['project_id'] == project_id else doc['project_id']
            header = Header(revision, identity, doc['parent_revision_id'], op, signature, digest)
        if project_id is None:
            project_id = header.project_id
        if header.project_id != project_id:
            if cached is not None:
                return scan(store, root=root, control=control, operation_id=operation_id,
                            head_revision=head_revision)
            raise ValueError('foreign ancestry')
        op = header.operation_id
        if op is not None:
            if op in ops:
                duplicate = True
            ops[op] = revision
        headers[revision] = header
        # Keep at most the query match; no full Documents survive in the cache.
        if op == operation_id and doc is not None:
            new_documents[revision] = doc
        revision = header.parent
        if revision is None:
            if complete:
                return scan(store, root=root, control=control, operation_id=operation_id,
                            head_revision=head_revision)
            break
    else:
        # New ancestry must connect to a complete cached head, not an arbitrary
        # old node (e.g. a restore/fork). Fall back to a fresh canonical scan.
        if not complete:
            raise ValueError('ancestry cycle')
        if visited and revision != cached.head:
            return scan(store, root=root, control=control, operation_id=operation_id,
                        head_revision=head_revision)
    if duplicate:
        raise ValueError('duplicate operation ID')
    coverage = Coverage(root, control, project_id, headers, ops)
    requested_head = head_revision if head_revision is not None else control
    # Locate the explicit head only within the captured control ancestry. Walk
    # headers without re-decoding the canonical prefix or selected ancestors.
    revision = control
    allowed = set()
    reached = False
    while revision is not None:
        if revision in allowed:
            raise ValueError('ancestry cycle')
        allowed.add(revision)
        if revision == requested_head:
            reached = True
            break
        revision = headers[revision].parent
    if not reached:
        raise ValueError('head is not committed')
    match = ops.get(operation_id)
    if match is not None and requested_head != control:
        revision = requested_head
        while revision is not None and revision != match:
            revision = headers[revision].parent
        if revision is None:
            match = None
    document = new_documents.get(match)
    if match is not None and document is None:
        document, signature, digest = snapshots.snapshot_evidence(store, match)
        header = headers[match]
        if signature != header.signature or digest != header.sha256:
            raise ValueError('matched snapshot changed')
    return coverage, requested_head, document
