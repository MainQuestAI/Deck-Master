"""RP-05: synthetic preview fixtures, real PPT compilation/render/readback."""
import uuid

import pytest
from PIL import Image

from deck_master import pipeline, service, stages
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from page_visual_helpers import pass_page_review
from test_candidates import store, start, accept, envelope  # noqa: F401


def prepared(store):
    for pid in ('p01', 'p02'):
        task = service.open_host_task(store, kind='reconstruct', page_ids=[pid],
                                      instruction='L1 synthetic SVG for preview reuse regression')
        start(store, task)
        payload = envelope(store, task)
        from xml.sax.saxutils import escape
        from hostenv import resolve_host_font
        doc = store.load_document()
        entry = next(e for e in doc['pages'] if e['page_id'] == pid)
        page = store.read_object_json(entry['page'])
        original = store.read_object_json(entry['blueprint'])['file']['sha256']
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" '
               f'data-blueprint-sha256="{original}"><rect width="960" height="540" fill="#ffffff"/>'
               f'<text x="40" y="100" data-atom-id="atom:{pid}:title" font-family="{resolve_host_font()}" '
               f'font-size="32">{escape(page["customer_visible"]["title"])}</text></svg>')
        (store.staging_dir / task['operation_id'] / 'page.svg').write_text(svg)
        accept(store, task, payload)
    doc = store.load_document()
    new = bump_revision(doc, {'operation_id': 'fixture-previews', 'kind': 'artifact_adoption',
                             'description': 'L1 synthetic previews; no visual approval', 'read_set': []})
    png = store.staging_dir / 'fixture-preview.png'
    Image.new('RGB', (960, 540), 'white').save(png)
    for entry in new['pages']:
        entry['svg_preview'] = pipeline.artifact(store, png, 'svg_preview', page_id=entry['page_id'],
            derived_from=[entry['svg']], dependencies=[{'kind': 'svg', 'identity': entry['page_id'],
                                                       'sha256': entry['svg']['sha256']}])
    store.commit_change(base_revision=doc['revision_id'], document=new, operation_id='fixture-previews')
    for _ in range(2):
        pending = service.continue_project(store.project_root)['pending_tasks'][0]
        assert pending['review_stage'] == 'page_visual'
        pass_page_review(store.project_root, pending)
    return store.load_document()


@pytest.mark.render
def test_assembly_reuses_current_preview_but_really_renders_ppt(store, monkeypatch):
    before = prepared(store)
    calls = []
    real_run = pipeline.run

    def record(args, **kwargs):
        calls.append(args)
        assert 'rsvg-convert' not in str(args[0]), 'current SVG preview must not be rendered and discarded'
        return real_run(args, **kwargs)

    real_executable = pipeline.executable

    def without_rsvg(name):
        if name == 'rsvg-convert':
            raise pipeline.NeedsTool('rsvg deliberately unavailable: current previews suffice')
        return real_executable(name)

    monkeypatch.setattr(pipeline, 'run', record)
    monkeypatch.setattr(pipeline, 'executable', without_rsvg)
    response = stages.assemble(store.project_root, base_revision=before['revision_id'], operation_id=str(uuid.uuid4()))
    assert response['operation_result']['report']['status'] == 'pass'
    after = store.load_document()
    assert [e['svg_preview'] for e in after['pages']] == [e['svg_preview'] for e in before['pages']]
    assert any('--convert-to' in args for args in calls)
    assert any('-png' in args for args in calls)
    for entry in after['pages']:
        preview = store.read_object_json(entry['ppt_preview'])
        data = store.read_object_bytes(preview['file'])
        from io import BytesIO
        with Image.open(BytesIO(data)) as img:
            low, high = img.convert('L').getextrema()
            assert high - low > 20
    report = store.read_object_json(after['outputs']['render_report'])
    import json
    assert json.loads(store.read_object_bytes(report['file']))['status'] == 'pass'


@pytest.mark.parametrize('damage', ['missing', 'stale', 'wrong_page', 'corrupt'])
def test_invalid_preview_is_not_reused_or_assembled(store, monkeypatch, damage):
    before = prepared(store)
    entry = before['pages'][0]
    if damage == 'missing':
        entry['svg_preview'] = None
    elif damage == 'corrupt':
        obj = store.read_object_json(entry['svg_preview'])
        (store.project_root / obj['file']['path']).write_bytes(b'corrupt bytes')
    else:
        obj = store.read_object_json(entry['svg_preview'])
        if damage == 'stale':
            obj['derived_from'] = [before['pages'][1]['svg']]
        else:
            obj['page_id'] = 'p02'
        entry['svg_preview'] = store.put_json_object(obj)
    assert not pipeline._current_svg_preview(store, entry)
    with pytest.raises((OperationError, service.StoreError)):
        stages.require_assembly_ready(store, before)
