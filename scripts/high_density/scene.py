from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_valid, read_json, utc_now, write_json

CANVAS = {"width": 1672, "height": 941, "unit": "px"}
SCENE_DIR = Path("high_density_build/page_scenes")


class PageSceneRequired(ContractError):
    def __init__(self, page_id: str) -> None:
        self.page_id = page_id
        super().__init__(f"page scene requires Agent reconstruction for page {page_id}")


def scene_path(root: Path, page_id: str) -> Path:
    return root / SCENE_DIR / f"{page_id}.json"


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


def _text_element(
    *,
    element_id: str,
    role: str,
    priority: str,
    bbox: dict[str, float],
    text: str,
    text_ref: str,
    preferred_size: float,
    min_size: float,
    max_lines: int,
    color: str = "#18212b",
    weight: str = "400",
) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "kind": "text",
        "role": role,
        "priority": priority,
        "bbox": bbox,
        "text_ref": text_ref,
        "evidence_refs": [],
        "text": text,
        "text_fit": {
            "preferred_size_px": preferred_size,
            "min_size_px": min_size,
            "max_lines": max_lines,
            "line_height": 1.18,
        },
        "overflow_policy": "block",
        "editability_target": "native_text",
        "asset_policy": "none",
        "style": {"fill": color, "font_family": "Arial", "font_weight": weight},
        "pptx_expectation": {"object_type": "text", "must_readback": priority in {"P0", "P1"}},
    }


def _rect_element(
    *,
    element_id: str,
    role: str,
    priority: str,
    bbox: dict[str, float],
    fill: str,
    stroke: str = "#d5dde5",
    radius: float = 12,
) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "kind": "rect",
        "role": role,
        "priority": priority,
        "bbox": bbox,
        "editability_target": "native_shape",
        "asset_policy": "none",
        "style": {"fill": fill, "stroke": stroke, "stroke_width": 1.5, "radius": radius},
    }


def build_fixture_scene(lock: dict[str, Any], blueprint_sha256: str) -> dict[str, Any]:
    customer_visible = lock.get("customer_visible") or {}
    title = str(customer_visible.get("title") or lock["page_id"])
    subtitle = str(customer_visible.get("subtitle") or "")
    body_blocks = list(customer_visible.get("body_blocks") or [])
    labels = list(customer_visible.get("labels") or [])
    footnotes = list(customer_visible.get("footnotes") or [])
    elements: list[dict[str, Any]] = []
    elements.append(_rect_element(element_id="background", role="background", priority="P2", bbox={"x": 0, "y": 0, "w": 1672, "h": 941}, fill="#f7f9fb", stroke="#f7f9fb", radius=0))
    elements.append(_rect_element(element_id="header.rule", role="accent", priority="P2", bbox={"x": 80, "y": 156, "w": 1512, "h": 6}, fill="#d96b3b", stroke="#d96b3b", radius=3))
    elements.append(_text_element(element_id="title.main", role="title", priority="P0", bbox={"x": 80, "y": 56, "w": 1180, "h": 72}, text=title, text_ref="content_lock.customer_visible.title", preferred_size=42, min_size=30, max_lines=2, weight="700"))
    if subtitle:
        elements.append(_text_element(element_id="subtitle.main", role="subtitle", priority="P1", bbox={"x": 80, "y": 130, "w": 1350, "h": 32}, text=subtitle, text_ref="content_lock.customer_visible.subtitle", preferred_size=18, min_size=14, max_lines=1, color="#556474"))

    count = max(1, len(body_blocks))
    columns = 3 if count > 4 else 2
    rows = max(1, math.ceil(count / columns))
    gap_x = 24
    gap_y = 22
    content_x = 80
    content_y = 200
    content_w = 1512
    content_h = 640
    card_w = (content_w - gap_x * (columns - 1)) / columns
    card_h = (content_h - gap_y * (rows - 1)) / rows
    palette = ["#ffffff", "#eef5fb", "#fff3e8", "#edf7f1", "#f3effa", "#f8f1ed"]
    for index, block in enumerate(body_blocks):
        row, column = divmod(index, columns)
        x = content_x + column * (card_w + gap_x)
        y = content_y + row * (card_h + gap_y)
        block_id = f"block.{index + 1:02d}"
        elements.append(_rect_element(element_id=block_id, role="content_card", priority="P1", bbox={"x": x, "y": y, "w": card_w, "h": card_h}, fill=palette[index % len(palette)]))
        block_title = _block_title(block, index)
        body_text = _block_text(block)
        has_block_title = isinstance(block, dict) and any(block.get(key) for key in ("title", "label", "name", "heading"))
        if has_block_title:
            elements.append(_text_element(element_id=f"{block_id}.title", role="card_title", priority="P1", bbox={"x": x + 24, "y": y + 22, "w": card_w - 48, "h": 38}, text=block_title, text_ref=f"content_lock.customer_visible.body_blocks.{index}.title", preferred_size=22, min_size=16, max_lines=2, color="#1f3a54", weight="700"))
            if body_text == block_title:
                body_text = ""
        else:
            body_text = _block_text(block)
        if body_text:
            body_y = 72 if has_block_title else 22
            body_height = card_h - 96 if has_block_title else card_h - 44
            elements.append(_text_element(element_id=f"{block_id}.body", role="body", priority="P1", bbox={"x": x + 24, "y": y + body_y, "w": card_w - 48, "h": body_height}, text=body_text, text_ref=f"content_lock.customer_visible.body_blocks.{index}", preferred_size=18, min_size=13, max_lines=6, color="#364655"))

    if labels:
        label_text = "  ·  ".join(str(label) for label in labels)
        elements.append(_text_element(element_id="labels.footer", role="label_row", priority="P2", bbox={"x": 80, "y": 866, "w": 1200, "h": 28}, text=label_text, text_ref="content_lock.customer_visible.labels", preferred_size=14, min_size=11, max_lines=1, color="#556474"))
    if footnotes:
        footnote_text = "  ".join(str(note) for note in footnotes)
        elements.append(_text_element(element_id="sources.footer", role="sources", priority="P0", bbox={"x": 80, "y": 900, "w": 1512, "h": 24}, text=footnote_text, text_ref="content_lock.customer_visible.footnotes", preferred_size=11, min_size=9, max_lines=1, color="#697887"))

    scene = {
        "schema_version": "deck_page_scene.v1",
        "run_id": lock["run_id"],
        "page_id": lock["page_id"],
        "source": "fixture_auto",
        "canvas": dict(CANVAS),
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "blueprint_sha256": blueprint_sha256,
        "transform": {"scale": 1, "offset_x": 0, "offset_y": 0, "fit_mode": "approved_frame"},
        "background": {"fill": "#f7f9fb"},
        "elements": elements,
        "created_at": utc_now(),
    }
    validate_scene(scene)
    return scene


def validate_scene(scene: dict[str, Any]) -> None:
    assert_valid("page_scene", scene)
    canvas = scene.get("canvas") or CANVAS
    width = float(canvas.get("width") or 0)
    height = float(canvas.get("height") or 0)
    if width != CANVAS["width"] or height != CANVAS["height"] or canvas.get("unit") != CANVAS["unit"]:
        raise ContractError("page scene must use the canonical 1672x941 px canvas")
    for element in scene.get("elements", []):
        bbox = element.get("bbox") or {}
        x = float(bbox.get("x") or 0)
        y = float(bbox.get("y") or 0)
        w = float(bbox.get("w") or 0)
        h = float(bbox.get("h") or 0)
        if x < 0 or y < 0 or x + w > width + 0.01 or y + h > height + 0.01:
            raise ContractError(
                f"scene element {element.get('element_id')} is out of canvas bounds"
            )
        if element.get("kind") == "text" and not str(element.get("text_ref") or "").startswith("content_lock."):
            raise ContractError(
                f"text element {element.get('element_id')} must reference content_lock"
            )
        if element.get("kind") == "image":
            if element.get("asset_policy") != "registered" or element.get("editability_target") != "registered_asset":
                raise ContractError(
                    f"image element {element.get('element_id')} must use registered asset policy"
                )
        elif element.get("asset_policy") == "registered":
            raise ContractError(
                f"non-image element {element.get('element_id')} cannot use registered asset policy"
            )


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
    for element in scene.get("elements", []):
        if element.get("kind") != "text":
            continue
        ref = str(element.get("text_ref") or "")
        lock_ref = ref.removeprefix("content_lock.")
        expected = _reference_text(_resolve_ref(lock, lock_ref), str(element.get("role") or ""))
        actual = str(element.get("text") or "")
        if actual != expected:
            raise ContractError(
                f"scene text drift in {element.get('element_id')}: expected locked text from {ref}"
            )


def load_scene(root: Path, page_id: str) -> dict[str, Any]:
    scene = read_json(scene_path(root, page_id))
    validate_scene(scene)
    return scene


def write_scene(root: Path, scene: dict[str, Any]) -> Path:
    validate_scene(scene)
    path = scene_path(root, str(scene["page_id"]))
    write_json(path, scene)
    return path


__all__ = [
    "CANVAS",
    "PageSceneRequired",
    "build_fixture_scene",
    "load_scene",
    "scene_path",
    "validate_scene",
    "validate_scene_content",
    "write_scene",
]
