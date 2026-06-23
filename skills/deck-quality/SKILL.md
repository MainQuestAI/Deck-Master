---
name: deck-quality
description: Deck Master quality entry for draft, render, delivery, customer-visible safety, evidence, confidentiality, and brand gates.
triggers:
  - run deck quality gate
  - check customer visible safety
  - check delivery blockers
  - deck quality
---

# Deck Quality

Use this skill before client export or whenever a deck may contain internal
language, placeholder text, stale artifacts, or evidence issues.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master quality-gate draft --run-dir <run_dir>
~/.deck-master/bin/deck-master quality-gate customer-visible-safety --run-dir <run_dir> --artifact <pptx>
~/.deck-master/bin/deck-master quality-gate delivery --run-dir <run_dir> --artifact <pptx>
~/.deck-master/bin/deck-master import-quality-findings --run-dir <run_dir> --input <findings.json>
```

## Blocking Rule

P0 findings block client export. Internal export may be used only for repair and
must stay marked degraded.
