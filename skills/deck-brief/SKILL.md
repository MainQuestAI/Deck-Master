---
name: deck-brief
description: Deck Master briefing entry for turning raw materials, deep research reports, and meeting notes into customer-visible deck brief inputs.
triggers:
  - create deck brief
  - summarize deck materials
  - turn research into ppt brief
  - deck brief
---

# Deck Brief

Use this skill when the user provides source material and wants Deck Master to
extract the business problem, audience, claims, evidence, and deck intent.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master import-context-pack --run-dir <run_dir> --input <context_pack.json>
~/.deck-master/bin/deck-master build-brief --run-dir <run_dir>
~/.deck-master/bin/deck-master build-claim-map --run-dir <run_dir>
```

## Boundary

Keep internal production notes out of customer-visible content. Production notes
belong in source metadata, speaker notes, or internal planning fields.
