from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from build.manifest import BuildManifestError, build_manifest_v2, legacy_preview_adapter
from runtime.artifact_validator import validate_artifact_manifest
from runtime.events import append_event
from runtime.run_state import ensure_run_dirs, load_request, read_json

from .blueprint import (
    BLUEPRINT_MANIFEST_DIR,
    BlueprintInvalid,
    BlueprintRequired,
    blueprint_path,
    blueprint_manifest_path,
    build_blueprint_prompt_artifact,
    ensure_blueprint_manifest,
    load_blueprint_manifest,
)
from .content import (
    LOCKS_DIR,
    NBB_PLAN_PATH,
    approve_nbb_plan,
    build_content_lock,
    build_nbb_plan,
    load_content_lock,
    load_nbb_plan,
    load_page_packages,
    write_content_lock,
    write_nbb_plan,
)
from .contracts import ContractError, assert_valid, assert_v2, read_json as read_contract_json, run_relative, safe_run_path, sha256_file, sha256_json, utc_now, write_json as write_contract_json
from .pptx import PptxEditabilityError, compile_pptx, readback_pptx, pptx_path, readback_path, trace_path
from .scene import build_fixture_scene, load_scene, scene_path, validate_scene_content, write_scene
from .style import STYLE_LOCK_PATH, StyleSelectionRequired, ensure_style_lock, load_style_lock, write_style_lock
from .svg import (
    PREVIEW_DIR,
    SvgVisualError,
    build_visual_review,
    compile_svg,
    load_visual_review,
    preview_path,
    render_preview,
    review_path,
    svg_path,
)

HIGH_DENSITY_DIR = Path("high_density_build")
STATUS_PATH = HIGH_DENSITY_DIR / "status.json"
MANIFEST_PATH = HIGH_DENSITY_DIR / "high_density_manifest.json"
BUILD_MANIFEST_PATH = Path("build/build_manifest.json")
ARTIFACT_MANIFEST_PATH = Path("build/artifact_manifest.json")
RENDER_RESULT_PATH = Path("render_results/render_result.json")
REQUIRED_STAGES = ("content_lock", "blueprint", "page_scene", "svg", "visual_review", "pptx", "readback", "handback")
REGISTERED_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg"}
HIGH_DENSITY_PROFILE_VERSION = "high-density-builder-core-v2"


class HighDensityBuildError(ValueError):
    def __init__(self, code: str, message: str, *, stage: str = "", page_id: str = "", artifacts: list[str] | None = None) -> None:
        self.code = code
        self.stage = stage
        self.page_id = page_id
        self.artifacts = list(artifacts or [])
        super().__init__(message)


def _mode(root: Path) -> str:
    value = str(load_request(root).get("run_mode") or "production").strip().lower()
    return value if value in {"production", "fixture", "dev", "benchmark"} else "production"


def _run_id(root: Path) -> str:
    return str(load_request(root).get("run_id") or root.name)


def _legacy_synthetic_fixture(root: Path) -> bool:
    """Keep the historical synthetic regression fixture deterministic.

    Real production runs must make an explicit style decision.  The checked-in
    fixture predates that gate and is deliberately kept self-contained so the
    standard regression suite can continue to exercise the full compiler.
    """
    request = load_request(root)
    project_name = str(request.get("project_name") or "").strip().lower()
    return project_name.startswith("synthetic high density fixture")


def _resume_command(root: Path) -> str:
    return f"deck-master build run --run-dir {root} --profile high-density"


def _status_payload(
    root: Path,
    status: str,
    *,
    page_id: str = "",
    stage: str = "",
    next_action: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "deck_high_density_status.v2",
        "run_id": _run_id(root),
        "builder_profile": "high_density",
        "status": status,
        "current_stage": stage,
        "next_action": next_action or {"kind": "none"},
        "updated_at": utc_now(),
    }
    if page_id:
        payload["current_page_id"] = page_id
    if error:
        payload["error"] = error
    assert_v2("high_density_status", payload)
    return payload


def _write_status(root: Path, payload: dict[str, Any]) -> Path:
    return write_contract_json(root / STATUS_PATH, payload)


def record_high_density_failure(run_dir: str | Path, error: HighDensityBuildError) -> dict[str, Any]:
    """Persist a blocked state so CLI and next-step can recover deterministically."""
    root = ensure_run_dirs(run_dir)
    _ensure_dirs(root)
    stage = str(error.stage or "content_lock")
    page_id = str(error.page_id or "")
    retry_command = _resume_command(root)
    next_action: dict[str, Any] = {
        "kind": "retry",
        "stage": stage,
        "resume_command": retry_command,
        "reason": "Resolve the recorded high-density error, then resume the build.",
    }
    if page_id:
        next_action["page_id"] = page_id
        retry_command = f"deck-master build retry --run-dir {root} --profile high-density --page-id {page_id} --stage {stage}"
        next_action["resume_command"] = retry_command
    payload = _status_payload(
        root,
        "blocked",
        page_id=page_id,
        stage=stage,
        next_action=next_action,
        error={
            "code": error.code,
            "message": str(error),
            "stage": stage,
            "page_id": page_id,
            "artifacts": list(error.artifacts),
        },
    )
    _write_status(root, payload)
    append_event(root, "high_density.blocked", target=page_id or _run_id(root), payload_ref=STATUS_PATH.as_posix(), data=payload["error"])
    return payload


def _waiting(
    root: Path,
    *,
    page_id: str,
    stage: str,
    kind: str,
    input_ref: str,
    output_ref: str,
    output_refs: list[str] | None = None,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    waiting_status = "awaiting_user_decision" if kind == "awaiting_user_decision" else "awaiting_agent_build"
    resolved_output_refs = list(dict.fromkeys([output_ref, *(output_refs or [])]))
    next_action = {
        "kind": kind,
        "run_id": _run_id(root),
        "page_id": page_id,
        "stage": stage,
        "input_ref": input_ref,
        "output_ref": output_ref,
        "input_refs": [input_ref],
        "output_refs": resolved_output_refs,
        "required_schema": {"content_lock": "deck_nbb_plan.v1" if kind == "agent_nbb_enrich" else "deck_high_density_status.v2", "blueprint": "deck_blueprint_manifest.v2", "page_scene": "deck_page_scene.v2", "svg": "native-svg", "visual_review": "deck_visual_review.v2"}.get(stage, "deck_high_density_status.v2"),
        "acceptance_command": _resume_command(root),
        "resume_command": _resume_command(root),
        "reason": reason,
    }
    if details:
        next_action.update(details)
    payload = _status_payload(root, waiting_status, page_id=page_id, stage=stage, next_action=next_action)
    _write_status(root, payload)
    append_event(root, f"high_density.{waiting_status}", target=page_id or _run_id(root), payload_ref=STATUS_PATH.as_posix(), data=next_action)
    return {
        "schema_version": "deck_high_density_run_result.v2",
        "status": waiting_status,
        "run_id": _run_id(root),
        "builder_profile": "high_density",
        "current_page_id": page_id,
        "current_stage": stage,
        "next_action": next_action,
        "status_path": STATUS_PATH.as_posix(),
    }


def _ensure_dirs(root: Path) -> None:
    for directory in (
        root / HIGH_DENSITY_DIR / "content_locks",
        root / HIGH_DENSITY_DIR / "nbb",
        root / HIGH_DENSITY_DIR / "style",
        root / HIGH_DENSITY_DIR / "prompts",
        root / HIGH_DENSITY_DIR / "blueprints",
        root / HIGH_DENSITY_DIR / "page_scenes",
        root / HIGH_DENSITY_DIR / "scenes",
        root / HIGH_DENSITY_DIR / "svg",
        root / HIGH_DENSITY_DIR / "previews",
        root / HIGH_DENSITY_DIR / "comparisons",
        root / HIGH_DENSITY_DIR / "reviews",
        root / HIGH_DENSITY_DIR / "pptx",
        root / HIGH_DENSITY_DIR / "readback",
        root / HIGH_DENSITY_DIR / "traces",
        root / "build",
        root / "render_results",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _packages_for_build(root: Path) -> list[dict[str, Any]]:
    try:
        packages = load_page_packages(root, expected_run_id=_run_id(root))
    except (ContractError, ValueError) as exc:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock") from exc
    if packages:
        for package in packages:
            try:
                assert_valid("page_package", package)
            except ContractError as exc:
                raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock", page_id=str(package.get("page_id") or "")) from exc
            if package.get("status") != "ready_for_build":
                raise HighDensityBuildError(
                    "HD_CONTENT_LOCK_INVALID",
                    f"page package {package.get('page_id')} is not ready_for_build",
                    stage="content_lock",
                    page_id=str(package.get("page_id") or ""),
                )
        return packages
    mode = _mode(root)
    if mode not in {"fixture", "dev"}:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", "production high-density build requires page_packages/; preview_manifest is not a direct input", stage="content_lock")
    preview_path = root / "preview_manifest.json"
    if not preview_path.exists():
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", "page packages are missing", stage="content_lock")
    preview = read_json(preview_path)
    try:
        packages = legacy_preview_adapter(preview, run_id=_run_id(root))
    except BuildManifestError as exc:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock") from exc
    for package in packages:
        try:
            assert_valid("page_package", package)
        except ContractError as exc:
            raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock", page_id=str(package.get("page_id") or "")) from exc
        package["status"] = "ready_for_build"
        write_contract_json(root / "page_packages" / f"{package['page_id']}.json", package)
    return packages


def _validate_scene_assets(root: Path, package: dict[str, Any], scene: dict[str, Any]) -> dict[str, Path]:
    """Resolve only approved package assets referenced by the native scene."""
    bindings = {
        str(binding.get("asset_id")): binding
        for binding in package.get("asset_bindings", []) or []
        if isinstance(binding, dict) and binding.get("asset_id")
    }
    resolved: dict[str, Path] = {}
    for element in scene.get("elements", []):
        kind = str(element.get("kind") or "")
        if kind != "image":
            if element.get("asset_policy") == "registered":
                raise ContractError(f"registered asset policy is only valid for image elements: {element.get('element_id')}")
            continue
        asset_id = str(element.get("asset_ref") or "")
        binding = bindings.get(asset_id)
        if not binding or binding.get("approved") is not True:
            raise ContractError(f"image asset is not approved in page package: {asset_id or element.get('element_id')}")
        asset_path_value = str(binding.get("path") or "")
        try:
            asset_path = safe_run_path(root, asset_path_value)
        except ContractError as exc:
            raise ContractError(f"registered image asset path is invalid: {asset_path_value}") from exc
        if asset_path.suffix.lower() not in REGISTERED_ASSET_EXTENSIONS or not asset_path.is_file():
            raise ContractError(f"registered image asset is missing or unsupported: {asset_path_value}")
        binding_sha = str(binding.get("sha256") or "")
        scene_sha = str(element.get("asset_sha256") or "")
        actual_sha = sha256_file(asset_path)
        if len(binding_sha) != 64 or binding_sha != actual_sha or scene_sha != actual_sha:
            raise ContractError(f"registered image asset hash mismatch: {asset_id}")
        resolved[asset_id] = asset_path
    return resolved


def _backend() -> dict[str, Any]:
    return {
        "name": "deck-builder-high-density",
        "production_capable": True,
        "contract_versions": [
            "deck_page_package.v1",
            "deck_build_manifest.v2",
            "deck_nbb_plan.v1",
            "deck_high_density_style_lock.v1",
            "deck_content_lock.v2",
            "deck_blueprint_manifest.v2",
            "deck_page_scene.v2",
            "deck_visual_metrics.v1",
            "deck_visual_review.v2",
            "deck_svg_to_drawingml_trace.v1",
            "deck_pptx_readback.v2",
            "deck_high_density_manifest.v2",
            "deck_high_density_status.v2",
        ],
    }


def _high_density_source_fingerprint(manifest: dict[str, Any], style_lock: dict[str, Any], nbb_plan_sha256: str) -> str:
    return sha256_json(
        {
            "base_source_fingerprint": str(manifest.get("source_fingerprint") or ""),
            "style_lock_sha256": str(style_lock.get("style_lock_sha256") or ""),
            "nbb_plan_sha256": nbb_plan_sha256,
            "profile_version": HIGH_DENSITY_PROFILE_VERSION,
        }
    )


def _validate_nbb_plan_lineage(root: Path, plan: dict[str, Any], packages: list[dict[str, Any]], run_id: str) -> None:
    loaded = load_nbb_plan(root, packages=packages, expected_run_id=run_id, require_approved=True)
    if loaded.get("nbb_plan_sha256") != plan.get("nbb_plan_sha256"):
        raise ContractError("NBB plan changed while validating lineage")


def _refresh_build_manifest_lineage(root: Path, manifest: dict[str, Any], packages: list[dict[str, Any]], style_lock: dict[str, Any], nbb_plan_sha256: str) -> dict[str, Any]:
    refreshed = build_manifest_v2(
        run_id=_run_id(root),
        packages=packages,
        builder_backend=dict(manifest.get("builder_backend") or _backend()),
        output_profile=str(manifest.get("output_profile") or "production_pptx"),
        required_page_ids=[str(package["page_id"]) for package in packages],
        required_outputs=list(manifest.get("required_outputs") or []),
        style_lock=style_lock,
        builder_profile="high_density",
        now=None,
    )
    refreshed["run_mode"] = _mode(root)
    refreshed["source_fingerprint"] = _high_density_source_fingerprint(refreshed, style_lock, nbb_plan_sha256)
    refreshed["pages"] = [{**page, "page_package_path": f"page_packages/{page['page_id']}.json"} for page in refreshed["pages"]]
    assert_valid("build_manifest", refreshed)
    return refreshed


def _prepare_high_density(run_dir: str | Path, *, output_profile: str = "production_pptx") -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    _ensure_dirs(root)
    if output_profile not in {"production_pptx", "client_delivery"}:
        raise HighDensityBuildError("BUILD_PROFILE_UNSUPPORTED", f"high-density output profile is unsupported: {output_profile}")
    packages = _packages_for_build(root)
    if not packages:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", "no page packages available", stage="content_lock")
    mode = _mode(root)
    style_mode = "fixture" if _legacy_synthetic_fixture(root) else mode
    style_selection_pending = False
    try:
        style_lock = ensure_style_lock(root, _run_id(root), mode=style_mode)
    except StyleSelectionRequired as exc:
        # Keep a valid, explicitly unapproved lock in the build manifest so
        # the run remains inspectable and recoverable while style selection is
        # pending. Production execution still blocks on this lock.
        style_selection_pending = True
        write_style_lock(root, _run_id(root), "cyber-01", approved=False)
        style_lock = load_style_lock(root, require_approved=False, expected_run_id=_run_id(root))
    nbb_plan_sha256 = "0" * 64
    lock_paths: list[str] = []
    if mode in {"fixture", "dev"}:
        try:
            nbb_plan = build_nbb_plan(
                packages,
                run_id=_run_id(root),
                selected_storyline_id="storyline.decision",
                approved_by="fixture",
            )
            write_nbb_plan(root, nbb_plan)
            nbb_plan_sha256 = str(nbb_plan["nbb_plan_sha256"])
            page_plans = {str(page["page_id"]): page for page in nbb_plan["pages"]}
            for package in packages:
                path = write_content_lock(
                    root,
                    package,
                    page_plans[str(package["page_id"])],
                    nbb_plan_sha256=nbb_plan_sha256,
                )
                lock_paths.append(run_relative(root, path))
        except ContractError as exc:
            raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock") from exc
    builder_manifest = build_manifest_v2(
        run_id=_run_id(root),
        packages=packages,
        builder_backend=_backend(),
        output_profile=output_profile,
        required_page_ids=[str(package["page_id"]) for package in packages],
        required_outputs=[
            "high_density_build/high_density_manifest.json",
            "high_density_build/svg/",
            "high_density_build/pptx/deck_high_density.pptx",
            "build/artifact_manifest.json",
            "render_results/render_result.json",
        ],
        style_lock=style_lock,
        builder_profile="high_density",
        now=None,
    )
    builder_manifest["run_mode"] = _mode(root)
    builder_manifest["source_fingerprint"] = _high_density_source_fingerprint(builder_manifest, style_lock, nbb_plan_sha256)
    builder_manifest["pages"] = [
        {
            **page,
            "page_package_path": f"page_packages/{page['page_id']}.json",
        }
        for page in builder_manifest["pages"]
    ]
    assert_valid("build_manifest", builder_manifest)
    write_contract_json(root / BUILD_MANIFEST_PATH, builder_manifest)
    if style_selection_pending:
        status = _status_payload(
            root,
            "awaiting_user_decision",
            stage="style_lock",
            next_action={
                "kind": "awaiting_user_decision",
                "run_id": _run_id(root),
                "stage": "style_lock",
                "input_refs": ["high_density_build/style/style_options.json"],
                "output_refs": ["high_density_build/style/style_lock.json"],
                "required_schema": "deck_high_density_style_lock.v1",
                "acceptance_command": f"deck-master build prepare --run-dir {root} --profile high-density",
                "resume_command": f"deck-master build prepare --run-dir {root} --profile high-density",
                "reason": "Choose and approve one of the eight fixed CyberPPT-derived styles before production ImageGen.",
            },
        )
    else:
        status = _status_payload(root, "prepared", stage="content_lock", next_action={"kind": "none"})
    _write_status(root, status)
    append_event(root, "high_density.prepared", target=_run_id(root), payload_ref=BUILD_MANIFEST_PATH.as_posix(), data={"page_count": len(packages), "content_locks": lock_paths})
    return {
        "schema_version": "deck_high_density_prepare_result.v2",
        "status": "awaiting_user_decision" if style_selection_pending else "prepared",
        "run_id": _run_id(root),
        "builder_profile": "high_density",
        "output_profile": output_profile,
        "page_count": len(packages),
        "build_manifest": BUILD_MANIFEST_PATH.as_posix(),
        "status_path": STATUS_PATH.as_posix(),
    }


def prepare_high_density(run_dir: str | Path, *, output_profile: str = "production_pptx") -> dict[str, Any]:
    try:
        return _prepare_high_density(run_dir, output_profile=output_profile)
    except HighDensityBuildError as error:
        record_high_density_failure(run_dir, error)
        raise
    except ContractError as error:
        failure = HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(error), stage="content_lock")
        record_high_density_failure(run_dir, failure)
        raise failure from error


def _load_builder_manifest(root: Path) -> dict[str, Any]:
    path = root / BUILD_MANIFEST_PATH
    if not path.exists():
        request = load_request(root)
        _prepare_high_density(root, output_profile=str(request.get("output_profile") or "production_pptx"))
    if not path.exists():
        return {"status": "awaiting_user_decision", "builder_profile": "high_density"}
    manifest = read_contract_json(path)
    effective_profile = str(manifest.get("builder_profile") or "standard")
    if effective_profile != "high_density":
        raise HighDensityBuildError("BUILDER_PROFILE_MISMATCH", "existing build manifest is not high-density", stage="content_lock")
    assert_valid("build_manifest", manifest)
    return manifest


def _page_record(root: Path, package: dict[str, Any], status: str, *, lock: dict[str, Any], blueprint_manifest: dict[str, Any], scene: dict[str, Any], blockers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    page_id = str(package["page_id"])
    image = blueprint_path(root, page_id)
    if image is None:
        raise HighDensityBuildError("HD_BLUEPRINT_REGEN_REQUIRED", f"blueprint image missing on page {page_id}", stage="blueprint", page_id=page_id)
    refs = {
        "content_lock": root / LOCKS_DIR / f"{page_id}.json",
        "blueprint": root / blueprint_manifest["image_path"],
        "page_scene": scene_path(root, page_id),
        "svg": svg_path(root, page_id),
        "preview": preview_path(root, page_id),
        "visual_review": review_path(root, page_id),
        "pptx_trace": trace_path(root),
        "readback_report": readback_path(root),
    }
    return {
        "page_id": page_id,
        "order": int(package.get("order") or 0),
        "status": status,
        **{
            key: {"path": run_relative(root, path), "sha256": sha256_file(path)}
            for key, path in refs.items()
            if path.exists()
        },
        "blockers": list(blockers or []),
    }


def _write_page_trace_files(root: Path, scenes: list[dict[str, Any]]) -> None:
    trace = read_contract_json(trace_path(root))
    pages = {str(page.get("page_id")): page for page in trace.get("pages", [])}
    for scene in scenes:
        page_id = str(scene["page_id"])
        path = root / HIGH_DENSITY_DIR / "traces" / f"{page_id}.json"
        write_contract_json(path, {"schema_version": "deck_pptx_trace_page.v1", "page_id": page_id, "trace": pages.get(page_id, {}), "created_at": utc_now()})


def _artifact(root: Path, *, artifact_id: str, kind: str, path: Path, editability: str, page_id: str = "") -> dict[str, Any]:
    media = {
        "deck_pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "page_png": "image/png",
    }[kind]
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "path": run_relative(root, path),
        "media_type": media,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "validation_status": "validated",
        "editability": editability,
        "page_id": page_id,
        "source_mode": "fixture" if _mode(root) in {"fixture", "dev"} else "high_density",
        "source_fingerprint": "",
        "created_at": utc_now(),
    }


def _write_canonical_handback(root: Path, manifest: dict[str, Any], pages: list[dict[str, Any]], pptx: Path) -> None:
    artifacts = [_artifact(root, artifact_id="deck_high_density_pptx", kind="deck_pptx", path=pptx, editability="native")]
    for page in pages:
        preview = root / page["preview"]["path"]
        artifacts.append(_artifact(root, artifact_id=f"{page['page_id']}_preview", kind="page_png", path=preview, editability="flat_image", page_id=page["page_id"]))
    for artifact in artifacts:
        artifact["source_fingerprint"] = manifest["source_fingerprint"]
    artifact_manifest = {
        "schema_version": "deck_artifact_manifest.v1",
        "run_id": _run_id(root),
        "source_fingerprint": manifest["source_fingerprint"],
        "page_count": len(pages),
        "artifacts": artifacts,
        "warnings": [],
        "created_at": utc_now(),
    }
    write_contract_json(root / ARTIFACT_MANIFEST_PATH, artifact_manifest)
    artifact_validation = validate_artifact_manifest(
        root,
        artifact_manifest,
        expected_source_fingerprint=manifest["source_fingerprint"],
        allow_non_client_deliverable=True,
    )
    if not artifact_validation["valid"]:
        raise HighDensityBuildError(
            "HD_CONTRACT_HANDBACK_FAILED",
            "artifact manifest validation failed: " + "; ".join(artifact_validation["errors"]),
            stage="handback",
            artifacts=[ARTIFACT_MANIFEST_PATH.as_posix()],
        )
    render_result = {
        "schema_version": "deck_render_result.v2",
        "run_id": _run_id(root),
        "session_id": f"high-density-{manifest['source_fingerprint'][:12]}",
        "tool": "deck-builder-high-density",
        "status": "completed",
        "artifact_path": run_relative(root, pptx),
        "preview_dir": (root / PREVIEW_DIR).relative_to(root).as_posix() if (root / PREVIEW_DIR).exists() else "high_density_build/previews",
        "page_count": len(pages),
        "source_fingerprint": manifest["source_fingerprint"],
        "build_manifest": BUILD_MANIFEST_PATH.as_posix(),
        "artifact_manifest": ARTIFACT_MANIFEST_PATH.as_posix(),
        "artifacts": artifacts,
        "page_previews": [{"page_id": page["page_id"], "preview_path": page["preview"]["path"]} for page in pages],
        "warnings": [],
        "created_at": utc_now(),
    }
    assert_valid("render_result", render_result)
    write_contract_json(root / RENDER_RESULT_PATH, render_result)


def _invalidate_page_downstream(root: Path, page_id: str) -> None:
    blueprint = blueprint_path(root, page_id)
    if blueprint is not None:
        _remove_if_exists(blueprint)
    for manifest_name in (f"{page_id}.manifest.json", f"{page_id}.blueprint_manifest.json"):
        _remove_if_exists(root / BLUEPRINT_MANIFEST_DIR / manifest_name)
    _remove_if_exists(root / "high_density_build" / "prompts" / f"{page_id}.blueprint_prompt.json")
    _invalidate_page_scene_downstream(root, page_id)


def _invalidate_page_scene_downstream(root: Path, page_id: str) -> None:
    for path in (
        scene_path(root, page_id),
        root / "high_density_build" / "scenes" / f"{page_id}.page_scene.json",
        svg_path(root, page_id),
        preview_path(root, page_id),
        root / "high_density_build" / "previews" / f"{page_id}.pptx.png",
        review_path(root, page_id),
        root / "high_density_build" / "reviews" / f"{page_id}.metrics.json",
        root / "high_density_build" / "reviews" / f"{page_id}.svg_vs_pptx.metrics.json",
        root / "high_density_build" / "blueprints" / f"{page_id}.normalized.png",
    ):
        _remove_if_exists(path)
    for path in (
        pptx_path(root),
        trace_path(root),
        readback_path(root),
        root / MANIFEST_PATH,
        root / ARTIFACT_MANIFEST_PATH,
        root / RENDER_RESULT_PATH,
    ):
        _remove_if_exists(path)


def _invalidate_nbb_downstream(root: Path, packages: list[dict[str, Any]], *, remove_plan: bool = True) -> None:
    if remove_plan:
        _remove_if_exists(root / NBB_PLAN_PATH)
    for package in packages:
        page_id = str(package.get("page_id") or "")
        _remove_if_exists(root / LOCKS_DIR / f"{page_id}.json")
        _remove_if_exists(root / LOCKS_DIR / f"{page_id}.content_lock.json")
        _invalidate_page_downstream(root, page_id)


def _reset_nbb_downstream(root: Path, manifest: dict[str, Any], packages: list[dict[str, Any]], style_lock: dict[str, Any]) -> dict[str, Any]:
    """Remove artifacts that could have been produced from an unapproved NBB state."""
    _invalidate_nbb_downstream(root, packages, remove_plan=False)
    refreshed = _refresh_build_manifest_lineage(root, manifest, packages, style_lock, "0" * 64)
    refreshed["status"] = "building"
    write_contract_json(root / BUILD_MANIFEST_PATH, refreshed)
    return refreshed


def _run_high_density(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    _ensure_dirs(root)
    manifest = _load_builder_manifest(root)
    if not (root / BUILD_MANIFEST_PATH).exists():
        status_file = root / STATUS_PATH
        if status_file.exists():
            return read_contract_json(status_file)
        return {"status": "awaiting_user_decision", "builder_profile": "high_density", "status_path": STATUS_PATH.as_posix()}
    try:
        packages = _packages_for_build(root)
    except ContractError as error:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(error), stage="content_lock") from error
    mode = _mode(root)
    execution_mode = "fixture" if _legacy_synthetic_fixture(root) else mode
    try:
        style_lock = load_style_lock(root, require_approved=True, expected_run_id=_run_id(root))
    except StyleSelectionRequired as exc:
        return _waiting(root, page_id="", stage="style_lock", kind="awaiting_user_decision", input_ref="high_density_build/style/style_options.json", output_ref="high_density_build/style/style_lock.json", reason=str(exc))
    manifest["status"] = "building"
    write_contract_json(root / BUILD_MANIFEST_PATH, manifest)
    nbb_plan_sha256 = "0" * 64
    nbb_plan_file = root / NBB_PLAN_PATH
    if not nbb_plan_file.exists():
        manifest = _reset_nbb_downstream(root, manifest, packages, style_lock)
        return _waiting(
            root,
            page_id="",
            stage="content_lock",
            kind="agent_nbb_enrich",
            input_ref="page_packages/",
            output_ref=NBB_PLAN_PATH.as_posix(),
            reason="Run the content-specific NBB enrichment and evidence audit, then write a pending deck_nbb_plan.v1 with two or three candidate storylines.",
        )
    try:
        pending_plan = load_nbb_plan(root, packages=packages, expected_run_id=_run_id(root), require_approved=False)
    except ContractError as exc:
        message = str(exc)
        if "Page Package hash is stale" in message or "page coverage is stale" in message:
            _invalidate_nbb_downstream(root, packages)
            manifest = _refresh_build_manifest_lineage(root, manifest, packages, style_lock, "0" * 64)
            manifest["status"] = "building"
            write_contract_json(root / BUILD_MANIFEST_PATH, manifest)
            append_event(root, "high_density.nbb_invalidated", target=_run_id(root), payload_ref=NBB_PLAN_PATH.as_posix(), data={"reason": "page_package_changed"})
            return _waiting(
                root,
                page_id="",
                stage="content_lock",
                kind="agent_nbb_enrich",
                input_ref="page_packages/",
                output_ref=NBB_PLAN_PATH.as_posix(),
                reason=f"The Page Packages changed, so the previous NBB plan and all downstream artifacts were invalidated: {message}",
            )
        manifest = _reset_nbb_downstream(root, manifest, packages, style_lock)
        return _waiting(
            root,
            page_id="",
            stage="content_lock",
            kind="agent_nbb_enrich",
            input_ref="page_packages/",
            output_ref=NBB_PLAN_PATH.as_posix(),
            reason=f"Regenerate the malformed or stale NBB plan before content locks can be created: {message}",
        )
    selection = pending_plan.get("selection") or {}
    if str(selection.get("status") or "") != "approved":
        manifest = _reset_nbb_downstream(root, manifest, packages, style_lock)
        candidates = [
            {
                "storyline_id": str(item.get("storyline_id") or ""),
                "management_conclusion": str(item.get("management_conclusion") or ""),
                "audience": str(item.get("audience") or ""),
                "visual_potential": str(item.get("visual_potential") or ""),
                "not_recommended_because": str(item.get("not_recommended_because") or ""),
            }
            for item in pending_plan.get("storyline_candidates") or []
        ]
        recommended_id = str(selection.get("recommended_storyline_id") or "")
        return _waiting(
            root,
            page_id="",
            stage="content_lock",
            kind="awaiting_user_decision",
            input_ref=NBB_PLAN_PATH.as_posix(),
            output_ref=NBB_PLAN_PATH.as_posix(),
            reason="Select one NBB storyline candidate. The same approved plan can resume without asking again until the Page Packages change.",
            details={
                "required_schema": "deck_nbb_plan.v1",
                "recommended_storyline_id": recommended_id,
                "storyline_candidates": candidates,
                "approval_command": f"deck-master build retry --run-dir {root} --profile high-density --stage content_lock --storyline-id {recommended_id}",
            },
        )
    try:
        nbb_plan = load_nbb_plan(root, packages=packages, expected_run_id=_run_id(root), require_approved=True)
        nbb_plan_sha256 = str(nbb_plan["nbb_plan_sha256"])
    except ContractError as exc:
        raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock") from exc
    page_plans = {str(page.get("page_id") or ""): page for page in nbb_plan.get("pages") or [] if isinstance(page, dict)}
    refreshed_manifest = _refresh_build_manifest_lineage(root, manifest, packages, style_lock, nbb_plan_sha256)
    if (
        refreshed_manifest.get("source_fingerprint") != manifest.get("source_fingerprint")
        or refreshed_manifest.get("pages") != manifest.get("pages")
        or refreshed_manifest.get("style_lock") != manifest.get("style_lock")
    ):
        manifest = refreshed_manifest
    manifest["status"] = "building"
    write_contract_json(root / BUILD_MANIFEST_PATH, manifest)
    scenes: list[dict[str, Any]] = []
    locks: dict[str, dict[str, Any]] = {}
    asset_paths_by_page: dict[str, dict[str, Path]] = {}
    page_records: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package["page_id"])
        page_plan = page_plans.get(page_id)
        if page_plan is None:
            raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", f"NBB page plan is missing on page {page_id}", stage="content_lock", page_id=page_id)
        try:
            try:
                lock = load_content_lock(root, page_id, expected_run_id=_run_id(root))
            except ContractError:
                write_content_lock(root, package, page_plan, nbb_plan_sha256=nbb_plan_sha256)
                lock = load_content_lock(root, page_id, expected_run_id=_run_id(root))
            current_lock = build_content_lock(package, page_plan, nbb_plan_sha256=nbb_plan_sha256)
            lock_stale = (
                lock.get("page_package_sha256") != current_lock.get("page_package_sha256")
                or lock.get("content_lock_sha256") != current_lock.get("content_lock_sha256")
                or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "") != nbb_plan_sha256
            )
            if lock_stale:
                write_content_lock(root, package, page_plan, nbb_plan_sha256=nbb_plan_sha256)
                _invalidate_page_downstream(root, page_id)
                lock = load_content_lock(root, page_id, expected_run_id=_run_id(root))
                append_event(
                    root,
                    "high_density.content_lock_invalidated",
                    target=page_id,
                    payload_ref=f"{LOCKS_DIR.as_posix()}/{page_id}.json",
                    data={"reason": "page_package_hash_changed"},
                )
        except ContractError as exc:
            raise HighDensityBuildError("HD_CONTENT_LOCK_INVALID", str(exc), stage="content_lock", page_id=page_id) from exc
        locks[page_id] = lock
        blueprint_manifest_file = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.blueprint_manifest.json"
        if not blueprint_manifest_file.exists():
            blueprint_manifest_file = root / BLUEPRINT_MANIFEST_DIR / f"{page_id}.manifest.json"
        previous_blueprint_sha = ""
        if blueprint_manifest_file.exists():
            try:
                previous_blueprint_sha = str(read_contract_json(blueprint_manifest_file).get("image_sha256") or "")
            except ContractError:
                previous_blueprint_sha = ""
        try:
            prompt_file = root / "high_density_build" / "prompts" / f"{page_id}.blueprint_prompt.json"
            blueprint_file = blueprint_manifest_path(root, page_id)
            expected_nbb_sha = nbb_plan_sha256 or str((lock.get("lineage") or {}).get("nbb_plan_sha256") or "0" * 64)
            if prompt_file.exists():
                try:
                    existing_prompt = read_contract_json(prompt_file)
                except ContractError:
                    existing_prompt = {}
                if (
                    existing_prompt.get("content_lock_sha256") != lock.get("content_lock_sha256")
                    or existing_prompt.get("style_lock_sha256") != style_lock.get("style_lock_sha256")
                    or existing_prompt.get("nbb_plan_sha256") != expected_nbb_sha
                ):
                    _invalidate_page_downstream(root, page_id)
                    prompt_file = root / "high_density_build" / "prompts" / f"{page_id}.blueprint_prompt.json"
                    append_event(root, "high_density.blueprint_invalidated", target=page_id, payload_ref=prompt_file.relative_to(root).as_posix(), data={"reason": "prompt_lineage_changed"})
            if blueprint_file.exists():
                try:
                    existing_blueprint = read_contract_json(blueprint_file)
                except ContractError:
                    existing_blueprint = {}
                if (
                    existing_blueprint.get("content_lock_sha256") != lock.get("content_lock_sha256")
                    or existing_blueprint.get("style_lock_sha256") != style_lock.get("style_lock_sha256")
                    or existing_blueprint.get("nbb_plan_sha256") != expected_nbb_sha
                ):
                    _invalidate_page_downstream(root, page_id)
                    prompt_file = root / "high_density_build" / "prompts" / f"{page_id}.blueprint_prompt.json"
                    append_event(root, "high_density.blueprint_invalidated", target=page_id, payload_ref=f"{BLUEPRINT_MANIFEST_DIR.as_posix()}/{page_id}.blueprint_manifest.json", data={"reason": "blueprint_lineage_changed"})
            if not prompt_file.exists():
                build_blueprint_prompt_artifact(root, page_id, lock, style_lock=style_lock, nbb_plan_sha256=nbb_plan_sha256)
            ensure_blueprint_manifest(root, page_id, lock, style_lock=style_lock, nbb_plan_sha256=nbb_plan_sha256)
            blueprint_manifest = load_blueprint_manifest(root, page_id, expected_run_id=_run_id(root))
        except BlueprintRequired:
            return _waiting(root, page_id=page_id, stage="blueprint", kind="agent_imagegen", input_ref=f"high_density_build/prompts/{page_id}.blueprint_prompt.json", output_ref=f"high_density_build/blueprints/{page_id}.png", reason="Read the frozen content-aware prompt, call ImageGen, and save the approved blueprint at output_ref.")
        except BlueprintInvalid as exc:
            if "not been approved" in str(exc):
                return _waiting(root, page_id=page_id, stage="blueprint", kind="agent_imagegen", input_ref=f"high_density_build/prompts/{page_id}.blueprint_prompt.json", output_ref=f"high_density_build/blueprints/{page_id}.png", reason="Approve the generated blueprint after confirming the frame, annotations, and image hash.")
            raise HighDensityBuildError("HD_BLUEPRINT_REGEN_REQUIRED", str(exc), stage="blueprint", page_id=page_id) from exc
        except ContractError as exc:
            raise HighDensityBuildError("HD_BLUEPRINT_REGEN_REQUIRED", str(exc), stage="blueprint", page_id=page_id) from exc
        if previous_blueprint_sha and previous_blueprint_sha != str(blueprint_manifest.get("image_sha256") or ""):
            _invalidate_page_scene_downstream(root, page_id)
            append_event(
                root,
                "high_density.blueprint_invalidated",
                target=page_id,
                payload_ref=blueprint_manifest_file.relative_to(root).as_posix(),
                data={"reason": "blueprint_hash_changed"},
            )

        scene_file = scene_path(root, page_id)
        if scene_file.exists():
            try:
                scene = load_scene(root, page_id)
            except ContractError as exc:
                raise HighDensityBuildError("HD_PAGE_SCENE_INVALID", str(exc), stage="page_scene", page_id=page_id) from exc
            if str(scene.get("run_id") or "") != _run_id(root):
                raise HighDensityBuildError("HD_PAGE_SCENE_INVALID", f"page scene run_id mismatch on page {page_id}", stage="page_scene", page_id=page_id)
            if scene.get("content_lock_sha256") != lock.get("content_lock_sha256"):
                raise HighDensityBuildError("HD_PAGE_SCENE_INVALID", f"page scene is stale for page {page_id}", stage="page_scene", page_id=page_id)
            if scene.get("blueprint_sha256") != blueprint_manifest.get("image_sha256"):
                raise HighDensityBuildError("HD_PAGE_SCENE_INVALID", f"page scene blueprint is stale for page {page_id}", stage="page_scene", page_id=page_id)
        elif execution_mode in {"fixture", "dev"}:
            layout_id = str((package.get("visual_spec") or {}).get("page_type") or "")
            scene = build_fixture_scene(
                lock,
                str(blueprint_manifest["image_sha256"]),
                blueprint_path=blueprint_path(root, page_id),
                layout_id=layout_id,
            )
            write_scene(root, scene)
        else:
            return _waiting(
                root,
                page_id=page_id,
                stage="page_scene",
                kind="agent_visual_reconstruct",
                input_ref=f"high_density_build/blueprints/{page_id}.manifest.json",
                output_ref=f"high_density_build/scenes/{page_id}.page_scene.json",
                output_refs=[f"high_density_build/svg/{page_id}.svg"],
                reason="Reconstruct the blueprint into semantic native scene geometry and approved native SVG with locked text and overflow policies.",
            )
        try:
            validate_scene_content(scene, lock)
        except ContractError as exc:
            raise HighDensityBuildError("HD_PAGE_SCENE_INVALID", str(exc), stage="page_scene", page_id=page_id) from exc
        try:
            asset_paths_by_page[page_id] = _validate_scene_assets(root, package, scene)
        except ContractError as exc:
            raise HighDensityBuildError("HD_ASSET_POLICY_BLOCKED", str(exc), stage="svg", page_id=page_id) from exc
        scenes.append(scene)
        try:
            svg_file = svg_path(root, page_id)
            if execution_mode in {"fixture", "dev"}:
                compile_svg(scene, svg_file, assets=asset_paths_by_page[page_id])
            elif not svg_file.exists():
                return _waiting(
                    root,
                    page_id=page_id,
                    stage="svg",
                    kind="agent_visual_reconstruct",
                    input_ref=f"high_density_build/scenes/{page_id}.page_scene.json",
                    output_ref=f"high_density_build/svg/{page_id}.svg",
                    reason="Write the approved native SVG from the reconstructed page scene; the runtime will validate and compile this SVG without replacing it.",
                )
            else:
                from .svg import validate_svg

                validate_svg(svg_file, page_id=page_id)
            render_preview(svg_path(root, page_id), preview_path(root, page_id))
        except SvgVisualError as exc:
            if execution_mode not in {"fixture", "dev"}:
                return _waiting(
                    root,
                    page_id=page_id,
                    stage="svg",
                    kind="agent_svg_repair",
                    input_ref=f"high_density_build/svg/{page_id}.svg",
                    output_ref=f"high_density_build/svg/{page_id}.svg",
                    reason=f"Repair the approved native SVG and resume after validation: {exc}",
                )
            raise HighDensityBuildError(exc.code, str(exc), stage="svg", page_id=page_id) from exc
        review_file = review_path(root, page_id)
        if review_file.exists():
            try:
                load_visual_review(root, page_id)
            except SvgVisualError as exc:
                if execution_mode not in {"fixture", "dev"}:
                    try:
                        review_payload = read_contract_json(review_file)
                    except ContractError:
                        review_payload = {}
                    self_passed = str((review_payload.get("self_review") or {}).get("status") or "") == "pass"
                    main_passed = str((review_payload.get("main_review") or {}).get("status") or "") == "pass"
                    if self_passed and not main_passed:
                        return _waiting(root, page_id=page_id, stage="visual_review", kind="agent_main_review", input_ref=f"high_density_build/reviews/{page_id}.visual_review.json", output_ref=f"high_density_build/reviews/{page_id}.visual_review.json", reason=f"Read the producer self-review and actual visual metrics, then complete the independent main review: {exc}")
                    return _waiting(root, page_id=page_id, stage="visual_review", kind="agent_svg_repair", input_ref=f"high_density_build/reviews/{page_id}.visual_review.json", output_ref=f"high_density_build/svg/{page_id}.svg", output_refs=[f"high_density_build/reviews/{page_id}.visual_review.json"], reason=f"Repair the approved SVG using the recorded visual findings, then write a refreshed passing visual review: {exc}")
                raise HighDensityBuildError("HD_SVG_REVIEW_FAILED", str(exc), stage="visual_review", page_id=page_id) from exc
        elif execution_mode in {"fixture", "dev"}:
            try:
                build_visual_review(root, scene, mode=execution_mode)
            except SvgVisualError as exc:
                raise HighDensityBuildError("HD_SVG_REVIEW_FAILED", str(exc), stage="visual_review", page_id=page_id) from exc
            try:
                load_visual_review(root, page_id)
            except SvgVisualError as exc:
                raise HighDensityBuildError("HD_SVG_REVIEW_FAILED", str(exc), stage="visual_review", page_id=page_id) from exc
        else:
            return _waiting(root, page_id=page_id, stage="visual_review", kind="agent_self_review", input_ref=f"high_density_build/svg/{page_id}.svg", output_ref=f"high_density_build/reviews/{page_id}.visual_review.json", reason="Review SVG against the blueprint, repair overflow or drift, and write a passing self-review with the required visual evidence.")
        page_records.append(_page_record(root, package, "visual_review_passed", lock=lock, blueprint_manifest=blueprint_manifest, scene=scene))

    try:
        pptx, trace = compile_pptx(root, scenes, locks, asset_paths_by_page=asset_paths_by_page)
        _write_page_trace_files(root, scenes)
        readback = readback_pptx(root, scenes, locks, pptx)
    except PptxEditabilityError as exc:
        raise HighDensityBuildError("HD_PPTX_EDITABILITY_FAILED", str(exc), stage="readback") from exc
    for record in page_records:
        record["status"] = "completed"
        record["pptx_trace"] = {"path": run_relative(root, root / HIGH_DENSITY_DIR / "traces" / f"{record['page_id']}.json"), "sha256": sha256_file(root / HIGH_DENSITY_DIR / "traces" / f"{record['page_id']}.json")}
        record["readback_report"] = {"path": run_relative(root, readback), "sha256": sha256_file(readback)}
    high_density_manifest = {
        "schema_version": "deck_high_density_manifest.v2",
        "run_id": _run_id(root),
        "builder_profile": "high_density",
        "source_fingerprint": manifest["source_fingerprint"],
        "nbb_plan": {"path": run_relative(root, root / NBB_PLAN_PATH), "sha256": nbb_plan_sha256},
        "style_lock": {"path": run_relative(root, root / STYLE_LOCK_PATH), "sha256": str(style_lock.get("style_lock_sha256") or "")},
        "status": "building",
        "pages": page_records,
        "created_at": utc_now(),
    }
    assert_v2("high_density_manifest", high_density_manifest)
    write_contract_json(root / MANIFEST_PATH, high_density_manifest)
    _write_canonical_handback(root, manifest, page_records, pptx)
    high_density_manifest["status"] = "completed"
    high_density_manifest["completed_at"] = utc_now()
    assert_v2("high_density_manifest", high_density_manifest)
    write_contract_json(root / MANIFEST_PATH, high_density_manifest)
    manifest["status"] = "completed"
    manifest["high_density_manifest"] = MANIFEST_PATH.as_posix()
    manifest["builder_profile"] = "high_density"
    write_contract_json(root / BUILD_MANIFEST_PATH, manifest)
    status = _status_payload(root, "completed", stage="handback", next_action={"kind": "none"})
    _write_status(root, status)
    append_event(root, "high_density.completed", target=_run_id(root), payload_ref=MANIFEST_PATH.as_posix(), data={"page_count": len(page_records), "pptx": run_relative(root, pptx)})
    return {
        "schema_version": "deck_high_density_run_result.v2",
        "status": "completed",
        "run_id": _run_id(root),
        "builder_profile": "high_density",
        "page_count": len(page_records),
        "high_density_manifest": MANIFEST_PATH.as_posix(),
        "build_manifest": BUILD_MANIFEST_PATH.as_posix(),
        "artifact_manifest": ARTIFACT_MANIFEST_PATH.as_posix(),
        "render_result": RENDER_RESULT_PATH.as_posix(),
        "pptx": run_relative(root, pptx),
        "status_path": STATUS_PATH.as_posix(),
    }


def run_high_density(run_dir: str | Path) -> dict[str, Any]:
    try:
        return _run_high_density(run_dir)
    except HighDensityBuildError as error:
        record_high_density_failure(run_dir, error)
        raise
    except ContractError as error:
        failure = HighDensityBuildError("HD_CONTRACT_HANDBACK_FAILED", str(error), stage="handback")
        record_high_density_failure(run_dir, failure)
        raise failure from error


def build_high_density_status(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    build_manifest_file = root / BUILD_MANIFEST_PATH
    if build_manifest_file.exists():
        build_manifest = read_contract_json(build_manifest_file)
        if str(build_manifest.get("builder_profile") or "standard") != "high_density":
            raise HighDensityBuildError("BUILDER_PROFILE_MISMATCH", "existing build manifest is not high-density", stage="content_lock")
    status_file = root / STATUS_PATH
    if status_file.exists():
        status = read_contract_json(status_file)
        assert_v2("high_density_status", status)
    else:
        status = _status_payload(root, "prepared" if (root / BUILD_MANIFEST_PATH).exists() else "blocked", stage="content_lock", next_action={"kind": "retry", "resume_command": _resume_command(root)})
    status["status_path"] = STATUS_PATH.as_posix()
    status["build_manifest"] = BUILD_MANIFEST_PATH.as_posix() if (root / BUILD_MANIFEST_PATH).exists() else ""
    status["high_density_manifest"] = MANIFEST_PATH.as_posix() if (root / MANIFEST_PATH).exists() else ""
    status["artifact_manifest"] = ARTIFACT_MANIFEST_PATH.as_posix() if (root / ARTIFACT_MANIFEST_PATH).exists() else ""
    status["render_result"] = RENDER_RESULT_PATH.as_posix() if (root / RENDER_RESULT_PATH).exists() else ""
    return status


def watch_high_density_status(run_dir: str | Path, *, timeout_seconds: float = 30.0, poll_seconds: float = 0.25) -> dict[str, Any]:
    """Wait for a terminal high-density state; prepared/building are non-terminal."""
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    last_key = ""
    terminal = {"completed", "blocked", "failed", "awaiting_user_decision"}
    while True:
        status = build_high_density_status(run_dir)
        key = "|".join(str(status.get(item) or "") for item in ("status", "current_page_id", "current_stage"))
        if key != last_key:
            events.append({"status": status.get("status"), "current_page_id": status.get("current_page_id", ""), "current_stage": status.get("current_stage", ""), "next_action": status.get("next_action", {})})
            last_key = key
        if str(status.get("status") or "") in terminal:
            status["watch"] = {"events": events, "timed_out": False}
            return status
        if time.monotonic() - started >= max(0.0, timeout_seconds):
            status["watch"] = {"events": events, "timed_out": True, "timeout_seconds": timeout_seconds}
            return status
        time.sleep(max(0.01, poll_seconds))


def _remove_if_exists(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _retry_high_density(
    run_dir: str | Path,
    *,
    page_id: str = "",
    stage: str | None = None,
    storyline_id: str = "",
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest_path = root / BUILD_MANIFEST_PATH
    if not manifest_path.exists():
        raise HighDensityBuildError("HD_RETRY_TARGET_INVALID", "retry requires a prepared high-density build", stage=stage or "content_lock", page_id=page_id)
    try:
        manifest = read_contract_json(manifest_path)
        assert_valid("build_manifest", manifest)
    except ContractError as exc:
        raise HighDensityBuildError("HD_RETRY_TARGET_INVALID", str(exc), stage=stage or "content_lock", page_id=page_id) from exc
    if stage and stage not in REQUIRED_STAGES:
        raise HighDensityBuildError("HD_STAGE_UNSUPPORTED", f"unsupported high-density stage: {stage}")
    target_stage = stage or "blueprint"
    allowed_pages = {str(item.get("page_id") or "") for item in manifest.get("pages", []) if isinstance(item, dict)}
    if target_stage == "content_lock" and not page_id:
        if storyline_id:
            try:
                approve_nbb_plan(root, storyline_id, approver="user")
            except ContractError as exc:
                raise HighDensityBuildError("HD_NBB_SELECTION_INVALID", str(exc), stage="content_lock") from exc
        elif not (root / NBB_PLAN_PATH).exists():
            raise HighDensityBuildError("HD_NBB_SELECTION_INVALID", "deck-scope content_lock retry requires an NBB plan and storyline_id", stage="content_lock")
        target_page_ids = sorted(allowed_pages)
    else:
        if not page_id:
            raise HighDensityBuildError("HD_RETRY_TARGET_INVALID", f"retry stage {target_stage} requires --page-id", stage=target_stage)
        if page_id not in allowed_pages:
            raise HighDensityBuildError("HD_RETRY_TARGET_INVALID", f"retry page_id is not registered in the build manifest: {page_id}", stage=stage or "content_lock", page_id=page_id)
        target_page_ids = [page_id]
    stages = list(REQUIRED_STAGES)
    start = stages.index(target_stage)
    for target_page_id in target_page_ids:
        for downstream in stages[start:]:
            if downstream == "content_lock":
                _remove_if_exists(root / LOCKS_DIR / f"{target_page_id}.json")
                _remove_if_exists(root / LOCKS_DIR / f"{target_page_id}.content_lock.json")
            elif downstream == "blueprint":
                blueprint = blueprint_path(root, target_page_id)
                if blueprint is not None:
                    _remove_if_exists(blueprint)
                _remove_if_exists(root / BLUEPRINT_MANIFEST_DIR / f"{target_page_id}.manifest.json")
                _remove_if_exists(root / BLUEPRINT_MANIFEST_DIR / f"{target_page_id}.blueprint_manifest.json")
                _remove_if_exists(root / "high_density_build" / "prompts" / f"{target_page_id}.blueprint_prompt.json")
            elif downstream == "page_scene":
                _remove_if_exists(scene_path(root, target_page_id))
                _remove_if_exists(root / "high_density_build" / "scenes" / f"{target_page_id}.page_scene.json")
            elif downstream == "svg":
                _remove_if_exists(svg_path(root, target_page_id))
                _remove_if_exists(preview_path(root, target_page_id))
            elif downstream == "visual_review":
                _remove_if_exists(review_path(root, target_page_id))
                _remove_if_exists(root / "high_density_build" / "reviews" / f"{target_page_id}.metrics.json")
                _remove_if_exists(root / "high_density_build" / "reviews" / f"{target_page_id}.svg_vs_pptx.metrics.json")
    if target_stage in {"content_lock", "blueprint", "page_scene", "svg", "visual_review", "pptx", "readback", "handback"}:
        _remove_if_exists(pptx_path(root))
        _remove_if_exists(trace_path(root))
        _remove_if_exists(readback_path(root))
        _remove_if_exists(root / MANIFEST_PATH)
        _remove_if_exists(root / ARTIFACT_MANIFEST_PATH)
        _remove_if_exists(root / RENDER_RESULT_PATH)
    status = _status_payload(root, "building", page_id=page_id, stage=target_stage, next_action={"kind": "retry", "page_id": page_id, "stage": target_stage, "resume_command": _resume_command(root)})
    _write_status(root, status)
    append_event(root, "high_density.retry_started", target=page_id, payload_ref=STATUS_PATH.as_posix(), data={"stage": target_stage})
    return _run_high_density(root)


def retry_high_density(run_dir: str | Path, *, page_id: str = "", stage: str | None = None, storyline_id: str = "") -> dict[str, Any]:
    try:
        return _retry_high_density(run_dir, page_id=page_id, stage=stage, storyline_id=storyline_id)
    except HighDensityBuildError as error:
        record_high_density_failure(run_dir, error)
        raise
    except ContractError as error:
        failure = HighDensityBuildError("HD_CONTRACT_HANDBACK_FAILED", str(error), stage=stage or "handback", page_id=page_id)
        record_high_density_failure(run_dir, failure)
        raise failure from error


__all__ = [
    "HighDensityBuildError",
    "build_high_density_status",
    "prepare_high_density",
    "record_high_density_failure",
    "retry_high_density",
    "run_high_density",
    "watch_high_density_status",
]
