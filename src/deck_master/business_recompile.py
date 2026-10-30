"""D05 task-strategy reconciliation on fixed inputs and existing compose writes."""
from __future__ import annotations

from . import models
from .store import StoreError

CAPABILITY = 'business-recompile.v1'
VERSION = 'content_impact.v2'
STRATEGY_FACTS = {'brief', 'audience', 'scenario', 'existing_decisions'}
STATES = {'affected', 'needs_reassessment', 'reusable_after_review', 'unverified'}


def enabled(store, document):
    return models.writer_at_least(document, 'business-framing.v1')


def _read(store, ref):
    try:
        return store.read_object_json(ref) if ref else None
    except (OSError, ValueError, StoreError):
        return None


def project_impact(store, before, after, impact, unreadable):
    """A conservative projection; no source miss becomes a reuse decision."""
    value = {key: item for key, item in impact.items() if key != 'unaffected_pages'}
    value['schema_version'] = VERSION
    value['basis'] = {'before_input_digest': models.compute_input_digest(before),
        'after_input_digest': models.compute_input_digest(after),
        'narrative_ref': after.get('narrative'), 'plan_ref': after.get('content_plan'),
        'task_before': before.get('task') or {}, 'task_after': after.get('task') or {}}
    strategy = bool(set(impact['changed_task_fields']) & STRATEGY_FACTS)
    value['strategy_reassessment_required'] = strategy
    context_readable = (not after.get('narrative') or _read(store, after['narrative']) is not None) and (
        not after.get('content_plan') or _read(store, after['content_plan']) is not None)
    rows = []
    for entry in after.get('pages') or []:
        pid = entry['page_id']
        if pid in unreadable or not context_readable:
            state, codes = 'unverified', ['fixed_content_unreadable']
        elif pid in impact['affected_pages']:
            state, codes = 'affected', ['linked_source_changed']
        elif strategy:
            state, codes = 'needs_reassessment', ['strategy_task_facts_changed']
        elif impact['has_impact']:
            state, codes = 'needs_reassessment', ['changed_input_context_requires_review']
        else:
            state, codes = 'unverified', ['no_semantic_reuse_review']
        rows.append({'page_id': pid, 'state': state, 'reason_codes': codes,
            'evidence_refs': [ref for ref in (entry['page'], after.get('narrative'), after.get('content_plan')) if ref]})
    value['page_assessments'] = rows
    value['affected_pages'] = sorted(row['page_id'] for row in rows if row['state'] == 'affected')
    value['note'] = 'Fixed input impact only. Reassess strategy before rewrite/reuse; no automatic full rewrite or reuse.'
    value['impact_digest'] = models.sha256_bytes(models.canonical_json_bytes({k: v for k, v in value.items() if k != 'impact_digest'}))
    models.validate_schema('content_impact_v2', value)
    return value


def pending_impact(store, document):
    """Recover all pending changes from the actual manuscript's input basis."""
    basis = (document.get('content_basis') or {}).get('input_digest')
    if not basis or basis == models.compute_input_digest(document):
        return None
    origin = document
    while models.compute_input_digest(origin) != basis:
        if not origin.get('parent_revision_id'):
            raise models.ModelError('content_impact/basis', 'the prior content input basis is not in readable history')
        origin = store.load_document(origin['parent_revision_id'])
    from .content_impact import analyze_input_change
    return analyze_input_change(store, origin, document)


def bind_task(store, document, task, impact=None):
    if task.get('intent') != 'input_revision' or not enabled(store, document):
        return
    impact = pending_impact(store, document) if impact is None else impact
    if not impact or impact.get('schema_version') != VERSION or not impact['has_impact']:
        return
    models.validate_schema('content_impact_v2', impact)
    task['inputs'].append(store.put_json_object(impact))
    task['required_capabilities'].append(CAPABILITY)
    task['instruction'] += (
        ' 读取inputs中的固定content_impact.v2，按新任务重新判断主张、取舍与页序；来源未变不表示可复用。'
        'diff.page_assessments须逐页覆盖旧实际页面，每项含page_id、state、reason_codes、evidence_refs、reason；'
        'state只用affected/needs_reassessment/reusable_after_review/unverified。改写或删除标affected；'
        '复用须标reusable_after_review并具体说明对新策略仍成立的理由，evidence_refs含旧Page Ref及新Narrative/Plan Ref。'
        '未判断或缺证据不能清除待协调状态。策略事实变化须同次提交narrative与plan，并在diff.strategy_summary说明具体取舍；'
        '场景切换须有正文/论证职责的实质变化，不能只改标题和语气。业务事实仍绑定真实来源，不编造采购共识或能力。'
        '复用页只重绑必要映射，保留原字与原Ref沿革；正文变化时同步处理逐字稿，旧图不因内容采用自动成为新成品。')


def frozen_impact(store, task):
    if CAPABILITY not in task.get('required_capabilities', []):
        return None
    found = []
    for ref in task.get('inputs') or []:
        item = _read(store, ref)
        if isinstance(item, dict) and item.get('schema_version') == VERSION:
            models.validate_schema('content_impact_v2', item)
            found.append(item)
    if len(found) != 1:
        raise models.ModelError('content_impact/task', 'one frozen v2 impact is required')
    return found[0]


def validate_reconciliation(store, document, task, changes):
    impact = frozen_impact(store, task)
    if impact is None:
        return
    def fail(field, text):
        return models.ModelError('input_revision/' + field, text)
    if impact['basis']['after_input_digest'] != changes.request.expected_digest:
        raise fail('basis', 'the reconciliation must bind the frozen input impact')
    diff = changes.request.diff
    rows = diff.get('page_assessments')
    entries = changes.entries
    if not isinstance(rows, list) or len(rows) != len(entries) or {r.get('page_id') for r in rows if isinstance(r, dict)} != set(entries):
        raise fail('page_assessments', 'assess every fixed old Page exactly once')
    retaining = changes.request.binding.get('adoption_policy') in ('proposal_only', 'candidate_only')
    for row in rows:
        pid = row['page_id'];state = row.get('state')
        codes = row.get('reason_codes')
        if (state not in STATES or not isinstance(codes, list) or not codes
                or any(not isinstance(code, str) or not code.strip() for code in codes)
                or not isinstance(row.get('reason'), str) or not row['reason'].strip()):
            raise fail('page_assessments', 'each judgment needs a registered state and a concrete reason')
        refs = row.get('evidence_refs')
        if not isinstance(refs, list) or entries[pid]['page'] not in refs:
            raise fail('page_assessments/evidence_refs', 'judgment must include the exact old Page Ref')
        for ref in refs:
            store.read_object_bytes(ref)
        if state in ('unverified', 'needs_reassessment'):
            if not retaining:
                raise fail('page_assessments/state', 'unreviewed content cannot be adopted as reconciled')
        elif state == 'affected':
            if pid not in changes.changed_pages and pid not in changes.removed:
                raise fail('page_assessments/state', 'an affected page needs its substantive proposal or removal')
            if (pid in changes.changed_pages and store.read_object_json(entries[pid]['page']).get('speaker_notes')
                    and 'speech' not in changes.request.changed_layers):
                raise fail('changed_layers', 'changed copy with an existing script needs its speech reconciliation')
        else:
            old = store.read_object_json(entries[pid]['page']);new = changes.pages.get(pid)
            if new is None or any(new.get(key) != old.get(key) for key in ('customer_visible', 'speaker_notes', 'visual_spec')):
                raise fail('page_assessments/reuse', 'reused content keeps the actual fixed text and visual intent')
            if changes.narrative_ref not in refs:
                raise fail('page_assessments/evidence_refs', 'reuse must name the strategy it was reviewed against')
    if impact['strategy_reassessment_required'] or impact['affected_claims']:
        if not {'narrative', 'plan'} <= set(changes.request.changed_layers):
            raise fail('changed_layers', 'strategy changes require paired Narrative and Plan proposals')
        if not isinstance(diff.get('strategy_summary'), str) or not diff['strategy_summary'].strip():
            raise fail('strategy_summary', 'explain actual strategic selection, reuse and order decisions')
        if 'scenario' in impact['changed_task_fields'] and entries and not retaining:
            body_changed = any(pid not in entries or changes.pages[pid]['customer_visible'].get('body_blocks') !=
                store.read_object_json(entries[pid]['page'])['customer_visible'].get('body_blocks') for pid in changes.pages)
            old_roles = (changes.old_plan or {}).get('input', {}).get('page_roles')
            if not body_changed and not changes.removed:
                raise fail('scenario', 'a scenario switch cannot be reconciled by titles alone')
            if changes.order == list(entries) and (changes.plan_input or {}).get('page_roles') == old_roles:
                raise fail('scenario', 'a scenario switch must reassess actual page responsibilities or order')
