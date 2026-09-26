"""Versioned edit, review, export and history use cases shared by CLI and UI."""
from __future__ import annotations
from pathlib import Path
import copy
import io
import json
import shutil
import uuid
import zipfile
from .content import check_page
from .models import bump_revision, canonical_json_bytes, compute_input_digest, sha256_bytes
from .store import Store, ConflictError, StoreError
from .tasks import _project_transaction


def _current_artifact_digests(store, doc, extra_subjects=()):
    """Current dependency digests for review freshness (content/page/style/svg/pptx)."""
    from .models import canonical_json_bytes
    from .production import resolve_design
    design = doc.get('design_context') or {}
    artifacts = {}
    subject_info = {}
    current_refs = {}
    for entry in doc.get('pages') or []:
        for role in ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview'):
            ref = entry.get(role)
            if ref:
                current_refs[(ref['path'], ref['sha256'])] = (entry['page_id'], role)
    pptx_ref = (doc.get('outputs') or {}).get('pptx')
    if pptx_ref:
        current_refs[(pptx_ref['path'], pptx_ref['sha256'])] = (None, 'pptx')
    subject_refs = list(extra_subjects)
    historical_reviews = []
    for review_ref in doc.get('reviews') or []:
        try:
            prior_review = store.read_object_json(review_ref)
            historical_reviews.append(prior_review)
            subject_refs.extend(prior_review.get('subjects') or [])
        except (KeyError, ValueError, StoreError):
            continue
    subject_refs += [ref for entry in doc.get('pages') or []
                     for role in ('page', 'blueprint', 'svg', 'svg_preview', 'ppt_preview')
                     if (ref := entry.get(role))]
    if pptx_ref:
        subject_refs.append(pptx_ref)
    for ref in subject_refs:
        if not isinstance(ref, dict) or 'path' not in ref or 'sha256' not in ref:
            continue
        key = (ref['path'], ref['sha256'])
        if key in subject_info:
            continue
        try:
            obj = store.read_object_json(ref)
            if obj.get('schema_version') == 'deck_artifact.v1':
                role, page_id = obj.get('role'), obj.get('page_id')
                content_sha = obj['file']['sha256']
            elif obj.get('schema_version') == 'deck_page_package.v2':
                role, page_id, content_sha = 'page', obj.get('page_id'), ref['sha256']
            else:
                continue
            info = {'role': role, 'page_id': page_id,
                    'file_sha': content_sha, 'current': key in current_refs}
            if role == 'pptx':
                slide_pages = [dep['identity'] for dep in obj.get('dependencies') or []
                               if dep.get('kind') == 'svg' and dep.get('identity')]
                if slide_pages:
                    try:
                        with zipfile.ZipFile(io.BytesIO(store.read_object_bytes(obj['file']))) as deck:
                            info['slides'] = {
                                slide_page: sha256_bytes(deck.read(f'ppt/slides/slide{index}.xml'))
                                for index, slide_page in enumerate(slide_pages, 1)}
                    except (KeyError, StoreError, zipfile.BadZipFile):
                        pass
            subject_info[key] = info
        except (KeyError, ValueError, StoreError, zipfile.BadZipFile):
            continue
    artifacts['_subjects'] = subject_info
    current_asset_ids = {asset.get('asset_id') for asset in design.get('assets') or []}
    missing_asset_deps = {(dep.get('identity'), dep.get('sha256'))
                          for prior_review in historical_reviews
                          for dep in prior_review.get('dependencies') or []
                          if dep.get('kind') == 'asset' and dep.get('identity') not in current_asset_ids}
    retired_assets = set()
    revision = doc.get('parent_revision_id')
    visited = set()
    while revision and revision not in visited and missing_asset_deps:
        visited.add(revision)
        try:
            historic = store.load_document(revision)
        except StoreError:
            break
        for asset in (historic.get('design_context') or {}).get('assets') or []:
            matching = {(aid, sha) for aid, sha in missing_asset_deps if aid == asset.get('asset_id')}
            if not matching:
                continue
            try:
                resource = store.read_object_json(asset['artifact'])
                store.read_object_bytes(resource['file'])
                verified = (asset['asset_id'], resource['file']['sha256'])
                if verified in matching:
                    retired_assets.add(verified)
                    missing_asset_deps.discard(verified)
            except (KeyError, StoreError):
                continue
        revision = historic.get('parent_revision_id')
    artifacts['_retired_assets'] = retired_assets
    for asset in design.get('assets') or []:
        ref = asset.get('artifact')
        if ref:
            try:
                resource = store.read_object_json(ref)
                store.read_object_bytes(resource['file'])
                artifacts[f"asset:{asset['asset_id']}"] = resource['file']['sha256']
            except (KeyError, StoreError) as exc:
                raise StoreError(f"asset:{asset.get('asset_id')}",
                                 'stored asset reference is unreadable; restore or replace it') from exc
    for entry in doc.get('pages') or []:
        page_id = entry['page_id']
        page = store.read_object_json(entry['page']) if entry.get('page') else {}
        if entry.get('page'):
            artifacts[f'content:page:{page_id}'] = entry['page']['sha256']
        if page:
            from .production import style_font_fingerprint
            _, style = resolve_design(page, design, design.get('assets') or [])
            assets_by_id = {a['asset_id']: a for a in design.get('assets') or []}
            font_fp = style_font_fingerprint(
                design, style,
                lambda aid: (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
            artifacts[f'style:{page_id}'] = sha256_bytes(
                canonical_json_bytes({'style': style, 'fonts': font_fp}))
        for slot, kind, identity in (('blueprint', 'blueprint', f'blueprint:{page_id}'),
                                     ('svg', 'artifact', f'svg:{page_id}'),
                                     ('svg_preview', 'artifact', f'svg_preview:{page_id}'),
                                     ('ppt_preview', 'artifact', f'ppt_preview:{page_id}')):
            ref = entry.get(slot)
            if ref:
                dependency_key = f'{kind}:{identity}' if kind == 'artifact' else identity
                artifacts[dependency_key] = store.read_object_json(ref)['file']['sha256']
                # object-ref sha too, so closing-review subjects (which cite
                # the artifact object) can be freshness/currentness-checked
                artifacts[f'{dependency_key}:ref'] = ref['sha256']
    outputs = doc.get('outputs') or {}
    if outputs.get('pptx'):
        try:
            artifacts['artifact:pptx'] = store.read_object_json(outputs['pptx'])['file']['sha256']
            artifacts['artifact:pptx:ref'] = outputs['pptx']['sha256']
        except Exception:
            pass  # unreadable injected refs simply cannot match any review dependency
    # P1-07: resolvable dependency digests beyond page/style/artifact objects.
    for source in doc.get('sources') or []:
        extract = source.get('extract')
        if extract:
            artifacts[f"source:{source.get('source_id')}"] = extract['sha256']
    artifacts['policy:document'] = sha256_bytes(canonical_json_bytes(doc.get('policy') or {}))
    # Legacy reviews have no input dependency. Their immutable adoption history
    # identifies which observations predate the latest semantic input change.
    # Retain the Review objects; only content/privacy need a new observation.
    artifacts['_input_stale_reviews'] = set()
    if doc.get('content_basis'):
        digest = compute_input_digest(doc)
        revision = doc.get('parent_revision_id')
        visited = set()
        while revision and revision not in visited:
            visited.add(revision)
            prior = store.load_document(revision)
            if compute_input_digest(prior) != digest:
                artifacts['_input_stale_reviews'] = {
                    (ref['path'], ref['sha256']) for ref in prior.get('reviews') or []}
                break
            revision = prior.get('parent_revision_id')
    return artifacts


def _output_facts(store, doc):
    """Hard output facts (P1-01): render report state and produced-artifact
    completeness, read from the current objects — reviews never override them."""
    import json as _json
    facts = {'render_report_missing': False, 'completeness': []}
    outputs = doc.get('outputs') or {}
    if not outputs.get('pptx'):
        return facts
    report_ref = outputs.get('render_report')
    if not report_ref:
        facts['render_report_missing'] = True
    else:
        try:
            report = _json.loads(store.read_object_bytes(store.read_object_json(report_ref)['file']))
            facts['render_report_status'] = report.get('status')
            facts['render_report_findings'] = report.get('findings') or []
        except Exception:
            facts['render_report_missing'] = True
    for entry in doc.get('pages') or []:
        if not entry.get('svg'):
            facts['completeness'].append({'page_id': entry['page_id'], 'code': 'missing_svg'})
        elif not entry.get('ppt_preview'):
            facts['completeness'].append({'page_id': entry['page_id'], 'code': 'missing_preview'})
    return facts


def check_summary(store, doc):
    """The full CheckSummary behind review_status (one interpretation, AC-R03)."""
    from . import review as review_mod
    reviews = [{**store.read_object_json(ref), 'ref': ref} for ref in doc.get('reviews') or []]
    document = {**doc, 'tasks': [store.read_object_json(ref) for ref in doc.get('tasks') or []],
                '_output_facts': _output_facts(store, doc)}
    return review_mod.evaluate_current(document, reviews, _current_artifact_digests(store, doc))


def review_status(store, doc):
    """Load-side verdict; the single interpretation lives in review.evaluate_current."""
    return check_summary(store, doc)['status']


def page_visual_summary(store, doc, entry):
    from .review import evaluate_page_visual
    from .production import resolve_design
    page = store.read_object_json(entry['page'])
    effective, _ = resolve_design(page, doc['design_context'],
                                  doc['design_context'].get('assets') or [])
    reviews = [{**store.read_object_json(ref), 'ref': ref} for ref in doc.get('reviews') or []]
    return evaluate_page_visual(entry, reviews, _current_artifact_digests(store, doc),
                                effective.get('allowed_asset_ids') or [])


def _professional_evidence(store, doc):
    """Human/professional review dimensions are reported honestly: a kind only
    shows its recorded status when a current review exists, else not_evaluated
    (never a fabricated human pass)."""
    current = (doc.get('outputs') or {}).get('pptx')
    evidence = {'professional_use': 'not_evaluated', 'desktop_editing': 'not_evaluated'}
    for ref in doc.get('reviews') or []:
        review = store.read_object_json(ref)
        kind = review.get('kind')
        if kind in evidence and current and current in (review.get('subjects') or []):
            evidence[kind] = review.get('status') or 'not_evaluated'
    return evidence



def operation_revision(store, current, operation_id):
    """Walk committed ancestry only; never replay an uncommitted orphan revision."""
    node=current
    while node:
        if node['change']['operation_id']==operation_id:
            return node
        parent=node['parent_revision_id']
        node=store.load_document(parent) if parent else None
    return None


def edit_page(project_dir, *, page, base_revision, page_hash, operation_id):
    return _edit(Store(project_dir),page=check_page(page),base_revision=base_revision,page_hash=page_hash,operation_id=operation_id)

@_project_transaction
def _edit(store, *, page, base_revision, page_hash, operation_id):
    doc=store.load_document();entry=next((e for e in doc['pages'] if e['page_id']==page['page_id']),None)
    if entry is None:raise StoreError('page_id','not found')
    prior=operation_revision(store,doc,operation_id)
    if prior:
        previous=next((e for e in prior['pages'] if e['page_id']==page['page_id']),None)
        if prior['change']['kind']=='content_update' and previous and store.read_object_json(previous['page'])==page:
            return {'status':'already_applied','revision_id':doc['revision_id'],'applied_revision_id':prior['revision_id']}
        raise ConflictError('operation_id','different payload already applied')
    if entry['page']['sha256']!=page_hash:raise ConflictError('page_hash','page changed; reload and rebase')
    # Disjoint page edits can rebase, but design changes cannot.
    base=store.load_document(base_revision)
    if base['design_context']!=doc['design_context']:raise ConflictError('design_context','design moved since edit began')
    updated=bump_revision(doc,{'operation_id':operation_id,'kind':'content_update','description':'edit '+page['page_id'],'read_set':[]})
    for e in updated['pages']:
        if e['page_id']==page['page_id']:
            e['page']=store.put_json_object(page)
            e['svg']=e['svg_preview']=e['ppt_preview']=None
    updated['outputs']={key:None for key in doc['outputs']}
    for i,ref in enumerate(updated['tasks']):
        task=store.read_object_json(ref)
        if page['page_id'] in task['scope_pages'] and task['status'] in ('awaiting_host','running'):
            task['status']='superseded';updated['tasks'][i]=store.put_json_object(task)
    store._commit_locked(base_revision=doc['revision_id'],document=updated,operation_id=operation_id,blobs=[])
    return {'status':'edited','revision_id':updated['revision_id'],'next_action':'continue','preserved_blueprint':entry['blueprint']}


def export_project(project_dir, *, output_dir, purpose='working'):
    store=Store(project_dir)
    with store._locked():
        return _export_locked(store, output_dir=output_dir, purpose=purpose)

def _export_locked(store, *, output_dir, purpose):
    if purpose == 'working':
        purpose = 'review'  # accepted alias (2026-09-16 evidence); semantics = review
    if purpose not in ('review', 'delivery'):
        raise StoreError('purpose', 'must be review or delivery')
    doc=store.load_document()
    from .models import input_alignment as _input_alignment
    from .errors import InputReconciliationPending
    alignment=_input_alignment(doc)
    if alignment=='needs_reconciliation' and purpose=='delivery':
        raise InputReconciliationPending('input_alignment',
            'inputs changed after this content was completed; run inputs update and finish the '
            'dispatched input_revision task before delivery (delivery is refused while '
            'input_alignment is needs_reconciliation)')
    if not doc['outputs'].get('pptx'):raise StoreError('outputs/pptx','no current PPT; continue production')
    summary=check_summary(store,doc)
    status=summary['status']
    if purpose=='delivery' and status!='pass':
        failed=[key for key,value in summary['dimensions'].items() if value['open_must_fix'] or value['status']=='fail']
        raise StoreError('reviews',f'delivery requires every required check to pass; '
                         f'current review status is {status!r} '
                         f'(unresolved: {sorted(set(summary["missing_dimensions"]) | set(failed))})')
    if purpose=='delivery' and (doc.get('policy') or {}).get('professional_review_required_for_delivery'):
        current=doc['outputs'].get('pptx')
        satisfied=False
        for ref in doc.get('reviews') or []:
            review=store.read_object_json(ref)
            if not current or current not in (review.get('subjects') or []):
                continue
            if review.get('status')=='fail':
                continue
            if review.get('kind')=='professional_use' or \
                    (review.get('reviewer') or {}).get('type') in ('human_internal','human_external'):
                satisfied=True
                break
        if not satisfied:
            raise StoreError('policy/professional_review_required_for_delivery',
                             'delivery requires a non-failing professional_use or human review '
                             'recorded on the current output')
    destination=Path(output_dir)
    destination.mkdir(parents=True,exist_ok=False)
    try:
        for role,ref in doc['outputs'].items():
            if ref and (purpose == 'review' or role == 'pptx'):
                obj=store.read_object_json(ref);suffix=Path(obj['file']['path']).suffix
                (destination/('deck'+suffix if role=='pptx' else role+suffix)).write_bytes(store.read_object_bytes(obj['file']))
        for index,entry in enumerate(doc['pages'],1):
            directory=destination/f'{index:02d}-{entry["page_id"]}';directory.mkdir()
            if purpose == 'review':
                (directory/'page.json').write_bytes(store.read_object_bytes(entry['page']))
            for slot in ('blueprint','svg','svg_preview','ppt_preview'):
                if entry[slot]:
                    obj=store.read_object_json(entry[slot]);(directory/(slot+Path(obj['file']['path']).suffix)).write_bytes(store.read_object_bytes(obj['file']))
        if purpose == 'review':
            # Only immutable project data and the pinned pointer travel; no service PID, lock or staging.
            portable=destination/'project'/'.deckmaster'
            portable.mkdir(parents=True)
            for name in ('objects', 'revisions'):
                shutil.copytree(store.deck_root/name, portable/name)
            (portable/'current.json').write_bytes((store.deck_root/'current.json').read_bytes())
        failed_dimensions=sorted(key for key,value in summary['dimensions'].items()
                                 if value['open_must_fix'] or value['status']=='fail')
        pptx_ref=doc['outputs'].get('pptx')
        editability='unknown'
        if pptx_ref:
            editability=store.read_object_json(pptx_ref).get('editability') or 'unknown'
        facts=summary.get('output_facts') or {}
        report={'project_id':doc['project_id'],'revision_id':doc['revision_id'],'purpose':purpose,
                'review_status':status,
                'input_alignment':alignment,
                'unresolved':{'missing_dimensions':sorted(summary['missing_dimensions']),
                              'failed_dimensions':failed_dimensions,
                              'render_report_missing':bool(facts.get('render_report_missing')),
                              'render_report_findings':facts.get('render_report_findings') or [],
                              'completeness_gaps':facts.get('completeness') or [],
                              'not_evaluated_dimensions':dict(summary.get('dimension_reasons') or {})},
                'editability':editability,
                'professional_evidence':_professional_evidence(store,doc),
                'desktop_editing':'not_evaluated',
                'evidence_level':'engineering'}
        if alignment=='needs_reconciliation':
            report['notice']='待按新要求更新'
        (destination/'delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    except Exception:
        shutil.rmtree(destination);raise
    return {'status':'exported','revision_id':doc['revision_id'],'output_dir':str(destination)}


def history(project_dir):
    store=Store(project_dir);document=store.load_document();current=document['revision_id'];records=[]
    while document:
        records.append({'revision_id':document['revision_id'],'parent_revision_id':document['parent_revision_id'],'created_at':document['created_at'],'change':document['change'],'page_count':len(document['pages'])})
        parent=document['parent_revision_id']
        document=store.load_document(parent) if parent else None
    return {'current':current,'revisions':records}


def restore(project_dir, *, revision_id, base_revision, operation_id):
    return _restore(Store(project_dir),revision_id=revision_id,base_revision=base_revision,operation_id=operation_id)

@_project_transaction
def _restore(store, *, revision_id, base_revision, operation_id):
    current=store.load_document()
    prior=operation_revision(store,current,operation_id)
    if prior:
        if prior['change']['kind']=='restore' and prior['change']['description']=='restore '+revision_id:
            return {'status':'already_applied','revision_id':current['revision_id'],'applied_revision_id':prior['revision_id']}
        raise ConflictError('operation_id','different operation already applied')
    if current['revision_id']!=base_revision:raise ConflictError('revision','project changed')
    ancestor=current
    while ancestor and ancestor['revision_id']!=revision_id:
        parent=ancestor['parent_revision_id']
        ancestor=store.load_document(parent) if parent else None
    if ancestor is None:raise StoreError('revision_id','not a committed ancestor of current revision')
    past=ancestor
    updated=bump_revision(current,{'operation_id':operation_id,'kind':'restore','description':'restore '+revision_id,'read_set':[]})
    for key in ('pages','design_context','sources','outputs'):
        updated[key]=copy.deepcopy(past[key])
    # Call facts and policy are never rolled back by restoring old page content.
    for i,ref in enumerate(updated['tasks']):
        task=store.read_object_json(ref)
        if task['status'] in ('running','awaiting_host'):
            task['status']='superseded';updated['tasks'][i]=store.put_json_object(task)
    store._commit_locked(base_revision=base_revision,document=updated,operation_id=operation_id,blobs=[])
    return {'status':'restored','revision_id':updated['revision_id'],'restored_from':revision_id}
