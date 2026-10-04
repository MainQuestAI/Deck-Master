"""Immutable screenshot references and reasoning-only visual analysis tasks.

No provider runs in this module. Analysis results have no Page/artifact write
scope; confirmed recipes reuse the existing trial/adoption ledger.
"""
from __future__ import annotations

import copy
import io
import json
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from . import operations, tasks
from .models import (bump_revision, canonical_json_bytes, content_identity,
                     sha256_bytes, validate_artifact_semantics, validate_schema)
from .snapshots import load_snapshot
from .method_resources import method_resources, method_release
from .store import Store

MAX_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 32_000_000
DIMENSIONS = ('palette', 'typography', 'composition', 'spacing', 'density', 'lines', 'icons')
FORMATS = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'), 'WEBP': ('webp', 'image/webp')}


def fail(field, message, *, conflict=False):
    raise operations.OperationError('visual_reference_conflict' if conflict else 'visual_reference_invalid',
                                    field, message, exit_code=5 if conflict else 2)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _records(store, document):
    rows = []
    for ref in document.get('style_references', []):
        record = store.read_object_json(ref)
        validate_schema('style_reference', record)
        if record['project_id'] != document['project_id']:
            fail('reference', 'reference belongs to another project')
        rows.append((record, ref))
    return rows


def owned(store, document, reference_id):
    for record, ref in _records(store, document):
        if record['reference_id'] == reference_id:
            return record, ref
    fail('reference_id', 'reference is not in this committed project version')


def _artifact(store, data, ext, media, *, original=None):
    obj = {'schema_version':'deck_artifact.v1', 'artifact_id':'reference-' + sha256_bytes(data),
           'page_id':None, 'role':'asset', 'file':store.put_blob(data, ext=ext), 'media_type':media,
           'created_at':_now(), 'dependencies':[], 'derived_from':[original] if original else [],
           'provenance':{'source_type':'user_supplied'}, 'limitations':[], 'editability':'not_applicable'}
    validate_artifact_semantics(obj)
    return store.put_json_object(obj)


@operations.public
def import_reference(project, *, data=None, file=None, base_revision, operation_id):
    operations.validate_id(operation_id, new=True)
    if data is None:
        source = Path(file).expanduser()
        if not source.is_file() or source.stat().st_size > MAX_BYTES:
            fail('file', 'select a real image no larger than 64 MiB')
        data = source.read_bytes()
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        fail('file', 'image must contain 1–64 MiB of bytes')
    store = Store(project)
    with store._locked():
        doc = store.load_document()
        digest = operations.request_digest(doc, 'styles.references.import', base_revision, {'sha256':sha256_bytes(data)})
        recovered = operations.recover(store, operation_id, digest)
        if recovered:
            return recovered
        if doc['revision_id'] != base_revision:
            fail('base_revision', 'project changed; preserve selected file and reload', conflict=True)
        if doc.get('compatibility', {}).get('project_format') != 'workbench.v3':
            fail('project', 'screenshot references require workbench.v3')
        if len(doc.get('style_references', [])) >= 100:
            fail('references', 'this project already has 100 reference versions')
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in FORMATS or image.width * image.height > MAX_PIXELS:
                    fail('file', 'use PNG/JPEG/WebP with at most 32 million pixels')
                ext, media = FORMATS[image.format]
                if getattr(image, 'n_frames', 1) != 1:
                    fail('file', 'animated references are unsupported; select one still image')
                image.load()
                oriented = ImageOps.exif_transpose(image)
                preview = oriented.convert('RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB')
                out = io.BytesIO(); preview.save(out, format='PNG')
                width, height = preview.size
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            fail('file', 'image cannot be decoded; original project remains unchanged: ' + type(exc).__name__)
        original = _artifact(store, data, ext, media)
        derived = _artifact(store, out.getvalue(), 'png', 'image/png', original=original)
        record = {'schema_version':'style-reference.v1', 'project_id':doc['project_id'],
                  'reference_id':'reference-' + uuid.uuid4().hex, 'artifact_ref':original,
                  'preview_ref':derived, 'width':width, 'height':height, 'created_at':_now()}
        validate_schema('style_reference', record)
        ref = store.put_json_object(record)
        updated = bump_revision(doc, {'operation_id':operation_id,'kind':'task_update',
                    'description':'Imported independent screenshot reference; page outputs unchanged','read_set':[]})
        updated['style_references'] = [*doc.get('style_references', []), ref]
        result = {'status':'imported','revision_id':updated['revision_id'],'reference_id':record['reference_id'],'ref':ref}
        return operations.commit_locked(store,document=updated,base_revision=base_revision,operation_id=operation_id,
                                        kind='styles.references.import',digest=digest,result=result)


@operations.public
def listing(project, *, revision=None, reference_id=None):
    store = Store(project); doc = load_snapshot(store, revision)
    rows = []
    for record, ref in _records(store, doc):
        if reference_id and reference_id != record['reference_id']:
            continue
        original = store.read_object_json(record['artifact_ref'])
        preview = store.read_object_json(record['preview_ref'])
        rows.append({'ref':ref, 'reference':record, 'original':original,
                     'preview':{'ref':record['preview_ref'], **preview}})
    if reference_id and not rows:
        fail('reference_id', 'reference is not in this committed version')
    return {'revision_id':doc['revision_id'], 'project_id':doc['project_id'], 'references':rows, 'fonts':copy.deepcopy(doc['design_context'].get('fonts', []))}


@operations.public
def analyze(project, *, reference_ids=None, instruction=None, input=None, base_revision, operation_id):
    if input is not None:
        if not isinstance(input, dict) or set(input) != {"reference_ids", "instruction"}:
            fail("input", "use reference_ids and instruction")
        reference_ids, instruction = input["reference_ids"], input["instruction"]
    operations.validate_id(operation_id, new=True)
    if (not isinstance(reference_ids,list) or not 1 <= len(reference_ids) <= 5
            or any(not isinstance(value,str) for value in reference_ids)
            or len(set(reference_ids)) != len(reference_ids)):
        fail('reference_ids', 'select 1–5 distinct imported screenshots')
    if not isinstance(instruction,str) or not instruction.strip() or len(instruction) > 4000:
        fail('instruction', 'describe the visual direction in 1–4000 characters')
    store = Store(project)
    with store._locked():
        doc = store.load_document()
        digest = operations.request_digest(doc,'styles.analyze',base_revision,{'reference_ids':reference_ids,'instruction':instruction})
        recovered = operations.recover(store,operation_id,digest)
        if recovered:
            return recovered
        if doc['revision_id'] != base_revision:
            fail('base_revision','project changed; preserve requirements and reload',conflict=True)
        rows = [owned(store,doc,rid) for rid in reference_ids]
        request = {'schema_version':'style-analysis-request.v1','project_id':doc['project_id'],
                   'references':[ref for _,ref in rows],'instruction':instruction,
                   'fonts':copy.deepcopy(doc['design_context'].get('fonts',[]))}
        request_ref = store.put_json_object(request)
        task = tasks.new_task(task_id='task-'+uuid.uuid4().hex,operation_id=str(uuid.uuid4()),
                             kind='style_analyze',scope_pages=[],instruction=instruction,inputs=[request_ref],
                             method_release=method_release(method_resources('style_analyze')),
                             dependencies=[{'kind':'artifact','identity':record['reference_id'],'sha256':ref['sha256']}
                                           for record,ref in rows],dispatch_revision=doc['revision_id'],
                             produced_against=content_identity(doc))
        task.update(protocol_version='changes.v1',required_capabilities=['visual_reference'],analysis_request_ref=request_ref)
        updated = bump_revision(doc, {'operation_id':operation_id,'kind':'task_update',
                                     'description':'Visual analysis ready for Host; no image calls','read_set':[]})
        updated['tasks'] = [*doc['tasks'],store.put_json_object(task)]
        result = {'status':'awaiting_host','revision_id':updated['revision_id'],'task_id':task['task_id'],'max_calls':0,
                  'handoff':'请执行 Deck Master 截图视觉分析任务 ' + task['task_id'] + '。项目目录：' + str(store.project_root) + '。通过 task show 读取完整工作单，声明 visual_reference 能力，返回零生图调用的 style_analysis；不要更改页面或自动采用。'}
        return operations.commit_locked(store,document=updated,base_revision=base_revision,operation_id=operation_id,
                                        kind='styles.analyze',digest=digest,result=result)


def inputs_current(store, document, task):
    request = store.read_object_json(task['analysis_request_ref'])
    if request['project_id'] != document['project_id']:
        return False
    available = document.get('style_references', [])
    return all(ref in available for ref in request['references']) and request['fonts'] == document['design_context'].get('fonts',[])


def work_order(store, document, task):
    request = store.read_object_json(task['analysis_request_ref'])
    rows = []
    for ref in request['references']:
        record = store.read_object_json(ref)
        rows.append({'reference_id':record['reference_id'],'original':store.read_object_json(record['artifact_ref'])['file'],
                     'preview':store.read_object_json(record['preview_ref'])['file'],'width':record['width'],'height':record['height']})
    return {'request_ref':task['analysis_request_ref'],'request':request,'reference_images':rows,
            'result_contract':'visual-style-spec.v1','requirements':
            'Read every exact screenshot. Analyze all seven dimensions with normalized evidence regions and certainty. '
            'Report conflicting references and uncertain fonts. Do not copy business text or logos. '
            'Submit kind=style_analyze and style_analysis with dimensions,palette,font_suggestions,conflicts,limitations only. '
            'No Page, SVG, reviews, image generation or usage events. Core binds refs and generates the breakdown.'}


def _breakdown(spec, records):
    """Geometry comes only from reported image regions, never inferred content."""
    labels = {'palette':'配色','typography':'文字层级','composition':'构图','spacing':'间距','density':'密度','lines':'线条','icons':'图标'}
    height = max(740, 155 + len(records) * 210)
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
            f'<rect width="1200" height="{height}" fill="#ffffff"/>',
            '<text x="32" y="42" font-family="Arial, sans-serif" font-size="24" fill="#111111">参考截图 · 视觉规范与观察位置</text>']
    for i,color in enumerate(spec['palette']):
        bits.append(f'<rect x="{32+i*64}" y="64" width="48" height="24" fill="{color}"/>')
    for index,record in enumerate(records):
        x0,y0,w = 32,145+index*210,440
        h=min(170,w*record['height']/record['width'])
        bits.append(f'<text x="{x0}" y="{y0-12}" font-family="Arial, sans-serif" font-size="15" fill="#333333">参考 {index+1} · 观察区域示意（数字对应右侧规则）</text>')
        bits.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f6f7f8" stroke="#cccccc"/>')
        for number,key in enumerate(DIMENSIONS,1):
            evidence = next((e for e in spec['dimensions'][key]['evidence'] if e['reference_id']==record['reference_id']), None)
            if evidence is None:
                continue
            x,y,rw,rh=evidence['region']
            color=('#225588','#887744','#448877','#885588','#775544','#667788','#557788')[number-1]
            bits.append(f'<rect x="{x0+x*w}" y="{y0+y*h}" width="{rw*w}" height="{rh*h}" fill="none" stroke="{color}" stroke-width="1.5"/>')
            bits.append(f'<text x="{x0+x*w+4}" y="{y0+y*h+18}" font-family="Arial, sans-serif" font-size="14" fill="{color}">{number}</text>')
    for i,key in enumerate(DIMENSIONS):
        y = 138 + i*78
        bits.append(f'<text x="520" y="{y}" font-family="Arial, sans-serif" font-size="18" fill="#111111">{i+1} · {labels[key]}</text>')
        summary = spec['dimensions'][key]['summary']
        for line in range(2):
            text = summary[line*37:(line+1)*37]
            bits.append(f'<text x="520" y="{y+24+line*21}" font-family="Arial, sans-serif" font-size="15" fill="#333333">{escape(text)}</text>')
    bits.append(f'<text x="32" y="{height-24}" font-family="Arial, sans-serif" font-size="15" fill="#555555">示意图用于定位观察依据；完整规则、字体近似和不确定性请查看规范详情。</text></svg>')
    return ''.join(bits).encode()


def accept_analysis(store, document, task, envelope, produced_against, result_digest):
    if any(envelope.get(key) for key in ('files','pages','page_order','artifact_specs','reviews','usage_events','content_update','generation_result','content_plan')):
        fail('result','visual analysis has no page, image-generation or review write scope')
    value = envelope.get('style_analysis')
    if not isinstance(value,dict) or set(value) != {'dimensions','palette','font_suggestions','conflicts','limitations'}:
        fail('style_analysis','submit exactly dimensions, palette, font_suggestions, conflicts, limitations')
    request = store.read_object_json(task['analysis_request_ref'])
    placeholder = task['analysis_request_ref']
    spec = {**copy.deepcopy(value),'schema_version':'visual-style-spec.v1','project_id':document['project_id'],
            'analysis_request_ref':task['analysis_request_ref'],'references':request['references'],'breakdown':placeholder}
    validate_schema('visual_style_spec',spec)
    records = [store.read_object_json(ref) for ref in request['references']]
    allowed = {row['reference_id'] for row in records}
    for dimension in spec['dimensions'].values():
        for evidence in dimension['evidence']:
            x,y,w,h = evidence['region']
            if evidence['reference_id'] not in allowed or w <= 0 or h <= 0 or x+w > 1 or y+h > 1:
                fail('evidence','region must be inside a frozen reference image')
    for conflict in spec['conflicts']:
        if not set(conflict['reference_ids']) <= allowed:
            fail('conflicts','conflict must refer to frozen screenshots')
    spec['breakdown'] = store.put_blob(_breakdown(spec, records),ext='svg')
    spec_ref = store.put_json_object(spec)
    updated_task = {**task,'status':'completed','result_refs':[spec_ref],'updated_at':_now()}
    updated = bump_revision(document,{'operation_id':task['operation_id'],'kind':'task_update',
                                     'description':'Visual specification returned; current slides unchanged','read_set':[]})
    tasks._replace_task_in_document(updated,task,store.put_json_object(updated_task),store)
    response = {'status':'accepted','revision_id':updated['revision_id'],'result_refs':[spec_ref],
                'work_complete':tasks.derive_work_complete(updated,store),'next_action':'confirm_visual_style'}
    return tasks._commit_adoption(store,document=updated,base_revision=document['revision_id'],task=task,envelope=envelope,
                                 produced_against=produced_against,result_digest=result_digest,response=response)


def owned_spec(store, document, ref):
    if not any(task.get('kind') == 'style_analyze' and task.get('status') == 'completed' and ref in task['result_refs']
               for task_ref in document['tasks'] for task in [store.read_object_json(task_ref)]):
        fail('visual_style_ref','use a completed analysis result owned by this project')
    spec = store.read_object_json(ref);validate_schema('visual_style_spec',spec)
    if spec['project_id'] != document['project_id']:
        fail('visual_style_ref','spec belongs to another project')
    return spec


def recipe_references(store, document, value):
    spec = owned_spec(store,document,value['visual_style_ref'])
    selected = value.get('primary_reference_id')
    records = [store.read_object_json(ref) for ref in spec['references']]
    ids = {row['reference_id'] for row in records}
    if selected and selected not in ids:
        fail('primary_reference_id','select a screenshot from this analysis')
    if spec['conflicts']:
        fail('primary_reference_id','choose one reference and analyze it again; mixed specifications cannot be confirmed')
    return [{'kind':'external','reference_id':row['reference_id'],'artifact_ref':row['artifact_ref'],'role':'reference'}
            for row in records if not selected or row['reference_id'] == selected]
