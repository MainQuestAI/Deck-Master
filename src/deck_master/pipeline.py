"""Local production and tool discovery; all adopted bytes go through Store."""
from __future__ import annotations
import json
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
        for index,(source,page) in enumerate(zip(pages,expected_pages),1):
            root=ET.fromstring(z.read(f'ppt/slides/slide{index}.xml'))
            texts=[e.text or '' for e in root.findall('.//a:t',ns)]
            joined=normalize(''.join(texts))
            svg_texts=[s['text'] for s in source['shapes'] if s['kind']=='text']
            if texts!=svg_texts:findings.append({'page_id':page['page_id'],'code':'svg_ppt_text_mismatch'})
            for atom in visible_atoms(page):
                if atom.get('text') and normalize(atom['text']) not in joined:
                    findings.append({'page_id':page['page_id'],'code':'missing_visible_atom','atom_id':atom['atom_id'],'text':atom['text']})
            for node in root.findall('.//a:rPr',ns):
                if float(node.get('sz','0'))<600 or any(int(a.get('val','100000'))==0 for a in node.findall('.//a:alpha',ns)):
                    findings.append({'page_id':page['page_id'],'code':'hidden_or_tiny_text'})
            stats.append({'page_id':page['page_id'],'text_runs':len(texts),'native_shapes':len(root.findall('.//p:sp',ns))})
    return {'status':'fail' if findings else 'pass','findings':findings,'pages':stats,'visual_review':'not_evaluated','desktop_editing':'not_evaluated'}

def produce(project_dir):
    store=Store(project_dir);doc=store.load_document()
    for tool in ('rsvg-convert','soffice','pdftoppm'):executable(tool)
    with tempfile.TemporaryDirectory(prefix='production-',dir=store.staging_dir) as temporary:
        work=Path(temporary);inputs=[];parsed=[];expected=[]
        for index,entry in enumerate(doc['pages']):
            obj=store.read_object_json(entry['svg']);data=store.read_object_bytes(obj['file'])
            path=work/f'page-{index+1}.svg';path.write_bytes(data)
            inputs.append(SvgInput(entry['page_id'],path));parsed.append(parse_svg(data,page_id=entry['page_id']))
            expected.append(store.read_object_json(entry['page']))
        fonts=resolve_fonts(parsed);canvas=doc['design_context']['canvas']
        options=CompileOptions(width_px=canvas['slide_width_in']*96,height_px=canvas['slide_height_in']*96,fonts=fonts)
        compiled=compile_deck(inputs,options,work/'compiled')
        renders=render_deck(compiled.pptx_path,work/'rendered',fonts=fonts)
        if len(renders)!=len(inputs):raise RuntimeError('rendered slide count differs from current page count')
        report=readback(compiled.pptx_path,parsed,expected)
        report_path=work/'readback.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        deps=[{'kind':'svg','identity':e['page_id'],'sha256':e['svg']['sha256']} for e in doc['pages']]
        new=bump_revision(doc,{'operation_id':'production-'+uuid.uuid4().hex,'kind':'artifact_adoption','description':'native compile, dual rendering and actual PPT readback','read_set':[]})
        for i,entry in enumerate(new['pages']):
            preview=work/f'svg-{i+1}.png';run([executable('rsvg-convert'),str(inputs[i].path),'-o',str(preview)])
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
