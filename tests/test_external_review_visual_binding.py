"""Synthetic reviews exercise actual revision writes, not customer approvals."""
import json
import pytest
from quality_review_v2_helpers import canonical_gate
from quality.gate_freshness import report_currentity
from quality.external_review import validate_review_binding, ExternalReviewError
from test_revision_transactions import commit

@pytest.mark.parametrize('relative',[
 'high_density_build/svg/P001.svg',
 'high_density_build/page_scenes/P001.json',
 'high_density_build/scenes/P001.page_scene.json',
 'high_density_build/content_locks/P001.json',
 'high_density_build/blueprints/P001.png',
])
def test_visual_revision_change_stales_dispatched_review(tmp_path,relative):
    seed=tmp_path/relative;seed.parent.mkdir(parents=True);seed.write_text('old reviewed bytes')
    old=canonical_gate(tmp_path)
    assert relative in {r['ref'] for r in old['canonical_review']['based_on']['input_refs']}
    commit(tmp_path,'visual-change',{relative:'new actual visual bytes'})
    assert report_currentity(tmp_path,old)['status']=='stale'
    with pytest.raises(ExternalReviewError,match='inputs changed'):
        validate_review_binding(tmp_path,old['canonical_review'])


def test_registered_asset_bytes_bound_even_outside_default_asset_folder(tmp_path):
    folder=tmp_path/'page_packages';folder.mkdir();asset=tmp_path/'custom-photo.jpg';asset.write_bytes(b'old photo')
    (folder/'P001.json').write_text(json.dumps({'page_id':'P001','asset_bindings':[{'asset_id':'photo','path':'custom-photo.jpg','approved':True}]}))
    old=canonical_gate(tmp_path)
    assert 'custom-photo.jpg' in {r['ref'] for r in old['canonical_review']['based_on']['input_refs']}
    commit(tmp_path,'photo-change',{'custom-photo.jpg':b'new photo'})
    assert report_currentity(tmp_path,old)['status']=='stale'


@pytest.mark.parametrize('changed',['artifact','preview','selected_artifact'])
def test_final_review_binds_selected_artifact_and_preview_before_dispatch(tmp_path,changed):
    artifact=tmp_path/'deck.pptx';artifact.write_bytes(b'actual artifact A')
    preview=tmp_path/'P001.png';preview.write_bytes(b'actual preview A')
    result=tmp_path/'render_results/render_result.json';result.parent.mkdir();result.write_text(json.dumps({'artifact_path':'deck.pptx','pages':[{'page_id':'P001','preview_path':'P001.png'}]}))
    old=canonical_gate(tmp_path)
    refs={r['ref'] for r in old['canonical_review']['based_on']['input_refs']}
    assert {'deck.pptx','P001.png','render_results/render_result.json'} <= refs
    # Actual render/build outputs are live selected outputs, not stale input projections.
    commit(tmp_path,'baseline',{'input-note.txt':'baseline'})
    if changed=='artifact': artifact.write_bytes(b'actual artifact B')
    elif changed=='preview':preview.write_bytes(b'actual preview B')
    else:
        (tmp_path/'deck-B.pptx').write_bytes(artifact.read_bytes())
        result.write_text(json.dumps({'artifact_path':'deck-B.pptx','pages':[{'page_id':'P001','preview_path':'P001.png'}]}))
    assert report_currentity(tmp_path,old,artifact)['status']=='stale'
    with pytest.raises(ExternalReviewError,match='inputs changed'):
        validate_review_binding(tmp_path,old['canonical_review'])


def test_old_content_only_report_not_rebound_on_import(tmp_path):
    old=canonical_gate(tmp_path)
    svg=tmp_path/'high_density_build/svg/P001.svg';svg.parent.mkdir(parents=True);svg.write_text('<svg/>')
    assert report_currentity(tmp_path,old)['status']=='stale'
    with pytest.raises(ExternalReviewError,match='inputs changed'):
        validate_review_binding(tmp_path,old['canonical_review'])


def test_preview_directory_only_is_bound(tmp_path):
    folder=tmp_path/'previews';folder.mkdir();(folder/'P001.png').write_bytes(b'preview')
    result=tmp_path/'render_results/render_result.json';result.parent.mkdir();result.write_text(json.dumps({'preview_dir':'previews'}))
    old=canonical_gate(tmp_path)
    assert 'previews/P001.png' in {r['ref'] for r in old['canonical_review']['based_on']['input_refs']}
    (folder/'P001.png').write_bytes(b'changed preview')
    assert not report_currentity(tmp_path,old)['current']


def test_render_selected_output_cannot_escape_run(tmp_path):
    canonical_gate(tmp_path)
    result=tmp_path/'render_results/render_result.json';result.parent.mkdir();result.write_text(json.dumps({'artifact_path':'../outside.pptx'}))
    from quality.external_review import prepare_quality_review_v2
    with pytest.raises(ExternalReviewError,match='escapes run scope'):
        prepare_quality_review_v2(tmp_path,scope='semantic',required_page_ids=['P001'])
