from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from page_roles import page_role_with_warning

from .contracts import ContractError, assert_v2, read_json, sha256_json, utc_now, write_json
from .visibility import assert_visible_text_allowed, validate_visibility_policy

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
    if element_id.startswith("business_implication"):
        return "component.business_implication"
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


def _rect_element(*, element_id: str, role: str, priority: str, bbox: dict[str, float], fill: str, stroke: str = "#d5dde5", radius: float = 12, stroke_width: float = 1.5, component_id: str = "", z_index: int = 1) -> dict[str, Any]:
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
        "style": {"fill": fill, "stroke": stroke, "stroke_width": stroke_width, "radius": radius},
    }


def _line_element(*, element_id: str, role: str, bbox: dict[str, float], stroke: str, stroke_width: float, component_id: str, z_index: int = 2) -> dict[str, Any]:
    return {
        "element_id": element_id,
        "component_id": component_id,
        "kind": "line",
        "role": role,
        "priority": "P2",
        "bbox": bbox,
        "source_blueprint_bbox": dict(bbox),
        "target_svg_bbox": dict(bbox),
        "target_ppt_bbox": dict(bbox),
        "z_index": z_index,
        "editability_target": "native_shape",
        "asset_policy": "none",
        "style": {"stroke": stroke, "stroke_width": stroke_width, "opacity": 1},
    }


def _fixture_icon_element(*, visual_id: str, bbox: dict[str, float], stroke: str) -> dict[str, Any]:
    x, y = float(bbox["x"]), float(bbox["y"])
    path = f"M {x:.2f} {y:.2f} L {x + 14:.2f} {y:.2f} L {x + 20:.2f} {y + 6:.2f} L {x + 54:.2f} {y + 6:.2f} L {x + 54:.2f} {y + 40:.2f} L {x:.2f} {y + 40:.2f} Z M {x:.2f} {y + 14:.2f} L {x + 54:.2f} {y + 14:.2f}"
    return {
        "element_id": f"{visual_id}.path",
        "visual_id": visual_id,
        "component_id": "component.icon.header",
        "kind": "path",
        "role": "icon",
        "priority": "P2",
        "bbox": dict(bbox),
        "source_blueprint_bbox": dict(bbox),
        "target_svg_bbox": dict(bbox),
        "target_ppt_bbox": dict(bbox),
        "z_index": 5,
        "path": path,
        "editability_target": "native_shape_group",
        "asset_policy": "none",
        "style": {"fill": "none", "stroke": stroke, "stroke_width": 3, "stroke-linecap": "round", "stroke-linejoin": "round", "fill-rule": "nonzero", "opacity": 1},
    }


def _fixture_icon_elements_from_blueprint(blueprint_path: Path | None, visual_id: str, fallback_bbox: dict[str, float]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Project the fixture's registered icon into the semantic Scene.

    The fixture deliberately exercises the same source forms accepted by the
    production parser: inherited groups, local symbol/use, multiple subpaths,
    curves, holes, opacity and transforms. The Scene stores the normalized
    native path commands so the later SVG and DrawingML stages consume the
    same geometry.
    """
    fallback = [_fixture_icon_element(visual_id=visual_id, bbox=fallback_bbox, stroke="#419bfd")]
    if blueprint_path is None or blueprint_path.suffix.lower() != ".svg":
        return fallback, dict(fallback_bbox)
    try:
        from .svg_native import SvgNativeError, commands_to_svg_path, parse_svg_native

        root = ElementTree.fromstring(blueprint_path.read_text(encoding="utf-8"))
        native = parse_svg_native(root)
    except (OSError, ElementTree.ParseError):
        return fallback, dict(fallback_bbox)
    except SvgNativeError as exc:
        raise ContractError(f"fixture visual registry icon cannot be normalized: {exc}") from exc
    groups = native.get("groups") or {}
    group = next(
        (
            value
            for value in groups.values()
            if str(value.get("visual_id") or "") == "icon.header"
            or str(value.get("group_id") or "") == "blueprint.icon.header"
        ),
        None,
    )
    if not group:
        return fallback, dict(fallback_bbox)
    native_by_id = {str(item.get("element_id") or ""): item for item in native.get("elements") or []}
    children = [native_by_id[str(child_id)] for child_id in group.get("child_ids") or [] if str(child_id) in native_by_id]
    if not children or any(not item.get("commands") for item in children):
        return fallback, dict(fallback_bbox)
    left = min(float(item["bbox"]["x"]) for item in children)
    top = min(float(item["bbox"]["y"]) for item in children)
    right = max(float(item["bbox"]["x"]) + float(item["bbox"]["w"]) for item in children)
    bottom = max(float(item["bbox"]["y"]) + float(item["bbox"]["h"]) for item in children)
    icon_bbox = {"x": left, "y": top, "w": right - left, "h": bottom - top}
    projected: list[dict[str, Any]] = []
    for index, item in enumerate(children, start=1):
        style = item.get("style") or {}
        element_id = f"{visual_id}.path" if len(children) == 1 else f"{visual_id}.path.{index:02d}"
        projected.append(
            {
                "element_id": element_id,
                "visual_id": visual_id,
                "component_id": "component.icon.header",
                "kind": "path",
                "role": "icon",
                "priority": "P2",
                "bbox": dict(item["bbox"]),
                "source_blueprint_bbox": dict(item["bbox"]),
                "target_svg_bbox": dict(item["bbox"]),
                "target_ppt_bbox": dict(item["bbox"]),
                "z_index": 5,
                "path": commands_to_svg_path(item["commands"]),
                "editability_target": "native_shape_group",
                "asset_policy": "none",
                "style": {
                    "fill": str(style.get("fill") or "none"),
                    "stroke": str(style.get("stroke") or "none"),
                    "stroke_width": float(style.get("stroke-width") or 0),
                    "stroke-linecap": str(style.get("stroke-linecap") or "butt"),
                    "stroke-linejoin": str(style.get("stroke-linejoin") or "miter"),
                    "fill-rule": str(style.get("fill-rule") or "nonzero"),
                    "opacity": float(style.get("opacity") or 1),
                    "fill_opacity": float(style.get("fill-opacity") or 1),
                    "stroke_opacity": float(style.get("stroke-opacity") or 1),
                },
            }
        )
    return projected, icon_bbox


def _visual_style_type(elements: list[dict[str, Any]]) -> str:
    fills = {str((element.get("style") or {}).get("fill") or "none").lower() for element in elements}
    strokes = {str((element.get("style") or {}).get("stroke") or "none").lower() for element in elements}
    has_fill = any(value not in {"none", "transparent"} for value in fills)
    has_stroke = any(value not in {"none", "transparent"} for value in strokes)
    if has_fill and has_stroke:
        return "filled-outline"
    if has_fill:
        return "filled"
    if any(str((element.get("style") or {}).get("stroke-linecap") or "").lower() == "round" for element in elements):
        return "outline-rounded"
    return "outline"


def _layout_boxes(layout_id: str, count: int) -> list[dict[str, float]]:
    layouts: dict[str, list[dict[str, float]]] = {
        "framework": [
            {"x": 80, "y": 200, "w": 744, "h": 289},
            {"x": 848, "y": 200, "w": 744, "h": 289},
            {"x": 80, "y": 511, "w": 744, "h": 289},
            {"x": 848, "y": 511, "w": 744, "h": 289},
        ],
        "process": [
            {"x": 80, "y": 200, "w": 360, "h": 600},
            {"x": 464, "y": 200, "w": 360, "h": 600},
            {"x": 848, "y": 200, "w": 360, "h": 600},
            {"x": 1232, "y": 200, "w": 360, "h": 600},
        ],
        "table": [
            {"x": 80, "y": 200, "w": 1512, "h": 300},
            {"x": 80, "y": 524, "w": 480, "h": 276},
            {"x": 596, "y": 524, "w": 480, "h": 276},
            {"x": 1112, "y": 524, "w": 480, "h": 276},
        ],
        "comparison": [
            {"x": 80, "y": 220, "w": 700, "h": 260},
            {"x": 892, "y": 220, "w": 700, "h": 260},
            {"x": 80, "y": 520, "w": 700, "h": 280},
            {"x": 892, "y": 520, "w": 700, "h": 280},
        ],
        "architecture": [
            {"x": 621, "y": 200, "w": 430, "h": 230},
            {"x": 80, "y": 500, "w": 430, "h": 300},
            {"x": 621, "y": 500, "w": 430, "h": 300},
            {"x": 1162, "y": 500, "w": 430, "h": 300},
        ],
        "data_story": [
            {"x": 80, "y": 200, "w": 980, "h": 600},
            {"x": 1084, "y": 200, "w": 508, "h": 180},
            {"x": 1084, "y": 410, "w": 508, "h": 180},
            {"x": 1084, "y": 620, "w": 508, "h": 180},
        ],
        "dense_narrative": [
            {"x": 80, "y": 200, "w": 488, "h": 280},
            {"x": 592, "y": 200, "w": 488, "h": 280},
            {"x": 1104, "y": 200, "w": 488, "h": 280},
            {"x": 80, "y": 520, "w": 1512, "h": 280},
        ],
    }
    selected = layouts.get(layout_id) or layouts["framework"]
    if count <= len(selected):
        return selected[:count]
    return selected + layouts["framework"][: max(0, count - len(selected))]


def _fixture_background(blueprint_path: Path | None) -> str:
    if blueprint_path is None or blueprint_path.suffix.lower() != ".svg":
        return "#f7f9fb"
    try:
        root = ElementTree.fromstring(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError):
        return "#f7f9fb"
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "rect":
            continue
        try:
            is_canvas = (
                float(node.get("x") or 0) == 0
                and float(node.get("y") or 0) == 0
                and float(node.get("width") or 0) >= CANVAS["width"]
                and float(node.get("height") or 0) >= CANVAS["height"]
            )
        except (TypeError, ValueError):
            continue
        if is_canvas:
            fill = str(node.get("fill") or "")
            if len(fill) == 7 and fill.startswith("#"):
                return fill
    return "#f7f9fb"


def _fixture_text_colors(background: str) -> tuple[str, str, str]:
    try:
        red, green, blue = (int(background[index : index + 2], 16) for index in (1, 3, 5))
        luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    except (TypeError, ValueError):
        luminance = 1.0
    if luminance < 0.42:
        return "#f7f9fb", "#d8e5f2", "#d8e5f2"
    return "#18212b", "#556474", "#697887"


def _fixture_blueprint_boxes(blueprint_path: Path | None, count: int) -> list[dict[str, Any]]:
    if blueprint_path is None or blueprint_path.suffix.lower() != ".svg":
        return []
    try:
        root = ElementTree.fromstring(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError):
        return []
    boxes: list[dict[str, float]] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "rect":
            continue
        try:
            box = {
                "x": float(node.get("x") or 0),
                "y": float(node.get("y") or 0),
                "w": float(node.get("width") or 0),
                "h": float(node.get("height") or 0),
                "fill": str(node.get("fill") or "#ffffff"),
                "stroke": str(node.get("stroke") or "#d5dde5"),
                "radius": float(node.get("rx") or 0),
                "stroke_width": float(node.get("stroke-width") or 1),
            }
        except (TypeError, ValueError):
            continue
        if box["y"] >= 180 and box["y"] + box["h"] <= 810 and box["w"] >= 240 and box["h"] >= 120:
            boxes.append(box)
    return boxes[:count] if len(boxes) >= count else []


def _fixture_blueprint_rule(blueprint_path: Path | None) -> dict[str, Any] | None:
    if blueprint_path is None or blueprint_path.suffix.lower() != ".svg":
        return None
    try:
        root = ElementTree.fromstring(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError):
        return None
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "path" or str(node.get("d") or "").strip() != "M80 156 H1592":
            continue
        try:
            stroke_width = float(node.get("stroke-width") or 6)
        except (TypeError, ValueError):
            stroke_width = 6
        return {"stroke": str(node.get("stroke") or "#419bfd"), "stroke_width": stroke_width}
    return None


def _fixture_blueprint_decorations(blueprint_path: Path | None) -> list[dict[str, Any]]:
    if blueprint_path is None or blueprint_path.suffix.lower() != ".svg":
        return []
    try:
        root = ElementTree.fromstring(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError):
        return []
    decorations: list[dict[str, Any]] = []
    index = 1
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "path":
            continue
        path = str(node.get("d") or "").strip()
        if path == "M80 156 H1592":
            continue
        if path not in {"M80 820 H1592", "M836 200 V800"}:
            continue
        try:
            stroke_width = float(node.get("stroke-width") or 2)
        except (TypeError, ValueError):
            stroke_width = 2
        if path == "M80 820 H1592":
            bbox = {"x": 80, "y": 820, "w": 1512, "h": 0.01}
        else:
            bbox = {"x": 836, "y": 200, "w": 0.01, "h": 600}
        decorations.append({"element_id": f"blueprint.decoration.{index:02d}", "bbox": bbox, "stroke": str(node.get("stroke") or "#d5dde5"), "stroke_width": stroke_width})
        index += 1
    return decorations


def build_fixture_scene(lock: dict[str, Any], blueprint_sha256: str, blueprint_path: Path | None = None, *, layout_id: str = "") -> dict[str, Any]:
    customer_visible = lock.get("customer_visible") or {}
    enrichment = lock.get("enrichment") or {}
    title = str(customer_visible.get("title") or lock["page_id"])
    subtitle = str(customer_visible.get("subtitle") or "")
    body_blocks = list(customer_visible.get("body_blocks") or [])
    callouts = list(customer_visible.get("callouts") or [])
    layout_id = layout_id or str((enrichment.get("material_pool") or {}).get("recommended_visual") or "framework")
    raw_page_role = (enrichment.get("analysis") or {}).get("page_role") or layout_id or "dense_narrative"
    page_role, role_warning = page_role_with_warning(raw_page_role, default="content")
    background = _fixture_background(blueprint_path)
    title_color, secondary_color, _source_color = _fixture_text_colors(background)
    elements: list[dict[str, Any]] = []
    digest = int(hashlib.sha256(blueprint_sha256.encode("ascii")).hexdigest()[:8], 16)
    accent = ("#" + f"{0x2D + digest % 80:02x}{0x75 + digest % 60:02x}{0xC5 + digest % 30:02x}")
    blueprint_rule = _fixture_blueprint_rule(blueprint_path)
    if blueprint_rule:
        accent = str(blueprint_rule["stroke"])
        rule_width = float(blueprint_rule["stroke_width"])
        rule_y = 156 - rule_width / 2
        rule_height = rule_width
        rule_stroke_width = 0
    else:
        rule_width = 1.5
        rule_y = 156
        rule_height = 6
        rule_stroke_width = rule_width
    elements.append(_rect_element(element_id="background", role="background", priority="P2", bbox={"x": 0, "y": 0, "w": 1672, "h": 941}, fill=background, stroke=background, radius=0, component_id="component.background", z_index=0))
    elements.append(_rect_element(element_id="header.rule", role="accent", priority="P2", bbox={"x": 80, "y": rule_y, "w": 1512, "h": rule_height}, fill=accent, stroke=accent, radius=0, stroke_width=rule_stroke_width, component_id="component.header", z_index=2))
    elements.append(_text_element(element_id="title.main", role="title", priority="P0", bbox={"x": 80, "y": 56, "w": 1180, "h": 72}, text=title, text_ref="content_lock.customer_visible.title", preferred_size=42, min_size=30, max_lines=2, color=title_color, weight="700"))
    if subtitle:
        elements.append(_text_element(element_id="subtitle.main", role="subtitle", priority="P1", bbox={"x": 80, "y": 130, "w": 1350, "h": 32}, text=subtitle, text_ref="content_lock.customer_visible.subtitle", preferred_size=18, min_size=14, max_lines=1, color=secondary_color))

    count = max(1, len(body_blocks))
    layout_boxes = _fixture_blueprint_boxes(blueprint_path, count) or _layout_boxes(layout_id, count)
    palette = ["#ffffff", "#eef5fb", "#fff3e8", "#edf7f1", "#f3effa", "#f8f1ed"]
    for index, block in enumerate(body_blocks):
        box = layout_boxes[index]
        x, y, card_w, card_h = box["x"], box["y"], box["w"], box["h"]
        block_id = f"block.{index + 1:02d}"
        component_id = f"component.body.{index + 1:02d}"
        elements.append(
            _rect_element(
                element_id=block_id,
                role="content_card",
                priority="P1",
                bbox={"x": x, "y": y, "w": card_w, "h": card_h},
                fill=str(box.get("fill") or palette[(index + digest) % len(palette)]),
                stroke=str(box.get("stroke") or "#d5dde5"),
                radius=float(box["radius"]) if "radius" in box else 12,
                stroke_width=float(box.get("stroke_width") or 1.5),
                component_id=component_id,
                z_index=3,
            )
        )
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

    for decoration in _fixture_blueprint_decorations(blueprint_path):
        elements.append(
            _line_element(
                element_id=str(decoration["element_id"]),
                role="blueprint_decoration",
                bbox=dict(decoration["bbox"]),
                stroke=str(decoration["stroke"]),
                stroke_width=float(decoration["stroke_width"]),
                component_id="component.blueprint.decoration",
                z_index=2,
            )
        )

    business_implication = str(enrichment.get("business_implication") or enrichment.get("so_what") or "")
    if callouts:
        callout_text = _reference_text(callouts, "callout")
        elements.append(_rect_element(element_id="callouts.panel", role="callout", priority="P0", bbox={"x": 80, "y": 764, "w": 1512, "h": 40}, fill="#fff7e8", stroke="#e6c989", radius=6, component_id="component.callouts", z_index=4))
        elements.append(_text_element(element_id="callouts.text", role="callout", priority="P0", bbox={"x": 100, "y": 771, "w": 1472, "h": 26}, text=callout_text, text_ref="content_lock.customer_visible.callouts", preferred_size=14, min_size=10, max_lines=1, color="#6d4e13", weight="700", component_id="component.callouts"))
    if business_implication:
        elements.append(_rect_element(element_id="business_implication.panel", role="business_implication", priority="P0", bbox={"x": 80, "y": 820, "w": 1512, "h": 44}, fill="#eaf2fb", stroke="#c7d9ec", radius=6, component_id="component.business_implication", z_index=4))
        elements.append(_text_element(element_id="business_implication.text", role="business_implication", priority="P0", bbox={"x": 100, "y": 828, "w": 1472, "h": 28}, text=business_implication, text_ref="content_lock.enrichment.business_implication", preferred_size=15, min_size=11, max_lines=1, color="#1f4f7d", weight="700", component_id="component.business_implication"))

    icon_visual_id = f"icon.header.{lock['page_id']}"
    fallback_icon_bbox = {"x": 1500, "y": 68, "w": 54, "h": 40}
    icon_elements, icon_bbox = _fixture_icon_elements_from_blueprint(blueprint_path, icon_visual_id, fallback_icon_bbox)
    elements.extend(icon_elements)

    required_components = list(lock.get("required_component_ids") or [])
    scene = {
        "schema_version": "deck_page_scene.v2",
        "run_id": lock["run_id"],
        "page_id": lock["page_id"],
        "source": "fixture_auto" if blueprint_path is None else "agent_reconstruction",
        "canvas": dict(CANVAS),
        "blueprint": {"source_canvas": dict(CANVAS), "slide_frame": {"x": 0, "y": 0, "w": 1672, "h": 941}, "source_to_scene_transform": {"scale": 1, "offset_x": 0, "offset_y": 0, "fit_mode": "approved_frame"}},
        "layout_id": layout_id,
        "page_role": page_role,
        "migration_warnings": [role_warning] if role_warning else [],
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "blueprint_sha256": blueprint_sha256,
        "transform": {"scale": 1, "offset_x": 0, "offset_y": 0, "fit_mode": "approved_frame"},
        "component_signature": [{"component_id": component_id, "present": any(item.get("component_id") == component_id for item in elements), "source": "content_lock"} for component_id in required_components],
        "scene_signature": sha256_json(
            {
                "blueprint_sha256": blueprint_sha256,
                "elements": [
                    {
                        "element_id": item["element_id"],
                        "kind": item["kind"],
                        "bbox": item["bbox"],
                        "z_index": item.get("z_index", 0),
                        "path": item.get("path", ""),
                        "style": item.get("style") or {},
                    }
                    for item in elements
                ],
            }
        ),
        "required_component_ids": required_components,
        "required_text_refs": list(lock.get("required_text_refs") or []),
        "visual_registry": [{"visual_id": icon_visual_id, "semantic_name": "folder process marker", "visual_type": "icon", "priority": "P2", "blueprint_bbox": dict(icon_bbox), "svg_group_id": icon_visual_id, "child_element_ids": [str(element["element_id"]) for element in icon_elements], "style_type": _visual_style_type(icon_elements), "acceptance_requirements": ["semantic identity", "negative space", "line width", "direction", "local crop metrics"]}],
        "text_fit_policy": {"font_fallback": "Arial", "minimum_p0_p1_px": 9, "overflow": "block"},
        "overflow_policy": {"mode": "block", "allowed_font_scale": {"min": 0.75, "max": 1.0}},
        "unresolved_visual_elements": [],
        "background": {"fill": background},
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
    visual_ids: set[str] = set()
    element_ids = {str(element.get("element_id") or "") for element in scene.get("elements", [])}
    for visual in scene.get("visual_registry") or []:
        visual_id = str(visual.get("visual_id") or "")
        if not visual_id or visual_id in visual_ids:
            raise ContractError(f"visual registry visual_id must be unique: {visual_id}")
        visual_ids.add(visual_id)
        group_id = str(visual.get("svg_group_id") or "")
        if not group_id:
            raise ContractError(f"visual registry requires svg_group_id: {visual_id}")
        child_ids = {str(value) for value in visual.get("child_element_ids") or []}
        if not child_ids:
            raise ContractError(f"visual registry {visual_id} requires native child elements")
        missing_children = sorted(child_ids - element_ids)
        if missing_children:
            raise ContractError(f"visual registry {visual_id} references missing scene children: {', '.join(missing_children)}")
        for child_id in child_ids:
            child = next(element for element in scene.get("elements", []) if str(element.get("element_id") or "") == child_id)
            if str(child.get("visual_id") or visual_id) != visual_id:
                raise ContractError(f"scene visual child {child_id} is bound to the wrong visual_id")


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
    policy = lock.get("visibility_policy") or {}
    validate_visibility_policy(policy, page_id=str(lock.get("page_id") or ""))
    lock_components = [str(value) for value in lock.get("required_component_ids") or []]
    scene_components = [str(value) for value in scene.get("required_component_ids") or []]
    if scene_components != lock_components:
        raise ContractError("scene required component set does not exactly match content lock")
    lock_text_requirements = list(lock.get("required_text_refs") or [])
    scene_text_requirements = list(scene.get("required_text_refs") or [])
    if scene_text_requirements != lock_text_requirements:
        raise ContractError("scene required text set does not exactly match content lock")
    signature = {
        str(item.get("component_id") or ""): bool(item.get("present"))
        for item in scene.get("component_signature") or []
        if isinstance(item, dict)
    }
    if set(signature) != set(lock_components) or not all(signature.values()):
        raise ContractError("scene component signature does not exactly cover content lock")
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
        assert_visible_text_allowed(policy, actual, page_id=str(lock.get("page_id") or ""), context=f"scene:{element.get('element_id')}")
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
