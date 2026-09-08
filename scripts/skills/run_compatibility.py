"""Stable installed-launcher guard; survives activation of an older release.

Only standard-library imports: the active release may predate this module.
This guards the managed entrypoint, not direct execution of historical source.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

SUPPORTED_RUN_FORMATS = ['deck_build_route.v1', 'deck_build_revision.v1', 'deck_build_revision.v2']


def _json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'expected JSON object: {path.name}')
    return value


def _option(argv: list[str], name: str) -> str:
    value = ''
    for index, argument in enumerate(argv):
        if argument.startswith(name + '='):
            value = argument[len(name) + 1:]
        elif argument == name and index + 1 < len(argv):
            value = argv[index + 1]
    return value


def _run_root(release: Path, argv: list[str]) -> Path | None:
    directory = _option(argv, '--run-dir')
    if directory:
        return Path(directory).expanduser().resolve()
    run_id = _option(argv, '--run-id')
    if not run_id:
        return None
    directory = _option(argv, '--runs-dir')
    if not directory:
        # Matches the CLI's configured_runs_dir, without importing old code.
        directory = str(_json(Path.home() / '.deck-master/config.json').get('default_runs_dir') or release / 'runs')
    return (Path(directory).expanduser() / run_id).resolve()


def required_formats(root: Path) -> tuple[set[str], dict]:
    formats: set[str] = set()
    request = _json(root / 'request.json')
    route = _json(root / 'build/route.json')
    if request.get('profile') == 'native' or request.get('builder_profile') == 'native' or route.get('engine_id') == 'deck_native':
        formats.add(str(route.get('schema_version') or 'deck_build_route.v1'))
    pointer = _json(root / 'build/current_revision.json')
    revision = pointer.get('revision_id')
    if revision:
        if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', revision):
            raise ValueError('invalid current revision identifier')
        manifest = _json(root / 'build/revisions' / revision / 'revision_manifest.json')
        if not manifest.get('schema_version'):
            raise ValueError('current revision manifest is missing its format')
        formats.add(str(manifest['schema_version']))
    return formats, pointer


def _status_command(argv: list[str]) -> bool:
    # Skip only documented global options; unknown forms fail closed.
    index = 0
    while index < len(argv) and argv[index].startswith('--'):
        option = argv[index].split('=', 1)[0]
        if option in {'--runs-dir', '--workspace'}:
            index += 1 if '=' in argv[index] else 2
        elif option == '--dev-allow-unsetup':
            index += 1
        else:
            return False
    return argv[index:index + 2] in [['build', 'status'], ['workflow', 'status']]


def check(release: Path, argv: list[str]) -> tuple[dict | None, int]:
    root = _run_root(release, argv)
    if root is None or '--help' in argv or '-h' in argv:
        return None, 0
    formats, pointer = required_formats(root)
    manifest = _json(release / 'release-manifest.json')
    declared = manifest.get('supported_run_formats', ['deck_build_revision.v1'])
    if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
        raise ValueError('release supported_run_formats must be a list of strings')
    unsupported = sorted(formats - set(declared))
    if not unsupported:
        return None, 0
    readonly_status = _status_command(argv)
    return {
        'schema_version': 'deck_master_run_compatibility.v1',
        'status': 'legacy_read_only' if readonly_status else 'blocked',
        'code': 'RUN_FORMAT_READ_ONLY',
        'read_only': True,
        'unsupported_run_formats': unsupported,
        'supported_run_formats': declared,
        'revision_id': pointer.get('revision_id', ''),
        'message': 'The active release does not declare support for this Run format. Data is preserved; upgrade the software to continue. This is compatibility status, not build readiness.',
    }, 0 if readonly_status else 2


def main() -> None:
    release = Path(sys.argv[1]).resolve()
    argv = sys.argv[2:]
    try:
        payload, exit_code = check(release, argv)
    except (OSError, ValueError) as exc:
        payload, exit_code = {'status': 'blocked', 'code': 'RUN_FORMAT_UNREADABLE', 'read_only': True, 'message': str(exc)}, 2
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(exit_code)
    os.execv(sys.executable, [sys.executable, str(release / 'scripts/deck_master.py'), *argv])


if __name__ == '__main__':
    main()
