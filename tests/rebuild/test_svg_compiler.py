from pathlib import Path
import pytest
from deck_master.compiler.svg import parse_svg, SvgError
from deck_master.compiler import compile_deck, CompileOptions, SvgInput


def test_native_source_preserves_text_spacing_and_zero_opacity():
    page = parse_svg(b'<svg viewBox="0 0 100 75"><g opacity="0"><text x="2" y="20" letter-spacing="3">NOVA</text></g></svg>', page_id='p')
    assert page['shapes'][0]['text'] == 'NOVA'
    assert page['shapes'][0]['opacity'] == 0
    assert page['shapes'][0]['letter_spacing'] == 3

@pytest.mark.parametrize('body', ['<image href="secret.png"/>', '<script/>', '<rect filter="blur(2)"/>'])
def test_unsupported_svg_fails_explicitly(body):
    with pytest.raises(SvgError):
        parse_svg(f'<svg viewBox="0 0 100 75">{body}</svg>'.encode(), page_id='p')


def test_failed_export_does_not_publish_pptx(tmp_path):
    source = tmp_path / 'page.svg'
    source.write_text('<svg viewBox="0 0 100 75"><rect width="100" height="75"/></svg>')
    with pytest.raises(FileNotFoundError):
        compile_deck([SvgInput('p', source)], CompileOptions('/missing/node', '/missing/module'), tmp_path / 'out')
    assert not (tmp_path / 'out' / 'deck.pptx').exists()


def test_curve_endpoints_remain_native():
    page = parse_svg(b'<svg viewBox="0 0 100 75"><path d="M 0 0 C 0 30 30 30 30 0 Z"/></svg>', page_id='p')
    cmds = page['shapes'][0]['commands']
    assert cmds[0] == {'moveTo': {'x': 0, 'y': 0}}
    assert cmds[-2] == {'lineTo': {'x': 30, 'y': 0}}
    assert cmds[-1] == {'close': {}}
    assert len(cmds) > 5
