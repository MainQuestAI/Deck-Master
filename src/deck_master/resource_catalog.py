"""Shared, stdlib-only catalog validation for runtime, build and installation.

This module describes registered files; it never executes their contents.
The build hook loads this same module without importing the runtime package.
"""
import json
from pathlib import Path, PurePosixPath

PUBLIC_SKILLS = ('deck-master', 'deck-content', 'deck-design', 'deck-review')
CATALOG_PATH = 'resource-catalog.json'
CATALOG_TARGET = 'deck_master/resources/skill/' + CATALOG_PATH
KINDS = {'instruction', 'example', 'template', 'data', 'script'}

# Immutable pre-catalog format, only for old release/task compatibility.
LEGACY_IDS = ('collaboration-routing', 'physical-units', 'style-calibration',
              'candidates-and-stages', 'icon-quality', 'visual-reference',
              'source-reading', 'content-methods', 'content-examples',
              'content-calibration', 'input-update', 'blueprint-svg', 'review-and-repair')


def needs_catalog_writer(task):
    return any(row['id'] not in LEGACY_IDS or row['relative_path'] != f"references/{row['id']}.md"
               for row in task.get('method_manifest', []))


def relative_path(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or PurePosixPath(value).is_absolute()
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError(f'invalid catalog relative path: {value!r}')
    return value


def safe_file(root, relative):
    root = Path(root)
    relative_path(relative)
    path = root
    if root.is_symlink():
        raise ValueError('catalog root symlink is forbidden')
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink():
            raise ValueError(f'catalog symlink is forbidden: {relative}')
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'missing or escaped catalog file: {relative}')
    return path


def validate_catalog(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'resources'}:
        raise ValueError('invalid resource catalog fields')
    if value['schema_version'] != 'method_catalog.v1' or not isinstance(value['resources'], list):
        raise ValueError('unsupported resource catalog')
    resources, paths = {}, set()
    required = {'id', 'relative_path', 'kind', 'owner', 'consumers', 'dependencies',
                'task_kinds', 'phases', 'review_units', 'readable'}
    for row in value['resources']:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError('invalid catalog resource fields')
        mid = row['id']
        if not isinstance(mid, str) or not mid or mid in resources:
            raise ValueError(f'unknown or duplicate catalog ID: {mid!r}')
        path = relative_path(row['relative_path'])
        if path in paths or path == CATALOG_PATH or path.split('/')[0] not in {'references', 'assets', 'scripts'}:
            raise ValueError(f'duplicate or unsupported catalog resource path: {path}')
        if row['kind'] not in KINDS or row['owner'] not in PUBLIC_SKILLS or type(row['readable']) is not bool:
            raise ValueError(f'invalid resource classification: {mid}')
        for key in ('consumers', 'dependencies', 'task_kinds', 'phases', 'review_units'):
            values = row[key]
            if (not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values)
                    or len(values) != len(set(values))):
                raise ValueError(f'invalid catalog {key}: {mid}')
        if not row['consumers'] or not set(row['consumers']) <= set(PUBLIC_SKILLS):
            raise ValueError(f'invalid resource consumers: {mid}')
        resources[mid] = row
        paths.add(path)
    for mid in (*LEGACY_IDS, 'installation'):
        row = resources.get(mid)
        if (row is None or row['relative_path'] != f'references/{mid}.md'
                or row['readable'] != (mid != 'installation')):
            raise ValueError(f'catalog must retain the existing resource: {mid}')
    # Validate the entire DAG, including resources not selected this time.
    active, done = set(), set()

    def visit(mid):
        if mid not in resources:
            raise ValueError(f'unknown catalog dependency: {mid}')
        if mid in active:
            raise ValueError(f'cyclic catalog dependency: {mid}')
        if mid in done:
            return
        active.add(mid)
        for dep in resources[mid]['dependencies']:
            if not resources.get(dep, {}).get('readable', False):
                raise ValueError(f'unknown or unreadable catalog dependency: {dep}')
            visit(dep)
        active.remove(mid)
        done.add(mid)
    for mid in resources:
        visit(mid)
    return resources


def load_catalog(root):
    return validate_catalog(json.loads(safe_file(root, CATALOG_PATH).read_bytes()))


def canonical_mapping(resources, *, include_catalog=True):
    mapping = {'deck_master/resources/skills/RESOLVER.md': 'skills/RESOLVER.md'}
    for skill in PUBLIC_SKILLS:
        target = 'deck_master/resources/skill' if skill == 'deck-master' else f'deck_master/resources/skills/{skill}'
        for name in ('SKILL.md', 'agents/openai.yaml'):
            mapping[f'{target}/{name}'] = f'skills/{skill}/{name}'
    for row in resources.values():
        relative = row['relative_path']
        mapping['deck_master/resources/skill/' + relative] = 'skills/deck-master/' + relative
    if include_catalog:
        mapping[CATALOG_TARGET] = 'skills/deck-master/' + CATALOG_PATH
    return mapping


def select(resources, selected, *, role, kind=None, phase=None, review_units=None):
    if selected is None:
        return ()
    if not isinstance(selected, (list, tuple)) or any(not isinstance(mid, str) for mid in selected):
        raise ValueError('selected_resource_ids must be a list of registered IDs')
    output, seen = [], set()
    if review_units is not None and (
            not isinstance(review_units, (list, tuple)) or any(
                not isinstance(u, str) and
                (not isinstance(u, dict) or not isinstance(u.get('kind'), str))
                for u in review_units)):
        raise ValueError('invalid resource review scope')
    units = {u if isinstance(u, str) else u['kind'] for u in (review_units or [])}

    def visit(mid):
        if mid in seen:
            return
        row = resources.get(mid)
        if not row or not row['readable']:
            raise ValueError(f'unknown or unreadable selected resource: {mid}')
        if (role not in row['consumers']
                or kind is not None and row['task_kinds'] and kind not in row['task_kinds']
                or row['phases'] and (kind is not None or phase is not None) and phase not in row['phases']
                or role == 'deck-review' and row['review_units'] and (not units or not units & set(row['review_units']))):
            raise ValueError(f'resource outside role/phase/scope: {mid}')
        seen.add(mid)
        for dependency in row['dependencies']:
            visit(dependency)
        output.append(mid)
    for mid in selected:
        visit(mid)
    return tuple(output)
