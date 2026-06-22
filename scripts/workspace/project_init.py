from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.run_state import write_json
from workspace.foundation import repair_workspace, validate_workspace

PROJECT_SCHEMA_VERSION = "deck_master_project.v1"
MATERIAL_INVENTORY_SCHEMA_VERSION = "deck_master_material_inventory.v1"
WORKSPACE_POLICY_SCHEMA_VERSION = "deck_master_workspace_policy.v1"
RUN_BINDINGS_SCHEMA_VERSION = "deck_master_run_bindings.v1"

PROJECT_DIRS = [
    "00-客户原始需求",
    "01-会议与沟通",
    "02-AI协作过程/有价值",
    "02-AI协作过程/临时过程",
    "03-参考素材/历史方案",
    "03-参考素材/客户素材",
    "03-参考素材/竞品与行业",
    "03-参考素材/截图与证据",
    "04-方案与交付物/deck-master",
    "04-方案与交付物/exports",
    "04-方案与交付物/review",
    ".deck-master",
    "quality",
]

DEFAULT_FORBIDDEN_TERMS = (
    "# Forbidden Terms\n"
    "\n"
    "Add project-specific customer-visible forbidden terms here, one term per line.\n"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_if_missing(path: Path, payload: dict[str, Any], created: list[str], preserved: list[str]) -> None:
    if path.exists():
        preserved.append(path.as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, payload)
    created.append(path.as_posix())


def _write_text_if_missing(path: Path, content: str, created: list[str], preserved: list[str]) -> None:
    if path.exists():
        preserved.append(path.as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path.as_posix())


def init_deck_project(workspace_dir: str | Path, *, name: str) -> dict[str, Any]:
    root = Path(workspace_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    preserved: list[str] = []

    for rel in PROJECT_DIRS:
        path = root / rel
        if path.exists():
            preserved.append(path.relative_to(root).as_posix())
            continue
        path.mkdir(parents=True, exist_ok=True)
        created.append(path.relative_to(root).as_posix() + "/")

    directory_map = {
        "customer_raw_requirements": "00-客户原始需求",
        "meetings_and_comms": "01-会议与沟通",
        "ai_process_valuable": "02-AI协作过程/有价值",
        "ai_process_temporary": "02-AI协作过程/临时过程",
        "reference_historical_decks": "03-参考素材/历史方案",
        "reference_customer_assets": "03-参考素材/客户素材",
        "reference_competitor_industry": "03-参考素材/竞品与行业",
        "reference_screenshots_evidence": "03-参考素材/截图与证据",
        "delivery_deck_master": "04-方案与交付物/deck-master",
        "delivery_exports": "04-方案与交付物/exports",
        "delivery_review": "04-方案与交付物/review",
    }
    now = _utc_now()
    project_dir = root / ".deck-master"

    _write_json_if_missing(
        project_dir / "deck_project.json",
        {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "name": name,
            "workspace_dir": str(root),
            "created_at": now,
            "directory_map": directory_map,
            "public_entry_skill": "deck-init",
        },
        created,
        preserved,
    )
    _write_json_if_missing(
        project_dir / "material_inventory.json",
        {
            "schema_version": MATERIAL_INVENTORY_SCHEMA_VERSION,
            "workspace_dir": str(root),
            "updated_at": now,
            "sources": [],
            "source_categories": {
                "customer_raw_requirements": "00-客户原始需求",
                "meeting_notes": "01-会议与沟通",
                "reference_material": "03-参考素材",
            },
        },
        created,
        preserved,
    )
    _write_json_if_missing(
        project_dir / "workspace_policy.json",
        {
            "schema_version": WORKSPACE_POLICY_SCHEMA_VERSION,
            "workspace_dir": str(root),
            "created_at": now,
            "customer_visible_content_boundary": "only_customer_visible_fields_can_enter_final_slides",
            "private_material_policy": "do_not_commit_customer_raw_materials_or_secrets",
            "production_export_policy": "requires_final_readiness_ready",
        },
        created,
        preserved,
    )
    _write_json_if_missing(
        project_dir / "run_bindings.json",
        {
            "schema_version": RUN_BINDINGS_SCHEMA_VERSION,
            "workspace_dir": str(root),
            "updated_at": now,
            "active_run_id": "",
            "runs": [],
        },
        created,
        preserved,
    )
    _write_text_if_missing(root / "quality" / "forbidden_terms.md", DEFAULT_FORBIDDEN_TERMS, created, preserved)

    legacy_repair = repair_workspace(root, name=name)
    validation = validate_workspace(root)
    return {
        "schema_version": "deck_master_project_init.v1",
        "status": "initialized" if created else "already_initialized",
        "workspace_dir": str(root),
        "name": name,
        "created": created,
        "preserved": preserved,
        "project_files": {
            "deck_project": str(project_dir / "deck_project.json"),
            "material_inventory": str(project_dir / "material_inventory.json"),
            "workspace_policy": str(project_dir / "workspace_policy.json"),
            "run_bindings": str(project_dir / "run_bindings.json"),
        },
        "legacy_workspace_repair": legacy_repair,
        "validation": validation,
    }
