"""Validate the isolated documentation candidate; product application 需要 Codex 核验."""
import argparse
import ast
import contextlib
import csv
import hashlib
import io
import json
import posixpath
import re
import runpy
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import unquote

BASE = '62dfcfc5637f0bee2358074c4458047689dd5299'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path.cwd(), help='Read-only fixed-baseline source checkout.')
parser.add_argument('--output', type=Path, required=True, help='Output directory produced by doc_governance_probe.py.')
args = parser.parse_args()
ROOT = args.source.resolve(strict=True)
OUT = args.output.resolve()
CANDIDATE = OUT / 'candidate'
if ROOT == OUT or ROOT.is_relative_to(OUT) or OUT.is_relative_to(ROOT):
    raise SystemExit('Source and output must be disjoint dedicated trees.')
if any(p.is_symlink() for p in (args.output, *args.output.parents)) or any((OUT / name).is_symlink() for name in ('verification.json', 'existing-broken-links.json')):
    raise SystemExit('Output must not use symbolic links.')
TREE = json.loads((OUT / 'source-tree.json').read_text())
TRACKED = {x['path']: x for x in TREE['tree'] if x['type'] == 'blob'}
AFTER = set(json.loads((OUT / 'candidate-paths.json').read_text()))
FIXTURES = json.loads((OUT / 'fixture-map.json').read_text())
EDITS = json.loads((OUT / 'exact-edits.json').read_text())
LINK = re.compile(r'!?\[[^\]\n]*\]\(([^)\n]+)\)')
HTML = re.compile(r'(?:href|src)\s*=\s*["\x27]([^"\x27]+)["\x27]')
SCHEME = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def dirs(paths):
    return {str(parent) for p in paths for parent in Path(p).parents}

def local_target(raw, source, paths):
    value = raw.strip().strip('<>')
    if ' "' in value:
        value = value.split(' "', 1)[0]
    if not value or value.startswith(('#', '//')) or SCHEME.match(value):
        return None
    path = unquote(value.split('#', 1)[0].split('?', 1)[0]).rstrip('/')
    if not path:
        return None
    # Markdown targets are resolved relative to their containing document.
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))

def links(root, paths):
    valid = set(paths) | dirs(paths)
    records, broken, permalink_errors = [], [], []
    for p in sorted(paths):
        if not p.endswith(('.md', '.html')):
            continue
        try:
            text = (root / p).read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            continue
        for line, body in enumerate(text.splitlines(), 1):
            for match in list(LINK.finditer(body)) + list(HTML.finditer(body)):
                raw = match.group(1)
                row = {'source': p, 'line': line, 'raw': raw}
                if f'https://github.com/MainQuestAI/Deck-Master/' in raw and BASE in raw:
                    prefix = re.match(r'https://github.com/MainQuestAI/Deck-Master/(blob|tree)/' + BASE + r'/(.*)', raw)
                    if prefix:
                        target = unquote(prefix.group(2).split('#', 1)[0]).rstrip('/')
                        if target not in TRACKED and target not in dirs(TRACKED):
                            permalink_errors.append({**row, 'target': target})
                    continue
                target = local_target(raw, p, valid)
                if target is None:
                    continue
                row['target'] = target
                records.append(row)
                if target not in valid:
                    broken.append(row)
    return records, broken, permalink_errors

report = {'baseline': BASE, 'status': 'intermediate documentation sample verification',
          'validation_scope': {'candidate_stage': 'intermediate_documentation_sample',
                               'includes': ['archive_bytes', 'fixture_bytes', 'markdown_html_links',
                                            'package_resource_inventory', 'legacy_manifest'],
                               'excludes': ['final_candidate', 'json_csv_references', 'product_acceptance']},
          'final_candidate_status': 'not_evaluated'}
snapshot_errors = []
for p, item in TRACKED.items():
    raw = (ROOT / p).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if blob != item['sha']:
        snapshot_errors.append(p)
report['baseline_blob_errors'] = snapshot_errors

archive_path = next((CANDIDATE / 'docs/history').glob('*.zip'))
manifest_path = CANDIDATE / 'docs/history/manifest.csv'
rows = list(csv.DictReader(manifest_path.open()))
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    assert archive.read('ARCHIVE-MANIFEST.csv') == manifest_path.read_bytes()
    assert len(archive.namelist()) == len(rows) + 1
    for row in rows:
        raw = archive.read(row['original_path'])
        assert raw == (ROOT / row['original_path']).read_bytes(), row['original_path']
        assert len(raw) == int(row['bytes']) and digest(raw) == row['sha256']
    assert (set(TRACKED) - AFTER) <= {row['original_path'] for row in rows}
report['archive_preservation'] = {'original_files': len(rows), 'crc': 'PASS', 'byte_parity': 'PASS', 'manifest_parity': 'PASS', 'all_removed_paths_preserved': True}
assert all((ROOT / old).read_bytes() == (CANDIDATE / new).read_bytes() for old, new in FIXTURES.items())
report['fixture_byte_parity'] = {'files': len(FIXTURES), 'status': 'PASS'}

unchanged_scopes = ('src/', 'skills/', 'tools/', '.github/')
unchanged_configs = ('pyproject.toml', 'MANIFEST.in', 'setup.py')
scoped = [p for p in TRACKED if p.startswith(unchanged_scopes) or p in unchanged_configs]
assert all(p in AFTER and (ROOT / p).read_bytes() == (CANDIDATE / p).read_bytes() for p in scoped)
report['runtime_skill_packaging_unchanged'] = {'files': len(scoped), 'status': 'PASS'}
changed_tests = [x['path'] for x in EDITS if x['path'].startswith('tests/')]
reverse_strings = {value: key for key, value in FIXTURES.items()}
reverse_strings['tests/rebuild/fixtures/history/content-collaboration-v1.2'] = 'docs/reports/content-collaboration-v1.2'
class RestorePath(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value in reverse_strings:
            return ast.copy_location(ast.Constant(value=reverse_strings[node.value]), node)
        return node
for p in [x for x in TRACKED if x.startswith('tests/')]:
    assert p in AFTER
    if p not in changed_tests:
        assert (ROOT / p).read_bytes() == (CANDIDATE / p).read_bytes(), p
    else:
        original = ast.parse((ROOT / p).read_text())
        new = RestorePath().visit(ast.parse((CANDIDATE / p).read_text()))
        assert ast.dump(original, include_attributes=False) == ast.dump(new, include_attributes=False), p
report['test_semantics'] = {'changed_files': changed_tests, 'only_three_fixture_path_constants_changed': True, 'tests_deleted': 0, 'assertions_deleted': 0}

before_links, before_broken, _ = links(ROOT, TRACKED)
after_links, after_broken, permalink_errors = links(CANDIDATE, AFTER)
baseline_broken = {(x['source'], x['raw'], x['target']) for x in before_broken}
introduced = [x for x in after_broken if (x['source'], x['raw'], x['target']) not in baseline_broken]
report['links'] = {'syntax_scope': 'Markdown inline links/images and HTML href/src; local target existence and fixed-baseline target identity, not external network or every fragment anchor', 'before_local_link_occurrences': len(before_links), 'after_local_link_occurrences': len(after_links), 'before_broken_local_occurrences': len(before_broken), 'after_broken_local_occurrences': len(after_broken), 'introduced_broken_local_occurrences': introduced, 'fixed_baseline_permalink_target_errors': permalink_errors}
(OUT / 'existing-broken-links.json').write_text(json.dumps({'before': before_broken, 'after': after_broken}, ensure_ascii=False, indent=2))

def headings(path):
    text = path.read_text(encoding='utf-8-sig')
    result, counts = set(), {}
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        if match:
            value = re.sub(r'<[^>]+>', '', match.group(1)).lower().replace('`', '')
            value = ''.join(ch for ch in value if ch in '-_' or not unicodedata.category(ch).startswith(('P', 'S')))
            value = re.sub(r'\s', '-', value)
            count = counts.get(value, 0)
            counts[value] = count + 1
            result.add(value + (f'-{count}' if count else ''))
    result.update(re.findall(r'(?:id|name)=["\x27]([^"\x27]+)["\x27]', text))
    return result

fragment_checks = []
for p in sorted({x['path'] for x in EDITS if x['path'].endswith('.md')} | {x for x in AFTER - set(TRACKED) if x.endswith('.md')}):
    before_raw = {m.group(1) for m in LINK.finditer((ROOT / p).read_text())} if p in TRACKED else set()
    for match in LINK.finditer((CANDIDATE / p).read_text()):
        raw = match.group(1)
        if '#' not in raw or raw in before_raw:
            continue
        prefix = re.match(r'https://github.com/MainQuestAI/Deck-Master/blob/' + BASE + r'/(.*)', raw)
        if prefix:
            target, fragment = unquote(prefix.group(1)).split('#', 1)
            filepath = ROOT / target
        elif not SCHEME.match(raw):
            target = local_target(raw, p, AFTER)
            fragment = unquote(raw.split('#', 1)[1])
            filepath = CANDIDATE / (target or p)
        else:
            continue
        if filepath.suffix != '.md' or not filepath.is_file():
            continue
        fragment_checks.append({'source': p, 'raw': raw, 'target': target, 'fragment': fragment, 'found': fragment in headings(filepath)})
report['changed_markdown_fragments'] = fragment_checks

build_hook = runpy.run_path(str(CANDIDATE / 'tools/build_hook.py'))
before_inventory = build_hook['resource_inventory'](ROOT)
after_inventory = build_hook['resource_inventory'](CANDIDATE)
assert before_inventory == after_inventory
report['canonical_package_resources'] = {'status': 'PASS', 'files': len(after_inventory['files']), 'source_version': build_hook['source_version'](CANDIDATE), 'build_files_unchanged': True, 'wheel_or_sdist_build_performed': False}
sys.path.insert(0, str(CANDIDATE / 'src'))
from deck_master import cli
output = io.StringIO()
with contextlib.redirect_stdout(output):
    code = cli._legacy_manifest([])
actual_manifest = json.loads(output.getvalue())
expected_manifest = json.loads((ROOT / 'docs/archive/pre-rebuild/product-capability-manifest.v09.json').read_text())
assert actual_manifest == expected_manifest and code == 0
report['legacy_manifest_alias'] = {'status': 'PASS', 'path_retained': True, 'json_unchanged': True}
report['pass'] = not snapshot_errors and not introduced and not permalink_errors and all(x['found'] for x in fragment_checks)
(OUT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
print('Intermediate documentation sample only; final_candidate_status: not_evaluated.', file=sys.stderr)
if not report['pass']:
    raise SystemExit(1)
