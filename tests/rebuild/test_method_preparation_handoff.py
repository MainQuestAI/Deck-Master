"""RP-18 read-only preparation round trips preserve real role/phase/scope."""
import json

import pytest
from deck_master import method_library_view as lib, method_resources as methods, models
from deck_master.content_insight import InsightError
from deck_master.insight_http import route
from test_webui_content_insight import candidate, bytes_at


def test_speech_handoff_rechecks_and_reads_identical_resources(tmp_path):
    project, store, _, _ = candidate(tmp_path)
    before = bytes_at(project)
    context = {'mode':'independent', 'role':'deck-review', 'phase':'speech', 'review_units':['speech']}
    preview = lib.preview(project, {'context':context, 'selected_resource_ids':['writing-profiles']})
    packet = json.loads(preview['handoff']['text'].split('```json\n')[1].split('\n```')[0])
    assert packet['effective_context'] == {'role':'deck-review','kind':None,'intent':None,'phase':'speech',
                                           'review_units':['speech'],'request_scope':None}
    recovered = lib.preview(project, packet['preview_request'])
    assert recovered['preview_digest'] == packet['preview_digest']
    assert recovered['resolved_manifest'] == packet['resolved_manifest']
    assert 'method-review' in recovered['default_ids']
    assert 'source-reading' not in recovered['default_ids']
    for resource in recovered['resolved_manifest']:
        body = lib.resource(resource['id'], catalog_digest=recovered['catalog_digest'], sha256=resource['sha256'])
        assert models.sha256_bytes(body['content'].encode()) == resource['sha256']
    assert bytes_at(project) == before


def test_no_phase_browsing_does_not_enable_selection_or_dispatch(tmp_path):
    project, store, _, _ = candidate(tmp_path)
    before = bytes_at(project)
    preview = lib.preview(project, {'context':{'mode':'project','revision':store.current_revision_id()},'selected_resource_ids':[]})
    assert preview['dispatch_status'] == 'cannot_dispatch' and not preview['handoff']['copy_allowed']
    entry = next(e for e in preview['entries'] if e['id'] == 'content-to-visual')
    assert not entry['selectable'] and entry['sha256'] is None
    # Discovery reads the real installed body on demand, without declaring a frozen basis.
    body = route(project, '/api/method-library/resources/content-to-visual', 'catalog_digest='+preview['catalog_digest'])
    assert body['content'] and body['preparation_only']
    assert body['sha256'] == models.sha256_bytes(body['content'].encode())
    with pytest.raises(InsightError):
        lib.resource('content-to-visual', catalog_digest=preview['catalog_digest'], sha256='0'*64)
    with pytest.raises(InsightError):
        route(project, '/api/method-library/resources/installation', 'catalog_digest='+preview['catalog_digest'])
    assert bytes_at(project) == before


def test_design_phase_and_image_dispatch_keep_conversion_separate():
    for phase in ['design','production']:
        assert 'content-to-visual' in methods.method_ids_for('compose',phase=phase)
    assert methods.method_ids_for('blueprint') == ('visual-reference','physical-units','content-to-visual')
    assert methods.method_ids_for('reconstruct') == ('blueprint-svg','physical-units','content-to-visual')
    # The historical selector is immutable, not silently backfilled with new methods.
    assert methods.rc3_method_ids_for('blueprint') == ('blueprint-svg','physical-units')


def test_content_speech_preparation_uses_phase_methods_not_role_union(tmp_path):
    project, _, _, _ = candidate(tmp_path)
    preview = lib.preview(project, {'context':{'mode':'independent','role':'deck-content',
        'phase':'speech','review_units':[]}, 'selected_resource_ids':[]})
    assert preview['default_ids'] == ['collaboration-routing', 'content-methods', 'content-examples', 'writing-profiles']
    assert 'method-selection' not in preview['default_ids']
