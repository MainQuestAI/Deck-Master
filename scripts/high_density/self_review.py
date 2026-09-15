from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import ContractError
from .svg import record_visual_self_review


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a producer self-review for a high-density visual page")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--observation", action="append", required=True)
    parser.add_argument("--issue", action="append", default=[])
    decision = parser.add_mutually_exclusive_group(required=True)
    decision.add_argument("--revision-required", action="store_true", dest="revision_required")
    decision.add_argument("--no-revision-required", action="store_false", dest="revision_required")
    args = parser.parse_args()
    try:
        path = record_visual_self_review(
            Path(args.run_dir).expanduser().resolve(),
            args.page_id,
            reviewer_id=args.reviewer_id,
            observations=args.observation,
            issues=args.issue,
            revision_required=args.revision_required,
        )
    except ContractError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "recorded", "review": path.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
