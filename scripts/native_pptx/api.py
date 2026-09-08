"""SC-1.1 ND-01: native compile facade (spec 03 §3.2 target API).

``compile_svg_deck`` / ``readback_pptx`` wrap the single compile
implementation (``native_pptx.pptx``) with hash validation and versioned
identity. The compiler receives NO backend binding and never queries an
external PPT Master product; result objects carry compile status only —
``client_delivery_ready`` is decided by gates/approval, never here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Callable

from .contracts import ContractError, sha256_file
from .pptx import PptxEditabilityError, compile_pptx, readback_pptx as _readback_impl
from .svg_pipeline import SvgVisualError

ENGINE_ID = "deck_native"
ENGINE_VERSION = "native_pptx/1.1"
SVG_SUBSET_VERSION = "hd-svg-subset/1"

# NDC_* error codes (spec 03 §3.7) mapped from the existing error surfaces.
NDC_ERROR_MAP = {
    "HD_SVG_UNSUPPORTED_ELEMENT": "NDC_SVG_UNSUPPORTED",
    "HD_SVG_UNSAFE_ATTRIBUTE": "NDC_SVG_UNSUPPORTED",
    "HD_ASSET_POLICY_BLOCKED": "NDC_ASSET_UNREGISTERED",
}
NDC_COMPILE_FAILED = "NDC_COMPILE_FAILED"
NDC_READBACK_FAILED = "NDC_READBACK_FAILED"
NDC_RENDERER_UNAVAILABLE = "NDC_RENDERER_UNAVAILABLE"


class NativeCompileError(RuntimeError):
    """Native kernel error carrying page_id, element_id, code and recovery."""

    def __init__(
        self,
        message: str,
        *,
        code: str = NDC_COMPILE_FAILED,
        page_id: str = "",
        element_id: str = "",
        expected: Any = None,
        actual: Any = None,
        input_sha256: str = "",
        recovery: str = "",
    ) -> None:
        self.code = code
        self.page_id = page_id
        self.element_id = element_id
        self.expected = expected
        self.actual = actual
        self.input_sha256 = input_sha256
        self.recovery = recovery
        super().__init__(message)


@dataclass
class NativeCompileRequest:
    """Validated compile inputs resolved by the Run adapter (never by HOME)."""

    root: Path
    scenes: list[dict[str, Any]]
    locks: dict[str, dict[str, Any]]
    asset_paths_by_page: dict[str, dict[str, Path]] = field(default_factory=dict)
    validate_approved: Callable[[Path, dict[str, Any], dict[str, Any], dict[str, Path]], None] | None = None
    expected_sha256: dict[str, str] = field(default_factory=dict)  # page_id -> pinned approved-SVG sha

    svg_paths: dict[str, Path] = field(default_factory=dict)
    output_root: Path | None = None
    canvas_mode: str = "legacy"

    def _svg(self, page_id: str) -> Path:
        path = self.svg_paths.get(page_id)
        if path is None:
            path = self.root / "high_density_build" / "svg" / f"{page_id}.svg"
        elif not Path(path).is_absolute():
            path = self.root / path
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_relative_to(self.root.expanduser().resolve()):
            raise NativeCompileError("SVG input escapes the request root", code="NDC_INPUT_PATH_INVALID", page_id=page_id)
        return resolved

    def validated(self) -> "NativeCompileRequest":
        if self.canvas_mode not in {"native", "legacy"}:
            raise NativeCompileError("unknown canvas_mode")
        page_ids = [str(scene.get("page_id") or "") for scene in self.scenes]
        if len(set(page_ids)) != len(page_ids) or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", page_id) for page_id in page_ids):
            raise NativeCompileError("duplicate or unsafe compile page ids")
        root = self.root.expanduser().resolve()
        for assets in self.asset_paths_by_page.values():
            for path in assets.values():
                if not Path(path).resolve().is_relative_to(root):
                    raise NativeCompileError("asset input escapes the request root", code="NDC_INPUT_PATH_INVALID")
        if self.canvas_mode == "native" and any(not self.expected_sha256.get(page_id) for page_id in page_ids):
            raise NativeCompileError("native compile requires an approved SVG hash for every page", code="NDC_INPUT_HASH_MISSING")
        for scene in self.scenes:
            page_id = str(scene.get("page_id") or "")
            svg = self._svg(page_id)
            pinned = self.expected_sha256.get(page_id)
            if pinned:
                if not svg.exists():
                    raise NativeCompileError(
                        f"page {page_id}: approved SVG is missing but a hash was pinned",
                        code=NDC_READBACK_FAILED,
                        page_id=page_id,
                        recovery="re-run the SVG stage for this page before compiling",
                    )
                actual = sha256_file(svg)
                if actual != pinned:
                    raise NativeCompileError(
                        f"page {page_id}: approved SVG changed since approval",
                        code=NDC_READBACK_FAILED,
                        page_id=page_id,
                        input_sha256=actual,
                        recovery="re-run the SVG stage for this page before compiling",
                    )
        return NativeCompileRequest(
            root=self.root.expanduser().resolve(),
            scenes=self.scenes,
            locks=self.locks,
            asset_paths_by_page=self.asset_paths_by_page,
            validate_approved=self.validate_approved,
            expected_sha256=dict(self.expected_sha256),
            svg_paths={page_id: self._svg(page_id) for page_id in page_ids},
            output_root=self.output_root,
            canvas_mode=self.canvas_mode,
        )


@dataclass
class NativeCompileResult:
    status: str
    pptx_path: Path
    trace_path: Path
    engine_id: str = ENGINE_ID
    engine_version: str = ENGINE_VERSION
    svg_subset_version: str = SVG_SUBSET_VERSION
    input_sha256: dict[str, str] = field(default_factory=dict)
    root: Path | None = None
    output_root: Path | None = None
    page_ids: list[str] = field(default_factory=list)
    canvas_mode: str = "legacy"
    svg_paths: dict[str, Path] = field(default_factory=dict)


def compile_svg_deck(request: NativeCompileRequest) -> NativeCompileResult:
    """Compile approved SVGs + scenes into a native PPTX with a real trace."""

    request = request.validated()
    root = request.root
    if request.validate_approved is None:
        raise NativeCompileError(
            "compile_svg_deck requires validate_approved (adapter-injected approved-SVG validator); "
            "refusing to compile without the business validation pass",
            recovery="wire the adapter validator before compiling",
        )
    try:
        pptx, trace = compile_pptx(
            root,
            request.scenes,
            request.locks,
            asset_paths_by_page=request.asset_paths_by_page,
            validate_approved=request.validate_approved,
            svg_paths=request.svg_paths,
            output_root=request.output_root,
            canvas_mode=request.canvas_mode,
        )
    except PptxEditabilityError as exc:
        raise NativeCompileError(str(exc), code=NDC_COMPILE_FAILED, recovery="repair the page and recompile") from exc
    except SvgVisualError as exc:
        page_id = str(getattr(exc, "page_id", "") or "")
        svg_file = request._svg(page_id)
        raise NativeCompileError(
            str(exc),
            code=NDC_ERROR_MAP.get(str(getattr(exc, "code", "")), NDC_COMPILE_FAILED),
            page_id=page_id,
            input_sha256=sha256_file(svg_file) if svg_file.exists() else "",
            recovery="fix the SVG subset violation on the page and re-approve it",
        ) from exc
    except ContractError as exc:
        raise NativeCompileError(str(exc), code=NDC_COMPILE_FAILED) from exc
    input_sha = {
        str(scene.get("page_id") or ""): sha256_file(request._svg(str(scene.get("page_id") or "")))
        for scene in request.scenes
        if str(scene.get("page_id") or "")
    }
    if any(input_sha.get(page_id) != expected for page_id, expected in request.expected_sha256.items()):
        raise NativeCompileError("approved SVG changed during compilation", code=NDC_READBACK_FAILED,
                                 recovery="retry from the committed input revision")
    return NativeCompileResult(status="compiled", pptx_path=pptx, trace_path=trace, input_sha256=input_sha,
                               root=root, output_root=request.output_root, page_ids=list(input_sha), canvas_mode=request.canvas_mode,
                               svg_paths=request.svg_paths, svg_subset_version="native-svg-subset/1" if request.canvas_mode == "native" else SVG_SUBSET_VERSION)


def readback_pptx(result: NativeCompileResult, scenes: list[dict[str, Any]], locks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Readback the compiled deck against its scenes/locks (trace-verified)."""

    if result.canvas_mode == "native" or result.output_root is not None:
        from .readback import readback_native
        return readback_native(result, scenes, locks)
    root = result.root or result.pptx_path.parent.parent.parent  # legacy callers only
    try:
        report_path = _readback_impl(root, scenes, locks, result.pptx_path)
    except PptxEditabilityError as exc:
        raise NativeCompileError(str(exc), code=NDC_READBACK_FAILED, recovery="recompile after fixing the page") from exc
    return {"schema_version": "deck_native_readback.v1", "report_path": str(report_path)}


def render_pptx(result: NativeCompileResult, renderer: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render a compiled deck into a fresh output root; never grants approval."""
    from .render import RenderError, render_deck

    config = renderer or {}
    if result.status != "compiled":
        raise NativeCompileError("cannot render an uncompiled result")
    page_ids = result.page_ids
    if not page_ids:
        try:
            page_ids = [str(page.get("page_id") or "") for page in json.loads(result.trace_path.read_text(encoding="utf-8")).get("pages", [])]
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise NativeCompileError("render trace is missing or invalid", code="NDC_RENDER_FAILED") from exc
    output = Path(config.get("output_root") or (result.output_root or result.pptx_path.parent) / "rendered")
    try:
        return render_deck(result.pptx_path, page_ids, output,
                           timeout_seconds=float(config.get("timeout_seconds", 120)), dpi=int(config.get("dpi", 144)))
    except RenderError as exc:
        raise NativeCompileError(str(exc), code=exc.code, recovery="repair the renderer and retry in a fresh revision") from exc
