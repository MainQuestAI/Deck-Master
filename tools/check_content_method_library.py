#!/usr/bin/env python3
"""Read-only engineering checks; neither content review nor release approval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import runpy
from urllib.parse import unquote, urlsplit

LINK = re.compile(r'(?<!!)\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
LABEL = re.compile(r'虚构|教学|示范|示例|synthetic|fictional|example', re.I)


def check_library(root: Path) -> dict:
    root = root.resolve()
    hook = runpy.run_path(str(root / 'tools/build_hook.py'))
    # The authoritative build algorithm rejects unknown/missing files and symlinks.
    inventory = hook['resource_inventory'](root)
    catalog = runpy.run_path(str(root / 'src/deck_master/resource_catalog.py'))
    library = root / 'skills/deck-master'
    resources = catalog['load_catalog'](library)
    registered = {(library / row['relative_path']).resolve() for row in resources.values()}
    errors, links = [], 0
    for mid, row in resources.items():
        path = library / row['relative_path']
        if path.suffix != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        if row['kind'] == 'example' and not LABEL.search(text):
            errors.append(f'{mid}: example lacks an explicit example/fictional label')
        for href in LINK.findall(text):
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            links += 1
            if target not in registered or not target.is_file():
                errors.append(f'{mid}: local link is not a registered file: {href}')
    return {'status': 'FAIL' if errors else 'PASS', 'scope': 'resource engineering only',
            'professional_content_review': 'NOT_RUN', 'resource_count': len(resources),
            'public_skills': inventory['public_skills'], 'packaged_file_count': len(inventory['files']),
            'local_links_checked': links, 'errors': errors,
            'sha256_by_source': {row['canonical_source']: row['sha256']
                                 for row in inventory['files'].values()}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = check_library(args.root)
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        result = {'status': 'FAIL', 'scope': 'resource engineering only', 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
