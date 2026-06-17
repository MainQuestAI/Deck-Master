from __future__ import annotations

import json
import subprocess
import shlex
import sys
from pathlib import Path
from typing import Any

TOOL_REGISTRY_NAME = "tool_registry.json"
GLOBAL_TOOL_REGISTRY = Path.home() / ".deck-master" / "tools.json"
SCHEMA_VERSION = "deck_tool_registry.v1"


class ToolRegistryError(ValueError):
    pass


def _read_registry(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolRegistryError(f"Invalid tool registry JSON at {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ToolRegistryError(f"Tool registry payload must be an object: {path}")
    tools = payload.get("tools", {})
    return {
        str(name): value
        for name, value in (tools.items() if isinstance(tools, dict) else [])
        if isinstance(value, dict)
    }


def _registry_path(workspace: str | Path | None) -> Path | None:
    if workspace:
        path = Path(workspace).expanduser().resolve() / TOOL_REGISTRY_NAME
        if path.exists():
            return path
    if GLOBAL_TOOL_REGISTRY.exists():
        return GLOBAL_TOOL_REGISTRY
    return None


def _format_value(value: str, *, run_dir: Path, workspace: str | None) -> str:
    return value.format(run_dir=str(run_dir), workspace=str(workspace or ""))


def _format_list(values: list[Any], *, run_dir: Path, workspace: str | None) -> list[str]:
    return [_format_value(str(value), run_dir=run_dir, workspace=workspace) for value in values]


def _default_args(run_dir: Path, workspace: str | None) -> list[str]:
    return [
        "generate",
        "--task-dir",
        f"{run_dir}/generation_tasks",
        "--output-dir",
        f"{run_dir}/generation_results",
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bundled_capability_exists(tool: str) -> bool:
    repo_capability = _repo_root() / "product_capabilities" / tool
    installed_capability = Path.home() / ".deck-master" / "current" / "capabilities" / tool
    return repo_capability.exists() or installed_capability.exists()


def _bundled_tool_entry(tool: str, *, run_dir: Path, workspace: str | None) -> tuple[list[str], dict[str, Any], str] | None:
    if tool != "ppt-deck-pro-max" or not _bundled_capability_exists(tool):
        return None
    script = _repo_root() / "scripts" / "capabilities" / "ppt_deck_pro_max.py"
    if not script.exists():
        return None
    command = [sys.executable, str(script), *_default_args(run_dir, workspace)]
    entry = {
        "schema_version": SCHEMA_VERSION,
        "command": sys.executable,
        "type": "bundled",
        "args_template": command[1:],
        "availability_check": [sys.executable, "--version"],
        "capability": tool,
    }
    return command, entry, "bundled capability"


def _coerce_command(command: str, *, run_dir: Path, workspace: str | None) -> list[str]:
    raw = _format_value(command, run_dir=run_dir, workspace=workspace).strip()
    if not raw:
        raise ToolRegistryError("Tool command is empty.")
    parsed = shlex.split(raw)
    if not parsed:
        raise ToolRegistryError("Tool command is empty.")
    return parsed


def _coerce_args(value: Any, *, run_dir: Path, workspace: str | None) -> list[str]:
    if not isinstance(value, list):
        return _default_args(run_dir, workspace)
    return _format_list(value, run_dir=run_dir, workspace=workspace)


def _coerce_availability_check(value: Any, *, tool_command: str, run_dir: Path, workspace: str | None) -> list[str]:
    if not isinstance(value, list):
        return [tool_command, "--version"]
    return _format_list(value, run_dir=run_dir, workspace=workspace)


def resolve_tool_command(
    tool: str,
    run_dir: str | Path,
    *,
    workspace: str | Path | None = None,
    cli_tool_command: str | None = None,
) -> tuple[list[str], dict[str, Any], str]:
    root = Path(run_dir).expanduser().resolve()
    workspace_path = str(workspace) if workspace else None

    if cli_tool_command:
        command = _coerce_command(cli_tool_command, run_dir=root, workspace=workspace_path)
        args = _default_args(root, workspace_path)
        entry = {
            "schema_version": SCHEMA_VERSION,
            "command": command[0],
            "type": "cli",
            "args_template": args,
            "availability_check": [command[0], "--version"],
            "source": "cli_override",
            "warning": "Explicit capability override used. Output remains subject to Deck Master import contract.",
        }
        return [*command, *args], entry, "cli_override"

    bundled = _bundled_tool_entry(tool, run_dir=root, workspace=workspace_path)
    if bundled is not None:
        return bundled

    registry_path = _registry_path(workspace_path)
    if registry_path is None:
        raise ToolRegistryError(f"Tool registry missing. Configure '{tool}' in ~/.deck-master/tools.json")

    tools = _read_registry(registry_path)
    raw_entry = tools.get(tool)
    if raw_entry is None:
        raise ToolRegistryError(f"Tool '{tool}' not registered in {registry_path}.")

    tool_command = str(raw_entry.get("command", "")).strip()
    if not tool_command:
        raise ToolRegistryError(f"Tool '{tool}' missing command field.")
    if raw_entry.get("type", "cli") != "cli":
        raise ToolRegistryError(f"Tool '{tool}' type unsupported: {raw_entry.get('type')}")

    args = _coerce_args(raw_entry.get("args_template"), run_dir=root, workspace=workspace_path)

    rendered = {
        "schema_version": str(raw_entry.get("schema_version", SCHEMA_VERSION)),
        "command": tool_command,
        "type": "cli",
        "args_template": args,
    }
    rendered["availability_check"] = _coerce_availability_check(
        raw_entry.get("availability_check"),
        tool_command=tool_command,
        run_dir=root,
        workspace=workspace_path,
    )

    return [tool_command, *args], rendered, f"{registry_path}"


def check_tool_available(command: list[str], *, availability_check: list[str] | None = None) -> tuple[bool, str]:
    probe = availability_check or [command[0], "--version"]
    try:
        proc = subprocess.run(probe, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, f"Tool command not found: {probe[0]}"
    if proc.returncode != 0:
        return (
            False,
            (proc.stderr or proc.stdout or "tool availability check failed"),
        )
    return True, ""


def resolve_tool_for_session(
    tool: str,
    run_dir: str | Path,
    *,
    workspace: str | Path | None = None,
    cli_tool_command: str | None = None,
) -> dict[str, Any]:
    command, entry, origin = resolve_tool_command(
        tool,
        run_dir,
        workspace=workspace,
        cli_tool_command=cli_tool_command,
    )
    return {
        "tool": tool,
        "source": origin,
        "command": command,
        "availability_check": entry.get("availability_check", []),
        "entry": entry,
    }
