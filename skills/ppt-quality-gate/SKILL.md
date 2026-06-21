---
name: ppt-quality-gate
description: Deck Master bundled quality governance capability for fixture-safe quality findings, quality report import, and delivery blocking review.
triggers:
  - run deck quality review
  - import quality findings
  - check delivery blockers
  - ppt quality gate
---

# PPT Quality Gate Capability

Use this capability for structured quality review inside Deck Master. Active
run findings must be imported into Deck Master quality reports.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir> --run-id <run_id>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master quality-gate draft --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master import-quality-findings --run-dir <run_dir> --run-id <run_id> --input <findings.json>
```
