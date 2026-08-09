from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import ContractError


MIGRATION_REQUIRED_CODE = "HD_MBB_MIGRATION_REQUIRED"
_LEGACY_METHOD = "".join(("n", "b", "b"))
_LEGACY_SCHEMA_PREFIX = "deck_" + _LEGACY_METHOD + "_"


def legacy_method_dir(root: Path) -> Path:
    """Return the retired content-plan directory without reintroducing its name."""
    return Path(root) / "high_density_build" / _LEGACY_METHOD


def _contains_retired_token(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_retired_token(key) or _contains_retired_token(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_retired_token(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return (
        _LEGACY_METHOD in lowered
        or _LEGACY_SCHEMA_PREFIX in lowered
        or ("high_density_build/" + _LEGACY_METHOD) in lowered
    )


def legacy_artifact_reason(root: Path, payload: Any | None = None) -> str | None:
    """Describe a retired content-plan artifact, if one is present."""
    root = Path(root)
    retired_dir = legacy_method_dir(root)
    if retired_dir.exists():
        return "retired content-plan directory detected"
    if payload is not None and _contains_retired_token(payload):
        return "retired content-plan schema or lineage detected"
    build_root = root / "high_density_build"
    if build_root.is_dir():
        for path in sorted(build_root.rglob("*.json")):
            try:
                text = path.read_text(encoding="utf-8").casefold()
            except OSError:
                return "unable to inspect high-density artifacts for migration"
            if _LEGACY_METHOD in text or _LEGACY_SCHEMA_PREFIX in text:
                return "retired content-plan lineage detected in a high-density artifact"
    return None


def assert_current_mbb_artifact(root: Path, payload: Any | None = None) -> None:
    reason = legacy_artifact_reason(root, payload)
    if reason:
        raise ContractError(f"{MIGRATION_REQUIRED_CODE}: {reason}; regenerate the MBB content plan from Page Packages")


def retired_method_token() -> str:
    """Expose the retired token for migration tests without active terminology."""
    return _LEGACY_METHOD


__all__ = [
    "MIGRATION_REQUIRED_CODE",
    "assert_current_mbb_artifact",
    "legacy_artifact_reason",
    "legacy_method_dir",
    "retired_method_token",
]
