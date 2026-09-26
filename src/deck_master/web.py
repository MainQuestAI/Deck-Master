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
from urllib.parse import parse_qs, urlparse

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


class WorkbenchHandler(BaseHTTPRequestHandler):
    store: Store
    static_dir: Path
    write_token: str
    runtime_state: dict

    def log_message(self, fmt, *args):  # quiet default
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, media: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", media)
        self.send_header("Cache-Control", "no-cache")
        # One Content-Security-Policy header: sandboxed isolation for SVG,
        # the default self-only policy for everything else.
        if media == "image/svg+xml":
            self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'")
        else:
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
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
            data=self._read_json_body()
            from .samples import sample_info
            sample = sample_info(self.store.project_root)
            if sample and sample['readonly'] and self.path not in ('/api/ui-state',):
                self._send_json({'error': {'code': 'sample_readonly', 'message': 'this synthetic example is read-only; create your own project'}}, 403)
                return
            from . import editing, service
            if self.path in ('/api/drafts/save', '/api/drafts/import', '/api/drafts/recovery', '/api/ui-state'):
                from . import ui_journal
                action = {'/api/drafts/save': ui_journal.save, '/api/drafts/import': ui_journal.import_recovery,
                          '/api/drafts/recovery': ui_journal.recovery_file, '/api/ui-state': ui_journal.save_position}[self.path]
                result = action(self.store.project_root, **data)
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
            elif self.path=='/api/restore':result=editing.restore(self.store.project_root,**data)
            elif self.path=='/api/check':
                from . import editing as editing_mod
                summary=editing_mod.check_summary(self.store,_editing_review_doc(self.store))
                result={'status':summary['status'],'reason':summary.get('reason'),
                        'missing_dimensions':summary['missing_dimensions'],
                        'stale':summary['stale']}
            elif self.path=='/api/export':
                import uuid
                data.setdefault('output_dir',str(self.store.project_root/'exports'/uuid.uuid4().hex[:12]))
                result=editing.export_project(self.store.project_root,**data)
            else:self._send_json({'error':'not found'},404);return
            self._send_json(result)
        except Exception as exc:
            if self.path.startswith(('/api/drafts/', '/api/ui-state')):
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
        if parsed.path.startswith('/v2/') or parsed.path == '/v2':
            self._serve_v2(parsed.path)
            return
        if parsed.path in ('/api/project', '/api/drafts', '/api/ui-state', '/api/inputs', '/api/compose/handoff') or parsed.path.startswith('/api/drafts/'):
            try:
                from . import ui_journal, service
                if parsed.path == '/api/project':
                    result = ui_journal.project_info(self.store.project_root)
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
        if parsed.path in ("/api/view", "/api/view/summary", "/api/workbench", "/api/tasks", "/api/reviews", "/api/content-plan") or parsed.path.startswith(("/api/pages/", "/api/requests/", "/api/attempts/")):
            self._read_projection(parsed)
            return
        if parsed.path=='/api/session':
            self._send_json({'token':self.write_token});return
        if parsed.path=='/api/history':
            from .editing import history
            self._send_json(history(self.store.project_root));return
        if parsed.path in ("/", "/index.html"):
            self._send_bytes(
                (self.static_dir / "index.html").read_bytes(), "text/html; charset=utf-8"
            )
            return
        if parsed.path == "/style.css":
            self._send_bytes((self.static_dir / "style.css").read_bytes(), "text/css; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._send_bytes((self.static_dir / "app.js").read_bytes(), "text/javascript; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok", **self.runtime_state,
                             "project_identity": _project_identity(self.store.project_root),
                             "ui_available": (self.static_dir / 'v2' / 'index.html').is_file()})
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
                     '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2'}.get(target.suffix)
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
            if parsed.path == "/api/view":
                payload = view_mod.project_view(project, revision=revision)
            elif parsed.path in ("/api/view/summary", "/api/workbench"):
                payload = workbench_mod.workbench_summary(project, revision=revision)
            elif parsed.path == "/api/tasks":
                payload = workbench_mod.tasks_view(project, revision=revision)
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
                            404 if exc.error_code == 'generation_object_not_found' else 422)
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


def open_view(project_dir: Path | str, *, open_browser: bool = True) -> dict:
    """``view --open``: reuse a healthy service, spawn a detached one if needed.

    The server runs in its own process (``python -m deck_master.view_server``),
    so it keeps serving after the CLI exits. Startup waits bounded on a health
    check; failures return ``unavailable`` with the real reason (spec 09.5).
    """
    project_dir = Path(project_dir).expanduser().resolve()
    if not (project_dir / ".deckmaster" / "current.json").is_file():
        return {
            "review_url": None,
            "view_status": "unavailable",
            "detail": "project has no current Document; run create first",
        }
    try:
        state = ensure_service(project_dir)
    except ServiceUnavailable as exc:
        return {"review_url": None, "view_status": "unavailable", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - spawn/health failures surface as a real reason
        return {"review_url": None, "view_status": "unavailable", "detail": f"view service failed: {exc}"}
    if open_browser:
        opened = False
        try:
            opened = bool(webbrowser.open(state["url"], new=2))
        except Exception:  # noqa: BLE001 - no browser on this host
            opened = False
        if not opened:
            return {
                "review_url": state["url"],
                "view_status": "available",
                "detail": "no browser could be opened; use the local URL above",
                "port": state["port"],
                "pid": state.get("pid"),
                "reused": state.get("reused", False),
            }
    return {
        "review_url": state["url"],
        "view_status": "opened" if open_browser else "available",
        "port": state["port"],
        "pid": state.get("pid"),
        "reused": state.get("reused", False),
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
