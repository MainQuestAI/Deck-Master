---
name: ppt-deck-pro-max
description: Deck Master bundled production intelligence capability for generation sessions, page production handoff, and generation result import with run_id plus session_id binding.
---

# PPT Deck Pro Max Capability

Use this capability for page production inside a Deck Master generation session.
Active run output must return through Deck Master generation-session import.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master generation-session status --run-dir <run_dir> --run-id <run_id>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master generation-session create --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master run-generation --run-dir <run_dir> --run-id <run_id> --dry-run
~/.deck-master/bin/deck-master generation-session import-results --run-dir <run_dir> --run-id <run_id> --input <result.json>
```
