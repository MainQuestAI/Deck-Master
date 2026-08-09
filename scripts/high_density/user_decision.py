from __future__ import annotations

import argparse
import json
from pathlib import Path

from .content import record_mbb_user_decision
from .contracts import ContractError


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a host-attested MBB storyline decision.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--storyline-id", required=True)
    parser.add_argument("--attestor-id", required=True)
    args = parser.parse_args()
    try:
        path = record_mbb_user_decision(Path(args.run_dir).expanduser().resolve(), args.storyline_id, attestor_id=args.attestor_id)
    except ContractError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "recorded", "receipt": path.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
