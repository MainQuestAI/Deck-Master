"""Recorded production facts for a fixed page. No compiler, OCR or quality verdict."""
from __future__ import annotations

import copy
import re

from .snapshots import READ_FAILURES


def _metadata(ctx, ref, role, page_id=None):
    obj = ctx.read(ref)
    if (obj.get('schema_version') != 'deck_artifact.v1' or obj.get('role') != role
            or obj.get('page_id') != page_id):
        raise ValueError('artifact scope differs')
    return obj


def _artifact(ctx, ref, role, page_id=None):
    result = {'ref': ref, 'state': 'not_recorded' if ref is None else 'recorded', 'editability': 'unknown'}
    if ref is None:
        return result, None
    try:
        obj = _metadata(ctx, ref, role, page_id)
        result.update(file=copy.deepcopy(obj['file']), editability=obj.get('editability') or 'unknown')
        return result, obj
    except READ_FAILURES:
        result['state'] = 'unreadable'
        return result, None


def _payload(ctx, ref, role, pptx):
    result = {'ref': ref, 'state': 'not_recorded' if ref is None else 'recorded', 'pptx_relation': 'unknown'}
    if ref is None:
        return result, None
    try:
        obj = _metadata(ctx, ref, role)
        value = ctx.read(obj['file'])
        if not isinstance(value, dict):
            raise ValueError('invalid production record')
        result['file'] = copy.deepcopy(obj['file'])
        # These older records do not name the PPTX parent. Matching stored input
        # dependencies support an inference only, never a direct output binding.
        deps = obj.get('dependencies') or []
        if pptx and deps and deps == pptx.get('dependencies'):
            result['pptx_relation'] = 'shared_inputs'
        return result, value
    except READ_FAILURES:
        result['state'] = 'unreadable'
        return result, None


def projection(ctx, entry, deck_output):
    doc = ctx.document
    outputs = doc.get('outputs') or {}
    svg, svg_obj = _artifact(ctx, entry.get('svg'), 'svg', entry['page_id'])
    pptx, pptx_obj = _artifact(ctx, outputs.get('pptx'), 'pptx')
    pptx['applicability'] = deck_output.get('applicability', 'unknown')
    report, report_data = _payload(ctx, outputs.get('render_report'), 'render_report', pptx_obj)
    report.update(text_runs=None, native_shapes=None, findings=[], recorded_status='unknown')
    if report_data is not None:
        try:
            rows = [p for p in report_data.get('pages', []) if p['page_id'] == entry['page_id']]
            if len(rows) > 1:
                raise ValueError('duplicate page counts')
            if rows:
                row = rows[0]
                for key in ('text_runs', 'native_shapes'):
                    if type(row[key]) is not int or row[key] < 0:
                        raise ValueError('invalid count')
                report.update({key: row[key] for key in ('text_runs', 'native_shapes')})
            report['recorded_status'] = report_data.get('status') if report_data.get('status') in ('pass', 'fail') else 'unknown'
            # Preserve structured recorded findings, excluding unrelated page rows.
            report['findings'] = copy.deepcopy([f for f in report_data.get('findings', [])
                                               if f.get('page_id') in (None, entry['page_id'])])
        except READ_FAILURES:
            report.update(state='unreadable', text_runs=None, native_shapes=None, findings=[], recorded_status='unknown')
    trace, trace_data = _payload(ctx, outputs.get('trace'), 'object_trace', pptx_obj)
    trace.update(svg_input_image_elements=None, svg_relation='unknown', compiler_fonts=[], diagnostics=[])
    if trace_data is not None:
        try:
            rows = [p for p in trace_data.get('pages', []) if p['page_id'] == entry['page_id']]
            if len(rows) > 1:
                raise ValueError('duplicate trace page')
            if rows and svg_obj and rows[0].get('sha256') == svg_obj['file']['sha256']:
                shapes = rows[0]['shapes']
                if not isinstance(shapes, list) or any(not isinstance(s, dict) or not isinstance(s.get('kind'), str) for s in shapes):
                    raise ValueError('invalid trace shapes')
                trace['svg_relation'] = 'input_hash_match'
                trace['svg_input_image_elements'] = sum(s['kind'] == 'image' for s in shapes)
            for family, record in (trace_data.get('fonts') or {}).items():
                digest = record.get('sha256')
                if isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest):
                    trace['compiler_fonts'].append({'family_key': family, 'sha256': digest})
            trace['diagnostics'] = copy.deepcopy([d for d in trace_data.get('diagnostics', [])
                                                 if d.get('page_id') == entry['page_id']])
        except READ_FAILURES:
            trace.update(state='unreadable', svg_input_image_elements=None, svg_relation='unknown', compiler_fonts=[], diagnostics=[])
    evaluations = {kind: {'status': 'not_evaluated', 'ref': None, 'reviewer_type': None, 'subject': outputs.get('pptx')}
                   for kind in ('professional_use', 'desktop_editing')}
    unreadable_reviews = False
    for ref in doc.get('reviews') or []:
        try:
            review = ctx.read(ref)
            if review.get('schema_version') != 'deck_review.v1':
                raise ValueError('invalid review')
            kind = review['kind']
            if kind in evaluations and outputs.get('pptx') and outputs['pptx'] in review['subjects']:
                evaluations[kind].update(status=review['status'], ref=copy.deepcopy(ref), reviewer_type=review['reviewer']['type'])
        except READ_FAILURES:
            unreadable_reviews = True
    return {'revision_id': doc['revision_id'], 'page_id': entry['page_id'], 'scope': 'fixed_snapshot',
            'svg': svg, 'pptx': pptx, 'render_report': report, 'object_trace': trace,
            'declared_fonts': copy.deepcopy((doc.get('design_context') or {}).get('fonts') or []),
            'font_substitution': 'not_recorded', 'ppt_raster_ratio': None, 'ocr_text_layer': 'not_recorded',
            'evaluations': evaluations, 'unreadable_reviews': unreadable_reviews,
            'limitations': ['text_runs_are_not_text_boxes', 'native_shapes_include_text_shapes',
                            'trace_images_are_svg_inputs_not_ppt_raster_ratio', 'compiler_fonts_are_inputs_not_desktop_substitution',
                            'editability_metadata_is_not_desktop_editing_proof', 'no_office_edit_data_or_native_table_claim']}
