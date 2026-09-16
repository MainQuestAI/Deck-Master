"""Codex-hosted blueprint production requests.

The package prepares an exact, inspectable prompt projection.  It does not
call a provider or read API credentials: the Codex host executes its built-in
image tool and returns the resulting file through the normal task envelope.
"""

from __future__ import annotations

import json
from typing import Any

from .models import canonical_json_bytes, sha256_bytes


def _visible_block(block: dict[str, Any]) -> dict[str, Any]:
    """Keep the complete customer-visible block, including nested items/cells."""
    return json.loads(json.dumps(block, ensure_ascii=False))


def _style_for(page: dict[str, Any], design_context: dict[str, Any]) -> dict[str, Any]:
    visual = page.get("visual_spec") or {}
    style_id = visual.get("style_ref") or design_context.get("default_style_id")
    styles = design_context.get("styles") or []
    style = next((item for item in styles if item.get("style_id") == style_id), None)
    if style is None:
        raise ValueError(f"page {page.get('page_id')} references unknown style {style_id!r}")
    return style


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
    style = _style_for(page, resolved_design_context)
    asset_ids = set(resolved_design_context.get("allowed_asset_ids") or [])
    assets = [asset for asset in permitted_assets if asset.get("asset_id") in asset_ids]
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
        "Asset type: editable-presentation blueprint reference, one complete 16:9 slide\n"
        "Primary request: Create a polished business slide blueprint from the exact structured input below. "
        "Preserve every visible fact, number, unit, label, footnote, node and directed relationship.\n"
        "Style/medium: precise enterprise presentation design; clear hierarchy; production-ready reference image\n"
        "Composition/framing: use the supplied canvas, layout intent and node relationships; keep all content inside safe margins\n"
        "Text: render the supplied customer-visible text verbatim and legibly\n"
        "Constraints: do not add claims; do not omit modules; connect arrows to their actual nodes; "
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
