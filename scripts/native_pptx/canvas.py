"""Native canvas constants and asset dimension probing (SC-1.1 ND-01).

Single source of the HD/native canvas geometry, re-exported by the
high-density blueprint module for compatibility. Helper bodies are moved
verbatim from high_density/blueprint.py — one implementation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import ContractError


CANVAS_WIDTH = 1672
CANVAS_HEIGHT = 941
CANVAS_RATIO = CANVAS_WIDTH / CANVAS_HEIGHT


class BlueprintInvalid(ContractError):
    """Raised when a blueprint image's dimensions cannot be read."""


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    head = path.read_text(encoding="utf-8", errors="ignore")[:8192]
    viewbox = re.search(r"viewBox\s*=\s*[\"']\s*[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", head)
    if viewbox:
        return round(float(viewbox.group(1))), round(float(viewbox.group(2)))
    width = re.search(r"width\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    height = re.search(r"height\s*=\s*[\"'](\d+(?:\.\d+)?)", head)
    if width and height:
        return round(float(width.group(1))), round(float(height.group(1)))
    return None


def image_dimensions(path: Path) -> tuple[int, int]:
    dimensions = _png_dimensions(path) if path.suffix.lower() == ".png" else _svg_dimensions(path) if path.suffix.lower() == ".svg" else None
    if dimensions is None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                dimensions = image.size
        except Exception as exc:  # pragma: no cover - provider format path
            raise BlueprintInvalid(f"cannot read blueprint dimensions: {path}") from exc
    if dimensions[0] <= 0 or dimensions[1] <= 0:
        raise BlueprintInvalid(f"blueprint dimensions must be positive: {path}")
    return dimensions
