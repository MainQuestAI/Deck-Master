---
name: ppt-master
description: Deck Master bundled build and render capability for producing run-local HTML render artifacts and canonical render results. Use inside a Deck Master run when a preview needs a delivery-oriented render handback.
---

# PPT Master Capability

PPT Master is the default Deck Master build and render capability. In an active
Deck Master run, every output must return through Deck Master import or state
update paths.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir> --run-id <run_id>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master render --run-dir <run_dir> --run-id <run_id> --format html --fixture-safe
~/.deck-master/bin/deck-master render-status --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --run-id <run_id> --input <render_result.json>
```

## Output Rule

The canonical v0.9.13 render result is
`render_results/render_result.json`. Legacy render result paths are accepted
only as import inputs and must be normalized into the canonical path.
