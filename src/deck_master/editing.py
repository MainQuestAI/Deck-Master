"""Versioned edit, review, export and history use cases shared by CLI and UI."""
from __future__ import annotations
from pathlib import Path
import copy
import json
import shutil
import uuid
from .content import check_page
from .models import bump_revision
from .store import Store, ConflictError, StoreError
from .tasks import _project_transaction


def _current_artifact_digests(store, doc):
    """Current dependency digests for review freshness (content/page/svg/pptx)."""
    artifacts = {}
    for entry in doc.get('pages') or []:
        page_id = entry['page_id']
        if entry.get('page'):
            artifacts[f'content:page:{page_id}'] = entry['page']['sha256']
        for slot, kind, identity in (('blueprint', 'blueprint', f'blueprint:{page_id}'),
                                     ('svg', 'artifact', f'svg:{page_id}'),
                                     ('svg_preview', 'artifact', f'svg_preview:{page_id}'),
                                     ('ppt_preview', 'artifact', f'ppt_preview:{page_id}')):
            ref = entry.get(slot)
            if ref:
                artifacts[identity] = store.read_object_json(ref)['file']['sha256']
    outputs = doc.get('outputs') or {}
    if outputs.get('pptx'):
        try:
            artifacts['artifact:pptx'] = store.read_object_json(outputs['pptx'])['file']['sha256']
        except Exception:
            pass  # unreadable injected refs simply cannot match any review dependency
    return artifacts


def review_status(store, doc):
    """Load-side verdict; the single interpretation lives in review.evaluate_current."""
    from . import review as review_mod
    reviews = [{**store.read_object_json(ref), 'ref': ref} for ref in doc.get('reviews') or []]
    document = {**doc, 'tasks': [store.read_object_json(ref) for ref in doc.get('tasks') or []]}
    summary = review_mod.evaluate_current(document, reviews, _current_artifact_digests(store, doc))
    return summary['status']



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
    if purpose not in ('working', 'delivery'):
        raise StoreError('purpose', 'must be working or delivery')
    doc=store.load_document()
    if not doc['outputs'].get('pptx'):raise StoreError('outputs/pptx','no current PPT; continue production')
    if purpose=='delivery' and review_status(store,doc)!='pass':raise StoreError('reviews','current deck review incomplete or failed')
    destination=Path(output_dir)
    destination.mkdir(parents=True,exist_ok=False)
    try:
        for role,ref in doc['outputs'].items():
            if ref and (purpose == 'working' or role == 'pptx'):
                obj=store.read_object_json(ref);suffix=Path(obj['file']['path']).suffix
                (destination/('deck'+suffix if role=='pptx' else role+suffix)).write_bytes(store.read_object_bytes(obj['file']))
        for index,entry in enumerate(doc['pages'],1):
            directory=destination/f'{index:02d}-{entry["page_id"]}';directory.mkdir()
            if purpose == 'working':
                (directory/'page.json').write_bytes(store.read_object_bytes(entry['page']))
            for slot in ('blueprint','svg','svg_preview','ppt_preview'):
                if entry[slot]:
                    obj=store.read_object_json(entry[slot]);(directory/(slot+Path(obj['file']['path']).suffix)).write_bytes(store.read_object_bytes(obj['file']))
        if purpose == 'working':
            # Only immutable project data and the pinned pointer travel; no service PID, lock or staging.
            portable=destination/'project'/'.deckmaster'
            portable.mkdir(parents=True)
            for name in ('objects', 'revisions'):
                shutil.copytree(store.deck_root/name, portable/name)
            (portable/'current.json').write_bytes((store.deck_root/'current.json').read_bytes())
        (destination/'delivery.json').write_text(json.dumps({'project_id':doc['project_id'],'revision_id':doc['revision_id'],'purpose':purpose,'review_status':review_status(store,doc),'editability':'editable_shapes_and_text','desktop_editing':'not_evaluated'},ensure_ascii=False,indent=2))
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
