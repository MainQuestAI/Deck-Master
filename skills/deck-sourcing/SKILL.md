---
name: deck-sourcing
description: Deck Master sourcing entry for deciding which pages need historical assets, new production, evidence screenshots, or project-specific reference material.
triggers:
  - source deck assets
  - find reusable slides
  - search ppt library
  - decide page sourcing
---

# Deck Sourcing

Use this skill after page tasks exist and before new page production starts.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master search-library --run-dir <run_dir>
~/.deck-master/bin/deck-master import-library-selection --run-dir <run_dir> --input <selection.json>
~/.deck-master/bin/deck-master decide-sourcing --run-dir <run_dir>
~/.deck-master/bin/deck-master record-library-feedback --run-dir <run_dir> --page-task-id <page> --candidate-id <candidate> --outcome <outcome>
```

## Decision Rule

Use existing assets when they match the page claim, audience, visual pattern,
and evidence need. Send pages to production when reuse would weaken the story.
