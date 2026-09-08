"""Two real manifest writers must not share a temporary pathname."""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from skills import installer

def test_simultaneous_manifest_replace_keeps_complete_json(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, 'INSTALL_LOG_DIR', tmp_path)
    original_replace = Path.replace
    barrier = threading.Barrier(2)
    observed = []
    def replace(source, target):
        if Path(target).name == 'companion-manifest.json':
            observed.append(source)
            barrier.wait(timeout=5)
        return original_replace(source, target)
    monkeypatch.setattr(Path, 'replace', replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:installer.write_companion_manifest(), range(2)))
    assert results[0] == results[1]
    assert len(set(observed)) == 2
    actual = json.loads(results[0].read_text())
    expected = installer.companion_manifest()
    assert actual.pop('generated_at')
    expected.pop('generated_at')
    assert actual == expected
    assert list(results[0].parent.glob('*.tmp')) == []
