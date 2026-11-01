"""Host-environment portability helpers for the rebuild test suite.

Font families and tool assumptions differ across maintainer machines and CI
runners; tests must resolve what the host actually has instead of assuming
macOS fonts or repository-local virtualenv paths.
"""
from __future__ import annotations

import functools
import shutil
import subprocess

FONT_CANDIDATES = ("Hiragino Sans GB", "Noto Sans CJK SC", "Noto Sans CJK JP",
                   "DejaVu Sans", "Helvetica", "Arial")


@functools.lru_cache(maxsize=1)
def resolve_host_font() -> str:
    """First candidate font family that fc-match resolves exactly."""
    if not shutil.which("fc-match"):
        raise RuntimeError("fc-match unavailable; cannot resolve a host font family")
    for candidate in FONT_CANDIDATES:
        result = subprocess.run(["fc-match", "-f", "%{family}", candidate],
                                capture_output=True, text=True, check=True)
        if candidate.lower() in result.stdout.lower():
            return candidate
    raise RuntimeError(f"no resolvable font family among {FONT_CANDIDATES}")


@functools.lru_cache(maxsize=1)
def host_font_file() -> str:
    """Resolved font file path for :func:`resolve_host_font`."""
    result = subprocess.run(["fc-match", "-f", "%{file}", resolve_host_font()],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def host_fonts() -> dict:
    """CompileOptions-ready fonts mapping for the resolved host family."""
    return {resolve_host_font(): host_font_file()}
