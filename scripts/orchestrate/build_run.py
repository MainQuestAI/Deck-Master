from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PREVIEW_DIR = Path(__file__).resolve().parents[1] / "preview"
sys.path.insert(0, str(PREVIEW_DIR))

from manifest import MANIFEST_NAME, load_manifest


class BuildRunError(ValueError):
    pass


def load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildRunError(f"Plan file not found: {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise BuildRunError(f"Invalid plan JSON: {exc.msg}") from exc

    for field in ("run_id", "title", "pages"):
        if field not in plan:
            raise BuildRunError(f"Missing required plan field: {field}")
    if not isinstance(plan["pages"], list) or not plan["pages"]:
        raise BuildRunError("Plan pages must be a non-empty list.")
    return plan


def resolve_asset(plan_path: Path, asset_path: str) -> Path:
    candidate = Path(asset_path).expanduser()
    if not candidate.is_absolute():
        candidate = plan_path.parent / candidate
    return candidate.resolve()


def safe_link_name(page_id: str, asset: Path) -> str:
    suffix = asset.suffix or ".png"
    safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in page_id)
    return f"{safe_id}{suffix}"


def reset_run_dir(run_dir: Path, force: bool, preserve_existing: bool = False) -> None:
    if preserve_existing:
        (run_dir / "links").mkdir(parents=True, exist_ok=True)
        (run_dir / "notes").mkdir(parents=True, exist_ok=True)
        return
    if run_dir.exists() and any(run_dir.iterdir()):
        if not force:
            raise BuildRunError(f"Run directory is not empty. Re-run with --force: {run_dir}")
        shutil.rmtree(run_dir)
    (run_dir / "links").mkdir(parents=True, exist_ok=True)
    (run_dir / "notes").mkdir(parents=True, exist_ok=True)


def write_asset_link(source: Path, target: Path, mode: str) -> None:
    if target.exists() or target.is_symlink():
        target.unlink()
    if not source.exists():
        return
    if mode == "copy":
        shutil.copy2(source, target)
    else:
        os.symlink(source, target)


def manifest_page(plan_path: Path, run_dir: Path, page: dict[str, Any], link_mode: str) -> dict[str, Any]:
    for field in ("page_id", "order", "source_type", "preview_asset", "narrative_role"):
        if field not in page:
            raise BuildRunError(f"Page is missing required field: {field}")

    source = resolve_asset(plan_path, page["preview_asset"])
    link_name = safe_link_name(page["page_id"], source)
    write_asset_link(source, run_dir / "links" / link_name, link_mode)

    result = {
        key: value
        for key, value in page.items()
        if key not in {"preview_asset", "decision", "notes"}
    }
    result["preview_path"] = f"links/{link_name}"
    result["decision"] = page.get("decision", "needs_review")
    result["notes"] = page.get("notes", "")
    try:
        result["source_preview_asset"] = str(source.relative_to(run_dir))
    except ValueError:
        result["source_preview_asset"] = str(source)
    result["asset_link_mode"] = link_mode
    return result


def build_run(
    plan_path: Path,
    run_dir: Path,
    force: bool = False,
    link_mode: str = "symlink",
    preserve_existing: bool = False,
) -> dict[str, Any]:
    if link_mode not in {"symlink", "copy"}:
        raise BuildRunError("link_mode must be symlink or copy.")

    plan = load_plan(plan_path)
    reset_run_dir(run_dir, force, preserve_existing=preserve_existing)
    manifest = {
        "run_id": plan["run_id"],
        "title": plan["title"],
        "status": plan.get("status", "draft"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pages": [
            manifest_page(plan_path, run_dir, page, link_mode)
            for page in sorted(plan["pages"], key=lambda item: item["order"])
        ],
    }
    manifest_path = run_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return load_manifest(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Deck Master preview run from an orchestration plan.")
    parser.add_argument("plan", help="JSON plan with pages and preview assets")
    parser.add_argument("run_dir", help="Output run directory")
    parser.add_argument("--force", action="store_true", help="Replace an existing run directory")
    parser.add_argument("--link-mode", choices=["symlink", "copy"], default="symlink")
    parser.add_argument("--preserve-existing", action="store_true", help="Keep existing run artifacts and only refresh preview files")
    args = parser.parse_args()

    try:
        manifest = build_run(
            Path(args.plan).expanduser().resolve(),
            Path(args.run_dir).expanduser().resolve(),
            force=args.force,
            link_mode=args.link_mode,
            preserve_existing=args.preserve_existing,
        )
    except BuildRunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    print(json.dumps({"run_id": manifest["run_id"], "pages": len(manifest["pages"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
