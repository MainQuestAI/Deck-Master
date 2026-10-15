"""Root actual p04 engineering observation; never a full-deck delivery action."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import traceback
import zipfile
import xml.etree.ElementTree as ET

BASE = Path('/workspace/work/rc3/native-image-pilot-03')
PROJECT = BASE / 'run-02-project'
INSTALL = Path('/workspace/work/rc3/candidate-03-5dbdf72')
EXPECTED = '5dbdf72089d6625449a23a52ef3e23859c597b4e'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    from deck_master import pipeline, service
    from deck_master.compiler import CompileOptions, SvgInput, compile_deck
    from deck_master.compiler.svg import parse_svg
    from deck_master.store import Store

    action = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        manifest_bytes = (INSTALL / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_bytes)
        assert manifest['source_sha'] == EXPECTED
        assert digest(manifest_bytes) == 'bcb668040f2c5e7cd0613b792517f6ec055f1d5925b5e5a582c076e67dfdbb10'
        assert str(INSTALL / 'prefix/.deck-master/releases' / manifest['release_id']) in service.__file__
        save(out / 'reader-identity.json', {
            'source_sha': EXPECTED, 'manifest_sha256': digest(manifest_bytes),
            'release_id': manifest['release_id'], 'python': sys.executable,
            'service': service.__file__, 'pipeline': pipeline.__file__,
            'compiler': sys.modules['deck_master.compiler'].__file__,
            'assurance': 'root actual installed engineering observation; host_attested',
            'actual_image_origin': '8057905162f20926cfc1a0a96252bc6745f4e700',
            'whole_deck_delivery': False, 'human_desktop_verification': None,
        })
        store = Store(PROJECT)
        before = store.load_document()
        save(out / 'before-document.json', before)
        entry = next(e for e in before['pages'] if e['page_id'] == 'p04')
        page = store.read_object_json(entry['page'])
        assert entry['page']['sha256'] == 'cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b'
        assert len(before['pages']) == 8
        save(out / 'fixed-page.json', page)
        artifact = store.read_object_json(entry['svg'])
        data = store.read_object_bytes(artifact['file'])
        (out / 'actual-p04.svg').write_bytes(data)
        save(out / 'actual-svg-artifact.json', artifact)
        parsed = parse_svg(data, page_id='p04', assets={})
        save(out / 'actual-svg-ir.json', parsed)
        check_status = 'not_evaluated'
        if action == 'preview':
            preview_ref = pipeline.preview_svg_page(PROJECT, 'p04')
            preview_artifact = store.read_object_json(preview_ref)
            (out / 'actual-p04-preview.png').write_bytes(store.read_object_bytes(preview_artifact['file']))
            save(out / 'preview-result.json', {'ref': preview_ref, 'artifact': preview_artifact})
            assert preview_artifact['derived_from'] == [entry['svg']]
            assert preview_artifact['dependencies'] == [
                {'kind': 'svg', 'identity': 'p04', 'sha256': entry['svg']['sha256']}]
            check_status = 'preview_binding_pass; visual_quality_not_evaluated'
        elif action == 'compile':
            fonts = pipeline.resolve_fonts([parsed])
            save(out / 'resolved-fonts.json', {k: {'path': v, 'sha256': digest(Path(v).read_bytes())} for k, v in fonts.items()})
            result = compile_deck([SvgInput('p04', out / 'actual-p04.svg', page.get('speaker_notes', ''))],
                CompileOptions(width_px=1600, height_px=900, fonts=fonts), out / 'native')
            report = pipeline.readback(result.pptx_path, [parsed], [page])
            save(out / 'actual-readback.json', report)
            rendered = pipeline.render_deck(result.pptx_path, out / 'rendered', fonts=fonts)
            check_status = 'pass' if report['status'] == 'pass' and len(rendered) == 1 else 'fail'
            with zipfile.ZipFile(result.pptx_path) as archive:
                root = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
                ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
                      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                counts = {'native_shapes': len(root.findall('.//p:sp', ns)),
                          'text_runs': len(root.findall('.//a:t', ns)),
                          'pictures': len(root.findall('.//p:pic', ns)),
                          'media_members': [n for n in archive.namelist() if n.startswith('ppt/media/')]}
            save(out / 'actual-compile-result.json', {
                'pptx': str(result.pptx_path), 'pptx_sha256': digest(result.pptx_path.read_bytes()),
                'compile_manifest': str(result.manifest_path), 'diagnostics': result.diagnostics,
                'readback_status': report['status'], 'counts': counts,
                'render_count': len(rendered), 'mechanical_check_status': check_status,
                'rendered': [{'path': str(p), 'sha256': digest(p.read_bytes())} for p in rendered],
                'scope': 'one-page pure-library engineering file; not Document.outputs or full eight-page delivery',
                'visual_quality': None, 'desktop_editing': None,
            })
        else:
            raise ValueError(action)
        after = store.load_document()
        save(out / 'after-document.json', after)
        assert [e['page'] for e in after['pages']] == [e['page'] for e in before['pages']]
        assert after['narrative'] == before['narrative']
        assert after['content_plan'] == before['content_plan']
        assert after['outputs'] == before['outputs']
        assert all(a == b for a, b in zip(after['pages'], before['pages']) if a['page_id'] != 'p04')
        after_entry = next(e for e in after['pages'] if e['page_id'] == 'p04')
        assert {k: v for k, v in after_entry.items() if k != 'svg_preview'} == {
            k: v for k, v in entry.items() if k != 'svg_preview'}
        if action == 'compile':
            assert after == before
        save(out / 'root-observation.json', {'action': action, 'completed': True,
            'mechanical_check_status': check_status,
            'quality_or_desktop_pass': None,
            'all_eight_page_content_refs_unchanged': True, 'other_seven_page_entries_unchanged': True,
            'narrative_content_plan_outputs_unchanged': True, 'project_document_unchanged': after == before,
            'actual_new_image_calls': 0, 'human_acceptance': None, 'desktop_acceptance': None})
    except BaseException:
        (out / 'failure-traceback.txt').write_text(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
