from __future__ import annotations
import json
import math
import posixpath
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from .atoms import visible_atoms
class NeedsTool(RuntimeError):
    pass


class RendererError(RuntimeError):
    pass


def executable(name):
    configured=os.environ.get('DECK_MASTER_'+name.upper().replace('-','_'))
    path=shutil.which(configured or name)
    if not path:raise NeedsTool(f'{name} unavailable; configure DECK_MASTER_{name.upper().replace("-","_")}')
    return path


def run(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=120, **kwargs)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b'').decode(errors='replace').strip()
        raise RendererError(f'{Path(args[0]).name} exited {exc.returncode}: {detail or "no stderr"}') from exc
    except subprocess.TimeoutExpired as exc:
        raise RendererError(f'{Path(args[0]).name} timed out after {exc.timeout}s') from exc


def resolve_fonts(pages):
    fonts={}
    for page in pages:
        for shape in [run for source in page['shapes']
                      for run in [source, *source.get('runs', [])]]:
            if 'kind' not in shape:
                shape = {**shape, 'kind': 'text'}
            if shape['kind']!='text':continue
            name=shape['font_family'];key=name+(':bold' if shape['bold'] else '')
            if key in fonts:continue
            result=run([executable('fc-match'),'-f','%{family}\n%{file}',name+(':style=Bold' if shape['bold'] else '')]).stdout.decode().split('\n',1)
            if len(result)!=2 or name.lower() not in result[0].lower():raise NeedsTool(f'font {name} unavailable; explicitly choose an installed font in design and SVG')
            fonts[key]=result[1]
    return fonts


def renderer_environment():
    """Use the host's full Fontconfig configuration in macOS render children.

    The macOS LibreOffice bundle can embed a different Fontconfig prefix from
    fc-match. Its default then silently substitutes fonts (or loses CJK glyphs).
    Discover the active host configuration, without changing global settings or
    replacing it with a partial font-directory configuration.
    """
    if sys.platform != 'darwin' or any(os.environ.get(key) for key in
                                     ('FONTCONFIG_FILE', 'FONTCONFIG_PATH')):
        return None  # Inherit the caller's explicit configuration unchanged.
    try:
        listing = run([executable('fc-conflist')]).stdout.decode()
    except (OSError, RendererError, UnicodeError) as exc:
        raise NeedsTool('cannot discover host Fontconfig; configure FONTCONFIG_FILE') from exc
    configs = set()
    for line in listing.splitlines():
        match = re.match(r'^\+ (/.*/fonts\.conf): ', line)
        if match:
            configs.add(Path(match.group(1)))
    if len(configs) != 1:
        raise NeedsTool('host Fontconfig root is missing or ambiguous; configure FONTCONFIG_FILE')
    config = configs.pop()
    try:
        with config.open('rb') as stream:
            stream.read(1)
    except OSError as exc:
        raise NeedsTool('host Fontconfig root is unreadable; configure FONTCONFIG_FILE') from exc
    return {**os.environ, 'FONTCONFIG_FILE': str(config)}


def render_deck(pptx_path, output_dir, *, fonts):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    # resolve_fonts already verified these fonts using the host's Fontconfig.
    # Bridge the macOS bundle's different default prefix to that full config.
    # Linux and explicit caller configuration retain their existing behavior.
    environment = renderer_environment()
    profile=(output_dir/'lo-profile').resolve().as_uri()
    run([executable('soffice'),f'-env:UserInstallation={profile}','--headless','--convert-to','pdf','--outdir',str(output_dir),str(pptx_path)], env=environment)
    pdf=output_dir/(Path(pptx_path).stem+'.pdf')
    if not pdf.is_file():raise RuntimeError('renderer did not produce a PDF')
    run([executable('pdftoppm'),'-r','120','-png',str(pdf),str(output_dir/'page')], env=environment)
    return sorted(output_dir.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))


def readback(pptx_path,pages,expected_pages):
    ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
    findings=[];stats=[]
    from .compiler.native import notes_records, normalize_notes
    actual_notes = notes_records(pptx_path)
    for row, page in zip(actual_notes, expected_pages):
        if row['page_id'] != page['page_id']:
            findings.append({'page_id': page['page_id'], 'code': 'notes_page_identity_mismatch'})
        if row['notes'] != normalize_notes(page.get('speaker_notes', '')):
            findings.append({'page_id': page['page_id'], 'code': 'speaker_notes_mismatch'})
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
            tables = {s['table_id'] for s in source['shapes']
                      if s.get('native_table') and s.get('table_frame')}
            for graphic in root.findall('.//p:graphicFrame', ns):
                table_id = graphic.find('p:nvGraphicFramePr/p:cNvPr', ns).get('name')
                if table_id not in tables:
                    continue
                members = [s for s in source['shapes'] if s.get('table_id') == table_id]
                frame = next(s for s in members if s.get('native_table'))
                xs = sorted({frame['x'], frame['x'] + frame['width'],
                             *(s['points'][0][0] for s in members if s['kind'] == 'line'
                               and s['points'][0][0] == s['points'][1][0])})
                ys = sorted({frame['y'], frame['y'] + frame['height'],
                             *(s['points'][0][1] for s in members if s['kind'] == 'line'
                               and s['points'][0][1] == s['points'][1][1])})
                for r, row in enumerate(graphic.findall('.//a:tbl/a:tr', ns)):
                    for c, cell in enumerate(row.findall('a:tc', ns)):
                        expected = sorted((s for s in members if s['kind'] == 'text'
                                           and r + 1 < len(ys) and c + 1 < len(xs)
                                           and xs[c] <= s['x'] < xs[c + 1] and ys[r] <= s['y'] < ys[r + 1]),
                                          key=lambda s: (s['y'], s['x']))
                        actual = ''.join(t.text or '' for t in cell.findall('.//a:t', ns))
                        if normalize(actual) != normalize(''.join(s['text'] for s in expected)):
                            findings.append({'page_id': page['page_id'], 'code': 'svg_ppt_text_mismatch', 'element': table_id})
            # Legacy geometry checks apply to drawn grids, not native cells.
            # Read native table text above without manufacturing shape XML.
            checked_source = {**source, 'shapes': [s for s in source['shapes'] if s.get('table_id') not in tables]}
            checked_page = deepcopy(page)
            checked_page['customer_visible']['body_blocks'] = [b for b in page['customer_visible'].get('body_blocks', [])
                                                               if b.get('id') not in tables]
            svg_texts = [s['text'] for s in checked_source['shapes'] if s['kind'] == 'text']
            native_texts = [''.join(t.text or '' for t in sp.findall('.//a:t', ns))
                            for sp in root.findall('.//p:sp', ns) if sp.findall('.//a:t', ns)]
            if native_texts != svg_texts:
                findings.append({'page_id':page['page_id'],'code':'svg_ppt_text_mismatch'})
            for atom in visible_atoms(page):
                if atom.get('text') and normalize(atom['text']) not in joined:
                    findings.append({'page_id':page['page_id'],'code':'missing_visible_atom','atom_id':atom['atom_id'],'text':atom['text']})
            from .readback_text import _check_required_text
            findings.extend(_check_required_text(root, checked_source, checked_page))
            from .readback_relations import check_native_relations
            findings.extend(check_native_relations(root, checked_source, checked_page))
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
                endpoints=edge_endpoints(sp)
                if endpoints is None:
                    findings.append({'page_id':page['page_id'],'code':'unverifiable_edge_geometry',
                                     'edge_id':edge_id,'from':edge.get('from'),'to':edge.get('to')})
                    continue
                start,end=endpoints
                from_center=node_centers.get(edge.get('from'));to_center=node_centers.get(edge.get('to'))
                if start is None or from_center is None or to_center is None:continue
                # Native arrow decorations are visible semantics independent
                # of path point order. headEnd is the start decoration;
                # moving a triangle there reverses an otherwise unchanged line.
                head = sp.find('p:spPr/a:ln/a:headEnd', ns)
                tail = sp.find('p:spPr/a:ln/a:tailEnd', ns)
                head_arrow = head is not None and head.get('type', 'none') != 'none'
                if head_arrow:
                    findings.append({'page_id': page['page_id'], 'code': 'reversed_arrow',
                                     'edge_id': edge_id, 'from': edge.get('from'), 'to': edge.get('to'),
                                     'element': sp.find('p:nvSpPr/p:cNvPr', ns).get('name'),
                                     'detail': 'native start decoration points against the declared forward relationship',
                                     'native_arrow_endings': {'head': head.get('type'),
                                                              'tail': tail.get('type') if tail is not None else None}})
                    continue
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
    return {'status':'fail' if findings else 'pass','findings':findings,'pages':stats,
            'notes': actual_notes, 'notes_newlines': 'LF',
            'visual_review':'not_evaluated','desktop_editing':'not_evaluated'}
