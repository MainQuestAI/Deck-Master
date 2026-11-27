"""Native plan validation, geometry helpers, icon search, and image cropping."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re

from PIL import Image, ImageOps

from ..atoms import column_cell_ids, visible_atoms
from ..jobs import projection
from ..render import NeedsTool, resolve_fonts

DEFAULT_FONT = "Noto Sans CJK SC"
_HEX_COLOR = re.compile(r"^#?[0-9A-Fa-f]{6}$")

ICONS = Path(__file__).resolve().parents[1] / "resources" / "icons" / "tabler-outline"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
# Exact standard 16:9 widescreen slide width (40/3 in * 914400 EMU/in).
SLIDE_WIDTH_EMU = 12192000

# Reports of a sentence drawn twice counted atoms of at least eight characters.
# Shorter repeats are labels, not that finding.
_REPEATED_ATOM_MIN_CHARS = 8


def emu_per_px(plan):
    """EMU per source-image pixel: slide width is fixed, height follows the source aspect ratio."""
    return SLIDE_WIDTH_EMU / plan["canvas_px"]["w"]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("坐标和尺寸必须是有限数字")
    return value


def inside_box(bbox, w, h):
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox 必须是 [x,y,w,h]")
    x, y, width, height = map(number, bbox)
    if min(x, y, width, height) < 0 or x + width > w or y + height > h:
        raise ValueError("bbox 超出原图画布")


def icon_file(icon_id):
    prefix = "tabler-outline/"
    if not isinstance(icon_id, str) or not icon_id.startswith(prefix):
        raise ValueError("图标必须来自 Tabler outline")
    name = icon_id[len(prefix) :]
    candidate = (ICONS / f"{name}.svg").resolve()
    if not candidate.is_relative_to(ICONS.resolve()) or "/" in name or not candidate.is_file():
        raise ValueError(f"图标不存在：{icon_id}")
    return candidate


def _validate_image_asset(op, page):
    name = op.get("file")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("image 缺少素材文件")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"image 素材必须是当前任务目录内的相对路径：{name}")
    plan_path = page.get("plan")
    if not plan_path:
        return
    plan_dir = Path(plan_path).resolve().parent
    candidate = (plan_dir / rel).resolve()
    if not candidate.is_relative_to(plan_dir) or not candidate.is_file():
        raise ValueError(f"image 素材路径越出当前任务目录或不存在：{name}")
    try:
        with Image.open(candidate) as image:
            if image.format not in ("PNG", "JPEG"):
                raise ValueError(f"image 素材只支持 PNG 或 JPEG：{name}")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"image 素材无法按 PNG/JPEG 读取：{name}（{exc}）") from exc


def _validate_color(value, label, *, allow_none=False):
    if allow_none and value == "none":
        return
    if not isinstance(value, str) or not _HEX_COLOR.match(value):
        suffix = "或 none" if allow_none else ""
        raise ValueError(f"{label} 必须是 6 位十六进制颜色（如 #225588）{suffix}：{value!r}")


def _resolve_native_fonts(plans):
    shapes = []
    for plan in plans:
        for op in plan.get("ops", []):
            kind = op.get("op")
            if kind == "text":
                bold = op.get("weight") == "bold" or (
                    isinstance(op.get("weight"), (int, float)) and op["weight"] >= 600
                )
                shapes.append({"kind": "text", "font_family": op.get("font") or DEFAULT_FONT, "bold": bold})
            elif kind == "table":
                table_font = op.get("font") or DEFAULT_FONT
                header = op.get("header_style") or {}
                for row_index, row in enumerate(op.get("cells", [])):
                    for cell in row:
                        style = {**op, **(header if row_index == 0 else {}), **cell}
                        bold = style.get("weight") == "bold" or (
                            isinstance(style.get("weight"), (int, float)) and style["weight"] >= 600
                        )
                        shapes.append(
                            {
                                "kind": "text",
                                "font_family": style.get("font") or table_font,
                                "bold": bold,
                            }
                        )
    return resolve_fonts([{"shapes": shapes}]) if shapes else {}


def _omitted_column_labels(plan, atoms, groups):
    """Column labels may be listed instead of drawn. Every other atom stays required."""
    if "omitted" not in plan:
        return set()
    items = plan["omitted"]
    if not isinstance(items, list):
        raise ValueError("omitted 必须是列表")
    omitted = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("省略项必须包含 atom_id 和 reason")
        atom_id = item.get("atom_id")
        reason = item.get("reason")
        if (
            not isinstance(atom_id, str)
            or atom_id not in atoms
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError("省略项必须是当前正文的 atom，并写明理由")
        if atom_id not in groups:
            raise ValueError("只有表格列名可以标注省略")
        omitted.add(atom_id)
    return omitted


def _finite_size(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _band_tolerance(width):
    # Cells of one column sit together. Cards in a row are farther apart than this.
    return max(40, width * 0.08)


def _x_bands(boxes, tolerance):
    centers = sorted(box[0] + box[2] / 2 for box in boxes)
    bands = []
    for center in centers:
        if bands and abs(center - bands[-1][0]) <= tolerance:
            mean, count = bands[-1]
            count += 1
            bands[-1] = [mean + (center - mean) / count, count]
        else:
            bands.append([center, 1])
    return bands


def _placement(where, item, bbox):
    return {
        "where": where,
        "atom_id": item.get("atom_id"),
        "bbox": bbox,
        "size": item.get("size"),
        "repeat": item.get("repeat") is True,
    }


def _placements(plan):
    found = []
    for op in plan["ops"]:
        if op["op"] == "text":
            found.append(_placement("text", op, op["bbox"]))
        elif op["op"] == "table":
            top = op["bbox"][1]
            for row_index, row in enumerate(op["cells"]):
                left = op["bbox"][0]
                height = op["row_heights"][row_index]
                for col_index, cell in enumerate(row):
                    width = op["col_widths"][col_index]
                    found.append(_placement("cell", cell, [left, top, width, height]))
                    left += width
                top += height
    return found


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _compact_length(text):
    return len("".join(text.split()))


def _per_card_column_heading(placements, cell_boxes, tolerance):
    """One column label above each horizontal group is the card-title placement."""
    if len(placements) < 2 or any(item["where"] != "text" for item in placements):
        return False
    bands = _x_bands(cell_boxes, tolerance)
    if len(bands) != len(placements):
        return False
    used = set()
    for item in placements:
        center = item["bbox"][0] + item["bbox"][2] / 2
        match = None
        for index, (band_center, _count) in enumerate(bands):
            if index in used:
                continue
            if abs(center - band_center) <= tolerance:
                match = index
                break
        if match is None:
            return False
        used.add(match)
    return True


def _px_text(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _canvas_not_original(plan, page):
    """Hint when the plan canvas is still not the original's pixel size.

    Image.size is the same pair image-info reports. It does not apply EXIF
    orientation, so a rotated file is not treated as a different canvas.
    An unreadable file is skipped: this hint must not become a new failure.
    """
    source = page.get("source_image")
    if not isinstance(source, str) or not source:
        return None
    try:
        with Image.open(source) as image:
            image_size = image.size
    except (OSError, ValueError):
        return None
    width, height = plan["canvas_px"]["w"], plan["canvas_px"]["h"]
    if (width, height) == image_size:
        return None
    return {
        "level": "warning",
        "code": "canvas_not_original",
        "plan_px": {"w": width, "h": height},
        "image_px": {"w": image_size[0], "h": image_size[1]},
        "message": (
            f"plan.canvas_px 为 {_px_text(width)}×{_px_text(height)}，本页原图为 "
            f"{image_size[0]}×{image_size[1]} px。画布仍不是原图像素。此提示不阻止交回或采用。"
        ),
    }


def _plan_warnings(plan, atoms, groups):
    """Non-blocking hints. Assemble does not run this, and nothing here raises."""
    tolerance = _band_tolerance(plan["canvas_px"]["w"])
    by_atom = {}
    for item in _placements(plan):
        by_atom.setdefault(item["atom_id"], []).append(item)
    cell_boxes = {}
    cell_sizes = {}
    for label_id, cell_ids in groups.items():
        boxes = []
        sizes = []
        for cell_id in cell_ids:
            for item in by_atom.get(cell_id, []):
                if item["where"] != "text":
                    continue
                boxes.append(item["bbox"])
                if _finite_size(item["size"]):
                    sizes.append(item["size"])
        cell_boxes[label_id] = boxes
        cell_sizes[label_id] = sizes
    warnings = []
    for atom_id in sorted(by_atom):
        group = by_atom[atom_id]
        text = atoms.get(atom_id)
        if text is None:
            continue
        extras = len(group) - 1
        if extras > 0 and _compact_length(text) >= _REPEATED_ATOM_MIN_CHARS:
            marked = sum(item["repeat"] for item in group)
            per_card = atom_id in groups and _per_card_column_heading(
                group, cell_boxes.get(atom_id, []), tolerance
            )
            if marked < extras and not per_card:
                warnings.append(
                    {
                        "level": "warning",
                        "code": "repeated_atom",
                        "atom_id": atom_id,
                        "count": len(group),
                        "text": text,
                    }
                )
        if atom_id not in groups:
            continue
        labels = [item for item in group if item["where"] == "text"]
        sizes = cell_sizes.get(atom_id, [])
        if len(labels) != 1 or len(_x_bands(cell_boxes.get(atom_id, []), tolerance)) < 2 or not sizes:
            continue
        label_size = labels[0]["size"]
        if not _finite_size(label_size) or not label_size < _median(sizes):
            continue
        warnings.append(
            {
                "level": "warning",
                "code": "orphan_column_label",
                "atom_id": atom_id,
                "text": text,
            }
        )
    return warnings


def validate_plan(plan, page):
    if plan.get("schema") != "deck.native_plan.v1" or plan.get("page") != page["id"]:
        raise ValueError("plan 格式或页编号不匹配")
    if "notes" in plan:
        raise ValueError("讲稿通过 page.notes 传入，不写进 plan")
    _validate_color(plan.get("background"), "background")
    w, h = number(plan["canvas_px"]["w"]), number(plan["canvas_px"]["h"])
    if min(w, h) <= 0:
        raise ValueError("画布尺寸必须大于零")
    projected = projection(page)
    atoms = {a["atom_id"]: a["text"] for a in visible_atoms(projected) if a["text"] is not None}
    covered = set()

    def text(item):
        atom = item.get("atom_id")
        if atom not in atoms or item.get("text") != atoms[atom]:
            raise ValueError(f"文字必须与当前 content 的 atom 一致：{atom}")
        covered.add(atom)

    def margin(item):
        if "margin" not in item:
            return
        value = item["margin"]
        values = value if isinstance(value, list) else [value] * 4
        if len(values) != 4 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
            for v in values
        ):
            raise ValueError("margin 必须是非负有限数字或 [上,右,下,左] 四个非负有限数字（原图像素）")

    for op in plan["ops"]:
        kind = op["op"]
        if kind not in ("text", "shape", "arrow", "icon", "image", "table"):
            raise ValueError(f"不支持的原语：{kind}")
        if kind == "arrow":
            for point in (op["start"], op["end"]):
                if len(point) != 2:
                    raise ValueError("箭头端点必须是 [x,y]")
                inside_box([*point, 0, 0], w, h)
            if "color" in op:
                _validate_color(op["color"], "arrow.color", allow_none=True)
        else:
            inside_box(op["bbox"], w, h)
        if kind == "shape":
            if "fill" in op:
                _validate_color(op["fill"], "shape.fill", allow_none=True)
            if isinstance(op.get("line"), dict) and "color" in op["line"]:
                _validate_color(op["line"]["color"], "shape.line.color", allow_none=True)
        if kind == "shape" and "radius" in op and op["type"] not in ("rect", "roundRect"):
            raise ValueError("圆角只用于矩形")
        if kind == "text":
            if "color" in op:
                _validate_color(op["color"], "text.color")
            text(op)
        elif kind == "table":
            if "color" in op:
                _validate_color(op["color"], "table.color")
            if isinstance(op.get("line"), dict) and "color" in op["line"]:
                _validate_color(op["line"]["color"], "table.line.color", allow_none=True)
            header = op.get("header_style") or {}
            if "color" in header:
                _validate_color(header["color"], "table.header_style.color")
            if "fill" in header:
                _validate_color(header["fill"], "table.header_style.fill", allow_none=True)
            margin(op)
            margin(header)
            widths, heights, rows = op["col_widths"], op["row_heights"], op["cells"]
            if (
                len(rows) != len(heights)
                or not widths
                or not heights
                or any(len(r) != len(widths) for r in rows)
            ):
                raise ValueError("表格单元格、列宽和行高不匹配")
            if any(number(v) <= 0 for v in [*widths, *heights]):
                raise ValueError("表格行高和列宽必须大于零")
            if not math.isclose(sum(widths), op["bbox"][2]) or not math.isclose(
                sum(heights), op["bbox"][3]
            ):
                raise ValueError("表格行高和列宽合计必须等于 bbox")
            for row in rows:
                for cell in row:
                    if "color" in cell:
                        _validate_color(cell["color"], "table.cell.color")
                    if "fill" in cell:
                        _validate_color(cell["fill"], "table.cell.fill", allow_none=True)
                    margin(cell)
                    text(cell)
        elif kind == "icon":
            if "color" in op:
                _validate_color(op["color"], "icon.color")
            icon_file(op["icon_id"])
        elif kind == "image":
            if any(key in op for key in ("text", "atom_id", "cells", "content")):
                raise ValueError("image 不能承载正文，请用原生文字或表格")
            if op["bbox"][2] * op["bbox"][3] > w * h * 0.4:
                raise ValueError("单张图片面积不能超过画布的 40%")
            _validate_image_asset(op, page)
        elif kind == "shape" and op["type"] == "custom":
            points = op["points"]
            if len(points) < 2:
                raise ValueError("custom 至少需要两个点")
            for point in points:
                if len(point) != 2:
                    raise ValueError("custom 点必须是 bbox 内的 [x,y]")
                inside_box([*point, 0, 0], op["bbox"][2], op["bbox"][3])
        if kind not in ("text", "table", "image") and any(
            key in op for key in ("text", "atom_id", "content")
        ):
            raise ValueError("上屏文字必须使用 text 或 table 原语")
    groups = column_cell_ids(projected)
    omitted = _omitted_column_labels(plan, atoms, groups)
    missing = set(atoms) - covered - omitted
    if missing:
        raise ValueError("plan 缺少正文 atom：" + "、".join(sorted(missing)))
    result = {"page": page["id"], "atoms": len(covered)}
    warnings = _plan_warnings(plan, atoms, groups)
    canvas = _canvas_not_original(plan, page)
    if canvas:
        warnings.append(canvas)
    if warnings:
        result["warnings"] = warnings
    return result


def page_directory(work, page_id):
    root = (Path(work) / "native").resolve()
    destination = (root / page_id).resolve()
    if not page_id or destination == root or not destination.is_relative_to(root):
        raise ValueError("页编号必须位于 native 目录下")
    return destination


def crop(job):
    page = job["page"]
    crop_id = job.get("id")
    if (
        not isinstance(crop_id, str)
        or not crop_id.strip()
        or "/" in crop_id
        or "\\" in crop_id
        or crop_id in (".", "..")
        or crop_id.startswith(".")
    ):
        raise ValueError("裁图名称必须是不含路径分隔符的文件名")
    if "output_dir" in job:
        destination = Path(job["output_dir"]).resolve()
    else:
        destination = (page_directory(job["work"], page["id"]) / "assets").resolve()
    target = (destination / f"{crop_id}.png").resolve()
    if not target.is_relative_to(destination) or target.parent != destination:
        raise ValueError("裁图编号必须位于本页 assets 目录下")
    box = job.get("box")
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("bbox 必须是 [x,y,w,h]")
    x, y, w, h = map(number, box)
    if w <= 0 or h <= 0:
        raise ValueError("裁图宽高必须大于零")
    with Image.open(page["source_image"]) as image:
        transposed = ImageOps.exif_transpose(image)
        inside_box([x, y, w, h], *transposed.size)
        destination.mkdir(parents=True, exist_ok=True)
        cropped = transposed.crop((x, y, x + w, y + h))
        cropped.save(target, format="PNG")
        out_w, out_h = cropped.size
    return {
        "file": str(target),
        "relative_path": f"assets/{crop_id}.png",
        "width": out_w,
        "height": out_h,
        "format": "PNG",
    }


def icon_search(job):
    from ..vendor.cyberppt.select_icon import load_index, search_icons

    query = job.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("请提供非空的图标检索关键词")
    limit = job.get("limit", 12)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("limit 必须是 1 到 100 之间的整数")
    index_path = ICONS / "index.json"
    if not index_path.is_file():
        raise NeedsTool("找不到内置 Tabler 图标索引；请重新安装 deck-tools")
    index = load_index(index_path)
    matches = search_icons(index, query, library="tabler-outline", limit=limit)
    items = []
    for item in matches:
        items.append(
            {
                "icon_id": item["icon_id"],
                "name": item["name"],
                "category": item.get("category", ""),
                "tags": item.get("tags", []),
            }
        )
    return {"query": query, "count": len(items), "icons": items}
