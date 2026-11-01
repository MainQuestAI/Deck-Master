from typing import Any

class NeedsNormalization(ValueError):
    pass

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

