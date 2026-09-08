from __future__ import annotations

import base64
import binascii
import hashlib
import html
import math
import re
import secrets
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

from .blueprint import load_blueprint_manifest
from .contracts import ContractError, assert_v2, read_json, safe_run_path, sha256_file, sha256_json, utc_now, write_json
from .integrity import sign_review_attestation, sign_runtime_payload, verify_review_attestation, verify_runtime_payload
from .review_policy import load_review_policy, resolve_review_policy
from .scene import load_scene
from .svg_paint import SvgPaintError, parse_node_paint, parse_svg_paint
from .svg_native import SvgNativeError, format_svg_native_error, parse_svg_native, svg_recovery_command
from .visual import VisualMetricsError, _svg_geometry_bbox, _text_contrast_metrics, compute_visual_metrics, normalize_blueprint, write_visual_metrics
from .visibility import assert_visible_text_allowed

from native_pptx.svg_pipeline import (  # SC-1.1 ND-01: single implementation in native_pptx
    FORBIDDEN_TAGS,
    PREVIEW_DIR,
    REVIEW_DIR,
    SVG_DIR,
    UNSUPPORTED_TAGS,
    SvgVisualError,
    main_review_receipt_path,
    metrics_path,
    preview_path,
    review_path,
    svg_path,
    validate_svg,
)
COMPARISON_DIR = Path("high_density_build/comparisons")
from native_pptx.canvas import CANVAS_HEIGHT, CANVAS_WIDTH, CANVAS_RATIO  # noqa: F401
IMAGE_HEAVY_PAGE_ROLES = {"cover", "section", "section_divider", "divider", "visual", "visual_divider", "image", "image_page"}



def _page_role_policy(page_role: str) -> dict[str, float]:
    if page_role in IMAGE_HEAVY_PAGE_ROLES:
        return {"max_single_image_area": 0.85, "max_total_image_area": 0.90}
    return {"max_single_image_area": 0.35, "max_total_image_area": 0.50}







def _run_mode(root: Path) -> str:
    try:
        value = str(read_json(root / "request.json").get("run_mode") or "fixture").strip().lower()
    except ContractError:
        value = "fixture"
    return value if value in {"fixture", "dev", "production", "benchmark"} else "production"


def _estimated_width(text: str, size: float) -> float:
    width = 0.0
    for char in text:
        width += size * (0.95 if ord(char) > 127 else 0.56)
    return width


def wrap_text(text: str, width: float, size: float, *, measure: Callable[[str], float] | None = None) -> list[str]:
    if not text:
        return [""]
    if width <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    tokens = list(text) if any(ord(char) > 127 for char in text) else re.split(r"(\s+)", text)
    for token in tokens:
        candidate = current + token
        if current and (measure(candidate) if measure else _estimated_width(candidate, size)) > width:
            lines.append(current.rstrip())
            current = token.lstrip()
        else:
            current = candidate
    if current.strip() or not lines:
        lines.append(current.rstrip())
    return lines


def _color(value: Any, default: str = "#18212b") -> str:
    text = str(value or default)
    return text if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else default


def _attrs(items: dict[str, Any]) -> str:
    return " ".join(f'{key}="{html.escape(str(value), quote=True)}"' for key, value in items.items())


def _text_svg(element: dict[str, Any], page_id: str) -> str:
    from PIL import ImageFont

    bbox = element["bbox"]
    fit = element["text_fit"]
    text = str(element.get("text") or "")
    size = float(fit.get("preferred_size_px") or 18)
    min_size = float(fit.get("min_size_px") or max(9, size * 0.7))
    max_lines = int(fit.get("max_lines") or 1)
    line_height = float(fit.get("line_height") or 1.18)
    style = element.get("style") or {}
    font_path = _font_path(str(style.get("font_family") or "Arial"), page_id, str(element["element_id"]), str(style.get("font_weight") or "400"))
    while True:
        # Match submission validation's font resolution and pixel-size rounding.
        font = ImageFont.truetype(str(font_path), max(1, round(size)))
        lines = wrap_text(text, float(bbox["w"]), size, measure=font.getlength)
        overflow = (
            len(lines) > max_lines
            or len(lines) * size * line_height > float(bbox["h"]) + 0.01
            or any(font.getlength(line) > float(bbox["w"]) + 0.01 for line in lines)
        )
        if not overflow or size <= min_size:
            break
        size = max(min_size, size - 1)
    if overflow:
        raise SvgVisualError(f"P0/P1 text overflow in {element['element_id']}", page_id=page_id)
    x = float(bbox["x"])
    y = float(bbox["y"])
    attrs = {
        "id": element["element_id"],
        "x": f"{x:.2f}",
        "y": f"{y + size:.2f}",
        "fill": _color(style.get("fill")),
        "font-family": str(style.get("font_family") or "Arial"),
        "font-size": f"{size:.2f}px",
        "font-weight": str(style.get("font_weight") or "400"),
        "opacity": str(style.get("opacity", 1)),
        "data-pptx-component": str(element.get("component_id") or ""),
        "data-pptx-z": str(element.get("z_index") or 0),
        "data-pptx-bounds": f"{x:.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
        "data-pptx-text": text,
        "data-pptx-text-ref": str(element.get("text_ref") or ""),
        "data-pptx-priority": str(element.get("priority") or ""),
    }
    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else f"{size * line_height:.2f}"
        tspans.append(f'<tspan x="{x:.2f}" dy="{dy}">{html.escape(line)}</tspan>')
    return f"<text {_attrs(attrs)}>{''.join(tspans)}</text>"


def _rect_svg(element: dict[str, Any]) -> str:
    bbox = element["bbox"]
    style = element.get("style") or {}
    attrs = {
        "id": element["element_id"],
        "x": f"{float(bbox['x']):.2f}",
        "y": f"{float(bbox['y']):.2f}",
        "width": f"{float(bbox['w']):.2f}",
        "height": f"{float(bbox['h']):.2f}",
        "rx": f"{float(style.get('radius') or 0):.2f}",
        "fill": _color(style.get("fill"), "none"),
        "stroke": _color(style.get("stroke"), "none"),
        "stroke-width": str(style.get("stroke_width") or 0),
        "opacity": str(style.get("opacity", 1)),
        "data-pptx-component": str(element.get("component_id") or ""),
        "data-pptx-z": str(element.get("z_index") or 0),
        "data-pptx-bounds": f"{float(bbox['x']):.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
    }
    return f"<rect {_attrs(attrs)}/>"


def _asset_data_uri(path: Path) -> str:
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower())
    if not mime:
        raise SvgVisualError(f"unsupported registered image asset: {path}", code="HD_ASSET_POLICY_BLOCKED")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _image_svg(element: dict[str, Any], asset: Path | None, page_id: str) -> str:
    if asset is None or not asset.is_file():
        raise SvgVisualError(f"registered image asset is unavailable for {element['element_id']}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=str(element.get("element_id") or ""))
    bbox = element["bbox"]
    if float(bbox["x"]) <= 0.01 and float(bbox["y"]) <= 0.01 and float(bbox["w"]) >= CANVAS_WIDTH - 0.01 and float(bbox["h"]) >= CANVAS_HEIGHT - 0.01:
        raise SvgVisualError("whole-page image wrapper is blocked", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    return (
        f'<image id="{html.escape(str(element["element_id"]), quote=True)}" '
        f'x="{float(bbox["x"]):.2f}" y="{float(bbox["y"]):.2f}" '
        f'width="{float(bbox["w"]):.2f}" height="{float(bbox["h"]):.2f}" '
        f'href="{_asset_data_uri(asset)}" data-pptx-asset="registered" '
        f'data-pptx-asset-id="{html.escape(str(element.get("asset_ref") or ""), quote=True)}" '
        f'data-pptx-component="{html.escape(str(element.get("component_id") or ""), quote=True)}" '
        f'data-pptx-z="{int(element.get("z_index") or 0)}" '
        f'data-pptx-priority="{html.escape(str(element.get("priority") or ""), quote=True)}" '
        f'data-pptx-bounds="{float(bbox["x"]):.2f},{float(bbox["y"]):.2f},{float(bbox["w"]):.2f},{float(bbox["h"]):.2f}"/>'
    )


def _wrap_visual_svg(element: dict[str, Any], rendered: str) -> str:
    visual_id = str(element.get("visual_id") or "")
    if not visual_id:
        return rendered
    return f'<g id="{html.escape(visual_id, quote=True)}" data-pptx-visual-id="{html.escape(visual_id, quote=True)}" data-pptx-group-id="{html.escape(visual_id, quote=True)}">{rendered}</g>'


def compile_svg(scene: dict[str, Any], output: Path, *, assets: dict[str, Path] | None = None) -> Path:
    from .scene import validate_scene

    page_id = str(scene["page_id"])
    page_role = str(scene.get("page_role") or "content")
    image_policy = _page_role_policy(page_role)
    try:
        validate_scene(scene)
    except ContractError as exc:
        raise SvgVisualError(str(exc), page_id=page_id, code="HD_PAGE_SCENE_INVALID") from exc
    scene_elements = list(scene.get("elements", []))
    image_area = 0.0
    p0_p1_text = [element for element in scene_elements if element.get("kind") == "text" and element.get("priority") in {"P0", "P1"}]
    for element in scene_elements:
        if element.get("kind") != "image":
            continue
        bbox = element.get("bbox") or {}
        area = float(bbox.get("w") or 0) * float(bbox.get("h") or 0)
        image_area += area
        if area / (CANVAS_WIDTH * CANVAS_HEIGHT) > image_policy["max_single_image_area"]:
            raise SvgVisualError(f"image asset exceeds {image_policy['max_single_image_area']:.0%} of canvas: {element.get('element_id')}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=str(element.get("element_id") or ""))
        image_z = int(element.get("z_index") or 0)
        for text in p0_p1_text:
            text_bbox = text.get("bbox") or {}
            overlap_w = max(0.0, min(float(bbox.get("x") or 0) + float(bbox.get("w") or 0), float(text_bbox.get("x") or 0) + float(text_bbox.get("w") or 0)) - max(float(bbox.get("x") or 0), float(text_bbox.get("x") or 0)))
            overlap_h = max(0.0, min(float(bbox.get("y") or 0) + float(bbox.get("h") or 0), float(text_bbox.get("y") or 0) + float(text_bbox.get("h") or 0)) - max(float(bbox.get("y") or 0), float(text_bbox.get("y") or 0)))
            if image_z >= int(text.get("z_index") or 0) and overlap_w * overlap_h > 0:
                raise SvgVisualError(f"image asset covers P0/P1 text: {element.get('element_id')} -> {text.get('element_id')}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=str(element.get("element_id") or ""))
    if image_area / (CANVAS_WIDTH * CANVAS_HEIGHT) > image_policy["max_total_image_area"]:
        raise SvgVisualError(f"registered image assets exceed {image_policy['max_total_image_area']:.0%} of canvas", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    rendered_elements: list[tuple[str, str]] = []

    def add_rendered(element: dict[str, Any], rendered: str) -> None:
        rendered_elements.append((str(element.get("visual_id") or ""), rendered))

    ordered_elements = sorted(enumerate(scene_elements), key=lambda item: (int(item[1].get("z_index") or 0), item[0]))
    for _, element in ordered_elements:
        kind = element.get("kind")
        if kind == "text":
            add_rendered(element, _text_svg(element, page_id))
        elif kind == "rect":
            add_rendered(element, _rect_svg(element))
        elif kind == "line":
            bbox = element["bbox"]
            style = element.get("style") or {}
            attrs = {
                "id": element["element_id"],
                "x1": f"{float(bbox['x']):.2f}",
                "y1": f"{float(bbox['y']):.2f}",
                "x2": f"{float(bbox['x']) + float(bbox['w']):.2f}",
                "y2": f"{float(bbox['y']) + float(bbox['h']):.2f}",
                "stroke": _color(style.get("stroke"), "#657485"),
                "stroke-width": str(style.get("stroke_width") or 2),
                "opacity": str(style.get("opacity", 1)),
                "data-pptx-component": str(element.get("component_id") or ""),
                "data-pptx-z": str(element.get("z_index") or 0),
                "data-pptx-bounds": f"{float(bbox['x']):.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
            }
            add_rendered(element, f"<line {_attrs(attrs)}/>")
        elif kind in {"circle", "ellipse"}:
            bbox = element["bbox"]
            style = element.get("style") or {}
            attrs = {
                "id": element["element_id"],
                "cx": f"{float(bbox['x']) + float(bbox['w']) / 2:.2f}",
                "cy": f"{float(bbox['y']) + float(bbox['h']) / 2:.2f}",
                "rx": f"{float(bbox['w']) / 2:.2f}",
                "ry": f"{float(bbox['h']) / 2:.2f}",
                "fill": _color(style.get("fill"), "none"),
                "stroke": _color(style.get("stroke"), "none"),
                "stroke-width": str(style.get("stroke_width") or 0),
                "opacity": str(style.get("opacity", 1)),
                "data-pptx-component": str(element.get("component_id") or ""),
                "data-pptx-z": str(element.get("z_index") or 0),
                "data-pptx-bounds": f"{float(bbox['x']):.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
            }
            add_rendered(element, f"<ellipse {_attrs(attrs)}/>")
        elif kind == "path":
            path_data = str(element.get("path") or "")
            if not path_data or re.search(r"[<>&]", path_data):
                raise SvgVisualError(f"invalid path data in {element['element_id']}", page_id=page_id)
            style = element.get("style") or {}
            fill = _color(style.get("fill"), "none")
            stroke = _color(style.get("stroke"), "none")
            add_rendered(element,
                f'<path id="{html.escape(str(element["element_id"]), quote=True)}" '
                f'd="{html.escape(path_data, quote=True)}" fill="{fill}" stroke="{stroke}" stroke-width="{style.get("stroke_width") or 0}" '
                f'opacity="{style.get("opacity", 1)}" fill-opacity="{style.get("fill_opacity", style.get("fill-opacity", 1))}" stroke-opacity="{style.get("stroke_opacity", style.get("stroke-opacity", 1))}" '
                f'stroke-linecap="{style.get("stroke-linecap", style.get("linecap", "butt"))}" stroke-linejoin="{style.get("stroke-linejoin", style.get("linejoin", "miter"))}" fill-rule="{style.get("fill-rule", style.get("fill_rule", "nonzero"))}" '
                f'data-pptx-component="{html.escape(str(element.get("component_id") or ""), quote=True)}" data-pptx-z="{element.get("z_index") or 0}" data-pptx-bounds="{float(element["bbox"]["x"]):.2f},{float(element["bbox"]["y"]):.2f},{float(element["bbox"]["w"]):.2f},{float(element["bbox"]["h"]):.2f}"/>'
            )
        elif kind == "polygon":
            points = element.get("points") or []
            if len(points) < 3:
                raise SvgVisualError(f"polygon needs at least three points in {element['element_id']}", page_id=page_id)
            style = element.get("style") or {}
            point_text = " ".join(f"{float(point[0]):.2f},{float(point[1]):.2f}" for point in points)
            add_rendered(element,
                f'<polygon id="{html.escape(str(element["element_id"]), quote=True)}" '
                f'points="{point_text}" fill="{_color(style.get("fill"), "none")}" '
                f'stroke="{_color(style.get("stroke"), "none")}" stroke-width="{style.get("stroke_width") or 0}" opacity="{style.get("opacity", 1)}" fill-rule="{style.get("fill-rule", "nonzero")}" '
                f'data-pptx-component="{html.escape(str(element.get("component_id") or ""), quote=True)}" data-pptx-z="{element.get("z_index") or 0}" data-pptx-bounds="{float(element["bbox"]["x"]):.2f},{float(element["bbox"]["y"]):.2f},{float(element["bbox"]["w"]):.2f},{float(element["bbox"]["h"]):.2f}"/>'
            )
        elif kind == "image":
            add_rendered(element, _image_svg(element, (assets or {}).get(str(element.get("asset_ref") or "")), page_id))
        else:
            raise SvgVisualError(f"unsupported scene element kind: {kind}", page_id=page_id)
    elements: list[str] = []
    index = 0
    while index < len(rendered_elements):
        visual_id, rendered = rendered_elements[index]
        if not visual_id:
            elements.append(rendered)
            index += 1
            continue
        children = [rendered]
        index += 1
        while index < len(rendered_elements) and rendered_elements[index][0] == visual_id:
            children.append(rendered_elements[index][1])
            index += 1
        elements.append(_wrap_visual_svg({"visual_id": visual_id}, "".join(children)))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" '
        f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" data-pptx-page-role="{html.escape(page_role, quote=True)}">'
        f'<g id="page.{html.escape(page_id, quote=True)}" data-pptx-bounds="0,0,{CANVAS_WIDTH},{CANVAS_HEIGHT}">'
        + "".join(elements)
        + "</g></svg>"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    validate_svg(output, page_id=page_id)
    return output



def _bbox_overlap(first: dict[str, float], second: dict[str, float]) -> float:
    width = max(0.0, min(first["x"] + first["w"], second["x"] + second["w"]) - max(first["x"], second["x"]))
    height = max(0.0, min(first["y"] + first["h"], second["y"] + second["h"]) - max(first["y"], second["y"]))
    return width * height


def _font_path(family: str, page_id: str, element_id: str, weight: str = "400") -> Path:
    requested = family.strip().strip("'\"") or "Arial"
    matcher = shutil.which("fc-match")
    if matcher:
        bold = str(weight).lower() in {"bold", "bolder", "600", "700", "800", "900"}
        pattern = requested + (":weight=bold" if bold else "")
        result = subprocess.run([matcher, pattern, "-f", "%{family}|%{file}\n"], capture_output=True, text=True)
        matched_family, _, matched_file = result.stdout.strip().partition("|")
        generic = requested.lower() in {"sans-serif", "serif", "monospace"}
        names = {name.strip().lower() for name in matched_family.split(",")}
        compatible_families = {
            "arial": {"arial", "arimo", "liberation sans"},
            "helvetica": {"helvetica", "arial", "arimo", "liberation sans"},
        }
        accepted_names = compatible_families.get(requested.lower(), {requested.lower()})
        if result.returncode == 0 and matched_file and (generic or bool(names & accepted_names)):
            path = Path(matched_file)
            if path.is_file():
                return path
    known = {
        "arial": Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        "helvetica": Path("/System/Library/Fonts/Helvetica.ttc"),
    }
    fallback = known.get(requested.lower())
    if fallback and fallback.is_file():
        return fallback
    raise SvgVisualError(f"unresolvable SVG font {requested} on {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW")


def _inherited_fill_opacity(node: Any, ancestors: list[Any]) -> float:
    # fill-opacity is inherited, not composited: a child's explicit value
    # replaces the closest ancestor value. `ancestors` is nearest-first.
    for candidate in [node, *ancestors]:
        if candidate.get("fill-opacity") is not None:
            return float(candidate.get("fill-opacity"))
    return 1.0


def _validate_svg_text(node: Any, scene_element: dict[str, Any], page_id: str, ancestors: list[Any]) -> None:
    from PIL import ImageFont

    element_id = str(node.get("id") or "")
    required_attributes = {"font-family", "font-size", "font-weight", "fill", "data-pptx-text", "data-pptx-text-ref"}
    missing_attributes = sorted(attribute for attribute in required_attributes if node.get(attribute) is None)
    if missing_attributes:
        raise SvgVisualError(f"SVG text style is incomplete on {element_id}: {', '.join(missing_attributes)}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW")
    expected_text = str(scene_element.get("text") or "")
    declared_text = str(node.get("data-pptx-text") or "")
    if declared_text != expected_text:
        raise SvgVisualError(f"SVG text drift on {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    if str(node.get("data-pptx-text-ref") or "") != str(scene_element.get("text_ref") or ""):
        raise SvgVisualError(f"SVG text ref drift on {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    fill = str(node.get("fill") or "").lower()
    direct_text = str(node.text or "") + "".join(str(child.tail or "") for child in node)
    if (direct_text.strip() and fill in {"", "none", "transparent"}) or str(node.get("visibility") or "").lower() == "hidden" or str(node.get("display") or "").lower() == "none":
        raise SvgVisualError(f"hidden SVG text is blocked: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    try:
        ancestor_opacity = 1.0
        for ancestor in ancestors:
            if str(ancestor.get("display") or "").lower() == "none" or str(ancestor.get("visibility") or "").lower() in {"hidden", "collapse"}:
                raise SvgVisualError(f"hidden SVG text ancestor is blocked: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
            ancestor_opacity *= float(ancestor.get("opacity", 1))
        opacity = ancestor_opacity * float(node.get("opacity", 1)) * _inherited_fill_opacity(node, ancestors)
        font_size = float(str(node.get("font-size") or "").removesuffix("px"))
    except ValueError as exc:
        raise SvgVisualError(f"SVG text style is invalid: {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW") from exc
    if (direct_text.strip() and opacity < 0.05) or font_size <= 0:
        raise SvgVisualError(f"hidden or invalid SVG text is blocked: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    bounds = _svg_geometry_bbox(node)
    font = ImageFont.truetype(str(_font_path(str(node.get("font-family") or "Arial"), page_id, element_id, str(node.get("font-weight") or "400"))), max(1, round(font_size)))
    tspans = [child for child in list(node) if str(child.tag).split("}")[-1] == "tspan"]
    if len(tspans) != len(list(node)):
        raise SvgVisualError(f"SVG text supports only direct tspan children: {element_id}", page_id=page_id, code="HD_SVG_UNSUPPORTED_ELEMENT")
    lines: list[str] = []
    current = str(node.text or "")
    line_steps: list[float] = []
    current_width = float(font.getlength(current))
    current_max_size = font_size
    line_widths: list[float] = []
    line_sizes: list[float] = []
    for tspan in tspans:
        allowed = {"x", "y", "dx", "dy", "fill", "fill-opacity", "opacity", "font-family", "font-size", "font-weight", "font-style"}
        unsupported = sorted(str(name).split("}")[-1] for name in tspan.attrib if str(name).split("}")[-1] not in allowed)
        if unsupported:
            raise SvgVisualError(
                f"unsupported SVG property {unsupported[0]} on {element_id} tspan; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id}",
                page_id=page_id,
                code="HD_SVG_UNSUPPORTED_PROPERTY",
            )
        text = "".join(tspan.itertext())
        tspan_fill = str(tspan.get("fill") or node.get("fill") or "").lower()
        try:
            tspan_opacity = (
                ancestor_opacity
                * float(node.get("opacity", 1))
                * float(tspan.get("opacity", 1))
                * _inherited_fill_opacity(tspan, [node, *ancestors])
            )
        except ValueError as exc:
            raise SvgVisualError(f"SVG tspan paint is invalid: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT") from exc
        if tspan_fill in {"", "none", "transparent"} or tspan_opacity < 0.05:
            raise SvgVisualError(f"hidden SVG text in tspan is blocked: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
        family = str(tspan.get("font-family") or node.get("font-family") or "Arial")
        try:
            tspan_size = float(str(tspan.get("font-size") or node.get("font-size") or "").removesuffix("px"))
            dy = float(str(tspan.get("dy") or 0).removesuffix("px"))
        except ValueError as exc:
            raise SvgVisualError(f"SVG tspan size or line offset is invalid: {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW") from exc
        if tspan_size <= 0:
            raise SvgVisualError(f"SVG tspan font size is invalid: {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW")
        tspan_font = ImageFont.truetype(str(_font_path(family, page_id, element_id, str(tspan.get("font-weight") or node.get("font-weight") or "400"))), max(1, round(tspan_size)))
        if current and (tspan.get("y") is not None or abs(dy) > 0.01):
            lines.append(current)
            line_widths.append(current_width)
            line_sizes.append(current_max_size)
            current = text
            current_width = float(tspan_font.getlength(text))
            current_max_size = tspan_size
            line_steps.append(abs(dy))
        else:
            current += text
            current_width += float(tspan_font.getlength(text))
            current_max_size = max(current_max_size, tspan_size)
        tail = str(tspan.tail or "")
        current += tail
        current_width += float(font.getlength(tail))
    if current or not lines:
        lines.append(current)
        line_widths.append(current_width)
        line_sizes.append(current_max_size)
    visible_text = " ".join(line.strip() for line in lines)
    # CJK wraps introduce no word separator. Only remove a visual line boundary
    # between CJK characters/punctuation; preserve real whitespace and require
    # exact source characters, so English word boundaries cannot disappear.
    cjk_boundary = re.compile(r"[\u2e80-\ua4cf\uf900-\ufaff\uff00-\uffef]")
    cjk_visible = lines[0] if lines else ""
    for previous, following in zip(lines, lines[1:]):
        joiner = "" if (
            previous and following
            and cjk_boundary.fullmatch(previous[-1])
            and cjk_boundary.fullmatch(following[0])
        ) else " "
        cjk_visible += joiner + following
    if " ".join(declared_text.split()) != " ".join(visible_text.split()) and declared_text != cjk_visible:
        raise SvgVisualError(f"visible SVG text drift on {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    if any(step < font_size * 0.7 or step > font_size * 2.5 for step in line_steps):
        raise SvgVisualError(f"SVG tspan line height is invalid: {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW")
    measured_width = max(line_widths, default=0.0)
    measured_height = max(sum(line_sizes), font_size + sum(line_steps or [font_size * 1.18] * max(0, len(lines) - 1)))
    if measured_width > bounds["w"] + 1 or measured_height > bounds["h"] + 1:
        raise SvgVisualError(f"SVG text overflow in {element_id}", page_id=page_id, code="HD_SVG_TEXT_OVERFLOW")


def validate_approved_svg(
    path: Path,
    scene: dict[str, Any],
    lock: dict[str, Any],
    assets: dict[str, Path] | None = None,
) -> dict[str, Any]:
    from .scene import validate_scene_content

    page_id = str(scene.get("page_id") or lock.get("page_id") or "")
    page_role = str(scene.get("page_role") or ((lock.get("enrichment") or {}).get("analysis") or {}).get("page_role") or "content")
    image_policy = _page_role_policy(page_role)
    validate_scene_content(scene, lock)
    result = validate_svg(path, page_id=page_id)
    root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    try:
        native_document = parse_svg_native(root)
    except SvgNativeError as exc:
        raise SvgVisualError(format_svg_native_error(exc, page_id=page_id), page_id=page_id, code=exc.code) from exc
    native_elements = {str(item.get("element_id") or ""): item for item in native_document.get("elements") or []}
    native_by_source = {str(item.get("source_element_id") or ""): item for item in native_document.get("elements") or []}
    registered_group_ids = {str(visual.get("svg_group_id") or visual.get("visual_id") or "") for visual in scene.get("visual_registry") or []}
    for group_id in native_document.get("groups") or {}:
        if str(group_id) not in registered_group_ids:
            raise SvgVisualError(
                f"approved SVG contains an unregistered visual group {group_id}; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id}",
                page_id=page_id,
                code="HD_SVG_VISUAL_REGISTRY_UNREGISTERED",
            )
    for visual in scene.get("visual_registry") or []:
        if not isinstance(visual, dict):
            continue
        visual_id = str(visual.get("visual_id") or "")
        group_id = str(visual.get("svg_group_id") or visual_id)
        group = (native_document.get("groups") or {}).get(group_id)
        if group is None:
            raise SvgVisualError(f"approved SVG is missing registered visual group {visual_id}; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id}", page_id=page_id, code="HD_SVG_VISUAL_REGISTRY_MISSING")
        expected_children = {str(value) for value in visual.get("child_element_ids") or []}
        actual_children = {str(value) for value in group.get("child_ids") or []}
        if expected_children != actual_children:
            missing_children = sorted(expected_children - actual_children)
            extra_children = sorted(actual_children - expected_children)
            details = []
            if missing_children:
                details.append(f"missing={','.join(missing_children)}")
            if extra_children:
                details.append(f"extra={','.join(extra_children)}")
            raise SvgVisualError(
                f"visual registry {visual_id} child set drift: {'; '.join(details)}; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id}",
                page_id=page_id,
                code="HD_SVG_VISUAL_REGISTRY_MISSING",
            )
    parents = {child: parent for parent in root.iter() for child in list(parent)}
    visible_tags = {"text", "rect", "circle", "ellipse", "line", "path", "polyline", "polygon", "image"}
    visible_nodes = [node for node in root.iter() if str(node.tag).split("}")[-1] in visible_tags]
    for node in visible_nodes:
        if str(node.tag).split("}")[-1] == "text":
            assert_visible_text_allowed(
                lock.get("visibility_policy") or {},
                "".join(node.itertext()),
                page_id=page_id,
                context=f"svg:{node.get('id') or '<unnamed>'}",
            )
    nodes = {str(node.get("id") or ""): node for node in visible_nodes}
    scene_elements = {str(element.get("element_id") or ""): element for element in scene.get("elements") or []}
    for element_id, element in scene_elements.items():
        node = nodes.get(element_id)
        if node is None and element_id not in native_elements and element_id in native_by_source:
            node = native_by_source[element_id].get("node")
        if node is None and element_id not in native_elements:
            raise SvgVisualError(
                f"approved SVG is missing scene element: {element_id}; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id}",
                page_id=page_id,
                code="HD_SVG_CONTENT_DRIFT",
            )
    required_components = set(str(value) for value in lock.get("required_component_ids") or [])
    present_components = {str(node.get("data-pptx-component") or "") for node in visible_nodes}
    present_components.update(str(item.get("node").get("data-pptx-component") or "") for item in native_elements.values() if item.get("node") is not None)
    missing_components = sorted(required_components - present_components)
    if missing_components:
        raise SvgVisualError(f"approved SVG is missing required components: {', '.join(missing_components)}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
    required_text = [element for element in scene_elements.values() if element.get("kind") == "text"]
    for element in required_text:
        element_id = str(element.get("element_id") or "")
        node = nodes.get(element_id)
        if node is None or str(node.tag).split("}")[-1] != "text":
            raise SvgVisualError(f"approved SVG is missing required text element: {element_id}", page_id=page_id, code="HD_SVG_CONTENT_DRIFT")
        ancestors: list[Any] = []
        parent = parents.get(node)
        while parent is not None:
            ancestors.append(parent)
            parent = parents.get(parent)
        _validate_svg_text(node, element, page_id, ancestors)
    dom_order = {str(node.get("id") or ""): index for index, node in enumerate(visible_nodes)}
    previous_z = -10**9
    for node in visible_nodes:
        try:
            z_index = int(node.get("data-pptx-z") or 0)
        except ValueError as exc:
            raise SvgVisualError(f"SVG z-order is invalid on {node.get('id')}", page_id=page_id, code="HD_SVG_Z_ORDER") from exc
        if z_index < previous_z:
            raise SvgVisualError(f"SVG DOM z-order drifts on {node.get('id')}", page_id=page_id, code="HD_SVG_Z_ORDER")
        previous_z = z_index
    image_area = 0.0
    canvas_area = CANVAS_WIDTH * CANVAS_HEIGHT
    p0_p1_text = [element for element in required_text if element.get("priority") in {"P0", "P1"}]
    for node in visible_nodes:
        if str(node.tag).split("}")[-1] != "image":
            continue
        element_id = str(node.get("id") or "")
        scene_element = scene_elements.get(element_id)
        if not scene_element or scene_element.get("kind") != "image":
            raise SvgVisualError(f"SVG image is not registered in Scene: {element_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id)
        bbox = _svg_geometry_bbox(node)
        area = bbox["w"] * bbox["h"]
        image_area += area
        if area / canvas_area > image_policy["max_single_image_area"]:
            raise SvgVisualError(f"image asset exceeds {image_policy['max_single_image_area']:.0%} of canvas: {element_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id)
        asset_id = str(scene_element.get("asset_ref") or "")
        asset_path = (assets or {}).get(asset_id)
        if asset_path is None or not asset_path.is_file() or sha256_file(asset_path) != str(scene_element.get("asset_sha256") or ""):
            raise SvgVisualError(f"registered image asset hash mismatch: {asset_id or element_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id)
        href = str(node.get("href") or node.get("{http://www.w3.org/1999/xlink}href") or "")
        try:
            embedded = base64.b64decode(href.split(",", 1)[1], validate=True)
        except (IndexError, ValueError, binascii.Error) as exc:
            raise SvgVisualError(f"embedded image payload is invalid: {element_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id) from exc
        if hashlib.sha256(embedded).hexdigest() != sha256_file(asset_path) or str(node.get("data-pptx-asset-id") or "") != asset_id:
            raise SvgVisualError(f"embedded image asset lineage mismatch: {element_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id)
        for text in p0_p1_text:
            text_id = str(text.get("element_id") or "")
            if dom_order[element_id] > dom_order.get(text_id, -1) and _bbox_overlap(bbox, _svg_geometry_bbox(nodes[text_id])) > 0:
                raise SvgVisualError(f"image asset covers P0/P1 text: {element_id} -> {text_id}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=element_id)
    if image_area / canvas_area > image_policy["max_total_image_area"]:
        raise SvgVisualError(f"registered image assets exceed {image_policy['max_total_image_area']:.0%} of canvas", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    contrast = _text_contrast_metrics(path, scene)
    low_contrast = [element_id for element_id, value in contrast["elements"].items() if float(value["contrast_ratio"]) < 3.0]
    if low_contrast:
        raise SvgVisualError(
            f"P0/P1 SVG text contrast is below 3.0: {', '.join(low_contrast)}",
            page_id=page_id,
            code="HD_SVG_CONTENT_DRIFT",
        )
    return result


def render_preview(svg: Path, preview: Path) -> Path:
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise SvgVisualError("rsvg-convert is required for native SVG preview")
    preview.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([converter, "-w", str(CANVAS_WIDTH), "-h", str(CANVAS_HEIGHT), "-o", str(preview), str(svg)], capture_output=True, text=True)
    if result.returncode != 0 or not preview.exists() or preview.stat().st_size == 0:
        raise SvgVisualError(f"SVG preview failed: {result.stderr.strip() or 'unknown converter error'}")
    return preview


def _review_evidence(
    *,
    status: str,
    source: str,
    reviewer_id: str,
    action_id: str,
    reviewed_at: str | None,
    svg_sha256: str,
    blueprint_sha256: str,
    metrics_sha256: str,
    full_page_check: str,
    region_check_ids: list[str],
    issues_found: list[dict[str, Any]],
    revision_required: bool,
    evidence_sha256: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "reviewer_id": reviewer_id,
        "action_id": action_id,
        "reviewed_at": reviewed_at,
        "svg_sha256": svg_sha256,
        "blueprint_sha256": blueprint_sha256,
        "metrics_sha256": metrics_sha256,
        "full_page_check": full_page_check,
        "region_check_ids": list(region_check_ids),
        "issues_found": list(issues_found),
        "revision_required": revision_required,
        "evidence_sha256": evidence_sha256,
    }


def _region_bbox(elements: list[dict[str, Any]]) -> dict[str, float]:
    if not elements:
        return {"x": 0.0, "y": 0.0, "w": float(CANVAS_WIDTH), "h": float(CANVAS_HEIGHT)}
    left = min(float((element.get("bbox") or {}).get("x") or 0) for element in elements)
    top = min(float((element.get("bbox") or {}).get("y") or 0) for element in elements)
    right = max(float((element.get("bbox") or {}).get("x") or 0) + float((element.get("bbox") or {}).get("w") or 0) for element in elements)
    bottom = max(float((element.get("bbox") or {}).get("y") or 0) + float((element.get("bbox") or {}).get("h") or 0) for element in elements)
    return {"x": left, "y": top, "w": max(0.0, right - left), "h": max(0.0, bottom - top)}


def _build_region_checks(scene: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    elements = [element for element in scene.get("elements") or [] if isinstance(element, dict)]
    title = [element for element in elements if element.get("kind") == "text" and str(element.get("text_ref") or "").endswith(".title") and element.get("priority") == "P0"]
    insight = [element for element in elements if "business_implication" in str(element.get("component_id") or "") or "business_implication" in str(element.get("text_ref") or "")]
    footer = [element for element in elements if "source" in str(element.get("component_id") or "") or "footnotes" in str(element.get("text_ref") or "")]
    main = [element for element in elements if element not in title and element not in insight and element not in footer]
    groups = {
        "title": title,
        "main_visual": main,
        "business_implication": insight,
        "source_footer": footer,
    }
    findings = list(metrics.get("findings") or [])
    checks: list[dict[str, Any]] = []
    for region_id, region_elements in groups.items():
        issues = [item for item in findings if region_id in str(item).lower() or (region_id == "main_visual" and item.get("code") in {"visual_ssim_below_threshold", "p0_region_ssim_below_threshold", "visual_overflow", "illegal_text_overlap", "direction_mismatch"})]
        bbox = _region_bbox(region_elements)
        optional_empty = region_id == "source_footer" and not region_elements
        evidence = {
            "region_id": region_id,
            "bbox": bbox,
            "element_ids": [str(element.get("element_id") or "") for element in region_elements],
            "issues": issues,
        }
        checks.append(
            {
                "region_id": region_id,
                "status": "pass" if (optional_empty or (region_elements and not issues and metrics.get("status") == "pass")) else "failed" if issues or not region_elements else "pending",
                "bbox": bbox,
                "issue_count": len(issues) + (0 if region_elements or optional_empty else 1),
                "notes": "No source footer is required by the Content Lock." if optional_empty else "Measured from the current Scene and rendered visual metrics.",
                "evidence_sha256": sha256_json(evidence),
            }
        )
    return checks


def _build_visual_object_checks(scene: dict[str, Any], metrics: dict[str, Any], visual_type: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in metrics.get("object_checks") or []:
        if str(item.get("visual_type") or "") != visual_type:
            continue
        evidence = {
            "visual_id": str(item.get("visual_id") or ""),
            "visual_type": visual_type,
            "status": str(item.get("status") or "failed"),
            "source_crop_sha256": str(item.get("source_crop_sha256") or ""),
            "svg_crop_sha256": str(item.get("svg_crop_sha256") or ""),
            "pptx_crop_sha256": str(item.get("pptx_crop_sha256") or ""),
            "values": item.get("values") or {},
        }
        checks.append({
            "visual_id": str(item.get("visual_id") or ""),
            "status": "pass" if item.get("status") == "pass" else "failed",
            "evidence_sha256": sha256_json(evidence),
            "notes": "Local crop metrics are computed from the current source and rendered artifacts.",
            "values": item.get("values") or {},
        })
    return checks


def _parse_review_time(value: Any, *, field: str, page_id: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise SvgVisualError(f"visual review {field} timestamp is invalid on page {page_id}", page_id=page_id) from exc
    if parsed.tzinfo is None:
        raise SvgVisualError(f"visual review {field} timestamp requires a timezone on page {page_id}", page_id=page_id)
    return parsed


def _validate_review_lineage(review: dict[str, Any], page_id: str) -> None:
    challenge = review.get("runtime_challenge") or {}
    challenge_payload = {key: value for key, value in challenge.items() if key != "integrity"}
    verify_runtime_payload("visual_review_actions.v1", challenge_payload, challenge.get("integrity") or {})
    expected_hashes = {
        "svg_sha256": str(review.get("svg_sha256") or ""),
        "blueprint_sha256": str(review.get("blueprint_sha256") or ""),
        "metrics_sha256": str(review.get("metrics_sha256") or ""),
    }
    for field, expected in expected_hashes.items():
        if str(challenge.get(field) or "") != expected:
            raise SvgVisualError(f"visual review Runtime challenge {field} is stale on page {page_id}", page_id=page_id)
    self_review = review.get("self_review") or {}
    main_review = review.get("main_review") or {}
    for name, evidence, action_field in (
        ("self", self_review, "self_action_id"),
        ("main", main_review, "main_action_id"),
    ):
        if str(evidence.get("action_id") or "") != str(challenge.get(action_field) or ""):
            raise SvgVisualError(f"visual {name} review action is stale on page {page_id}", page_id=page_id)
        for field, expected in expected_hashes.items():
            if str(evidence.get(field) or "") != expected:
                raise SvgVisualError(f"visual {name} review {field} is stale on page {page_id}", page_id=page_id)
        status = str(evidence.get("status") or "")
        source = str(evidence.get("source") or "")
        reviewed_at = evidence.get("reviewed_at")
        if status == "pending":
            if source != "runtime_challenge" or reviewed_at is not None:
                raise SvgVisualError(f"pending visual {name} review evidence is invalid on page {page_id}", page_id=page_id)
        elif status == "pass":
            allowed = {"agent_self_review", "fixture_self_review"} if name == "self" else {"agent_main_review", "fixture_main_review"}
            if source not in allowed or not str(evidence.get("reviewer_id") or ""):
                raise SvgVisualError(f"visual {name} review source is invalid on page {page_id}", page_id=page_id)
            _parse_review_time(reviewed_at, field=f"{name} reviewed_at", page_id=page_id)
            if evidence.get("full_page_check") != "pass" or bool(evidence.get("revision_required")):
                raise SvgVisualError(f"passing visual {name} review lacks a passing full-page gate on page {page_id}", page_id=page_id)
        if len(list(evidence.get("region_check_ids") or [])) < 4 or not str(evidence.get("evidence_sha256") or ""):
            raise SvgVisualError(f"visual {name} review lacks complete region evidence on page {page_id}", page_id=page_id)
    if str(main_review.get("self_review_sha256") or "") != sha256_json(self_review):
        raise SvgVisualError(f"main visual review is stale for self review on page {page_id}", page_id=page_id)
    if self_review.get("status") == "pass" and main_review.get("status") == "pass":
        if str(self_review.get("reviewer_id") or "") == str(main_review.get("reviewer_id") or ""):
            raise SvgVisualError(f"self and main visual reviews require independent reviewer IDs on page {page_id}", page_id=page_id)
        self_time = _parse_review_time(self_review.get("reviewed_at"), field="self reviewed_at", page_id=page_id)
        main_time = _parse_review_time(main_review.get("reviewed_at"), field="main reviewed_at", page_id=page_id)
        if main_time < self_time:
            raise SvgVisualError(f"main visual review precedes self review on page {page_id}", page_id=page_id)


def _main_review_receipt_payload(review: dict[str, Any]) -> dict[str, Any]:
    main_review = review.get("main_review") or {}
    challenge = review.get("runtime_challenge") or {}
    return {
        "schema_version": "deck_visual_main_review_receipt.v1",
        "run_id": str(review.get("run_id") or ""),
        "page_id": str(review.get("page_id") or ""),
        "review_sha256": sha256_json(review),
        "main_review_sha256": sha256_json(main_review),
        "runtime_challenge_sha256": sha256_json(challenge),
        "svg_sha256": str(review.get("svg_sha256") or ""),
        "blueprint_sha256": str(review.get("blueprint_sha256") or ""),
        "metrics_sha256": str(review.get("metrics_sha256") or ""),
        "main_action_id": str(main_review.get("action_id") or ""),
        "reviewer_id": str(main_review.get("reviewer_id") or ""),
        "reviewed_at": str(main_review.get("reviewed_at") or ""),
        "status": str(main_review.get("status") or ""),
        "full_page_check": str(main_review.get("full_page_check") or ""),
        "region_check_ids": list(main_review.get("region_check_ids") or []),
        "review_evidence_sha256": str(main_review.get("evidence_sha256") or ""),
        "attested_at": utc_now(),
    }


def _load_main_review_receipt(
    root: Path,
    page_id: str,
    review: dict[str, Any],
    *,
    require_external: bool = False,
) -> dict[str, Any]:
    try:
        receipt = read_json(main_review_receipt_path(root, page_id))
    except ContractError as exc:
        raise SvgVisualError(
            f"independent main visual review attestation is required on page {page_id}",
            page_id=page_id,
            code="HD_VISUAL_REVIEW_ATTESTATION_REQUIRED",
        ) from exc
    try:
        assert_v2("visual_main_review_receipt", receipt)
        payload = {key: value for key, value in receipt.items() if key != "integrity"}
        integrity = receipt.get("integrity") or {}
        if require_external:
            verify_review_attestation(payload, integrity)
        else:
            try:
                verify_runtime_payload("visual_main_review_local_receipt.v1", payload, integrity)
            except ContractError as local_error:
                try:
                    verify_review_attestation(payload, integrity)
                except ContractError as external_error:
                    raise ContractError(
                        f"local or external main visual review receipt verification failed: {external_error}"
                    ) from local_error
    except ContractError as exc:
        kind = "external main visual review attestation" if require_external else "main visual review receipt"
        raise SvgVisualError(f"{kind} is invalid on page {page_id}: {exc}", page_id=page_id, code="HD_VISUAL_REVIEW_ATTESTATION_INVALID") from exc
    expected = _main_review_receipt_payload(review)
    for field, value in expected.items():
        if field == "attested_at":
            continue
        if receipt.get(field) != value:
            raise SvgVisualError(f"independent main visual review attestation {field} is stale on page {page_id}", page_id=page_id, code="HD_VISUAL_REVIEW_ATTESTATION_STALE")
    if str(receipt.get("reviewer_id") or "") == str((review.get("self_review") or {}).get("reviewer_id") or ""):
        raise SvgVisualError(f"independent main visual review attestation reuses the producer reviewer on page {page_id}", page_id=page_id, code="HD_VISUAL_REVIEW_ATTESTATION_INVALID")
    return receipt


def _review_pass_evidence(root: Path, page_id: str, review: dict[str, Any], *, reviewer_id: str, action_field: str, source: str) -> dict[str, Any]:
    """Build a review conclusion from the current measured artifacts."""
    if not str(reviewer_id or "").strip():
        raise SvgVisualError(f"visual {source} reviewer_id is required on page {page_id}", page_id=page_id)
    try:
        scene = load_scene(root, page_id)
        metrics_file = safe_run_path(root, str(review.get("metrics_ref") or ""))
        metrics = read_json(metrics_file)
    except ContractError as exc:
        raise SvgVisualError(f"visual {source} inputs are invalid on page {page_id}", page_id=page_id) from exc
    try:
        assert_v2("visual_metrics", metrics)
    except ContractError as exc:
        raise SvgVisualError(f"visual {source} metrics contract is invalid on page {page_id}", page_id=page_id) from exc
    if sha256_file(metrics_file) != str(review.get("metrics_sha256") or "") or metrics.get("status") != "pass":
        raise SvgVisualError(f"visual {source} requires passing current metrics on page {page_id}", page_id=page_id)
    expected_regions = _build_region_checks(scene, metrics)
    if any(item.get("status") != "pass" for item in expected_regions) or any(item.get("status") != "pass" for item in metrics.get("object_checks") or []):
        raise SvgVisualError(f"visual {source} requires passing region checks on page {page_id}", page_id=page_id)
    svg_sha = sha256_file(svg_path(root, page_id))
    if svg_sha != str(review.get("svg_sha256") or ""):
        raise SvgVisualError(f"visual {source} SVG hash is stale on page {page_id}", page_id=page_id)
    blueprint_sha = str(review.get("blueprint_sha256") or "")
    metrics_sha = str(review.get("metrics_sha256") or "")
    evidence = {
        "svg_sha256": svg_sha,
        "blueprint_sha256": blueprint_sha,
        "metrics_sha256": metrics_sha,
        "region_checks": expected_regions,
    }
    challenge = review.get("runtime_challenge") or {}
    action_id = str(challenge.get(action_field) or "")
    if not re.fullmatch(r"[a-f0-9]{32}", action_id):
        raise SvgVisualError(f"visual {source} Runtime action is invalid on page {page_id}", page_id=page_id)
    return _review_evidence(
        status="pass",
        source=source,
        reviewer_id=str(reviewer_id),
        action_id=action_id,
        reviewed_at=utc_now(),
        svg_sha256=svg_sha,
        blueprint_sha256=blueprint_sha,
        metrics_sha256=metrics_sha,
        full_page_check="pass",
        region_check_ids=[str(item["region_id"]) for item in expected_regions],
        issues_found=[],
        revision_required=False,
        evidence_sha256=sha256_json(evidence),
    )


def record_visual_self_review(root: Path, page_id: str, *, reviewer_id: str) -> Path:
    """Record the producer's measured review conclusion before main review."""
    review = read_json(review_path(root, page_id))
    if review.get("schema_version") != "deck_visual_review.v2" or str(review.get("page_id") or "") != page_id:
        raise SvgVisualError(f"visual review contract is invalid on page {page_id}", page_id=page_id)
    if _run_mode(root) not in {"production", "benchmark"}:
        raise SvgVisualError("external self review is only required for production or benchmark runs", page_id=page_id)
    _validate_review_lineage(review, page_id)
    self_review = _review_pass_evidence(root, page_id, review, reviewer_id=reviewer_id, action_field="self_action_id", source="agent_self_review")
    main_review = dict(review.get("main_review") or {})
    main_review["self_review_sha256"] = sha256_json(self_review)
    review["self_review"] = self_review
    review["main_review"] = main_review
    # Producer-only policy can complete from this evidence. Independent-main
    # policy still observes the pending main review on the next load.
    review["visual_status"] = "pass"
    review["verdict"] = "pass"
    assert_v2("visual_review", review)
    return write_json(review_path(root, page_id), review)


def record_visual_main_review(root: Path, page_id: str, *, reviewer_id: str) -> Path:
    """Record an independent main review and create a local receipt."""
    review = read_json(review_path(root, page_id))
    if review.get("schema_version") != "deck_visual_review.v2" or str(review.get("page_id") or "") != page_id:
        raise SvgVisualError(f"visual review contract is invalid on page {page_id}", page_id=page_id)
    if _run_mode(root) not in {"production", "benchmark"}:
        raise SvgVisualError("external main visual review attestation is only required for production or benchmark runs", page_id=page_id)
    if not str(reviewer_id or "").strip():
        raise SvgVisualError(f"independent main visual reviewer_id is required on page {page_id}", page_id=page_id)
    _validate_review_lineage(review, page_id)
    self_review = review.get("self_review") or {}
    if str(self_review.get("status") or "") != "pass":
        raise SvgVisualError(f"producer self review must pass before main review on page {page_id}", page_id=page_id)
    main_review = review.get("main_review") or {}
    if str(self_review.get("reviewer_id") or "") == str(reviewer_id):
        raise SvgVisualError(f"independent main visual review reuses the producer reviewer on page {page_id}", page_id=page_id)
    if str(main_review.get("status") or "") != "pass":
        main_review = _review_pass_evidence(root, page_id, review, reviewer_id=reviewer_id, action_field="main_action_id", source="agent_main_review")
        main_review["self_review_sha256"] = sha256_json(self_review)
        review["main_review"] = main_review
        review["visual_status"] = "pass"
        review["verdict"] = "pass"
        assert_v2("visual_review", review)
        write_json(review_path(root, page_id), review)
        review = read_json(review_path(root, page_id))
    elif str(main_review.get("reviewer_id") or "") != str(reviewer_id):
        raise SvgVisualError(f"main visual reviewer_id does not match the attested reviewer on page {page_id}", page_id=page_id)
    load_visual_review(root, page_id, review_depth="producer_only", receipt_policy="local_traceable")
    payload = _main_review_receipt_payload(review)
    policy = load_review_policy(root)
    if policy["receipt_policy"] == "external_signed":
        try:
            integrity = sign_review_attestation(payload)
        except ContractError as exc:
            raise SvgVisualError(
                f"external main visual review attestation cannot be issued on page {page_id}: {exc}",
                page_id=page_id,
                code="HD_VISUAL_REVIEW_ATTESTATION_REQUIRED",
            ) from exc
    else:
        integrity = sign_runtime_payload("visual_main_review_local_receipt.v1", payload)
    receipt = {**payload, "integrity": integrity}
    assert_v2("visual_main_review_receipt", receipt)
    return write_json(main_review_receipt_path(root, page_id), receipt)


def build_visual_review(root: Path, scene: dict[str, Any], *, mode: str) -> Path:
    page_id = str(scene["page_id"])
    try:
        blueprint_manifest = load_blueprint_manifest(root, page_id, expected_run_id=str(scene.get("run_id") or ""))
        blueprint_preview = normalize_blueprint(root, blueprint_manifest)
        svg_preview = preview_path(root, page_id)
        metrics = compute_visual_metrics(root, scene, blueprint_preview, svg_preview)
        metrics_file = write_visual_metrics(root, scene, metrics)
    except (ContractError, VisualMetricsError, OSError) as exc:
        raise SvgVisualError(f"visual metrics could not be computed on page {page_id}: {exc}", page_id=page_id) from exc
    passed_metrics = metrics.get("status") == "pass"
    region_checks = _build_region_checks(scene, metrics)
    icon_checks = _build_visual_object_checks(scene, metrics, "icon")
    curve_checks = _build_visual_object_checks(scene, metrics, "curve")
    table_checks = _build_visual_object_checks(scene, metrics, "table")
    region_check_ids = [str(item["region_id"]) for item in region_checks]
    object_checks_passed = all(item.get("status") == "pass" for item in icon_checks + curve_checks + table_checks)
    region_passed = all(item.get("status") == "pass" for item in region_checks) and object_checks_passed
    review_issues = list(metrics.get("findings") or [])
    full_page_check = "pass" if passed_metrics and region_passed else "failed"
    svg_sha = sha256_file(svg_path(root, page_id))
    blueprint_sha = str(scene.get("blueprint_sha256") or "")
    metrics_sha = sha256_file(metrics_file)
    full_page_evidence = {
        "svg_sha256": svg_sha,
        "blueprint_sha256": blueprint_sha,
        "metrics_sha256": metrics_sha,
        "region_checks": region_checks,
    }
    review_evidence_sha = sha256_json(full_page_evidence)
    created_at = utc_now()
    challenge_payload = {
        "self_action_id": secrets.token_hex(16),
        "main_action_id": secrets.token_hex(16),
        "svg_sha256": svg_sha,
        "blueprint_sha256": blueprint_sha,
        "metrics_sha256": metrics_sha,
        "issued_at": created_at,
    }
    fixture_review = passed_metrics and mode in {"fixture", "dev"}
    self_review = _review_evidence(
        status="pass" if fixture_review else "pending",
        source="fixture_self_review" if fixture_review else "runtime_challenge",
        reviewer_id="fixture-producer" if fixture_review else "pending",
        action_id=challenge_payload["self_action_id"],
        reviewed_at=created_at if fixture_review else None,
        svg_sha256=svg_sha,
        blueprint_sha256=blueprint_sha,
        metrics_sha256=metrics_sha,
        full_page_check=full_page_check if fixture_review else "pending",
        region_check_ids=region_check_ids,
        issues_found=review_issues,
        revision_required=not passed_metrics,
        evidence_sha256=review_evidence_sha,
    )
    main_review = {
        **_review_evidence(
            status="pass" if fixture_review else "pending",
            source="fixture_main_review" if fixture_review else "runtime_challenge",
            reviewer_id="fixture-main-reviewer" if fixture_review else "pending",
            action_id=challenge_payload["main_action_id"],
            reviewed_at=created_at if fixture_review else None,
            svg_sha256=svg_sha,
            blueprint_sha256=blueprint_sha,
            metrics_sha256=metrics_sha,
            full_page_check=full_page_check if fixture_review else "pending",
            region_check_ids=region_check_ids,
            issues_found=review_issues,
            revision_required=not passed_metrics,
            evidence_sha256=review_evidence_sha,
        ),
        "self_review_sha256": sha256_json(self_review),
    }
    review = {
        "schema_version": "deck_visual_review.v2",
        "run_id": scene["run_id"],
        "page_id": page_id,
        "svg_sha256": svg_sha,
        "blueprint_sha256": blueprint_sha,
        "blueprint_preview_sha256": sha256_file(blueprint_preview),
        "svg_preview_sha256": sha256_file(svg_preview),
        "review_mode": "computed_fixture" if mode in {"fixture", "dev"} else "agent_main_review",
        "metrics_ref": str(metrics_file.relative_to(root).as_posix()),
        "metrics_sha256": metrics_sha,
        "runtime_challenge": {
            **challenge_payload,
            "integrity": sign_runtime_payload("visual_review_actions.v1", challenge_payload),
        },
        "visual_status": "pass" if fixture_review else "needs_review",
        "full_page_checks": {"canvas_ratio": "pass", "stable_ids": "pass", "p0_p1_geometry": "pass" if passed_metrics else "failed", "layout": "pass" if region_passed else "failed", "mask_coverage": float((metrics.get("values") or {}).get("mask_coverage") or 0), "icon_coverage": 1.0 if not icon_checks else sum(1 for item in icon_checks if item.get("status") == "pass") / len(icon_checks), "curve_coverage": 1.0 if not curve_checks else sum(1 for item in curve_checks if item.get("status") == "pass") / len(curve_checks), "table_coverage": 1.0 if not table_checks else sum(1 for item in table_checks if item.get("status") == "pass") / len(table_checks)},
        "region_checks": region_checks,
        "icon_checks": icon_checks,
        "curve_checks": curve_checks,
        "table_checks": table_checks,
        "issues_found": review_issues,
        "unresolved_issues": [] if passed_metrics and region_passed else review_issues,
        "self_review": self_review,
        "main_review": main_review,
        "verdict": "pass" if fixture_review else "needs_review",
        "created_at": created_at,
    }
    assert_v2("visual_review", review)
    path = review_path(root, page_id)
    write_json(path, review)
    return path


def _metrics_projection(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in ("schema_version", "comparison", "inputs", "thresholds", "values", "coverage", "geometry", "object_checks", "findings", "status")}


def load_visual_review(
    root: Path,
    page_id: str,
    *,
    require_external_receipt: bool = False,
    review_depth: str = "",
    receipt_policy: str = "",
) -> dict[str, Any]:
    policy = resolve_review_policy(
        {
            "review_depth": review_depth,
            "receipt_policy": receipt_policy,
        }
    )
    if require_external_receipt:
        policy = {**policy, "review_depth": "independent_main", "receipt_policy": "external_signed"}
    require_main_review = policy["review_depth"] == "independent_main"
    review = read_json(review_path(root, page_id))
    if review.get("schema_version") != "deck_visual_review.v2" or review.get("page_id") != page_id:
        raise SvgVisualError(f"visual review contract is invalid on page {page_id}", page_id=page_id)
    assert_v2("visual_review", review)
    _validate_review_lineage(review, page_id)
    self_status = str((review.get("self_review") or {}).get("status") or "")
    main_status = str((review.get("main_review") or {}).get("status") or "")
    if review.get("unresolved_issues"):
        raise SvgVisualError(f"visual review has unresolved issues on page {page_id}", page_id=page_id)
    if self_status != "pass":
        raise SvgVisualError(f"visual review requires passing producer self-review evidence on page {page_id}", page_id=page_id)
    if main_status == "failed" or main_status not in {"pass", "pending"}:
        raise SvgVisualError(f"visual review main review evidence is invalid on page {page_id}", page_id=page_id)
    if require_main_review and main_status != "pass":
        raise SvgVisualError(f"visual review requires passing independent main review evidence on page {page_id}", page_id=page_id)
    if review.get("visual_status") != "pass" or review.get("verdict") != "pass":
        if not (not require_main_review and main_status == "pending" and review.get("visual_status") == "needs_review" and review.get("verdict") == "needs_review"):
            raise SvgVisualError(f"visual review has not passed on page {page_id}", page_id=page_id)
    try:
        metrics_file = safe_run_path(root, str(review.get("metrics_ref") or ""))
    except ContractError as exc:
        raise SvgVisualError(f"visual review metrics path is invalid on page {page_id}", page_id=page_id) from exc
    metrics = read_json(metrics_file)
    try:
        assert_v2("visual_metrics", metrics)
    except ContractError as exc:
        raise SvgVisualError(f"visual review metrics contract is invalid on page {page_id}", page_id=page_id) from exc
    if sha256_file(metrics_file) != str(review.get("metrics_sha256") or "") or metrics.get("status") != "pass":
        raise SvgVisualError(f"visual review metrics are stale or failed on page {page_id}", page_id=page_id)
    current_svg = svg_path(root, page_id)
    try:
        current_svg_sha = sha256_file(current_svg)
    except OSError as exc:
        raise SvgVisualError(f"current SVG is missing on page {page_id}", page_id=page_id) from exc
    if str(review.get("svg_sha256") or "") != current_svg_sha:
        raise SvgVisualError(f"visual review is stale for SVG on page {page_id}", page_id=page_id)
    try:
        scene = load_scene(root, page_id)
    except ContractError as exc:
        raise SvgVisualError(f"current page scene is missing on page {page_id}", page_id=page_id) from exc
    if str(review.get("run_id") or "") != str(scene.get("run_id") or ""):
        raise SvgVisualError(f"visual review run_id is stale on page {page_id}", page_id=page_id)
    if str(review.get("blueprint_sha256") or "") != str(scene.get("blueprint_sha256") or ""):
        raise SvgVisualError(f"visual review is stale for blueprint on page {page_id}", page_id=page_id)
    current_preview = preview_path(root, page_id)
    if not current_preview.exists() or str(review.get("svg_preview_sha256") or "") != sha256_file(current_preview):
        raise SvgVisualError(f"visual review is stale for SVG preview on page {page_id}", page_id=page_id)
    try:
        blueprint_manifest = load_blueprint_manifest(root, page_id, expected_run_id=str(scene.get("run_id") or ""))
        blueprint_preview = normalize_blueprint(root, blueprint_manifest)
        if str(review.get("blueprint_preview_sha256") or "") != sha256_file(blueprint_preview):
            raise SvgVisualError(f"visual review is stale for blueprint preview on page {page_id}", page_id=page_id)
        computed = compute_visual_metrics(root, scene, blueprint_preview, current_preview)
    except (ContractError, VisualMetricsError, OSError) as exc:
        raise SvgVisualError(f"visual review metrics could not be recomputed on page {page_id}", page_id=page_id) from exc
    if _metrics_projection(metrics) != _metrics_projection(computed):
        raise SvgVisualError(f"visual review metrics are not tool-computed for current artifacts on page {page_id}", page_id=page_id)
    expected_regions = _build_region_checks(scene, computed)
    if review.get("region_checks") != expected_regions:
        raise SvgVisualError(f"visual review region evidence is not tool-computed for current artifacts on page {page_id}", page_id=page_id)
    for field, visual_type in (("icon_checks", "icon"), ("curve_checks", "curve"), ("table_checks", "table")):
        if review.get(field) != _build_visual_object_checks(scene, computed, visual_type):
            raise SvgVisualError(f"visual review {field} evidence is not tool-computed for current artifacts on page {page_id}", page_id=page_id)
    expected_full_page_evidence = {
        "svg_sha256": str(review.get("svg_sha256") or ""),
        "blueprint_sha256": str(review.get("blueprint_sha256") or ""),
        "metrics_sha256": str(review.get("metrics_sha256") or ""),
        "region_checks": expected_regions,
    }
    expected_evidence_sha = sha256_json(expected_full_page_evidence)
    for name in ("self_review", "main_review"):
        if str((review.get(name) or {}).get("evidence_sha256") or "") != expected_evidence_sha:
            raise SvgVisualError(f"visual {name} evidence is stale on page {page_id}", page_id=page_id)
    expected_status = "pass" if computed.get("status") == "pass" and all(item.get("status") == "pass" for item in expected_regions) and all(item.get("status") == "pass" for item in computed.get("object_checks") or []) else "failed"
    if expected_status == "pass" and (review.get("full_page_checks") or {}).get("layout") != "pass":
        raise SvgVisualError(f"visual review full-page layout evidence failed on page {page_id}", page_id=page_id)
    values = computed.get("values") or {}
    if float(values.get("text_masked_ssim") or 0) < 0.92 or float(values.get("bbox_max_delta_px") or 0) > 2.0:
        raise SvgVisualError(f"visual review fidelity gate failed on page {page_id}", page_id=page_id)
    if _run_mode(root) in {"production", "benchmark"} and require_main_review:
        receipt_path = main_review_receipt_path(root, page_id)
        if policy["receipt_policy"] == "external_signed":
            _load_main_review_receipt(root, page_id, review, require_external=True)
        elif policy["receipt_policy"] == "local_traceable":
            if not receipt_path.exists():
                raise SvgVisualError(
                    f"local main visual review receipt is required on page {page_id}",
                    page_id=page_id,
                    code="HD_VISUAL_REVIEW_ATTESTATION_REQUIRED",
                )
            _load_main_review_receipt(root, page_id, review)
    return review


__all__ = [
    "PREVIEW_DIR",
    "REVIEW_DIR",
    "SVG_DIR",
    "SvgVisualError",
    "build_visual_review",
    "compile_svg",
    "load_visual_review",
    "main_review_receipt_path",
    "metrics_path",
    "preview_path",
    "render_preview",
    "record_visual_self_review",
    "record_visual_main_review",
    "review_path",
    "svg_path",
    "validate_approved_svg",
    "validate_svg",
]
