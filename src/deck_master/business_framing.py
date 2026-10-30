"""Narrative.v2 integrity and frozen-task consumption; no second content store."""
from __future__ import annotations

from . import models

CAPABILITY = 'business-framing.v1'
VERSION = 'narrative.v2'
TASK_FACTS = ('brief', 'audience', 'scenario', 'existing_decisions')


def validate(narrative):
    """References and structure only; business quality still needs author review."""
    known = {node['node_id'] for node in narrative['nodes']}
    issues = {item['issue_id'] for item in narrative['issues']}
    strategy = narrative['business_strategy']
    for field in ('established_node_ids', 'focus_node_ids', 'support_node_ids', 'omitted_node_ids'):
        unknown = set(strategy[field]) - known
        if unknown:
            raise models.ModelError('narrative/business_strategy/' + field, f'unknown node ids: {sorted(unknown)}')
    if set(strategy['focus_node_ids']) & (set(strategy['support_node_ids']) | set(strategy['omitted_node_ids'])):
        raise models.ModelError('narrative/business_strategy', 'focus, support and omitted placements must not conflict')
    if set(strategy['support_node_ids']) & set(strategy['omitted_node_ids']):
        raise models.ModelError('narrative/business_strategy', 'support and omitted placements must not conflict')
    frame = narrative['business_frame']
    if narrative['maturity'] == 'argument' and (frame is None or not strategy['focus_node_ids']):
        raise models.ModelError('narrative/business_frame', 'argument requires an expandable frame and focused nodes')
    if narrative['maturity'] == 'argument' and narrative['central_node_id'] not in strategy['focus_node_ids']:
        raise models.ModelError('narrative/business_strategy/focus_node_ids', 'the central claim must remain in focus')
    if frame is not None:
        topic_ids = [topic['topic_id'] for topic in frame['topics']]
        if len(set(topic_ids)) != len(topic_ids):
            raise models.ModelError('narrative/business_frame/topics', 'duplicate topic_id')
        for topic in frame['topics']:
            if {link['node_id'] for link in topic['links']} - known or set(topic['gap_issue_ids']) - issues:
                raise models.ModelError('narrative/business_frame/topics', 'unknown node or gap issue')
            pairs = [(link['node_id'], link['role']) for link in topic['links']]
            if len(pairs) != len(set(pairs)):
                raise models.ModelError('narrative/business_frame/topics', 'duplicate topic link')
        for relation in frame['relations']:
            if {relation['from_topic_id'], relation['to_topic_id']} - set(topic_ids):
                raise models.ModelError('narrative/business_frame/relations', 'unknown topic_id')
    for application in narrative['method_applications']:
        value = narrative
        try:
            for part in application['result_pointer'][1:].split('/'):
                part = part.replace('~1', '/').replace('~0', '~')
                value = value[int(part)] if isinstance(value, list) and part.isdecimal() else value[part]
            if value is None:
                raise KeyError('absent result')
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise models.ModelError('narrative/method_applications/result_pointer', 'result location does not exist') from exc


def validate_task_result(store, document, task, narrative):
    """Do not silently upgrade old tasks or accept v1 from a v2-only Host task."""
    required = CAPABILITY in (task.get('required_capabilities') or [])
    if required != (narrative.get('schema_version') == VERSION):
        raise models.ModelError('narrative/schema_version', 'result must match the frozen business-framing capability')
    if not required:
        return
    basis = narrative['input_basis']
    bound = {(dep['kind'], dep['identity'], dep['projection']): dep['sha256']
             for dep in (task.get('collaboration_binding') or {}).get('eligibility_basis', [])}
    from .dependency_slices import make_dependency_slice
    for field in TASK_FACTS:
        expected = make_dependency_slice(store, document, kind='task_fact', identity=field, projection='value')
        key = ('task_fact', field, 'value')
        if bound.get(key) != expected['sha256'] or not any(dep == expected for dep in basis):
            raise models.ModelError('narrative/input_basis', f'current frozen {field} basis is required')
    methods = {item['id']: item['sha256'] for item in task.get('method_manifest', [])}
    for application in narrative['method_applications']:
        if application['task_id'] != task['task_id'] or methods.get(application['method_id']) != application['sha256']:
            raise models.ModelError('narrative/method_applications', 'application must name this frozen Task method/hash')
    from .content_plan import validate_source_links
    for node in narrative['nodes']:
        validate_source_links(store, document, node['source_links'], 'narrative/nodes/' + node['node_id'])


def validate_adoption_basis(store, document, narrative, decision):
    """Recheck strategy inputs between the two CAS adoptions of a zero-page plan."""
    if narrative.get('schema_version') != VERSION:
        return
    from .dependency_slices import make_dependency_slice
    for field in TASK_FACTS:
        expected = make_dependency_slice(store, document, kind='task_fact', identity=field, projection='value')
        if expected not in narrative['input_basis'] or expected not in decision.get('basis', []):
            raise models.ModelError('collaboration/adopt_proposal/basis', f'business strategy {field} basis changed or missing')
    from .content_plan import validate_source_links
    for node in narrative['nodes']:
        validate_source_links(store, document, node['source_links'], 'narrative/adoption/' + node['node_id'])
