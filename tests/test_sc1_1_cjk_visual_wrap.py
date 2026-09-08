"""Visual CJK line breaks preserve exact locked content."""
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from high_density.svg import _validate_svg_text, SvgVisualError


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
