"""Codex-hosted blueprint production requests.

The package prepares an exact, inspectable prompt projection.  It does not
call a provider or read API credentials: the Codex host executes its built-in
image tool and returns the resulting file through the normal task envelope.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .models import ModelError, canonical_json_bytes, sha256_bytes


def _visible_block(block: dict[str, Any]) -> dict[str, Any]:
    """Keep the complete customer-visible block, including nested items/cells."""
    return json.loads(json.dumps(block, ensure_ascii=False))


def _style_for(page: dict[str, Any], design_context: dict[str, Any]) -> dict[str, Any]:
    visual = page.get("visual_spec") or {}
    style_id = visual.get("style_ref") or design_context.get("default_style_id")
    styles = design_context.get("styles") or []
    style = next((item for item in styles if item.get("style_id") == style_id), None)
    if style is None:
        raise ModelError("visual_spec/style_ref", f"unknown style {style_id!r}")
    return style


def resolve_design(page, design, permitted_assets):
    effective = deepcopy(design)
    style = deepcopy(_style_for(page, design))
    overrides = (page.get("visual_spec") or {}).get("design_overrides") or {}
    project_ids = set(design.get("allowed_asset_ids") or [])
    page_ids = set(overrides.get("allowed_asset_ids", project_ids))
    if not page_ids <= project_ids:
        raise ModelError("visual_spec/design_overrides/allowed_asset_ids", "page asset permissions exceed project")
    asset_map = {a["asset_id"]: a for a in permitted_assets}
    for aid in project_ids:
        if aid not in asset_map or asset_map[aid].get("external_use") != "allowed":
            raise ModelError("design_context/allowed_asset_ids", f"asset {aid!r} is missing or not allowed for external use")
    fonts = {f["font_id"]: f for f in design.get("fonts") or []}
    for slot in ("body_font_id", "heading_font_id"):
        fid = overrides.get(slot, style["typography"].get(slot))
        if fid not in fonts:
            raise ModelError(f"visual_spec/design_overrides/{slot}", f"unknown font {fid!r}")
        style["typography"][slot] = fid
    effective["language"] = overrides.get("language", design["language"])
    effective["styles"] = [style]
    effective["default_style_id"] = style["style_id"]
    effective["allowed_asset_ids"] = sorted(page_ids)
    effective["assets"] = [a for a in permitted_assets if a["asset_id"] in page_ids]
    return effective, style


def style_font_fingerprint(design, style, asset_sha):
    """Font-reality slice of a style fingerprint (P1-06).

    ``asset_sha`` maps a design asset_id to its stored artifact content sha
    (or None). Resolved font files hash by content, so swapping bytes under
    the same font_id always changes the fingerprint; unresolvable fonts are
    conservatively recorded by their declared identity.
    """
    fonts_by_id = {f.get("font_id"): f for f in (design or {}).get("fonts") or []}
    typography = (style or {}).get("typography") or {}
    entries = []
    for slot in ("body_font_id", "heading_font_id"):
        font_id = typography.get(slot)
        font = fonts_by_id.get(font_id) or {}
        sha = asset_sha(font.get("asset_id")) if font.get("asset_id") else None
        if sha:
            entries.append((slot, "asset", sha))
        else:
            entries.append((slot, "decl", font_id, font.get("family"), font.get("face"),
                            font.get("weight")))
    return repr(sorted(entries))


def project_prompt(
    page: dict[str, Any],
    resolved_design_context: dict[str, Any],
    permitted_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project one Page and its resolved design into the actual ImageGen input.

    ``projection`` is stored beside the prompt so tests and later review can
    prove which source fields entered the submitted request.  Speaker notes
    and ``internal_only`` are deliberately excluded from the visible design.
    """
    visible = page.get("customer_visible") or {}
    visual = page.get("visual_spec") or {}
    resolved_design_context, style = resolve_design(page, resolved_design_context, permitted_assets)
    assets = resolved_design_context["assets"]
    projection = {
        "page_id": page.get("page_id"),
        "language": resolved_design_context.get("language") or "zh-CN",
        "canvas": resolved_design_context.get("canvas") or {},
        "style": style,
        "fonts": resolved_design_context.get("fonts") or [],
        "permitted_assets": assets,
        "customer_visible": {
            "title": visible.get("title") or "",
            "subtitle": visible.get("subtitle") or "",
            "body_blocks": [_visible_block(block) for block in visible.get("body_blocks") or []],
            "labels": visible.get("labels") or [],
            "footnotes": visible.get("footnotes") or [],
            "callouts": visible.get("callouts") or [],
        },
        "visual_spec": {
            "intent": visual.get("intent") or "",
            "layout_hint": visual.get("layout_hint") or "",
            "reference_mode": visual.get("reference_mode") or "new_design",
            "nodes": visual.get("nodes") or [],
            "edges": visual.get("edges") or [],
            "style_ref": visual.get("style_ref") or resolved_design_context.get("default_style_id"),
        },
    }
    payload = json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True)
    prompt = (
        "Use case: productivity-visual\n"
        "Asset type: editable-presentation blueprint reference, one complete slide\n"
        f"Canvas: {projection['canvas']['width_px']}x{projection['canvas']['height_px']} px; "
        f"physical size {projection['canvas']['slide_width_in']}x{projection['canvas']['slide_height_in']} in; contain fit\n"
        "Primary request: Create a polished business slide blueprint from the exact structured input below. "
        "Preserve every visible fact, number, unit, label, footnote, node and directed relationship.\n"
        "Style/medium: precise enterprise presentation design; clear hierarchy; production-ready reference image\n"
        "Composition/framing: use the supplied canvas, layout intent and node relationships; keep all content inside safe margins\n"
        "Text: render the supplied customer-visible text verbatim and legibly\n"
        "Constraints: do not add claims or invent numeric values, dates, customer data, or outcomes. "
        "If a chart needs data absent from the input, use an unlabeled schematic marked 示意数据, "
        "without plausible-looking values. Do not omit modules; connect arrows to their actual nodes; "
        "use only permitted assets; no watermark; no internal notes\n"
        "Structured input:\n" + payload
    )
    return {
        "schema_version": "deck_blueprint_request.v1",
        "page_id": page.get("page_id"),
        "prompt": prompt,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "projection": projection,
        "projection_sha256": sha256_bytes(canonical_json_bytes(projection)),
        "host": "codex_imagegen",
        "requires": ["image_generation", "image_inspection", "local_file_access"],
    }
