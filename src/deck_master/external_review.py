"""Strict external review packets: read source bytes, never initialize a run.

Mechanical observations are deliberately separate from professional review.
No renderer or reviewer is silently substituted by an archive/text reader.
"""
from __future__ import annotations

import io
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import stat
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree

from .models import ModelError, canonical_json_bytes, sha256_bytes, load_schema
from .operations import OperationError


def _path(value, field):
    if not isinstance(value, (str, os.PathLike)) or not str(value):
        raise ModelError(field, 'a local path is required')
    path = Path(os.path.abspath(Path(value).expanduser()))
    # Resolve only after checking every component, including the final name.
    for item in [path, *path.parents]:
        if item.is_symlink():
            raise ModelError(field, f'symlink is not an allowed source/output: {item}')
    return path


def _read(path):
    """Open a regular file without following a substituted final symlink."""
    _path(path, 'source')
    if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
        raise ModelError('source', f'not a regular file: {path}')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ModelError('source', f'not a regular file: {path}')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read()
        after = os.fstat(fd)
        _path(path, 'source')
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
        try:
            current = signature(path.stat(follow_symlinks=False))
        except OSError:
            current = None
        if signature(before) != signature(after) or signature(after) != current:
            # Retain the bytes actually observed, but make the final inventory
            # comparison fail even if a writer restores the original content.
            return data, ('source_changed_during_read', signature(before), signature(after), current)
        return data, signature(after)
    finally:
        os.close(fd)


def _inventory(roots):
    def fail(error):
        raise ModelError('source', 'source directory cannot be completely read') from error
    files, directories = set(), []
    for root in roots:
        _path(root, 'source')
        if root.is_dir():
            directories.append(root)
            for directory, names, filenames in os.walk(root, followlinks=False, onerror=fail):
                current = Path(directory)
                for name in names:
                    _path(current / name, 'source')
                for name in filenames:
                    files.add(_path(current / name, 'source'))
        elif root.is_file():
            files.add(root)
        else:
            raise FileNotFoundError(str(root))
    entries, signatures, contents = [], {}, {}
    for path in sorted(files, key=str):
        try:
            data, signature = _read(path)
        except OSError as exc:
            raise ModelError('source', f'source file cannot be read safely: {path}') from exc
        uri = path.as_uri()
        entries.append({'source_uri': uri, 'sha256': sha256_bytes(data), 'size': len(data),
                        'media_type': mimetypes.guess_type(path.name)[0] or 'application/octet-stream'})
        signatures[uri] = signature
        contents[uri] = data
    # Empty directories and added/deleted paths participate in unchanged checks.
    for root in directories:
        for directory, names, _ in os.walk(root, followlinks=False, onerror=fail):
            for path in (Path(directory), *(Path(directory) / name for name in names)):
                s = path.stat(follow_symlinks=False)
                signatures[path.as_uri() + '/'] = (s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns)
    return entries, signatures, contents


def _source(source):
    revision = None
    if isinstance(source, (str, os.PathLike)):
        roots = [_path(source, 'source')]
        kind = 'project' if (roots[0] / '.deckmaster/current.json').is_file() else ('fileset' if roots[0].is_dir() else 'file')
    elif isinstance(source, dict):
        unknown = set(source) - {'kind', 'path', 'files', 'revision'}
        if unknown:
            raise ModelError('source', f'unknown source fields: {sorted(unknown)}')
        kind, revision = source.get('kind'), source.get('revision')
        if kind == 'fileset':
            if 'path' in source or revision is not None or not isinstance(source.get('files'), list) or not source['files']:
                raise ModelError('source/files', 'an explicit nonempty file set is required')
            roots = [_path(value, 'source/files') for value in source['files']]
            if any(not path.is_file() for path in roots):
                raise ModelError('source/files', 'file sets contain regular files only')
        elif kind in ('project', 'file'):
            if 'files' in source or (kind == 'file' and revision is not None):
                raise ModelError('source', 'fields do not match source kind')
            roots = [_path(source.get('path'), 'source/path')]
        else:
            raise ModelError('source/kind', 'expected project, file or fileset')
    elif isinstance(source, list):
        return _source({'kind': 'fileset', 'files': source})
    else:
        raise ModelError('source', 'expected local source path or explicit source descriptor')
    if len(roots) != len(set(roots)):
        raise ModelError('source/files', 'duplicate source paths')
    if kind == 'file' and not roots[0].is_file():
        raise ModelError('source/path', 'file source must be a regular file')
    if kind == 'project' and roots[0].exists() and not roots[0].is_dir():
        raise ModelError('source/path', 'project source must be a project directory')
    return kind, roots, revision


def _output(path, roots):
    if path is None:
        return None
    target = _path(path, 'report_output')
    boundaries = set(roots)
    for root in roots:
        boundaries.update(parent for parent in root.parents if (parent / '.deckmaster/current.json').is_file())
    for root in boundaries:
        if target == root or target in root.parents or (root.is_dir() and root in target.parents):
            raise ModelError('report_output', 'report output must be outside every source, without overlap')
    if target.exists():
        raise ModelError('report_output', 'report output already exists; choose a new path')
    return target


def _publish(target, payload):
    """Exclusive creation through held directories; no ancestor symlink race."""
    if os.open not in os.supports_dir_fd or not hasattr(os, 'O_DIRECTORY'):
        raise ModelError('report_output', 'strict output creation requires directory descriptor support; use the inline packet')
    directory = os.open(target.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in target.parent.parts[1:]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0), dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
                     0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8') + b'\n')
    finally:
        os.close(directory)


def _pptx(data):
    """Bounded archive observations, without extracting or executing content."""
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('duplicate archive members')
            parts = [name for name in names if re.fullmatch(r'ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml', name)]
            if len(parts) > 2000 or any(archive.getinfo(n).file_size > 8_000_000 for n in parts):
                raise ValueError('readback coverage limit exceeded')
            texts = []
            for name in sorted(parts):
                root = ElementTree.fromstring(archive.read(name))
                text = '\n'.join(item.text or '' for item in root.iter() if item.tag == '{http://schemas.openxmlformats.org/drawingml/2006/main}t')
                texts.append({'part': name, 'text': text[:16000], 'truncated': len(text) > 16000})
            return {'kind': 'pptx_archive_readback', 'status': 'observed',
                    'slide_count': len([n for n in parts if n.startswith('ppt/slides/')]),
                    'notes_part_count': len([n for n in parts if n.startswith('ppt/notesSlides/')]),
                    'parts': texts, 'visual_review': 'not_evaluated'}
    except (BadZipFile, ValueError, ElementTree.ParseError, KeyError, RuntimeError) as exc:
        return {'kind': 'pptx_archive_readback', 'status': 'unreadable', 'detail': str(exc), 'visual_review': 'not_evaluated'}


def _observe(entries, contents):
    observations, has_pptx = [], False
    for entry in entries:
        uri, data = entry['source_uri'], contents[entry['source_uri']]
        suffix = Path(uri).suffix.lower()
        if suffix == '.pptx':
            value, has_pptx = _pptx(data), True
        elif suffix in ('.txt', '.md', '.json', '.csv', '.tsv', '.svg'):
            try:
                text = data.decode('utf-8')
                value = {'kind': 'text_readback', 'status': 'observed', 'text': text[:16000], 'truncated': len(text) > 16000}
            except UnicodeDecodeError:
                value = {'kind': 'text_readback', 'status': 'unreadable', 'detail': 'source is not UTF-8'}
        else:
            value = {'kind': 'file_integrity', 'status': 'observed', 'detail': 'bytes hashed; content not evaluated'}
        observations.append({'source_uri': uri, 'sha256': entry['sha256'], **value})
    return observations, has_pptx


def evaluate(source, *, source_sha256=None, scope, persistence='none', report_output=None, adapter_context=None):
    """Create an external packet from immutable observed bytes, with zero source writes.

    No JSON or opaque context supplies reviewer execution to this reader. A
    subsequent trusted reviewer can submit its report through the import service.
    """
    if persistence != 'none':
        raise ModelError('persistence', 'strict external evaluation requires persistence=none')
    if not isinstance(scope, dict):
        raise ModelError('scope', 'an explicit scope object is required')
    from jsonschema import Draft202012Validator
    schema = load_schema('collaboration')
    validator = Draft202012Validator({'$ref': '#/$defs/scope', '$defs': schema['$defs']})
    problem = next(validator.iter_errors(scope), None)
    if problem is not None:
        raise ModelError('scope/' + '/'.join(str(p) for p in problem.absolute_path), problem.message)
    if (scope['page_manifest_ref'] is not None or scope['external_artifact_ref'] is not None
            or scope['allow_page_membership_change'] or scope['allow_page_order_change']):
        raise ModelError('scope', 'external evaluation uses source URIs, without Store Refs or write permissions')
    if len(scope['page_ids']) != len(set(scope['page_ids'])) or len(scope['layers']) != len(set(scope['layers'])):
        raise ModelError('scope', 'duplicate page ids or layers')
    from .collaboration_api import _reject_context
    _reject_context(scope)
    kind, roots, revision = _source(source)
    target = _output(report_output, roots)
    entries, signatures, contents = _inventory(roots)
    if not entries:
        raise ModelError('source', 'source contains no readable files')
    project_id, artifact_revision = None, None
    selected = entries
    subject_uris = {entry['source_uri'] for entry in entries}
    if kind == 'project':
        from .snapshots import load_snapshot
        from .store import Store
        document = load_snapshot(Store(roots[0]), revision)
        project_id, artifact_revision = document['project_id'], document['revision_id']
        if set(scope['page_ids']) - {page['page_id'] for page in document['pages']}:
            raise ModelError('scope/page_ids', 'page id is absent from the selected project snapshot')
        wanted = set()
        def collect(value):
            if isinstance(value, dict):
                if set(value) == {'path', 'sha256'}:
                    path = roots[0] / value['path']
                    uri = path.as_uri()
                    if uri not in contents or sha256_bytes(contents[uri]) != value['sha256']:
                        raise ModelError('source/ref', 'snapshot object is missing or its hash changed')
                    if uri not in wanted:
                        wanted.add(uri)
                        if path.suffix == '.json':
                            try:
                                collect(json.loads(contents[uri]))
                            except (ValueError, UnicodeDecodeError) as exc:
                                raise ModelError('source/ref', 'snapshot object is unreadable') from exc
                else:
                    for item in value.values():
                        collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
        refs = [document.get('narrative'), document.get('content_plan'), *document['outputs'].values()]
        refs += [page.get(key) for page in document['pages'] if page['page_id'] in scope['page_ids']
                 for key in ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview')]
        refs += [row.get(key) for row in document.get('sources', []) for key in ('original', 'extract')]
        subject_uris = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            collect(ref)
            uri = (roots[0] / ref['path']).as_uri()
            subject_uris.add(uri)
            if ref['path'].endswith('.json'):
                obj = json.loads(contents[uri])
                if isinstance(obj, dict) and isinstance(obj.get('file'), dict):
                    subject_uris.add((roots[0] / obj['file']['path']).as_uri())
        selected = [entry for entry in entries if entry['source_uri'] in wanted]
    elif scope['page_ids']:
        raise ModelError('scope/page_ids', 'external files do not imply stable project page ids')
    manifest = {'source_kind': kind, 'original_project_id': project_id,
                'artifact_revision_id': artifact_revision, 'files': entries}
    digest = sha256_bytes(canonical_json_bytes(manifest))
    source_digest = entries[0]['sha256'] if kind == 'file' else digest
    if source_sha256 is not None and source_sha256 != source_digest:
        raise ModelError('source_sha256', 'declared source SHA256 does not match the observed source')
    observations, has_pptx = _observe(selected, contents)
    renderer = bool(shutil.which('soffice') and shutil.which('pdftoppm'))
    limitations = [{'code': 'needs_reviewer', 'detail': 'No independent reviewer executed; professional dimensions remain not_evaluated.'}]
    if has_pptx:
        limitations.append({'code': 'visual_review_not_evaluated', 'detail': 'Archive text/notes readback does not inspect rendered slide appearance.'})
        if not renderer:
            limitations.append({'code': 'needs_tool', 'detail': 'PPT rendering requires soffice and pdftoppm; no renderer fallback was used.'})
    try:
        after_entries, after_signatures, _ = _inventory(roots)
        unchanged = entries == after_entries and signatures == after_signatures
    except (OSError, ModelError, OperationError):
        unchanged = False
    if not unchanged:
        limitations.append({'code': 'source_changed', 'detail': 'Source inventory changed during evaluation; this packet cannot be imported.'})
    subjects = [{'source_uri': entry['source_uri'], 'sha256': entry['sha256'], 'media_type': entry['media_type']}
                for entry in selected if entry['source_uri'] in subject_uris]
    from . import __version__
    report = {'schema_version': 'external_review_report.v1', 'source_manifest': manifest,
              'source_manifest_sha256': digest, 'source_unchanged': unchanged, 'scope': scope,
              'subjects': subjects, 'engineering_observations': observations, 'reviews': [],
              'provenance': {'executor_type': 'tool', 'assurance': 'engineering',
                             'reviewer_executed': False, 'trust_boundary': 'local_bytes_only',
                             'implementation': {'module': __name__, 'package_version': __version__,
                                                'sha256': sha256_bytes(Path(__file__).read_bytes())},
                             'observations_sha256': sha256_bytes(canonical_json_bytes(observations)),
                             'methods': [], 'author_exclusion_set': {'status': 'unknown', 'execution_refs': []},
                             'renderer': {'available': renderer, 'executed': False}},
              'limitations': limitations, 'evidence_level': 'engineering'}
    # Read-only handoff: these are returned bytes, never an executed review or
    # provenance.methods application claim. Scope remains the caller's scope.
    from .method_resources import read_methods, method_release
    layers = set(scope.get('layers') or [])
    units = set()
    if layers & {'narrative', 'plan', 'page_copy'}:
        units.add('content')
    if 'speech' in layers:
        units.add('speech')
    if layers & {'design', 'blueprint', 'svg', 'output'}:
        units.update({'blueprint_fidelity', 'readability'})
    review_methods = read_methods('review', review_units=sorted(units) if units else None)
    external_report = {'report': report, 'report_sha256': sha256_bytes(canonical_json_bytes(report))}
    if target is not None:
        _output(target, roots)
        try:
            _publish(target, external_report)
        except OSError as exc:
            raise ModelError('report_output', 'report output cannot be exclusively created; choose a new external path') from exc
    status = 'source_changed' if not unchanged else ('needs_tool' if has_pptx and not renderer else 'needs_reviewer')
    return {'status': status, 'source_hashes': entries, 'source_sha256': source_digest,
            'external_report': external_report, 'report_output': str(target) if target else None,
            'evidence_level': 'engineering', 'limitations': limitations,
            'method_context': {'methods': review_methods, 'method_release': method_release(review_methods),
                               'consumption': 'runtime_returned_bytes', 'host_application': 'not_recorded'},
            'artifact_revision_id': artifact_revision, 'control_revision_id': None,
            'next_action': 'repeat_from_fixed_source' if not unchanged else 'review_the_readable_packet'}
