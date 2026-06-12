from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def team_dir(workspace_dir: str | Path) -> Path:
    return Path(workspace_dir) / "team"


def ensure_team_dir(workspace_dir: str | Path) -> Path:
    d = team_dir(workspace_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_user(
    workspace_dir: str | Path,
    user_id: str,
    name: str,
    email: str = "",
    role: str = "member",
) -> dict[str, Any]:
    """添加用户。同一 user_id 重复创建时报错。"""
    d = ensure_team_dir(workspace_dir)
    users_path = d / "users.json"

    users = _load_json(users_path, [])
    for u in users:
        if u.get("user_id") == user_id:
            raise ValueError(f"User already exists: {user_id}")

    user = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "role": role,
        "created_at": utc_now(),
    }
    users.append(user)
    _save_json(users_path, users)

    _append_audit(workspace_dir, "user.added", user_id, {"name": name, "role": role})
    return user


def assign_role(
    workspace_dir: str | Path,
    user_id: str,
    role: str,
) -> dict[str, Any]:
    """分配角色。"""
    d = ensure_team_dir(workspace_dir)
    users_path = d / "users.json"
    users = _load_json(users_path, [])

    for user in users:
        if user.get("user_id") == user_id:
            user["role"] = role
            user["role_updated_at"] = utc_now()
            _save_json(users_path, users)
            _append_audit(workspace_dir, "role.assigned", user_id, {"role": role})
            return user

    raise ValueError(f"User not found: {user_id}")


def list_users(workspace_dir: str | Path) -> list[dict[str, Any]]:
    d = team_dir(workspace_dir)
    return _load_json(d / "users.json", [])


def list_audit(workspace_dir: str | Path) -> list[dict[str, Any]]:
    d = team_dir(workspace_dir)
    path = d / "audit_log.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _append_audit(workspace_dir: str | Path, action: str, user_id: str, data: dict) -> None:
    d = ensure_team_dir(workspace_dir)
    path = d / "audit_log.jsonl"
    entry = {"timestamp": utc_now(), "action": action, "user_id": user_id, **data}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default if default is not None else []


def _save_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
