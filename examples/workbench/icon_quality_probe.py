"""Offline catalog/native stroke probe; synthetic geometry, zero model calls."""
import argparse
import json
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from deck_master import icons, pipeline
from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.compiler.svg import parse_svg


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--node');parser.add_argument('--artifact-module');parser.add_argument('--render',action='store_true')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    entries=[];inputs=[];expected=[]
    for asset in icons.catalog()['icons']:
        root=icons.tree((icons.CATALOG/(asset['id']+'.svg')).read_bytes())
        root.set('stroke','#1478ff');root.set('data-icon-license','lucide-1.49.0')
        # Independent oracle: the bundled source declares these properties.
        assert root.get('stroke-linecap')=='round' and root.get('stroke-linejoin')=='round'
        expected.append(('round','round',float(root.get('stroke-width'))))
        path=args.out/(asset['id']+'.svg');path.write_bytes(ET.tostring(root))
        entries.append(parse_svg(path.read_bytes(),page_id=asset['id']));inputs.append(SvgInput(asset['id'],path))
    caps=('butt','round','square');joins=('miter','round','bevel')
    for cap,join in zip(caps,joins):
        name=cap+'-'+join;path=args.out/(name+'.svg')
        path.write_text(f'<svg viewBox="0 0 24 24"><path id="duplicate" d="M4 8L12 8L12 18" fill="none" stroke="#1478ff" stroke-width="2" stroke-linecap="{cap}" stroke-linejoin="{join}"/><path id="duplicate" d="M4 20L20 20" fill="none" stroke="#1478ff" stroke-width="3" stroke-linecap="{cap}" stroke-linejoin="{join}"/></svg>')
        entries.append(parse_svg(path.read_bytes(),page_id=name));inputs.append(SvgInput(name,path));expected.append((cap,join,None))
    result=compile_deck(inputs,CompileOptions(node_executable=args.node,artifact_module=args.artifact_module,width_px=240,height_px=240),args.out/'compiled')
    ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'};records=[]
    with zipfile.ZipFile(result.pptx_path) as archive:
        assert b'ISC License' in archive.read('docProps/core.xml')
        for index,entry in enumerate(entries,1):
            root=ET.fromstring(archive.read(f'ppt/slides/slide{index}.xml'));shapes=root.findall('p:cSld/p:spTree/p:sp',ns)
            assert not root.findall('.//p:pic',ns) and len(shapes)==len(entry['shapes'])
            cap,join,width=expected[index-1]
            for shape_index,(shape,source) in enumerate(zip(shapes,entry['shapes'])):
                line=shape.find('p:spPr/a:ln',ns)
                assert line.get('cap')=={'butt':'flat','round':'rnd','square':'sq'}[cap]
                assert line.find('a:'+join,ns) is not None
                assert int(line.get('w'))==round((width if width is not None else (2,3)[shape_index])*10*9525)
            records.append({'icon':entry['page_id'],'native_shapes':len(shapes),'stroke_properties':'pass'})
    renders=pipeline.render_deck(result.pptx_path,args.out/'rendered',fonts={}) if args.render else []
    assert not args.render or len(renders)==len(inputs)
    report={'synthetic':True,'model_calls':0,'backend':'node' if args.node else 'python','icons':24,'pages':len(inputs),'actual_renders':len(renders),'checks':records,'status':'pass'}
    (args.out/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
