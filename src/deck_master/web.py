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
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import view as view_mod
from .store import Store
from . import workbench as workbench_mod
from .errors import TypedServiceError, NEXT_ACTIONS_BY_CODE
from .models import ModelError

STATE_FILE = "view.json"


def _editing_review_doc(store):
    return store.load_document()


class ServiceUnavailable(RuntimeError):
    """The read-only service could not start or become healthy in time."""


def _project_identity(project_dir):
    return hashlib.sha256(str(Path(project_dir).resolve()).encode()).hexdigest()

def _state_path(project_dir: Path) -> Path:
    return project_dir / ".deckmaster" / STATE_FILE


def read_active_service(project_dir: Path) -> dict | None:
    path = _state_path(project_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return None


def _write_state(project_dir: Path, state: dict) -> None:
    path = _state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n")


def _port_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class WorkbenchHandler(BaseHTTPRequestHandler):
    store: Store
    static_dir: Path
    write_token: str

    def log_message(self, fmt, *args):  # quiet default
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, media: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", media)
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

    def do_POST(self):
        origin=self.headers.get('Origin')
        allowed=(f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        if not self._local_host() or origin not in allowed or not secrets.compare_digest(self.headers.get('X-Deck-Token',''),self.write_token):
            self._send_json({'error':'same-origin session token required'},403);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2_000_000:raise ValueError('invalid request size')
            data=json.loads(self.rfile.read(length))
            from . import editing, service
            if self.path=='/api/requests/freeze':
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
        if parsed.path in ("/api/view", "/api/view/summary", "/api/workbench", "/api/tasks", "/api/reviews") or parsed.path.startswith(("/api/pages/", "/api/requests/", "/api/attempts/")):
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
            self._send_json({"status": "ok", "project_identity": _project_identity(self.store.project_root)})
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
        state = read_active_service(self.project_dir)
        if state and _port_alive(int(state["port"])) and _health_ok(state["url"], self.project_dir):
            return state["url"]  # same-project URL reuse (spec 09.5.3)
        self.port = _free_port()
        handler = type(
            "BoundHandler",
            (WorkbenchHandler,),
            {"store": self.store, "static_dir": _static_dir(), "write_token": secrets.token_urlsafe(32)},
        )
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        url = f"http://127.0.0.1:{self.port}/"
        _write_state(self.project_dir, {"port": self.port, "url": url})
        return url

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
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


def ensure_service(project_dir: Path) -> dict:
    """Reuse a healthy active service, or spawn a detached one and wait for it."""
    existing = read_active_service(project_dir)
    if existing and _port_alive(int(existing["port"])) and _health_ok(existing["url"], project_dir):
        return {**existing, "reused": True}
    port = _free_port()
    log_path = project_dir / ".deckmaster" / "view-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    import os
    import subprocess
    import sys
    import time

    child_env = dict(os.environ)

    import deck_master

    package_root = Path(deck_master.__file__).resolve().parents[1]
    previous = os.environ.get("PYTHONPATH")
    child_env["PYTHONPATH"] = str(package_root) + (os.pathsep + previous if previous else "")
    log_handle = open(log_path, "ab")
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "deck_master.view_server",
                "--project",
                str(project_dir),
                "--port",
                str(port),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
            env=child_env,
            start_new_session=True,
        )
    finally:
        log_handle.close()
    url = f"http://127.0.0.1:{port}/"
    _write_state(project_dir, {"port": port, "url": url, "pid": process.pid})
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if process.poll() is not None:
            raise ServiceUnavailable(
                f"view server exited early with code {process.poll()}; see {log_path}"
            )
        if _port_alive(port) and _health_ok(url, project_dir):
            return {"port": port, "url": url, "pid": process.pid, "reused": False}
        time.sleep(0.1)
    process.terminate()
    raise ServiceUnavailable(
        f"view server did not become healthy within 5s; see {log_path}"
    )


def _health_ok(url: str, project_dir: Path | str) -> bool:
    import json as _json
    import urllib.request

    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=1.5) as response:
            payload = _json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok" and payload.get("project_identity") == _project_identity(project_dir)
    except Exception:  # noqa: BLE001
        return False


def stop_service(project_dir: Path | str) -> dict:
    """Terminate the detached view server recorded for this project."""
    import os
    import signal

    state = read_active_service(Path(project_dir).expanduser())
    if not state:
        return {"view_status": "not_running", "review_url": None}
    pid = state.get("pid")
    stopped = False
    if pid and _health_ok(state["url"], project_dir):
        try:
            os.kill(int(pid), signal.SIGTERM)
            stopped = True
        except (ProcessLookupError, PermissionError):
            stopped = False
    _write_state(Path(project_dir).expanduser(), {"port": state["port"], "url": state["url"], "pid": pid, "stopped": stopped})
    return {"view_status": "stopped" if stopped else "not_running", "review_url": None}


def service_status(project_dir: Path | str) -> dict:
    project_dir = Path(project_dir).expanduser()
    state = read_active_service(project_dir)
    if not state:
        return {"view_status": "not_running", "review_url": None}
    alive = _port_alive(int(state["port"])) and _health_ok(state["url"], project_dir)
    return {
        "view_status": "running" if alive else "stale",
        "review_url": state["url"] if alive else None,
        "port": state["port"],
    }
