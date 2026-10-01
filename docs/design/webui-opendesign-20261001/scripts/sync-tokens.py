"""从唯一维护源更新入口内联 token；支持 --check 检查漂移。"""
from pathlib import Path
import re
import sys
root = Path(__file__).resolve().parents[1]
source = (root / 'tokens.css').read_text()
block = source[source.index(':root {'):].strip()
check = '--check' in sys.argv
for name in ('index.html', 'design-system.html'):
    path = root / name
    text = path.read_text()
    updated, count = re.subn(r':root\s*\{.*?\}', lambda _: block, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{name}: 缺少 token 区块')
    if check and updated != text:
        raise SystemExit(f'{name}: token 与维护源不一致')
    if not check:
        path.write_text(updated)
print('两个入口 token 与 tokens.css 一致')
