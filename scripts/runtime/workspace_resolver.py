from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.setup_status import _normalize_run_mode, _run_mode_allows_setup_skip, _run_mode_requires_workspace
from workspace.foundation import validate_workspace


def _normalize_workspace(path: str | None) -> str:
    if not path:
        return ""
    return str(Path(path).expanduser().resolve())


def resolve_workspace_for_run(
    *,
    run_dir,
    request: dict[str, Any] | None = None,
    cli_workspace: str | None = None,
    run_mode: str | None = None,
    allow_dev_bypass: bool = False,
) -> dict[str, Any]:
    """Resolve workspace by spec-priority and return a decision object.

    Priority:
      1. CLI --workspace
      2. request.json.workspace
      3. setup.active_workspace

    If an existing request has a workspace and CLI passes another value, this
    resolution is blocked for explicit conflict handling.
    """
    requested_mode = _normalize_run_mode(run_mode or "production")
    cli_ws = _normalize_workspace(cli_workspace)
    requested_ws = ""
    if isinstance(request, dict):
        requested_ws = _normalize_workspace(str(request.get("workspace") or ""))

    resolved: dict[str, Any] = {
        "run_dir": str(Path(run_dir).expanduser().resolve()),
        "requested_run_mode": requested_mode,
        "resolved_from": "",
        "resolved_workspace": "",
        "requested_workspace": requested_ws,
        "cli_workspace": cli_ws,
        "setup_workspace": "",
        "workspace_required": _run_mode_requires_workspace(requested_mode),
        "allow_dev_bypass": _run_mode_allows_setup_skip(requested_mode, allow_dev_bypass),
        "conflicts": [],
        "warnings": [],
        "blocked": False,
        "reasons": [],
        "workspace_exists": False,
        "workspace_valid": False,
        "workspace_report": {},
    }

    cfg = read_setup_config()
    if isinstance(cfg, dict) and not cfg.get("_invalid"):
        resolved["setup_workspace"] = _normalize_workspace(str(cfg.get("active_workspace") or ""))

    has_request_workspace = bool(requested_ws)
    if cli_ws and has_request_workspace and cli_ws != requested_ws:
        resolved["blocked"] = True
        resolved["conflicts"].append("workspace")
        resolved["reasons"].append(f"request workspace={requested_ws} conflicts with cli workspace={cli_ws}")

    if cli_ws:
        resolved["resolved_workspace"] = cli_ws
        resolved["resolved_from"] = "cli"
    elif has_request_workspace:
        resolved["resolved_workspace"] = requested_ws
        resolved["resolved_from"] = "request"
    elif resolved["setup_workspace"]:
        resolved["resolved_workspace"] = resolved["setup_workspace"]
        resolved["resolved_from"] = "setup"

        if has_request_workspace:
            resolved["warnings"].append("setup workspace differs from requested workspace")

    if resolved["resolved_workspace"]:
        workspace_root = Path(resolved["resolved_workspace"])
        resolved["workspace_exists"] = workspace_root.exists()
        if not workspace_root.exists():
            resolved["blocked"] = True
            resolved["conflicts"].append("workspace")
            resolved["reasons"].append(f"workspace not found: {workspace_root}")
        else:
            report = validate_workspace(workspace_root)
            resolved["workspace_report"] = report
            resolved["workspace_valid"] = report.get("status") == "valid"
            if not resolved["workspace_valid"] and not resolved["allow_dev_bypass"]:
                resolved["blocked"] = True
                resolved["conflicts"].append("workspace")
                resolved["reasons"].append(f"workspace not ready: {workspace_root}")
    elif resolved["workspace_required"]:
        resolved["blocked"] = True
        resolved["conflicts"].append("workspace")
        resolved["reasons"].append("production or benchmark run requires workspace")
    elif not resolved["allow_dev_bypass"]:
        resolved["warnings"].append("workspace is optional for this run mode")

    if not resolved["blocked"] and has_request_workspace and resolved["setup_workspace"] and resolved["setup_workspace"] != requested_ws:
        resolved["warnings"].append("setup workspace differs from request workspace")

    return resolved


def read_setup_config() -> dict[str, Any] | None:
    from runtime.setup_status import _read_config

    return _read_config()
