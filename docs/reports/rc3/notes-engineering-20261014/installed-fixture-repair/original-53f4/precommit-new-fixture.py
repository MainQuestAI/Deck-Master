import sys, importlib.util, json, hashlib
from pathlib import Path
import deck_master
package=Path(deck_master.__file__).resolve().parent
assert 'site-packages' in package.parts and package.is_relative_to(Path(sys.prefix).resolve())
source=Path('/workspace/work/rc3/cards/rc3-02/examples/workbench/w11_browser.py')
spec=importlib.util.spec_from_file_location('actual_new_w11',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(__file__).parent/'precommit-new-fixture';root.mkdir()
project,store,old=m.fixture(root,'DejaVu Sans')
from deck_master import exports
checks=[]
for purpose in ['review','delivery','engineering']:
 result=exports.create(project,purpose=purpose,output_dir=root/purpose)
 import zipfile
 archive=next((root/purpose).glob('*.zip'))
 with zipfile.ZipFile(archive) as z:m.verify_download_notes(z,result['manifest'],store)
 checks.append({'purpose':purpose,'manifest':result['manifest'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
(root/'precommit-checks.json').write_text(json.dumps({'status':'PASS','scope':'precommit example bytehash only; runtime actual original53f4 installed. Not a frozen new source run.','example_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'module':str(package),'checks':checks},indent=2)+'\n')
print('PASS: legitimate notes, actual body-tamper refusal, three real exports notes/privacy/original checks')
