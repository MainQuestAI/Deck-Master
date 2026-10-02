"""Frozen icon scopes and bounded SVG trials; no automatic semantic matching."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from . import changes, operations
from .compiler.svg import parse_svg
from .local_state import project_path
from .models import bump_revision, canonical_json_bytes, require_writer, validate_schema
from .snapshots import load_snapshot
from .store import Store, _atomic_write_bytes

GEOMETRY = {'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'use'}
CATALOG = Path(__file__).parent / 'resources/icons/lucide'


def fail(field, message, conflict=False):
    raise operations.OperationError('icon_basis_changed' if conflict else 'icon_invalid', field, message, exit_code=5 if conflict else 2)


def digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def tree(data):
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.I): fail('svg', 'XML declarations are not allowed')
    try: return ET.fromstring(data)
    except ET.ParseError as exc: fail('svg', str(exc))


def tag(node): return node.tag.split('}')[-1]


def canon(node, parent_text=False):
    # Inter-element formatting is irrelevant; text content is not.
    text = node.text if tag(node) in ('text', 'tspan', 'title', 'desc', 'metadata') else (node.text or '').strip()
    return [node.tag, sorted(node.attrib.items()), text or '', (node.tail or '') if parent_text else (node.tail or '').strip(), [canon(c, tag(node) in ('text','tspan')) for c in node]]


def nodes(root):
    def walk(parent, prefix=()):
        for i, node in enumerate(parent):
            path = (*prefix, i)
            yield '/'.join(map(str, path)), node
            yield from walk(node, path)
    return dict(walk(root))


def selected(root, locators):
    found = nodes(root); paths = [v['path'] for v in locators]
    if len(paths) != len(set(paths)) or any(a != b and b.startswith(a + '/') for a in paths for b in paths):
        fail('objects', 'select distinct non-nested geometry subtrees')
    for loc in locators:
        path = loc['path']; node = found.get(path)
        parents = [found['/'.join(path.split('/')[:i])] for i in range(1, len(path.split('/')))]
        if node is None or digest(canon(node)) != loc['sha256']: fail('objects', 'object locator no longer matches its frozen SVG', True)
        if any(tag(p) in ('defs', 'symbol') for p in parents) or any(tag(n) not in GEOMETRY for n in node.iter()):
            fail('objects', 'text, image, shared definitions and mixed groups cannot be replaced')
        # A local use is safe only when its resolved tree consists of geometry.
        if any(tag(n) == 'use' for n in node.iter()):
            isolated(root, path)  # parser checks cyclic/external references
    owned={id(n) for path in paths for n in found[path].iter()}
    identities={n.get('id') for path in paths for n in found[path].iter() if n.get('id')}
    for n in root.iter():
        if id(n) in owned: continue
        for key,value in n.attrib.items():
            if (key.endswith('href') and value.startswith('#') and value[1:] in identities) or any('#'+ident in value for ident in identities if 'url(' in value):
                fail('objects','selected geometry is shared by an unselected object; select the use instance instead')
    return found


def isolated(root, path):
    """Retain all ancestor transforms/styles and local definitions for geometry inspection."""
    result = copy.deepcopy(root)
    def keep(parent, indices):
        chosen = list(parent)[indices[0]]
        for child in list(parent):
            if child is not chosen and tag(child) != 'defs': parent.remove(child)
        if len(indices) > 1: keep(chosen, indices[1:])
    keep(result, [int(v) for v in path.split('/')])
    # SVG permits local use references to visible geometry outside defs. Copy
    # only their dependency closure into private defs, never into the scope.
    definitions = {n.get('id'): n for n in root.iter() if n.get('id')}
    available = {n.get('id') for n in result.iter() if n.get('id')}
    pending = [n.get('href') or n.get('{http://www.w3.org/1999/xlink}href') for n in result.iter() if tag(n) == 'use']
    private = ET.Element('{http://www.w3.org/2000/svg}defs')
    while pending:
        href = pending.pop()
        if not href or not href.startswith('#') or href[1:] in available: continue
        source = definitions.get(href[1:])
        if source is None: continue  # the parser reports the unresolved reference
        clone = copy.deepcopy(source); private.append(clone)
        available.update(n.get('id') for n in clone.iter() if n.get('id'))
        pending.extend(n.get('href') or n.get('{http://www.w3.org/1999/xlink}href') for n in clone.iter() if tag(n) == 'use')
    if len(private): result.append(private)
    parsed = parse_svg(ET.tostring(result), page_id='icon')
    if any(s['kind'] in ('text', 'image') for s in parsed['shapes']): fail('objects', 'referenced geometry includes text or images')
    return parsed


def bounds(parsed):
    points = []
    for shape in parsed['shapes']:
        margin = shape['stroke_width'] / 2 if shape['stroke'] != 'none' else 0
        pts = shape.get('points') or [p for cmd in shape.get('commands', []) for op,p in cmd.items() if op != 'close']
        if pts:
            xy = [(p['x'], p['y']) if isinstance(p, dict) else p for p in pts]
        else:
            xy = [(shape.get('x',0), shape.get('y',0)), (shape.get('x',0)+shape.get('width',0), shape.get('y',0)+shape.get('height',0))]
        for x,y in xy: points.extend([(x-margin,y-margin),(x+margin,y+margin)])
    if not points: return None
    xs, ys = zip(*points); w,h = parsed['width'],parsed['height']
    return {'x': min(xs)/w, 'y': min(ys)/h, 'width': (max(xs)-min(xs))/w, 'height': (max(ys)-min(ys))/h}


def _entry(doc, pid):
    entry = next((e for e in doc['pages'] if e['page_id']==pid), None)
    if not entry or not entry.get('svg') or not entry.get('blueprint'): fail('page_id', 'a recorded SVG and original image are required')
    return entry


def svg_bytes(store, ref): return store.read_object_bytes(store.read_object_json(ref)['file'])


@operations.public
def inspect(project, *, page_id, revision=None):
    store=Store(project_path(project)); doc=load_snapshot(store, revision); entry=_entry(doc,page_id)
    artifact=store.read_object_json(entry['svg']); root=tree(store.read_object_bytes(artifact['file'])); result=[]
    for path,node in nodes(root).items():
        loc={'path':path,'sha256':digest(canon(node))}
        try:
            selected(root,[loc]); box=bounds(isolated(root,path))
        except (operations.OperationError, ValueError): continue
        if box and box['width']>0 and box['height']>0:
            result.append({**loc,'label':node.get('id') or tag(node),'region':box})
    return {'project_id':doc['project_id'],'revision_id':doc['revision_id'],'page_id':page_id,
            'page_ref':entry['page'],'svg_ref':entry['svg'],'blueprint_ref':entry['blueprint'],
            'svg_file':artifact['file'],'objects':result,'semantic_classification':'not_performed'}


@operations.public
def catalog(project=None):
    value=json.loads((CATALOG/'manifest.json').read_text())
    if hashlib.sha256((CATALOG/value['license_file']).read_bytes()).hexdigest()!=value['license_sha256']:
        fail('catalog','packaged license checksum mismatch')
    for asset in value['icons']:
        raw=(CATALOG/(asset['id']+'.svg')).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=asset['sha256']: fail('catalog','packaged icon checksum mismatch')
    return {**value,'digest':digest(value)}


def _owned(store, doc, recipe_id=None, ref=None):
    for current in doc.get('icon_recipes',[]):
        if ref is not None and current!=ref: continue
        value=store.read_object_json(current);validate_schema('icon_recipe',value)
        if value['project_id']!=doc['project_id']:fail('recipe','foreign recipe')
        if ref==current or recipe_id==value['recipe_id']:return value,current
    fail('recipe','recipe not in this committed project version')


def _sample(store,doc,icon,require_current=True):
    from . import candidates
    candidate,_,task=candidates._lookup(candidates._records(store,doc),icon['sample_candidate_id'])
    entry=_entry(doc,candidate['page_id'])
    if require_current and (candidates._state(store,doc,candidate)['generation_basis']['status']!='current' or entry['svg']!=candidate['result_ref'] or not any(a['candidate_id']==candidate['candidate_id'] for a in doc.get('candidate_adoptions',[]))):
        fail('sample_candidate_id','reuse requires a still-current, explicitly adopted icon candidate',True)
    ref=task.get('stage_request',{}).get('icon_recipe_ref')
    if not ref:fail('sample_candidate_id','sample is not an icon candidate')
    recipe,_=_owned(store,doc,ref=ref)
    target=next(t for t in recipe['input']['targets'] if t['page_id']==candidate['page_id'])
    index=icon['sample_icon_index']
    if index>=len(target['icons']):fail('sample_icon_index','sample icon is absent')
    original=target['icons'][index]
    if original['semantic_key']!=icon['semantic_key']:fail('semantic_key','reuse must preserve the explicitly confirmed meaning')
    return candidate,original


def _proposal(store,doc,value):
    validate_schema('icon_input',value)
    if doc.get('compatibility',{}).get('project_format')!='workbench.v3':fail('project','icons require workbench.v3; no implicit migration')
    if value['project_id']!=doc['project_id'] or value['base_revision']!=doc['revision_id']:fail('base_revision','read the current project and propose again',True)
    if not value['instruction'].strip():fail('instruction','provide a concrete requirement')
    cat=catalog(); ids={a['id'] for a in cat['icons']}; seen=set()
    for target in value['targets']:
        pid=target['page_id']
        if pid in seen:fail('targets','combine all selected icons on one page into one target')
        seen.add(pid); entry=_entry(doc,pid)
        if any(target[k]!=entry[s] for k,s in [('page_ref','page'),('svg_ref','svg'),('blueprint_ref','blueprint')]):fail('target','page or artifact changed',True)
        root=tree(svg_bytes(store,entry['svg'])); locators=[]
        for icon in target['icons']:
            for key in ('original_region','svg_region'):
                box=icon[key]
                if box['width']<=0 or box['height']<=0 or box['x']+box['width']>1.000001 or box['y']+box['height']>1.000001:fail(key,'region must be nonempty and inside its own canvas')
            locators+=icon['objects']
            if icon['method']=='standard' and icon.get('asset_id') not in ids:fail('asset_id','choose a packaged catalog icon')
            if icon['method']=='reuse':
                if 'sample_candidate_id' not in icon or 'sample_icon_index' not in icon:fail('sample','select one adopted sample icon')
                _sample(store,doc,icon)
            elif len(value['targets'])>1:fail('targets','first adopt one sample before cross-page reuse')
        selected(root,locators)
        for icon in target['icons']:
            region=icon['svg_region']
            for loc in icon['objects']:
                box=bounds(isolated(root,loc['path']))
                if not box or box['x'] < region['x']-.002 or box['y'] < region['y']-.002 or box['x']+box['width'] > region['x']+region['width']+.002 or box['y']+box['height'] > region['y']+region['height']+.002:
                    fail('svg_region','highlight must contain the selected geometry in slide coordinates')
    for ref in value['annotation_refs']:
        if ref not in doc.get('annotations',[]):fail('annotation_refs','opinion is not committed')
        note=store.read_object_json(ref)
        from .annotation_service import validate
        validate(store,doc,note)
        if note.get('page_id') and note['page_id'] not in seen:fail('annotation_refs','opinion belongs to an unselected page')
        if note.get('page_id'):
            target=next(t for t in value['targets'] if t['page_id']==note['page_id'])
            expected={'svg':target['svg_ref'],'original_image':target['blueprint_ref']}.get(note.get('layer'))
            if note.get('page_ref')!=target['page_ref'] or (expected and note.get('artifact_ref')!=expected):fail('annotation_refs','opinion basis changed; create a new opinion explicitly',True)
    return {'schema_version':'icon_proposal.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],
            'input':copy.deepcopy(value),'catalog_digest':cat['digest']}


def _proposal_ref(proposal_id):
    if not isinstance(proposal_id,str) or not re.fullmatch('icon-proposal-[a-f0-9]{64}',proposal_id):fail('proposal_id','invalid immutable proposal ID')
    sha=proposal_id.removeprefix('icon-proposal-');return {'path':f'.deckmaster/objects/{sha[:2]}/{sha}.json','sha256':sha}


@operations.public
def propose(project, *, input):
    store=Store(project_path(project));doc=load_snapshot(store);proposal=_proposal(store,doc,input)
    ref=store.put_json_object(proposal)
    # Disposable inbox only; the entry explicitly is NOT a confirmation/Document fact.
    folder=store.deck_root/'cache/icon-proposals';folder.mkdir(parents=True,exist_ok=True)
    _atomic_write_bytes(folder/(ref['sha256']+'.json'),canonical_json_bytes(ref))
    return {'status':'suggestion','proposal_id':'icon-proposal-'+ref['sha256'],'proposal_ref':ref,'proposal':proposal,'model_calls':0}


@operations.public
def listing(project, *, revision=None):
    store=Store(project_path(project));doc=load_snapshot(store,revision); proposals=[]
    for p in sorted((store.deck_root/'cache/icon-proposals').glob('*.json')):
        ref=json.loads(p.read_text());v=store.read_object_json(ref);validate_schema('icon_recipe',v)
        if v['project_id']==doc['project_id'] and v['base_revision']==doc['revision_id']:
            proposals.append({'proposal_id':'icon-proposal-'+ref['sha256'],'proposal_ref':ref,'proposal':v})
    samples=[]
    from . import candidates
    records=candidates._records(store,doc) if doc.get('candidate_adoptions') else {}
    for adoption in doc.get('candidate_adoptions',[]):
        candidate,_,task=candidates._lookup(records,adoption['candidate_id'])
        ref=task.get('stage_request',{}).get('icon_recipe_ref')
        if not ref or _entry(doc,candidate['page_id'])['svg']!=candidate['result_ref']:continue
        recipe,_=_owned(store,doc,ref=ref)
        target=next(t for t in recipe['input']['targets'] if t['page_id']==candidate['page_id'])
        for i,icon in enumerate(target['icons']):
            sample={'sample_candidate_id':candidate['candidate_id'],'sample_icon_index':i,'semantic_key':icon['semantic_key']}
            try:_sample(store,doc,sample)
            except operations.OperationError:continue
            if not any(s['sample_candidate_id']==sample['sample_candidate_id'] and s['sample_icon_index']==i for s in samples):samples.append({**sample,'page_id':candidate['page_id'],'label':icon['label'],'style':icon['style']})
    return {'revision_id':doc['revision_id'],'proposals':proposals,'samples':samples,'recipes':[{'ref':r,'recipe':_owned(store,doc,ref=r)[0]} for r in doc.get('icon_recipes',[])]}


@operations.public
def confirm(project, *, proposal_id, base_revision, operation_id):
    operations.validate_id(operation_id,new=True);store=Store(project_path(project));pr=_proposal_ref(proposal_id);proposal=store.read_object_json(pr)
    validate_schema('icon_recipe',proposal)
    with store._locked():
        doc=store.load_document();rd=operations.request_digest(doc,'icons.confirm',base_revision,{'proposal_ref':pr})
        previous=operations.recover(store,operation_id,rd)
        if previous:return previous
        if doc['revision_id']!=base_revision or proposal['base_revision']!=base_revision:fail('base_revision','proposal is stale',True)
        if _proposal(store,doc,proposal['input'])!=proposal:fail('proposal','proposal does not match its frozen inputs')
        recipe={**proposal,'schema_version':'icon_recipe.v1','recipe_id':'icon-'+uuid.uuid4().hex,'proposal_ref':pr}
        validate_schema('icon_recipe',recipe);ref=store.put_json_object(recipe)
        updated=bump_revision(copy.deepcopy(doc),{'operation_id':operation_id,'kind':'task_update','description':'Confirmed icon scope; no dispatch','read_set':[]})
        require_writer(updated,'icon-quality.v1');updated['icon_recipes']=[*doc.get('icon_recipes',[]),ref]
        return operations.commit_locked(store,document=updated,base_revision=base_revision,operation_id=operation_id,kind='icons.confirm',digest=rd,
            result={'status':'confirmed','revision_id':updated['revision_id'],'recipe_id':recipe['recipe_id'],'recipe_ref':ref,'model_calls':0})


def validate_change(store,doc,value):
    recipe,_=_owned(store,doc,ref=value['icon_recipe_ref'])
    if value.get('mode')!='trial' or value['max_calls']!=0 or value.get('references') or value.get('style_recipe_ref'):fail('mode','icon repairs require zero-call SVG trials')
    ids=[t['page_id'] for t in value['targets']];anchors={t['page_id']:t for t in recipe['input']['targets']}
    if not ids or len(ids)!=len(set(ids)) or any(pid not in anchors for pid in ids):fail('targets','select explicit recipe pages')
    if value['instruction']!=recipe['input']['instruction'] or value['annotation_refs']!=recipe['input']['annotation_refs']:fail('instruction','retain the confirmed requirement and opinions')
    for t in value['targets']:
        a=anchors[t['page_id']]; e=_entry(doc,t['page_id'])
        if t.get('stage')!='repair' or t['layer']!='svg' or t['page_ref']!=a['page_ref'] or t['artifact_ref']!=a['svg_ref']:fail('targets','target differs from confirmed icon recipe')
        if e['page']!=a['page_ref'] or e['svg']!=a['svg_ref'] or e['blueprint']!=a['blueprint_ref']:fail('targets','icon target changed',True)
        for icon in a['icons']:
            if icon['method']=='reuse':_sample(store,doc,icon)
    return recipe


@operations.public
def plan(project, *, input):
    if not isinstance(input,dict) or set(input)!={'recipe_id','page_ids'}:fail('input','provide recipe_id and explicit page_ids')
    store=Store(project_path(project));doc=load_snapshot(store);recipe,ref=_owned(store,doc,input['recipe_id']);anchors={t['page_id']:t for t in recipe['input']['targets']}
    ids=input['page_ids']
    if not isinstance(ids,list) or not ids or any(p not in anchors for p in ids):fail('page_ids','select confirmed target pages')
    value={'schema_version':'change_intent.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],
           'intent':'icon_repair','instruction':recipe['input']['instruction'],'annotation_refs':recipe['input']['annotation_refs'],
           'mode':'trial','max_calls':0,'icon_recipe_ref':ref,'targets':[{'page_id':pid,'page_ref':anchors[pid]['page_ref'],
           'layer':'svg','stage':'repair','artifact_ref':anchors[pid]['svg_ref']} for pid in ids]}
    return changes.plan(project,input=value)


def check_scope(store,doc,task,data):
    ref=task.get('stage_request',{}).get('icon_recipe_ref')
    if not ref:return None
    recipe,_=_owned(store,doc,ref=ref);pid=task['scope_pages'][0];target=next(t for t in recipe['input']['targets'] if t['page_id']==pid)
    before=tree(svg_bytes(store,target['svg_ref']));after=tree(data)
    locators=[v for icon in target['icons'] for v in icon['objects']];selected(before,locators);found=nodes(after)
    selected_paths={v['path'] for v in locators}
    outside_ids={n.get('id') for p,n in found.items() if not any(p==a or p.startswith(a+'/') for a in selected_paths) and n.get('id')}
    for loc in locators:
        n=found.get(loc['path'])
        if n is None or any(tag(e) not in GEOMETRY-{'use'} for e in n.iter()):fail('result','replacement must be explicit native geometry at each selected locator')
        if any(e.get('id') in outside_ids for e in n.iter() if e.get('id')):fail('result','replacement ID aliases an unselected object')
        isolated(after,loc['path'])
    def masked(root):
        result=copy.deepcopy(root);items=nodes(result)
        for loc in locators:
            n=items[loc['path']];tail=n.tail;n.clear();n.tail=tail;n.tag='icon-selection'
        return canon(result)
    if masked(before)!=masked(after):fail('result','SVG changed outside the confirmed icon scope')
    expected=nodes(tree(_render_recipe(store,doc,recipe,target,allow_redraw=True)))
    for icon in target['icons']:
        if icon['method'] in ('standard','reuse'):
            for loc in icon['objects']:
                if canon(found[loc['path']])!=canon(expected[loc['path']]):fail('result','standard or reused geometry differs from the confirmed asset and style')
        region=icon['svg_region']
        for loc in icon['objects']:
            box=bounds(isolated(after,loc['path']))
            if box and (box['x'] < region['x']-.002 or box['y'] < region['y']-.002 or box['x']+box['width'] > region['x']+region['width']+.002 or box['y']+box['height'] > region['y']+region['height']+.002):
                fail('result','new icon exceeds the confirmed display region')
    return {'status':'pass','outside_scope_unchanged':True,'recipe_ref':ref,'source_svg_ref':target['svg_ref'],
            'result_sha256':hashlib.sha256(data).hexdigest(),'selected_objects':len(locators)}


def _matrix(root, path):
    from .compiler.geometry import _matrix_product, _parse_transform, _IDENTITY
    matrix=_parse_transform(root.get('transform'),element_id='root');found=nodes(root)
    for i in range(1,len(path.split('/'))):
        n=found['/'.join(path.split('/')[:i])]
        matrix=_matrix_product(matrix,_parse_transform(n.get('transform'),element_id=path))
    return matrix


def _inverse(matrix):
    a,b,c,d,e,f=matrix;det=a*d-b*c
    if abs(det)<1e-10:fail('transform','selected object has a singular ancestor transform')
    return d/det,-b/det,-c/det,a/det,(c*f-d*e)/det,(b*e-a*f)/det


def _matrix_text(matrix):return 'matrix('+ ' '.join(format(v,'.12g') for v in matrix)+')'


def _global_fragment(root,path):
    found=nodes(root);wrapper=ET.Element('{http://www.w3.org/2000/svg}g',{'transform':_matrix_text(_matrix(root,path))})
    # Inherited paint is made explicit; the replacement must not depend on another page's ancestors.
    for n in [root,*[found['/'.join(path.split('/')[:i])] for i in range(1,len(path.split('/')))]]:
        attrs=dict(n.attrib)
        for item in n.get('style','').split(';'):
            if ':' in item:
                k,v=item.split(':',1);attrs[k.strip()]=v.strip()
        for k,v in attrs.items():
            if k in ('fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','opacity','fill-opacity','stroke-opacity'):wrapper.set(k,v)
    wrapper.append(copy.deepcopy(found[path]));return wrapper


@operations.public
def draft(project, *, recipe_id, page_id):
    """Deterministic standard/reuse geometry for a Host to inspect and submit normally."""
    store=Store(project_path(project));doc=load_snapshot(store);recipe,ref=_owned(store,doc,recipe_id)
    target=next((t for t in recipe['input']['targets'] if t['page_id']==page_id),None)
    if not target:fail('page_id','page was not included in recipe')
    current=_entry(doc,page_id)
    if current['svg']!=target['svg_ref']:fail('svg_ref','target changed',True)
    data=_render_recipe(store,doc,recipe,target)
    task={'scope_pages':[page_id],'stage_request':{'icon_recipe_ref':ref}}
    check=check_scope(store,doc,task,data)
    return {'page_id':page_id,'recipe_ref':ref,'svg':data.decode(),'scope_check':check,'model_calls':0,
            'next_action':'Host must inspect and submit through the claimed icon trial task; this is not a candidate or adoption'}


@operations.public
def preview(project, *, proposal_id, page_id):
    """Derived fixed proposal SVG; never a candidate or an actual PPT preview."""
    store=Store(project_path(project));value=store.read_object_json(_proposal_ref(proposal_id))
    validate_schema('icon_recipe',value);current=load_snapshot(store)
    if value['project_id']!=current['project_id']:fail('proposal_id','foreign proposal')
    base=load_snapshot(store,value['base_revision']);target=next((t for t in value['input']['targets'] if t['page_id']==page_id),None)
    if not target:fail('page_id','page absent from proposal')
    raw=_render_recipe(store,base,value,target,allow_redraw=True)
    return {'file':store.put_blob(raw,ext='svg'),'page_id':page_id,'kind':'proposal_svg','model_calls':0,
            'ready_icon_indices':[i for i,n in enumerate(target['icons']) if n['method']!='redraw']}


def _render_recipe(store,doc,recipe,target,allow_redraw=False):
    root=tree(svg_bytes(store,target['svg_ref']));found=nodes(root)
    width,height=map(float,root.get('viewBox').split()[2:]);ns='{http://www.w3.org/2000/svg}'
    for icon in target['icons']:
        if icon['method']=='redraw':
            if allow_redraw: continue
            fail('method','faithful redraw requires the Host to construct explicit geometry')
        region=icon['svg_region'];x,y,w,h=region['x']*width,region['y']*height,region['width']*width,region['height']*height
        group=ET.Element(ns+'g',{'fill':'none','stroke':icon['style']['color'],'stroke-width':str(icon['style']['stroke_width']),
                               'stroke-linecap':'round','stroke-linejoin':'round'})
        if icon['method']=='standard':
            group.set('data-icon-license','lucide-1.49.0')
            group.append(ET.Comment('\nLucide 1.49.0\n'+(CATALOG/'LICENSE.txt').read_text().replace('---','—').replace('--','—')))
            catalog();source=tree((CATALOG/(icon['asset_id']+'.svg')).read_bytes());k=min(w/24,h/24)
            group.set('transform',f'translate({x+(w-24*k)/2} {y+(h-24*k)/2}) scale({k})')
            for child in source:
                if tag(child) in GEOMETRY-{'use'}:group.append(copy.deepcopy(child))
        else:
            candidate,source_icon=_sample(store,doc,icon,require_current=False);source=tree(svg_bytes(store,candidate['result_ref']))
            if any(n.get('data-icon-license')=='lucide-1.49.0' for n in source.iter()):
                group.set('data-icon-license','lucide-1.49.0')
                group.append(ET.Comment('\nLucide 1.49.0\n'+(CATALOG/'LICENSE.txt').read_text().replace('---','—').replace('--','—')))
            sw,sh=map(float,source.get('viewBox').split()[2:]);box=source_icon['svg_region'];sx,sy=box['x']*sw,box['y']*sh
            bw,bh=box['width']*sw,box['height']*sh;k=min(w/bw,h/bh)
            group.set('transform',f'translate({x+(w-bw*k)/2} {y+(h-bh*k)/2}) scale({k}) translate({-sx} {-sy})')
            for loc in source_icon['objects']:
                fragment=_global_fragment(source,loc['path'])
                # Reuse geometry and business details in the target's recorded
                # monochrome paint style. Do not inherit the sample page color.
                for n in fragment.iter():
                    for key in ('fill','stroke'):
                        if n.get(key)==source_icon['style']['color']:n.set(key,icon['style']['color'])
                    if n.get('stroke-width'):
                        n.set('stroke-width',str(float(n.get('stroke-width'))*icon['style']['stroke_width']/source_icon['style']['stroke_width']))
                    if n.get('style'):
                        declarations=[]
                        for item in n.get('style').split(';'):
                            if ':' not in item:continue
                            key,value=item.split(':',1)
                            if key.strip() in ('fill','stroke') and value.strip()==source_icon['style']['color']:value=icon['style']['color']
                            if key.strip()=='stroke-width':value=str(float(value)*icon['style']['stroke_width']/source_icon['style']['stroke_width'])
                            declarations.append(key+':'+value)
                        n.set('style',';'.join(declarations))
                group.append(fragment)
        first=icon['objects'][0]['path'];wrapper=ET.Element(ns+'g',{'transform':_matrix_text(_inverse(_matrix(root,first)))})
        wrapper.append(group)
        for j,loc in enumerate(icon['objects']):
            old=found[loc['path']];replacement=wrapper if j==0 else ET.Element(ns+'g')
            replacement.tail=old.tail;old.attrib.clear();old.attrib.update(replacement.attrib);old.tag=replacement.tag;old.text=replacement.text;old[:]=list(replacement)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
