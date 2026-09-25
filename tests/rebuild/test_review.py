"""T11 unified review interpretation: all ten ACs against review.py plus the
refactored entry points (editing.review_status, tasks._adopt_review)."""
import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter

from deck_master import review as review_mod
from deck_master import service
from deck_master.editing import review_status
from deck_master.models import content_identity
from deck_master import tasks as tasks_mod
from deck_master.store import Store


def ref(seed, ext='json'):
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {'path': f'.deckmaster/objects/{digest[:2]}/{digest}.{ext}', 'sha256': digest}


PAGE_REF = ref('page-p1')
PPTX_REF = ref('pptx-v2')
PPTX_OLD = ref('pptx-v1')
A1_REF = ref('svg-a1', 'svg')


def make_document(pptx=PPTX_REF, pages=('p1',), tasks=()):
    return {
        'pages': [{'page_id': pid, 'page': ref(f'page-{pid}')} for pid in pages],
        'outputs': {'pptx': pptx} if pptx else {},
        'tasks': list(tasks),
    }


def current_artifacts():
    return {'content:page:p1': PAGE_REF['sha256'], 'artifact:pptx': PPTX_REF['sha256'],
            'artifact:svg:p1': A1_REF['sha256']}


def finding(fid, impact='must_fix', resolution='open', evidence=()):
    return {'finding_id': fid, 'kind': 'content', 'impact': impact, 'page_id': 'p1',
            'element_refs': ['atom:p1:block:b1:text'], 'message': '问题', 'expected': '期待',
            'actual': '实际', 'evidence': list(evidence), 'resolution': resolution}


def make_review(kind, page_id='p1', status='pass', *, seed, subjects=None, findings=(),
                dependencies=None, replaces=None, observations=None, reviewer=None):
    if subjects is None:
        subjects = [PAGE_REF, PPTX_REF]
    return {
        'schema_version': 'deck_review.v1',
        'review_id': f'r-{seed}',
        'kind': kind,
        'status': status,
        'subjects': subjects,
        'dependencies': dependencies if dependencies is not None else
            [{'kind': 'content', 'identity': f'page:{page_id}', 'sha256': PAGE_REF['sha256']}],
        'reviewer': reviewer or {'type': 'host_self', 'id': 'host-1', 'execution_ref': None,
                                 'independence_confirmed': False},
        'observations': ['实际检查记录'] if observations is None else observations,
        'findings': list(findings),
        'created_at': '2026-09-20T00:00:00Z',
        'replaces': replaces,
    }


def pass_set(seed='ok'):
    return [make_review(kind, seed=f'{seed}-{kind}') for kind in review_mod.REQUIRED_KINDS]


# ---------------------------------------------------------------------------
# AC-R01 / AC-R10: current outputs only; stale history never overrides.


def test_evaluate_counts_only_current_dependency_reviews():
    document = make_document()
    current_pass = make_review('content', seed='cur', findings=[finding('f0', impact='must_fix', resolution='fixed', evidence=[ref('ev', 'png')])])
    # An old review pointing at a previous pptx is history, not current.
    stale_pass = make_review('blueprint_content', seed='old', subjects=[PAGE_REF, PPTX_OLD])
    # A review whose dependency sha drifted from the current page is stale too.
    drifted = make_review('readability', seed='drift',
                          dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': '0' * 64}])
    summary = review_mod.evaluate_current(document, [current_pass, stale_pass, drifted], current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert summary['dimensions']['content:p1']['status'] == 'pass'
    stale_keys = {(s['kind'], s['page_id']) for s in summary['stale']}
    assert ('blueprint_content', 'p1') in stale_keys
    assert ('readability', 'p1') in stale_keys
    assert 'blueprint_content:p1' in summary['missing_dimensions']
    assert 'readability:p1' in summary['missing_dimensions']


def test_stale_pass_does_not_override_current_fail():
    document = make_document()
    old_pass = make_review('content', seed='old-pass', subjects=[PAGE_REF, PPTX_OLD])
    current_fail = make_review('content', seed='cur-fail', status='fail', findings=[finding('f1')])
    others = [r for r in pass_set() if r['kind'] != 'content']
    summary = review_mod.evaluate_current(document, [old_pass, current_fail] + others, current_artifacts())
    assert summary['status'] == 'fail'
    assert summary['dimensions']['content:p1']['open_must_fix'] == ['f1']
    assert any(s['review_id'] == 'r-old-pass' for s in summary['stale'])


def test_all_required_dimensions_pass_only_when_current():
    summary = review_mod.evaluate_current(make_document(), pass_set(), current_artifacts())
    assert summary['status'] == 'pass'
    assert summary['missing_dimensions'] == []
    assert summary['stale'] == []


# ---------------------------------------------------------------------------
# AC-R02: empty is unknown, never a default high score.


def test_empty_reviews_are_not_evaluated_not_full_marks():
    document = make_document(pages=('p1', 'p2', 'p3'))
    summary = review_mod.evaluate_current(document, [], current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert len(summary['missing_dimensions']) == 3 * len(review_mod.REQUIRED_KINDS)
    # Executed-but-not-evaluated dimensions do not pass either.
    registered = [make_review(kind, seed=f'ne-{kind}', status='not_evaluated') for kind in review_mod.REQUIRED_KINDS]
    summary = review_mod.evaluate_current(document.__class__(
        {**document, 'pages': document['pages'][:1]}), registered, current_artifacts())
    assert summary['status'] == 'not_evaluated'


# ---------------------------------------------------------------------------
# AC-R03: submit/load/export share the same interpretation.


def _project_with_passing_reviews(tmp_path):
    from deck_master.compiler import CompileOptions, SvgInput, compile_deck
    project = tmp_path / 'proj'
    service.create(project, brief='review unity', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': '统一审阅', 'body_blocks': []},
        'visual_spec': {'intent': 'unity', 'reference_mode': 'new_design'},
    }]})
    svg = tmp_path / 'p.svg'
    svg.write_text('<svg viewBox="0 0 960 720"><rect width="960" height="720"/></svg>')
    compiled = compile_deck([SvgInput('p1', svg)], CompileOptions(width_px=960, height_px=720),
                            tmp_path / 'out')
    store = Store(project)
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    pptx_ref = adopt_artifact(store, compiled.pptx_path, 'pptx')
    report_file = tmp_path / 'readback-pass.json'
    report_file.write_text(json.dumps({'status': 'pass', 'findings': [], 'pages': []}, ensure_ascii=False))
    bumped = tasks_mod.bump_revision(document, {'operation_id': 'attach-pptx', 'kind': 'task_update',
                                                'description': 'outputs', 'read_set': []})
    bumped['outputs']['pptx'] = pptx_ref
    bumped['outputs']['render_report'] = adopt_artifact(store, report_file, 'render_report')
    bumped['pages'][0]['svg'] = adopt_artifact(store, svg, 'svg', page_id='p1')
    bumped['pages'][0]['ppt_preview'] = adopt_artifact(store, svg, 'ppt_preview', page_id='p1')
    store.commit_change(base_revision=document['revision_id'], document=bumped, operation_id='attach-pptx')
    for kind in review_mod.REQUIRED_KINDS:
        task = tasks_mod.new_task(
            task_id=f'review-{kind}', operation_id=f'op-{kind}', kind='review', scope_pages=['p1'],
            instruction='review', inputs=[store.load_document()['pages'][0]['page']],
            dependencies=[], dispatch_revision=store.load_document()['revision_id'],
            produced_against=content_identity(store.load_document()))
        task_ref = store.put_json_object(task)
        doc = store.load_document()
        bumped = tasks_mod.bump_revision(doc, {'operation_id': f'dispatch-{kind}', 'kind': 'task_update',
                                               'description': 'open', 'read_set': []})
        bumped['tasks'] = list(bumped.get('tasks') or []) + [task_ref]
        store.commit_change(base_revision=doc['revision_id'], document=bumped, operation_id=f'dispatch-{kind}')
        doc = store.load_document()
        subjects = [doc['outputs']['pptx'], doc['pages'][0]['page']]
        envelope = {'kind': 'review', 'files': [], 'reviews': [{
            'schema_version': 'deck_review.v1', 'review_id': f'rv-{kind}', 'kind': kind, 'status': 'pass',
            'subjects': subjects,
            'dependencies': [{'kind': 'content', 'identity': 'page:p1', 'sha256': doc['pages'][0]['page']['sha256']}],
            'reviewer': {'type': 'host_self', 'id': 'host-1', 'execution_ref': None,
                         'independence_confirmed': False},
            'observations': ['实际检查'], 'findings': [], 'created_at': '2026-09-20T00:00:00Z',
            'replaces': None}]}
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload=envelope)
    return project


def test_load_and_export_share_evaluate_current(tmp_path):
    from deck_master.editing import export_project
    project = _project_with_passing_reviews(tmp_path)
    store = Store(project)
    doc = store.load_document()
    reviews = [{**store.read_object_json(r), 'ref': r} for r in doc['reviews']]
    from deck_master.editing import _current_artifact_digests, _output_facts
    summary = review_mod.evaluate_current(
        {**doc, 'tasks': [store.read_object_json(t) for t in doc['tasks']],
         '_output_facts': _output_facts(store, doc)}, reviews,
        _current_artifact_digests(store, doc))
    assert summary['status'] == review_status(store, doc) == 'pass'
    outcome = export_project(project, output_dir=tmp_path / 'delivery', purpose='delivery')
    assert outcome['status'] == 'exported'


def test_handoff_check_rejects_external_ppt_and_accepts_current_export(tmp_path):
    from deck_master.handoff import check_handoff
    from deck_master.pipeline import artifact

    project = _project_with_passing_reviews(tmp_path)
    store = Store(project)
    doc = store.load_document()
    image = tmp_path / 'original.png'
    Image.new('RGB', (120, 80), 'white').save(image)
    bumped = tasks_mod.bump_revision(doc, {'operation_id': 'complete-page-slots', 'kind': 'task_update',
                                          'description': 'complete page slots', 'read_set': []})
    bumped['pages'][0]['blueprint'] = artifact(store, image, 'blueprint', page_id='p1')
    bumped['pages'][0]['svg_preview'] = artifact(store, image, 'svg_preview', page_id='p1')
    store.commit_change(base_revision=doc['revision_id'], document=bumped,
                        operation_id='complete-page-slots')
    from deck_master.editing import export_project
    export_project(project, output_dir=tmp_path / 'review-export', purpose='review')
    current = tmp_path / 'review-export' / 'deck.pptx'
    checked = check_handoff(project, file_path=current)
    assert checked['status'] == 'verified'
    assert checked['file_sha256'] == checked['current_pptx_sha256']

    external = tmp_path / 'text-only.pptx'
    external.write_bytes(b'not the current deck')
    blocked = check_handoff(project, file_path=external)
    assert blocked['status'] == 'blocked'
    assert 'candidate_not_current_output' in blocked['gaps']


def test_handoff_check_blocks_while_production_has_no_ppt(tmp_path, capsys):
    from deck_master.handoff import check_handoff

    project = tmp_path / 'project'
    service.create(project, brief='new draft', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': '待制作', 'body_blocks': []},
        'visual_spec': {'intent': 'test', 'reference_mode': 'new_design'},
    }]})
    external = tmp_path / 'external.pptx'
    external.write_bytes(b'external')
    blocked = check_handoff(project, file_path=external)
    assert blocked['status'] == 'blocked'
    assert 'missing_current_pptx' in blocked['gaps']
    assert 'p1:missing_blueprint' in blocked['gaps']
    from deck_master.cli import main
    assert main(['handoff-check', '--project', str(project), '--file', str(external)]) == 3
    assert json.loads(capsys.readouterr().out)['gaps'] == blocked['gaps']


def test_export_blocked_when_interpretation_fails(tmp_path):
    from deck_master.editing import export_project
    from deck_master.store import StoreError
    project = _project_with_passing_reviews(tmp_path)
    store = Store(project)
    doc = store.load_document()
    fail = make_review('privacy', seed='late-fail', status='fail', findings=[finding('fx')],
                       subjects=[doc['outputs']['pptx'], doc['pages'][0]['page']],
                       dependencies=[{'kind': 'content', 'identity': 'page:p1',
                                      'sha256': doc['pages'][0]['page']['sha256']}])
    fail_ref = store.put_json_object(fail)
    bumped = tasks_mod.bump_revision(doc, {'operation_id': 'add-fail', 'kind': 'task_update',
                                           'description': 'inject failing review', 'read_set': []})
    bumped['reviews'] = list(bumped.get('reviews') or []) + [fail_ref]
    store.commit_change(base_revision=doc['revision_id'], document=bumped, operation_id='add-fail')
    doc = store.load_document()
    assert review_status(store, doc) == 'fail'
    with pytest.raises(StoreError):
        export_project(project, output_dir=tmp_path / 'blocked', purpose='delivery')


# ---------------------------------------------------------------------------
# AC-R04: pixel triage with real generated PNGs, three classes.


def _render_pair(tmp_path, kind):
    expected = Image.new('RGB', (160, 100), (255, 255, 255))
    draw = ImageDraw.Draw(expected)
    draw.rounded_rectangle([10, 10, 90, 60], radius=8, fill=(30, 60, 120))
    draw.rectangle([120, 20, 140, 40], fill=(200, 40, 40))
    actual = expected.copy()
    if kind == 'deleted-icon':
        actual = Image.new('RGB', (160, 100), (255, 255, 255))
        draw2 = ImageDraw.Draw(actual)
        draw2.rounded_rectangle([10, 10, 90, 60], radius=8, fill=(30, 60, 120))
    elif kind == 'square-corner':
        actual = Image.new('RGB', (160, 100), (255, 255, 255))
        draw2 = ImageDraw.Draw(actual)
        draw2.rectangle([10, 10, 90, 60], fill=(30, 60, 120))
        draw2.rectangle([120, 20, 140, 40], fill=(200, 40, 40))
    elif kind == 'antialias':
        # A real renderer anti-alias / font-rasterisation difference: an
        # actual Gaussian blur with radius >= 1, not a near-identity pass.
        actual = expected.filter(ImageFilter.GaussianBlur(1.5))
    exp_path, act_path = tmp_path / f'{kind}-exp.png', tmp_path / f'{kind}-act.png'
    expected.save(exp_path)
    actual.save(act_path)
    return exp_path, act_path


REGIONS = [{'region_id': 'canvas', 'bbox': (0, 0, 160, 100)},
           {'region_id': 'icon', 'bbox': (115, 15, 145, 45)},
           {'region_id': 'corner', 'bbox': (10, 10, 18, 18)}]


def test_triage_deleted_icon_is_must_fix(tmp_path):
    expected, actual = _render_pair(tmp_path, 'deleted-icon')
    findings = review_mod.triage_render_difference(expected, actual, REGIONS)
    icon = next(f for f in findings if f['location'] == 'icon')
    assert icon['impact'] == 'must_fix'
    assert 'collapsed' in icon['detail']


def test_triage_rounding_lost_is_must_fix(tmp_path):
    expected, actual = _render_pair(tmp_path, 'square-corner')
    findings = review_mod.triage_render_difference(expected, actual, REGIONS)
    corner = next(f for f in findings if f['location'] == 'corner')
    assert corner['impact'] == 'must_fix'


def test_triage_antialias_is_accepted_variance_candidate(tmp_path):
    expected, actual = _render_pair(tmp_path, 'antialias')
    findings = review_mod.triage_render_difference(expected, actual, REGIONS)
    assert not any(f['impact'] == 'must_fix' for f in findings)
    canvas = next(f for f in findings if f['location'] == 'canvas')
    assert canvas['impact'] == 'accepted_variance', canvas
    assert 'variance scale' in canvas['detail']


def test_triage_size_mismatch_is_judgment_not_silent(tmp_path):
    small = Image.new('RGB', (80, 50), (255, 255, 255))
    small_path = tmp_path / 'small.png'
    small.save(small_path)
    expected, _ = _render_pair(tmp_path, 'antialias')
    findings = review_mod.triage_render_difference(expected, small_path, REGIONS)
    assert findings[0]['impact'] == 'needs_judgment'
    assert findings[0]['location'] == 'canvas'


# ---------------------------------------------------------------------------
# AC-R05: reviewer independence honesty.


def test_independence_requires_real_evidence():
    v = review_mod.validate_independence
    assert v({'type': 'host_self', 'id': 'host-A', 'execution_ref': None, 'independence_confirmed': True}) is False
    # Two different host_self id strings still cannot certify independence.
    assert v({'type': 'host_self', 'id': 'host-B', 'execution_ref': 'x', 'independence_confirmed': True}) is False
    assert v({'type': 'tool', 'id': 'scanner', 'execution_ref': None, 'independence_confirmed': True}) is False
    # independent_host / human types need an actual execution ref.
    assert v({'type': 'independent_host', 'id': 'ext', 'execution_ref': None, 'independence_confirmed': True}) is False
    assert v({'type': 'independent_host', 'id': 'ext', 'execution_ref': 'run-123', 'independence_confirmed': True}) is True
    assert v({'type': 'human_external', 'id': 'reviewer', 'execution_ref': None, 'independence_confirmed': True}) is False
    assert v({'type': 'human_external', 'id': 'reviewer', 'execution_ref': 'reading-log', 'independence_confirmed': True}) is True
    assert v({'type': 'host_self', 'id': 'host-A', 'execution_ref': None, 'independence_confirmed': False}) is False


# ---------------------------------------------------------------------------
# AC-R06: a fix is closed only by a real recheck review on the new product.


def _r0_failing():
    old_svg = ref('svg-a0-old', 'svg')
    return make_review('conversion', seed='r0', status='fail',
                       subjects=[PAGE_REF, PPTX_OLD, old_svg], findings=[finding('f1')],
                       dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': PAGE_REF['sha256']},
                                     {'kind': 'artifact', 'identity': 'svg:p1', 'sha256': old_svg['sha256']}])


def _r1_closing(r0, *, seed='r1', observations=('复查新产物:标签已存在。',), evidence=(None,)):
    ev = [e if e is not None else ref(f'{seed}-evidence', 'png') for e in evidence]
    candidate = make_review(r0['kind'], seed=seed, status='pass',
                            subjects=[PAGE_REF, PPTX_REF, A1_REF],
                            findings=[finding('f1', impact='must_fix', resolution='fixed', evidence=ev)],
                            replaces=r0['ref'], observations=list(observations),
                            dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': PAGE_REF['sha256']},
                                          {'kind': 'artifact', 'identity': 'svg:p1', 'sha256': A1_REF['sha256']}])
    candidate['review_id'] = r0['review_id']
    return candidate


def test_fixed_requires_replaces_new_subject_and_recheck():
    r0 = _r0_failing()
    r0['ref'] = ref('r0-object')
    r1 = _r1_closing(r0)
    document = make_document()
    summary = review_mod.evaluate_current(document, [r0, r1], current_artifacts())
    dimension = summary['dimensions']['conversion:p1']
    assert dimension['open_must_fix'] == []
    assert dimension['closed_findings'] == ['f1']
    assert dimension['status'] == 'pass'


@pytest.mark.parametrize('mutate', [
    'no_replaces', 'old_subjects', 'no_observations', 'no_evidence', 'stale_subject',
])
def test_fixed_rejected_without_full_recheck(mutate):
    r0 = _r0_failing()
    r0['ref'] = ref('r0-object')
    r1 = _r1_closing(r0)
    if mutate == 'no_replaces':
        r1['replaces'] = None
    elif mutate == 'old_subjects':
        r1['subjects'] = [PAGE_REF, PPTX_REF]
    elif mutate == 'no_observations':
        r1['observations'] = []
    elif mutate == 'no_evidence':
        r1['findings'][0]['evidence'] = []
    elif mutate == 'stale_subject':
        r1['subjects'] = [PAGE_REF, PPTX_REF, ref('svg-a0-old', 'svg')]
    document = make_document()
    summary = review_mod.evaluate_current(document, [r0, r1], current_artifacts())
    dimension = summary['dimensions']['conversion:p1']
    assert dimension['open_must_fix'] == ['f1']
    assert summary['status'] == 'fail'


def test_adopt_review_validates_replaces_chain(tmp_path):
    project = tmp_path / 'proj'
    service.create(project, brief='adopt', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 't', 'body_blocks': []},
        'visual_spec': {'intent': 'x', 'reference_mode': 'new_design'}}]})
    store = Store(project)
    doc = store.load_document()
    a0 = store.put_blob(b'<svg id="a0"/>', ext='svg')
    a1 = store.put_blob(b'<svg id="a1"/>', ext='svg')
    evidence = store.put_blob(b'visual recheck', ext='png')
    r0 = _r0_failing()
    r0['subjects'] = [doc['pages'][0]['page'], a0]
    r0_ref = store.put_json_object(r0)
    from deck_master.tasks import EnvelopeError, _adopt_review

    def r1_base(**overrides):
        candidate = _r1_closing({**r0, 'ref': r0_ref})
        candidate['subjects'] = r0['subjects'] + [a1]
        candidate['findings'][0]['evidence'] = [evidence]
        candidate.update(overrides)
        return candidate

    with pytest.raises(EnvelopeError):
        _adopt_review(store, r1_base(replaces=ref('missing-object')))
    with pytest.raises(EnvelopeError):
        _adopt_review(store, r1_base(replaces=doc['pages'][0]['page']))
    with pytest.raises(EnvelopeError):
        _adopt_review(store, r1_base(review_id='different-id'))
    with pytest.raises(EnvelopeError):
        _adopt_review(store, r1_base(subjects=r0['subjects']))
    # Raw blobs are not current page artifacts and cannot prove a page repair.
    with pytest.raises(EnvelopeError, match='same-page product'):
        _adopt_review(store, r1_base())


def test_final_review_accepts_only_evidenced_current_judgment_resolution():
    old = make_review('content', seed='judgment', status='needs_review', findings=[
        finding('variance', impact='needs_judgment'),
        finding('still-open', impact='needs_judgment')])
    old['ref'] = ref('judgment-review')
    accepted = make_review('content', seed='resolution', status='pass', replaces=old['ref'])
    accepted['review_id'] = old['review_id']
    accepted['findings'] = [{**finding('variance', impact='needs_judgment',
                                      resolution='accepted_variance', evidence=[ref('proof')]),
                             'resolution_reason': '逐项核对后没有字形遮挡'}]
    others = [r for r in pass_set() if r['kind'] != 'content']
    reviews = [old, accepted, *others]
    result = review_mod.evaluate_current(make_document(), reviews, current_artifacts())
    assert result['dimensions']['content:p1']['pending_judgments'] == ['still-open']
    assert result['status'] == 'needs_review'
    accepted['findings'].append({**finding('still-open', impact='needs_judgment',
                                          resolution='accepted_variance', evidence=[ref('proof')]),
                                 'resolution_reason': '复核确认是合理差异'})
    assert review_mod.evaluate_current(make_document(), reviews, current_artifacts())['status'] == 'pass'
    accepted['dependencies'][0]['sha256'] = '0' * 64
    assert review_mod.evaluate_current(make_document(), reviews, current_artifacts())['status'] == 'needs_review'
    accepted['dependencies'][0]['sha256'] = PAGE_REF['sha256']
    accepted['findings'][0]['evidence'] = []
    assert review_mod.evaluate_current(make_document(), reviews, current_artifacts())['status'] == 'needs_review'


def test_receiver_accepts_same_product_variance_but_not_must_fix_relabel(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='review', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 't', 'body_blocks': []},
        'visual_spec': {'intent': 'x', 'reference_mode': 'new_design'}}]})
    store = Store(project)
    subject = store.load_document()['pages'][0]['page']
    evidence = store.put_blob(b'observed no glyph overlap', ext='png')
    original = make_review('blueprint_fidelity', seed='variance', status='needs_review',
                           subjects=[subject], findings=[finding('f1', impact='needs_judgment')],
                           dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': subject['sha256']}])
    original_ref = store.put_json_object(original)
    candidate = make_review('blueprint_fidelity', seed='recheck', subjects=[subject],
                            replaces=original_ref,
                            dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': subject['sha256']}])
    candidate['review_id'] = original['review_id']
    candidate['findings'] = [{**finding('f1', impact='needs_judgment',
                                       resolution='accepted_variance', evidence=[evidence]),
                              'resolution_reason': '已实际检查字形没有遮挡'}]
    assert tasks_mod._adopt_review(store, candidate) == candidate
    without_reason = deepcopy(candidate)
    without_reason['findings'][0]['resolution_reason'] = ''
    with pytest.raises(tasks_mod.EnvelopeError, match='reason'):
        tasks_mod._adopt_review(store, without_reason)
    must_fix = deepcopy(original)
    must_fix['findings'][0]['impact'] = 'must_fix'
    must_fix['status'] = 'fail'
    candidate['replaces'] = store.put_json_object(must_fix)
    with pytest.raises(tasks_mod.EnvelopeError, match='needs_judgment'):
        tasks_mod._adopt_review(store, candidate)


# ---------------------------------------------------------------------------
# AC-R07: real leaks found, business words left alone.


def test_privacy_scan_finds_internal_fields_and_markers():
    page = {'customer_visible': {
        'title': '发布版页面',
        'body_blocks': [{'id': 'b1', 'type': 'paragraph', 'text': '本页包含 内部资料 级别内容'}],
        'internal_only': {'note': '仅内部讨论', 'speaker_notes': '讲者备注:不要读出来'},
    }}
    findings = review_mod.privacy_findings(page)
    impacts = {(f['location'], f['impact']) for f in findings}
    assert any('/internal_only' in loc for loc, _ in impacts)
    assert any('speaker_notes' in loc for loc, _ in impacts)
    assert any('sensitive marker' in f['detail'] for f in findings)


def test_privacy_scan_ignores_business_words():
    page = {'customer_visible': {
        'title': '控制台缩略图',
        'body_blocks': [{'id': 'b1', 'type': 'paragraph', 'text': '左屏与右屏的页角色分工如下'}],
    }}
    assert review_mod.privacy_findings(page) == []


def test_privacy_scan_teaching_context_is_not_a_leak():
    howto = {'customer_visible': {'title': '教学页', 'body_blocks': [
        {'id': 'b', 'type': 'paragraph', 'text': '如何制作PPT的五个步骤'}]}}
    assert review_mod.privacy_findings(howto, intent='教学任务:讲解幻灯片制作') == []
    flagged = review_mod.privacy_findings(howto)
    assert flagged and all(f['impact'] == 'needs_judgment' for f in flagged)


# ---------------------------------------------------------------------------
# AC-C05: fact / calculation / advice separation.


def test_classify_finding_recomputes_calculations():
    ok = review_mod.classify_finding('完成率 54÷120=45%,与本期目标一致')
    assert ok['category'] == 'calculation' and ok['impact'] == 'advisory'
    bad = review_mod.classify_finding('完成率 54÷120=52%')
    assert bad['category'] == 'calculation' and bad['impact'] == 'must_fix'
    assert '45' in bad['detail']


def test_classify_finding_numbers_without_basis_need_judgment():
    claim = review_mod.classify_finding('预计上线后效率提升40%')
    assert claim['category'] == 'unsupported_number' and claim['impact'] == 'needs_judgment'
    sourced = review_mod.classify_finding('效率提升40%(依据上季度基准)')
    assert sourced['category'] == 'fact'


def test_classify_finding_advice_is_advisory_and_readonly():
    advice = review_mod.classify_finding('建议补充一个失败案例以增强说服力')
    assert advice['category'] == 'advice' and advice['impact'] == 'advisory'
    conditional = review_mod.classify_finding('如果受众是管理层,则建议先给结论')
    assert conditional['category'] == 'advice'
    fact = review_mod.classify_finding('本期范围只包含只读接口')
    assert fact['category'] == 'fact'


# ---------------------------------------------------------------------------
# AC-B07: source expectations are independent of the SVG registry.


def test_source_expectations_survive_registry_shrink():
    regions = [{'region_id': 'icon', 'importance': 'essential'},
               {'region_id': 'chart', 'importance': 'supporting'},
               {'region_id': 'footer', 'importance': 'decorative'}]
    full = review_mod.source_expectations(regions, ['icon', 'chart', 'footer'])
    assert full['coverage'] == 1.0
    shrunk = review_mod.source_expectations(regions, ['icon'])
    assert {r['region_id'] for r in shrunk['regions']} == {'icon', 'chart', 'footer'}
    assert shrunk['regions'][0]['status'] == 'confirmed'
    assert shrunk['regions'][1]['status'] == 'not_evaluated'
    assert shrunk['coverage'] is None
    empty = review_mod.source_expectations(regions, [])
    assert all(r['status'] == 'not_evaluated' for r in empty['regions'])
    assert empty['coverage'] is None


def test_style_dependency_freshness_turns_old_pass_into_stale():
    # A review depending on the page's effective style is current only while
    # the style fingerprint matches; a style change demotes it to history.
    from deck_master.models import canonical_json_bytes, sha256_bytes
    style = {'style_id': 'default'}
    style_sha = sha256_bytes(canonical_json_bytes(style))
    document = make_document()
    review = make_review('content', seed='styled',
                         dependencies=[{'kind': 'style', 'identity': 'p1',
                                        'sha256': style_sha}])
    summary = review_mod.evaluate_current(document, [review], {**current_artifacts(),
                                                               'style:p1': style_sha})
    assert summary['status'] == 'not_evaluated'
    assert 'content:p1' in summary['dimensions'], 'style-fresh review counts as current'
    # Style drifts: same review becomes stale and the dimension turns missing.
    summary = review_mod.evaluate_current(document, [review],
                                          {**current_artifacts(), 'style:p1': 'a' * 64})
    assert 'content:p1' in summary['missing_dimensions']
    assert any(s['reason'] == 'dependency sha does not match the current object'
               for s in summary['stale'])


def test_untracked_dependency_kind_is_conservatively_stale():
    document = make_document()
    review = make_review('content', seed='untracked',
                         dependencies=[{'kind': 'toolchain', 'identity': 'compiler',
                                        'sha256': '0' * 64}])
    summary = review_mod.evaluate_current(document, [review], current_artifacts())
    assert 'content:p1' in summary['missing_dimensions']
    assert any('unverifiable dependency kind' in s['reason'] for s in summary['stale'])


def test_open_task_suspends_only_its_scope_pages():
    # A running/awaiting Host task blocks interpretation only for its scope
    # pages; other pages keep their current dimensions (no global blackout).
    document = make_document(pages=('p1', 'p2'))
    p2_ref = ref('page-p2')
    reviews = pass_set('s1') + [
        make_review(kind, page_id='p2', seed=f's2-{kind}', subjects=[p2_ref, PPTX_REF],
                    dependencies=[{'kind': 'content', 'identity': 'page:p2',
                                   'sha256': p2_ref['sha256']}])
        for kind in review_mod.REQUIRED_KINDS
    ]
    artifacts = {**current_artifacts(), 'content:page:p2': ref('page-p2')['sha256']}
    task = {'task_id': 't-1', 'status': 'running', 'scope_pages': ['p2']}
    summary = review_mod.evaluate_current({**document, 'tasks': [task]}, reviews, artifacts)
    assert summary['status'] == 'not_evaluated'
    assert 'p2' in summary['reason']
    assert set(summary['dimensions']) == {f'{kind}:p1' for kind in review_mod.REQUIRED_KINDS}
    assert all(key.endswith(':p2') for key in summary['missing_dimensions'])
    # A fail on an unsuspended page still surfaces (fail is not masked).
    failing = make_review('content', seed='sf', status='fail', findings=[finding('fx')])
    summary = review_mod.evaluate_current({**document, 'tasks': [task]}, [failing] + reviews[1:7], artifacts)
    assert summary['status'] == 'fail'


def test_privacy_false_friend_does_not_mask_sensitive_marker_in_same_string():
    page = {'customer_visible': {
        'title': '缩略图说明:此图机密,仅限内部使用',
        'body_blocks': [],
    }}
    findings = review_mod.privacy_findings(page)
    assert findings and all(f['impact'] == 'must_fix' for f in findings), \
        'a sensitive marker in a string that also contains a business word must still report'


# ---------------------------------------------------------------------------
# PR 轮 A (P1-01/02/07): output facts in the one interpretation, finding-level
# continuation, substance gates, and unified dependency resolution.


def _facts_document(facts):
    return {**make_document(), '_output_facts': facts}


def test_render_report_fail_overrides_passing_reviews():
    facts = {'render_report_status': 'fail',
             'render_report_findings': [{'page_id': 'p1', 'code': 'missing_visible_atom',
                                         'atom_id': 'atom:p1:title', 'text': '标题'}],
             'completeness': []}
    summary = review_mod.evaluate_current(_facts_document(facts), pass_set(), current_artifacts())
    assert summary['status'] == 'fail'
    assert summary['render_report_findings'][0]['code'] == 'missing_visible_atom'


def test_missing_render_report_blocks_pass():
    facts = {'render_report_missing': True, 'completeness': []}
    summary = review_mod.evaluate_current(_facts_document(facts), pass_set(), current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert summary['output_facts']['render_report_missing'] is True


def test_completeness_gap_blocks_pass():
    facts = {'completeness': [{'page_id': 'p1', 'code': 'missing_svg'}]}
    summary = review_mod.evaluate_current(_facts_document(facts), pass_set(), current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert summary['output_facts']['completeness'][0]['code'] == 'missing_svg'


def test_plain_pass_does_not_clear_open_findings():
    # R0 fail (F1+F2) then a plain new pass on the same deps: open findings continue.
    r0 = make_review('content', seed='r0-open', status='fail',
                     findings=[finding('f1'), finding('f2')])
    plain_pass = make_review('content', seed='r0-plain', status='pass')
    summary = review_mod.evaluate_current(make_document(), [r0, plain_pass], current_artifacts())
    dimension = summary['dimensions']['content:p1']
    assert dimension['open_must_fix'] == ['f1', 'f2']
    assert summary['status'] == 'fail'


def test_partial_closure_keeps_remaining_findings_open():
    r0 = _r0_failing()
    r0['kind'] = 'content'
    r0['findings'].append(finding('f2'))
    r0['ref'] = ref('r0-partial-object')
    closing = _r1_closing(r0)
    summary = review_mod.evaluate_current(make_document(), [r0, closing], current_artifacts())
    dimension = summary['dimensions']['content:p1']
    assert dimension['closed_findings'] == ['f1'] and dimension['open_must_fix'] == ['f2']
    assert summary['status'] == 'fail'


def test_finding_closure_requires_changed_bytes_on_the_finding_page_and_survives_forks():
    old_svg, new_svg, other_svg = ref('old-p1', 'json'), ref('new-p1', 'json'), ref('new-p2', 'json')
    original = make_review('conversion', seed='page-owned', status='fail',
                           subjects=[PAGE_REF, PPTX_OLD, old_svg], findings=[finding('f1')],
                           dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': PAGE_REF['sha256']}])
    original['ref'] = ref('page-owned-review')
    def closing(subject, seed):
        candidate = make_review('conversion', seed=seed, subjects=[PAGE_REF, PPTX_REF, subject],
                                replaces=original['ref'], findings=[finding('f1', resolution='fixed', evidence=[ref('proof')])])
        candidate['review_id'] = original['review_id']
        return candidate
    context = {**current_artifacts(), '_subjects': {
        (PAGE_REF['path'], PAGE_REF['sha256']): {'page_id': 'p1', 'role': 'page', 'file_sha': PAGE_REF['sha256'], 'current': True},
        (PPTX_OLD['path'], PPTX_OLD['sha256']): {'page_id': None, 'role': 'pptx', 'file_sha': 'old-deck', 'current': False},
        (PPTX_REF['path'], PPTX_REF['sha256']): {'page_id': None, 'role': 'pptx', 'file_sha': 'new-deck', 'current': True},
        (old_svg['path'], old_svg['sha256']): {'page_id': 'p1', 'role': 'svg', 'file_sha': 'old', 'current': False},
        (new_svg['path'], new_svg['sha256']): {'page_id': 'p1', 'role': 'svg', 'file_sha': 'new', 'current': True},
        (other_svg['path'], other_svg['sha256']): {'page_id': 'p2', 'role': 'svg', 'file_sha': 'new', 'current': True},
    }}
    good, wrong_page = closing(new_svg, 'good'), closing(other_svg, 'wrong-page')
    assert not review_mod.finding_closed([original, wrong_page], original, original['findings'][0], context)
    assert review_mod.finding_closed([original, good, wrong_page], original, original['findings'][0], context)
    assert review_mod.finding_closed([original, wrong_page, good], original, original['findings'][0], context)
    same_bytes = closing(new_svg, 'same-bytes')
    context['_subjects'][(new_svg['path'], new_svg['sha256'])]['file_sha'] = 'old'
    assert not review_mod.finding_closed([original, same_bytes], original, original['findings'][0], context)
    deck_only = closing(new_svg, 'deck-only')
    deck_only['subjects'] = [PAGE_REF, PPTX_REF]
    context['_subjects'][(PPTX_OLD['path'], PPTX_OLD['sha256'])]['slides'] = {'p1': 'slide-1', 'p2': 'slide-2'}
    context['_subjects'][(PPTX_REF['path'], PPTX_REF['sha256'])]['slides'] = {'p1': 'slide-1', 'p2': 'changed-2'}
    assert not review_mod.finding_closed([original, deck_only], original, original['findings'][0], context)
    context['_subjects'][(PPTX_REF['path'], PPTX_REF['sha256'])]['slides']['p1'] = 'changed-1'
    assert review_mod.finding_closed([original, deck_only], original, original['findings'][0], context)
    middle_svg = ref('middle-p1', 'json')
    context['_subjects'][(middle_svg['path'], middle_svg['sha256'])] = {
        'page_id': 'p1', 'role': 'svg', 'file_sha': 'middle', 'current': False}
    middle = closing(middle_svg, 'middle')
    middle['ref'] = ref('middle-review')
    middle['subjects'] = [PAGE_REF, PPTX_OLD, middle_svg]
    middle['findings'][0]['resolution'] = 'open'
    tail = closing(new_svg, 'tail')
    tail['replaces'] = middle['ref']
    context['_subjects'][(new_svg['path'], new_svg['sha256'])]['file_sha'] = 'new'
    assert review_mod.finding_closed([original, middle, tail], original, original['findings'][0], context)


def test_retired_asset_can_leave_closure_dependencies_but_broken_active_asset_cannot():
    original = _r0_failing()
    original['ref'] = ref('asset-owner')
    original['dependencies'].append({'kind': 'asset', 'identity': 'retired', 'sha256': ref('asset')['sha256']})
    candidate = _r1_closing(original)
    candidate['findings'][0]['resolution_reason'] = '旧资产已从当前设计移除，本页新 SVG 已复核'
    context = {**current_artifacts(), '_retired_assets': {('retired', ref('asset')['sha256'])}}
    assert review_mod.finding_closed([original, candidate], original, original['findings'][0], context)
    context['_retired_assets'] = set()
    assert not review_mod.finding_closed([original, candidate], original, original['findings'][0], context)


def test_retired_asset_requires_a_matching_readable_historical_reference(tmp_path):
    from deck_master.editing import _current_artifact_digests
    project = tmp_path / 'project'
    service.create(project, brief='资产历史', draft={'pages': [{
        'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 't', 'body_blocks': []},
        'visual_spec': {'intent': 'x', 'reference_mode': 'new_design'}}]})
    image = tmp_path / 'asset.png'
    from PIL import Image
    Image.new('RGB', (8, 8), 'red').save(image)
    service.import_asset(project, asset_id='logo', kind='logo', file_path=image)
    store = Store(project)
    doc = store.load_document()
    asset = doc['design_context']['assets'][0]
    sha = store.read_object_json(asset['artifact'])['file']['sha256']
    prior = make_review('conversion', seed='old-asset', subjects=[doc['pages'][0]['page']],
                        dependencies=[{'kind': 'asset', 'identity': 'logo', 'sha256': sha},
                                      {'kind': 'asset', 'identity': 'logo', 'sha256': 'a' * 64}])
    changed = tasks_mod.bump_revision(doc, {'operation_id': 'asset-review', 'kind': 'task_update',
                                            'description': 'historical review', 'read_set': []})
    changed['reviews'].append(store.put_json_object(prior))
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id='asset-review')
    design = deepcopy(store.load_document()['design_context'])
    design['assets'] = []
    design['allowed_asset_ids'] = []
    service.update_design(project, design_context=design)
    retired = _current_artifact_digests(store, store.load_document())['_retired_assets']
    assert ('logo', sha) in retired
    assert ('logo', 'a' * 64) not in retired


def test_tool_pass_rejected_for_substantive_kinds():
    tool_pass = make_review('content', seed='tool-content', status='pass',
                            reviewer={'type': 'tool', 'id': 'scanner', 'execution_ref': None,
                                      'independence_confirmed': False})
    others = [r for r in pass_set() if r['kind'] != 'content']
    summary = review_mod.evaluate_current(make_document(), [tool_pass] + others, current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert summary['dimension_reasons']['content:p1'] == 'tool_cannot_substance'


def test_empty_observations_pass_rejected():
    silent = make_review('readability', seed='silent', status='pass', observations=[])
    others = [r for r in pass_set() if r['kind'] != 'readability']
    summary = review_mod.evaluate_current(make_document(), [silent] + others, current_artifacts())
    assert summary['status'] == 'not_evaluated'
    assert summary['dimension_reasons']['readability:p1'] == 'missing_execution_evidence'


def test_blueprint_fidelity_tool_pass_rejected():
    tool_pass = make_review('blueprint_fidelity', seed='tool-bf', status='pass',
                            reviewer={'type': 'tool', 'id': 'diff', 'execution_ref': None,
                                      'independence_confirmed': False})
    others = [r for r in pass_set() if r['kind'] != 'blueprint_fidelity']
    summary = review_mod.evaluate_current(make_document(), [tool_pass] + others, current_artifacts())
    assert summary['dimension_reasons']['blueprint_fidelity:p1'] == 'tool_cannot_substance'


def test_resolvable_source_dependency_is_current():
    document = make_document()
    document['sources'] = [{'source_id': 'src-1', 'name': 'm.txt', 'original_uri': 'm.txt',
                            'original_sha256': None, 'format': 'txt',
                            'extract': {'path': '.deckmaster/objects/ab/x.json', 'sha256': 'b' * 64},
                            'external_use': 'unspecified', 'restriction': '', 'locator_scheme': 'none'}]
    review = make_review('content', seed='src-dep', status='pass',
                         dependencies=[{'kind': 'source', 'identity': 'src-1', 'sha256': 'b' * 64}])
    summary = review_mod.evaluate_current(document, [review], {**current_artifacts(), 'source:src-1': 'b' * 64})
    assert 'content:p1' in summary['dimensions']


def test_unresolvable_source_dependency_is_stale():
    review = make_review('content', seed='src-miss', status='pass',
                         dependencies=[{'kind': 'source', 'identity': 'ghost', 'sha256': 'b' * 64}])
    summary = review_mod.evaluate_current(make_document(), [review], current_artifacts())
    assert 'content:p1' in summary['missing_dimensions']
    assert any('unresolvable source' in s['reason'] for s in summary['stale'])


def test_missing_artifact_dependency_is_stale_not_skipped():
    review = make_review('content', seed='art-miss', status='pass',
                         dependencies=[{'kind': 'artifact', 'identity': 'ppt_preview:p1', 'sha256': 'b' * 64}])
    summary = review_mod.evaluate_current(make_document(), [review], current_artifacts())
    assert 'content:p1' in summary['missing_dimensions']
    assert any('unverifiable' in s['reason'] for s in summary['stale'])


def _page_only_owner():
    owner = make_review('conversion', seed='page-only', status='fail', subjects=[PAGE_REF],
                        findings=[finding('f1')],
                        dependencies=[{'kind': 'content', 'identity': 'page:p1', 'sha256': PAGE_REF['sha256']},
                                      {'kind': 'artifact', 'identity': 'svg:p1', 'sha256': 'b' * 64}])
    owner['ref'] = ref('page-only-owner')
    return owner


def _page_only_context():
    return {**current_artifacts(), '_subjects': {
        (PAGE_REF['path'], PAGE_REF['sha256']): {'page_id': 'p1', 'role': 'page',
                                                 'file_sha': PAGE_REF['sha256'], 'current': True},
        (PPTX_REF['path'], PPTX_REF['sha256']): {'page_id': None, 'role': 'pptx',
                                                 'file_sha': 'new-deck', 'current': True},
        (A1_REF['path'], A1_REF['sha256']): {'page_id': 'p1', 'role': 'svg',
                                             'file_sha': A1_REF['sha256'], 'current': True},
    }}


def test_owner_without_deck_or_svg_subject_closes_on_current_page_dependency_change():
    owner = _page_only_owner()
    closing = _r1_closing(owner)
    context = _page_only_context()
    assert review_mod.finding_closed([owner, closing], owner, owner['findings'][0], context)
    summary = review_mod.evaluate_current(make_document(), [owner, closing], context)
    assert summary['dimensions']['conversion:p1']['open_must_fix'] == []


def test_owner_without_deck_subject_stays_open_when_svg_digest_did_not_change():
    owner = _page_only_owner()
    owner['dependencies'][1]['sha256'] = A1_REF['sha256']
    closing = _r1_closing(owner)
    assert not review_mod.finding_closed([owner, closing], owner, owner['findings'][0], _page_only_context())


def test_untracked_legacy_dependency_can_be_dropped_only_with_reason():
    owner = _r0_failing()
    owner['ref'] = ref('legacy-superset')
    owner['dependencies'].append({'kind': 'svg_legacy', 'identity': 'p1', 'sha256': 'c' * 64})
    closing = _r1_closing(owner)
    assert not review_mod.finding_closed([owner, closing], owner, owner['findings'][0], current_artifacts())
    closing['findings'][0]['resolution_reason'] = '旧依赖已不再跟踪，本页新 SVG 已复核'
    assert review_mod.finding_closed([owner, closing], owner, owner['findings'][0], current_artifacts())
    tracked = _r1_closing(owner)
    tracked['findings'][0]['resolution_reason'] = '丢弃仍在跟踪的依赖'
    tracked['dependencies'] = [dep for dep in tracked['dependencies'] if dep['identity'] != 'svg:p1']
    owner['dependencies'] = [dep for dep in owner['dependencies'] if dep['kind'] != 'svg_legacy']
    assert not review_mod.finding_closed([owner, tracked], owner, owner['findings'][0], current_artifacts())


def test_page_visual_ignores_historical_findings_without_the_page():
    blueprint, svg, preview = ref('bp-p1'), ref('svg-p1'), ref('pv-p1')
    entry = {'page_id': 'p1', 'page': PAGE_REF, 'blueprint': blueprint, 'svg': svg, 'svg_preview': preview}
    artifacts = {'content:page:p1': PAGE_REF['sha256'], 'blueprint:p1': 'b' * 64,
                 'artifact:svg:p1': 'c' * 64, 'style:p1': 'd' * 64}
    deps = [{'kind': 'content', 'identity': 'page:p1', 'sha256': PAGE_REF['sha256']},
            {'kind': 'blueprint', 'identity': 'p1', 'sha256': 'b' * 64},
            {'kind': 'artifact', 'identity': 'svg:p1', 'sha256': 'c' * 64},
            {'kind': 'style', 'identity': 'p1', 'sha256': 'd' * 64}]
    reviews = []
    for kind in review_mod.PAGE_VISUAL_KINDS:
        item = make_review(kind, seed=f'pv-{kind}', subjects=[PAGE_REF, blueprint, svg, preview],
                           dependencies=deps)
        item['review_stage'] = 'page_visual'
        reviews.append(item)
    orphan = make_review('readability', seed='orphan', status='fail', subjects=[PAGE_REF],
                         dependencies=deps[:1], findings=[{**finding('f-null'), 'page_id': None}])
    orphan['review_stage'] = 'page_visual'
    summary = review_mod.evaluate_page_visual(entry, [*reviews, orphan], artifacts)
    assert summary['unclosed_prior_findings'] == []
    assert summary['status'] == 'pass'
