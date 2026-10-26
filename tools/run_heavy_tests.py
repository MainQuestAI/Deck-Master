"""Serialize explicitly opted-in local test batches; child commands do not lock.

Usage: python tools/run_heavy_tests.py --record output/run.json -- COMMAND ...
This does not control unrelated processes or change the remote CI matrix.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import tempfile
import time


def source_fingerprint():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).split(b'\0')
    fingerprint = hashlib.sha256()
    for name in sorted(names):
        path = Path(os.fsdecode(name))
        if name and path.is_file():
            fingerprint.update(name + b'\0' + path.read_bytes())
    return fingerprint.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('a command is required')
    if os.environ.get('DECK_MASTER_HEAVY_BATCH'):
        # Explicitly nested wrappers belong to the parent's batch and record.
        return subprocess.call(command)
    lock = Path(tempfile.gettempdir()) / f'deck-master-heavy-tests-{os.getuid()}.lock'
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        fingerprint = source_fingerprint()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        code = subprocess.call(command, env={**os.environ, 'DECK_MASTER_HEAVY_BATCH': str(os.getpid())})
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        finished_fingerprint = source_fingerprint()
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps({
            'head': head, 'worktree_sha256_before': fingerprint,
            'worktree_sha256_after': finished_fingerprint,
            'source_changed_during_run': fingerprint != finished_fingerprint,
            'command': command, 'platform': platform.platform(),
            'wall_seconds': time.monotonic() - started, 'exit_code': code,
            'reaped_children_user_seconds': usage.ru_utime - before.ru_utime,
            'reaped_children_system_seconds': usage.ru_stime - before.ru_stime,
            'scope': 'Only batches using this runner are serialized; CPU excludes detached/unreaped descendants.',
        }, indent=2) + '\n')
        return code


if __name__ == '__main__':
    raise SystemExit(main())
