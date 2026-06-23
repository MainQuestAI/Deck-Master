from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_builder_backend_status.v1"
BACKEND_NAME = "ppt-master"
PRODUCTION_RUN_MODES = {"production", "benchmark"}
REQUIRED_PACKAGE_DIRS = ("references", "scripts", "templates")
REQUIRED_PRODUCTION_OPERATIONS = {"render", "writeback", "smoke"}


def production_requires_builder_backend(run_mode: str | None) -> bool:
    return str(run_mode or "production").strip().lower() in PRODUCTION_RUN_MODES


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("DECK_MASTER_PPT_MASTER_BACKEND")
    if env_path:
        paths.append(Path(env_path).expanduser())
    home = Path.home()
    paths.extend(
        [
            home / ".codex" / "skills" / BACKEND_NAME,
            home / ".deck-master" / "current" / "skills" / BACKEND_NAME,
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _frontmatter_ok(path: Path) -> bool:
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return False
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---\n"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    frontmatter = parts[1]
    return f"name: {BACKEND_NAME}" in frontmatter and "description:" in frontmatter


def _nonempty_dir(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def _load_capability(path: Path) -> dict[str, Any]:
    for name in ("deck-master-backend.json", "capability.json"):
        capability_path = path / name
        if not capability_path.exists():
            continue
        try:
            payload = json.loads(capability_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"_parse_error": str(capability_path)}
        return payload if isinstance(payload, dict) else {}
    return {}


def _operations(capability: dict[str, Any]) -> set[str]:
    raw: list[Any] = []
    runtime = capability.get("runtime") if isinstance(capability.get("runtime"), dict) else {}
    if isinstance(runtime.get("operations"), list):
        raw.extend(runtime["operations"])
    if isinstance(capability.get("operations"), list):
        raw.extend(capability["operations"])

    operations: set[str] = set()
    for item in raw:
        for token in str(item or "").strip().lower().replace("_", "-").split():
            operations.add(token)
    return operations


def inspect_builder_backend_package(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser()
    resolved = root.resolve() if root.exists() else root
    result: dict[str, Any] = {
        "path": str(root),
        "resolved": str(resolved),
        "exists": root.exists(),
        "is_symlink": root.is_symlink(),
        "frontmatter_ok": False,
        "required_dirs": {},
        "capability_manifest": False,
        "capability_schema": "",
        "operations": [],
        "full_package": False,
        "production_capable": False,
        "reasons": [],
    }
    if not root.exists() or not root.is_dir():
        result["reasons"].append("backend package is missing")
        return result

    result["frontmatter_ok"] = _frontmatter_ok(root)
    if not result["frontmatter_ok"]:
        result["reasons"].append("SKILL.md frontmatter is missing name/description")

    dir_status = {name: _nonempty_dir(root / name) for name in REQUIRED_PACKAGE_DIRS}
    result["required_dirs"] = dir_status
    missing_dirs = [name for name, ready in dir_status.items() if not ready]
    if missing_dirs:
        result["reasons"].append("backend package is missing non-empty dirs: " + ", ".join(missing_dirs))

    capability = _load_capability(root)
    result["capability_manifest"] = bool(capability) and "_parse_error" not in capability
    result["capability_schema"] = str(capability.get("schema_version") or "")
    operations = _operations(capability)
    result["operations"] = sorted(operations)
    result["full_package"] = bool(result["frontmatter_ok"] and not missing_dirs)

    if not result["capability_manifest"]:
        result["reasons"].append("backend capability manifest is missing or invalid")
    missing_ops = sorted(REQUIRED_PRODUCTION_OPERATIONS - operations)
    if missing_ops:
        result["reasons"].append("backend capability manifest lacks operations: " + ", ".join(missing_ops))

    result["production_capable"] = bool(result["full_package"] and result["capability_manifest"] and not missing_ops)
    return result


def builder_backend_status() -> dict[str, Any]:
    candidates = [inspect_builder_backend_package(path) for path in _candidate_paths()]
    production = next((item for item in candidates if item.get("production_capable")), None)
    full = next((item for item in candidates if item.get("full_package")), None)
    existing = next((item for item in candidates if item.get("exists")), None)
    selected = production or full or existing or (candidates[0] if candidates else {})
    production_capable = bool(selected.get("production_capable"))
    backend_type = "missing"
    if production_capable:
        backend_type = "production_backend"
    elif selected.get("full_package"):
        backend_type = "full_package_not_certified"
    elif selected.get("exists"):
        backend_type = "adapter_only"

    reasons = [str(item) for item in selected.get("reasons", []) if item]
    blocking_reason = (
        "PPT Master production backend is ready."
        if production_capable
        else "PPT Master production backend is not certified for Deck Builder: " + "; ".join(reasons)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "backend_name": BACKEND_NAME,
        "status": "ready" if production_capable else "blocked",
        "backend_type": backend_type,
        "production_capable": production_capable,
        "selected": selected,
        "candidates": candidates,
        "blocking_reason": blocking_reason,
    }
