---
name: deck-builder
description: Deck Master build entry for producing delivery-oriented HTML, PDF, PNG, PPTX, artifact manifest, render result, and editability metadata through the PPT Master backend.
triggers:
  - build deck
  - render deck
  - export pptx artifact
  - deck builder
---

# Deck Builder

Use this skill after preview review and quality gate pass. Deck Builder is the
public Deck Master build entry. PPT Master is the backend dependency.

## First Checks

```bash
~/.deck-master/bin/deck-master suite-status --target codex --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master build prepare --run-dir <run_dir>
~/.deck-master/bin/deck-master build run --run-dir <run_dir>
~/.deck-master/bin/deck-master build status --run-dir <run_dir>
~/.deck-master/bin/deck-master render-status --run-dir <run_dir>
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
```

## Backend Rule

Production/client export requires the full PPT Master backend package. Internal
repair may continue with degraded status, but it cannot be marked deliverable.
