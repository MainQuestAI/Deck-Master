"""Explicit, source-bound native migration; historical artifacts remain intact."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 'deck_build_migration_plan.v1'
_EXCLUDED = ('build/migrations/', 'build/revisions/', 'workflow/actions/')


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _files(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if any(name == prefix.rstrip('/') or name.startswith(prefix) for prefix in _EXCLUDED):
            continue
        if path.is_symlink():
            raise ValueError(f'migration_symlink: {name}')
        if path.is_file() and name not in {'workflow/.actions.lock', 'build/.action_commit.lock'}:
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        raise ValueError(f'expected object: {path.name}')
    return result


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def _detect_run_kind(root: Path) -> str:
    route = _json(root / 'build/route.json')
    if route:
        engine = route.get('engine_id')
        return {'legacy_ppt_master': 'legacy_ppt_master', 'deck_native': 'native'}.get(engine, 'unknown')
    if (root / 'high_density_build/status.json').exists():
        return 'high_density'
    if (root / 'build/render_request.json').exists():
        return 'legacy_ppt_master'
    result = _json(root / 'render_results/render_result.json')
    return 'native' if result.get('tool') == 'deck_native' else 'unknown'


def build_migration_plan(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('migration_run_missing')
    files = _files(root)
    kind = _detect_run_kind(root)
    from build.native_engine import _approved_packages
    missing = []
    try:
        packages = _approved_packages(root)
    except (ValueError, RuntimeError, FileNotFoundError, KeyError):
        packages = []
    if not packages:
        missing.append('approved_page_packages')
    request = _json(root / 'request.json')
    route = {
        'schema_version': 'deck_build_route.v1', 'engine_id': 'deck_native',
        'authoring_mode': 'direct_svg',
        'density': 'high' if kind == 'high_density' else 'standard',
        'library_mode': str(request.get('library_mode') or 'auto'),
        'origin_run_mode': str(request.get('run_mode') or 'production'),
        'selection_origin': 'legacy_migration', 'selection_ref': 'build/migrations',
    }
    plan = {
        'schema_version': SCHEMA_VERSION, 'run_id': root.name, 'run_dir': str(root),
        'detected': kind, 'dry_run': True, 'target_profile': 'native',
        'source_fingerprint': _digest(files), 'source_files': files,
        'source_route': _json(root / 'build/route.json'),
        'source_revision': _json(root / 'build/current_revision.json'),
        'target_route': route, 'scope_pages': [str(p['page_id']) for p in packages],
        'preserved_files': {name: value for name, value in files.items()
                            if name.endswith('.pptx') or 'approv' in name},
        'missing_evidence': missing,
        'read_only': kind == 'unknown' or bool(missing),
        'actions': [] if kind in {'unknown', 'native'} else [
            {'kind': 'rebuild_route'}, {'kind': 'recompile'}, {'kind': 'reapprove'}],
        'invalidated_gates': ['build', 'render', 'readback', 'quality', 'final_artifact_approval'],
        'path_mapping': 'source paths retained; candidate and new build artifacts stored in migration directory',
        'rollback': 'rollback_migration(run_dir, plan_id); refuses if current revision changed',
        'notes': ['Old approved files and approval records are never rewritten or re-signed.'],
    }
    plan['plan_id'] = _digest(plan)
    return plan


def _load_plan(root: Path, plan: dict[str, Any] | str | Path) -> dict[str, Any]:
    value = dict(plan) if isinstance(plan, dict) else _json(Path(plan))
    identifier = value.pop('plan_id', '')
    if identifier != _digest(value):
        raise ValueError('migration_plan_changed')
    value['plan_id'] = identifier
    if value.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('migration_plan_changed')
    if value.get('run_dir') != str(root) or value.get('run_id') != root.name:
        raise ValueError('migration_wrong_run')
    if value.get('source_fingerprint') != _digest(_files(root)):
        raise ValueError('migration_source_changed')
    if value != build_migration_plan(root):
        raise ValueError('migration_plan_changed')
    return value


def _migration_dir(root: Path, migration_id: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{64}', migration_id):
        raise ValueError('invalid_migration_id')
    result = root / 'build/migrations' / migration_id
    for parent in (root / 'build', root / 'build/migrations', result):
        if parent.is_symlink():
            raise ValueError('migration_symlink')
    return result


def apply_migration(run_dir: str | Path, plan: dict[str, Any] | str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    plan = _load_plan(root, plan)
    if plan['detected'] == 'native':
        return {'status': 'no_migration_needed', 'plan_id': plan['plan_id']}
    if plan['read_only']:
        return {'status': 'blocked', 'code': 'migration_required',
                'missing_evidence': plan['missing_evidence'], 'plan_id': plan['plan_id']}
    directory = _migration_dir(root, plan['plan_id'])
    candidate = directory / 'candidate'
    if directory.exists():
        if _recover_result(root, directory):
            raise ValueError('migration_already_applied')
        # Preserve failed candidate evidence while allowing dependency repairs
        # to retry the same unchanged, source-bound plan.
        if candidate.exists():
            candidate.rename(directory / ('failed-candidate-' + uuid.uuid4().hex))
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory / 'plan.json', plan)
    # Only immutable bytes from the approved plan are copied; symlinks are forbidden.
    for name, digest in plan['source_files'].items():
        content = (root / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('migration_source_changed')
        target = candidate / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    request = _json(candidate / 'request.json')
    request['profile'] = 'native'
    request['authoring_mode'] = 'direct_svg'
    _write(candidate / 'request.json', request)
    _write(candidate / 'build/route.json', plan['target_route'])
    # The candidate must not reference an existing committed snapshot in the source.
    (candidate / 'build/current_revision.json').unlink(missing_ok=True)
    try:
        from runtime.build import run_build
        result = run_build(candidate)
        if result.get('status') not in {'compiled', 'built', 'completed', 'ready'}:
            raise ValueError(f"migration_candidate_not_built: {result.get('status')}")
        pptx = Path(str(result.get('artifact_path') or result.get('pptx_path') or result.get('pptx') or ''))
        if not pptx.is_absolute():
            pptx = candidate / pptx
        if not pptx.is_file() or not pptx.resolve().is_relative_to(candidate.resolve()):
            raise ValueError('migration_candidate_artifact_missing')
        from workflow.actions import create_action_envelope, stage_action_result, commit_action_result, read_current_revision
        action_id = 'migration-' + plan['plan_id'][:24]
        rollback_revision = str(plan['source_revision'].get('revision_id') or '')
        if not rollback_revision:
            baseline = create_action_envelope(action_id=action_id + '-baseline', task_id=action_id + '-baseline',
                scope_pages=plan['scope_pages'], permission='migration', input_fingerprint=plan['source_fingerprint'])
            stage_action_result(root, baseline, {'request.json': (root / 'request.json').read_bytes()})
            baseline_receipt = commit_action_result(root, baseline,
                current_input_fingerprint=lambda: _digest(_files(root)),
                targets={'request.json': root / 'request.json'}, expected_revision='')
            rollback_revision = baseline_receipt['revision_id']
        commit_fingerprint = _digest(_files(root))
        # A concurrent writer between candidate build and baseline cannot be accepted.
        from workflow.actions import read_revision_state
        baseline_files = read_revision_state(root, rollback_revision)
        for name, digest in plan['source_files'].items():
            if name == 'build/current_revision.json':
                continue
            if name not in baseline_files or hashlib.sha256(baseline_files[name]).hexdigest() != digest:
                raise ValueError('migration_source_changed')
        envelope = create_action_envelope(action_id=action_id, task_id=action_id,
            scope_pages=plan['scope_pages'], permission='migration',
            input_fingerprint=commit_fingerprint)
        # New files never overwrite an old output or its approval record.
        output_name = f"build/migration_outputs/{plan['plan_id']}.pptx"
        outputs = {'build/route.json': json.dumps(plan['target_route']).encode(),
                   'request.json': json.dumps(request).encode(), output_name: pptx.read_bytes()}
        pending = {'status': 'applied', 'plan_id': plan['plan_id'], 'action_id': action_id,
                   'rollback_revision': rollback_revision, 'artifact': output_name,
                   'artifact_sha256': hashlib.sha256(outputs[output_name]).hexdigest(),
                   'approval_status': 'pending', 'candidate_result': result}
        _write(directory / 'pending.json', pending)
        stage_action_result(root, envelope, outputs)
        receipt = commit_action_result(root, envelope,
            current_input_fingerprint=lambda: _digest(_files(root)),
            targets={name: root / name for name in outputs},
            expected_revision=rollback_revision)
        record = {'status': 'applied', 'plan_id': plan['plan_id'],
                  'revision_id': receipt['revision_id'], 'rollback_revision': rollback_revision, 'artifact': output_name,
                  'artifact_sha256': hashlib.sha256(outputs[output_name]).hexdigest(),
                  'approval_status': 'pending', 'candidate_result': result}
        _write(directory / 'result.json', record)
        return record
    except Exception as exc:
        _write(directory / 'failure.json', {'status': 'failed', 'error': str(exc)})
        raise


def verify_migration(run_dir: str | Path, migration_id: str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    directory = _migration_dir(root, migration_id)
    plan = _json(directory / 'plan.json')
    if not plan:
        raise ValueError('migration_not_found')
    result = _recover_result(root, directory)
    blockers = []
    for name, digest in plan['preserved_files'].items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            blockers.append(f'preserved_file_changed:{name}')
    if not result:
        blockers.append('migration_not_committed')
    elif result.get('status') == 'applied':
        from workflow.actions import read_current_revision
        if read_current_revision(root).get('revision_id') != result.get('revision_id'):
            blockers.append('current_revision_changed')
        artifact = root / result['artifact']
        if not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest() != result['artifact_sha256']:
            blockers.append('migration_artifact_changed')
    return {'status': 'blocked' if blockers else 'verified', 'plan_id': migration_id,
            'blockers': blockers, 'approval_status': 'pending'}


def rollback_migration(run_dir: str | Path, migration_id: str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    directory = _migration_dir(root, migration_id)
    plan = _json(directory / 'plan.json')
    result = _recover_result(root, directory)
    if not plan or result.get('status') != 'applied':
        raise ValueError('migration_not_applied')
    from workflow.actions import restore_revision
    restore_revision(root, expected_revision=result['revision_id'],
                     revision_id=result['rollback_revision'])
    from workflow.actions import recover_projections
    recover_projections(root)
    # This route was introduced by migration; removing only its compatibility
    # projection exposes the original trace-based route. New artifacts stay.
    route_path = root / 'build/route.json'
    if not plan['source_route'] and route_path.exists() and _json(route_path) == plan['target_route']:
        route_path.unlink()
    result['status'] = 'rolled_back'
    _write(directory / 'result.json', result)
    return {'status': 'rolled_back', 'plan_id': migration_id, 'approval_status': 'pending'}


def _recover_result(root: Path, directory: Path) -> dict[str, Any]:
    result = _json(directory / 'result.json')
    if result:
        return result
    pending = _json(directory / 'pending.json')
    if not pending:
        return {}
    from workflow.actions import action_applied
    receipt = action_applied(root, pending['action_id'])
    if not receipt:
        return {}
    return {**pending, 'revision_id': receipt['revision_id']}
