---
name: deck-learn
description: Deck Master learning entry for delivery outcomes, reusable asset feedback, benchmark results, and workspace learning packs.
triggers:
  - record deck feedback
  - build learning pack
  - record delivery outcome
  - deck learn
---

# Deck Learn

Use this optional skill after review, delivery, or benchmark completion.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master record-library-feedback --run-dir <run_dir> --apply
~/.deck-master/bin/deck-master delivery record-outcome --run-dir <run_dir>
~/.deck-master/bin/deck-master build-learning-pack --workspace <workspace>
~/.deck-master/bin/deck-master show-learning-pack --workspace <workspace>
```

## Output Rule

Learning output must stay in the workspace and avoid customer secrets, keys,
raw private documents, or build caches.
