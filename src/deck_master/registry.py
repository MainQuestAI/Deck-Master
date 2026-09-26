"""Explicit local project registration. No directory discovery or deletion."""
from __future__ import annotations

import os
from pathlib import Path

from .local_state import LocalStateError, absolute_path, local_lock, project_path, read_json, safe_path, write_json
from .models import sha256_bytes
from .snapshots import load_snapshot
from .store import Store


def registry_path(value=None):
    value = value or Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "deck-master" / "projects.json"
    raw = absolute_path(value, field="registry")
    # Canonicalize explicitly chosen parent aliases, but never follow the file.
    return safe_path(raw.parent.resolve(), raw.name)


def _read(path):
    data = read_json(path, default={"schema_version": "project_registry.v1", "projects": []})
    if data.get("schema_version") != "project_registry.v1" or not isinstance(data.get("projects"), list):
        raise LocalStateError("registry", "unsupported registry; preserve the file for recovery")
    seen = set()
    for item in data["projects"]:
        if (not isinstance(item, dict) or set(item) != {"entry_id", "path", "title", "project_id"}
                or any(not isinstance(v, str) for v in item.values())
                or not Path(item["path"]).is_absolute()
                or sha256_bytes(item["path"].encode()) != item["entry_id"] or item["entry_id"] in seen):
            raise LocalStateError("registry", "invalid project entry; preserve the file for recovery")
        seen.add(item["entry_id"])
    return data


def _entry(path):
    doc = load_snapshot(Store(path))
    return {"entry_id": sha256_bytes(str(path).encode()), "path": str(path),
            "title": doc["task"]["title"], "project_id": doc["project_id"]}


def register(registry, path):
    target = project_path(path)
    entry = _entry(target)
    registry = registry_path(registry)
    with local_lock(safe_path(registry.parent, registry.name + ".lock")):
        data = _read(registry)
        before = list(data["projects"])
        data["projects"] = [entry if old["entry_id"] == entry["entry_id"] else old for old in before]
        if not any(old["entry_id"] == entry["entry_id"] for old in before):
            data["projects"].append(entry)
        if before != data["projects"]:
            write_json(registry, data)
    return {"status": "registered", "project": entry}


def remove(registry, entry_id):
    registry = registry_path(registry)
    with local_lock(safe_path(registry.parent, registry.name + ".lock")):
        data = _read(registry)
        before = data["projects"]
        data["projects"] = [old for old in before if old["entry_id"] != entry_id]
        if before != data["projects"]:
            write_json(registry, data)
    return {"status": "unregistered", "entry_id": entry_id}


def registered_path(registry, entry_id):
    for item in _read(registry_path(registry))["projects"]:
        if item["entry_id"] == entry_id:
            return project_path(item["path"])
    raise LocalStateError("entry_id", "project is not registered in this launcher")


def listing(registry):
    entries = []
    for item in _read(registry_path(registry))["projects"]:
        try:
            path = project_path(item["path"])
            doc = load_snapshot(Store(path))
            from .ui_journal import read_position
            try:
                position = read_position(path)
            except (LocalStateError, OSError):
                position = None
            entries.append({**item, "title": doc["task"]["title"], "available": True,
                            "revision_id": doc["revision_id"], "position": position})
        except (LocalStateError, OSError, RuntimeError, ValueError):
            entries.append({**item, "available": False, "position": None})
    return {"schema_version": "project_registry.v1", "projects": entries}


def create_project(registry, *, path, title, brief, audience, sources=None):
    """Prepare a complete project privately, publish it, then register explicitly.

    Registry failures leave a complete project that can be registered again;
    no cleanup ever deletes the published project or user's source materials.
    """
    import shutil
    import tempfile
    from . import service

    for key, value in (("title", title), ("brief", brief), ("audience", audience)):
        if not isinstance(value, str) or not value.strip():
            raise LocalStateError(key, "name, purpose and audience are required")
    target = absolute_path(path, field="project")
    target = safe_path(target.parent.resolve(), target.name)
    if not target.parent.is_dir() or target.exists():
        raise LocalStateError("project", "select a new project folder under an existing writable directory")
    registry = registry_path(registry)
    # Preflight the registry before creating any project content.
    with local_lock(safe_path(registry.parent, registry.name + ".lock")):
        _read(registry)
    stage_root = Path(tempfile.mkdtemp(prefix=".deck-master-create-", dir=target.parent))
    stage = stage_root / target.name
    try:
        result = service.create(stage, brief=brief, title=title, audience=audience,
                                sources=sources or [], project_format="workbench.v3")
        # mkdir reserves the destination without replacing an existing folder.
        target.mkdir()
        try:
            (stage / ".deckmaster").rename(target / ".deckmaster")
        except BaseException:
            target.rmdir()  # only our still-empty reservation
            raise
    finally:
        shutil.rmtree(stage_root)
    published = Store(target)
    result["pending_tasks"] = service._pending_host_tasks(published.load_document(), published)
    try:
        entry = register(registry, target)["project"]
    except (OSError, LocalStateError) as exc:
        return {**result, "registered": False, "path": str(target),
                "detail": str(exc), "next_action": "register the complete project at this path"}
    return {**result, "registered": True, "project": entry, "model_started": False}
