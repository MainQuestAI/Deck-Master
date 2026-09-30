"""Copy the original synthetic pressure checkpoint without regenerating its data.

The input project is never written. Manifest, Candidate, Attempt and immutable
object bytes are unchanged; only a NEW copy's current pointer selects the exact
recorded factory revision. This gives repeatable background task states after a
failed pressure run consumes the reserved tasks. Never use with a user project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from deck_master.local_state import write_json
from deck_master.store import Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();source=args.fixture.resolve();out=args.out.resolve()
    manifest_bytes=(source/'manifest.json').read_bytes();m=json.loads(manifest_bytes)
    assert m['factory']=='w01-pressure.v1' and m['synthetic'] and m['page_count']==300 and m['candidate_count']==1500 and m['attempt_count']==4500
    source_store=Store(source/'project'); original_pointer=source_store.read_current()
    doc=source_store.load_document(m['fixture_revision'])
    assert len(doc['pages'])==300 and len(doc['candidates'])==1500
    out.mkdir(parents=True,exist_ok=False);target=out/'project/.deckmaster';target.mkdir(parents=True)
    for name in ('objects','revisions'):
        shutil.copytree(source_store.deck_root/name,target/name)
    pointer={'format':'deckmaster-current.v2','revision_id':doc['revision_id'],'minimum_writer':doc['compatibility']['minimum_writer']}
    write_json(target/'current.json',pointer)
    sample=source_store.deck_root/'workbench/sample.json'
    if sample.exists():
        (target/'workbench').mkdir(exist_ok=True);shutil.copyfile(sample,target/'workbench/sample.json')
    (out/'manifest.json').write_bytes(manifest_bytes)
    copied=Store(out/'project'); candidate_hashes=[];attempts=set()
    for ref in doc['candidates']:
        candidate=copied.read_object_json(ref);candidate_hashes.append(ref['sha256'])
        # Candidate history references are verified by normal candidate reads in
        # pressure; all underlying object bytes are checked below.
    count=0
    for path in copied.objects_dir.glob('*/*'):
        if path.is_file():
            assert hashlib.sha256(path.read_bytes()).hexdigest()==path.stem;count+=1
    assert source_store.read_current()==original_pointer
    report={'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),'selected_factory_revision':doc['revision_id'],
            'source_pointer_unchanged':True,'copied_objects_verified':count,'candidate_refs':len(candidate_hashes),
            'same_manifest_bytes':True,'regenerated_images_candidates_attempts':False,'scope':'new synthetic checkpoint copy only'}
    (out/'checkpoint-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
