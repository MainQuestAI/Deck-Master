from __future__ import annotations

import copy
import math
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .blueprint import CANVAS_HEIGHT, CANVAS_WIDTH, image_dimensions
from .contracts import ContractError, read_json, run_relative, sha256_file, sha256_json, write_json


class VisualMetricsError(ContractError):
    pass


VISUAL_QUALITY_POLICY: dict[str, Any] = {
    "version": "visual-quality-policy.v1",
    "crop": {
        "padding": "max(4px,12%)",
        "size_px": 256,
        "tiny_size_px": 512,
        "minimum_object_size_px": 8,
    },
    "blueprint_vs_svg": {
        "ssim_min": 0.80,
        "edge_f1_min": 0.60,
        "silhouette_iou_min": 0.65,
        "color_delta_max": 0.20,
        "bbox_delta_px_max": 3.0,
        "occupancy_delta_max": 0.25,
    },
    "svg_vs_pptx": {
        "ssim_min": 0.95,
        "edge_f1_min": 0.90,
        "silhouette_iou_min": 0.92,
        "color_delta_max": 0.08,
        "bbox_delta_px_max": 1.0,
        "occupancy_delta_max": 0.12,
    },
    "renderer_tolerance": {
        "alignment_radius_px": 4,
        "local_match_blur_radius_px": 1.0,
        "silhouette_luma_threshold": 225,
        "edge_delta_threshold": 2,
        "edge_dilation_kernel": 5,
    },
    "full_page": {
        "text_mask_max_coverage": 0.35,
        "min_unmasked_coverage": 0.25,
        "p0_p1_bbox_delta_px_max": 2.0,
        "p0_p1_text_contrast_ratio_min": 3.0,
    },
}
VISUAL_QUALITY_POLICY_SHA256 = sha256_json(VISUAL_QUALITY_POLICY)
_RENDERER_FINGERPRINT_CACHE: dict[str, Any] | None = None


_PATH_TOKEN_RE = re.compile(r"([AaCcHhLlMmQqSsTtVvZz])|([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)")


def _number(value: Any, *, label: str) -> float:
    try:
        raw = str(value).strip()
        result = float(raw[:-2] if raw.lower().endswith("px") else raw)
    except (TypeError, ValueError) as exc:
        raise VisualMetricsError(f"SVG {label} is not numeric") from exc
    if not math.isfinite(result):
        raise VisualMetricsError(f"SVG {label} is not finite")
    return result


def _declared_bounds(node: Any) -> dict[str, float]:
    raw = str(node.get("data-pptx-bounds") or "")
    values = raw.split(",")
    if len(values) != 4:
        raise VisualMetricsError(f"SVG element {node.get('id') or '<anonymous>'} has invalid data-pptx-bounds")
    x, y, width, height = (_number(value, label="data-pptx-bounds") for value in values)
    if width < 0 or height < 0:
        raise VisualMetricsError(f"SVG element {node.get('id') or '<anonymous>'} has negative bounds")
    return {"x": x, "y": y, "w": width, "h": height}


def _points_bounds(points: list[tuple[float, float]]) -> dict[str, float]:
    if not points:
        raise VisualMetricsError("SVG geometry has no points")
    xs, ys = zip(*points)
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def _path_points(path_data: str) -> list[tuple[float, float]]:
    matches = list(_PATH_TOKEN_RE.finditer(path_data))
    cursor = 0
    for match in matches:
        if path_data[cursor : match.start()].strip(" ,\t\r\n"):
            raise VisualMetricsError("SVG path contains unsupported separators or syntax")
        cursor = match.end()
    if path_data[cursor:].strip(" ,\t\r\n"):
        raise VisualMetricsError("SVG path contains unsupported separators or syntax")
    tokens = [(match.group(1) or match.group(2)) for match in matches]
    if not tokens:
        raise VisualMetricsError("SVG path is empty")
    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    start = current
    command = ""
    index = 0

    def number() -> float:
        nonlocal index
        if index >= len(tokens) or re.fullmatch(r"[A-Za-z]", tokens[index]):
            raise VisualMetricsError("SVG path command has incomplete coordinates")
        value = _number(tokens[index], label="path coordinate")
        index += 1
        return value

    def point(x: float, y: float, relative: bool) -> tuple[float, float]:
        return (x + current[0], y + current[1]) if relative else (x, y)

    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"[A-Za-z]", token):
            command = token
            index += 1
            if command in "Zz":
                current = start
                command = ""
                continue
            if command.upper() not in {"M", "L", "H", "V", "C", "Q"}:
                raise VisualMetricsError(f"SVG path command is unsupported: {command}")
        if not command:
            raise VisualMetricsError("SVG path coordinates are missing a command")
        relative = command.islower()
        upper = command.upper()
        if upper in {"M", "L"}:
            target = point(number(), number(), relative)
            current = target
            if upper == "M" and not points:
                start = target
            points.append(target)
            if upper == "M":
                command = "l" if relative else "L"
        elif upper == "H":
            x = number()
            current = (x + current[0], current[1]) if relative else (x, current[1])
            points.append(current)
        elif upper == "V":
            y = number()
            current = (current[0], y + current[1]) if relative else (current[0], y)
            points.append(current)
        elif upper == "C":
            control_1 = point(number(), number(), relative)
            control_2 = point(number(), number(), relative)
            target = point(number(), number(), relative)
            origin = current
            for step in range(1, 17):
                t = step / 16
                inverse = 1 - t
                points.append((inverse**3 * origin[0] + 3 * inverse**2 * t * control_1[0] + 3 * inverse * t**2 * control_2[0] + t**3 * target[0], inverse**3 * origin[1] + 3 * inverse**2 * t * control_1[1] + 3 * inverse * t**2 * control_2[1] + t**3 * target[1]))
            current = target
        elif upper == "Q":
            control = point(number(), number(), relative)
            target = point(number(), number(), relative)
            origin = current
            for step in range(1, 13):
                t = step / 12
                inverse = 1 - t
                points.append((inverse**2 * origin[0] + 2 * inverse * t * control[0] + t**2 * target[0], inverse**2 * origin[1] + 2 * inverse * t * control[1] + t**2 * target[1]))
            current = target
    return points


def _svg_geometry_bbox(node: Any) -> dict[str, float]:
    tag = str(node.tag).split("}")[-1]
    if tag == "text":
        bounds = _declared_bounds(node)
        x = _number(node.get("x"), label="text x")
        baseline = _number(node.get("y"), label="text y")
        font_size = _number(node.get("font-size"), label="text font-size")
        if x < bounds["x"] - 0.01 or x > bounds["x"] + bounds["w"] + 0.01 or baseline < bounds["y"] or baseline > bounds["y"] + bounds["h"] + font_size:
            raise VisualMetricsError(f"SVG text geometry escapes its declared layout box: {node.get('id')}")
        return bounds
    if tag == "rect":
        return {"x": _number(node.get("x") or 0, label="rect x"), "y": _number(node.get("y") or 0, label="rect y"), "w": _number(node.get("width"), label="rect width"), "h": _number(node.get("height"), label="rect height")}
    if tag == "line":
        x1, y1 = _number(node.get("x1"), label="line x1"), _number(node.get("y1"), label="line y1")
        x2, y2 = _number(node.get("x2"), label="line x2"), _number(node.get("y2"), label="line y2")
        return _points_bounds([(x1, y1), (x2, y2)])
    if tag in {"circle", "ellipse"}:
        cx, cy = _number(node.get("cx"), label="ellipse cx"), _number(node.get("cy"), label="ellipse cy")
        rx = _number(node.get("r"), label="circle r") if tag == "circle" else _number(node.get("rx"), label="ellipse rx")
        ry = rx if tag == "circle" else _number(node.get("ry"), label="ellipse ry")
        if rx < 0 or ry < 0:
            raise VisualMetricsError(f"SVG ellipse has negative radius: {node.get('id')}")
        return {"x": cx - rx, "y": cy - ry, "w": rx * 2, "h": ry * 2}
    if tag in {"polygon", "polyline"}:
        raw = str(node.get("points") or "")
        values = [_number(value, label="polygon point") for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", raw)]
        if len(values) < 6 or len(values) % 2:
            raise VisualMetricsError(f"SVG {tag} has invalid points: {node.get('id')}")
        return _points_bounds(list(zip(values[::2], values[1::2])))
    if tag == "path":
        return _points_bounds(_path_points(str(node.get("d") or "")))
    if tag == "image":
        return {"x": _number(node.get("x") or 0, label="image x"), "y": _number(node.get("y") or 0, label="image y"), "w": _number(node.get("width"), label="image width"), "h": _number(node.get("height"), label="image height")}
    raise VisualMetricsError(f"SVG geometry is unavailable for element {node.get('id') or '<anonymous>'}")


def _svg_element_bboxes(root: Path, page_id: str, element_ids: set[str]) -> dict[str, dict[str, float]]:
    from .svg_native import SvgNativeError, parse_svg_native

    try:
        document = ElementTree.fromstring(root.read_text(encoding="utf-8"))
        native = parse_svg_native(document)
    except (OSError, ElementTree.ParseError, SvgNativeError, ContractError) as exc:
        raise VisualMetricsError(f"cannot inspect SVG geometry: {root}") from exc
    geometries = {
        str(item.get("element_id") or ""): dict(item.get("bbox") or {})
        for item in native.get("elements") or []
        if item.get("element_id")
    }
    missing = sorted(element_ids - set(geometries))
    if missing:
        raise VisualMetricsError(f"SVG is missing geometry for page {page_id}: {', '.join(missing)}")
    return {element_id: geometries[element_id] for element_id in sorted(element_ids)}


def _load_image(path: Path, *, size: tuple[int, int] = (CANVAS_WIDTH, CANVAS_HEIGHT)):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency probe covers this
        raise VisualMetricsError("Pillow is required for visual metrics") from exc
    try:
        with Image.open(path) as image:
            return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    except Exception as exc:
        raise VisualMetricsError(f"cannot read visual artifact: {path}") from exc


def _render_svg_to_png(svg: Path, output: Path, width: int, height: int) -> Path:
    converter = shutil.which("rsvg-convert")
    if not converter:
        raise VisualMetricsError("rsvg-convert is required for blueprint normalization")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([converter, "-w", str(width), "-h", str(height), "-o", str(output), str(svg)], capture_output=True, text=True)
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        raise VisualMetricsError(result.stderr.strip() or "SVG renderer failed")
    return output


def normalize_blueprint(root: Path, manifest: dict[str, Any]) -> Path:
    """Crop the approved source frame into the canonical comparison canvas."""
    from PIL import Image, ImageFilter

    source = root / str(manifest["image_path"])
    width, height = image_dimensions(source)
    raw = source
    temp = root / "high_density_build" / "blueprints" / f".{manifest['page_id']}.source.png"
    if source.suffix.lower() == ".svg":
        _render_svg_to_png(source, temp, width, height)
        raw = temp
    image = _load_image(raw, size=(width, height))
    frame = manifest["slide_frame"]
    x, y, w, h = (float(frame[key]) for key in ("x", "y", "w", "h"))
    left, top = max(0, round(x)), max(0, round(y))
    right, bottom = min(width, round(x + w)), min(height, round(y + h))
    cropped = image.crop((left, top, right, bottom)).resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    output = root / "high_density_build" / "blueprints" / f"{manifest['page_id']}.normalized.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output, format="PNG")
    if temp.exists():
        temp.unlink()
    return output


def _ssim(reference, candidate, mask=None) -> float:
    import numpy as np

    reference_array = np.asarray(reference.convert("L"), dtype=np.float64)
    candidate_array = np.asarray(candidate.convert("L"), dtype=np.float64)
    if reference_array.shape != candidate_array.shape:
        raise VisualMetricsError("visual comparison images must have the same dimensions")
    if mask is not None:
        valid = ~mask
        if int(valid.sum()) < 1000:
            raise VisualMetricsError("visual mask leaves too few valid pixels")
        # Text is evaluated through content/readback contracts.  Replacing it
        # in the visual candidate makes the SSIM measure the surrounding
        # composition, edges, color, and spacing rather than font rasterizer
        # differences between rsvg-convert and LibreOffice.
        candidate_array = candidate_array.copy()
        candidate_array[mask] = reference_array[mask]

    window = 11
    if min(reference_array.shape) < window:
        return 1.0

    def box_sum(array):
        padded = np.pad(array, ((1, 0), (1, 0)), mode="constant")
        integral = padded.cumsum(axis=0).cumsum(axis=1)
        return integral[window:, window:] - integral[:-window, window:] - integral[window:, :-window] + integral[:-window, :-window]

    area = float(window * window)
    mean_reference = box_sum(reference_array) / area
    mean_candidate = box_sum(candidate_array) / area
    variance_reference = np.maximum(0.0, box_sum(reference_array * reference_array) / area - mean_reference * mean_reference)
    variance_candidate = np.maximum(0.0, box_sum(candidate_array * candidate_array) / area - mean_candidate * mean_candidate)
    covariance = box_sum(reference_array * candidate_array) / area - mean_reference * mean_candidate
    c1, c2 = 6.5025, 58.5225
    numerator = (2 * mean_reference * mean_candidate + c1) * (2 * covariance + c2)
    denominator = (mean_reference * mean_reference + mean_candidate * mean_candidate + c1) * (variance_reference + variance_candidate + c2)
    score = np.divide(numerator, denominator, out=np.ones_like(numerator), where=denominator != 0)
    return max(0.0, min(1.0, float(np.mean(score))))


def _text_mask(svg_file: Path, page_id: str):
    import numpy as np

    try:
        document = ElementTree.fromstring(svg_file.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise VisualMetricsError(f"cannot build text mask from SVG on page {page_id}") from exc
    masked = copy.deepcopy(document)
    visible_tags = {"text", "rect", "circle", "ellipse", "line", "path", "polyline", "polygon", "image"}
    for node in masked.iter():
        tag = str(node.tag).split("}")[-1]
        if tag == "text" or tag == "tspan":
            node.set("fill", "#000000")
            node.set("stroke", "none")
            node.set("opacity", "1")
            node.attrib.pop("filter", None)
        elif tag in visible_tags:
            node.set("opacity", "0")
    namespace = str(masked.tag).split("}")[0].removeprefix("{") if "}" in str(masked.tag) else "http://www.w3.org/2000/svg"
    background = ElementTree.Element(f"{{{namespace}}}rect", {"x": "0", "y": "0", "width": str(CANVAS_WIDTH), "height": str(CANVAS_HEIGHT), "fill": "#ffffff"})
    masked.insert(0, background)
    with tempfile.TemporaryDirectory(prefix="deck-master-text-mask-") as directory:
        temp_svg = Path(directory) / f"{page_id}.svg"
        temp_png = Path(directory) / f"{page_id}.png"
        ElementTree.ElementTree(masked).write(temp_svg, encoding="utf-8", xml_declaration=True)
        _render_svg_to_png(temp_svg, temp_png, CANVAS_WIDTH, CANVAS_HEIGHT)
        grayscale = np.asarray(_load_image(temp_png).convert("L"))
    mask = grayscale < 250
    expanded = mask.copy()
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            shifted = np.zeros_like(mask)
            source_y = slice(max(0, -dy), min(CANVAS_HEIGHT, CANVAS_HEIGHT - dy))
            source_x = slice(max(0, -dx), min(CANVAS_WIDTH, CANVAS_WIDTH - dx))
            target_y = slice(max(0, dy), min(CANVAS_HEIGHT, CANVAS_HEIGHT + dy))
            target_x = slice(max(0, dx), min(CANVAS_WIDTH, CANVAS_WIDTH + dx))
            shifted[target_y, target_x] = mask[source_y, source_x]
            expanded |= shifted
    coverage = float(expanded.mean())
    full_page = VISUAL_QUALITY_POLICY["full_page"]
    if coverage > float(full_page["text_mask_max_coverage"]):
        raise VisualMetricsError(f"text mask coverage exceeds {full_page['text_mask_max_coverage']:.0%} on page {page_id}: {coverage:.4f}")
    if float((~expanded).mean()) < float(full_page["min_unmasked_coverage"]):
        raise VisualMetricsError(f"text mask leaves less than {full_page['min_unmasked_coverage']:.0%} valid pixels on page {page_id}")
    if int((~expanded).sum()) < 1000:
        raise VisualMetricsError(f"text mask leaves too few valid pixels on page {page_id}")
    return expanded


def _relative_luminance(rgb):
    import numpy as np

    normalized = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(normalized <= 0.04045, normalized / 12.92, ((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[..., 0] + 0.7152 * linear[..., 1] + 0.0722 * linear[..., 2]


def _text_contrast_metrics(svg_file: Path, scene: dict[str, Any], candidate=None) -> dict[str, Any]:
    import numpy as np

    page_id = str(scene.get("page_id") or "")
    required = {
        str(element.get("element_id") or ""): element
        for element in scene.get("elements") or []
        if element.get("kind") == "text" and element.get("priority") in {"P0", "P1"}
    }
    if not required:
        return {"minimum_ratio": 21.0, "elements": {}}
    try:
        document = ElementTree.fromstring(svg_file.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise VisualMetricsError(f"cannot inspect SVG text contrast on page {page_id}") from exc
    background_document = copy.deepcopy(document)
    hidden_ids: set[str] = set()
    for node in background_document.iter():
        element_id = str(node.get("id") or "")
        if element_id in required:
            node.set("display", "none")
            hidden_ids.add(element_id)
    missing = sorted(set(required) - hidden_ids)
    if missing:
        raise VisualMetricsError(f"cannot measure missing required text contrast on page {page_id}: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="deck-master-text-contrast-") as directory:
        directory_path = Path(directory)
        background_svg = directory_path / f"{page_id}.background.svg"
        background_png = directory_path / f"{page_id}.background.png"
        ElementTree.ElementTree(background_document).write(background_svg, encoding="utf-8", xml_declaration=True)
        _render_svg_to_png(background_svg, background_png, CANVAS_WIDTH, CANVAS_HEIGHT)
        background = _load_image(background_png)
        if candidate is None:
            candidate_png = directory_path / f"{page_id}.candidate.png"
            _render_svg_to_png(svg_file, candidate_png, CANVAS_WIDTH, CANVAS_HEIGHT)
            candidate = _load_image(candidate_png)

    candidate_array = np.asarray(candidate.convert("RGB"), dtype=np.uint8)
    background_array = np.asarray(background.convert("RGB"), dtype=np.uint8)
    geometry = _svg_element_bboxes(svg_file, page_id, set(required))
    element_metrics: dict[str, dict[str, Any]] = {}
    for element_id, element in required.items():
        bbox = geometry[element_id]
        left = max(0, int(math.floor(float(bbox["x"]))))
        top = max(0, int(math.floor(float(bbox["y"]))))
        right = min(CANVAS_WIDTH, int(math.ceil(float(bbox["x"]) + float(bbox["w"]))))
        bottom = min(CANVAS_HEIGHT, int(math.ceil(float(bbox["y"]) + float(bbox["h"]))))
        foreground = candidate_array[top:bottom, left:right]
        underlying = background_array[top:bottom, left:right]
        delta = np.max(np.abs(foreground.astype(np.int16) - underlying.astype(np.int16)), axis=2)
        changed = delta >= 2
        minimum_pixels = max(4, len(re.sub(r"\s+", "", str(element.get("text") or ""))))
        if int(changed.sum()) < minimum_pixels:
            contrast_ratio = 1.0
            changed_pixels = int(changed.sum())
        else:
            changed_values = delta[changed]
            core_threshold = max(2.0, float(np.percentile(changed_values, 75)))
            core = changed & (delta >= core_threshold)
            foreground_luminance = _relative_luminance(foreground[core])
            background_luminance = _relative_luminance(underlying[core])
            lighter = np.maximum(foreground_luminance, background_luminance)
            darker = np.minimum(foreground_luminance, background_luminance)
            contrast_ratio = float(np.median((lighter + 0.05) / (darker + 0.05)))
            changed_pixels = int(changed.sum())
        element_metrics[element_id] = {
            "priority": str(element.get("priority") or ""),
            "contrast_ratio": round(contrast_ratio, 6),
            "changed_pixels": changed_pixels,
        }
    return {
        "minimum_ratio": min(float(item["contrast_ratio"]) for item in element_metrics.values()),
        "elements": element_metrics,
    }


def _edge_similarity(reference, candidate, mask) -> float:
    import numpy as np

    first = np.asarray(reference.convert("L"), dtype=np.int16)
    second = np.asarray(candidate.convert("L"), dtype=np.int16)
    first_edges = np.zeros_like(first, dtype=bool)
    second_edges = np.zeros_like(second, dtype=bool)
    first_edges[:, 1:] |= np.abs(first[:, 1:] - first[:, :-1]) > 20
    first_edges[1:, :] |= np.abs(first[1:, :] - first[:-1, :]) > 20
    second_edges[:, 1:] |= np.abs(second[:, 1:] - second[:, :-1]) > 20
    second_edges[1:, :] |= np.abs(second[1:, :] - second[:-1, :]) > 20
    valid = ~mask
    first_edges &= valid
    second_edges &= valid
    denominator = int(first_edges.sum()) + int(second_edges.sum())
    return 1.0 if denominator == 0 else 2.0 * float((first_edges & second_edges).sum()) / denominator


def _overlap_area(first: dict[str, Any], second: dict[str, Any]) -> float:
    width = max(0.0, min(float(first["x"]) + float(first["w"]), float(second["x"]) + float(second["w"])) - max(float(first["x"]), float(second["x"])))
    height = max(0.0, min(float(first["y"]) + float(first["h"]), float(second["y"]) + float(second["h"])) - max(float(first["y"]), float(second["y"])))
    return width * height


def _color_delta(reference, candidate, mask=None) -> float:
    import numpy as np

    a = np.asarray(reference, dtype=np.float64)
    b = np.asarray(candidate, dtype=np.float64)
    if mask is not None:
        valid = ~mask
        if int(valid.sum()) < 1000:
            raise VisualMetricsError("visual mask leaves too few valid pixels")
        a, b = a[valid], b[valid]
    return float(np.abs(a - b).mean() / 255.0)


def _region_ssim(reference, candidate, mask, bbox: dict[str, Any]) -> float:
    x = max(0, int(float(bbox.get("x") or 0)))
    y = max(0, int(float(bbox.get("y") or 0)))
    right = min(CANVAS_WIDTH, x + max(1, int(float(bbox.get("w") or 0))))
    bottom = min(CANVAS_HEIGHT, y + max(1, int(float(bbox.get("h") or 0))))
    if right <= x or bottom <= y:
        return 0.0
    return _ssim(reference.crop((x, y, right, bottom)), candidate.crop((x, y, right, bottom)), mask[y:bottom, x:right])


def _svg_component_ids(root: Path, page_id: str) -> set[str]:
    svg_path = root / "high_density_build" / "svg" / f"{page_id}.svg"
    if not svg_path.exists():
        return set()
    try:
        document = ElementTree.fromstring(svg_path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise VisualMetricsError(f"cannot inspect SVG component registry: {svg_path}") from exc
    return {str(node.get("data-pptx-component") or "") for node in document.iter() if node.get("data-pptx-component")}


def renderer_fingerprint() -> dict[str, Any]:
    """Capture the actual render toolchain used by visual evidence."""
    global _RENDERER_FINGERPRINT_CACHE
    if _RENDERER_FINGERPRINT_CACHE is not None:
        return copy.deepcopy(_RENDERER_FINGERPRINT_CACHE)
    import numpy
    from PIL import __version__ as pillow_version
    from pptx import __version__ as pptx_version

    def command_version(command: str, args: list[str]) -> str:
        executable = shutil.which(command)
        if not executable:
            return "missing"
        result = subprocess.run([executable, *args], capture_output=True, text=True)
        text = (result.stdout or result.stderr).strip().splitlines()
        return text[0][:240] if text else "unknown"

    font_path = ""
    matcher = shutil.which("fc-match")
    if matcher:
        result = subprocess.run([matcher, "Arial", "-f", "%{file}"], capture_output=True, text=True)
        font_path = result.stdout.strip()
    font_sha256 = ""
    if font_path and Path(font_path).is_file():
        font_sha256 = sha256_file(Path(font_path))
    fingerprint = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pillow": str(pillow_version),
        "numpy": str(numpy.__version__),
        "python_pptx": str(pptx_version),
        "librsvg": command_version("rsvg-convert", ["--version"]),
        "libreoffice": command_version("soffice", ["--version"]),
        "poppler": command_version("pdftoppm", ["-v"]),
        "font": {"requested": "Arial", "path": font_path, "sha256": font_sha256},
        "commands": {
            "svg": {"executable": "rsvg-convert", "args": ["-w", "<width>", "-h", "<height>", "-o", "<output>", "<input>"]},
            "pptx_to_pdf": {"executable": "soffice", "args": ["<profile>", "--headless", "--nologo", "--nodefault", "--nofirststartwizard", "--convert-to", "pdf", "--outdir", "<temp>", "<input.pptx>"]},
            "pdf_to_png": {"executable": "pdftoppm", "args": ["-png", "-r", "144", "<input.pdf>", "<prefix>"]},
        },
    }
    _RENDERER_FINGERPRINT_CACHE = copy.deepcopy(fingerprint)
    return fingerprint


def _safe_visual_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "visual"


def _crop_image(image: Any, bbox: dict[str, Any], output: Path) -> Path:
    from PIL import Image

    minimum_size = float(VISUAL_QUALITY_POLICY["crop"]["minimum_object_size_px"])
    if float(bbox.get("w") or 0) < minimum_size or float(bbox.get("h") or 0) < minimum_size:
        raise VisualMetricsError("visual registry object is smaller than 8x8px")
    padding = max(4.0, max(float(bbox.get("w") or 0), float(bbox.get("h") or 0)) * 0.12)
    left = max(0, int(math.floor(float(bbox.get("x") or 0) - padding)))
    top = max(0, int(math.floor(float(bbox.get("y") or 0) - padding)))
    right = min(CANVAS_WIDTH, int(math.ceil(float(bbox.get("x") or 0) + float(bbox.get("w") or 0) + padding)))
    bottom = min(CANVAS_HEIGHT, int(math.ceil(float(bbox.get("y") or 0) + float(bbox.get("h") or 0) + padding)))
    tiny = min(float(bbox.get("w") or 0), float(bbox.get("h") or 0)) < 16.0
    size = int(VISUAL_QUALITY_POLICY["crop"]["tiny_size_px"] if tiny else VISUAL_QUALITY_POLICY["crop"]["size_px"])
    cropped = image.crop((left, top, right, bottom)).resize((size, size), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output, format="PNG")
    return output


def _silhouette_iou(reference: Any, candidate: Any) -> float:
    import numpy as np

    first = np.asarray(reference.convert("RGB"), dtype=np.int16)
    second = np.asarray(candidate.convert("RGB"), dtype=np.int16)
    # Ignore low-amplitude antialiasing halos. The crop still records the
    # original hashes, while the metric evaluates the stable foreground.
    threshold = int(VISUAL_QUALITY_POLICY["renderer_tolerance"]["silhouette_luma_threshold"])
    first_mask = np.any(first < threshold, axis=2)
    second_mask = np.any(second < threshold, axis=2)
    union = int((first_mask | second_mask).sum())
    return 1.0 if union == 0 else float((first_mask & second_mask).sum()) / union


def _shift_crop(image: Any, dx: int, dy: int) -> Any:
    from PIL import Image

    width, height = image.size
    shifted = Image.new("RGB", (width, height), image.getpixel((0, 0)))
    source_left, source_top = max(0, -dx), max(0, -dy)
    source_right, source_bottom = min(width, width - dx), min(height, height - dy)
    target_left, target_top = max(0, dx), max(0, dy)
    if source_right > source_left and source_bottom > source_top:
        shifted.paste(image.crop((source_left, source_top, source_right, source_bottom)), (target_left, target_top))
    return shifted


def _best_local_alignment(reference: Any, candidate: Any, radius: int | None = None) -> tuple[Any, int, int]:
    if radius is None:
        radius = int(VISUAL_QUALITY_POLICY["renderer_tolerance"]["alignment_radius_px"])
    best = (float("-inf"), candidate, 0, 0)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = _shift_crop(candidate, dx, dy)
            score = _ssim(reference, shifted)
            if score > best[0] or (score == best[0] and abs(dx) + abs(dy) < abs(best[2]) + abs(best[3])):
                best = (score, shifted, dx, dy)
    return best[1], best[2], best[3]


def _local_edge_f1(reference: Any, candidate: Any) -> float:
    import numpy as np
    from PIL import Image, ImageFilter

    def edge_map(image: Any) -> Any:
        values = np.asarray(image.convert("L"), dtype=np.int16)
        edges = np.zeros_like(values, dtype=bool)
        edges[:, 1:] |= np.abs(values[:, 1:] - values[:, :-1]) > 2
        edges[1:, :] |= np.abs(values[1:, :] - values[:-1, :]) > 2
        kernel = int(VISUAL_QUALITY_POLICY["renderer_tolerance"]["edge_dilation_kernel"])
        if kernel % 2 == 0:
            kernel += 1
        return np.asarray(Image.fromarray((edges * 255).astype("uint8")).filter(ImageFilter.MaxFilter(kernel))) > 0

    first_edges = edge_map(reference)
    second_edges = edge_map(candidate)
    denominator = int(first_edges.sum()) + int(second_edges.sum())
    return 1.0 if denominator == 0 else 2.0 * float((first_edges & second_edges).sum()) / denominator


def _visual_registry_bboxes(scene: dict[str, Any], svg_file: Path) -> dict[str, dict[str, Any]]:
    from .svg_native import SvgNativeError, parse_svg_native

    try:
        document = ElementTree.fromstring(svg_file.read_text(encoding="utf-8"))
        native = parse_svg_native(document)
    except (OSError, ElementTree.ParseError, SvgNativeError) as exc:
        raise VisualMetricsError(f"cannot inspect visual registry geometry: {svg_file}") from exc
    by_group: dict[str, dict[str, float]] = {}
    for group_id, group in (native.get("groups") or {}).items():
        children = [item for item in native.get("elements") or [] if str(item.get("element_id") or "") in set(group.get("child_ids") or [])]
        if children:
            left = min(float(item["bbox"]["x"]) for item in children)
            top = min(float(item["bbox"]["y"]) for item in children)
            right = max(float(item["bbox"]["x"]) + float(item["bbox"]["w"]) for item in children)
            bottom = max(float(item["bbox"]["y"]) + float(item["bbox"]["h"]) for item in children)
            by_group[str(group_id)] = {"x": left, "y": top, "w": right - left, "h": bottom - top}
    return {str(item.get("visual_id") or ""): {"blueprint": item.get("blueprint_bbox") or {}, "svg": by_group.get(str(item.get("svg_group_id") or item.get("visual_id") or "")), "registry": item} for item in scene.get("visual_registry") or [] if item.get("visual_id")}


def _object_checks(root: Path, scene: dict[str, Any], reference: Any, candidate: Any, *, reference_path: Path, candidate_path: Path, comparison: str, candidate_geometry: dict[str, dict[str, float]] | None) -> list[dict[str, Any]]:
    registries = list(scene.get("visual_registry") or [])
    if not registries:
        return []
    from PIL import Image, ImageFilter

    page_id = str(scene.get("page_id") or "page")
    geometry = _visual_registry_bboxes(scene, root / "high_density_build" / "svg" / f"{page_id}.svg")
    checks: list[dict[str, Any]] = []
    blueprint_path = root / "high_density_build" / "blueprints" / f"{page_id}.normalized.png"
    if not blueprint_path.exists() and comparison == "blueprint_vs_svg":
        blueprint_path = reference_path
    if comparison == "svg_vs_pptx" and not blueprint_path.exists():
        raise VisualMetricsError(f"normalized blueprint is required for local visual checks on page {page_id}")
    for visual in registries:
        visual_id = str(visual.get("visual_id") or "")
        entry = geometry.get(visual_id) or {"blueprint": visual.get("blueprint_bbox") or {}, "svg": None, "registry": visual}
        blueprint_bbox = entry.get("blueprint") or {}
        svg_bbox = entry.get("svg")
        if comparison == "svg_vs_pptx":
            source_bbox = svg_bbox or blueprint_bbox
            group_id = str((entry.get("registry") or {}).get("svg_group_id") or visual_id)
            target_bbox = (candidate_geometry or {}).get(group_id) or (candidate_geometry or {}).get(visual_id)
            svg_image = reference
            target_image = candidate
        else:
            source_bbox = blueprint_bbox
            target_bbox = svg_bbox
            svg_image = candidate
            target_image = candidate
        object_dir = root / "high_density_build" / "comparisons" / page_id / "objects"
        prefix = _safe_visual_filename(visual_id)
        if blueprint_path and blueprint_path.exists():
            blueprint_image = _load_image(blueprint_path)
        else:
            blueprint_image = reference if comparison == "blueprint_vs_svg" else None
        source_crop = _crop_image(blueprint_image, blueprint_bbox, object_dir / f"{prefix}.blueprint.png") if blueprint_image is not None else object_dir / f"{prefix}.blueprint.png"
        if comparison == "svg_vs_pptx":
            svg_crop = _crop_image(svg_image, source_bbox, object_dir / f"{prefix}.svg.png")
            pptx_crop_path = object_dir / f"{prefix}.pptx.png"
            if target_bbox:
                pptx_crop = _crop_image(target_image, target_bbox, pptx_crop_path)
            else:
                Image.new("RGB", (256, 256), "white").save(pptx_crop_path, format="PNG")
                pptx_crop = pptx_crop_path
            comparison_source = svg_crop
            comparison_target = pptx_crop
        else:
            svg_crop = _crop_image(svg_image, target_bbox or blueprint_bbox, object_dir / f"{prefix}.svg.png")
            pptx_crop = None
            comparison_source = source_crop
            comparison_target = svg_crop
        if target_bbox is None:
            values = {"ssim": 0.0, "edge_f1": 0.0, "silhouette_iou": 0.0, "color_delta": 1.0, "bbox_delta_px": 999.0, "occupancy_delta": 1.0, "alignment_dx_px": 0, "alignment_dy_px": 0}
            status = "failed"
            finding = {"code": "missing_visual_registry_object", "visual_id": visual_id}
        else:
            source_image = Image.open(comparison_source).convert("RGB")
            comparison_image = Image.open(comparison_target).convert("RGB")
            # SVG and LibreOffice use different antialiasing kernels. Keep
            # the raw crop hashes above, but compare a policy-controlled
            # low-radius image for local stability metrics. Geometry,
            # occupancy, silhouette and semantic registry checks remain
            # independent gates.
            local_blur = float(VISUAL_QUALITY_POLICY["renderer_tolerance"].get("local_match_blur_radius_px") or 0.0)
            if local_blur > 0:
                source_image = source_image.filter(ImageFilter.GaussianBlur(radius=local_blur))
                comparison_image = comparison_image.filter(ImageFilter.GaussianBlur(radius=local_blur))
            comparison_image, alignment_dx, alignment_dy = _best_local_alignment(source_image, comparison_image)
            bbox_delta = max(abs(float(source_bbox.get(key) or 0) - float(target_bbox.get(key) or 0)) for key in ("x", "y", "w", "h"))
            import numpy as np

            first_mask = np.any(np.asarray(source_image) < 245, axis=2)
            second_mask = np.any(np.asarray(comparison_image) < 245, axis=2)
            occupancy_delta = abs(float(first_mask.mean()) - float(second_mask.mean()))
            values = {
                "ssim": _ssim(source_image, comparison_image),
                "edge_f1": _local_edge_f1(source_image, comparison_image),
                "silhouette_iou": _silhouette_iou(source_image, comparison_image),
                "color_delta": _color_delta(source_image, comparison_image),
                "bbox_delta_px": bbox_delta,
                "occupancy_delta": occupancy_delta,
                "alignment_dx_px": abs(alignment_dx),
                "alignment_dy_px": abs(alignment_dy),
            }
            policy_thresholds = VISUAL_QUALITY_POLICY[comparison]
            thresholds = {
                "ssim": float(policy_thresholds["ssim_min"]),
                "edge_f1": float(policy_thresholds["edge_f1_min"]),
                "silhouette_iou": float(policy_thresholds["silhouette_iou_min"]),
                "color_delta": float(policy_thresholds["color_delta_max"]),
                "bbox_delta_px": float(policy_thresholds["bbox_delta_px_max"]),
                "occupancy_delta": float(policy_thresholds["occupancy_delta_max"]),
            }
            failing = [key for key, limit in thresholds.items() if (values[key] < limit if key in {"ssim", "edge_f1", "silhouette_iou"} else values[key] > limit)]
            status = "pass" if not failing else "failed"
            finding = {"code": "visual_object_threshold_failed", "visual_id": visual_id, "metrics": failing} if failing else {}
        check = {
            "visual_id": visual_id,
            "visual_type": str(visual.get("visual_type") or "complex_visual"),
            "priority": str(visual.get("priority") or "P2"),
            "source_crop_path": run_relative(root, source_crop) if source_crop.exists() else run_relative(root, svg_crop),
            "source_crop_sha256": sha256_file(source_crop if source_crop.exists() else svg_crop),
            "svg_crop_path": run_relative(root, svg_crop),
            "svg_crop_sha256": sha256_file(svg_crop),
            "pptx_crop_path": run_relative(root, pptx_crop) if pptx_crop else "",
            "pptx_crop_sha256": sha256_file(pptx_crop) if pptx_crop else "",
            "bbox": dict(blueprint_bbox),
            "values": values,
            "status": status,
        }
        if finding:
            check["finding"] = finding
        checks.append(check)
    return checks


def compute_visual_metrics(
    root: Path,
    scene: dict[str, Any],
    blueprint_preview: Path,
    svg_preview: Path,
    *,
    comparison: str = "blueprint_vs_svg",
    thresholds: dict[str, float] | None = None,
    candidate_geometry: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        raise VisualMetricsError("NumPy is required for visual metrics") from exc
    reference = _load_image(blueprint_preview)
    candidate = _load_image(svg_preview)
    page_id = str(scene["page_id"])
    svg_file = root / "high_density_build" / "svg" / f"{page_id}.svg"
    mask = _text_mask(svg_file, page_id)
    import numpy as np

    ref_array = np.asarray(reference)
    candidate_array = np.asarray(candidate)
    policy = {"text_masked_ssim": 0.92, "p0_region_ssim": 0.92, "bbox_max_delta_px": 2.0, "color_delta": 0.25, "edge_similarity": 0.15, "p0_p1_text_contrast_ratio": 3.0}
    try:
        run_mode = str(read_json(root / "request.json").get("run_mode") or "production").strip().lower()
    except ContractError:
        run_mode = "production"
    if comparison == "svg_vs_pptx":
        policy.update({"text_masked_ssim": 0.97, "bbox_max_delta_px": 1.0, "edge_similarity": 0.45})
    if run_mode in {"fixture", "dev"}:
        # Synthetic fixtures exercise compiler contracts, not provider-image
        # fidelity. Keep their structural gates while avoiding false failures
        # from the deliberately generic fixture composition.
        policy["p0_region_ssim"] = 0.80
        if comparison == "svg_vs_pptx":
            policy["edge_similarity"] = 0.25
    if thresholds:
        policy.update({str(key): float(value) for key, value in thresholds.items()})
    geometry_elements = {str(element.get("element_id") or "") for element in scene.get("elements", []) if element.get("priority") in {"P0", "P1"}}
    svg_geometry = _svg_element_bboxes(svg_file, page_id, geometry_elements)
    bbox_deltas: list[float] = []
    geometry_pairs: list[dict[str, Any]] = []
    for element in scene.get("elements", []):
        if element.get("priority") not in {"P0", "P1"}:
            continue
        element_id = str(element.get("element_id") or "")
        if comparison == "svg_vs_pptx":
            source = svg_geometry[element_id]
            target = (candidate_geometry or {}).get(element_id)
            if target is None:
                raise VisualMetricsError(f"PPTX geometry is missing for {element_id}")
        else:
            source = element.get("source_blueprint_bbox") or element.get("bbox") or {}
            target = svg_geometry[element_id]
        deltas = {key: abs(float(source.get(key) or 0) - float(target.get(key) or 0)) for key in ("x", "y", "w", "h")}
        bbox_deltas.extend(deltas.values())
        geometry_pairs.append({"element_id": element_id, "source": source, "target": target, "delta": deltas})
    required_components = {str(value) for value in scene.get("required_component_ids") or []}
    present_components = _svg_component_ids(root, str(scene["page_id"]))
    missing_components = sorted(required_components - present_components)
    # Text contrast is a native-SVG content gate.  Re-rendering it against a
    # LibreOffice candidate would measure office anti-aliasing and font
    # substitution rather than whether the approved SVG text is visible.
    text_contrast = _text_contrast_metrics(svg_file, scene)
    # ImageGen blueprints contain provider-rendered glyphs that are replaced
    # by locked native text during redraw. The source-to-SVG gate uses a
    # slightly wider low-frequency pass for sub-cell vectorization noise;
    # SVG-to-PPTX keeps the stricter 3px pass. Raw edges, color, geometry, and
    # text gates continue to catch real redraw drift.
    from PIL import ImageFilter

    ssim_blur_radius = 3.2 if comparison == "blueprint_vs_svg" else 3.0
    ssim_reference = reference.filter(ImageFilter.GaussianBlur(radius=ssim_blur_radius))
    ssim_candidate = candidate.filter(ImageFilter.GaussianBlur(radius=ssim_blur_radius))
    ssim = _ssim(ssim_reference, ssim_candidate, mask)
    p0_regions = [svg_geometry[str(element.get("element_id") or "")] for element in scene.get("elements", []) if element.get("priority") == "P0"]
    p0_region_scores = [_region_ssim(ssim_reference, ssim_candidate, mask, bbox) for bbox in p0_regions]
    p0_region_ssim = min(p0_region_scores) if p0_region_scores else ssim
    color_delta = _color_delta(ref_array, candidate_array, mask)
    edge_similarity = _edge_similarity(reference, candidate, mask)
    anchor_max_delta = max((max(pair["delta"]["x"], pair["delta"]["y"]) for pair in geometry_pairs), default=0.0)
    direction_mismatches = sum(
        1
        for pair in geometry_pairs
        if (float(pair["source"].get("w") or 0) >= float(pair["source"].get("h") or 0))
        != (float(pair["target"].get("w") or 0) >= float(pair["target"].get("h") or 0))
    )
    overflow_count = sum(1 for bbox in svg_geometry.values() if bbox["x"] < 0 or bbox["y"] < 0 or bbox["x"] + bbox["w"] > CANVAS_WIDTH or bbox["y"] + bbox["h"] > CANVAS_HEIGHT)
    text_boxes = [svg_geometry[str(element.get("element_id") or "")] for element in scene.get("elements", []) if element.get("kind") == "text" and element.get("priority") in {"P0", "P1"}]
    illegal_overlap_count = sum(1 for index, first in enumerate(text_boxes) for second in text_boxes[index + 1 :] if _overlap_area(first, second) > 1)
    mask_coverage = float(mask.mean())
    object_checks = _object_checks(
        root,
        scene,
        reference,
        candidate,
        reference_path=blueprint_preview,
        candidate_path=svg_preview,
        comparison=comparison,
        candidate_geometry=candidate_geometry,
    )
    findings: list[dict[str, Any]] = []
    if ssim < policy["text_masked_ssim"]:
        findings.append({"code": "visual_ssim_below_threshold", "value": ssim, "threshold": policy["text_masked_ssim"]})
    if p0_region_ssim < policy["p0_region_ssim"]:
        findings.append({"code": "p0_region_ssim_below_threshold", "value": p0_region_ssim, "threshold": policy["p0_region_ssim"]})
    if bbox_deltas and max(bbox_deltas) > policy["bbox_max_delta_px"]:
        findings.append({"code": "p0_p1_bbox_drift", "value": max(bbox_deltas), "threshold": policy["bbox_max_delta_px"]})
    if missing_components:
        findings.append({"code": "missing_components", "component_ids": missing_components})
    if color_delta > policy["color_delta"]:
        findings.append({"code": "region_color_delta", "value": color_delta, "threshold": policy["color_delta"]})
    if edge_similarity < policy["edge_similarity"]:
        findings.append({"code": "edge_similarity_below_threshold", "value": edge_similarity, "threshold": policy["edge_similarity"]})
    if overflow_count:
        findings.append({"code": "visual_overflow", "count": overflow_count})
    if illegal_overlap_count:
        findings.append({"code": "illegal_text_overlap", "count": illegal_overlap_count})
    if direction_mismatches:
        findings.append({"code": "direction_mismatch", "count": direction_mismatches})
    low_contrast = [element_id for element_id, value in text_contrast["elements"].items() if float(value["contrast_ratio"]) < policy["p0_p1_text_contrast_ratio"]]
    if low_contrast:
        findings.append(
            {
                "code": "p0_p1_text_contrast_below_threshold",
                "element_ids": low_contrast,
                "value": text_contrast["minimum_ratio"],
                "threshold": policy["p0_p1_text_contrast_ratio"],
            }
        )
    failed_objects = [item for item in object_checks if item.get("status") != "pass"]
    if failed_objects:
        findings.append({"code": "visual_object_checks_failed", "visual_ids": [str(item.get("visual_id") or "") for item in failed_objects]})
    toolchain = renderer_fingerprint()
    metrics = {
        "schema_version": "deck_visual_metrics.v1",
        "run_id": str(scene["run_id"]),
        "page_id": str(scene["page_id"]),
        "comparison": {"kind": comparison, "renderer": f"rsvg-convert + Pillow + NumPy; SSIM uses {ssim_blur_radius:g}px Gaussian blur", "toolchain": toolchain, "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "unit": "px"}},
        "inputs": {"reference_path": run_relative(root, blueprint_preview), "reference_sha256": sha256_file(blueprint_preview), "candidate_path": run_relative(root, svg_preview), "candidate_sha256": sha256_file(svg_preview), "mask_sha256": sha256_json(mask.astype(bool).tolist()), "mask_coverage": mask_coverage, "svg_geometry_sha256": sha256_json(svg_geometry), "candidate_geometry_sha256": sha256_json(candidate_geometry) if candidate_geometry is not None else ""},
        "policy": {"version": VISUAL_QUALITY_POLICY["version"], "sha256": VISUAL_QUALITY_POLICY_SHA256, "object": VISUAL_QUALITY_POLICY[comparison], "renderer_tolerance": VISUAL_QUALITY_POLICY["renderer_tolerance"]},
        "thresholds": policy,
        "values": {"text_masked_ssim": ssim, "p0_region_ssim": p0_region_ssim, "bbox_max_delta_px": max(bbox_deltas) if bbox_deltas else 0.0, "anchor_max_delta_px": anchor_max_delta, "region_color_delta": color_delta, "edge_similarity": edge_similarity, "p0_p1_min_text_contrast_ratio": text_contrast["minimum_ratio"], "mask_coverage": mask_coverage, "overflow_count": overflow_count, "illegal_overlap_count": illegal_overlap_count, "direction_mismatch_count": direction_mismatches},
        "geometry": {"source": "svg_dom_geometry" if comparison == "svg_vs_pptx" else "scene_blueprint_bbox", "target": "pptx_readback_geometry" if comparison == "svg_vs_pptx" else "svg_dom_geometry", "pairs": geometry_pairs},
        "coverage": {"required_components": len(required_components), "present_components": len(required_components - set(missing_components)), "component_coverage": 1.0 if not missing_components else (len(required_components) - len(missing_components)) / max(1, len(required_components)), "p0_p1_bbox_coverage": 1.0 if not bbox_deltas or max(bbox_deltas) <= policy["bbox_max_delta_px"] else 0.0, "p0_p1_text_contrast": text_contrast["elements"], "visual_registry_coverage": 1.0 if not object_checks else sum(1 for item in object_checks if item.get("status") == "pass") / len(object_checks)},
        "object_checks": object_checks,
        "findings": findings,
        "status": "pass" if not findings else "failed",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    return metrics


def write_visual_metrics(root: Path, scene: dict[str, Any], metrics: dict[str, Any], *, comparison: str | None = None) -> Path:
    suffix = ""
    if comparison:
        safe_comparison = comparison.replace("/", "_").replace(" ", "_")
        suffix = f".{safe_comparison}"
    path = root / "high_density_build" / "reviews" / f"{scene['page_id']}{suffix}.metrics.json"
    write_json(path, metrics)
    return path


__all__ = ["VisualMetricsError", "compute_visual_metrics", "normalize_blueprint", "write_visual_metrics"]
