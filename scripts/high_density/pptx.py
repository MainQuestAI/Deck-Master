from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .contracts import ContractError, sha256_file, utc_now, write_json
from .svg import _estimated_width, wrap_text

PPTX_DIR = Path("high_density_build/pptx")
TRACE_DIR = Path("high_density_build/traces")
READBACK_DIR = Path("high_density_build/readback")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
SLIDE_WIDTH_IN = 13.333333
SLIDE_HEIGHT_IN = 7.5
PPTX_BBOX_TOLERANCE_PT = 0.75


class PptxEditabilityError(ContractError):
    pass


_PATH_TOKEN_RE = re.compile(
    r"([AaCcHhLlMmQqSsTtVvZz])|([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)


def pptx_path(root: Path) -> Path:
    return root / PPTX_DIR / "deck_high_density.pptx"


def trace_path(root: Path) -> Path:
    return root / TRACE_DIR / "pptx_trace.json"


def readback_path(root: Path) -> Path:
    return root / READBACK_DIR / "readback_report.json"


def _rgb(value: Any, default: str = "18212b") -> RGBColor:
    text = str(value or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        text = default
    return RGBColor.from_string(text.upper())


def _inches(value: float, total: float) -> float:
    return float(value) / total * (SLIDE_WIDTH_IN if total == CANVAS_WIDTH else SLIDE_HEIGHT_IN)


def _set_shape_fill(shape: Any, style: dict[str, Any]) -> None:
    fill = str(style.get("fill") or "").lower()
    if fill in {"", "none", "transparent"}:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(fill)
    stroke = str(style.get("stroke") or "").lower()
    if stroke in {"", "none", "transparent"}:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = _rgb(stroke, "d5dde5")
        shape.line.width = Pt(float(style.get("stroke_width") or 1))


def _fit_text_size(element: dict[str, Any]) -> float:
    bbox = element["bbox"]
    fit = element.get("text_fit") or {}
    size = float(fit.get("preferred_size_px") or 18)
    min_size = float(fit.get("min_size_px") or max(9, size * 0.7))
    max_lines = int(fit.get("max_lines") or 1)
    line_height = float(fit.get("line_height") or 1.18)
    text = str(element.get("text") or "")
    lines = wrap_text(text, float(bbox["w"]), size)
    while len(lines) > max_lines and size > min_size:
        size = max(min_size, size - 1)
        lines = wrap_text(text, float(bbox["w"]), size)
    if (
        len(lines) > max_lines
        or len(lines) * size * line_height > float(bbox["h"]) + 0.01
        or any(_estimated_width(line, size) > float(bbox["w"]) + 0.01 for line in lines)
    ):
        raise PptxEditabilityError(f"text does not fit in {element.get('element_id')}")
    return size


def _add_text(slide: Any, element: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    bbox = element["bbox"]
    shape = slide.shapes.add_textbox(
        Inches(_inches(float(bbox["x"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["y"]), CANVAS_HEIGHT)),
        Inches(_inches(float(bbox["w"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["h"]), CANVAS_HEIGHT)),
    )
    shape.name = str(element["element_id"])
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Pt(0)
    frame.margin_right = Pt(0)
    frame.margin_top = Pt(0)
    frame.margin_bottom = Pt(0)
    paragraph = frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = str(element.get("text") or "")
    style = element.get("style") or {}
    font = run.font
    font.name = str(style.get("font_family") or "Arial")
    font.size = Pt(_fit_text_size(element) * 72 / 96)
    font.bold = str(style.get("font_weight") or "400") in {"600", "700", "bold", "Bold"}
    font.color.rgb = _rgb(style.get("fill"), "18212b")
    paragraph.space_after = Pt(0)
    trace.append({"element_id": element["element_id"], "object_type": "text", "shape_name": shape.name, "bbox": bbox, "text": element.get("text", "")})


def _add_rect(slide: Any, element: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    bbox = element["bbox"]
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if float((element.get("style") or {}).get("radius") or 0) > 0 else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type,
        Inches(_inches(float(bbox["x"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["y"]), CANVAS_HEIGHT)),
        Inches(_inches(float(bbox["w"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["h"]), CANVAS_HEIGHT)),
    )
    shape.name = str(element["element_id"])
    _set_shape_fill(shape, element.get("style") or {})
    trace.append({"element_id": element["element_id"], "object_type": "shape", "shape_name": shape.name, "bbox": bbox})


def _add_line(slide: Any, element: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    bbox = element["bbox"]
    shape = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(_inches(float(bbox["x"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["y"]), CANVAS_HEIGHT)),
        Inches(_inches(float(bbox["x"]) + float(bbox["w"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["y"]) + float(bbox["h"]), CANVAS_HEIGHT)),
    )
    shape.name = str(element["element_id"])
    style = element.get("style") or {}
    shape.line.color.rgb = _rgb(style.get("stroke"), "657485")
    shape.line.width = Pt(float(style.get("stroke_width") or 2))
    trace.append({"element_id": element["element_id"], "object_type": "line", "shape_name": shape.name, "bbox": bbox})


def _path_points(path_data: str) -> tuple[list[tuple[float, float]], bool]:
    """Parse the straight-line SVG subset supported by the first PPTX compiler."""
    matches = list(_PATH_TOKEN_RE.finditer(path_data))
    cursor = 0
    for match in matches:
        if path_data[cursor : match.start()].strip(" ,\t\r\n"):
            raise PptxEditabilityError("path contains unsupported separators or syntax")
        cursor = match.end()
    if path_data[cursor:].strip(" ,\t\r\n"):
        raise PptxEditabilityError("path contains unsupported separators or syntax")
    tokens = [(match.group(1) or match.group(2)) for match in matches]
    if not tokens:
        raise PptxEditabilityError("path is empty")

    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    start = current
    command = ""
    closed = False
    index = 0

    def number() -> float:
        nonlocal index
        if index >= len(tokens) or re.fullmatch(r"[A-Za-z]", tokens[index]):
            raise PptxEditabilityError("path command has incomplete coordinates")
        value = float(tokens[index])
        index += 1
        return value

    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"[A-Za-z]", token):
            command = token
            index += 1
            if command in "Zz":
                if len(points) < 2:
                    raise PptxEditabilityError("closed path needs at least two points")
                closed = True
                current = start
                command = ""
                continue
            if command not in "MmLlHhVv":
                raise PptxEditabilityError(f"unsupported path command: {command}")
        if not command:
            raise PptxEditabilityError("path coordinates are missing a command")

        relative = command.islower()
        upper = command.upper()
        if upper in {"M", "L"}:
            x = number()
            y = number()
            if relative:
                x += current[0]
                y += current[1]
            current = (x, y)
            if upper == "M" and not points:
                start = current
                points.append(current)
                command = "l" if relative else "L"
            else:
                points.append(current)
        elif upper == "H":
            x = number()
            if relative:
                x += current[0]
            current = (x, current[1])
            points.append(current)
        elif upper == "V":
            y = number()
            if relative:
                y += current[1]
            current = (current[0], y)
            points.append(current)

    if len(points) < 2:
        raise PptxEditabilityError("path needs at least two points")
    return points, closed


def _add_path(slide: Any, element: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    points, closed = _path_points(str(element.get("path") or ""))
    _add_freeform(slide, element, points, closed=closed, trace=trace)


def _add_freeform(
    slide: Any,
    element: dict[str, Any],
    points: list[tuple[float, float]],
    *,
    closed: bool,
    trace: list[dict[str, Any]],
) -> None:
    x_scale = float(Inches(SLIDE_WIDTH_IN)) / CANVAS_WIDTH
    y_scale = float(Inches(SLIDE_HEIGHT_IN)) / CANVAS_HEIGHT
    emu_points = [(x * x_scale, y * y_scale) for x, y in points]
    builder = slide.shapes.build_freeform(
        start_x=emu_points[0][0],
        start_y=emu_points[0][1],
        scale=1.0,
    )
    builder.add_line_segments(emu_points[1:], close=closed)
    shape = builder.convert_to_shape()
    shape.name = str(element["element_id"])
    _set_shape_fill(shape, element.get("style") or {})
    trace.append({"element_id": element["element_id"], "object_type": "freeform", "shape_name": shape.name, "bbox": element["bbox"], "closed": closed})


def _add_polygon(slide: Any, element: dict[str, Any], trace: list[dict[str, Any]]) -> None:
    points = [(float(point[0]), float(point[1])) for point in element.get("points") or []]
    if len(points) < 3:
        raise PptxEditabilityError(f"polygon needs at least three points in {element.get('element_id')}")
    _add_freeform(slide, element, points, closed=True, trace=trace)


def _add_image(slide: Any, element: dict[str, Any], asset_paths: dict[str, Path], trace: list[dict[str, Any]]) -> None:
    asset_id = str(element.get("asset_ref") or "")
    asset_path = asset_paths.get(asset_id)
    if asset_path is None or not asset_path.is_file():
        raise PptxEditabilityError(f"registered image asset is unavailable: {asset_id}")
    bbox = element["bbox"]
    shape = slide.shapes.add_picture(
        str(asset_path),
        Inches(_inches(float(bbox["x"]), CANVAS_WIDTH)),
        Inches(_inches(float(bbox["y"]), CANVAS_HEIGHT)),
        width=Inches(_inches(float(bbox["w"]), CANVAS_WIDTH)),
        height=Inches(_inches(float(bbox["h"]), CANVAS_HEIGHT)),
    )
    shape.name = str(element["element_id"])
    trace.append({"element_id": element["element_id"], "object_type": "registered_asset", "shape_name": shape.name, "asset_id": asset_id, "bbox": bbox})


def compile_pptx(
    root: Path,
    scenes: list[dict[str, Any]],
    locks: dict[str, dict[str, Any]],
    *,
    asset_paths_by_page: dict[str, dict[str, Path]] | None = None,
) -> tuple[Path, Path]:
    presentation = Presentation()
    presentation.slide_width = Inches(SLIDE_WIDTH_IN)
    presentation.slide_height = Inches(SLIDE_HEIGHT_IN)
    blank_layout = presentation.slide_layouts[6]
    trace_pages: list[dict[str, Any]] = []
    for scene in scenes:
        slide = presentation.slides.add_slide(blank_layout)
        trace: list[dict[str, Any]] = []
        for element in scene.get("elements", []):
            kind = element.get("kind")
            if kind == "text":
                _add_text(slide, element, trace)
            elif kind == "rect":
                _add_rect(slide, element, trace)
            elif kind == "line":
                _add_line(slide, element, trace)
            elif kind == "path":
                _add_path(slide, element, trace)
            elif kind == "polygon":
                _add_polygon(slide, element, trace)
            elif kind == "image":
                _add_image(slide, element, (asset_paths_by_page or {}).get(str(scene["page_id"]), {}), trace)
            else:
                raise PptxEditabilityError(f"unsupported scene element kind: {kind}")
        notes = str((locks.get(str(scene["page_id"])) or {}).get("customer_visible", {}).get("speaker_notes") or "")
        if not notes:
            notes = str((locks.get(str(scene["page_id"])) or {}).get("speaker_notes") or "")
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        trace_pages.append({"page_id": scene["page_id"], "elements": trace, "speaker_notes_present": bool(notes)})
    output = pptx_path(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(output)
    trace_file = trace_path(root)
    write_json(trace_file, {"schema_version": "deck_pptx_trace.v1", "pptx_sha256": sha256_file(output), "pages": trace_pages, "created_at": utc_now()})
    return output, trace_file


def readback_pptx(root: Path, scenes: list[dict[str, Any]], locks: dict[str, dict[str, Any]], output: Path) -> Path:
    presentation = Presentation(output)
    expected_text: list[str] = []
    for scene in scenes:
        expected_text.extend(str(element.get("text") or "") for element in scene.get("elements", []) if element.get("kind") == "text" and element.get("priority") in {"P0", "P1"})
    actual_text: list[str] = []
    missing_elements: list[str] = []
    geometry_errors: list[str] = []
    geometry_mismatches: list[dict[str, Any]] = []
    notes_count = 0
    expected_image_count = sum(
        1
        for scene in scenes
        for element in scene.get("elements", [])
        if element.get("kind") == "image"
    )
    actual_image_count = sum(
        1
        for slide in presentation.slides
        for shape in slide.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    )
    expected_notes_count = sum(
        1
        for scene in scenes
        if str((locks.get(str(scene["page_id"])) or {}).get("speaker_notes") or "").strip()
    )
    for slide_index, slide in enumerate(presentation.slides):
        actual_text.extend(shape.text for shape in slide.shapes if hasattr(shape, "text") and shape.text)
        if slide.notes_slide.notes_text_frame.text.strip():
            notes_count += 1
        for shape in slide.shapes:
            name = str(shape.name or "")
            if name and name not in {"", "Title 1"} and hasattr(shape, "left"):
                if shape.left < 0 or shape.top < 0 or shape.left + shape.width > presentation.slide_width or shape.top + shape.height > presentation.slide_height:
                    geometry_errors.append(name)
        if slide_index < len(scenes):
            expected_elements = {
                str(element.get("element_id")): element
                for element in scenes[slide_index].get("elements", [])
            }
            actual_elements = {str(shape.name): shape for shape in slide.shapes if shape.name}
            for element_id, element in expected_elements.items():
                shape = actual_elements.get(element_id)
                if shape is None:
                    missing_elements.append(element_id)
                    continue
                expected = element["bbox"]
                actual = {
                    "x": float(shape.left) / float(presentation.slide_width) * CANVAS_WIDTH,
                    "y": float(shape.top) / float(presentation.slide_height) * CANVAS_HEIGHT,
                    "w": float(shape.width) / float(presentation.slide_width) * CANVAS_WIDTH,
                    "h": float(shape.height) / float(presentation.slide_height) * CANVAS_HEIGHT,
                }
                deltas = {
                    key: abs(actual[key] - float(expected[key]))
                    for key in ("x", "y", "w", "h")
                }
                px_to_pt = SLIDE_WIDTH_IN * 72 / CANVAS_WIDTH
                if max(deltas.values()) * px_to_pt > PPTX_BBOX_TOLERANCE_PT:
                    geometry_mismatches.append(
                        {"element_id": element_id, "expected": expected, "actual": actual, "delta": deltas}
                    )
    normalized_actual = "\n".join(actual_text)
    missing_text = [text for text in expected_text if text and text not in normalized_actual]
    report = {
        "schema_version": "deck_pptx_readback.v1",
        "pptx_sha256": sha256_file(output),
        "slide_count": len(presentation.slides),
        "expected_slide_count": len(scenes),
        "speaker_notes_count": notes_count,
        "expected_speaker_notes_count": expected_notes_count,
        "text_readback": {"expected_p0_p1": len(expected_text), "missing": missing_text},
        "geometry": {"out_of_bounds": geometry_errors, "mismatches": geometry_mismatches},
        "editable_object_count": sum(len(slide.shapes) for slide in presentation.slides),
        "image_shape_count": actual_image_count,
        "expected_image_count": expected_image_count,
        "status": "pass" if len(presentation.slides) == len(scenes) and notes_count == expected_notes_count and actual_image_count == expected_image_count and not missing_text and not missing_elements and not geometry_errors and not geometry_mismatches else "failed",
        "created_at": utc_now(),
    }
    if report["status"] != "pass":
        raise PptxEditabilityError(f"PPTX readback failed: {report}")
    path = readback_path(root)
    write_json(path, report)
    return path


__all__ = ["PptxEditabilityError", "compile_pptx", "pptx_path", "readback_path", "readback_pptx", "trace_path"]
