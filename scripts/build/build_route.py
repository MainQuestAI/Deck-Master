"""Request-bound native routing, with explicit legacy continuation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROUTE_SCHEMA_VERSION = "deck_build_route.v1"
ROUTE_PATH = Path("build/route.json")
ENGINES = {"deck_native", "legacy_ppt_master"}
AUTHORING_MODES = {"image_blueprint", "direct_svg"}
DENSITIES = {"standard", "high"}


def _normalize(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def validate_route(route: dict) -> dict:
    from jsonschema import Draft202012Validator
    from native_pptx.contracts import SCHEMA_DIR
    schema = SCHEMA_DIR / "build-route.v1.schema.json"
    Draft202012Validator(json.loads(schema.read_text())).validate(route)
    return route


def load_persisted_route(run_dir: str | Path) -> dict[str, Any]:
    from workflow.actions import read_current_revision, read_revision_state
    root = Path(run_dir).expanduser().resolve()
    if read_current_revision(root).get("revision_id"):
        raw = read_revision_state(root).get(ROUTE_PATH.as_posix())
        if raw is None:
            return {}
        payload = json.loads(raw)
    else:
        path = root / ROUTE_PATH
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    # Older PR31 route records are readable; never manufacture selection approval.
    if payload.get("schema_version") != ROUTE_SCHEMA_VERSION:
        raise ValueError("migration_required: unrecognized persisted build route")
    if "selection_origin" not in payload:
        payload = {**payload, "selection_origin": "existing_run", "selection_ref": "build/route.json"}
        payload.pop("compatibility_note", None)
        if payload.get("engine_id") == "legacy_ppt_master":
            payload["authoring_mode"] = "legacy_external"
    return validate_route(payload)


def persist_route(run_dir: str | Path, route: dict[str, Any]) -> dict[str, Any]:
    from uuid import uuid4
    from workflow.actions import (
        ActionStaleError, _acquire_run_lock, _release_run_lock, _atomic_json,
        read_current_revision, create_action_envelope, stage_action_result,
        commit_action_result,
    )
    root = Path(run_dir).expanduser().resolve()
    validate_route(route)
    identity = ("engine_id", "authoring_mode", "density", "library_mode", "origin_run_mode")
    # Rebase only over unrelated concurrent work. A winning route is immutable,
    # including its original selection provenance; a competing choice is an error.
    for _ in range(5):
        lock = _acquire_run_lock(root)
        try:
            existing = load_persisted_route(root)
            if existing:
                if any(existing.get(key) != route.get(key) for key in identity):
                    raise ValueError("build route conflicts with the first persisted selection")
                return existing
            revision = read_current_revision(root).get("revision_id", "")
            if not revision:
                # Legacy runs without snapshots retain their compatibility path.
                # The shared lock ensures a later baseline includes this route.
                _atomic_json(root / ROUTE_PATH, route)
                return route
        finally:
            _release_run_lock(lock)
        action = "route_" + uuid4().hex
        envelope = create_action_envelope(
            action_id=action, task_id=action, scope_pages=["route"],
            permission="runtime", input_fingerprint="route_absent",
        )
        stage_action_result(root, envelope, {ROUTE_PATH.as_posix(): json.dumps(route, ensure_ascii=False, indent=2) + "\n"})
        try:
            commit_action_result(
                root, envelope, expected_revision=revision,
                current_input_fingerprint=lambda: "route_present" if load_persisted_route(root) else "route_absent",
                targets={ROUTE_PATH.as_posix(): root / ROUTE_PATH},
            )
            return route
        except ActionStaleError:
            continue
    raise ValueError("build route persistence conflicted with concurrent revisions; retry")


def _derive_route(request: dict[str, Any], run_dir: Path | None) -> dict[str, Any]:
    profile = _normalize(request.get("profile")).replace("_", "-")
    authoring = _normalize(request.get("authoring_mode"))
    explicit = bool(profile in {"native", "direct-svg", "legacy-ppt-master"} or authoring)
    route = {"schema_version": ROUTE_SCHEMA_VERSION, "engine_id": "deck_native", "authoring_mode": "image_blueprint", "density": "high" if profile == "high-density" else "standard", "library_mode": str(request.get("library_mode") or "auto"), "origin_run_mode": str(request.get("origin_run_mode") or request.get("run_mode") or "production"), "selection_origin": "user_explicit" if explicit else "default_policy", "selection_ref": "request.json" if explicit else None}
    if profile not in {"", "native", "standard", "high-density", "direct-svg", "legacy-ppt-master"}:
        raise ValueError(f"unknown build profile: {profile!r}")
    if authoring and authoring not in AUTHORING_MODES:
        raise ValueError(f"unknown authoring_mode: {authoring!r}")
    if authoring:
        route["authoring_mode"] = authoring
    if profile == "direct-svg":
        if authoring and authoring != "direct_svg":
            raise ValueError("authoring mode conflicts with direct-svg profile")
        route["authoring_mode"] = "direct_svg"
    if profile == "legacy-ppt-master":
        if authoring:
            raise ValueError("legacy profile does not accept native authoring mode")
        route.update(engine_id="legacy_ppt_master", authoring_mode="legacy_external")
    if run_dir and not explicit:
        if (run_dir / "build/render_request.json").exists():
            route.update(engine_id="legacy_ppt_master", authoring_mode="legacy_external", selection_origin="existing_run", selection_ref="build/render_request.json")
        elif (run_dir / "high_density_build/status.json").exists():
            route.update(density="high", selection_origin="existing_run", selection_ref="high_density_build/status.json")
        elif (run_dir / "render_results/render_result.json").exists():
            result = json.loads((run_dir / "render_results/render_result.json").read_text())
            tool = str(result.get("tool") or result.get("builder_backend", {}).get("backend_name") or "")
            if tool in {"ppt-master", "ppt_master", "legacy_ppt_master"}:
                route.update(engine_id="legacy_ppt_master", authoring_mode="legacy_external", selection_origin="existing_run", selection_ref="render_results/render_result.json")
            elif tool != "deck_native":
                raise ValueError("migration_required: existing render engine cannot be identified")
        elif any((run_dir / name).exists() for name in ("build/build_manifest.json", "build/artifact_manifest.json", "final_approval.json")) or any(run_dir.glob("*.pptx")):
            raise ValueError("migration_required: historical output exists without an identifiable engine; preserve it read-only")
    return validate_route(route)


def resolve_build_route(request: dict[str, Any], *, run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve() if run_dir is not None else None
    if root is not None:
        persisted = load_persisted_route(root)
        if persisted:
            from build.run_policy import enforce_origin_mode
            enforce_origin_mode(root, request or {})
            return persisted
    return _derive_route(request or {}, root)


def is_native(route: dict[str, Any]) -> bool:
    return route.get("engine_id") == "deck_native"
