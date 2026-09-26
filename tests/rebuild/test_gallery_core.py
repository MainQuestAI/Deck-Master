"""W04 core evidence: real objects and HTTP; no model or frontend proof."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import threading
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image
import pytest

from deck_master import gallery_state, samples, thumbnails, ui_journal
from deck_master.local_state import LocalStateError, LocalStateConflict
from deck_master.models import bump_revision, content_identity, validate_schema
from deck_master.pipeline import artifact
from deck_master.store import Store
from deck_master.web import WorkbenchServer


@pytest.fixture
def project(tmp_path, monkeypatch):
    path = tmp_path / 'project'
    samples.create_sample(path, page_count=5, readonly=False)
    queue = thumbnails.ThumbnailQueue()
    monkeypatch.setattr(thumbnails, 'QUEUE', queue)
    yield path
    queue.close()


def state(project):
    info = ui_journal.project_info(project)
    return {'schema_version': 'ui_gallery.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
            'revision_id': info['revision_id'], 'layer': 'original_image', 'mode': 'grid', 'columns': 3,
            'selected_page_ids': ['p01', 'p03'], 'references': [], 'filter': {'chapter_id': None, 'status': 'all'},
            'anchor': {'page_id': 'p03', 'offset': .25}, 'zoom': {'synchronized': True, 'scale': 1}}


def original(project, index=0):
    store = Store(project)
    return store.read_object_json(store.load_document()['pages'][index]['blueprint'])['file']


def business(project):
    store = Store(project)
    return (store.read_current(), content_identity(store.load_document()), sorted(p.name for p in store.revisions_dir.glob('*.json')))


def request(url, path, payload=None, headers=None):
    if payload is not None:
        headers = {'Origin': url.rstrip('/'), 'X-Deck-Token': request(url, '/api/session')[1]['token'], **(headers or {})}
    req = urllib.request.Request(url.rstrip('/') + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers or {})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        result = json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw
        return response.status, result, dict(response.headers)


def test_gallery_ack_cas_reference_pin_and_business_immutability(project):
    before = business(project)
    value = state(project)
    value['filter']['chapter_id'] = 'example'
    value['references'] = [{'page_id': 'p01', 'revision_id': value['revision_id'], 'original_ref': original(project)}]
    saved = gallery_state.save(project, state=value)
    assert gallery_state.save(project, state=value)['replayed']
    assert gallery_state.get(project)['record'] == saved['record']
    other = copy.deepcopy(value); other['columns'] = 4
    with pytest.raises(LocalStateConflict): gallery_state.save(project, state=other)
    result = gallery_state.save(project, state=other, expected_etag=saved['record']['etag'])
    assert result['record']['sequence'] == 2 and business(project) == before


def test_reorder_does_not_change_personal_selection_or_reference_basis(project):
    value = state(project)
    value['references'] = [{'page_id': 'p01', 'revision_id': value['revision_id'], 'original_ref': original(project)}]
    saved = gallery_state.save(project, state=value)['record']
    store = Store(project); doc = store.load_document()
    changed = bump_revision(doc, {'kind': 'task_update', 'operation_id': 'fixture-order', 'description': 'fixture reorder', 'read_set': []})
    changed['pages'].reverse()
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='fixture-order')
    assert gallery_state.get(project)['record'] == saved
    value['revision_id'] = store.current_revision_id()
    updated = gallery_state.save(project, state=value, expected_etag=saved['etag'])['record']['state']
    assert updated['selected_page_ids'] == ['p01', 'p03'] and updated['references'] == saved['state']['references']


@pytest.mark.parametrize('case', ['project', 'page', 'chapter', 'reference', 'duplicate', 'compare', 'overflow', 'anchor'])
def test_invalid_gallery_state_never_overwrites_saved_selection(project, case):
    good = state(project); saved = gallery_state.save(project, state=good)['record']; bad = copy.deepcopy(good)
    if case == 'project': bad['project_identity'] = 'a' * 64
    elif case == 'page': bad['selected_page_ids'] = ['p99']
    elif case == 'chapter': bad['filter']['chapter_id'] = 'not-a-chapter'
    elif case == 'reference': bad['references'] = [{'page_id': 'p01', 'revision_id': bad['revision_id'], 'original_ref': original(project, 1)}]
    elif case == 'duplicate': bad['selected_page_ids'] = ['p01', 'p01']
    elif case == 'compare': bad.update(mode='compare', selected_page_ids=['p01'])
    elif case == 'overflow': bad['selected_page_ids'] = ['p01', 'p02', 'p03', 'p04', 'p05']
    else: bad['anchor']['page_id'] = 'p99'
    with pytest.raises((LocalStateError, ValueError)):
        gallery_state.save(project, state=bad, expected_etag=saved['etag'])
    assert gallery_state.get(project)['record'] == saved


def test_gallery_two_windows_only_one_changed_state_wins(project):
    value = state(project); saved = gallery_state.save(project, state=value)['record']
    def change(columns):
        try: return gallery_state.save(project, state={**value, 'columns': columns}, expected_etag=saved['etag'])
        except LocalStateConflict: return None
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(change, [2, 4]))
    assert sum(result is not None for result in results) == 1


def test_thumbnail_cold_warm_size_integrity_and_source_preservation(project):
    ref = original(project); store = Store(project)
    before = business(project), store.read_object_bytes(ref)
    first = thumbnails.request(project, ref=ref)
    assert first['status'] in ('queued', 'running') and first['cache'] == 'miss'
    thumbnails.QUEUE.drain()
    ready = thumbnails.request(project, ref=ref)
    assert ready['status'] == 'ready' and ready['cache'] == 'hit'
    data, media = thumbnails.file_bytes(project, ready['cache_key'])
    assert media == 'image/png'
    with Image.open(BytesIO(data)) as image:
        assert image.size == (480, 270)
    assert (business(project), store.read_object_bytes(ref)) == before
    assert thumbnails.QUEUE.metrics()['completed'] == 1


def test_new_image_warms_after_gallery_activation_without_waiting_for_decode(project, tmp_path, monkeypatch):
    thumbnails.activate(project)
    started = threading.Event(); release = threading.Event(); real = thumbnails._generate
    def slow(*args):
        started.set(); assert release.wait(5); return real(*args)
    monkeypatch.setattr(thumbnails, '_generate', slow)
    image = tmp_path / 'new.png'; Image.new('RGB', (100, 80), '#acbeef').save(image)
    store = Store(project)
    try:
        ref = artifact(store, image, 'blueprint', page_id='p01')
        assert store.read_object_json(ref)['role'] == 'blueprint'
        assert started.wait(2)
        assert thumbnails.QUEUE.metrics()['completed'] == 0
    finally:
        release.set(); thumbnails.QUEUE.drain()
    assert thumbnails.request(project, ref=store.read_object_json(ref)['file'])['cache'] == 'hit'


def test_bounded_background_queue_and_foreground_promotion(project, monkeypatch):
    entered = threading.Barrier(3); release = threading.Event(); completed = []
    def fake_generate(root, ref, identity, key):
        if len(completed) == 0:
            try: entered.wait(timeout=2)
            except threading.BrokenBarrierError: pass
        assert release.wait(5); completed.append(ref['sha256'])
    monkeypatch.setattr(thumbnails, '_generate', fake_generate)
    identity = ui_journal.project_info(project)['project_identity']; queue = thumbnails.QUEUE
    refs = [{'path': f'.deckmaster/objects/00/{i:064x}.png', 'sha256': f'{i:064x}'} for i in range(67)]
    queue.submit(project, refs[0], identity, priority=10); queue.submit(project, refs[1], identity, priority=10)
    entered.wait(timeout=3)
    try:
        for ref in refs[2:66]: assert queue.submit(project, ref, identity, priority=10)['status'] == 'queued'
        assert queue.submit(project, refs[66], identity)['status'] == 'busy'
        queue.submit(project, refs[65], identity, priority=0)
        metrics = queue.metrics()
        assert metrics['running'] == 2 and metrics['queued'] == 64
    finally:
        release.set(); queue.drain()
    assert refs[65]['sha256'] in completed[:4]
    assert queue.metrics()['peak_running'] == 2 and queue.metrics()['peak_queued'] == 64


def test_bad_hash_unsupported_svg_and_cache_corruption_retry(project):
    ref = original(project)
    with pytest.raises(ValueError): thumbnails.request(project, ref={**ref, 'sha256': 'a' * 64})
    source = Store(project).project_root / ref['path']
    original_bytes = source.read_bytes()
    source.write_bytes(b'injected hash failure')
    assert thumbnails.request(project, ref=ref)['status'] == 'queued'
    thumbnails.QUEUE.drain()
    assert thumbnails.request(project, ref=ref)['status'] == 'failed'
    source.write_bytes(original_bytes)
    svg = Store(project).put_blob(b'<svg xmlns="http://www.w3.org/2000/svg"/>', ext='svg')
    assert thumbnails.request(project, ref=svg)['status'] == 'unsupported'
    thumbnails.request(project, ref=ref, retry=True); thumbnails.QUEUE.drain()
    good = thumbnails.request(project, ref=ref)
    _meta, file, _lock = thumbnails._paths(Store(project), good['cache_key'])
    file.write_bytes(b'broken derivative')
    with pytest.raises(LocalStateError): thumbnails.file_bytes(project, good['cache_key'])
    assert thumbnails.request(project, ref=ref)['status'] == 'failed'
    assert thumbnails.request(project, ref=ref, retry=True)['status'] == 'queued'
    thumbnails.QUEUE.drain()
    assert thumbnails.request(project, ref=ref)['status'] == 'ready'


def test_cross_project_cache_and_symlink_cannot_read_foreign_derivative(project, tmp_path):
    ref = original(project); thumbnails.request(project, ref=ref); thumbnails.QUEUE.drain()
    cached = thumbnails.request(project, ref=ref)
    other = tmp_path / 'different' / 'project'; samples.create_sample(other, page_count=1, readonly=False)
    assert original(other) == ref  # same synthetic bytes, different logical project
    thumbnails.request(other, ref=ref); thumbnails.QUEUE.drain()
    second = thumbnails.request(other, ref=ref)
    assert cached['cache_key'] != second['cache_key']
    with pytest.raises(LocalStateError): thumbnails.file_bytes(other, cached['cache_key'])
    root = thumbnails._directory(Store(other)); image = root / (second['cache_key'] + '.png')
    image.unlink(); image.symlink_to(thumbnails._directory(Store(project)) / (cached['cache_key'] + '.png'))
    with pytest.raises(LocalStateError): thumbnails.file_bytes(other, second['cache_key'])


def test_gallery_and_thumbnail_http_keep_host_origin_hash_and_csp_guards(project):
    server = WorkbenchServer(project); url = server.start()
    try:
        for path in ['/api/gallery', '/api/thumbnails', '/api/thumbnail-file']:
            assert request(url, path, headers={'Host': 'outside.invalid'})[0] == 403
        before = business(project)
        assert request(url, '/api/gallery')[1]['record'] is None
        assert request(url, '/api/gallery', {'state': state(project)}, headers={'Origin': 'http://outside.invalid'})[0] == 403
        assert request(url, '/api/gallery', {'state': state(project)})[0] == 200
        query = urllib.parse.urlencode(original(project))
        assert request(url, '/api/thumbnails?' + query)[0] == 202
        thumbnails.QUEUE.drain()
        status, result, _headers = request(url, '/api/thumbnails?' + query)
        assert status == 200 and result['status'] == 'ready' and 'source_signature' not in result
        status, blob, headers = request(url, result['url'])
        assert status == 200 and blob.startswith(b'\x89PNG')
        assert headers['Cache-Control'] == 'private, max-age=31536000, immutable'
        assert "script-src 'self'" in headers['Content-Security-Policy']
        assert request(url, '/api/thumbnail-file?cache_key=../../bad')[0] == 422
        assert request(url, '/api/thumbnails?' + query + '&path=/etc/passwd')[0] == 422
        assert request(url, '/api/thumbnails?path=/etc/passwd&sha256=' + 'a' * 64)[0] == 422
        assert request(url, '/api/gallery')[0] == 200
        assert business(project) == before
    finally:
        server.stop()


def test_schema_mirrors_are_identical_and_personal_state_is_valid(project):
    validate_schema('ui_gallery', state(project))
    root = Path(__file__).resolve().parents[2]
    for name in ('ui-gallery.v1.schema.json', 'thumbnail.v1.schema.json'):
        mirror = next((root / 'docs/specs/deck-master-workbench-v3').rglob(name))
        assert mirror.read_bytes() == (root / 'src/deck_master/resources/contracts' / name).read_bytes()


def test_missing_reference_keeps_selection_and_can_be_removed_without_manual_file_repair(project):
    value = state(project)
    ref = original(project)
    value['references'] = [{'page_id': 'p01', 'revision_id': value['revision_id'], 'original_ref': ref}]
    first = gallery_state.save(project, state=value)['record']
    source = Store(project).project_root / ref['path']
    raw = source.read_bytes(); source.unlink()
    try:
        loaded = gallery_state.get(project)
        assert loaded['record'] == first and loaded['issues'][0]['code'] == 'gallery_basis_unavailable'
        without = {**value, 'references': []}
        assert gallery_state.save(project, state=without, expected_etag=first['etag'])['status'] == 'saved'
        assert gallery_state.get(project)['record']['state']['selected_page_ids'] == value['selected_page_ids']
    finally:
        source.write_bytes(raw)


def test_mixed_gallery_factory_keeps_originals_and_declares_synthetic_layers(tmp_path):
    from deck_master import workbench
    project = tmp_path / 'gallery'
    manifest = samples.create_gallery_sample(project, page_count=24)
    summary = workbench.workbench_summary(project)
    assert summary['page_count'] == 24 and manifest['model_calls'] == 0
    assert manifest['actual_ppt_rendering'] is False and manifest['candidate_count'] == 0
    pages = {page['page_id']: page for page in summary['pages']}
    assert {page_id for page_id, page in pages.items() if page['stages']['blueprint']['existence'] == 'not_generated'} == {'p03', 'p14'}
    assert {page_id for page_id, page in pages.items() if page['stages']['ppt_preview']['applicability']['status'] == 'basis_changed'} == {'p11', 'p21'}
    assert summary['content_plan']['chapter_count'] == 3
    store = Store(project); previous = store.load_document(manifest['original_revision'])
    for entry in previous['pages']:
        assert store.read_object_bytes(store.read_object_json(entry['blueprint'])['file'])
    assert samples.sample_info(project)['readonly']
