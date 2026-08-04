from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_valid, read_json, run_relative, sha256_file, sha256_json, utc_now, write_json

BLUEPRINT_DIR = Path("high_density_build/blueprints")
BLUEPRINT_MANIFEST_DIR = Path("high_density_build/blueprints")
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
CANVAS_RATIO = CANVAS_WIDTH / CANVAS_HEIGHT


class BlueprintRequired(ContractError):
    def __init__(self, page_id: str, lock_ref: str) -> None:
        self.page_id = page_id
        self.lock_ref = lock_ref
        super().__init__(f"blueprint image required for page {page_id}")


class BlueprintInvalid(ContractError):
    pass


def blueprint_path(root: Path, page_id: str) -> Path | None:
    directory = root / BLUEPRINT_DIR
    for extension in SUPPORTED_EXTENSIONS:
        candidate = directory / f"{page_id}{extension}"
        if candidate.exists():
            return candidate
    return None


def blueprint_manifest_path(root: Path, page_id: str) -> Path:
    return root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    head = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    viewbox = re.search(r"viewBox\s*=\s*[\"']\s*[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", head)
    if viewbox:
        return round(float(viewbox.group(1))), round(float(viewbox.group(2)))
    width = re.search(r"width\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    height = re.search(r"height\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    if width and height:
        return round(float(width.group(1))), round(float(height.group(1)))
    return None


def image_dimensions(path: Path) -> tuple[int, int]:
    dimensions = _png_dimensions(path) if path.suffix.lower() == ".png" else None
    if dimensions is None and path.suffix.lower() == ".svg":
        dimensions = _svg_dimensions(path)
    if dimensions is None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                dimensions = image.size
        except Exception as exc:  # pragma: no cover - optional format/provider path
            raise BlueprintInvalid(f"cannot read blueprint dimensions: {path}") from exc
    if dimensions[0] <= 0 or dimensions[1] <= 0:
        raise BlueprintInvalid(f"blueprint dimensions must be positive: {path}")
    return dimensions


def build_blueprint_prompt(lock: dict[str, Any], style_lock: dict[str, Any] | None = None) -> str:
    analysis = lock.get("enrichment", {}).get("analysis", {})
    page_role = analysis.get("page_role", "dense_narrative")
    density = analysis.get("density_band", "high")
    style = style_lock or {
        "palette": "ink, cobalt, copper, mint",
        "typography": "clean sans-serif with strong hierarchy",
        "canvas": "16:9",
    }
    return "\n".join(
        [
            "Create a high-density consulting presentation slide blueprint.",
            f"Page role: {page_role}. Density band: {density}.",
            f"Visual system: {style}.",
            "Use a clear 16:9 slide frame and preserve a readable safe area.",
            "Maximize useful information density with aligned regions, explicit hierarchy, and varied visual structure.",
            "Do not draw page numbers, generation annotations, internal labels, placeholder comments, or hidden production notes.",
            "Treat all visible text in the reference content as layout guidance only; the native redraw will restore locked text.",
            "Prefer native-feeling cards, connectors, tables, diagrams, and legible labels over decorative empty space.",
        ]
    )


def _default_slide_frame(width: int, height: int) -> dict[str, float]:
    ratio = width / height
    if abs(ratio - CANVAS_RATIO) <= 0.02:
        return {"x": 0, "y": 0, "w": width, "h": height}
    if ratio > CANVAS_RATIO:
        frame_height = width / CANVAS_RATIO
        return {"x": 0, "y": (height - frame_height) / 2, "w": width, "h": frame_height}
    frame_width = height * CANVAS_RATIO
    return {"x": (width - frame_width) / 2, "y": 0, "w": frame_width, "h": height}


def ensure_blueprint_manifest(root: Path, page_id: str, lock: dict[str, Any], *, style_lock: dict[str, Any] | None = None) -> Path:
    image = blueprint_path(root, page_id)
    if image is None:
        raise BlueprintRequired(page_id, f"high_density_build/content_locks/{page_id}.json")
    dimensions = image_dimensions(image)
    manifest_path = blueprint_manifest_path(root, page_id)
    prompt = build_blueprint_prompt(lock, style_lock)
    existing = read_json(manifest_path) if manifest_path.exists() else {}
    expected_prompt_sha = sha256_json(prompt)
    if existing and existing.get("prompt_sha256") and str(existing["prompt_sha256"]) != expected_prompt_sha:
        raise BlueprintInvalid(f"blueprint prompt is stale on page {page_id}")
    slide_frame = existing.get("slide_frame") or _default_slide_frame(*dimensions)
    try:
        frame_x = float(slide_frame["x"])
        frame_y = float(slide_frame["y"])
        frame_width = float(slide_frame["w"])
        frame_height = float(slide_frame["h"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BlueprintInvalid(f"blueprint slide_frame is invalid on page {page_id}") from exc
    frame_ratio = frame_width / frame_height if frame_height else 0.0
    if abs(frame_ratio - CANVAS_RATIO) > 0.02:
        raise BlueprintInvalid(f"approved slide_frame ratio drifts from 16:9 on page {page_id}")
    if (
        frame_x < 0
        or frame_y < 0
        or frame_width <= 0
        or frame_height <= 0
        or frame_x + frame_width > dimensions[0] + 0.01
        or frame_y + frame_height > dimensions[1] + 0.01
    ):
        raise BlueprintInvalid(f"blueprint slide_frame is outside the source canvas on page {page_id}")
    manifest = {
        "schema_version": "deck_blueprint_manifest.v1",
        "run_id": lock["run_id"],
        "page_id": page_id,
        "image_path": run_relative(root, image),
        "image_sha256": sha256_file(image),
        "prompt_sha256": expected_prompt_sha,
        "source_canvas": {"width": dimensions[0], "height": dimensions[1], "unit": "px"},
        "slide_frame": slide_frame,
        "fit_mode": "approved_frame" if existing.get("slide_frame") else "contain",
        "internal_annotations": [],
        "approved": bool(existing.get("approved", False)) or image.suffix.lower() == ".svg",
        "created_at": str(existing.get("created_at") or utc_now()),
    }
    if manifest["internal_annotations"]:
        raise BlueprintInvalid(f"blueprint contains internal annotations on page {page_id}")
    assert_valid("blueprint_manifest", manifest)
    write_json(manifest_path, manifest)
    return manifest_path


def load_blueprint_manifest(root: Path, page_id: str) -> dict[str, Any]:
    path = blueprint_manifest_path(root, page_id)
    manifest = read_json(path)
    assert_valid("blueprint_manifest", manifest)
    if str(manifest.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint manifest page_id mismatch on page {page_id}")
    image = safe_image_path(root, str(manifest.get("image_path") or ""))
    expected_image = blueprint_path(root, page_id)
    if expected_image is None or image.resolve() != expected_image.resolve():
        raise BlueprintInvalid(f"blueprint manifest image_path mismatch on page {page_id}")
    dimensions = image_dimensions(image)
    source_canvas = manifest.get("source_canvas") or {}
    if (float(source_canvas.get("width") or 0), float(source_canvas.get("height") or 0)) != dimensions:
        raise BlueprintInvalid(f"blueprint source canvas is stale on page {page_id}")
    if str(manifest.get("image_sha256") or "") != sha256_file(image):
        raise BlueprintInvalid(f"blueprint hash is stale on page {page_id}")
    if not manifest.get("approved"):
        raise BlueprintInvalid(f"blueprint has not been approved on page {page_id}")
    return manifest


def safe_image_path(root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise BlueprintInvalid(f"blueprint path must be run-relative: {value}")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise BlueprintInvalid(f"blueprint path escapes run directory: {value}") from exc
    if not path.exists() or not path.is_file():
        raise BlueprintInvalid(f"blueprint image missing: {value}")
    return path


__all__ = [
    "BLUEPRINT_DIR",
    "BlueprintInvalid",
    "BlueprintRequired",
    "build_blueprint_prompt",
    "blueprint_manifest_path",
    "blueprint_path",
    "ensure_blueprint_manifest",
    "image_dimensions",
    "load_blueprint_manifest",
]
