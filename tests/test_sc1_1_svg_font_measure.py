"""Host SVG layout uses the same font metrics as submission validation."""
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from PIL import ImageFont
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from high_density.svg import _font_path, _text_svg, _validate_svg_text, SvgVisualError


def element(text,width,size=31,minimum=31,max_lines=4,height=150):
    return dict(element_id='caption',text=text,text_ref='content_lock.customer_visible.title',bbox=dict(x=10,y=10,w=width,h=height),style=dict(font_family='Arial',fill='#000000'),text_fit=dict(preferred_size_px=size,min_size_px=minimum,max_lines=max_lines),component_id='content',priority='P1')


def validate(e):
    node=ET.fromstring(_text_svg(e,'P001'))
    _validate_svg_text(node,e,'P001',[])
    return node


def test_wide_english_words_wrap_before_measured_overflow():
    font=ImageFont.truetype(str(_font_path('Arial','P001','caption')),31)
    e=element('WWW WWW',font.getlength('WWW WWW')-5)
    node=validate(e)
    assert len(list(node)) == 2
    assert node.get('font-size') == '31.00px'


def test_single_wide_word_shrinks_to_fit_actual_font():
    font=ImageFont.truetype(str(_font_path('Arial','P001','caption')),31)
    node=validate(element('WWWW',font.getlength('WWWW')-8,minimum=20,max_lines=1))
    assert float(node.get('font-size').removesuffix('px')) < 31


def test_fixed_size_wide_word_is_rejected_without_bbox_tolerance():
    font=ImageFont.truetype(str(_font_path('Arial','P001','caption')),31)
    with pytest.raises(SvgVisualError,match='overflow'):
        _text_svg(element('WWWW',font.getlength('WWWW')-8,max_lines=1),'P001')


def test_cjk_wrap_preserves_all_characters_and_font_size():
    font=ImageFont.truetype(str(_font_path('Arial','P001','caption')),31)
    text='准备确认接口与指标责任人'
    node=validate(element(text,font.getlength(text[:5])+.1))
    assert ''.join(node.itertext()) == text
    assert len(list(node)) >= 2
    assert node.get('font-size') == '31.00px'
