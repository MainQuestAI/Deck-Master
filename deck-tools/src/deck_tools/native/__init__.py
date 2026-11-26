"""File-only native reconstruction facade: no project database or adoption state."""

from __future__ import annotations

import sys

from ..readback_core import (
    missing_visible_atoms as _missing_visible_atoms,
    slide_text_objects as _slide_text_objects,
    take_span as _take_span,
)
from ..render import render_deck
from .assemble import assemble
from .generate import (
    _render_svg_png,
    _render_svg_png_cached,
    _svg_png_width,
    _transparent_png,
    emit_native_slide,
    ensure_svg_content_type_and_notes_order,
    generate,
    render,
    select_blank_layout,
)
from .plan import (
    DEFAULT_FONT,
    ICONS,
    NS,
    SLIDE_WIDTH_EMU,
    _canvas_not_original,
    _omitted_column_labels,
    _plan_warnings,
    _resolve_native_fonts,
    _validate_color,
    _validate_image_asset,
    crop,
    emu_per_px,
    icon_file,
    icon_search,
    inside_box,
    number,
    page_directory,
    read_json,
    validate_plan,
    write_json,
)
from .readback import (
    _omitted_column_label_ids,
    detect_missing_visual_objects,
    readback,
)


def dispatch(command, job):
    if command == "validate-plan":
        return validate_plan(read_json(job["page"]["plan"]), job["page"])
    return {
        "crop": crop,
        "render": render,
        "assemble": assemble,
        "icon-search": icon_search,
    }[command](job)


__all__ = [
    "DEFAULT_FONT",
    "ICONS",
    "NS",
    "SLIDE_WIDTH_EMU",
    "assemble",
    "crop",
    "detect_missing_visual_objects",
    "dispatch",
    "emit_native_slide",
    "emu_per_px",
    "ensure_svg_content_type_and_notes_order",
    "generate",
    "icon_file",
    "icon_search",
    "inside_box",
    "number",
    "page_directory",
    "read_json",
    "readback",
    "render",
    "render_deck",
    "select_blank_layout",
    "sys",
    "validate_plan",
    "write_json",
    "_canvas_not_original",
    "_missing_visible_atoms",
    "_omitted_column_label_ids",
    "_omitted_column_labels",
    "_plan_warnings",
    "_render_svg_png",
    "_render_svg_png_cached",
    "_resolve_native_fonts",
    "_slide_text_objects",
    "_svg_png_width",
    "_take_span",
    "_transparent_png",
    "_validate_color",
    "_validate_image_asset",
]
