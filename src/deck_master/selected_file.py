"""Bounded reads of an explicitly selected local file, never a web path."""
import hashlib
import os
from pathlib import Path
import stat

from .models import ModelError
from .store import ConflictError


class SelectedFileError(ModelError):
    http_status = 400
    exit_code = 2

    def __init__(self, code, message):
        self.error_code = code
        super().__init__('file_path', message)


def read_selected_file(path, *, sizes):
    """Read one stable regular inode, bounded by the expected output lengths."""
    path = Path(path).expanduser().absolute()
    allowed = set(sizes)
    if not allowed:
        raise SelectedFileError('selected_output_missing', 'no output to compare')
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SelectedFileError('selected_file_type', 'expected a regular non-symlink file')
        if before.st_size not in allowed:
            raise ConflictError('file_path', 'candidate_not_selected_output: unexpected file size')
        chunks, remaining = [], before.st_size
        digest = hashlib.sha256()
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise ConflictError('file_path', 'selected_file_changed: file was truncated')
            chunks.append(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise ConflictError('file_path', 'selected_file_changed: file grew during reading')
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if signature(before) != signature(os.fstat(fd)) or signature(before) != signature(path.lstat()):
            raise ConflictError('file_path', 'selected_file_changed: file changed during reading')
        data = b''.join(chunks)
        return data, digest.hexdigest()
    except OSError as exc:
        raise SelectedFileError('selected_file_unreadable', 'cannot read the selected regular file') from exc
    finally:
        if fd is not None:
            os.close(fd)
