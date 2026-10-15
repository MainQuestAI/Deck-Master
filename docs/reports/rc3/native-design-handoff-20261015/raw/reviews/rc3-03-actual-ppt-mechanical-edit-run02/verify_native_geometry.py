"""Read-only native geometry and changed-ZIP-member verification."""
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
a=objects(base['ppt/slides/slide1.xml']);other=read(r/'D-real-recompile/deck.pptx');b=objects(other['ppt/slides/slide1.xml'])
assert len(a)==len(b)==len(ir['shapes'])
positions=[]
for original,moved,source in zip(a,b,ir['shapes']):
    name=lambda sp:sp.find('p:nvSpPr/p:cNvPr',ns).get('name')
    assert name(original)==name(moved)
    offa=original.find('p:spPr/a:xfrm/a:off',ns);offb=moved.find('p:spPr/a:xfrm/a:off',ns)
    delta=[int(offb.get(k))-int(offa.get(k)) for k in ['x','y']]
    in_group=source['id'].split(':')[0] in group_ids
    assert delta==([0,2*9525] if in_group else [0,0]),(name(original),delta,in_group)
    positions.append({'name':name(original),'original_source_id':source['id'],'part_of_main_chain':in_group,'delta_emu':delta})
frame=next(sp for sp in b if sp.find('p:nvSpPr/p:cNvPr',ns).get('name')=='main-chain-frame')
off=frame.find('p:spPr/a:xfrm/a:off',ns);ext=frame.find('p:spPr/a:xfrm/a:ext',ns)
x,y=int(off.get('x'))/9525,int(off.get('y'))/9525;w,h=int(ext.get('cx'))/9525,int(ext.get('cy'))/9525
stroke=1.5/2
margins={'left':x-stroke,'right':1600-(x+w+stroke),'top':y-stroke,'bottom':900-(y+h+stroke)}
assert min(margins.values())>=48
result={'status':'PASS_actual_geometry_delta_only','negative_copy_changed_zip_members':changed,'D_all_native_offsets':positions,'D_group_frame_bounds_px':[x,y,w,h],'D_frame_external_margins_with_halfstroke_px':margins,'D_non_group_objects_unchanged':True,'notes_and_other_zip_members_preserved_in_B_C':True}
record=r/'native-geometry-and-zip-delta-verification.json'
assert json.loads(record.read_text())==result
print(json.dumps({'group_moved_shape_count':sum(p['part_of_main_chain'] for p in positions),'total_shapes':len(positions),'margins':margins,'B_C_changed_members':changed},ensure_ascii=False))
