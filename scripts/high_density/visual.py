from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .blueprint import CANVAS_HEIGHT, CANVAS_WIDTH, image_dimensions
from .contracts import ContractError, read_json, sha256_file, sha256_json, write_json


class VisualMetricsError(ContractError):
    pass


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
    bbox_deltas: list[float] = []
    for element in scene.get("elements", []):
        if element.get("priority") not in {"P0", "P1"}:
            continue
        source = element.get("source_blueprint_bbox") or element.get("bbox") or {}
        target = element.get("target_svg_bbox") or element.get("bbox") or {}
        for key in ("x", "y", "w", "h"):
            bbox_deltas.append(abs(float(source.get(key) or 0) - float(target.get(key) or 0)))
    required_components = {str(value) for value in scene.get("required_component_ids") or []}
    present_components = _svg_component_ids(root, str(scene["page_id"]))
    if not present_components:
        present_components = {str(element.get("component_id") or "") for element in scene.get("elements", [])}
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
        "inputs": {"reference_path": str(blueprint_preview), "reference_sha256": sha256_file(blueprint_preview), "candidate_path": str(svg_preview), "candidate_sha256": sha256_file(svg_preview), "mask_sha256": sha256_json(mask.astype(bool).tolist())},
        "thresholds": policy,
        "values": {"text_masked_ssim": ssim, "p0_region_ssim": p0_region_ssim, "bbox_max_delta_px": max(bbox_deltas) if bbox_deltas else 0.0, "region_color_delta": color_delta},
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
