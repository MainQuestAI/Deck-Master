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
    from .production import resolve_page_rendering_design
    design = doc.get('design_context') or {}
    artifacts = {}
    subject_info = {}
    current_refs = {}
    for role in ('narrative', 'content_plan'):
        ref = doc.get(role)
        if ref:
            current_refs[(ref['path'], ref['sha256'])] = (None, role)
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
    subject_refs += [ref for role in ('narrative', 'content_plan') if (ref := doc.get(role))]
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
            elif obj.get('schema_version') == 'narrative.v1':
                role, page_id, content_sha = 'narrative', None, ref['sha256']
            elif obj.get('schema_version') == 'content_plan.v2':
                role, page_id, content_sha = 'content_plan', None, ref['sha256']
            else:
                continue
            info = {'role': role, 'page_id': page_id,
                    'file_sha': content_sha, 'current': key in current_refs}
            if role == 'page':
                from .visual_dependencies import page_visual_digest
                digest_reader = getattr(store, 'page_visual_digest', None)
                info['visual_sha'] = digest_reader(ref) if digest_reader else page_visual_digest(obj)
            # Ephemeral interpretation of actual immutable manuscript objects.
            # A deck-level preproduction fix needs changed content, not only a
            # version/previous_ref or production-note hash change. No extra
            # state is written to the Store and legacy file hashes stay intact.
            if role == 'narrative':
                body = {k: obj.get(k) for k in ('communication_job',
                        'central_node_id', 'nodes', 'edges', 'issues', 'alternatives')}
                body['nodes'] = [{k: v for k, v in node.items() if k != 'source_links'}
                                 for node in obj.get('nodes') or []]
                body['issues'] = [{k: v for k, v in issue.items()
                                  if k not in ('resolution', 'resolution_ref')}
                                 for issue in obj.get('issues') or []]
            elif role == 'content_plan':
                plan_input = copy.deepcopy(obj.get('input') or {})
                for item in plan_input.get('page_roles') or []:
                    item.pop('source_links', None)
                for item in plan_input.get('issues') or []:
                    item.pop('resolution', None)
                    item.pop('resolution_ref', None)
                body = {'input': plan_input}
            elif role == 'page':
                visual = obj.get('visual_spec') or {}
                mapping = obj.get('content_mapping') or {}
                body = {'customer_visible': obj.get('customer_visible'),
                        'visual_semantics': {k: visual.get(k) for k in ('intent', 'nodes', 'edges')},
                        'visible_mapping': [{k: v for k, v in link.items() if k != 'source_links'}
                                            for link in mapping.get('visible_links') or []]}
            else:
                body = None
            if body is not None:
                if role in ('narrative', 'content_plan'):
                    outline_body = copy.deepcopy(body)
                    if role == 'narrative':
                        outline_body['nodes'] = obj.get('nodes') or []
                    else:
                        outline_body['input']['page_roles'] = (obj.get('input') or {}).get('page_roles') or []
                    info['outline_semantic_sha'] = sha256_bytes(canonical_json_bytes(outline_body))
                source_body = copy.deepcopy(body)
                if role in ('narrative', 'content_plan'):
                    source_body = outline_body
                elif role == 'page':
                    source_body['visible_mapping'] = mapping.get('visible_links') or []
                # Source associations, versions and locators are substantive for
                # source findings, but do not stand in for unrelated prose fixes.
                info['source_semantic_sha'] = sha256_bytes(canonical_json_bytes(source_body))
                source_speech_body = ({**source_body, 'speaker_notes': obj.get('speaker_notes'),
                                       'speech_segments': mapping.get('speech_segments')}
                                      if role == 'page' else source_body)
                info['source_speech_semantic_sha'] = sha256_bytes(canonical_json_bytes(source_speech_body))
                info['semantic_sha'] = sha256_bytes(canonical_json_bytes(body))
                speech_body = ({**body, 'speaker_notes': obj.get('speaker_notes'),
                                'speech_segments': (obj.get('content_mapping') or {}).get('speech_segments')}
                               if role == 'page' else body)
                info['speech_semantic_sha'] = sha256_bytes(canonical_json_bytes(speech_body))
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
    # Historical Page references stay historical. Only named visual consumers
    # may use an actual, schema-valid equivalent Page as their current basis.
    from .visual_dependencies import page_visual_equivalent
    visual_aliases = {}
    notes_aliases = {}
    for entry in doc.get('pages') or []:
        current = store.read_object_json(entry['page'])
        for key, info in subject_info.items():
            if info.get('role') != 'page' or info.get('page_id') != entry['page_id']:
                continue
            prior_ref = {'path': key[0], 'sha256': key[1]}
            if page_visual_equivalent(store, prior_ref, entry['page'], entry['page_id']):
                visual_aliases.setdefault(entry['page_id'], set()).add(key)
            prior = store.read_object_json(prior_ref)
            if notes_only_change(prior, current):
                notes_aliases.setdefault(f"content:page:{entry['page_id']}", set()).add(key[1])
    plan_ref = doc.get('content_plan')
    if plan_ref:
        current_plan = store.read_object_json(plan_ref)
        for key, info in subject_info.items():
            if info.get('role') != 'content_plan':
                continue
            prior_plan = store.read_object_json({'path': key[0], 'sha256': key[1]})
            fields = ('schema_version', 'project_id', 'plan_id', 'origin', 'mode',
                      'narrative_ref', 'imported_manuscript', 'input', 'basis')
            if any(prior_plan.get(field) != current_plan.get(field) for field in fields):
                continue
            links = prior_plan.get('page_links') or []
            if (len(links) == len(doc.get('pages') or []) and
                    [link.get('page_id') for link in links] == current_plan.get('input', {}).get('page_order') and
                    all((link.get('page_ref') or {}).get('sha256') in
                        notes_aliases.get(f"content:page:{link.get('page_id')}", set()) for link in links)):
                notes_aliases.setdefault('content:content_plan', set()).add(key[1])
    artifacts['_visual_page_aliases'] = visual_aliases
    artifacts['_preproduction_notes_aliases'] = notes_aliases
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
            notes = str(page.get('speaker_notes') or '').replace('\r\n', '\n').replace('\r', '\n')
            artifacts[f'content:page_notes:{page_id}'] = sha256_bytes(notes.encode('utf-8'))
        if page:
            from .production import style_font_fingerprint
            effective = resolve_page_rendering_design(store, doc, entry)
            style = effective['styles'][0]
            assets_by_id = {a['asset_id']: a for a in design.get('assets') or []}
            font_fp = style_font_fingerprint(
                effective, style,
                lambda aid: (assets_by_id.get(aid) or {}).get('artifact', {}).get('sha256'))
            artifacts[f'style:{page_id}'] = sha256_bytes(
                canonical_json_bytes({'style': style, 'fonts': font_fp,
                    **({'recipe_parameters': effective['recipe_parameters']}
                       if 'recipe_parameters' in effective else {})}))
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
    # Content collaboration v1.2 CONTRACTS §11.5/§11.6: a preproduction review
    # binds the current Narrative and ContentPlan pointers by object hash, using
    # the same dependency-id scheme as page/style/artifact slices.
    for identity, pointer in (('narrative', doc.get('narrative')),
                              ('content_plan', doc.get('content_plan'))):
        if isinstance(pointer, dict) and pointer.get('sha256'):
            artifacts[f'content:{identity}'] = pointer['sha256']
    artifacts['policy:document'] = sha256_bytes(canonical_json_bytes(doc.get('policy') or {}))
    # Legacy reviews have no input dependency. Their immutable adoption history
    # identifies which observations predate the latest semantic input change.
    # Retain the Review objects; only content/privacy need a new observation.
    artifacts['_input_stale_reviews'] = set()
    if doc.get('content_basis'):
        input_digest = getattr(store, 'input_digest', compute_input_digest)
        digest = input_digest(doc)
        revision = doc.get('parent_revision_id')
        visited = set()
        while revision and revision not in visited:
            visited.add(revision)
            prior = store.load_document(revision)
            if input_digest(prior) != digest:
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


class ReviewReadContext:
    """Dependency facts for one exact document interpretation, within one call.

    A value copy binds all fields, including policy/reviews/notes/output refs;
    reusing the context with another interpretation fails instead of going stale.
    """
    def __init__(self, store, document):
        self.store = store
        self.document = copy.deepcopy(document)
        self.artifacts = _current_artifact_digests(store, document)
        self.reviews = [{**store.read_object_json(ref), 'ref': ref}
                        for ref in document.get('reviews') or []]
        from .review import replacement_index
        self.replacements = replacement_index(self.reviews)

    def require(self, store, document):
        if self.store is not store or self.document != document:
            raise ValueError('review context belongs to a different snapshot interpretation')
        return self


def check_summary(store, doc, *, read_context=None):
    """The full CheckSummary behind review_status (one interpretation, AC-R03)."""
    from . import review as review_mod
    context = (read_context or ReviewReadContext(store, doc)).require(store, doc)
    reviews = context.reviews
    document = {**doc, 'tasks': [store.read_object_json(ref) for ref in doc.get('tasks') or []],
                '_output_facts': _output_facts(store, doc)}
    return review_mod.evaluate_current(document, reviews, context.artifacts, replacements=context.replacements, store=store)


def review_status(store, doc):
    """Load-side verdict; the single interpretation lives in review.evaluate_current."""
    return check_summary(store, doc)['status']


def page_visual_summary(store, doc, entry, *, read_context=None):
    from .review import evaluate_page_visual
    from .production import resolve_page_rendering_design
    effective = resolve_page_rendering_design(store, doc, entry)
    context = (read_context or ReviewReadContext(store, doc)).require(store, doc)
    return evaluate_page_visual(entry, context.reviews, context.artifacts,
                                effective.get('allowed_asset_ids') or [], replacements=context.replacements)


def _professional_evidence(store, doc):
    """Delegate to the single professional-evidence interpretation
    (delivery_eligibility); kept for existing importers."""
    from .delivery_eligibility import professional_policy
    return professional_policy(store, doc)['evidence']



def operation_revision(store, current, operation_id):
    """Walk committed ancestry only; never replay an uncommitted orphan revision."""
    node=current
    while node:
        if node['change']['operation_id']==operation_id:
            return node
        parent=node['parent_revision_id']
        node=store.load_document(parent) if parent else None
    return None


def _eligibility_guard(store, action, targets=None, context=None):
    """One call shape for every editing boundary (CONTRACTS §6.2 rows 3/6/7)."""
    from . import eligibility
    payload = dict(context or {})
    if targets is not None:
        payload["targets"] = targets
    return eligibility.guard(store, store.load_document(), action, context=payload)


def edit_page(project_dir, *, page, base_revision, page_hash, operation_id):
    return _edit(Store(project_dir),page=check_page(page),base_revision=base_revision,page_hash=page_hash,operation_id=operation_id)


def notes_only_change(before, after):
    """Only the actual notes and their codepoint mapping may differ."""
    def remaining(page):
        value = copy.deepcopy(page)
        value.pop('speaker_notes', None)
        if isinstance(value.get('content_mapping'), dict):
            value['content_mapping'].pop('speech_segments', None)
        return value
    return remaining(before) == remaining(after)


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
    before = store.read_object_json(entry['page'])
    notes_only = notes_only_change(before, page)
    _eligibility_guard(store, "page.edit", {
        "page_ids": [page['page_id']], "layers": ['speech'] if notes_only else ['page_copy']})
    updated=bump_revision(copy.deepcopy(doc),{'operation_id':operation_id,'kind':'content_update','description':'edit '+page['page_id'],'read_set':[]})
    if doc.get('collaboration') or notes_only or bool(page.get('speaker_notes')):
        from .models import require_writer
        require_writer(updated, 'rc3.v1')
    for e in updated['pages']:
        if e['page_id']==page['page_id']:
            e['page']=store.put_json_object(page)
            e['ppt_preview']=None
            if not notes_only:
                e['svg']=e['svg_preview']=None
    plan_ref = doc.get('content_plan')
    if plan_ref:
        plan = store.read_object_json(plan_ref)
        if (plan.get('schema_version') == 'content_plan.v2' and
                plan.get('mode') in ('bound', 'imported_mapping')):
            from .content_plan import attach, refresh_v2_plan_links
            attach(updated, refresh_v2_plan_links(
                store, doc, {}, plan, updated['pages'], previous_ref=plan_ref))
    updated['outputs']={key:None for key in doc['outputs']}
    from .tasks import task_inputs_current
    for i,ref in enumerate(updated['tasks']):
        task=store.read_object_json(ref)
        if (page['page_id'] in task['scope_pages'] and
                task['status'] in ('queued','awaiting_host','running') and
                (not notes_only or not task_inputs_current(store, updated, task))):
            task['status']='superseded';updated['tasks'][i]=store.put_json_object(task)
    store._commit_locked(base_revision=doc['revision_id'],document=updated,operation_id=operation_id,blobs=[])
    return {'status':'edited','revision_id':updated['revision_id'],'next_action':'continue','preserved_blueprint':entry['blueprint']}


def export_project(project_dir, *, output_dir, purpose='working', revision=None, export_id=None, notes_policy=None):
    """Export a frozen public copy or explicitly internal recovery package."""
    from .exports import create
    # exports.create owns the exact selected artifact/projection + current
    # control judgement. A preliminary current-only check would disagree for
    # historical files and for sanitized presenter-notes projections.
    return create(project_dir, output_dir=output_dir, purpose=purpose, revision=revision,
                  export_id=export_id, notes_policy=notes_policy)


def _history_row(document, parent):
    slots = {'page': 'content', 'blueprint': 'original_image', 'svg': 'svg',
             'svg_preview': 'svg_preview', 'ppt_preview': 'ppt'}
    before = {entry['page_id']: entry for entry in (parent or {}).get('pages', [])}
    after = {entry['page_id']: entry for entry in document['pages']}
    changed = []
    basis = bool(parent and any(document.get(key) != parent.get(key)
                               for key in ('task', 'sources', 'design_context')))
    for pid in dict.fromkeys([*after, *before]):
        old, new = before.get(pid, {}), after.get(pid, {})
        layers = [label for key, label in slots.items() if old.get(key) != new.get(key)]
        if pid not in before or pid not in after:
            layers.append('membership')
        if basis:
            layers.append('basis')
        if layers:
            changed.append({'page_id': pid, 'layers': layers})
    order_changed = list(before) != list(after)
    kind = document.get('change', {}).get('kind')
    actions = {'artifact_adoption':'采用候选', 'content_adoption':'采用正文候选', 'content_update':'修改正文', 'artifact_adopt':'采用制作结果',
               'candidate_adopt':'采用候选', 'restore':'恢复历史', 'design_update':'调整设计',
               'input_update':'更新任务与材料', 'task_update':'执行记录', 'initial':'创建项目'}
    action = actions.get(kind, '项目更新')
    if kind == 'task_update' and changed:
        action = '页面更新'
    return {'revision_id': document['revision_id'], 'parent_revision_id': document['parent_revision_id'],
            'created_at': document['created_at'], 'committed_at': document.get('committed_at'),
            'change': document['change'], 'page_count': len(document['pages']), 'action': action,
            'changed_pages': changed, 'order_changed': order_changed,
            'outputs_changed': bool(parent and parent.get('outputs') != document['outputs'])}


def history(project_dir, *, revision=None, page_id=None, layer=None, limit=None, cursor=None, related_only=True):
    """An anchored read projection; legacy calls still return the full ancestry."""
    from .snapshots import FixedSnapshotReader
    store = Store(project_dir)
    head = revision or store.current_revision_id()
    start = None
    if cursor:
        pieces = cursor.split(':')
        if len(pieces) != 2 or (revision and revision != pieces[0]):
            raise StoreError('cursor', 'cursor must preserve its original history head')
        head, start = pieces
    reader = FixedSnapshotReader(store, head_revision=head)
    document = reader.load(head)
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
        raise StoreError('limit', 'history page size must be 1–100')
    if start:
        if start not in reader.ancestry(head):
            raise StoreError('cursor', 'cursor is not in the fixed committed ancestry')
        document = reader.load(start)
    records = []
    next_cursor = None
    while document:
        parent_id = document['parent_revision_id']
        parent = reader.load(parent_id) if parent_id else None
        row = _history_row(document, parent)
        relevant = [item for item in row['changed_pages'] if (not page_id or item['page_id'] == page_id)
                    and (not layer or layer in item['layers'] or 'basis' in item['layers'])]
        legacy_full = limit is None and not page_id and not layer
        if legacy_full or not related_only or relevant or (not page_id and not layer and (row['outputs_changed'] or row['order_changed'])):
            records.append(row)
        if limit is not None and len(records) >= limit:
            next_cursor = head + ':' + parent_id if parent_id else None
            break
        document = parent
    # `current` keeps its historical meaning (project head); `head` is this
    # read's anchor. delivery-desk marks the anchor with its own field so the
    # identity chips no longer mislabel a historical revision as 当前版本.
    return {'current': store.current_revision_id(), 'head': head, 'revisions': records, 'pagination': {'limit': limit, 'next_cursor': next_cursor},
            'time_policy': 'committed_at only; historical absence remains unknown'}


def restore(project_dir, *, revision_id, base_revision, operation_id):
    return _restore(Store(project_dir),revision_id=revision_id,base_revision=base_revision,operation_id=operation_id)

@_project_transaction
def _restore(store, *, revision_id, base_revision, operation_id):
    # Restore recovers content/visual facts only; the current request,
    # decisions, withdrawals, pauses, budget and writer boundary stay as they
    # are (CONTRACTS §7.1). It is still a project write and consumes the gate.
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
    _eligibility_guard(store, 'restore', restore_targets(store, current, ancestor))
    updated=restore_document(store,current,ancestor,operation_id)
    store._commit_locked(base_revision=base_revision,document=updated,operation_id=operation_id,blobs=[])
    return {'status':'restored','revision_id':updated['revision_id'],'restored_from':revision_id}


def restore_targets(store, current, ancestor):
    """Actual changed content/visual targets of a restore under current control."""
    current_pages = {entry['page_id']: entry for entry in current['pages']}
    old_pages = {entry['page_id']: entry for entry in ancestor['pages']}
    targets = sorted(pid for pid in current_pages.keys() | old_pages.keys()
                     if current_pages.get(pid) != old_pages.get(pid))
    layers = []
    for pointer, layer in (('narrative', 'narrative'), ('content_plan', 'plan'), ('outputs', 'output')):
        if current.get(pointer) != ancestor.get(pointer):
            layers.append(layer)
    for pid in targets:
        before, after = current_pages.get(pid), old_pages.get(pid)
        if not before or not after or before['page'] != after['page']:
            layers.extend(['page_copy', 'speech'])
        if not before or not after or before.get('blueprint') != after.get('blueprint'):
            layers.append('blueprint')
        if not before or not after or before.get('svg') != after.get('svg'):
            layers.append('svg')
    return {'page_ids': targets, 'layers': sorted(set(layers)),
            'allow_page_membership_change': set(current_pages) != set(old_pages),
            'allow_page_order_change': [e['page_id'] for e in current['pages']] != [e['page_id'] for e in ancestor['pages']]}


def restore_document(store, current, past, operation_id):
    """Shared restoration transform; call facts, stop policy and task facts stay current."""
    updated=bump_revision(current,{'operation_id':operation_id,'kind':'restore','description':'restore '+past['revision_id'],'read_set':[]})
    for key in ('pages','design_context','sources','outputs'):
        updated[key]=copy.deepcopy(past[key])
    if past.get('content_plan'):
        updated['content_plan'] = copy.deepcopy(past['content_plan'])
    else:
        updated.pop('content_plan', None)
    # Narrative is content: it is restored with the content it governed, and
    # removed when the target snapshot predates it (MIGRATION §4).
    if past.get('narrative'):
        updated['narrative'] = copy.deepcopy(past['narrative'])
    else:
        updated.pop('narrative', None)
    # The collaboration control region is never rolled back: the current
    # request, decisions, authorizations, pause/revocation state, stop policy
    # and the raised minimum writer stay exactly as they are (MIGRATION §4).
    updated['collaboration'] = current.get('collaboration')
    if not past.get('pages'):
        updated.pop('content_basis', None)
    elif past.get('content_basis'):
        updated['content_basis'] = copy.deepcopy(past['content_basis'])
    else:
        updated['content_basis'] = {'input_digest': compute_input_digest(past),
                                    'input_revision_id': None, 'resolved_by_task_id': None}
    # Call facts and policy are never rolled back by restoring old page content.
    for i,ref in enumerate(updated['tasks']):
        task=store.read_object_json(ref)
        if task['status'] in ('running','awaiting_host','blocked'):
            task['status']='superseded';updated['tasks'][i]=store.put_json_object(task)
    return updated
