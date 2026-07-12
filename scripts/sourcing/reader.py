"""Read sourcing plans through one canonical v2 shape."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .plan import SCHEMA_VERSION, migrate_v1


def canonicalize_sourcing_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("sourcing plan must be an object")
    if payload.get("schema_version") == SCHEMA_VERSION and isinstance(payload.get("pages"), list):
        return copy.deepcopy(payload)
    if isinstance(payload.get("decisions"), list):
        return migrate_v1(payload)
    raise ValueError("sourcing plan must contain v2 pages[] or legacy v1 decisions[]")


def read_sourcing_plan(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    return canonicalize_sourcing_plan(payload)


__all__ = ["canonicalize_sourcing_plan", "read_sourcing_plan"]
