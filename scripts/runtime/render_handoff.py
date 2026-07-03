from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from runtime.run_state import write_json
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.runtime.run_state import write_json

RENDER_REQUEST_SCHEMA_VERSION = "deck_render_request.v1"
RENDER_REQUEST_NAME = "render_request.json"
EXPECTED_RENDER_RESULT_SCHEMA_VERSION = "deck_render_result.v2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_handoff_contract_ready() -> bool:
    return RENDER_REQUEST_SCHEMA_VERSION == "deck_render_request.v1" and bool(RENDER_REQUEST_NAME)


def write_render_request(
    root: Path,
    *,
    build_dir_name: str,
    build_manifest_name: str,
    render_results_dir: str,
    render_result_name: str,
    request: dict[str, Any],
    manifest: dict[str, Any],
    backend: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    run_id = str(request.get("run_id") or root.name)
    run_mode = str(manifest.get("run_mode") or request.get("run_mode") or "production")
    request_id = "render-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    payload = {
        "schema_version": RENDER_REQUEST_SCHEMA_VERSION,
        "status": "awaiting_external_render",
        "handoff_status": "handoff_ready",
        "run_id": run_id,
        "request_id": request_id,
        "run_mode": run_mode,
        "tool": "ppt-master",
        "builder_backend": backend,
        "backend_identity": {
            "name": str((backend.get("dependency_status") or {}).get("name") or backend.get("backend_name") or "ppt-master"),
            "binding_status": str((backend.get("dependency_status") or {}).get("binding_status") or ""),
            "repo_label": str((backend.get("dependency_status") or {}).get("repo_label") or ""),
            "git_remote": str((backend.get("dependency_status") or {}).get("git_remote") or ""),
            "git_sha": str((backend.get("dependency_status") or {}).get("git_sha") or ""),
        },
        "inputs": {
            "run_dir": str(root),
            "preview_manifest": "preview_manifest.json",
            "build_manifest": f"{build_dir_name}/{build_manifest_name}",
            "source_fingerprint": manifest.get("source_fingerprint"),
            "pages": manifest.get("pages", []),
        },
        "required_outputs": list(manifest.get("required_outputs") or []),
        "expected_render_result": {
            "schema_version": EXPECTED_RENDER_RESULT_SCHEMA_VERSION,
            "writeback_path": f"{render_results_dir}/{render_result_name}",
            "artifact_manifest_path": f"{build_dir_name}/artifact_manifest.json",
            "status": "completed",
            "required_fields": [
                "schema_version",
                "run_id",
                "tool",
                "status",
                "artifact_path",
                "preview_dir",
                "page_count",
                "page_previews",
            ],
        },
        "writeback": {
            "render_result": f"{render_results_dir}/{render_result_name}",
            "artifact_manifest": f"{build_dir_name}/artifact_manifest.json",
            "import_command": f"deck-master import-render-result --run-dir {root} --input <render_result.json>",
        },
        "notes": [
            "External renderer must create the final deck artifacts and write a real render_result.json.",
            "Deck Master does not treat contract smoke output as production render_result.",
        ],
        "created_at": _utc_now(),
    }
    path = root / build_dir_name / RENDER_REQUEST_NAME
    write_json(path, payload)
    return path, payload
