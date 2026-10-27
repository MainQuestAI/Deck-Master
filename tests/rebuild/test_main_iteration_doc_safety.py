"""Each standalone generator rejects unsafe layouts before any write."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize('kind', ['equal', 'source-in-output', 'output-in-source',
                                 'existing-candidate', 'candidate-symlink', 'output-symlink', 'parent-symlink'])
def test_standalone_doc_generator_rejects_before_writes(tmp_path, kind):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'sentinel').write_bytes(b'must remain byte-identical')
    output = tmp_path / 'output'
    if kind == 'equal':
        output = source
    elif kind == 'source-in-output':
        output = tmp_path
    elif kind == 'output-in-source':
        output = source / 'output'
    elif kind in {'existing-candidate', 'candidate-symlink'}:
        output.mkdir()
        if kind == 'existing-candidate':
            (output / 'candidate').mkdir()
        else:
            (output / 'candidate').symlink_to(source, target_is_directory=True)
    elif kind == 'output-symlink':
        output.symlink_to(source, target_is_directory=True)
    else:
        link = tmp_path / 'link'; link.symlink_to(source, target_is_directory=True)
        output = link / 'output'
    def snapshot():
        return {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob('*') if p.is_file()}
    before = snapshot()
    script = Path(__file__).resolve().parents[2] / 'tools/main_iteration_20261027/doc_governance_probe.py'
    result = subprocess.run([sys.executable, str(script), '--source', str(source), '--output', str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert snapshot() == before
    assert not (output / 'source-tree.json').exists()


def test_machine_references_resolve_to_identical_archive_members_or_local_dependency():
    root = Path(__file__).resolve().parents[2]
    mapping = json.loads((root / 'docs/history/machine-references.json').read_text())
    assert len(mapping['references']) == 262
    assert len({row['target'] for row in mapping['references']}) == 82
    archive = next((root / 'docs/history').glob('*.zip'))
    with zipfile.ZipFile(archive) as opened:
        for row in mapping['references']:
            assert hashlib.sha256((root / row['source']).read_bytes()).hexdigest() == row['source_sha256']
            data = (root / row['target']).read_bytes() if row['resolution'] == 'local' else opened.read(row['target'])
            assert hashlib.sha256(data).hexdigest() == row['target_sha256']
    w12 = root / 'docs/reports/workbench-v3-execution-20260926/W12.md'
    assert w12.is_file() and w12.stat().st_size == 3077
