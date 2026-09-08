"""Read-only native continuation, shared by CLI state and next-step."""
from pathlib import Path
from typing import Any


def native_continuation(root: Path) -> dict[str, Any] | None:
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
    task_path = root / 'build/host_imagegen_task.json'
    task = read_json(task_path) if task_path.exists() else {}
    pending = [page for page in task.get('pages', []) if not action_applied(root, page['action_id'])]
    if status['status'] == 'completed':
        from quality.gate_policy import resolve_required_gates
        artifact = Path(status['artifact_path'])
        artifact = (artifact if artifact.is_absolute() else root / artifact).resolve()
        if not artifact.is_relative_to(root.resolve()):
            raise ValueError('native artifact escapes run')
        request = read_json(root / 'request.json')
        policy = resolve_required_gates(root, artifact, builder_profile='standard', output_profile='production_pptx', run_mode=request.get('run_mode', 'production'))
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
