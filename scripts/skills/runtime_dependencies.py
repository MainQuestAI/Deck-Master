"""Release-only exact wheel installation. Never resolve build dependencies online.

Refresh requirements/{runtime,build}.lock intentionally: choose compatible exact
versions, obtain non-yanked bdist_wheel SHA256 from the official PyPI version JSON,
then rerun clean 3.11/3.12 installations and compiler/render regression. All wheel
hashes are allowed; this is not a claim that every wheel platform was tested.
The runtime receipt records the platform distribution actually selected.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
from email.parser import BytesParser

LOCK_PATHS = ('requirements/build.lock', 'requirements/runtime.lock')

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()

def read_lock(path: Path) -> dict:
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split()
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', parts[0])
        if not match or len(parts) < 2 or any(not re.fullmatch(r'--hash=sha256:[a-f0-9]{64}', x) for x in parts[1:]):
            raise ValueError(f'Unpinned or invalid dependency in {path.name}')
        name = normalized(match[1])
        if name in result:
            raise ValueError(f'Duplicate dependency: {name}')
        result[name] = {'version': match[2], 'hashes': [x.split(':')[1] for x in parts[1:]]}
    if not result:
        raise ValueError(f'Empty dependency lock: {path.name}')
    return result

def verify_lock_files(root: Path) -> dict:
    declared = {}
    for line in (root/'SHA256SUMS').read_text().splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            declared[parts[1].strip()] = parts[0]
    result = {}
    for relative in LOCK_PATHS:
        path = root/relative
        if path.is_symlink() or not path.is_file() or declared.get(relative) != digest(path):
            raise ValueError(f'Dependency lock checksum mismatch: {relative}')
        result.update(read_lock(path))
    return result

def verify_wheels(folder: Path, packages: dict) -> list:
    records = []
    seen = set()
    for path in sorted(folder.iterdir()):
        if path.suffix != '.whl' or path.is_symlink():
            raise ValueError('Only regular wheel files are accepted')
        with zipfile.ZipFile(path) as wheel:
            metadata = [n for n in wheel.namelist() if n.endswith('.dist-info/METADATA') and n.count('/') == 1]
            if len(metadata) != 1:
                raise ValueError('Invalid wheel metadata')
            info = BytesParser().parsebytes(wheel.read(metadata[0]))
        name = normalized(info['Name'])
        sha = digest(path)
        if name not in packages or name in seen or info['Version'] != packages[name]['version'] or sha not in packages[name]['hashes']:
            raise ValueError(f'Wheel differs from dependency lock: {path.name}')
        seen.add(name)
        records.append({'name': name, 'version': info['Version'], 'filename': path.name, 'sha256': sha})
    if seen != set(packages):
        raise ValueError('Wheel set does not cover complete dependency lock')
    return records

def install_locked_runtime(root: Path, python: Path) -> dict:
    packages = verify_lock_files(root)  # Before any package execution/network.
    env = {k:v for k,v in os.environ.items() if not k.startswith('PIP_') and k not in ('PYTHONPATH', 'PYTHONHOME')}
    env.update(PYTHONNOUSERSITE='1', PIP_CONFIG_FILE=os.devnull, SOURCE_DATE_EPOCH='1704067200')
    commands = []
    def run(args):
        command = [str(python), '-m', 'pip', '--isolated', '--disable-pip-version-check', *args]
        commands.append(command)
        completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, timeout=300)
        if completed.returncode:
            raise ValueError('Locked dependency installation failed: ' + completed.stdout[-3000:] + completed.stderr[-3000:])
    with tempfile.TemporaryDirectory(prefix='deck-locked-wheels-') as temporary:
        wheels = Path(temporary)/'dependencies'; wheels.mkdir()
        flags = ['--require-hashes', '--only-binary=:all:', '-r', str(root/LOCK_PATHS[0]), '-r', str(root/LOCK_PATHS[1])]
        run(['download', '--index-url', 'https://pypi.org/simple', '--no-cache-dir', '--dest', str(wheels), *flags])
        records = verify_wheels(wheels, packages)
        run(['install', '--no-index', '--find-links', str(wheels), *flags])
        own = Path(temporary)/'project'; own.mkdir()
        run(['wheel', '--no-index', '--no-deps', '--no-build-isolation', '--wheel-dir', str(own), str(root)])
        built = list(own.glob('*.whl'))
        if len(built) != 1:
            raise ValueError('Expected exactly one locally built Deck Master wheel')
        own_digest = digest(built[0])
        run(['install', '--no-index', '--no-deps', str(built[0])])
        run(['check'])
        query = subprocess.run([str(python), '-c', 'import importlib.metadata as m,json; print(json.dumps({d.metadata["Name"]:d.version for d in m.distributions()}))'], env=env, capture_output=True, text=True, check=True)
        installed = {normalized(k): v for k,v in json.loads(query.stdout).items()}
        if set(installed) != set(packages) | {'deck-master'} or any(installed.get(k) != v['version'] for k,v in packages.items()):
            raise ValueError('Installed distributions differ from dependency lock')
        receipt = {'schema_version': 'deck_dependency_install.v1', 'locks': {p:digest(root/p) for p in LOCK_PATHS}, 'distributions': records, 'project_wheel_sha256': own_digest, 'installed_versions': installed}
        (root/'.venv/dependency-install.json').write_text(json.dumps(receipt, indent=2)+'\n')
        return receipt
