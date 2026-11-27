"""Multi-page native PPTX assembly, sanitization, and readback."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from .. import sanitize
from .generate import generate
from .plan import _resolve_native_fonts, read_json
from .readback import readback


def assemble(job):
    from . import render_deck as package_render_deck

    output = (Path(job["work"]) / "native" / "deck.pptx").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    plans = [read_json(p["plan"]) for p in job["pages"]]
    resolved_fonts = _resolve_native_fonts(plans)
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix=".deck-", suffix=".pptx", delete=False
    ) as temp:
        temporary = Path(temp.name)
    warnings = []
    hints = []
    try:
        _, _, warnings = generate(job["pages"], temporary, mode="deck")
        temporary.write_bytes(
            sanitize.pptx(
                temporary.read_bytes(),
                "deck.pptx",
                notes=[{"page_id": p["id"], "notes": p.get("notes", "")} for p in job["pages"]],
                findings=hints,
            )
        )
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    directory = output.parent / "deck-render"
    with tempfile.TemporaryDirectory(prefix="deck-native-deck-") as temp:
        images = package_render_deck(output, temp, fonts=resolved_fonts)
        if len(images) != len(job["pages"]):
            raise RuntimeError("整套渲染页数与输入不一致")
        directory.mkdir(exist_ok=True)
        previews = []
        for i, image in enumerate(images, 1):
            target = directory / f"page-{i}.png"
            target.write_bytes(image.read_bytes())
            previews.append(str(target))
    report = readback(output, job["pages"])
    if warnings:
        report["warnings"] = warnings
    sanitize.attach_hint_findings(report, hints)
    return {"pptx": str(output), "render_pngs": previews, "findings": report}
