from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .blueprint import CANVAS_HEIGHT, CANVAS_WIDTH, image_dimensions
from .contracts import ContractError, read_json, sha256_file, sha256_json, write_json


class VisualMetricsError(ContractError):
    pass


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
    try:
        document = ElementTree.fromstring(root.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        raise VisualMetricsError(f"cannot inspect SVG geometry: {root}") from exc
    nodes = {str(node.get("id")): node for node in document.iter() if node.get("id")}
    missing = sorted(element_ids - set(nodes))
    if missing:
        raise VisualMetricsError(f"SVG is missing geometry for page {page_id}: {', '.join(missing)}")
    return {element_id: _svg_geometry_bbox(nodes[element_id]) for element_id in sorted(element_ids)}


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
    from PIL import Image

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
        if int(valid.sum()) < 100:
            return 1.0
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


def _text_mask(scene: dict[str, Any]):
    import numpy as np

    mask = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)
    for element in scene.get("elements", []):
        if element.get("kind") != "text":
            continue
        bbox = element.get("bbox") or {}
        x, y = max(0, int(float(bbox.get("x") or 0))), max(0, int(float(bbox.get("y") or 0)))
        w, h = max(0, int(float(bbox.get("w") or 0))), max(0, int(float(bbox.get("h") or 0)))
        mask[y : min(CANVAS_HEIGHT, y + h), x : min(CANVAS_WIDTH, x + w)] = True
    return mask


def _color_delta(reference, candidate, mask=None) -> float:
    import numpy as np

    a = np.asarray(reference, dtype=np.float64)
    b = np.asarray(candidate, dtype=np.float64)
    if mask is not None:
        valid = ~mask
        if int(valid.sum()) < 100:
            return 0.0
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
    mask = _text_mask(scene)
    import numpy as np

    ref_array = np.asarray(reference)
    candidate_array = np.asarray(candidate)
    policy = {"text_masked_ssim": 0.92, "p0_region_ssim": 0.92, "bbox_max_delta_px": 2.0, "color_delta": 0.25}
    if comparison == "svg_vs_pptx":
        policy.update({"text_masked_ssim": 0.97, "bbox_max_delta_px": 1.0})
    if thresholds:
        policy.update({str(key): float(value) for key, value in thresholds.items()})
    page_id = str(scene["page_id"])
    geometry_elements = {str(element.get("element_id") or "") for element in scene.get("elements", []) if element.get("priority") in {"P0", "P1"}}
    svg_file = root / "high_density_build" / "svg" / f"{page_id}.svg"
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
    ssim = _ssim(reference, candidate, mask)
    p0_regions = [element.get("bbox") or {} for element in scene.get("elements", []) if element.get("priority") == "P0"]
    p0_region_scores = [_region_ssim(reference, candidate, mask, bbox) for bbox in p0_regions]
    p0_region_ssim = min(p0_region_scores) if p0_region_scores else ssim
    color_delta = _color_delta(ref_array, candidate_array, mask)
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
    metrics = {
        "schema_version": "deck_visual_metrics.v1",
        "run_id": str(scene["run_id"]),
        "page_id": str(scene["page_id"]),
        "comparison": {"kind": comparison, "renderer": "rsvg-convert + Pillow + NumPy", "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "unit": "px"}},
        "inputs": {"reference_path": str(blueprint_preview), "reference_sha256": sha256_file(blueprint_preview), "candidate_path": str(svg_preview), "candidate_sha256": sha256_file(svg_preview), "mask_sha256": sha256_json(mask.astype(bool).tolist()), "svg_geometry_sha256": sha256_json(svg_geometry), "candidate_geometry_sha256": sha256_json(candidate_geometry) if candidate_geometry is not None else ""},
        "thresholds": policy,
        "values": {"text_masked_ssim": ssim, "p0_region_ssim": p0_region_ssim, "bbox_max_delta_px": max(bbox_deltas) if bbox_deltas else 0.0, "region_color_delta": color_delta},
        "geometry": {"source": "svg_dom_geometry" if comparison == "svg_vs_pptx" else "scene_blueprint_bbox", "target": "pptx_readback_geometry" if comparison == "svg_vs_pptx" else "svg_dom_geometry", "pairs": geometry_pairs},
        "coverage": {"required_components": len(required_components), "present_components": len(required_components - set(missing_components)), "component_coverage": 1.0 if not missing_components else (len(required_components) - len(missing_components)) / max(1, len(required_components)), "p0_p1_bbox_coverage": 1.0 if not bbox_deltas or max(bbox_deltas) <= policy["bbox_max_delta_px"] else 0.0},
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
