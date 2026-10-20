"""RC4 N3 mechanical contract evidence; synthetic projects, no model calls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from deck_master import content_production, method_resources, models, service, tasks
from deck_master.store import Store
from test_content_contracts import _narrative, _node
from test_compose_v2_phases import (
    _project, _request, _dispatch, _submit, _argument_narrative, _adopt_direction,
    _scope, _instruction,
)

POLICY = "argument-connectivity.v1"
BASELINE = "a08bc68c1cbbbc806205104c2bb01f3f096305f0"
REPO = Path(__file__).resolve().parents[2]


def _bytes(project):
    return {str(path.relative_to(project)): path.read_bytes()
            for path in project.rglob('*') if path.is_file() and path.name != 'write.lock'}


@pytest.mark.parametrize('extra', [
    {}, {'edges': [{'from_node_id': 'n2', 'to_node_id': 'n2', 'relation': 'supports'}]},
    {'issues': [{'issue_id': 'i1', 'question': 'unknown', 'resolution_ref': None,
                 'impact': 'blocker', 'resolution': 'open', 'affected_node_ids': ['n1', 'n2']}]},
])
def test_disconnected_nodes_and_self_loops_do_not_pass(extra):
    narrative = _narrative(nodes=[_node(), _node(node_id='n2')], **extra)
    # Historical reads retain their old semantics.
    models.validate_narrative_semantics(narrative)
    before = copy.deepcopy(narrative)
    with pytest.raises(models.NarrativeDisconnected) as caught:
        models.validate_narrative_semantics(narrative, policy=POLICY)
    assert caught.value.error_details == {'central_node_id': 'n1', 'unreachable_node_ids': ['n2'], 'policy': POLICY}
    assert narrative == before


def test_qualification_and_weak_mixed_direction_chain_preserve_input():
    nodes = [_node(qualification_node_ids=['q']), _node(node_id='q', role='qualification'),
             _node(node_id='n2'), _node(node_id='n3')]
    narrative = _narrative(nodes=nodes, edges=[
        {'from_node_id': 'q', 'to_node_id': 'n2', 'relation': 'prerequisite'},
        {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'leads_to'},
        {'from_node_id': 'n3', 'to_node_id': 'n2', 'relation': 'supports'},
    ])
    before = models.canonical_json_bytes(narrative)
    models.validate_narrative_semantics(narrative, policy=POLICY)
    assert models.canonical_json_bytes(narrative) == before
    models.validate_narrative_semantics(_narrative(), policy=POLICY)
    models.validate_narrative_semantics(_narrative(maturity='framing', nodes=[], central_node_id=None), policy=POLICY)


@pytest.mark.parametrize(('stage', 'units', 'expected'), [
    ('preproduction', ['argument', 'page_copy', 'progression'], ['source-reading','content-methods','content-examples','content-calibration','review-and-repair','method-review']),
    ('preproduction', ['page_copy','progression'], ['source-reading','content-methods','content-examples','content-calibration','review-and-repair','method-review']),
    ('final', ['content'], ['source-reading','content-methods','content-calibration','review-and-repair','method-review']),
    ('final', ['speech'], ['content-methods','review-and-repair','method-review']),
    ('page_visual', ['blueprint_content','readability'], ['review-and-repair','physical-units']),
    ('final', ['conversion','privacy'], ['review-and-repair','physical-units']),
    ('final', ['content','conversion','speech'], ['source-reading','content-methods','content-calibration','review-and-repair','physical-units','method-review']),
])
def test_review_scope_union_is_stable(stage, units, expected):
    assert list(method_resources.method_ids_for('review', intent=stage, review_units=units)) == expected
    assert list(method_resources.method_ids_for('review', intent=stage, review_units=list(reversed(units)) + units)) == expected
    task = tasks.new_task(task_id='review', operation_id='review-op', kind='review', scope_pages=[],
                          instruction='scope', inputs=[], dependencies=[], dispatch_revision='r1',
                          produced_against='0' * 64, review_stage=stage,
                          review_units=[{'kind': u, 'page_ids': [], 'reason': 'missing'} for u in units])
    assert [item['id'] for item in task['method_manifest']] == expected
    assert method_resources.methods_sha256(task['method_manifest']) == task['method_release']['methods_sha256']
    assert 'content_validation_policy' not in task


@pytest.mark.parametrize(('stage','units'), [('final', []), ('final', [1]), ('final', 'content'), ('final',['bogus']), ('page_visual',['content']), ('preproduction',['privacy'])])
def test_invalid_explicit_scope_cannot_silently_reduce_review(stage, units):
    with pytest.raises(models.ModelError, match='review_units'):
        method_resources.method_ids_for('review', intent=stage, review_units=units)


def test_actual_create_continue_and_phase_producer_freeze_atomic_floor(tmp_path):
    project = tmp_path / 'created'
    service.create(project, brief='neutral training', sources=[])
    store = Store(project)
    document = store.load_document()
    assert document['compatibility']['minimum_writer'] == 'method-catalog.v1'
    task = store.read_object_json(document['tasks'][0])
    assert task['method_manifest']
    before = _bytes(project)
    method_resources.read_task_methods(project, task['task_id'])
    service.continue_project(project)
    assert _bytes(project) == before

    (tmp_path / 'phase').mkdir()
    project, store = _project(tmp_path / 'phase')
    _request(project, store)
    task = _dispatch(store, phase='argument')
    assert task['content_validation_policy'] == POLICY
    assert method_resources.resolve_task_methods(task)['basis_status'] == 'current'
    current = store.load_document()
    assert current['compatibility']['minimum_writer'] == 'method-catalog.v1'
    before_current = (project / '.deckmaster/current.json').read_bytes()
    disconnected = _argument_narrative(current['project_id'], edges=[])
    with pytest.raises(models.NarrativeDisconnected) as caught:
        _submit(project, task, {'narrative': disconnected}, 'narrative')
    assert caught.value.unreachable_node_ids == ['n2','q1']
    assert (project / '.deckmaster/current.json').read_bytes() == before_current
    assert tasks._lookup_task(store.load_document(), task['task_id'], store)['status'] == 'running'
    accepted = _submit(project, task, {'narrative': _argument_narrative(current['project_id'])}, 'narrative')
    before = _bytes(project)
    assert _submit(project, task, {'narrative': _argument_narrative(current['project_id'])}, 'narrative')['status'] == 'already_applied'
    assert _bytes(project) == before
    assert accepted['adopted'] is False


def test_no_task_review_reads_scope_without_writes():
    broad = method_resources.read_skill_methods('deck-review')
    assert 'content-calibration' in [m['id'] for m in broad['methods']]
    visual = method_resources.read_skill_methods('deck-review', review_units=['conversion'])
    assert [m['id'] for m in visual['methods']] == ['collaboration-routing','review-and-repair','physical-units']
    assert visual['context'] is None and visual['dispatch'] is None


def test_rc3_selector_does_not_inject_new_review_methods(tmp_path, monkeypatch):
    task = tasks.new_task(task_id='legacy', operation_id='legacy-op', kind='review', scope_pages=[],
                          instruction='old visual methods', inputs=[], dependencies=[], dispatch_revision='r1',
                          produced_against='0' * 64, review_stage='final')
    del task['method_manifest']
    old = method_resources._read_ids(method_resources.rc3_method_ids_for('review', intent='final'))
    task['method_release'] = method_resources.method_release(old)
    resolved = method_resources.resolve_task_methods(task)
    assert resolved['basis_status'] == 'current'
    assert [m['id'] for m in resolved['methods']] == ['review-and-repair','physical-units']
    alternate = tmp_path / 'install'
    for entry in old:
        path = alternate / entry['relative_path']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(entry['path']).read_bytes())
    monkeypatch.setattr(method_resources, 'resolve_root', lambda: alternate)
    (alternate / old[0]['relative_path']).write_text('changed')
    assert method_resources.resolve_task_methods(task)['basis_status'] == 'basis_changed'
    (alternate / old[1]['relative_path']).unlink()
    missing = method_resources.resolve_task_methods(task)
    assert missing['basis_status'] == 'basis_changed'
    assert any(i.get('reason') == 'missing' for i in missing['issues'])


def test_missing_policy_cannot_bypass_acceptance_and_continue_reissues(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store)
    task = _dispatch(store, phase='argument')
    original = copy.deepcopy(task)
    task.pop('method_manifest'); task.pop('content_validation_policy')
    document = store.load_document()
    changed = models.bump_revision(document, {'operation_id':'fixture-legacy-active','kind':'task_update','description':'old active Task','read_set':[]})
    tasks._replace_task_in_document(changed, original, store.put_json_object(task), store)
    store.commit_change(base_revision=document['revision_id'],document=changed, operation_id='fixture-legacy-active')
    before = (project / '.deckmaster/current.json').read_bytes()
    with pytest.raises(tasks.MethodBasisChanged):
        _submit(project, task, {'narrative':_argument_narrative(document['project_id'],edges=[])}, 'narrative')
    assert (project / '.deckmaster/current.json').read_bytes() == before
    service.continue_project(project)
    current = store.load_document()
    assert tasks._lookup_task(current, task['task_id'], store)['status'] == 'superseded'
    replacements = [store.read_object_json(ref) for ref in current['tasks']
                    if store.read_object_json(ref)['status'] == 'awaiting_host'
                    and (store.read_object_json(ref).get('collaboration_binding') or {}).get('phase') == 'argument']
    assert len(replacements) == 1
    assert replacements[0]['task_id'] != task['task_id']
    assert replacements[0]['content_validation_policy'] == POLICY
    assert replacements[0]['method_manifest']


@pytest.fixture(scope='module')
def baseline_checkout(tmp_path_factory):
    root = tmp_path_factory.mktemp('real-rc3-code')
    archive = subprocess.run(['git','archive',BASELINE,'src/deck_master','skills/deck-master','pyproject.toml'],
                             cwd=REPO,check=True,capture_output=True).stdout
    import io
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(root, filter='data')
    return root


def _baseline_env(root):
    return {**os.environ,'PYTHONPATH': str(root / 'src') + os.pathsep + str(REPO / 'tests/rebuild')}


def test_real_old_writer_refuses_before_any_project_bytes_change(tmp_path, baseline_checkout):
    project = tmp_path / 'project'; service.create(project, brief='neutral training', sources=[])
    before = _bytes(project)
    result = subprocess.run([sys.executable,'-c',
        'from deck_master import service; '
        'service.continue_project(__import__("sys").argv[1])',str(project)],
        env=_baseline_env(baseline_checkout), cwd=baseline_checkout, capture_output=True,text=True)
    assert result.returncode != 0 and 'unsupported minimum writer' in result.stderr
    assert _bytes(project) == before
    assert models.collaboration_required({'compatibility':{'minimum_writer':'rc4-content.v1'}})
    with pytest.raises(models.ModelError, match='collaboration'):
        document = Store(project).load_document(); document.pop('collaboration')
        models.validate_document_semantics(document)


def test_real_rc3_committed_disconnected_proposal_can_first_adopt_and_replay(tmp_path, baseline_checkout, monkeypatch):
    script = '''
import json, sys
from pathlib import Path
from test_compose_v2_phases import _project,_request,_dispatch,_submit,_argument_narrative
project,store=_project(Path(sys.argv[1]));_request(project,store)
task=_dispatch(store,phase="argument")
argument=_argument_narrative(store.load_document()["project_id"],edges=[])
result=_submit(project,task,{"narrative":argument},"narrative")
Path(sys.argv[1],"legacy.json").write_text(json.dumps({"task":task,"argument":argument,"result":result}))
'''
    subprocess.run([sys.executable,'-c',script,str(tmp_path)],env=_baseline_env(baseline_checkout),
                   cwd=baseline_checkout,check=True,capture_output=True,text=True)
    project=tmp_path/'proj'; store=Store(project)
    data=json.loads((tmp_path/'legacy.json').read_text())
    assert 'method_manifest' not in data['task']
    before=_bytes(project)
    replay=_submit(project,data['task'],{'narrative':data['argument']},'narrative')
    assert replay['status']=='already_applied' and _bytes(project)==before
    assert store.load_document()['compatibility']['minimum_writer']=='rc3-entry.v1'
    assert content_production._committed_legacy_narrative(store,store.load_document(),data['result']['narrative_ref'])
    _adopt_direction(project,store,data['result']['narrative_ref'])
    assert store.load_document()['narrative']==data['result']['narrative_ref']
    assert store.load_document()['compatibility']['minimum_writer']=='rc3-entry.v1'
    # The first new Task and writer floor are both committed, or neither is.
    import deck_master.store as store_module
    original_write=store_module._atomic_write_bytes
    before_document=store.load_document()
    before_pointer=(project/'.deckmaster/current.json').read_bytes()
    def fail_pointer(path, raw):
        if path.name=='current.json':
            raise OSError('synthetic pointer failure before RC4 floor publication')
        return original_write(path,raw)
    monkeypatch.setattr(store_module,'_atomic_write_bytes',fail_pointer)
    with pytest.raises(OSError,match='pointer failure'):
        content_production.open_phase_task(store,before_document,operation_id='first-rc4-failed',phase='argument')
    assert (project/'.deckmaster/current.json').read_bytes()==before_pointer
    assert store.load_document()==before_document
    monkeypatch.setattr(store_module,'_atomic_write_bytes',original_write)
    new_task=content_production.open_phase_task(store,before_document,operation_id='first-rc4-commit',phase='argument')
    assert new_task['method_manifest'] and new_task['content_validation_policy']==POLICY
    assert store.load_document()['compatibility']['minimum_writer']=='method-catalog.v1'


def test_orphan_and_forged_legacy_markers_do_not_bypass_adoption(tmp_path):
    project,store=_project(tmp_path);_request(project,store)
    narrative=_argument_narrative(store.load_document()['project_id'],edges=[])
    ref=store.put_json_object(narrative)
    assert not content_production._committed_legacy_narrative(store,store.load_document(),ref)
    before=store.load_document().get('narrative')
    with pytest.raises(models.NarrativeDisconnected):
        _adopt_direction(project,store,ref)
    assert store.load_document().get('narrative')==before


@pytest.mark.parametrize('layers,expected', [
    (['review'], ['source-reading','content-methods','content-calibration','review-and-repair','physical-units','method-review']),
    (['speech'], ['content-methods','review-and-repair','method-review']),
    (['svg'], ['review-and-repair','physical-units']),
    (['page_copy'], ['source-reading','content-methods','content-calibration','review-and-repair','method-review']),
])
def test_external_review_handoff_methods_are_readonly_and_not_application(tmp_path, layers, expected):
    from deck_master import external_review
    source=tmp_path/'manuscript.txt';source.write_text('Neutral complete paragraph.')
    before=_bytes(tmp_path)
    scope=_scope(layers=layers, page_ids=[], allow_page_membership_change=False, purpose='review')
    result=external_review.evaluate(source,scope=scope)
    assert [m['id'] for m in result['method_context']['methods']]==expected
    assert result['method_context']['host_application']=='not_recorded'
    assert result['external_report']['report']['provenance']['methods']==[]
    assert _bytes(tmp_path)==before


def test_input_revision_applies_policy_atomically_to_new_narrative(tmp_path):
    from test_planned_input_revision import dispatched_revision, planned_payload, submit
    project,store,task=dispatched_revision(tmp_path)
    assert task['content_validation_policy']==POLICY
    payload=planned_payload(store,task)
    narrative=store.read_object_json(payload['proposals'][0]['ref'])
    narrative['edges']=[]
    payload['proposals'][0]['ref']=store.put_json_object(narrative)
    before=_bytes(project)
    with pytest.raises(models.NarrativeDisconnected):
        submit(project,task,payload)
    assert _bytes(project)==before


def test_single_center_argument_formally_accepts_without_artificial_edges(tmp_path):
    project,store=_project(tmp_path);_request(project,store)
    task=_dispatch(store,phase='argument')
    narrative=_argument_narrative(store.load_document()['project_id'])
    narrative['nodes']=narrative['nodes'][:1];narrative['edges']=[]
    assert _submit(project,task,{'narrative':narrative},'narrative')['status']=='accepted'


def test_error_details_use_existing_cli_and_collaboration_envelopes(capsys):
    from deck_master import cli
    from deck_master.collaboration_api import error_response
    exc=models.NarrativeDisconnected('n1',['isolated'])
    assert cli._fail(exc)==2
    error=json.loads(capsys.readouterr().err)['error']
    assert error['code']=='narrative_disconnected' and error['field']=='payload.narrative.nodes'
    assert error['details']['unreachable_node_ids']==['isolated']
    response,http,code=error_response(exc)
    assert (http,code)==(400,2)
    assert response['error']['details']['policy']==POLICY


@pytest.mark.parametrize('mode', ['named','natural','master','recovery'])
def test_same_review_task_preserves_manifest_across_four_entry_modes(tmp_path, mode):
    from test_rc3_content_methods import _dispatch as dispatch_review
    project,store,outcome=dispatch_review(tmp_path)
    before=_bytes(project)
    response=method_resources.read_skill_methods('deck-review',entry_mode=mode,project=project,
        task_id=outcome['task']['task_id'],text='review this manuscript' if mode=='natural' else None)
    assert [{k:m[k] for k in ('id','relative_path','sha256')} for m in response['methods']]==outcome['task']['method_manifest']
    assert [m['id'] for m in response['entry_methods']]==['collaboration-routing']
    assert _bytes(project)==before


def test_real_review_dispatch_reuses_only_the_same_scope(tmp_path):
    from test_content_preproduction_review import _deck
    project, store = _deck(tmp_path)
    options = {"kind": "review", "page_ids": ["p1", "p2"],
               "review_stage": "final", "instruction": "Review the explicitly selected units"}
    visual_units = [{"kind": "readability", "page_ids": ["p1", "p2"], "reason": "missing"}]
    content_units = [{"kind": "content", "page_ids": ["p1", "p2"], "reason": "missing"}]
    visual = service.open_host_task(store, **options, review_units=visual_units)
    before = _bytes(project)
    assert service.open_host_task(store, **options, review_units=visual_units) == visual
    assert _bytes(project) == before
    content = service.open_host_task(store, **options, review_units=content_units)
    assert content["task_id"] != visual["task_id"]
    assert content["review_units"] == content_units
    assert [item["id"] for item in content["method_manifest"]] == [
        "source-reading", "content-methods", "content-calibration", "review-and-repair", "method-review"]
    before = _bytes(project)
    with pytest.raises(models.ModelError, match="review_units"):
        service.open_host_task(store, **options, review_units=[{"kind": "bogus", "page_ids": [], "reason": "missing"}])
    assert _bytes(project) == before


@pytest.mark.parametrize("stage", ["final", "page_visual", "preproduction"])
def test_real_review_dispatch_default_and_reordered_units_reuse_without_writes(tmp_path, stage):
    from deck_master.review import PAGE_VISUAL_KINDS, REVIEW_DIMENSIONS
    from test_content_preproduction_review import _deck
    project, store = _deck(tmp_path)
    pages = ["p1"] if stage == "page_visual" else ["p1", "p2"]
    options = {"kind": "review", "page_ids": pages, "review_stage": stage,
               "instruction": "Review the stage's full default scope"}
    default = service.open_host_task(store, **options)
    if stage == "preproduction":
        from deck_master.content_review import required_units
        kinds = required_units(store, store.load_document())
    else:
        kinds = PAGE_VISUAL_KINDS if stage == "page_visual" else REVIEW_DIMENSIONS
    explicit = [{"kind": kind, "page_ids": list(reversed(pages)), "reason": "missing"}
                for kind in reversed(kinds)]
    before = _bytes(project)
    assert service.open_host_task(store, **options, review_units=explicit) == default
    assert _bytes(project) == before
    assert "review_units" not in tasks._lookup_task(store.load_document(), default["task_id"], store)


def test_new_and_legacy_stamp_finalization_have_distinct_contracts(tmp_path):
    from deck_master import collaboration_binding
    project,store=_project(tmp_path);_request(project,store)
    document=store.load_document()
    current=tasks.new_task(task_id='new-task',operation_id='new-op',kind='compose',scope_pages=[],
        instruction='new production scope',inputs=[],dependencies=[],dispatch_revision=document['revision_id'],
        produced_against=models.content_identity(document))
    legacy=copy.deepcopy(current);legacy.pop('method_manifest');legacy.pop('method_release')
    before=_bytes(project)
    for task in (current,legacy):
        collaboration_binding.stamp_task(store,document,task,phase='production',write_scope=_scope(),
            adoption_policy='proposal_only')
    assert [m['id'] for m in current['method_manifest']]==list(method_resources.method_ids_for('compose',phase='production'))
    assert 'method_manifest' not in legacy and 'content_validation_policy' not in legacy
    assert _bytes(project)==before


def test_shared_sources_alternatives_and_issues_are_not_argument_edges():
    from test_content_contracts import _source_link
    narrative=_narrative(nodes=[_node(source_links=[_source_link()]),
        _node(node_id='n2',source_links=[_source_link()])],
        alternatives=[{'option_id':'alt','description':'compare','benefit':'unknown','cost':'unknown',
                       'affected_node_ids':['n1','n2']}],
        issues=[{'issue_id':'gap','question':'unknown','impact':'advisory','resolution':'open',
                 'resolution_ref':None,'affected_node_ids':['n1','n2']}])
    with pytest.raises(models.NarrativeDisconnected):
        models.validate_narrative_semantics(narrative,policy=POLICY)


def test_forged_old_completed_task_without_committed_receipt_is_no_exemption(tmp_path):
    project,store=_project(tmp_path);_request(project,store)
    doc=store.load_document()
    narrative=_argument_narrative(doc['project_id'],edges=[]);ref=store.put_json_object(narrative)
    fake=tasks.new_task(task_id='fake-old',operation_id='fake-acceptance',kind='compose',scope_pages=[],
        instruction='forged old marker is no proof',inputs=[],dependencies=[],dispatch_revision=doc['revision_id'],
        produced_against=models.content_identity(doc),status='completed')
    fake.pop('method_manifest');fake.update(protocol_version='compose.v2',result_refs=[ref])
    # Reusing a real binding still cannot manufacture a historical receipt.
    fake['collaboration_binding']=copy.deepcopy(store.read_object_json(doc['tasks'][0])['collaboration_binding'])
    bumped=models.bump_revision(doc,{'operation_id':'fake-history','kind':'task_update','description':'synthetic forged marker','read_set':[]})
    bumped['tasks'].append(store.put_json_object(fake))
    store.commit_change(base_revision=doc['revision_id'],document=bumped,operation_id='fake-history')
    assert not content_production._committed_legacy_narrative(store,store.load_document(),ref)
    with pytest.raises(models.NarrativeDisconnected):
        _adopt_direction(project,store,ref)


@pytest.mark.parametrize('change', ['rewritten_proposal', 'replaced_request'])
def test_real_rc3_acceptance_exemption_requires_unchanged_object_and_current_request(tmp_path, baseline_checkout, change):
    script = '''
import json, sys
from pathlib import Path
from test_compose_v2_phases import _project,_request,_dispatch,_submit,_argument_narrative
project,store=_project(Path(sys.argv[1]));_request(project,store)
task=_dispatch(store,phase="argument")
result=_submit(project,task,{"narrative":_argument_narrative(store.load_document()["project_id"],edges=[])},"narrative")
Path(sys.argv[1],"legacy-ref.json").write_text(json.dumps(result["narrative_ref"]))
'''
    subprocess.run([sys.executable,'-c',script,str(tmp_path)],env=_baseline_env(baseline_checkout),
        cwd=baseline_checkout,check=True,capture_output=True,text=True)
    project=tmp_path/'proj';store=Store(project)
    ref=json.loads((tmp_path/'legacy-ref.json').read_text())
    if change=='rewritten_proposal':
        narrative=store.read_object_json(ref)
        narrative['nodes'][0]['statement']+=' Rewritten after acceptance.'
        ref=store.put_json_object(narrative)
    else:
        from deck_master import collaboration
        doc=store.load_document()
        collaboration.start_request(project,input={'intent':'content_only','content_intent':'content_full',
            'scope':_scope(), 'instruction_evidence':_instruction(store,'replacement'),
            'replace_request_id':doc['collaboration']['request']['request_id']},
            base_revision=doc['revision_id'],operation_id='new-scope-request')
    assert not content_production._committed_legacy_narrative(store,store.load_document(),ref)
    before_narrative=store.load_document().get('narrative')
    with pytest.raises(models.NarrativeDisconnected):
        _adopt_direction(project,store,ref)
    assert store.load_document().get('narrative')==before_narrative


def test_method_reissue_keeps_real_change_action_binding_valid(tmp_path, monkeypatch):
    import shutil
    from deck_master import changes
    from test_content_candidates import (project as candidate_project, dispatch_content_trial,
                                         start_task, accept, page_envelope)
    project,store=candidate_project.__wrapped__(tmp_path)
    task=dispatch_content_trial(project,store)
    original_change=copy.deepcopy(task['change_binding'])
    installed=tmp_path/'new-method-installation'
    shutil.copytree(method_resources.resolve_root(),installed)
    method=installed/'references/content-methods.md'
    method.write_bytes(method.read_bytes()+b'\nUpdated method bytes for synthetic recovery.\n')
    monkeypatch.setattr(method_resources,'resolve_root',lambda:installed)
    tasks.reissue_changed_method_tasks(store)
    doc=store.load_document()
    assert tasks._lookup_task(doc,task['task_id'],store)['status']=='superseded'
    replacement=next(store.read_object_json(ref) for ref in reversed(doc['tasks'])
        if store.read_object_json(ref).get('change_binding',{}).get('action_id')==original_change['action_id']
        and store.read_object_json(ref)['task_id']!=task['task_id'])
    assert replacement['change_binding']['change_ref']!=original_change['change_ref']
    assert changes.action_for_task(store,doc,replacement)['action_id']==original_change['action_id']
    start_task(project,replacement)
    assert accept(project,replacement,page_envelope(store,replacement))['status']=='candidate_ready'


def test_method_reissue_preserves_unspent_fixed_page_credit(tmp_path, monkeypatch):
    import shutil
    from deck_master import eligibility
    from test_rc3_budget_workflow import project as budget_project, grant, spend
    project, store = budget_project(tmp_path)
    authorization = grant(project, store)
    document = store.load_document()
    task = service.open_blueprint_task(store, document, document["pages"][0])
    key = task["collaboration_binding"]["budget_key"]
    budget_before = eligibility.authorization_budget(store, store.load_document(), authorization["authorization_ref"])
    installed = tmp_path / "updated-budget-method-installation"
    shutil.copytree(method_resources.resolve_root(), installed)
    method = installed / "references/physical-units.md"
    method.write_bytes(method.read_bytes() + b"\nSynthetic method revision; no external tool ran.\n")
    monkeypatch.setattr(method_resources, "resolve_root", lambda: installed)
    tasks.reissue_changed_method_tasks(store)
    document = store.load_document()
    retired = tasks._lookup_task(document, task["task_id"], store)
    replacement = next(store.read_object_json(ref) for ref in reversed(document["tasks"])
        if store.read_object_json(ref)["kind"] == "blueprint"
        and store.read_object_json(ref)["task_id"] != task["task_id"])
    assert retired["status"] == "superseded"
    assert [item["state"] for item in retired["call_allowances"]] == ["released"]
    assert replacement["collaboration_binding"]["budget_key"] == key
    assert [item["state"] for item in replacement["call_allowances"]] == ["reserved"]
    budget_after = eligibility.authorization_budget(store, document, authorization["authorization_ref"])
    assert (budget_after["used"], budget_after["remaining"]) == (budget_before["used"], budget_before["remaining"])
    assert eligibility.credit_state(store, document, key)["used"] == 1
    spend(project, store, replacement)
    assert eligibility.credit_state(store, store.load_document(), key)["state"] == "exhausted"


@pytest.mark.parametrize("outcome", ["consumed", "unknown"])
def test_method_reissue_does_not_refresh_spent_or_unknown_fixed_credit(tmp_path, monkeypatch, outcome):
    import shutil
    from deck_master import eligibility
    from test_rc3_budget_workflow import project as budget_project, grant, spend
    project, store = budget_project(tmp_path)
    grant(project, store)
    document = store.load_document()
    task = service.open_blueprint_task(store, document, document["pages"][0])
    spend(project, store, task, outcome=outcome)
    installed = tmp_path / "updated-spent-method-installation"
    shutil.copytree(method_resources.resolve_root(), installed)
    method = installed / "references/physical-units.md"
    method.write_bytes(method.read_bytes() + b"\nSynthetic method revision; no external tool ran.\n")
    monkeypatch.setattr(method_resources, "resolve_root", lambda: installed)
    before = store.load_document()
    error = tasks.MethodBasisChanged if outcome == "unknown" else eligibility.EligibilityBlocked
    with pytest.raises(error):
        tasks.reissue_changed_method_tasks(store)
    assert store.load_document() == before
    assert eligibility.credit_state(store, before, task["collaboration_binding"]["budget_key"])["remaining"] == 0


@pytest.mark.parametrize("state", ["reserved", "consumed", "unknown"])
def test_method_reissue_preserves_change_action_call_ceiling(tmp_path, monkeypatch, state):
    import shutil
    import uuid
    from deck_master import changes, eligibility
    from test_rc3_budget_workflow import project as budget_project, grant, spend, change_input
    project, store = budget_project(tmp_path, intent="edit")
    authorization = grant(project, store, template="explicit", max_external_calls=2)
    plan = changes.plan(project, input=change_input(store, ids=("p1",)))
    result = changes.commit(project, plan_id=plan["plan_id"], base_revision=store.current_revision_id(),
                            operation_id=str(uuid.uuid4()))["operation_result"]
    task = tasks._lookup_task(store.load_document(), result["task_ids"][0], store)
    original_change = store.read_object_json(task["change_binding"]["change_ref"])
    assert changes.action_for_task(store, store.load_document(), task)["max_calls"] == 1
    if state != "reserved":
        spend(project, store, task, outcome=state)
    installed = tmp_path / "updated-action-method-installation"
    shutil.copytree(method_resources.resolve_root(), installed)
    method = installed / "references/physical-units.md"
    method.write_bytes(method.read_bytes() + b"\nSynthetic method revision; no external tool ran.\n")
    monkeypatch.setattr(method_resources, "resolve_root", lambda: installed)
    before = store.load_document()
    if state == "unknown":
        with pytest.raises(tasks.MethodBasisChanged):
            tasks.reissue_changed_method_tasks(store)
        assert store.load_document() == before
        return
    tasks.reissue_changed_method_tasks(store)
    document = store.load_document()
    replacement = next(store.read_object_json(ref) for ref in reversed(document["tasks"])
        if store.read_object_json(ref).get("change_binding", {}).get("action_id") == task["change_binding"]["action_id"]
        and store.read_object_json(ref)["task_id"] != task["task_id"])
    action = changes.action_for_task(store, document, replacement)
    assert action["max_calls"] == (1 if state == "reserved" else 0)
    assert len(replacement["call_allowances"]) == (1 if state == "reserved" else 0)
    assert store.read_object_json(task["change_binding"]["change_ref"]) == original_change
    budget = eligibility.authorization_budget(store, document, authorization["authorization_ref"])
    assert (budget["ceiling"], budget["used"], budget["remaining"]) == (2, 1, 1)
    with pytest.raises(tasks.CallBlocked, match="change plan call upper bound"):
        tasks.allocate_call_allowances(store, task_id=replacement["task_id"], count=1)
    assert store.load_document() == document
