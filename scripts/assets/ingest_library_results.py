from __future__ import annotations
from pathlib import Path
from typing import Any
import json

from assets.schema import (
    create_slide_asset,
    register_asset,
    load_asset_graph,
)
from assets.canonical_id import candidate_to_canonical_id, normalize_title
from assets.feedback import append_feedback
from runtime.events import append_typed_event


def ingest_library_results(
    run_dir: str | Path,
    workspace_dir: str | Path | None = None,
) -> dict[str, Any]:
    """把 library results 中的候选页注册为 workspace asset。

    输入：
    - run_dir/library_results/selection.json
    - run_dir/library_results/by_beat/*.json（可选）

    输出：
    - workspace assets/asset_graph.json（如果有 workspace_dir）
    - workspace assets/slide_assets/*.json
    - run 内 asset_refs.json

    返回：
    {
        "run_id": str,
        "registered_count": int,
        "skipped_count": int,
        "errors": [...],
        "asset_refs": [...],
    }
    """
    run_dir = Path(run_dir).expanduser().resolve()
    run_id = run_dir.name

    # 读取 selection.json
    selection_path = run_dir / "library_results" / "selection.json"
    if not selection_path.exists():
        return {"run_id": run_id, "registered_count": 0, "skipped_count": 0, "errors": ["selection.json not found"], "asset_refs": []}

    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"run_id": run_id, "registered_count": 0, "skipped_count": 0, "errors": [f"Invalid JSON: {e}"], "asset_refs": []}

    registered_count = 0
    skipped_count = 0
    errors: list[str] = []
    asset_refs: list[dict[str, Any]] = []

    # 处理 by_beat 结果
    by_beat = selection.get("by_beat", {})
    for beat_id, candidates in by_beat.items():
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                cid = candidate_to_canonical_id(candidate)
                title = candidate.get("title", candidate.get("page_title", ""))
                page_number = candidate.get("page_number", candidate.get("slide_index", 0))
                screenshot = candidate.get("screenshot_path", "")

                asset = create_slide_asset(
                    canonical_slide_id=cid,
                    source_path=candidate.get("source_pptx", ""),
                    page_number=page_number,
                    title=title,
                    file_sha256=candidate.get("file_sha256", ""),
                    screenshot_path=screenshot,
                    source_type="library_slide",
                    metadata={
                        "confidence": candidate.get("confidence", candidate.get("score", 0)),
                        "beat_id": beat_id,
                        "source_project": candidate.get("source_project", ""),
                    },
                )

                if workspace_dir:
                    register_asset(workspace_dir, asset)

                asset_refs.append({
                    "beat_id": beat_id,
                    "canonical_slide_id": cid,
                    "title": title,
                })
                registered_count += 1

            except Exception as e:
                errors.append(f"Failed to register candidate for beat {beat_id}: {e}")
                skipped_count += 1

    # 也处理顶层 candidates 列表
    top_candidates = selection.get("candidates", [])
    if isinstance(top_candidates, list):
        for candidate in top_candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                cid = candidate_to_canonical_id(candidate)
                # 检查是否已注册
                if any(ref["canonical_slide_id"] == cid for ref in asset_refs):
                    continue

                asset = create_slide_asset(
                    canonical_slide_id=cid,
                    source_path=candidate.get("source_pptx", ""),
                    page_number=candidate.get("page_number", candidate.get("slide_index", 0)),
                    title=candidate.get("title", candidate.get("page_title", "")),
                    file_sha256=candidate.get("file_sha256", ""),
                    screenshot_path=candidate.get("screenshot_path", ""),
                    source_type="library_slide",
                )

                if workspace_dir:
                    register_asset(workspace_dir, asset)

                asset_refs.append({
                    "beat_id": "",
                    "canonical_slide_id": cid,
                    "title": candidate.get("title", ""),
                })
                registered_count += 1
            except Exception as e:
                skipped_count += 1

    # 写 asset_refs.json
    asset_refs_data = {
        "run_id": run_id,
        "asset_refs": asset_refs,
    }
    refs_path = run_dir / "asset_refs.json"
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = refs_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asset_refs_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(refs_path)

    # 写 event
    try:
        append_typed_event(
            run_dir, "artifact_written", "ingest_library_results",
            f"Ingested {registered_count} library candidates as assets.",
            refs=["asset_refs.json"],
        )
    except Exception:
        pass

    # 空结果写 event
    if registered_count == 0:
        try:
            append_typed_event(
                run_dir, "step_completed", "ingest_library_results",
                "No library candidates to ingest.",
                severity="warn",
            )
        except Exception:
            pass

    return {
        "run_id": run_id,
        "registered_count": registered_count,
        "skipped_count": skipped_count,
        "errors": errors,
        "asset_refs": asset_refs,
    }
