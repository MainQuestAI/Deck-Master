"""Detached loopback workbench server entry.

``python -m deck_master.view_server --project <dir> --port <n>`` runs the
read-only workbench in the foreground of its own process, so a CLI that
spawns it detached can exit while the service keeps serving (spec 09.5).
Parent records pid/port in ``view.json``; a stale entry is health-checked
and replaced on the next ``view --open``.
"""

from __future__ import annotations

import argparse
import signal
import secrets
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

from .store import Store
from .web import _static_dir, WorkbenchHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deck-master-view-server")
    parser.add_argument("--project", required=True)
    parser.add_argument("--port", type=int, required=True)
    options = parser.parse_args(argv)
    store = Store(Path(options.project).expanduser().resolve())
    handler = type(
        "BoundHandler",
        (WorkbenchHandler,),
        {"store": store, "static_dir": _static_dir(), "write_token": secrets.token_urlsafe(32)},
    )
    server = ThreadingHTTPServer(("127.0.0.1", options.port), handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
