#!/usr/bin/env python3
"""Read one real native Codex image completion without fabricating a receipt.

Run a real built-in image tool first. IDs below must come from its runtime event.
This probe makes no generation call and cannot close the full W02-AC07 chain.
"""
import argparse
import json
from pathlib import Path

from deck_master.observations import collect_codex_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--turn-id", required=True)
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    observation = collect_codex_image({"source": "codex_session.v1", "thread_id": args.thread_id,
                                      "turn_id": args.turn_id, "item_id": args.item_id})
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "native-observation.json").write_text(json.dumps(observation.metadata, ensure_ascii=False, indent=2) + "\n")
    (args.out / "tool-output.png").write_bytes(observation.output_bytes)
    print(json.dumps({"status": "collected", "observer": observation.metadata["observer"],
                      "output_sha256": observation.metadata["output"]["sha256"],
                      "coverage": observation.metadata["coverage"], "W02_AC07": "unverified"}))


if __name__ == "__main__":
    main()
