import hashlib
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.skills.runtime_dependencies import verify_lock_files, read_lock


class DependencyLockTest(unittest.TestCase):
    def test_lock_tamper_is_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'requirements').mkdir()
            for name in ('build', 'runtime'):
                p = root / f'requirements/{name}.lock'
                p.write_text('demo==1.0 --hash=sha256:' + 'a'*64 + '\n')
            (root / 'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root)) for p in (root/'requirements').glob('*')))
            verify_lock_files(root)
            (root/'requirements/runtime.lock').write_text('demo>=1.0\n')
            with self.assertRaises(ValueError):
                verify_lock_files(root)

    def test_floating_or_unhashed_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.lock'
            for value in ('demo>=1.0', 'demo==1.0', '--extra-index-url https://example.com', 'demo==1.0 --hash=sha256:no'):
                p.write_text(value)
                with self.assertRaises(ValueError):
                    read_lock(p)

    def test_wheel_tampering_rejected_even_with_same_metadata(self):
        import zipfile
        from scripts.skills.runtime_dependencies import verify_wheels
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            wheel = root/'demo-1.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as z:
                z.writestr('demo-1.0.dist-info/METADATA', 'Name: demo\nVersion: 1.0\n')
                z.writestr('demo.py', 'ORIGINAL=True')
            packages = {'demo': {'version':'1.0', 'hashes':[hashlib.sha256(wheel.read_bytes()).hexdigest()]}}
            self.assertEqual(verify_wheels(root, packages)[0]['version'], '1.0')
            with zipfile.ZipFile(wheel, 'a') as z:
                z.writestr('extra.py', 'TAMPERED=True')
            with self.assertRaisesRegex(ValueError, 'differs'):
                verify_wheels(root, packages)
