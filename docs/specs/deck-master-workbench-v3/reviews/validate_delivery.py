"""Design delivery consistency checks; not production behavior acceptance."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
errors=[]; cards={}
for n in range(1,13):
    name=f'W{n:02d}'
    text=(ROOT/'packages'/f'{name}.md').read_text()
    matches=re.findall(r'^- \*\*(W\d{2}-AC\d{2})\*\*：(.*)$',text,re.M)
    if not matches: errors.append(f'{name}: no acceptance definitions')
    for key,description in matches:
        if key in cards: errors.append(f'duplicate {key}')
        cards[key]=(name,description.strip())
matrix={}
for line in (ROOT/'ACCEPTANCE.md').read_text().splitlines():
    if re.match(r'^\| W\d{2}-AC\d{2} \|',line):
        cols=[c.strip() for c in line.split('|')[1:-1]]
        key,desc,owner=cols[:3]
        if key in matrix: errors.append(f'matrix duplicate {key}')
        matrix[key]=(owner,desc)
        if cols[-1]!='未实施 / 未验证': errors.append(f'production status changed: {key}')
if len(cards)!=87 or len(matrix)!=87: errors.append(f'AC count {len(cards)}/{len(matrix)}')
for key in set(cards)|set(matrix):
    if cards.get(key)!=matrix.get(key): errors.append(f'AC mismatch {key}')
missing=[]
for p in ROOT.rglob('*.md'):
    for link in re.findall(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)',p.read_text()):
        target=link.strip('<>').split('#')[0]
        if not target or '://' in target or target.startswith('mailto:'): continue
        if not (p.parent/target).exists(): missing.append(f'{p.relative_to(ROOT)}: {target}')
errors+=missing
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in str(p) and p.name not in ('delivery-check.json','final-manifest.json')}
result={'scope':'design documentation consistency only','acceptance_items':len(cards),'owners':12,'production_implemented':0,'production_verified':0,'errors':errors,'status':'passed' if not errors else 'failed'}
(ROOT/'reviews/delivery-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
(ROOT/'reviews/final-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
