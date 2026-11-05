"""Discover only the tools and fonts used by the file pipeline."""
import sys
from .render import NeedsTool, executable, renderer_environment, resolve_fonts

# rsvg-convert is called directly by SVG raster checks and the preview path, so doctor must check it.
RSVG_FIX = (
    "缺少 rsvg-convert。macOS：brew install librsvg；"
    "Debian/Ubuntu：sudo apt-get install -y librsvg2-bin。"
    "装好后重新运行 deck doctor。"
)
FONT_HINT = (
    "未检查字体。请运行 deck doctor --fonts <设计里的字体名>；"
    "字体缺失时，用 fc-list : family 选一个已安装的字体，设计和 SVG 里都改用它的名字。"
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
