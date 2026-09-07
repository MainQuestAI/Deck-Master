"""SC-1.1 ND-01: native compile facade (spec 03 §3.2 target API).

``compile_svg_deck`` / ``readback_pptx`` wrap the single compile
implementation (``native_pptx.pptx``) with hash validation and versioned
identity. The compiler receives NO backend binding and never queries an
external PPT Master product; result objects carry compile status only —
``client_delivery_ready`` is decided by gates/approval, never here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .contracts import ContractError, sha256_file
from .pptx import PptxEditabilityError, compile_pptx, readback_pptx as _readback_impl
from .svg_pipeline import SvgVisualError

ENGINE_ID = "deck_native"
ENGINE_VERSION = "native_pptx/1.0"
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

    def _svg(self, page_id: str) -> Path:
        return self.root.expanduser().resolve() / "high_density_build" / "svg" / f"{page_id}.svg"

    def validated(self) -> "NativeCompileRequest":
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
        )
    except PptxEditabilityError as exc:
        raise NativeCompileError(str(exc), code=NDC_COMPILE_FAILED, recovery="repair the page and recompile") from exc
    except SvgVisualError as exc:
        page_id = str(getattr(exc, "page_id", "") or "")
        svg_file = root / "high_density_build" / "svg" / f"{page_id}.svg"
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
        str(scene.get("page_id") or ""): sha256_file(root / "high_density_build" / "svg" / f"{scene.get('page_id')}.svg")
        for scene in request.scenes
        if str(scene.get("page_id") or "")
    }
    return NativeCompileResult(status="compiled", pptx_path=pptx, trace_path=trace, input_sha256=input_sha)


def readback_pptx(result: NativeCompileResult, scenes: list[dict[str, Any]], locks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Readback the compiled deck against its scenes/locks (trace-verified)."""

    root = result.pptx_path.parent.parent.parent  # run root (high_density_build/pptx/<file> -> run)
    try:
        report_path = _readback_impl(root, scenes, locks, result.pptx_path)
    except PptxEditabilityError as exc:
        raise NativeCompileError(str(exc), code=NDC_READBACK_FAILED, recovery="recompile after fixing the page") from exc
    return {"schema_version": "deck_native_readback.v1", "report_path": str(report_path)}


def render_pptx(result: NativeCompileResult, renderer: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render pages of a compiled deck; the renderer wiring lands with the
    engine adapter (ND-02/ND-03). Until then this fails closed."""

    raise NativeCompileError(
        "NDC_RENDERER_UNAVAILABLE: no renderer is wired for this environment",
        code=NDC_RENDERER_UNAVAILABLE,
        recovery="configure the local renderer or run visual checks via the host",
    )
