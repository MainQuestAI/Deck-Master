"""SC-1.1 ND-02: real native runtime capability probe.

Replaces the external PPT Master binding assertion with a probe of what the
default route actually needs: the kernel modules import, python-pptx is
present, the SVG subset pieces load, and (when a renderer is configured)
the renderer/字体 environment responds. No HOME probing, no external
product directory checks, no environment-variable shortcuts — ``installed``
or ``contract_declared`` never equals ``verified``.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROBE_SCHEMA_VERSION = "deck_native_runtime_probe.v1"
FONTS_ENV = "DECK_MASTER_NATIVE_FONTS_DIR"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _engine_fingerprint() -> str:
    import hashlib

    digest = hashlib.sha256()
    package_dir = Path(__file__).resolve().parent
    for module in sorted(package_dir.glob("*.py")):
        digest.update(module.name.encode("utf-8"))
        digest.update(hashlib.sha256(module.read_bytes()).digest())
    return digest.hexdigest()[:16]


def probe_native_runtime() -> dict[str, Any]:
    """Probe the built-in native runtime for real capability evidence."""

    checks: dict[str, Any] = {}
    failures: list[str] = []
    engine_fp = _engine_fingerprint()

    try:
        import pptx  # noqa: F401

        checks["python_pptx"] = {"status": "verified", "version": str(getattr(pptx, "__version__", ""))}
    except Exception as exc:  # noqa: BLE001
        checks["python_pptx"] = {"status": "blocked", "error": str(exc)}
        failures.append("python-pptx is unavailable: " + str(exc))

    for module_name in ("native_pptx.pptx", "native_pptx.svg_pipeline", "native_pptx.svg_native", "native_pptx.svg_paint", "native_pptx.visibility"):
        try:
            __import__(module_name)
            checks[module_name] = {"status": "verified"}
        except Exception as exc:  # noqa: BLE001
            checks[module_name] = {"status": "blocked", "error": str(exc)}
            failures.append(f"{module_name} failed to import: {exc}")

    from .canvas import CANVAS_HEIGHT, CANVAS_WIDTH

    checks["canvas"] = {"status": "verified", "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}

    fonts_value = str(__import__("os").environ.get(FONTS_ENV, "")).strip()
    fonts_dir = Path(fonts_value) if fonts_value else None
    font_verified = False
    font_detail: dict[str, Any] = {"status": "unverified", "source": str(FONTS_ENV) if fonts_value else "system"}
    if fonts_dir is not None and fonts_dir.is_dir():
        for font_file in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")) + list(fonts_dir.glob("*.ttc"))):
            try:
                from PIL import ImageFont

                ImageFont.truetype(str(font_file), 12)
                font_verified = True
                font_detail = {"status": "verified", "source": str(FONTS_ENV), "font": font_file.name}
                break
            except Exception:  # noqa: BLE001 - try the next font file
                continue
    if font_verified:
        checks["fonts"] = font_detail
    else:
        # A non-empty directory is NOT font evidence — a real font file must
        # load. Unverified fonts degrade (readback text fidelity) but do not
        # block compilation.
        checks["fonts"] = font_detail
        failures.append("fonts unverified: no loadable font file found (truetype load required)")

    # SC-1.1 review: "verified" needs real evidence, not import success.
    # compilable: run a minimal SVG->PPTX compile through the kernel.
    compilable_check = _probe_compilable()
    checks["compile_smoke"] = compilable_check
    if compilable_check["status"] != "verified":
        failures.append("native compile smoke failed: " + str(compilable_check.get("error", "")))

    engine_version = engine_fp
    hard_failures = [f for f in failures if "failed to import" in f or "python-pptx" in f or "compile smoke failed" in f]
    status = "ready" if not failures else ("blocked" if hard_failures else "degraded_ready")
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "probe_id": f"native_probe_{engine_fp}",
        "engine_id": "deck_native",
        "engine_version": engine_version,
        "checked_at": _utc_now(),
        "checks": checks,
        "required_missing": failures if status == "blocked" else [],
        "optional_unavailable": [f for f in failures if status != "blocked"],
        "status": status,
        "renderer": {"configured": False, "note": "renderer wiring lands with the engine adapter (ND-02/ND-03)"},
    }


def native_runtime_ready(probe: dict[str, Any] | None = None) -> bool:
    probe = probe or probe_native_runtime()
    return str(probe.get("status") or "") in {"ready", "degraded_ready"}


def public_probe_summary(probe: dict[str, Any]) -> dict[str, Any]:
    """Redacted public view: no absolute paths, no machine specifics."""

    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "engine_id": probe.get("engine_id", "deck_native"),
        "probe_id": probe.get("probe_id", ""),
        "status": probe.get("status", ""),
        "checks": {name: {"status": item.get("status", "")} for name, item in (probe.get("checks") or {}).items()},
        "required_missing": list(probe.get("required_missing") or []),
        "optional_unavailable": list(probe.get("optional_unavailable") or []),
        "renderer": probe.get("renderer", {}),
    }


def _probe_compilable() -> dict[str, Any]:
    """Real kernel evidence beyond imports (SC-1.1 review: import !=
    verified). Generates a subset-constrained SVG and drives it through the
    kernel's validate + native-parse + paint-parse pipeline. Full PPTX
    emission requires the run's scene/lock contracts and stays with the
    engine adapter; this probe verifies the kernel parsing core."""

    import tempfile

    try:
        with tempfile.TemporaryDirectory(prefix="native_probe_") as tmp:
            root = Path(tmp)
            from .svg_pipeline import CANVAS_HEIGHT, CANVAS_WIDTH, validate_svg

            svg_path = root / "probe.svg"
            svg_path.write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
                'data-pptx-page-role="content" width="1672" height="941">'
                '<rect id="p.bg" x="0" y="0" width="1672" height="941" fill="#ffffff" stroke="none" '
                'stroke-width="0" data-pptx-bounds="0,0,1672,941"/>'
                '<text id="p.t" x="80" y="120" font-family="Arial" font-size="28" font-weight="bold" '
                'fill="#18212b" data-pptx-bounds="80,90,400,50" data-pptx-text="Probe" data-pptx-text-ref="p.t">Probe</text>'
                "</svg>",
                encoding="utf-8",
            )
            result = validate_svg(svg_path, page_id="PROBE")
            if not result.get("valid"):
                return {"status": "blocked", "error": "kernel validate_svg rejected the probe SVG"}
            from xml.etree import ElementTree

            from .svg_native import parse_svg_native
            from .svg_paint import parse_svg_paint

            document = ElementTree.fromstring(svg_path.read_text(encoding="utf-8"))
            native = parse_svg_native(document)
            paint = parse_svg_paint(document)
            if not native.get("elements") or not paint:
                return {"status": "blocked", "error": "kernel parse returned no elements/paint"}
            return {"status": "verified", "elements": len(native.get("elements") or []), "paint_entries": len(paint)}
    except Exception as exc:  # noqa: BLE001 - probe reports the failure
        return {"status": "blocked", "error": str(exc)}
