"""终审补丁 P2 回归：候选正文文本化必须覆盖完整 customer_visible。

page-text.js 是无 DOM 依赖的纯函数——按 test_browser_wire_digest 先例用 node
直接执行，五类字段级修改（嵌套列表子项/表头/脚注/标签/强调说明）各自必须改变
输出；标题与段落不变的基线候选必须与当前正文一致。
"""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'

BASE = {
    'customer_visible': {
        'title': '页面标题', 'subtitle': '副标题',
        'body_blocks': [
            {'type': 'paragraph', 'text': '普通段落。'},
            {'type': 'bullets', 'heading': '要点', 'items': [
                {'text': '第一层', 'children': [{'text': '第二层子项', 'children': []}]}]},
            {'type': 'table', 'title': '预算表', 'columns': [
                {'id': 'c1', 'label': '金额（万元）'}, {'id': 'c2', 'label': '口径'}],
             'rows': [{'cells': [{'column_id': 'c1', 'display_text': '120'}, {'column_id': 'c2', 'display_text': '预测值'}]}]},
        ],
        'callouts': [{'text': '强调说明'}], 'labels': [{'text': '内部标签'}], 'footnotes': [{'text': '脚注：预测口径'}],
    }
}


def mutated(**patch):
    import copy
    value = copy.deepcopy(BASE)
    for path, new in patch.items():
        node = value
        keys = path.split('/')
        for key in keys[:-1]:
            node = node[int(key)] if key.isdigit() else node[key]
        last = keys[-1]
        node[int(last) if last.isdigit() else last] = new
    return value


"""终审补丁 P2 回归：候选正文文本化必须覆盖完整 customer_visible。

page-text.js 是无 DOM 依赖的纯函数——按 test_browser_wire_digest 先例用 node
直接执行，五类字段级修改（嵌套列表子项/表头/脚注/标签/强调说明）各自必须改变
输出；标题与段落不变的基线候选必须与当前正文一致。
"""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'

BASE = {
    'customer_visible': {
        'title': '页面标题', 'subtitle': '副标题',
        'body_blocks': [
            {'type': 'paragraph', 'text': '普通段落。'},
            {'type': 'bullets', 'heading': '要点', 'items': [
                {'text': '第一层', 'children': [{'text': '第二层子项', 'children': []}]}]},
            {'type': 'table', 'title': '预算表', 'columns': [
                {'id': 'c1', 'label': '金额（万元）'}, {'id': 'c2', 'label': '口径'}],
             'rows': [{'cells': [{'column_id': 'c1', 'display_text': '120'}, {'column_id': 'c2', 'display_text': '预测值'}]}]},
        ],
        'callouts': [{'text': '强调说明'}], 'labels': [{'text': '内部标签'}], 'footnotes': [{'text': '脚注：预测口径'}],
    }
}


def mutated(**patch):
    import copy
    value = copy.deepcopy(BASE)
    for path, new in patch.items():
        node = value
        keys = path.split('/')
        for key in keys[:-1]:
            node = node[int(key)] if key.isdigit() else node[key]
        last = keys[-1]
        node[int(last) if last.isdigit() else last] = new
    return value


def test_page_text_covers_every_customer_visible_field():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to run the shipped pure page-text module')
    cases = {
        'nested-bullet': mutated(**{'customer_visible/body_blocks/1/items/0/children/0/text': '第二层子项（改）'}),
        'table-header': mutated(**{'customer_visible/body_blocks/2/columns/0/label': '金额（亿元）'}),
        'footnote': mutated(**{'customer_visible/footnotes/0/text': '脚注：实际口径'}),
        'label': mutated(**{'customer_visible/labels/0/text': '外发标签'}),
        'callout': mutated(**{'customer_visible/callouts/0/text': '新的强调说明'}),
    }
    script = ('import {pageText} from ' + json.dumps((V2 / 'page-text.js').as_uri()) + ';'
              'const base = pageText(' + json.dumps(BASE, ensure_ascii=False) + ');'
              'const cases = {};'
              + ''.join('cases[' + json.dumps(name, ensure_ascii=False) + '] = pageText(' + json.dumps(v, ensure_ascii=False) + ');' for name, v in cases.items())
              + 'console.log(JSON.stringify({base, cases}));')
    result = subprocess.run([node, '--experimental-default-type=module', '--input-type=module', '-e', script],
                            capture_output=True, text=True, check=True)
    output = json.loads(result.stdout)
    baseline = output['base']
    for name, text in output['cases'].items():
        assert text != baseline, f'{name} 修改必须改变正文文本化输出'
    assert '万元' in baseline and '第二层子项' in baseline and '预测口径' in baseline and '内部标签' in baseline and '强调说明' in baseline


def test_page_text_table_semantics_follow_render_join():
    """终审补丁 P2 回归：表格文本化必须与实际渲染器同规则——按 columns 定义顺序、
    用 cell.column_id === col.id 关联数值。
    (a) 交换单元格的 column_id（数值换业务含义）→ 输出必须变化；
    (b) 仅打乱 cells 存储顺序（关联不变）→ 输出必须不变；
    (c) 调整 columns 定义顺序 → 输出跟随新列序。"""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to run the shipped pure page-text module')
    table_of = lambda doc_value: doc_value['customer_visible']['body_blocks'][2]

    def run(doc_value):
        script = ('import {pageText} from ' + json.dumps((V2 / 'page-text.js').as_uri()) + ';'
                  'console.log(JSON.stringify(pageText(' + json.dumps(doc_value, ensure_ascii=False) + ')));')
        result = subprocess.run([node, '--experimental-default-type=module', '--input-type=module', '-e', script],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    baseline_doc = mutated(**{'customer_visible/body_blocks/2/columns/0/label': '金额（万元）'})
    baseline = run(baseline_doc)

    # (a) 列归属变化：实际显示的 金额=80→100、口径=100→80，文本化必须同步反映
    swapped = copy.deepcopy(baseline_doc)
    table = table_of(swapped)
    table['rows'][0]['cells'] = [
        {'column_id': 'c1', 'display_text': '100'},
        {'column_id': 'c2', 'display_text': '80'}]
    swapped_text = run(swapped)
    assert swapped_text != baseline, '列归属变化必须出现在比较文本中'

    # (b) 仅存储顺序变化：column_id↔数值关联不变 → 实际显示不变，文本化也不变
    reordered = copy.deepcopy(baseline_doc)
    cells = table_of(reordered)['rows'][0]['cells']
    assert [c['column_id'] for c in cells] == ['c1', 'c2']
    table_of(reordered)['rows'][0]['cells'] = list(reversed(cells))
    reordered_text = run(reordered)
    assert reordered_text == baseline, '仅存储顺序变化不得制造差异'

    # (c) 列定义顺序调整：输出跟随新列序（与实际页面渲染一致）
    recolumned = copy.deepcopy(baseline_doc)
    table = table_of(recolumned)
    table['columns'] = list(reversed(table['columns']))
    table['rows'][0]['cells'] = list(reversed(table['rows'][0]['cells']))
    recolumned_text = run(recolumned)
    assert recolumned_text != baseline, '列定义顺序变化会改变实际显示，文本化必须跟随'


def test_page_text_table_semantics_follow_render_join():
    """终审补丁 P2 回归：表格文本化必须与实际渲染器同规则——按 columns 定义顺序、
    用 cell.column_id === col.id 关联数值。
    (a) 交换单元格的 column_id（数值换业务含义）→ 输出必须变化；
    (b) 仅打乱 cells 存储顺序（关联不变）→ 输出必须不变；
    (c) 调整 columns 定义顺序 → 输出跟随新列序。"""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to run the shipped pure page-text module')
    table_of = lambda doc_value: doc_value['customer_visible']['body_blocks'][2]


def test_page_text_table_semantics_follow_render_join():
    """终审补丁 P2 回归：表格文本化必须与实际渲染器同规则——按 columns 定义顺序、
    用 cell.column_id === col.id 关联数值。
    (a) 交换单元格的 column_id（数值换业务含义）→ 输出必须变化；
    (b) 仅打乱 cells 存储顺序（关联不变）→ 输出必须不变；
    (c) 调整 columns 定义顺序 → 输出跟随新列序。"""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed to run the shipped pure page-text module')

    def run(doc_value):
        script = ('import {pageText} from ' + json.dumps((V2 / 'page-text.js').as_uri()) + ';'
                  'console.log(JSON.stringify(pageText(' + json.dumps(doc_value, ensure_ascii=False) + ')));')
        result = subprocess.run([node, '--experimental-default-type=module', '--input-type=module', '-e', script],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def table_of(doc_value):
        return doc_value['customer_visible']['body_blocks'][2]

    baseline_doc = mutated(**{'customer_visible/body_blocks/2/columns/0/label': '金额（万元）'})
    baseline = run(baseline_doc)
    assert '120 | 预测值' in baseline

    # (a) 列归属变化：实际显示的 金额=100、口径=80，文本化必须同步反映
    swapped = copy.deepcopy(baseline_doc)
    table_of(swapped)['rows'][0]['cells'] = [
        {'column_id': 'c1', 'display_text': '100'},
        {'column_id': 'c2', 'display_text': '80'}]
    swapped_text = run(swapped)
    assert swapped_text != baseline, '列归属变化必须出现在比较文本中'
    assert '100 | 80' in swapped_text

    # (b) 仅存储顺序变化：column_id↔数值关联不变 → 实际显示不变，文本化也不变
    reordered = copy.deepcopy(baseline_doc)
    cells = table_of(reordered)['rows'][0]['cells']
    assert [c['column_id'] for c in cells] == ['c1', 'c2']
    table_of(reordered)['rows'][0]['cells'] = list(reversed(cells))
    assert run(reordered) == baseline, '仅存储顺序变化不得制造差异'

    # (c) 列定义顺序调整：输出跟随新列序（与实际页面渲染一致）
    recolumned = copy.deepcopy(baseline_doc)
    table = table_of(recolumned)
    table['columns'] = list(reversed(table['columns']))
    table['rows'][0]['cells'] = list(reversed(table['rows'][0]['cells']))
    recolumned_text = run(recolumned)
    assert recolumned_text != baseline, '列定义顺序变化会改变实际显示，文本化必须跟随'
