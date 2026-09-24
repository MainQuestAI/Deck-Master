"""Explicit SVG paint projection with preserved zero-valued opacity."""
import math
import re


def gradient(raw, definitions, identity):
    if not isinstance(raw,str) or not raw.startswith('url('):
        return raw
    match=re.fullmatch(r'url\(\s*#([^\s)]+)\s*\)',raw)
    if not match or match[1] not in definitions:
        raise ValueError(f'{identity}: unresolved local gradient')
    node=definitions[match[1]]
    tag=node.tag.rsplit('}',1)[-1]
    if tag not in ('linearGradient','radialGradient'):
        raise ValueError(f'{identity}: paint reference is not a gradient')
    if node.get('gradientUnits','objectBoundingBox')!='objectBoundingBox' or node.get('gradientTransform'):
        raise ValueError(f'{identity}: gradient requires objectBoundingBox without gradientTransform')
    if node.get('spreadMethod','pad')!='pad' or any(k.endswith('href') for k in node.attrib):
        raise ValueError(f'{identity}: gradient inheritance/repeating spread unsupported')
    def fraction(raw):
        value=float(raw[:-1])/100 if raw.endswith('%') else float(raw)
        if not math.isfinite(value):raise ValueError(f'{identity}: nonfinite gradient number')
        return value
    stops=[]
    for child in node:
        if child.tag.rsplit('}',1)[-1]!='stop':raise ValueError(f'{identity}: unsupported gradient child')
        attrs=dict(child.attrib)
        for item in attrs.pop('style','').split(';'):
            if item.strip():
                key,value=item.split(':',1);attrs[key.strip()]=value.strip()
        if set(attrs)-{'offset','stop-color','stop-opacity','id'}:raise ValueError(f'{identity}: unsupported gradient stop attribute')
        offset=fraction(attrs.get('offset','0'));alpha=fraction(attrs.get('stop-opacity','1'))
        if not 0<=alpha<=1 or not 0<=offset<=1 or stops and offset<stops[-1]['offset']:
            raise ValueError(f'{identity}: invalid gradient stop order/range')
        stops.append({'offset':offset,'color':attrs.get('stop-color','#000000'),'opacity':alpha})
    if len(stops)<2:raise ValueError(f'{identity}: gradient needs at least two stops')
    if tag=='linearGradient':
        x1,y1,x2,y2=[fraction(node.get(k,v)) for k,v in [('x1','0'),('y1','0'),('x2','1'),('y2','0')]]
        # DrawingML linear fills span the bounding box; reject shortened vectors.
        if (x1,y1,x2,y2) not in (
            (0,0,1,0),(1,0,0,0),(0,0,0,1),(0,1,0,0),
            (0,0,1,1),(1,1,0,0),(1,0,0,1),(0,1,1,0),
        ):
            raise ValueError(f'{identity}: only full-edge or corner-to-corner gradient vectors supported')
        return {'kind':'linear','angle':math.degrees(math.atan2(y2-y1,x2-x1))%360,'stops':stops}
    if any(fraction(node.get(k,'.5'))!=.5 for k in ('cx','cy','r','fx','fy')):
        raise ValueError(f'{identity}: only centered radial gradient supported')
    return {'kind':'radial','stops':stops}
