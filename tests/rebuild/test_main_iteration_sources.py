"""MAIN-ITER-20261027: deduplication must preserve block and table meaning."""
import zipfile

import pytest

from deck_master.sources import read_source


def paragraph(text):
    return f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'


def table(body):
    return f'<w:tbl><w:tr><w:tc>{body}</w:tc></w:tr></w:tbl>'


def control(body):
    return f'<w:sdt><w:sdtContent>{body}</w:sdtContent></w:sdt>'


def textbox(body):
    return f'<w:p><w:r><w:pict><w:txbxContent>{body}</w:txbxContent></w:pict></w:r></w:p>'


@pytest.mark.parametrize('kind', ['paragraphs', 'cell', 'nested', 'textbox',
                                  'ordinary', 'table-control', 'row-control',
                                  'cell-control', 'nested-grid', 'textbox-table'])
def test_docx_blocks_survive_single_extraction(tmp_path, kind):
    pair = paragraph('100') + paragraph('200')
    content = {
        'paragraphs': pair, 'cell': table(pair), 'nested': table(table(pair)),
        'textbox': textbox(pair), 'ordinary': table(paragraph('收入')),
        'table-control': control(table(paragraph('收入'))),
        'row-control': '<w:tbl>' + control('<w:tr><w:tc>' + paragraph('收入') + '</w:tc></w:tr>') + '</w:tbl>',
        'cell-control': '<w:tbl><w:tr>' + control('<w:tc>' + paragraph('收入') + '</w:tc>') + '</w:tr></w:tbl>',
        'nested-grid': table('<w:tbl>' + ''.join('<w:tr>' + ''.join('<w:tc>' + paragraph(v) + '</w:tc>' for v in row) + '</w:tr>' for row in [('收入', '成本'), ('300', '400')]) + '</w:tbl>'),
        'textbox-table': textbox(table(paragraph('收入'))),
    }[kind]
    path = tmp_path / 'blocks.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + content + '</w:body></w:document>')
    result = read_source(path)
    if kind in {'paragraphs', 'cell', 'nested', 'textbox'}:
        assert result.text.count('100') == result.text.count('200') == 1
        assert '100200' not in result.text
        if result.tables:
            assert result.tables[-1]['rows'] == [['100\n200']]
    else:
        assert result.text.count('收入') == 1
    if kind in {'nested', 'nested-grid'}:
        assert len(result.tables) == 2
    if kind == 'nested-grid':
        assert result.tables[-1]['rows'] == [['收入', '成本'], ['300', '400']]
    if kind in {'textbox', 'textbox-table'}:
        assert result.status == 'pending_visual' and result.image_pages
    assert result.locators and result.original_sha256
