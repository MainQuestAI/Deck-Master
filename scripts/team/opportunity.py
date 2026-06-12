from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def opportunities_dir(workspace_dir: str | Path) -> Path:
    return Path(workspace_dir) / "opportunities"


def create_opportunity(
    workspace_dir: str | Path,
    client_name: str,
    industry: str = "",
    *,
    opp_id: str = "",
) -> dict[str, Any]:
    """创建 opportunity。"""
    if not opp_id:
        opp_id = f"opp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    opp_dir = opportunities_dir(workspace_dir) / opp_id
    opp_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("runs", "exports", "outcomes"):
        (opp_dir / sub).mkdir(exist_ok=True)

    opportunity = {
        "schema_version": "deck_opportunity.v1",
        "opp_id": opp_id,
        "client_name": client_name,
        "industry": industry,
        "created_at": utc_now(),
        "runs": [],
        "outcomes": [],
    }

    _save_json(opp_dir / "opportunity.json", opportunity)
    return opportunity


def attach_run(
    workspace_dir: str | Path,
    opp_id: str,
    run_id: str,
) -> dict[str, Any]:
    """将 run 关联到 opportunity。"""
    opp_dir = opportunities_dir(workspace_dir) / opp_id
    opp_path = opp_dir / "opportunity.json"

    if not opp_path.exists():
        raise ValueError(f"Opportunity not found: {opp_id}")

    opportunity = json.loads(opp_path.read_text(encoding="utf-8"))

    if run_id not in opportunity.get("runs", []):
        opportunity.setdefault("runs", []).append(run_id)

    _save_json(opp_path, opportunity)

    # 创建 symlink 或记录文件
    runs_dir = opp_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    marker = runs_dir / f"{run_id}.json"
    if not marker.exists():
        _save_json(marker, {"run_id": run_id, "attached_at": utc_now()})

    return opportunity


def list_opportunities(workspace_dir: str | Path) -> list[dict[str, Any]]:
    """列出所有 opportunities。"""
    base = opportunities_dir(workspace_dir)
    if not base.exists():
        return []
    results = []
    for opp_dir in base.iterdir():
        if opp_dir.is_dir():
            opp_path = opp_dir / "opportunity.json"
            if opp_path.exists():
                try:
                    results.append(json.loads(opp_path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
    return results


def _save_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
