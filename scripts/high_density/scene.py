from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_v2, read_json, utc_now, write_json

CANVAS = {"width": 1672, "height": 941, "unit": "px"}
SCENE_DIR = Path("high_density_build/page_scenes")
CANONICAL_SCENE_DIR = Path("high_density_build/scenes")


class PageSceneRequired(ContractError):
    def __init__(self, page_id: str) -> None:
        self.page_id = page_id
        super().__init__(f"page scene requires Agent reconstruction for page {page_id}")


def scene_path(root: Path, page_id: str) -> Path:
    return root / SCENE_DIR / f"{page_id}.json"


def canonical_scene_path(root: Path, page_id: str) -> Path:
    return root / CANONICAL_SCENE_DIR / f"{page_id}.page_scene.json"


def _block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        for key in ("text", "body", "description", "value", "title"):
            if block.get(key) is not None:
                return str(block[key])
        return " ".join(str(value) for value in block.values() if isinstance(value, (str, int, float)))
    return str(block or "")


def _block_title(block: Any, index: int) -> str:
    if isinstance(block, dict):
        for key in ("title", "label", "name", "heading"):
            if block.get(key):
                return str(block[key])
    return f"Key point {index + 1}"


def _component_id_for(element_id: str, role: str) -> str:
    if element_id == "title.main":
        return "component.title"
    if element_id.startswith("block."):
        return f"component.body.{element_id.split('.')[1]}"
    if element_id.startswith("so_what"):
        return "component.so_what"
    if element_id.startswith("sources"):
        return "component.sources"
    if element_id.startswith("labels"):
        return "component.labels"
    return f"component.{role or element_id}"


def _text_element(*, element_id: str, role: str, priority: str, bbox: dict[str, float], text: str, text_ref: str, preferred_size: float, min_size: float, max_lines: int, color: str = "#18212b", weight: str = "400", component_id: str = "") -> dict[str, Any]:
    return {
        "element_id": element_id,
        "component_id": component_id or _component_id_for(element_id, role),
        "kind": "text",
        "role": role,
        "priority": priority,
        "bbox": bbox,
        "source_blueprint_bbox": dict(bbox),
        "target_svg_bbox": dict(bbox),
        "target_ppt_bbox": dict(bbox),
        "z_index": 20,
        "text_ref": text_ref,
        "content_lock_text_ref": text_ref,
        "evidence_refs": [],
        "text": text,
        "text_fit": {"preferred_size_px": preferred_size, "min_size_px": min_size, "max_lines": max_lines, "line_height": 1.18},
        "overflow_policy": "block",
        "editability_target": "native_text",
        "asset_policy": "none",
        "style": {"fill": color, "font_family": "Arial", "font_weight": weight},
        "pptx_expectation": {"object_type": "text", "must_readback": priority in {"P0", "P1"}},
    }


def _rect_element(*, element_id: str, role: str, priority: str, bbox: dict[str, float], fill: str, stroke: str = "#d5dde5", radius: float = 12, component_id: str = "", z_index: int = 1) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "component_id": component_id or _component_id_for(element_id, role),
        "kind": "rect",
        "role": role,
        "priority": priority,
        "bbox": bbox,
        "source_blueprint_bbox": dict(bbox),
        "target_svg_bbox": dict(bbox),
        "target_ppt_bbox": dict(bbox),
        "z_index": z_index,
        "editability_target": "native_shape",
        "asset_policy": "none",
        "style": {"fill": fill, "stroke": stroke, "stroke_width": 1.5, "radius": radius},
    }


def build_fixture_scene(lock: dict[str, Any], blueprint_sha256: str, blueprint_path: Path | None = None) -> dict[str, Any]:
    customer_visible = lock.get("customer_visible") or {}
    enrichment = lock.get("enrichment") or {}
    title = str(customer_visible.get("title") or lock["page_id"])
    subtitle = str(customer_visible.get("subtitle") or "")
    body_blocks = list(customer_visible.get("body_blocks") or [])
    labels = list(customer_visible.get("labels") or [])
    footnotes = list(customer_visible.get("footnotes") or [])
    elements: list[dict[str, Any]] = []
    digest = int(hashlib.sha256(blueprint_sha256.encode("ascii")).hexdigest()[:8], 16)
    accent = ("#" + f"{0x2D + digest % 80:02x}{0x75 + digest % 60:02x}{0xC5 + digest % 30:02x}")
    elements.append(_rect_element(element_id="background", role="background", priority="P2", bbox={"x": 0, "y": 0, "w": 1672, "h": 941}, fill="#f7f9fb", stroke="#f7f9fb", radius=0, component_id="component.background", z_index=0))
    elements.append(_rect_element(element_id="header.rule", role="accent", priority="P2", bbox={"x": 80, "y": 156, "w": 1512, "h": 6}, fill=accent, stroke=accent, radius=3, component_id="component.header", z_index=2))
    elements.append(_text_element(element_id="title.main", role="title", priority="P0", bbox={"x": 80, "y": 56, "w": 1180, "h": 72}, text=title, text_ref="content_lock.customer_visible.title", preferred_size=42, min_size=30, max_lines=2, weight="700"))
    if subtitle:
        elements.append(_text_element(element_id="subtitle.main", role="subtitle", priority="P1", bbox={"x": 80, "y": 130, "w": 1350, "h": 32}, text=subtitle, text_ref="content_lock.customer_visible.subtitle", preferred_size=18, min_size=14, max_lines=1, color="#556474"))

    count = max(1, len(body_blocks))
    columns = 3 if count > 4 else 2
    rows = max(1, math.ceil(count / columns))
    gap_x, gap_y = 24, 22
    content_x, content_y, content_w, content_h = 80, 200, 1512, 600
    card_w = (content_w - gap_x * (columns - 1)) / columns
    card_h = (content_h - gap_y * (rows - 1)) / rows
    palette = ["#ffffff", "#eef5fb", "#fff3e8", "#edf7f1", "#f3effa", "#f8f1ed"]
    for index, block in enumerate(body_blocks):
        row, column = divmod(index, columns)
        x = content_x + column * (card_w + gap_x)
        y = content_y + row * (card_h + gap_y)
        block_id = f"block.{index + 1:02d}"
        component_id = f"component.body.{index + 1:02d}"
        elements.append(_rect_element(element_id=block_id, role="content_card", priority="P1", bbox={"x": x, "y": y, "w": card_w, "h": card_h}, fill=palette[(index + digest) % len(palette)], component_id=component_id, z_index=3))
        block_title = _block_title(block, index)
        body_text = _block_text(block)
        has_block_title = isinstance(block, dict) and any(block.get(key) for key in ("title", "label", "name", "heading"))
        if has_block_title:
            elements.append(_text_element(element_id=f"{block_id}.title", role="card_title", priority="P1", bbox={"x": x + 24, "y": y + 22, "w": card_w - 48, "h": 38}, text=block_title, text_ref=f"content_lock.customer_visible.body_blocks.{index}.title", preferred_size=22, min_size=16, max_lines=2, color="#1f3a54", weight="700", component_id=component_id))
            if body_text == block_title:
                body_text = ""
        if body_text:
            body_y = 72 if has_block_title else 22
            body_height = card_h - 96 if has_block_title else card_h - 44
            elements.append(_text_element(element_id=f"{block_id}.body", role="body", priority="P1", bbox={"x": x + 24, "y": y + body_y, "w": card_w - 48, "h": body_height}, text=body_text, text_ref=f"content_lock.customer_visible.body_blocks.{index}", preferred_size=18, min_size=13, max_lines=6, color="#364655", component_id=component_id))

    so_what = str(enrichment.get("so_what") or "")
    if so_what:
        elements.append(_rect_element(element_id="so_what.panel", role="so_what", priority="P0", bbox={"x": 80, "y": 820, "w": 1512, "h": 44}, fill="#eaf2fb", stroke="#c7d9ec", radius=6, component_id="component.so_what", z_index=4))
        elements.append(_text_element(element_id="so_what.text", role="so_what", priority="P0", bbox={"x": 100, "y": 828, "w": 1472, "h": 28}, text=so_what, text_ref="content_lock.enrichment.so_what", preferred_size=15, min_size=11, max_lines=1, color="#1f4f7d", weight="700", component_id="component.so_what"))
    if labels:
        elements.append(_text_element(element_id="labels.footer", role="label_row", priority="P2", bbox={"x": 80, "y": 866, "w": 1200, "h": 28}, text="  ·  ".join(str(label) for label in labels), text_ref="content_lock.customer_visible.labels", preferred_size=14, min_size=11, max_lines=1, color="#556474", component_id="component.labels"))
    if footnotes:
        elements.append(_text_element(element_id="sources.footer", role="sources", priority="P0", bbox={"x": 80, "y": 900, "w": 1512, "h": 24}, text="  ".join(str(note) for note in footnotes), text_ref="content_lock.customer_visible.footnotes", preferred_size=11, min_size=9, max_lines=1, color="#697887", component_id="component.sources"))

    required_components = list(lock.get("required_component_ids") or [])
    scene = {
        "schema_version": "deck_page_scene.v2",
        "run_id": lock["run_id"],
        "page_id": lock["page_id"],
        "source": "fixture_auto" if blueprint_path is None else "agent_reconstruction",
        "canvas": dict(CANVAS),
        "blueprint": {"source_canvas": dict(CANVAS), "slide_frame": {"x": 0, "y": 0, "w": 1672, "h": 941}, "source_to_scene_transform": {"scale": 1, "offset_x": 0, "offset_y": 0, "fit_mode": "approved_frame"}},
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "blueprint_sha256": blueprint_sha256,
        "transform": {"scale": 1, "offset_x": 0, "offset_y": 0, "fit_mode": "approved_frame"},
        "component_signature": [{"component_id": component_id, "present": any(item.get("component_id") == component_id for item in elements), "source": "content_lock"} for component_id in required_components],
        "required_component_ids": required_components,
        "required_text_refs": list(lock.get("required_text_refs") or []),
        "text_fit_policy": {"font_fallback": "Arial", "minimum_p0_p1_px": 9, "overflow": "block"},
        "overflow_policy": {"mode": "block", "allowed_font_scale": {"min": 0.75, "max": 1.0}},
        "unresolved_visual_elements": [],
        "background": {"fill": "#f7f9fb"},
        "elements": elements,
        "approved": False,
        "created_at": utc_now(),
    }
    validate_scene(scene)
    return scene


def validate_scene(scene: dict[str, Any]) -> None:
    assert_v2("page_scene", scene)
    canvas = scene.get("canvas") or CANVAS
    width, height = float(canvas.get("width") or 0), float(canvas.get("height") or 0)
    if width != CANVAS["width"] or height != CANVAS["height"] or canvas.get("unit") != CANVAS["unit"]:
        raise ContractError("page scene must use the canonical 1672x941 px canvas")
    ids: set[str] = set()
    for element in scene.get("elements", []):
        element_id = str(element.get("element_id") or "")
        if not element_id or element_id in ids:
            raise ContractError(f"scene element_id must be unique: {element_id}")
        ids.add(element_id)
        bbox = element.get("bbox") or {}
        try:
            x, y, w, h = (float(bbox.get(key) or 0) for key in ("x", "y", "w", "h"))
            z_index = int(element.get("z_index") or 0)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"scene element {element_id} has invalid geometry or z-order") from exc
        if not all(math.isfinite(value) for value in (x, y, w, h)):
            raise ContractError(f"scene element {element_id} has non-finite geometry")
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width + 0.01 or y + h > height + 0.01:
            raise ContractError(f"scene element {element_id} is out of canvas bounds")
        style = element.get("style") or {}
        try:
            opacity = float(style.get("opacity", 1))
            for key in ("stroke_width", "radius"):
                if key in style and style[key] is not None:
                    value = float(style[key])
                    if not math.isfinite(value) or value < 0:
                        raise ValueError(key)
            if not math.isfinite(opacity) or opacity <= 0 or opacity > 1:
                raise ValueError("opacity")
        except (TypeError, ValueError) as exc:
            raise ContractError(f"scene element {element_id} has invalid style values") from exc
        if str(element.get("kind") or "") == "text":
            ref = str(element.get("text_ref") or "")
            if not ref.startswith("content_lock."):
                raise ContractError(f"text element {element_id} must reference content_lock")
            fit = element.get("text_fit") or {}
            try:
                preferred = float(fit.get("preferred_size_px") or 0)
                minimum = float(fit.get("min_size_px") or 0)
                max_lines = int(fit.get("max_lines") or 0)
            except (TypeError, ValueError) as exc:
                raise ContractError(f"text element {element_id} has invalid fit policy") from exc
            if not all(math.isfinite(value) for value in (preferred, minimum)) or preferred <= 0 or minimum <= 0 or max_lines < 1:
                raise ContractError(f"text element {element_id} has invalid fit policy")
        if element.get("kind") == "image":
            if element.get("asset_policy") != "registered" or element.get("editability_target") != "registered_asset":
                raise ContractError(f"image element {element_id} must use registered asset policy")
        elif element.get("asset_policy") == "registered":
            raise ContractError(f"non-image element {element_id} cannot use registered asset policy")
    required = set(str(value) for value in scene.get("required_component_ids") or [])
    present = {str(element.get("component_id") or "") for element in scene.get("elements", [])}
    missing = sorted(value for value in required if value not in present)
    if missing:
        raise ContractError(f"scene is missing required components: {', '.join(missing)}")


def _resolve_ref(document: Any, ref: str) -> Any:
    value = document
    for part in ref.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ContractError(f"scene text reference cannot be resolved: {ref}")
    return value


def _reference_text(value: Any, role: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        separator = "  ·  " if role == "label_row" else "  " if role == "sources" else " "
        return separator.join(_reference_text(item, role) for item in value)
    if isinstance(value, dict):
        for key in ("text", "body", "description", "value", "title"):
            if value.get(key) is not None:
                return str(value[key])
        return " ".join(_reference_text(item, role) for item in value.values() if isinstance(item, (str, int, float)))
    return str(value or "")


def validate_scene_content(scene: dict[str, Any], lock: dict[str, Any]) -> None:
    actual_refs: set[str] = set()
    for element in scene.get("elements", []):
        if element.get("kind") != "text":
            continue
        ref = str(element.get("text_ref") or "")
        actual_refs.add(ref)
        lock_ref = ref.removeprefix("content_lock.")
        expected = _reference_text(_resolve_ref(lock, lock_ref), str(element.get("role") or ""))
        actual = str(element.get("text") or "")
        if actual != expected:
            raise ContractError(f"scene text drift in {element.get('element_id')}: expected locked text from {ref}")
    required_refs = {str(item.get("ref") or "") for item in lock.get("required_text_refs") or [] if isinstance(item, dict) and item.get("required", True)}
    missing = sorted(ref for ref in required_refs if ref not in actual_refs)
    if missing:
        raise ContractError(f"scene is missing required text refs: {', '.join(missing)}")


def load_scene(root: Path, page_id: str) -> dict[str, Any]:
    canonical = canonical_scene_path(root, page_id)
    legacy = scene_path(root, page_id)
    selected = canonical if canonical.exists() else legacy
    scene = read_json(selected)
    if canonical.exists() and legacy.exists() and read_json(legacy) != scene:
        raise ContractError(f"page scene mirror is stale on page {page_id}")
    validate_scene(scene)
    return scene


def write_scene(root: Path, scene: dict[str, Any]) -> Path:
    validate_scene(scene)
    page_id = str(scene["page_id"])
    canonical = canonical_scene_path(root, page_id)
    legacy = scene_path(root, page_id)
    write_json(canonical, scene)
    write_json(legacy, scene)
    return legacy


__all__ = [
    "CANVAS",
    "CANONICAL_SCENE_DIR",
    "PageSceneRequired",
    "build_fixture_scene",
    "canonical_scene_path",
    "load_scene",
    "scene_path",
    "validate_scene",
    "validate_scene_content",
    "write_scene",
]
