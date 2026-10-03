"""External R1/R2 full production pipeline and disposable preview identity."""
import json
from pathlib import Path

import pytest
from PIL import Image

from deck_master import candidate_preview, icons, pipeline, readback_text, service
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from deck_master.store import Store
from test_readback import _atom_page, FAMILY
from test_external_review_readback import text
from test_icon_quality import icon_store, confirm, input_for, dispatch, start, accept

pytestmark=pytest.mark.render


@pytest.mark.parametrize('case,expected',[('duplicate-hidden','fail'),('duplicate-visible','pass'),('no-fill','fail'),('solid','pass'),('partial-gradient','pass')])
def test_actual_render_and_persisted_produce_report(tmp_path,case,expected):
    duplicate=case.startswith('duplicate');words=['30%','30%'] if duplicate else ['REPORT','Body']
    page={'schema_version':'deck_page_package.v2',**_atom_page(words)}
    path=tmp_path/'project';service.create(path,brief='Synthetic external review evidence',draft={'pages':[page]},
        design={'canvas':{'width_px':200,'height_px':100,'slide_width_in':200/96,'slide_height_in':100/96,'fit':'contain'}})
    body=text(words[0]);attrs='data-atom-id="atom:p1:block:b1:text"' if not duplicate else ''
    if case=='duplicate-hidden':attrs+=' opacity="0"'
    if case=='no-fill':attrs+=' fill="none"'
    if case=='partial-gradient':
        body='<defs><linearGradient id="paint"><stop offset="0" stop-opacity="1"/><stop offset="1" stop-opacity="0"/></linearGradient></defs>'+body
        attrs+=' fill="url(#paint)"'
    body+=text(words[1],60,attrs);svg=tmp_path/'source.svg';svg.write_text('<svg viewBox="0 0 200 100">'+body+'</svg>')
    pipeline.run([pipeline.executable('rsvg-convert'),str(svg),'-o',str(tmp_path/'source.png')])
    store=Store(path);doc=store.load_document();updated=bump_revision(doc,{'operation_id':'attach-proof-svg','kind':'artifact_adoption','description':'synthetic SVG fixture','read_set':[]})
    updated['pages'][0]['svg']=pipeline.artifact(store,svg,'svg',page_id='p1');store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='attach-proof-svg')
    report=pipeline.produce(path);doc=store.load_document()
    stored=json.loads(store.read_object_bytes(store.read_object_json(doc['outputs']['render_report'])['file']))
    assert report['status']==stored['status']==expected
    rendered=store.read_object_json(doc['pages'][0]['ppt_preview'])['file'];png=tmp_path/'actual.png';png.write_bytes(store.read_object_bytes(rendered))
    for filename in ('source.png','actual.png'):
        with Image.open(tmp_path/filename) as image:
            background=Image.new('RGBA',image.size,'white');background.alpha_composite(image.convert('RGBA'))
            rgb=background.convert('RGB');crop=rgb.crop((0,round(rgb.height*.35),rgb.width,round(rgb.height*.85)))
            dark=sum(max(pixel)<180 for pixel in crop.getdata())
            assert (dark==0 if expected=='fail' else dark>10), (case,filename,dark)
    (tmp_path/'readback.json').write_text(json.dumps(stored,indent=2))
    (tmp_path/'actual.pptx').write_bytes(store.read_object_bytes(store.read_object_json(doc['outputs']['pptx'])['file']))


def test_readback_implementation_change_cannot_reuse_old_candidate_check(icon_store,monkeypatch):
    recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0];start(icon_store,task)
    data=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode()
    cid=accept(icon_store,task,data)['candidate_ids'][0];result=candidate_preview.request(icon_store.project_root,candidate_id=cid)
    assert result['status']=='ready'
    original=candidate_preview._sha
    monkeypatch.setattr(candidate_preview,'_sha',lambda path:'0'*64 if Path(path).resolve()==Path(readback_text.__file__).resolve() else original(path))
    state=candidate_preview.status(icon_store.project_root,candidate_id=cid)
    assert state['status']=='not_requested' and state['cache_key']!=result['cache_key']
    with pytest.raises(OperationError):candidate_preview.require_ready(icon_store.project_root,cid)
    assert (candidate_preview._folder(icon_store)/result['cache_key']/'report.json').exists()
