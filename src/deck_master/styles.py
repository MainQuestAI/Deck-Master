"""Versioned style suggestions and bounded trials over the existing change ledger."""
from __future__ import annotations

import copy
import json
import re
import uuid

from . import changes, operations
from .local_state import project_path
from .models import bump_revision, require_writer, sha256_bytes, validate_schema
from .snapshots import load_snapshot
from .store import Store

DEFAULT_DIMENSIONS = {'palette': '借用参考页配色', 'typography': '借用参考页文字层级'}
DIMENSIONS = {'palette': '配色', 'typography': '文字层级', 'density': '密度', 'lines': '线条', 'composition': '构图'}


class StyleConflict(operations.OperationError):
    def __init__(self, field, message, items):
        super().__init__('style_conflict', field, message, exit_code=5)
        self.items = items

    def payload(self):
        result = super().payload(); result['error']['items'] = self.items
        result['error']['docs_ref'] = 'docs/agent-recovery-playbook.md#style-calibration'
        return result


def fail(field, message):
    raise operations.OperationError('style_invalid', field, message)


def _owned(store, document, recipe_id=None, ref=None):
    for current in document.get('style_recipes', []):
        if ref is not None and current != ref:
            continue
        recipe = store.read_object_json(current); validate_schema('style_recipe', recipe)
        if recipe['project_id'] != document['project_id']:
            fail('recipe', 'recipe belongs to another project')
        if recipe_id == recipe['recipe_id'] or ref == current:
            return recipe, current
    fail('recipe', 'recipe is not in the selected committed project version')


def _sources(store, reference):
    from .workbench import page_lineage
    lineage = page_lineage(store.project_root, reference['page_id'], revision=reference['revision_id'])
    return {'reference': copy.deepcopy(reference), 'submitted': lineage['prompts']['submitted'],
            'prepared': lineage['prompts']['prepared'],
            'requests': [{key: record[key] for key in ('ref', 'request_id', 'input')}
                         for record in lineage['generation']['requests']],
            'unstructured_text_policy': 'Keep original text; exact selected excerpts or explicitly confirmed Host suggestions only.'}


def _proposal(store, document, value):
    validate_schema('style_input', value)
    if document.get('compatibility', {}).get('project_format') != 'workbench.v3':
        fail('project', 'style calibration requires a workbench.v3 project')
    if value['project_id'] != document['project_id']:
        fail('project_id', 'input belongs to another project')
    if value['base_revision'] != document['revision_id']:
        raise StyleConflict('base_revision', 'read current state and propose again', [])
    if not value['instruction'].strip():
        fail('instruction', 'provide a short concrete style requirement')
    reference = value['reference']
    if reference['role'] != 'reference':
        fail('reference/role', 'style reference must be an independent reference image')
    changes._reference_files(store, document, [reference])
    if reference['page_id'] in value['target_page_ids']:
        fail('target_page_ids', 'the reference page cannot be a target')
    dimensions = copy.deepcopy(value.get('dimensions', DEFAULT_DIMENSIONS))
    if not dimensions or any(not v.strip() for v in dimensions.values()):
        fail('dimensions', 'select at least one concrete visual dimension')
    unknown = sorted(set(dimensions) - set(DIMENSIONS))
    if unknown:
        fail('dimensions', 'unknown style dimensions: ' + ', '.join(unknown))
    # B06-AC01：未选维度成为显式保持项（沿用目标页），随 proposal/recipe 可追溯。
    preserve_dimensions = {key: DIMENSIONS[key] for key in DIMENSIONS if key not in dimensions}
    targets, conflicts = [], []
    entries = {e['page_id']: e for e in document['pages']}
    resolutions = value.get('resolutions', {})
    for pid in value['target_page_ids']:
        entry = entries.get(pid)
        if not entry:
            fail('target_page_ids', 'target page is absent from this project')
        page = store.read_object_json(entry['page'])
        targets.append({'page_id': pid, 'page_ref': entry['page'], 'blueprint_ref': entry.get('blueprint'),
                        'content': copy.deepcopy(page['customer_visible'])})
        # This is a narrow, disclosed lexical conflict check, not semantic NLP.
        target_text = json.dumps(page.get('visual_spec', {}), ensure_ascii=False).lower()
        requested = (value['instruction'] + '\n' + '\n'.join(dimensions.values()) + '\n' + value.get('host_suggestion', '')).lower()
        minimal = lambda s: any(word in s for word in ('极简', 'minimal', '低密度'))
        dense = lambda s: any(word in s for word in ('高密度', 'high density', 'high-density', 'dense'))
        if (minimal(requested) and dense(target_text)) or (dense(requested) and minimal(target_text)) or (minimal(requested) and dense(requested)):
            cid = pid + ':density'
            conflicts.append({'conflict_id': cid, 'page_id': pid, 'dimension': 'density',
                              'cause': 'minimal_vs_dense', 'target_constraints': target_text,
                              'requested': requested, 'resolution': resolutions.get(cid)})
    if set(resolutions) - {c['conflict_id'] for c in conflicts}:
        fail('resolutions', 'resolution must identify a displayed conflict')
    selected = value.get('prompt_selection')
    if selected:
        from .text_ranges import validate
        validate(store.project_root, page_id=reference['page_id'], layer=selected['layer'],
                 revision_id=reference['revision_id'], selection=selected['selection'])
    previous = _owned(store, document, recipe_id=value['parent_recipe_id'])[0] if value.get('parent_recipe_id') else None
    before = previous['input'] if previous else {}
    diff = [{'field': key, 'before': before.get(key), 'after': value.get(key)} for key in
            ('reference', 'target_page_ids', 'instruction', 'dimensions', 'prompt_selection', 'host_suggestion', 'resolutions')
            if before.get(key) != value.get(key)]
    # preserve_dimensions 是投影值（input 上不存在）：与父版本的投影比较，
    # 未选维度集合变化才产生条目——否则 diff 对它永远沉默。
    prev_preserve = {key: DIMENSIONS[key] for key in DIMENSIONS
                     if key not in (previous.get('dimensions') if previous else {})}
    if prev_preserve != preserve_dimensions:
        diff.append({'field': 'preserve_dimensions', 'before': prev_preserve, 'after': preserve_dimensions})
    return {'schema_version': 'style_proposal.v1', 'project_id': document['project_id'],
            'base_revision': document['revision_id'], 'input': copy.deepcopy(value), 'targets': targets,
            'reference_sources': _sources(store, reference), 'dimensions': dimensions,
            'preserve_dimensions': preserve_dimensions, 'conflicts': conflicts,
            'diff': diff, 'preserve_target_content': True,
            'suggestion_state': 'unconfirmed' if value.get('host_suggestion') else 'none'}


@operations.public
def propose(project, *, input):
    store = Store(project_path(project)); document = load_snapshot(store)
    proposal = _proposal(store, document, input); validate_schema('style_proposal', proposal)
    ref = store.put_json_object(proposal)
    return {'status': 'suggestion', 'proposal_id': 'style-proposal-' + ref['sha256'],
            'proposal_ref': ref, 'proposal': proposal, 'model_calls': 0}


def _read_proposal(store, proposal_id):
    if not isinstance(proposal_id, str) or not re.fullmatch(r'style-proposal-[a-f0-9]{64}', proposal_id):
        fail('proposal_id', 'use the immutable proposal ID')
    digest = proposal_id.removeprefix('style-proposal-')
    ref = {'path': f'.deckmaster/objects/{digest[:2]}/{digest}.json', 'sha256': digest}
    value = store.read_object_json(ref); validate_schema('style_proposal', value)
    return value, ref


@operations.public
def confirm(project, *, proposal_id, base_revision, operation_id):
    operations.validate_id(operation_id, new=True); store = Store(project_path(project))
    proposal, proposal_ref = _read_proposal(store, proposal_id)
    with store._locked():
        document = store.load_document()
        digest = operations.request_digest(document, 'styles.confirm', base_revision, {'proposal_ref': proposal_ref})
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if document['revision_id'] != base_revision or proposal['base_revision'] != base_revision:
            raise StyleConflict('base_revision', 'project changed; review a new suggestion', [])
        rederived = _proposal(store, document, proposal['input'])
        # 兼容旧核心产出的 proposal（无 preserve_dimensions 键）：该键按重推导
        # 值补齐后整体比较，其余字段必须逐字节一致。
        normalized = dict(proposal)
        normalized.setdefault('preserve_dimensions', rederived['preserve_dimensions'])
        if rederived != normalized:
            fail('proposal', 'suggestion changed; review the original recorded sources')
        unresolved = [c for c in proposal['conflicts'] if c['resolution'] is None]
        if unresolved:
            raise StyleConflict('conflicts', 'explicitly resolve each displayed constraint conflict', unresolved)
        parent, parent_ref = _owned(store, document, recipe_id=proposal['input']['parent_recipe_id']) if proposal['input'].get('parent_recipe_id') else (None, None)
        recipe = {**copy.deepcopy(proposal), 'schema_version': 'style_recipe.v1',
                  'recipe_id': 'recipe-' + uuid.uuid4().hex, 'version': parent['version'] + 1 if parent else 1,
                  'parent_ref': parent_ref, 'proposal_ref': proposal_ref,
                  'suggestion_state': 'confirmed' if proposal['input'].get('host_suggestion') else 'none'}
        validate_schema('style_recipe', recipe); ref = store.put_json_object(recipe)
        updated = bump_revision(copy.deepcopy(document), {'operation_id': operation_id, 'kind': 'task_update',
                                      'description': 'Confirmed immutable style recipe; no dispatch', 'read_set': []})
        require_writer(updated, 'style-recipes.v1'); updated['style_recipes'] = [*document.get('style_recipes', []), ref]
        result = {'status': 'confirmed', 'revision_id': updated['revision_id'], 'recipe_id': recipe['recipe_id'],
                  'recipe_ref': ref, 'model_calls': 0}
        return operations.commit_locked(store, document=updated, base_revision=base_revision, operation_id=operation_id,
                                        kind='styles.confirm', digest=digest, result=result)


@operations.public
def listing(project, *, revision=None):
    store = Store(project_path(project)); doc = load_snapshot(store, revision)
    return {'project_id': doc['project_id'], 'revision_id': doc['revision_id'],
            'recipes': [{'ref': ref, 'recipe': _owned(store, doc, ref=ref)[0]} for ref in doc.get('style_recipes', [])]}


@operations.public
def show(project, *, recipe_id, revision=None):
    store = Store(project_path(project)); doc = load_snapshot(store, revision); recipe, ref = _owned(store, doc, recipe_id)
    return {'project_id': doc['project_id'], 'revision_id': doc['revision_id'], 'recipe': recipe, 'ref': ref}


def instruction(recipe, page_id):
    value = recipe['input']; dimensions = recipe['dimensions']
    lines = ['跨页风格试作。只借用明确选定的视觉维度，不复制参考页的标题、事实、数字、论点或其它正文。',
             '目标页结构化正文必须完整保留；未选维度沿用目标页。构图仅在单独选择 composition 时借用。',
             '用户简短要求：' + value['instruction'], '明确借用维度：' + json.dumps(dimensions, ensure_ascii=False)]
    if recipe.get('preserve_dimensions'):
        lines.append('明确保持维度（沿用目标页，不向参考看齐）：' + json.dumps(recipe['preserve_dimensions'], ensure_ascii=False))
    if value.get('prompt_selection'):
        lines.append('用户明确选择的原文片段（仅作风格参考，不作为目标正文）：' + value['prompt_selection']['selection']['excerpt'])
    if value.get('host_suggestion'):
        lines.append('用户已确认的 Host 建议（不是历史实际提示词）：' + value['host_suggestion'])
    for conflict in recipe['conflicts']:
        if conflict['page_id'] == page_id:
            lines.append('约束取舍：' + ('保留目标页密度约束，忽略与之冲突的参考密度要求。' if conflict['resolution'] == 'keep_target'
                                      else '本次明确允许所选参考密度替代目标密度约束，目标正文仍须完整保留。'))
    return '\n'.join(lines)


def validate_change(store, document, value):
    recipe, ref = _owned(store, document, ref=value['style_recipe_ref'])
    ids = [t['page_id'] for t in value['targets']]
    anchors = {t['page_id']: t for t in recipe['targets']}
    if value.get('mode') != 'trial' or any(t['layer'] != 'original_image' for t in value['targets']):
        fail('mode', 'style plans only produce original-image trial candidates')
    if value.get('references') != [recipe['input']['reference']] or value['instruction'] != instruction(recipe, '*'):
        fail('style_recipe_ref', 'plan must preserve the exact recipe requirement and reference')
    adopted = value.get('style_adopted_candidate_id')
    if not adopted and len(ids) != 1:
        fail('targets', 'first try exactly one page; expand only after explicit adoption')
    if adopted:
        from .candidates import show as candidate_show
        candidate = candidate_show(store.project_root, candidate_id=adopted)
        record = candidate['candidate']
        task = next((store.read_object_json(r) for r in document['tasks'] if store.read_object_json(r)['task_id'] == record['task_id']), None)
        current = next((e for e in document['pages'] if e['page_id'] == record['page_id']), None)
        if (not candidate['adopted_revisions'] or candidate['generation_basis']['status'] != 'current' or record['stage'] != 'blueprint' or not current
                or current.get('blueprint') != record['result_ref'] or record['page_id'] in ids
                or not task or task.get('stage_request', {}).get('style_recipe_ref') != ref):
            fail('style_adopted_candidate_id', 'expand from a currently adopted original-image candidate of this exact recipe')
    conflicts = []
    for pid in ids:
        anchor = anchors.get(pid); entry = next((e for e in document['pages'] if e['page_id'] == pid), None)
        if anchor is None:
            fail('targets', 'target was not explicitly included in this recipe')
        if not entry or entry['page'] != anchor['page_ref'] or entry.get('blueprint') != anchor['blueprint_ref']:
            conflicts.append({'page_id': pid, 'cause': 'target_basis_changed', 'expected': anchor,
                              'current': {'page_ref': entry['page'], 'blueprint_ref': entry.get('blueprint')} if entry else None})
    if conflicts:
        raise StyleConflict('targets', 'selected target bases changed; unaffected targets remain readable', conflicts)
    return recipe


@operations.public
def plan(project, *, input):
    if not isinstance(input, dict) or set(input) - {'recipe_id', 'page_ids', 'max_calls', 'adopted_candidate_id'}:
        fail('input', 'use recipe_id, page_ids, max_calls and optional adopted_candidate_id')
    ids = input.get('page_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(pid, str) for pid in ids) or len(ids) != len(set(ids)):
        fail('page_ids', 'select unique explicit target pages')
    store = Store(project_path(project)); doc = load_snapshot(store); recipe, ref = _owned(store, doc, input.get('recipe_id'))
    entries = {e['page_id']: e for e in doc['pages']}
    if any(pid not in entries for pid in ids):
        raise StyleConflict('page_ids', 'selected pages are no longer in the project', [{'page_id': p, 'cause': 'page_absent'} for p in ids if p not in entries])
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
             'intent': 'style_calibration', 'instruction': instruction(recipe, '*'), 'annotation_refs': [],
             'max_calls': input.get('max_calls'), 'mode': 'trial', 'references': [recipe['input']['reference']],
             'style_recipe_ref': ref, 'targets': [{'page_id': pid, 'page_ref': entries[pid]['page'],
                    'layer': 'original_image', 'stage': 'blueprint', 'artifact_ref': entries[pid].get('blueprint')} for pid in ids]}
    if input.get('adopted_candidate_id'):
        value['style_adopted_candidate_id'] = input['adopted_candidate_id']
    return changes.plan(project, input=value)


def apply_request(store, document, value, request, page_id):
    recipe = validate_change(store, document, value)
    request['prompt'] = instruction(recipe, page_id) + '\n\n' + request['prompt']
    request['prompt_sha256'] = sha256_bytes(request['prompt'].encode('utf-8'))
