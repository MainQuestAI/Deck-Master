"""Artifact fingerprinting and staleness helpers for the Workflow runtime.

A fingerprint is a stable sha256 over the canonical content of an artifact
(or a set of artifacts). Staleness is propagated by comparing modification
times: a stage is stale when any of its ``staleness_dependencies`` was touched
more recently than its own outputs.

Both computations are deterministic for a given filesystem state, so the
workflow snapshot can be fully rebuilt and yields identical output across
recomputations of the same run (A2 success criterion).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_canonical_hash(path: Path) -> str:
    """sha256 of the canonical (sorted, compact) JSON form, so cosmetic key
    reordering does not change the fingerprint."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # not JSON (or unreadable): fall back to raw bytes hash
        return _file_hash(path)
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def fingerprint_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    if path.suffix == ".json":
        return _json_canonical_hash(path)
    return _file_hash(path)


def fingerprint_set(paths: Iterable[Path]) -> str:
    """Aggregate sha256 over a sorted list of file content hashes.

    Path-independent: only file *contents* participate, so resolving a
    symlinked root (``/tmp`` vs ``/private/tmp`` on macOS) does not change the
    fingerprint. Empty input maps to a stable zero fingerprint so callers can
    always embed a value.
    """
    hashes: list[str] = []
    for p in sorted(set(paths)):
        if p.exists() and not p.is_dir():
            h = fingerprint_file(p)
            if h:
                hashes.append(h)
    blob = json.dumps(sorted(hashes))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def latest_mtime(paths: Iterable[Path]) -> datetime | None:
    """Most recent mtime among existing files in ``paths`` (recurses dirs)."""
    latest: datetime | None = None
    for p in paths:
        if not p.exists():
            continue
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file():
                    latest = _max(latest, _mtime(child))
        else:
            latest = _max(latest, _mtime(p))
    return latest


def earliest_mtime(paths: Iterable[Path]) -> datetime | None:
    """Earliest mtime among existing files (recurses dirs). Empty → None."""
    earliest: datetime | None = None
    seen = False
    for p in paths:
        if not p.exists():
            continue
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file():
                    earliest = _min(earliest, _mtime(child))
                    seen = True
        else:
            earliest = _min(earliest, _mtime(p))
            seen = True
    return earliest if seen else None


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _max(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b


def _min(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a <= b else b
