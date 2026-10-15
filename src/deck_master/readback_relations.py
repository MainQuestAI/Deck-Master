"""Located Page relationship checks on actual editable native text geometry.

Atom bindings locate text; they do not by themselves prove the table cell or
node owns that text. These checks consume native PPTX coordinates, so a later
conversion that moves a carrier is checked as well as the source SVG.
"""
from __future__ import annotations

import math

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
EMU_PER_PX = 9525


def _geometry(shape):
    transform = shape.find("p:spPr/a:xfrm", NS)
    if transform is None:
        return None
    offset, extent = transform.find("a:off", NS), transform.find("a:ext", NS)
    if offset is None or extent is None:
        return None
    x, y = int(offset.get("x")) / EMU_PER_PX, int(offset.get("y")) / EMU_PER_PX
    width, height = int(extent.get("cx")) / EMU_PER_PX, int(extent.get("cy")) / EMU_PER_PX
    return {"x": x, "y": y, "width": width, "height": height,
            "cx": x + width / 2, "cy": y + height / 2}


def check_native_relations(root, source, page):
    shapes = {}
    for native in root.findall(".//p:sp", NS):
        identity = native.find("p:nvSpPr/p:cNvPr", NS)
        if identity is not None:
            shapes[identity.get("name")] = native
    atoms = {}
    nodes = {}
    texts = []
    for original in source["shapes"]:
        name = original.get("atom_id") or original["id"]
        native = shapes.get(name)
        geometry = _geometry(native) if native is not None else None
        if geometry is None:
            continue
        record = {**geometry, "element": original["id"], "node_ref": original.get("node_ref"),
                  "kind": original["kind"]}
        if original["kind"] == "text":
            record["text"] = "".join(item.text or "" for item in native.findall(".//a:t", NS))
            texts.append(record)
        if original.get("atom_id"):
            atoms.setdefault(original["atom_id"], []).append(record)
        if original.get("node_ref"):
            nodes.setdefault(original["node_ref"], []).append(record)
    findings = []
    page_id = page["page_id"]
    from .content import visible_atoms
    for atom in visible_atoms(page):
        if atom["atom_id"] not in atoms and atom.get("text"):
            matching = [record for record in texts if record["text"] == atom["text"]]
            if len(matching) == 1:
                atoms[atom["atom_id"]] = matching
    for table_index, table in enumerate(page["customer_visible"].get("body_blocks", [])):
        if table["type"] != "table" or not table.get("columns") or not table.get("rows"):
            continue
        table_id = table.get("id") or f"table-{table_index + 1}"
        columns = [column.get("id") or f"col-{index + 1}" for index, column in enumerate(table["columns"])]
        rows = [{**row, "id": row.get("id") or f"row-{index + 1}"}
                for index, row in enumerate(table["rows"])]
        header_x = {}
        for column_id in columns:
            carriers = atoms.get(f"atom:{page_id}:column:{table_id}:{column_id}:label", [])
            if carriers:
                header_x[column_id] = min(item["x"] for item in carriers)
        row_y = {}
        key_column = columns[0]
        for row in rows:
            carriers = atoms.get(f"atom:{page_id}:cell:{table_id}:{row['id']}:{key_column}:display_text", [])
            if carriers:
                row_y[row["id"]] = min(item["y"] for item in carriers)
        gaps_x = [abs(first - second) for index, first in enumerate(header_x.values())
                  for second in list(header_x.values())[index + 1:] if abs(first - second) > 1]
        gaps_y = [abs(first - second) for index, first in enumerate(row_y.values())
                  for second in list(row_y.values())[index + 1:] if abs(first - second) > 1]
        tolerance_x = min(gaps_x) / 2 if gaps_x else float("inf")
        tolerance_y = min(gaps_y) / 2 if gaps_y else float("inf")
        for row in rows:
            for cell in row["cells"]:
                column_id = cell["column_id"]
                atom_id = f"atom:{page_id}:cell:{table_id}:{row['id']}:{column_id}:display_text"
                carriers = atoms.get(atom_id, [])
                if not carriers:
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx"})
                    continue
                x, y = min(item["x"] for item in carriers), min(item["y"] for item in carriers)
                if column_id not in header_x or row["id"] not in row_y:
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx"})
                elif (abs(x - header_x[column_id]) > tolerance_x
                      or abs(y - row_y[row["id"]]) > tolerance_y):
                    findings.append({"page_id": page_id, "code": "table_cell_ownership_mismatch",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "svg_elements": [item["element"] for item in carriers],
                                     "readback_layer": "native_pptx", "position": [x, y],
                                     "expected_column_x": header_x[column_id], "expected_row_y": row_y[row["id"]]})
    centers = {}
    for node_id, carriers in nodes.items():
        # A declared native node container anchors geometry; text-only nodes
        # use their label, never a stray responsibility to widen ownership.
        containers = [item for item in carriers if item["kind"] != "text"]
        selected = max(containers, key=lambda item: item["width"] * item["height"]) if containers else None
        if selected is not None:
            centers[node_id] = (selected["cx"], selected["cy"])
    for node in page.get("visual_spec", {}).get("nodes", []):
        node_id = node["node_id"]
        if node_id not in centers:
            label = atoms.get(node.get("label_ref"), [])
            if label:
                centers[node_id] = (label[0]["cx"], label[0]["cy"])
    for node in page.get("visual_spec", {}).get("nodes", []):
        node_id = node["node_id"]
        for atom_id in [node.get("label_ref"), *(node.get("responsibility_refs") or [])]:
            for carrier in atoms.get(atom_id, []):
                assigned = carrier["node_ref"]
                wrong_label = assigned is not None and assigned != node_id
                point = (carrier["cx"], carrier["cy"])
                own = centers.get(node_id)
                nearest = min(centers, key=lambda key: math.dist(point, centers[key])) if centers else None
                wrong_geometry = (own is not None and nearest is not None and nearest != node_id
                                  and math.dist(point, centers[nearest]) + 8 < math.dist(point, own))
                if wrong_label or wrong_geometry:
                    findings.append({"page_id": page_id, "code": "node_atom_ownership_mismatch",
                                     "atom_id": atom_id, "node_id": node_id,
                                     "actual_node_id": assigned if wrong_label else nearest,
                                     "svg_elements": [carrier["element"]], "readback_layer": "native_pptx"})
    return findings
