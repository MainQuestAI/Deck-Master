"""Request-scoped read projection; never an authority or persistent state.

The caller pins both documents once. Existing completion, review and action
projections remain the owners of their facts. Priority is recovery, input
reconciliation, existing work, comparison, then missing production layers.
"""
from .content_production import completion_status
from .store import StoreError


def after_action(function):
    """Opt-in observation after a mutation, outside its durable replay receipt."""
    from functools import wraps

    @wraps(function)
    def wrapped(project_dir, *args, summary_protocol=None, **kwargs):
        from .workbench import workbench_summary, ReadModelError
        if summary_protocol not in (None, 'workbench_summary.v2'):
            raise ReadModelError('read_protocol_unsupported', 'summary_protocol',
                                 'use workbench_summary.v2 or omit', http_status=400)
        result = function(project_dir, *args, **kwargs)
        if summary_protocol:
            # A receipt can describe an old committed operation. Its observation
            # is separately labeled and never becomes the old operation result.
            try:
                result['current_work'] = workbench_summary(
                    project_dir, revision=result.get('revision_id'),
                    protocol=summary_protocol)['current_work']
            except (StoreError, OSError, ValueError, KeyError, TypeError):
                result['current_work_unavailable'] = True
                result['observation_recovery'] = 'preserve committed result; query the original operation, then retry view only'
        return result
    return wrapped

PRIORITY = {name: index for index, name in enumerate((
    'verify_execution', 'inspect_failure', 'reconcile_inputs', 'replan',
    'handoff', 'compare_candidates', 'review_results', 'review_quality',
    'refresh_stage', 'prepare_stage'))}


def project(store, artifact, control, summary, *, fixed=False):
    request = (artifact.get('collaboration') or {}).get('request') or {}
    completion = completion_status(store, artifact)
    scope = completion.get('effective_scope') or {}
    current_request = (control.get('collaboration') or {}).get('request') or {}
    historical = fixed and artifact['revision_id'] != control['revision_id']
    actions, optional = [], []
    content_only = request.get('intent') == 'content_only'
    design_plan = any(c.get('kind') == 'requested_design_plan' for c in completion['checks'])
    full_delivery = None
    if request.get('intent') == 'full_deck' and not design_plan:
        from .delivery_eligibility import describe_snapshots
        try:
            full_delivery = describe_snapshots(store, artifact, control)
            ready = full_delivery['status'] == 'ready'
            output = full_delivery['selected_output']['artifact_ref']
            completion = {**completion,
                'state': 'completed' if ready else completion['state'],
                'outputs': [*completion['outputs'], *([output] if output else [])],
                'checks': [*completion['checks'], {'kind': 'requested_delivery',
                    'status': 'pass' if ready else 'not_evaluated', 'basis': full_delivery}],
                'responsible_role': 'caller' if ready else completion['responsible_role'],
                'next_action': 'read_delivery' if ready else completion['next_action']}
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            completion = {**completion, 'state': 'needs_recovery',
                'missing': [*completion['missing'], {'code': 'delivery_facts_unreadable'}]}
    from .eligibility import scope_page_ids
    try:
        selected = scope_page_ids(store, scope) if scope else []
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        selected = []
    ids = set(selected if selected is not None else [entry['page_id'] for entry in artifact.get('pages', [])])
    for action in summary['next_actions'].get('actions', []):
        outside = (historical or not request or
            (action['kind'] != 'verify_execution' and action['page_ids'] and not set(action['page_ids']) & ids) or
            (action['kind'] in ('prepare_stage', 'refresh_stage') and
             (content_only or design_plan or {'svg_preview': 'svg', 'ppt_preview': 'output', 'pptx': 'output'}.get(action['layer'], action['layer']) not in scope.get('layers', []))))
        (optional if outside else actions).append(action)
    actions.sort(key=lambda a: (PRIORITY.get(a['kind'], 99), a['action_id']))
    review = {'status': 'not_evaluated', 'review_refs': artifact.get('reviews') or [],
              'missing_units': [], 'blocking_findings': []}
    if (request.get('content_intent') == 'plan_only' or not artifact.get('pages')) and artifact.get('narrative') and artifact.get('content_plan'):
        from .outline_review import status
        try:
            review = status(store, artifact)
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            review['status'] = 'unknown'
    elif artifact.get('pages') and not design_plan:
        from .content_review import preproduction_status
        try:
            review = preproduction_status(store, artifact, page_ids=sorted(ids))
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            review['status'] = 'unknown'
    blockers = []
    if historical:
        code, role, label, title, surface = 'read_snapshot', 'caller', '阅读此版本', '正在查看历史版本', 'content'
    elif not request:
        code, role, label, title, surface = 'read_artifacts', 'caller', '阅读已有产物', '本次工作范围未知', 'content'
    elif design_plan:
        done = completion['state'] == 'completed'
        code, role = completion['next_action'], completion['responsible_role']
        label = '查看本次设计方案' if done else '准备本次设计方案'
        title = '本次设计方案已完成' if done else '设计方案准备中'
        surface = 'style'
    elif content_only and completion['state'] == 'completed':
        code, role, label, surface = 'return_requested_content', 'caller', '阅读本次内容', 'content'
        product_name = {'plan_only': '论证与大纲', 'write_only': '上屏稿',
                        'speech_only': '口播稿', 'content_full': '完整内容'}.get(request.get('content_intent'), '内容')
        title = f'本次{product_name}已完成'
    elif full_delivery and full_delivery['status'] == 'ready':
        code, role, label, title, surface = 'read_delivery', 'caller', '阅读本次交付', '本次整稿已具备交付资格', 'runs'
    else:
        code, role, label, title, surface = 'continue_project', 'master', '查看下一工作', '本次工作待接续', 'runs'
        from .eligibility import evaluate
        try:
            decision = evaluate(store, artifact, control, 'continue_project')
            blockers = decision['reasons']
            if not decision['allowed']:
                code = decision['next_action'] or 'inspect_blockers'
                role = decision['responsible_role']
        except (StoreError, OSError, ValueError, KeyError, TypeError):
            code, role = 'recover_current_facts', 'master'
            blockers = [{'code': 'facts_unreadable'}]
    if (not historical and request and review.get('review_subject') == 'outline'
            and review['status'] != 'pass' and not current_request.get('paused') and not current_request.get('closed')):
        code, role, label, title, surface = 'review_outline', 'reviewer', '阅读待审大纲', '大纲已保留，结构审查待完成', 'content'
    primary = None
    recovery = actions and actions[0]['kind'] in ('verify_execution', 'inspect_failure', 'reconcile_inputs', 'replan')
    if not historical and request and actions and (recovery or (
            code not in ('review_outline', 'read_delivery') and not design_plan and not (content_only and completion['state'] == 'completed'))):
        primary = actions[0]
        code = primary['kind']
        role = 'master'
        layer = {'blueprint': '原图', 'svg': 'SVG', 'svg_preview': 'SVG 预览',
                 'ppt_preview': 'PPT 预览', 'pptx': '整稿 PPT'}.get(primary['layer'], '产物')
        titles = {'verify_execution': '执行待核实', 'inspect_failure': '失败待查看',
                  'reconcile_inputs': '输入待协调', 'replan': '需重新计划', 'handoff': '制作任务待交接',
                  'compare_candidates': '候选待比较', 'review_results': '结果待阅读', 'review_quality': '质量记录待查看'}
        labels = {'verify_execution': '去核实', 'inspect_failure': '查看失败', 'reconcile_inputs': '去协调',
                  'replan': '重新计划', 'handoff': '去交接', 'compare_candidates': '比较候选',
                  'review_results': '去阅读', 'review_quality': '查看记录', 'prepare_stage': '查看待补页', 'refresh_stage': '查看依据'}
        title = (f"{len(primary['page_ids'])} 页{layer}" + ('待生成' if code == 'prepare_stage' else '依据已变化')
                 if code in ('prepare_stage', 'refresh_stage') else titles[code])
        label, surface = labels[code], 'content' if code == 'reconcile_inputs' else 'runs'
    # Reading an output remains legal when production is paused or withdrawn.
    # The UI action is a navigation target; it is never an execution grant.
    navigation = {'surface': surface}
    if code == 'read_delivery':
        navigation['runs_area'] = 'files'
    elif code == 'return_requested_content' and request.get('content_intent') != 'plan_only':
        page_id = next((entry['page_id'] for entry in artifact.get('pages', []) if entry['page_id'] in ids), None)
        if page_id:
            surface = 'page'
            navigation = {'surface': surface, 'page_id': page_id, 'layer': 'content'}
    return {'identity': {'project_id': artifact['project_id'], 'request_id': request.get('request_id'),
                'artifact_revision_id': artifact['revision_id'], 'control_revision_id': control['revision_id'],
                'control_request_id': current_request.get('request_id'),
                'snapshot_mode': 'fixed' if fixed else 'current'},
            'scope': {'intent': request.get('intent'), 'content_intent': request.get('content_intent'),
                      'effective_scope': completion.get('effective_scope'), 'known': bool(request)},
            'delivery': completion, 'review': review,
            'next': {'action': code, 'responsible_role': role, 'label': label, 'title': title,
                     'surface': surface, 'navigation_only': True,
                     'navigation': navigation,
                     'source_refs': completion['outputs'], 'primary_action': primary, 'actions': actions},
            'blockers': blockers, 'optional': optional}


def from_snapshot(store, document):
    """Shared Host projection on the exact document already selected by reader."""
    from .workbench import _ReadContext, _summary
    ctx = _ReadContext(store, document)
    try:
        return project(store, document, document, _summary(ctx, revision=None))
    finally:
        ctx.close()
