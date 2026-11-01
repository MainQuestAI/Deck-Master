"""Discover only the tools and fonts used by the file pipeline."""
import sys
from .render import NeedsTool, executable, renderer_environment, resolve_fonts


def diagnose(fonts):
    checks = [{"name": "python", "available": True, "path": sys.executable}]
    for name in ("soffice", "pdftoppm", "fc-match"):
        try:
            checks.append({"name": name, "available": True, "path": executable(name)})
        except NeedsTool as exc:
            checks.append({"name": name, "available": False, "detail": str(exc)})
    try:
        renderer_environment()
        checks.append({"name": "renderer_fontconfig", "available": True})
    except NeedsTool as exc:
        checks.append({"name": "renderer_fontconfig", "available": False, "detail": str(exc)})
    for name in fonts:
        try:
            resolved = resolve_fonts([{"shapes": [{"kind": "text", "font_family": name, "bold": False}]}])
            checks.append({"name": name, "available": True, "path": resolved[name]})
        except NeedsTool as exc:
            checks.append({"name": name, "available": False, "detail": str(exc)})
    return {"status": "ready" if all(c["available"] for c in checks) else "needs_tool", "checks": checks}
