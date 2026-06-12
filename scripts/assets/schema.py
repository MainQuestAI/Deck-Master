from __future__ import annotations
from typing import Any
from pathlib import Path
import hashlib
import json

SCHEMA_VERSION = "deck_asset_graph.v1"
ASSET_SCHEMA_VERSION = "deck_slide_asset.v1"


def compute_canonical_slide_id(
    file_sha256: str = "",
    page_number: int = 0,
    normalized_title: str = "",
    *,
    fallback_source_ref: str = "",
    fallback_text_summary: str = "",
) -> str:
    """计算 canonical slide ID。

    规则：slide_ + sha256(file_sha256 + ":" + page_number + ":" + normalized_title)[0:16]

    Fallback：
    - 缺 file_sha256 → normalized_source_ref + page_number + normalized_title
    - 缺 title → text summary 前 120 字
    """
    title = normalized_title.strip()
    if not title and fallback_text_summary:
        title = fallback_text_summary[:120].strip()

    if file_sha256:
        raw = f"{file_sha256}:{page_number}:{title}"
    else:
        raw = f"{fallback_source_ref}:{page_number}:{title}"

    hash_hex = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"slide_{hash_hex}"


def compute_file_sha256(path: str | Path) -> str:
    """计算文件 SHA256 hash。"""
    h = hashlib.sha256()
    p = Path(path)
    if not p.exists():
        return ""
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_slide_asset(
    canonical_slide_id: str,
    *,
    source_path: str = "",
    workspace_relative_path: str = "",
    external_path: str = "",
    page_number: int = 0,
    title: str = "",
    file_sha256: str = "",
    screenshot_path: str = "",
    source_type: str = "library_slide",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建 slide asset 条目。"""
    asset = {
        "schema_version": ASSET_SCHEMA_VERSION,
        "canonical_slide_id": canonical_slide_id,
        "source_type": source_type,
        "page_number": page_number,
        "title": title,
        "file_sha256": file_sha256,
        "screenshot_path": screenshot_path,
        "screenshot_available": bool(screenshot_path),
        "metadata": metadata or {},
    }

    # 路径规则
    if workspace_relative_path:
        asset["workspace_relative_path"] = workspace_relative_path
    elif external_path:
        asset["external_path"] = external_path
    elif source_path:
        asset["source_path"] = source_path

    # 缺截图标记
    if not screenshot_path:
        asset["health_flags"] = ["missing_screenshot"]
    else:
        asset["health_flags"] = []

    return asset


def load_asset_graph(workspace_dir: str | Path) -> dict[str, Any]:
    """加载 workspace 的 asset graph。"""
    path = Path(workspace_dir) / "assets" / "asset_graph.json"
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "assets": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"schema_version": SCHEMA_VERSION, "assets": []}
        if "schema_version" not in data:
            data["schema_version"] = SCHEMA_VERSION
        if "assets" not in data:
            data["assets"] = []
        return data
    except json.JSONDecodeError:
        return {"schema_version": SCHEMA_VERSION, "assets": []}


def save_asset_graph(workspace_dir: str | Path, graph: dict[str, Any]) -> Path:
    """原子保存 asset graph。"""
    path = Path(workspace_dir) / "assets" / "asset_graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def register_asset(
    workspace_dir: str | Path,
    asset: dict[str, Any],
) -> dict[str, Any]:
    """注册或更新 asset 到 graph。

    如果 canonical_slide_id 已存在，合并更新。
    如果是新 asset，添加到 graph。
    """
    graph = load_asset_graph(workspace_dir)
    assets = graph.get("assets", [])
    cid = asset.get("canonical_slide_id", "")

    for i, existing in enumerate(assets):
        if existing.get("canonical_slide_id") == cid:
            # 合并：更新 metadata，保留历史记录
            existing.update({k: v for k, v in asset.items() if k not in ("canonical_slide_id", "schema_version")})
            assets[i] = existing
            graph["assets"] = assets
            save_asset_graph(workspace_dir, graph)
            return existing

    assets.append(asset)
    graph["assets"] = assets
    save_asset_graph(workspace_dir, graph)
    return asset
