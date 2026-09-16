"""Explicit, self-contained SVG subset; no old runtime or external resources."""
from __future__ import annotations

import re
import math
import copy
from .geometry import _parse_path, commands_to_svg_path, _parse_transform, _matrix_product, _apply_matrix, _IDENTITY
import xml.etree.ElementTree as ET


class SvgError(ValueError):
    pass


def parse_svg(data: bytes, *, page_id: str) -> dict:
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.I):
        raise SvgError(f'{page_id}: XML entities/DOCTYPE are forbidden')
    root = ET.fromstring(data)
    def numbers(raw):
        return [float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', raw)]
    box = numbers(root.get('viewBox', ''))
    if len(box) != 4 or box[:2] != [0, 0] or min(box[2:]) <= 0:
        raise SvgError(f'{page_id}: require positive viewBox starting at 0 0')
    shapes = []
    definitions = {e.get('id'): e for e in root.iter() if e.get('id')}
    active_uses = set()
    def transformed(base, matrix):
        a,b,c,d,_,_=matrix
        sx=math.hypot(a,b);sy=math.hypot(c,d)
        base['stroke_width'] *= (sx+sy)/2
        if base['stroke']!='none' and abs(sx-sy)>1e-6:
            raise SvgError(f"{page_id}/{base['id']}: nonuniform transformed stroke requires an explicit outline")
        if matrix == _IDENTITY:return base
        def point(x,y):return list(_apply_matrix(matrix,(x,y)))
        kind=base['kind']
        if kind=='text':
            if abs(sx-sy)>1e-6:raise SvgError(f"{page_id}/{base['id']}: nonuniform text scaling unsupported")
            base['x'],base['y']=point(base['x'],base['y']);base['font_size']*=sx
            base['rotation']=math.degrees(math.atan2(b,a));base['letter_spacing']*=sx
        elif kind in ('circle','ellipse') and abs(sx-sy)<1e-6 and abs(base['width']-base['height'])<1e-6:
            cx,cy=point(base['x']+base['width']/2,base['y']+base['height']/2)
            base.update(x=cx-base['width']*sx/2,y=cy-base['height']*sy/2,width=base['width']*sx,height=base['height']*sy)
        elif kind in ('rect','circle','ellipse'):
            x,y,w,h=base['x'],base['y'],base['width'],base['height']
            if abs(b)<1e-9 and abs(c)<1e-9 and a>0 and d>0:
                base.update(x=a*x+matrix[4],y=d*y+matrix[5],width=w*a,height=h*d,rx=base.get('rx',0)*min(a,d))
            else:
                if kind=='rect':
                    if base.get('rx'):raise SvgError(f"{page_id}/{base['id']}: rotated rounded rect requires explicit path")
                    pts=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
                else:
                    # Include analytic extrema; do not infer bounds from four samples.
                    rx,ry=w/2,h/2
                    angles=[i*math.pi/64 for i in range(128)]
                    angles += [math.atan2(c*ry,a*rx)+j*math.pi for j in (0,1)]
                    angles += [math.atan2(d*ry,b*rx)+j*math.pi for j in (0,1)]
                    pts=[[x+rx+rx*math.cos(t),y+ry+ry*math.sin(t)] for t in sorted(t%(2*math.pi) for t in angles)]
                base['kind']='polygon';base['points']=[point(*p) for p in pts]
        elif 'points' in base:base['points']=[point(*p) for p in base['points']]
        elif 'commands' in base:
            base['commands']=[{op:dict(zip(('x','y'),point(p['x'],p['y'])))} if op!='close' else command for command in base['commands'] for op,p in command.items()]
        return base
    def visit(el, inherited, matrix=_IDENTITY):
        tag = el.tag.split('}')[-1]
        el = copy.deepcopy(el)
        if el.get('style'):
            for declaration in el.attrib.pop('style').split(';'):
                if not declaration.strip():continue
                key,value=declaration.split(':',1)
                if key.strip() not in ('fill','stroke','stroke-width','opacity','fill-opacity','stroke-opacity','font-family','font-size','font-weight','text-anchor'):
                    raise SvgError(f'{page_id}: unsupported style property {key}')
                el.set(key.strip(),value.strip())
        matrix=_matrix_product(matrix,_parse_transform(el.attrib.pop('transform',None),element_id=el.get('id',tag)))
        attrs = {**inherited, **el.attrib}
        identity = el.get('id', tag)
        for key in el.attrib:
            if key.startswith('on') or key in ('style', 'transform', 'filter', 'mask', 'clip-path') or (key.endswith('href') and tag!='use'):
                raise SvgError(f'{page_id}/{identity}: unsupported {key}; flatten to explicit geometry')
        if tag=='defs':return
        if tag=='use':
            href=el.get('href') or el.get('{http://www.w3.org/1999/xlink}href','')
            if not href.startswith('#') or href[1:] not in definitions or href in active_uses:
                raise SvgError(f'{page_id}/{identity}: unresolved or cyclic local use')
            target=copy.deepcopy(definitions[href[1:]])
            if target.tag.split('}')[-1]=='symbol':target.tag='{http://www.w3.org/2000/svg}g'
            active_uses.add(href)
            translated=_matrix_product(matrix,(1.,0.,0.,1.,float(el.get('x',0)),float(el.get('y',0))))
            visit(target,inherited,translated);active_uses.remove(href);return
        if any('url(' in value for value in el.attrib.values()):
            raise SvgError(f'{page_id}/{identity}: referenced paint is not in the current subset')
        if tag in ('title', 'desc', 'metadata'):
            return
        if tag not in ('svg','g','rect','circle','ellipse','line','polygon','polyline','path','text','tspan'):
            raise SvgError(f'{page_id}/{identity}: unsupported {tag}; provide native geometry')
        inherited_keys=('fill','stroke','stroke-width','font-family','font-size','font-weight','text-anchor','opacity','fill-opacity','stroke-opacity')
        if tag in ('svg','g'):
            style={key:attrs[key] for key in inherited_keys if key in attrs}
            # SVG group opacity multiplies ancestor opacity.
            if 'opacity' in el.attrib:
                style['opacity']=str(float(inherited.get('opacity','1'))*float(el.attrib['opacity']))
            for child in el: visit(child,style,matrix)
            return
        def num(key, default=0):
            raw=attrs.get(key,str(default))
            try:
                value=float(raw)
                if not math.isfinite(value):raise ValueError()
                return value
            except ValueError: raise SvgError(f'{page_id}/{identity}: {key} must use unitless pixels')
        base=dict(id=identity,kind=tag,fill=attrs.get('fill','#000000'),stroke=attrs.get('stroke','none'),stroke_width=num('stroke-width',1),opacity=num('opacity',1),fill_opacity=num('fill-opacity',1),stroke_opacity=num('stroke-opacity',1),atom_id=el.get('data-atom-id'))
        if 'opacity' in el.attrib:
            base['opacity'] = float(inherited.get('opacity',1))*float(el.attrib['opacity'])
        if tag=='text':
            children=list(el)
            if any(x.tag.split('}')[-1]!='tspan' for x in children):
                raise SvgError(f'{page_id}/{identity}: only direct tspan in text')
            runs=[]
            if el.text and el.text.strip(): runs.append((el.text,attrs))
            cursor={**attrs}
            for child in children:
                if list(child): raise SvgError(f'{page_id}/{identity}: nested tspan unsupported')
                c={**attrs,**child.attrib}
                c['x']=c.get('x',cursor.get('x','0'))
                c['y']=str(float(c.get('y',cursor.get('y','0')))+float(c.get('dy','0')))
                if 'dx' in c: c['x']=str(float(c['x'])+float(c['dx']))
                runs.append((child.text or '',c));cursor=c
                if child.tail and child.tail.strip(): raise SvgError(f'{page_id}/{identity}: trailing inline text unsupported')
            for i,(text,a) in enumerate(runs):
                shapes.append(transformed({**base,'id':f'{identity}:{i}','text':text,'x':float(a.get('x',0)), 'y':float(a.get('y',0)), 'font_size':float(a.get('font-size',24)), 'font_family':a.get('font-family','Noto Sans SC').split(',')[0].strip(' \"\''), 'letter_spacing':float(a.get('letter-spacing',0)),'bold':a.get('font-weight','400') in ('bold','600','700','800','900'),'anchor':a.get('text-anchor','start'),'fill':a.get('fill',base['fill'])},matrix))
            return
        if tag=='tspan': raise SvgError(f'{page_id}/{identity}: orphan tspan')
        if tag=='rect': base.update(x=num('x'),y=num('y'),width=num('width'),height=num('height'),rx=num('rx'))
        elif tag in ('circle','ellipse'):
            rx=num('r') if tag=='circle' else num('rx');ry=num('r') if tag=='circle' else num('ry')
            base.update(x=num('cx')-rx,y=num('cy')-ry,width=2*rx,height=2*ry)
        elif tag=='line': base['points']=[[num('x1'),num('y1')],[num('x2'),num('y2')]]
        elif tag in ('polygon','polyline'):
            pts=numbers(attrs.get('points',''))
            if len(pts)<4 or len(pts)%2: raise SvgError(f'{page_id}/{identity}: invalid points')
            base['points']=[pts[i:i+2] for i in range(0,len(pts),2)]
        elif tag=='path': base['commands']=parse_path(commands_to_svg_path(_parse_path(attrs.get('d',''),element_id=identity)),f'{page_id}/{identity}')
        shapes.append(transformed(base,matrix))
    visit(root,{})
    return dict(page_id=page_id,width=box[2],height=box[3],shapes=shapes)


def parse_path(d: str, identity: str) -> list:
    """M/L/H/V/C/Q/Z, including relative forms; curves flattened to 0.2px."""
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',d)
    if re.sub(r'[\s,]','',re.sub(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?','',d)):
        raise SvgError(f'{identity}: invalid path data')
    out=[]; pos=[0.,0.]; start=pos[:]; i=0; command=None
    def emit(p):
        out.append({'lineTo':dict(x=p[0],y=p[1])})
    def curve(points,depth=0):
        a,b=points[0],points[-1]
        dx,dy=b[0]-a[0],b[1]-a[1]; length=(dx*dx+dy*dy)**.5
        error=max(((abs(dx*(a[1]-p[1])-(a[0]-p[0])*dy)/length) if length else ((p[0]-a[0])**2+(p[1]-a[1])**2)**.5) for p in points[1:-1])
        if error<=.2 or depth>=16: emit(b);return
        levels=[points]
        while len(levels[-1])>1:
            row=levels[-1];levels.append([[(u[0]+v[0])/2,(u[1]+v[1])/2] for u,v in zip(row,row[1:])])
        curve([row[0] for row in levels],depth+1);curve([row[-1] for row in reversed(levels)],depth+1)
    while i<len(tokens):
        if tokens[i].isalpha(): command=tokens[i];i+=1
        if command is None: raise SvgError(f'{identity}: missing path command')
        op=command.upper();relative=command.islower()
        if op=='Z': out.append({'close':{}});pos=start[:];command=None;continue
        counts={'M':2,'L':2,'H':1,'V':1,'C':6,'Q':4}
        if op not in counts: raise SvgError(f'{identity}: unsupported path command {command}')
        n=counts[op]
        try: vals=list(map(float,tokens[i:i+n]))
        except ValueError: raise SvgError(f'{identity}: incomplete path command')
        if len(vals)!=n: raise SvgError(f'{identity}: incomplete path command')
        i+=n
        if op in ('H','V'):
            new=pos[:];axis=0 if op=='H' else 1;new[axis]=vals[0]+(pos[axis] if relative else 0);emit(new);pos=new
        else:
            points=[[vals[j]+(pos[0] if relative else 0),vals[j+1]+(pos[1] if relative else 0)] for j in range(0,n,2)]
            if op=='M': out.append({'moveTo':dict(x=points[0][0],y=points[0][1])});start=points[0];command='l' if relative else 'L'
            elif op=='L': emit(points[0])
            else: curve([pos]+points)
            pos=points[-1]
    return out
