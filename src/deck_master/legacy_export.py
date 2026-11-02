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
    root = Path(project).expanduser().resolve()
    destination = Path(out).expanduser()
    resolved_out = destination.resolve()
    if resolved_out.is_relative_to(root):
        raise LegacyExportError(
            f"输出目录位于旧项目之内：{resolved_out}；请写到项目目录之外"
        )
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
    if document.get("content_plan"):
        plan = _read_json(store, document.get("content_plan"), "content_plan", "", unmapped)
        if plan is not None:
            _apply_plan(plan, framing, unmapped)
    if document.get("narrative"):
        narrative = _read_json(store, document.get("narrative"), "narrative", "", unmapped)
        if narrative is not None:
            _apply_narrative(narrative, framing, unmapped)
    return framing


def _append_text(items: list[str], text: Any) -> None:
    if isinstance(text, str) and text and text not in items:
        items.append(text)


def _append_open_questions(
    questions: list[str], issues: Any, unmapped: list[dict[str, Any]], kind: str,
) -> None:
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        if issue.get("resolution") == "open":
            _append_text(questions, issue.get("question"))
        else:
            unmapped.append({"kind": kind, "id": issue.get("issue_id") or "",
                             "reason": f"已处理问题的状态未映射：{issue.get('resolution')}；{issue.get('question') or ''}"})


def _ref_labels(links: Any) -> list[str]:
    labels = []
    for link in links or []:
        if not isinstance(link, dict):
            continue
        label = f"{link.get('source_id') or ''} {link.get('locator') or ''}".strip()
        if label:
            labels.append(label)
    return labels


def _apply_plan(plan: dict[str, Any], framing: dict[str, Any], unmapped: list[dict[str, Any]]) -> None:
    payload = plan.get("input") if isinstance(plan.get("input"), dict) else {}
    summary = payload.get("input_summary")
    if isinstance(summary, str) and summary:
        framing["thesis"] = summary
    goals = {
        goal.get("goal_id"): goal
        for goal in payload.get("goals") or []
        if isinstance(goal, dict)
    }
    roles = [
        role for role in payload.get("page_roles") or [] if isinstance(role, dict)
    ]
    roles_by_page = {role.get("page_id"): role for role in roles}
    chapters = payload.get("chapters") or []
    if chapters:
        pillars = []
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            points: list[str] = []
            for goal_id in chapter.get("goal_ids") or []:
                _append_text(points, (goals.get(goal_id) or {}).get("purpose"))
            for page_id in chapter.get("page_ids") or []:
                role = roles_by_page.get(page_id) or {}
                _append_text(points, role.get("intended_takeaway"))
                for goal in goals.values():
                    if goal.get("page_id") == page_id:
                        _append_text(points, goal.get("purpose"))
            pillars.append({"title": chapter.get("title") or "", "points": points})
        framing["pillars"] = pillars
    elif roles:
        framing["pillars"] = [
            {
                "title": role.get("role") or role.get("intended_takeaway") or "",
                "points": [role["intended_takeaway"]] if role.get("intended_takeaway") else [],
            }
            for role in roles
        ]
    questions: list[str] = []
    for fact in payload.get("unresolved_facts") or []:
        _append_text(questions, fact)
    for goal in payload.get("goals") or []:
        if isinstance(goal, dict):
            for fact in goal.get("unresolved_facts") or []:
                _append_text(questions, fact)
    _append_open_questions(questions, payload.get("issues"), unmapped, "content_plan_issue")
    if questions:
        framing["questions"] = questions


def _apply_narrative(
    narrative: dict[str, Any],
    framing: dict[str, Any],
    unmapped: list[dict[str, Any]],
) -> None:
    central = narrative.get("central_node_id")
    for node in narrative.get("nodes") or []:
        statement = node.get("statement") or ""
        node_id = node.get("node_id") or ""
        authority = node.get("authority")
        mapped = False
        if node_id == central and statement:
            if framing["thesis"] and framing["thesis"] != statement:
                unmapped.append({"kind": "content_plan_summary", "id": "",
                                 "reason": f"中心主张优先，原计划摘要保留于此：{framing['thesis']}"})
            framing["thesis"] = statement
            mapped = True
        if authority in ("reported_fact", "calculation"):
            _append_text(framing["facts"], statement)
            mapped = True
        elif authority == "hypothesis":
            _append_text(framing["assumptions"], statement)
            mapped = True
        if not mapped:
            unmapped.append({"kind": "narrative_node", "id": node_id,
                             "reason": f"主张图节点未映射：authority={authority}；{statement}"})
    outcome = (narrative.get("communication_job") or {}).get("desired_outcome")
    if outcome:
        unmapped.append({"kind": "communication_job", "id": "",
                         "reason": f"沟通目标保留于此，不代填中心主张：{outcome}"})
    _append_open_questions(framing["questions"], narrative.get("issues"), unmapped, "narrative_issue")
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
            if artifact is not None:
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
    purposes, todos, refs = _page_plan_fields(store, document)
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
                "layout": visual.get("layout_hint") or "",
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
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    purposes: dict[str, str] = {}
    todos: dict[str, list[str]] = {}
    refs: dict[str, list[str]] = {}
    plan = _load(store, document.get("content_plan"))
    if plan is None:
        return purposes, todos, refs
    payload = plan.get("input") if isinstance(plan.get("input"), dict) else {}
    for goal in payload.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        page_id = goal.get("page_id") or ""
        if not page_id:
            continue
        if goal.get("purpose"):
            purposes[page_id] = goal["purpose"]
        todos[page_id] = [
            fact for fact in goal.get("unresolved_facts") or [] if isinstance(fact, str) and fact
        ]
        labels = _ref_labels(goal.get("source_links"))
        if labels:
            refs[page_id] = labels
    for role in payload.get("page_roles") or []:
        if not isinstance(role, dict):
            continue
        page_id = role.get("page_id") or ""
        if not page_id:
            continue
        if page_id not in purposes and role.get("role"):
            purposes[page_id] = role["role"]
        elif page_id not in purposes and role.get("intended_takeaway"):
            purposes[page_id] = role["intended_takeaway"]
        if page_id not in refs:
            labels = _ref_labels(role.get("source_links"))
            if labels:
                refs[page_id] = labels
    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict) or issue.get("resolution") != "open":
            continue
        question = issue.get("question")
        if not isinstance(question, str) or not question:
            continue
        for page_id in issue.get("affected_page_ids") or []:
            if not isinstance(page_id, str) or not page_id:
                continue
            bucket = todos.setdefault(page_id, [])
            if question not in bucket:
                bucket.append(question)
    return purposes, todos, refs


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
        unmapped.append(
            {
                "kind": kind,
                "id": item_id,
                "reason": "引用为空，对象未写入档案",
            }
        )
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
