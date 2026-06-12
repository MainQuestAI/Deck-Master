from __future__ import annotations
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "deck_solution_package.v1"


def create_solution_package(
    workspace_dir: str | Path,
    package_id: str,
    *,
    industry: str = "",
    best_for: str = "",
    example_runs: list[str] | None = None,
    source_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """从已交付 run 创建 solution package。"""
    package = {
        "schema_version": SCHEMA_VERSION,
        "package_id": package_id,
        "industry": industry,
        "best_for": best_for,
        "recommended_archetypes": [],
        "claim_patterns": [],
        "slide_assets": [],
        "quality_policy_refs": [],
        "example_runs": example_runs or [],
    }

    # 如果有 source run，提取 pattern
    if source_run_dir:
        run_dir = Path(source_run_dir).expanduser().resolve()

        # 从 narrative plan 提取 archetypes
        plan_path = run_dir / "narrative_plan.json"
        if plan_path.exists():
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                roles = set()
                for beat in plan.get("beats", []):
                    role = beat.get("role", "")
                    if role:
                        roles.add(role)
                package["recommended_archetypes"] = sorted(roles)
            except json.JSONDecodeError:
                pass

        # 从 claim map 提取 patterns
        claim_path = run_dir / "claim_map.json"
        if claim_path.exists():
            try:
                claims = json.loads(claim_path.read_text(encoding="utf-8"))
                package["claim_patterns"] = [
                    {"claim": c.get("claim", ""), "why_it_matters": c.get("why_it_matters", "")}
                    for c in claims.get("claims", [])[:5]
                ]
            except json.JSONDecodeError:
                pass

        # 从 asset_refs 提取 slide assets
        refs_path = run_dir / "asset_refs.json"
        if refs_path.exists():
            try:
                refs = json.loads(refs_path.read_text(encoding="utf-8"))
                package["slide_assets"] = [
                    ref.get("canonical_slide_id", "")
                    for ref in refs.get("asset_refs", [])
                    if ref.get("canonical_slide_id")
                ]
            except json.JSONDecodeError:
                pass

    # 保存
    pkg_dir = Path(workspace_dir) / "packages" / "solution_packages"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    path = pkg_dir / f"{package_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

    return package


def apply_solution_package(
    workspace_dir: str | Path,
    package_id: str,
    run_dir: str | Path,
) -> dict[str, Any]:
    """在新 run 中应用 solution package。"""
    pkg_path = Path(workspace_dir) / "packages" / "solution_packages" / f"{package_id}.json"
    if not pkg_path.exists():
        raise ValueError(f"Solution package not found: {package_id}")

    package = json.loads(pkg_path.read_text(encoding="utf-8"))

    # 将 package 信息写入 run 的 workspace refs
    run_path = Path(run_dir).expanduser().resolve()
    request_path = run_path / "request.json"
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            request["solution_package"] = {
                "package_id": package_id,
                "industry": package.get("industry", ""),
                "recommended_archetypes": package.get("recommended_archetypes", []),
            }
            tmp = request_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(request_path)
        except json.JSONDecodeError:
            pass

    return package
