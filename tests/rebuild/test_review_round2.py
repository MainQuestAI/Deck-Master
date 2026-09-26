"""Behavior regressions for PR 39's second review."""
import json
from pathlib import Path

import pytest

from deck_master import cli, sources


@pytest.mark.parametrize('directory', [False, True])
def test_missing_reader_aborts_create(tmp_path, monkeypatch, capsys, directory):
    material = tmp_path / 'materials'
    material.mkdir()
    (material / 'good.md').write_text('real material')
    pdf = material / 'report.pdf'
    from PIL import Image
    Image.new('RGB', (10, 10), 'white').save(pdf)
    monkeypatch.setattr(sources.shutil, 'which', lambda _: None)
    project = tmp_path / 'project'
    code = cli.main(['create', '--brief', 'test', '--source', str(material if directory else pdf), '--out', str(project)])
    assert code == 3
    error = json.loads(capsys.readouterr().err)['error']
    assert error['code'] == 'needs_tool'
    assert str(pdf) in error['message']
    assert 'pdftotext' in error['message']
    assert not project.exists()


@pytest.mark.parametrize('cycle', ['self', 'pair', 'ancestor', 'broken'])
def test_directory_links_do_not_block_material(tmp_path, capsys, cycle):
    root = tmp_path / 'materials'
    root.mkdir()
    (root / 'good.md').write_text('real material')
    link = root / 'loop'
    link.symlink_to({'self': 'loop', 'pair': 'other', 'ancestor': '.', 'broken': 'missing'}[cycle])
    if cycle == 'pair':
        (root / 'other').symlink_to('loop')
    result = sources.discover_sources([root], out_dir=tmp_path / 'project')
    assert [p.name for p in result['adopted']] == ['good.md']
    assert any(Path(p['path']).name == 'loop' for p in result['skipped'])
    assert cli.main(['create', '--brief', 'test', '--source', str(root), '--out', str(tmp_path / 'project')]) == 0
    created = json.loads(capsys.readouterr().out)
    assert [p['name'] for p in created['sources_adopted']] == ['good.md']
    assert created['sources_skipped']



def test_explicit_loop_is_input_error(tmp_path, capsys):
    link = tmp_path / 'loop.pdf'
    link.symlink_to(link.name)
    assert cli.main(['create', '--brief', 'test', '--source', str(link), '--out', str(tmp_path / 'p')]) == 2


@pytest.mark.parametrize('change', ['add', 'replace'])
def test_missing_reader_update_preserves_project(tmp_path, monkeypatch, change):
    from PIL import Image
    from deck_master import service
    from deck_master.errors import SourceNeedsTool
    from deck_master.store import Store
    source = tmp_path / 'good.md'
    source.write_text('existing material')
    project = tmp_path / 'project'
    service.create(project, brief='test', sources=[source])
    before = Store(project).load_document()
    pdf = tmp_path / 'new.pdf'
    Image.new('RGB', (10, 10), 'white').save(pdf)
    monkeypatch.setattr(sources.shutil, 'which', lambda _: None)
    entry = {'path': str(pdf)}
    if change == 'replace':
        entry['source_id'] = before['sources'][0]['source_id']
    with pytest.raises(SourceNeedsTool):
        service.inputs_update(project, patch={'reason': 'new material', 'source_changes': {change: [entry]}},
                              base_revision=before['revision_id'], operation_id='missing-reader')
    assert Store(project).load_document() == before


def test_missing_pptx_dependency_preserves_tool_error(tmp_path, monkeypatch):
    import builtins
    from deck_master.errors import SourceNeedsTool
    original_import = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'pptx':
            raise ImportError('python-pptx unavailable')
        return original_import(name, *args, **kwargs)
    path = tmp_path / 'slides.pptx'
    path.write_bytes(b'content is not parsed without dependency')
    monkeypatch.setattr(builtins, '__import__', missing)
    with pytest.raises(SourceNeedsTool, match='python-pptx') as error:
        sources.read_source_snapshot(path)
    assert error.value.path == str(path)


@pytest.mark.parametrize('suffix,data', [('txt', b'\xff'), ('json', b'{bad'),
                                        ('docx', b'bad zip'), ('pptx', b'bad zip'), ('pdf', b'bad pdf')])
def test_bad_material_is_not_a_tool_requirement(tmp_path, monkeypatch, suffix, data):
    import subprocess
    from deck_master.errors import SourceUnreadable
    path = tmp_path / ('bad.' + suffix)
    path.write_bytes(data)
    if suffix == 'pdf':
        monkeypatch.setattr(sources.shutil, 'which', lambda _: '/reader/pdftotext')
        monkeypatch.setattr(sources.subprocess, 'run', lambda *a, **kw:
                            subprocess.CompletedProcess(a[0], 1, b'', b'invalid PDF'))
    with pytest.raises(SourceUnreadable) as error:
        sources.read_source_snapshot(path)
    assert error.value.path == str(path)
    assert 'deck-source-' not in str(error.value)
