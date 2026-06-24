---
name: ppt-library
description: Deck Master bundled asset intelligence capability for historical slide search, candidate selection import, and run-local library feedback queue.
triggers:
  - search slide library
  - find historical slides
  - import library selection
  - record library feedback
  - ppt library
---

# PPT Library Compatibility Entry

This compatibility entry is kept for existing prompts and local installs.
For new Deck Master workflows, prefer `deck-sourcing`.

Use it for historical asset retrieval inside Deck Master. Active run output
must return through Deck Master sourcing state.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master library-status
~/.deck-master/bin/deck-master search-library --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master import-library-selection --run-dir <run_dir> --run-id <run_id> --input <selection.json>
~/.deck-master/bin/deck-master record-library-feedback --run-dir <run_dir> --run-id <run_id> --page-task-id <page> --beat-id <beat> --candidate-id <candidate> --outcome <outcome>
```


<!-- skill-os-contract:v1 -->
## Public Stage
Maps to public stage: deck-sourcing. This is a compatibility wrapper; prefer the public `deck-sourcing` skill for new runs.
