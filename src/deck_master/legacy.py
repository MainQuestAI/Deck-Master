"""Read-only legacy import (spec 12): known v1 drafts and HD runs into a new
project copy. The source directory is never written, never initialised, and
never executed; old completed/pass strings are history only, never a new
review pass. Unknown structures are reported with concrete field pointers.
"""
from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path

from .content import check_page
from .models import bump_revision, default_design_context, new_document, validate_document_semantics
from .store import Store

V1_PAGE_SCHEMA = 'deck_page_package.v1'
V2_PAGE_SCHEMA = 'deck_page_package.v2'
MEDIA_SUFFIXES = {'.svg', '.png', '.jpg', '.jpeg', '.pptx'}
HD_MARKERS = ('preview_manifest.json', 'narrative_plan.json', 'page_tasks.json')
ZERO_HASH = '0' * 64
# v1 page top-level metadata keys this importer deliberately does NOT carry
# into Page v2 (recorded in the import report instead of being dropped).
V1_PRESERVED_METADATA = ('internal_only', 'provenance')
# v1 page top-level keys that must be explicitly normalized, never dropped.
V1_REQUIRED_NORMALIZATION = ('asset_bindings', 'citations')


class LegacyError(ValueError):
    """Base for controlled legacy-import failures."""


class LegacyFormatError(LegacyError):
    """The input matches no known legacy schema; fields spell out what was found."""


class LegacyNormalizationRequired(LegacyError):
    """Known format with structures this importer cannot map automatically."""

    def __init__(self, unknown_fields):
        self.unknown_fields = list(unknown_fields)
        super().__init__('legacy import needs normalization: ' + '; '.join(self.unknown_fields))


class LegacySourceModified(LegacyError):
    """The source directory changed during import; the copy is refused."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    """Relative-path → digest for every file under root (read-only basis).

    A single-file root snapshots just that file. Symbolic links are recorded
    by their own link target, not the target's content, so a link pointing
    outside the tree can never attribute external changes to the source
    (spec 12.1 read-only semantics).
    """
    if root.is_file():
        return {root.name: _sha256_file(root)}
    entries = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file() and not path.is_symlink():
            continue
        relative = str(path.relative_to(root))
        if path.is_symlink():
            entries[relative] = 'symlink:' + os.readlink(path)
        else:
            entries[relative] = _sha256_file(path)
    return entries


def _classify(root: Path) -> tuple[str, dict]:
    """Explicit schema/version discrimination — never substring guessing."""
    if root.is_file():
        try:
            raw = json.loads(root.read_text(encoding='utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LegacyFormatError(f'{root}: not parseable JSON ({exc})') from exc
        if isinstance(raw, dict) and raw.get('schema_version') == V1_PAGE_SCHEMA:
            return 'v1_page_file', {'pages': [raw]}
        found = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        raise LegacyFormatError(
            f'{root}: 未识别的单文件格式(schema_version 缺失或非 {V1_PAGE_SCHEMA}); 顶层字段: {found}')

    hd = {name[:-5]: json.loads((root / name).read_text(encoding='utf-8'))
          for name in HD_MARKERS if (root / name).is_file()}
    v1_pages = sorted(root.glob('*.v1.json')) + sorted(root.glob('pages/*.json'))
    detected_v1 = []
    for candidate in v1_pages:
        try:
            raw = json.loads(candidate.read_text(encoding='utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and raw.get('schema_version') == V1_PAGE_SCHEMA:
            detected_v1.append(raw)
    if {'preview_manifest', 'narrative_plan', 'page_tasks'} <= set(hd):
        return 'hd_run', hd
    if detected_v1:
        return 'v1_draft_dir', {'pages': detected_v1}
    present = sorted(p.name for p in root.iterdir())
    raise LegacyFormatError(
        f'{root}: 既不是 HD run(缺 {[m for m in ("preview_manifest", "narrative_plan", "page_tasks") if m not in hd]})'
        f'也没有 {V1_PAGE_SCHEMA} 页包; 目录内容: {present}')


def _map_v1_block(block: dict, index: int, pointer: str, unknown: list) -> dict | None:
    block_id = block.get('id') or f'b{index + 1}'
    if 'text' in block and 'items' not in block:
        return {'id': block_id, 'type': 'paragraph', 'text': block['text']}
    if 'items' in block and 'text' in block:
        unknown.append(f'{pointer} (同时含 text 与 items,无法唯一映射)')
        return None
    if 'items' in block:
        items = []
        for item_index, item in enumerate(block.get('items') or []):
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                entry = {'id': item.get('id') or f'i{item_index + 1}', 'text': item['text']}
                if item.get('items'):
                    nested = [{'text': str(child.get('text', child))} for child in item['items']]
                    entry['items'] = nested
                items.append(entry)
            else:
                unknown.append(f'{pointer}/items/{item_index}')
                return None
        mapped = {'id': block_id, 'type': 'bullets', 'items': items}
        if isinstance(block.get('heading'), str):
            mapped['heading'] = block['heading']
        return mapped
    unknown.append(pointer)
    return None


def _map_v1_page(page: dict, unknown: list) -> dict:
    pointer_base = f"pages[{page.get('page_id', '?')}]"
    for key in V1_REQUIRED_NORMALIZATION:
        if page.get(key):
            unknown.append(f'{pointer_base}/{key} (顶层字段需显式规范化,不静默丢弃)')
    visible = page.get('customer_visible') or {}
    blocks = []
    for index, block in enumerate(visible.get('body_blocks') or []):
        mapped = _map_v1_block(block, index, f'{pointer_base}/customer_visible/body_blocks/{index}', unknown)
        if mapped is None:
            continue
        blocks.append(mapped)
    customer = {'title': visible.get('title') if isinstance(visible.get('title'), str) else '',
                'body_blocks': blocks}
    if isinstance(visible.get('subtitle'), str):
        customer['subtitle'] = visible['subtitle']
    for key in ('labels', 'footnotes'):
        values = []
        for item_index, item in enumerate(visible.get(key) or []):
            if isinstance(item, str):
                values.append({'id': f'{key[:-1]}-{item_index + 1}', 'text': item})
            elif isinstance(item, dict) and isinstance(item.get('text'), str):
                values.append({'id': item.get('id') or f'{key[:-1]}-{item_index + 1}', 'text': item['text']})
            else:
                unknown.append(f'{pointer_base}/customer_visible/{key}/{item_index}')
        if values:
            customer[key] = values
    visual = {}
    source_visual = page.get('visual_spec') or {}
    if isinstance(source_visual.get('nodes'), list):
        nodes = []
        for node_index, node in enumerate(source_visual['nodes']):
            if isinstance(node, dict) and node.get('node_id') and node.get('status') and node.get('label_ref'):
                nodes.append(node)
            else:
                unknown.append(f'{pointer_base}/visual_spec/nodes/{node_index} '
                               '(缺 node_id/status/label_ref,不静默过滤)')
        if nodes:
            visual['nodes'] = nodes
    if isinstance(source_visual.get('edges'), list):
        edges = []
        for edge_index, edge in enumerate(source_visual['edges']):
            if isinstance(edge, dict) and edge.get('edge_id') and edge.get('from') and edge.get('to') \
                    and edge.get('direction') and edge.get('relationship'):
                edges.append(edge)
            else:
                unknown.append(f'{pointer_base}/visual_spec/edges/{edge_index} '
                               '(缺 edge_id/from/to/direction/relationship,不静默过滤)')
        if edges:
            visual['edges'] = edges
    if isinstance(source_visual.get('intent'), str):
        visual['intent'] = source_visual['intent']
    visual['reference_mode'] = 'new_design'
    mapped = {'schema_version': V2_PAGE_SCHEMA, 'page_id': page.get('page_id'),
              'customer_visible': customer, 'visual_spec': visual}
    if isinstance(page.get('speaker_notes'), str):
        mapped['speaker_notes'] = page['speaker_notes']
    return mapped


def _map_hd_run(hd: dict, unknown: list) -> list[dict]:
    planning = {task.get('beat_id'): (task.get('planning') or {})
                for task in (hd.get('page_tasks', {}).get('tasks') or [])}
    beats = {beat.get('beat_id'): beat for beat in (hd.get('narrative_plan', {}).get('beats') or [])}
    pages = []
    for preview in hd.get('preview_manifest', {}).get('pages') or []:
        beat_id = preview.get('beat_id') or preview.get('page_id')
        if not beat_id:
            raise LegacyFormatError('preview_manifest.pages[]: beat_id 与 page_id 双缺,无法定位页')
        plan = planning.get(beat_id) or {}
        core = plan.get('core_claim') or plan.get('content_goal')
        title = plan.get('page_title') or preview.get('title') or beat_id
        body = []
        if isinstance(core, str) and core.strip():
            body.append({'id': 'b1', 'type': 'paragraph', 'text': core})
        for key in sorted(set(plan) - {'page_title', 'role', 'core_claim', 'content_goal',
                                       'evidence_need', 'visual_need', 'density',
                                       'preferred_archetype', 'workspace_refs',
                                       'quality_requirements', 'gaps'}):
            unknown.append(f'page_tasks.tasks[{beat_id}].planning.{key}')
        beat = beats.get(beat_id) or {}
        pages.append({
            'schema_version': V2_PAGE_SCHEMA, 'page_id': beat_id,
            'customer_visible': {'title': title, 'body_blocks': body},
            'visual_spec': {'intent': f"legacy hd run page (role {preview.get('narrative_role') or beat.get('role') or 'unknown'})",
                            'reference_mode': 'new_design'},
        })
    return pages


def _media_files(root: Path) -> list[Path]:
    skip_dirs = {'.git', '.deckmaster', 'node_modules', '__pycache__'}
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        if any(part in skip_dirs or part.startswith('.') for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def inspect_legacy(input_path) -> dict:
    """Dry-run plan: pages, media, design declarations, unknowns, source hashes."""
    root = Path(input_path).expanduser()
    if not root.exists():
        raise LegacyFormatError(f'{root}: path does not exist')
    format_name, payload = _classify(root)
    unknown: list = []
    if format_name == 'hd_run':
        pages = _map_hd_run(payload, unknown)
    else:
        pages = [_map_v1_page(page, unknown) for page in payload['pages']]
    media_root = root if root.is_dir() else root.parent
    media = [{'path': str(path.relative_to(media_root)), 'sha256': _sha256_file(path),
              'suffix': path.suffix.lower()} for path in _media_files(media_root)]
    fingerprints = []
    if format_name != 'hd_run':
        fingerprints = [(page.get('page_id'), (page.get('source_fingerprint') or ''))
                        for page in payload['pages']]
    zero = [page_id for page_id, fingerprint in fingerprints if fingerprint == ZERO_HASH]
    if zero:
        raise LegacyFormatError(f'全零假 hash 拒绝: pages {zero} 的 source_fingerprint 为 64 个 0')
    legacy_status = []
    if format_name == 'hd_run':
        legacy_status = [{'page_id': p.get('page_id') or p.get('beat_id'), 'status': p.get('status')}
                         for p in payload['preview_manifest'].get('pages') or []]
    else:
        legacy_status = [{'page_id': p.get('page_id'), 'status': p.get('status')}
                         for p in payload['pages']]
    preserved = {}
    if format_name != 'hd_run':
        for page in payload['pages']:
            kept = {key: page.get(key) for key in V1_PRESERVED_METADATA if key in page}
            if kept:
                preserved[page.get('page_id')] = kept
    return {'format': format_name,
            'page_count': len(pages),
            'page_ids': [page['page_id'] for page in pages],
            'unknown_fields': sorted(set(unknown)),
            'media': media,
            'claimed_source_fingerprints': {pid: fp for pid, fp in fingerprints if fp},
            'deliberately_not_carried': preserved,
            'legacy_status': legacy_status,
            'source_original_sha256': _sha256_file(root) if root.is_file() else None,
            'notes': ['旧 completed/pass 字符串仅历史说明,不生成新 Review 通过',
                      '缺原文 original_sha256 允许 null;未知原 hash 不追认为旧原文']}


def _check_output_location(root: Path, out: Path) -> None:
    root_resolved = root.resolve()
    out_resolved = out.resolve()
    if out_resolved == root_resolved or root_resolved in out_resolved.parents \
            or out_resolved in root_resolved.parents:
        raise LegacyError(f'--out {out} 与源 {root} 相同或互为子目录;import 只写新副本,拒绝就地/嵌套输出')


def import_legacy(input_path, out_path, *, inspect_only: bool = False) -> dict:
    root = Path(input_path).expanduser()
    out = Path(out_path).expanduser()
    snapshot_root = root
    before = snapshot(snapshot_root)
    plan = inspect_legacy(root)
    if inspect_only:
        return {'status': 'inspected', **plan}
    if plan['unknown_fields']:
        raise LegacyNormalizationRequired(plan['unknown_fields'])
    _check_output_location(root, out)
    created: Path | None = None
    try:
        if out.exists() and any(out.iterdir()):
            raise LegacyError(f'{out}: output directory must be fresh')

        store = Store(out)
        created = store.project_root
        document = new_document(project_id=out.name, task={'title': f'Legacy import of {root.name}',
                                                            'brief': f'Read-only import from {root}'})
        store.init_project(document, operation_id='legacy-import-init')
        design = default_design_context()
        work = store.staging_dir / 'legacy-import'
        work.mkdir(parents=True, exist_ok=True)

        media_root = root if root.is_dir() else root.parent
        media_artifacts = {}
        for item in plan['media']:
            source = media_root / item['path']
            copied = work / Path(item['path']).name
            copied.write_bytes(source.read_bytes())
            role = 'pptx' if item['suffix'] == '.pptx' else ('svg' if item['suffix'] == '.svg' else 'asset')
            ref = _import_media_artifact(store, copied, role, item['path'])
            media_artifacts[item['path']] = (ref, role)

        format_name = plan['format']
        _, payload = _classify(root)
        if format_name == 'hd_run':
            pages_payload = _map_hd_run(payload, [])
        else:
            pages_payload = [_map_v1_page(page, []) for page in payload['pages']]

        page_entries = []
        for mapped in pages_payload:
            normalized = check_page(mapped)
            page_ref = store.put_json_object(normalized)
            svg_ref = None
            for rel_path, (ref, role) in media_artifacts.items():
                stem = Path(rel_path).stem
                if role == 'svg' and (stem == normalized['page_id'] or stem.startswith(normalized['page_id'])):
                    svg_ref = ref
                    break
            page_entries.append({'page_id': normalized['page_id'], 'page': page_ref, 'blueprint': None,
                                 'svg': svg_ref, 'svg_preview': None, 'ppt_preview': None})

        report = {'format': format_name, 'plan': plan,
                  'pptx_artifacts': [rel for rel, (ref, role) in media_artifacts.items() if role == 'pptx'],
                  'provenance_note': '旧 completed/pass/reviewer 字符串仅历史说明;新 Review 状态保持未评估(legacy 未验证)'}
        report_path = work / 'legacy-import-report.json'
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        report_ref = _import_media_artifact(store, report_path, 'source_extract', 'legacy-import-report.json')

        current = store.load_document()
        bumped = bump_revision(current, {'operation_id': 'legacy-import-pages', 'kind': 'content_update',
                                         'description': f'legacy import from {root.name}', 'read_set': []})
        bumped['pages'] = page_entries
        bumped['design_context'] = design
        bumped['sources'] = [{
            'source_id': 'legacy-import-1', 'name': root.name,
            'original_uri': str(root.resolve()),
            'original_sha256': plan['source_original_sha256'],
            'format': plan['format'], 'extract': report_ref,
            'external_use': 'unspecified',
            'restriction': 'legacy import; 旧 pass 不继承; 缺原文时仅已存 extract/媒体可用',
            'locator_scheme': 'none',
        }]
        validate_document_semantics(bumped)
        store.commit_change(base_revision=current['revision_id'], document=bumped,
                            operation_id='legacy-import-pages')

        after = snapshot(snapshot_root)
        if after != before:
            raise LegacySourceModified(f'{root}: source files changed during import; refusing the copy')
        return {'status': 'imported', 'project': str(out), 'revision_id': bumped['revision_id'],
                'page_count': len(page_entries), 'format': plan['format'], 'report': report}
    except Exception:
        if created is not None and created.exists() and not inspect_only:
            import shutil
            shutil.rmtree(created, ignore_errors=True)
        raise


def _import_media_artifact(store: Store, path: Path, role: str, original_rel_path: str) -> dict:
    """Store imported media with an honest legacy_import provenance (spec 12);
    the original relative path is kept in limitations, never as a live path."""
    import uuid

    from deck_master.models import canonical_json_bytes  # local import avoids cycles
    from deck_master.tasks import _utc_now_iso
    from deck_master.models import validate_artifact_semantics, sha256_bytes

    suffix = path.suffix.lower()
    media = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
             '.json': 'application/json'}.get(suffix, 'application/octet-stream')
    data = path.read_bytes()
    file_ref = store.put_blob(data, ext=suffix[1:] if suffix else 'bin')
    artifact = {'schema_version': 'deck_artifact.v1',
                'artifact_id': f'{role}-{uuid.uuid4().hex[:12]}',
                'page_id': None, 'role': role, 'file': file_ref, 'media_type': media,
                'created_at': _utc_now_iso(), 'dependencies': [], 'derived_from': [],
                'provenance': {'source_type': 'legacy_import', 'tool': 'import-legacy'},
                'limitations': [f'original relative path in source run: {original_rel_path}']}
    if role == 'pptx':
        artifact['editability'] = 'unknown'
    validate_artifact_semantics(artifact)
    return store.put_json_object(artifact)
