from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_v2, read_json, sha256_json, utc_now, write_json

STYLE_DIR = Path("high_density_build/style")
STYLE_OPTIONS_PATH = STYLE_DIR / "style_options.json"
STYLE_LOCK_PATH = STYLE_DIR / "style_lock.json"


class StyleSelectionRequired(ContractError):
    def __init__(self, options_path: Path) -> None:
        self.options_path = options_path
        super().__init__(f"an approved high-density style lock is required; choose from {options_path.as_posix()}")


def _style(
    style_id: str,
    name: str,
    background: str,
    ink: str,
    accent: str,
    secondary: str,
    surface: str,
    *,
    grid: str,
    typography: str,
) -> dict[str, Any]:
    return {
        "style_id": style_id,
        "name": name,
        "source": "cyber-ppt-reference-registry",
        "palette": {
            "background": background,
            "ink": ink,
            "primary": accent,
            "secondary": secondary,
            "surface": surface,
            "muted": "#657485",
            "line": "#d5dde5",
        },
        "grid": {"canvas": {"width": 1672, "height": 941, "unit": "px", "ratio": "16:9"}, "safe_area": {"x": 80, "y": 48, "w": 1512, "h": 845}, "system": grid},
        "typography": {"family": typography, "title_px": 42, "body_px": 18, "caption_px": 12, "numeric_px": 30, "line_height": 1.18},
        "chart_language": {"primary": accent, "secondary": secondary, "axis": "hairline", "labels": "native_text"},
        "table_language": {"header": accent, "row_rule": "hairline", "cell_padding_px": 14},
        "surface_system": {"background": background, "card": surface, "header": ink, "footer": "muted", "radius_px": 8},
        "density_rules": {"minimum_information_regions": 3, "minimum_required_components": 3, "avoid_empty_hero_space": True, "preserve_safe_area": True},
        "prohibitions": ["page numbers", "internal labels", "prompt labels", "wireframe labels", "generation annotations", "hidden production notes"],
    }


CYBER_PPT_STYLES: tuple[dict[str, Any], ...] = (
    _style("cyber-01", "Ink Cobalt", "#f7f9fb", "#18212b", "#419BFD", "#d96b3b", "#ffffff", grid="12-column consulting grid", typography="Arial"),
    _style("cyber-02", "Midnight Signal", "#101722", "#f7f9fb", "#66b7ff", "#ffb26b", "#1b2735", grid="dark editorial grid", typography="Arial"),
    _style("cyber-03", "Paper Mint", "#f3f7f1", "#17332b", "#2f8f83", "#e28b4b", "#ffffff", grid="modular evidence grid", typography="Arial"),
    _style("cyber-04", "Cobalt Ledger", "#eef5fb", "#17324d", "#1f6fd1", "#c65c42", "#ffffff", grid="comparison matrix grid", typography="Arial"),
    _style("cyber-05", "Copper Brief", "#fff7ef", "#3b2720", "#c65c42", "#3d91c9", "#ffffff", grid="storyline rail grid", typography="Arial"),
    _style("cyber-06", "Graphite Mint", "#edf2ef", "#202b2a", "#3d8f78", "#3c78b5", "#ffffff", grid="architecture flow grid", typography="Arial"),
    _style("cyber-07", "Blue Whiteboard", "#f5f8ff", "#1c2d52", "#3c71c7", "#d57d42", "#ffffff", grid="diagram canvas grid", typography="Arial"),
    _style("cyber-08", "Warm Signal", "#fbf4ed", "#30251f", "#d27a43", "#4f8da8", "#ffffff", grid="dense narrative grid", typography="Arial"),
)


def style_options() -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in CYBER_PPT_STYLES]


def write_style_options(root: Path) -> Path:
    path = root / STYLE_OPTIONS_PATH
    write_json(path, {"schema_version": "deck_style_options.v1", "styles": style_options(), "created_at": utc_now()})
    return path


def _lock_from_style(root: Path, run_id: str, style: dict[str, Any], *, approved: bool, approver: str = "") -> dict[str, Any]:
    lock = {
        "schema_version": "deck_high_density_style_lock.v1",
        "run_id": run_id,
        **copy.deepcopy(style),
        "approval": {"approver": approver or "unavailable", "source": "explicit_style_selection" if approver else "fixture_default"},
        "approved": approved,
        "created_at": utc_now(),
    }
    lock["style_lock_sha256"] = sha256_json({key: value for key, value in lock.items() if key not in {"style_lock_sha256", "created_at", "updated_at"}})
    assert_v2("style_lock", lock)
    return lock


def write_style_lock(root: Path, run_id: str, style_id: str = "cyber-01", *, approved: bool = True, approver: str = "") -> Path:
    selected = next((item for item in CYBER_PPT_STYLES if item["style_id"] == style_id), None)
    if selected is None:
        raise ContractError(f"unknown high-density style id: {style_id}")
    path = root / STYLE_LOCK_PATH
    write_json(path, _lock_from_style(root, run_id, selected, approved=approved, approver=approver))
    return path


def load_style_lock(root: Path, *, require_approved: bool = True, expected_run_id: str | None = None) -> dict[str, Any]:
    path = root / STYLE_LOCK_PATH
    if not path.exists():
        raise StyleSelectionRequired(root / STYLE_OPTIONS_PATH)
    lock = read_json(path)
    assert_v2("style_lock", lock)
    selected = next((item for item in CYBER_PPT_STYLES if item["style_id"] == lock.get("style_id")), None)
    if selected is None:
        raise ContractError(f"style lock must select one of the fixed CyberPPT styles: {lock.get('style_id')}")
    for key in ("style_id", "name", "source", "palette", "grid", "typography", "chart_language", "table_language", "surface_system", "density_rules", "prohibitions"):
        if lock.get(key) != selected.get(key):
            raise ContractError(f"style lock does not match the registered style: {lock.get('style_id')}")
    if expected_run_id and str(lock.get("run_id") or "") != expected_run_id:
        raise ContractError(f"style lock run_id mismatch: expected {expected_run_id}")
    if require_approved and lock.get("approved") is not True:
        raise StyleSelectionRequired(root / STYLE_OPTIONS_PATH)
    expected = sha256_json({key: value for key, value in lock.items() if key not in {"style_lock_sha256", "created_at", "updated_at"}})
    if lock.get("style_lock_sha256") != expected:
        raise ContractError("style lock hash is stale")
    return lock


def ensure_style_lock(root: Path, run_id: str, *, mode: str, style_id: str | None = None, approver: str = "") -> dict[str, Any]:
    if (root / STYLE_LOCK_PATH).exists():
        return load_style_lock(root, require_approved=True, expected_run_id=run_id)
    write_style_options(root)
    if style_id:
        write_style_lock(root, run_id, style_id, approved=True, approver=approver)
        return load_style_lock(root, expected_run_id=run_id)
    if mode in {"fixture", "dev"}:
        write_style_lock(root, run_id, "cyber-01", approved=True)
        return load_style_lock(root, expected_run_id=run_id)
    raise StyleSelectionRequired(root / STYLE_OPTIONS_PATH)


__all__ = [
    "CYBER_PPT_STYLES",
    "STYLE_DIR",
    "STYLE_LOCK_PATH",
    "STYLE_OPTIONS_PATH",
    "StyleSelectionRequired",
    "ensure_style_lock",
    "load_style_lock",
    "style_options",
    "write_style_lock",
    "write_style_options",
]
