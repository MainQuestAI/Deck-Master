"""SC-1.1 ND-02: build route resolution.

A fixed, request-bound route record (spec 02 §2.2): engine_id,
authoring_mode, density, library_mode and origin_run_mode are decided once
per run/build and stored with the request. New runs default to the built-in
native engine; legacy profiles map with explicit compatibility notes; only
an explicit legacy-ppt-master route ever consults the external backend
binding.
"""

from __future__ import annotations

from typing import Any

ROUTE_SCHEMA_VERSION = "deck_build_route.v1"
ENGINES = {"deck_native", "legacy_ppt_master"}
AUTHORING_MODES = {"image_blueprint", "direct_svg"}
DENSITIES = {"standard", "high"}


def resolve_build_route(request: dict[str, Any]) -> dict[str, Any]:
    """Resolve the engine route for a request.

    New runs (no profile) default to deck_native + image_blueprint. The old
    ``standard`` profile maps to native with a one-time compatibility note;
    ``high-density`` maps to native with density=high (no separate backend).
    ``legacy-ppt-master`` is an explicit compatibility route only — it never
    becomes a default and its readiness checks are the only consumers of the
    external binding.
    """

    profile = str((request or {}).get("profile") or "").strip().lower().replace("_", "-")
    route: dict[str, Any] = {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "engine_id": "deck_native",
        "authoring_mode": "image_blueprint",
        "density": "standard",
        "library_mode": str((request or {}).get("library_mode") or "auto"),
        "origin_run_mode": str((request or {}).get("run_mode") or "production"),
    }
    if profile == "legacy-ppt-master" or profile == "legacy_ppt_master":
        route["engine_id"] = "legacy_ppt_master"
        return route
    if profile == "high-density" or profile == "high_density":
        route["density"] = "high"
        return route
    if profile == "standard":
        route["compatibility_note"] = (
            "profile 'standard' now maps to the built-in deck_native engine; "
            "the external PPT Master default backend was retired by SC-1.1"
        )
        return route
    if profile in {"", "native"}:
        return route
    if profile == "direct-svg":
        route["authoring_mode"] = "direct_svg"
        return route
    raise ValueError(f"unknown build profile: {profile!r}")


def is_native(route: dict[str, Any]) -> bool:
    return str(route.get("engine_id") or "") == "deck_native"
