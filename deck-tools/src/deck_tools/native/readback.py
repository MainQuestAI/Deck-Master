"""Native PPTX readback and non-blocking missing-visual-object detection."""

from __future__ import annotations

from collections import deque
from pathlib import Path
import zipfile

from lxml import etree
from PIL import Image

from ..atoms import column_cell_ids, visible_atoms
from ..jobs import projection
from ..readback_core import (
    check_notes_and_count,
    missing_visible_atoms,
    slide_text_objects,
)
from .plan import read_json

_ANALYSIS_WIDTH = 320
_DIFF_CHANNEL_THRESHOLD = 42
_SOURCE_CONTRAST_THRESHOLD = 32
_MIN_COMPONENT_CELLS = 16
_MIN_COMPONENT_SIDE = 3
_MAX_VISUAL_WARNINGS = 8
_MASK_PAD_PX = 6


def _source_has_foreground_object(
    src_bytes: bytes,
    grid_w: int,
    grid_h: int,
    gx: int,
    gy: int,
    gw: int,
    gh: int,
) -> bool:
    """Confirm the source image actually has a distinct visual object in this box.

    Avoids false positives when the source image is flat/blank and the plan
    intentionally added a background or container shape in that region.
    """
    x0 = max(0, gx - 2)
    y0 = max(0, gy - 2)
    x1 = min(grid_w - 1, gx + gw + 1)
    y1 = min(grid_h - 1, gy + gh + 1)
    border_r = border_g = border_b = 0
    border_count = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if gx <= x < gx + gw and gy <= y < gy + gh:
                continue
            base = (y * grid_w + x) * 3
            border_r += src_bytes[base]
            border_g += src_bytes[base + 1]
            border_b += src_bytes[base + 2]
            border_count += 1
    if border_count == 0:
        return False
    br = border_r / border_count
    bg = border_g / border_count
    bb = border_b / border_count
    contrasting = 0
    for y in range(gy, min(grid_h, gy + gh)):
        row = y * grid_w
        for x in range(gx, min(grid_w, gx + gw)):
            base = (row + x) * 3
            if (
                max(
                    abs(src_bytes[base] - br),
                    abs(src_bytes[base + 1] - bg),
                    abs(src_bytes[base + 2] - bb),
                )
                >= _SOURCE_CONTRAST_THRESHOLD
            ):
                contrasting += 1
                if contrasting >= _MIN_COMPONENT_CELLS:
                    return True
    return False


def _omitted_column_label_ids(page):
    """Column labels the plan lists as not drawn. Other omitted ids stay required."""
    plan = read_json(page["plan"])
    labels = set(column_cell_ids(projection(page)))
    return {
        item["atom_id"]
        for item in plan.get("omitted") or []
        if isinstance(item, dict) and item.get("atom_id") in labels
    }


def readback(pptx, pages):
    from ..compiler.native import notes_records, normalize_notes

    notes = notes_records(Path(pptx).read_bytes())
    findings = check_notes_and_count(
        notes,
        [(page["id"], page.get("notes", "")) for page in pages],
        normalize_notes=normalize_notes,
    )
    with zipfile.ZipFile(pptx) as archive:
        for index, (page, _actual) in enumerate(zip(pages, notes), 1):
            root = etree.fromstring(archive.read(f"ppt/slides/slide{index}.xml"))
            atoms = visible_atoms(projection(page))
            omitted = _omitted_column_label_ids(page)
            if omitted:
                atoms = [atom for atom in atoms if atom["atom_id"] not in omitted]
            for atom in missing_visible_atoms(slide_text_objects(root), atoms):
                findings.append(
                    {
                        "page_id": page["id"],
                        "code": "missing_visible_atom",
                        "atom_id": atom["atom_id"],
                        "text": atom["text"],
                    }
                )
    return {"status": "fail" if findings else "pass", "findings": findings}


def _mark_excluded_boxes(plan, grid_w: int, grid_h: int) -> bytearray:
    """Mask regions owned by text, table, icon, or image ops so text drift is ignored."""
    canvas_w = float(plan["canvas_px"]["w"])
    canvas_h = float(plan["canvas_px"]["h"])
    excluded = bytearray(grid_w * grid_h)
    sx = grid_w / canvas_w
    sy = grid_h / canvas_h
    pad_x = max(1, round(_MASK_PAD_PX * sx))
    pad_y = max(1, round(_MASK_PAD_PX * sy))
    for op in plan.get("ops", []):
        if op.get("op") not in ("text", "table", "icon", "image"):
            continue
        bbox = op.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        x0 = max(0, int(bbox[0] * sx) - pad_x)
        y0 = max(0, int(bbox[1] * sy) - pad_y)
        x1 = min(grid_w, int((bbox[0] + bbox[2]) * sx + 0.999) + pad_x)
        y1 = min(grid_h, int((bbox[1] + bbox[3]) * sy + 0.999) + pad_y)
        for gy in range(y0, y1):
            row_offset = gy * grid_w
            for gx in range(x0, x1):
                excluded[row_offset + gx] = 1
    return excluded


def _dilate_once(mask: bytearray, width: int, height: int) -> bytearray:
    """Bridge 1-cell gaps inside an omitted icon or thin illustration stroke."""
    out = bytearray(mask)
    for y in range(height):
        row = y * width
        for x in range(width):
            if not mask[row + x]:
                continue
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= height:
                    continue
                nrow = ny * width
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if 0 <= nx < width:
                        out[nrow + nx] = 1
    return out


def detect_missing_visual_objects(
    source_image_path: str | Path | None,
    render_image_path: str | Path | None,
    plan: dict,
) -> list[dict]:
    """Compare source and rendered images outside text/table/icon/image boxes.

    Significant connected pixel diffs indicate icons, illustrations, or crops
    present in the original image but omitted from the plan. Always returns
    non-blocking warning dicts and never raises on unreadable images.
    """
    if not source_image_path or not render_image_path:
        return []
    try:
        canvas = plan.get("canvas_px") or {}
        canvas_w = float(canvas["w"])
        canvas_h = float(canvas["h"])
        if canvas_w <= 0 or canvas_h <= 0:
            return []
        with Image.open(source_image_path) as src_img, Image.open(render_image_path) as rnd_img:
            grid_w = min(_ANALYSIS_WIDTH, max(1, src_img.width))
            grid_h = max(1, round(grid_w * src_img.height / max(1, src_img.width)))
            src_rgb = src_img.convert("RGB").resize((grid_w, grid_h), Image.Resampling.BILINEAR)
            rnd_rgb = rnd_img.convert("RGB").resize((grid_w, grid_h), Image.Resampling.BILINEAR)
            src_bytes = src_rgb.tobytes()
            rnd_bytes = rnd_rgb.tobytes()
    except (OSError, ValueError, KeyError, TypeError):
        return []

    excluded = _mark_excluded_boxes(plan, grid_w, grid_h)
    raw_diff = bytearray(grid_w * grid_h)
    for idx in range(grid_w * grid_h):
        if excluded[idx]:
            continue
        base = idx * 3
        dr = abs(src_bytes[base] - rnd_bytes[base])
        dg = abs(src_bytes[base + 1] - rnd_bytes[base + 1])
        db = abs(src_bytes[base + 2] - rnd_bytes[base + 2])
        if max(dr, dg, db) >= _DIFF_CHANNEL_THRESHOLD:
            raw_diff[idx] = 1

    if not any(raw_diff):
        return []

    diff = _dilate_once(raw_diff, grid_w, grid_h)
    visited = bytearray(grid_w * grid_h)
    components: list[tuple[int, int, int, int, int]] = []
    for y in range(grid_h):
        for x in range(grid_w):
            start = y * grid_w + x
            if not diff[start] or visited[start]:
                continue
            visited[start] = 1
            queue = deque([(x, y)])
            min_x = max_x = x
            min_y = max_y = y
            raw_cells = 0
            while queue:
                cx, cy = queue.popleft()
                cidx = cy * grid_w + cx
                if raw_diff[cidx]:
                    raw_cells += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < grid_w and 0 <= ny < grid_h:
                        nidx = ny * grid_w + nx
                        if diff[nidx] and not visited[nidx]:
                            visited[nidx] = 1
                            queue.append((nx, ny))
            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            if (
                raw_cells >= _MIN_COMPONENT_CELLS
                and bw >= _MIN_COMPONENT_SIDE
                and bh >= _MIN_COMPONENT_SIDE
                and _source_has_foreground_object(src_bytes, grid_w, grid_h, min_x, min_y, bw, bh)
            ):
                components.append((raw_cells, min_x, min_y, bw, bh))

    components.sort(key=lambda item: (-item[0], item[2], item[1]))
    warnings: list[dict] = []
    total_cells = float(grid_w * grid_h)
    scale_x = canvas_w / grid_w
    scale_y = canvas_h / grid_h
    for raw_cells, gx, gy, gw, gh in components[:_MAX_VISUAL_WARNINGS]:
        bx = max(0, round(gx * scale_x))
        by = max(0, round(gy * scale_y))
        bw_px = min(round(canvas_w) - bx, max(1, round(gw * scale_x)))
        bh_px = min(round(canvas_h) - by, max(1, round(gh * scale_y)))
        warnings.append(
            {
                "level": "warning",
                "code": "missing_visual_object",
                "bbox": [bx, by, bw_px, bh_px],
                "area_ratio": round(raw_cells / total_cells, 4),
                "message": (
                    f"原图区域 [{bx}, {by}, {bw_px}, {bh_px}] 与渲染图存在显著非文字视觉差异，"
                    "可能漏登记了图标、插画或局部裁图；请对照原图确认是否需要补 icon 或 crop。此提示不阻止交回或采用。"
                ),
            }
        )
    return warnings
