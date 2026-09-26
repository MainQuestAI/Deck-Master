"""Identity-checked loopback services; child binds before publishing metadata."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from http.server import ThreadingHTTPServer

from . import __version__
from .local_state import LocalStateError, local_lock, read_json, safe_path, write_json

PROTOCOL = "workbench-service.v1"
# Capture this process's implementation at import, not on each health request.
# An editable checkout can change while an older process is still serving.
_PACKAGE = Path(__file__).parent
BUILD_ID = hashlib.sha256(b"".join(
    str(p.relative_to(_PACKAGE)).encode() + b"\0" + p.read_bytes()
    for p in sorted(_PACKAGE.rglob("*"))
    if p.is_file() and p.suffix in (".py", ".json", ".html", ".css", ".js")
)).hexdigest()
HEALTH_KEYS = ("role", "identity", "instance_id", "pid", "port", "protocol_version", "service_version", "build_id")


class ServiceUnavailable(LocalStateError):
    error_code = "service_unavailable"
    exit_code = 4


class PortConflict(ServiceUnavailable):
    error_code = "port_conflict"
    exit_code = 5


def identity(path):
    return hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()


def descriptor(*, project=None, registry=None):
    if (project is None) == (registry is None):
        raise LocalStateError("service", "choose one project or registry")
    if project is not None:
        from .local_state import project_path
        target = project_path(project)
        state = safe_path(target, ".deckmaster", "view.json")
        role = "project"
    else:
        from .registry import registry_path
        target = registry_path(registry)
        state = safe_path(target.parent, target.name + ".runtime.json")
        role = "launcher"
    return {"role": role, "identity": identity(target), "target": target, "state_path": state}


def read_state(desc):
    try:
        return read_json(desc["state_path"])
    except (LocalStateError, OSError):
        return None


def healthy(state, desc):
    if not isinstance(state, dict) or not all(key in state for key in HEALTH_KEYS):
        return False
    expected = {"role": desc["role"], "identity": desc["identity"], "protocol_version": PROTOCOL,
                "service_version": __version__, "build_id": BUILD_ID}
    if any(state.get(key) != value for key, value in expected.items()):
        return False
    port = state.get("port")
    if (type(port) is not int or not 0 < port < 65536 or type(state.get("pid")) is not int
            or state["pid"] <= 0 or not isinstance(state.get("instance_id"), str)
            or len(state["instance_id"]) != 32 or state.get("url") != f"http://127.0.0.1:{port}/"):
        return False
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.7)
    try:
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        payload = json.loads(response.read(16_385))
        return response.status == 200 and payload.get("status") == "ok" and all(
            payload.get(key) == state[key] for key in HEALTH_KEYS)
    except (OSError, ValueError, http.client.HTTPException, AttributeError):
        return False
    finally:
        connection.close()


def _metadata_lock(desc):
    return local_lock(safe_path(desc["state_path"].parent, desc["state_path"].name + ".lock"))


def clear_own_state(desc, instance_id):
    with _metadata_lock(desc):
        state = read_state(desc)
        if state and state.get("instance_id") == instance_id:
            desc["state_path"].unlink(missing_ok=True)


def bind_server(desc, *, port=0, instance_id=None):
    from .web import WorkbenchHandler, _static_dir
    from .store import Store
    attrs = {"static_dir": _static_dir(), "write_token": secrets.token_urlsafe(32)}
    if desc["role"] == "project":
        attrs["store"] = Store(desc["target"])
        handler_class = WorkbenchHandler
    else:
        from .launcher import LauncherHandler
        attrs["registry_path"] = desc["target"]
        handler_class = LauncherHandler
    handler = type("BoundHandler", (handler_class,), attrs)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        if exc.errno in (48, 98, 10048):
            raise PortConflict("port", "requested port is in use; select 0 or another port") from exc
        raise ServiceUnavailable("service", "loopback service could not bind") from exc
    port = server.server_port
    state = {"role": desc["role"], "identity": desc["identity"],
             "instance_id": instance_id or secrets.token_hex(16), "pid": os.getpid(), "port": port,
             "url": f"http://127.0.0.1:{port}/", "protocol_version": PROTOCOL,
             "service_version": __version__, "build_id": BUILD_ID}
    handler.runtime_state = state
    return server, state


def publish(desc, state):
    with _metadata_lock(desc):
        write_json(desc["state_path"], state)


def _check_port(port):
    if type(port) is not int or not 0 <= port <= 65535:
        raise LocalStateError("port", "port must be between 0 and 65535")


def ensure(desc, *, port=0):
    _check_port(port)
    # Serializes launch decisions, not HTTP requests or Document operations.
    startup_lock = safe_path(desc["state_path"].parent, desc["state_path"].name + ".start.lock")
    with local_lock(startup_lock):
        state = read_state(desc)
        if healthy(state, desc):
            if port and port != state["port"]:
                raise PortConflict("port", "this service is already running on a different port; stop it first")
            return {**state, "reused": True}
        instance = secrets.token_hex(16)
        command = [sys.executable, "-m", "deck_master.view_server", "--port", str(port),
                   "--instance-id", instance, "--" + ("project" if desc["role"] == "project" else "registry"),
                   str(desc["target"])]
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = str(_PACKAGE.parent) + (os.pathsep + child_env["PYTHONPATH"] if child_env.get("PYTHONPATH") else "")
        log = safe_path(desc["state_path"].parent, desc["state_path"].name + ".log")
        with log.open("ab") as stream:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                       env=child_env, start_new_session=True)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            state = read_state(desc)
            if state and state.get("instance_id") == instance and healthy(state, desc):
                return {**state, "reused": False}
            if process.poll() is not None:
                clear_own_state(desc, instance)
                error = PortConflict if process.returncode == 5 else ServiceUnavailable
                raise error("service", "service could not start; inspect its local runtime log")
            time.sleep(0.05)
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        clear_own_state(desc, instance)
        raise ServiceUnavailable("service", "service did not become healthy within 8 seconds; retry or inspect its local log")


def stop(desc):
    # Never signal a PID from stale metadata or a service of another identity.
    startup_lock = safe_path(desc["state_path"].parent, desc["state_path"].name + ".start.lock")
    with local_lock(startup_lock):
        state = read_state(desc)
        if not healthy(state, desc):
            return {"status": "not_running", "role": desc["role"]}
        if state["pid"] == os.getpid():
            raise ServiceUnavailable("service", "in-process services must be stopped by their owner")
        try:
            os.kill(state["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not healthy(state, desc):
                clear_own_state(desc, state["instance_id"])
                return {"status": "stopped", "role": desc["role"]}
            time.sleep(0.05)
        raise ServiceUnavailable("service", "service has not confirmed shutdown; its metadata is retained")
