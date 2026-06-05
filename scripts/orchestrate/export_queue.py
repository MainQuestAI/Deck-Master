from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PREVIEW_DIR = Path(__file__).resolve().parents[1] / "preview"
sys.path.insert(0, str(PREVIEW_DIR))

from manifest import DECISIONS, load_manifest


def export_queue(run_dir: Path, decisions: set[str]) -> dict[str, Any]:
    invalid = decisions - DECISIONS
    if invalid:
        raise ValueError(f"Invalid decisions: {', '.join(sorted(invalid))}")

    manifest = load_manifest(run_dir)
    pages = [
        {
            "page_id": page["page_id"],
            "order": page["order"],
            "title": page.get("title", page["page_id"]),
            "source_type": page["source_type"],
            "decision": page["decision"],
            "preview_path": page["preview_path"],
            "source_preview_asset": page.get("source_preview_asset", ""),
            "source_pptx": page.get("source_pptx", ""),
            "source_slide_index": page.get("source_slide_index", ""),
            "source_project": page.get("source_project", ""),
            "narrative_role": page.get("narrative_role", ""),
            "notes": page.get("notes", ""),
        }
        for page in manifest["pages"]
        if page["decision"] in decisions
    ]
    return {
        "run_id": manifest["run_id"],
        "title": manifest["title"],
        "source_manifest": str((run_dir / "preview_manifest.json").resolve()),
        "decisions": sorted(decisions),
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the reviewed page queue for the next Deck step.")
    parser.add_argument("run_dir", help="Directory containing preview_manifest.json")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument(
        "--decision",
        action="append",
        dest="decisions",
        default=["approved"],
        help="Decision to include. Repeat for multiple decisions.",
    )
    args = parser.parse_args()

    try:
        payload = export_queue(Path(args.run_dir).expanduser().resolve(), set(args.decisions))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).expanduser().resolve().write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
