"""Classify existing local-link diagnostics and check current entrances. 需要 Codex 核验."""
import argparse
import collections
import hashlib
import json
import posixpath
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='Output directory produced by doc_governance_probe.py.')
args = parser.parse_args()
OUT = args.output.resolve()
CANDIDATE = OUT / 'candidate'
TRACKED = {x['path'] for x in json.loads((OUT / 'source-tree.json').read_text())['tree']}
AFTER = set(json.loads((OUT / 'candidate-paths.json').read_text()))
DIRS = {str(x) for p in AFTER for x in Path(p).parents}
broken = json.loads((OUT / 'existing-broken-links.json').read_text())['after']
LINK = re.compile(r'!?\[[^\]\n]*\]\(([^)\n]+)\)')
INLINE = re.compile(r'(?<!`)`([^`\n]+)`(?!`)')
SCHEME = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')
active_evidence_sources = {
    'docs/specs/deck-master-content-collaboration-v1.2/CONTENT-QUALITY-ITERATION.md': 'Lines 3–11 retain inherited current TASKS/ACCEPTANCE/CONTRACTS; lines 33–48 and 332–353 cite a separate fixed-SHA source package not present in this tracked tree. Same filenames in current src are not the same historical bytes.',
    'docs/specs/deck-master-webui-v4-20260930/UX-REPAIR-DECISIONS.md': 'Lines 3–5 say D1–D4 are in-force decisions; their external final-repair-plan source is absent from the fixed tree. Decisions remain readable locally, original supporting plan requires its owner.',
}
rows = []
for item in broken:
    p = item['source']
    if p.startswith('src/deck_master/resources/static/') and item['raw'].startswith(('/v2/', '/studio/')):
        target = 'src/deck_master/resources/static/' + item['raw'].lstrip('/')
        assert target in AFTER
        category = 'false_positive_http_route'
        reason = 'HTTP absolute URL, not a filesystem root. web.py:438–443,657–671,816–824 resolves it into the packaged static tree.'
        resolution = target
    elif p in active_evidence_sources:
        category = 'active_inherited_evidence_gap_needs_owner'
        reason = active_evidence_sources[p]
        resolution = None
    elif p.startswith('docs/specs/deck-master-rebuild-v1/sources/'):
        category = 'historical_original_reference_gap'
        reason = 'Received September 16 old-architecture source, retained verbatim. Retired scripts/:line references and missing original audit attachments are historical gaps, not current commands.'
        resolution = None
    else:
        category = 'historical_report_or_coverage_gap'
        reason = 'Dated implementation evidence / coverage appendix refers to excluded dist artifacts, missing evidence package, or a private worktree. Do not substitute unrelated same-name files or invent a permalink.'
        resolution = None
    name = Path(item['target'].rsplit(':', 1)[0]).name
    candidates = [x for x in sorted(TRACKED) if Path(x).name == name]
    rows.append({**item, 'category': category, 'reason': reason, 'verified_resolution': resolution, 'same_basename_candidates_not_identity_proof': candidates, 'action': 'no product edit' if resolution else 'keep original and record missing provenance; 需要 Codex 核验'})

priority = {'README.md', 'AGENTS.md', 'CLAUDE.md', 'DESIGN.md', 'CONTRIBUTING.md', 'ROADMAP.md', 'SUPPORT.md', 'SECURITY.md', 'CHANGELOG.md', 'skills/RESOLVER.md', 'docs/specs/README.md', 'docs/releases/1.0.0-preparation.md'}
priority |= {p for p in AFTER if p.startswith('docs/') and len(Path(p).parts) == 2 and p.endswith('.md')}
priority |= {p for p in AFTER if p.startswith('skills/') and p.endswith('/SKILL.md')}

def anchors(path):
    text = path.read_text(encoding='utf-8-sig')
    found, counts = set(), {}
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        if not match:
            continue
        value = re.sub(r'<[^>]+>', '', match.group(1)).lower().replace('`', '')
        value = ''.join(x for x in value if x in '-_' or not unicodedata.category(x).startswith(('P', 'S')))
        value = re.sub(r'\s', '-', value)
        n = counts.get(value, 0)
        counts[value] = n + 1
        found.add(value + (f'-{n}' if n else ''))
    found.update(re.findall(r'(?:id|name)=["\x27]([^"\x27]+)["\x27]', text))
    return found

entry_checks = []
entry_issues = []
historical_inline_mentions = []
for p in sorted(priority):
    raw = (CANDIDATE / p).read_bytes()
    count = fragments = inline_paths = 0
    for n, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        for match in LINK.finditer(line):
            value = match.group(1).strip().strip('<>')
            if SCHEME.match(value) or value.startswith('//'):
                continue
            path, _, fragment = unquote(value).partition('#')
            target = posixpath.normpath(posixpath.join(posixpath.dirname(p), path)) if path else p
            count += 1
            if target not in AFTER and target not in DIRS:
                entry_issues.append({'source': p, 'line': n, 'raw': value, 'reason': 'missing local target'})
            elif fragment and target.endswith('.md'):
                fragments += 1
                if fragment not in anchors(CANDIDATE / target):
                    entry_issues.append({'source': p, 'line': n, 'raw': value, 'reason': 'unresolved Markdown fragment'})
        for match in INLINE.finditer(line):
            value = match.group(1)
            if not value.startswith(('docs/', 'skills/', 'src/', 'tests/', 'tools/')) or re.search(r'\s|[<>…*]', value):
                continue
            value = value.split('#', 1)[0].rstrip('/')
            inline_paths += 1
            if value not in AFTER and value not in DIRS:
                item = {'source': p, 'line': n, 'raw': value, 'reason': 'exact repository path missing'}
                if p == 'CHANGELOG.md' and value == 'docs/contracts' and 73 <= n <= 94:
                    historical_inline_mentions.append({**item, 'classification': 'versioned historical path mention, not a current filesystem instruction', 'basis': 'CHANGELOG.md:73–94 explicitly records v0.9.14-preview.4 packaging behavior; preserve old release facts.'})
                else:
                    entry_issues.append(item)
    entry_checks.append({'path': p, 'sha256': hashlib.sha256(raw).hexdigest(), 'lines': len(raw.decode('utf-8-sig').splitlines()), 'local_link_occurrences': count, 'fragment_occurrences': fragments, 'exact_inline_repository_paths': inline_paths})

result = {'status': 'classified; 正式应用需要 Codex 核验', 'counts': dict(collections.Counter(x['category'] for x in rows)), 'existing_diagnostics': len(rows), 'priority_entry_files': entry_checks, 'priority_entry_issues': entry_issues, 'priority_true_local_link_failures': len(entry_issues), 'historical_inline_mentions': historical_inline_mentions, 'known_active_evidence_gaps': [x for x in rows if x['category'] == 'active_inherited_evidence_gap_needs_owner'], 'all_diagnostics': rows, 'scope': 'Local target + priority Markdown fragment and exact inline repo-path checks; no claim of public external URL liveness or unavailable original attachments.'}
(OUT / 'link-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'counts': result['counts'], 'priority_files': len(entry_checks), 'priority_entry_issues': entry_issues}, ensure_ascii=False, indent=2))
if entry_issues:
    raise SystemExit(1)
