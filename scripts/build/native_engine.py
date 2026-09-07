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
    packages = PagePackageIndex(root).list_packages()
    approved = [pkg for pkg in packages if str(pkg.get("status") or "") in {"ready_for_build", "ready"}]
    if not approved:
        raise NativeEngineError("no approved page packages (ready_for_build) to compile")
    return approved


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
    route = resolve_build_route(request)
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


def submit_approved_svg(run_dir: str | Path, page_id: str, svg_text: str, *, action_id: str, task_id: str = "native-svg") -> dict[str, Any]:
    """Stage one host-authored SVG for approval-checked compilation.

    Staging + revision pointer semantics come from the existing action
    envelope; the approved SVG lands under high_density_build/svg (the
    single layout the validator/compiler share).
    """

    root = Path(run_dir).expanduser().resolve()
    from workflow.actions import commit_action_result, stage_action_result

    envelope = {
        "schema_version": "deck_stage_action.v1",
        "action_id": f"svg_{page_id}_{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
        "task_id": str(task_id),
        "scope_pages": [page_id],
        "permission": "agent",
        "input_fingerprint": "host_svg",
    }
    stage_action_result(root, envelope, {"svg": svg_text})
    marker = commit_action_result(
        root,
        envelope,
        current_input_fingerprint="host_svg",
        targets={"svg": root / "high_density_build" / "svg" / f"{page_id}.svg"},
    )
    return {"status": "svg_staged", "page_id": page_id, "revision_id": marker.get("revision_id", "")}


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
    result = compile_svg_deck(
        NativeCompileRequest(
            root=root,
            scenes=scenes,
            locks=locks,
            asset_paths_by_page={},
            validate_approved=validate_approved_svg,
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
