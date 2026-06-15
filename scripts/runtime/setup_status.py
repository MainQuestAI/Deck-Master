from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skills.installer import validate_skill
from workspace.foundation import repair_workspace, validate_workspace


SCHEMA_VERSION = "deck_master_setup.v1"
CONFIG_NAME = "config.json"
SETUP_EVENTS_NAME = "setup_events.jsonl"
DEFAULT_REVIEW_COCKPIT_URL = "http://127.0.0.1:5050"


class SetupError(ValueError):
    """Raised when Deck Master setup blocks a real run."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def install_root() -> Path:
    return Path.home() / ".deck-master"


def config_path() -> Path:
    return install_root() / CONFIG_NAME


def configured_runs_dir(fallback: str | Path) -> Path:
    cfg = _read_config()
    if isinstance(cfg, dict) and not cfg.get("_invalid") and cfg.get("default_runs_dir"):
        return Path(str(cfg["default_runs_dir"])).expanduser().resolve()
    return Path(fallback).expanduser().resolve()


def _append_setup_event(action: str, *, status: str, data: dict[str, Any] | None = None) -> None:
    root = install_root()
    root.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": _utc_now(),
        "actor": "deck_master",
        "action": action,
        "status": status,
        "data": data or {},
    }
    with (root / SETUP_EVENTS_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_config() -> dict[str, Any] | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_invalid": f"Invalid setup config JSON: {exc.msg}"}
    return payload if isinstance(payload, dict) else {"_invalid": "Setup config must be a JSON object."}


def _write_config(payload: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_setup(
    *,
    workspace: str | None = None,
    runs_dir: str | None = None,
    targets: list[str] | None = None,
    review_cockpit_url: str = DEFAULT_REVIEW_COCKPIT_URL,
    repair: bool = False,
) -> dict[str, Any]:
    root = install_root()
    root.mkdir(parents=True, exist_ok=True)

    active_workspace = Path(workspace).expanduser().resolve() if workspace else None
    if active_workspace and repair:
        repair_workspace(active_workspace)

    default_runs = Path(runs_dir).expanduser().resolve() if runs_dir else None
    if default_runs is None:
        default_runs = active_workspace / "runs" if active_workspace else root / "runs"
    default_runs.mkdir(parents=True, exist_ok=True)

    agent_targets = targets or ["codex"]
    config = {
        "schema_version": SCHEMA_VERSION,
        "setup_completed_at": _utc_now(),
        "install_root": str(root),
        "active_workspace": str(active_workspace) if active_workspace else "",
        "default_runs_dir": str(default_runs),
        "review_cockpit_url": review_cockpit_url or DEFAULT_REVIEW_COCKPIT_URL,
        "agent_targets": agent_targets,
    }
    _write_config(config)
    status = setup_status(workspace=str(active_workspace) if active_workspace else None, write_event=False)
    _append_setup_event("setup.completed", status=status["status"], data={"config": config, "status": status})
    return {"status": "setup_completed", "config": config, "setup_status": status}


def setup_status(*, workspace: str | None = None, write_event: bool = True) -> dict[str, Any]:
    cfg = _read_config()
    missing: list[str] = []
    repairs: list[str] = []
    warnings: list[str] = []
    agent_status: dict[str, Any] = {}
    workspace_report: dict[str, Any] | None = None
    workspace_path = ""

    if cfg is None:
        missing.append(str(config_path()))
        result = {
            "schema_version": "deck_master_setup_status.v1",
            "status": "blocked",
            "config_path": str(config_path()),
            "missing_items": missing,
            "repair_items": repairs,
            "warnings": warnings,
            "next_command": "deck-master setup --workspace <path> --target codex",
        }
        if write_event:
            _append_setup_event("setup.status.checked", status=result["status"], data=result)
        return result

    if cfg.get("_invalid"):
        missing.append(str(cfg["_invalid"]))
        status_value = "blocked"
    else:
        status_value = "ready"
        if cfg.get("schema_version") != SCHEMA_VERSION:
            missing.append("schema_version")
        if not cfg.get("setup_completed_at"):
            missing.append("setup_completed_at")

        root = Path(str(cfg.get("install_root") or install_root())).expanduser()
        if not root.exists():
            missing.append("install_root")

        default_runs = Path(str(cfg.get("default_runs_dir") or "")).expanduser()
        if not str(default_runs) or not default_runs.is_dir():
            missing.append("default_runs_dir")

        if not cfg.get("review_cockpit_url"):
            missing.append("review_cockpit_url")

        workspace_path = workspace or str(cfg.get("active_workspace") or "")
        if workspace_path:
            workspace_report = validate_workspace(workspace_path)
            if workspace_report.get("status") != "valid":
                repairs.extend(workspace_report.get("missing_items", []))

        for target in cfg.get("agent_targets") or []:
            agent_status[str(target)] = validate_skill(str(target))
            if not agent_status[str(target)].get("valid"):
                missing.append(f"agent_target:{target}")

        if missing:
            status_value = "blocked"
        elif repairs:
            status_value = "needs_repair"

    result = {
        "schema_version": "deck_master_setup_status.v1",
        "status": status_value,
        "config_path": str(config_path()),
        "config": cfg,
        "missing_items": missing,
        "repair_items": repairs,
        "warnings": warnings,
        "workspace": workspace_report,
        "agent_targets": agent_status,
        "next_command": "",
    }
    if status_value == "blocked":
        setup_workspace = workspace_path or "<path>"
        result["next_command"] = f"deck-master setup --workspace {setup_workspace} --target codex"
    elif status_value == "needs_repair":
        setup_workspace = workspace_path or "<path>"
        result["next_command"] = f"deck-master setup --workspace {setup_workspace} --repair-workspace --target codex"

    if write_event:
        _append_setup_event("setup.status.checked", status=status_value, data=result)
    return result


def is_dev_setup_allowed(value: bool = False) -> bool:
    import os

    return value or os.environ.get("DECK_MASTER_DEV_SKIP_SETUP") == "1"


def require_setup_ready(*, dev_allow_unsetup: bool = False, workspace: str | None = None) -> None:
    if is_dev_setup_allowed(dev_allow_unsetup):
        return
    status = setup_status(workspace=workspace)
    if status["status"] != "ready":
        raise SetupError(
            "Deck Master setup is not ready. "
            f"status={status['status']}; next={status.get('next_command', '')}"
        )
