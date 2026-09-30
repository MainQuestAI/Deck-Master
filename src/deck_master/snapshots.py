"""Safe committed snapshot traversal shared by projections and recovery."""
from __future__ import annotations

import json
from functools import lru_cache
import re

from .models import validate_ref
from .store import StoreError

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
SLOTS = ("page", "blueprint", "svg", "svg_preview", "ppt_preview")
READ_FAILURES = (StoreError, OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError)


class ReadModelError(StoreError):
    """Public read error with no filesystem paths or raw parser diagnostics."""

    exit_code = 2

    def __init__(self, code, field, message, *, http_status=404):
        super().__init__(field, message)
        self.error_code = code
        self.http_status = http_status

    def payload(self):
        return {"status": "error", "error": {
            "code": self.error_code, "message": self.detail, "field": self.path,
            "next_action": "read available project history and select a valid snapshot",
            "docs_ref": "docs/agent-recovery-playbook.md#workbench-snapshot-reads",
        }}


def _snapshot(store, revision):
    if not isinstance(revision, str) or not IDENTIFIER.fullmatch(revision):
        raise ReadModelError("invalid_revision", "revision", "invalid revision identifier", http_status=400)
    path = store.revisions_dir / (revision + ".json")
    # Check components before resolving: resolving first would hide symlinks.
    if any(p.is_symlink() for p in (store.deck_root, store.revisions_dir, path)):
        raise ReadModelError("revision_unavailable", "revision", "snapshot is not available in this project")
    try:
        if path.resolve().parent != store.revisions_dir.resolve():
            raise ValueError("outside revision directory")
        doc = json.loads(path.read_bytes())
        if (not isinstance(doc, dict) or doc.get("revision_id") != revision
                or doc.get("schema_version") != "deck_document.v1"
                or not isinstance(doc.get("project_id"), str)
                or not isinstance(doc.get("pages"), list)
                or not isinstance(doc.get("outputs"), dict)
                or any(not isinstance(doc.get(k), list) for k in ("tasks", "reviews"))
                or any(not isinstance(p, dict) or not isinstance(p.get("page_id"), str) for p in doc["pages"])
                or (doc.get("parent_revision_id") is not None
                    and not isinstance(doc["parent_revision_id"], str))):
            raise ValueError("invalid snapshot identity")
        refs = [p.get(slot) for p in doc["pages"] for slot in SLOTS]
        refs += doc["tasks"] + doc["reviews"] + list(doc["outputs"].values())
        for ref in refs:
            if ref is not None:
                # A corrupt Document must not echo an absolute or foreign path
                # as a public slot/ref before object-level error handling runs.
                validate_ref(ref, where="snapshot/ref")
        return doc
    except (OSError, ValueError, RuntimeError) as exc:
        raise ReadModelError("revision_unavailable", "revision", "snapshot is not readable in this project") from exc


def committed_snapshots(store):
    """Capture current once and walk only its same-project committed ancestry."""
    try:
        if store.deck_root.is_symlink() or (store.deck_root / "current.json").is_symlink():
            raise ValueError("symlinked pointer")
        current = store.current_revision_id()
        if current is None:
            raise ValueError("no current revision")
    except READ_FAILURES as exc:
        raise ReadModelError("project_unavailable", "project", "project snapshot is not readable") from exc
    doc = _snapshot(store, current)
    project_id = doc["project_id"]
    yield doc
    visited = {current}
    while doc.get("parent_revision_id"):
        parent = doc["parent_revision_id"]
        if parent in visited:
            break
        visited.add(parent)
        doc = _snapshot(store, parent)
        if doc["project_id"] != project_id:
            break
        yield doc


@lru_cache(maxsize=4096)
def _cached_header(project, revision, signature):
    # Retain only ancestry metadata, never a large mutable Document. Signature
    # includes inode and nanosecond times so replacement/corruption invalidates it.
    from .store import Store
    doc = _snapshot(Store(project), revision)
    return doc["project_id"], doc.get("parent_revision_id")


def _header(store, revision):
    if not isinstance(revision, str) or not IDENTIFIER.fullmatch(revision):
        raise ReadModelError("invalid_revision", "revision", "invalid revision identifier", http_status=400)
    path = store.revisions_dir / (revision + ".json")
    if any(p.is_symlink() for p in (store.deck_root, store.revisions_dir, path)):
        raise ReadModelError("revision_unavailable", "revision", "snapshot is not available in this project")
    try:
        stat = path.stat()
        signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        return _cached_header(str(store.project_root), revision, signature)
    except OSError as exc:
        raise ReadModelError("revision_unavailable", "revision", "snapshot is not readable in this project") from exc


def committed_headers(store, *, head=None):
    """Walk verified ancestry without reparsing every immutable large snapshot."""
    if store.deck_root.is_symlink() or (store.deck_root / "current.json").is_symlink():
        raise ReadModelError("project_unavailable", "project", "project snapshot is not readable")
    revision = head or store.current_revision_id()
    if revision is None:
        raise ReadModelError("project_unavailable", "project", "project snapshot is not readable")
    project_id = None; visited = set()
    while revision and revision not in visited:
        visited.add(revision)
        identity, parent = _header(store, revision)
        project_id = identity if project_id is None else project_id
        if identity != project_id:
            break
        yield revision, identity, parent
        revision = parent


def load_snapshot(store, revision=None):
    """Read one committed snapshot; copied/orphan files never become history."""
    if revision is None:
        return next(committed_snapshots(store))
    if not isinstance(revision, str) or not IDENTIFIER.fullmatch(revision):
        raise ReadModelError("invalid_revision", "revision", "invalid revision identifier", http_status=400)
    for current, identity, _ in committed_headers(store):
        if current == revision:
            document = _snapshot(store, current)
            if document["project_id"] != identity:
                raise ReadModelError("revision_unavailable", "revision", "snapshot identity changed while reading")
            return document
    raise ReadModelError("revision_not_found", "revision", "revision is not committed in this project")
