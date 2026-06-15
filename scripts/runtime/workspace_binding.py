from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_event
from runtime.run_state import REQUEST_NAME, RunStateError, read_json, write_json
from workspace.foundation import MANIFEST_NAME

SCHEMA_VERSION = "deck_workspace_binding.v1"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _normalize_workspace(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _default_workspace_id(workspace_dir: Path, manifest: dict[str, Any] | None = None) -> str:
    if isinstance(manifest, dict):
        candidate = manifest.get("workspace_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return f"workspace_{workspace_dir.name}"


def bind_workspace(
    run_dir: str | Path,
    workspace: str | Path,
    *,
    reason: str = "",
    resolved_from: str = "cli",
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    if not root.is_dir():
        raise RunStateError(f"Run directory not found: {root}")

    request_path = root / REQUEST_NAME
    request = read_json(request_path)
    run_id = str(request.get("run_id") or root.name)

    workspace_path = _normalize_workspace(workspace)
    if not workspace_path.exists():
        raise RunStateError(f"Workspace not found: {workspace_path}")

    workspace_manifest_path = workspace_path / MANIFEST_NAME
    workspace_manifest = read_json(workspace_manifest_path) if workspace_manifest_path.exists() else {}
    workspace_id = _default_workspace_id(workspace_path, workspace_manifest)

    timestamp = _utc_stamp()
    backup_dir = root / "overrides" / f"workspace_binding_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if request_path.exists():
        shutil.copy2(request_path, backup_dir / REQUEST_NAME)

    previous_workspace = str(request.get("workspace") or "")
    previous_workspace_id = str(request.get("workspace_id") or "")

    request["workspace"] = str(workspace_path)
    request["workspace_id"] = workspace_id
    request["workspace_manifest_ref"] = MANIFEST_NAME
    request["workspace_resolved_from"] = resolved_from

    write_json(root / REQUEST_NAME, request)

    binding_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_dir": str(root),
        "timestamp": timestamp,
        "workspace": str(workspace_path),
        "workspace_id": workspace_id,
        "workspace_manifest_ref": MANIFEST_NAME,
        "workspace_resolved_from": resolved_from,
        "previous_workspace": previous_workspace,
        "previous_workspace_id": previous_workspace_id,
        "workspace_name": str(workspace_manifest.get("name") or workspace_path.name),
        "reason": reason,
    }
    binding_payload_path = write_json(root / "workspace_binding.json", binding_payload)

    append_event(
        root,
        "workspace.bound",
        target=run_id,
        payload_ref=str(binding_payload_path.relative_to(root)),
        data={
            "workspace": str(workspace_path),
            "workspace_id": workspace_id,
            "previous_workspace": previous_workspace,
            "reason": reason,
            "binding_file": str(binding_payload_path.relative_to(root)),
        },
    )

    return {
        "status": "bound",
        "run_id": run_id,
        "run_dir": str(root),
        "workspace": str(workspace_path),
        "workspace_id": workspace_id,
        "workspace_manifest_ref": MANIFEST_NAME,
        "workspace_resolved_from": resolved_from,
        "backup_dir": str(backup_dir),
        "binding_file": str(binding_payload_path),
    }
