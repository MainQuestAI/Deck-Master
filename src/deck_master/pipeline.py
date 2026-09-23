"""Local production and tool discovery; all adopted bytes go through Store."""
from __future__ import annotations
import json
import posixpath
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET
from .compiler import CompileOptions, SvgInput, compile_deck
from .compiler.svg import parse_svg
from .production import resolve_design
from .content import visible_atoms
from .models import bump_revision, validate_artifact_semantics
from .store import Store
from .tasks import _utc_now_iso

class NeedsTool(RuntimeError):
    pass

def executable(name):
    configured=os.environ.get('DECK_MASTER_'+name.upper().replace('-','_'))
    path=shutil.which(configured or name)
    if not path:raise NeedsTool(f'{name} unavailable; configure DECK_MASTER_{name.upper().replace("-","_")}')
    return path

def run(args, **kwargs):
    return subprocess.run(args,check=True,capture_output=True,timeout=120,**kwargs)

def resolve_fonts(pages):
    fonts={}
    for page in pages:
        for shape in page['shapes']:
            if shape['kind']!='text':continue
            name=shape['font_family'];key=name+(':bold' if shape['bold'] else '')
            if key in fonts:continue
            result=run([executable('fc-match'),'-f','%{family}\n%{file}',name+(':style=Bold' if shape['bold'] else '')]).stdout.decode().split('\n',1)
            if len(result)!=2 or name.lower() not in result[0].lower():raise NeedsTool(f'font {name} unavailable; explicitly choose an installed font in design and SVG')
            fonts[key]=result[1]
    return fonts

def artifact(store,path,role,*,page_id=None,dependencies=(),derived_from=()):
    suffix=Path(path).suffix.lower()
    media={'.svg':'image/svg+xml','.png':'image/png','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','.json':'application/json'}[suffix]
    obj={'schema_version':'deck_artifact.v1','artifact_id':role+'-'+uuid.uuid4().hex[:12],'page_id':page_id,'role':role,'file':store.put_blob(Path(path).read_bytes(),ext=suffix[1:]),'media_type':media,'created_at':_utc_now_iso(),'dependencies':list(dependencies),'derived_from':list(derived_from),'provenance':{'source_type':'tool_generated','tool':'deck_master.local'},'limitations':[]}
    if role=='pptx':obj['editability']='editable_shapes_and_text'
    validate_artifact_semantics(obj)
    return store.put_json_object(obj)

def render_deck(pptx_path, output_dir, *, fonts):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    # Explicit font directories also work with the bundled headless renderer.
    config=ET.Element('fontconfig')
    for directory in sorted({str(Path(f).parent) for f in fonts.values()}):ET.SubElement(config,'dir').text=directory
    ET.SubElement(config,'cachedir').text=str(output_dir/'font-cache')
    config_path=output_dir/'fonts.conf';config_path.write_bytes(ET.tostring(config))
    env={**os.environ,'FONTCONFIG_FILE':str(config_path)}
    profile=(output_dir/'lo-profile').resolve().as_uri()
    run([executable('soffice'),f'-env:UserInstallation={profile}','--headless','--convert-to','pdf','--outdir',str(output_dir),str(pptx_path)],env=env)
    pdf=output_dir/(Path(pptx_path).stem+'.pdf')
    if not pdf.is_file():raise RuntimeError('renderer did not produce a PDF')
    run([executable('pdftoppm'),'-r','120','-png',str(pdf),str(output_dir/'page')])
    return sorted(output_dir.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))

def readback(pptx_path,pages,expected_pages):
    ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
    findings=[];stats=[]
    normalize=lambda t:''.join(str(t).split())
    with zipfile.ZipFile(pptx_path) as z:
        presentation=ET.fromstring(z.read('ppt/presentation.xml'))
        slide_ids=presentation.findall('p:sldIdLst/p:sldId',ns)
        sld_sz=presentation.find('p:sldSz',ns)
        slide_cx=int(sld_sz.get('cx'));slide_cy=int(sld_sz.get('cy'))
        relationships=ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
        targets={r.get('Id'):r.get('Target') for r in relationships if r.get('TargetMode')!='External'}
        slide_paths=[]
        for slide_id in slide_ids:
            target=targets.get(slide_id.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'),'')
            slide_paths.append(posixpath.normpath(posixpath.join('ppt',target)) if not target.startswith('/') else target.lstrip('/'))
        actual_count=len(slide_ids)
        if actual_count!=len(expected_pages) or len(pages)!=len(expected_pages):
            findings.append({'code':'slide_count_mismatch','actual':actual_count,'expected':len(expected_pages),'svg_inputs':len(pages)})
        for index,(source,page) in enumerate(zip(pages,expected_pages),1):
            slide_path=slide_paths[index-1] if index<=len(slide_paths) else ''
            if slide_path not in z.namelist():
                findings.append({'page_id':page['page_id'],'code':'missing_slide'})
                continue
            root=ET.fromstring(z.read(slide_path))
            texts=[e.text or '' for e in root.findall('.//a:t',ns)]
            joined=normalize(''.join(texts))
            svg_texts=[s['text'] for s in source['shapes'] if s['kind']=='text']
            if texts!=svg_texts:findings.append({'page_id':page['page_id'],'code':'svg_ppt_text_mismatch'})
            for atom in visible_atoms(page):
                if atom.get('text') and normalize(atom['text']) not in joined:
                    findings.append({'page_id':page['page_id'],'code':'missing_visible_atom','atom_id':atom['atom_id'],'text':atom['text']})
            # AC-K10 (P1-05): per-atom readability — every customer-visible
            # atom must be carried by a readable run (>= 6pt and not fully
            # transparent, spec 06.3). Runs whose text no atom covers are
            # decorative and never judged. The page-level all-hidden check
            # below stays as a backstop for layers that dodge atom mapping.
            MIN_READABLE_SZ = 600  # 6pt in DrawingML hundredths-of-a-point units
            run_nodes = root.findall('.//a:rPr', ns)
            normalize = lambda s: ''.join(str(s).split())
            atoms = visible_atoms(page)
            atom_texts = {normalize(atom['text']) for atom in atoms
                          if atom.get('text') and normalize(atom['text'])}
            if run_nodes:
                def run_unreadable(props):
                    try: small = float(props.get('sz', '0')) < MIN_READABLE_SZ
                    except ValueError: small = False
                    transparent = any(int(a.get('val', '100000')) == 0
                                        for a in props.findall('.//a:alpha', ns))
                    return small or transparent
                run_pairs = list(zip(root.findall('.//a:rPr', ns), root.findall('.//a:t', ns)))
                for props, text_node in run_pairs:
                    run_text = normalize(text_node.text or '')
                    if not run_text or run_text not in atom_texts:
                        continue  # decorative run: no atom requires it
                    if run_unreadable(props):
                        atom = next(a for a in atoms if normalize(a.get('text')) == run_text)
                        findings.append({'page_id': page['page_id'], 'code': 'unreadable_text',
                                         'atom_id': atom['atom_id'],
                                         'detail': f"run renders at sz={props.get('sz')!r} "
                                                   f"(or transparent) for a required atom"})
                if texts and all(run_unreadable(props) for props in run_nodes):
                    findings.append({'page_id': page['page_id'], 'code': 'hidden_or_tiny_text',
                                     'detail': 'all text runs are transparent or under 6pt'})
            # AC-K10: real text overflow — a shape box leaving the slide bounds.
            for sp in root.findall('.//p:sp',ns):
                name_node=sp.find('p:nvSpPr/p:cNvPr',ns)
                xfrm=sp.find('p:spPr/a:xfrm',ns)
                if name_node is None or xfrm is None:continue
                off=xfrm.find('a:off',ns);ext=xfrm.find('a:ext',ns)
                if off is None or ext is None:continue
                x,y=int(off.get('x')),int(off.get('y'));w,h=int(ext.get('cx')),int(ext.get('cy'))
                if x<0 or y<0 or x+w>slide_cx or y+h>slide_cy:
                    findings.append({'page_id':page['page_id'],'code':'shape_outside_slide','element':name_node.get('name'),'bounds':[x,y,w,h],'slide':[slide_cx,slide_cy]})
            # AC-K08: verify declared node/edge relations against the actual
            # slide geometry, located via data-node-ref/data-edge-ref bindings.
            visual=page.get('visual_spec') or {}
            nodes=visual.get('nodes') or []
            edges=visual.get('edges') or []
            ppt_by_name={}
            for sp in root.findall('.//p:sp',ns):
                name_node=sp.find('p:nvSpPr/p:cNvPr',ns)
                if name_node is not None:ppt_by_name[name_node.get('name')]=sp
            def shape_name(s):return s.get('atom_id') or s['id']
            def sp_center(sp):
                off=sp.find('p:spPr/a:xfrm/a:off',ns);ext=sp.find('p:spPr/a:xfrm/a:ext',ns)
                if off is None or ext is None:return None
                return (int(off.get('x'))+int(ext.get('cx'))/2,int(off.get('y'))+int(ext.get('cy'))/2)
            def edge_endpoints(sp):
                path=sp.find('p:spPr/a:custGeom/a:pathLst/a:path',ns)
                if path is None:return None
                off=sp.find('p:spPr/a:xfrm/a:off',ns)
                if off is None:return None
                ox,oy=int(off.get('x')),int(off.get('y'))
                pts=[]
                for child in path:
                    op=child.tag.rsplit('}',1)[-1]
                    if op=='close':continue
                    pt=child.find('a:pt',ns)
                    if pt is None:return None
                    pts.append((ox+int(pt.get('x')),oy+int(pt.get('y'))))
                if len(pts)<2:return None
                return pts[0],pts[-1]
            node_centers={}
            for node in nodes:
                node_id=node.get('node_id')
                refs=[s for s in source['shapes'] if s.get('node_ref')==node_id]
                center=None
                for candidate in refs:
                    sp=ppt_by_name.get(shape_name(candidate))
                    if sp is not None:
                        center=sp_center(sp);break
                if center is None:
                    findings.append({'page_id':page['page_id'],'code':'missing_node','node_id':node_id})
                else:
                    node_centers[node_id]=center
            for edge in edges:
                edge_id=edge.get('edge_id')
                refs=[s for s in source['shapes'] if s.get('edge_ref')==edge_id]
                sp=next((ppt_by_name.get(shape_name(s)) for s in refs if shape_name(s) in ppt_by_name),None)
                if sp is None:
                    findings.append({'page_id':page['page_id'],'code':'missing_edge','edge_id':edge_id})
                    continue
                if edge.get('direction') in ('both','undirected'):continue
                start,end=edge_endpoints(sp)
                from_center=node_centers.get(edge.get('from'));to_center=node_centers.get(edge.get('to'))
                if start is None or from_center is None or to_center is None:continue
                # P1-05: dual-endpoint verification with a declared tolerance.
                # Reversal is judged on the START point; reachability on both
                # ends (a short stub near A that never arrives at B fails).
                ENDPOINT_TOLERANCE_PX = 8.0  # connection slop vs node bbox centres
                tol2 = (ENDPOINT_TOLERANCE_PX * 9525) ** 2
                d_start_from = (start[0]-from_center[0])**2 + (start[1]-from_center[1])**2
                d_start_to = (start[0]-to_center[0])**2 + (start[1]-to_center[1])**2
                d_end_to = (end[0]-to_center[0])**2 + (end[1]-to_center[1])**2
                d_end_from = (end[0]-from_center[0])**2 + (end[1]-from_center[1])**2
                element = sp.find('p:nvSpPr/p:cNvPr', ns).get('name')
                if d_start_to < d_start_from:
                    findings.append({'page_id': page['page_id'], 'code': 'reversed_arrow',
                                     'edge_id': edge_id, 'from': edge.get('from'), 'to': edge.get('to'),
                                     'element': element})
                elif d_start_from > tol2 or d_end_to > tol2:
                    findings.append({'page_id': page['page_id'], 'code': 'edge_not_connected',
                                     'edge_id': edge_id, 'from': edge.get('from'), 'to': edge.get('to'),
                                     'element': element,
                                     'detail': f'endpoints miss their nodes: '
                                               f'd(start,from)={d_start_from**0.5/9525:.1f}px, '
                                               f'd(end,to)={d_end_to**0.5/9525:.1f}px '
                                               f'(tolerance {ENDPOINT_TOLERANCE_PX}px)'})
            stats.append({'page_id':page['page_id'],'text_runs':len(texts),'native_shapes':len(root.findall('.//p:sp',ns))})
    return {'status':'fail' if findings else 'pass','findings':findings,'pages':stats,'visual_review':'not_evaluated','desktop_editing':'not_evaluated'}

def produce(project_dir):
    store=Store(project_dir);doc=store.load_document()
    for tool in ('rsvg-convert','soffice','pdftoppm'):executable(tool)
    with tempfile.TemporaryDirectory(prefix='production-',dir=store.staging_dir) as temporary:
        work=Path(temporary);inputs=[];parsed=[];expected=[];approved={};preview_inputs=[]
        for index,entry in enumerate(doc['pages']):
            obj=store.read_object_json(entry['svg']);data=store.read_object_bytes(obj['file'])
            page=store.read_object_json(entry['page'])
            effective,_=resolve_design(page,doc['design_context'],doc['design_context'].get('assets',[]))
            mapping={}
            for asset in effective['assets']:
                resource=store.read_object_json(asset['artifact'])
                if resource['media_type'] not in ('image/png','image/jpeg'):continue
                raster=work/(asset['asset_id']+Path(resource['file']['path']).suffix)
                raster.write_bytes(store.read_object_bytes(resource['file']));mapping[asset['asset_id']]=str(raster)
            approved[entry['page_id']]=mapping
            path=work/f'page-{index+1}.svg';path.write_bytes(data)
            inputs.append(SvgInput(entry['page_id'],path));parsed.append(parse_svg(data,page_id=entry['page_id'],assets=mapping))
            preview_tree=ET.fromstring(data)
            for node in preview_tree.iter():
                if node.tag.rsplit('}',1)[-1]=='image':
                    key='href' if node.get('href') is not None else '{http://www.w3.org/1999/xlink}href'
                    node.set(key,Path(mapping[node.get(key)]).as_uri())
            preview_path=work/f'preview-input-{index+1}.svg';preview_path.write_bytes(ET.tostring(preview_tree));preview_inputs.append(preview_path)
            expected.append(page)
        fonts=resolve_fonts(parsed);canvas=doc['design_context']['canvas']
        options=CompileOptions(width_px=canvas['slide_width_in']*96,height_px=canvas['slide_height_in']*96,fonts=fonts,assets=approved)
        compiled=compile_deck(inputs,options,work/'compiled')
        renders=render_deck(compiled.pptx_path,work/'rendered',fonts=fonts)
        if len(renders)!=len(inputs):raise RuntimeError('rendered slide count differs from current page count')
        report=readback(compiled.pptx_path,parsed,expected)
        report_path=work/'readback.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        deps=[{'kind':'svg','identity':e['page_id'],'sha256':e['svg']['sha256']} for e in doc['pages']]
        new=bump_revision(doc,{'operation_id':'production-'+uuid.uuid4().hex,'kind':'artifact_adoption','description':'native compile, dual rendering and actual PPT readback','read_set':[]})
        for i,entry in enumerate(new['pages']):
            preview=work/f'svg-{i+1}.png';run([executable('rsvg-convert'),str(preview_inputs[i]),'-o',str(preview)])
            entry['svg_preview']=artifact(store,preview,'svg_preview',page_id=entry['page_id'],dependencies=deps,derived_from=[entry['svg']])
            entry['ppt_preview']=artifact(store,renders[i],'ppt_preview',page_id=entry['page_id'],dependencies=deps,derived_from=[entry['svg']])
        for i, ref in enumerate(new['tasks']):
            task = store.read_object_json(ref)
            if task['kind'] == 'review' and task['status'] in ('running','awaiting_host'):
                task['status'] = 'superseded'
                new['tasks'][i] = store.put_json_object(task)
        new['outputs']={'pptx':artifact(store,compiled.pptx_path,'pptx',dependencies=deps),'trace':artifact(store,compiled.manifest_path,'object_trace',dependencies=deps),'render_report':artifact(store,report_path,'render_report',dependencies=deps)}
        store.commit_change(base_revision=doc['revision_id'],document=new,operation_id=new['change']['operation_id'])
        return report
