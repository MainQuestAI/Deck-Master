from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_v2, read_json, run_relative, sha256_file, sha256_json, utc_now, write_json

BLUEPRINT_DIR = Path("high_density_build/blueprints")
PROMPT_DIR = Path("high_density_build/prompts")
BLUEPRINT_MANIFEST_DIR = BLUEPRINT_DIR
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg")
CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
CANVAS_RATIO = CANVAS_WIDTH / CANVAS_HEIGHT
SAFE_PAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class BlueprintRequired(ContractError):
    def __init__(self, page_id: str, lock_ref: str) -> None:
        self.page_id = page_id
        self.lock_ref = lock_ref
        super().__init__(f"blueprint image required for page {page_id}")


class BlueprintInvalid(ContractError):
    pass


def _assert_page_id(page_id: str) -> None:
    if not SAFE_PAGE_ID.fullmatch(str(page_id or "")) or ".." in str(page_id):
        raise BlueprintInvalid(f"unsafe blueprint page_id: {page_id}")


def blueprint_path(root: Path, page_id: str) -> Path | None:
    _assert_page_id(page_id)
    directory = root / BLUEPRINT_DIR
    for extension in SUPPORTED_EXTENSIONS:
        candidate = directory / f"{page_id}{extension}"
        if candidate.exists():
            return candidate
    return None


def blueprint_manifest_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    canonical = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json"
    legacy = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"
    return canonical if canonical.exists() or not legacy.exists() else legacy


def prompt_path(root: Path, page_id: str) -> Path:
    _assert_page_id(page_id)
    return root / PROMPT_DIR / f"{page_id}.blueprint_prompt.json"


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    head = path.read_text(encoding="utf-8", errors="ignore")[:8192]
    viewbox = re.search(r"viewBox\s*=\s*[\"']\s*[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", head)
    if viewbox:
        return round(float(viewbox.group(1))), round(float(viewbox.group(2)))
    width = re.search(r"width\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    height = re.search(r"height\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    if width and height:
        return round(float(width.group(1))), round(float(height.group(1)))
    return None


def image_dimensions(path: Path) -> tuple[int, int]:
    dimensions = _png_dimensions(path) if path.suffix.lower() == ".png" else _svg_dimensions(path) if path.suffix.lower() == ".svg" else None
    if dimensions is None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                dimensions = image.size
        except Exception as exc:  # pragma: no cover - provider format path
            raise BlueprintInvalid(f"cannot read blueprint dimensions: {path}") from exc
    if dimensions[0] <= 0 or dimensions[1] <= 0:
        raise BlueprintInvalid(f"blueprint dimensions must be positive: {path}")
    return dimensions


def _default_slide_frame(width: int, height: int) -> dict[str, float]:
    ratio = width / height
    if abs(ratio - CANVAS_RATIO) <= 0.02:
        return {"x": 0, "y": 0, "w": width, "h": height}
    if ratio > CANVAS_RATIO:
        frame_height = width / CANVAS_RATIO
        return {"x": 0, "y": (height - frame_height) / 2, "w": width, "h": frame_height}
    frame_width = height * CANVAS_RATIO
    return {"x": (width - frame_width) / 2, "y": 0, "w": frame_width, "h": height}


def _content_summary(lock: dict[str, Any]) -> dict[str, Any]:
    visible = lock.get("customer_visible") or {}
    enrichment = lock.get("enrichment") or {}
    blocks = visible.get("body_blocks") or []
    return {
        "title": str(visible.get("title") or ""),
        "subtitle": str(visible.get("subtitle") or ""),
        "conclusion": str(enrichment.get("conclusion") or ""),
        "so_what": str(enrichment.get("so_what") or ""),
        "body": [json.dumps(block, ensure_ascii=False, sort_keys=True) if isinstance(block, (dict, list)) else str(block) for block in blocks],
        "evidence_ids": [str(item.get("evidence_id") if isinstance(item, dict) else item) for item in lock.get("evidence_bindings") or []],
        "required_components": list(lock.get("required_component_ids") or []),
        "storyline_id": str(enrichment.get("storyline_id") or (lock.get("lineage") or {}).get("selected_storyline_id") or ""),
        "handoff": str(enrichment.get("handoff") or ""),
        "caveat": list(enrichment.get("caveat") or []),
        "material_pool": enrichment.get("material_pool") or {},
        "derived_claims": enrichment.get("derived_claims") or [],
        "target_language": str(lock.get("target_language") or "zh-CN"),
    }


def build_blueprint_prompt(lock: dict[str, Any], style_lock: dict[str, Any] | None = None, *, nbb_plan_sha256: str = "") -> str:
    style = style_lock or {"style_id": "unlocked", "palette": {}, "grid": {}, "typography": {}}
    summary = _content_summary(lock)
    style_name = str(style.get("name") or style.get("style_id") or "locked style")
    return "\n".join(
        [
            "Create a high-density consulting presentation slide blueprint for an editable native redraw.",
            f"Page title: {summary['title']}",
            f"Page conclusion: {summary['conclusion'] or summary['title']}",
            f"Management implication (SO WHAT): {summary['so_what']}",
            f"Selected NBB storyline: {summary['storyline_id'] or 'unavailable'}.",
            f"Supporting content: {' | '.join(summary['body'])}",
            f"Evidence IDs: {', '.join(summary['evidence_ids']) or 'none'}.",
            f"Caveats: {' | '.join(summary['caveat']) or 'none'}.",
            f"Page handoff: {summary['handoff'] or 'unavailable'}.",
            f"Material pool: {json.dumps(summary['material_pool'], ensure_ascii=False, sort_keys=True)}.",
            f"Derived claim lineage: {json.dumps(summary['derived_claims'], ensure_ascii=False, sort_keys=True)}.",
            f"Required visual components: {', '.join(summary['required_components'])}.",
            f"Target language: {summary['target_language']}.",
            f"Locked visual style: {style_name}; palette={json.dumps(style.get('palette') or {}, ensure_ascii=False, sort_keys=True)}; grid={json.dumps(style.get('grid') or {}, ensure_ascii=False, sort_keys=True)}.",
            f"NBB plan lineage: {nbb_plan_sha256 or lock.get('lineage', {}).get('nbb_plan_sha256', 'unavailable')}.",
            "Use a contained 16:9 slide frame with dense but readable information regions, explicit hierarchy, evidence anchors, and a visible SO WHAT area.",
            "Treat all visible text as composition guidance. The native redraw will restore exact locked text from the content lock.",
            "Do not invent facts, numbers, logos, quotes, citations, page numbers, internal labels, prompt labels, wireframe labels, generation annotations, or hidden production notes.",
        ]
    )


def build_blueprint_prompt_artifact(root: Path, page_id: str, lock: dict[str, Any], *, style_lock: dict[str, Any] | None = None, nbb_plan_sha256: str = "") -> Path:
    prompt_text = build_blueprint_prompt(lock, style_lock, nbb_plan_sha256=nbb_plan_sha256)
    style_hash = str((style_lock or {}).get("style_lock_sha256") or "0" * 64)
    artifact = {
        "schema_version": "deck_blueprint_prompt.v1",
        "run_id": str(lock["run_id"]),
        "page_id": str(page_id),
        "prompt_template_version": "cyber-ppt-high-density.v2",
        "prompt_text": prompt_text,
        "prompt_sha256": sha256_json(prompt_text),
        "content_lock_ref": f"high_density_build/content_locks/{page_id}.content_lock.json",
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "nbb_plan_ref": "high_density_build/nbb/nbb_plan.json",
        "nbb_plan_sha256": nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        "style_lock_ref": "high_density_build/style/style_lock.json",
        "style_lock_sha256": style_hash,
        "content_summary": _content_summary(lock),
        "required_components": list(lock.get("required_component_ids") or []),
        "forbidden_items": ["page numbers", "internal labels", "prompt labels", "wireframe labels", "generation annotations", "hidden production notes"],
        "created_at": utc_now(),
    }
    from .contracts import assert_v2

    assert_v2("blueprint_prompt", artifact)
    path = prompt_path(root, page_id)
    write_json(path, artifact)
    return path


def _validate_frame(frame: dict[str, Any], dimensions: tuple[int, int], page_id: str) -> None:
    try:
        x, y, width, height = (float(frame[key]) for key in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError) as exc:
        raise BlueprintInvalid(f"blueprint slide_frame is invalid on page {page_id}") from exc
    if height <= 0 or width <= 0 or abs(width / height - CANVAS_RATIO) > 0.02:
        raise BlueprintInvalid(f"approved slide_frame ratio drifts from 16:9 on page {page_id}")
    if x < 0 or y < 0 or x + width > dimensions[0] + 0.01 or y + height > dimensions[1] + 0.01:
        raise BlueprintInvalid(f"blueprint slide_frame is outside the source canvas on page {page_id}")


def _assert_manifest_mirror_consistent(root: Path, page_id: str, canonical: Path) -> None:
    legacy = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"
    if not canonical.exists() or not legacy.exists():
        return
    try:
        canonical_payload = read_json(canonical)
        legacy_payload = read_json(legacy)
    except ContractError as exc:
        raise BlueprintInvalid(f"blueprint manifest mirror is unreadable on page {page_id}") from exc
    if canonical_payload != legacy_payload:
        raise BlueprintInvalid(f"blueprint manifest mirror is stale on page {page_id}")


def ensure_blueprint_manifest(root: Path, page_id: str, lock: dict[str, Any], *, style_lock: dict[str, Any] | None = None, nbb_plan_sha256: str = "") -> Path:
    _assert_page_id(page_id)
    image = blueprint_path(root, page_id)
    if image is None:
        raise BlueprintRequired(page_id, f"high_density_build/content_locks/{page_id}.content_lock.json")
    prompt_file = prompt_path(root, page_id)
    if not prompt_file.exists():
        raise BlueprintInvalid(f"blueprint prompt must be written before image generation on page {page_id}")
    prompt = read_json(prompt_file)
    assert_v2("blueprint_prompt", prompt)
    expected_nbb_sha = nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64)
    expected_style_sha = str((style_lock or {}).get("style_lock_sha256") or prompt.get("style_lock_sha256") or "0" * 64)
    if str(prompt.get("run_id") or "") != str(lock.get("run_id") or "") or str(prompt.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint prompt identity is stale on page {page_id}")
    if str(prompt.get("nbb_plan_sha256") or "") != expected_nbb_sha or str(prompt.get("style_lock_sha256") or "") != expected_style_sha:
        raise BlueprintInvalid(f"blueprint prompt lineage is stale on page {page_id}")
    expected_prompt = build_blueprint_prompt(lock, style_lock, nbb_plan_sha256=nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64))
    expected_prompt_sha = sha256_json(expected_prompt)
    if prompt.get("prompt_sha256") != expected_prompt_sha or prompt.get("content_lock_sha256") != lock.get("content_lock_sha256"):
        raise BlueprintInvalid(f"blueprint prompt is stale on page {page_id}")
    dimensions = image_dimensions(image)
    manifest_path = blueprint_manifest_path(root, page_id)
    _assert_manifest_mirror_consistent(root, page_id, root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json")
    existing = read_json(manifest_path) if manifest_path.exists() else {}
    if existing and existing.get("schema_version") != "deck_blueprint_manifest.v2":
        raise BlueprintInvalid(f"preview-era blueprint manifest cannot enter v2 production on page {page_id}")
    slide_frame = existing.get("slide_frame") or _default_slide_frame(*dimensions)
    _validate_frame(slide_frame, dimensions, page_id)
    frame_x = float(slide_frame["x"])
    frame_y = float(slide_frame["y"])
    frame_width = float(slide_frame["w"])
    frame_height = float(slide_frame["h"])
    scale = CANVAS_WIDTH / frame_width
    transform = {
        "scale": scale,
        "offset_x": -frame_x * scale,
        "offset_y": -frame_y * scale,
        "crop": {"x": frame_x, "y": frame_y, "w": frame_width, "h": frame_height},
        "rounding_policy": "half_up_2dp",
    }
    style_hash = str((style_lock or {}).get("style_lock_sha256") or prompt.get("style_lock_sha256") or "0" * 64)
    manifest = {
        "schema_version": "deck_blueprint_manifest.v2",
        "run_id": str(lock["run_id"]),
        "page_id": page_id,
        "image_path": run_relative(root, image),
        "image_sha256": sha256_file(image),
        "prompt_ref": run_relative(root, prompt_file),
        "prompt_sha256": expected_prompt_sha,
        "content_lock_sha256": str(lock["content_lock_sha256"]),
        "nbb_plan_sha256": nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64),
        "style_lock_sha256": style_hash,
        "source_canvas": {"width": dimensions[0], "height": dimensions[1], "unit": "px"},
        "slide_frame": {"x": frame_x, "y": frame_y, "w": frame_width, "h": frame_height},
        "source_to_scene_transform": transform,
        "fit_mode": "approved_frame" if existing.get("slide_frame") else "contain",
        "internal_annotations": [],
        "provider": existing.get("provider") or {"tool": "agent_imagegen", "model": "unavailable", "request_id": "unavailable"},
        "approved": bool(existing.get("approved", False)) or image.suffix.lower() == ".svg",
        "created_at": str(existing.get("created_at") or utc_now()),
    }
    if manifest["internal_annotations"]:
        raise BlueprintInvalid(f"blueprint contains internal annotations on page {page_id}")
    assert_v2("blueprint_manifest", manifest)
    write_json(root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json", manifest)
    # Compatibility mirror for existing callers; it carries the same v2 payload.
    write_json(root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json", manifest)
    return root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json"


def load_blueprint_manifest(root: Path, page_id: str, *, expected_run_id: str | None = None) -> dict[str, Any]:
    path = blueprint_manifest_path(root, page_id)
    _assert_manifest_mirror_consistent(root, page_id, root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json")
    manifest = read_json(path)
    assert_v2("blueprint_manifest", manifest)
    if str(manifest.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint manifest page_id mismatch on page {page_id}")
    if expected_run_id and str(manifest.get("run_id") or "") != expected_run_id:
        raise BlueprintInvalid(f"blueprint manifest run_id mismatch on page {page_id}: expected {expected_run_id}")
    image = safe_image_path(root, str(manifest.get("image_path") or ""))
    expected_image = blueprint_path(root, page_id)
    if expected_image is None or image.resolve() != expected_image.resolve():
        raise BlueprintInvalid(f"blueprint manifest image_path mismatch on page {page_id}")
    prompt = read_json(safe_run_path(root, str(manifest.get("prompt_ref") or "")))
    assert_v2("blueprint_prompt", prompt)
    if str(prompt.get("run_id") or "") != str(manifest.get("run_id") or "") or str(prompt.get("page_id") or "") != page_id:
        raise BlueprintInvalid(f"blueprint prompt identity is stale on page {page_id}")
    for field in ("content_lock_sha256", "nbb_plan_sha256", "style_lock_sha256"):
        if str(prompt.get(field) or "") != str(manifest.get(field) or ""):
            raise BlueprintInvalid(f"blueprint prompt {field} is stale on page {page_id}")
    if prompt.get("prompt_sha256") != manifest.get("prompt_sha256"):
        raise BlueprintInvalid(f"blueprint prompt hash is stale on page {page_id}")
    if str(manifest.get("image_sha256") or "") != sha256_file(image):
        raise BlueprintInvalid(f"blueprint hash is stale on page {page_id}")
    dimensions = image_dimensions(image)
    source_canvas = manifest.get("source_canvas") or {}
    if (float(source_canvas.get("width") or 0), float(source_canvas.get("height") or 0)) != dimensions:
        raise BlueprintInvalid(f"blueprint source canvas is stale on page {page_id}")
    _validate_frame(manifest.get("slide_frame") or {}, dimensions, page_id)
    if not manifest.get("approved"):
        raise BlueprintInvalid(f"blueprint has not been approved on page {page_id}")
    return manifest


def safe_run_path(root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        raise BlueprintInvalid(f"blueprint path must be run-relative: {value}")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise BlueprintInvalid(f"blueprint path escapes run directory: {value}") from exc
    if not path.exists() or not path.is_file():
        raise BlueprintInvalid(f"blueprint artifact missing: {value}")
    return path


def safe_image_path(root: Path, value: str) -> Path:
    path = safe_run_path(root, value)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise BlueprintInvalid(f"unsupported blueprint extension: {path.suffix}")
    return path


__all__ = [
    "BLUEPRINT_DIR",
    "BLUEPRINT_MANIFEST_DIR",
    "BlueprintInvalid",
    "BlueprintRequired",
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "PROMPT_DIR",
    "build_blueprint_prompt",
    "build_blueprint_prompt_artifact",
    "blueprint_manifest_path",
    "blueprint_path",
    "ensure_blueprint_manifest",
    "image_dimensions",
    "load_blueprint_manifest",
    "prompt_path",
    "safe_image_path",
]
