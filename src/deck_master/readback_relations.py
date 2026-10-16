"""Located Page relationship checks on actual editable native text geometry.

Atom bindings locate text; they do not by themselves prove the table cell or
node owns that text. These checks consume native PPTX coordinates, so a later
conversion that moves a carrier is checked as well as the source SVG.
"""
from __future__ import annotations

import math
from collections import defaultdict

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
    angle = math.radians(int(transform.get('rot', '0')) / 60000)
    if angle:
        cx, cy = x + width / 2, y + height / 2
        width, height = (abs(width * math.cos(angle)) + abs(height * math.sin(angle)),
                         abs(width * math.sin(angle)) + abs(height * math.cos(angle)))
        x, y = cx - width / 2, cy - height / 2
    return {"x": x, "y": y, "width": width, "height": height,
            "cx": x + width / 2, "cy": y + height / 2}


def _inside(item, bounds):
    # Two EMUs account only for independently rounded native offsets/extents.
    epsilon = 2 / EMU_PER_PX
    left, top, right, bottom = bounds
    return (item['x'] >= left - epsilon and item['y'] >= top - epsilon
            and item['x'] + item['width'] <= right + epsilon
            and item['y'] + item['height'] <= bottom + epsilon)


def _table_grid(records, table_id, columns, rows, atoms, page_id, incomplete):
    """Recover a declared table's complete grid from actual native geometry.

    No text width/alignment is a column boundary. A tagged frame needs all
    full-span native rules and correctly located headers before it proves cell
    bounds. An absent/ambiguous grid is unverified, never an enlarged tolerance.
    """
    grids = set()
    for frame in records:
        if not frame.get('table_frame') or frame.get('table_id') != table_id:
            continue
        left, top = frame['x'], frame['y']
        right, bottom = left + frame['width'], top + frame['height']
        # Native emitters give a zero-width/height line a 0.01px extent.
        # This epsilon identifies coincident rules; it is not cell text slop.
        epsilon = .02
        vertical, horizontal = [], []
        for rule in records:
            if rule['kind'] != 'line':
                continue
            if (rule['width'] <= epsilon and left < rule['x'] < right
                    and abs(rule['y'] - top) <= epsilon
                    and abs(rule['height'] - frame['height']) <= epsilon):
                vertical.append(rule['x'])
            if (rule['height'] <= epsilon and top < rule['y'] < bottom
                    and abs(rule['x'] - left) <= epsilon
                    and abs(rule['width'] - frame['width']) <= epsilon):
                horizontal.append(rule['y'])
        if len(vertical) != len(columns) - 1 or len(horizontal) != len(rows):
            continue
        xs, ys = (left, *sorted(vertical), right), (top, *sorted(horizontal), bottom)
        if any(b - a <= epsilon for values in (xs, ys) for a, b in zip(values, values[1:])):
            continue
        valid = True
        for index, column in enumerate(columns):
            atom_id = f'atom:{page_id}:column:{table_id}:{column}:label'
            headers = atoms.get(atom_id, [])
            if (not headers or atom_id in incomplete
                    or any(not _inside(item, (xs[index], ys[0], xs[index + 1], ys[1])) for item in headers)):
                valid = False
                break
        if valid:
            grids.add((xs, ys))
    return next(iter(grids)) if len(grids) == 1 else None


def check_native_relations(root, source, page):
    shapes = defaultdict(list)
    for native in root.findall(".//p:sp", NS):
        identity = native.find("p:nvSpPr/p:cNvPr", NS)
        if identity is not None:
            shapes[identity.get("name")].append(native)
    originals = defaultdict(list)
    for original in source['shapes']:
        originals[original.get('atom_id') or original['id']].append(original)
    atoms = {}
    nodes = {}
    texts = []
    records = []
    incomplete = set()
    for name, group in originals.items():
        carriers = shapes.get(name, [])
        if len(carriers) != len(group):
            incomplete.add(name)
        # Both emitters preserve source order. Match occurrences, never reuse
        # the last same-named shape for every line of a multiline atom. Keep
        # extra native occurrences too; count/geometry gaps remain unverified.
        for index, native in enumerate(carriers):
            original = group[min(index, len(group) - 1)]
            geometry = _geometry(native)
            if geometry is None:
                incomplete.add(name)
                continue
            identity = native.find('p:nvSpPr/p:cNvPr', NS)
            record = {**geometry, 'element': original['id'], 'native_shape_id': identity.get('id'),
                      'node_ref': original.get('node_ref'), 'kind': original['kind'],
                      'table_id': original.get('table_id'), 'table_frame': original.get('table_frame')}
            records.append(record)
            if original['kind'] == 'text':
                record['text'] = ''.join(item.text or '' for item in native.findall('.//a:t', NS))
                texts.append(record)
            if original.get('atom_id'):
                atoms.setdefault(original['atom_id'], []).append(record)
            if original.get('node_ref'):
                nodes.setdefault(original['node_ref'], []).append(record)
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
        declared_grid = any(item.get('table_id') == table_id and item.get('table_frame')
                            for item in source['shapes'])
        grid = _table_grid(records, table_id, columns, rows, atoms, page_id, incomplete) if declared_grid else None
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
        for row_index, row in enumerate(rows):
            for cell in row["cells"]:
                column_id = cell["column_id"]
                atom_id = f"atom:{page_id}:cell:{table_id}:{row['id']}:{column_id}:display_text"
                carriers = atoms.get(atom_id, [])
                if (not carriers or atom_id in incomplete
                        or (declared_grid and grid is None)):
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx",
                                     "expected_carrier_count": len(originals.get(atom_id, [])),
                                     "actual_carrier_count": len(shapes.get(atom_id, [])),
                                     "native_shape_ids": [sp.find('p:nvSpPr/p:cNvPr', NS).get('id')
                                                          for sp in shapes.get(atom_id, [])],
                                     "native_carriers": [{key: item[key] for key in
                                         ('native_shape_id', 'element', 'x', 'y', 'width', 'height')}
                                         for item in carriers],
                                     "detail": 'missing/extra native carriers or insufficient table grid geometry'})
                    continue
                x, y = min(item["x"] for item in carriers), min(item["y"] for item in carriers)
                if grid is not None:
                    xs, ys = grid
                    column_index = columns.index(column_id)
                    bounds = (xs[column_index], ys[row_index + 1], xs[column_index + 1], ys[row_index + 2])
                    mismatch = any(not _inside(item, bounds) for item in carriers)
                else:
                    bounds = None
                    mismatch = any(abs(item['x'] - header_x.get(column_id, item['x'])) > tolerance_x
                                   or abs(item['y'] - row_y.get(row['id'], item['y'])) > tolerance_y
                                   for item in carriers)
                if column_id not in header_x or row["id"] not in row_y:
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx"})
                elif mismatch:
                    findings.append({"page_id": page_id, "code": "table_cell_ownership_mismatch",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "svg_elements": [item["element"] for item in carriers],
                                     "readback_layer": "native_pptx", "position": [x, y],
                                     "cell_bounds": bounds,
                                     "native_carriers": [{key: item[key] for key in
                                         ('native_shape_id', 'element', 'x', 'y', 'width', 'height')}
                                         for item in carriers],
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
