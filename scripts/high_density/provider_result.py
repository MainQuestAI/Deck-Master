from __future__ import annotations

import argparse
import json
from pathlib import Path

from .blueprint import record_provider_host_result
from .contracts import ContractError


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a Host-managed ImageGen result for a high-density run.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--source-image", required=True)
    args = parser.parse_args()
    try:
        destination = record_provider_host_result(
            Path(args.run_dir).expanduser().resolve(),
            args.page_id,
            Path(args.source_image).expanduser().resolve(),
        )
    except ContractError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "recorded", "blueprint": destination.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
