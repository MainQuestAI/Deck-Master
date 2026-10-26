import subprocess
import sys
for iteration in range(1, 11):
    print(f'Contention product trial {iteration}/10', flush=True)
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/rebuild/test_pr189_clear_storage_browser.py::test_two_first_attempts_serialize_only_the_local_record', '--require-browser', '--chromium-executable', '/usr/bin/chromium'])
    if result.returncode:
        raise SystemExit(result.returncode)
