"""SC-1.1 ND-03: native run adapter (engine layer).

Turns approved Page Packages + Content Lock into native compile inputs and
writes the standard artifact/build/readback lineage. Two authoring modes:

- ``direct_svg``: the host Agent authors the approved SVG per page (SVG
  subset-constrained); no ImageGen is required — fully local.
- ``image_blueprint``: the runtime dispatches a host task envelope for
  ImageGen + SVG reconstruction; compilation proceeds only from approved
  host outputs. Without real host image tools the run reports
  awaiting_agent_imagegen honestly — never silently degrades to fixture.

The adapter owns Run-layout resolution and hash pinning; the compiler
(``native_pptx.api``) stays pure.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from build.build_route import is_native, resolve_build_route
    from native_pptx.api import (
        NativeCompileError,
        NativeCompileRequest,
        compile_svg_deck,
        readback_pptx as api_readback,
    )
    from native_pptx.probe import probe_native_runtime
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.build.build_route import is_native, resolve_build_route
    from scripts.native_pptx.api import NativeCompileError, NativeCompileRequest, compile_svg_deck
    from scripts.native_pptx.probe import probe_native_runtime

try:
    from production.page_package import PagePackageIndex
except ModuleNotFoundError:  # pragma: no cover
    from scripts.production.page_package import PagePackageIndex

SVG_SUBSET_STAGE_DIR = "build/native_svg"
NATIVE_ENGINE_VERSION = "native_engine/1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _approved_packages(root: Path) -> list[dict[str, Any]]:
    """Validate the COMPLETE buildable page set (review P1-05).

    Every page the narrative requires must have an approved package — a
    blocked/missing/draft page blocks the WHOLE deck build with the page
    list, instead of silently compiling a subset.
    """

    packages_dir = root / "page_packages"
    if packages_dir.is_dir():
        for package_file in sorted(packages_dir.glob("*.json")):
            if package_file.name == "index.json":
                continue
            try:
                json.loads(package_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise NativeEngineError(
                    f"page package is corrupt: {package_file.name}: {exc}",
                    code="NDC_PACKAGE_CORRUPT",
                    recovery=f"repair or regenerate {package_file.name} before building",
                ) from exc
    packages = PagePackageIndex(root).list_packages()
    approved = [pkg for pkg in packages if str(pkg.get("status") or "") in {"ready_for_build", "ready"}]
    if not approved:
        raise NativeEngineError(
            "no approved page packages (ready_for_build) to compile",
            code="NDC_NO_APPROVED_PAGES",
            recovery="run the producer to approve page packages first",
        )
    # coverage against the narrative's required pages
    required_pages = _required_page_ids(root)
    approved_ids = {str(pkg.get("page_id") or "") for pkg in approved}
    not_ready = sorted(set(required_pages) - approved_ids)
    if not_ready:
        raise NativeEngineError(
            f"page set incomplete: required pages not approved for build: {not_ready}",
            code="NDC_PAGE_SET_INCOMPLETE",
            recovery=f"approve or repair pages {not_ready} before compiling the deck",
        )
    return approved


def _required_page_ids(root: Path) -> list[str]:
    for name in ("narrative_plan.json", "page_tasks.json"):
        path = root / name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        beats = payload.get("beats") or payload.get("tasks") or []
        ids = [str(item.get("page_id") or item.get("beat_id") or "") for item in beats if isinstance(item, dict)]
        if ids:
            return [item for item in ids if item]
    # no narrative/page tasks recorded: the approved set is the page set
    return [str(pkg.get("page_id") or "") for pkg in PagePackageIndex(root).list_packages()]


class NativeEngineError(RuntimeError):
    """Native engine error with an NDC-style code and recovery hint."""

    def __init__(self, message: str, *, code: str = "NDC_ENGINE_FAILED", recovery: str = "") -> None:
        self.code = code
        self.recovery = recovery
        super().__init__(message)


def prepare_native_run(run_dir: str | Path) -> dict[str, Any]:
    """Validate the run for a native build and record the fixed route.

    Requires approved packages and a native runtime probe; image_blueprint
    runs additionally require host image tools, which are reported as an
    explicit awaiting state rather than a silent degradation.
    """

    root = Path(run_dir).expanduser().resolve()
    request_path = root / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8")) if request_path.exists() else {}
    route = resolve_build_route(request, run_dir=root)
    from build.build_route import persist_route

    persist_route(root, route)  # the route is fixed once per run
    probe = probe_native_runtime()
    approved = _approved_packages(root)
    response: dict[str, Any] = {
        "run_id": str(root.name),
        "engine_id": route["engine_id"],
        "authoring_mode": route["authoring_mode"],
        "runtime_probe": {"status": probe["status"], "probe_id": probe["probe_id"]},
        "pages": [str(pkg.get("page_id") or "") for pkg in approved],
        "status": "prepared",
    }
    if not probe["status"] in {"ready", "degraded_ready"}:
        raise NativeEngineError(
            f"native runtime probe failed: {probe['required_missing']}",
            code="NDC_KERNEL_UNAVAILABLE",
            recovery="install the built-in compile kernel dependencies",
        )
    return {**response, "status": "awaiting_svg_authoring" if route["authoring_mode"] == "direct_svg" else "awaiting_agent_imagegen"}


def _svg_input_fingerprint(root: Path, page_id: str) -> str:
    """Recomputed INSIDE the commit lock: the current page package content +
    content lock sha + page id. A late host result produced against older
    inputs can never overwrite newer SVGs (review P1-04)."""

    import hashlib

    digest = hashlib.sha256()
    digest.update(str(page_id).encode("utf-8"))
    package_file = root / "page_packages" / f"{page_id}.json"
    if package_file.exists():
        digest.update(hashlib.sha256(package_file.read_bytes()).digest())
    lock_file = root / "high_density_build" / "content_locks" / f"{page_id}.json"
    canonical_lock = root / "high_density_build" / "content_locks" / f"{page_id}.content_lock.json"
    for candidate in (canonical_lock, lock_file):
        if candidate.exists():
            digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            break
    return digest.hexdigest()


def submit_approved_svg(
    run_dir: str | Path,
    page_id: str,
    svg_text: str,
    *,
    action_id: str,
    task_id: str = "native-svg",
    expected_revision: str | None = None,
    produced_against: str | None = None,
) -> dict[str, Any]:
    """Stage one host-authored SVG for approval-checked compilation.

    SC-1.1 P1-04: the CALLER's action_id is authoritative (Runtime-issued);
    the input fingerprint is recomputed under the commit lock from the
    current package + lock — never a constant. Optional expected_revision
    gives compare-and-swap semantics; a replay of the same action with the
    same output is idempotent, a different output conflicts.
    """

    root = Path(run_dir).expanduser().resolve()
    from workflow.actions import action_applied, commit_action_result, stage_action_result

    # conflict check: same action id with a DIFFERENT output must not pass
    applied = action_applied(root, str(action_id))
    if applied:
        import hashlib

        recorded_files = applied.get("applied_files") or []
        target_rel = f"high_density_build/svg/{page_id}.svg"
        if target_rel in [str(item) for item in recorded_files]:
            # idempotent replay: compare output content via staged text
            current_target = root / "high_density_build" / "svg" / f"{page_id}.svg"
            if current_target.exists() and hashlib.sha256(svg_text.encode("utf-8")).digest() != hashlib.sha256(current_target.read_bytes()).digest():
                raise NativeEngineError(
                    f"action {action_id} already applied with different output on page {page_id}; conflict rejected",
                    code="NDC_ACTION_CONFLICT",
                    recovery="issue a new action id for the revised SVG",
                )
        return {"status": "already_applied", "page_id": page_id, "revision_id": applied.get("revision_id", ""), "action_id": str(action_id)}

    # the envelope binds the fingerprint the host result was PRODUCED
    # against (dispatch time); the commit recomputes the current one inside
    # the lock — a late result against moved-on inputs is rejected.
    envelope = {
        "schema_version": "deck_stage_action.v1",
        "action_id": str(action_id),
        "task_id": str(task_id),
        "scope_pages": [page_id],
        "permission": "agent",
        "input_fingerprint": str(produced_against if produced_against is not None else _svg_input_fingerprint(root, page_id)),
    }
    stage_action_result(root, envelope, {"svg": svg_text})
    marker = commit_action_result(
        root,
        envelope,
        current_input_fingerprint=lambda: _svg_input_fingerprint(root, page_id),
        targets={"svg": root / "high_density_build" / "svg" / f"{page_id}.svg"},
        expected_revision=expected_revision,
    )
    return {"status": "svg_staged", "page_id": page_id, "revision_id": marker.get("revision_id", ""), "action_id": str(action_id)}


def run_native_compile(run_dir: str | Path, *, run_mode: str = "production") -> dict[str, Any]:
    """Compile + readback the approved SVGs through the native kernel.

    Business validation stays with the adapter (HD validate_approved_svg);
    the compile result carries engine/subset identity and per-input hashes —
    never client_delivery_ready.
    """

    root = Path(run_dir).expanduser().resolve()
    try:
        from native_pptx.svg_pipeline import validate_svg
    except ModuleNotFoundError:  # pragma: no cover
        from scripts.native_pptx.svg_pipeline import validate_svg

    from high_density.svg import validate_approved_svg  # adapter seam (single implementation via shim)

    approved = _approved_packages(root)
    # Single source of truth: the run's existing v2 scenes and content locks
    # (produced by the approved content pipeline) — the engine never projects
    # a second copy of page truth.
    from high_density.scene import load_scene
    from high_density.content import load_content_lock

    page_ids = [str(pkg.get("page_id") or "") for pkg in approved]
    scenes = [load_scene(root, page_id) for page_id in page_ids]
    locks = {page_id: load_content_lock(root, page_id) for page_id in page_ids}
    # SC-1.1 P1-05: resolve registered assets from the approved packages
    # (reuse the HD validator) and pin every approved SVG's hash.
    asset_paths_by_page = _resolve_asset_paths(root, approved)
    expected_sha256 = _approved_svg_hashes(root, page_ids)
    result = compile_svg_deck(
        NativeCompileRequest(
            root=root,
            scenes=scenes,
            locks=locks,
            asset_paths_by_page=asset_paths_by_page,
            validate_approved=validate_approved_svg,
            expected_sha256=expected_sha256,
        )
    )
    readback = api_readback(result, scenes, locks)
    write_json_native_run(root, {"compile": {"engine_version": result.engine_version, "input_sha256": result.input_sha256}, "readback": readback})
    return {
        "status": "compiled",
        "run_id": str(root.name),
        "pptx_path": str(result.pptx_path),
        "trace_path": str(result.trace_path),
        "readback": readback,
        "engine_version": result.engine_version,
        "svg_subset_version": result.svg_subset_version,
    }



def write_json_native_run(root: Path, payload: dict[str, Any]) -> None:
    path = root / "build" / "native_compile_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dispatch_imagegen_task(run_dir: str | Path) -> dict[str, Any]:
    """Emit the awaiting_agent_imagegen host task envelope (image_blueprint).

    The task carries the approved customer-visible projection as blueprint
    input; ImageGen content is a VISUAL source only (spec ND-D06) — facts
    come from the Content Lock. With no real host image tool, the run stays
    awaiting and nothing is faked.
    """

    root = Path(run_dir).expanduser().resolve()
    approved = _approved_packages(root)
    payload = {
        "schema_version": "deck_host_imagegen_task.v1",
        "run_id": str(root.name),
        "stage": "prepare_blueprint",
        "status": "awaiting_agent_imagegen",
        "pages": [
            {
                "page_id": str(pkg.get("page_id") or ""),
                "blueprint_brief": {
                    "title": (pkg.get("customer_visible") or {}).get("title", ""),
                    "body": [str(block.get("text") or "") for block in (pkg.get("customer_visible") or {}).get("body_blocks", []) if isinstance(block, dict)],
                    "visual_intent": (pkg.get("visual_spec") or {}).get("expected_visual", ""),
                    "page_role": (pkg.get("visual_spec") or {}).get("page_role", ""),
                },
            }
            for pkg in approved
        ],
        "note": "no image generation tool detected on this host; the run cannot proceed honestly until the host provides one",
    }
    path = root / "build" / "host_imagegen_task.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _resolve_asset_paths(root: Path, packages: list[dict[str, Any]]) -> dict[str, dict[str, Path]]:
    """Resolve approved package asset_bindings into per-page asset paths."""

    from high_density.engine import _validate_scene_assets
    from high_density.scene import load_scene

    asset_paths_by_page: dict[str, dict[str, Path]] = {}
    for package in packages:
        page_id = str(package.get("page_id") or "")
        if not page_id:
            continue
        bindings = package.get("asset_bindings") or []
        if not bindings:
            asset_paths_by_page[page_id] = {}
            continue
        scene = load_scene(root, page_id)
        asset_paths_by_page[page_id] = _validate_scene_assets(root, package, scene)
    return asset_paths_by_page


def _approved_svg_hashes(root: Path, page_ids: list[str]) -> dict[str, str]:
    """Pin the sha256 of every approved SVG at compile time."""

    import hashlib

    hashes: dict[str, str] = {}
    for page_id in page_ids:
        svg = root / "high_density_build" / "svg" / f"{page_id}.svg"
        if svg.exists():
            hashes[page_id] = hashlib.sha256(svg.read_bytes()).hexdigest()
    return hashes
