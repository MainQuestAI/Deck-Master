"""Discover only the tools and fonts used by the file pipeline."""
import sys
from .render import NeedsTool, executable, renderer_environment, resolve_fonts

# SVG raster checks and the skill's preview path call rsvg-convert directly.
# A doctor that never looks for it reports ready on a machine that cannot run them.
RSVG_FIX = (
    "缺少 rsvg-convert。macOS：brew install librsvg；"
    "Debian/Ubuntu：sudo apt-get install -y librsvg2-bin。"
    "装好后重新运行 deck doctor。"
)
# Omitting --fonts used to look the same as "fonts are fine".
FONT_HINT = (
    "未检查字体。请运行 deck doctor --fonts <设计里的字体名>；"
    "缺字体时用 fc-list : family 选出已安装字体，并在设计与 SVG 里写这个名字。"
)


def diagnose(fonts):
    checks = [{"name": "python", "available": True, "path": sys.executable}]
    for name in ("soffice", "pdftoppm", "fc-match", "rsvg-convert"):
        try:
            checks.append({"name": name, "available": True, "path": executable(name)})
        except NeedsTool as exc:
            detail = RSVG_FIX if name == "rsvg-convert" else str(exc)
            checks.append({"name": name, "available": False, "detail": detail})
    try:
        renderer_environment()
        checks.append({"name": "renderer_fontconfig", "available": True})
    except NeedsTool as exc:
        checks.append({"name": "renderer_fontconfig", "available": False, "detail": str(exc)})
    if fonts:
        for name in fonts:
            try:
                resolved = resolve_fonts([{"shapes": [{"kind": "text", "font_family": name, "bold": False}]}])
                checks.append({"name": name, "available": True, "path": resolved[name]})
            except NeedsTool as exc:
                checks.append({"name": name, "available": False, "detail": str(exc)})
    else:
        checks.append({"name": "fonts", "level": "warn", "available": False, "detail": FONT_HINT})
    blocking = [item for item in checks if item.get("level") != "warn"]
    status = "ready" if all(item["available"] for item in blocking) else "needs_tool"
    return {"status": status, "checks": checks}
