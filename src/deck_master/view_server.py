"""Internal detached service runner; the public command remains deck-master."""
from __future__ import annotations

import argparse
import signal
import sys
import threading

from . import local_runtime as runtime


def main(argv=None):
    parser = argparse.ArgumentParser(prog="deck-master internal local server")
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--project")
    targets.add_argument("--registry")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--instance-id")
    options = parser.parse_args(argv)
    desc = runtime.descriptor(project=options.project, registry=options.registry)
    server = state = None
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    try:
        server, state = runtime.bind_server(desc, port=options.port, instance_id=options.instance_id)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        if not runtime.healthy(state, desc):
            raise runtime.ServiceUnavailable("service", "bound service failed its own health check")
        runtime.publish(desc, state)
        stopped.wait()
        return 0
    except runtime.ServiceUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if state:
            runtime.clear_own_state(desc, state["instance_id"])


if __name__ == "__main__":
    raise SystemExit(main())
