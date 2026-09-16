"""The rebuilt CLI is delivered with T04; running the module is honest about that."""

from __future__ import annotations

import json
import sys

from . import __version__


def main() -> int:
    payload = {
        "error": "cli_not_implemented_yet",
        "detail": "The rebuilt CLI lands with task card T04 (WP01).",
        "version": __version__,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
