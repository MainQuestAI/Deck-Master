import copy
import uuid

import pytest

from deck_master import annotation_service as annotations
from deck_master.models import content_identity, ModelError, sha256_bytes
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / 'sample'; create_sample(path, page_count=2, readonly=False)
    store = Store(path); doc = store.load_document()
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'],
            'base_revision': doc['revision_id'], 'scope': 'page', 'page_id': 'p01',
            'page_ref': doc['pages'][0]['page'], 'intent': 'clarify', 'body': 'Clarify this claim',
            'status': 'open', 'location': {'kind': 'whole'}}
    return store, doc, note


def save(store, doc, notes, op=None):
    return annotations.save(store.project_root, input={'schema_version': 'annotation_batch.v1',
                            'project_id': doc['project_id'], 'annotations': notes},
                            base_revision=doc['revision_id'], operation_id=op or str(uuid.uuid4()))


def test_save_only_opinions_replays_and_keeps_production_identity(sample):
    store, doc, note = sample; identity = content_identity(doc); op = str(uuid.uuid4())
    first = save(store, doc, [note], op)
    now = store.load_document()
    assert content_identity(now) == identity and now['tasks'] == doc['tasks'] and now['outputs'] == doc['outputs']
    assert save(store, doc, [note], op)['operation_result'] == first['operation_result']
    records = annotations.list_annotations(store.project_root)['annotations']
    assert len(records) == 1 and records[0]['annotation']['base_revision'] == doc['revision_id']


@pytest.mark.parametrize('bad', ['page_ref', 'scope', 'project', 'extra', 'text_on_image', 'rect_bounds', 'dimensions'])
def test_batch_failure_has_zero_commit(sample, bad):
    store, doc, note = sample; invalid = copy.deepcopy(note)
    if bad == 'page_ref': invalid['page_ref'] = doc['pages'][1]['page']
    elif bad == 'scope': invalid['scope'] = 'chapter'
    elif bad == 'project': invalid['project_id'] = 'foreign'
    elif bad == 'extra': invalid['unexpected'] = True
    else:
        invalid.update(scope='artifact', layer='original_image', artifact_ref=doc['pages'][0]['blueprint'])
        invalid['location'] = {'kind': 'rect', 'canvas': {'width': 960, 'height': 540}, 'x': 0.1, 'y': 0.2, 'width': 0.3, 'height': 0.4}
        if bad == 'text_on_image': invalid['location'] = {'kind': 'text', 'range': {}}
        elif bad == 'rect_bounds': invalid['location']['width'] = 1
        else: invalid['location']['canvas']['width'] = 1600
    with pytest.raises((OperationError, ModelError)):
        save(store, doc, [note, invalid])
    assert store.current_revision_id() == doc['revision_id']
    assert 'annotations' not in store.load_document()


def test_all_scopes_and_fixed_geometry(sample):
    store, doc, page = sample
    project = {k: v for k, v in page.items() if k not in ('page_id', 'page_ref')}; project['scope'] = 'project'
    chapter = {**project, 'scope': 'chapter', 'chapter_id': 'example', 'content_plan_ref': doc['content_plan']}
    region = {**page, 'scope': 'artifact', 'layer': 'original_image', 'artifact_ref': doc['pages'][0]['blueprint'],
              'location': {'kind': 'rect', 'canvas': {'width': 960, 'height': 540}, 'x': .2, 'y': .3, 'width': .4, 'height': .5}}
    text = store.read_object_json(page['page_ref'])['customer_visible']['title']
    selection = {**page, 'scope': 'artifact', 'layer': 'content', 'artifact_ref': page['page_ref'],
                 'location': {'kind': 'text', 'range': {'schema_version': 'text_range.v1', 'ref': page['page_ref'],
                 'locator': '/customer_visible/title', 'text_sha256': sha256_bytes(text.encode()),
                 'start': 0, 'end': 2, 'excerpt': text[:2]}}}
    result = save(store, doc, [project, chapter, page, region, selection])
    assert len(result['operation_result']['annotations']) == 5
    assert len(annotations.list_annotations(store.project_root)['annotations']) == 5
