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

    def collect_text_items(kind: str, items: list, path: list, parent: str = "") -> None:
        for index, item in enumerate(items):
            fallback = f"{parent}-child-{index + 1}" if parent else f"{kind}-{index + 1}"
            stable_id = _stable_id(item, fallback)
            item_path = [*path, index]
            if item.get("text") is not None:
                push(kind, _atom_id(page_id, kind, stable_id, "text"),
                     _pointer("customer_visible", *item_path, "text"), item["text"])
            collect_text_items(kind, item.get("children") or [],
                               [*item_path, "children"], stable_id)

    for group, kind in (("labels", "label"), ("footnotes", "footnote"), ("callouts", "callout")):
        collect_text_items(kind, visible.get(group) or [], [group])
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
    if block.get("title"):
        atoms.append({
            "atom_id": _atom_id(page_id, "table", table_id, "title"),
            "pointer": _pointer("customer_visible", "body_blocks", block_index, "title"),
            "text": block["title"],
            "kind": "table_title",
        })
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


def column_cell_ids(page: dict) -> dict[str, list[str]]:
    """Map each column-label atom to the cell atoms of that column.

    Plan checks use the grouping to tell one leftover column name from a label
    that titles a single column. The ids are the same strings visible_atoms emits.
    """
    page_id = page["page_id"]
    visible = page.get("customer_visible") or {}
    groups: dict[str, list[str]] = {}
    for block_index, block in enumerate(visible.get("body_blocks") or []):
        if block.get("type") != "table":
            continue
        table_id = _stable_id(block, f"table-{block_index + 1}")
        for column_index, column in enumerate(block.get("columns") or []):
            column_id = _stable_id(column, f"col-{column_index + 1}")
            groups[_atom_id(page_id, "column", f"{table_id}:{column_id}", "label")] = []
        for row_index, row in enumerate(block.get("rows") or []):
            row_id = _stable_id(row, f"row-{row_index + 1}")
            for cell_index, cell in enumerate(row.get("cells") or []):
                column_id = cell.get("column_id") or f"col-{cell_index + 1}"
                label_id = _atom_id(page_id, "column", f"{table_id}:{column_id}", "label")
                cell_id = _atom_id(
                    page_id, "cell", f"{table_id}:{row_id}:{column_id}", "display_text"
                )
                groups.setdefault(label_id, []).append(cell_id)
    return groups

