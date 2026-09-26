"""Small local files: explicit paths, core atomic writes, separate file locks.

These files are UI recovery/discovery data, never Document or operation truth.
"""
from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from .errors import TypedServiceError
from .models import canonical_json_bytes
from .store import _atomic_write_bytes, locked_file

MAX_BODY = 2_000_000


class LocalStateError(TypedServiceError):
    error_code = "local_state_invalid"


class LocalStateConflict(LocalStateError):
    error_code = "local_state_conflict"
    exit_code = 5


def absolute_path(value, *, field="path"):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise LocalStateError(field, "provide an absolute local path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LocalStateError(field, "provide an absolute local path")
    return path


def safe_path(root, *parts):
    """Only literal child names; never resolve away a symlink inside the root."""
    path = Path(root)
    if path.is_symlink():
        raise LocalStateError("path", "symlinked local state is not supported")
    for part in parts:
        if not isinstance(part, str) or not part or part in (".", "..") or "/" in part or "\\" in part:
            raise LocalStateError("path", "invalid local state name")
        path = path / part
        if path.is_symlink():
            raise LocalStateError("path", "symlinked local state is not supported")
    return path


def read_json(path, *, default=None, max_bytes=MAX_BODY):
    safe_path(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise LocalStateError("local_state", "local state must be a regular file")
            raw = stream.read(max_bytes + 1)
    except FileNotFoundError:
        return default
    if len(raw) > max_bytes:
        raise LocalStateError("local_state", "file exceeds the supported size")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (ValueError, UnicodeError) as exc:
        raise LocalStateError("local_state", "local state is not valid JSON; keep it for recovery") from exc


def write_json(path, value):
    raw = canonical_json_bytes(value)
    if len(raw) > MAX_BODY:
        raise LocalStateError("local_state", "file exceeds the supported size")
    safe_path(path)
    _atomic_write_bytes(path, raw)


@contextmanager
def local_lock(path):
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_file(path):
        yield


def project_path(value):
    from .legacy import looks_like_legacy_run
    from .snapshots import load_snapshot
    from .store import Store

    path = absolute_path(value, field="project").resolve()
    if looks_like_legacy_run(path):
        error = LocalStateError("project", "old run format requires a separate documented import")
        error.error_code = "legacy_run_format"
        raise error
    if not path.is_dir():
        raise LocalStateError("project", "project directory does not exist")
    load_snapshot(Store(path))  # Validate before creating any local state.
    return path
