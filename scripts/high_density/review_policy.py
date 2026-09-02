"""Resolve the two independent dimensions of visual review policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import ContractError, read_json

REVIEW_DEPTHS = frozenset({"producer_only", "independent_main"})
RECEIPT_POLICIES = frozenset({"local_traceable", "external_signed"})


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def resolve_review_policy(request: Mapping[str, Any] | None) -> dict[str, str]:
    """Return canonical review dimensions while preserving the legacy flag."""
    payload = request or {}
    legacy = _normalized(payload.get("review_policy"))
    depth = _normalized(payload.get("review_depth"))
    receipt = _normalized(payload.get("receipt_policy"))

    if depth not in REVIEW_DEPTHS:
        depth = ""
    if receipt not in RECEIPT_POLICIES:
        receipt = ""

    if not depth and not receipt:
        if legacy == "external_signed":
            depth, receipt = "independent_main", "external_signed"
        else:
            depth, receipt = "producer_only", "local_traceable"
    else:
        depth = depth or ("independent_main" if legacy == "external_signed" else "producer_only")
        receipt = receipt or ("external_signed" if legacy == "external_signed" else "local_traceable")

    # An external receipt attests an independent main review by definition.
    if receipt == "external_signed":
        depth = "independent_main"

    return {
        "review_depth": depth,
        "receipt_policy": receipt,
        "legacy_review_policy": legacy or ("external_signed" if receipt == "external_signed" else "local_traceable"),
    }


def load_review_policy(root: Path) -> dict[str, str]:
    try:
        request = read_json(root / "request.json")
    except ContractError:
        request = {}
    return resolve_review_policy(request)


__all__ = [
    "RECEIPT_POLICIES",
    "REVIEW_DEPTHS",
    "load_review_policy",
    "resolve_review_policy",
]
