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


def create_gallery_sample(project, *, page_count=30, readonly=True):
    """Explicit mixed-layer fixture, not a reconstruction or PPT render claim.

    SVG and PPT-preview images are independently drawn synthetic layer examples;
    no actual PPT file, candidate, Attempt, quality approval, or Host call is
    fabricated. The manifest names visual deviations for a later user test.
    """
    import copy
    from pathlib import Path
    import uuid
    from PIL import Image, ImageDraw
    from .models import validate_schema
    from .pipeline import artifact

    if type(page_count) is not int or not 24 <= page_count <= 300:
        raise LocalStateError('page_count', 'gallery fixture requires 24 to 300 pages')
    create_sample(project, page_count=page_count, readonly=readonly)
    store = Store(project); doc = store.load_document()
    original_revision = doc['revision_id']
    deviations = {'p08', 'p19'}
    missing = {'p03', 'p14'}
    stale = {'p11', 'p21'}

    def synthetic_art(data, extension, role, entry, *, dependencies=(), derived_from=()):
        file = store.put_blob(data, ext=extension)
        ref = artifact(store, store.project_root / file['path'], role, page_id=entry['page_id'],
                       dependencies=dependencies, derived_from=derived_from)
        obj = store.read_object_json(ref)
        obj['limitations'] = ['Explicit synthetic layer fixture; not an actual model, SVG reconstruction or PPT rendering result.']
        return store.put_json_object(obj)

    def image_bytes(canvas):
        output = BytesIO(); canvas.save(output, format='PNG'); return output.getvalue()

    for index, entry in enumerate(doc['pages'], 1):
        page_id = entry['page_id']; old = entry['blueprint']
        old_image = store.read_object_json(old)['file']
        if page_id not in missing and (index % 3 == 0 or page_id in stale):
            canvas = Image.new('RGB', (960, 540), '#f7f7f7'); draw = ImageDraw.Draw(canvas)
            draw.rectangle((40, 40, 920, 500), outline='#56606a', width=3)
            draw.text((80, 150), f'PAGE {index:02} / SYNTHETIC PPT PREVIEW', fill='#23303a')
            for offset in range(4): draw.rectangle((80, 220 + offset * 42, 780 - offset * 60, 238 + offset * 42), fill='#c2cfda')
            entry['ppt_preview'] = synthetic_art(image_bytes(canvas), 'png', 'ppt_preview', entry,
                dependencies=[{'kind': 'blueprint', 'identity': 'page:' + page_id, 'sha256': old['sha256']}], derived_from=[old])
        if page_id in deviations or page_id in stale:
            with Image.open(BytesIO(store.read_object_bytes(old_image))) as image:
                canvas = image.convert('RGB')
            draw = ImageDraw.Draw(canvas)
            if page_id in deviations:
                draw.rectangle((0, 0, 960, 540), fill='#6b2468' if page_id == 'p08' else '#143e87')
                for offset in range(9): draw.rectangle((40, 35 + offset * 52, 920, 55 + offset * 52), fill='#e5adc5' if page_id == 'p08' else '#78bade')
                draw.text((80, 160), f'PAGE {index:02} / DENSE ALTERNATE COMPOSITION', fill='white')
            else:
                draw.rectangle((0, 480, 960, 540), fill='#d1e4d6')
                draw.text((60, 500), 'UPDATED ORIGINAL / SYNTHETIC REVISION', fill='#173523')
            entry['blueprint'] = synthetic_art(image_bytes(canvas), 'png', 'blueprint', entry,
                dependencies=[{'kind': 'content', 'identity': 'page:' + page_id, 'sha256': entry['page']['sha256']}])
        if index % 2 == 0 and page_id not in missing:
            content = f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><rect width="960" height="540" fill="#f0f3f4"/><rect x="40" y="40" width="12" height="440" fill="#28768a"/><text x="90" y="120" font-family="sans-serif" font-size="32" fill="#23333b">PAGE {index:02} / SYNTHETIC SVG LAYER</text><rect x="90" y="190" width="700" height="50" fill="#b0c8d0"/><rect x="90" y="280" width="500" height="50" fill="#cad9de"/></svg>'
            entry['svg'] = synthetic_art(content.encode(), 'svg', 'svg', entry,
                dependencies=[{'kind': 'blueprint', 'identity': 'page:' + page_id, 'sha256': entry['blueprint']['sha256']}], derived_from=[entry['blueprint']])
        if page_id in missing: entry['blueprint'] = None

    plan = copy.deepcopy(store.read_object_json(doc['content_plan']))
    old_plan = doc['content_plan']
    plan['plan_id'] = 'plan-' + uuid.uuid4().hex
    plan['version'] += 1; plan['previous_ref'] = old_plan
    goal_ids = [goal['goal_id'] for goal in plan['input']['goals']]
    chapter_size = (page_count + 2) // 3
    plan['input']['chapters'] = [{'chapter_id': f'chapter-{i + 1}', 'title': title, 'goal_ids': goal_ids[i * chapter_size:(i + 1) * chapter_size]}
        for i, title in enumerate(['项目与材料', '逐页制作', '检查与交付'])]
    validate_schema('content_plan', plan)
    doc['content_plan'] = store.put_json_object(plan)
    updated = bump_revision(doc, {'operation_id': 'synthetic-gallery', 'kind': 'task_update',
        'description': 'Explicit mixed-layer gallery fixture; no model or rendering claim', 'read_set': []})
    store.commit_change(base_revision=original_revision, document=updated, operation_id='synthetic-gallery')
    manifest = {'schema_version': 'gallery_fixture.v1', 'factory': FACTORY_VERSION, 'seed': 0,
        'page_count': page_count, 'page_ids': [entry['page_id'] for entry in doc['pages']], 'revision_id': updated['revision_id'],
        'original_revision': original_revision, 'style_deviation_pages': sorted(deviations), 'missing_original_pages': sorted(missing),
        'stale_ppt_preview_pages': sorted(stale), 'source_dimensions': [960, 540],
        'candidate_count': 0, 'attempt_count': 0, 'model_calls': 0, 'actual_ppt_rendering': False,
        'user_30_second_observation': 'not measured'}
    write_json(safe_path(Path(project), '.deckmaster', 'workbench', 'gallery-fixture.json'), manifest)
    return manifest
