"""Renderer subprocesses must see the same full font configuration as fc-match."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from deck_tools import render as pipeline


@pytest.fixture
def renderer_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.sys, 'platform', 'darwin')
    monkeypatch.delenv('FONTCONFIG_FILE', raising=False)
    monkeypatch.delenv('FONTCONFIG_PATH', raising=False)
    monkeypatch.setattr(pipeline, 'executable', lambda name: name)
    calls = []
    listing = {'stdout': b''}

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == 'fc-conflist':
            return SimpleNamespace(stdout=listing['stdout'])
        if args[0] == 'soffice':
            output = Path(args[args.index('--outdir') + 1])
            (output / 'deck.pdf').write_bytes(b'%PDF-fake')
        elif args[0] == 'pdftoppm':
            Path(args[-1] + '-1.png').write_bytes(b'fake PNG')
        return SimpleNamespace(stdout=b'')

    monkeypatch.setattr(pipeline, 'run', run)
    return calls, listing


def test_macos_render_children_use_full_active_host_config(tmp_path, renderer_calls):
    calls, listing = renderer_calls
    config = tmp_path / 'host fonts' / 'fonts.conf'
    config.parent.mkdir()
    config.write_text('<fontconfig/>')
    listing['stdout'] = (f'- /inactive/fonts.conf: Inactive\n'
                         f'+ {config.parent}/conf.d/10-hinting.conf: Hinting\n'
                         f'+ {config}: Default configuration file\n').encode()
    before = dict(os.environ)
    images = pipeline.render_deck(tmp_path / 'deck.pptx', tmp_path / 'out', fonts={})
    assert [image.name for image in images] == ['page-1.png']
    assert [args[0] for args, _ in calls] == ['fc-conflist', 'soffice', 'pdftoppm']
    for _, kwargs in calls[1:]:
        assert kwargs['env'] == {**before, 'FONTCONFIG_FILE': str(config)}
    assert dict(os.environ) == before


@pytest.mark.parametrize('platform,explicit', [
    ('linux', {}), ('win32', {}),
    ('darwin', {'FONTCONFIG_FILE': '/user/custom.conf'}),
    ('darwin', {'FONTCONFIG_PATH': '/user/configs'}),
])
def test_existing_environment_is_inherited_without_discovery(
        tmp_path, monkeypatch, renderer_calls, platform, explicit):
    calls, _ = renderer_calls
    monkeypatch.setattr(pipeline.sys, 'platform', platform)
    for key, value in explicit.items():
        monkeypatch.setenv(key, value)
    before = dict(os.environ)
    pipeline.render_deck(tmp_path / 'deck.pptx', tmp_path / 'out', fonts={})
    assert [args[0] for args, _ in calls] == ['soffice', 'pdftoppm']
    assert all(kwargs['env'] is None for _, kwargs in calls)
    assert dict(os.environ) == before


@pytest.mark.parametrize('listing', [b'', b'- /inactive/fonts.conf: Inactive\n',
    b'+ /one/fonts.conf: One\n+ /two/fonts.conf: Two\n',
    b'+ /missing/fonts.conf: Missing\n'])
def test_bad_discovery_stops_before_rendering(tmp_path, renderer_calls, listing):
    calls, response = renderer_calls
    response['stdout'] = listing
    with pytest.raises(pipeline.NeedsTool, match='configure FONTCONFIG_FILE'):
        pipeline.render_deck(tmp_path / 'deck.pptx', tmp_path / 'out', fonts={})
    assert [args[0] for args, _ in calls] == ['fc-conflist']


