"""Discover only the tools and fonts used by the file pipeline."""
import os
import sys
from .render import NeedsTool, executable, renderer_environment, resolve_fonts

TOOL_FIXES = {
    "soffice": (
        "缺少 LibreOffice 的 soffice。macOS：brew install --cask libreoffice；"
        "Debian/Ubuntu：sudo apt-get install -y libreoffice-impress。"
        "装好后重新运行 deck doctor。"
    ),
    "pdftoppm": (
        "缺少 Poppler 的 pdftoppm。macOS：brew install poppler；"
        "Debian/Ubuntu：sudo apt-get install -y poppler-utils。"
        "装好后重新运行 deck doctor。"
    ),
    "fc-match": (
        "缺少 Fontconfig 的 fc-match。macOS：brew install fontconfig；"
        "Debian/Ubuntu：sudo apt-get install -y fontconfig。"
        "装好后重新运行 deck doctor。"
    ),
    "rsvg-convert": (
        "缺少 rsvg-convert。macOS：brew install librsvg；"
        "Debian/Ubuntu：sudo apt-get install -y librsvg2-bin。"
        "装好后重新运行 deck doctor。"
    ),
}
MACOS_BREW_BUNDLE_HINT = (
    "macOS 一键补齐渲染依赖："
    "brew install librsvg poppler fontconfig && brew install --cask libreoffice"
)
FONT_HINT = (
    "未检查字体。请运行 deck doctor --fonts <设计里的字体名>；"
    "字体缺失时，用 fc-list : family 选一个已安装的字体，设计和 SVG 里都改用它的名字。"
)


def diagnose(fonts):
    checks = [{"name": "python", "available": True, "path": sys.executable}]
    missing_tools = []
    for name in ("soffice", "pdftoppm", "fc-match", "rsvg-convert"):
        try:
            checks.append({"name": name, "available": True, "path": executable(name)})
        except NeedsTool as exc:
            missing_tools.append(name)
            detail = TOOL_FIXES.get(name) or str(exc)
            checks.append({"name": name, "available": False, "detail": detail})
    try:
        env = renderer_environment()
        fc_entry = {"name": "renderer_fontconfig", "available": True}
        fc_file = (env or {}).get("FONTCONFIG_FILE") or os.environ.get("FONTCONFIG_FILE")
        if fc_file:
            fc_entry["path"] = fc_file
        checks.append(fc_entry)
    except NeedsTool as exc:
        missing_tools.append("renderer_fontconfig")
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
    result = {"status": status, "checks": checks}
    if sys.platform == "darwin" and missing_tools:
        result["macos_brew_hint"] = MACOS_BREW_BUNDLE_HINT
    return result
