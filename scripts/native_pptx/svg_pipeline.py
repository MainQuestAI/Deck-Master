"""Native SVG pipeline helpers (SC-1.1 ND-01).

Moved verbatim from high_density/svg.py: run-relative artifact paths,
the SVG subset validator and its constants. One implementation; the
high-density svg module re-imports these names.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .canvas import CANVAS_HEIGHT, CANVAS_WIDTH
from .contracts import ContractError
from .svg_native import SvgNativeError, format_svg_native_error, parse_svg_native, svg_recovery_command
from .svg_paint import SvgPaintError, parse_node_paint, parse_svg_paint
from .visual import VisualMetricsError, _svg_geometry_bbox


SVG_DIR = Path("high_density_build/svg")
PREVIEW_DIR = Path("high_density_build/previews")
REVIEW_DIR = Path("high_density_build/reviews")
COMPARISON_DIR = Path("high_density_build/comparisons")
FORBIDDEN_TAGS = {"foreignObject", "script", "iframe", "style"}
UNSUPPORTED_TAGS = {"mask", "clipPath", "pattern"}


def join_cjk_text_lines(parts: list[str]) -> str:
    """Normalize line boundaries only; retain characters and in-line spaces."""
    boundary = re.compile(r"[\u2e80-\ua4cf\uf900-\ufaff\uff00-\uffef]")
    joined = parts[0] if parts else ""
    for previous, following in zip(parts, parts[1:]):
        joiner = "" if (previous and following and boundary.fullmatch(previous[-1])
                        and boundary.fullmatch(following[0])) else " "
        joined += joiner + following
    return joined


class SvgVisualError(ContractError):
    def __init__(self, message: str, *, page_id: str = "", code: str = "HD_SVG_REVIEW_FAILED", element_id: str = "") -> None:
        self.page_id = page_id
        self.element_id = element_id
        self.code = code
        super().__init__(message)



def svg_path(root: Path, page_id: str) -> Path:
    from workflow.actions import active_input_path

    return active_input_path(root / SVG_DIR / f"{page_id}.svg")


def preview_path(root: Path, page_id: str) -> Path:
    return root / PREVIEW_DIR / f"{page_id}.png"


def review_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.visual_review.json"


def metrics_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.metrics.json"


def main_review_receipt_path(root: Path, page_id: str) -> Path:
    return root / REVIEW_DIR / f"{page_id}.main_review_receipt.json"


def validate_svg(path: Path, *, page_id: str = "") -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise SvgVisualError(f"SVG parse failed: {exc}", page_id=page_id) from exc
    try:
        paint_registry = parse_svg_paint(root)
    except SvgPaintError as exc:
        raise SvgVisualError(
            f"visual_id=<none> element_id={exc.element_id or '<none>'} property=<unknown> code={exc.code} reason={exc}; recovery: {svg_recovery_command(page_id)}",
            page_id=page_id,
            code=exc.code,
        ) from exc
    try:
        native_document = parse_svg_native(root)
    except SvgNativeError as exc:
        raise SvgVisualError(format_svg_native_error(exc, page_id=page_id), page_id=page_id, code=exc.code) from exc
    native_geometry = {str(element.get("element_id") or ""): element.get("bbox") or {} for element in native_document.get("elements") or []}
    tags = {str(node.tag).split("}")[-1] for node in root.iter()}
    forbidden = sorted(tags & FORBIDDEN_TAGS)
    if forbidden:
        raise SvgVisualError(f"forbidden SVG elements: {', '.join(forbidden)}", page_id=page_id)
    unsupported = sorted(tags & UNSUPPORTED_TAGS)
    if unsupported:
        offending = next(node for node in root.iter() if str(node.tag).split("}")[-1] in unsupported)
        element_id = str(offending.get("id") or "<anonymous>")
        raise SvgVisualError(
            f"unsupported SVG element {unsupported[0]} on {element_id}; recovery: deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id or '<page_id>'}",
            page_id=page_id,
            code="HD_SVG_UNSUPPORTED_ELEMENT",
        )
    from .canvas import NATIVE_CANVAS

    canvas_x, canvas_y, canvas_width, canvas_height = 0.0, 0.0, float(CANVAS_WIDTH), float(CANVAS_HEIGHT)
    if NATIVE_CANVAS.get():
        try:
            canvas_x, canvas_y, canvas_width, canvas_height = [float(value) for value in re.split(r"[\s,]+", str(root.get("viewBox") or "").strip())]
        except ValueError as exc:
            raise SvgVisualError("SVG viewBox requires four numbers", page_id=page_id) from exc
        if not all(math.isfinite(value) for value in (canvas_x, canvas_y, canvas_width, canvas_height)) or min(canvas_width, canvas_height) <= 0:
            raise SvgVisualError("SVG viewBox dimensions must be finite and positive", page_id=page_id)
    elif root.get("viewBox") != f"0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}":
        raise SvgVisualError("SVG canvas or viewBox is invalid", page_id=page_id)
    if root.tag.split("}")[-1] != "svg":
        raise SvgVisualError("SVG root must be svg", page_id=page_id)
    if not str(root.get("data-pptx-page-role") or ""):
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
            if attr_name in {"href", "xlink:href"} and tag not in {"image", "use"}:
                raise SvgVisualError(f"external SVG href is blocked on {node_id or tag}", page_id=page_id, code="HD_SVG_UNSAFE_ATTRIBUTE")
        if node_id:
            if node_id in ids:
                raise SvgVisualError(f"duplicate SVG element id: {node_id}", page_id=page_id)
            ids.add(node_id)
        if node.get("style") or node.get("class"):
            raise SvgVisualError("external CSS/style attributes are blocked", page_id=page_id)
        definition_node = tag in {"defs", "linearGradient", "radialGradient", "filter", "stop", "feDropShadow", "feGaussianBlur"}
        if node.get("opacity") is not None and not definition_node:
            try:
                opacity = float(str(node.get("opacity")).removesuffix("px"))
            except (TypeError, ValueError) as exc:
                raise SvgVisualError(f"SVG opacity is invalid: {node_id}", page_id=page_id) from exc
            if not math.isfinite(opacity) or opacity < 0 or opacity > 1:
                raise SvgVisualError(f"SVG opacity must be between 0 and 1: {node_id}", page_id=page_id)
        for attribute in () if definition_node else ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "stroke-width", "font-size"):
            if node.get(attribute) is None:
                continue
            try:
                value = float(str(node.get(attribute)).removesuffix("px"))
            except (TypeError, ValueError) as exc:
                raise SvgVisualError(f"SVG {attribute} is invalid: {node_id}", page_id=page_id) from exc
            if not math.isfinite(value) or (attribute in {"width", "height", "r", "rx", "ry", "stroke-width", "font-size"} and value < 0):
                raise SvgVisualError(f"SVG {attribute} is out of range: {node_id}", page_id=page_id)
        if tag not in {"svg", "g", "defs", "linearGradient", "radialGradient", "filter", "stop", "feDropShadow", "feGaussianBlur", "tspan", "title", "desc", "metadata"}:
            try:
                parse_node_paint(node, paint_registry)
            except SvgPaintError as exc:
                raise SvgVisualError(str(exc), page_id=page_id, code=exc.code) from exc
        if node.get("opacity") is not None and float(node.get("opacity")) == 0:
            # Transparent decorative geometry is a supported SVG boundary.
            # Hidden text (including alternate numeric spellings) cannot satisfy
            # the content lock or editability gate.
            hides_text = tag in {"text", "tspan"} or (tag == "g" and any(
                child.tag.rsplit("}", 1)[-1] in {"text", "tspan"} for child in node.iter()))
            if hides_text:
                message = "hidden SVG ancestor group is blocked" if tag == "g" else "hidden SVG element is blocked"
                raise SvgVisualError(f"{message}: {node_id}", page_id=page_id)
        if tag in visible_tags:
            if not node_id:
                raise SvgVisualError(f"visible SVG element must have a stable element id: {tag}", page_id=page_id)
            if not str(node.get("data-pptx-bounds") or ""):
                raise SvgVisualError(f"visible SVG element is missing data-pptx-bounds: {node_id}", page_id=page_id)
            try:
                bbox = native_geometry.get(node_id) or _svg_geometry_bbox(node)
            except VisualMetricsError as exc:
                raise SvgVisualError(f"SVG element geometry is invalid: {node_id}", page_id=page_id) from exc
            if bbox["x"] < canvas_x - 0.01 or bbox["y"] < canvas_y - 0.01 or bbox["x"] + bbox["w"] > canvas_x + canvas_width + 0.01 or bbox["y"] + bbox["h"] > canvas_y + canvas_height + 0.01:
                raise SvgVisualError(f"SVG element overflows the canvas: {node_id}", page_id=page_id)
        if tag != "image":
            continue
        if node.get("data-pptx-asset") != "registered":
            raise SvgVisualError("SVG image is missing registered asset marker", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=node_id)
        href = node.get("href") or node.get("{http://www.w3.org/1999/xlink}href") or ""
        if not href.startswith("data:image/"):
            raise SvgVisualError("SVG image must be an embedded registered asset", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=node_id)
        try:
            x = float(node.get("x") or 0)
            y = float(node.get("y") or 0)
            width = float(node.get("width") or 0)
            height = float(node.get("height") or 0)
        except ValueError as exc:
            raise SvgVisualError("SVG registered image geometry is invalid", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=node_id) from exc
        if x <= canvas_x + 0.01 and y <= canvas_y + 0.01 and width >= canvas_width - 0.01 and height >= canvas_height - 0.01:
            raise SvgVisualError("whole-page image wrapper is blocked", page_id=page_id, code="HD_ASSET_POLICY_BLOCKED", element_id=node_id)
    return {"valid": True, "tags": sorted(tags), "forbidden": [], "paint": paint_registry}
