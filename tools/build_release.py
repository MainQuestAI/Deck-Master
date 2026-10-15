"""Build a candidate wheel/sdist and exhaustive canonical resource provenance."""
from pathlib import Path
import argparse
import email
import hashlib
import json
import runpy
import subprocess
import sys
import tarfile
import zipfile


def build_release(output):
    root = Path(__file__).resolve().parents[1]
    hook = runpy.run_path(str(root / 'tools/build_hook.py'))
    inventory = hook['resource_inventory'](root)
    version = hook['source_version'](root)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

    sha = git('rev-parse', 'HEAD')
    dirty = bool(git('status', '--porcelain'))
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                    '-w', str(output), str(root)], check=True)
    subprocess.run([sys.executable, '-c', 'from setuptools.build_meta import build_sdist; '
                    f'build_sdist({str(output)!r})'], cwd=root, check=True)
    wheel = next(output.glob('*.whl'))
    sdist = next(output.glob('*.tar.gz'))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        required = ['deck_master/resources/static/v2/app.js']
        required += ['deck_master/resources/contracts/' + name + '.schema.json'
                     for name in ('document.v1', 'page.v2', 'artifact.v1', 'task.v1', 'review.v1')]
        for name in required:
            if name not in names:
                raise RuntimeError('missing resource: ' + name)
        if any(name.startswith(('runtime/', 'workflow/', 'high_density/', 'preview/', 'build/')) for name in names):
            raise RuntimeError('legacy package in wheel')
        if hook['validate_wheel_inventory'](archive, root=root) != inventory:
            raise RuntimeError('canonical methods changed during candidate build')
        metadata = email.message_from_bytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
        if metadata['Version'] != version:
            raise RuntimeError('wheel version differs from pyproject')
        files = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in sorted(names) if not name.endswith('/')}
    with tarfile.open(sdist) as archive:
        members = archive.getnames()
        prefix = members[0].split('/')[0] + '/'
        if email.message_from_bytes(archive.extractfile(prefix + 'PKG-INFO').read())['Version'] != version:
            raise RuntimeError('sdist version differs from source')
        actual = {name[len(prefix):] for name in members if name.startswith(prefix + 'skills/') and archive.getmember(name).isfile()}
        expected = {row['canonical_source'] for row in inventory['files'].values()}
        if actual != expected:
            raise RuntimeError(f'sdist Skill inventory mismatch: unknown={sorted(actual-expected)}, missing={sorted(expected-actual)}')
        for row in inventory['files'].values():
            member = archive.getmember(prefix + row['canonical_source'])
            if not member.isfile() or hashlib.sha256(archive.extractfile(member).read()).hexdigest() != row['sha256']:
                raise RuntimeError('sdist canonical method mismatch: ' + row['canonical_source'])
    if hook['resource_inventory'](root) != inventory:
        raise RuntimeError('canonical methods changed during candidate build')
    manifest = {
        'release_id': sha[:12] + '-' + hashlib.sha256(wheel.read_bytes()).hexdigest()[:12],
        'source_sha': sha, 'source_dirty': dirty, 'package_version': version,
        'compiler_version': 'python-native-v1', 'wheel': wheel.name,
        'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'sdist': sdist.name, 'sdist_sha256': hashlib.sha256(sdist.read_bytes()).hexdigest(),
        'files': files, 'method_resource_inventory': inventory,
        'entry': ['python', '-m', 'deck_master'], 'professional_evidence': 'not_evaluated',
    }
    (output / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    print(json.dumps(build_release(parser.parse_args().out), indent=2))
