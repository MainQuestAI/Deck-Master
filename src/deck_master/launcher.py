"""Project launcher and handoff entrypoints. No browser-side model executor."""
from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import sys
from urllib.parse import urlparse
import webbrowser

from . import local_runtime as runtime, registry
from .local_state import LocalStateError, project_path
from .snapshots import load_snapshot
from .store import Store
from .web import WorkbenchHandler, _static_dir


def open_workbench(*, project=None, registry_file=None, ui="v2", port=0, open_browser=True, stop=False):
    if ui not in ("v2", "legacy") or (ui == "legacy" and project is None):
        raise LocalStateError("ui", "legacy UI requires an explicit project")
    runtime._check_port(port)
    desc = runtime.descriptor(project=project) if project else runtime.descriptor(registry=registry.registry_path(registry_file))
    if stop:
        return runtime.stop(desc)
    entry = registry.register(registry_file, project)["project"] if project else None
    state = runtime.ensure(desc, port=port)
    available = ui == "legacy" or (_static_dir() / "v2" / "index.html").is_file()
    url = state["url"] + ("v2/" if ui == "v2" else "")
    opened = False
    if open_browser and available:
        try:
            opened = bool(webbrowser.open(url, new=2))
        except Exception:
            pass
    return {**state, "url": url, "mode": ui, "project_id": entry["project_id"] if entry else None,
            "status": "available" if available else "core_ready_ui_unavailable",
            "ui_available": available, "browser_opened": opened,
            "host_execution": "handoff_required"}


def pick_directory():
    if sys.platform != "darwin":
        return {"status": "manual_path_required", "path": None}
    # Fixed native script, no interpolated user strings and no shell.
    script = 'try\nPOSIX path of (choose folder with prompt "选择 Deck Master 项目目录")\non error number -128\nreturn ""\nend try'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
    if result.returncode:
        return {"status": "manual_path_required", "path": None}
    selected = result.stdout.strip()
    return {"status": "selected" if selected else "cancelled", "path": str(Path(selected).resolve()) if selected else None}


def compose_handoff(project):
    """Read the one eligible compose task. Never dispatch a duplicate or run it."""
    from . import tasks
    store = Store(project_path(project))
    doc = load_snapshot(store)
    eligible = []
    for ref in doc["tasks"]:
        task = store.read_object_json(ref)
        if task.get("kind") == "compose" and task.get("status") in ("awaiting_host", "running") and tasks.task_inputs_current(store, doc, task):
            eligible.append(task)
    if len(eligible) > 1:
        raise LocalStateError("tasks", "multiple eligible compose tasks require core recovery")
    if not eligible:
        return {"status": "no_pending_compose", "task_id": None, "model_started": False}
    task = eligible[0]
    command = "deck-master task status --project " + shlex.quote(str(store.project_root)) + " --task-id " + shlex.quote(task["task_id"]) + " --json"
    return {"status": "awaiting_host" if task["status"] == "awaiting_host" else "running",
            "task_id": task["task_id"], "kind": task["kind"], "intent": task.get("intent"),
            "revision_id": doc["revision_id"], "model_started": False,
            "handoff": "请使用 Deck Master Skill 读取并处理这个 compose 任务。先检查材料缺口；不要重复新建任务。\n" + command}


class LauncherHandler(WorkbenchHandler):
    registry_path: Path

    def do_GET(self):
        if not self._local_host():
            self._send_json({"error": "loopback Host required"}, 403)
            return
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/v2", "/v2/") or parsed.path.startswith("/v2/"):
            self._serve_v2("/v2/" if parsed.path == "/" else parsed.path)
            return
        if parsed.path == "/api/session":
            self._send_json({"token": self.write_token})
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok", **self.runtime_state,
                             "registry_identity": self.runtime_state["identity"],
                             "ui_available": (self.static_dir / "v2" / "index.html").is_file()})
            return
        if parsed.path == "/api/projects":
            try:
                self._send_json({**registry.listing(self.registry_path),
                                 "folder_picker": sys.platform == "darwin"})
            except Exception as exc:
                self._send_error(exc)
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authorized_write():
            return
        try:
            data = self._read_json_body()
            if self.path == "/api/projects/register":
                result = registry.register(self.registry_path, **data)
            elif self.path == "/api/projects/remove":
                result = registry.remove(self.registry_path, **data)
            elif self.path == "/api/projects/create":
                result = registry.create_project(self.registry_path, **data)
            elif self.path == "/api/projects/sample":
                if data:
                    raise LocalStateError("body", "sample creation takes no arbitrary paths")
                from .local_state import safe_path
                from .samples import create_sample, sample_info
                sample = safe_path(self.registry_path.parent, 'samples', 'workbench-v1')
                if not sample.exists():
                    create_sample(sample)
                elif not sample_info(sample):
                    raise LocalStateError('sample', 'sample location is occupied; use a different registry directory')
                result = registry.register(self.registry_path, sample)
            elif self.path == "/api/projects/open":
                if set(data) - {"entry_id", "ui"}:
                    raise LocalStateError("body", "open accepts an entry_id and optional ui")
                target = registry.registered_path(self.registry_path, data["entry_id"])
                result = open_workbench(project=target, registry_file=self.registry_path,
                                        ui=data.get("ui", "v2"), open_browser=False)
                if result["mode"] == "v2":
                    from urllib.parse import urlencode
                    result["url"] += "?" + urlencode({"launcher": self.runtime_state["url"] + "v2/"})
            elif self.path == "/api/directories/pick":
                if data:
                    raise LocalStateError("body", "directory picker takes no paths or scripts")
                result = pick_directory()
            else:
                self._send_json({"error": "not found"}, 404)
                return
            self._send_json(result)
        except Exception as exc:
            self._send_error(exc)
