"""Read-only native continuation, shared by CLI state and next-step."""
from pathlib import Path
from typing import Any


def native_continuation(root: Path) -> dict[str, Any] | None:
    from build.native_tasks import stopped_native_tasks
    stopped=stopped_native_tasks(root)
    if stopped:
        return {'stage':'stopped', 'reason':'Native host action cancelled by user; explicit build retry required',
                'next_command':'', 'build_status':{'status':'stopped'}, 'blocking_issues':stopped,
                'host_task':{'kind':'native_stopped', 'actions':stopped}}
    from conversation.brief_compiler import run_brief_conflict_blockers
    blockers = run_brief_conflict_blockers(root)
    if blockers and any(isinstance(b,dict) and b.get('code')=='context_reading_incomplete' for b in blockers):
        return {'stage':'blocked_context_reading', 'reason':'Required source ranges have not been read',
                'next_command':'', 'build_status':{'status':'blocked'}, 'blocking_issues':blockers,
                'host_task':{'kind':'extract_context_sources','blockers':blockers,
                             'inputs':['context_manifest.json'],
                             'resume_command':f'deck-master import-context-pack --run-dir {root} --input <extraction.json> --merge'}}
    if blockers:
        return {'stage':'blocked_source_conflicts', 'reason':'Declared source conflicts require evidence-based Brief resolution',
                'next_command':'', 'build_status':{'status':'blocked'}, 'blocking_issues':blockers,
                'host_task':{'kind':'resolve_declared_source_conflicts', 'blockers':blockers,
                             'inputs':['context_manifest.json','deck_brief.json'],
                             'resume_command':f'deck-master build-brief --run-dir {root} --agent-extract <resolved-extraction.json>'}}
    from context_intake.research_runtime import research_continuation
    research = research_continuation(root)
    if research:
        return research
    from production.content_handoff import content_continuation
    content = content_continuation(root)
    if content:
        return content
    from build.build_route import load_persisted_route
    from native_pptx.contracts import read_json
    from workflow.actions import action_applied
    route = load_persisted_route(root)
    if not route or route.get('engine_id') != 'deck_native':
        return None
    from runtime.build import build_status
    status = build_status(root)
    command = f'deck-master build run --run-dir {root}'
    stage, reason = 'needs_build', 'native build is not current'
    from build.native_tasks import pending_native_task
    task = pending_native_task(root) or {}
    pending = task.get('pages', [])
    if status['status'] == 'completed':
        from quality.gate_policy import resolve_required_gates
        artifact = Path(status['artifact_path'])
        artifact = (artifact if artifact.is_absolute() else root / artifact).resolve()
        if not artifact.is_relative_to(root.resolve()):
            raise ValueError('native artifact escapes run')
        request = read_json(root / 'request.json')
        from build.run_policy import enforce_origin_mode
        policy = resolve_required_gates(root, artifact, builder_profile='standard', output_profile='production_pptx', run_mode=enforce_origin_mode(root, request))
        if policy.get('required_gate_satisfied') and not policy.get('current_blockers'):
            stage, reason = 'ready_for_client_export', 'native build and required quality gates are current'
            command = f'deck-master final-readiness --run-dir {root} --artifact {artifact} --expected-pages {status["page_count"]}'
        else:
            from runtime.next_step import _next_quality_gate_command
            stage, reason = 'needs_draft_gate', 'native build requires current quality review'
            command = _next_quality_gate_command(root, artifact, status['page_count'], policy)
    elif pending:
        from build.native_engine import _svg_input_fingerprint
        # A changed content input invalidates a dispatched task. Rebuild prepares
        # the replacement task; polling never creates actions or consumes budget.
        fresh = all(page.get('produced_against') == _svg_input_fingerprint(root, page['page_id']) for page in pending)
        if fresh:
            stage, reason = 'awaiting_agent_execution', f'native host task awaits {task.get("stage")}'
            command = f'deck-master build status --run-dir {root}'
    return {'stage': stage, 'reason': reason, 'next_command': command, 'host_task': task if pending else {}, 'build_status': status}
