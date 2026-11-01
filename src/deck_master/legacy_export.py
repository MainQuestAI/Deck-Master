"""Read-only export of an old project into a neutral archive for deck import."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .store import Store, StoreError

FORMAT = "legacy-export.v1"
OPEN_ALLOWANCES = {"in_flight", "unknown"}
OPEN_TASKS = {"queued", "awaiting_host", "running"}
UNMAPPED_DOCUMENT_KEYS = (
    "annotations",
    "changes",
    "candidates",
    "style_recipes",
    "icon_recipes",
    "page_derivations",
    "style_references",
)


class LegacyExportError(ValueError):
    error_code = "invalid_input"
    exit_code = 2


def export_project(project: str | Path, out: str | Path) -> dict[str, Any]:
    root = Path(project).expanduser()
    destination = Path(out).expanduser()
    if destination.exists():
        raise LegacyExportError(f"输出目录已存在：{destination}；请指定新目录")
    store = Store(root)
    try:
        document = store.load_document()
    except StoreError as exc:
        raise LegacyExportError(
            f"无法读取旧项目：{exc}；请指定含 .deckmaster 的作品目录"
        ) from exc
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".legacy-export-", dir=parent))
    try:
        files_dir = staging / "files"
        files_dir.mkdir()
        unmapped: list[dict[str, Any]] = []
        manifest = {
            "format": FORMAT,
            "source": {
                "project_id": document.get("project_id") or "",
                "revision_id": document.get("revision_id") or "",
            },
            "brief": _brief(document),
            "materials": _materials(store, document, files_dir, unmapped),
            "framing": _framing(store, document, unmapped),
            "style": _style(store, document, files_dir, unmapped),
            "pages": _pages(store, document, files_dir, unmapped),
            "last_export": _last_export(store, document, files_dir, unmapped),
            "reviews": _objects(store, document.get("reviews") or [], "review", unmapped),
            "authorizations": _objects(
                store,
                ((document.get("collaboration") or {}).get("authorizations") or []),
                "authorization",
                unmapped,
            ),
            "open_calls": _open_calls(store, document, unmapped),
            "unmapped": unmapped,
        }
        _note_unmapped_document(document, unmapped)
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "status": "exported",
        "format": FORMAT,
        "out": str(destination),
        "pages": len(manifest["pages"]),
        "materials": len(manifest["materials"]),
        "files": len(list((destination / "files").iterdir())),
        "reviews": len(manifest["reviews"]),
        "authorizations": len(manifest["authorizations"]),
        "open_calls": len(manifest["open_calls"]),
        "unmapped": len(unmapped),
    }


def _brief(document: dict[str, Any]) -> dict[str, Any]:
    task = document.get("task") or {}
    return {
        "title": task.get("title") or "",
        "audience": task.get("audience") or "",
        "task_type": task.get("scenario") or "",
        "goal": task.get("brief") or "",
        "constraints": list(task.get("existing_decisions") or []),
        "page_limit": task.get("page_limit"),
    }


def _materials(
    store: Store,
    document: dict[str, Any],
    files_dir: Path,
    unmapped: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    materials = []
    for source in document.get("sources") or []:
        source_id = source.get("source_id") or ""
        extract = _read_json(store, source.get("extract"), "material", source_id, unmapped)
        file_name = ""
        text_file = ""
        status = "needs_tool"
        if extract is not None:
            status = extract.get("status") or status
            original = extract.get("original_file")
            file_name = _copy_ref(store, original, files_dir) if original else ""
            if not file_name:
                unmapped.append(
                    {
                        "kind": "material_file",
                        "id": source_id,
                        "reason": "材料原件不在对象库中，未写入档案",
                    }
                )
            text = extract.get("text")
            if isinstance(text, str) and text:
                text_file = _write_bytes(files_dir, text.encode("utf-8"), "txt")
        materials.append(
            {
                "id": source_id,
                "name": source.get("name") or "",
                "file": file_name,
                "text_file": text_file,
                "status": status,
            }
        )
    return materials


def _framing(
    store: Store,
    document: dict[str, Any],
    unmapped: list[dict[str, Any]],
) -> dict[str, Any]:
    framing = {
        "thesis": "",
        "pillars": [],
        "facts": [],
        "assumptions": [],
        "questions": [],
    }
    plan = _read_json(store, document.get("content_plan"), "content_plan", "", unmapped)
    if plan is not None:
        _apply_plan(plan, framing)
    narrative = _read_json(store, document.get("narrative"), "narrative", "", unmapped)
    if narrative is not None:
        _apply_narrative(narrative, framing, unmapped)
    return framing


def _apply_plan(plan: dict[str, Any], framing: dict[str, Any]) -> None:
    payload = plan.get("input") or {}
    summary = payload.get("input_summary")
    if isinstance(summary, str) and summary:
        framing["thesis"] = summary
    goals = {goal.get("goal_id"): goal for goal in payload.get("goals") or []}
    chapters = payload.get("chapters") or []
    if chapters:
        pillars = []
        for chapter in chapters:
            points = []
            for goal_id in chapter.get("goal_ids") or []:
                purpose = (goals.get(goal_id) or {}).get("purpose")
                if purpose:
                    points.append(purpose)
            for page_id in chapter.get("page_ids") or []:
                for goal in goals.values():
                    if goal.get("page_id") == page_id and goal.get("purpose"):
                        points.append(goal["purpose"])
            pillars.append({"title": chapter.get("title") or "", "points": points})
        framing["pillars"] = pillars
    elif payload.get("page_roles"):
        framing["pillars"] = [
            {
                "title": role.get("role") or role.get("intended_takeaway") or "",
                "points": [role["intended_takeaway"]] if role.get("intended_takeaway") else [],
            }
            for role in payload.get("page_roles") or []
        ]
    questions = list(payload.get("unresolved_facts") or [])
    for goal in payload.get("goals") or []:
        questions.extend(goal.get("unresolved_facts") or [])
    if questions:
        framing["questions"] = questions


def _apply_narrative(
    narrative: dict[str, Any],
    framing: dict[str, Any],
    unmapped: list[dict[str, Any]],
) -> None:
    job = narrative.get("communication_job") or {}
    if not framing["thesis"] and job.get("desired_outcome"):
        framing["thesis"] = job["desired_outcome"]
    central = narrative.get("central_node_id")
    for node in narrative.get("nodes") or []:
        statement = node.get("statement") or ""
        node_id = node.get("node_id") or ""
        role = node.get("role")
        authority = node.get("authority")
        if node_id == central and statement and not framing["thesis"]:
            framing["thesis"] = statement
            continue
        if authority == "reported_fact" or role == "evidence":
            if statement:
                framing["facts"].append(statement)
            continue
        if authority == "hypothesis":
            if statement:
                framing["assumptions"].append(statement)
            continue
        unmapped.append(
            {
                "kind": "narrative_node",
                "id": node_id,
                "reason": "主张图节点无法映射到 framing 的摘要字段",
            }
        )
    for issue in narrative.get("issues") or []:
        text = issue.get("statement") or issue.get("issue_id") or ""
        if text:
            framing["questions"].append(text)
    if narrative.get("edges"):
        unmapped.append(
            {
                "kind": "narrative_edges",
                "id": "",
                "reason": "主张图的边不映射到新 framing",
            }
        )


def _style(
    store: Store,
    document: dict[str, Any],
    files_dir: Path,
    unmapped: list[dict[str, Any]],
) -> dict[str, Any]:
    design = document.get("design_context") or {}
    canvas = design.get("canvas") or {}
    styles = design.get("styles") or []
    palette = []
    if styles:
        colors = styles[0].get("colors") or {}
        for value in colors.values():
            if isinstance(value, str) and value not in palette:
                palette.append(value)
    fonts = []
    for font in design.get("fonts") or []:
        family = font.get("family")
        if isinstance(family, str) and family and family not in fonts:
            fonts.append(family)
    assets = []
    for asset in design.get("assets") or []:
        asset_id = asset.get("asset_id") or asset.get("id") or ""
        artifact = _read_json(store, asset.get("artifact"), "asset", asset_id, unmapped)
        file_name = ""
        if artifact is not None:
            file_name = _copy_ref(store, artifact.get("file"), files_dir)
        if not file_name:
            unmapped.append(
                {
                    "kind": "asset",
                    "id": asset_id,
                    "reason": "素材文件无法复制",
                }
            )
            continue
        assets.append({"id": asset_id, "file": file_name})
    if canvas.get("fit"):
        unmapped.append(
            {
                "kind": "canvas_fit",
                "id": "",
                "reason": "新画布没有 fit 字段，导入时保留宽高",
            }
        )
    return {
        "canvas": {
            "width_px": int(canvas.get("width_px") or 1600),
            "height_px": int(canvas.get("height_px") or 900),
            "slide_width_in": float(canvas.get("slide_width_in") or 13.333),
            "slide_height_in": float(canvas.get("slide_height_in") or 7.5),
        },
        "palette": palette,
        "fonts": fonts,
        "assets": assets,
    }


def _pages(
    store: Store,
    document: dict[str, Any],
    files_dir: Path,
    unmapped: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    purposes, layouts, todos, refs = _page_plan_fields(store, document)
    pages = []
    for entry in document.get("pages") or []:
        page_id = entry.get("page_id") or ""
        page = _read_json(store, entry.get("page"), "page", page_id, unmapped)
        if page is None:
            continue
        visible = page.get("customer_visible") or {}
        extra = [key for key in visible if key not in {
            "title",
            "subtitle",
            "body_blocks",
            "labels",
            "footnotes",
            "callouts",
        }]
        for key in extra:
            unmapped.append(
                {
                    "kind": "page_content_field",
                    "id": f"{page_id}/{key}",
                    "reason": "页 content 含有新模型没有的字段",
                }
            )
        visual = page.get("visual_spec") or {}
        if visual.get("nodes") or visual.get("edges"):
            unmapped.append(
                {
                    "kind": "visual_spec",
                    "id": page_id,
                    "reason": "页上关系图不映射到新作品",
                }
            )
        pages.append(
            {
                "id": page_id,
                "purpose": purposes.get(page_id) or visual.get("intent") or "",
                "layout": layouts.get(page_id) or visual.get("layout_hint") or "",
                "content": {
                    "title": visible.get("title") or "",
                    "subtitle": visible.get("subtitle") or "",
                    "body_blocks": visible.get("body_blocks") or [],
                    "labels": visible.get("labels") or [],
                    "footnotes": visible.get("footnotes") or [],
                    "callouts": visible.get("callouts") or [],
                },
                "notes": page.get("speaker_notes") or "",
                "todo": todos.get(page_id) or [],
                "refs": refs.get(page_id) or [],
                "image": _artifact_file(store, entry.get("blueprint"), files_dir, "image", page_id, unmapped),
                "svg": _artifact_file(store, entry.get("svg"), files_dir, "svg", page_id, unmapped),
                "preview": _preview_file(store, entry.get("svg_preview"), files_dir, page_id, unmapped),
            }
        )
    return pages


def _page_plan_fields(
    store: Store,
    document: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    purposes: dict[str, str] = {}
    layouts: dict[str, str] = {}
    todos: dict[str, list[str]] = {}
    refs: dict[str, list[str]] = {}
    plan = _load(store, document.get("content_plan"))
    if plan is None:
        return purposes, layouts, todos, refs
    payload = plan.get("input") or {}
    for goal in payload.get("goals") or []:
        page_id = goal.get("page_id") or ""
        if not page_id:
            continue
        if goal.get("purpose"):
            purposes[page_id] = goal["purpose"]
        todos[page_id] = list(goal.get("unresolved_facts") or [])
        refs[page_id] = [
            f"{link.get('source_id')} {link.get('locator')}".strip()
            for link in goal.get("source_links") or []
            if link.get("source_id") or link.get("locator")
        ]
    for role in payload.get("page_roles") or []:
        page_id = role.get("page_id") or ""
        if page_id and role.get("role") and page_id not in purposes:
            purposes[page_id] = role["role"]
    return purposes, layouts, todos, refs


def _last_export(
    store: Store,
    document: dict[str, Any],
    files_dir: Path,
    unmapped: list[dict[str, Any]],
) -> dict[str, str] | None:
    ref = (document.get("outputs") or {}).get("pptx")
    if not ref:
        return None
    return _artifact_file(store, ref, files_dir, "last_export", "", unmapped)


def _artifact_file(
    store: Store,
    ref: dict[str, str] | None,
    files_dir: Path,
    kind: str,
    item_id: str,
    unmapped: list[dict[str, Any]],
) -> dict[str, str] | None:
    if not ref:
        return None
    artifact = _read_json(store, ref, kind, item_id, unmapped)
    if artifact is None:
        return None
    name = _copy_ref(store, artifact.get("file"), files_dir)
    if not name:
        unmapped.append(
            {
                "kind": kind,
                "id": item_id,
                "reason": "产物文件无法复制",
            }
        )
        return None
    return {"file": name}


def _preview_file(
    store: Store,
    ref: dict[str, str] | None,
    files_dir: Path,
    page_id: str,
    unmapped: list[dict[str, Any]],
) -> str | None:
    copied = _artifact_file(store, ref, files_dir, "preview", page_id, unmapped)
    if copied is None:
        return None
    return copied["file"]


def _objects(
    store: Store,
    refs: list[dict[str, str]],
    kind: str,
    unmapped: list[dict[str, Any]],
) -> list[Any]:
    values = []
    for index, ref in enumerate(refs):
        obj = _read_json(store, ref, kind, str(index), unmapped)
        if obj is not None:
            values.append(obj)
    return values


def _open_calls(
    store: Store,
    document: dict[str, Any],
    unmapped: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    calls = []
    for ref in document.get("tasks") or []:
        task = _read_json(store, ref, "task", "", unmapped)
        if task is None:
            continue
        task_id = task.get("task_id") or ""
        kind = task.get("kind") or ""
        listed = False
        for allowance in task.get("call_allowances") or []:
            state = allowance.get("state")
            if state not in OPEN_ALLOWANCES:
                continue
            calls.append(
                {
                    "task_id": task_id,
                    "allowance_id": allowance.get("allowance_id"),
                    "state": state,
                    "kind": kind,
                }
            )
            listed = True
        if not listed and task.get("status") in OPEN_TASKS:
            calls.append(
                {
                    "task_id": task_id,
                    "allowance_id": None,
                    "state": task.get("status"),
                    "kind": kind,
                }
            )
        unmapped.append(
            {
                "kind": "task",
                "id": task_id,
                "reason": "旧任务不恢复到新 run；在途调用只列入 open_calls",
            }
        )
    return calls


def _note_unmapped_document(document: dict[str, Any], unmapped: list[dict[str, Any]]) -> None:
    for key in UNMAPPED_DOCUMENT_KEYS:
        if document.get(key):
            unmapped.append(
                {
                    "kind": key,
                    "id": "",
                    "reason": "旧对象不映射到新作品",
                }
            )
    task = document.get("task") or {}
    if task.get("presentation_mode") and task.get("presentation_mode") != "live":
        unmapped.append(
            {
                "kind": "presentation_mode",
                "id": "",
                "reason": "演示方式没有对应的新 brief 字段",
            }
        )
    decisions = (document.get("collaboration") or {}).get("decisions") or []
    if decisions:
        unmapped.append(
            {
                "kind": "decisions",
                "id": "",
                "reason": "协作决定不映射到新作品",
            }
        )


def _load(store: Store, ref: dict[str, str] | None) -> Any | None:
    if not ref:
        return None
    try:
        return store.read_object_json(ref)
    except (StoreError, TypeError, KeyError):
        return None


def _read_json(
    store: Store,
    ref: dict[str, str] | None,
    kind: str,
    item_id: str,
    unmapped: list[dict[str, Any]],
) -> Any | None:
    if not ref:
        return None
    try:
        return store.read_object_json(ref)
    except (StoreError, TypeError, KeyError) as exc:
        unmapped.append(
            {
                "kind": kind,
                "id": item_id,
                "reason": f"对象无法读取：{exc}",
            }
        )
        return None


def _copy_ref(store: Store, ref: dict[str, str] | None, files_dir: Path) -> str:
    if not isinstance(ref, dict) or "path" not in ref:
        return ""
    try:
        data = store.read_object_bytes(ref)
    except (StoreError, TypeError, KeyError):
        return ""
    suffix = Path(ref["path"]).suffix.lstrip(".") or "bin"
    digest = ref.get("sha256") or hashlib.sha256(data).hexdigest()
    name = f"{digest}.{suffix}"
    target = files_dir / name
    if not target.exists():
        target.write_bytes(data)
    return name


def _write_bytes(files_dir: Path, data: bytes, suffix: str) -> str:
    digest = hashlib.sha256(data).hexdigest()
    name = f"{digest}.{suffix}"
    target = files_dir / name
    if not target.exists():
        target.write_bytes(data)
    return name
