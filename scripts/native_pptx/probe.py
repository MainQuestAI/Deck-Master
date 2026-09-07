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
    if fonts_dir is not None and fonts_dir.is_dir() and any(fonts_dir.iterdir()):
        checks["fonts"] = {"status": "verified", "source": str(FONTS_ENV), "count": sum(1 for _ in fonts_dir.iterdir())}
    else:
        # system font dirs are a soft probe: compile may still work for the
        # declared subset, but readback text fidelity must record it.
        checks["fonts"] = {"status": "unverified", "source": "system"}
        failures.append("fonts unverified: no DECK_MASTER_NATIVE_FONTS_DIR and no system font probe in this environment")

    engine_version = engine_fp
    status = "ready" if not failures else ("blocked" if any("python-pptx" in f or "failed to import" in f for f in failures) else "degraded_ready")
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
