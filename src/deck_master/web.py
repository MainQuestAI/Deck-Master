"""Read-only loopback workbench service for the rebuilt core (spec 09.5, 10).

Only GET routes serve real Document data and project-object files; the four
view slots (content/blueprint/svg/ppt) render real data or an explicit wait.
The service binds to 127.0.0.1; remote binding is out of scope for T05.
Same-project service reuse: ``view.json`` records the active port and is
health-checked before reuse (spec 09.5.3).
"""

from __future__ import annotations

import json
import hashlib
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, unquote

from . import view as view_mod
from .store import Store
from . import workbench as workbench_mod
from .errors import TypedServiceError, NEXT_ACTIONS_BY_CODE
from .models import ModelError
from .local_runtime import ServiceUnavailable

STATE_FILE = "view.json"


def _editing_review_doc(store):
    return store.load_document()


def _project_identity(project_dir):
    return hashlib.sha256(str(Path(project_dir).resolve()).encode()).hexdigest()

def _state_path(project_dir: Path) -> Path:
    return project_dir / ".deckmaster" / STATE_FILE


def read_active_service(project_dir: Path) -> dict | None:
    from .local_runtime import descriptor, read_state
    try:
        return read_state(descriptor(project=project_dir))
    except (ValueError, RuntimeError, OSError):
        return None


def _write_state(project_dir: Path, state: dict) -> None:
    from .local_runtime import descriptor, publish
    publish(descriptor(project=project_dir), state)


# Server-side capability names (single source for /api/health and the
# /api/project effective-action projection).
UI_CAPABILITIES = ("ui_draft.v1", "ui_gallery.v1", "ui_overview.v1", "thumbnails.v1", "fixed_snapshot.v1", "text_range.v1",
                   "page_detail.v1", "annotations.v1", "changes.v1", "operations.v1", "candidates.v1",
                   "stages.v1", "run_desk.v1", "style_recipes.v1", "content_ops.v1", "exports.v1",
                   "restoration.v1", "workbench_actions.v1", "action_targets.v1", "icon_quality.v1", "result_reading.v1", "history_summary.v1", "visual_reference.v1")


class WorkbenchHandler(BaseHTTPRequestHandler):
    store: Store
    static_dir: Path
    write_token: str
    runtime_state: dict

    def log_message(self, fmt, *args):  # quiet default
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_json_bytes(body, status)

    def _send_json_bytes(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, media: str, *, immutable=False, download_name=None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", media)
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Cache-Control", "private, max-age=31536000, immutable" if immutable else "no-cache")
        # One Content-Security-Policy header: sandboxed isolation for SVG,
        # the default self-only policy for everything else.
        if media == "image/svg+xml":
            self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'")
        else:
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _local_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def _authorized_write(self):
        origin=self.headers.get('Origin')
        allowed=(f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        if not self._local_host() or origin not in allowed or not secrets.compare_digest(self.headers.get('X-Deck-Token',''),self.write_token):
            self._send_json({'error':'same-origin session token required'},403)
            return False
        return True

    def _read_json_body(self):
        from .local_state import MAX_BODY, LocalStateError
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise LocalStateError('body', 'one Content-Length is required')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= MAX_BODY:
            raise LocalStateError('body', 'request must be at most 2,000,000 bytes')
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise LocalStateError('body', 'request must be a JSON object')
        return value

    def _send_error(self, exc):
        from .local_state import LocalStateError
        from .operations import OperationError
        if isinstance(exc, OperationError):
            self._send_json(exc.payload(), exc.http_status)
            return
        if isinstance(exc, (LocalStateError, ModelError, workbench_mod.ReadModelError)):
            self._send_json({'error': {'code': getattr(exc, 'error_code', 'invalid_input'),
                            'message': getattr(exc, 'detail', str(exc)), 'field': getattr(exc, 'path', None),
                            'next_action': 'keep local input; read the saved state or correct the named field'}},
                            409 if getattr(exc, 'exit_code', 2) == 5 else 422)
        else:
            self._send_json({'error': {'code': 'local_io_failed', 'message': 'local action failed; retain input and inspect the path or runtime log',
                                      'field': None, 'next_action': 'retry after checking local permissions and input'}}, 400)

    def do_POST(self):
        if not self._authorized_write():
            return
        try:
            if urlparse(self.path).path == '/api/styles/references/import':
                from . import visual_styles
                from .samples import sample_info
                if (sample_info(self.store.project_root) or {}).get('readonly'):
                    self._send_json({'error': {'code':'sample_readonly','message':'example is read-only'}},403);return
                fields = parse_qs(urlparse(self.path).query,keep_blank_values=True)
                if set(fields) != {'base_revision','operation_id'} or any(len(v)!=1 or not v[0] for v in fields.values()):
                    visual_styles.fail('query','use one base_revision and operation_id')
                lengths = self.headers.get_all('Content-Length',[])
                if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not 0 < int(lengths[0]) <= visual_styles.MAX_BYTES:
                    visual_styles.fail('body','one Content-Length of at most 64 MiB is required')
                length=int(lengths[0]); data=self.rfile.read(length)
                if len(data) != length: visual_styles.fail('body','incomplete image upload')
                self._send_json(visual_styles.import_reference(self.store.project_root,data=data,**{key:v[0] for key,v in fields.items()}));return
            data=self._read_json_body()
            from .samples import sample_info
            sample = sample_info(self.store.project_root)
            if sample and sample['readonly'] and self.path not in ('/api/ui-state', '/api/gallery', '/api/overview', '/api/text-ranges/validate'):
                self._send_json({'error': {'code': 'sample_readonly', 'message': 'this synthetic example is read-only; create your own project'}}, 403)
                return
            # G54（B07 回填）：document 写族端点补与 FORMAT_GATED 投影一致的格式门。
            # G54 defensive copy only: candidates plan/adopt/decision are gated
            # at the service layer (_require_workbench); stages.assemble keeps its
            # existing service-layer stage_format_required error, not masked here.
            if self.path in ('/api/candidates/plan', '/api/candidates/adopt', '/api/candidates/decision'):
                document = self.store.load_document()
                if document.get('compatibility', {}).get('project_format') != 'workbench.v3':
                    self._send_json({'error': {'code': 'unsupported_project_format', 'message': 'this action requires a workbench.v3 project'}}, 409)
                    return
            from . import editing, service
            if self.path in ('/api/drafts/save', '/api/drafts/import', '/api/drafts/recovery', '/api/ui-state'):
                from . import ui_journal
                action = {'/api/drafts/save': ui_journal.save, '/api/drafts/import': ui_journal.import_recovery,
                          '/api/drafts/recovery': ui_journal.recovery_file, '/api/ui-state': ui_journal.save_position}[self.path]
                result = action(self.store.project_root, **data)
            elif self.path in ('/api/ui-state/plan-clear', '/api/ui-state/commit-clear'):
                from . import ui_journal
                action = {'/api/ui-state/plan-clear': ui_journal.plan_clear,
                          '/api/ui-state/commit-clear': ui_journal.commit_clear}[self.path]
                result = action(self.store.project_root, **data)
            elif self.path == '/api/gallery':
                from .gallery_state import save
                result = save(self.store.project_root, **data)
            elif self.path == '/api/result-reading/import-legacy':
                from .result_reading import import_legacy
                result = import_legacy(self.store.project_root, **data)
            elif self.path == '/api/result-reading':
                from .result_reading import mark
                result = mark(self.store.project_root, **data)
            elif self.path == '/api/overview':
                from .overview_state import save
                result = save(self.store.project_root, **data)
            elif self.path in ('/api/annotations/batch', '/api/changes/plan', '/api/changes/commit', '/api/candidates/plan', '/api/candidates/adopt', '/api/candidates/decision', '/api/stages/assemble', '/api/styles/propose', '/api/styles/confirm', '/api/styles/plan', '/api/styles/analyze', '/api/content/plan', '/api/content/commit', '/api/content/inputs'):
                from . import annotation_service, changes, candidates, stages, styles, content_ops, visual_styles
                action = {'/api/content/plan': content_ops.plan, '/api/content/commit': content_ops.commit, '/api/content/inputs': content_ops.inputs, '/api/annotations/batch': annotation_service.save,
                          '/api/changes/plan': changes.plan, '/api/changes/commit': changes.commit,
                          '/api/candidates/plan': candidates.plan, '/api/candidates/adopt': candidates.adopt,
                          '/api/candidates/decision': candidates.decide,
                          '/api/stages/assemble': stages.assemble,
                          '/api/styles/analyze': visual_styles.analyze, '/api/styles/propose': styles.propose, '/api/styles/confirm': styles.confirm, '/api/styles/plan': styles.plan}[self.path]
                result = action(self.store.project_root, **data)
            elif self.path in ('/api/icons/propose', '/api/icons/confirm', '/api/icons/plan', '/api/icons/preview', '/api/candidate-preview/request'):
                from . import icons, candidate_preview
                action = {'/api/icons/propose':icons.propose, '/api/icons/confirm':icons.confirm, '/api/icons/plan':icons.plan, '/api/icons/preview':icons.preview, '/api/candidate-preview/request':candidate_preview.request}[self.path]
                result = action(self.store.project_root, **data)
            elif self.path == '/api/text-ranges/validate':
                from .text_ranges import validate
                result = validate(self.store.project_root, **data)
            elif self.path == '/api/inputs/update':
                from .local_state import project_path
                result = service.inputs_update(project_path(self.store.project_root), **data)
            elif self.path=='/api/requests/freeze':
                from .generation import freeze
                result=freeze(self.store.project_root,**data)
            elif self.path=='/api/edit':result=editing.edit_page(self.store.project_root,**data)
            elif self.path=='/api/feedback':
                task=service.open_host_task(self.store,kind='repair',page_ids=[data['page_id']],instruction=data['instruction'],base_revision=data.get('base_revision'),page_hash=data.get('page_hash'))
                result={'status':'awaiting_host','task_id':task['task_id']}
            elif self.path=='/api/cancel':result=service.task_cancel(self.store.project_root,**data)
            elif self.path in ('/api/history/plan-restore','/api/history/commit-restore'):
                from . import restoration
                action=restoration.plan if self.path.endswith('plan-restore') else restoration.commit
                result=action(self.store.project_root,**data)
            elif self.path=='/api/restore':result=editing.restore(self.store.project_root,**data)
            elif self.path=='/api/check':
                from . import editing as editing_mod
                summary=editing_mod.check_summary(self.store,_editing_review_doc(self.store))
                result={'status':summary['status'],'reason':summary.get('reason'),
                        'missing_dimensions':summary['missing_dimensions'],
                        'stale':summary['stale']}
            elif self.path=='/api/exports':
                from . import exports
                from .operations import OperationError
                if set(data)-{'purpose','revision','export_id'}:
                    raise OperationError('invalid_export_request','body','only purpose, revision and export_id are accepted')
                result=exports.create(self.store.project_root,**data)
            elif self.path=='/api/export':
                import uuid
                data.setdefault('output_dir',str(self.store.project_root/'exports'/uuid.uuid4().hex[:12]))
                result=editing.export_project(self.store.project_root,**data)
            else:self._send_json({'error':'not found'},404);return
            self._send_json(result)
        except Exception as exc:
            if self.path.startswith(('/api/drafts/', '/api/ui-state', '/api/gallery', '/api/overview', '/api/text-ranges/', '/api/annotations/', '/api/changes/', '/api/candidates/', '/api/stages/', '/api/styles/', '/api/icons/', '/api/candidate-preview/', '/api/content/', '/api/export', '/api/history/')):
                self._send_error(exc)
                return
            from .store import ConflictError
            from .tasks import TaskConflict
            if isinstance(exc, TypedServiceError):
                self._send_json({'error': {'code':exc.error_code, 'message':exc.detail, 'field':exc.path,
                                  'next_action':NEXT_ACTIONS_BY_CODE.get(exc.error_code, 'read task status and the recovery playbook')}},
                                409 if exc.exit_code == 5 else 422)
                return
            if self.path == '/api/requests/freeze' and isinstance(exc, (ModelError, ConflictError, TaskConflict)):
                conflict = isinstance(exc, (ConflictError, TaskConflict))
                self._send_json({'error': {'code':'conflict' if conflict else 'invalid_input',
                                  'message':str(exc), 'field':getattr(exc, 'path', None),
                                  'next_action':'rebase or read new inputs' if conflict else 'fix the named field'}},
                                409 if conflict else 422)
                return
            self._send_json({'error':str(exc)},409 if isinstance(exc,(ConflictError,TaskConflict)) else 400)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if not self._local_host():
            self._send_json({'error':'loopback Host required'},403);return
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/exports/') or parsed.path == '/api/export-facts':
            from . import exports
            from .operations import OperationError
            try:
                query=parse_qs(parsed.query,keep_blank_values=True)
                if parsed.path=='/api/export-facts':
                    if set(query)-{'revision'} or any(len(v)!=1 for v in query.values()):
                        raise OperationError('invalid_export_request','query','one optional revision is accepted')
                    self._send_json(exports.describe(self.store.project_root,revision=query.get('revision',[None])[0]));return
                if parsed.query:raise OperationError('invalid_export_request','query','download URLs do not accept query parameters')
                parts=parsed.path.split('/')
                if len(parts)==4:
                    self._send_json(exports.show(self.store.project_root,export_id=parts[3]));return
                if len(parts)>=6 and parts[4]=='files':
                    filename=unquote('/'.join(parts[5:]))
                    data,name=exports.download(self.store.project_root,export_id=parts[3],filename=filename)
                    self._send_bytes(data,'application/octet-stream',download_name=name);return
                raise OperationError('export_file_not_found','url','use a returned export download URL',http_status=404)
            except Exception as exc:
                self._send_error(exc);return
        if parsed.path.startswith('/v2/') or parsed.path == '/v2':
            self._serve_v2(parsed.path)
            return
        if parsed.path.startswith('/api/content/sources/') or parsed.path.startswith('/api/content/lineage/'):
            try:
                from . import content_ops, operations
                is_source = parsed.path.startswith('/api/content/sources/')
                query = parse_qs(parsed.query, keep_blank_values=True)
                allowed = {'revision', 'locator', 'extract_sha256'} if is_source else {'revision'}
                if set(query) - allowed or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise operations.OperationError('invalid_input', 'query', 'use one nonempty value per supported source query field')
                fields = {key: value[0] for key, value in query.items()}
                result = content_ops.source(self.store.project_root, source_id=parsed.path.removeprefix('/api/content/sources/'), **fields) if is_source else content_ops.lineage(self.store.project_root, page_id=parsed.path.removeprefix('/api/content/lineage/'), **fields)
                self._send_json(result)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path == '/api/styles/references' or parsed.path.startswith('/api/styles/references/'):
            try:
                from . import visual_styles
                query=parse_qs(parsed.query,keep_blank_values=True)
                if set(query)-{'revision'} or any(len(v)!=1 or not v[0] for v in query.values()): visual_styles.fail('query','use one optional revision')
                rid=parsed.path.removeprefix('/api/styles/references/') if parsed.path != '/api/styles/references' else None
                self._send_json(visual_styles.listing(self.store.project_root,reference_id=rid,**{k:v[0] for k,v in query.items()}))
            except Exception as exc: self._send_error(exc)
            return
        if parsed.path == '/api/styles' or parsed.path.startswith('/api/styles/'):
            try:
                from . import styles, operations
                query = parse_qs(parsed.query, keep_blank_values=True)
                if set(query) - {'revision'} or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise operations.OperationError('invalid_input', 'query', 'use one optional nonempty revision')
                fields = {key: value[0] for key, value in query.items()}
                result = styles.listing(self.store.project_root, **fields) if parsed.path == '/api/styles' else styles.show(
                    self.store.project_root, recipe_id=parsed.path.removeprefix('/api/styles/'), **fields)
                self._send_json(result)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ('/api/icons/inspect', '/api/icons/catalog', '/api/icons/list', '/api/icons/catalog/file', '/api/candidate-preview/status', '/api/candidate-preview/file'):
            try:
                from . import icons, candidate_preview
                query = parse_qs(parsed.query)
                if any(len(v) != 1 for v in query.values()): raise ValueError('duplicate query parameter')
                fields = {k:v[0] for k,v in query.items()}
                if parsed.path == '/api/candidate-preview/file':
                    data, media = candidate_preview.file_bytes(self.store.project_root, **fields)
                    self._send_bytes(data, media)
                elif parsed.path == '/api/icons/catalog/file':
                    self._send_bytes(icons.catalog_asset_bytes(fields.get('asset_id'), fields.get('sha256')), 'image/svg+xml', immutable=True)
                else:
                    action = {'/api/icons/inspect':icons.inspect, '/api/icons/catalog':icons.catalog, '/api/icons/list':icons.listing, '/api/candidate-preview/status':candidate_preview.status}[parsed.path]
                    self._send_json(action(self.store.project_root, **fields))
            except Exception as exc: self._send_error(exc)
            return
        if parsed.path == '/api/candidates' or parsed.path.startswith('/api/candidates/'):
            try:
                from . import candidates, operations
                query = parse_qs(parsed.query, keep_blank_values=True)
                allowed = {'revision', 'page_id'} if parsed.path == '/api/candidates' else {'revision'}
                if set(query) - allowed or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise operations.OperationError('invalid_input', 'query', 'use one nonempty value for each supported query field')
                fields = {key: value[0] for key, value in query.items()}
                if parsed.path == '/api/candidates':
                    result = candidates.listing(self.store.project_root, **fields)
                else:
                    result = candidates.show(self.store.project_root, candidate_id=parsed.path.removeprefix('/api/candidates/'), **fields)
                self._send_json(result)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ('/api/annotations', '/api/changes') or parsed.path.startswith(('/api/operations/', '/api/changes/')):
            try:
                from . import annotation_service, changes, operations
                if parsed.path == '/api/annotations':
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    allowed = {'revision', 'page_id', 'layer', 'scope'}
                    if set(query) - allowed or any(len(value) != 1 or not value[0] for value in query.values()):
                        raise operations.OperationError('invalid_input', 'query', 'use one nonempty value for each supported query field')
                    self._send_json(annotation_service.list_annotations(self.store.project_root,
                                                                        **{key: value[0] for key, value in query.items()}))
                    return
                if parsed.query:
                    raise operations.OperationError('invalid_input', 'query', 'this read takes no query parameters')
                if parsed.path == '/api/changes':
                    result = changes.list_changes(self.store.project_root)
                elif parsed.path.startswith('/api/operations/'):
                    result = operations.show(self.store.project_root, operation_id=parsed.path.removeprefix('/api/operations/'))
                elif parsed.path.endswith('/handoff'):
                    result = changes.handoff(self.store.project_root, change_id=parsed.path[len('/api/changes/'):-len('/handoff')])
                else:
                    self._send_json({'error': 'not found'}, 404)
                    return
                self._send_json(result)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ('/api/gallery', '/api/overview', '/api/result-reading', '/api/thumbnails', '/api/thumbnail-file'):
            try:
                from . import gallery_state, thumbnails
                query = parse_qs(parsed.query, keep_blank_values=True)
                if any(len(values) != 1 for values in query.values()):
                    raise thumbnails.ThumbnailError('query', 'provide one value for each parameter')
                if parsed.path == '/api/result-reading':
                    from .result_reading import get
                    if query: raise ValueError('reading state takes no query parameters')
                    self._send_json(get(self.store.project_root))
                elif parsed.path == '/api/overview':
                    from .overview_state import get
                    if set(query) != {'revision'} or not query['revision'][0]:
                        raise thumbnails.ThumbnailError('query', 'overview state requires one fixed revision')
                    self._send_json(get(self.store.project_root, revision=query['revision'][0]))
                elif parsed.path == '/api/gallery':
                    if query:
                        raise thumbnails.ThumbnailError('query', 'gallery state takes no query parameters')
                    thumbnails.activate(self.store.project_root)
                    self._send_json(gallery_state.get(self.store.project_root))
                elif parsed.path == '/api/thumbnail-file':
                    if set(query) != {'cache_key'}:
                        raise thumbnails.ThumbnailError('query', 'thumbnail file requires one derived cache identity')
                    data, media = thumbnails.file_bytes(self.store.project_root, query['cache_key'][0])
                    self._send_bytes(data, media, immutable=True)
                else:
                    if set(query) - {'path', 'sha256', 'variant', 'retry'} or not {'path', 'sha256'} <= set(query):
                        raise thumbnails.ThumbnailError('query', 'thumbnail requests require a verified object reference')
                    if query.get('retry', ['0'])[0] not in ('0', '1'):
                        raise thumbnails.ThumbnailError('retry', 'retry must be 0 or 1')
                    result = thumbnails.request(self.store.project_root,
                        ref={'path': query['path'][0], 'sha256': query['sha256'][0]},
                        variant=query.get('variant', [thumbnails.VARIANT])[0], retry=query.get('retry', ['0'])[0] == '1')
                    self._send_json(result, 202 if result['status'] in ('queued', 'running', 'busy') else 200)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ('/api/project', '/api/drafts', '/api/ui-state', '/api/inputs', '/api/compose/handoff') or parsed.path.startswith('/api/drafts/'):
            try:
                from . import ui_journal, service
                if parsed.path == '/api/project':
                    result = ui_journal.project_info(self.store.project_root, server_capabilities=UI_CAPABILITIES)
                elif parsed.path == '/api/drafts':
                    result = ui_journal.list_drafts(self.store.project_root)
                elif parsed.path == '/api/ui-state':
                    result = {'record': ui_journal.read_position(self.store.project_root)}
                elif parsed.path == '/api/inputs':
                    result = service.inputs_show(self.store.project_root)
                elif parsed.path == '/api/compose/handoff':
                    from .launcher import compose_handoff
                    result = compose_handoff(self.store.project_root)
                else:
                    result = ui_journal.get(self.store.project_root, parsed.path.removeprefix('/api/drafts/'))
                self._send_json(result)
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ("/api/view", "/api/view/summary", "/api/workbench", "/api/tasks", "/api/reviews", "/api/content-plan") or parsed.path.startswith(("/api/pages/", "/api/requests/", "/api/attempts/", "/api/tasks/", "/api/actions/")):
            self._read_projection(parsed)
            return
        if parsed.path=='/api/session':
            self._send_json({'token':self.write_token});return
        if parsed.path=='/api/history':
            from .editing import history
            try:
                params = parse_qs(parsed.query, keep_blank_values=True)
                if set(params) - {'revision', 'page_id', 'layer', 'limit', 'cursor', 'related_only'} or any(len(values) != 1 or not values[0] for values in params.values()):
                    raise ValueError('use one nonempty value per supported history parameter')
                if params.get('related_only', ['1'])[0] not in ('0', '1'):
                    raise ValueError('related_only must be 0 or 1')
                from .operations import OperationError
                limit_value = params.get('limit', [None])[0]
                try:
                    limit = int(limit_value) if limit_value is not None else None
                except ValueError:
                    raise OperationError('invalid_input', 'limit', 'limit must be an integer') from None
                self._send_json(history(self.store.project_root, revision=params.get('revision', [None])[0], page_id=params.get('page_id', [None])[0], layer=params.get('layer', [None])[0], limit=limit, cursor=params.get('cursor', [None])[0], related_only=params.get('related_only', ['1'])[0] != '0'))
            except Exception as exc:
                self._send_error(exc)
            return
        if parsed.path in ("/", "/index.html"):
            # the v2 entry content is safe to serve on any path: its assets
            # use absolute /v2/ URLs
            self._serve_v2("/v2/")
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok", **self.runtime_state,
                             "project_identity": _project_identity(self.store.project_root),
                             "ui_available": (self.static_dir / 'v2' / 'index.html').is_file(),
                             "ui_capabilities": list(UI_CAPABILITIES)})
            return
        if parsed.path == "/api/file":
            query = parse_qs(parsed.query)
            path_value = (query.get("path") or [""])[0]
            if not path_value.startswith(".deckmaster/objects/"):
                self._send_json({"error": "only .deckmaster/objects paths are served"}, 403)
                return
            try:
                data, media = view_mod.artifact_bytes(self.store, {"path": path_value, "sha256": (query.get("sha256") or [""])[0]})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": workbench_mod.object_error()}, 404)
                return
            self._send_bytes(data, media)
            return
        self._send_json({"error": "not found"}, 404)

    def _serve_v2(self, path):
        from .local_state import safe_path
        name = 'index.html' if path in ('/v2', '/v2/') else path.removeprefix('/v2/')
        try:
            target = safe_path(self.static_dir, 'v2', *name.split('/'))
            media = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                     '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.svg': 'image/svg+xml'}.get(target.suffix)
            if not media or not target.is_file():
                raise FileNotFoundError
            self._send_bytes(target.read_bytes(), media)
        except (ValueError, RuntimeError, OSError):
            self._send_json({'error': {'code': 'ui_unavailable', 'message': 'workbench UI resource is not installed'}}, 404)

    def _read_projection(self, parsed):
        """All related GETs share one revision contract and sanitized errors."""
        query = parse_qs(parsed.query, keep_blank_values=True)
        try:
            revisions = query.get("revision", [])
            if len(revisions) > 1:
                raise workbench_mod.ReadModelError("invalid_revision", "revision", "provide one revision", http_status=400)
            revision = revisions[0] if revisions else None
            project = self.store.project_root
            reading=None;reading_unavailable=False
            if 'personal' in query:
                if query['personal']!=['1']:raise ValueError('personal must be 1')
                from .result_reading import get
                if parsed.path not in ('/api/view/summary','/api/workbench') and 'reading_etag' not in query:
                    raise ValueError('personal lists require reading_etag from summary or reading state')
                if 'reading_etag' in query and len(query['reading_etag'])!=1:raise ValueError('provide one reading_etag')
                try:reading=get(project,expected_etag=query.get('reading_etag',[None])[0])
                except (TypedServiceError,ModelError,OSError,ValueError,KeyError,TypeError):
                    if parsed.path not in ('/api/view/summary','/api/workbench') or 'reading_etag' in query:raise
                    reading_unavailable=True
            if parsed.path == "/api/view":
                payload = view_mod.project_view(project, revision=revision)
            elif parsed.path in ("/api/view/summary", "/api/workbench"):
                result=workbench_mod.workbench_summary_json(project, revision=revision, reading=reading)
                if reading_unavailable:
                    payload=json.loads(result);payload['reading_unavailable']=True;self._send_json(payload)
                else:self._send_json_bytes(result)
                return
            elif parsed.path.startswith('/api/actions/'):
                parts = parsed.path.split('/')
                if len(parts) != 5 or parts[-1] != 'targets':
                    raise workbench_mod.ReadModelError('action_not_found', 'action_id', 'unknown action endpoint', http_status=404)
                if set(query) - {'revision', 'limit', 'offset', 'personal', 'reading_etag'} or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise workbench_mod.ReadModelError('invalid_action_query', 'query', 'use one value per supported query field', http_status=400)
                try:
                    limit, offset = int(query.get('limit', ['30'])[0]), int(query.get('offset', ['0'])[0])
                except ValueError as exc:
                    raise workbench_mod.ReadModelError('invalid_action_query', 'pagination', 'pagination must use integers', http_status=400) from exc
                payload = workbench_mod.action_targets(project, parts[3], revision=revision, limit=limit, offset=offset, reading=reading)
            elif parsed.path == "/api/tasks":
                from . import run_desk
                fields = ('limit', 'offset', 'change_id', 'status', 'attention')
                if any(field in query for field in fields):
                    if any(len(query.get(field, [])) > 1 for field in fields):
                        raise run_desk.RunReadError('invalid_run_query', 'query', 'provide each filter once', http_status=400)
                    try:
                        limit = int(query.get('limit', ['30'])[0]); offset = int(query.get('offset', ['0'])[0])
                    except ValueError as exc:
                        raise run_desk.RunReadError('invalid_run_query', 'pagination', 'pagination must use integers', http_status=400) from exc
                    attention = query.get('attention', ['0'])[0]
                    if attention not in ('0', '1'):
                        raise run_desk.RunReadError('invalid_run_query', 'attention', 'attention must be 0 or 1', http_status=400)
                    payload = run_desk.listing(project, revision=revision, limit=limit, offset=offset,
                        change_id=query.get('change_id', [None])[0], status=query.get('status', [None])[0], attention=attention == '1', reading=reading)
                else:
                    payload = workbench_mod.tasks_view(project, revision=revision)
            elif parsed.path.startswith('/api/tasks/'):
                from .run_desk import detail
                payload = detail(project, task_id=parsed.path.removeprefix('/api/tasks/'), revision=revision)
            elif parsed.path == "/api/content-plan":
                from .content_plan import show
                payload = show(project, revision=revision)
            elif parsed.path.startswith(("/api/requests/", "/api/attempts/")):
                from .generation import show
                parts = parsed.path.split("/")
                if len(parts) != 4:
                    self._send_json({"error": "not found"}, 404)
                    return
                payload = show(project, revision=revision, **{"request_id" if parts[2] == "requests" else "attempt_id": parts[3]})
            elif parsed.path == "/api/reviews":
                page_filter = (query.get("page_id") or [None])[0]
                view = view_mod.project_view(project, revision=revision)
                payload = {"project_id": view["project_id"], "revision_id": view["revision_id"],
                           "reviews": [r for r in view.get("reviews") or []
                                       if not page_filter or page_filter in (r.get("page_ids") or [])]}
            else:
                parts = parsed.path.split("/")
                if len(parts) == 5 and parts[-1] == "lineage":
                    payload = workbench_mod.page_lineage(project, parts[3], revision=revision)
                elif len(parts) == 4:
                    payload = workbench_mod.page_view(project, parts[3], revision=revision)
                else:
                    self._send_json({"error": "not found"}, 404)
                    return
            self._send_json(payload)
        except workbench_mod.ReadModelError as exc:
            self._send_json(exc.payload(), exc.http_status)
        except TypedServiceError as exc:
            self._send_json({'error': {'code':exc.error_code, 'message':exc.detail, 'field':exc.path,
                              'next_action':NEXT_ACTIONS_BY_CODE.get(exc.error_code, 'read task status and the recovery playbook')}},
                            404 if exc.error_code == 'generation_object_not_found' else 409 if exc.error_code=='local_state_conflict' else 422)
        except workbench_mod.READ_FAILURES:
            exc = workbench_mod.ReadModelError("project_unavailable", "project", "project snapshot is not readable", http_status=422)
            self._send_json(exc.payload(), exc.http_status)


class WorkbenchServer:
    def __init__(self, project_dir: Path | str) -> None:
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.store = Store(self.project_dir)
        self.httpd = None
        self.thread = None
        self.port = None

    def start(self) -> str:
        from . import local_runtime as runtime
        from .local_state import local_lock, safe_path
        self.desc = runtime.descriptor(project=self.project_dir)
        state_path = self.desc['state_path']
        with local_lock(safe_path(state_path.parent, state_path.name + '.start.lock')):
            state = runtime.read_state(self.desc)
            if runtime.healthy(state, self.desc):
                return state['url']
            self.httpd, self.state = runtime.bind_server(self.desc)
            self.port = self.state['port']
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            try:
                if not runtime.healthy(self.state, self.desc):
                    raise ServiceUnavailable('service', 'in-process service health check failed')
                runtime.publish(self.desc, self.state)
            except BaseException:
                self.stop()
                raise
            return self.state['url']

    def stop(self) -> None:
        if self.httpd:
            from .local_runtime import clear_own_state
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join(timeout=2)
            clear_own_state(self.desc, self.state['instance_id'])
            self.httpd = None


def _static_dir() -> Path:
    import importlib.resources

    static_root = importlib.resources.files("deck_master").joinpath("resources/static")
    # importlib.resources may return a MultiplexedPath/Traversable; fall back to the
    # packaged directory when it is a real filesystem path (editable install).
    candidate = Path(str(static_root))
    if candidate.is_dir():
        return candidate
    raise RuntimeError("static resources not available in this installation")


def open_view(project_dir: Path | str, *, open_browser: bool = True, ui: str | None = None) -> dict:
    """``view --open``: reuse a healthy service, spawn a detached one if needed.

    The server runs in its own process (``python -m deck_master.view_server``),
    so it keeps serving after the CLI exits. Startup waits bounded on a health
    check; failures return ``unavailable`` with the real reason (spec 09.5).
    The v2 workbench is the only supported UI entry.
    """
    if ui not in (None, "v2"):
        return {"review_url": None, "view_status": "unavailable",
                "detail": "only the v2 workbench UI is available", "ui": ui}
    project_dir = Path(project_dir).expanduser().resolve()
    if not (project_dir / ".deckmaster" / "current.json").is_file():
        return {
            "review_url": None,
            "view_status": "unavailable",
            "detail": "project has no current Document; run create first",
            "ui": ui,
        }
    try:
        state = ensure_service(project_dir)
    except ServiceUnavailable as exc:
        return {"review_url": None, "view_status": "unavailable", "detail": str(exc), "ui": ui}
    except Exception as exc:  # noqa: BLE001 - spawn/health failures surface as a real reason
        return {"review_url": None, "view_status": "unavailable", "detail": f"view service failed: {exc}", "ui": ui}
    # same incomplete-install guard as the launcher: never point the browser
    # at a /v2/ entry the installed static tree cannot serve
    ui_available = (_static_dir() / "v2" / "index.html").is_file()
    if not ui_available:
        return {"review_url": state["url"], "view_status": "core_ready_ui_unavailable",
                "detail": "the v2 workbench UI is not present in this installation; reinstall the complete workbench package",
                "port": state["port"], "pid": state.get("pid"),
                "reused": state.get("reused", False), "ui": ui}
    url = state["url"] + "v2/"
    if open_browser:
        opened = False
        try:
            opened = bool(webbrowser.open(url, new=2))
        except Exception:  # noqa: BLE001 - no browser on this host
            opened = False
        if not opened:
            return {
                "review_url": url,
                "view_status": "available",
                "detail": "no browser could be opened; use the local URL above",
                "port": state["port"],
                "pid": state.get("pid"),
                "reused": state.get("reused", False),
                "ui": ui,
            }
    return {
        "review_url": url,
        "view_status": "opened" if open_browser else "available",
        "port": state["port"],
        "pid": state.get("pid"),
        "reused": state.get("reused", False),
        "ui": ui,
    }


def ensure_service(project_dir: Path, *, port=0) -> dict:
    from .local_runtime import descriptor, ensure
    return ensure(descriptor(project=project_dir), port=port)


def _health_ok(url: str, project_dir: Path | str) -> bool:
    from .local_runtime import descriptor, healthy, read_state
    try:
        desc = descriptor(project=project_dir)
        state = read_state(desc)
        return bool(state and state.get("url") == url and healthy(state, desc))
    except (ValueError, RuntimeError, OSError):
        return False


def stop_service(project_dir: Path | str) -> dict:
    from .local_runtime import descriptor, stop
    if not read_active_service(Path(project_dir).expanduser()):
        return {"view_status": "not_running", "review_url": None}
    result = stop(descriptor(project=project_dir))
    return {"view_status": result["status"], "review_url": None}


def service_status(project_dir: Path | str) -> dict:
    state = read_active_service(Path(project_dir).expanduser())
    if not state:
        return {"view_status": "not_running", "review_url": None}
    alive = _health_ok(state.get("url"), project_dir)
    return {"view_status": "running" if alive else "stale",
            "review_url": state.get("url") if alive else None, "port": state.get("port")}
