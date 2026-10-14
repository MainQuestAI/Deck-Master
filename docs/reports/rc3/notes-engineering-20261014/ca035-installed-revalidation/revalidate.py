"""Read-only old-pack revalidation under an observed exact candidate revision."""
from pathlib import Path
import hashlib
import importlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import zipfile

from PIL import Image
from deck_master.compiler import SvgInput, CompileOptions, compile_deck
from deck_master.compiler.svg import parse_svg
from deck_master.compiler.native import notes_records
from deck_master.export_sanitize import pptx, public_projection_safe
from deck_master.pipeline import readback, resolve_fonts, render_deck, executable
from deck_master.store import Store

HEAD = 'ca0351d2397ba154e9f77363bd0f325629eb0ebd'
TREE = '05191deede70f26e661b28f4221c3c0d00ef2ecf'
SOURCE = Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-ca035')
OBJECT_REPOSITORY = SOURCE
PACK = Path('/workspace/work/rc3/notes-local-acceptance')
OLDWORK = Path('/workspace/work/rc3/notes-local-acceptance-work')
HERE = Path(__file__).resolve().parent
INSTALL_MANIFEST = Path('/workspace/work/rc3/candidate-02-ca035/manifest.json')
SNAPSHOT = json.loads(INSTALL_MANIFEST.read_text())
EXPECTED_PACKAGE = Path(SNAPSHOT['module_path']).parent
if SNAPSHOT['source_sha'] != HEAD or SNAPSHOT['source_tree'] != TREE:
    raise RuntimeError('Isolated installation manifest differs from candidate')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(OBJECT_REPOSITORY), *args], text=True).strip()


def file_identity(path):
    return {'path': str(path), 'sha256': digest(path.read_bytes()), 'size': path.stat().st_size}


def pixels(path):
    with Image.open(path) as image:
        rgba = image.convert('RGBA')
        return {'dimensions': list(rgba.size), 'rgba_sha256': digest(rgba.tobytes())}


def render_identity(paths):
    return [{**file_identity(path), **pixels(path)} for path in paths]


def assert_source():
    if git('rev-parse', HEAD) != HEAD or git('rev-parse', HEAD + '^{tree}') != TREE:
        raise RuntimeError('Observed candidate head/tree changed')
    paths = git('ls-tree', '-r', '--name-only', HEAD, 'src/deck_master', 'skills/deck-master').splitlines()
    rows = []
    for name in paths:
        actual = (SOURCE / name).read_bytes()
        committed = subprocess.check_output(['git', '-C', str(OBJECT_REPOSITORY), 'show', HEAD + ':' + name])
        if actual != committed:
            raise RuntimeError('Package source differs from exact Git revision: ' + name)
        rows.append({'path': name, 'sha256': digest(actual), 'size': len(actual)})
    return rows


source_files = assert_source()
modules = []
for name in ('deck_master', 'deck_master.compiler.api', 'deck_master.compiler.native',
             'deck_master.pipeline', 'deck_master.export_sanitize', 'deck_master.exports', 'deck_master.store'):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    if not path.is_relative_to(EXPECTED_PACKAGE):
        raise RuntimeError('Execution borrowed another module origin: ' + str(path))
    modules.append({'module': name, **file_identity(path)})
distribution = importlib.metadata.distribution('deck-master')
installed_files = [file_identity(Path(distribution.locate_file(item)).resolve()) for item in distribution.files
                   if str(item).endswith(('.pth', '.json', '/METADATA', '/RECORD', '/entry_points.txt', '/WHEEL'))]
entry = Path(sys.executable).parent / 'deck-master'
if entry.is_file():
    installed_files.append(file_identity(entry))
editable = {'kind': 'isolated_wheel_install', 'distribution_name': distribution.metadata['Name'],
            'version': distribution.version, 'direct_url': json.loads(distribution.read_text('direct_url.json') or 'null'),
            'python': platform.python_version(), 'python_executable': file_identity(Path(sys.executable).resolve()),
            'module_origins': modules, 'installed_metadata_and_entrypoints': installed_files,
            'installed_identity_sha256': digest(json.dumps(installed_files, sort_keys=True, separators=(',', ':')).encode()),
            'wheel_identity': SNAPSHOT['wheel_sha256'], 'limitation': 'This process uses the actual isolated wheel installation under Python -I.'}
if editable['direct_url'] and editable['direct_url'].get('dir_info', {}).get('editable'):
    raise RuntimeError('Isolated validation unexpectedly used editable install')

old_hashes = json.loads((PACK / 'SHA256SUMS.json').read_text())
for row in old_hashes['files']:
    actual = PACK / row['path']
    if digest(actual.read_bytes()) != row['sha256'] or actual.stat().st_size != row['size']:
        raise RuntimeError('Original acceptance pack changed: ' + row['path'])
old_zip = OLDWORK / 'rc3-notes-local-acceptance.zip'
with zipfile.ZipFile(old_zip) as archive:
    for path in PACK.rglob('*'):
        if path.is_file() and archive.read(path.relative_to(PACK).as_posix()) != path.read_bytes():
            raise RuntimeError('Original archive differs from its pack: ' + str(path))

store = Store(OLDWORK / 'project')
doc = store.load_document()
pages = [store.read_object_json(entry['page']) for entry in doc['pages']]
trace = json.loads((PACK / 'compile-input.json').read_text())
inputs = []
parsed = []
records = []
for page, compiled_input in zip(pages, trace['pages'], strict=True):
    path = OLDWORK / (page['page_id'] + '.svg')
    raw = path.read_bytes()
    if digest(raw) != compiled_input['sha256'] or page['page_id'] != compiled_input['page_id']:
        raise RuntimeError('Original fixed input mismatch')
    inputs.append(SvgInput(page['page_id'], path, page.get('speaker_notes', '')))
    parsed.append(parse_svg(raw, page_id=page['page_id']))
    records.append({'page_id': page['page_id'], 'notes': page.get('speaker_notes', '')})
fonts = resolve_fonts(parsed)
native = compile_deck(inputs, CompileOptions(fonts=fonts), HERE / 'internal-recompiled-native')
native_readback = readback(native.pptx_path, parsed, pages)
if native_readback['status'] != 'pass':
    raise RuntimeError(native_readback)
native_render = render_deck(native.pptx_path, HERE / 'internal-recompiled-native-render', fonts=fonts)
public = pptx(native.pptx_path.read_bytes(), 'deck.pptx', notes=records, include_notes=True)
public_path = HERE / 'final-public-rebuilt.pptx'
public_path.write_bytes(public)
public_readback = readback(public_path, parsed, pages)
# Public sanitizer deliberately removes SVG atom shape names. The ordinary
# geometry/body readback is inspected separately; exact ordered notes/IDs are
# additionally compared as full values below, with no fuzzy string matching.
actual_notes = notes_records(public_path)
if [(r['page_id'], r['notes']) for r in actual_notes] != [(r['page_id'], r['notes']) for r in records]:
    raise RuntimeError('Final public full notes/identity mismatch')
public_render = render_deck(public_path, HERE / 'final-public-actual-render', fonts=fonts)
public_projection_safe(json.loads((PACK / 'manifest.json').read_text()), 'original-public-manifest')

wheel_path = next(Path('/workspace/work/rc3/candidate-02-ca035/dist').glob('*.whl'))
if digest(wheel_path.read_bytes()) != SNAPSHOT['wheel_sha256']:
    raise RuntimeError('Actual wheel bytes differ from installation manifest')
wheel_files = []
with zipfile.ZipFile(wheel_path) as wheel:
    for name in sorted(wheel.namelist()):
        if not name.startswith('deck_master/') or name.endswith('/'):
            continue
        raw = wheel.read(name)
        installed = EXPECTED_PACKAGE.parent / name
        source = (SOURCE / 'skills/deck-master' / name.removeprefix('deck_master/resources/skill/')
                  if name.startswith('deck_master/resources/skill/') else SOURCE / 'src' / name)
        if installed.read_bytes() != raw or source.read_bytes() != raw:
            raise RuntimeError('Wheel/source/install byte mismatch: ' + name)
        wheel_files.append({'path': name, 'sha256': digest(raw), 'size': len(raw)})
if len(wheel_files) != SNAPSHOT['verified_source_package_install_files']:
    raise RuntimeError('Actual package file count differs from root manifest')
editable['wheel_source_install_bytes'] = {'wheel': file_identity(wheel_path), 'files': wheel_files,
    'verified_file_count': len(wheel_files)}

original_native = OLDWORK / 'compiled' / 'deck.pptx'
with zipfile.ZipFile(original_native) as old, zipfile.ZipFile(native.pptx_path) as new:
    part_differences = [name for name in sorted(set(old.namelist()) | set(new.namelist()))
                        if name not in old.namelist() or name not in new.namelist() or old.read(name) != new.read(name)]
    zip_times_equal = [(i.filename, i.date_time) for i in old.infolist()] == [(i.filename, i.date_time) for i in new.infolist()]
result = {
    'status': 'EXACT_CANDIDATE_REVALIDATION_COMPLETE', 'source_commit': HEAD, 'source_tree': TREE,
    'old_pack_historical_identity': {'source_commit': None, 'source_tree': None,
        'status': 'NOT_FROZEN_AT_ORIGINAL_BUILD', 'warning': 'This new revalidation does not retroactively bind the old build to this commit.'},
    'execution_installation': editable,
    'source_package': {'provenance': 'Read-only detached Git snapshot verified against immutable Git commit objects, not live source', 'snapshot_path': str(SOURCE), 'files': source_files,
        'identity_sha256': digest(json.dumps(source_files, sort_keys=True, separators=(',', ':')).encode())},
    'original_pack': {'path': str(PACK), 'archive': file_identity(old_zip),
        'manifest': file_identity(PACK / 'SHA256SUMS.json'), 'all_files_verified': True},
    'actual_fixed_inputs': {'original_revision': doc['revision_id'],
        'compile_manifest': file_identity(PACK / 'compile-input.json'),
        'pages': [{'page_id': e['page_id'], 'page_ref': e['page']} for e in doc['pages']],
        'svg_files': [file_identity(item.path) for item in inputs],
        'fonts': [{'family': name, **file_identity(Path(path))} for name, path in fonts.items()]},
    'internal_native': {'original': file_identity(original_native), 'recompiled': file_identity(native.pptx_path),
        'same_raw_sha256': digest(original_native.read_bytes()) == digest(native.pptx_path.read_bytes()),
        'differing_uncompressed_parts': part_differences, 'zip_timestamps_equal': zip_times_equal,
        'raw_hash_difference_explanation': 'ZIP creation timestamps differ' if not part_differences and not zip_times_equal else None,
        'compile_manifest': file_identity(native.manifest_path), 'readback': native_readback,
        'actual_render': render_identity(native_render)},
    'final_public': {'original': file_identity(PACK / 'deck.pptx'), 'rebuilt': file_identity(public_path),
        'same_bytes': public == (PACK / 'deck.pptx').read_bytes(), 'full_ordered_notes': actual_notes,
        'readback': public_readback, 'actual_render': render_identity(public_render),
        'renderer_input': file_identity(public_path)},
    'original_render_scope': {'input': file_identity(original_native),
        'scope': 'Original actual-render PNGs were rendered from internal native PPTX, not the public sanitized copy.',
        'files': render_identity(sorted(PACK.glob('actual-render-*.png')))},
    'toolchain': [{'tool': name, 'path': executable(name)} for name in ('rsvg-convert', 'soffice', 'pdftoppm')],
    'wheel_snapshot_manifest': {**file_identity(INSTALL_MANIFEST), 'manifest': SNAPSHOT},
    'evidence_limits': ['Explicit synthetic L1 Page/SVG/Plan fixture; no real model author or human acceptance.',
                       'Native compile, public sanitizer reconstruction and public-file actual render/readback ran under exact observed isolated wheel candidate.',
                       'Observed Python -I module origins, immutable installation manifest and wheel/source/install bytes identify this actual execution.'],
    'desktop_notes_view': 'NOT_RUN', 'desktop_edit_save_reopen': 'NOT_RUN', 'human_acceptance': 'NOT_RUN',
}
if source_files != assert_source():
    raise RuntimeError('Source package bytes moved during revalidation')
if not result['final_public']['same_bytes']:
    result['status'] = 'REVALIDATED_PUBLIC_HASH_DIFFERENCE_NEEDS_EXPLANATION'
(HERE / 'revalidation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
(HERE / 'native-readback.json').write_text(json.dumps(native_readback, ensure_ascii=False, indent=2) + '\n')
(HERE / 'final-public-full-readback.json').write_text(json.dumps(public_readback, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'source_commit': HEAD, 'source_tree': TREE,
    'native_raw_equal': result['internal_native']['same_raw_sha256'], 'different_parts': part_differences,
    'public_same_bytes': result['final_public']['same_bytes'],
    'public_sha256': digest(public), 'public_readback_status': public_readback['status'],
    'public_render_count': len(public_render), 'report': str(HERE / 'revalidation.json')}, ensure_ascii=False))
