"""Read-only engineering diagnostics through actual compiler/render/readback.

These isolated regression artifacts are never adopted production outputs and
never stand in for PageVisual, human, independent or model quality approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from deck_master import pipeline
from deck_master.operations import OperationError
from deck_master.store import Store
from rc3_fixtures import source_snapshot


def render_engineering_diagnostic(project, *, output_dir):
    """Prove formal assembly refuses, then inspect the SVG without publishing."""
    project = Path(project).resolve()
    output_dir = Path(output_dir).resolve()
    assert not output_dir.is_relative_to(project), 'engineering artifacts must stay outside the source project'
    store = Store(project)
    document = store.load_document()
    before = source_snapshot(project)
    assert all(value is None for value in document['outputs'].values())
    with pytest.raises(OperationError) as blocked:
        pipeline.produce(project)
    assert blocked.value.error_code in ('stage_prerequisite_missing', 'stage_quality_blocked')
    assert source_snapshot(project) == before

    output_dir.mkdir(parents=True)
    inputs, parsed, expected, assets, svg_previews = [], [], [], {}, []
    for index, entry in enumerate(document['pages'], 1):
        page_id = entry['page_id']
        page = store.read_object_json(entry['page'])
        data = store.read_object_bytes(store.read_object_json(entry['svg'])['file'])
        assets[page_id] = pipeline.page_asset_paths(store, document, entry, output_dir)
        svg = output_dir / f'page-{index}.svg'
        svg.write_bytes(data)
        inputs.append(pipeline.SvgInput(page_id, svg, page.get('speaker_notes', '')))
        parsed.append(pipeline.parse_svg(data, page_id=page_id, assets=assets[page_id]))
        expected.append(page)
        preview_input = output_dir / f'preview-input-{index}.svg'
        preview_input.write_bytes(pipeline.preview_svg_bytes(data, page_id=page_id, assets=assets[page_id]))
        preview = output_dir / f'svg-{index}.png'
        pipeline.run([pipeline.executable('rsvg-convert'), str(preview_input), '-o', str(preview)])
        svg_previews.append(preview)

    fonts = pipeline.resolve_fonts(parsed)
    canvas = document['design_context']['canvas']
    compiled = pipeline.compile_deck(inputs, pipeline.CompileOptions(
        width_px=canvas['slide_width_in'] * 96, height_px=canvas['slide_height_in'] * 96,
        fonts=fonts, assets=assets), output_dir / 'compiled')
    ppt_previews = pipeline.render_deck(compiled.pptx_path, output_dir / 'rendered', fonts=fonts)
    assert len(ppt_previews) == len(inputs)
    report = pipeline.readback(compiled.pptx_path, parsed, expected)
    report_path = output_dir / 'readback.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    assert json.loads(report_path.read_bytes()) == report
    assert source_snapshot(project) == before
    assert store.load_document() == document
    artifacts = [compiled.pptx_path, compiled.manifest_path, report_path, *svg_previews, *ppt_previews]
    provenance = {'evidence_level': 'L1_ENGINEERING_ONLY', 'visual_acceptance': 'not_evaluated',
        'production_published': False, 'production_refusal': blocked.value.error_code,
        'source_revision_id': document['revision_id'], 'source_unchanged': True,
        'files': [{'path': str(path.relative_to(output_dir)),
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in artifacts]}
    (output_dir / 'diagnostic.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    return {'report': report, 'report_path': report_path, 'pptx_path': compiled.pptx_path,
        'svg_previews': svg_previews, 'ppt_previews': ppt_previews, 'provenance': provenance}
