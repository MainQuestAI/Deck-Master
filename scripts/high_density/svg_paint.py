from __future__ import annotations

import math
import re
from typing import Any
from xml.etree import ElementTree

from .contracts import ContractError


class SvgPaintError(ContractError):
    def __init__(self, message: str, *, element_id: str = "", code: str = "HD_SVG_UNSUPPORTED_STYLE") -> None:
        self.element_id = element_id
        self.code = code
        super().__init__(message)


_URL_RE = re.compile(r"^url\(#([A-Za-z_][A-Za-z0-9_.:-]*)\)$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFINITION_TAGS = {"linearGradient", "radialGradient", "filter", "symbol"}
_PRIMITIVE_TAGS = {"feDropShadow", "feGaussianBlur"}


def _tag(node: Any) -> str:
    return str(node.tag).split("}")[-1]


def _number(raw: Any, *, name: str, element_id: str, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(str(raw))
    except (TypeError, ValueError) as exc:
        raise SvgPaintError(f"SVG {name} is invalid on {element_id}", element_id=element_id) from exc
    if not math.isfinite(value) or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise SvgPaintError(f"SVG {name} is out of range on {element_id}", element_id=element_id)
    return value


def _normalized(raw: Any, *, name: str, element_id: str) -> float:
    text = str(raw if raw is not None else "0").strip()
    if text.endswith("%"):
        return _number(text[:-1], name=name, element_id=element_id, minimum=0, maximum=100) / 100
    return _number(text, name=name, element_id=element_id, minimum=0, maximum=1)


def _opacity(raw: Any, *, name: str, element_id: str, default: float = 1.0) -> float:
    if raw is None or str(raw).strip() == "":
        return default
    return _number(raw, name=name, element_id=element_id, minimum=0, maximum=1)


def _color(raw: Any, *, name: str, element_id: str, default: str = "#000000") -> str:
    value = str(raw or default).strip()
    if not _HEX_RE.fullmatch(value):
        raise SvgPaintError(f"SVG {name} must be a six-digit hex color on {element_id}", element_id=element_id)
    return value.lower()


def _reject_attrs(node: Any, allowed: set[str], *, element_id: str) -> None:
    for raw_name in node.attrib:
        name = str(raw_name).split("}")[-1]
        if name not in allowed:
            raise SvgPaintError(f"unsupported SVG property {name} on {element_id}", element_id=element_id, code="HD_SVG_UNSUPPORTED_PROPERTY")


def _gradient(node: Any) -> dict[str, Any]:
    gradient_id = str(node.get("id") or "")
    if not gradient_id:
        raise SvgPaintError("SVG gradient requires a stable id", code="HD_SVG_UNSUPPORTED_PROPERTY")
    common = {"id", "gradientUnits", "spreadMethod", "gradientTransform", "href", "xlink:href"}
    if _tag(node) == "linearGradient":
        allowed = common | {"x1", "y1", "x2", "y2"}
        _reject_attrs(node, allowed, element_id=gradient_id)
        if node.get("gradientUnits") not in {None, "objectBoundingBox"}:
            raise SvgPaintError(f"gradientUnits is unsupported on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        if node.get("spreadMethod") is not None or node.get("gradientTransform") is not None or node.get("href") is not None or node.get("{http://www.w3.org/1999/xlink}href") is not None:
            raise SvgPaintError(f"gradient inheritance or transform is unsupported on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        coordinates = {
            "x1": _normalized(node.get("x1", "0%"), name="x1", element_id=gradient_id),
            "y1": _normalized(node.get("y1", "0%"), name="y1", element_id=gradient_id),
            "x2": _normalized(node.get("x2", "100%"), name="x2", element_id=gradient_id),
            "y2": _normalized(node.get("y2", "0%"), name="y2", element_id=gradient_id),
        }
        gradient_type = "linear"
    else:
        allowed = common | {"cx", "cy", "r", "fx", "fy"}
        _reject_attrs(node, allowed, element_id=gradient_id)
        if node.get("gradientUnits") not in {None, "objectBoundingBox"}:
            raise SvgPaintError(f"gradientUnits is unsupported on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        if node.get("spreadMethod") is not None or node.get("gradientTransform") is not None or node.get("href") is not None or node.get("{http://www.w3.org/1999/xlink}href") is not None:
            raise SvgPaintError(f"gradient inheritance or transform is unsupported on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        coordinates = {
            "cx": _normalized(node.get("cx", "50%"), name="cx", element_id=gradient_id),
            "cy": _normalized(node.get("cy", "50%"), name="cy", element_id=gradient_id),
            "r": _normalized(node.get("r", "50%"), name="r", element_id=gradient_id),
            "fx": _normalized(node.get("fx", node.get("cx", "50%")), name="fx", element_id=gradient_id),
            "fy": _normalized(node.get("fy", node.get("cy", "50%")), name="fy", element_id=gradient_id),
        }
        gradient_type = "radial"
    stops: list[dict[str, Any]] = []
    last_offset = -1.0
    for stop in list(node):
        if _tag(stop) != "stop":
            raise SvgPaintError(f"unsupported gradient child on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        stop_id = f"{gradient_id}.stop.{len(stops) + 1}"
        _reject_attrs(stop, {"offset", "stop-color", "stop-opacity"}, element_id=stop_id)
        offset_raw = str(stop.get("offset") or "")
        offset = _normalized(offset_raw, name="offset", element_id=stop_id)
        if offset < last_offset:
            raise SvgPaintError(f"gradient stops must be ordered on {gradient_id}", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
        last_offset = offset
        stops.append({"offset": offset, "color": _color(stop.get("stop-color"), name="stop-color", element_id=stop_id), "opacity": _opacity(stop.get("stop-opacity"), name="stop-opacity", element_id=stop_id)})
    if not 2 <= len(stops) <= 8:
        raise SvgPaintError(f"gradient {gradient_id} must contain 2-8 direct stops", element_id=gradient_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
    angle = 0.0
    if gradient_type == "linear":
        angle = math.degrees(math.atan2(coordinates["y2"] - coordinates["y1"], coordinates["x2"] - coordinates["x1"])) % 360
    return {"kind": "gradient", "gradient_id": gradient_id, "gradient_type": gradient_type, "coordinates": coordinates, "stops": stops, "angle": angle, "fidelity": "native_normalized" if gradient_type == "linear" else "approximate"}


def _effect(node: Any) -> dict[str, Any]:
    effect_id = str(node.get("id") or "")
    if not effect_id:
        raise SvgPaintError("SVG filter requires a stable id", code="HD_SVG_UNSUPPORTED_PROPERTY")
    _reject_attrs(node, {"id"}, element_id=effect_id)
    children = list(node)
    if len(children) != 1 or _tag(children[0]) not in _PRIMITIVE_TAGS:
        raise SvgPaintError(f"filter {effect_id} must contain one supported primitive", element_id=effect_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
    primitive = children[0]
    primitive_tag = _tag(primitive)
    primitive_id = f"{effect_id}.{primitive_tag}"
    allowed = {"dx", "dy", "stdDeviation", "flood-color", "flood-opacity", "color", "opacity"}
    _reject_attrs(primitive, allowed, element_id=primitive_id)
    std_deviation = _number(primitive.get("stdDeviation", "0"), name="stdDeviation", element_id=primitive_id, minimum=0)
    dx = _number(primitive.get("dx", "0"), name="dx", element_id=primitive_id)
    dy = _number(primitive.get("dy", "0"), name="dy", element_id=primitive_id)
    color = _color(primitive.get("flood-color", primitive.get("color", "#000000")), name="flood-color", element_id=primitive_id)
    opacity = _opacity(primitive.get("flood-opacity", primitive.get("opacity")), name="flood-opacity", element_id=primitive_id, default=0.35)
    effect_type = "shadow" if abs(dx) > 0.0001 or abs(dy) > 0.0001 else "glow"
    return {"kind": effect_type, "effect_id": effect_id, "primitive": primitive_tag, "dx": dx, "dy": dy, "std_deviation": std_deviation, "color": color, "opacity": opacity, "fidelity": "native_normalized"}


def parse_svg_paint(root: ElementTree.Element) -> dict[str, Any]:
    definitions = [child for child in list(root) if _tag(child) == "defs"]
    if len(definitions) > 1:
        raise SvgPaintError("SVG must contain at most one direct defs block", code="HD_SVG_UNSUPPORTED_PROPERTY")
    gradients: dict[str, dict[str, Any]] = {}
    effects: dict[str, dict[str, Any]] = {}
    defs = definitions[0] if definitions else None
    if defs is not None:
        for child in list(defs):
            child_tag = _tag(child)
            if child_tag in {"linearGradient", "radialGradient"}:
                parsed = _gradient(child)
                gradients[str(parsed["gradient_id"])] = parsed
            elif child_tag == "filter":
                parsed = _effect(child)
                effects[str(parsed["effect_id"])] = parsed
            elif child_tag == "symbol":
                # Symbols are semantic definitions. Their leaf paint is
                # resolved by svg_native after local use expansion.
                continue
            else:
                raise SvgPaintError(f"unsupported direct defs element {child_tag}", code="HD_SVG_UNSUPPORTED_PROPERTY")
    for node in root.iter():
        if _tag(node) in _DEFINITION_TAGS and not (defs is not None and node in list(defs)):
            raise SvgPaintError(f"paint definition must be a direct child of defs: {node.get('id') or _tag(node)}", element_id=str(node.get("id") or ""), code="HD_SVG_UNSUPPORTED_PROPERTY")
    return {"gradients": gradients, "effects": effects}


def _paint_value(raw: Any, *, paint_name: str, element_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    value = str(raw or "").strip()
    if value.lower() in {"", "none", "transparent"}:
        return {"kind": "none"}
    match = _URL_RE.fullmatch(value)
    if match:
        gradient_id = match.group(1)
        gradient = (registry.get("gradients") or {}).get(gradient_id)
        if gradient is None:
            raise SvgPaintError(f"{paint_name} references unknown gradient {gradient_id} on {element_id}", element_id=element_id, code="HD_SVG_UNSUPPORTED_STYLE")
        return dict(gradient)
    if not _HEX_RE.fullmatch(value):
        raise SvgPaintError(f"SVG {paint_name} is outside the supported native palette on {element_id}", element_id=element_id)
    return {"kind": "solid", "color": value.lower(), "fidelity": "native"}


def parse_node_paint(node: Any, registry: dict[str, Any]) -> dict[str, Any]:
    element_id = str(node.get("id") or _tag(node))
    overall_opacity = _opacity(node.get("opacity"), name="opacity", element_id=element_id)
    filter_value = str(node.get("filter") or "").strip()
    effect = None
    if filter_value and filter_value.lower() not in {"none", "transparent"}:
        match = _URL_RE.fullmatch(filter_value)
        if not match:
            raise SvgPaintError(f"SVG filter must be a local URL on {element_id}", element_id=element_id)
        effect_id = match.group(1)
        effect = (registry.get("effects") or {}).get(effect_id)
        if effect is None:
            raise SvgPaintError(f"SVG filter references unknown effect {effect_id} on {element_id}", element_id=element_id)
        effect = dict(effect)
    return {
        "fill": _paint_value(node.get("fill"), paint_name="fill", element_id=element_id, registry=registry),
        "stroke": _paint_value(node.get("stroke"), paint_name="stroke", element_id=element_id, registry=registry),
        "opacity": overall_opacity,
        "fill_opacity": _opacity(node.get("fill-opacity"), name="fill-opacity", element_id=element_id),
        "stroke_opacity": _opacity(node.get("stroke-opacity"), name="stroke-opacity", element_id=element_id),
        "effect": effect,
    }


__all__ = ["SvgPaintError", "parse_node_paint", "parse_svg_paint"]
