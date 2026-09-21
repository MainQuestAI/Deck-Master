"""Native DrawingML emitter. Paint derived from B0 pptx::_append_color.

B0 2a866cf: keep explicit alpha=0; no business runtime imports.
The current IR contains only source-derived coordinates and visible text.
"""
from pathlib import Path
from PIL import ImageFont, ImageColor
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt


def paint(parent, color, alpha):
    for child in list(parent):
        if child.tag.rsplit('}',1)[-1] in ('solidFill','noFill','gradFill'):
            parent.remove(child)
    if isinstance(color,dict):
        fill=OxmlElement('a:gradFill');fill.set('rotWithShape','1');stops=OxmlElement('a:gsLst')
        for item in color['stops']:
            stop=OxmlElement('a:gs');stop.set('pos',str(round(item['offset']*100000)))
            holder=OxmlElement('a:rPr');paint(holder,item['color'],alpha*item['opacity'])
            stop.append(holder[0][0]);stops.append(stop)
        fill.append(stops)
        if color['kind']=='linear':
            direction=OxmlElement('a:lin');direction.set('ang',str(round(color['angle']*60000)));direction.set('scaled','1')
        else:
            direction=OxmlElement('a:path');direction.set('path','circle');rect=OxmlElement('a:fillToRect')
            for key in ('l','t','r','b'):rect.set(key,'50000')
            direction.append(rect)
        fill.append(direction);parent.append(fill);return
    if color == 'none':
        parent.append(OxmlElement('a:noFill')); return
    fill=OxmlElement('a:solidFill'); rgb=OxmlElement('a:srgbClr')
    rgba=ImageColor.getrgb(color)
    rgb.set('val',''.join(f'{v:02X}' for v in rgba[:3]))
    opacity=OxmlElement('a:alpha');opacity.set('val',str(round(alpha*100000)))
    rgb.append(opacity);fill.append(rgb);parent.append(fill)


def emit(pages, width, height, fonts, output):
    pres=Presentation();pres.slide_width=round(width*9525);pres.slide_height=round(height*9525)
    for page in pages:
        slide=pres.slides.add_slide(pres.slide_layouts[6]); k=min(width/page['width'],height/page['height'])
        ox=(width-page['width']*k)/2;oy=(height-page['height']*k)/2
        def X(x):return round((ox+x*k)*9525)
        def Y(y):return round((oy+y*k)*9525)
        def S(v):return round(v*k*9525)
        for s in page['shapes']:
            if s['kind']=='image':
                from PIL import Image
                x,y,w,h=s['x'],s['y'],s['width'],s['height']
                if s['fit']=='contain':
                    with Image.open(s['asset_path']) as raster:iw,ih=raster.size
                    ratio=min(w/iw,h/ih);x+=(w-iw*ratio)/2;y+=(h-ih*ratio)/2;w=iw*ratio;h=ih*ratio
                sh=slide.shapes.add_picture(s['asset_path'],X(x),Y(y),S(w),S(h));sh.name=s.get('atom_id') or s['id']
                if s['fit']=='cover':
                    with Image.open(s['asset_path']) as raster:iw,ih=raster.size
                    if iw/ih>w/h:sh.crop_left=sh.crop_right=(1-(w/h)/(iw/ih))/2
                    else:sh.crop_top=sh.crop_bottom=(1-(iw/ih)/(w/h))/2
                continue
            if s['kind']=='text':
                family=s['font_family'];key=family+(':bold' if s['bold'] else '')
                filename=fonts.get(key,fonts.get(family))
                if not filename:raise ValueError(f"{page['page_id']}/{s['id']}: font file not supplied: {key}")
                font=ImageFont.truetype(str(filename),size=1000)
                text_width=font.getlength(s['text'])/1000*s['font_size']+max(0,len(s['text'])-1)*s.get('letter_spacing',0)
                w=text_width+s['font_size']*1.0;x=s['x']
                if s['anchor']=='middle':x-=w/2
                if s['anchor']=='end':x-=w
                y=s['y']-s['font_size']*.88;h=s['font_size']*1.5
                # The IR anchor is already in final page coordinates; glyph rotation is
                # applied once through sh.rotation below, so the box stays at the anchor.
                sh=slide.shapes.add_textbox(X(x),Y(y),S(w),S(h))
                tf=sh.text_frame;tf.clear();tf.word_wrap=False;tf.vertical_anchor=MSO_ANCHOR.TOP
                from pptx.enum.text import MSO_AUTO_SIZE
                tf.auto_size=MSO_AUTO_SIZE.NONE
                tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
                p=tf.paragraphs[0];p.alignment={'middle':PP_ALIGN.CENTER,'end':PP_ALIGN.RIGHT}.get(s['anchor'],PP_ALIGN.LEFT)
                p.space_before=p.space_after=Pt(0)
                run=p.add_run();run.text=s['text']
                props=run._r.get_or_add_rPr()
                # Fill properties must precede latin/ea/cs in a:rPr.
                paint(props,s['fill'],s['opacity']*s['fill_opacity'])
                run.font.size=Pt(s['font_size']*k*.75);run.font.name=family;run.font.bold=s['bold']
                for name in ('ea','cs'):
                    e=OxmlElement('a:'+name);e.set('typeface',family);props.append(e)
                # Letter spacing is written once by the api.py post-pass, which
                # keys on the shape name for both native and node emitters.
            elif s['kind'] in ('rect','circle','ellipse'):
                shape=MSO_SHAPE.OVAL if s['kind']!='rect' else MSO_SHAPE.ROUNDED_RECTANGLE if s.get('rx') else MSO_SHAPE.RECTANGLE
                sh=slide.shapes.add_shape(shape,X(s['x']),Y(s['y']),S(s['width']),S(s['height']))
                if shape==MSO_SHAPE.ROUNDED_RECTANGLE:
                    sh.adjustments[0]=min(.5,s['rx']/min(s['width'],s['height']))
            else:
                cmds=list(s.get('commands') or [{('moveTo' if i==0 else 'lineTo'):{'x':p[0],'y':p[1]}} for i,p in enumerate(s['points'])])
                if s['kind']=='polygon':cmds.append({'close':{}})
                pts=[next(iter(c.values())) for c in cmds if 'close' not in c]
                l=min(p['x'] for p in pts);t=min(p['y'] for p in pts);w=max(.01,max(p['x'] for p in pts)-l);h=max(.01,max(p['y'] for p in pts)-t)
                sh=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,X(l),Y(t),S(w),S(h))
                sp=sh._element.spPr
                for old in list(sp):
                    if old.tag.rsplit('}',1)[-1]=='prstGeom':sp.remove(old)
                geom=OxmlElement('a:custGeom')
                for tag in ('avLst','gdLst','ahLst','cxnLst'):geom.append(OxmlElement('a:'+tag))
                rect=OxmlElement('a:rect')
                for name,val in [('l','0'),('t','0'),('r','r'),('b','b')]:rect.set(name,val)
                geom.append(rect);lst=OxmlElement('a:pathLst');path=OxmlElement('a:path');path.set('w',str(max(1,S(w))));path.set('h',str(max(1,S(h))))
                for c in cmds:
                    op=next(iter(c));node=OxmlElement('a:'+('lnTo' if op=='lineTo' else op))
                    if op!='close':
                        point=OxmlElement('a:pt');point.set('x',str(S(c[op]['x']-l)));point.set('y',str(S(c[op]['y']-t)));node.append(point)
                    path.append(node)
                lst.append(path);geom.append(lst);sp.append(geom)
            if s.get('rotation'):sh.rotation=s['rotation']
            sh.name=s.get('atom_id') or s['id']
            for node in list(sh._element):
                if node.tag.rsplit('}',1)[-1]=='style':sh._element.remove(node)
            if s['kind']!='text':
                # CT_ShapeProperties order: geometry, fill, a:ln, effectLst.
                paint(sh._element.spPr,s['fill'],s['opacity']*s['fill_opacity'])
                line=sh._element.spPr.get_or_add_ln();line.set('w',str(S(s['stroke_width'])))
                paint(line,s['stroke'],s['opacity']*s['stroke_opacity'])
                caps={'butt':'flat','round':'rnd','square':'sq'}
                joins={'miter':'miter','round':'round','bevel':'bevel'}
                if s.get('stroke_linecap','butt') not in caps or s.get('stroke_linejoin','miter') not in joins:
                    raise ValueError(f"{page['page_id']}/{s['id']}: unsupported stroke cap/join")
                line.set('cap',caps[s.get('stroke_linecap','butt')])
                join=OxmlElement('a:'+joins[s.get('stroke_linejoin','miter')])
                if s.get('stroke_linejoin','miter')=='miter':join.set('lim',str(round(s.get('stroke_miterlimit',4)*100000)))
                line.append(join)
                sh._element.spPr.append(OxmlElement('a:effectLst'))
            else:
                sh._element.spPr.append(OxmlElement('a:effectLst'))
    pres.save(output)
