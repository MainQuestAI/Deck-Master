"""Read-only census of this actual final-v3 original and its four copies."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
root=Path(__file__).resolve().parent
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
result={}
for name,path in [('original',root/'inputs/original.pptx'),('A',root/'A-python-object-text-edited.pptx'),('B',root/'B-native-cell-row-ownership-swapped.pptx'),('C',root/'C-native-edge-and-visible-arrow-reversed.pptx'),('D',root/'D-real-recompile/deck.pptx')]:
    with zipfile.ZipFile(path) as archive:
        slide=ET.fromstring(archive.read('ppt/slides/slide1.xml'))
        text=[t.text or '' for t in slide.findall('.//a:t',ns)]
        result[name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'native_shapes':len(slide.findall('.//p:sp',ns)),'text_runs':len(text),
          'visible_characters':len(''.join(text)),'pictures':len(slide.findall('.//p:pic',ns)),
          'media_members':[n for n in archive.namelist() if n.startswith('ppt/media/')]}
        assert result[name]['pictures']==0 and not result[name]['media_members']
with (root/'native-package-measurements.json').open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,sort_keys=True);stream.write('\n')
print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
