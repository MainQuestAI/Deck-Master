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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from build.build_route import resolve_build_route
    from native_pptx.api import (
        NativeCompileError,
        NativeCompileRequest,
        compile_svg_deck,
        readback_pptx as api_readback,
    )
    from native_pptx.probe import probe_native_runtime
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.build.build_route import resolve_build_route
    from scripts.native_pptx.api import NativeCompileError, NativeCompileRequest, compile_svg_deck, readback_pptx as api_readback
    from scripts.native_pptx.probe import probe_native_runtime

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

    from workflow.actions import revision_input_path

    packages_dir = revision_input_path(root, root / "page_packages")
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
    packages = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(packages_dir.glob("*.json")) if path.name != "index.json"]
    from native_pptx.contracts import assert_valid

    seen_ids, seen_orders = set(), set()
    for package in packages:
        if package.get("status") == "ready":
            from native_pptx.contracts import sha256_json
            from high_density.content import load_content_lock
            try:
                legacy_lock = load_content_lock(root, str(package["page_id"]), expected_run_id=root.name)
            except (ValueError, RuntimeError, OSError, KeyError):
                legacy_lock = {}
            if legacy_lock.get("page_package_sha256") != sha256_json(package):
                raise NativeEngineError("legacy ready requires a matching approved Content Lock; use ready_for_build for newly approved packages", code="NDC_PACKAGE_APPROVAL")
        candidate = {**package, "status": "ready_for_build"} if package.get("status") == "ready" else package
        assert_valid("page_package", candidate)
        page_id, order = str(package["page_id"]), int(package["order"])
        if page_id in seen_ids or order in seen_orders or package["run_id"] != root.name:
            raise NativeEngineError("duplicate page identity/order or cross-run package", code="NDC_PAGE_SCOPE")
        from high_density.content import _assert_safe_page_id

        _assert_safe_page_id(page_id)
        seen_ids.add(page_id)
        seen_orders.add(order)
    packages.sort(key=lambda pkg: int(pkg.get("order") or 0))
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
        from workflow.actions import revision_input_path

        path = revision_input_path(root, root / name)
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
    from workflow.actions import revision_input_path

    folder = revision_input_path(root, root / "page_packages")
    return [str(json.loads(path.read_text()).get("page_id") or "") for path in sorted(folder.glob("*.json")) if path.name != "index.json"]


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
    from build.native_content import ensure_native_content

    ensure_native_content(root, approved)
    from build.native_contracts import write_task_readiness
    task_readiness = write_task_readiness(root, probe, task_kind="direct_svg_build" if route["authoring_mode"] == "direct_svg" else "image_blueprint_build")
    response: dict[str, Any] = {
        "run_id": str(root.name),
        "engine_id": route["engine_id"],
        "authoring_mode": route["authoring_mode"],
        "runtime_probe": {"status": probe["status"], "probe_id": probe["probe_id"]},
        "task_readiness": task_readiness,
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


def _svg_input_fingerprint(root: Path, page_id: str, *, include_blueprint: bool = True) -> str:
    from workflow.actions import revision_read
    with revision_read(root):
        return _svg_revision_fingerprint(root, page_id, include_blueprint=include_blueprint)


def _svg_revision_fingerprint(root: Path, page_id: str, *, include_blueprint: bool = True) -> str:
    """Recomputed INSIDE the commit lock: the current page package content +
    content lock sha + page id. A late host result produced against older
    inputs can never overwrite newer SVGs (review P1-04)."""

    import hashlib

    digest = hashlib.sha256()
    digest.update(str(page_id).encode("utf-8"))
    from workflow.actions import active_input_path

    package_file = active_input_path(root / "page_packages" / f"{page_id}.json")
    if package_file.exists():
        digest.update(hashlib.sha256(package_file.read_bytes()).digest())
    lock_file = root / "high_density_build" / "content_locks" / f"{page_id}.json"
    canonical_lock = root / "high_density_build" / "content_locks" / f"{page_id}.content_lock.json"
    for candidate in (canonical_lock, lock_file):
        candidate = active_input_path(candidate)
        if candidate.exists():
            digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            break
    from high_density.blueprint import blueprint_path

    blueprint = blueprint_path(root, page_id)
    receipt = active_input_path(root / "high_density_build/blueprints" / f"{page_id}.blueprint.json")
    if receipt.exists():
        from native_pptx.contracts import safe_run_path

        blueprint = safe_run_path(root, json.loads(receipt.read_text()).get("image_ref", ""))
    if include_blueprint and blueprint is not None:
        blueprint = active_input_path(blueprint)
        if blueprint.is_file():
            digest.update(hashlib.sha256(blueprint.read_bytes()).digest())
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
    scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from workflow.actions import revision_read
    with revision_read(run_dir, fresh=True):
        return _submit_approved_svg_revision(run_dir, page_id, svg_text, action_id=action_id,
            task_id=task_id, expected_revision=expected_revision, produced_against=produced_against, scene=scene)


def _submit_approved_svg_revision(run_dir, page_id, svg_text, *, action_id, task_id, expected_revision, produced_against, scene):
    """Validate and atomically commit the host's SVG and matching Scene.

    The issued task, not caller-supplied budgets/scope, is authoritative.
    Failed validations consume the same finite per-page stage budget.
    """
    import hashlib
    import tempfile
    from workflow.actions import action_applied, commit_action_result, stage_action_result, record_action_failure, check_action_budget
    from build.native_tasks import issued_task, current_task_fingerprint
    from high_density.content import load_content_lock
    from high_density.scene import validate_scene, validate_scene_content
    from high_density.svg import validate_approved_svg
    from native_pptx.contracts import sha256_json

    root = Path(run_dir).expanduser().resolve()
    if produced_against is None:
        raise NativeEngineError("submit requires the dispatch-time input fingerprint", code="NDC_MISSING_INPUT_FINGERPRINT")
    output_sha = hashlib.sha256(svg_text.encode("utf-8")).hexdigest()
    scene_sha = sha256_json(scene)
    applied = action_applied(root, str(action_id))
    if applied:
        if (
            applied.get("scope_pages") != [page_id]
            or applied.get("input_fingerprint") != produced_against
            or applied.get("output_sha256") != output_sha
            or applied.get("scene_sha256") != scene_sha
        ):
            raise NativeEngineError("action already applied with different SVG/Scene", code="NDC_ACTION_CONFLICT")
        return {"status": "already_applied", "page_id": page_id, "action_id": action_id, "revision_id": applied["revision_id"]}
    task = issued_task(root, str(action_id), page_id, str(produced_against))
    task_id = task["task_id"]
    budget = check_action_budget(root, task_id, max_actions=int(task["budget"]["max_actions"]))
    if budget["exhausted"]:
        raise NativeEngineError("native host action budget exhausted", code="NDC_BUDGET_EXHAUSTED")
    try:
        if str(produced_against) != _svg_input_fingerprint(root, page_id):
            raise NativeEngineError("host result input fingerprint is stale", code="NDC_STALE_INPUT")
        if not isinstance(scene, dict):
            raise NativeEngineError("host result requires both SVG and Scene", code="NDC_SCENE_REQUIRED")
        lock = load_content_lock(root, page_id, expected_run_id=root.name)
        if (
            scene.get("page_id") != page_id
            or scene.get("run_id") != root.name
            or scene.get("content_lock_sha256") != lock["content_lock_sha256"]
        ):
            raise NativeEngineError("host Scene identity or content-lock hash mismatch", code="NDC_SCENE_IDENTITY")
        if task.get("blueprint_sha256") and scene.get("blueprint_sha256") != task["blueprint_sha256"]:
            raise NativeEngineError("host Scene blueprint hash mismatch", code="NDC_SCENE_IDENTITY")
        validate_scene(scene)
        validate_scene_content(scene, lock)
        assets = _resolve_asset_paths_for_scene(root, page_id, scene)
        with tempfile.TemporaryDirectory(prefix="native-svg-validate-") as tmp:
            candidate = Path(tmp) / "page.svg"
            candidate.write_text(svg_text, encoding="utf-8")
            validate_approved_svg(candidate, scene, lock, assets)
        envelope = {
            "schema_version": "deck_stage_action.v1",
            "action_id": action_id,
            "task_id": task_id,
            "scope_pages": [page_id],
            "permission": "agent",
            "input_fingerprint": produced_against,
            "budget": task["budget"],
        }
        scene_text = json.dumps(scene, ensure_ascii=False, indent=2) + "\n"
        stage_action_result(root, envelope, {"svg": svg_text, "scene": scene_text, "scene_mirror": scene_text})
        from high_density.scene import canonical_scene_path, scene_path

        marker = commit_action_result(
            root,
            envelope,
            current_input_fingerprint=lambda: current_task_fingerprint(root, action_id, page_id, str(produced_against)),
            targets={
                "svg": root / "high_density_build/svg" / f"{page_id}.svg",
                "scene": canonical_scene_path(root, page_id),
                "scene_mirror": scene_path(root, page_id),
            },
            expected_revision=expected_revision,
            receipt_data={"output_sha256": output_sha, "scene_sha256": scene_sha},
        )
    except Exception as exc:
        record_action_failure(root, action_id=action_id, task_id=task_id, reason=str(exc))
        raise
    return {"status": "svg_staged", "page_id": page_id, "action_id": action_id, "revision_id": marker["revision_id"]}


def _resolve_asset_paths_for_scene(root: Path, page_id: str, scene: dict[str, Any]) -> dict[str, Path]:
    from high_density.engine import _validate_scene_assets

    package = next((p for p in _approved_packages(root) if p["page_id"] == page_id), None)
    if package is None:
        raise NativeEngineError("submitted page is outside the approved page set", code="NDC_PAGE_SCOPE")
    return _validate_scene_assets(root, package, scene) if package.get("asset_bindings") else {}


def native_build_fingerprint(run_dir: str | Path) -> str:
    """Fingerprint the fixed revision and actual compile dependencies."""
    import importlib.metadata
    import shutil
    from workflow.actions import revision_read, revision_input_path
    from high_density.content import load_content_lock
    from high_density.scene import load_scene
    from native_pptx.contracts import sha256_file, sha256_json

    root = Path(run_dir).expanduser().resolve()
    with revision_read(root):
        packages = _approved_packages(root)
        pages = [p["page_id"] for p in packages]
        locks = {page: load_content_lock(root, page) for page in pages}
        scenes = [load_scene(root, page) for page in pages]
        hashes = {page: sha256_file(revision_input_path(root, root / "high_density_build/svg" / f"{page}.svg")) for page in pages}
        dependencies = {}
        for name in (
            "request.json",
            "narrative_plan.json",
            "solution_spec.json",
            "solution_model.json",
            "diagram_spec.json",
            "diagram_views.json",
            "style_lock.json",
            "context_pack.json",
            "context_manifest.json",
            "page_tasks.json",
            "source_manifest.json",
            "evidence_graph.json",
        ):
            path = revision_input_path(root, root / name)
            if path.is_file():
                dependencies[name] = sha256_file(path)
        source_dir = revision_input_path(root, root / "sources")
        if source_dir.is_dir():
            for path in sorted(source_dir.rglob("*")):
                if path.is_file():
                    dependencies["sources/" + path.relative_to(source_dir).as_posix()] = sha256_file(path)
        assets = _resolve_asset_paths(root, packages)
        for page, bindings in assets.items():
            for asset, path in bindings.items():
                dependencies[f"asset:{page}:{asset}"] = sha256_file(revision_input_path(root, path))
        from native_pptx.probe import _engine_fingerprint

        tools = {"native_pptx": _engine_fingerprint()}
        for distribution in ("python-pptx", "Pillow", "numpy"):
            tools[distribution] = importlib.metadata.version(distribution)
        for binary in ("soffice", "pdftoppm", "rsvg-convert"):
            executable = shutil.which(binary)
            tools[binary] = sha256_file(Path(executable).resolve()) if executable else "unavailable"
        # Font files are real build inputs too. Installing a missing weight
        # must invalidate earlier render/readback evidence.
        from high_density.svg import _font_path
        from xml.etree import ElementTree
        for page in pages:
            document = ElementTree.parse(revision_input_path(root, root / "high_density_build/svg" / f"{page}.svg"))
            for node in document.getroot().iter():
                if node.tag.split("}")[-1] != "text":
                    continue
                for span in [node, *list(node)]:
                    family = str(span.get("font-family") or node.get("font-family") or "Arial")
                    weight = str(span.get("font-weight") or node.get("font-weight") or "400")
                    key = "font:" + family + ":" + weight
                    if key not in tools:
                        tools[key] = sha256_file(_font_path(family, page, str(node.get("id") or "text"), weight))
        return sha256_json(
            {
                "pages": pages,
                "packages": packages,
                "locks": locks,
                "scenes": scenes,
                "svg": hashes,
                "dependencies": dependencies,
                "tools": tools,
            }
        )


def run_native_compile(run_dir: str | Path, *, run_mode: str = "production") -> dict[str, Any]:
    from workflow.actions import revision_read

    root = Path(run_dir).expanduser().resolve()
    with revision_read(root) as revision:
        return _compile_revision(root, run_mode=run_mode, revision=revision or "initial")


def _compile_revision(root: Path, *, run_mode: str, revision: str) -> dict[str, Any]:
    import uuid
    from high_density.svg import validate_approved_svg
    from high_density.scene import load_scene, validate_scene
    from high_density.content import load_content_lock
    from native_pptx.contracts import sha256_file, sha256_json, read_json
    from native_pptx.api import render_pptx
    from workflow.actions import revision_input_path

    approved = _approved_packages(root)
    page_ids = [str(pkg["page_id"]) for pkg in approved]
    scenes = [load_scene(root, page) for page in page_ids]
    locks = {page: load_content_lock(root, page, expected_run_id=root.name) for page in page_ids}
    for package, scene in zip(approved, scenes):
        lock = locks[package["page_id"]]
        if lock["page_package_sha256"] != sha256_json(package) or scene.get("content_lock_sha256") != lock["content_lock_sha256"]:
            raise NativeEngineError("native compile inputs are stale", code="NDC_STALE_INPUT")
        validate_scene(scene)
    svg_paths = {page: revision_input_path(root, root / "high_density_build/svg" / f"{page}.svg") for page in page_ids}
    hashes = {page: sha256_file(path) for page, path in svg_paths.items()}
    fingerprint = native_build_fingerprint(root)
    native_content = all(lock.get("enrichment", {}).get("framework") == "native_narrative" for lock in locks.values())
    from build.native_contracts import write_compile_request, write_task_readiness
    resolved_assets = _resolve_asset_paths(root, approved)
    if native_content:
        write_compile_request(root, revision=revision, fingerprint=fingerprint, packages=approved,
                              scenes=scenes, locks=locks, svg_paths=svg_paths, assets=resolved_assets,
                              native_canvas=True)
    # Legacy HD retains its original input protocol and canvas mapping; never
    # label its anisotropic mapping as the new native contain contract.
    write_task_readiness(root, probe_native_runtime(), task_kind="compile_approved_svg")
    output_root = root / "build/native_outputs" / f"{revision}_{uuid.uuid4().hex[:12]}" if native_content else None
    base_result = {
        "schema_version": "deck_native_compile_result.v1",
        "run_id": root.name,
        "build_revision": revision,
        "engine_id": "deck_native",
        "engine_version": "native_pptx/1.0",
        "subset_version": "hd-svg-subset/1",
        "input_fingerprint": fingerprint,
        "pages": [],
        "warnings": [],
        "errors": [],
        "created_at": _utc_now(),
    }
    try:
        result = compile_svg_deck(
            NativeCompileRequest(
                root=root,
                scenes=scenes,
                locks=locks,
                asset_paths_by_page=resolved_assets,
                validate_approved=validate_approved_svg,
                expected_sha256=hashes,
                svg_paths=svg_paths,
                output_root=output_root,
                canvas_mode="native" if native_content else "legacy",
            )
        )
        readback = api_readback(result, scenes, locks)
        trace = read_json(result.trace_path)
        pages = []

        def flatten(entries):
            for item in entries:
                yield item
                yield from flatten(item.get("children") or [])

        for index, page in enumerate(page_ids, 1):
            entry = next(p for p in trace["pages"] if p["page_id"] == page)
            elements = list(flatten(entry.get("elements") or []))
            pages.append(
                {
                    "page_id": page,
                    "order": index,
                    "svg_sha256": hashes[page],
                    "text_objects": sum(e.get("object_type") == "text" for e in elements),
                    "image_objects": sum(e.get("object_type") == "registered_asset" for e in elements),
                    "shape_objects": sum(e.get("object_type") not in {"text", "registered_asset", "group"} for e in elements),
                }
            )
        payload = {
            **base_result,
            "status": "compiled",
            "engine_version": result.engine_version,
            "subset_version": result.svg_subset_version,
            "pages": pages,
            "outputs": {
                "deck_pptx": {"path": result.pptx_path.relative_to(root).as_posix(), "sha256": sha256_file(result.pptx_path)},
                "object_trace": {"path": result.trace_path.relative_to(root).as_posix(), "sha256": sha256_file(result.trace_path)},
            },
        }
        write_json_native_run(root, payload)
        rendered = render_pptx(result) if native_content else {}
        return {
            "status": "compiled",
            "run_id": root.name,
            "pptx_path": str(result.pptx_path),
            "trace_path": str(result.trace_path),
            "readback": readback,
            "render": rendered,
            "build_revision": revision,
            "input_fingerprint": fingerprint,
            "packages": approved,
            "page_count": len(page_ids),
            "engine_version": result.engine_version,
            "svg_subset_version": result.svg_subset_version,
        }
    except Exception as exc:
        # A renderer failure does not falsify successful compilation; the
        # failed build is still blocked and carries an explicit renderer code.
        if not isinstance(exc, NativeCompileError) or exc.code not in {"NDC_RENDERER_UNAVAILABLE", "NDC_RENDER_FAILED"}:
            write_json_native_run(
                root,
                {
                    **base_result,
                    "status": "failed",
                    "errors": [
                        {
                            "code": str(getattr(exc, "code", "NDC_COMPILE_FAILED")),
                            "message": str(exc),
                            "page_id": getattr(exc, "page_id", None),
                            "element_id": getattr(exc, "element_id", None),
                        }
                    ],
                },
            )
        raise


def write_json_native_run(root: Path, payload: dict[str, Any]) -> None:
    import jsonschema

    from native_pptx.contracts import SCHEMA_DIR

    schema_path = SCHEMA_DIR / "native-compile-result.v1.schema.json"
    jsonschema.Draft202012Validator(
        json.loads(schema_path.read_text(encoding="utf-8")), format_checker=jsonschema.FormatChecker()
    ).validate(payload)
    path = root / "build" / "native_compile_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dispatch_imagegen_task(run_dir: str | Path) -> dict[str, Any]:
    """Compatibility entry: issue the same durable native host task."""
    from build.native_content import ensure_native_content
    from build.native_tasks import dispatch_native_task

    root = Path(run_dir).expanduser().resolve()
    packages = _approved_packages(root)
    ensure_native_content(root, packages)
    return dispatch_native_task(root, "imagegen", packages)


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


def _load_request_safe(root: Path) -> dict[str, Any]:
    request_path = root / "request.json"
    if not request_path.exists():
        return {}
    try:
        return json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
