"""Deterministic synthetic example content; never a production fallback.

Only explicit sample creation calls this factory. Runtime UUIDs differ, while
the content and image bytes for a given factory version are reproducible.
"""
from __future__ import annotations

from io import BytesIO

from . import service
from .local_state import LocalStateError, read_json, safe_path, write_json
from .models import bump_revision, validate_artifact_semantics
from .store import Store

FACTORY_VERSION = "workbench-synthetic.v1"


def sample_info(project):
    path = safe_path(project, ".deckmaster", "workbench", "sample.json")
    info = read_json(path)
    if info and (info.get("format") != FACTORY_VERSION or type(info.get("readonly")) is not bool):
        raise LocalStateError("sample", "unsupported synthetic sample marker")
    return info


def create_sample(project, *, page_count=5, readonly=True):
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    project = Path(project)
    if project.exists():
        raise LocalStateError("project", "sample destination must be a new directory")
    if type(page_count) is not int or not 1 <= page_count <= 300:
        raise LocalStateError("page_count", "sample requires 1 to 300 pages")
    titles = ["项目目标与阅读顺序", "材料如何成为内容", "每页保留原图与来源", "修改后需要重新确认", "交付前查看缺口"]
    pages = [{"schema_version": "deck_page_package.v2", "page_id": f"p{i:02}",
              "customer_visible": {"title": titles[(i - 1) % len(titles)], "body_blocks": []},
              "visual_spec": {"intent": "明确标注的合成流程示例，无真实客户事实", "reference_mode": "new_design"}}
             for i in range(1, page_count + 1)]
    plan = {"schema_version": "content_plan_input.v1", "input_summary": "合成样例用于理解工作台，不代表真实模型生成或客户验收。",
            "chapters": [{"chapter_id": "example", "title": "工作台使用示例", "goal_ids": ["g-" + p["page_id"] for p in pages]}],
            "goals": [{"goal_id": "g-" + p["page_id"], "page_id": p["page_id"], "purpose": p["customer_visible"]["title"],
                       "source_links": [], "unresolved_facts": ["合成示例，不提供客户事实。"]} for p in pages],
            "unresolved_facts": ["未执行真实 Host、专业质量检查或客户验收。"]}
    service.create(project, title="工作台合成示例", brief="阅读示例，了解整稿、内容、单页、任务与交付。", audience="第一次使用工作台的人",
                   project_format="workbench.v3", draft={"pages": pages, "content_plan": plan})
    store = Store(project)
    doc = store.load_document()
    # Pillow 10.0 is a supported dependency; its bitmap default has no size
    # argument. Scaling the small label image works across the supported range.
    font = ImageFont.load_default()
    def draw_label(canvas, position, text, size, color):
        box = font.getbbox(text)
        stamp = Image.new("RGBA", (box[2] + 2, box[3] + 2))
        ImageDraw.Draw(stamp).text((0, 0), text, font=font, fill=color)
        ratio = size / max(1, box[3])
        stamp = stamp.resize((int(stamp.width * ratio), int(stamp.height * ratio)), Image.Resampling.NEAREST)
        canvas.paste(stamp, position, stamp)
    for i, entry in enumerate(doc["pages"], 1):
        canvas = Image.new("RGB", (960, 540), "#f6f7f4")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((48, 48, 54, 450), fill="#148564")
        draw_label(canvas, (86, 60), "DECK MASTER / SYNTHETIC EXAMPLE", 27, "#148564")
        draw_label(canvas, (86, 150), f"{i:02}   Understand the workflow", 27, "#1c2824")
        for y, caption in [(236, "Materials > Content > Page"), (310, "Original image > Review > Delivery")]:
            draw.rounded_rectangle((86, y, 860, y + 54), radius=6, fill="#e5ebe4")
            draw_label(canvas, (106, y + 10), caption, 27, "#33483e")
        draw_label(canvas, (86, 450), "Synthetic diagram. No model call or quality approval.", 19, "#53635a")
        output = BytesIO()
        canvas.save(output, format="PNG")
        file_ref = store.put_blob(output.getvalue(), ext="png")
        # Use the shared Artifact builder to preserve the real read contract.
        from .pipeline import artifact
        path = store.project_root / file_ref["path"]
        entry["blueprint"] = artifact(store, path, "blueprint", page_id=entry["page_id"], dependencies=[
            {"kind": "content", "identity": "page:" + entry["page_id"], "sha256": entry["page"]["sha256"]}])
        validate_artifact_semantics(store.read_object_json(entry["blueprint"]))
    bumped = bump_revision(doc, {"operation_id": "synthetic-images", "kind": "task_update", "description": "Explicit synthetic sample images; no Host call", "read_set": []})
    store.commit_change(base_revision=doc["revision_id"], document=bumped, operation_id="synthetic-images")
    write_json(safe_path(project, ".deckmaster", "workbench", "sample.json"),
               {"format": FACTORY_VERSION, "readonly": readonly, "evidence_level": "synthetic", "model_calls": 0})
    return {"project_id": doc["project_id"], "page_count": page_count, "synthetic": True, "readonly": readonly}
