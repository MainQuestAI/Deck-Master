"""Project-scoped immutable material uploads, before explicit input confirmation.

An upload is a recoverable local staging receipt, not a source registration or
Host dispatch. Only content inputs can add the staged bytes to the Document.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import operations
from .local_state import local_lock, project_path, read_json, safe_path, write_json
from .models import sha256_bytes
from .sources import SUPPORTED_EXTENSIONS
from .store import _atomic_write_bytes

MAX_BYTES = 64 * 1024 * 1024


def _directory(project, upload_id):
    if not isinstance(upload_id, str) or not re.fullmatch(r"upload-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", upload_id):
        raise operations.OperationError('material_upload_invalid', 'upload_id', 'use the original material upload UUID', http_status=422)
    return safe_path(project_path(project), '.deckmaster', 'workbench', 'uploads', upload_id)


def _name(name):
    if not isinstance(name, str) or not name or len(name) > 180 or name in ('.', '..') or any(c in name for c in '/\\') or any(ord(c) < 32 for c in name):
        raise operations.OperationError('material_upload_invalid', 'name', 'use a plain material filename', http_status=422)
    if Path(name).suffix.lower().lstrip('.') not in SUPPORTED_EXTENSIONS:
        raise operations.OperationError('material_upload_invalid', 'name', 'unsupported material file type', http_status=422)
    return name


@operations.public
def show(project, *, upload_id):
    directory = _directory(project, upload_id)
    receipt = read_json(safe_path(directory, 'receipt.json'))
    if receipt is None:
        raise operations.OperationError('material_upload_not_found', 'upload_id', 'this material upload has not completed', http_status=404)
    if receipt.get('upload_id') != upload_id or receipt.get('status') != 'uploaded':
        raise operations.OperationError('material_upload_changed', 'receipt', 'upload identity changed', http_status=409)
    path = safe_path(directory, 'file', _name(receipt.get('name')))
    if not path.is_file() or path.stat().st_size != receipt.get('size') or sha256_bytes(path.read_bytes()) != receipt.get('sha256'):
        raise operations.OperationError('material_upload_changed', 'file', 'uploaded material changed; original input was not modified', http_status=409)
    return receipt


@operations.public
def receive(project, *, upload_id, name, data):
    directory = _directory(project, upload_id)
    name = _name(name)
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise operations.OperationError('material_upload_invalid', 'file', 'choose a nonempty file up to 64 MiB', http_status=422)
    receipt = {'status': 'uploaded', 'upload_id': upload_id, 'name': name, 'size': len(data), 'sha256': sha256_bytes(data)}
    with local_lock(safe_path(directory.parent, 'uploads.lock')):
        record_path = safe_path(directory, 'receipt.json')
        previous = read_json(record_path)
        if previous is not None:
            if previous != receipt:
                raise operations.OperationError('material_upload_conflict', 'upload_id', 'this upload ID belongs to different bytes or a different filename', http_status=409)
            return show(project, upload_id=upload_id)
        file_dir = safe_path(directory, 'file')
        file_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(safe_path(file_dir, name), data)
        write_json(record_path, receipt)
    return receipt


def resolve(project, upload_id):
    receipt = show(project, upload_id=upload_id)
    return safe_path(_directory(project, upload_id), 'file', receipt['name'])
