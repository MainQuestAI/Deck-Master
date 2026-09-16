"""Page normalization and visible atoms for the rebuilt core (spec 03.4, 03.10).

``visible_atoms`` lists every piece of customer-visible copy with a stable
atom id and a JSON Pointer. Atom ids come from stable ids (block/item/cell),
never array position or text hashes: reorder or rewording keeps the id,
copying creates a new id, and a missing id is assigned exactly once per
operation (deterministic, retry-stable — spec 03.10). Legacy JSON-Pointer
refs are rewritten to atom ids only during the one-time legacy import.

Unknown fields are never silently dropped (AC-C11): normalization raises the
paths that need a content-mapping decision instead of partial success.
``internal_only`` and speaker notes never become visible atoms.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .models import ModelError, validate_page_semantics

_ATOM_NAMESPACE = uuid.UUID("b0d5e11f-5ea1-4ea1-a001-dec0de000001")


class NeedsNormalization(ModelError):
    """The input contains content this version cannot map automatically."""


def _atom_id(page_id: str, kind: str, stable_id: str, field_name: str) -> str:
    return f"atom:{page_id}:{kind}:{stable_id}:{field_name}"


def _pointer(*parts) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _stable_id(entity: dict, fallback: str) -> str:
    entity_id = entity.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id
    return fallback


def visible_atoms(page: dict) -> list[dict]:
    """Every customer-visible text atom: {atom_id, pointer, text, kind}."""
    page_id = page["page_id"]
    visible = page.get("customer_visible") or {}
    atoms: list[dict] = []

    def push(kind: str, atom_id: str, pointer: str, text: Any) -> None:
        atoms.append({"atom_id": atom_id, "pointer": pointer, "text": text, "kind": kind})

    if visible.get("title") is not None:
        push("title", f"atom:{page_id}:title", "/customer_visible/title", visible["title"])
    if visible.get("subtitle") is not None:
        push(
            "subtitle",
            f"atom:{page_id}:subtitle",
            "/customer_visible/subtitle",
            visible["subtitle"],
        )

    blocks = visible.get("body_blocks") or []
    for block_index, block in enumerate(blocks):
        block_id = _stable_id(block, f"block-{block_index + 1}")
        block_type = block.get("type")
        if block_type == "bullets":
            if block.get("heading") is not None:
                push(
                    "block_heading",
                    _atom_id(page_id, "block", block_id, "heading"),
                    _pointer("customer_visible", "body_blocks", block_index, "heading"),
                    block["heading"],
                )
            _collect_items(
                atoms, page_id, block.get("items") or [], ["body_blocks", str(block_index)], block_id
            )
        elif block_type == "paragraph":
            if block.get("text") is not None:
                push(
                    "paragraph",
                    _atom_id(page_id, "block", block_id, "text"),
                    _pointer("customer_visible", "body_blocks", block_index, "text"),
                    block["text"],
                )
        elif block_type == "table":
            _collect_table(atoms, page_id, block, block_index)
        else:
            raise NeedsNormalization(
                f"page/body_blocks/{block_id}",
                f"unknown body block type {block_type!r}; map it to paragraph/bullets/table explicitly",
            )

    for label_index, label in enumerate(visible.get("labels") or []):
        label_id = _stable_id(label, f"label-{label_index + 1}")
        push(
            "label",
            _atom_id(page_id, "label", label_id, "text"),
            _pointer("customer_visible", "labels", label_index, "text"),
            label.get("text"),
        )
    for note_index, footnote in enumerate(visible.get("footnotes") or []):
        note_id = _stable_id(footnote, f"footnote-{note_index + 1}")
        push(
            "footnote",
            _atom_id(page_id, "footnote", note_id, "text"),
            _pointer("customer_visible", "footnotes", note_index, "text"),
            footnote.get("text"),
        )
    for callout_index, callout in enumerate(visible.get("callouts") or []):
        callout_id = _stable_id(callout, f"callout-{callout_index + 1}")
        push(
            "callout",
            _atom_id(page_id, "callout", callout_id, "text"),
            _pointer("customer_visible", "callouts", callout_index, "text"),
            callout.get("text"),
        )
    return atoms


def _collect_items(atoms: list, page_id: str, items: list, path: list, parent_id: str) -> None:
    """Bullets at every nesting level; item ids must be unique within the page."""
    for item_index, item in enumerate(items):
        item_id = _stable_id(item, f"{parent_id}-item-{item_index + 1}")
        if item.get("text") is not None:
            atoms.append(
                {
                    "atom_id": _atom_id(page_id, "item", item_id, "text"),
                    "pointer": _pointer("customer_visible", *path, "items", item_index, "text"),
                    "text": item["text"],
                    "kind": "item_text",
                }
            )
        nested = item.get("items") or []
        if nested:
            _collect_items(atoms, page_id, nested, path + ["items", str(item_index)], item_id)


def _collect_table(atoms: list, page_id: str, block: dict, block_index: int) -> None:
    table_id = _stable_id(block, f"table-{block_index + 1}")
    columns = block.get("columns") or []
    for column_index, column in enumerate(columns):
        column_id = _stable_id(column, f"col-{column_index + 1}")
        atoms.append(
            {
                "atom_id": _atom_id(page_id, "column", f"{table_id}:{column_id}", "label"),
                "pointer": _pointer(
                    "customer_visible", "body_blocks", block_index, "columns", column_index, "label"
                ),
                "text": column.get("label"),
                "kind": "column_label",
            }
        )
    rows = block.get("rows") or []
    for row_index, row in enumerate(rows):
        row_id = _stable_id(row, f"row-{row_index + 1}")
        cells = row.get("cells") or []
        for cell_index, cell in enumerate(cells):
            column_id = cell.get("column_id") or f"col-{cell_index + 1}"
            atoms.append(
                {
                    "atom_id": _atom_id(
                        page_id, "cell", f"{table_id}:{row_id}:{column_id}", "display_text"
                    ),
                    "pointer": _pointer(
                        "customer_visible",
                        "body_blocks",
                        block_index,
                        "rows",
                        row_index,
                        "cells",
                        cell_index,
                        "display_text",
                    ),
                    "text": cell.get("display_text"),
                    "kind": "table_cell",
                }
            )


def atom_ids(page: dict) -> set[str]:
    return {atom["atom_id"] for atom in visible_atoms(page)}


def validate_page_references(page: dict) -> None:
    """label_ref / responsibility_refs must point at real visible atoms (spec 03.9)."""
    ids = atom_ids(page)
    visual = page.get("visual_spec") or {}
    for node in visual.get("nodes") or []:
        node_id = node.get("node_id")
        label_ref = node.get("label_ref")
        if label_ref is not None and label_ref not in ids:
            raise NeedsNormalization(
                f"page/visual_spec/nodes/{node_id}",
                f"label_ref {label_ref!r} does not point at a visible atom",
            )
        for ref in node.get("responsibility_refs") or []:
            if ref not in ids:
                raise NeedsNormalization(
                    f"page/visual_spec/nodes/{node_id}",
                    f"responsibility_ref {ref!r} is not a visible atom",
                )
    for edge in visual.get("edges") or []:
        edge_id = edge.get("edge_id")
        label_ref = edge.get("label_ref")
        if label_ref is not None and label_ref not in ids:
            raise NeedsNormalization(
                f"page/visual_spec/edges/{edge_id}",
                f"label_ref {label_ref!r} is not a visible atom",
            )


def assign_missing_ids(page: dict, *, operation_id: str) -> tuple[dict, list[dict]]:
    """Assign persistent ids to blocks/items/cells/labels missing one (spec 03.10).

    Deterministic per ``operation_id`` + normalization-time position, so
    retrying the same operation reproduces the same ids. The caller must
    persist the returned page; later edits keep these explicit ids. Returns
    ``(normalized_page, id_map)`` with one entry ``{pointer, assigned_id}``
    per assigned id.
    """
    customer = dict(page.get("customer_visible") or {})
    mapping: list[dict] = []

    def fresh(pointer: str) -> str:
        assigned = "i-" + uuid.uuid5(_ATOM_NAMESPACE, f"{operation_id}:{pointer}").hex[:12]
        mapping.append({"pointer": pointer, "assigned_id": assigned})
        return assigned

    blocks = []
    for block_index, block in enumerate(customer.get("body_blocks") or []):
        updated = dict(block)
        block_pointer = f"/customer_visible/body_blocks/{block_index}"
        if not updated.get("id"):
            updated["id"] = fresh(block_pointer)
        if updated.get("type") == "bullets":
            updated["items"] = _assign_ids_recursive(
                updated.get("items") or [],
                [block_index, "items"],
                operation_id,
                mapping,
            )
        blocks.append(updated)
    customer["body_blocks"] = blocks

    for kind, slot in (("label", "labels"), ("footnote", "footnotes"), ("callout", "callouts")):
        entries = []
        for index, entry in enumerate(customer.get(slot) or []):
            updated_entry = dict(entry)
            if not updated_entry.get("id"):
                updated_entry["id"] = fresh(f"/customer_visible/{slot}/{index}")
            entries.append(updated_entry)
        customer[slot] = entries
    return {**page, "customer_visible": customer}, mapping


def _assign_ids_recursive(items: list, path: list, operation_id: str, mapping: list) -> list:
    assigned_items = []
    for item_index, item in enumerate(items):
        updated = dict(item)
        pointer = _pointer("customer_visible", *(str(part) for part in path), item_index)
        if not updated.get("id"):
            updated["id"] = "i-" + uuid.uuid5(
                _ATOM_NAMESPACE, f"{operation_id}:{pointer}"
            ).hex[:12]
            mapping.append({"pointer": pointer, "assigned_id": updated["id"]})
        nested = updated.get("items") or []
        if nested:
            updated["items"] = _assign_ids_recursive(
                nested, path + [item_index, "items"], operation_id, mapping
            )
        assigned_items.append(updated)
    return assigned_items


def normalize_legacy_pointers(page: dict) -> dict:
    """One-time rewrite of legacy JSON-Pointer refs into stable atom ids (spec 03.10)."""
    pointer_map = {atom["pointer"]: atom["atom_id"] for atom in visible_atoms(page)}
    visual = dict(page.get("visual_spec") or {})

    def remap(ref: Any, where: str) -> Any:
        if not isinstance(ref, str) or ref.startswith("atom:"):
            return ref
        if ref.startswith("/"):
            resolved = pointer_map.get(ref)
            if resolved is None:
                raise NeedsNormalization(
                    where, f"legacy pointer {ref!r} does not resolve to a visible atom"
                )
            return resolved
        return ref

    nodes = []
    for node in visual.get("nodes") or []:
        updated = dict(node)
        where = f"page/visual_spec/nodes/{node.get('node_id')}"
        if "label_ref" in updated:
            updated["label_ref"] = remap(updated["label_ref"], where)
        if "responsibility_refs" in updated:
            updated["responsibility_refs"] = [
                remap(ref, where) for ref in updated["responsibility_refs"]
            ]
        nodes.append(updated)
    visual["nodes"] = nodes

    edges = []
    for edge in visual.get("edges") or []:
        updated = dict(edge)
        where = f"page/visual_spec/edges/{edge.get('edge_id')}"
        if "label_ref" in updated:
            updated["label_ref"] = remap(updated["label_ref"], where)
        edges.append(updated)
    visual["edges"] = edges
    return {**page, "visual_spec": visual}


def check_page(page: dict, *, legacy_pointers: bool = False) -> dict:
    """Whole-page prevalidation; returns the normalized page or raises with paths."""
    if legacy_pointers:
        page = normalize_legacy_pointers(page)
    validate_page_semantics(page)
    validate_page_references(page)
    return page


def normalize_design_assets(store, design_partial: dict, *, base_dir) -> dict:
    """First-import design normalization (spec 03.3a).

    ``assets`` entries arrive with ``file`` (local path resolved against
    ``base_dir``) or ``artifact`` Ref — never both. ``file`` bytes are stored
    as an immutable asset Artifact first; only the permanent Ref reaches the
    Document. No temporary path is written into the authority.
    """
    assets = []
    for entry in design_partial.get("assets") or []:
        has_file = entry.get("file") is not None
        has_artifact = entry.get("artifact") is not None
        if has_file and has_artifact:
            raise ModelError(
                f"design_context/assets/{entry.get('asset_id')}",
                "file and artifact cannot both be present",
            )
        if has_file:
            file_path = Path(entry["file"])
            if not file_path.is_absolute():
                file_path = base_dir / file_path
            file_path = file_path.resolve()
            if not file_path.is_file():
                raise ModelError(
                    f"design_context/assets/{entry.get('asset_id')}",
                    f"asset file not found: {entry['file']}",
                )
            suffix = file_path.suffix.lstrip(".").lower() or "bin"
            from .models import validate_artifact_semantics

            artifact = {
                "schema_version": "deck_artifact.v1",
                "artifact_id": f"asset-{entry.get('asset_id')}",
                "page_id": None,
                "role": "asset",
                "file": store.put_blob(file_path.read_bytes(), ext=suffix),
                "media_type": _media_type(file_path),
                "created_at": _utc_now_iso(),
                "dependencies": [],
                "derived_from": [],
                "provenance": {"source_type": "user_supplied"},
                "limitations": [],
                "editability": "not_applicable",
            }
            validate_artifact_semantics(artifact)
            artifact_ref = store.put_json_object(artifact)
            entry = {**entry, "artifact": artifact_ref}
        entry = {key: value for key, value in entry.items() if key != "file"}
        assets.append(entry)
    return {**design_partial, "assets": assets}


def _media_type(path: Path) -> str:
    suffix = path.suffix.lstrip(".").lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "svg": "image/svg+xml",
        "webp": "image/webp",
        "ttf": "font/ttf",
        "otf": "font/otf",
    }.get(suffix, "application/octet-stream")


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
