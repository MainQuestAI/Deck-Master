"""Versioned commercial-content criteria over existing review/compose contracts.

The canonical method text owns the criteria. Projections below only locate the
adopted strategy/frame in existing Plan roles and actual atoms; they never score
wording or turn nonempty mappings into a semantic pass.
"""
from __future__ import annotations

from . import models
from .method_resources import resolve_root

VERSION = 'business-expression-review.v1'
CAPABILITY = 'business-review.v1'
IDENTITY = 'business-expression-review-standard'
MARKER = '## 商业框架评价标准 ' + VERSION


def standard(store, document):
    ref = document.get('narrative')
    if not ref:
        return None
    narrative = store.read_object_json(ref)
    if narrative.get('schema_version') != 'narrative.v2':
        return None
    path = resolve_root() / 'references/method-review.md'
    raw = path.read_bytes();text = raw.decode('utf-8')
    if MARKER not in text:
        raise models.ModelError('business_review/standard', 'canonical versioned review method is missing')
    method = {'id': 'method-review', 'relative_path': 'references/method-review.md',
              'sha256': models.sha256_bytes(raw)}
    dependency = {'kind': 'policy', 'identity': IDENTITY,
                  'sha256': models.sha256_bytes(models.canonical_json_bytes({'version': VERSION, 'method': method}))}
    return {'version': VERSION, 'method': method, 'dependency': dependency,
            'criteria_text': MARKER + text.split(MARKER, 1)[1]}


def projection(store, document, *, page_ids=None):
    criteria = standard(store, document)
    if criteria is None:
        return None
    narrative = store.read_object_json(document['narrative'])
    plan = store.read_object_json(document['content_plan']) if document.get('content_plan') else None
    roles = (plan or {}).get('input', {}).get('page_roles', [])
    frame = narrative.get('business_frame') or {}
    locations = ['node:' + n['node_id'] for n in narrative['nodes']]
    locations += ['topic:' + t['topic_id'] for t in frame.get('topics', [])]
    locations += ['role:' + r['page_id'] for r in roles]
    from .content import visible_atoms
    for entry in document.get('pages', []):
        if page_ids is not None and entry['page_id'] not in page_ids:
            continue
        page = store.read_object_json(entry['page'])
        locations += [a['atom_id'] for a in visible_atoms(page)]
        locations += ['segment:' + page['page_id'] + ':' + segment['segment_id']
                      for segment in (page.get('content_mapping') or {}).get('speech_segments', [])]
    return {'standard': criteria, 'finding_locations': locations, 'narrative_ref': document['narrative'],
            'plan_ref': document.get('content_plan'), 'strategy': narrative['business_strategy'],
            'topics': [{**topic, 'planned_page_ids': [role['page_id'] for role in roles
                       if set(role['narrative_node_ids']).intersection(link['node_id'] for link in topic['links'])]}
                       for topic in frame.get('topics', [])],
            'relations': frame.get('relations', []),
            'interpretation': 'Locators only, not semantic approval. Read complete nodes, sources, atoms and notes; '
                              'a topic-node match does not establish a true capability or an adequate explanation.'}


def frozen_standard(store, task):
    values = []
    for ref in task.get('inputs') or []:
        if not ref.get('path', '').endswith('.json'):
            continue
        value = store.read_object_json(ref)
        if isinstance(value, dict) and value.get('schema_version') == 'content_review_packet.v1' and value.get('business_review'):
            values.append(value['business_review']['standard'])
    if CAPABILITY in task.get('required_capabilities', []) and not values:
        raise models.ModelError('task/business_review', 'frozen business review packet is required')
    if values and any(v != values[0] for v in values):
        raise models.ModelError('task/business_review', 'conflicting frozen business review standards')
    return values[0] if values else None


def prepare_task(store, document, task):
    if task.get('kind') != 'review' or task.get('review_stage') != 'preproduction' or standard(store, document) is None:
        return
    # Direct public dispatch also gets a real packet. Existing/pending Tasks are
    # never sent through this producer or supplemented on a read/recovery.
    packets = []
    for ref in task.get('inputs', []):
        if ref['path'].endswith('.json'):
            value = store.read_object_json(ref)
            if isinstance(value, dict) and value.get('schema_version') == 'content_review_packet.v1':
                packets.append(value)
    if len(packets) > 1 or packets and packets[0].get('business_review') != projection(store, document, page_ids=task.get('scope_pages')):
        raise models.ModelError('task/business_review', 'one current business projection is required; do not forge locators or upgrade an old packet')
    if not packets:
        from . import content_review, outline_review
        packet = (outline_review.packet(store, document) if task.get('review_subject') == 'outline' else
                  content_review.build_review_packet(store, document, page_ids=task.get('scope_pages'),
                      required=[u['kind'] for u in task.get('review_units') or []],
                      requirement=content_review.requirement_state(store, document)['effective']))
        task['inputs'].append(store.put_json_object(packet))
    task['required_capabilities'] = list(dict.fromkeys([*task['required_capabilities'], CAPABILITY]))
    if frozen_standard(store, task) != standard(store, document):
        raise models.ModelError('task/business_review', 'dispatch must freeze the current criteria and method bytes')


def validate_result(store, task, reviews):
    criteria = frozen_standard(store, task)
    if criteria is not None:
        locations = set()
        for ref in task['inputs']:
            if ref['path'].endswith('.json'):
                packet = store.read_object_json(ref)
                if isinstance(packet, dict) and packet.get('schema_version') == 'content_review_packet.v1':
                    locations.update((packet.get('business_review') or {}).get('finding_locations', []))
        for review in reviews:
            if criteria['dependency'] not in review.get('dependencies', []):
                raise models.ModelError('review/dependencies', 'review must bind its frozen business standard')
            for finding in review.get('findings', []):
                if not locations.intersection(finding.get('element_refs', [])) or not finding.get('evidence'):
                    raise models.ModelError('review/findings', 'business finding needs an actual frozen content locator and evidence')


def applicable(store, document, review):
    criteria = standard(store, document)
    return criteria is None or criteria['dependency'] in review.get('dependencies', [])


def expansion_required(store, document):
    if document.get('pages') or standard(store, document) is None:
        return False
    return True


def guard_expansion(store, document):
    if expansion_required(store, document):
        plan = store.read_object_json(document['content_plan']) if document.get('content_plan') else None
        if not plan or plan.get('mode') != 'planned' or plan.get('narrative_ref') != document['narrative']:
            raise models.ModelError('compose/outline_review', 'adopt the matching planned Plan before full expansion')
        from .outline_review import status
        if status(store, document)['status'] != 'pass':
            raise models.ModelError('compose/outline_review', 'business outline needs current argument/progression review before full expansion')


def validate_expansion(store, document, page_order, plan_input):
    if not expansion_required(store, document):
        return
    guard_expansion(store, document)
    original = store.read_object_json(document['content_plan'])['input']
    if page_order != original['page_order']:
        raise models.ModelError('compose/page_order', 'expand the adopted planned order; replan explicitly before changing it')
    roles = {r['page_id']: r for r in plan_input.get('page_roles', [])}
    for role in original['page_roles']:
        actual = roles.get(role['page_id']) or {}
        for field in ('narrative_node_ids', 'required_qualifications'):
            if not set(role[field]) <= set(actual.get(field, [])):
                raise models.ModelError('compose/plan_input/' + field, 'retain adopted role nodes and qualifications during expansion')


def expansion_instruction(store, document):
    if standard(store, document) is None:
        return ''
    return (' 沿已采用 Narrative 的作者任务、策略与 business_frame 展开，不重新造框架。'
            '每页按匹配 Plan 职责把主题落实为业务动作、关系、案例及必要条件，不能只改标题。'
            '可见 atom 与口播片段保留实际节点／来源对应。演示写清场景、现有能力与要支持的判断；'
            '尚不能证明可演示时保留待验证路径，不声称已连通、已演示或已产生效果。')
