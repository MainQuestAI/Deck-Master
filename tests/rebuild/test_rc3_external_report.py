"""L1 synthetic bytes: strict packets never manufacture professional approval."""
import io
import json
from zipfile import ZipFile

import pytest

from deck_master import cli, external_review
from deck_master.collaboration_api import invoke
from deck_master.models import ModelError, canonical_json_bytes, sha256_bytes
from rc3_fixtures import historical_snapshot, source_snapshot


def scope():
    return {'subject': 'deck', 'page_ids': [], 'page_manifest_ref': None,
            'external_artifact_ref': None, 'layers': ['review'],
            'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'review'}


def pptx_bytes():
    stream = io.BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('ppt/slides/slide1.xml', '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Actual visible text</a:t></p:sld>')
        archive.writestr('ppt/notesSlides/notesSlide1.xml', '<a:t xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">Actual notes</a:t>')
    return stream.getvalue()


def test_single_file_raw_hash_readback_and_external_output(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    pptx = source / 'actual.pptx'
    pptx.write_bytes(pptx_bytes())
    before = source_snapshot(source)
    monkeypatch.setattr(external_review.shutil, 'which', lambda _: None)
    output = tmp_path / 'reports' / 'packet.json'
    response, http, code = invoke(None, 'review.evaluate', {'source': str(pptx),
        'source_sha256': sha256_bytes(pptx.read_bytes()), 'scope': scope(), 'report_output': str(output)})
    assert (http, code) == (409, 4)
    assert response['error']['code'] == response['status'] == 'needs_tool'
    result = response['result']
    assert result['status'] == 'needs_tool'
    report = result['external_report']['report']
    assert result['source_sha256'] == sha256_bytes(pptx.read_bytes())
    assert report['source_manifest_sha256'] != result['source_sha256']
    assert report['source_unchanged'] is True and report['reviews'] == []
    readback = report['engineering_observations'][0]
    assert readback['slide_count'] == readback['notes_part_count'] == 1
    assert {p['text'] for p in readback['parts']} == {'Actual visible text', 'Actual notes'}
    assert {item['code'] for item in report['limitations']} >= {'needs_tool', 'needs_reviewer'}
    assert report['provenance']['reviewer_executed'] is False
    assert json.loads(output.read_text()) == result['external_report']
    assert result['external_report']['report_sha256'] == sha256_bytes(canonical_json_bytes(report))
    assert source_snapshot(source) == before
    assert not (source / '.deckmaster').exists()
    with pytest.raises(ModelError, match='already exists'):
        external_review.evaluate(pptx, scope=scope(), report_output=output)


def test_nonproject_directory_and_explicit_fileset_are_readable_without_document(tmp_path):
    folder = tmp_path / 'manuscript'
    folder.mkdir()
    first, second = folder / 'copy.md', folder / 'speech.txt'
    first.write_text('Manuscript content')
    second.write_text('Spoken content')
    before = source_snapshot(folder)
    result = external_review.evaluate(folder, scope=scope())
    assert result['status'] == 'needs_reviewer'
    assert result['external_report']['report']['source_manifest']['source_kind'] == 'fileset'
    text = [entry['text'] for entry in result['external_report']['report']['engineering_observations']]
    assert text == ['Manuscript content', 'Spoken content']
    selected = external_review.evaluate({'kind': 'fileset', 'files': [str(second), str(first)]}, scope=scope())
    assert selected['source_sha256'] == result['source_sha256']
    again = external_review.evaluate([first, second], source_sha256=result['source_sha256'], scope=scope())
    assert again['source_sha256'] == result['source_sha256']
    assert source_snapshot(folder) == before


def test_project_snapshot_read_is_historical_and_does_not_write_source(tmp_path):
    fixture = historical_snapshot(tmp_path, scenario='strict historical reader, no production')
    project, revision = fixture['project'], fixture['revision_id']
    before = source_snapshot(project)
    result = external_review.evaluate({'kind': 'project', 'path': str(project), 'revision': revision}, scope=scope())
    manifest = result['external_report']['report']['source_manifest']
    assert manifest['artifact_revision_id'] == revision
    assert manifest['original_project_id'] == project.name
    assert result['external_report']['report']['source_unchanged'] is True
    assert source_snapshot(project) == before


@pytest.mark.parametrize('output_kind', ['inside', 'same', 'source_alias', 'output_alias', 'ancestor_alias'])
def test_source_and_output_aliases_refused_before_any_output(tmp_path, output_kind):
    folder = tmp_path / 'source'
    folder.mkdir()
    source = folder / 'copy.txt'
    source.write_text('unchanged source')
    before = source_snapshot(folder)
    if output_kind == 'inside':
        selected, output = folder, folder / 'report.json'
    elif output_kind == 'same':
        selected, output = source, source
    elif output_kind == 'source_alias':
        selected, output = tmp_path / 'source-link', tmp_path / 'report.json'
        selected.symlink_to(folder, target_is_directory=True)
    elif output_kind == 'output_alias':
        selected, output = source, tmp_path / 'alias.json'
        output.symlink_to(source)
    else:
        alias = tmp_path / 'parent-link'
        alias.symlink_to(folder, target_is_directory=True)
        selected, output = source, alias / 'report.json'
    with pytest.raises(ModelError, match='symlink|outside|overlap'):
        external_review.evaluate(selected, scope=scope(), report_output=output)
    assert source_snapshot(folder) == before


def test_symlink_anywhere_in_source_tree_refused(tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    (folder / 'a.txt').write_text('a')
    (folder / 'hidden-link').symlink_to(tmp_path / 'missing')
    with pytest.raises(ModelError, match='symlink'):
        external_review.evaluate(folder, scope=scope())


def test_source_change_produces_nonimportable_readable_report(tmp_path, monkeypatch):
    source = tmp_path / 'copy.txt'
    source.write_text('before')
    observe = external_review._observe
    def change_after_read(entries, contents):
        result = observe(entries, contents)
        source.write_text('after')
        return result
    monkeypatch.setattr(external_review, '_observe', change_after_read)
    response, http, code = invoke(None, 'review.evaluate', {'source': str(source),
        'scope': scope(), 'report_output': str(tmp_path / 'report.json')})
    assert (http, code) == (409, 5)
    assert response['error']['code'] == response['status'] == 'source_changed'
    assert response['error']['path'] == 'source'
    result = response['result']
    report = result['external_report']['report']
    assert result['status'] == 'source_changed'
    assert report['source_unchanged'] is False
    assert report['engineering_observations'][0]['text'] == 'before'
    assert report['reviews'] == []


@pytest.mark.parametrize('extra,expected', [({'source_sha256': '0' * 64}, 'source_sha256'),
    ({'persistence': 'project'}, 'persistence'), ({'scope': {'unknown': True}}, 'scope')])
def test_invalid_hash_persistence_and_scope_do_not_write(tmp_path, extra, expected):
    source = tmp_path / 'copy.txt'
    source.write_text('input')
    values = {'scope': scope(), 'report_output': tmp_path / 'packet.json', **extra}
    with pytest.raises(ModelError, match=expected):
        external_review.evaluate(source, **values)
    assert not (tmp_path / 'packet.json').exists()


def test_cli_evaluate_and_json_context_refusal_share_envelope(tmp_path, capsys):
    source = tmp_path / 'copy.txt'
    source.write_text('Actual draft')
    assert cli.main(['review', 'evaluate', str(source), '--persistence', 'none']) == 4
    captured = capsys.readouterr()
    assert captured.out == ''
    result = json.loads(captured.err)
    assert result['schema_version'] == 'collaboration_response.v1'
    assert result['status'] == 'needs_reviewer'
    assert result['error']['code'] == 'needs_reviewer'
    assert result['result']['external_report']['report']['engineering_observations'][0]['text'] == 'Actual draft'
    response, http, code = invoke(None, 'review.evaluate', {'source': str(source), 'scope': scope(),
        'adapter_context': {'human_review_receipts': []}})
    assert (http, code) == (403, 4)
    assert response['error']['code'] == 'untrusted_adapter_context'


def test_special_file_in_source_tree_is_refused_without_opening_fifo(tmp_path):
    import os
    source = tmp_path / 'source'
    source.mkdir()
    os.mkfifo(source / 'pipe')
    with pytest.raises(ModelError, match='regular file'):
        external_review.evaluate(source, scope=scope())


def test_single_project_file_cannot_place_report_back_into_enclosing_project(tmp_path):
    fixture = historical_snapshot(tmp_path, scenario='strict enclosing-project output boundary')
    source = fixture['project'] / 'external.txt'
    source.write_text('File selected from an existing project')
    before = source_snapshot(fixture['project'])
    with pytest.raises(ModelError, match='outside'):
        external_review.evaluate(source, scope=scope(), report_output=fixture['project'] / 'packet.json')
    assert source_snapshot(fixture['project']) == before


def test_empty_project_page_scope_is_never_expanded_to_every_page(tmp_path):
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'Fixed historical Page', 'body_blocks': []},
        'visual_spec': {'intent': 'reader', 'reference_mode': 'new_design'}}
    fixture = historical_snapshot(tmp_path, scenario='empty page set stays empty in external review', pages=[page])
    project = fixture['project']
    uri = (project / fixture['refs']['pages'][0]['path']).as_uri()
    empty = external_review.evaluate(project, scope=scope())['external_report']['report']
    assert all(subject['source_uri'] != uri for subject in empty['subjects'])
    exact = external_review.evaluate(project, scope={**scope(), 'subject': 'pages', 'page_ids': ['p1']})['external_report']['report']
    assert [subject['source_uri'] for subject in exact['subjects']] == [uri]
    assert exact['source_unchanged'] is True
