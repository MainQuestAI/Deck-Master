"""AC23 剩余项（字体回退与共同行为收敛）：静态检查，不需要浏览器。

- 字体只从 token 取用，且 token 链带通用回退与中文字族（界面文案是中文）。
- `.stack` 这类高频类必须有基础 display 规则（F16 记录过的漂移）。
"""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'
GENERIC = ('serif', 'sans-serif', 'monospace', 'system-ui', 'ui-monospace')
CJK = ('PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC')


def tokens_text():
    return (STATIC / 'tokens.css').read_text(encoding='utf-8')


def test_font_tokens_carry_generic_and_cjk_fallbacks():
    text = tokens_text()
    for name in ('--font-body', '--font-mono'):
        line = next((row for row in text.splitlines() if row.strip().startswith(name)), None)
        assert line, f'{name} 未定义'
        assert any(family in line for family in GENERIC), f'{name} 缺少通用回退：{line.strip()}'
        assert any(family in line for family in CJK), f'{name} 缺少中文字族回退：{line.strip()}'


def test_consumers_use_font_tokens_only():
    offenders = []
    for sheet in sorted(STATIC.glob('*.css')):
        if sheet.name == 'tokens.css':
            continue
        for number, line in enumerate(sheet.read_text(encoding='utf-8').splitlines(), 1):
            if 'font-family' not in line:
                continue
            if not re.search(r'font-family\s*:\s*var\(--font-', line):
                offenders.append(f'{sheet.name}:{number}: {line.strip()[:80]}')
    assert not offenders, '字体必须来自 token：' + '; '.join(offenders)


def test_high_frequency_stack_class_has_a_display_rule_and_hidden_guard():
    """`.stack` 是使用最广的类；没有基础规则时 <label class="stack"> 会退化成 inline，
    且任何作者 display 规则都会盖掉 [hidden]。两条都要在。"""
    text = ''.join(sheet.read_text(encoding='utf-8')
                   for sheet in STATIC.glob('*.css') if sheet.name != 'tokens.css')
    assert re.search(r'(^|[},])\s*\.stack\s*\{[^}]*display\s*:', text, re.M), '.stack 缺少基础 display 规则'
    assert re.search(r'(^|[},])\s*\.stack\[hidden\]\s*\{[^}]*display\s*:\s*none', text, re.M), \
        '.stack[hidden] 缺少守卫（作者 display 规则会盖掉 hidden）'
