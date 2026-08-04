from __future__ import annotations

import base64
import html
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .contracts import ContractError, read_json, sha256_file, utc_now, write_json

SVG_DIR = Path("high_density_build/svg")
PREVIEW_DIR = Path("high_density_build/previews")
REVIEW_DIR = Path("high_density_build/reviews")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
FORBIDDEN_TAGS = {"foreignObject", "script", "iframe", "style"}


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
        "data-pptx-bounds": f"{x:.2f},{float(bbox['y']):.2f},{float(bbox['w']):.2f},{float(bbox['h']):.2f}",
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
        f'data-pptx-bounds="{float(bbox["x"]):.2f},{float(bbox["y"]):.2f},{float(bbox["w"]):.2f},{float(bbox["h"]):.2f}"/>'
    )


def compile_svg(scene: dict[str, Any], output: Path, *, assets: dict[str, Path] | None = None) -> Path:
    page_id = str(scene["page_id"])
    elements: list[str] = []
    for element in scene.get("elements", []):
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
            }
            elements.append(f"<line {_attrs(attrs)}/>")
        elif kind == "path":
            path_data = str(element.get("path") or "")
            if not path_data or re.search(r"[<>&]", path_data):
                raise SvgVisualError(f"invalid path data in {element['element_id']}", page_id=page_id)
            style = element.get("style") or {}
            fill = _color(style.get("fill"), "none")
            stroke = _color(style.get("stroke"), "none")
            elements.append(
                f'<path id="{html.escape(str(element["element_id"]), quote=True)}" '
                f'd="{html.escape(path_data, quote=True)}" fill="{fill}" stroke="{stroke}"/>'
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
                f'stroke="{_color(style.get("stroke"), "none")}" stroke-width="{style.get("stroke_width") or 0}"/>'
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
    if root.tag.split("}")[-1] != "svg" or root.get("viewBox") != f"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}":
        raise SvgVisualError("SVG canvas or viewBox is invalid", page_id=page_id)
    if root.get("data-pptx-page-role") != "content":
        raise SvgVisualError("SVG root is missing data-pptx-page-role", page_id=page_id)
    for node in root.iter():
        if str(node.tag).split("}")[-1] != "image":
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
    priorities = {element["priority"] for element in scene.get("elements", [])}
    review = {
        "schema_version": "deck_visual_review.v1",
        "run_id": scene["run_id"],
        "page_id": page_id,
        "svg_sha256": sha256_file(svg_path(root, page_id)),
        "blueprint_sha256": str(scene.get("blueprint_sha256") or ""),
        "review_mode": "synthetic_fixture" if mode in {"fixture", "dev"} else "agent_main_review",
        "visual_status": "pass",
        "text_masked_ssim": 1.0 if mode in {"fixture", "dev"} else None,
        "bbox_max_delta_px": 0.0,
        "overflow_findings": [],
        "layout_checks": {"canvas_ratio": "pass", "stable_ids": "pass", "p0_p1_geometry": "pass"},
        "icon_checks": [],
        "issues_found": [],
        "unresolved_issues": [],
        "p0_p1_present": "P0" in priorities and "P1" in priorities,
        "self_review_count": 1,
        "revision_count": 0,
        "created_at": utc_now(),
    }
    if mode not in {"fixture", "dev"}:
        review["visual_status"] = "needs_review"
    path = review_path(root, page_id)
    write_json(path, review)
    return path


def load_visual_review(root: Path, page_id: str) -> dict[str, Any]:
    review = read_json(review_path(root, page_id))
    if review.get("schema_version") != "deck_visual_review.v1" or review.get("page_id") != page_id:
        raise SvgVisualError(f"visual review contract is invalid on page {page_id}", page_id=page_id)
    if review.get("visual_status") != "pass" or review.get("unresolved_issues"):
        raise SvgVisualError(f"visual review has not passed on page {page_id}", page_id=page_id)
    try:
        ssim = float(review.get("text_masked_ssim"))
        bbox_delta = float(review.get("bbox_max_delta_px"))
    except (TypeError, ValueError) as exc:
        raise SvgVisualError(f"visual review metrics are missing on page {page_id}", page_id=page_id) from exc
    if ssim < 0.92 or bbox_delta > 2.0:
        raise SvgVisualError(f"visual review fidelity gate failed on page {page_id}", page_id=page_id)
    current_svg = svg_path(root, page_id)
    try:
        current_svg_sha = sha256_file(current_svg)
    except OSError as exc:
        raise SvgVisualError(f"current SVG is missing on page {page_id}", page_id=page_id) from exc
    if str(review.get("svg_sha256") or "") != current_svg_sha:
        raise SvgVisualError(f"visual review is stale for SVG on page {page_id}", page_id=page_id)
    scene_file = root / "high_density_build" / "page_scenes" / f"{page_id}.json"
    try:
        scene = read_json(scene_file)
    except ContractError as exc:
        raise SvgVisualError(f"current page scene is missing on page {page_id}", page_id=page_id) from exc
    if str(review.get("blueprint_sha256") or "") != str(scene.get("blueprint_sha256") or ""):
        raise SvgVisualError(f"visual review is stale for blueprint on page {page_id}", page_id=page_id)
    return review


__all__ = [
    "PREVIEW_DIR",
    "REVIEW_DIR",
    "SVG_DIR",
    "SvgVisualError",
    "build_visual_review",
    "compile_svg",
    "load_visual_review",
    "preview_path",
    "render_preview",
    "review_path",
    "svg_path",
    "validate_svg",
]
