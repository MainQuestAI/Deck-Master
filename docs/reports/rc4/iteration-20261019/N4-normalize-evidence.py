"""Preserve exact N4 evidence, then normalize only portable locator strings.

Run after N4A-probe.py, with --raw-dir pointing outside the checkout. The
normalization manifest explains any embedded source-extract body hash change;
resource hashes and measured counts continue to name the original bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    checkout = directory.parents[3]
    raw_dir = args.raw_dir.resolve()
    if raw_dir.is_relative_to(checkout):
        parser.error('--raw-dir must be outside the checkout')
    raw_dir.mkdir(parents=True, exist_ok=True)

    def portable(value):
        value = value.replace(str(checkout), '<checkout>')
        value = re.sub(r'/(?:private/)?tmp/deck-master-n4a-synthetic-[^/\\"\s]+/project',
                       '<synthetic-project>', value)
        value = re.sub(r'/(?:private/)?tmp/deck-master-n4a-synthetic-[^/\\"\s]+',
                       '<synthetic-input>', value)
        value = re.sub(r'/(?:private/)?tmp/pytest-of-[^/\\"\s]+/pytest-[0-9]+',
                       '<synthetic-tests>', value)
        value = re.sub(r'/(?:private/)?tmp/(dm-n4[^/\\"\s]*)',
                       r'<synthetic-tests>/\1', value)
        return value

    records = {}
    for path in sorted(directory.glob('N4*')):
        if not path.is_file() or path.name == 'N4-evidence-normalization.json':
            continue
        raw = path.read_bytes()
        destination = raw_dir / path.name
        if destination.exists() and destination.read_bytes() != raw:
            raise RuntimeError('raw evidence directory already contains a different stage; use a new directory')
        destination.write_bytes(raw)
        changed, body_overrides = [], []

        def normalize(value, pointer=''):
            if isinstance(value, list):
                return [normalize(item, f'{pointer}/{index}') for index, item in enumerate(value)]
            if isinstance(value, dict):
                result = {key: normalize(item, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
                          for key, item in value.items()}
                if isinstance(value.get('content'), str) and result['content'] != value['content']:
                    original = value['content'].encode('utf-8')
                    display = result['content'].encode('utf-8')
                    if value.get('sha256') != digest(original):
                        raise RuntimeError('raw body does not match its declared digest')
                    body_overrides.append({'pointer': pointer + '/content',
                        'declared_original_resource_sha256': value['sha256'],
                        'original_content_sha256': digest(original),
                        'normalized_display_content_sha256': digest(display),
                        'original_content_bytes': len(original), 'normalized_display_content_bytes': len(display)})
                return result
            if isinstance(value, str):
                result = portable(value)
                if result != value:
                    changed.append(pointer)
                return result
            return value

        if path.suffix == '.json':
            value = json.loads(raw)
            normalized = normalize(value)
            data = (json.dumps(normalized, ensure_ascii=False, indent=2) + '\n').encode() if changed else raw
        elif path.suffix == '.py':
            data = raw  # Runnable source is not a response sample or log.
        else:
            normalized = portable(raw.decode('utf-8'))
            if normalized != raw.decode('utf-8'):
                changed.append('text locator strings')
                if path.suffix == '.txt':
                    normalized = ('Portable evidence: locator strings normalized; raw hashes and exact originals '
                                  'are recorded in N4-evidence-normalization.json.\n\n' + normalized)
                data = normalized.encode()
            else:
                data = raw
        path.write_bytes(data)
        records[path.name] = {'original_sha256': digest(raw), 'original_bytes': len(raw),
            'normalized_sha256': digest(data), 'normalized_bytes': len(data),
            'normalized_locator_fields': changed, 'body_content_locator_overrides': body_overrides}

    manifest = {'scope': 'SYNTHETIC_ENGINEERING',
        'source_baseline_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip(),
        'normalization': 'Only locator strings are normalized. IDs, resource hashes, payload prose and measured counts are retained.',
        'placeholders': {'<checkout>': 'source checkout root', '<synthetic-project>': 'temporary synthetic project root',
                         '<synthetic-input>': 'temporary synthetic input directory', '<synthetic-tests>': 'temporary test evidence root'},
        'hash_boundary': 'Declared body hashes/byte lengths identify original runtime bytes. If an embedded JSON body contains an absolute locator, its display text changes only at that locator; both exact body hashes/lengths are listed below. Normalized display samples are not byte-for-byte replay payloads.',
        'raw_archive': 'External integration-input archive raw-evidence/N4/final; exact location supplied to the integration owner. manifest.json records original file SHA256 values.',
        'files': records}
    (raw_dir / 'manifest.json').write_text(json.dumps({'scope': 'SYNTHETIC_ENGINEERING',
        'files': {name: {'sha256': info['original_sha256'], 'bytes': info['original_bytes']}
                  for name, info in records.items()}}, ensure_ascii=False, indent=2) + '\n')
    target = directory / 'N4-evidence-normalization.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Preserved {len(records)} exact evidence files; normalized only locator strings.')


if __name__ == '__main__':
    main()
