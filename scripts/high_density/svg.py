from __future__ import annotations

import base64
import html
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .blueprint import load_blueprint_manifest
from .contracts import ContractError, assert_v2, read_json, safe_run_path, sha256_file, utc_now, write_json
from .scene import load_scene
from .visual import VisualMetricsError, _svg_geometry_bbox, compute_visual_metrics, normalize_blueprint, write_visual_metrics

SVG_DIR = Path("high_density_build/svg")
PREVIEW_DIR = Path("high_density_build/previews")
REVIEW_DIR = Path("high_density_build/reviews")
COMPARISON_DIR = Path("high_density_build/comparisons")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
FORBIDDEN_TAGS = {"foreignObject", "script", "iframe", "style"}
UNSUPPORTED_TAGS = {"linearGradient", "radialGradient", "filter", "mask", "clipPath", "pattern", "use"}


class SvgVisualError(ContractError):
    def __init__(self, message: str, *, page_id: str = "", code: str = "HD_SVG_REVIEW_FAILED") -> None:
        self.page_id = page_id
        self.code = code
        super().__init__(message)


def svg_path(root: Path, page_id: str) -> Path:
    return root / SVG_DIR / f"{page_id}.svg"


def preview_path(root: Path, page_id: str) -> Path:
    return root / PREVIEW_DIR / f"{page_id}.png"


def review_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.visual_review.json"


def metrics_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.metrics.json"


def _estimated_width(text: str, size: float) -> float:
    width = 0.0
    for char in text:
        width += size * (0.95 if ord(char) > 127 else 0.56)
    return width


def wrap_text(text: str, width: float, size: float) -> list[str]:
    if not text:
        return [""]
    if width <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    tokens = list(text) if any(ord(char) > 127 for char in text) else re.split(r"(\s+)", text)
    for token in tokens:
        candidate = current + token
        if current and _estimated_width(candidate, size) > width:
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
    bbox = element["bbox"]
    fit = element["text_fit"]
    text = str(element.get("text") or "")
    size = float(fit.get("preferred_size_px") or 18)
    min_size = float(fit.get("min_size_px") or max(9, size * 0.7))
    max_lines = int(fit.get("max_lines") or 1)
    line_height = float(fit.get("line_height") or 1.18)
    lines = wrap_text(text, float(bbox["w"]), size)
    while len(lines) > max_lines and size > min_size:
        size = max(min_size, size - 1)
        lines = wrap_text(text, float(bbox["w"]), size)
    if (
        len(lines) > max_lines
        or len(lines) * size * line_height > float(bbox["h"]) + 0.01
        or any(_estimated_width(line, size) > float(bbox["w"]) + 0.01 for line in lines)
    ):
        raise SvgVisualError(f"P0/P1 text overflow in {element['element_id']}", page_id=page_id)
    style = element.get("style") or {}
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
        "opacity": str(style.get("opacity") or 1),
        "data-pptx-component": str(element.get("component_id") or ""),
        "data-pptx-z": str(element.get("z_index") or 0),
        "data-pptx-bounds": f"{x:.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
        "data-pptx-text": text,
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
        "opacity": str(style.get("opacity") or 1),
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
        raise SvgVisualError(f"registered image asset is unavailable for {element['element_id']}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
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
        f'data-pptx-bounds="{float(bbox["x"]):.2f},{float(bbox["y"]):.2f},{float(bbox["w"]):.2f},{float(bbox["h"]):.2f}"/>'
    )


def compile_svg(scene: dict[str, Any], output: Path, *, assets: dict[str, Path] | None = None) -> Path:
    from .scene import validate_scene

    page_id = str(scene["page_id"])
    try:
        validate_scene(scene)
    except ContractError as exc:
        raise SvgVisualError(str(exc), page_id=page_id, code="HD_PAGE_SCENE_INVALID") from exc
    scene_elements = list(scene.get("elements", []))
    image_area = 0.0
    p0_text = [element for element in scene_elements if element.get("kind") == "text" and element.get("priority") == "P0"]
    for element in scene_elements:
        if element.get("kind") != "image":
            continue
        bbox = element.get("bbox") or {}
        area = float(bbox.get("w") or 0) * float(bbox.get("h") or 0)
        image_area += area
        if area / (CANVAS_WIDTH * CANVAS_HEIGHT) > 0.35:
            raise SvgVisualError(f"image asset exceeds 35% of canvas: {element.get('element_id')}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
        image_z = int(element.get("z_index") or 0)
        for text in p0_text:
            text_bbox = text.get("bbox") or {}
            overlap_w = max(0.0, min(float(bbox.get("x") or 0) + float(bbox.get("w") or 0), float(text_bbox.get("x") or 0) + float(text_bbox.get("w") or 0)) - max(float(bbox.get("x") or 0), float(text_bbox.get("x") or 0)))
            overlap_h = max(0.0, min(float(bbox.get("y") or 0) + float(bbox.get("h") or 0), float(text_bbox.get("y") or 0) + float(text_bbox.get("h") or 0)) - max(float(bbox.get("y") or 0), float(text_bbox.get("y") or 0)))
            if image_z >= int(text.get("z_index") or 0) and overlap_w * overlap_h > 0:
                raise SvgVisualError(f"image asset covers P0 text: {element.get('element_id')} -> {text.get('element_id')}", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    if image_area / (CANVAS_WIDTH * CANVAS_HEIGHT) > 0.50:
        raise SvgVisualError("registered image assets exceed 50% of canvas", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    elements: list[str] = []
    ordered_elements = sorted(enumerate(scene_elements), key=lambda item: (int(item[1].get("z_index") or 0), item[0]))
    for _, element in ordered_elements:
        kind = element.get("kind")
        if kind == "text":
            elements.append(_text_svg(element, page_id))
        elif kind == "rect":
            elements.append(_rect_svg(element))
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
                "opacity": str(style.get("opacity") or 1),
                "data-pptx-component": str(element.get("component_id") or ""),
                "data-pptx-z": str(element.get("z_index") or 0),
                "data-pptx-bounds": f"{float(bbox['x']):.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
            }
            elements.append(f"<line {_attrs(attrs)}/>")
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
                "opacity": str(style.get("opacity") or 1),
                "data-pptx-component": str(element.get("component_id") or ""),
                "data-pptx-z": str(element.get("z_index") or 0),
                "data-pptx-bounds": f"{float(bbox['x']):.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
            }
            elements.append(f"<ellipse {_attrs(attrs)}/>")
        elif kind == "path":
            path_data = str(element.get("path") or "")
            if not path_data or re.search(r"[<>&]", path_data):
                raise SvgVisualError(f"invalid path data in {element['element_id']}", page_id=page_id)
            style = element.get("style") or {}
            fill = _color(style.get("fill"), "none")
            stroke = _color(style.get("stroke"), "none")
            elements.append(
                f'<path id="{html.escape(str(element["element_id"]), quote=True)}" '
                f'd="{html.escape(path_data, quote=True)}" fill="{fill}" stroke="{stroke}" stroke-width="{style.get("stroke_width") or 0}" '
                f'opacity="{style.get("opacity") or 1}" data-pptx-component="{html.escape(str(element.get("component_id") or ""), quote=True)}" data-pptx-z="{element.get("z_index") or 0}" data-pptx-bounds="{float(element["bbox"]["x"]):.2f},{float(element["bbox"]["y"]):.2f},{float(element["bbox"]["w"]):.2f},{float(element["bbox"]["h"]):.2f}"/>'
            )
        elif kind == "polygon":
            points = element.get("points") or []
            if len(points) < 3:
                raise SvgVisualError(f"polygon needs at least three points in {element['element_id']}", page_id=page_id)
            style = element.get("style") or {}
            point_text = " ".join(f"{float(point[0]):.2f},{float(point[1]):.2f}" for point in points)
            elements.append(
                f'<polygon id="{html.escape(str(element["element_id"]), quote=True)}" '
                f'points="{point_text}" fill="{_color(style.get("fill"), "none")}" '
                f'stroke="{_color(style.get("stroke"), "none")}" stroke-width="{style.get("stroke_width") or 0}" opacity="{style.get("opacity") or 1}" '
                f'data-pptx-component="{html.escape(str(element.get("component_id") or ""), quote=True)}" data-pptx-z="{element.get("z_index") or 0}" data-pptx-bounds="{float(element["bbox"]["x"]):.2f},{float(element["bbox"]["y"]):.2f},{float(element["bbox"]["w"]):.2f},{float(element["bbox"]["h"]):.2f}"/>'
            )
        elif kind == "image":
            elements.append(_image_svg(element, (assets or {}).get(str(element.get("asset_ref") or "")), page_id))
        else:
            raise SvgVisualError(f"unsupported scene element kind: {kind}", page_id=page_id)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" '
        f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" data-pptx-page-role="content">'
        f'<g id="page.{html.escape(page_id, quote=True)}" data-pptx-bounds="0,0,{CANVAS_WIDTH},{CANVAS_HEIGHT}">'
        + "".join(elements)
        + "</g></svg>"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    validate_svg(output, page_id=page_id)
    return output


def validate_svg(path: Path, *, page_id: str = "") -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise SvgVisualError(f"SVG parse failed: {exc}", page_id=page_id) from exc
    tags = {str(node.tag).split("}")[-1] for node in root.iter()}
    forbidden = sorted(tags & FORBIDDEN_TAGS)
    if forbidden:
        raise SvgVisualError(f"forbidden SVG elements: {', '.join(forbidden)}", page_id=page_id)
    unsupported = sorted(tags & UNSUPPORTED_TAGS)
    if unsupported:
        raise SvgVisualError(f"unsupported SVG element {', '.join(unsupported)} requires native compiler support", page_id=page_id, code="HD_SVG_UNSUPPORTED_ELEMENT")
    if root.tag.split("}")[-1] != "svg" or root.get("viewBox") != f"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}":
        raise SvgVisualError("SVG canvas or viewBox is invalid", page_id=page_id)
    if root.get("data-pptx-page-role") != "content":
        raise SvgVisualError("SVG root is missing data-pptx-page-role", page_id=page_id)
    ids: set[str] = set()
    visible_tags = {"text", "rect", "circle", "ellipse", "line", "path", "polyline", "polygon", "image"}
    for node in root.iter():
        tag = str(node.tag).split("}")[-1]
        node_id = str(node.get("id") or "")
        for raw_name in node.attrib:
            attr_name = str(raw_name).split("}")[-1].lower()
            if attr_name.startswith("on"):
                raise SvgVisualError(f"SVG event attribute is blocked: {attr_name} on {node_id or tag}", page_id=page_id, code="HD_SVG_UNSAFE_ATTRIBUTE")
            if attr_name in {"href", "xlink:href"} and tag != "image":
                raise SvgVisualError(f"external SVG href is blocked on {node_id or tag}", page_id=page_id, code="HD_SVG_UNSAFE_ATTRIBUTE")
        if node_id:
            if node_id in ids:
                raise SvgVisualError(f"duplicate SVG element id: {node_id}", page_id=page_id)
            ids.add(node_id)
        if node.get("style") or node.get("class"):
            raise SvgVisualError("external CSS/style attributes are blocked", page_id=page_id)
        if node.get("transform"):
            raise SvgVisualError(f"per-element SVG transforms are unsupported: {node_id}", page_id=page_id, code="HD_SVG_UNSUPPORTED_ELEMENT")
        if node.get("opacity") is not None:
            try:
                opacity = float(str(node.get("opacity")).removesuffix("px"))
            except (TypeError, ValueError) as exc:
                raise SvgVisualError(f"SVG opacity is invalid: {node_id}", page_id=page_id) from exc
            if not math.isfinite(opacity) or opacity <= 0 or opacity > 1:
                raise SvgVisualError(f"SVG opacity must be between 0 and 1: {node_id}", page_id=page_id)
        for attribute in ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "stroke-width", "font-size"):
            if node.get(attribute) is None:
                continue
            try:
                value = float(str(node.get(attribute)).removesuffix("px"))
            except (TypeError, ValueError) as exc:
                raise SvgVisualError(f"SVG {attribute} is invalid: {node_id}", page_id=page_id) from exc
            if not math.isfinite(value) or (attribute in {"width", "height", "r", "rx", "ry", "stroke-width", "font-size"} and value < 0):
                raise SvgVisualError(f"SVG {attribute} is out of range: {node_id}", page_id=page_id)
        for paint in ("fill", "stroke"):
            value = str(node.get(paint) or "").strip()
            if value and value.lower() not in {"none", "transparent"} and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise SvgVisualError(f"SVG {paint} is outside the supported native palette: {node_id}", page_id=page_id, code="HD_SVG_UNSUPPORTED_STYLE")
        if node.get("opacity") is not None and str(node.get("opacity")) in {"0", "0.0"}:
            raise SvgVisualError(f"hidden SVG element is blocked: {node_id}", page_id=page_id)
        if tag in visible_tags:
            if not node_id:
                raise SvgVisualError(f"visible SVG element must have a stable element id: {tag}", page_id=page_id)
            if not str(node.get("data-pptx-bounds") or ""):
                raise SvgVisualError(f"visible SVG element is missing data-pptx-bounds: {node_id}", page_id=page_id)
            try:
                bbox = _svg_geometry_bbox(node)
            except VisualMetricsError as exc:
                raise SvgVisualError(f"SVG element geometry is invalid: {node_id}", page_id=page_id) from exc
            if bbox["x"] < -0.01 or bbox["y"] < -0.01 or bbox["x"] + bbox["w"] > CANVAS_WIDTH + 0.01 or bbox["y"] + bbox["h"] > CANVAS_HEIGHT + 0.01:
                raise SvgVisualError(f"SVG element overflows the canvas: {node_id}", page_id=page_id)
        if tag != "image":
            continue
        if node.get("data-pptx-asset") != "registered":
            raise SvgVisualError("SVG image is missing registered asset marker", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
        href = node.get("href") or node.get("{http://www.w3.org/1999/xlink}href") or ""
        if not href.startswith("data:image/"):
            raise SvgVisualError("SVG image must be an embedded registered asset", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
        try:
            x = float(node.get("x") or 0)
            y = float(node.get("y") or 0)
            width = float(node.get("width") or 0)
            height = float(node.get("height") or 0)
        except ValueError as exc:
            raise SvgVisualError("SVG registered image geometry is invalid", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED") from exc
        if x <= 0.01 and y <= 0.01 and width >= CANVAS_WIDTH - 0.01 and height >= CANVAS_HEIGHT - 0.01:
            raise SvgVisualError("whole-page image wrapper is blocked", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED")
    return {"valid": True, "tags": sorted(tags), "forbidden": []}


def render_preview(svg: Path, preview: Path) -> Path:
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise SvgVisualError("rsvg-convert is required for native SVG preview")
    preview.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([converter, "-w", str(CANVAS_WIDTH), "-h", str(CANVAS_HEIGHT), "-o", str(preview), str(svg)], capture_output=True, text=True)
    if result.returncode != 0 or not preview.exists() or preview.stat().st_size == 0:
        raise SvgVisualError(f"SVG preview failed: {result.stderr.strip() or 'unknown converter error'}")
    return preview


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
    priorities = {element["priority"] for element in scene.get("elements", [])}
    passed_metrics = metrics.get("status") == "pass"
    review = {
        "schema_version": "deck_visual_review.v2",
        "run_id": scene["run_id"],
        "page_id": page_id,
        "svg_sha256": sha256_file(svg_path(root, page_id)),
        "blueprint_sha256": str(scene.get("blueprint_sha256") or ""),
        "blueprint_preview_sha256": sha256_file(blueprint_preview),
        "svg_preview_sha256": sha256_file(svg_preview),
        "review_mode": "computed_fixture" if mode in {"fixture", "dev"} else "agent_main_review",
        "metrics_ref": str(metrics_file.relative_to(root).as_posix()),
        "metrics_sha256": sha256_file(metrics_file),
        "visual_status": "pass" if passed_metrics and mode in {"fixture", "dev"} else "needs_review",
        "full_page_checks": {"canvas_ratio": "pass", "stable_ids": "pass", "p0_p1_geometry": "pass" if passed_metrics else "failed"},
        "region_checks": [],
        "issues_found": list(metrics.get("findings") or []),
        "unresolved_issues": [] if passed_metrics else list(metrics.get("findings") or []),
        "self_review": {"status": "pass" if passed_metrics else "failed", "source": "tool_metrics"},
        "main_review": {"status": "pass" if passed_metrics and mode in {"fixture", "dev"} else "pending", "source": "fixture_policy" if mode in {"fixture", "dev"} else "agent"},
        "verdict": "pass" if passed_metrics and mode in {"fixture", "dev"} else "needs_review",
        "created_at": utc_now(),
    }
    assert_v2("visual_review", review)
    path = review_path(root, page_id)
    write_json(path, review)
    return path


def _metrics_projection(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in ("schema_version", "comparison", "inputs", "thresholds", "values", "coverage", "geometry", "findings", "status")}


def load_visual_review(root: Path, page_id: str) -> dict[str, Any]:
    review = read_json(review_path(root, page_id))
    if review.get("schema_version") != "deck_visual_review.v2" or review.get("page_id") != page_id:
        raise SvgVisualError(f"visual review contract is invalid on page {page_id}", page_id=page_id)
    assert_v2("visual_review", review)
    if review.get("visual_status") != "pass" or review.get("verdict") != "pass" or review.get("unresolved_issues"):
        raise SvgVisualError(f"visual review has not passed on page {page_id}", page_id=page_id)
    if str((review.get("self_review") or {}).get("status") or "") != "pass" or str((review.get("main_review") or {}).get("status") or "") != "pass":
        raise SvgVisualError(f"visual review requires passing self and main review evidence on page {page_id}", page_id=page_id)
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
    values = computed.get("values") or {}
    if float(values.get("text_masked_ssim") or 0) < 0.92 or float(values.get("bbox_max_delta_px") or 0) > 2.0:
        raise SvgVisualError(f"visual review fidelity gate failed on page {page_id}", page_id=page_id)
    return review


__all__ = [
    "PREVIEW_DIR",
    "REVIEW_DIR",
    "SVG_DIR",
    "SvgVisualError",
    "build_visual_review",
    "compile_svg",
    "load_visual_review",
    "metrics_path",
    "preview_path",
    "render_preview",
    "review_path",
    "svg_path",
    "validate_svg",
]
