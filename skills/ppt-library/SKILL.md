---
name: ppt-library
description: Deck Master bundled asset intelligence capability for historical slide search, candidate selection import, and run-local library feedback queue.
---

# PPT Library Capability

Use this capability for historical asset retrieval inside Deck Master. Active
run output must return through Deck Master sourcing state.

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
