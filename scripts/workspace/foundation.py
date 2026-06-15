from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.run_state import read_json, write_json

MANIFEST_NAME = "workspace_manifest.json"
SCHEMA_VERSION = "deck_workspace.v1"
ASSET_GRAPH_SCHEMA = "deck_asset_graph.v1"

# Standard directory structure relative to workspace root.
STANDARD_DIRS = [
    "visual-system",
    "structure-assets",
    "quality",
    "assets/slide_assets",
    "runs",
    "exports",
]

# Standard files relative to workspace root. Values are placeholder content.
STANDARD_FILES: dict[str, str] = {
    "visual-system/design_spec.md": "# Design Spec\n",
    "visual-system/spec_lock.md": "# Spec Lock\n",
    "visual-system/brand_assets.md": "# Brand Assets\n",
    "structure-assets/page_archetypes.md": "# Page Archetypes\n",
    "structure-assets/section_patterns.md": "# Section Patterns\n",
    "structure-assets/component_library.md": "# Component Library\n",
    "quality/scoring_rubric.md": "# Scoring Rubric\n",
    "quality/forbidden_terms.md": "# Forbidden Terms\n",
    "quality/delivery_checklist.md": "# Delivery Checklist\n",
}


class WorkspaceError(ValueError):
    """Raised when workspace operations fail validation."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _pptx_page_count(path: Path) -> int | None:
    """Return slide count via python-pptx, or None if unavailable."""
    try:
        from pptx import Presentation  # type: ignore[import-untyped]

        return len(Presentation(str(path)).slides)
    except Exception:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_workspace(workspace_dir: str | Path, name: str) -> dict[str, Any]:
    """Create a new workspace directory structure.

    Raises WorkspaceError if the directory already exists and is non-empty.
    Returns the manifest dict.
    """
    root = Path(workspace_dir).expanduser().resolve()

    if root.exists() and any(root.iterdir()):
        raise WorkspaceError(f"Workspace already exists and is non-empty: {root}")

    root.mkdir(parents=True, exist_ok=True)

    # Create standard directories.
    for rel in STANDARD_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    # Create standard markdown files.
    for rel, content in STANDARD_FILES.items():
        (root / rel).write_text(content, encoding="utf-8")

    # asset_graph.json
    write_json(
        root / "assets/asset_graph.json",
        {"schema_version": ASSET_GRAPH_SCHEMA, "assets": []},
    )

    # asset_feedback.jsonl (empty)
    (root / "assets/asset_feedback.jsonl").write_text("", encoding="utf-8")

    # workspace_manifest.json
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "workspace_dir": str(root),
        "created_at": _utc_now(),
        "reference_ppt": None,
        "reference_ppt_hash": None,
        "reference_ppt_pages": None,
        "registered_at": None,
    }
    write_json(root / MANIFEST_NAME, manifest)

    return manifest


def register_workspace(
    workspace_dir: str | Path,
    reference_ppt: str | Path | None = None,
) -> dict[str, Any]:
    """Register an existing workspace, optionally linking a reference PPT.

    Raises WorkspaceError if manifest is missing or reference PPT does not exist.
    Returns the updated manifest dict.
    """
    root = Path(workspace_dir).expanduser().resolve()
    manifest_path = root / MANIFEST_NAME

    try:
        manifest = read_json(manifest_path)
    except Exception as exc:
        raise WorkspaceError(f"Cannot read workspace manifest: {exc}") from exc

    if reference_ppt is not None:
        ppt_path = Path(reference_ppt).expanduser().resolve()
        if not ppt_path.is_file():
            raise WorkspaceError(f"Reference PPT not found: {ppt_path}")

        manifest["reference_ppt"] = str(ppt_path)
        manifest["reference_ppt_hash"] = _sha256(ppt_path)
        manifest["reference_ppt_pages"] = _pptx_page_count(ppt_path)
        manifest["registered_at"] = _utc_now()

        write_json(manifest_path, manifest)

    return manifest


def validate_workspace(workspace_dir: str | Path) -> dict[str, Any]:
    """Validate workspace completeness.

    Returns a validation report dict. Does not raise on missing items;
    instead sets status to 'pending_manual_review'.
    """
    root = Path(workspace_dir).expanduser().resolve()
    missing_items: list[str] = []
    warnings: list[str] = []
    ref_info: dict[str, Any] | None = None

    # Check manifest.
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        missing_items.append(MANIFEST_NAME)
        manifest = {}
    else:
        try:
            manifest = read_json(manifest_path)
        except Exception:
            missing_items.append(f"{MANIFEST_NAME} (invalid JSON)")
            manifest = {}

    # Check standard directories.
    for rel in STANDARD_DIRS:
        if not (root / rel).is_dir():
            missing_items.append(rel + "/")

    # Check standard files.
    for rel in STANDARD_FILES:
        if not (root / rel).is_file():
            missing_items.append(rel)

    # Check asset files.
    if not (root / "assets/asset_graph.json").is_file():
        missing_items.append("assets/asset_graph.json")
    if not (root / "assets/asset_feedback.jsonl").is_file():
        missing_items.append("assets/asset_feedback.jsonl")

    # Reference PPT check.
    ref_ppt = manifest.get("reference_ppt")
    if ref_ppt is not None:
        ref_path = Path(ref_ppt)
        if not ref_path.is_file():
            warnings.append(f"Reference PPT not found: {ref_ppt}")
        else:
            ref_info = {
                "path": str(ref_path),
                "hash": manifest.get("reference_ppt_hash"),
                "pages": manifest.get("reference_ppt_pages"),
            }

    status = "valid" if not missing_items else "pending_manual_review"

    return {
        "schema_version": "deck_workspace_validation.v1",
        "workspace_dir": str(root),
        "status": status,
        "missing_items": missing_items,
        "reference_ppt": ref_info,
        "warnings": warnings,
    }


def repair_workspace(workspace_dir: str | Path, *, name: str | None = None) -> dict[str, Any]:
    """Create missing standard workspace structure without overwriting files."""
    root = Path(workspace_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    for rel in STANDARD_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    for rel, content in STANDARD_FILES.items():
        path = root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    asset_graph = root / "assets" / "asset_graph.json"
    if not asset_graph.exists():
        write_json(asset_graph, {"schema_version": ASSET_GRAPH_SCHEMA, "assets": []})

    feedback = root / "assets" / "asset_feedback.jsonl"
    if not feedback.exists():
        feedback.parent.mkdir(parents=True, exist_ok=True)
        feedback.write_text("", encoding="utf-8")

    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        write_json(
            manifest_path,
            {
                "schema_version": SCHEMA_VERSION,
                "name": name or root.name,
                "workspace_dir": str(root),
                "created_at": _utc_now(),
                "reference_ppt": None,
                "reference_ppt_hash": None,
                "reference_ppt_pages": None,
                "registered_at": _utc_now(),
            },
        )

    return validate_workspace(root)
