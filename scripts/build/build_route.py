"""SC-1.1 ND-02: build route resolution and persistence.

A fixed, request-bound route record (spec 02 §2.2): engine_id,
authoring_mode, density, library_mode and origin_run_mode are decided ONCE
per run and persisted at `build/route.json` (deck_build_route.v1). Later
request changes (stale profile flags) never re-route an existing run. New
runs default to the built-in native engine; legacy profiles map with
explicit compatibility notes; only an explicit legacy-ppt-master route (or
an old run's recorded traces) ever consults the external backend binding.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROUTE_SCHEMA_VERSION = "deck_build_route.v1"
ROUTE_PATH = Path("build") / "route.json"
ENGINES = {"deck_native", "legacy_ppt_master"}
AUTHORING_MODES = {"image_blueprint", "direct_svg"}
DENSITIES = {"standard", "high"}


def _normalize(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def load_persisted_route(run_dir: str | Path) -> dict[str, Any]:
    """Return the persisted route record, or {} when none exists."""

    path = Path(run_dir).expanduser().resolve() / ROUTE_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema_version") != ROUTE_SCHEMA_VERSION:
        return {}
    return payload


def persist_route(run_dir: str | Path, route: dict[str, Any]) -> dict[str, Any]:
    """Persist the fixed route for a run. First write wins: an existing
    persisted route is returned unchanged (never silently re-routed)."""

    root = Path(run_dir).expanduser().resolve()
    existing = load_persisted_route(root)
    if existing:
        return existing
    payload = dict(route)
    payload["schema_version"] = ROUTE_SCHEMA_VERSION
    path = root / ROUTE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def _derive_route(request: dict[str, Any], run_dir: Path | None) -> dict[str, Any]:
    profile = _normalize((request or {}).get("profile")).replace("_", "-")
    route: dict[str, Any] = {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "engine_id": "deck_native",
        "authoring_mode": "image_blueprint",
        "density": "standard",
        "library_mode": str((request or {}).get("library_mode") or "auto"),
        "origin_run_mode": str((request or {}).get("run_mode") or "production"),
    }
    authoring = _normalize((request or {}).get("authoring_mode"))
    if authoring:
        if authoring not in AUTHORING_MODES:
            raise ValueError(f"unknown authoring_mode: {authoring!r}")
        route["authoring_mode"] = authoring

    if profile == "legacy-ppt-master":
        route["engine_id"] = "legacy_ppt_master"
        return route
    if profile == "high-density":
        route["density"] = "high"
        return route
    if profile == "standard":
        route["compatibility_note"] = (
            "profile 'standard' now maps to the built-in deck_native engine; "
            "the external PPT Master default backend was retired by SC-1.1"
        )
        return route
    if profile in {"", "native"}:
        # Old-run continuation: no persisted route + HD traces -> the run
        # keeps its density profile on the same native kernel.
        if run_dir is not None and (run_dir / "high_density_build" / "status.json").exists():
            route["density"] = "high"
        return route
    if profile == "direct-svg":
        route["authoring_mode"] = "direct_svg"
        return route
    raise ValueError(f"unknown build profile: {profile!r}")


def resolve_build_route(request: dict[str, Any], *, run_dir: str | Path | None = None) -> dict[str, Any]:
    """Resolve the engine route for a run.

    The persisted route (if any) wins — the route is fixed once per run.
    Otherwise it is derived from the request (new runs default to
    deck_native + image_blueprint) and may be persisted by the caller.
    """

    root = Path(run_dir).expanduser().resolve() if run_dir is not None else None
    if root is not None:
        persisted = load_persisted_route(root)
        if persisted:
            return persisted
    return _derive_route(request, root)


def is_native(route: dict[str, Any]) -> bool:
    return str(route.get("engine_id") or "") == "deck_native"
