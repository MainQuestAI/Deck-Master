---
name: ppt-deck-pro-max
description: Deck Master bundled production intelligence capability for generation sessions, page production handoff, and generation result import with run_id plus session_id binding.
triggers:
  - start a generation session
  - run page production
  - import generation results
  - ppt deck pro max
---

# PPT Deck Pro Max Compatibility Entry

This compatibility entry is kept for existing prompts and local installs.
For new Deck Master workflows, prefer `deck-producer`.

Use it for page production inside a Deck Master generation session. Active run
output must return through Deck Master generation-session import.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master generation-session status --run-dir <run_dir> --run-id <run_id>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master generation-session create --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master run-generation --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master generation-session dispatch --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master generation-session import-results --run-dir <run_dir> --run-id <run_id> --input <result.json>
~/.deck-master/bin/deck-master generation-session import-results --run-dir <run_dir> --run-id <run_id> --input <result_dir>
```

## Production Dispatch

Production `run-generation` writes `generation_dispatch/dispatch_package.json` and sets the session to `awaiting_agent_execution`.
Read the dispatch package, produce real assets under the run directory, then write `deck_generation_result.v2` files into `generation_results/`.

Each completed result must include run/session binding, run-relative paths, SHA-256 checksums, byte sizes, `source_fingerprint`, and `producer` metadata.
Bundled placeholder output is fixture/dev only and cannot be imported as production output.
