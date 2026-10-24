"""Run repository tests against the actual wheel, including spawned children.

Use the wheel venv's python -I and set DECK_VERIFY_WHEEL / DECK_VERIFY_OUTPUT.
Pass ordinary pytest arguments. This is review tooling, not a runtime adapter.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
# pytest's source conftest is inherited by multiprocessing spawn. Remove only
# this checkout's src entry before importing the installed package in each child.
sys.path[:] = [p for p in sys.path if Path(p).resolve() != ROOT / 'src']
import deck_master
import deck_master.web
import pytest

PACKAGE = Path(deck_master.__file__).resolve().parent
sys.path.append(str(ROOT))  # Source-only build-hook tests import tools.build_hook.


def fingerprint():
    return {str(p.relative_to(PACKAGE)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PACKAGE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


if __name__ == '__main__':
    assert 'site-packages' in str(PACKAGE), PACKAGE
    assert deck_master.web._static_dir().resolve().is_relative_to(PACKAGE)
    output = Path(os.environ['DECK_VERIFY_OUTPUT'])
    output.parent.mkdir(parents=True, exist_ok=True)
    wheel = Path(os.environ['DECK_VERIFY_WHEEL'])
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    tree = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    checked = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith('deck_master/') and not name.endswith('/'):
                assert archive.read(name) == (PACKAGE.parent / name).read_bytes(), name
                checked.append(name)
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'src/deck_master'], text=True).splitlines()
    for name in tracked:
        expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', sha + ':' + name])
        assert (PACKAGE.parent / Path(name).relative_to('src')).read_bytes() == expected, name
    before = fingerprint()

    class Recorder:
        def pytest_runtest_logreport(self, report):
            if report.failed or report.skipped:
                with output.with_suffix('.events.jsonl').open('a') as stream:
                    stream.write(json.dumps({'nodeid': report.nodeid, 'when': report.when,
                        'outcome': report.outcome, 'duration': report.duration,
                        'longrepr': str(report.longrepr)}, ensure_ascii=False) + '\n')

    result = pytest.main(sys.argv[1:], plugins=[Recorder()])
    modules = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
               if (name == 'deck_master' or name.startswith('deck_master.')) and getattr(module, '__file__', None)}
    identity = {'checkout_sha': sha, 'tree': tree, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'wheel_files': len(checked), 'tracked_runtime_files': len(tracked),
        'version': importlib.metadata.version('deck-master'), 'module': deck_master.__file__, 'modules': modules,
        'all_modules_installed': all(Path(p).is_relative_to(PACKAGE) for p in modules.values()),
        'package_unchanged': before == fingerprint(), 'pytest_exit': int(result)}
    output.with_suffix('.identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    assert identity['all_modules_installed'] and identity['package_unchanged'], identity
    sys.exit(int(result))
