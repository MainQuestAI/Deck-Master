# W01 read-model example

Run from a source checkout with the project's Python dependencies installed:

```sh
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-example
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-base-300 --pages 300
PYTHONPATH=src python examples/workbench/w01_lineage.py --out /tmp/w01-browser --serve
```

The output directory must be new. The script creates a temporary **synthetic**
project through the core, stores mixed-stage test artifacts and a saved request,
then takes project/revision/page/ref IDs from actual responses. It checks pinned
history after a later core edit, prompt separation, read-only behavior and a
missing-version error. The project is removed on exit; inputs, raw responses,
manifest and 100 latency samples remain in the output directory.

`--serve` keeps the temporary service alive for browser checks until Ctrl-C.
Its first title contains inert attack text and its SVG contains an intentionally
blocked script. These fixtures are not suitable for a production deck. No
Host/model, renderer, install or customer-delivery claim comes from this script.

The 300-page sample has **zero Candidates and Attempts**, with no concurrent
updates during sampling. It cannot close W01-AC01's 300×5×3 pressure requirement.

## CLI and HTTP

| CLI | HTTP |
| --- | --- |
| `view --project <dir> --summary [--revision <id>] --json` | `/api/view/summary?revision=<id>` (alias `/api/workbench`) |
| `view --project <dir> --revision <id> --json` | `/api/view?revision=<id>` |
| `view --project <dir> --page-id <id> [--revision <id>] --json` | `/api/pages/<id>?revision=<id>` |
| `view --project <dir> --page-id <id> --lineage [--revision <id>] --json` | `/api/pages/<id>/lineage?revision=<id>` |
| Existing `view --project <dir> --json` | Service status (unchanged) |

`/api/tasks` and `/api/reviews` also honor revision. All routes retain the bound
project and loopback Host restrictions. Reads require no token; write safety is
unchanged. Every explicit version must be a committed ancestor of the captured
current pointer. Invalid versions do not fall back to current. The two new
schemas are read projections, not additional persistent object types.

The summary omits page bodies, prompt text and candidate/attempt detail. It
reprojects the selected Document with a bounded immutable JSON-object cache;
keys include project root, object path/hash and inode/size/mtime/ctime. Path and
symlink checks run even on cache hits. Reads validate object bytes and contracts;
binary files are hash-checked by `/api/file`, not repeatedly during polling.
Detail reads stored request/submitted text and never rerun prompt projection.
Legacy actual text is only `host_reported`; result linkage without a saved
binding is `unknown`. A PPT preview co-recorded with an output has a `derived`
snapshot relationship, not a proven compiler parent.
