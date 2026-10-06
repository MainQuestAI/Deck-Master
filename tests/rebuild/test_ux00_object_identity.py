"""UX-00 回归：对象身份契约（C01/N01/F03/F04）的 node 侧语义。

覆盖三件事：
1. ``dom.button`` 的第三实参永远是 primary，禁用必须走 ``props.disabled``——
   visual-style 分页曾把边界条件误当第三实参传入，按钮从不禁用，
   首组/末组仍可点击并产生越界请求（N02/F03/AC03 的契约层）。
2. 版本短码与其它对象短码分离：``version()`` 保留 "R " 前缀；
   ``shortRef()`` 用于决定/配方摘要，不得伪装成版本（F04/AC04）。
3. 交接复制快照守卫：只有"已成功读取且与当前所选一致"的组才可复制；
   等待响应期间切换组必须拒绝复制旧组文本（N01/F01/AC01 的判定层）。
浏览器侧的完整反例见 test_ux00_fixes_browser.py。
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'

SCRIPT = """
const V2 = <v2uri>;
const dom = await import(V2 + '/dom.js');
const changeHandoff = await import(V2 + '/change-handoff.js');
const checks = [];
const assert = (name, ok) => { if (!ok) throw new Error('failed: ' + name); checks.push(name); };

// --- 最小 DOM 桩：el() 只需要 createElement/createTextNode/append/属性赋值 ---
class FakeNode {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.listeners = {}; }
  append(...kids) { this.children.push(...kids); }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
}
globalThis.document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: text => ({text}),
};
globalThis.Node = FakeNode;

// F03：button 契约——第三实参是 primary；禁用只能通过 props.disabled。
const noop = () => {};
const gated = dom.button('上一组', noop, false, {disabled: true});
assert('props_disabled', gated.disabled === true);
assert('props_disabled_not_primary', gated.className === '');
const primary = dom.button('保存', noop, true);
assert('primary_class', primary.className === 'primary');
assert('primary_not_disabled', !primary.disabled);
const flagged = dom.button('下一组', noop, false);
assert('third_arg_false_not_disabled', !flagged.disabled);

// F04：版本短码保留 "R " 前缀；决定等其它对象短码不得伪装成版本。
assert('version_prefix', dom.version('0123456789abcdef') === 'R 01234567');
assert('version_missing', dom.version('') === '当前版本');
assert('shortref_plain', dom.shortRef('0123456789abcdef') === '01234567');
assert('shortref_missing', dom.shortRef(undefined) === '未记录');
assert('shortref_not_version', !dom.shortRef('0123456789abcdef').startsWith('R '));

// F01：复制快照守卫——身份一致才放行，快照在点击时冻结。
const guard = changeHandoff.copySnapshot;
assert('rejects_unloaded', guard(null, null, 'a') === null);
assert('rejects_stale_group', guard({text: 'A'}, 'a', 'b') === null);
assert('rejects_missing_identity', guard({text: 'A'}, null, 'a') === null);
const snap = guard({text: 'A'}, 'a', 'a');
assert('accepts_loaded_selection', Boolean(snap) && snap.id === 'a' && snap.text === 'A');

console.log(JSON.stringify({passed: true, checks}));
"""


def run_node():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the shipped-module identity contract')
    script = SCRIPT.replace('<v2uri>', json.dumps(V2.as_uri() + '/'))
    return subprocess.run([node, '--input-type=module', '-e', script],
                          capture_output=True, text=True, timeout=30, check=True)


def test_object_identity_contracts():
    result = run_node()
    value = json.loads(result.stdout)
    assert value['passed'] and len(value['checks']) >= 13
