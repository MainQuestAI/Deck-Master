---
name: deck-autopilot
description: Deck Master workflow autopilot for advancing a run across init, brief, planning, sourcing, production, build, quality, review, and delivery checkpoints.
triggers:
  - run deck autopilot
  - continue deck workflow
  - make ppt from materials
  - deck autopilot
---

# Deck Autopilot

Use this skill when the user wants Deck Master to keep advancing the workflow
until a real blocker appears.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master workflow-autopilot --mode quick --run-dir <run_dir>
~/.deck-master/bin/deck-master workflow-autopilot --mode production --run-dir <run_dir>
~/.deck-master/bin/deck-master workflow-autopilot --mode repair --run-dir <run_dir>
~/.deck-master/bin/deck-master workflow-autopilot --mode review-only --run-dir <run_dir>
```

## Stop Conditions

Stop and report when material is missing, setup is blocked, Agent execution is
waiting, quality has P0 findings, final readiness is blocked, or export is ready.
