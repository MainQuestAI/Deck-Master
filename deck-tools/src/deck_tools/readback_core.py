"""Shared OOXML readback primitives used by both SVG and native pipelines."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

DRAWING_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def normalize_text(value: object) -> str:
    return "".join(str(value).split())


def slide_text_objects(root: Any, *, merge_same_atom: bool = False) -> list[str]:
    """Return one whitespace-collapsed string per shape or table cell.

    Runs inside a single shape or cell stay together, while separate shapes
    and cells are never concatenated into one string. When ``merge_same_atom``
    is True (used by SVG readback), shapes sharing the same ``atom:`` cNvPr
    name are merged so multi-line SVG text elements for one atom stay united.
    """
    objects: list[str] = []
    atom_slots: dict[str, int] = {}
    for sp in root.findall(".//p:sp", DRAWING_NS):
        parts = [node.text or "" for node in sp.findall(".//a:t", DRAWING_NS)]
        collapsed = "".join("".join(parts).split())
        if not collapsed:
            continue
        if merge_same_atom:
            cnvpr = sp.find("p:nvSpPr/p:cNvPr", DRAWING_NS)
            name = cnvpr.get("name") if cnvpr is not None else None
            if name and name.startswith("atom:"):
                slot = atom_slots.get(name)
                if slot is not None:
                    objects[slot] += collapsed
                    continue
                atom_slots[name] = len(objects)
        objects.append(collapsed)
    for tc in root.findall(".//a:tc", DRAWING_NS):
        parts = [node.text or "" for node in tc.findall(".//a:t", DRAWING_NS)]
        collapsed = "".join("".join(parts).split())
        if collapsed:
            objects.append(collapsed)
    return objects


def take_span(text: str, mask: bytearray, needle: str) -> bool:
    length = len(needle)
    start = 0
    while start <= len(text) - length:
        index = text.find(needle, start)
        if index < 0:
            return False
        if any(mask[index : index + length]):
            start = index + 1
            continue
        for offset in range(length):
            mask[index + offset] = 1
        return True
    return False


def _take_split_span(objects: Sequence[str], masks: Sequence[bytearray], needle: str) -> bool:
    """Allow one SVG atom split across consecutive unconsumed text shapes."""
    count = len(objects)
    for start in range(count):
        if not objects[start] or any(masks[start]):
            continue
        combined = []
        length = 0
        for end in range(start, count):
            if any(masks[end]):
                break
            combined.append(objects[end])
            length += len(objects[end])
            if end > start and length >= len(needle):
                joined = "".join(combined)
                pos = joined.find(needle)
                if pos >= 0:
                    cursor = 0
                    span_end = pos + len(needle)
                    for idx in range(start, end + 1):
                        piece_len = len(objects[idx])
                        overlap_lo = max(0, pos - cursor)
                        overlap_hi = min(piece_len, span_end - cursor)
                        for offset in range(overlap_lo, overlap_hi):
                            masks[idx][offset] = 1
                        cursor += piece_len
                    return True
                if length > len(needle) * 2:
                    break
    return False


def missing_visible_atoms(
    objects: Sequence[str],
    atoms: Iterable[dict[str, Any]],
    *,
    allow_split_spans: bool = False,
) -> list[dict[str, Any]]:
    """Consume each expected visible atom within one slide text object or cell.

    Longest atom first, so a short atom is reported missing when its only copy
    sits inside a longer atom on the slide. Separate objects are never merged
    by default, and matched spans are masked rather than removed so bridging
    two fragments cannot fabricate a non-existent string.
    """
    masks = [bytearray(len(text)) for text in objects]
    missing: list[dict[str, Any]] = []
    needles: list[tuple[str, dict[str, Any]]] = []
    for atom in atoms:
        raw = atom.get("text")
        if not raw:
            continue
        needle = normalize_text(raw)
        if needle:
            needles.append((needle, atom))
    needles.sort(key=lambda item: len(item[0]), reverse=True)
    for needle, atom in needles:
        if any(take_span(text, mask, needle) for text, mask in zip(objects, masks)):
            continue
        if allow_split_spans and _take_split_span(objects, masks, needle):
            continue
        missing.append(atom)
    return missing


def check_notes_and_count(
    actual_notes: Sequence[dict[str, Any]],
    expected_pages: Sequence[tuple[str, str]],
    *,
    normalize_notes,
    include_svg_inputs: int | None = None,
) -> list[dict[str, Any]]:
    """Verify slide count, page identity in notes, and speaker notes parity."""
    findings: list[dict[str, Any]] = []
    if len(actual_notes) != len(expected_pages) or (
        include_svg_inputs is not None and include_svg_inputs != len(expected_pages)
    ):
        record: dict[str, Any] = {
            "code": "slide_count_mismatch",
            "actual": len(actual_notes),
            "expected": len(expected_pages),
        }
        if include_svg_inputs is not None:
            record["svg_inputs"] = include_svg_inputs
        findings.append(record)
    for actual, (page_id, expected_notes) in zip(actual_notes, expected_pages):
        if actual["page_id"] != page_id:
            findings.append({"page_id": page_id, "code": "notes_page_identity_mismatch"})
        if actual["notes"] != normalize_notes(expected_notes):
            findings.append({"page_id": page_id, "code": "speaker_notes_mismatch"})
    return findings


def check_shapes_outside_slide(
    root: Any,
    page_id: str,
    slide_cx: int,
    slide_cy: int,
) -> list[dict[str, Any]]:
    """Report any shape or table graphicFrame whose transform leaves slide bounds."""
    findings: list[dict[str, Any]] = []
    carriers = [
        (sp.find("p:nvSpPr/p:cNvPr", DRAWING_NS), sp.find("p:spPr/a:xfrm", DRAWING_NS))
        for sp in root.findall(".//p:sp", DRAWING_NS)
    ]
    carriers.extend(
        (graphic.find("p:nvGraphicFramePr/p:cNvPr", DRAWING_NS), graphic.find("p:xfrm", DRAWING_NS))
        for graphic in root.findall(".//p:graphicFrame", DRAWING_NS)
    )
    for name_node, xfrm in carriers:
        if name_node is None or xfrm is None:
            continue
        off = xfrm.find("a:off", DRAWING_NS)
        ext = xfrm.find("a:ext", DRAWING_NS)
        if off is None or ext is None:
            continue
        x = int(off.get("x"))
        y = int(off.get("y"))
        w = int(ext.get("cx"))
        h = int(ext.get("cy"))
        if x < 0 or y < 0 or x + w > slide_cx or y + h > slide_cy:
            findings.append(
                {
                    "page_id": page_id,
                    "code": "shape_outside_slide",
                    "element": name_node.get("name"),
                    "bounds": [x, y, w, h],
                    "slide": [slide_cx, slide_cy],
                }
            )
    return findings
