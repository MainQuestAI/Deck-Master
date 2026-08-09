from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any


REQUIRED_SCHEMAS = (
    "content-lock.v2.schema.json",
    "blueprint-prompt.v1.schema.json",
    "blueprint-content-review.v1.schema.json",
    "blueprint-manifest.v2.schema.json",
    "page-scene.v2.schema.json",
    "visual-metrics.v1.schema.json",
    "visual-review.v2.schema.json",
    "svg-to-drawingml-trace.v1.schema.json",
    "pptx-readback.v2.schema.json",
    "high-density-manifest.v2.schema.json",
    "high-density-status.v2.schema.json",
    "nbb-plan.v1.schema.json",
    "style-lock.v1.schema.json",
)


def _font_ready() -> tuple[bool, str]:
    candidates = [
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return True, str(candidate)
    if shutil.which("fc-match"):
        return True, "fc-match"
    return False, "no approved sans-serif font found"


def inspect_high_density_capability(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    checks: list[dict[str, Any]] = []
    schema_dir = root / "docs" / "contracts"
    missing_schemas = [name for name in REQUIRED_SCHEMAS if not (schema_dir / name).is_file()]
    checks.append({"name": "v2_schemas", "ready": not missing_schemas, "missing": missing_schemas})
    packages = {}
    for package in ("jsonschema", "pptx", "PIL", "numpy"):
        ready = importlib.util.find_spec(package) is not None
        packages[package] = ready
    checks.append({"name": "python_packages", "ready": all(packages.values()), "packages": packages})
    renderers = {"svg": shutil.which("rsvg-convert") or "", "pptx": shutil.which("soffice") or "", "pdf_to_png": shutil.which("pdftoppm") or ""}
    checks.append({"name": "renderers", "ready": all(renderers.values()), "renderers": renderers})
    font_ready, font_detail = _font_ready()
    checks.append({"name": "fonts", "ready": font_ready, "detail": font_detail})
    ready = all(bool(check["ready"]) for check in checks)
    return {
        "capability": "deck_master.build.high_density.v1",
        "status": "ready" if ready else "blocked_runtime_dependency",
        "ready": ready,
        "checks": checks,
        "production_requirements": ["v2 schemas", "jsonschema", "python-pptx", "Pillow", "NumPy", "rsvg-convert", "soffice", "pdftoppm", "sans-serif font"],
    }


__all__ = ["inspect_high_density_capability"]
