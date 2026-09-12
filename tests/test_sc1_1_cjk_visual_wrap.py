"""Visual CJK line breaks preserve exact locked content."""
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from high_density.svg import _validate_svg_text, _text_svg, SvgVisualError


def check(declared, lines):
    node = ET.Element('text', {'id':'caption','font-family':'Arial','font-size':'20','font-weight':'400','fill':'#000000','data-pptx-text':declared,'data-pptx-text-ref':'content_lock.customer_visible.title','data-pptx-bounds':'10,10,1000,200','x':'10','y':'30'})
    for i,line in enumerate(lines):
        ET.SubElement(node,'tspan',{'x':'10','dy':'0' if i == 0 else '28'}).text=line
    scene={'element_id':'caption','text':declared,'text_ref':'content_lock.customer_visible.title'}
    _validate_svg_text(node,scene,'P001',[])


def test_cjk_visual_line_break_preserves_locked_characters():
    check('库存服务：可售量计算与预占',['库存服务：','可售量计算与预占'])
    check('现有ERP与WMS：提供库存事实',['现有ERP与WMS：','提供库存事实'])


@pytest.mark.parametrize('lines',[['库存服务：','可售量计算与占'],['库存服务：','可售量计算与预约']])
def test_cjk_visual_line_break_does_not_hide_deleted_or_changed_text(lines):
    with pytest.raises(SvgVisualError,match='visible SVG text drift'):
        check('库存服务：可售量计算与预占',lines)


def test_english_word_spaces_remain_semantic():
    check('Inventory service',['Inventory','service'])
    with pytest.raises(SvgVisualError,match='visible SVG text drift'):
        check('Inventory service',['Inventoryservice'])
    with pytest.raises(SvgVisualError,match='visible SVG text drift'):
        check('Inventoryservice',['Inventory','service'])


def test_locked_newlines_and_additional_cjk_wraps_preserve_content():
    check('准备\n记录：接口、指标口径与责任清单',
          ['准备', '记录：接口、指标口径与', '责任清单'])
    check('库存准确率\n数量一致的门店×SKU记录数 ÷ 已盘点记录数。',
          ['库存准确率', '数量一致的门店×SKU记录数 ÷ 已盘点', '记录数。'])
    check('Inventory service\n准备材料齐全',
          ['Inventory', 'service', '准备材料', '齐全'])


@pytest.mark.parametrize('lines', [
    ['准备', '记录：接口、指标口径与', '清单'],
    ['准备', '记录：接口、指标口径与', '责任名单'],
    ['准备', '责任清单', '记录：接口、指标口径与'],
])
def test_locked_newline_does_not_hide_missing_changed_or_reordered_text(lines):
    with pytest.raises(SvgVisualError, match='visible SVG text drift'):
        check('准备\n记录：接口、指标口径与责任清单', lines)


def test_multiline_cjk_normalization_preserves_actual_word_spaces():
    with pytest.raises(SvgVisualError, match='visible SVG text drift'):
        check('Inventory service\n准备材料齐全',
              ['Inventoryservice', '准备材料', '齐全'])
    with pytest.raises(SvgVisualError, match='visible SVG text drift'):
        check('准备\n关键 记录需要确认', ['准备', '关键记录需要', '确认'])


@pytest.mark.parametrize('declared', ['准备\n记录：接口、指标口径与责任清单',
                                      'Inventory service\nPrepare records',
                                      '准备\r\n记录：接口', '准备\t材料\n记录'])
def test_generated_svg_roundtrips_locked_whitespace_and_logical_lines(declared):
    element = {
        'element_id': 'caption', 'kind': 'text', 'text': declared,
        'text_ref': 'content_lock.customer_visible.title',
        'bbox': {'x': 10, 'y': 10, 'w': 900, 'h': 200},
        'text_fit': {'preferred_size_px': 20, 'min_size_px': 20,
                     'max_lines': 4, 'line_height': 1.2},
        'style': {'font_family': 'Arial', 'font_weight': '400', 'fill': '#000000'},
    }
    node = ET.fromstring(_text_svg(element, 'P001'))
    assert node.get('data-pptx-text') == declared
    assert [''.join(span.itertext()) for span in node] == declared.splitlines()
    _validate_svg_text(node, element, 'P001', [])
