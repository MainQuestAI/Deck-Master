"""Actual final-v3 native deltas, font fields, physical size and ZIP preservation."""
from pathlib import Path
import json
import xml.etree.ElementTree as E
import zipfile

r=Path(__file__).resolve().parent
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
def read(p):
    with zipfile.ZipFile(p) as z:return {n:z.read(n) for n in z.namelist()}
def objects(b):return E.fromstring(b).findall('.//p:sp',ns)
base=read(r/'inputs/original.pptx')
changed={}
for key,file in [('B','B-native-cell-row-ownership-swapped.pptx'),('C','C-native-edge-and-visible-arrow-reversed.pptx')]:
    other=read(r/file);assert base.keys()==other.keys()
    members=[n for n in base if base[n]!=other[n]];assert members==['ppt/slides/slide1.xml']
    changed[key]=members
svg=E.fromstring((r/'inputs/original.svg').read_bytes());g=next(x for x in svg if x.get('id')=='main-chain')
group_ids={x.get('id') for x in g.iter() if x.get('id')}
ir=json.loads((r/'inputs/actual-svg-ir.json').read_text())
effective=json.loads((r/'inputs/actual-effective-design.json').read_text());canvas=effective['canvas']
scale=min(canvas['slide_width_in']*96/ir['width'],canvas['slide_height_in']*96/ir['height'])
assert scale==0.8
a=objects(base['ppt/slides/slide1.xml']);other=read(r/'D-real-recompile/deck.pptx');b=objects(other['ppt/slides/slide1.xml'])
assert len(a)==len(b)==len(ir['shapes'])
positions=[]
for original,moved,source in zip(a,b,ir['shapes']):
    name=lambda sp:sp.find('p:nvSpPr/p:cNvPr',ns).get('name')
    assert name(original)==name(moved)
    offa=original.find('p:spPr/a:xfrm/a:off',ns);offb=moved.find('p:spPr/a:xfrm/a:off',ns)
    delta=[int(offb.get(k))-int(offa.get(k)) for k in ['x','y']]
    in_group=source['id'].split(':')[0] in group_ids
    assert delta==([0,round(2*scale*9525)] if in_group else [0,0]),(name(original),delta,in_group)
    positions.append({'name':name(original),'original_source_id':source['id'],'part_of_main_chain':in_group,'delta_emu':delta})
frame=next(sp for sp in b if sp.find('p:nvSpPr/p:cNvPr',ns).get('name')=='main-chain-frame')
off=frame.find('p:spPr/a:xfrm/a:off',ns);ext=frame.find('p:spPr/a:xfrm/a:ext',ns)
x,y=int(off.get('x'))/9525,int(off.get('y'))/9525;w,h=int(ext.get('cx'))/9525,int(ext.get('cy'))/9525
stroke=1.5*scale/2
physical_margins={'left':x-stroke,'right':canvas['slide_width_in']*96-(x+w+stroke),'top':y-stroke,'bottom':canvas['slide_height_in']*96-(y+h+stroke)}
logical_margins={k:v/scale for k,v in physical_margins.items()}
assert min(logical_margins.values())>=48
physical_checks={}
for label,path in [('original',r/'inputs/original.pptx'),('A',r/'A-python-object-text-edited.pptx'),('B',r/'B-native-cell-row-ownership-swapped.pptx'),('C',r/'C-native-edge-and-visible-arrow-reversed.pptx'),('D',r/'D-real-recompile/deck.pptx')]:
    data=read(path);size=E.fromstring(data['ppt/presentation.xml']).find('p:sldSz',ns)
    actual=[int(size.get('cx')),int(size.get('cy'))]
    assert actual==[12192000,6858000]
    root=E.fromstring(data['ppt/slides/slide1.xml'])
    points=[int(p.get('sz'))/100 for p in root.findall('.//a:rPr',ns) if p.get('sz') is not None]
    assert sorted(set(points))==[18,30]
    physical_checks[label]={'actual_emu':actual,'actual_point_sizes':sorted(set(points)),'explicit_point_run_count':len(points)}
result={'status':'PASS_actual_final_v3_geometry_physical_size_and_font_fields','scale':scale,
 'native_shape_count':len(positions),'moved_group_shape_count':sum(x['part_of_main_chain'] for x in positions),
 'unchanged_non_group_shape_count':sum(not x['part_of_main_chain'] for x in positions),
 'negative_copy_changed_zip_members':changed,'D_all_native_offsets':positions,
 'D_group_frame_bounds_96ppi_px':[x,y,w,h],
 'D_external_margins_physical_96ppi_px':physical_margins,'D_external_margins_svg_logical_px':logical_margins,
 'all_copy_physical_size_and_font_fields':physical_checks,
 'D_non_group_objects_unchanged':True,'notes_and_other_zip_members_preserved_in_B_C':True}
with (r/'native-geometry-and-zip-delta-verification.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({k:result[k] for k in ['native_shape_count','moved_group_shape_count','unchanged_non_group_shape_count','D_external_margins_svg_logical_px','all_copy_physical_size_and_font_fields']},ensure_ascii=False,indent=2))
