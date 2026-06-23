---
name: deck-producer
description: Deck Master production entry for generation sessions, Agent dispatch packages, page production, and deck_generation_result.v2 import.
triggers:
  - produce deck pages
  - start generation session
  - import generation result
  - deck producer
---

# Deck Producer

Use this skill when sourcing decides pages need new production or adaptation.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master generation-session create --run-dir <run_dir>
~/.deck-master/bin/deck-master run-generation --run-dir <run_dir>
~/.deck-master/bin/deck-master generation-session dispatch --run-dir <run_dir>
~/.deck-master/bin/deck-master generation-session import-results --run-dir <run_dir> --input <result.json>
~/.deck-master/bin/deck-master refresh-preview-from-generation --run-dir <run_dir>
```

## Output Rule

Production results must return as canonical `deck_generation_result.v2` with
run/session binding, safe paths, checksums, and real artifacts.
